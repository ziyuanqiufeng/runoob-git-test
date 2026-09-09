# -*- coding: utf-8 -*-
"""
城池建筑解锁与升级管理器。
每个建筑有多个等级，升级需要满足境界与城池声望，并消耗材料。
"""

import json
import os


class BuildingManager:
    """管理建筑等级配置与玩家建筑等级状态。"""

    def __init__(self, player, world, config_dir="config"):
        self.player = player
        self.world = world
        path = os.path.join(config_dir, "building_unlocks.json")
        with open(path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def get_building_level(self, building_id):
        """获取某建筑的当前等级（默认为 1）。"""
        return self.player.building_levels.get(building_id, 1)

    def get_building_config(self, building_id):
        """获取某建筑的完整配置。"""
        return self.config.get(building_id, {})

    def get_level_config(self, building_id, level):
        """获取某建筑指定等级的配置。"""
        building = self.config.get(building_id, {})
        for lv in building.get("levels", []):
            if lv.get("level") == level:
                return lv
        return None

    def get_max_level(self, building_id):
        """获取某建筑的最高等级。"""
        levels = self.config.get(building_id, {}).get("levels", [])
        return max((lv.get("level", 1) for lv in levels), default=1)

    def get_current_effects(self, building_id):
        """获取某建筑当前等级的效果。"""
        level = self.get_building_level(building_id)
        level_cfg = self.get_level_config(building_id, level)
        return level_cfg.get("effects", {}) if level_cfg else {}

    def get_city_reputation(self, city_id):
        """获取玩家在某城池的声望。"""
        return self.player.city_reputation.get(city_id, 0)

    def gain_city_reputation(self, city_id, amount):
        """增加玩家在某城池的声望。"""
        current = self.player.city_reputation.get(city_id, 0)
        self.player.city_reputation[city_id] = max(0, current + amount)

    def get_reputation_level(self, city_id):
        """根据声望值返回声望等级名称。"""
        rep = self.get_city_reputation(city_id)
        if rep >= 600:
            return "崇拜"
        if rep >= 300:
            return "尊敬"
        if rep >= 100:
            return "友善"
        return "陌生"

    def can_upgrade(self, building_id, city_id):
        """
        判断某建筑是否可以升级。
        返回 (bool, reason)，reason 为空表示可以升级。
        """
        current_level = self.get_building_level(building_id)
        max_level = self.get_max_level(building_id)
        if current_level >= max_level:
            return False, "该建筑已达最高等级。"

        next_level_cfg = self.get_level_config(building_id, current_level + 1)
        if not next_level_cfg:
            return False, "下一级配置缺失。"

        # 检查境界
        required_order = next_level_cfg.get("required_realm_order", 1)
        current_order = self._get_current_realm_order()
        if current_order < required_order:
            required_name = self._get_realm_name_by_order(required_order)
            return False, f"需要境界：{required_name}"

        # 检查城池声望
        required_rep = next_level_cfg.get("required_reputation", 0)
        current_rep = self.get_city_reputation(city_id)
        if current_rep < required_rep:
            return False, f"需要城池声望：{required_rep}（当前 {current_rep}）"

        # 检查消耗材料
        cost = next_level_cfg.get("cost", {})
        for item_id, count in cost.items():
            if self.player.count_item(item_id) < count:
                return False, f"材料不足：{item_id} x{count}"

        return True, ""

    def upgrade_building(self, building_id, city_id):
        """升级指定建筑，扣除消耗。返回 (bool, message)。"""
        ok, reason = self.can_upgrade(building_id, city_id)
        if not ok:
            return False, reason

        current_level = self.get_building_level(building_id)
        next_level_cfg = self.get_level_config(building_id, current_level + 1)
        cost = next_level_cfg.get("cost", {})

        # 扣除材料
        for item_id, count in cost.items():
            self.player.consume_items(item_id, count)

        # 升级
        self.player.building_levels[building_id] = current_level + 1
        return True, f"【{building_id}】升级至 {current_level + 1} 级！"

    def _get_current_realm_order(self):
        """获取玩家当前境界 order。"""
        realm = self.world.get_realm(self.player.realm_id)
        return realm.get("order", 1) if realm else 1

    def _get_realm_name_by_order(self, order):
        """根据境界 order 查找境界名称。"""
        for rid, rdata in self.world.realms.items():
            if rdata.get("order") == order:
                return rdata.get("name", rid)
        return "未知境界"
