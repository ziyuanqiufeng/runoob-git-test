# -*- coding: utf-8 -*-
"""拍卖行系统：周期性刷新稀有物品，玩家竞拍。"""
import random


class AuctionHouseManager:
    """管理拍卖行拍品列表与出价。"""

    def __init__(self, player, item_library, world):
        self.player = player
        self.item_library = item_library
        self.world = world
        # 当前拍品列表，每项 {item_id, name, base_price, current_price, bidder}
        self._lots = []
        self._last_refresh_month = -1

    def _should_refresh(self):
        current = self.world.year * 12 + self.world.month
        return current != self._last_refresh_month

    def refresh(self, lot_pool=None, count=5):
        """刷新本月拍品。"""
        if not self._should_refresh():
            return
        self._last_refresh_month = self.world.year * 12 + self.world.month
        self._lots = []
        if lot_pool is None:
            # 默认拍品池：稀有物品
            lot_pool = ["jade_pendant", "sword_manual", "marrow_pill", "iron_sword", "leather_armor"]
        for item_id in random.sample(lot_pool, min(count, len(lot_pool))):
            item = self.item_library.create(item_id)
            if item:
                base = max(10, getattr(item, "value", 20) * 2)
                self._lots.append({
                    "item_id": item_id,
                    "name": getattr(item, "name", item_id),
                    "base_price": base,
                    "current_price": base,
                    "bidder": None,
                })

    def get_lots(self):
        return self._lots

    def bid(self, lot_index, amount):
        """对某拍品出价。"""
        if lot_index < 0 or lot_index >= len(self._lots):
            return False, "拍品不存在。"
        lot = self._lots[lot_index]
        if amount <= lot["current_price"]:
            return False, "出价必须高于当前价格。"
        # 简单扣款：直接扣除玩家灵石（假设 spirit_stone 物品）
        stones = self.player.count_item("spirit_stone")
        if stones < amount:
            return False, "灵石不足。"
        # 退回上一位竞标者的灵石（简化：不处理）
        self.player.consume_items("spirit_stone", amount)
        lot["current_price"] = amount
        lot["bidder"] = "player"
        return True, f"出价成功，当前价格 {amount} 灵石。"

    def settle(self, lot_index):
        """结算拍品（玩家竞得时发放物品）。"""
        if lot_index < 0 or lot_index >= len(self._lots):
            return False, "拍品不存在。"
        lot = self._lots[lot_index]
        if lot["bidder"] != "player":
            return False, "你未竞得该物品。"
        item = self.item_library.create(lot["item_id"])
        if item:
            self.player.add_item(item)
        self._lots.pop(lot_index)
        return True, f"拍得【{lot['name']}】。"
