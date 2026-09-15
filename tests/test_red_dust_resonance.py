# -*- coding: utf-8 -*-
"""M21：红尘羁绊共鸣（Resonance）+ 温养（Warmth）测试。

覆盖：
- 共鸣档按亲密度阈值解锁（<40 无共鸣 / >=40 解锁首档 / >=80 解锁次档）；
- 月度共鸣结算 _apply_resonance_tick 对道心/心魔的稳定修正（含正/负 monthly_heart）；
- 温养羁绊 warm_bond：消耗灵石升温、上限钳制、资源不足失败、未入世/无此羁绊失败；
- get_status 暴露 resonances 与 warmth；
- config/red_dust.json 配置校验（合法 0 错误；非法升序/缺字段报错）；
- 引擎委托 red_dust_warm 接线。
"""
import json
import os
import tempfile
import unittest
import unittest.mock as mock  # noqa: F401  (used via unittest.mock.patch)

from game.player import Player
from game.red_dust_manager import RedDustManager
from tools.validate_configs import validate_red_dust


def _make_player():
    p = Player(name="共鸣测试")
    p.mental_state = 50
    p.heart_demon = 10
    return p


def _make_mgr(player=None):
    return RedDustManager(player or _make_player(), config_dir="config")


def _set_bond(mgr, btype, intimacy):
    mgr.player.red_dust_bonds = [
        {"type": btype, "name": mgr.config.get_bond_types()[btype]["name"], "intimacy": intimacy}
    ]


class TestResonanceThreshold(unittest.TestCase):
    def test_no_resonance_below_first_tier(self):
        mgr = _make_mgr()
        _set_bond(mgr, "zhiji", 39)
        self.assertIsNone(mgr._resonance_for(mgr.player.red_dust_bonds[0]))

    def test_first_tier_at_40(self):
        mgr = _make_mgr()
        _set_bond(mgr, "zhiji", 40)
        res = mgr._resonance_for(mgr.player.red_dust_bonds[0])
        self.assertEqual(res["name"], "高山流水")

    def test_second_tier_at_80(self):
        mgr = _make_mgr()
        _set_bond(mgr, "zhiji", 80)
        res = mgr._resonance_for(mgr.player.red_dust_bonds[0])
        self.assertEqual(res["name"], "金石之交")

    def test_all_five_types_unlock_at_80(self):
        mgr = _make_mgr()
        for bt in ("qingyuan", "zhiji", "zhiyou", "hongyan", "enyuan"):
            _set_bond(mgr, bt, 80)
            res = mgr._resonance_for(mgr.player.red_dust_bonds[0])
            self.assertIsNotNone(res, f"{bt} 应在 80 亲密度解锁共鸣")


