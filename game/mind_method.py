# -*- coding: utf-8 -*-
"""心法系统：提供被动修炼与战斗加成。"""
import json
import os


class MindMethodConfig:
    """加载并查询心法配置。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._methods = {}
        self._load()

    def _load(self):
        path = os.path.join(self.config_dir, "mind_methods.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            self._methods[entry["id"]] = entry

    def get(self, method_id):
        return self._methods.get(method_id)

    def get_all(self):
        return list(self._methods.values())

    def can_learn(self, method_id, player):
        """判断玩家是否满足学习条件。"""
        method = self.get(method_id)
        if not method:
            return False
        order = player.REALM_ORDER.get(player.realm_id, 0)
        if order < method.get("unlock_realm_order", 1):
            return False
        exclusive = method.get("exclusive_path")
        if exclusive and player.cultivation_path != exclusive:
            return False
        # 同属性心法需拥有对应灵根（none 属性不限），支持融合灵根展开
        element = method.get("element", "none")
        if element != "none" and not player.has_element(element):
            return False
        return True


class MindMethodManager:
    """管理玩家已学心法和装备心法的加成计算。"""

    def __init__(self, player, config_dir="config"):
        self.player = player
        self.config = MindMethodConfig(config_dir)

    def learn(self, method_id):
        """学习心法，成功返回 (True, msg)。"""
        if method_id in self.player.learned_mind_methods:
            return False, "你已经学过这门心法。"
        if not self.config.can_learn(method_id, self.player):
            return False, "你当前境界或流派不满足学习条件。"
        self.player.learned_mind_methods.append(method_id)
        return True, f"领悟心法【{self.config.get(method_id)['name']}】。"

    def equip(self, method_id):
        """装备心法。"""
        if method_id not in self.player.learned_mind_methods:
            return False, "尚未学习该心法。"
        self.player.equipped_mind_method = method_id
        return True, f"装备心法【{self.config.get(method_id)['name']}】。"

    def unequip(self):
        """卸下心法。"""
        if not self.player.equipped_mind_method:
            return False, "当前未装备心法。"
        self.player.equipped_mind_method = None
        return True, "已卸下心法。"

    def _get_effects(self):
        """获取当前装备心法的 effects 字典。"""
        mid = getattr(self.player, "equipped_mind_method", None)
        if not mid:
            return {}
        method = self.config.get(mid)
        return method.get("effects", {}) if method else {}

    def get_cultivation_speed_bonus(self):
        return self._get_effects().get("cultivation_speed", 0.0)

    def get_breakthrough_bonus(self):
        return self._get_effects().get("breakthrough_bonus", 0.0)

    def get_attack_mult_bonus(self):
        return self._get_effects().get("attack_mult", 0.0)

    def get_crit_rate_bonus(self):
        return self._get_effects().get("crit_rate_bonus", 0.0)

    def get_heal_bonus_mult(self):
        return self._get_effects().get("heal_bonus_mult", 0.0)

    def get_element_damage_bonus(self, element):
        bonuses = self._get_effects().get("element_damage", {})
        return bonuses.get(element, 0.0)

    def get_mental_state_recovery(self):
        return self._get_effects().get("mental_state_recovery", 0)

    def get_heart_demon_decay_bonus(self):
        return self._get_effects().get("heart_demon_decay_bonus", 0.0)

    def get_heart_demon_growth(self):
        return self._get_effects().get("heart_demon_growth", 0)

    def get_alchemy_success_bonus(self):
        return self._get_effects().get("alchemy_success", 0.0)
