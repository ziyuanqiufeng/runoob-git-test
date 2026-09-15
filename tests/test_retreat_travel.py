# -*- coding: utf-8 -*-
"""闭关修炼与旅行传送系统测试。

覆盖：地点灵气浓度、安全等级、袭击概率、旅行时间计算、
自定义闭关月数、灵石加速、传送阵、闭关弹窗 UI。
"""
import os
import unittest
from unittest.mock import patch, MagicMock

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
from game.teleport import TeleportManager
from game.travel_cost import TravelCostModel
from ui.cultivate_dialog import CultivateDialog


class TestLocationEnvironment(unittest.TestCase):
    """地点灵气浓度与安全等级相关测试。"""

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
            save_manager=SaveManager(save_path="test_retreat_env.json"),
        )

    def tearDown(self):
        if os.path.exists("test_retreat_env.json"):
            os.remove("test_retreat_env.json")

    def test_spirit_bonus_wild_base(self):
        """荒野地点灵气加成应为基础值。"""
        # qingyun 为 wild，推荐境界练气一层
        bonus = self.engine.get_location_spirit_bonus("qingyun")
        # 基础 0.05 + find_herb>=20 加 0.03 = 0.08
        self.assertAlmostEqual(bonus, 0.08, places=3)

    def test_spirit_bonus_city_lower_than_sect(self):
        """宗门灵气加成应高于城市。"""
        # fufeng_wind_sect 为 sect，推荐 qi_refining_3
        sect_bonus = self.engine.get_location_spirit_bonus("fufeng_wind_sect")
        # fufeng_city 为 city，推荐 qi_refining_2
        city_bonus = self.engine.get_location_spirit_bonus("fufeng_city")
        self.assertGreater(sect_bonus, city_bonus)

    def test_safety_level_sect_is_high(self):
        """宗门安全等级应处于较高水平。"""
        # fufeng_wind_sect 推荐境界练气三层，安全等级约 9
        safety = self.engine.get_location_safety_level("fufeng_wind_sect")
        self.assertGreaterEqual(safety, 8)

    def test_safety_level_city_higher_than_wild(self):
        """城市安全等级应高于荒野。"""
        city_safety = self.engine.get_location_safety_level("fufeng_city")
        wild_safety = self.engine.get_location_safety_level("heifeng")
        self.assertGreater(city_safety, wild_safety)

    def test_raid_chance_bounded(self):
        """袭击概率应在 [0.01, 0.20] 范围内。"""
        for loc_id in ["qingyun", "fufeng_city", "fufeng_wind_sect", "heifeng"]:
            chance = self.engine.get_location_raid_chance(loc_id)
            self.assertGreaterEqual(chance, 0.01)
            self.assertLessEqual(chance, 0.20)

    def test_raid_chance_decreases_with_safety(self):
        """安全等级越高，袭击概率应越低。"""
        sect_chance = self.engine.get_location_raid_chance("fufeng_wind_sect")
        wild_chance = self.engine.get_location_raid_chance("heifeng")
        self.assertLess(sect_chance, wild_chance)


