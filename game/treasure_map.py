# -*- coding: utf-8 -*-
"""藏宝图系统：生成、提示与结算。"""
import json
import os
import random


class TreasureMapConfig:
    """加载 config/treasure_maps.json 中的寻宝图配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "treasure_maps.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_rarity(self, rarity):
        return self.data.get("rarities", {}).get(rarity, {})

    def get_location_hint(self, location_id):
        return self.data.get("location_hints", {}).get(location_id, "一处隐秘之地")


class TreasureMapManager:
    """管理藏宝图的生成、提示与到达指定地点后的结算。"""

    def __init__(self, player, item_library, world, config_dir="config"):
        self.player = player
        self.item_library = item_library
        self.world = world
        self.config = TreasureMapConfig(config_dir)

    def generate(self, rarity="common", location_id=None):
        """生成一张藏宝图并加入玩家背包。

        rarity: common/rare/legendary，决定奖励品质。
        location_id: 指定藏宝地点，None 则随机选择。
        返回生成的藏宝图字典。
        """
        if location_id is None:
            location_id = self._random_location()
        hint = self.config.get_location_hint(location_id)
        map_obj = {
            "map_id": f"treasure_{rarity}_{self.world.year}_{self.world.month}",
            "rarity": rarity,
            "location_id": location_id,
            "hint": hint,
            "resolved": False,
        }
        self.player.treasure_maps.append(map_obj)
        return map_obj

    def _random_location(self):
        """从世界地点中随机选择一个可抵达地点作为藏宝点。"""
        locations = self.world.get_all_locations()
        if not locations:
            return "qingyun"
        return random.choice(locations)["id"]

    def _filter_reward_items(self, rarity):
        """根据稀有度配置筛选合适的奖励物品。"""
        cfg = self.config.get_rarity(rarity)
        min_value = cfg.get("min_value", 0)
        max_value = cfg.get("max_value", 999999)
        tags = set(cfg.get("item_tags", []))
        candidates = []
        for item_id, item in self.item_library.items.items():
            if not (min_value <= getattr(item, "value", 0) <= max_value):
                continue
            item_tags = {getattr(item, "type", "")}
            if tags and not (tags & item_tags):
                continue
            candidates.append(item_id)
        return candidates

    def resolve(self, map_index):
        """结算指定索引的藏宝图，玩家需已抵达对应地点。

        返回 (success: bool, message: str, rewards: list)。
        """
        if map_index < 0 or map_index >= len(self.player.treasure_maps):
            return False, "藏宝图索引无效。", []
        tm = self.player.treasure_maps[map_index]
        if tm.get("resolved"):
            return False, "这张藏宝图已经使用过了。", []
        if self.player.location_id != tm["location_id"]:
            loc = self.world.get_location(tm["location_id"])
            loc_name = loc["name"] if loc else tm["location_id"]
            return False, f"你尚未抵达藏宝地点【{loc_name}】。", []

        rewards = self._generate_rewards(tm["rarity"])
        tm["resolved"] = True
        return True, self._format_reward_message(rewards), rewards

    def _generate_rewards(self, rarity):
        """根据稀有度生成奖励物品列表。"""
        cfg = self.config.get_rarity(rarity)
        count_range = cfg.get("reward_count", [1, 1])
        count = random.randint(count_range[0], count_range[-1])
        candidates = self._filter_reward_items(rarity)
        rewards = []
        for _ in range(count):
            if not candidates:
                break
            item_id = random.choice(candidates)
            item = self.item_library.create(item_id)
            if item:
                self.player.add_item(item)
                rewards.append(item)
        return rewards

    def _format_reward_message(self, rewards):
        """格式化奖励提示文本。"""
        if not rewards:
            return "你挖开标记处，却发现宝箱早已被人取走。"
        names = "、".join(item.name for item in rewards)
        return f"你按图索骥，在一处隐秘角落找到宝藏：{names}。"

    def get_pending_maps(self):
        """获取所有未结算且当前地点可立即挖掘的藏宝图。"""
        return [
            (idx, tm)
            for idx, tm in enumerate(self.player.treasure_maps)
            if not tm.get("resolved") and tm.get("location_id") == self.player.location_id
        ]

    def get_hint(self, map_index):
        """获取藏宝图的文字提示。"""
        if 0 <= map_index < len(self.player.treasure_maps):
            tm = self.player.treasure_maps[map_index]
            loc = self.world.get_location(tm["location_id"])
            loc_name = loc["name"] if loc else tm["location_id"]
            return f"{tm['hint']}，似乎指向【{loc_name}】。"
        return ""
