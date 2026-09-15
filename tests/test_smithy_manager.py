# -*- coding: utf-8 -*-
"""炼器台管理器单元测试。"""
import unittest

from game.player import Player
from game.item import ItemLibrary
from game.residence import ResidenceManager
from game.smithy_manager import SmithyManager


class FixedRNG:
    """固定序列的伪随机数生成器，用于可重复测试。"""

    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def random(self):
        value = self.values[self.index % len(self.values)]
        self.index += 1
        return value


class TestSmithyManager(unittest.TestCase):
    """SmithyManager 核心功能测试。"""

    def setUp(self):
        """初始化测试玩家与炼器环境。"""
        self.player = Player(name="测试器修")
        self.item_lib = ItemLibrary(config_dir="config")
        # 提供充足灵石
        for _ in range(10000):
            self.player.add_item(self.item_lib.create("spirit_stone"))
        # 购买洞府（含炼器台）
        self.residence_manager = ResidenceManager(
            self.player, item_library=self.item_lib
        )
        self.residence_manager.buy_residence("cloud_peak_cave")
        self.manager = SmithyManager(
            self.player, self.item_lib, self.residence_manager
        )
        # 添加一柄可强化装备
        self.sword = self.item_lib.create("iron_sword")
        self.player.add_item(self.sword)

    def test_list_enhanceable_items(self):
        """应能列出背包中的可强化装备。"""
        items = self.manager.list_enhanceable_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, "iron_sword")

    def test_can_enhance(self):
        """新装备应可强化。"""
        ok, msg = self.manager.can_enhance(self.sword)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_enhance_success(self):
        """强化成功应提升装备等级。"""
        rng = FixedRNG([0.1])
        success, msg, destroyed = self.manager.enhance(self.sword, rng=rng)
        self.assertTrue(success)
        self.assertFalse(destroyed)
        self.assertEqual(self.sword.enhancement_level, 1)
        self.assertIn("+1", msg)

    def test_enhance_failure_no_destroy(self):
        """低级强化失败不应损毁装备。"""
        rng = FixedRNG([0.99])
        success, msg, destroyed = self.manager.enhance(self.sword, rng=rng)
        self.assertFalse(success)
        self.assertFalse(destroyed)
        # +0 装备无惩罚
        self.assertEqual(self.sword.enhancement_level, 0)

    def test_qi_path_bonus(self):
        """器修流派应提高强化成功率。"""
        base_rate = self.manager.preview_enhance(self.sword)[2]["success_rate"]
        self.player.cultivation_path = "qi"
        qi_rate = self.manager.preview_enhance(self.sword)[2]["success_rate"]
        self.assertGreater(qi_rate, base_rate)

    def test_preview_enhance(self):
        """preview_enhance 应返回强化信息。"""
        ok, msg, info = self.manager.preview_enhance(self.sword)
        self.assertTrue(ok)
        self.assertEqual(info["current_level"], 0)
        self.assertEqual(info["next_level"], 1)
        self.assertGreater(info["success_rate"], 0)
        self.assertGreater(info["cost"], 0)

    def test_enhance_cost_deducted(self):
        """强化应扣除灵石。"""
        before = self.player.count_item("spirit_stone")
        rng = FixedRNG([0.1])
        self.manager.enhance(self.sword, rng=rng)
        after = self.player.count_item("spirit_stone")
        self.assertLess(after, before)


if __name__ == "__main__":
    unittest.main()
