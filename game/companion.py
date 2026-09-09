# -*- coding: utf-8 -*-
"""道侣系统。

玩家可与 NPC 结为道侣，通过双修提升修为与好感，道侣还能在战斗中提供属性加成。
"""

import json
import os


class CompanionConfig:
    """道侣系统配置加载器。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "companions.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_max_companions(self):
        return self.data.get("max_companions", 1)

    def get_requirements(self):
        return self.data.get("requirements", {})

    def get_dual_cultivation(self):
        return self.data.get("dual_cultivation", {})

    def get_intimacy_levels(self):
        return self.data.get("intimacy_levels", [])

    def get_battle_bonus(self):
        return self.data.get("battle_bonus", {})

    def get_death_event(self):
        return self.data.get("events", {}).get("on_death", {})


class CompanionManager:
    """道侣管理器。"""

    def __init__(self, player, world, npc_library=None, config=None):
        self.player = player
        self.world = world
        self.npc_library = npc_library
        self.config = config or CompanionConfig()

    def _get_companion(self, npc_id):
        """获取指定 NPC 的道侣记录，若不存在返回 None。"""
        for companion in self.player.companions:
            if companion.get("npc_id") == npc_id:
                return companion
        return None

    def _get_npc(self, npc_id):
        """从 NPC 库获取 NPC 数据。"""
        if not self.npc_library:
            return None
        # 兼容两种 NPC 库存储方式：dict 或 list
        if isinstance(self.npc_library, dict):
            return self.npc_library.get(npc_id)
        if hasattr(self.npc_library, "get"):
            return self.npc_library.get(npc_id)
        return None

    def get_npc_favor(self, npc_id):
        """获取玩家对指定 NPC 的好感度。"""
        return self.player.npc_relationships.get(npc_id, 0)

    def can_form_companion(self, npc_id):
        """检查是否满足结为道侣条件。"""
        npc = self._get_npc(npc_id)
        if not npc:
            return False, "NPC 不存在。"
        if self._get_companion(npc_id):
            return False, "该 NPC 已是你的道侣。"
        if len(self.player.companions) >= self.config.get_max_companions():
            return False, f"道侣数量已达上限 {self.config.get_max_companions()}。"

        req = self.config.get_requirements()
        favor = self.get_npc_favor(npc_id)
        if favor < req.get("min_favor", 10):
            return False, f"好感度不足，需要达到 {req.get('min_favor', 10)}。"

        min_realm_order = req.get("min_realm_order", 0)
        if self.player.REALM_ORDER.get(self.player.realm_id, 0) < min_realm_order:
            return False, "境界不足，无法结为道侣。"

        return True, ""

    def _get_npc_name(self, npc):
        """兼容 dict 与 NPC 对象两种形式的名称读取。"""
        if isinstance(npc, dict):
            return npc.get("name", "未知")
        return getattr(npc, "name", "未知")

    def form_companion(self, npc_id):
        """与 NPC 结为道侣。"""
        ok, msg = self.can_form_companion(npc_id)
        if not ok:
            return False, msg
        npc = self._get_npc(npc_id)
        name = self._get_npc_name(npc)
        self.player.companions.append({
            "npc_id": npc_id,
            "name": name,
            "intimacy": 0,
            "is_alive": True,
            "last_dual_month": -999,
        })
        return True, f"你与【{name}】结为道侣，愿同修大道。"

    def can_dual_cultivate(self, npc_id):
        """检查是否可以与道侣双修。"""
        companion = self._get_companion(npc_id)
        if not companion:
            return False, "该 NPC 不是你的道侣。"
        if not companion.get("is_alive", True):
            return False, "道侣已逝，无法双修。"
        dual_cfg = self.config.get_dual_cultivation()
        cooldown = dual_cfg.get("cooldown_months", 3)
        elapsed = (self.world.year - 1) * 12 + self.world.month - companion.get("last_dual_month", -999)
        if elapsed < cooldown:
            return False, f"双修冷却中，还需 {cooldown - elapsed} 个月。"
        return True, ""

    def dual_cultivate(self, npc_id):
        """与道侣双修，增加修为、道心，降低心魔，提升亲密度。"""
        ok, msg = self.can_dual_cultivate(npc_id)
        if not ok:
            return False, msg
        companion = self._get_companion(npc_id)
        dual_cfg = self.config.get_dual_cultivation()
        qi_gain = dual_cfg.get("qi_gain_base", 100)
        qi_gain += dual_cfg.get("qi_gain_per_intimacy", 0) * companion.get("intimacy", 0)
        mental_gain = dual_cfg.get("mental_state_gain", 0)
        heart_decay = dual_cfg.get("heart_demon_decay", 0)

        self.player.qi += qi_gain
        self.player.mental_state = min(100, self.player.mental_state + mental_gain)
        self.player.heart_demon = max(0, self.player.heart_demon - heart_decay)
        companion["intimacy"] = min(100, companion.get("intimacy", 0) + 5)
        companion["last_dual_month"] = (self.world.year - 1) * 12 + self.world.month
        return True, f"双修结束，修为 +{qi_gain}，亲密度 +5。"

    def get_intimacy_level_name(self, intimacy):
        """根据亲密度获取等级名称。"""
        levels = self.config.get_intimacy_levels()
        matched = levels[0]["name"] if levels else ""
        for level in levels:
            if intimacy >= level.get("min", 0):
                matched = level["name"]
        return matched

    def get_battle_bonus(self):
        """获取所有在世道侣提供的战斗属性加成。"""
        total_attack = 0.0
        total_defense = 0.0
        bonus_cfg = self.config.get_battle_bonus()
        for companion in self.player.companions:
            if not companion.get("is_alive", True):
                continue
            intimacy = companion.get("intimacy", 0)
            atk = min(
                bonus_cfg.get("max_attack_bonus", 0.0),
                intimacy * bonus_cfg.get("attack_per_intimacy", 0.0),
            )
            defense = min(
                bonus_cfg.get("max_defense_bonus", 0.0),
                intimacy * bonus_cfg.get("defense_per_intimacy", 0.0),
            )
            total_attack += atk
            total_defense += defense
        return total_attack, total_defense

    def on_companion_death(self, npc_id, killer_enemy_id=None):
        """道侣死亡时触发惩罚与复仇任务标记。"""
        companion = self._get_companion(npc_id)
        if not companion or not companion.get("is_alive", True):
            return None
        companion["is_alive"] = False
        death_cfg = self.config.get_death_event()
        mental_loss = death_cfg.get("mental_state_loss", 0)
        heart_gain = death_cfg.get("heart_demon_gain", 0)
        self.player.mental_state = max(0, self.player.mental_state - mental_loss)
        self.player.heart_demon = min(100, self.player.heart_demon + heart_gain)
        return {
            "npc_id": npc_id,
            "mental_state_loss": mental_loss,
            "heart_demon_gain": heart_gain,
            "revenge_quest_id": death_cfg.get("revenge_quest_id"),
            "killer_enemy_id": killer_enemy_id,
        }

    def increase_intimacy(self, npc_id, amount):
        """增加指定道侣的亲密度。"""
        companion = self._get_companion(npc_id)
        if not companion:
            return False
        companion["intimacy"] = min(100, companion.get("intimacy", 0) + amount)
        return True

    def get_alive_companions(self):
        """获取所有在世的道侣。"""
        return [c for c in self.player.companions if c.get("is_alive", True)]
