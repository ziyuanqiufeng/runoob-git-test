# -*- coding: utf-8 -*-
"""维度② 红尘炼心 / 入世 —— 管理器逻辑测试。

覆盖：配置加载、入世/出尘、月度 no-op 与活跃态事件、主动历红尘、
情劫抉择、道心/心魔边界钳制、状态读取、pending_qingjie 持久化到 player。
"""
import random
import unittest

from game.player import Player
from game.red_dust_manager import RedDustManager, RedDustConfig


def _make_player():
    return Player(name="红尘测试")


def _make_mgr(player=None):
    return RedDustManager(player or _make_player(), config_dir="config")


class TestRedDustConfig(unittest.TestCase):
    def test_config_loads(self):
        cfg = RedDustConfig(config_dir="config")
        self.assertIn("bond_types", cfg.data)
        self.assertIn("red_dust_events", cfg.data)
        self.assertIn("qingjie_scenarios", cfg.data)
        self.assertTrue(cfg.get_bond_types())
        self.assertTrue(cfg.get_events())
        self.assertTrue(cfg.get_qingjie())


class TestRedDustEnterExit(unittest.TestCase):
    def test_enter_sets_active(self):
        mgr = _make_mgr()
        ok, msg = mgr.enter_red_dust()
        self.assertTrue(ok)
        self.assertTrue(mgr.is_active())
        self.assertEqual(mgr.player.red_dust_active, True)

    def test_enter_twice_fails(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        ok, msg = mgr.enter_red_dust()
        self.assertFalse(ok)

    def test_exit_without_enter_fails(self):
        mgr = _make_mgr()
        ok, msg = mgr.exit_red_dust()
        self.assertFalse(ok)

    def test_exit_resets_bonds_and_active(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        mgr._form_bond("zhiji")
        self.assertEqual(len(mgr.player.red_dust_bonds), 1)
        ok, msg = mgr.exit_red_dust()
        self.assertTrue(ok)
        self.assertFalse(mgr.is_active())
        self.assertEqual(mgr.player.red_dust_bonds, [])


class TestRedDustTick(unittest.TestCase):
    def test_tick_noop_when_inactive(self):
        mgr = _make_mgr()
        before = mgr.player.red_dust_months
        mgr.tick_monthly()
        self.assertEqual(mgr.player.red_dust_months, before)
        self.assertEqual(mgr.player.red_dust_bonds, [])

    def test_tick_active_forms_bond_and_qingjie(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        orig = random.random
        random.random = lambda: 0.0  # 强制所有概率判定通过
        try:
            mgr.tick_monthly()
        finally:
            random.random = orig
        self.assertEqual(mgr.player.red_dust_months, 1)
        self.assertTrue(len(mgr.player.red_dust_bonds) >= 1)
        self.assertIsNotNone(mgr.player.red_dust_pending_qingjie)

    def test_experience_requires_active(self):
        mgr = _make_mgr()
        ok, msg = mgr.experience()
        self.assertFalse(ok)

    def test_experience_active_triggers(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        ok, msg = mgr.experience()
        self.assertTrue(ok)
        self.assertIsNotNone(msg)


class TestRedDustQingjie(unittest.TestCase):
    def test_apply_without_pending_fails(self):
        mgr = _make_mgr()
        ok, msg = mgr.apply_qingjie_choice("let_go")
        self.assertFalse(ok)

    def test_apply_choice_adjusts_and_clears(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        scenario = {
            "id": "qj_parting",
            "name": "生离死别",
            "description": "x",
            "choices": [
                {"id": "let_go", "text": "放手", "result_text": "悟",
                 "effects": {"mental_delta": 6, "heart_delta": -3}},
                {"id": "cling", "text": "强留", "result_text": "执",
                 "effects": {"mental_delta": -2, "heart_delta": 8}},
            ],
        }
        mgr.player.red_dust_pending_qingjie = scenario
        mgr.player.mental_state = 50
        mgr.player.heart_demon = 10  # 非零基线，避免负向钳制掩盖断言
        mental0 = mgr.player.mental_state
        heart0 = mgr.player.heart_demon
        ok, msg = mgr.apply_qingjie_choice("let_go")
        self.assertTrue(ok)
        self.assertEqual(mgr.player.mental_state, mental0 + 6)
        self.assertEqual(mgr.player.heart_demon, heart0 - 3)
        self.assertIsNone(mgr.player.red_dust_pending_qingjie)

    def test_invalid_choice_fails(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        mgr.player.red_dust_pending_qingjie = {
            "id": "x", "name": "x", "description": "",
            "choices": [{"id": "a", "text": "t", "result_text": "r", "effects": {}}],
        }
        ok, msg = mgr.apply_qingjie_choice("nonexistent")
        self.assertFalse(ok)


class TestRedDustBounds(unittest.TestCase):
    def test_mental_clamped(self):
        mgr = _make_mgr()
        mgr.player.mental_state = 50
        mgr._adjust_mental(999)
        self.assertEqual(mgr.player.mental_state, 100)
        mgr._adjust_mental(-999)
        self.assertEqual(mgr.player.mental_state, 0)

    def test_heart_clamped(self):
        mgr = _make_mgr()
        mgr.player.heart_demon = 0
        mgr._adjust_heart(999)
        self.assertEqual(mgr.player.heart_demon, 100)
        mgr._adjust_heart(-999)
        self.assertEqual(mgr.player.heart_demon, 0)


class TestRedDustStatus(unittest.TestCase):
    def test_get_status_keys(self):
        mgr = _make_mgr()
        status = mgr.get_status()
        for key in ("active", "months", "bonds", "mental_state", "heart_demon",
                    "pending_qingjie", "bond_types", "enter", "exit"):
            self.assertIn(key, status)


if __name__ == "__main__":
    unittest.main()
