# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock

from game.player import Player
from game.item import ItemLibrary
from game.residence import ResidenceManager, ResidenceConfig


class TestResidenceManager(unittest.TestCase):
    """洞府系统测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.item_lib = ItemLibrary(config_dir="config")
        # 给玩家充足灵石
        for _ in range(10000):
            self.player.inventory.append(self.item_lib.create("spirit_stone"))
        self.player.sect_contribution = 5000
        self.manager = ResidenceManager(self.player, item_library=self.item_lib)

    def test_initial_no_residence(self):
        """初始状态应无洞府。"""
        self.assertIsNone(self.player.residence)

    def test_buy_residence(self):
        """购买洞府应扣除灵石与贡献并写入玩家数据。"""
        ok, msg = self.manager.buy_residence("cloud_peak_cave")
        self.assertTrue(ok, msg)
        self.assertEqual(self.player.residence["id"], "cloud_peak_cave")
        self.assertLess(self.player.count_item("spirit_stone"), 10000)
        self.assertLess(self.player.sect_contribution, 5000)

    def test_cannot_buy_two_residences(self):
        """已拥有洞府时不能再次购买。"""
        self.manager.buy_residence("cloud_peak_cave")
        ok, msg = self.manager.buy_residence("frost_lake_palace")
        self.assertFalse(ok)
        self.assertIn("已拥有", msg)

    def test_upgrade_building(self):
        """升级建筑应提升等级并扣除灵石。"""
        self.manager.buy_residence("cloud_peak_cave")
        money_before = self.player.count_item("spirit_stone")
        ok, msg = self.manager.upgrade_building("spirit_gathering_array")
        self.assertTrue(ok, msg)
        self.assertEqual(
            self.player.residence["buildings"]["spirit_gathering_array"], 1
        )
        self.assertLess(self.player.count_item("spirit_stone"), money_before)

    def test_upgrade_building_max_level(self):
        """建筑达到最高等级后不能再升级。"""
        self.manager.buy_residence("cloud_peak_cave")
        building = self.manager.config.get_building(
            "cloud_peak_cave", "spirit_gathering_array"
        )
        max_level = building["max_level"]
        for _ in range(max_level):
            self.manager.upgrade_building("spirit_gathering_array")
        ok, msg = self.manager.upgrade_building("spirit_gathering_array")
        self.assertFalse(ok)
        self.assertIn("最高等级", msg)

    def test_cultivation_speed_bonus(self):
        """聚灵阵应提供修炼速度加成。"""
        self.manager.buy_residence("cloud_peak_cave")
        self.assertEqual(self.manager.get_cultivation_speed_bonus(), 0.0)
        self.manager.upgrade_building("spirit_gathering_array")
        self.assertAlmostEqual(self.manager.get_cultivation_speed_bonus(), 0.05)

    def test_herb_production(self):
        """药园应正确计算产出概率。"""
        self.manager.buy_residence("cloud_peak_cave")
        self.manager.upgrade_building("herb_garden")
        production = self.manager.get_herb_production()
        self.assertEqual(len(production), 1)
        self.assertEqual(production[0]["herb_id"], "century_herb")
        self.assertAlmostEqual(production[0]["chance"], 0.1)

    def test_tick_monthly_production(self):
        """每月结算时药园应产出灵草。"""
        self.manager.buy_residence("cloud_peak_cave")
        self.manager.upgrade_building("herb_garden")
        rng = MagicMock()
        rng.random.return_value = 0.0  # 强制产出
        result = self.manager.tick_monthly(rng=rng)
        self.assertIn("century_herb", result["production"])
        self.assertGreater(
            self.player.count_item("century_herb"), 0
        )

    def test_raid_defense(self):
        """护府阵法应降低袭击概率。"""
        self.manager.buy_residence("cloud_peak_cave")
        base_chance = self.manager.config.get_raid_config()["base_chance"]
        # 未升级时无防御
        self.assertEqual(self.manager.get_raid_defense(), 0.0)
        for _ in range(5):
            self.manager.upgrade_building("defense_formation")
        defense = self.manager.get_raid_defense()
        self.assertGreater(defense, 0.0)
        self.assertLessEqual(defense, 0.9)

    def test_tick_monthly_raid(self):
        """每月结算时应可能触发袭击。"""
        self.manager.buy_residence("cloud_peak_cave")
        rng = MagicMock()
        rng.random.return_value = 0.0  # 强制产出与袭击都触发
        rng.choice.return_value = "wolf"
        rng.uniform.return_value = 0.1
        result = self.manager.tick_monthly(rng=rng)
        self.assertIsNotNone(result["raid"])
        self.assertEqual(result["raid"]["enemy_id"], "wolf")


if __name__ == "__main__":
    unittest.main()