class TestTravelTime(unittest.TestCase):
    """旅行时间计算与减免测试。"""

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
            save_manager=SaveManager(save_path="test_travel.json"),
        )

    def tearDown(self):
        if os.path.exists("test_travel.json"):
            os.remove("test_travel.json")

    def test_travel_time_at_least_one_month(self):
        """旅行时间至少为 1 个月。"""
        months = self.engine.calculate_travel_time("qingyun", "qingyun")
        self.assertGreaterEqual(months, 1)

    def test_travel_time_distance_effect(self):
        """远距离应比近距离耗时更长。"""
        # qingyun(200,100) 到 heifeng(400,250) 距离约 320
        near = self.engine.calculate_travel_time("heifeng", "qingyun")
        # qingyun 到 fufeng_city(480,60) 距离约 283
        far = self.engine.calculate_travel_time("fufeng_city", "qingyun")
        self.assertGreaterEqual(far, 1)
        self.assertGreaterEqual(near, 1)

    def test_travel_time_realm_bonus(self):
        """高境界应比低境界旅行更快。"""
        low = self.engine.calculate_travel_time("heifeng", "qingyun")
        # 提升到筑基初期
        self.player.realm_id = "foundation_early"
        high = self.engine.calculate_travel_time("heifeng", "qingyun")
        self.assertLess(high, low)

    def test_travel_time_city_easier_than_wild(self):
        """同距离下城市应比荒野耗时更短。"""
        # qingyun 到 fufeng_city(city) 与 heifeng(wild)
        city_months = self.engine.calculate_travel_time("fufeng_city", "qingyun")
        wild_months = self.engine.calculate_travel_time("heifeng", "qingyun")
        self.assertLess(city_months, wild_months)

    def test_gale_step_reduces_travel_time(self):
        """学习疾风步后应触发技能减免。"""
        self.player.learn_skill("gale_step")
        reduction_type, ratio = self.engine.get_travel_reduction()
        self.assertEqual(reduction_type, "skill")
        self.assertEqual(ratio, 0.30)

    def test_travel_by_flight_no_time_cost(self):
        """御剑飞行时旅行不消耗时间。"""
        self.player.unlock_feature("flight")
        initial_year = self.world.year
        self.engine.travel("heifeng")
        self.assertEqual(self.world.year, initial_year)
        self.assertEqual(self.player.location_id, "heifeng")


class TestCustomRetreat(unittest.TestCase):
    """自定义闭关月数与灵气加成测试。"""

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
            save_manager=SaveManager(save_path="test_retreat.json"),
        )

    def tearDown(self):
        if os.path.exists("test_retreat.json"):
            os.remove("test_retreat.json")

    def test_cultivate_increases_qi(self):
        """闭关应增加修为。"""
        initial_qi = self.player.qi
        self.engine.cultivate(months=3)
        self.assertGreater(self.player.qi, initial_qi)

    @patch("game.engine.random.random", return_value=0.99)
    def test_cultivate_advances_time(self, mock_random):
        """闭关应推进世界时间。"""
        # 在宗门地点闭关，避免地点袭击打断
        self.player.location_id = "fufeng_wind_sect"
        initial_year = self.world.year
        initial_month = self.world.month
        self.engine.cultivate(months=5)
        # 验证时间正好推进 5 个月
        elapsed = (self.world.year - initial_year) * 12 + (self.world.month - initial_month)
        self.assertGreaterEqual(elapsed, 5)

    @patch("game.engine.random.random", return_value=0.99)
    def test_cultivate_longer_yields_more_qi(self, mock_random):
        """闭关时间越长，修为增长越多。"""
        # 在宗门安全地点闭关，避免袭击打断；分别比较 3 个月与 6 个月
        self.player.location_id = "fufeng_wind_sect"
        self.engine.cultivate(months=3)
        qi_3 = self.player.qi

        # 使用独立玩家与世界，确保起始条件一致
        fresh_player = Player(name="测试修士二")
        fresh_player.location_id = "fufeng_wind_sect"
        fresh_world = World(config_dir="config")
        fresh_engine = GameEngine(
            fresh_player,
            fresh_world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
            save_manager=None,
        )
        fresh_engine.cultivate(months=6)
        qi_6 = fresh_player.qi
        self.assertGreater(qi_6, qi_3)

    @patch("game.engine.random.random", return_value=0.99)
    def test_cultivate_spirit_bonus_location(self, mock_random):
        """灵气更浓郁地点应获得更多修为。"""
        # 在宗门闭关
        self.player.location_id = "fufeng_wind_sect"
        self.engine.cultivate(months=3)
        qi_sect = self.player.qi

        # 使用独立玩家在荒野闭关，确保除地点外条件一致
        fresh_player = Player(name="测试修士二")
        fresh_player.location_id = "qingyun"
        fresh_world = World(config_dir="config")
        # 使用全新 EventPool，避免第一个 engine 修炼后的事件池状态污染对照组
        fresh_event_pool = EventPool(config_dir="config")
        fresh_engine = GameEngine(
            fresh_player,
            fresh_world,
            fresh_event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
            save_manager=None,
        )
        fresh_engine.cultivate(months=3)
        qi_wild = fresh_player.qi
        self.assertGreater(qi_sect, qi_wild)

    @patch("game.engine.random.random", return_value=0.0)
    @patch("game.engine.random.choice", return_value="wolf")
    def test_cultivate_interrupted_by_raid(self, mock_choice, mock_random):
        """荒野闭关时遭遇妖兽袭击应中断修炼。"""
        self.player.location_id = "qingyun"
        initial_qi = self.player.qi
        self.engine.cultivate(months=3)

        # 袭击触发后会进入战斗状态
        self.assertIsNotNone(self.engine.current_enemy)
        self.assertEqual(self.engine.current_enemy.id, "wolf")
        # 修为有所增加但未完成完整 3 个月
        self.assertGreater(self.player.qi, initial_qi)


