# -*- coding: utf-8 -*-
"""城池擂台排名系统。"""
import json
import os
import random


class ArenaRankingManager:
    """管理各城池演武场的排名对手与奖励。"""

    def __init__(self, config_dir="config"):
        self.config_dir = config_dir
        self._config = {}
        self._load()

    def _load(self):
        """加载擂台配置。"""
        path = os.path.join(self.config_dir, "arena_rankings.json")
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            self._config = json.load(f)

    def get_city_arena(self, city_id):
        """获取指定城池的演武场配置。"""
        return self._config.get("cities", {}).get(city_id)

    def get_opponents(self, city_id):
        """获取指定城池的所有对手列表（按排名从低到高）。"""
        arena = self.get_city_arena(city_id)
        if not arena:
            return []
        return arena.get("opponents", [])

    def get_opponent(self, city_id, opponent_id):
        """获取指定对手配置。"""
        for opp in self.get_opponents(city_id):
            if opp["id"] == opponent_id:
                return opp
        return None

    def get_challengeable_opponents(self, city_id, player_rank):
        """
        获取玩家当前可挑战的对手列表。

        规则：
        - 未上榜（rank=0）可挑战排名 1~3 的对手。
        - 已上榜可挑战排名高于自己最多 2 位的对手。
        """
        opponents = self.get_opponents(city_id)
        if not opponents:
            return []

        if player_rank <= 0:
            return opponents[:3]

        # 找到玩家当前排名的索引
        current_idx = player_rank - 1
        # 可挑战索引：当前索引往前最多 2 位
        start_idx = max(0, current_idx - 2)
        return opponents[start_idx:current_idx]

    def get_opponent_rank(self, city_id, opponent_id):
        """获取对手在排行榜中的名次（1 开始）。"""
        for idx, opp in enumerate(self.get_opponents(city_id), start=1):
            if opp["id"] == opponent_id:
                return idx
        return 0

    def calculate_rewards(self, opponent_rank):
        """根据对手排名计算基础奖励。"""
        base = self._config.get("base_rewards", {})
        multipliers = self._config.get("rank_multipliers", {})
        multiplier = multipliers.get(str(opponent_rank), 0.5)

        return {
            "spirit_stone": int(base.get("spirit_stone", 50) * multiplier),
            "reputation": int(base.get("reputation", 5) * multiplier),
            "skill_proficiency_chance": base.get("skill_proficiency_chance", 0.3),
        }

    def get_daily_challenge_limit(self):
        """每日挑战次数上限。"""
        return self._config.get("daily_challenge_limit", 5)

    def should_increase_rank(self, player_rank, opponent_rank):
        """判断战胜对手后是否提升排名。"""
        if player_rank <= 0:
            return opponent_rank <= 3
        return opponent_rank < player_rank

    def get_random_skill_for_proficiency(self, player):
        """随机选择玩家一个已学技能用于提升熟练度。"""
        if not player.skills:
            return None
        return random.choice(player.skills)
