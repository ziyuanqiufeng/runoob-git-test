# -*- coding: utf-8 -*-
"""势力声望系统。"""
import json
import os


class ReputationConfig:
    """加载声望配置。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._reps = {}
        self._load()

    def _load(self):
        path = os.path.join(self.config_dir, "reputation.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            self._reps[entry["id"]] = entry

    def get(self, rep_id):
        return self._reps.get(rep_id)

    def get_all(self):
        return list(self._reps.values())


class ReputationManager:
    """管理玩家在各大势力的声望值。"""

    def __init__(self, player, config_dir="config"):
        self.player = player
        self.config = ReputationConfig(config_dir)
        if not hasattr(player, "reputation"):
            player.reputation = {}

    def adjust(self, rep_id, amount):
        """调整某势力声望，返回 (new_value, level_title)。"""
        rep_cfg = self.config.get(rep_id)
        if not rep_cfg:
            return None, ""
        max_val = rep_cfg.get("max", 1000)
        current = self.player.reputation.get(rep_id, 0)
        new_val = max(0, min(max_val, current + amount))
        self.player.reputation[rep_id] = new_val
        return new_val, self.get_level_title(rep_id)

    def get_level_title(self, rep_id):
        rep_cfg = self.config.get(rep_id)
        if not rep_cfg:
            return ""
        value = self.player.reputation.get(rep_id, 0)
        title = ""
        for level in rep_cfg.get("levels", []):
            if value >= level["threshold"]:
                title = level["title"]
        return title

    def get_discount(self, rep_id):
        """根据声望返回商店折扣（0.0-1.0）。"""
        rep_cfg = self.config.get(rep_id)
        if not rep_cfg:
            return 0.0
        per_point = rep_cfg.get("shop_discount", 0.0)
        value = self.player.reputation.get(rep_id, 0)
        return min(0.3, value * per_point)

    def get_unlocked_npcs(self, rep_id):
        """返回因声望解锁的 NPC ID 列表。"""
        rep_cfg = self.config.get(rep_id)
        if not rep_cfg:
            return []
        value = self.player.reputation.get(rep_id, 0)
        unlocked = []
        for entry in rep_cfg.get("unlock_npcs", []):
            if value >= entry["threshold"]:
                unlocked.append(entry["npc_id"])
        return unlocked
