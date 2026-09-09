# -*- coding: utf-8 -*-
"""F-07 多周目特殊模式：新游戏开局时的模式选择、可用性判定与开局效应应用。

4 种模式：
- standard       正统求道（无限制）
- seize_rebirth  夺舍重生（需前世已达元婴：reincarnation_count >= 1）
- heaven_cycle   天道轮回（需已通关：has_won 为真）
- mortal_challenge 凡人挑战（天生无灵根，仅可走体修/符修）
- demonic_lone   魔道独行（正道宗门皆敌，杀伐更盛）
"""
import json
import os


class MetaConfig:
    """加载多周目模式配置。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        path = os.path.join(config_dir, "meta", "new_game_modes.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_modes(self):
        return self.data.get("modes", [])

    def get_mode(self, mode_id):
        for m in self.get_modes():
            if m["id"] == mode_id:
                return m
        return None


class MetaManager:
    """多周目模式可用性判定与开局效应应用。"""

    def __init__(self, config_dir="config"):
        self.config = MetaConfig(config_dir)

    def get_modes(self):
        return self.config.get_modes()

    def is_available(self, mode, player):
        """判定某模式对当前玩家是否可用，返回 (bool, reason)。"""
        require = mode.get("require", {}) or {}
        if "reincarnation_count_min" in require:
            cur = getattr(player, "reincarnation_count", 0)
            if cur < require["reincarnation_count_min"]:
                return False, f"需前世轮回至少 {require['reincarnation_count_min']} 次（当前 {cur}）"
        if require.get("has_won"):
            if not getattr(player, "has_won", False):
                return False, "需先完成一次飞升通关"
        return True, ""

    def get_modes_with_availability(self, player):
        """返回所有模式，并标注 current / available。"""
        current = getattr(player, "game_mode", "standard")
        result = []
        for m in self.get_modes():
            ok, reason = self.is_available(m, player)
            entry = dict(m)
            entry["available"] = ok
            entry["lock_reason"] = reason
            entry["current"] = (m["id"] == current)
            result.append(entry)
        return result

    def apply_to_player(self, player, mode_id):
        """
        将选定模式的开局效应应用到 player。

        返回模式 id（无效模式回退 standard）。
        """
        mode = self.config.get_mode(mode_id)
        if not mode:
            mode_id = "standard"
            mode = self.config.get_mode("standard")
        effects = mode.get("effects", {}) or {}
        player.game_mode = mode_id

        # 凡人挑战：无灵根
        if effects.get("no_spiritual_roots"):
            player.spiritual_roots = []
            if hasattr(player, "root_purities"):
                player.root_purities = {}
            player.no_spiritual_roots = True
        # 限制可选流派
        if "allowed_paths" in effects:
            player.allowed_paths = list(effects["allowed_paths"])

        # 起始属性加成
        if "start_bonus_attack" in effects and hasattr(player, "base_attack"):
            player.base_attack += effects["start_bonus_attack"]
        if "start_bonus_max_health" in effects and hasattr(player, "max_health"):
            player.max_health += effects["start_bonus_max_health"]
            player.health += effects["start_bonus_max_health"]

        # 业力偏移
        if "karma" in effects:
            player.karma = getattr(player, "karma", 0) + effects["karma"]

        # 敌对阵营
        if "hostile_factions" in effects:
            existing = getattr(player, "hostile_factions", []) or []
            merged = list(existing)
            for f in effects["hostile_factions"]:
                if f not in merged:
                    merged.append(f)
            player.hostile_factions = merged

        # 修炼/敌人强度修正（跨周目，作为独立乘区保存）
        meta_mod = getattr(player, "meta_modifiers", {}) or {}
        if "exp_mult" in effects:
            meta_mod["exp_mult"] = effects["exp_mult"]
        if "enemy_strength" in effects:
            meta_mod["enemy_strength"] = effects["enemy_strength"]
        player.meta_modifiers = meta_mod

        # 天赋加成（累加到转世修炼加成）
        if "talent_bonus" in effects:
            player.reincarnation_cultivation_bonus = (
                getattr(player, "reincarnation_cultivation_bonus", 0)
                + effects["talent_bonus"]
            )

        # 起始携带物品（延迟到新游戏流程发放）
        if "start_items" in effects:
            player.pending_start_items = list(effects["start_items"])

        return mode_id
