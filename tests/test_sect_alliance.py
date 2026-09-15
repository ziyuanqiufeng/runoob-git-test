# -*- coding: utf-8 -*-
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


class TestSectAlliance(unittest.TestCase):
    """宗门结盟与攻守同盟相关测试用例。"""

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
        self.save_path = "test_sect_alliance_save.json"
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
        """加入天剑宗并提升到内门弟子，同时补充足够贡献。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        self.player.sect_rank = "inner"
        self.player.sect_contribution = 10000

    def test_form_alliance_success(self):
        """成功与配置友好的宗门签订同盟。"""
        self._join_sect()
        con_before = self.player.sect_contribution
        ok, msg = self.engine.sect_manager.form_alliance("zixiao_palace")
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.sect_contribution, con_before - 5000)
        self.assertTrue(self.engine.sect_manager.is_allied("zixiao_palace"))
        self.assertEqual(len(self.engine.sect_manager.get_alliance_list()), 1)

    def test_form_alliance_by_player_relationship(self):
        """与原本中立的宗门通过个人关系达到友好后签订同盟。"""
        self._join_sect()
        self.engine.sect_manager.set_sect_relationship("xie_mo_cult", 50)
        ok, msg = self.engine.sect_manager.form_alliance("xie_mo_cult")
        self.assertTrue(ok, msg)
        self.assertTrue(self.engine.sect_manager.is_allied("xie_mo_cult"))

    def test_form_alliance_requires_sect(self):
        """未加入宗门时无法签订同盟。"""
        ok, msg = self.engine.sect_manager.form_alliance("zixiao_palace")
        self.assertFalse(ok)
        self.assertIn("尚未加入", msg)

    def test_form_alliance_requires_friendly(self):
        """非友好宗门无法签订同盟。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.form_alliance("xie_mo_cult")
        self.assertFalse(ok)
        self.assertIn("友好", msg)

    def test_form_alliance_requires_contribution(self):
        """贡献不足时无法签订同盟。"""
        self._join_sect()
        self.player.sect_contribution = 1000
        ok, msg = self.engine.sect_manager.form_alliance("zixiao_palace")
        self.assertFalse(ok)
        self.assertIn("贡献不足", msg)

    def test_cannot_form_alliance_with_self(self):
        """不能与本宗签订同盟。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.form_alliance("tianjian_sect")
        self.assertFalse(ok)
        self.assertIn("本宗", msg)

    def test_cannot_repeat_alliance(self):
        """不能重复与同一宗门签订同盟。"""
        self._join_sect()
        self.engine.sect_manager.form_alliance("zixiao_palace")
        ok, msg = self.engine.sect_manager.form_alliance("zixiao_palace")
        self.assertFalse(ok)
        self.assertIn("结盟", msg)

    def test_cannot_war_with_ally(self):
        """不能对同盟宗门开战。"""
        self._join_sect()
        self.engine.sect_manager.form_alliance("zixiao_palace")
        ok, msg = self.engine.sect_manager.can_start_war("zixiao_palace")
        self.assertFalse(ok)
        self.assertIn("同盟", msg)

    def test_break_alliance(self):
        """解除同盟后关系降至中立，且不再视为同盟。"""
        self._join_sect()
        self.engine.sect_manager.form_alliance("zixiao_palace")
        ok, msg = self.engine.sect_manager.break_alliance("zixiao_palace")
        self.assertTrue(ok, msg)
        self.assertFalse(self.engine.sect_manager.is_allied("zixiao_palace"))
        # 个人关系值应被重置为 0（配置层面的友好关系仍保留）
        self.assertEqual(
            self.engine.sect_manager.get_sect_relationship("zixiao_palace"), 0
        )

    def test_break_alliance_not_allied(self):
        """解除不存在的同盟应失败。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.break_alliance("zixiao_palace")
        self.assertFalse(ok)
        self.assertIn("未与该宗门结盟", msg)

    def test_alliance_expires(self):
        """同盟到期后自动解除。"""
        self._join_sect()
        self.engine.sect_manager.form_alliance("zixiao_palace")
        alliance = self.engine.sect_manager.get_alliance_list()[0]
        alliance["formed_year"] = self.world.year - 5
        alliance["formed_month"] = self.world.month
        messages = self.engine.sect_manager.tick_alliances(
            self.world.year, self.world.month
        )
        self.assertFalse(self.engine.sect_manager.is_allied("zixiao_palace"))
        self.assertEqual(len(messages), 1)
        self.assertIn("到期", messages[0])

    def test_alliance_shop_discount(self):
        """同盟宗门商店享受额外折扣。"""
        self._join_sect()
        self.engine.sect_manager.form_alliance("zixiao_palace")
        discount = self.engine.sect_manager.get_alliance_shop_discount("zixiao_palace")
        self.assertAlmostEqual(discount, 0.1)

    def test_no_discount_for_non_ally(self):
        """非同盟宗门没有同盟折扣。"""
        self._join_sect()
        discount = self.engine.sect_manager.get_alliance_shop_discount("zixiao_palace")
        self.assertAlmostEqual(discount, 0.0)

    def test_alliance_war_bonus(self):
        """同盟数量影响宗门战成功率加成。"""
        self._join_sect()
        self.assertAlmostEqual(
            self.engine.sect_manager.get_alliance_war_bonus(), 0.0
        )
        self.engine.sect_manager.form_alliance("zixiao_palace")
        self.assertAlmostEqual(
            self.engine.sect_manager.get_alliance_war_bonus(), 0.1
        )


if __name__ == "__main__":
    unittest.main()
