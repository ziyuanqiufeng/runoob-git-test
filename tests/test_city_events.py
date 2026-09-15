# -*- coding: utf-8 -*-
"""城池动态事件（妖兽攻城）单元测试。"""

import os
import unittest

from PySide6.QtWidgets import QApplication

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from game.city_event_manager import CityEventManager


class TestCityEventManager(unittest.TestCase):
    """CityEventManager 独立测试。"""

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.manager = CityEventManager(
            self.enemy_lib, self.item_lib, config_dir="config"
        )
        self.player = Player(name="测试修士")
        self.player.location_id = "fufeng_city"

    def test_get_event_for_city(self):
        """应能读取扶风城兽潮事件。"""
        events = self.manager.get_events_for_city("fufeng_city")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "beast_tide")

    def test_active_event_initially_none(self):
        """初始状态下当前城池无活跃事件。"""
        event = self.manager.get_active_event(self.player)
        self.assertIsNone(event)
        self.assertFalse(self.manager.has_active_event(self.player))

    def test_start_and_get_active_event(self):
        """手动激活事件后应能查询到。"""
        ok = self.manager.start_event(self.player, "beast_tide_fufeng")
        self.assertTrue(ok)
        self.assertIn("beast_tide_fufeng", self.player.active_world_events)
        event = self.manager.get_active_event(self.player)
        self.assertIsNotNone(event)
        self.assertEqual(event["name"], "扶风城兽潮")

    def test_create_enemies(self):
        """应根据配置创建对应数量与缩放的敌人。"""
        enemies = self.manager.create_enemies("beast_tide_fufeng")
        self.assertEqual(len(enemies), 3)
        self.assertIn("第 1/3 波", enemies[0].name)

    def test_calculate_rewards(self):
        """胜利时应返回配置的奖励。"""
        rewards = self.manager.calculate_rewards("beast_tide_fufeng", victory=True)
        self.assertEqual(rewards["spirit_stone"], 100)
        self.assertEqual(rewards["reputation"], 20)

    def test_finish_event_rewards(self):
        """结束事件应发放灵石奖励并移除活跃状态。"""
        self.manager.start_event(self.player, "beast_tide_fufeng")
        before = self.player.count_item("spirit_stone")
        rewards = self.manager.finish_event(self.player, "beast_tide_fufeng")
        self.assertEqual(rewards["spirit_stone"], 100)
        self.assertEqual(
            self.player.count_item("spirit_stone"), before + 100
        )
        self.assertNotIn("beast_tide_fufeng", self.player.active_world_events)


class TestEngineCityDefense(unittest.TestCase):
    """Engine 守城战集成测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.skill_lib = SkillLibrary(config_dir="config")
        self.npc_lib = NPCLibrary(config_dir="config")
        self.quest_lib = QuestLibrary(config_dir="config")

        self.player = Player(name="测试修士")
        self.player.location_id = "fufeng_city"
        self.player.base_attack = 100
        self.player.health = 100
        self.player.max_health = 100

        self.world = World(config_dir="config")
        self.event_pool = EventPool(config_dir="config")
        self.save_path = "test_city_event_save.json"
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
            save_manager=SaveManager(save_path=self.save_path),
        )

    def tearDown(self):
        if os.path.exists(self.save_path):
            os.remove(self.save_path)

    def test_join_city_defense_no_event(self):
        """无活跃事件时无法加入守城。"""
        event, enemies = self.engine.join_city_defense()
        self.assertIsNone(event)
        self.assertEqual(len(enemies), 0)

    def test_join_city_defense_creates_enemies(self):
        """激活事件后参与守城应生成敌人列表。"""
        self.engine.start_city_event("beast_tide_fufeng")
        event, enemies = self.engine.join_city_defense()
        self.assertIsNotNone(event)
        self.assertEqual(len(enemies), 3)
        self.assertIsNotNone(self.engine.pending_city_event)

    def test_get_next_city_defense_enemy(self):
        """应能按顺序取到下一波敌人。"""
        self.engine.start_city_event("beast_tide_fufeng")
        self.engine.join_city_defense()
        enemy1 = self.engine.get_next_city_defense_enemy()
        self.assertIsNotNone(enemy1)
        self.assertIn("第 1/3 波", enemy1.name)

    def test_advance_city_defense_wave(self):
        """推进波次并在全部击败后结算奖励。"""
        self.engine.start_city_event("beast_tide_fufeng")
        self.engine.join_city_defense()
        before = self.player.count_item("spirit_stone")

        # 模拟击败 3 波
        logs = []
        for _ in range(3):
            logs.extend(self.engine._advance_city_defense_wave())

        self.assertIsNone(self.engine.pending_city_event)
        self.assertNotIn("beast_tide_fufeng", self.player.active_world_events)
        self.assertEqual(self.player.count_item("spirit_stone"), before + 100)
        self.assertTrue(any("守城成功" in log for log in logs))


if __name__ == "__main__":
    unittest.main()
