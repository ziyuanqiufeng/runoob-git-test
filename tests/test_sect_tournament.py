"""宗门大比系统单元测试。"""
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


class TestSectTournament(unittest.TestCase):
    """宗门大比相关测试用例。"""

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
        self.save_path = "test_tournament_save.json"
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

    def _setup_eligible(self):
        """让玩家满足天剑宗大比的参加条件。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        self.player.location_id = "tianjian_sect"
        self.player.realm_id = "qi_refining_3"
        # 调整到第 12 个月（12 % 12 == 0），表示大比之期
        self.world.year = 1
        self.world.month = 12

    def test_no_sect_cannot_start(self):
        """未加入宗门不能参加大比。"""
        ok, msg = self.engine.sect_manager.can_start_tournament()
        self.assertFalse(ok)
        self.assertIn("未加入", msg)

    def test_wrong_location_blocked(self):
        """不在举办地点不能参加大比。"""
        self._setup_eligible()
        self.player.location_id = "qingyun_mountain"
        ok, msg = self.engine.sect_manager.can_start_tournament()
        self.assertFalse(ok)
        self.assertIn("需前往", msg)

    def test_low_realm_blocked(self):
        """境界不足不能参加大比。"""
        self._setup_eligible()
        self.player.realm_id = "qi_refining_1"
        ok, msg = self.engine.sect_manager.can_start_tournament()
        self.assertFalse(ok)
        self.assertIn("境界", msg)

    def test_eligible_can_start(self):
        """满足条件时可以参加大比。"""
        self._setup_eligible()
        ok, msg = self.engine.sect_manager.can_start_tournament()
        self.assertTrue(ok)

    def test_opponents_generated(self):
        """大比能按配置生成正确数量的对手。"""
        self._setup_eligible()
        opponents = self.engine.sect_manager.get_tournament_opponents()
        event = self.engine.sect_manager.get_sect_event("tournament")
        self.assertEqual(len(opponents), event.rounds)
        # 对手属性应随轮次递增
        self.assertLess(opponents[0].level, opponents[-1].level)

    def test_complete_tournament_rewards(self):
        """完成大比后按胜场发放贡献并记录参加时间。"""
        self._setup_eligible()
        contribution_before = self.player.sect_contribution
        ok, msg = self.engine.sect_manager.complete_tournament(wins=2)
        self.assertTrue(ok)
        event = self.engine.sect_manager.get_sect_event("tournament")
        expected = 2 * event.rewards.get("contribution_per_win", 0)
        self.assertEqual(
            self.player.sect_contribution,
            contribution_before + expected,
        )
        self.assertEqual(
            self.player.sect_tournament_last_month,
            self.world.year * 12 + self.world.month,
        )

    def test_cannot_repeat_same_month(self):
        """同月内不能重复参加大比。"""
        self._setup_eligible()
        self.engine.sect_manager.complete_tournament(wins=1)
        ok, msg = self.engine.sect_manager.can_start_tournament()
        self.assertFalse(ok)
        self.assertIn("本月已参加", msg)


if __name__ == "__main__":
    unittest.main()
