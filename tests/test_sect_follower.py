"""弟子招募与追随者系统单元测试。"""
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


class TestSectFollower(unittest.TestCase):
    """追随者系统相关测试用例。"""

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
        self.save_path = "test_follower_save.json"
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

    def _join_sect(self):
        """加入天剑宗并提升到内门弟子。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        self.player.sect_rank = "inner"
        self.player.sect_contribution = 2000

    def test_follower_capacity_by_rank(self):
        """追随者上限应随职位提升。"""
        self._join_sect()
        self.assertEqual(self.engine.sect_manager.get_follower_capacity(), 1)
        self.player.sect_rank = "core"
        self.assertEqual(self.engine.sect_manager.get_follower_capacity(), 2)

    def test_recruit_follower(self):
        """招募追随者后应加入列表并消耗贡献。"""
        self._join_sect()
        contribution_before = self.player.sect_contribution
        ok, msg = self.engine.sect_manager.recruit_follower("tianjian_sword_attendant")
        self.assertTrue(ok, msg)
        self.assertEqual(len(self.player.followers), 1)
        self.assertEqual(self.player.followers[0]["name"], "剑童")
        self.assertEqual(
            self.player.sect_contribution,
            contribution_before - 800,
        )

    def test_recruit_without_capacity_fails(self):
        """达到上限后无法再招募。"""
        self._join_sect()
        self.engine.sect_manager.recruit_follower("tianjian_sword_attendant")
        ok, msg = self.engine.sect_manager.recruit_follower("tianjian_sword_attendant")
        self.assertFalse(ok)
        self.assertIn("上限", msg)

    def test_passive_bonus(self):
        """空闲追随者应提供被动修炼加成。"""
        self._join_sect()
        self.engine.sect_manager.recruit_follower("tianjian_sword_attendant")
        bonus = self.engine.sect_manager.get_follower_passive_bonus()
        self.assertEqual(bonus, 0.05)
        # 派遣后无加成
        self.engine.sect_manager.dispatch_follower("tianjian_sword_attendant")
        bonus = self.engine.sect_manager.get_follower_passive_bonus()
        self.assertEqual(bonus, 0.0)

    def test_dispatch_and_complete_mission(self):
        """派遣追随者后经过月份应完成任务并带回奖励。"""
        self._join_sect()
        self.engine.sect_manager.recruit_follower("tianjian_sword_attendant")

        ok, msg = self.engine.sect_manager.dispatch_follower("tianjian_sword_attendant")
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.followers[0]["status"], "mission")

        # 推进 6 个月
        year = self.world.year
        month = self.world.month
        messages = []
        for i in range(1, 7):
            m = month + i
            y = year
            while m > 12:
                m -= 12
                y += 1
            messages.extend(self.engine.sect_manager.tick_followers(y, m))

        self.assertTrue(any("剑童" in msg for msg in messages))
        self.assertEqual(self.player.followers[0]["status"], "idle")
        self.assertGreaterEqual(self.player.count_item("spirit_stone"), 2)


if __name__ == "__main__":
    unittest.main()