class TestApplyResonanceTick(unittest.TestCase):
    def test_mental_up_heart_down(self):
        mgr = _make_mgr()
        _set_bond(mgr, "zhiji", 80)  # 金石之交: monthly_mental 3, monthly_heart -1
        mgr._apply_resonance_tick()
        self.assertEqual(mgr.player.mental_state, 53)
        self.assertEqual(mgr.player.heart_demon, 9)

    def test_no_effect_below_threshold(self):
        mgr = _make_mgr()
        _set_bond(mgr, "zhiji", 30)  # 未达 40 首档
        mgr._apply_resonance_tick()
        self.assertEqual(mgr.player.mental_state, 50)
        self.assertEqual(mgr.player.heart_demon, 10)

    def test_positive_heart_delta(self):
        mgr = _make_mgr()
        _set_bond(mgr, "enyuan", 80)  # 渡尽劫波: monthly_mental 2, monthly_heart 1
        mgr._apply_resonance_tick()
        self.assertEqual(mgr.player.mental_state, 52)
        self.assertEqual(mgr.player.heart_demon, 11)

    def test_resonance_applied_in_tick_monthly(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        _set_bond(mgr, "zhiji", 80)
        mgr.player.mental_state = 50
        mgr.player.heart_demon = 10
        # 固定 random：跳过随机事件/结缘（0.99 不小于 0.55/0.45），但 choice 仍可用
        with unittest.mock.patch("game.red_dust_manager.random") as mock_random:
            mock_random.random.return_value = 0.99
            mock_random.choice.side_effect = lambda seq: seq[-1]
            mgr.tick_monthly()
        # 衰减后 intimacy 76 → 高山流水（monthly_mental 2, monthly_heart 0）
        self.assertEqual(mgr.player.mental_state, 52)
        self.assertEqual(mgr.player.heart_demon, 10)


class TestWarmBond(unittest.TestCase):
    def _give_stones(self, mgr, n):
        from game.item import Item
        for _ in range(n):
            mgr.player.add_item(Item(
                item_id="spirit_stone", name="灵石", item_type="currency", value=1,
                description="", effects={}, stackable=True, max_stack=99, count=1,
            ))

    def test_warm_requires_active(self):
        mgr = _make_mgr()
        ok, msg = mgr.warm_bond("zhiji")
        self.assertFalse(ok)
        self.assertIn("入世", msg)

    def test_warm_no_such_bond(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        ok, msg = mgr.warm_bond("zhiji")
        self.assertFalse(ok)
        self.assertIn("并无羁绊", msg)

    def test_warm_insufficient_stones(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        _set_bond(mgr, "zhiji", 10)
        self._give_stones(mgr, 3)  # 不足 5
        before = mgr.player.red_dust_bonds[0]["intimacy"]
        ok, msg = mgr.warm_bond("zhiji")
        self.assertFalse(ok)
        self.assertEqual(mgr.player.red_dust_bonds[0]["intimacy"], before)

    def test_warm_success_consumes_stones(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        _set_bond(mgr, "zhiji", 10)
        self._give_stones(mgr, 10)
        before = mgr.player.red_dust_bonds[0]["intimacy"]
        ok, msg = mgr.warm_bond("zhiji")
        self.assertTrue(ok)
        self.assertEqual(mgr.player.red_dust_bonds[0]["intimacy"], before + 8)
        self.assertEqual(mgr.player.count_item("spirit_stone"), 5)

    def test_warm_at_cap_fails(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        _set_bond(mgr, "zhiji", 100)
        self._give_stones(mgr, 10)
        ok, msg = mgr.warm_bond("zhiji")
        self.assertFalse(ok)
        self.assertIn("无需", msg)


class TestStatusResonances(unittest.TestCase):
    def test_status_exposes_resonances_and_warmth(self):
        mgr = _make_mgr()
        mgr.enter_red_dust()
        _set_bond(mgr, "zhiji", 50)  # 高山流水共鸣 + 下一档金石之交(80)
        status = mgr.get_status()
        self.assertIn("resonances", status)
        self.assertIn("warmth", status)
        res = status["resonances"][0]
        self.assertEqual(res["resonance"]["name"], "高山流水")
        self.assertEqual(res["next"]["name"], "金石之交")
        self.assertEqual(status["warmth"]["cost_item"], "spirit_stone")
        self.assertEqual(status["warmth"]["cost_count"], 5)
        self.assertEqual(status["warmth"]["intimacy_gain"], 8)


class TestConfigValidation(unittest.TestCase):
    def test_valid_config_no_errors(self):
        errs = validate_red_dust("config")
        self.assertEqual(errs, [], f"合法配置不应报错：{errs}")

    def test_bad_resonance_order_reports_error(self):
        d = tempfile.mkdtemp()
        data = {
            "enter": {"bond_gain_chance": 0.1, "event_chance": 0.1, "qingjie_chance": 0.1},
            "exit": {"dao_heart_per_bond": 1, "heart_demon_per_bond": 1},
            "bond_types": {"zhiji": {"name": "知己", "mental_gain": 1, "heart_gain": 1, "intimacy_max": 100, "desc": "x"}},
            "monthly_decay": {"intimacy_decay_per_month": 1},
            "red_dust_events": [{"id": "e", "name": "e", "description": "e", "mental_delta": 0, "heart_delta": 0, "bond_chance": 0.1}],
            "qingjie_scenarios": [{"id": "q", "name": "q", "description": "q", "choices": [{"id": "a", "text": "t", "result_text": "r", "effects": {"mental_delta": 1, "heart_delta": 0}}]}],
            "bond_resonance": {"zhiji": [
                {"min_intimacy": 80, "name": "b", "monthly_mental": 1, "monthly_heart": 0, "desc": "x"},
                {"min_intimacy": 40, "name": "a", "monthly_mental": 1, "monthly_heart": 0, "desc": "x"},
            ]},
        }
        with open(os.path.join(d, "red_dust.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
        errs = validate_red_dust(d)
        self.assertTrue(any("升序" in e for e in errs), f"应报升序错误：{errs}")

    def test_bad_resonance_missing_name_reports_error(self):
        d = tempfile.mkdtemp()
        data = {
            "enter": {"bond_gain_chance": 0.1, "event_chance": 0.1, "qingjie_chance": 0.1},
            "exit": {"dao_heart_per_bond": 1, "heart_demon_per_bond": 1},
            "bond_types": {"zhiji": {"name": "知己", "mental_gain": 1, "heart_gain": 1, "intimacy_max": 100, "desc": "x"}},
            "monthly_decay": {"intimacy_decay_per_month": 1},
            "red_dust_events": [{"id": "e", "name": "e", "description": "e", "mental_delta": 0, "heart_delta": 0, "bond_chance": 0.1}],
            "qingjie_scenarios": [{"id": "q", "name": "q", "description": "q", "choices": [{"id": "a", "text": "t", "result_text": "r", "effects": {"mental_delta": 1, "heart_delta": 0}}]}],
            "bond_resonance": {"zhiji": [
                {"min_intimacy": 40, "monthly_mental": 1, "monthly_heart": 0, "desc": "x"},
            ]},
        }
        with open(os.path.join(d, "red_dust.json"), "w", encoding="utf-8") as f:
            json.dump(data, f)
        errs = validate_red_dust(d)
        self.assertTrue(any("name" in e for e in errs), f"应报缺 name 错误：{errs}")


class TestEngineDelegate(unittest.TestCase):
    def _make_engine(self, stones=20):
        from game.world import World
        from game.events import EventPool
        from game.item import ItemLibrary, Item
        from game.enemy import EnemyLibrary
        from game.skill import SkillLibrary
        from game.npc import NPCLibrary
        from game.quest import QuestLibrary
        from game.engine import GameEngine

        player = Player(name="温养引擎测试")
        for _ in range(stones):
            player.add_item(Item(
                item_id="spirit_stone", name="灵石", item_type="currency", value=1,
                description="", effects={}, stackable=True, max_stack=99, count=1,
            ))
        engine = GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
        )
        return engine

    def test_engine_red_dust_warm_wires_through(self):
        engine = self._make_engine(stones=20)
        engine.enter_red_dust()
        engine.red_dust_manager._form_bond("zhiji")  # intimacy 10
        before = engine.player.red_dust_bonds[0]["intimacy"]
        ok, msg = engine.red_dust_warm("zhiji")
        self.assertTrue(ok)
        self.assertEqual(engine.player.red_dust_bonds[0]["intimacy"], before + 8)
        self.assertEqual(engine.player.count_item("spirit_stone"), 15)


if __name__ == "__main__":
    unittest.main()
