# -*- coding: utf-8 -*-
"""信件与传闻系统。"""
import json
import os
import random


class RumorConfig:
    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._rumors = {}
        self._load()

    def _load(self):
        path = os.path.join(self.config_dir, "rumors.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            self._rumors[entry["id"]] = entry

    def get(self, rumor_id):
        return self._rumors.get(rumor_id)

    def get_all(self):
        return list(self._rumors.values())


class LetterRumorManager:
    """管理玩家收到的信件和听闻的传闻。"""

    def __init__(self, player, world, config_dir="config"):
        self.player = player
        self.world = world
        self.config = RumorConfig(config_dir)
        if not hasattr(player, "letters"):
            player.letters = []
        if not hasattr(player, "heard_rumors"):
            player.heard_rumors = []

    def add_letter(self, from_npc, content):
        self.player.letters.append({
            "from_npc": from_npc,
            "content": content,
            "year": self.world.year,
            "month": self.world.month,
            "read": False,
        })

    def mark_letter_read(self, index):
        if 0 <= index < len(self.player.letters):
            self.player.letters[index]["read"] = True
            return True
        return False

    def hear_rumor(self, location_id=None):
        """根据地点随机听闻一条传闻。"""
        candidates = [
            r for r in self.config.get_all()
            if r.get("location") == (location_id or self.player.location_id)
            and r["id"] not in self.player.heard_rumors
        ]
        if not candidates:
            return None
        rumor = random.choice(candidates)
        self.player.heard_rumors.append(rumor["id"])
        return rumor

    def gather_rumor_at_inn(self, category=None, cost_multiplier=1.0):
        """
        在客栈花费灵石打听消息。

        参数：
            category: 指定情报类别（market/secret/npc/event/trivia），
                      None 表示不限制类别。
            cost_multiplier: 成本倍率（可由城市政策等影响）。

        返回：
            (rumor, actual_cost) 元组；灵石不足或没有新传闻时返回 (None, 0)。
        """
        loc_id = self.player.location_id
        candidates = []
        for r in self.config.get_all():
            # 已听闻的不再出现
            if r["id"] in self.player.heard_rumors:
                continue
            # 类别过滤
            if category and r.get("category") != category:
                continue
            # 地点过滤：any 表示通用，其余需匹配当前城池
            rumor_loc = r.get("location", "any")
            if rumor_loc != "any" and rumor_loc != loc_id:
                continue
            candidates.append(r)

        if not candidates:
            return None, 0

        # 按权重随机选择
        weights = [r.get("weight", 10) for r in candidates]
        rumor = random.choices(candidates, weights=weights, k=1)[0]
        base_cost = rumor.get("cost", 100)
        actual_cost = max(1, int(base_cost * cost_multiplier))

        # 检查灵石
        if not hasattr(self.player, "count_item"):
            return None, 0
        if self.player.count_item("spirit_stone") < actual_cost:
            return None, actual_cost

        self.player.consume_items("spirit_stone", actual_cost)
        self.player.heard_rumors.append(rumor["id"])
        return rumor, actual_cost

    def apply_rumor_effect(self, rumor_id, engine):
        """应用传闻效果（解锁秘境、刷新 BOSS、给藏宝图）。"""
        rumor = self.config.get(rumor_id)
        if not rumor:
            return
        effect = rumor.get("effect", {})
        if "unlock_secret_realm" in effect:
            realm_id = effect["unlock_secret_realm"]
            if hasattr(engine, "secret_realm_manager"):
                engine.secret_realm_manager.unlock(realm_id)
        if "spawn_world_boss" in effect:
            boss_id = effect["spawn_world_boss"]
            if hasattr(engine, "world_boss_manager"):
                engine.world_boss_manager.spawn(boss_id)
        if "give_treasure_map" in effect:
            map_id = effect["give_treasure_map"]
            self.player.treasure_maps.append({
                "map_id": map_id,
                "location_id": rumor.get("location"),
                "hint": rumor.get("description", ""),
            })
