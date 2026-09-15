"""宗门设施系统单元测试。"""
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


class TestSectFacility(unittest.TestCase):
    """宗门设施相关测试用例。"""

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
        self.save_path = "test_facility_save.json"
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
        """加入天剑宗并获取足够贡献。"""
        self.engine.sect_manager.join_sect("tianjian_sect")
        self.player.sect_contribution = 1000

    def test_outer_can_use_spirit_gathering_array(self):
        """外门弟子可以使用聚灵阵。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.can_use_facility("spirit_gathering_array")
        self.assertTrue(ok, msg)

    def test_outer_cannot_use_alchemy_room(self):
        """外门弟子无法使用需内门职位的炼丹房。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.can_use_facility("alchemy_room")
        self.assertFalse(ok)
        self.assertIn("职位", msg)

    def test_use_spirit_gathering_array_adds_effect(self):
        """使用聚灵阵后应添加持续修炼加成效果。"""
        self._join_sect()
        ok, msg = self.engine.sect_manager.use_facility("spirit_gathering_array")
        self.assertTrue(ok, msg)
        self.assertIn("聚灵阵", msg)
        self.assertIn("spirit_gathering_array", self.player.active_facility_effects)
        bonus = self.engine.sect_manager.get_facility_cultivation_bonus()
        self.assertGreater(bonus, 0)

    def test_use_alchemy_room_gives_items(self):
        """使用炼丹房应立即获得丹药。"""
        self._join_sect()
        self.player.sect_rank = "inner"
        before = self.player.count_item("health_pill")
        ok, msg = self.engine.sect_manager.use_facility("alchemy_room")
        self.assertTrue(ok, msg)
        after = self.player.count_item("health_pill")
        self.assertGreater(after, before)

    def test_facility_cultivation_bonus_in_cultivate(self):
        """激活聚灵阵后修炼应获得更多修为。"""
        self._join_sect()
        self.engine.sect_manager.use_facility("spirit_gathering_array")

        # 屏蔽天气、心境、洞府等外部随机加成，只验证设施效果
        with patch.object(
            self.engine.weather_manager, "get_cultivation_speed_bonus", return_value=0.0
        ), patch.object(
            self.engine.mental_state_manager, "get_cultivation_speed_bonus", return_value=0.0
        ), patch.object(
            self.engine.residence_manager, "get_cultivation_speed_bonus", return_value=0.0
        ), patch.object(
            self.engine.weather_manager, "advance", return_value=(False, None, None, None, None)
        ), patch.object(
            self.engine.mental_state_manager, "tick_monthly", return_value=(0, 0, [])
        ), patch.object(
            self.engine.residence_manager, "tick_monthly", return_value={"production": [], "raid": None}
        ):
            # 记录聚灵阵生效时的修炼收益
            qi_before = self.player.qi
            self.engine.cultivate(1)
            gain_with = self.player.qi - qi_before

            # 移除效果后再修炼一次
            self.player.active_facility_effects.clear()
            qi_before = self.player.qi
            self.engine.cultivate(1)
            gain_without = self.player.qi - qi_before

        self.assertGreater(gain_with, gain_without)

    def test_facility_effect_expires(self):
        """聚灵阵效果应在持续月份结束后消失。"""
        self._join_sect()
        self.engine.sect_manager.use_facility("spirit_gathering_array")
        duration = self.player.active_facility_effects["spirit_gathering_array"]["remaining_months"]
        self.assertGreater(duration, 0)

        self.engine.sect_manager.tick_facility_effects(duration)
        self.assertNotIn("spirit_gathering_array", self.player.active_facility_effects)

    def test_insufficient_contribution(self):
        """贡献不足时无法使用设施。"""
        self._join_sect()
        self.player.sect_contribution = 0
        ok, msg = self.engine.sect_manager.can_use_facility("spirit_gathering_array")
        self.assertFalse(ok)
        self.assertIn("贡献", msg)


if __name__ == "__main__":
    unittest.main()
