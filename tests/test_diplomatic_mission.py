"""宗门外交任务单元测试。"""
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


class TestDiplomaticMission(unittest.TestCase):
    """外交任务接取、推进、结算相关测试用例。"""

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
        self.save_path = "test_diplomatic_mission_save.json"
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
        """加入天剑宗并提升到内门弟子，补充足够贡献。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        self.player.sect_rank = "inner"
        self.player.sect_contribution = 10000

    def test_can_accept_requires_sect(self):
        """未加入宗门时不能接取外交任务。"""
        ok, msg = self.engine.sect_manager.can_accept_diplomatic_mission(
            "gift_to_friend", "zixiao_palace"
        )
        self.assertFalse(ok)
        self.assertIn("尚未加入", msg)

    def test_can_accept_requires_rank(self):
        """职位不足时不能接取外交任务。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        self.player.sect_rank = "outer"
        ok, msg = self.engine.sect_manager.can_accept_diplomatic_mission(
            "gift_to_friend", "zixiao_palace"
        )
        self.assertFalse(ok)
        self.assertIn("职位", msg)

    def test_can_accept_requires_relation(self):
        """目标宗门关系不符合任务要求时不能接取。"""
        self._join_sect()
        # gift_to_friend 需要友好关系，xie_mo_cult 为敌对
        ok, msg = self.engine.sect_manager.can_accept_diplomatic_mission(
            "gift_to_friend", "xie_mo_cult"
        )
        self.assertFalse(ok)
        self.assertIn("关系", msg)

    def test_can_accept_requires_contribution(self):
        """贡献不足时不能接取外交任务。"""
        self._join_sect()
        self.player.sect_contribution = 100
        ok, msg = self.engine.sect_manager.can_accept_diplomatic_mission(
            "gift_to_friend", "zixiao_palace"
        )
        self.assertFalse(ok)
        self.assertIn("贡献不足", msg)

    def test_accept_diplomatic_mission(self):
        """正常接取外交任务应扣除贡献并设置状态。"""
        self._join_sect()
        con_before = self.player.sect_contribution
        ok, msg = self.engine.sect_manager.accept_diplomatic_mission(
            "gift_to_friend", "zixiao_palace"
        )
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.sect_contribution, con_before - 300)
        self.assertIsNotNone(self.player.sect_diplomatic_mission)
        self.assertEqual(
            self.player.sect_diplomatic_mission["mission_id"], "gift_to_friend"
        )
        self.assertEqual(
            self.player.sect_diplomatic_mission["target_sect_id"], "zixiao_palace"
        )

    def test_tick_success(self):
        """外交任务到期成功应提升关系并发放奖励。"""
        self._join_sect()
        self.engine.sect_manager.accept_diplomatic_mission(
            "gift_to_friend", "zixiao_palace"
        )
        # 推进到任务结束月份之后
        end_month = self.player.sect_diplomatic_mission["end_month"]
        self.world.year = end_month // 12
        self.world.month = end_month % 12 + 1

        rel_before = self.engine.sect_manager.get_sect_relationship("zixiao_palace")
        con_before = self.player.sect_contribution
        loyalty_before = self.player.sect_loyalty

        # 强制成功
        with patch("game.sect.random.random", return_value=0.0):
            messages = self.engine.sect_manager.tick_diplomatic_mission(
                self.world.year, self.world.month
            )

        self.assertEqual(len(messages), 1)
        self.assertIn("成功", messages[0])
        self.assertIsNone(self.player.sect_diplomatic_mission)
        self.assertGreater(
            self.engine.sect_manager.get_sect_relationship("zixiao_palace"),
            rel_before,
        )
        self.assertEqual(self.player.sect_contribution, con_before + 100)
        self.assertEqual(self.player.sect_loyalty, min(100, loyalty_before + 5))

    def test_tick_failure(self):
        """外交任务到期失败应只产生少量关系惩罚。"""
        self._join_sect()
        self.engine.sect_manager.accept_diplomatic_mission(
            "gift_to_friend", "zixiao_palace"
        )
        end_month = self.player.sect_diplomatic_mission["end_month"]
        self.world.year = end_month // 12
        self.world.month = end_month % 12 + 1

        rel_before = self.engine.sect_manager.get_sect_relationship("zixiao_palace")
        con_before = self.player.sect_contribution

        # 强制失败
        with patch("game.sect.random.random", return_value=1.0):
            messages = self.engine.sect_manager.tick_diplomatic_mission(
                self.world.year, self.world.month
            )

        self.assertEqual(len(messages), 1)
        self.assertIn("失败", messages[0])
        self.assertIsNone(self.player.sect_diplomatic_mission)
        # 失败惩罚为关系变化量的 -30%，不应超过成功时的提升幅度
        self.assertLessEqual(
            self.engine.sect_manager.get_sect_relationship("zixiao_palace"),
            rel_before,
        )
        # 失败后不应获得贡献奖励
        self.assertEqual(self.player.sect_contribution, con_before)

    def test_cancel_diplomatic_mission(self):
        """取消任务应清空状态且不退还贡献。"""
        self._join_sect()
        self.engine.sect_manager.accept_diplomatic_mission(
            "gift_to_friend", "zixiao_palace"
        )
        con_before = self.player.sect_contribution
        ok, msg = self.engine.sect_manager.cancel_diplomatic_mission()
        self.assertTrue(ok, msg)
        self.assertIsNone(self.player.sect_diplomatic_mission)
        self.assertEqual(self.player.sect_contribution, con_before)

    def test_engine_accept_diplomatic_mission(self):
        """Engine 封装方法应正确转发并持久化状态。"""
        self._join_sect()
        ok = self.engine.sect_accept_diplomatic_mission(
            "gift_to_friend", "zixiao_palace"
        )
        self.assertTrue(ok)
        self.assertEqual(
            self.player.sect_diplomatic_mission["mission_id"], "gift_to_friend"
        )

    def test_get_available_missions(self):
        """获取可接外交任务应过滤职位要求。"""
        self._join_sect()
        missions = self.engine.sect_manager.get_available_diplomatic_missions()
        # 内门弟子可接全部三种任务
        self.assertEqual(len(missions), 3)
        mission_ids = {m["id"] for m in missions}
        self.assertEqual(
            mission_ids, {"gift_to_friend", "sabotage_enemy", "mediate_neutral"}
        )


if __name__ == "__main__":
    unittest.main()
