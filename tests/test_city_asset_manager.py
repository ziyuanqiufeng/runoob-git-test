# -*- coding: utf-8 -*-
"""
城市资源自动补齐模块测试。
"""
import os
import shutil
import tempfile
import unittest

from game.city_asset_manager import (
    ensure_city_assets,
    _missing_backgrounds,
    _missing_buildings,
)


class TestCityAssetManager(unittest.TestCase):
    """测试城市资源自动补齐逻辑。"""

    def test_no_missing_assets_after_generation(self):
        """生成后不应再报缺失。"""
        # 先确保资源存在
        ensure_city_assets()
        self.assertEqual(_missing_backgrounds(), [])
        self.assertEqual(_missing_buildings(), [])

    def test_detects_missing_background(self):
        """删除某张背景图后应能检测出来。"""
        ensure_city_assets()
        bg_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "city_bg")
        bg_dir = os.path.abspath(bg_dir)
        target = os.path.join(bg_dir, "luoxia_city.png")
        backup = target + ".bak"
        try:
            shutil.move(target, backup)
            missing = _missing_backgrounds()
            self.assertIn("luoxia_city", missing)
        finally:
            shutil.move(backup, target)

    def test_detects_missing_building(self):
        """删除某张建筑图后应能检测出来。"""
        ensure_city_assets()
        building_dir = os.path.join(
            os.path.dirname(__file__), "..", "assets", "city_buildings", "luoxia_city"
        )
        building_dir = os.path.abspath(building_dir)
        target = os.path.join(building_dir, "inn.png")
        backup = target + ".bak"
        try:
            shutil.move(target, backup)
            missing = _missing_buildings()
            self.assertIn("luoxia_city", missing)
        finally:
            shutil.move(backup, target)


if __name__ == "__main__":
    unittest.main()