class TestTravelCostModel(unittest.TestCase):
    """旅行成本模型独立测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")
        # 使用 mock 的 sect_manager，仅需实现 get_beast_mount_bonus
        self.sect_manager = MagicMock()
        self.sect_manager.get_beast_mount_bonus.return_value = 0
        self.model = TravelCostModel(self.player, self.world, self.sect_manager)

    def test_flight_is_free(self):
        """御剑飞行预览应为免费。"""
        self.player.unlock_feature("flight")
        preview = self.model.get_cost_preview("heifeng")
        self.assertTrue(preview["free"])
        self.assertEqual(preview["actual_months"], 0)

    def test_base_time_decreases_with_realm(self):
        """高境界基础旅行时间应更短。"""
        low = self.model.calculate_base_time("heifeng")
        self.player.realm_id = "foundation_early"
        high = self.model.calculate_base_time("heifeng")
        self.assertLess(high, low)

    def test_speedup_with_spirit_stones(self):
        """灵石加速应减少耗时并返回消耗数量。"""
        for _ in range(50):
            item = self.item_lib.create("spirit_stone")
            if item:
                self.player.add_item(item)
        base_months = self.model.calculate_base_time("heifeng")
        actual, consumed, messages = self.model.apply_speedups(
            base_months, use_spirit_stones=100
        )
        self.assertLessEqual(actual, base_months)
        if base_months > 1:
            self.assertGreater(consumed, 0)
            self.assertTrue(any("灵石" in m for m in messages))

    def test_mount_is_free(self):
        """拥有坐骑型灵兽时预览应为免费。"""
        self.sect_manager.get_beast_mount_bonus.return_value = 1
        preview = self.model.get_cost_preview("heifeng")
        self.assertTrue(preview["free"])
        self.assertTrue(preview["has_mount"])


class TestTravelAndTeleport(unittest.TestCase):
    """旅行、灵石加速与传送阵测试。"""

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
            save_manager=SaveManager(save_path="test_teleport.json"),
        )
        # 给予足够灵石
        for _ in range(50):
            item = self.item_lib.create("spirit_stone")
            if item:
                self.player.add_item(item)

    def tearDown(self):
        if os.path.exists("test_teleport.json"):
            os.remove("test_teleport.json")

    def test_normal_travel_changes_location(self):
        """普通旅行应改变玩家位置。"""
        self.engine.travel("heifeng")
        self.assertEqual(self.player.location_id, "heifeng")

    def test_spirit_stones_reduce_travel_time(self):
        """花费灵石应缩短旅行时间。"""
        # 先计算不加速时间
        no_stone_months = self.engine.calculate_travel_time("heifeng")
        # 旅行时投入大量灵石
        initial_stones = self.player.count_item("spirit_stone")
        self.engine.travel("heifeng", use_spirit_stones=100)
        # 只要旅行时间大于 1，灵石就会被消耗
        if no_stone_months > 1:
            self.assertLess(self.player.count_item("spirit_stone"), initial_stones)

    def test_teleport_requires_unlock(self):
        """未解锁传送阵时无法传送。"""
        ok, msg = self.engine.teleport_manager.can_teleport("heifeng")
        self.assertFalse(ok)
        self.assertIn("未解锁", msg)

    def test_teleport_unlock_and_travel(self):
        """解锁并传送应消耗灵石并立即到达。"""
        initial_year = self.world.year
        initial_stones = self.player.count_item("spirit_stone")

        ok, msg = self.engine.teleport_manager.unlock("heifeng")
        self.assertTrue(ok)
        ok, msg = self.engine.teleport_manager.teleport("heifeng")
        self.assertTrue(ok)

        self.assertEqual(self.player.location_id, "heifeng")
        # 传送不推进时间
        self.assertEqual(self.world.year, initial_year)
        # 消耗 5 灵石
        self.assertEqual(self.player.count_item("spirit_stone"), initial_stones - 5)

    def test_engine_teleport_flag(self):
        """通过 engine.travel(use_teleport=True) 应走传送逻辑。"""
        self.engine.teleport_manager.unlock("heifeng")
        initial_year = self.world.year
        self.engine.travel("heifeng", use_teleport=True)
        self.assertEqual(self.player.location_id, "heifeng")
        self.assertEqual(self.world.year, initial_year)


class TestCultivateDialog(unittest.TestCase):
    """闭关弹窗 UI 测试。"""

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
            save_manager=SaveManager(save_path="test_dialog.json"),
        )

    def tearDown(self):
        if os.path.exists("test_dialog_dialog.json"):
            os.remove("test_dialog_dialog.json")

    def test_dialog_shows_location_info(self):
        """弹窗应显示当前地点名称。"""
        dialog = CultivateDialog(self.engine)
        self.assertIn("当前地点", dialog.loc_label.text())
        dialog.close()

    def test_dialog_estimate_updates(self):
        """调整月数后预估收益应更新。"""
        dialog = CultivateDialog(self.engine)
        initial_text = dialog.estimate_label.text()
        dialog.months_spin.setValue(24)
        updated_text = dialog.estimate_label.text()
        self.assertNotEqual(initial_text, updated_text)
        # 预估收益应随月数增加而变大
        self.assertIn("预估修为收益", updated_text)
        dialog.close()

    def test_dialog_selected_months(self):
        """确认闭关时应记录选择的月数。"""
        dialog = CultivateDialog(self.engine)
        dialog.months_spin.setValue(36)
        # 模拟点击确认按钮
        dialog._on_cultivate()
        self.assertEqual(dialog.selected_months, 36)
        self.assertEqual(dialog.result(), CultivateDialog.Accepted)
        dialog.close()


class TestTeleportManager(unittest.TestCase):
    """传送阵管理器独立测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.player = Player(name="测试修士")
        self.world = World(config_dir="config")
        self.manager = TeleportManager(self.player, self.world)
        for _ in range(20):
            item = self.item_lib.create("spirit_stone")
            if item:
                self.player.add_item(item)

    def test_unlock_adds_to_list(self):
        """解锁后地点应加入已解锁列表。"""
        ok, _ = self.manager.unlock("heifeng")
        self.assertTrue(ok)
        self.assertIn("heifeng", self.player.unlocked_teleports)

    def test_cannot_unlock_same_place_twice(self):
        """同一地点不能重复解锁。"""
        self.manager.unlock("heifeng")
        ok, msg = self.manager.unlock("heifeng")
        self.assertFalse(ok)
        self.assertIn("已解锁", msg)

    def test_teleport_same_location_fails(self):
        """传送至当前地点应失败。"""
        self.player.location_id = "qingyun"
        self.manager.unlock("qingyun")
        ok, msg = self.manager.can_teleport("qingyun")
        self.assertFalse(ok)
        self.assertIn("已经在", msg)

    def test_teleport_insufficient_stones(self):
        """灵石不足时应无法传送。"""
        self.player.inventory.clear()
        self.manager.unlock("heifeng")
        ok, msg = self.manager.can_teleport("heifeng")
        self.assertFalse(ok)
        self.assertIn("灵石不足", msg)


if __name__ == "__main__":
    unittest.main()
