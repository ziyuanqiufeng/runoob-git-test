# -*- coding: utf-8 -*-
"""世界 BOSS 系统。"""
import json
import os

from game.enemy import Enemy


class WorldBossConfig:
    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._bosses = {}
        self._load()

    def _load(self):
        path = os.path.join(self.config_dir, "world_bosses.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            self._bosses[entry["id"]] = entry

    def get(self, boss_id):
        return self._bosses.get(boss_id)


class WorldBossManager:
    """管理世界 BOSS 的刷新状态。状态保存在 world 中。"""

    def __init__(self, world, enemy_library, config_dir="config"):
        self.world = world
        self.enemy_library = enemy_library
        self.config = WorldBossConfig(config_dir)
        # 确保 world 有 boss 状态字段
        if not hasattr(world, "active_world_bosses"):
            world.active_world_bosses = {}
        if not hasattr(world, "defeated_world_bosses"):
            world.defeated_world_bosses = {}

    def spawn(self, boss_id):
        """在指定位置生成一个活跃 BOSS。"""
        boss_cfg = self.config.get(boss_id)
        if not boss_cfg:
            return None
        current_month = self.world.year * 12 + self.world.month
        self.world.active_world_bosses[boss_id] = {
            "spawned_month": current_month,
            "location": boss_cfg["location"],
        }
        return boss_cfg

    def tick(self, player=None):
        """每月调用一次：按 respawn_months 自动刷新世界 BOSS。

        首次刷新需要玩家境界达到 min_realm_order；
        被击败后按 respawn_months 重生。
        """
        current_month = self.world.year * 12 + self.world.month
        player_order = player.REALM_ORDER.get(player.realm_id, 0) if player else 9999
        for boss_id, boss_cfg in self.config._bosses.items():
            # 已活跃则跳过
            if boss_id in self.world.active_world_bosses:
                continue
            min_order = boss_cfg.get("min_realm_order", 1)
            if player_order < min_order:
                continue
            defeated_month = self.world.defeated_world_bosses.get(boss_id)
            respawn = boss_cfg.get("respawn_months", 9999)
            if defeated_month is None:
                # 首次刷新：达到境界即生成
                self.spawn(boss_id)
            elif current_month - defeated_month >= respawn:
                # 已过重生冷却
                self.spawn(boss_id)

    def get_active_bosses(self, location_id=None):
        """获取当前活跃 BOSS。"""
        result = []
        for boss_id in list(self.world.active_world_bosses.keys()):
            boss_cfg = self.config.get(boss_id)
            if not boss_cfg:
                continue
            if location_id and boss_cfg.get("location") != location_id:
                continue
            result.append(boss_cfg)
        return result

    def get_active_boss_at_location(self, location_id):
        """获取指定地点当前活跃的 BOSS 配置（若存在）。"""
        bosses = self.get_active_bosses(location_id=location_id)
        return bosses[0] if bosses else None

    def create_enemy(self, boss_id):
        """根据 BOSS 配置创建敌人实例，并标记 boss_id 便于战斗结算。"""
        boss_cfg = self.config.get(boss_id)
        if not boss_cfg:
            return None
        data = self.enemy_library.get(boss_cfg["base_enemy_id"])
        if not data:
            return None
        enemy = Enemy.from_dict(data)
        # 标记敌人来源，便于战斗结束后识别为世界 BOSS
        enemy.boss_id = boss_id
        enemy.name = boss_cfg.get("name", enemy.name)
        return enemy

    def get_participation_rewards(self, boss_id):
        """获取 BOSS 配置中的参与奖励字典（items + qi）。"""
        boss_cfg = self.config.get(boss_id)
        if not boss_cfg:
            return {}
        return boss_cfg.get("participation_rewards", {})

    def get_loot_rewards(self, boss_id):
        """获取 BOSS 被击败后的掉落物品 ID 列表。"""
        boss_cfg = self.config.get(boss_id)
        if not boss_cfg:
            return []
        return boss_cfg.get("loot", [])

    def grant_defeat_rewards(self, player, item_library, boss_id):
        """
        发放世界 BOSS 击败奖励：固定参与奖励 + 配置掉落。
        返回 (奖励消息列表, 获得物品名称列表)。
        """
        messages = []
        gained_names = []

        # 参与奖励（修为、灵石等）
        participation = self.get_participation_rewards(boss_id)
        if participation.get("qi"):
            player.qi += participation["qi"]
            messages.append(f"修为 +{participation['qi']}")
        for item_id, count in participation.items():
            if item_id == "qi":
                continue
            for _ in range(count):
                item = item_library.create(item_id)
                if item:
                    player.add_item(item)
                    gained_names.append(item.name)

        # 配置掉落
        for item_id in self.get_loot_rewards(boss_id):
            item = item_library.create(item_id)
            if item:
                player.add_item(item)
                gained_names.append(item.name)

        return messages, gained_names

    def defeat(self, boss_id):
        """击败后移除活跃状态并记录击败时间。"""
        if boss_id in self.world.active_world_bosses:
            self.world.active_world_bosses.pop(boss_id, None)
            current_month = self.world.year * 12 + self.world.month
            self.world.defeated_world_bosses[boss_id] = current_month
            return True
        return False
