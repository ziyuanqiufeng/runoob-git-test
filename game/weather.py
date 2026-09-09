# -*- coding: utf-8 -*-
"""天气与灵气潮汐系统。

世界每月会随机切换天气与灵气潮汐，影响修炼速度、元素伤害、敌人强度等。
状态保存在 World 对象中，WeatherManager 负责根据配置计算效果。
"""

import json
import os
import random


class WeatherConfig:
    """天气与灵气潮汐配置加载器。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "weather.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_weathers(self):
        return self.data.get("weathers", [])

    def get_spirit_tides(self):
        return self.data.get("spirit_tides", [])

    def get_seasons(self):
        return self.data.get("seasons", [])

    def get_weather(self, weather_id):
        for w in self.get_weathers():
            if w["id"] == weather_id:
                return w
        return None

    def get_spirit_tide(self, tide_id):
        for t in self.get_spirit_tides():
            if t["id"] == tide_id:
                return t
        return None

    def get_season_for_month(self, month):
        for season in self.get_seasons():
            if month in season.get("months", []):
                return season
        return None


class WeatherManager:
    """天气与灵气潮汐管理器。"""

    DEFAULT_WEATHER = "sunny"
    DEFAULT_TIDE = "normal"

    def __init__(self, world, config=None):
        self.world = world
        self.config = config or WeatherConfig()

    def _weighted_choice(self, options):
        """根据权重随机选择一个选项。"""
        total = sum(opt.get("weight", 1) for opt in options)
        r = random.uniform(0, total)
        upto = 0
        for opt in options:
            w = opt.get("weight", 1)
            upto += w
            if upto >= r:
                return opt
        return options[-1] if options else None

    def advance(self):
        """推进一个月，随机切换天气与灵气潮汐。

        返回 (weather_changed, previous_weather, new_weather, previous_tide, new_tide)。
        """
        prev_weather = getattr(self.world, "current_weather", self.DEFAULT_WEATHER)
        prev_tide = getattr(self.world, "current_spirit_tide", self.DEFAULT_TIDE)

        new_weather = self._weighted_choice(self.config.get_weathers())
        new_tide = self._weighted_choice(self.config.get_spirit_tides())

        weather_id = new_weather["id"] if new_weather else self.DEFAULT_WEATHER
        tide_id = new_tide["id"] if new_tide else self.DEFAULT_TIDE

        self.world.current_weather = weather_id
        self.world.current_spirit_tide = tide_id

        changed = (prev_weather != weather_id) or (prev_tide != tide_id)
        return changed, prev_weather, weather_id, prev_tide, tide_id

    def get_current_weather(self):
        """获取当前天气配置。"""
        weather_id = getattr(self.world, "current_weather", self.DEFAULT_WEATHER)
        return self.config.get_weather(weather_id)

    def get_current_spirit_tide(self):
        """获取当前灵气潮汐配置。"""
        tide_id = getattr(self.world, "current_spirit_tide", self.DEFAULT_TIDE)
        return self.config.get_spirit_tide(tide_id)

    def get_current_season(self):
        """获取当前季节配置。"""
        return self.config.get_season_for_month(self.world.month)

    def _merge_effects(self, *effect_dicts):
        """合并多个效果字典，相同 key 的数值相加。"""
        merged = {}
        for effects in effect_dicts:
            if not effects:
                continue
            for key, value in effects.items():
                merged[key] = merged.get(key, 0.0) + value
        return merged

    def get_all_effects(self):
        """获取当前天气、灵气潮汐、季节叠加后的全部效果。"""
        weather = self.get_current_weather()
        tide = self.get_current_spirit_tide()
        season = self.get_current_season()
        return self._merge_effects(
            weather.get("effects", {}) if weather else {},
            tide.get("effects", {}) if tide else {},
            season.get("effects", {}) if season else {},
        )

    def get_element_damage_bonus(self, element):
        """获取指定元素在当前环境下的伤害加成。"""
        effects = self.get_all_effects()
        return effects.get(f"{element}_damage", 0.0)

    def get_cultivation_speed_bonus(self, cultivation_path=None):
        """获取当前修炼速度加成。

        邪修在血月天气下额外享受 evil_cultivation_speed。
        """
        effects = self.get_all_effects()
        bonus = effects.get("cultivation_speed", 0.0)
        if cultivation_path == "xie":
            bonus += effects.get("evil_cultivation_speed", 0.0)
        return bonus

    def get_enemy_strength_bonus(self):
        """获取当前敌人强度加成。"""
        return self.get_all_effects().get("enemy_strength", 0.0)

    def get_breakthrough_bonus(self):
        """获取当前环境对突破成功率的加成。"""
        return self.get_all_effects().get("breakthrough_bonus", 0.0)

    def get_heart_demon_growth_bonus(self):
        """获取心魔增长速度加成。"""
        return self.get_all_effects().get("heart_demon_growth", 0.0)

    def get_herb_growth_bonus(self):
        """获取灵草生长速度加成。"""
        return self.get_all_effects().get("herb_growth", 0.0)

    def get_description(self):
        """获取当前天气与灵气潮汐的中文描述。"""
        weather = self.get_current_weather()
        tide = self.get_current_spirit_tide()
        season = self.get_current_season()
        parts = []
        if season:
            parts.append(season["name"])
        if weather:
            parts.append(weather["name"])
        if tide:
            parts.append(tide["name"])
        return " · ".join(parts)
