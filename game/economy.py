# -*- coding: utf-8 -*-
"""经济系统配置与价格修正计算。

负责加载 config/economy.json，并提供统一的价格参数查询接口，
避免 engine.py 中硬编码各类经济数值。
"""
import json
import os


class EconomyConfig:
    """经济配置：加载 economy.json 并提供价格修正参数。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "economy.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_base_multipliers(self):
        """返回基础 (buy, sell) 倍率。"""
        base = self.data.get("base_multipliers", {})
        return base.get("buy", 1.2), base.get("sell", 0.6)

    def get_relationship_params(self):
        """返回好感度折扣参数。"""
        return self.data.get("relationship_discount", {})

    def get_price_limits(self):
        """返回购买/出售倍率上下限。"""
        return self.data.get("price_limits", {})

    def get_festival_discount(self):
        """返回节日折扣倍率。"""
        return self.data.get("festival_discount", 0.9)

    def get_location_type_modifier(self, location_type):
        """返回某地点类型的价格修正。"""
        modifiers = self.data.get("location_type_modifiers", {})
        mod = modifiers.get(location_type, {})
        return mod.get("buy", 1.0), mod.get("sell", 1.0)
