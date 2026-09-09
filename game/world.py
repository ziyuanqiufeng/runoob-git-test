import json
import os


class World:
    """游戏世界，管理时间、境界配置、地点配置等全局数据。"""

    def __init__(self, config_dir="config"):
        # 加载境界配置
        realms_path = os.path.join(config_dir, "realms.json")
        with open(realms_path, "r", encoding="utf-8") as f:
            realms_data = json.load(f)

        # 用境界 ID 做键，方便快速查询
        self.realms = {r["id"]: r for r in realms_data}

        # 按 order 排序，用于查找下一个境界
        self.realm_list = sorted(realms_data, key=lambda r: r["order"])

        # 加载地点配置
        locations_path = os.path.join(config_dir, "locations.json")
        with open(locations_path, "r", encoding="utf-8") as f:
            locations_data = json.load(f)
        self.locations = {loc["id"]: loc for loc in locations_data}

        # 加载配方配置
        recipes_path = os.path.join(config_dir, "recipes.json")
        with open(recipes_path, "r", encoding="utf-8") as f:
            self.recipes = json.load(f)

        # 世界时间
        self.year = 1     # 第 1 年
        self.month = 1    # 第 1 月
        self.day = 1      # 第 1 日（每月固定 30 日，简化历法）
        self.hour = 8     # 当前时辰（0-23，初始为辰时）

        # 天气与灵气潮汐（由 WeatherManager 维护）
        self.current_weather = "sunny"       # 当前天气 ID
        self.current_spirit_tide = "normal"  # 当前灵气潮汐 ID

        # 内置节日配置（month, day）
        self.festivals = {
            "spring_festival": {"name": "春节", "month": 1, "day": 1, "greeting": "新春大吉，万象更新！"},
            "lantern_festival": {"name": "元宵", "month": 1, "day": 15, "greeting": "花灯如昼，月圆人圆。"},
            "qingming": {"name": "清明", "month": 4, "day": 5, "greeting": "春风化雨，慎终追远。"},
            "dragon_boat": {"name": "端午", "month": 5, "day": 5, "greeting": "龙舟竞渡，粽香四溢。"},
            "qixi": {"name": "七夕", "month": 7, "day": 7, "greeting": "银河迢迢，鹊桥相会。"},
            "mid_autumn": {"name": "中秋", "month": 8, "day": 15, "greeting": "月满中秋，千里共婵娟。"},
            "double_ninth": {"name": "重阳", "month": 9, "day": 9, "greeting": "登高望远，岁岁安康。"},
            "winter_solstice": {"name": "冬至", "month": 12, "day": 22, "greeting": "阴极阳生，否极泰来。"},
        }

    def advance(self, months=0, days=0, hours=0):
        """推进世界时间，支持月、日、小时三种粒度。"""
        self.hour += hours
        while self.hour >= 24:
            self.hour -= 24
            self.day += 1

        self.day += days
        while self.day > 30:
            self.day -= 30
            self.month += 1

        self.month += months
        while self.month > 12:
            self.month -= 12
            self.year += 1

    def get_realm(self, realm_id):
        """根据 ID 获取境界配置。"""
        return self.realms.get(realm_id)

    def next_realm(self, realm_id):
        """获取当前境界的下一个境界 ID。"""
        current = self.realms.get(realm_id)
        if not current:
            return None

        current_order = current["order"]
        # 找到 order 比当前大、且最接近的境界
        candidates = [r for r in self.realm_list if r["order"] > current_order]
        if candidates:
            return candidates[0]["id"]
        return None

    def is_max_realm(self, realm_id):
        """判断是否为最高境界。"""
        return realm_id == self.realm_list[-1]["id"]

    def get_location(self, location_id):
        """根据 ID 获取地点配置。"""
        return self.locations.get(location_id)

    def get_recipe(self, recipe_id):
        """根据 ID 获取配方配置。"""
        for recipe in self.recipes:
            if recipe["id"] == recipe_id:
                return recipe
        return None

    def to_dict(self):
        """序列化为字典，用于存档。"""
        return {
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "hour": self.hour,
            "current_weather": self.current_weather,
            "current_spirit_tide": self.current_spirit_tide,
        }

    @classmethod
    def from_dict(cls, data, config_dir="config"):
        """从字典恢复世界对象。"""
        world = cls(config_dir=config_dir)
        world.year = data.get("year", 1)
        world.month = data.get("month", 1)
        world.day = data.get("day", 1)
        world.hour = data.get("hour", 8)
        world.current_weather = data.get("current_weather", "sunny")
        world.current_spirit_tide = data.get("current_spirit_tide", "normal")
        return world

    def get_current_festival(self):
        """获取当前节日 ID，无节日返回 None。"""
        for fid, info in self.festivals.items():
            if info["month"] == self.month and info["day"] == self.day:
                return fid
        return None

    def get_time_label(self):
        """获取当前时辰的中文描述。"""
        hour = self.hour
        if 5 <= hour < 7:
            return "卯时（日出）"
        if 7 <= hour < 9:
            return "辰时（食时）"
        if 9 <= hour < 11:
            return "巳时（隅中）"
        if 11 <= hour < 13:
            return "午时（日中）"
        if 13 <= hour < 15:
            return "未时（日昳）"
        if 15 <= hour < 17:
            return "申时（哺时）"
        if 17 <= hour < 19:
            return "酉时（日入）"
        if 19 <= hour < 21:
            return "戌时（黄昏）"
        if 21 <= hour < 23:
            return "亥时（人定）"
        if 23 <= hour or hour < 1:
            return "子时（夜半）"
        if 1 <= hour < 3:
            return "丑时（鸡鸣）"
        if 3 <= hour < 5:
            return "寅时（平旦）"
        return "未知时辰"
