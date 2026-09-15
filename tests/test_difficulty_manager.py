# -*- coding: utf-8 -*-
"""难度系统单元测试（F-06）。"""
import unittest

from game.difficulty_manager import DifficultyManager


class _FakePlayer:
    def __init__(self):
        self.difficulty = "normal"
        self.difficulty_modifiers = {}


class TestDifficultyManager(unittest.TestCase):
    def setUp(self):
        self.dm = DifficultyManager(config_dir="config")

    def test_modifiers_default_normal(self):
        mods = self.dm.get_modifiers("normal")
        for v in mods.values():
            self.assertAlmostEqual(v, 1.0)

    def test_modifiers_hell_stronger(self):
        mods = self.dm.get_modifiers("hell")
        self.assertGreater(mods["enemy_strength"], 1.0)
        self.assertLess(mods["production_mult"], 1.0)

    def test_invalid_difficulty_falls_back(self):
        self.assertEqual(self.dm.get_modifiers("nope")["enemy_strength"], 1.0)

    def test_apply_to_player(self):
        p = _FakePlayer()
        self.dm.apply_to_player(p, "hard")
        self.assertEqual(p.difficulty, "hard")
        self.assertEqual(p.difficulty_modifiers["enemy_strength"], 1.3)
        # 无效难度回退默认
        p2 = _FakePlayer()
        self.dm.apply_to_player(p2, "???")
        self.assertEqual(p2.difficulty, "normal")

    def test_heaven_pursuit_gate(self):
        self.assertTrue(self.dm.should_trigger_heaven_pursuit("hell", True))
        self.assertFalse(self.dm.should_trigger_heaven_pursuit("hell", False))
        self.assertFalse(self.dm.should_trigger_heaven_pursuit("normal", True))


class TestHeavenPursuitIntegration(unittest.TestCase):
    def test_on_breakthrough_hell_triggers(self):
        dm = DifficultyManager(config_dir="config")
        p = _FakePlayer()
        p.difficulty = "hell"
        calls = []

        class _FakeEngine:
            def is_feature_enabled(self, flag):
                return True

            def create_heaven_pursuer(self, player):
                return {"name": "天道追杀者"}

            def start_combat(self, enemy):
                calls.append(enemy)

        pursuer = dm.on_breakthrough(_FakeEngine(), p, is_major_breakthrough=True)
        self.assertIsNotNone(pursuer)
        self.assertEqual(len(calls), 1)

    def test_on_breakthrough_normal_no_trigger(self):
        dm = DifficultyManager(config_dir="config")
        p = _FakePlayer()
        p.difficulty = "normal"
        calls = []

        class _FakeEngine:
            def is_feature_enabled(self, flag):
                return True

            def create_heaven_pursuer(self, player):
                return {"name": "x"}

            def start_combat(self, enemy):
                calls.append(enemy)

        self.assertIsNone(dm.on_breakthrough(_FakeEngine(), p, is_major_breakthrough=True))
        self.assertEqual(len(calls), 0)

    def test_on_breakthrough_flag_disabled(self):
        dm = DifficultyManager(config_dir="config")
        p = _FakePlayer()
        p.difficulty = "hell"
        calls = []

        class _FakeEngine:
            def is_feature_enabled(self, flag):
                return False

            def start_combat(self, enemy):
                calls.append(enemy)

        self.assertIsNone(dm.on_breakthrough(_FakeEngine(), p, is_major_breakthrough=True))
        self.assertEqual(len(calls), 0)


if __name__ == "__main__":
    unittest.main()
