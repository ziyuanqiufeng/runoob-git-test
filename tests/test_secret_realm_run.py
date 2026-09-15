# -*- coding: utf-8 -*-
"""SecretRealmManager Roguelike 运行逻辑测试（F-03）。"""
import random
import unittest

from game.player import Player
from game.secret_realm import SecretRealmManager


class _FakeEnemyLib:
    def __init__(self):
        base = {"name": "x", "level": 1, "hp": 40, "attack": 8,
                "defense": 2, "description": "", "loot": [], "exp": 5, "skills": []}
        self._d = {
            eid: dict(base, id=eid, name=eid)
            for eid in ("fire_scorpion", "flame_lion", "fire_snake")
        }

    def get(self, eid):
        return self._d.get(eid)


class _FakeItemLib:
    def create(self, iid):
        return type("Item", (), {"id": iid, "name": iid})()

    def get(self, iid):
        return self.create(iid)


def _make_player():
    p = Player(name="测试")
    p.spiritual_roots = ["fire"]
    p.realm_id = "qi_refining_5"  # 满足 fire_realm 的 min_realm_order=5
    p.cultivation_path = "fa"
    return p


def _make_mgr(feature=True):
    rng = random.Random(1)
    p = _make_player()
    mgr = SecretRealmManager(
        p, _FakeEnemyLib(), _FakeItemLib(),
        config_dir="config", rng=rng,
        feature_enabled=(lambda f: feature),
    )
    mgr.unlock("fire_realm")
    return mgr, p


class TestSecretRealmRun(unittest.TestCase):
    def test_start_run_and_map(self):
        mgr, p = _make_mgr()
        ok, msg = mgr.start_run("fire_realm", "normal", None)
        self.assertTrue(ok, msg)
        self.assertTrue(mgr.is_run_active())
        run = mgr.current_run()
        self.assertEqual(run["qi"], mgr.node_mgr.start_qi)
        self.assertTrue(mgr.get_available_node_ids())

    def test_enter_node_returns_descriptor(self):
        mgr, p = _make_mgr()
        mgr.start_run("fire_realm", "normal", None)
        desc = mgr.enter_node(mgr.get_available_node_ids()[0])
        self.assertIn(desc["kind"],
                      ("battle", "elite", "boss", "event", "shop", "unknown"))

    def test_battle_win_draws_and_add_card(self):
        mgr, p = _make_mgr()
        mgr.start_run("fire_realm", "normal", None)
        nid = mgr.get_available_node_ids()[0]
        mgr.enter_node(nid)
        res = mgr.on_battle_cleared(nid, True)
        self.assertIn("draws", res)
        self.assertGreaterEqual(res["coins"], 0)
        # 不可叠加卡不会重复添加
        self.assertTrue(mgr.add_card("iron_body"))
        before = len(mgr.current_run()["cards"])
        mgr.add_card("iron_body")  # 非叠加，应无效
        mgr.add_card("iron_body")
        after = len(mgr.current_run()["cards"])
        self.assertEqual(before, after)

    def test_event_choice(self):
        mgr, p = _make_mgr()
        mgr.start_run("fire_realm", "normal", None)
        nid = mgr.get_available_node_ids()[0]
        mgr.enter_node(nid)
        ev = mgr._pick_event()
        mgr.active_run["pending_event"] = ev
        res = mgr.choose_event(nid, 0)
        self.assertIn("applied", res)

    def test_combat_mods_and_end(self):
        mgr, p = _make_mgr()
        mgr.start_run("fire_realm", "normal", None)
        mgr.add_card("iron_body")
        mods = mgr.get_combat_mods()
        self.assertGreater(mods["defense_pct"], 0)
        summary = mgr.end_run(False)
        self.assertFalse(summary["victory"])
        self.assertGreaterEqual(p.realm_coins, 0)

    def test_party_synergy(self):
        mgr, p = _make_mgr()
        mgr.start_run("fire_realm", "normal", None)
        mgr.active_run["party"] = [
            {"name": "我", "path": "jian"},
            {"name": "丹童", "path": "dan"},
        ]
        mods = mgr.get_combat_mods()
        # 剑修+丹修 攻击+10%
        self.assertAlmostEqual(mods["attack_pct"], 0.10)

    def test_feature_flag_off(self):
        mgr, p = _make_mgr(feature=False)
        ok, msg = mgr.can_start_roguelike("fire_realm")
        self.assertFalse(ok)
        self.assertIn("未开启", msg)


if __name__ == "__main__":
    unittest.main()
