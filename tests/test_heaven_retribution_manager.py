# -*- coding: utf-8 -*-
"""天道反噬与生态平衡（维度④）单元测试。

覆盖：灵脉枯竭积累/恢复/满值产出归零、天道注视暴涨触发/衰减/消除、
等级阈值、游历无妄之灾、交易拒绝。不依赖引擎。
"""
import random
import unittest

from game.player import Player
from game.heaven_retribution_manager import HeavenRetributionManager


def _make_player():
    p = Player(name="天道试炼者")
    p.heaven_gaze = 0
    p.territory = None
    return p


def _make_mgr(player=None):
    return HeavenRetributionManager(player or _make_player())


class _FixedRng:
    """强制 random() 返回固定值序列。"""

    def __init__(self, value):
        self._value = value

    def random(self):
        return self._value

    def choice(self, seq):
        return seq[0]


class TestSpiritVeinDepletion(unittest.TestCase):
    def test_depletion_grows_when_over_capacity(self):
        mgr = _make_mgr()
        terr = {"tier": "spirit_vein", "name": "试炼灵脉", "depletion": 0, "treasury": 0}
        # 容量 200，抽取 1000 → 超额 800 * 0.05 = 40
        dep, monster = mgr.check_territory_depletion(terr, 1000)
        self.assertAlmostEqual(dep, 40)
        self.assertFalse(monster)

    def test_depletion_recovers_when_under_capacity(self):
        mgr = _make_mgr()
        terr = {"tier": "spirit_vein", "name": "试炼灵脉", "depletion": 30, "treasury": 0}
        dep, _ = mgr.check_territory_depletion(terr, 50)  # 低于容量 200
        self.assertEqual(dep, 28)  # 30 - 2.0

    def test_full_depletion_triggers_monster_and_zero_output(self):
        mgr = _make_mgr()
        # 强制 random < monster_chance(0.3)
        orig = random.random
        random.random = lambda: 0.1
        try:
            terr = {"tier": "spirit_vein", "name": "枯竭灵脉", "depletion": 99, "treasury": 500}
            dep, monster = mgr.check_territory_depletion(terr, 1000)
            self.assertEqual(dep, 100)
            self.assertTrue(monster)
            self.assertAlmostEqual(mgr.territory_output_multiplier(terr), 0.0)
        finally:
            random.random = orig

    def test_tier_capacity_scales(self):
        mgr = _make_mgr()
        self.assertEqual(mgr.config.get_tier_capacity("spirit_vein"), 200)
        self.assertEqual(mgr.config.get_tier_capacity("cave_heaven"), 1500)


class TestHeavenGaze(unittest.TestCase):
    def test_power_spike_adds_gaze(self):
        mgr = _make_mgr()
        self.assertTrue(mgr.on_power_spike(800))  # >= 500
        self.assertEqual(mgr._gaze(), 15)
        # 小增幅不触发
        mgr2 = _make_mgr()
        self.assertFalse(mgr2.on_power_spike(100))
        self.assertEqual(mgr2._gaze(), 0)

    def test_wealth_spike_adds_gaze(self):
        mgr = _make_mgr()
        self.assertTrue(mgr.on_wealth_spike(100, 200))  # 翻倍
        self.assertEqual(mgr._gaze(), 15)
        self.assertFalse(mgr.on_wealth_spike(100, 120))  # 未翻倍

    def test_tick_monthly_decays(self):
        mgr = _make_mgr()
        mgr._set_gaze(20)
        mgr.tick_monthly()
        self.assertEqual(mgr._gaze(), 17)  # 20 - 3

    def test_gaze_level_thresholds(self):
        mgr = _make_mgr()
        self.assertIsNone(mgr.get_gaze_level())
        mgr._set_gaze(10)
        self.assertEqual(mgr.get_gaze_level(), "low")
        mgr._set_gaze(50)
        self.assertEqual(mgr.get_gaze_level(), "mid")
        mgr._set_gaze(80)
        self.assertEqual(mgr.get_gaze_level(), "high")

    def test_relieve_reduces_gaze(self):
        mgr = _make_mgr()
        mgr._set_gaze(40)
        self.assertTrue(mgr.relieve("donate"))  # -20
        self.assertEqual(mgr._gaze(), 20)

    def test_trade_refused_only_when_gaze(self):
        mgr = _make_mgr()
        self.assertFalse(mgr.is_trade_refused())
        mgr._set_gaze(80)
        orig = random.random
        random.random = lambda: 0.0  # < 0.7 high 阈值
        try:
            self.assertTrue(mgr.is_trade_refused())
        finally:
            random.random = orig

    def test_travel_hazard_logs_at_high_gaze(self):
        mgr = _make_mgr()
        mgr._set_gaze(80)
        orig = random.random
        random.random = lambda: 0.0  # 强制触发
        try:
            class _FakeEngine:
                enemy_library = {}
                def start_combat(self, foe):
                    self.fought = foe
            eng = _FakeEngine()
            logs = mgr.roll_travel_hazard(eng)
            self.assertTrue(any("无妄之灾" in l or "杀人夺宝" in l for l in logs))
        finally:
            random.random = orig


if __name__ == "__main__":
    unittest.main()
