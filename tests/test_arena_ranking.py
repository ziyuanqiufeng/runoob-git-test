# -*- coding: utf-8 -*-
"""演武场擂台排名系统单元测试。"""

import os
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from game.arena_ranking_manager import ArenaRankingManager


class TestArenaRankingManager(unittest.TestCase):
    """演武场排名管理器测试。"""

    def setUp(self):
        self.manager = ArenaRankingManager(config_dir="config")

    def test_get_opponents_sorted(self):
        """扶风城应有 10 名按排名排列的对手。"""
        opponents = self.manager.get_opponents("fufeng_city")
        self.assertEqual(len(opponents), 10)
        self.assertEqual(opponents[0]["title"], "末位陪练")
        self.assertEqual(opponents[-1]["title"], "一品擂主")

    def test_challengeable_when_unranked(self):
        """未上榜玩家可挑战前 3 名。"""
        ops = self.manager.get_challengeable_opponents("fufeng_city", 0)
        self.assertEqual(len(ops), 3)
        self.assertEqual([o["title"] for o in ops],
                         ["末位陪练", "九品挑战者", "八品挑战者"])

    def test_challengeable_when_ranked(self):
        """排名 5 的玩家可挑战第 3、4 名。"""
        ops = self.manager.get_challengeable_opponents("fufeng_city", 5)
        self.assertEqual(len(ops), 2)
        self.assertEqual([o["title"] for o in ops],
                         ["八品挑战者", "七品挑战者"])

    def test_should_increase_rank(self):
        """战胜高排名对手才提升排名。"""
        self.assertTrue(self.manager.should_increase_rank(0, 3))
        self.assertTrue(self.manager.should_increase_rank(5, 3))
        self.assertFalse(self.manager.should_increase_rank(3, 5))

    def test_calculate_rewards(self):
        """排名越高奖励越多。"""
        reward_top = self.manager.calculate_rewards(1)
        reward_bottom = self.manager.calculate_rewards(10)
        self.assertGreater(reward_top["spirit_stone"], reward_bottom["spirit_stone"])
        self.assertGreater(reward_top["reputation"], reward_bottom["reputation"])


class TestEngineArenaRanking(unittest.TestCase):
    """Engine 演武场排名挑战集成测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.item_lib = ItemLibrary(config_dir="config")
        self.enemy_lib = EnemyLibrary(config_dir="config")
        self.skill_lib = SkillLibrary(config_dir="config")
        self.npc_lib = NPCLibrary(config_dir="config")
        self.quest_lib = QuestLibrary(config_dir="config")

        self.player = Player(name="测试修士")
        self.player.location_id = "fufeng_city"
        # 给足灵石与生命，避免无关失败
        for _ in range(500):
            item = self.item_lib.create("spirit_stone")
            if item:
                self.player.add_item(item)
        self.player.base_attack = 100
        self.player.health = 100
        self.player.max_health = 100
        self.player.learn_skill("fireball")

        self.world = World(config_dir="config")
        self.event_pool = EventPool(config_dir="config")
        self.save_path = "test_arena_save.json"
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_lib,
            self.enemy_lib,
            self.skill_lib,
            self.npc_lib,
            self.quest_lib,
            save_manager=SaveManager(save_path=self.save_path),
        )

    def tearDown(self):
        if os.path.exists(self.save_path):
            os.remove(self.save_path)

    def test_start_challenge_consumes_daily_count(self):
        """发起挑战应消耗今日次数并生成敌人。"""
        self.assertEqual(self.player.arena_daily_challenges, 0)
        enemy = self.engine.start_arena_ranking_challenge("arena_fufeng_1")
        self.assertIsNotNone(enemy)
        self.assertEqual(self.player.arena_daily_challenges, 1)
        self.assertIsNotNone(self.engine.pending_arena_opponent)

    def test_start_challenge_exceed_limit(self):
        """超过每日上限后无法继续挑战。"""
        # 先同步日期，避免 _reset_arena_daily_if_needed 自动重置计数
        self.player.arena_last_date = self.engine._get_today_str()
        limit = self.engine.arena_ranking_manager.get_daily_challenge_limit()
        self.player.arena_daily_challenges = limit
        enemy = self.engine.start_arena_ranking_challenge("arena_fufeng_1")
        self.assertIsNone(enemy)

    def test_finish_challenge_win_increases_rank(self):
        """战胜排名更高的对手后排名应提升，并获得奖励。"""
        # 直接设置 pending 对手为第 3 名
        opponent = self.engine.arena_ranking_manager.get_opponent(
            "fufeng_city", "arena_fufeng_3"
        )
        self.engine.pending_arena_opponent = opponent

        before_stones = self.player.count_item("spirit_stone")
        logs = self.engine._finish_arena_ranking_challenge(True)

        self.assertEqual(self.player.arena_rank, 3)
        self.assertTrue(any("排名提升至第 3 位" in log for log in logs))
        self.assertGreater(self.player.count_item("spirit_stone"), before_stones)
        self.assertIsNone(self.engine.pending_arena_opponent)

    def test_finish_challenge_win_no_rank_change(self):
        """战胜低排名对手不提升排名。"""
        self.player.arena_rank = 3
        opponent = self.engine.arena_ranking_manager.get_opponent(
            "fufeng_city", "arena_fufeng_5"
        )
        self.engine.pending_arena_opponent = opponent

        logs = self.engine._finish_arena_ranking_challenge(True)
        self.assertEqual(self.player.arena_rank, 3)
        self.assertTrue(any("排名未发生变化" in log for log in logs))

    def test_finish_challenge_lose(self):
        """失败不提升排名但有失败提示。"""
        opponent = self.engine.arena_ranking_manager.get_opponent(
            "fufeng_city", "arena_fufeng_1"
        )
        self.engine.pending_arena_opponent = opponent

        logs = self.engine._finish_arena_ranking_challenge(False)
        self.assertEqual(self.player.arena_rank, 0)
        self.assertTrue(any("挑战失败" in log for log in logs))
        self.assertIsNone(self.engine.pending_arena_opponent)

    def test_daily_reset_resets_challenge_count(self):
        """跨天后应重置每日挑战次数。"""
        self.player.arena_daily_challenges = 5
        self.player.arena_last_date = "0-1-1"
        self.engine._reset_arena_daily_if_needed()
        self.assertEqual(self.player.arena_daily_challenges, 0)


if __name__ == "__main__":
    unittest.main()
