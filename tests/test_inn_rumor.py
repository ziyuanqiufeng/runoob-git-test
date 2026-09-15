# -*- coding: utf-8 -*-
"""客栈打听消息系统单元测试。"""
import os
import sys
import unittest

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.player import Player
from game.world import World
from game.item import ItemLibrary
from game.letter_rumor import LetterRumorManager


class TestLetterRumorManager(unittest.TestCase):
    """信件传闻管理器测试。"""

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.player = Player(name="测试修士")
        self.player.location_id = "fufeng_city"
        # 通过 ItemLibrary 创建可堆叠灵石并加入背包
        for _ in range(1000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.world = World(config_dir="config")
        self.manager = LetterRumorManager(self.player, self.world, config_dir="config")

    def test_gather_rumor_consumes_spirit_stone(self):
        """打听消息应消耗灵石并返回传闻。"""
        before = self.player.count_item("spirit_stone")
        rumor, cost = self.manager.gather_rumor_at_inn()
        after = self.player.count_item("spirit_stone")

        self.assertIsNotNone(rumor)
        self.assertGreater(cost, 0)
        self.assertEqual(after, before - cost)
        self.assertIn(rumor["id"], self.player.heard_rumors)

    def test_gather_rumor_with_category(self):
        """指定类别时应只返回该类别的传闻。"""
        rumor, _ = self.manager.gather_rumor_at_inn(category="trivia")
        self.assertIsNotNone(rumor)
        self.assertEqual(rumor.get("category"), "trivia")

    def test_gather_rumor_not_enough_money(self):
        """灵石不足时应返回 None 并给出所需费用。"""
        self.player.consume_items("spirit_stone", 1000)  # 花光灵石
        rumor, cost = self.manager.gather_rumor_at_inn()
        self.assertIsNone(rumor)
        self.assertGreater(cost, 0)

    def test_heard_rumor_not_repeated(self):
        """已听闻的传闻不应再次出现。"""
        # 先打听一条
        first, _ = self.manager.gather_rumor_at_inn()
        self.assertIsNotNone(first)

        # 把其他传闻也全部听完
        for _ in range(50):
            rumor, _ = self.manager.gather_rumor_at_inn()
            if rumor is None:
                break

        # 再次打听应该没有新传闻
        final_rumor, _ = self.manager.gather_rumor_at_inn()
        if final_rumor is not None:
            # 若还有，则不应与 first 重复
            self.assertNotEqual(final_rumor["id"], first["id"])

    def test_gather_rumor_filters_by_location(self):
        """非 any 的传闻只在对应城池出现。"""
        self.player.location_id = "xuanshui_city"
        # 多次打听，确保至少有一次拿到当前城池相关传闻
        found_local = False
        for _ in range(20):
            rumor, _ = self.manager.gather_rumor_at_inn()
            if rumor is None:
                break
            loc = rumor.get("location", "any")
            self.assertTrue(loc in ("any", "xuanshui_city"))
            if loc == "xuanshui_city":
                found_local = True
        self.assertTrue(found_local)


class TestEngineGatherRumor(unittest.TestCase):
    """引擎层打听消息接口测试。"""

    def setUp(self):
        from game.events import EventPool
        from game.item import ItemLibrary
        from game.enemy import EnemyLibrary
        from game.skill import SkillLibrary
        from game.npc import NPCLibrary
        from game.quest import QuestLibrary
        from game.engine import GameEngine
        from game.save_manager import SaveManager

        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.skill_lib = SkillLibrary(config_dir="config")
        self.npc_lib = NPCLibrary(config_dir="config")
        self.quest_lib = QuestLibrary(config_dir="config")
        self.player = Player(name="测试修士")
        self.player.location_id = "fufeng_city"
        for _ in range(1000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        self.world = World(config_dir="config")
        self.event_pool = EventPool(config_dir="config")
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
            save_manager=SaveManager(save_path="test_inn_rumor.json"),
        )

    def tearDown(self):
        if os.path.exists("test_inn_rumor.json"):
            os.remove("test_inn_rumor.json")

    def test_engine_gather_rumor(self):
        """引擎层 gather_rumor_at_inn 应返回传闻并扣费。"""
        before = self.player.count_item("spirit_stone")
        rumor = self.engine.gather_rumor_at_inn()
        after = self.player.count_item("spirit_stone")

        self.assertIsNotNone(rumor)
        self.assertIn("description", rumor)
        self.assertLess(after, before)
        self.assertIn(rumor["id"], self.player.heard_rumors)

    def test_engine_gather_rumor_insufficient_funds(self):
        """灵石不足时引擎应返回 None。"""
        self.player.consume_items("spirit_stone", 1000)
        rumor = self.engine.gather_rumor_at_inn()
        self.assertIsNone(rumor)


class TestRumorConfigFormat(unittest.TestCase):
    """rumors.json 配置格式校验。"""

    def test_rumors_json_exists_and_valid(self):
        """配置文件应存在且为合法 JSON 列表。"""
        import json
        path = os.path.join("config", "rumors.json")
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_each_rumor_has_required_fields(self):
        """每条传闻应包含必要字段。"""
        import json
        path = os.path.join("config", "rumors.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for rumor in data:
            self.assertIn("id", rumor)
            self.assertIn("description", rumor)
            self.assertIn("category", rumor)
            self.assertIn("cost", rumor)
            self.assertIn("weight", rumor)


if __name__ == "__main__":
    unittest.main()
