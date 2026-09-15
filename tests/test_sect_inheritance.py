"""宗门传承与祖师堂单元测试。"""
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


class TestSectInheritance(unittest.TestCase):
    """祖师堂传承相关测试用例。"""

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
        self.save_path = "test_sect_inheritance_save.json"
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
        """加入天剑宗并提升到内门弟子，给予足够贡献与忠诚。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        self.player.sect_rank = "inner"
        self.player.sect_contribution = 10000
        self.player.sect_loyalty = 100

    def test_get_inheritance_list_requires_sect(self):
        """未加入宗门时传承列表为空。"""
        self.assertEqual(self.engine.sect_manager.get_inheritance_list(), [])

    def test_get_inheritance_list_after_join(self):
        """加入宗门后可看到本宗传承。"""
        self._join_sect()
        inheritances = self.engine.sect_manager.get_inheritance_list()
        self.assertEqual(len(inheritances), 2)
        self.assertEqual(inheritances[0]["id"], "tianjian_sword_intent")

    def test_can_learn_requires_sect(self):
        """未加入宗门不能参悟。"""
        ok, msg = self.engine.sect_manager.can_learn_inheritance("tianjian_sword_intent")
        self.assertFalse(ok)
        self.assertIn("尚未加入", msg)

    def test_can_learn_requires_rank(self):
        """职位不足不能参悟高阶传承。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        self.player.sect_rank = "inner"
        ok, msg = self.engine.sect_manager.can_learn_inheritance("tianjian_true_sword")
        self.assertFalse(ok)
        self.assertIn("职位", msg)

    def test_can_learn_requires_contribution(self):
        """贡献不足不能参悟。"""
        self._join_sect()
        self.player.sect_contribution = 0
        ok, msg = self.engine.sect_manager.can_learn_inheritance("tianjian_sword_intent")
        self.assertFalse(ok)
        self.assertIn("贡献", msg)

    def test_can_learn_requires_loyalty(self):
        """忠诚度不足不能参悟。"""
        self._join_sect()
        self.player.sect_loyalty = 0
        ok, msg = self.engine.sect_manager.can_learn_inheritance("tianjian_sword_intent")
        self.assertFalse(ok)
        self.assertIn("忠诚", msg)

    def test_learn_inheritance_success(self):
        """成功参悟传承：扣除消耗、提升攻击、加入已学习列表。"""
        self._join_sect()
        con_before = self.player.sect_contribution
        loy_before = self.player.sect_loyalty
        atk_before = self.player.base_attack

        ok, msg = self.engine.sect_manager.learn_inheritance("tianjian_sword_intent")
        self.assertTrue(ok, msg)

        self.assertEqual(self.player.sect_contribution, con_before - 2000)
        self.assertEqual(self.player.sect_loyalty, loy_before - 20)
        self.assertEqual(self.player.base_attack, atk_before + 5)
        self.assertIn("tianjian_sword_intent", self.player.learned_inheritances)
        self.assertEqual(self.player.ancestral_hall_monthly_count, 1)
        self.assertIn("天剑剑意", msg)

    def test_learn_inheritance_skill_reward(self):
        """参悟高阶传承可习得技能。"""
        self._join_sect()
        self.player.sect_rank = "core"
        ok, msg = self.engine.sect_manager.learn_inheritance("tianjian_true_sword")
        self.assertTrue(ok, msg)
        self.assertIn("sword_qi", self.player.skills)
        self.assertIn("剑气", msg)

    def test_cannot_repeat_learn(self):
        """已参悟的传承不能重复学习。"""
        self._join_sect()
        self.engine.sect_manager.learn_inheritance("tianjian_sword_intent")
        ok, msg = self.engine.sect_manager.can_learn_inheritance("tianjian_sword_intent")
        self.assertFalse(ok)
        self.assertIn("已经参悟", msg)

    def test_monthly_limit(self):
        """每月参悟次数达到上限后无法继续学习其他传承。"""
        self._join_sect()
        self.player.sect_rank = "core"  # 确保可学真传传承
        self.engine.sect_manager.learn_inheritance("tianjian_sword_intent")
        ok, msg = self.engine.sect_manager.can_learn_inheritance("tianjian_true_sword")
        self.assertFalse(ok)
        self.assertIn("本月", msg)

    def test_reset_monthly_count(self):
        """重置本月参悟次数。"""
        self._join_sect()
        self.engine.sect_manager.learn_inheritance("tianjian_sword_intent")
        self.engine.sect_manager.reset_ancestral_hall_monthly_count()
        self.assertEqual(self.player.ancestral_hall_monthly_count, 0)


if __name__ == "__main__":
    unittest.main()
