# -*- coding: utf-8 -*-
"""全局世界状态管理（F-04 新增）。

维护影响全局游戏状态的变量（灵气浓度 / 安全度 / 物价系数 / NPC 阵营态度 / 魔气浓度），
并提供灵气潮汐的周期性全局 buff/debuff。

所有状态持久化在 player.world_state，随存档自然保存；旧存档缺字段时由
Player.from_save 的默认值兜底，保证向后兼容。

设计要点：
- 状态读写带上下界钳制；
- 事件链效果以 (key, applied_delta) 形式记录，便于到期精确回滚；
- tick_monthly 作为引擎月度结算插座的注册回调，仅做灵气潮汐推进。
"""
import math


# 全局状态变量定义：键 -> (默认值, 最小值, 最大值)
DEFAULT_STATE = {
    "lingqi": (100.0, 0.0, 300.0),       # 灵气浓度基准（相对 100 为常态）
    "safety": (100.0, 0.0, 200.0),       # 世界安全度
    "price_index": (100.0, 20.0, 400.0),  # 全局物价系数（*100）
    "npc_mood": (50.0, 0.0, 100.0),      # NPC 阵营态度
    "dark_qi": (0.0, 0.0, 100.0),        # 魔气浓度
}

TIDE_PERIOD = 24  # 灵气潮汐周期（月）


class WorldStateManager:
    """全局世界状态管理器。"""

    def __init__(self, player, config_dir="config", notify_callback=None):
        self.player = player
        self.config_dir = config_dir
        self.notify = notify_callback or (lambda x: None)
        # 状态字典（首次访问时初始化默认值，旧存档缺字段则补默认）
        if not hasattr(player, "world_state") or not isinstance(
            getattr(player, "world_state", None), dict
        ):
            player.world_state = {}
        self.state = player.world_state
        self._ensure_defaults()
        if "tide_phase" not in self.state:
            self.state["tide_phase"] = 0
        if "active_modifiers" not in self.state:
            self.state["active_modifiers"] = []

    def _ensure_defaults(self):
        for key, (default, lo, hi) in DEFAULT_STATE.items():
            if key not in self.state:
                self.state[key] = default
            else:
                self.state[key] = max(lo, min(hi, float(self.state[key])))

    # ==================== 基础读写 ====================

    def get(self, key, default=None):
        return self.state.get(key, default)

    def get_all(self):
        return dict(self.state)

    def set(self, key, value):
        lo, hi = self._bounds(key)
        self.state[key] = max(lo, min(hi, float(value)))

    def modify(self, key, delta):
        self.set(key, self.get(key, 0) + delta)

    def _bounds(self, key):
        if key in DEFAULT_STATE:
            return DEFAULT_STATE[key][1], DEFAULT_STATE[key][2]
        return float("-inf"), float("inf")

    # ==================== 事件链效果应用 / 回滚 ====================

    @staticmethod
    def _resolve_delta(current, value):
        """value 可为数字（绝对增量）或 '+30%' / '-10%'（百分比刻度上的 +30 / -10 点）。

        说明：灵气/安全度/物价/阵营态度/魔气均为 0-100 或基准 100 的刻度，
        '+30%' 按游戏直觉理解为 +30 个百分点，而非相对当前值的 30%。
        """
        if isinstance(value, str):
            v = value.strip()
            if v.endswith("%"):
                return float(v[:-1])
            return float(v)
        return float(value)

    def apply_global_effect(self, key, value):
        """应用一个全局效果，返回 (key, applied_delta) 供回滚。"""
        before = float(self.get(key, 0.0))
        lo, hi = self._bounds(key)
        target = before + self._resolve_delta(before, value)
        after = max(lo, min(hi, target))
        applied = after - before
        self.state[key] = after
        return (key, applied)

    def apply_effects(self, effects):
        """批量应用效果，返回 applied 列表（用于回滚）。"""
        applied = []
        for key, val in (effects or {}).items():
            applied.append(self.apply_global_effect(key, val))
        return applied

    def revert_effects(self, applied_list):
        for key, delta in applied_list:
            self.modify(key, -delta)

    # ==================== 灵气潮汐 ====================

    def tick_tides(self):
        """推进灵气潮汐相位，并据相位缓慢牵引灵气浓度。"""
        phase = int(self.state.get("tide_phase", 0))
        phase = (phase + 1) % TIDE_PERIOD
        self.state["tide_phase"] = phase
        base = DEFAULT_STATE["lingqi"][0]
        wave = math.sin(2 * math.pi * phase / TIDE_PERIOD) * 15.0
        target = base + wave
        cur = float(self.get("lingqi", base))
        # 平滑移动灵气浓度向 target 靠拢
        self.set("lingqi", cur + (target - cur) * 0.2)

    def tide_multiplier(self):
        """灵气潮汐对修炼 / 灵植 / 妖兽的倍率（0.8~1.2）。"""
        phase = int(self.state.get("tide_phase", 0))
        return 1.0 + 0.2 * math.sin(2 * math.pi * phase / TIDE_PERIOD)

    def cultivation_multiplier(self):
        """综合灵气浓度与潮汐对修炼速度的影响。"""
        lingqi_factor = self.get("lingqi", 100.0) / 100.0
        return max(0.5, min(2.0, lingqi_factor)) * self.tide_multiplier()

    def herb_growth_multiplier(self):
        return max(0.3, self.get("lingqi", 100.0) / 100.0)

    def beast_activity_multiplier(self):
        """魔气越高、安全度越低，妖兽越活跃。"""
        dark = self.get("dark_qi", 0.0) / 100.0
        safety = self.get("safety", 100.0) / 100.0
        return max(0.5, min(2.5, 1.0 + dark * 0.8 - (safety - 1.0) * 0.3))

    # ==================== 月度结算入口（引擎插座） ====================

    def tick_monthly(self):
        self.tick_tides()

    # ==================== UI 展示 ====================

    def summary(self):
        return {
            "lingqi": round(self.get("lingqi"), 1),
            "safety": round(self.get("safety"), 1),
            "price_index": round(self.get("price_index"), 1),
            "npc_mood": round(self.get("npc_mood"), 1),
            "dark_qi": round(self.get("dark_qi"), 1),
            "tide_phase": self.state.get("tide_phase", 0),
            "tide_multiplier": round(self.tide_multiplier(), 3),
        }
