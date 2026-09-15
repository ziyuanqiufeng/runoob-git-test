# -*- coding: utf-8 -*-
"""拍卖行系统单元测试。"""
import unittest

from game.player import Player
from game.item import ItemLibrary
from game.world import World
from game.auction_house import AuctionHouseManager


class TestAuctionHouseManager(unittest.TestCase):
    """测试拍卖行拍品刷新、出价与结算逻辑。"""

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.player = Player(name="测试竞拍者")
        self.world = World(config_dir="config")
        self.manager = AuctionHouseManager(self.player, self.item_lib, self.world)
        # 给玩家充足灵石
        for _ in range(1000):
            self.player.add_item(self.item_lib.create("spirit_stone"))

    def test_refresh_creates_lots(self):
        """刷新应生成指定数量的拍品。"""
        self.manager.refresh(lot_pool=["jade_pendant", "sword_manual", "marrow_pill"], count=3)
        lots = self.manager.get_lots()
        self.assertEqual(len(lots), 3)
        for lot in lots:
            self.assertIn("item_id", lot)
            self.assertIn("base_price", lot)
            self.assertIn("current_price", lot)
            self.assertIsNone(lot["bidder"])

    def test_bid_success(self):
        """出价高于当前价应成功。"""
        self.manager.refresh(lot_pool=["jade_pendant"], count=1)
        ok, msg = self.manager.bid(0, 100)
        self.assertTrue(ok)
        self.assertIn("出价成功", msg)
        self.assertEqual(self.manager.get_lots()[0]["current_price"], 100)
        self.assertEqual(self.manager.get_lots()[0]["bidder"], "player")

    def test_bid_too_low_fails(self):
        """出价不高于当前价应失败。"""
        self.manager.refresh(lot_pool=["jade_pendant"], count=1)
        base = self.manager.get_lots()[0]["current_price"]
        ok, msg = self.manager.bid(0, base)
        self.assertFalse(ok)
        self.assertIn("高于", msg)

    def test_bid_insufficient_money_fails(self):
        """灵石不足时出价应失败。"""
        # 清空玩家灵石
        self.player.inventory = [
            i for i in self.player.inventory if i.id != "spirit_stone"
        ]
        self.manager.refresh(lot_pool=["jade_pendant"], count=1)
        ok, msg = self.manager.bid(0, 100)
        self.assertFalse(ok)
        self.assertIn("灵石不足", msg)

    def test_settle_success(self):
        """玩家领先的拍品结算后应获得物品。"""
        self.manager.refresh(lot_pool=["jade_pendant"], count=1)
        self.manager.bid(0, 100)
        before = self.player.count_item("jade_pendant")
        ok, msg = self.manager.settle(0)
        self.assertTrue(ok)
        self.assertIn("拍得", msg)
        self.assertEqual(self.player.count_item("jade_pendant"), before + 1)
        self.assertEqual(len(self.manager.get_lots()), 0)

    def test_settle_not_winning_fails(self):
        """未领先的拍品结算应失败。"""
        self.manager.refresh(lot_pool=["jade_pendant"], count=1)
        ok, msg = self.manager.settle(0)
        self.assertFalse(ok)
        self.assertIn("未竞得", msg)

    def test_refresh_only_once_per_month(self):
        """同一个月内重复刷新不应改变拍品。"""
        self.manager.refresh(lot_pool=["jade_pendant", "sword_manual"], count=2)
        first = [lot["item_id"] for lot in self.manager.get_lots()]
        self.manager.refresh(lot_pool=["marrow_pill", "iron_sword"], count=2)
        second = [lot["item_id"] for lot in self.manager.get_lots()]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
