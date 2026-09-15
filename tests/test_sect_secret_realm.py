"""宗门秘境/禁地探索单元测试。"""
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


class TestSectSecretRealm(unittest.TestCase):
    """宗门秘境/禁地相关测试用例。"""

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
        self.save_path = "test_secret_realm_save.json"
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

    def test_get_secret_realms_requires_rank(self):
        """职位不足时不应显示秘境。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        # 默认外门，应无可用秘境
        self.assertEqual(len(self.engine.sect_manager.get_secret_realms()), 0)
        self.player.sect_rank = "inner"
        self.assertEqual(len(self.engine.sect_manager.get_secret_realms()), 1)

    def test_can_enter_secret_realm(self):
        """满足条件时应可进入秘境。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.can_enter_secret_realm("tianjian_sword_tomb")
        self.assertTrue(ok, msg)

    def test_secret_realm_cooldown_blocks_entry(self):
        """冷却期间无法再次进入秘境。"""
        self._join_sect()
        current = self.world.year * 12 + self.world.month
        self.player.sect_secret_realm_cooldowns["tianjian_sword_tomb"] = current + 5
        ok, msg = self.engine.sect_manager.can_enter_secret_realm("tianjian_sword_tomb")
        self.assertFalse(ok)
        self.assertIn("冷却", msg)

    def test_enter_secret_realm_generates_enemy(self):
        """进入秘境应生成守关敌人并设置 pending。"""
        self._join_sect()
        enemy, msg = self.engine.sect_manager.enter_secret_realm("tianjian_sword_tomb")
        self.assertIsNotNone(enemy)
        self.assertIn("剑冢禁地", msg)

    def test_finish_secret_realm_win_gives_rewards(self):
        """通关秘境应发放奖励并设置冷却。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.finish_secret_realm("tianjian_sword_tomb", win=True)
        self.assertTrue(ok, msg)
        # 背包中应有奖励物品
        self.assertGreaterEqual(self.player.count_item("spirit_stone"), 2)
        self.assertGreaterEqual(self.player.count_item("sword_manual"), 1)
        # 修为增加
        self.assertGreaterEqual(self.player.qi, 100)
        # 冷却已设置
        self.assertGreater(
            self.engine.sect_manager.get_secret_realm_remaining_cooldown("tianjian_sword_tomb"), 0
        )

    def test_finish_secret_realm_lose_sets_cooldown_only(self):
        """未通关只设置冷却，不发放奖励。"""
        self._join_sect()
        qi_before = self.player.qi
        ok, msg = self.engine.sect_manager.finish_secret_realm("tianjian_sword_tomb", win=False)
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.qi, qi_before)
        self.assertEqual(self.player.count_item("sword_manual"), 0)
        self.assertGreater(
            self.engine.sect_manager.get_secret_realm_remaining_cooldown("tianjian_sword_tomb"), 0
        )

    def test_leave_sect_clears_secret_realm_cooldowns(self):
        """退出宗门应清空秘境冷却。"""
        self._join_sect()
        self.engine.sect_manager.finish_secret_realm("tianjian_sword_tomb", win=False)
        self.assertGreater(
            self.engine.sect_manager.get_secret_realm_remaining_cooldown("tianjian_sword_tomb"), 0
        )
        self.engine.sect_manager.leave_sect()
        self.assertEqual(self.player.sect_secret_realm_cooldowns, {})


if __name__ == "__main__":
    unittest.main()
