# -*- coding: utf-8 -*-
"""F-06 难度系统：难度选择、全局修正系数（Player 创建时应用）。

地狱难度专属「天道追杀」：每突破大境界触发追杀者战斗，复用引擎现有战斗。
"""
import json
import os


class DifficultyConfig:
    """加载难度配置。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        path = os.path.join(config_dir, "difficulty", "difficulty_settings.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_default(self):
        return self.data.get("default", "normal")

    def get_difficulties(self):
        return self.data.get("difficulties", [])

    def get_difficulty(self, difficulty_id):
        for d in self.get_difficulties():
            if d["id"] == difficulty_id:
                return d
        return None


class DifficultyManager:
    """难度选择、修正系数与天道追杀判定。"""

    def __init__(self, config_dir="config"):
        self.config = DifficultyConfig(config_dir)

    def get_difficulties(self):
        return self.config.get_difficulties()

    def get_default(self):
        return self.config.get_default()

    def get_modifiers(self, difficulty_id):
        """返回某难度的修正系数，缺失项补 1.0。"""
        diff = self.config.get_difficulty(difficulty_id)
        if not diff:
            diff = self.config.get_difficulty(self.get_default()) or {}
        mods = diff.get("modifiers", {})
        return {
            "enemy_strength": mods.get("enemy_strength", 1.0),
            "player_combat": mods.get("player_combat", 1.0),
            "production_mult": mods.get("production_mult", 1.0),
            "exp_mult": mods.get("exp_mult", 1.0),
            "drop_mult": mods.get("drop_mult", 1.0),
        }

    def apply_to_player(self, player, difficulty_id):
        """将难度与修正系数写入 player（创建时调用）。无效难度回退默认。"""
        if not self.config.get_difficulty(difficulty_id):
            difficulty_id = self.get_default()
        player.difficulty = difficulty_id
        player.difficulty_modifiers = self.get_modifiers(difficulty_id)
        return difficulty_id

    def should_trigger_heaven_pursuit(self, difficulty_id, is_major_breakthrough):
        """地狱难度且为大境界突破时触发天道追杀。"""
        diff = self.config.get_difficulty(difficulty_id)
        if not diff:
            return False
        return bool(diff.get("heaven_pursuit")) and bool(is_major_breakthrough)

    def on_breakthrough(self, engine, player, is_major_breakthrough):
        """
        突破成功后由引擎调用：若处于地狱难度且为大境界突破，则派遣追杀者。

        返回被触发的追杀者敌人对象，未触发则返回 None。
        """
        if not getattr(engine, "is_feature_enabled", lambda f: True)("achievement_tier"):
            return None
        if not self.should_trigger_heaven_pursuit(getattr(player, "difficulty", "normal"), is_major_breakthrough):
            return None
        pursuer = engine.create_heaven_pursuer(player)
        if pursuer:
            engine.start_combat(pursuer)
        return pursuer
