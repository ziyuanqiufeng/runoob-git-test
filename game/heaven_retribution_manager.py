# -*- coding: utf-8 -*-
"""
维度④ 天道反噬与生态平衡（F-08）。

设计边界：
- 与 difficulty_manager 的「天道追杀」（突破大境界触发）严格区分：
  本模块的「天道注视」由「战力 / 财富短时间指数级暴涨」触发。
- 「灵脉枯竭」由领地过度抽取灵气（聚灵塔 / 坊市等 spirit_stone 产出）超过品阶承载力触发。

全部为加法式接入，不改动引擎核心修炼数学。状态保存在 player 上：
- player.heaven_gaze       天道注视值 0-100
- territory["depletion"]   单块领地的灵脉枯竭度 0-100
"""

import json
import os
import random


class HeavenRetributionConfig:
    """加载维度④配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "heaven_retribution.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_depletion(self):
        return self.data.get("spirit_vein_depletion", {})

    def get_gaze(self):
        return self.data.get("heaven_gaze", {})

    def get_tier_capacity(self, tier):
        return int(self.get_depletion().get("tier_capacity", {}).get(tier, 200))

    def get_gaze_levels(self):
        return self.get_gaze().get("levels", {})

    def get_relief(self):
        return self.get_gaze().get("relief", {})

    def get_retribution_events(self):
        return self.data.get("retribution_events", [])


class HeavenRetributionManager:
    """天道反噬：灵脉枯竭 + 天道注视。"""

    def __init__(self, player, config_dir="config", notify_callback=None):
        self.player = player
        self.config = HeavenRetributionConfig(config_dir)
        self.notify = notify_callback or (lambda x: None)

    # ---------------- 状态读写（持久化在 player 上） ----------------
    def _gaze(self):
        return getattr(self.player, "heaven_gaze", 0) or 0

    def _set_gaze(self, value):
        cap = self.config.get_gaze().get("max", 100)
        self.player.heaven_gaze = max(0, min(cap, int(round(value))))

    # ---------------- 数值代理 ----------------
    def estimate_power(self, player=None):
        """战力代理：境界层级为主，修为为辅。"""
        p = player or self.player
        order = getattr(p, "REALM_ORDER", {}).get(getattr(p, "realm_id", ""), 1)
        return order * 1000 + int(getattr(p, "qi", 0) or 0)

    def estimate_wealth(self, player=None):
        """财富代理：私库灵石 + 各领地金库。"""
        p = player or self.player
        stone = p.count_item("spirit_stone") if hasattr(p, "count_item") else 0
        terr = getattr(p, "territory", None)
        treasuries = 0
        for t in self._iter_territories(terr):
            treasuries += int(t.get("treasury", 0) or 0)
        return stone + treasuries

    @staticmethod
    def _iter_territories(terr):
        if terr is None:
            return []
        if isinstance(terr, dict):
            return [terr]
        if isinstance(terr, list):
            return terr
        return []

    # ---------------- 灵脉枯竭 ----------------
    def check_territory_depletion(self, territory, monthly_extraction):
        """领地月度结算后调用：比对灵气抽取与承载力，调整枯竭度。

        返回 (depletion_level, monster_triggered)。
        """
        if not isinstance(territory, dict):
            return 0, False
        tier = territory.get("tier", "spirit_vein")
        cap = self.config.get_tier_capacity(tier)
        cfg = self.config.get_depletion()
        depletion = int(territory.get("depletion", 0) or 0)

        excess = max(0, monthly_extraction - cap)
        if excess > 0:
            depletion += excess * cfg.get("gain_per_excess_unit", 0.05)
        else:
            depletion -= cfg.get("recover_per_month", 2.0)
        depletion = max(0, min(cfg.get("max", 100), depletion))
        territory["depletion"] = int(round(depletion))

        monster_triggered = False
        if depletion >= cfg.get("max", 100):
            if random.random() < cfg.get("monster_chance_at_full", 0.3):
                monster_triggered = True
        return int(round(depletion)), monster_triggered

    def territory_output_multiplier(self, territory):
        """枯竭满值时产出倍率（用于领地结算时乘算）。"""
        if not isinstance(territory, dict):
            return 1.0
        cfg = self.config.get_depletion()
        depletion = int(territory.get("depletion", 0) or 0)
        if depletion <= 0:
            return 1.0
        if depletion >= cfg.get("max", 100):
            return float(cfg.get("output_multiplier_at_full", 0.0))
        # 线性衰减
        return 1.0 - (1.0 - cfg.get("output_multiplier_at_full", 0.0)) * (depletion / cfg.get("max", 100))

    # ---------------- 天道注视 ----------------
    def on_power_spike(self, amount=None):
        """战力暴涨时调用。amount 为本次增量，未提供则用代理值比较。"""
        if amount is None:
            amount = self.estimate_power()  # 调用方应传增量；此处兜底
        if amount >= self.config.get_gaze().get("power_spike_min", 500):
            self._add_gaze(self.config.get_gaze().get("gaze_per_spike", 15))
            return True
        return False

    def on_wealth_spike(self, before, after):
        """财富暴涨（如黑市倒卖、秘境刷宝）时调用。"""
        mult = self.config.get_gaze().get("wealth_spike_multiplier", 1.5)
        if before > 0 and after >= before * mult:
            self._add_gaze(self.config.get_gaze().get("gaze_per_spike", 15))
            return True
        return False

    def _add_gaze(self, value):
        self._set_gaze(self._gaze() + value)
        self.notify(
            f"[red]天道注视 +{value}（当前 {self._gaze()}）：你之造化已惊动上苍。"
        )

    def tick_monthly(self):
        """月度自然衰减注视值。"""
        if self._gaze() > 0:
            self._set_gaze(self._gaze() - self.config.get_gaze().get("decay_per_month", 3))

    def get_gaze_level(self):
        """返回当前注视等级键名：None/low/mid/high。"""
        g = self._gaze()
        if g <= 0:
            return None
        best = "low"
        for key, spec in self.config.get_gaze_levels().items():
            if g >= spec.get("threshold", 999):
                best = key
        return best

    def roll_travel_hazard(self, engine):
        """游历时按注视等级掷无妄之灾 / 杀人夺宝。返回日志列表。"""
        level = self.get_gaze_level()
        if not level:
            return []
        spec = self.config.get_gaze_levels().get(level, {})
        logs = []
        rng = random
        if rng.random() < spec.get("misfortune", 0.0):
            logs.append("[red]无妄之灾！天道注视之下，你途中陡生变故。")
        if rng.random() < spec.get("kill_for_treasure", 0.0):
            logs.append("[red]杀人夺宝！一名高阶修士循着你身上的气运杀来！")
            if hasattr(engine, "start_combat") and hasattr(engine, "enemy_library"):
                enemy = self._spawn_robber(engine)
                if enemy:
                    engine.start_combat(enemy)
        # 天道反噬事件池：高注视外出按等级概率触发其一
        logs.extend(self.roll_retribution_event(engine, rng))
        return logs

    def get_event_chance_for_level(self, level):
        """返回该注视等级触发反噬事件的概率（缺失则 0）。"""
        return float(self.config.get_gaze_levels().get(level, {}).get("retribution_event_chance", 0.0))

    def roll_retribution_event(self, engine=None, rng=None):
        """按当前注视等级掷一次天道反噬事件。返回日志列表（空表示未触发）。

        事件由 config.retribution_events 提供，按 min_gaze 阈值筛选当前注视
        可达者，再按 weight 加权抽取其一并施加 effects（修为折损 / 灵石损失 /
        道心波动 / 心魔波动 / 召来追夺者开战）。纯加法，不改动引擎核心。
        """
        level = self.get_gaze_level()
        if not level:
            return []
        rng = rng or random
        chance = self.get_event_chance_for_level(level)
        if chance <= 0 or rng.random() >= chance:
            return []
        gaze = self._gaze()
        eligible = [e for e in self.config.get_retribution_events()
                    if isinstance(e, dict) and int(e.get("min_gaze", 1)) <= gaze]
        if not eligible:
            return []
        # 按 weight 加权抽取（仅用 rng.random()，避免依赖 rng.choice）
        total = sum(float(e.get("weight", 1)) for e in eligible)
        pick = rng.random() * total
        chosen = eligible[-1]
        acc = 0.0
        for e in eligible:
            acc += float(e.get("weight", 1))
            if pick <= acc:
                chosen = e
                break
        return self._apply_retribution_event(chosen, engine)

    def _apply_retribution_event(self, event, engine):
        """施加单个反噬事件的效果并返回日志。"""
        eff = event.get("effects", {}) or {}
        parts = []
        p = self.player
        if "qi_loss" in eff:
            loss = int(eff["qi_loss"])
            before = int(getattr(p, "qi", 0) or 0)
            p.qi = max(0, before - loss)
            parts.append(f"修为 -{min(loss, before)}")
        if "stone_loss" in eff:
            loss = int(eff["stone_loss"])
            have = p.count_item("spirit_stone") if hasattr(p, "count_item") else 0
            lose = min(loss, have)
            if lose > 0 and hasattr(p, "consume_items"):
                p.consume_items("spirit_stone", lose)
            parts.append(f"灵石 -{lose}")
        if "mental_delta" in eff:
            d = int(eff["mental_delta"])
            ms = int(getattr(p, "mental_state", 50) or 50)
            p.mental_state = max(0, min(100, ms + d))
            parts.append(f"道心 {d:+d}")
        if "heart_delta" in eff:
            d = int(eff["heart_delta"])
            hd = int(getattr(p, "heart_demon", 0) or 0)
            p.heart_demon = max(0, min(100, hd + d))
            parts.append(f"心魔 {d:+d}")
        log = f"[red]天道反噬·{event.get('name', '未知')}：{event.get('desc', '')}"
        if parts:
            log += f"（{'; '.join(parts)}）"
        if eff.get("spawn_enemy") and engine is not None:
            if hasattr(engine, "start_combat") and hasattr(engine, "enemy_library"):
                enemy = self._spawn_robber(engine)
                if enemy:
                    engine.start_combat(enemy)
        self.notify(log)
        return [log]

    def _spawn_robber(self, engine):
        """生成一个比玩家略强的高阶修士作为杀人夺宝者。"""
        try:
            enemies = list(engine.enemy_library.values()) if hasattr(engine.enemy_library, "values") else []
            if not enemies:
                return None
            # 取战力代理最高的若干里随机一个，作为追夺者
            enemies.sort(key=lambda e: getattr(e, "power", getattr(e, "level", 0) or 0), reverse=True)
            return enemies[min(2, len(enemies) - 1)]
        except Exception:
            return None

    def is_trade_refused(self):
        """坊市 NPC 是否因注视而拒绝交易。"""
        level = self.get_gaze_level()
        if not level:
            return False
        chance = self.config.get_gaze_levels().get(level, {}).get("trade_refuse", 0.0)
        return random.random() < chance

    def relieve(self, method):
        """消除天道注视：donate / good_deed / seclude。"""
        amount = self.config.get_relief().get(method, 0)
        if amount:
            self._set_gaze(self._gaze() - amount)
            self.notify(f"[cyan]你以「{method}」消弭天道注视 -{amount}（当前 {self._gaze()}）。")
            return True
        return False

    def get_status(self):
        """供 UI 展示。"""
        gaze = self._gaze()
        eligible = [
            {"id": e.get("id", "unknown"), "name": e.get("name", "未知"), "desc": e.get("desc", "")}
            for e in self.config.get_retribution_events()
            if isinstance(e, dict) and int(e.get("min_gaze", 1)) <= gaze
        ]
        return {
            "gaze": gaze,
            "gaze_level": self.get_gaze_level(),
            "relief_methods": list(self.config.get_relief().keys()),
            "eligible_events": eligible,
            "event_chance": self.get_event_chance_for_level(self.get_gaze_level() or "low"),
        }
