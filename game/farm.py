# -*- coding: utf-8 -*-
"""灵植种植系统。"""
import json
import os
import random


class FarmConfig:
    """加载作物配置与季节信息。"""

    SEASONS = ["spring", "summer", "autumn", "winter"]

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._crops = {}
        self._load()

    def _load(self):
        path = os.path.join(self.config_dir, "crops.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            self._crops[entry["id"]] = entry

    def get_crop(self, crop_id):
        return self._crops.get(crop_id)

    def get_all_crops(self):
        return list(self._crops.values())

    @staticmethod
    def get_season(month):
        """根据世界月份返回季节：1-3春，4-6夏，7-9秋，10-12冬。"""
        return ["winter", "spring", "spring", "spring",
                "summer", "summer", "summer",
                "autumn", "autumn", "autumn",
                "winter", "winter"][month - 1]


class FarmManager:
    """管理洞府药园地块与作物生长。"""

    def __init__(self, player, item_library, world, config_dir="config"):
        self.player = player
        self.item_library = item_library
        self.world = world
        self.config = FarmConfig(config_dir)
        # 确保玩家有默认地块
        if not hasattr(player, "farm_plots") or player.farm_plots is None:
            player.farm_plots = []
        self._ensure_default_plots()

    def _ensure_default_plots(self):
        """根据洞府等级解锁地块。"""
        residence = getattr(self.player, "residence", None) or {}
        buildings = residence.get("buildings", {})
        garden_level = buildings.get("herb_garden", 0)
        max_plots = 2 + garden_level * 2
        # 扩展空地块
        while len(self.player.farm_plots) < max_plots:
            self.player.farm_plots.append(None)
        # 洞府降级时保留已有作物但不再新增
        self.player.farm_plots = self.player.farm_plots[:max_plots]

    def get_max_plots(self):
        residence = getattr(self.player, "residence", None) or {}
        buildings = residence.get("buildings", {})
        return 2 + buildings.get("herb_garden", 0) * 2

    def can_plant(self, plot_index, crop_id):
        """检查是否可以在指定地块种植。"""
        if plot_index < 0 or plot_index >= len(self.player.farm_plots):
            return False, "地块不存在。"
        if self.player.farm_plots[plot_index] is not None:
            return False, "该地块已有作物。"
        crop = self.config.get_crop(crop_id)
        if not crop:
            return False, "未知作物。"
        seed_id = crop.get("seed_item_id")
        if seed_id and self.player.count_item(seed_id) < 1:
            return False, f"缺少种子【{seed_id}】。"
        order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
        if order < crop.get("requirements", {}).get("min_realm_order", 1):
            return False, "境界不足，无法种植该作物。"
        return True, ""

    def plant(self, plot_index, crop_id):
        """在指定地块播种。"""
        ok, msg = self.can_plant(plot_index, crop_id)
        if not ok:
            return False, msg
        crop = self.config.get_crop(crop_id)
        seed_id = crop.get("seed_item_id")
        if seed_id:
            self.player.consume_items(seed_id, 1)
        self.player.farm_plots[plot_index] = {
            "crop_id": crop_id,
            "growth": 0,
            "state": "growing",  # growing / withered / mature
            "watered": False,
        }
        return True, f"播种【{crop['name']}】。"

    def water(self, plot_index):
        """浇水，本月生长速度翻倍。"""
        plot = self._get_plot(plot_index)
        if not plot:
            return False, "地块不存在。"
        if plot["state"] != "growing":
            return False, "只有生长中的作物可以浇水。"
        plot["watered"] = True
        return True, "浇水成功，本月生长加速。"

    def harvest(self, plot_index):
        """收获作物。"""
        plot = self._get_plot(plot_index)
        if not plot:
            return False, "地块不存在。"
        if plot["state"] != "mature":
            return False, "作物尚未成熟。"
        crop = self.config.get_crop(plot["crop_id"])
        item = self.item_library.create(crop["yield_item_id"])
        count = random.randint(crop.get("yield_min", 1), crop.get("yield_max", 1))
        if item:
            for _ in range(count):
                self.player.add_item(item)
        self.player.farm_plots[plot_index] = None
        return True, f"收获【{crop['name']}】x{count}。"

    def _get_plot(self, plot_index):
        if 0 <= plot_index < len(self.player.farm_plots):
            return self.player.farm_plots[plot_index]
        return None

    def tick_monthly(self):
        """推进所有作物生长一个月，返回收获/枯萎/生长日志。"""
        self._ensure_default_plots()
        logs = []
        season = self.config.get_season(self.world.month)
        for idx, plot in enumerate(self.player.farm_plots):
            if not plot:
                continue
            crop = self.config.get_crop(plot["crop_id"])
            if not crop:
                continue
            if plot["state"] == "withered":
                continue
            # 季节不适宜时，作物有概率枯萎
            if season not in crop.get("seasons", []):
                if random.random() < 0.3:
                    plot["state"] = "withered"
                    logs.append(f"第{idx + 1}块地的【{crop['name']}】因季节不适枯萎了。")
                    continue
            # 正常生长
            growth = 1
            if plot.get("watered"):
                growth += 1
                plot["watered"] = False
            plot["growth"] += growth
            if plot["growth"] >= crop.get("growth_months", 1):
                plot["state"] = "mature"
                logs.append(f"第{idx + 1}块地的【{crop['name']}】已成熟，可以收获了。")
        return logs
