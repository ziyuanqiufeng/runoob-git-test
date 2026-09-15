# -*- coding: utf-8 -*-
"""多周目模式单元测试（F-07）。"""
import unittest

from game.meta_manager import MetaManager


class _FakePlayer:
    def __init__(self):
        self.reincarnation_count = 0
        self.has_won = False
        self.game_mode = "standard"
        self.spiritual_roots = ["fire"]
        self.root_purities = {"fire": 0.8}
        self.allowed_paths = []
        self.no_spiritual_roots = False
        self.hostile_factions = []
        self.karma = 0
        self.base_attack = 10
        self.base_defense = 5
        self.max_health = 100
        self.health = 100
        self.meta_modifiers = {}
        self.reincarnation_cultivation_bonus = 0.0
        self.pending_start_items = []


class TestMetaAvailability(unittest.TestCase):
    def setUp(self):
        self.mm = MetaManager(config_dir="config")

    def test_standard_always_available(self):
        p = _FakePlayer()
        ok, _ = self.mm.is_available(self.mm.config.get_mode("standard"), p)
        self.assertTrue(ok)

    def test_seize_rebirth_requires_reincarnation(self):
        mode = self.mm.config.get_mode("seize_rebirth")
        p0 = _FakePlayer()
        ok, reason = self.mm.is_available(mode, p0)
        self.assertFalse(ok)
        self.assertIn("轮回", reason)
        p1 = _FakePlayer()
        p1.reincarnation_count = 1
        self.assertTrue(self.mm.is_available(mode, p1)[0])

    def test_heaven_cycle_requires_won(self):
        mode = self.mm.config.get_mode("heaven_cycle")
        p0 = _FakePlayer()
        self.assertFalse(self.mm.is_available(mode, p0)[0])
        p0.has_won = True
        self.assertTrue(self.mm.is_available(mode, p0)[0])

    def test_modes_with_availability_flags(self):
        p = _FakePlayer()
        modes = self.mm.get_modes_with_availability(p)
        ids = [m["id"] for m in modes]
        self.assertIn("standard", ids)
        std = next(m for m in modes if m["id"] == "standard")
        self.assertTrue(std["current"])
        seize = next(m for m in modes if m["id"] == "seize_rebirth")
        self.assertFalse(seize["available"])


class TestMetaApply(unittest.TestCase):
    def setUp(self):
        self.mm = MetaManager(config_dir="config")

    def test_apply_standard_is_noop(self):
        p = _FakePlayer()
        self.mm.apply_to_player(p, "standard")
        self.assertEqual(p.game_mode, "standard")
        self.assertFalse(p.no_spiritual_roots)

    def test_apply_mortal_challenge(self):
        p = _FakePlayer()
        self.mm.apply_to_player(p, "mortal_challenge")
        self.assertTrue(p.no_spiritual_roots)
        self.assertEqual(p.spiritual_roots, [])
        self.assertEqual(p.allowed_paths, ["ti", "fu"])
        self.assertEqual(p.max_health, 130)
        self.assertEqual(p.health, 130)

    def test_apply_demonic_lone(self):
        p = _FakePlayer()
        self.mm.apply_to_player(p, "demonic_lone")
        self.assertEqual(p.karma, 30)
        self.assertIn("righteous", p.hostile_factions)
        self.assertEqual(p.base_attack, 15)

    def test_apply_invalid_falls_back(self):
        p = _FakePlayer()
        self.mm.apply_to_player(p, "???")
        self.assertEqual(p.game_mode, "standard")

    def test_apply_seize_rebirth_bonus(self):
        p = _FakePlayer()
        p.reincarnation_count = 2
        self.mm.apply_to_player(p, "seize_rebirth")
        self.assertEqual(p.karma, -20)
        self.assertGreater(p.reincarnation_cultivation_bonus, 0)
        self.assertIn("spirit_stone", p.pending_start_items)


if __name__ == "__main__":
    unittest.main()
