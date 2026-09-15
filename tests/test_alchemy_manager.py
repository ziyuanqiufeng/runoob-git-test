# -*- coding: utf-8 -*-
"""炼丹管理器单元测试。"""
import unittest
import random

from game.player import Player
from game.item import ItemLibrary
from game.residence import ResidenceManager, ResidenceConfig
from game.alchemy_manager import AlchemyManager


class FixedRNG:
    """固定序列的伪随机数生成器，用于可重复测试。"""

    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def random(self):
        value = self.values[self.index % len(self.values)]
        self.index += 1
        return value


class TestAlchemyManager(unittest.TestCase):
    """AlchemyManager 核心功能测试。"""

    def setUp(self):
        """初始化测试玩家与炼丹环境。"""
        self.player = Player(name="测试丹修")
        self.item_lib = ItemLibrary(config_dir="config")
        # 提供充足灵石与材料
        for _ in range(1000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        for _ in range(100):
            self.player.add_item(self.item_lib.create("low_herb"))
        for _ in range(100):
            self.player.add_item(self.item_lib.create("spirit_liquid"))
        for _ in range(50):
            self.player.add_item(self.item_lib.create("century_herb"))
        for _ in range(50):
            self.player.add_item(self.item_lib.create("demon_core"))
        # 初始化洞府管理器并购买洞府（含炼丹室）
        self.residence_manager = ResidenceManager(
            self.player, item_library=self.item_lib
        )
        self.residence_manager.buy_residence("cloud_peak_cave")
        self.manager = AlchemyManager(
            self.player, self.item_lib, self.residence_manager
        )
        # 学会回春丹丹方
        self.player.learned_recipes.append("health_pill_recipe")

    def test_get_learned_recipes(self):
        """应只返回已习得的炼丹类配方。"""
        recipes = self.manager.get_learned_recipes()
        self.assertEqual(len(recipes), 1)
        self.assertEqual(recipes[0]["id"], "health_pill_recipe")

    def test_can_craft_without_recipe(self):
        """未习得丹方时应不可炼制。"""
        ok, msg = self.manager.can_craft("qi_pill_recipe")
        self.assertFalse(ok)
        self.assertIn("尚未掌握", msg)

    def test_can_craft_without_materials(self):
        """材料不足时应不可炼制。"""
        # 消耗掉所有 low_herb
        self.player.consume_items("low_herb", self.player.count_item("low_herb"))
        ok, msg = self.manager.can_craft("health_pill_recipe")
        self.assertFalse(ok)
        self.assertIn("材料不足", msg)

    def test_can_craft_success(self):
        """条件满足时应可炼制。"""
        ok, msg = self.manager.can_craft("health_pill_recipe")
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_craft_success_creates_item(self):
        """炼丹成功应产出丹药并扣除材料。"""
        before_count = self.player.count_item("health_pill")
        before_herb = self.player.count_item("low_herb")
        before_liquid = self.player.count_item("spirit_liquid")
        # 固定 RNG 使第一次判定成功
        rng = FixedRNG([0.1])
        success, msg, produced = self.manager.craft(
            "health_pill_recipe", rng=rng
        )
        self.assertTrue(success)
        self.assertEqual(len(produced), 1)
        self.assertEqual(self.player.count_item("health_pill"), before_count + 1)
        self.assertEqual(self.player.count_item("low_herb"), before_herb - 2)
        self.assertEqual(
            self.player.count_item("spirit_liquid"), before_liquid - 1
        )

    def test_craft_failure_no_product(self):
        """炼丹失败不应产出丹药。"""
        before_count = self.player.count_item("health_pill")
        # 固定 RNG 使判定失败
        rng = FixedRNG([0.99])
        success, msg, produced = self.manager.craft(
            "health_pill_recipe", rng=rng
        )
        self.assertFalse(success)
        self.assertEqual(len(produced), 0)
        self.assertEqual(self.player.count_item("health_pill"), before_count)

    def test_craft_quality_applied(self):
        """成功时应根据品质修改物品名称与效果。"""
        # roll=0 时 quality_score 最高，应出极品
        rng = FixedRNG([0.0])
        success, msg, produced = self.manager.craft(
            "health_pill_recipe", rng=rng
        )
        self.assertTrue(success)
        item = produced[0]
        self.assertIsNotNone(item.quality)
        self.assertIn(item.quality, ["普通", "上品", "极品"])
        # 极品时效果应提升
        if item.quality == "极品":
            self.assertIn("极品", item.name)
            self.assertGreater(item.effects.get("health", 0), 30)

    def test_craft_batch(self):
        """批量炼制应正确消耗并产出对应数量。"""
        before_count = self.player.count_item("health_pill")
        # 3 次全部成功
        rng = FixedRNG([0.1, 0.1, 0.1])
        success, msg, produced = self.manager.craft(
            "health_pill_recipe", batch=3, rng=rng
        )
        self.assertTrue(success)
        self.assertEqual(len(produced), 3)
        self.assertEqual(self.player.count_item("health_pill"), before_count + 3)

    def test_dan_xiu_bonus(self):
        """丹修流派应提高成功率。"""
        base_rate = self.manager._compute_success_rate(
            self.manager.get_recipe("health_pill_recipe")
        )
        self.player.cultivation_path = "dan_xiu"
        dan_rate = self.manager._compute_success_rate(
            self.manager.get_recipe("health_pill_recipe")
        )
        self.assertGreater(dan_rate, base_rate)

    def test_preview(self):
        """preview 应返回材料消耗与成功率信息。"""
        ok, msg, info = self.manager.preview("health_pill_recipe", batch=2)
        self.assertTrue(ok)
        self.assertGreater(info["success_rate"], 0)
        self.assertEqual(info["product_count"], 2)
        # 材料需求应乘以 batch
        for mat in info["materials"]:
            self.assertTrue(mat["enough"])


if __name__ == "__main__":
    unittest.main()
