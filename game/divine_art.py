# -*- coding: utf-8 -*-
"""神通/法则系统：高境界修士消耗悟道点领悟强力被动。"""
import json
import os


class DivineArtConfig:
    """加载神通配置。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._arts = {}
        self._load()

    def _load(self):
        path = os.path.join(self.config_dir, "divine_arts.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            self._arts[entry["id"]] = entry

    def get(self, art_id):
        return self._arts.get(art_id)

    def get_all(self):
        return list(self._arts.values())


class DivineArtManager:
    """管理神通领悟与效果。"""

    def __init__(self, player, config_dir="config"):
        self.player = player
        self.config = DivineArtConfig(config_dir)
        if not hasattr(player, "divine_arts"):
            player.divine_arts = []
        if not hasattr(player, "enlightenment_points"):
            player.enlightenment_points = 0

    def can_learn(self, art_id):
        art = self.config.get(art_id)
        if not art:
            return False, "未知神通。"
        if art_id in self.player.divine_arts:
            return False, "已领悟该神通。"
        order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
        if order < art.get("unlock_realm_order", 999):
            return False, "境界不足。"
        exclusive = art.get("exclusive_path")
        if exclusive and self.player.cultivation_path != exclusive:
            return False, "流派不匹配。"
        cost = art.get("cost", {}).get("enlightenment_points", 0)
        if self.player.enlightenment_points < cost:
            return False, f"悟道点不足（需要 {cost}）。"
        return True, ""

    def learn(self, art_id):
        ok, msg = self.can_learn(art_id)
        if not ok:
            return False, msg
        art = self.config.get(art_id)
        cost = art.get("cost", {}).get("enlightenment_points", 0)
        self.player.enlightenment_points -= cost
        self.player.divine_arts.append(art_id)
        return True, f"领悟神通【{art['name']}】！"

    def get_effects(self):
        """汇总所有已领悟神通的效果。"""
        merged = {}
        for art_id in self.player.divine_arts:
            art = self.config.get(art_id)
            if not art:
                continue
            for key, value in art.get("effects", {}).items():
                if key in merged and isinstance(value, dict):
                    for sub_key, sub_val in value.items():
                        merged[key][sub_key] = merged[key].get(sub_key, 0) + sub_val
                elif key == "element_damage":
                    merged.setdefault(key, {})
                    for sub_key, sub_val in value.items():
                        merged[key][sub_key] = merged[key].get(sub_key, 0) + sub_val
                else:
                    merged[key] = merged.get(key, 0) + value
        return merged

    def get_element_damage_bonus(self, element):
        bonuses = self.get_effects().get("element_damage", {})
        return bonuses.get(element, 0.0)

    def get_heal_bonus_mult(self):
        return self.get_effects().get("heal_bonus_mult", 0.0)

    def get_ignore_defense_ratio(self):
        return self.get_effects().get("ignore_defense_ratio", 0.0)

    def get_paralyze_chance(self):
        return self.get_effects().get("paralyze_chance", 0.0)
