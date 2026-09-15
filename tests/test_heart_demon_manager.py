# -*- coding: utf-8 -*-
"""心魔·道心系统（维度①）单元测试。

覆盖：违戒心魔、重大挫折、游历道心、心魔劫幻境抉择、天人合一顿悟、月度衰减。
不依赖引擎，直接构造 MentalStateManager + Player。
"""
import unittest

from game.player import Player
from game.mental_state import MentalStateManager


def _make_player():
    p = Player(name="道心试炼者")
    p.mental_state = 50
    p.heart_demon = 0
    p.personality_tags = []
    p.tribulation_effects = {}
    return p


def _make_mgr(player=None):
    return MentalStateManager(player or _make_player())


class _SeqRng:
    """可控随机源：random() 依次返回 seq 中的值，choice 取首项。"""

    def __init__(self, seq):
        self.seq = list(seq)
        self.i = 0

    def random(self):
        v = self.seq[self.i]
        self.i += 1
        return v

    def choice(self, seq):
        return seq[0]


class TestPreceptViolation(unittest.TestCase):
    def test_non_demonic_path_learning_demonic_skill_triggers(self):
        p = _make_player()
        p.cultivation_path = "jian"  # 正道剑修
        mgr = _make_mgr(p)
        triggered, delta = mgr.on_precept_violation("blood_demon_art")
        self.assertTrue(triggered)
        self.assertEqual(delta, 12)
        self.assertEqual(p.heart_demon, 12)
        self.assertEqual(p.mental_state, 47)  # 50 - 3

    def test_demonic_path_learning_demonic_skill_no_trigger(self):
        p = _make_player()
        p.cultivation_path = "mo"  # 本就是魔道
        mgr = _make_mgr(p)
        triggered, delta = mgr.on_precept_violation("blood_demon_art")
        self.assertFalse(triggered)
        self.assertEqual(delta, 0)
        self.assertEqual(p.heart_demon, 0)

    def test_normal_skill_no_trigger(self):
        p = _make_player()
        p.cultivation_path = "jian"
        mgr = _make_mgr(p)
        triggered, delta = mgr.on_precept_violation("some_normal_skill")
        self.assertFalse(triggered)
        self.assertEqual(p.heart_demon, 0)


class TestMajorSetback(unittest.TestCase):
    def test_family_collapse_raises_heart_demon(self):
        p = _make_player()
        mgr = _make_mgr(p)
        triggered, delta = mgr.on_major_setback("family_collapse")
        self.assertTrue(triggered)
        self.assertEqual(delta, 20)
        self.assertEqual(p.heart_demon, 20)
        self.assertEqual(p.mental_state, 42)  # 50 - 8

    def test_unknown_setback_no_effect(self):
        p = _make_player()
        mgr = _make_mgr(p)
        triggered, delta = mgr.on_major_setback("nonexistent")
        self.assertFalse(triggered)
        self.assertEqual(delta, 0)


class TestTravelDaoHeart(unittest.TestCase):
    def test_famous_location_boosts_more(self):
        p = _make_player()
        mgr = _make_mgr(p)
        mgr.on_travel(location_id="qingyun")
        self.assertEqual(p.mental_state, 55)  # 50 + famous_gain(5)

    def test_famous_flag_boosts(self):
        p = _make_player()
        mgr = _make_mgr(p)
        mgr.on_travel(famous=True)
        self.assertEqual(p.mental_state, 55)

    def test_normal_travel_small_gain(self):
        p = _make_player()
        mgr = _make_mgr(p)
        mgr.on_travel(location_id="unknown_spot")
        self.assertEqual(p.mental_state, 51)  # 50 + normal_gain(1)


class TestHeartDemonTribulation(unittest.TestCase):
    def test_trigger_only_when_above_threshold(self):
        p = _make_player()
        mgr = _make_mgr(p)
        self.assertFalse(mgr.should_trigger_heart_demon_tribulation())
        p.heart_demon = 60  # threshold
        self.assertTrue(mgr.should_trigger_heart_demon_tribulation())
        p.heart_demon = 80
        self.assertTrue(mgr.should_trigger_heart_demon_tribulation())

    def test_choice_shapes_personality_and_effects(self):
        p = _make_player()
        p.heart_demon = 80
        mgr = _make_mgr(p)
        scenario = mgr.get_heart_demon_tribulation_scenario(rng=_SeqRng([0.0]))
        self.assertIsNotNone(scenario)
        sid = scenario["id"]
        cid = scenario["choices"][0]["id"]  # 'slay' -> personality_tag 'cold'
        ok, msg = mgr.apply_tribulation_choice(sid, cid)
        self.assertTrue(ok)
        self.assertIn("cold", p.personality_tags)
        self.assertIn("kill_event_chance", p.tribulation_effects)

    def test_invalid_choice_returns_false(self):
        p = _make_player()
        p.heart_demon = 80
        mgr = _make_mgr(p)
        ok, msg = mgr.apply_tribulation_choice("past_self", "no_such_choice")
        self.assertFalse(ok)

    def test_merciful_choice_tag(self):
        p = _make_player()
        p.heart_demon = 80
        mgr = _make_mgr(p)
        scenario = mgr.get_heart_demon_tribulation_scenario(rng=_SeqRng([0.0]))
        sid = scenario["id"]
        cid = scenario["choices"][1]["id"]  # 'forgive' -> 'merciful'
        ok, _ = mgr.apply_tribulation_choice(sid, cid)
        self.assertTrue(ok)
        self.assertIn("merciful", p.personality_tags)


class TestUnityEnlightenment(unittest.TestCase):
    def test_low_dao_heart_no_enlightenment(self):
        p = _make_player()
        p.mental_state = 50  # < min_mental_state(80)
        mgr = _make_mgr(p)
        self.assertIsNone(mgr.maybe_unity_enlightenment(rng=_SeqRng([0.0])))

    def test_technique_enlightenment(self):
        p = _make_player()
        p.mental_state = 90
        mgr = _make_mgr(p)
        # 第一次 random() < 0.05 触发；第二次 < 0.3 选神通
        res = mgr.maybe_unity_enlightenment(rng=_SeqRng([0.01, 0.1]))
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "technique")

    def test_qi_enlightenment(self):
        p = _make_player()
        p.mental_state = 90
        mgr = _make_mgr(p)
        # 第一次 < 0.05 触发；第二次 >= 0.3 选修为
        res = mgr.maybe_unity_enlightenment(rng=_SeqRng([0.01, 0.5]))
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "qi")
        self.assertGreater(res["multiplier"], 1.0)


class TestMonthlyTick(unittest.TestCase):
    def test_decay_reduces_heart_demon_and_restores_dao_heart(self):
        p = _make_player()
        p.heart_demon = 50
        p.mental_state = 40
        mgr = _make_mgr(p)
        mental_delta, heart_delta, events = mgr.tick_monthly()
        self.assertLess(p.heart_demon, 50)  # 衰减
        self.assertGreater(p.mental_state, 40)  # 恢复
        self.assertLessEqual(heart_delta, 0)


if __name__ == "__main__":
    unittest.main()
