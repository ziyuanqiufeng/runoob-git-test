# -*- coding: utf-8 -*-
"""寿元与轮回晚年（维度⑤）单元测试。

覆盖：临近大限判定、坐化安排与身死转化、残魂化身高阶资格、残魂重塑、
前世遗迹回响。不依赖引擎。
"""
import random
import unittest

from game.player import Player
from game.lifespan_manager import LifespanManager


def _make_player():
    p = Player(name="轮回试炼者")
    p.age = 16
    p.max_lifespan = 100
    p.realm_id = "qi_refining_1"  # order 1，低于残魂门槛
    p.reincarnation_count = 0
    p.sit_pending = False
    p.past_life_arrangements = None
    p.past_life_relics = []
    p.remnant_soul = None
    p.is_remnant = False
    p.remnant_months = 0
    return p


def _make_mgr(player=None):
    return LifespanManager(player or _make_player())


class TestSitAndDissolve(unittest.TestCase):
    def test_not_near_end_cannot_arrange(self):
        mgr = _make_mgr()
        ok, _ = mgr.arrange_sit(["heir"])
        self.assertFalse(ok)
        self.assertFalse(mgr.player.sit_pending)

    def test_near_end_can_arrange(self):
        p = _make_player()
        p.age = 95  # max 100，near_end_years=10
        mgr = _make_mgr(p)
        ok, _ = mgr.arrange_sit(["heir", "leave_manual"])
        self.assertTrue(ok)
        self.assertTrue(mgr.player.sit_pending)
        self.assertIn("heir", mgr.player.past_life_arrangements)

    def test_invalid_arrangement_rejected(self):
        p = _make_player()
        p.age = 99
        mgr = _make_mgr(p)
        ok, _ = mgr.arrange_sit(["not_a_real_key"])
        self.assertFalse(ok)

    def test_on_death_converts_arrangements(self):
        p = _make_player()
        p.age = 99
        mgr = _make_mgr(p)
        mgr.arrange_sit(["leave_manual"])
        summary = mgr.on_death()
        self.assertTrue(any("功法" in s for s in summary))
        # 遗产：前世遗物中应出现功法残卷
        self.assertTrue(any(r.get("id") == "legacy_manual" for r in p.past_life_relics))
        self.assertFalse(p.sit_pending)


class TestRemnantSoul(unittest.TestCase):
    def test_cannot_become_remnant_at_low_realm(self):
        mgr = _make_mgr()
        ok, _ = mgr.become_remnant_soul("treasure")
        self.assertFalse(ok)

    def test_can_become_remnant_at_high_realm(self):
        p = _make_player()
        p.realm_id = "nascent_soul"  # order 18
        mgr = _make_mgr(p)
        ok, _ = mgr.become_remnant_soul("treasure")
        self.assertTrue(ok)
        self.assertTrue(p.is_remnant)
        self.assertEqual(p.remnant_soul["host_type"], "treasure")

    def test_reshape_after_min_months(self):
        p = _make_player()
        p.realm_id = "nascent_soul"
        mgr = _make_mgr(p)
        mgr.become_remnant_soul("treasure")
        # 先推进到最低月数（不重塑）
        orig = random.random
        random.random = lambda: 0.99  # 高于 reshape_chance(0.03)
        try:
            for _ in range(3):
                mgr.tick_remnant_soul()
            self.assertTrue(p.is_remnant)  # 仍残魂
            # 强制重塑成功
            random.random = lambda: 0.0
            reshaped = mgr.tick_remnant_soul()
            self.assertTrue(reshaped)
            self.assertFalse(p.is_remnant)
        finally:
            random.random = orig


class TestPastLifeEcho(unittest.TestCase):
    def test_echo_requires_past_life(self):
        mgr = _make_mgr()
        self.assertIsNone(mgr.roll_past_life_echo())

    def test_echo_triggers_with_past_life(self):
        p = _make_player()
        p.reincarnation_count = 1
        mgr = _make_mgr(p)
        orig = random.random
        random.random = lambda: 0.0  # 强制触发
        try:
            echo = mgr.roll_past_life_echo()
            self.assertIsNotNone(echo)
        finally:
            random.random = orig


if __name__ == "__main__":
    unittest.main()
