# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch

from game.world import World
from game.weather import WeatherManager, WeatherConfig


class TestWeatherManager(unittest.TestCase):
    """天气与灵气潮汐系统测试。"""

    def setUp(self):
        self.world = World(config_dir="config")
        self.manager = WeatherManager(self.world)

    def test_initial_state(self):
        """初始天气应为晴朗，灵气潮汐为平常。"""
        self.assertEqual(self.world.current_weather, "sunny")
        self.assertEqual(self.world.current_spirit_tide, "normal")

    def test_advance_changes_state(self):
        """advance 应能切换天气与潮汐状态。"""
        # 强制让 _weighted_choice 返回指定配置
        custom_config = MagicMock()
        custom_config.get_weathers.return_value = [
            {"id": "rainy", "name": "暴雨", "weight": 1, "effects": {}}
        ]
        custom_config.get_spirit_tides.return_value = [
            {"id": "high", "name": "灵气充盈", "weight": 1, "cultivation_speed": 0.15}
        ]
        manager = WeatherManager(self.world, config=custom_config)
        changed, prev_w, new_w, prev_t, new_t = manager.advance()
        self.assertTrue(changed)
        self.assertEqual(new_w, "rainy")
        self.assertEqual(new_t, "high")
        self.assertEqual(self.world.current_weather, "rainy")
        self.assertEqual(self.world.current_spirit_tide, "high")

    def test_get_current_weather(self):
        """应正确返回当前天气配置。"""
        self.world.current_weather = "thunderstorm"
        weather = self.manager.get_current_weather()
        self.assertEqual(weather["id"], "thunderstorm")

    def test_get_current_spirit_tide(self):
        """应正确返回当前灵气潮汐配置。"""
        self.world.current_spirit_tide = "surge"
        tide = self.manager.get_current_spirit_tide()
        self.assertEqual(tide["id"], "surge")

    def test_element_damage_bonus(self):
        """暴雨天应提升水属性伤害、降低火属性伤害。"""
        self.world.current_weather = "rainy"
        self.assertEqual(self.manager.get_element_damage_bonus("water"), 0.1)
        self.assertEqual(self.manager.get_element_damage_bonus("fire"), -0.1)

    def test_cultivation_speed_bonus(self):
        """灵气潮汐高涨时应提升修炼速度。"""
        self.world.current_spirit_tide = "surge"
        self.assertEqual(self.manager.get_cultivation_speed_bonus(), 0.35)

    def test_evil_cultivation_bonus(self):
        """血月时邪修应获得额外修炼加成。"""
        self.world.current_weather = "blood_moon"
        normal_bonus = self.manager.get_cultivation_speed_bonus()
        evil_bonus = self.manager.get_cultivation_speed_bonus(cultivation_path="xie")
        self.assertEqual(normal_bonus, 0.0)
        self.assertEqual(evil_bonus, 0.1)

    def test_season_effects(self):
        """季节应正确影响元素伤害。"""
        self.world.month = 1  # 春季
        bonus = self.manager.get_element_damage_bonus("wood")
        self.assertEqual(bonus, 0.05)
        self.world.month = 10  # 冬季
        bonus = self.manager.get_element_damage_bonus("water")
        self.assertEqual(bonus, 0.05)

    def test_enemy_strength_bonus(self):
        """血月应提升敌人强度。"""
        self.world.current_weather = "blood_moon"
        self.assertEqual(self.manager.get_enemy_strength_bonus(), 0.3)

    def test_herb_growth_bonus(self):
        """灵雨（+春季）应提升灵草生长速度。"""
        self.world.current_weather = "spirit_rain"
        # 默认 1 月为春季，额外 +0.1
        self.assertAlmostEqual(self.manager.get_herb_growth_bonus(), 0.3)

    def test_description(self):
        """描述应包含季节、天气、潮汐。"""
        self.world.month = 1
        self.world.current_weather = "sunny"
        self.world.current_spirit_tide = "normal"
        desc = self.manager.get_description()
        self.assertIn("春", desc)
        self.assertIn("晴朗", desc)
        self.assertIn("灵气平常", desc)

    def test_all_effects_merge(self):
        """应正确叠加天气、潮汐、季节效果。"""
        self.world.month = 1
        self.world.current_weather = "spirit_rain"
        self.world.current_spirit_tide = "high"
        effects = self.manager.get_all_effects()
        self.assertAlmostEqual(effects["cultivation_speed"], 0.25)
        self.assertAlmostEqual(effects["herb_growth"], 0.3)


if __name__ == "__main__":
    unittest.main()
