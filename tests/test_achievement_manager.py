# -*- coding: utf-8 -*-
"""成就系统扩展单元测试（F-06：分级 / 隐藏 / 称号 / 脱敏）。"""
import unittest

from game.achievement import AchievementManager, AchievementConfig


class _FakePlayer:
    """轻量玩家替身，仅暴露成就逻辑所需属性。"""

    def __init__(self):
        self.achievements = []
        self.achievement_progress = {}
        self.titles = []
        self.title_bonuses = {}
        self.unlocked_hidden_events = []
        self.base_attack = 10
        self.base_defense = 5
        self.max_health = 100
        self.health = 100
        self.karma = 0
        self.inventory = []

    def count_item(self, item_id):
        return 0

    def add_item(self, item):
        self.inventory.append(item)


def _mgr(player=None):
    return AchievementManager(player or _FakePlayer(), None, config_dir="config")


class TestAchievementConfig(unittest.TestCase):
    def test_tiers_and_hidden_loaded(self):
        cfg = AchievementConfig(config_dir="config")
        by_id = {a["id"]: a for a in cfg.get_all()}
        self.assertEqual(by_id["a_gold_realm_gc"]["tier"], "黄金")
        self.assertEqual(by_id["a_imm_win"]["tier"], "仙金")
        self.assertTrue(by_id["a_hidden_boss"]["hidden"])
        self.assertFalse(by_id["a_bronze_kill"]["hidden"])


class TestAchievementUnlock(unittest.TestCase):
    def test_kill_counter_tiers(self):
        p = _FakePlayer()
        m = _mgr(p)
        # 1 杀 → 青铜（仅断言 v2 成就已解锁，忽略旧 achievements.json 同名成就）
        m.check("kill", enemy_id="x")
        self.assertIn("a_bronze_kill", p.achievements)
        # 累计到 50 → 白银
        for _ in range(49):
            m.check("kill", enemy_id="x")
        self.assertIn("a_silver_kill", p.achievements)
        # 累计到 200 → 黄金
        for _ in range(150):
            m.check("kill", enemy_id="x")
        self.assertIn("a_gold_kill", p.achievements)

    def test_kill_counter_not_double_counted(self):
        """多成就共享 kill 事件时，进度只自增一次。"""
        p = _FakePlayer()
        m = _mgr(p)
        m.check("kill", enemy_id="x")
        # 一次事件仅使 kill_count +1，而非每个 kill 成就各 +1
        self.assertEqual(p.achievement_progress["kill_count"], 1)

    def test_skill_learn_count_and_hidden_specific(self):
        p = _FakePlayer()
        m = _mgr(p)
        # 习得失传十式 → 白银博学多闻
        for _ in range(10):
            m.check("skill_learn", skill_id=f"skill_{_}")
        self.assertIn("a_silver_skill", p.achievements)
        # 习得指定剑道绝学 → 隐藏成就（解锁隐藏事件）
        unlocked = m.check("skill_learn", skill_id="sword_art")
        ids = [u[0] for u in unlocked]
        self.assertIn("a_hidden_sword", ids)
        self.assertIn("hidden_event_sword_tomb", p.unlocked_hidden_events)

    def test_world_boss_hidden(self):
        p = _FakePlayer()
        m = _mgr(p)
        unlocked = m.check("kill", enemy_id="boss", world_boss=True)
        ids = [u[0] for u in unlocked]
        self.assertIn("a_hidden_boss", ids)
        self.assertIn("hidden_event_divine_slayer", p.unlocked_hidden_events)

    def test_breakthrough_realm_grants_title(self):
        p = _FakePlayer()
        m = _mgr(p)
        m.check("breakthrough", realm_id="golden_core_early")
        self.assertIn("a_gold_realm_gc", p.achievements)
        self.assertIn("金丹客", p.titles)
        self.assertEqual(p.title_bonuses.get("attack"), 5)
        self.assertEqual(p.base_attack, 15)  # 10 + 5
        self.assertEqual(p.base_defense, 8)  # 5 + 3

    def test_win_event(self):
        p = _FakePlayer()
        m = _mgr(p)
        m.check("win_game")
        self.assertIn("a_imm_win", p.achievements)
        self.assertIn("登仙者", p.titles)


class TestProgressSummary(unittest.TestCase):
    def test_hidden_masking_before_and_after_unlock(self):
        p = _FakePlayer()
        m = _mgr(p)
        summary = m.get_progress_summary()
        hidden = next(it for it in summary["items"] if it["id"] == "a_hidden_boss")
        self.assertFalse(hidden["done"])
        self.assertEqual(hidden["name"], "？？？")  # 未解锁脱敏

        m.check("kill", enemy_id="b", world_boss=True)
        summary2 = m.get_progress_summary()
        hidden2 = next(it for it in summary2["items"] if it["id"] == "a_hidden_boss")
        self.assertTrue(hidden2["done"])
        self.assertEqual(hidden2["name"], "弑神者")  # 解锁后显示真名

    def test_tier_grouping(self):
        p = _FakePlayer()
        m = _mgr(p)
        m.check("kill", enemy_id="x")
        summary = m.get_progress_summary()
        self.assertIn("青铜", summary["by_tier"])
        self.assertIn("a_bronze_kill", p.achievements)
        self.assertGreaterEqual(summary["by_tier"]["青铜"]["completed"], 1)


class TestBackwardCompat(unittest.TestCase):
    def test_missing_attrs_initialized(self):
        class _Bare:
            pass

        b = _Bare()
        m = AchievementManager(b, None, config_dir="config")
        self.assertEqual(b.titles, [])
        self.assertEqual(b.title_bonuses, {})
        self.assertEqual(b.unlocked_hidden_events, [])


if __name__ == "__main__":
    unittest.main()
