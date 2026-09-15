# -*- coding: utf-8 -*-
"""前世遗物链（M25）单元测试。

覆盖：遗物链加成纯函数（每环 / 圆满 / 多链叠加）、_record_relic 去重入链、
坐化留功法入链、探索回响入链、链进度状态暴露、转世时加成应用与 relic_chain 跨世携带、
配置合法与非法校验。
不依赖引擎；转世应用测试直接走 ReincarnationManager。
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from game.lifespan_manager import (
    LifespanManager,
    LifespanConfig,
    compute_relic_chain_bonus,
)
from game.reincarnation_manager import ReincarnationManager
from game.player import Player


def _make_player(relic_chain=None):
    p = Player(name="遗物链试炼者")
    p.age = 95                              # 临近大限，便于测试坐化
    p.max_lifespan = 100
    p.realm_id = "qi_refining"
    p.reincarnation_count = 1              # 已轮回，可触发前世回响
    p.past_life_relics = []
    p.relic_chain = list(relic_chain or [])
    return p


def _make_mgr(player=None):
    return LifespanManager(player or _make_player())


RETURN_ALL = ["broken_flying_sword", "old_taoist_robe", "silent_jade_slip"]


class TestChainBonusPure(unittest.TestCase):
    def test_empty_chain_no_bonus(self):
        b = compute_relic_chain_bonus([])
        self.assertEqual(b, {
            "wisdom": 0, "luck": 0, "constitution": 0, "max_health": 0,
            "cultivation_speed": 0.0, "breakthrough_bonus": 0.0,
        })

    def test_one_link_per_link_only(self):
        # broken_flying_sword 同时是两条链的 link：
        # return_to_origin per_link wisdom+1/cult+0.02，legacy_codex per_link cult+0.03
        b = compute_relic_chain_bonus(["broken_flying_sword"])
        self.assertEqual(b["wisdom"], 1)
        self.assertAlmostEqual(b["cultivation_speed"], 0.02 + 0.03)
        self.assertEqual(b["max_health"], 0)

    def test_complete_chain_adds_set(self):
        b = compute_relic_chain_bonus(RETURN_ALL)
        self.assertEqual(b["wisdom"], 1 * 3 + 3)          # 3 环 + 圆满 3
        self.assertEqual(b["max_health"], 20)             # 圆满
        # return_to_origin 圆满 0.11 + legacy_codex 单环 0.03
        self.assertAlmostEqual(b["cultivation_speed"], 0.02 * 3 + 0.05 + 0.03)

    def test_two_chains_sum(self):
        # return_to_origin 完整（0.11）+ legacy_codex 完整（per_link 0.03×2=0.06，set 突破+0.03）
        b = compute_relic_chain_bonus(RETURN_ALL + ["legacy_manual"])
        self.assertAlmostEqual(b["cultivation_speed"], 0.11 + 0.06)
        self.assertAlmostEqual(b["breakthrough_bonus"], 0.03)


class TestRecordRelic(unittest.TestCase):
    def test_record_dedup_and_is_new(self):
        mgr = _make_mgr()
        self.assertTrue(mgr._record_relic("broken_flying_sword", "断剑残锋"))
        self.assertIn("broken_flying_sword", mgr.player.relic_chain)
        # 再次记录同名遗物：不重复入链，且 is_new=False
        self.assertFalse(mgr._record_relic("broken_flying_sword", "断剑残锋"))
        self.assertEqual(mgr.player.relic_chain.count("broken_flying_sword"), 1)
        # 本世遗物列表每次都追加（叙事）
        self.assertEqual(len(mgr.player.past_life_relics), 2)

    def test_on_death_leave_manual_enters_chain(self):
        mgr = _make_mgr()
        mgr.arrange_sit(["leave_manual"])
        summary = mgr.on_death()
        self.assertIn("legacy_manual", mgr.player.relic_chain)
        self.assertTrue(any("遗泽" in s for s in summary))

    def test_explore_echo_enters_chain(self):
        mgr = _make_mgr()
        pool = mgr.config.get_relics().get("relic_pool", [])
        with patch("game.lifespan_manager.random") as rng:
            rng.random.side_effect = [0.0, 0.0]   # 触发回响 + 触发拾遗
            rng.choice.return_value = pool[0]
            mgr.roll_past_life_echo()
        self.assertIn(pool[0]["id"], mgr.player.relic_chain)


class TestChainStatus(unittest.TestCase):
    def test_status_counts_and_complete_flag(self):
        mgr = _make_mgr(_make_player(RETURN_ALL))
        status = mgr.get_relic_chain_status()
        by_id = {s["id"]: s for s in status}
        self.assertEqual(by_id["return_to_origin"]["found"], 3)
        self.assertTrue(by_id["return_to_origin"]["complete"])
        self.assertEqual(by_id["legacy_codex"]["found"], 1)  # 只含 broken_flying_sword
        self.assertFalse(by_id["legacy_codex"]["complete"])

    def test_get_status_exposes_chain(self):
        mgr = _make_mgr(_make_player(["broken_flying_sword"]))
        s = mgr.get_status()
        self.assertIn("relic_chain", s)
        self.assertIn("relic_chains_status", s)
        self.assertEqual(len(s["relic_chains_status"]), 2)


class TestReincarnationAppliesChain(unittest.TestCase):
    def _reincarnate(self, relic_chain):
        p = _make_player(relic_chain)
        p.reincarnation_count = 1
        mgr = ReincarnationManager(p)
        new_data = mgr.apply_inheritance([])
        new_player = mgr.create_new_player(new_data, Player)
        return new_data, new_player

    def test_partial_chain_applies_per_link(self):
        _, np = self._reincarnate(["broken_flying_sword"])
        self.assertIn("broken_flying_sword", np.relic_chain)   # 跨世携带
        self.assertEqual(np.wisdom, 5 + 1)
        self.assertAlmostEqual(np.reincarnation_cultivation_bonus, 0.02 + 0.03)
        self.assertEqual(np.max_health, 100)

    def test_complete_chain_applies_set_and_carry(self):
        new_data, np = self._reincarnate(RETURN_ALL)
        self.assertEqual(set(np.relic_chain), set(RETURN_ALL))
        self.assertEqual(np.wisdom, 5 + 6)
        self.assertEqual(np.max_health, 120)
        self.assertEqual(np.health, 120)
        self.assertAlmostEqual(np.reincarnation_cultivation_bonus, 0.11 + 0.03)
        # 链加成也进了转世摘要
        self.assertAlmostEqual(new_data["relic_chain_bonuses"]["wisdom"], 6)


class TestConfigValidation(unittest.TestCase):
    def test_current_config_valid(self):
        from tools.validate_configs import validate_lifespan
        errors = validate_lifespan("config")
        self.assertEqual([e for e in errors if "relic_chains" in e], [])

    def test_invalid_link_ref_rejected(self):
        payload = {
            "sit_and_dissolve": {"near_end_years": 10, "arrangements": {}},
            "remnant_soul": {
                "min_realm_order": 18, "host_types": ["treasure"],
                "reshape_chance_per_month": 0.03, "default_form": "formless",
                "forms": [{"id": "formless", "name": "无相", "desc": "x",
                           "min_mental_state": 0, "max_heart_demon": 99,
                           "require_host": None, "monthly_passive": {}}],
            },
            "past_life_relics": {"echo_chance_on_explore": 0.1, "relic_pool": [
                {"id": "a", "name": "甲", "echo": "e"}]},
            "relic_chains": {"chains": [{
                "id": "bad", "name": "坏链", "desc": "d",
                "links": ["unknown_relic"],
                "per_link": {"wisdom": 1}, "set": {}}]},
        }
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "lifespan.json"), "w", encoding="utf-8") as f:
                json.dump(payload, f)
            from tools.validate_configs import validate_lifespan
            errors = validate_lifespan(d)
        self.assertTrue(any("unknown_relic" in e for e in errors))

    def test_invalid_bonus_type_rejected(self):
        payload = {
            "sit_and_dissolve": {"near_end_years": 10, "arrangements": {}},
            "remnant_soul": {
                "min_realm_order": 18, "host_types": ["treasure"],
                "reshape_chance_per_month": 0.03, "default_form": "formless",
                "forms": [{"id": "formless", "name": "无相", "desc": "x",
                           "min_mental_state": 0, "max_heart_demon": 99,
                           "require_host": None, "monthly_passive": {}}],
            },
            "past_life_relics": {"echo_chance_on_explore": 0.1, "relic_pool": [
                {"id": "a", "name": "甲", "echo": "e"}]},
            "relic_chains": {"chains": [{
                "id": "bad", "name": "坏链", "desc": "d",
                "links": ["a"], "per_link": {"wisdom": "很多"}, "set": {}}]},
        }
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "lifespan.json"), "w", encoding="utf-8") as f:
                json.dump(payload, f)
            from tools.validate_configs import validate_lifespan
            errors = validate_lifespan(d)
        self.assertTrue(any("wisdom" in e and "整数" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
