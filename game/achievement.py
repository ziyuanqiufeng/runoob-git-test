# -*- coding: utf-8 -*-
"""成就系统：监听玩家行为并发放奖励。

F-06 扩展：支持成就分级（青铜/白银/黄金/仙金）、隐藏成就、称号奖励（带属性）、
解锁隐藏事件，并提供按品阶汇总的进度数据供 UI 使用。
"""
import json
import os


class AchievementConfig:
    """加载成就配置（基础 achievements.json + 扩展 achievements_v2.json）。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._achievements = {}
        self._load("achievements.json")
        self._load("achievement/achievements_v2.json")

    def _load(self, rel_path):
        path = os.path.join(self.config_dir, rel_path)
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            # 统一默认值：品阶、隐藏标记、奖励
            entry.setdefault("tier", "无")
            entry.setdefault("hidden", False)
            entry.setdefault("reward", {})
            self._achievements[entry["id"]] = entry

    def get(self, achievement_id):
        return self._achievements.get(achievement_id)

    def get_all(self):
        return list(self._achievements.values())


class AchievementManager:
    """管理成就进度与奖励发放。"""

    # 使用累计计数器的事件类型（每个事件只自增一次，避免多成就重复计数）
    _COUNTER_EVENTS = {
        "kill": "kill_count",
        "companion": "companion_count",
        "skill_learn": "skill_learn_count",
        "quest_complete": "quest_complete_count",
    }

    def __init__(self, player, item_library, config_dir="config"):
        self.player = player
        self.item_library = item_library
        self.config = AchievementConfig(config_dir)
        # 初始化成就字段（向后兼容旧存档）
        if not hasattr(player, "achievements"):
            player.achievements = []
        if not hasattr(player, "achievement_progress"):
            player.achievement_progress = {}
        if not hasattr(player, "titles"):
            player.titles = []
        if not hasattr(player, "title_bonuses"):
            player.title_bonuses = {}
        if not hasattr(player, "unlocked_hidden_events"):
            player.unlocked_hidden_events = []

    def check(self, event_type, **kwargs):
        """根据事件检查是否有新成就达成，返回 [(id, name), ...]。"""
        # 统一累计进度计数（每个事件类型只自增一次）
        counter_key = self._COUNTER_EVENTS.get(event_type)
        if counter_key is not None:
            self.player.achievement_progress[counter_key] = (
                self.player.achievement_progress.get(counter_key, 0) + 1
            )

        unlocked = []
        for aid, achievement in self.config._achievements.items():
            if aid in self.player.achievements:
                continue
            if self._match_condition(achievement.get("condition", {}), event_type, **kwargs):
                self._unlock(aid)
                unlocked.append((aid, achievement["name"]))
        return unlocked

    def _match_condition(self, condition, event_type, **kwargs):
        ctype = condition.get("type")
        if ctype == "kill" and event_type == "kill":
            if condition.get("world_boss"):
                return bool(kwargs.get("world_boss"))
            return self.player.achievement_progress.get("kill_count", 0) >= condition.get("count", 1)
        if ctype == "realm" and event_type == "breakthrough":
            return kwargs.get("realm_id") == condition.get("realm_id")
        if ctype == "item_total" and event_type == "item_change":
            item_id = condition.get("item_id")
            return self.player.count_item(item_id) >= condition.get("count", 1)
        if ctype == "companion" and event_type == "companion":
            return self.player.achievement_progress.get("companion_count", 0) >= condition.get("count", 1)
        if ctype == "sect_rank" and event_type == "sect_rank":
            rank_order = {"outer": 1, "inner": 2, "core": 3, "elder": 4, "leader": 5}
            return rank_order.get(kwargs.get("rank"), 0) >= rank_order.get(condition.get("rank"), 0)
        if ctype == "skill_learn" and event_type == "skill_learn":
            if condition.get("skill_id"):
                return kwargs.get("skill_id") == condition.get("skill_id")
            return self.player.achievement_progress.get("skill_learn_count", 0) >= condition.get("count", 1)
        if ctype == "quest_complete" and event_type == "quest_complete":
            return self.player.achievement_progress.get("quest_complete_count", 0) >= condition.get("count", 1)
        if ctype == "win" and event_type == "win_game":
            return True
        return False

    def _unlock(self, achievement_id):
        if achievement_id in self.player.achievements:
            return
        self.player.achievements.append(achievement_id)
        achievement = self.config.get(achievement_id)
        if not achievement:
            return
        reward = achievement.get("reward", {})

        # 发放属性奖励
        for attr in ["wisdom", "constitution", "luck"]:
            if attr in reward:
                setattr(self.player, attr, getattr(self.player, attr, 0) + reward[attr])

        # 发放物品奖励（item_library 缺失时跳过，保证健壮性）
        item_id = reward.get("item_id")
        if item_id and self.item_library is not None:
            count = reward.get("count", 1)
            item = self.item_library.create(item_id)
            if item:
                for _ in range(count):
                    self.player.add_item(item)

        # 称号奖励（带属性，直接累加到基础战斗属性；存档已含此值，读取时不重复应用）
        title = reward.get("title")
        if title and title not in self.player.titles:
            self.player.titles.append(title)
            bonus = reward.get("title_bonus", {})
            for key, val in bonus.items():
                self.player.title_bonuses[key] = self.player.title_bonuses.get(key, 0) + val
                if key == "attack" and hasattr(self.player, "base_attack"):
                    self.player.base_attack += val
                elif key == "defense" and hasattr(self.player, "base_defense"):
                    self.player.base_defense += val
                elif key == "max_health" and hasattr(self.player, "max_health"):
                    self.player.max_health += val
                    self.player.health += val

        # 解锁隐藏事件（供事件系统读取）
        unlock_event = reward.get("unlock_event")
        if unlock_event and unlock_event not in self.player.unlocked_hidden_events:
            self.player.unlocked_hidden_events.append(unlock_event)

    def get_progress_summary(self):
        """按品阶汇总成就进度，供 UI 展示（隐藏且未解锁者名称脱敏）。"""
        tiers = {}
        hidden_total = 0
        hidden_done = 0
        completed = set(self.player.achievements)
        items = []
        for ach in self.config.get_all():
            tier = ach.get("tier", "无")
            tiers.setdefault(tier, {"total": 0, "completed": 0})
            tiers[tier]["total"] += 1
            done = ach["id"] in completed
            if done:
                tiers[tier]["completed"] += 1
            hidden = bool(ach.get("hidden"))
            if hidden:
                hidden_total += 1
                if done:
                    hidden_done += 1
            name = ach["name"] if (done or not hidden) else "？？？"
            desc = ach.get("description", "") if (done or not hidden) else "未解锁的隐藏成就"
            items.append({
                "id": ach["id"],
                "name": name,
                "desc": desc,
                "tier": tier,
                "hidden": hidden,
                "done": done,
                "reward": ach.get("reward", {}),
            })
        return {
            "total": len(self.config.get_all()),
            "completed": len(completed),
            "by_tier": tiers,
            "titles": list(getattr(self.player, "titles", [])),
            "hidden_total": hidden_total,
            "hidden_completed": hidden_done,
            "items": items,
        }
