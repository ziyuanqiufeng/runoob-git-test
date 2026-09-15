# -*- coding: utf-8 -*-
"""属性主题区域环境效果单元测试。

验证地点配置中的 environmental_effects 在战斗回合开始时被正确结算：
- 寒冰原霜冻减速：降低玩家攻击力
- 雷泽天雷：随机轰击玩家或敌人
- 玄水祝福：对应属性玩家恢复生命
"""
import os
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import Enemy, EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager


class TestEnvironmentalEffects(unittest.TestCase):
    """环境效果结算测试。"""

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
        self.world = World(config_dir="config")
        self.event_pool = EventPool(config_dir="config")
        self.save_path = "test_environmental_effects_save.json"
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

    def _create_enemy(self, **kwargs):
        """构造一个可控测试敌人。"""
        data = {
            "id": kwargs.get("enemy_id", "test_enemy"),
            "name": kwargs.get("name", "测试敌人"),
            "alignment": "neutral",
            "hp": kwargs.get("hp", 100),
            "attack": kwargs.get("attack", 10),
            "defense": kwargs.get("defense", 0),
            "exp": 0,
            "loot": [],
        }
        data.update(kwargs)
        return Enemy.from_dict(data)

    def _setup_combat(self, enemy):
        """初始化战斗并清空玩家攻击削弱。"""
        self.player.health = self.player.max_health
        self.engine.start_combat(enemy)

    @patch("game.engine.random.random", return_value=0.0)
    def test_frost_slow_applies_attack_debuff(self, mock_random):
        """寒冰原的霜冻效果应降低玩家攻击力。"""
        enemy = self._create_enemy(hp=1000)
        self._setup_combat(enemy)
        self.player.location_id = "hanbing_yuan"

        logs = []
        self.engine._apply_environmental_effects(enemy, logs)

        # 应添加 1 个攻击削弱 buff
        self.assertEqual(len(self.engine.player_attack_debuffs), 1)
        self.assertEqual(self.engine.player_attack_debuffs[0]["amount"], 8)
        self.assertEqual(self.engine.player_attack_debuffs[0]["turns"], 2)
        self.assertTrue(any("寒冰原" in log for log in logs), logs)

    @patch("game.engine.random.random", side_effect=[0.0, 0.0])
    def test_thunder_strike_hits_player(self, mock_random):
        """雷泽天雷应能轰击玩家。"""
        enemy = self._create_enemy(hp=1000, defense=0)
        self._setup_combat(enemy)
        self.player.location_id = "leize"
        initial_health = self.player.health

        logs = []
        self.engine._apply_environmental_effects(enemy, logs)

        self.assertLess(self.player.health, initial_health)
        self.assertTrue(any("你遭到雷击" in log for log in logs), logs)

    @patch("game.engine.random.random", side_effect=[0.0, 0.9])
    def test_thunder_strike_hits_enemy(self, mock_random):
        """雷泽天雷应能轰击敌人。"""
        enemy = self._create_enemy(hp=1000, defense=0)
        self._setup_combat(enemy)
        self.player.location_id = "leize"
        initial_hp = enemy.hp

        logs = []
        self.engine._apply_environmental_effects(enemy, logs)

        self.assertLess(enemy.hp, initial_hp)
        self.assertTrue(
            any(f"{enemy.name} 遭到雷击" in log for log in logs), logs
        )

    @patch("game.engine.random.random", return_value=0.0)
    def test_water_blessing_heals_water_player(self, mock_random):
        """玄水城的水灵祝福应为水属性玩家恢复生命。"""
        enemy = self._create_enemy(hp=1000)
        self._setup_combat(enemy)
        self.player.location_id = "xuanshui_city"
        self.player.set_spiritual_roots(["water"])
        self.player.health = self.player.max_health - 50
        initial_health = self.player.health

        logs = []
        self.engine._apply_environmental_effects(enemy, logs)

        self.assertGreater(self.player.health, initial_health)
        self.assertTrue(any("玄水湖" in log for log in logs), logs)

    @patch("game.engine.random.random", return_value=0.0)
    def test_water_blessing_ignores_non_water_player(self, mock_random):
        """玄水城的水灵祝福不应为非水属性玩家恢复生命。"""
        enemy = self._create_enemy(hp=1000)
        self._setup_combat(enemy)
        self.player.location_id = "xuanshui_city"
        self.player.set_spiritual_roots(["fire"])
        self.player.health = self.player.max_health - 50
        initial_health = self.player.health

        logs = []
        self.engine._apply_environmental_effects(enemy, logs)

        self.assertEqual(self.player.health, initial_health)
        self.assertFalse(any("玄水湖" in log for log in logs), logs)


if __name__ == "__main__":
    unittest.main()
