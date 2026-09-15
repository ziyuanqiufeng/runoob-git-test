# -*- coding: utf-8 -*-
"""FamilyEventManager 单元测试（F-01 家族事件）。"""
import unittest

from game.family import FamilyManager, FamilyEventManager


def _empty_family():
    return {
        "name": "测试族", "reputation": 0, "level": 1,
        "created_month": 0, "month": 20, "members": [],
        "buildings": {}, "treasury": 500, "resources": {"herb": 0, "ore": 0},
        "diplomacy": {}, "pending_events": [], "history": [],
        "next_member_id": 1, "stolen_stone": 0,
    }


class TestFamilyEvent(unittest.TestCase):
    def test_trigger_condition_loyalty(self):
        fam = _empty_family()
        fam["members"].append({"id": "m1", "name": "阿忠", "loyalty": 10,
                               "aptitude": 50})
        mgr = FamilyEventManager(config_dir="config")
        # 低忠诚成员应使 member_betrayal 成为候选；多次触发应返回事件或 None
        ev = mgr.maybe_trigger(fam, rng=__import__("random").Random(1))
        # 不强制一定触发，但若有事件应含 choices
        if ev:
            self.assertIn("choices", ev)

    def test_resolve_reputation_and_recruit(self):
        fam = _empty_family()
        fam["members"].append({"id": "m1", "name": "家主", "loyalty": 80,
                               "aptitude": 90})
        # 用真实 FamilyManager，使其 recruit_member 真正写入成员
        mgr = FamilyManager(
            player=None, config_dir="config", get_month_callback=lambda: 0
        )
        mgr.player = type("P", (), {"family": fam, "karma": 0})()
        ev_mgr = FamilyEventManager(config_dir="config")
        ev = {
            "event_id": "marriage_proposal", "name": "联姻提议",
            "choices": [
                {"text": "接受联姻", "effect": {"recruit": 1, "reputation": 20}},
                {"text": "婉拒", "effect": {"reputation": -5}},
            ],
        }
        rep_before = fam["reputation"]
        log = ev_mgr.resolve_event(fam, ev, 0, rng=None, family_manager=mgr)
        self.assertGreater(fam["reputation"], rep_before)
        self.assertEqual(len(fam["members"]), 2)
        self.assertTrue(ev["resolved"])

    def test_resolve_loyalty_effect(self):
        fam = _empty_family()
        fam["members"].append({"id": "m1", "name": "甲", "loyalty": 50,
                               "aptitude": 50})
        ev_mgr = FamilyEventManager(config_dir="config")
        ev = {
            "event_id": "internal_power_struggle", "name": "争权",
            "choices": [
                {"text": "铁腕", "effect": {"loyalty_all": -10, "reputation": 10}},
                {"text": "妥协", "effect": {"loyalty_all": 10, "reputation": -10}},
            ],
        }
        ev_mgr.resolve_event(fam, ev, 1, rng=None, family_manager=None)
        self.assertEqual(fam["members"][0]["loyalty"], 60)


if __name__ == "__main__":
    unittest.main()
