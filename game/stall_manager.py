# -*- coding: utf-8 -*-
"""玩家摆摊系统。

允许玩家将背包中的物品上架到坊市摊位，设置单价与数量。
每月 tick 时根据商品价值与城池繁荣度计算售出概率，
售出后玩家获得灵石收入，未售出物品保留在摊位中。
"""
import random


class StallManager:
    """管理玩家摊位与摆摊收入。"""

    # 基础售出概率，每月对每个摊位商品判定一次
    BASE_SALE_CHANCE = 0.3

    def __init__(self, player, item_library):
        self.player = player
        self.item_library = item_library

    def get_stall_items(self):
        """获取当前摊位商品列表。"""
        return getattr(self.player, "stall_items", [])

    def get_pending_revenue(self):
        """获取待领取的摆摊收入。"""
        return getattr(self.player, "stall_revenue", 0)

    def setup_stall(self, item_id, price, count=1):
        """
        上架物品到摊位。

        参数：
            item_id: 要出售的物品 ID。
            price: 单价（灵石）。
            count: 出售数量。

        返回：
            (success, message) 元组。
        """
        if price <= 0:
            return False, "售价必须大于 0。"
        if count <= 0:
            return False, "数量必须大于 0。"

        owned = self.player.count_item(item_id)
        if owned < count:
            return False, f"背包中该物品不足（拥有 {owned} 个）。"

        # 从背包扣除物品
        if not self.player.consume_items(item_id, count):
            return False, "扣除物品失败。"

        # 初始化摊位字段
        if not hasattr(self.player, "stall_items"):
            self.player.stall_items = []
        if not hasattr(self.player, "stall_revenue"):
            self.player.stall_revenue = 0

        # 合并同类已上架物品
        for entry in self.player.stall_items:
            if entry["item_id"] == item_id and entry["price"] == price:
                entry["count"] += count
                return True, f"已上架 {item_id} ×{count}，单价 {price} 灵石。"

        self.player.stall_items.append({
            "item_id": item_id,
            "price": price,
            "count": count,
        })
        return True, f"已上架 {item_id} ×{count}，单价 {price} 灵石。"

    def cancel_stall(self, item_id, price):
        """
        下架指定商品，物品返还背包。

        返回 (success, message)。
        """
        for entry in list(self.player.stall_items):
            if entry["item_id"] == item_id and entry["price"] == price:
                count = entry["count"]
                self.player.stall_items.remove(entry)
                for _ in range(count):
                    item = self.item_library.create(item_id)
                    if item:
                        self.player.add_item(item)
                return True, f"已下架 {item_id} ×{count}，物品已返还背包。"
        return False, "未找到该摊位商品。"

    def collect_revenue(self):
        """领取摆摊收入。"""
        revenue = getattr(self.player, "stall_revenue", 0)
        if revenue <= 0:
            return 0
        for _ in range(revenue):
            item = self.item_library.create("spirit_stone")
            if item:
                self.player.add_item(item)
        self.player.stall_revenue = 0
        return revenue

    def tick_monthly(self, city_reputation=0):
        """
        每月推进摆摊销售。

        根据商品单价与价值、城池声望计算售出概率，
        售出后增加待领取收入。
        返回售出日志列表。
        """
        logs = []
        if not hasattr(self.player, "stall_items"):
            return logs

        for entry in list(self.player.stall_items):
            item_id = entry["item_id"]
            price = entry["price"]
            count = entry["count"]

            item = self.item_library.create(item_id)
            base_value = getattr(item, "value", price)

            # 售价越低、声望越高，越容易售出
            price_ratio = min(2.0, base_value / max(1, price))
            rep_bonus = min(0.3, city_reputation / 1000.0)
            chance = self.BASE_SALE_CHANCE * price_ratio + rep_bonus
            chance = max(0.05, min(0.95, chance))

            sold = 0
            for _ in range(count):
                if random.random() < chance:
                    sold += 1

            if sold > 0:
                entry["count"] -= sold
                income = sold * price
                self.player.stall_revenue += income
                logs.append(
                    f"[green]摊位售出 {item.name} ×{sold}，获得 {income} 灵石。"
                )
                if entry["count"] <= 0:
                    self.player.stall_items.remove(entry)

        return logs
