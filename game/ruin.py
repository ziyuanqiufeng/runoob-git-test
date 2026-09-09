# -*- coding: utf-8 -*-
"""上古遗迹探索系统。"""
import json
import os

from game.enemy import Enemy


class RuinConfig:
    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._ruins = {}
        self._load()

    def _load(self):
        path = os.path.join(self.config_dir, "ruins.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            self._ruins[entry["id"]] = entry

    def get(self, ruin_id):
        return self._ruins.get(ruin_id)

    def get_all(self):
        return list(self._ruins.values())


class RuinManager:
    """管理遗迹解锁、冷却与探索阶段。"""

    def __init__(self, player, enemy_library, item_library, world, config_dir="config"):
        self.player = player
        self.enemy_library = enemy_library
        self.item_library = item_library
        self.world = world
        self.config = RuinConfig(config_dir)

    def can_explore(self, ruin_id):
        ruin = self.config.get(ruin_id)
        if not ruin:
            return False, "遗迹不存在。"
        order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
        if order < ruin.get("min_realm_order", 1):
            return False, "境界不足。"
        last = self.player.explored_ruins.get(ruin_id, -999)
        current = self.world_month()
        cooldown = ruin.get("cooldown_months", 0)
        if current - last < cooldown:
            return False, f"遗迹冷却中，还需 {cooldown - (current - last)} 个月。"
        return True, ""

    def world_month(self):
        """获取当前世界总月份。"""
        return self.world.year * 12 + self.world.month

    def explore(self, ruin_id, world_month=None):
        ok, msg = self.can_explore(ruin_id)
        if not ok:
            return False, msg
        self.player.explored_ruins[ruin_id] = world_month or self.world_month()
        return True, "开始探索遗迹。"

    def get_stage(self, ruin_id, stage_index):
        ruin = self.config.get(ruin_id)
        stages = ruin.get("stages", [])
        if stage_index >= len(stages):
            return None
        return stages[stage_index]

    def create_stage_enemy(self, enemy_id):
        data = self.enemy_library.get(enemy_id)
        return Enemy.from_dict(data) if data else None

    def give_reward_item(self, item_id):
        item = self.item_library.create(item_id)
        if item:
            self.player.add_item(item)
            return item.name
        return item_id
