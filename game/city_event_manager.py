# -*- coding: utf-8 -*-
"""城池动态事件管理器。

目前主要实现妖兽攻城（兽潮）事件：各城池独立触发、玩家可参与守城，
连续击败多波妖兽后获得灵石与城池声望奖励。
"""
import json
import os

from game.enemy import Enemy


class CityEventManager:
    """管理城池动态事件（妖兽攻城等）。"""

    def __init__(self, enemy_library, item_library, config_dir="config"):
        self.enemy_library = enemy_library
        self.item_library = item_library
        self.config_dir = config_dir
        self._events = []
        self._event_map = {}
        self._load()

    def _load(self):
        """加载城池事件配置。"""
        path = os.path.join(self.config_dir, "city_events.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._events = data.get("events", [])
        self._event_map = {e["id"]: e for e in self._events}

    def get_event(self, event_id):
        """根据事件 ID 获取事件配置。"""
        return self._event_map.get(event_id)

    def get_events_for_city(self, city_id):
        """获取指定城池的所有事件配置。"""
        return [e for e in self._events if e.get("city_id") == city_id]

    def get_active_event(self, player):
        """
        获取玩家当前所在城池的活跃事件。

        玩家 active_world_events 中 key 与配置事件 ID 匹配即视为活跃。
        """
        city_id = getattr(player, "location_id", None)
        if not city_id:
            return None
        for event in self.get_events_for_city(city_id):
            if event["id"] in player.active_world_events:
                return event
        return None

    def has_active_event(self, player):
        """当前城池是否存在活跃事件。"""
        return self.get_active_event(player) is not None

    def create_enemies(self, event_id):
        """
        根据事件配置创建敌人列表。

        每个敌人会应用事件配置的 enemy_scale 属性缩放。
        """
        event = self.get_event(event_id)
        if not event:
            return []

        enemy_id = event.get("enemy_id", "wolf")
        enemy_count = event.get("enemy_count", 1)
        scale = event.get("enemy_scale", 1.0)

        enemy_data = self.enemy_library.get(enemy_id)
        if not enemy_data:
            return []

        enemies = []
        for i in range(enemy_count):
            enemy = Enemy.from_dict(enemy_data)
            enemy.name = f"{enemy.name}（第 {i + 1}/{enemy_count} 波）"
            if scale != 1.0:
                enemy.max_hp = int(enemy.max_hp * scale)
                enemy.hp = enemy.max_hp
                enemy.attack = int(enemy.attack * scale)
                enemy.defense = int(enemy.defense * scale)
            enemies.append(enemy)
        return enemies

    def calculate_rewards(self, event_id, victory=True):
        """计算事件奖励。"""
        event = self.get_event(event_id)
        if not event or not victory:
            return {"spirit_stone": 0, "reputation": 0}
        rewards = event.get("rewards", {})
        return {
            "spirit_stone": rewards.get("spirit_stone", 0),
            "reputation": rewards.get("reputation", 0),
        }

    def start_event(self, player, event_id):
        """手动激活一个事件（通常由传闻、任务或随机触发调用）。"""
        event = self.get_event(event_id)
        if not event:
            return False
        player.active_world_events[event_id] = {
            "started_year": player.world.year if hasattr(player, "world") else 0,
            "started_month": player.world.month if hasattr(player, "world") else 0,
        }
        return True

    def finish_event(self, player, event_id):
        """结束一个活跃事件并发放奖励。"""
        event = self.get_event(event_id)
        if not event:
            return {}
        if event_id in player.active_world_events:
            del player.active_world_events[event_id]

        rewards = self.calculate_rewards(event_id, victory=True)
        city_id = event.get("city_id", "")
        if rewards["spirit_stone"] > 0 and self.item_library:
            for _ in range(rewards["spirit_stone"]):
                item = self.item_library.create("spirit_stone")
                if item:
                    player.add_item(item)
        return rewards
