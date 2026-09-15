"""宗门战与灵脉争夺单元测试。"""
import os
import unittest
from unittest.mock import patch

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


class TestSectWar(unittest.TestCase):
    """宗门战与灵脉争夺相关测试用例。"""

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
        self.save_path = "test_sect_war_save.json"
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
        # 给玩家一个足以承受战争健康消耗的生命值
        self.player.health = self.player.max_health

    def test_can_start_war_requires_sect(self):
        """未加入宗门时不能发动宗门战。"""
        ok, msg = self.engine.sect_manager.can_start_war("zixiao_palace")
        self.assertFalse(ok)
        self.assertIn("尚未加入", msg)

    def test_can_start_war_no_self_war(self):
        """不能对自己宗门开战。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.can_start_war("tianjian_sect")
        self.assertFalse(ok)
        self.assertIn("自己宗门", msg)

    def test_can_start_war_requires_inner_rank(self):
        """外门弟子不能发动宗门战。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        self.player.sect_rank = "outer"
        ok, msg = self.engine.sect_manager.can_start_war("zixiao_palace")
        self.assertFalse(ok)
        self.assertIn("内门", msg)

    def test_can_start_war_blocks_friendly(self):
        """不能对友好宗门开战。"""
        self._join_sect()
        # 天剑宗配置中 friendly_to 包含 zixiao_palace
        ok, msg = self.engine.sect_manager.can_start_war("zixiao_palace")
        self.assertFalse(ok)
        self.assertIn("友好", msg)

    def test_can_start_war_allows_hostile(self):
        """可以对敌对/中立宗门开战。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.can_start_war("xie_mo_cult")
        self.assertTrue(ok, msg)

    def test_start_war_victory(self):
        """宗门战胜利：获得奖励、夺取灵脉、关系恶化。"""
        self._join_sect()
        target_id = "xie_mo_cult"
        # 强制 random.random() 返回 0 以判定胜利
        with patch("game.sect.random.random", return_value=0.0):
            ok, msg = self.engine.sect_manager.start_war(target_id)
        self.assertTrue(ok, msg)

        # 健康应被消耗
        self.assertLess(self.player.health, self.player.max_health)
        # 贡献与声望应增加
        self.assertGreater(self.player.sect_contribution, 0)
        # 忠诚度应增加或保持（胜利 +5）
        self.assertGreaterEqual(self.player.sect_loyalty, 5)
        # 与目标宗门关系恶化
        rel = self.engine.sect_manager.get_sect_relationship(target_id)
        self.assertLess(rel, 0)
        # 应夺取一条灵脉控制权（目标宗门剩余可控灵脉应减少）
        seized = self.engine.sect_manager.get_controllable_veins(target_id)
        self.assertLess(len(seized), 2)  # 目标宗门灵脉被夺，剩余少于初始 2 条

    def test_start_war_defeat(self):
        """宗门战失败：健康与忠诚度下降，关系恶化。"""
        self._join_sect()
        target_id = "xie_mo_cult"
        loyalty_before = self.player.sect_loyalty
        # 强制 random.random() 返回 1 以判定失败
        with patch("game.sect.random.random", return_value=1.0):
            ok, msg = self.engine.sect_manager.start_war(target_id)
        self.assertFalse(ok, msg)
        self.assertLess(self.player.health, self.player.max_health)
        self.assertLess(self.player.sect_loyalty, loyalty_before)

    def test_war_participation_increases(self):
        """每次参与宗门战都会增加参与次数。"""
        self._join_sect()
        before = self.player.sect_war_participation
        with patch("game.sect.random.random", return_value=1.0):
            self.engine.sect_manager.start_war("xie_mo_cult")
        self.assertEqual(self.player.sect_war_participation, before + 1)

    def test_spirit_vein_affects_cultivation_bonus(self):
        """控制的灵脉应提升洞府修炼加成。"""
        self._join_sect()
        bonus_before = self.engine.sect_manager.get_cultivation_bonus()
        # 手动让目标宗门的一条灵脉被本宗控制
        target = self.engine.sect_library.get("xie_mo_cult")
        for vein in target.spirit_veins:
            if vein.get("controlled_by") == "xie_mo_cult":
                vein["controlled_by"] = "tianjian_sect"
                break
        bonus_after = self.engine.sect_manager.get_cultivation_bonus()
        self.assertGreater(bonus_after, bonus_before)

    def test_controllable_veins_filter(self):
        """get_controllable_veins 只返回指定宗门控制的灵脉。"""
        veins = self.engine.sect_manager.get_controllable_veins("tianjian_sect")
        # 天剑宗至少控制剑冢灵脉与青云灵脉
        self.assertGreaterEqual(len(veins), 2)
        for vein in veins:
            self.assertEqual(vein.get("controlled_by"), "tianjian_sect")

    def test_leave_sect_clears_war_state(self):
        """退出宗门不应清空战争参与次数（该字段属于玩家成长记录）。"""
        self._join_sect()
        with patch("game.sect.random.random", return_value=0.0):
            self.engine.sect_manager.start_war("xie_mo_cult")
        participation = self.player.sect_war_participation
        self.engine.sect_manager.leave_sect()
        # 战争参与次数作为履历保留
        self.assertEqual(self.player.sect_war_participation, participation)


if __name__ == "__main__":
    unittest.main()
