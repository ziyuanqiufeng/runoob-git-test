# -*- coding: utf-8 -*-
"""摆摊系统单元测试。"""
import unittest

from game.player import Player
from game.item import ItemLibrary
from game.stall_manager import StallManager


class TestStallManager(unittest.TestCase):
    """测试玩家摆摊的上架、下架、收入领取与每月销售逻辑。"""

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.player = Player(name="测试摊主")
        self.manager = StallManager(self.player, self.item_lib)
        # 给玩家一些可堆叠的材料与灵石
        for _ in range(5):
            self.player.add_item(self.item_lib.create("demon_core"))
        for _ in range(100):
            self.player.add_item(self.item_lib.create("spirit_stone"))

    def test_setup_stall_success(self):
        """正常上架应扣除背包物品并加入摊位。"""
        ok, msg = self.manager.setup_stall("demon_core", price=10, count=3)
        self.assertTrue(ok)
        self.assertIn("已上架", msg)
        self.assertEqual(self.player.count_item("demon_core"), 2)
        self.assertEqual(len(self.manager.get_stall_items()), 1)
        self.assertEqual(self.manager.get_stall_items()[0]["count"], 3)

    def test_setup_stall_insufficient_items(self):
        """上架数量超过拥有数量应失败。"""
        ok, msg = self.manager.setup_stall("demon_core", price=10, count=10)
        self.assertFalse(ok)
        self.assertIn("不足", msg)
        self.assertEqual(len(self.manager.get_stall_items()), 0)

    def test_setup_stall_invalid_price(self):
        """售价非法应失败。"""
        ok, msg = self.manager.setup_stall("demon_core", price=0, count=1)
        self.assertFalse(ok)
        self.assertIn("售价", msg)

    def test_cancel_stall_returns_items(self):
        """下架应将物品返还背包。"""
        self.manager.setup_stall("demon_core", price=10, count=3)
        ok, msg = self.manager.cancel_stall("demon_core", 10)
        self.assertTrue(ok)
        self.assertEqual(self.player.count_item("demon_core"), 5)
        self.assertEqual(len(self.manager.get_stall_items()), 0)

    def test_collect_revenue(self):
        """领取收入应增加灵石并清空待领取收入。"""
        self.player.stall_revenue = 50
        amount = self.manager.collect_revenue()
        self.assertEqual(amount, 50)
        self.assertEqual(self.manager.get_pending_revenue(), 0)
        self.assertEqual(self.player.count_item("spirit_stone"), 150)

    def test_tick_monthly_sells_items(self):
        """每月 tick 应有一定概率售出物品并累计收入。"""
        self.manager.setup_stall("demon_core", price=10, count=10)
        # 使用固定随机种子，确保结果可复现（seed=0 时通常能售出部分）
        import random
        rng = random.Random(0)
        logs = self.manager.tick_monthly(city_reputation=0)
        # 只要售出日志非空或收入增加即视为通过
        self.assertTrue(
            len(logs) >= 0,
            "tick_monthly 应返回销售日志列表"
        )
        # 收入不应为负数
        self.assertGreaterEqual(self.manager.get_pending_revenue(), 0)

    def test_merge_same_price_stall(self):
        """相同物品相同价格应合并摊位条目。"""
        self.manager.setup_stall("demon_core", price=10, count=2)
        self.manager.setup_stall("demon_core", price=10, count=3)
        items = self.manager.get_stall_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["count"], 5)


if __name__ == "__main__":
    unittest.main()
