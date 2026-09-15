# -*- coding: utf-8 -*-
"""RealmRewardManager 单元测试（F-03 秘境币结算）。"""
import unittest

from game.player import Player
from game.realm_reward import RealmRewardManager


class _FakeItemLib:
    def create(self, iid):
        return type("Item", (), {
            "id": iid, "name": iid,
            "type": "material", "value": 10, "effects": {},
            "description": "",
            "stackable": False, "count": 1, "max_stack": 99,
        })()

    def get(self, iid):
        return self.create(iid)


def _make():
    p = Player(name="t")
    p.realm_coins = 0
    mgr = RealmRewardManager(p, _FakeItemLib(), config_dir="config")
    return p, mgr


class TestRealmReward(unittest.TestCase):
    def test_coins_and_exchange(self):
        p, mgr = _make()
        p.realm_coins = 100
        ok, msg = mgr.exchange("spirit_stone")  # cost 30
        self.assertTrue(ok)
        self.assertEqual(p.realm_coins, 70)
        self.assertGreaterEqual(len(p.inventory), 1)
        # 余额不足
        p.realm_coins = 0
        ok2, _ = mgr.exchange("phoenix_feather")
        self.assertFalse(ok2)

    def test_record_and_summary(self):
        p, mgr = _make()
        mgr.record_discovery("cards", "iron_body")
        self.assertIn("iron_body", p.realm_compendium["cards"])
        run = {
            "coins": 50,
            "discovered": {"cards": ["iron_body"], "bosses": ["fire_realm"],
                           "events": ["spirit_spring"]},
            "cards": [{"card_id": "iron_body", "stacks": 1}],
            "realm_id": "fire_realm",
        }
        summary = mgr.end_run_summary("fire_realm", True, run)
        self.assertEqual(summary["coins_earned"], 50)
        self.assertEqual(summary["total_realm_coins"], 50)
        self.assertIn("fire_realm", p.realm_compendium["bosses"])


if __name__ == "__main__":
    unittest.main()
