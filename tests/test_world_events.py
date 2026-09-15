# -*- coding: utf-8 -*-
"""动态世界事件系统单元测试。"""
import unittest

from PySide6.QtWidgets import QApplication

from game.engine import GameEngine
from game.enemy import EnemyLibrary
from game.events import EventPool
from game.item import ItemLibrary
from game.npc import NPCLibrary
from game.player import Player
from game.quest import QuestLibrary
from game.skill import SkillLibrary
from game.world import World
from game.world_event import WorldEventConfig, WorldEventManager


class TestWorldEventManager(unittest.TestCase):
    """测试世界事件的触发、持续、结束与效果。"""

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
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
        )
        self.manager = self.engine.world_event_manager

    def _inject_event(self, event):
        """辅助方法：向管理器注入单个事件配置。"""
        self.manager.config.events = [event]
        self.manager.config.event_map = {event["id"]: event}

    def test_scheduled_event_trigger(self):
        """scheduled 类型事件在指定月/日触发。"""
        self._inject_event(
            {
                "id": "test_scheduled",
                "name": "测试定时事件",
                "trigger": {"type": "scheduled", "month": 3, "day": 1},
                "conditions": [],
                "effects": [{"type": "notify", "message": "定时事件触发"}],
                "duration_months": 1,
            }
        )
        self.world.month = 3
        self.world.day = 1
        self.world.year = 1
        self.manager.tick()
        self.assertIn("test_scheduled", self.player.active_world_events)

    def test_random_event_with_conditions(self):
        """random 事件在满足条件时触发。"""
        self._inject_event(
            {
                "id": "test_random",
                "name": "测试随机事件",
                "trigger": {"type": "random", "chance": 1.0, "min_year": 1},
                "conditions": [{"type": "year", "value": ">=1"}],
                "effects": [{"type": "notify", "message": "随机事件触发"}],
                "duration_months": 2,
            }
        )
        self.manager.tick()
        self.assertIn("test_random", self.player.active_world_events)
        self.assertEqual(
            self.player.active_world_events["test_random"]["remaining_months"], 2
        )

    def test_event_duration_and_expire(self):
        """事件持续指定月数后自动结束。"""
        self._inject_event(
            {
                "id": "test_duration",
                "name": "测试持续事件",
                "trigger": {"type": "scheduled", "month": 1, "day": 1},
                "conditions": [],
                "effects": [{"type": "notify", "message": "持续事件"}],
                "duration_months": 2,
            }
        )
        self.world.month = 1
        self.world.day = 1
        self.manager.tick()
        self.assertIn("test_duration", self.player.active_world_events)
        # 切换到非触发月，避免 scheduled 事件反复触发
        self.world.month = 2
        # duration=2，再推进 2 个月事件应结束
        self.manager.tick()
        self.manager.tick()
        self.assertNotIn("test_duration", self.player.active_world_events)
        self.assertIn("test_duration", self.player.world_event_history)

    def test_event_cooldown(self):
        """事件结束后冷却期内不再触发。"""
        self._inject_event(
            {
                "id": "test_cooldown",
                "name": "测试冷却事件",
                "trigger": {"type": "scheduled", "month": 1, "day": 1},
                "conditions": [],
                "effects": [],
                "duration_months": 1,
            }
        )
        self.world.month = 1
        self.world.day = 1
        self.manager.tick()
        self.assertIn("test_cooldown", self.player.active_world_events)

        # 设置 1 年冷却，再推进 1 个月使事件结束
        self.manager.config.events[0]["trigger"]["cooldown_years"] = 1
        self.manager.tick()
        self.manager.tick()
        self.assertNotIn("test_cooldown", self.player.active_world_events)

        # 同年再次到达触发日，不应再次触发
        self.world.month = 1
        self.world.day = 1
        self.manager.tick()
        self.assertNotIn("test_cooldown", self.player.active_world_events)

    def test_change_npc_location_and_revert(self):
        """事件移动 NPC 当前位置，结束后恢复。"""
        npc = self.npc_lib.get("law_enforcer")
        original = npc.current_location  # 世界事件操作的是 current_location
        self._inject_event(
            {
                "id": "test_move",
                "name": "测试移动",
                "trigger": {"type": "scheduled", "month": 1, "day": 1},
                "conditions": [],
                "effects": [
                    {
                        "type": "change_npc_location",
                        "npc_id": "law_enforcer",
                        "location": "qingyun",
                    }
                ],
                "duration_months": 1,
            }
        )
        self.world.month = 1
        self.world.day = 1
        self.manager.tick()
        self.assertEqual(npc.current_location, "qingyun")

        # 切换到非触发月，避免 scheduled 事件反复触发
        self.world.month = 2
        # 事件持续 1 个月，再推进 1 个月应结束并恢复位置
        self.manager.tick()
        self.assertEqual(npc.current_location, original)

    def test_modify_price_multiplier(self):
        """事件修改地点价格倍率。"""
        self._inject_event(
            {
                "id": "test_price",
                "name": "测试价格",
                "trigger": {"type": "scheduled", "month": 1, "day": 1},
                "conditions": [],
                "effects": [
                    {
                        "type": "modify_price_multiplier",
                        "location": "qingyun",
                        "buy_mult": 0.5,
                        "sell_mult": 2.0,
                    }
                ],
                "duration_months": 1,
            }
        )
        self.world.month = 1
        self.world.day = 1
        self.manager.tick()
        self.assertIn("qingyun", self.player.world_event_price_mods)
        mods = self.player.world_event_price_mods["qingyun"]
        self.assertEqual(mods["buy_mult"], 0.5)
        self.assertEqual(mods["sell_mult"], 2.0)

        # 切换到非触发月，避免 scheduled 事件反复触发
        self.world.month = 2
        # 事件持续 1 个月，再推进 1 个月结束并移除倍率
        self.manager.tick()
        self.assertNotIn("qingyun", self.player.world_event_price_mods)

    def test_spawn_enemy_encounter(self):
        """spawn_enemy 效果产生遭遇。"""
        self._inject_event(
            {
                "id": "test_encounter",
                "name": "测试遭遇",
                "trigger": {"type": "scheduled", "month": 1, "day": 1},
                "conditions": [],
                "effects": [
                    {
                        "type": "spawn_enemy",
                        "enemy_id": "wolf",
                        "location": "heifeng",
                        "count": 1,
                    }
                ],
                "duration_months": 3,
            }
        )
        self.world.month = 1
        self.world.day = 1
        self.manager.tick()
        enc = self.manager.get_encounter_for_location("heifeng")
        self.assertIsNotNone(enc)
        self.assertEqual(enc["enemy_id"], "wolf")

    def test_compare_parser(self):
        """测试比较字符串解析。"""
        self.assertTrue(WorldEventManager._compare(5, ">3"))
        self.assertTrue(WorldEventManager._compare(3, ">=3"))
        self.assertTrue(WorldEventManager._compare(2, "<3"))
        self.assertTrue(WorldEventManager._compare(3, "<=3"))
        self.assertTrue(WorldEventManager._compare(3, "=3"))
        self.assertFalse(WorldEventManager._compare(2, ">3"))

    def test_camp_condition(self):
        """阵营条件判断。"""
        self._inject_event(
            {
                "id": "test_camp",
                "name": "测试阵营",
                "trigger": {"type": "random", "chance": 1.0},
                "conditions": [{"type": "camp", "evil_value": ">30"}],
                "effects": [],
                "duration_months": 1,
            }
        )
        # 不满足
        self.player.evil_value = 10
        self.manager.tick()
        self.assertNotIn("test_camp", self.player.active_world_events)
        # 满足
        self.player.evil_value = 50
        self.manager.tick()
        self.assertIn("test_camp", self.player.active_world_events)


if __name__ == "__main__":
    unittest.main()
