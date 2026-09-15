# -*- coding: utf-8 -*-
"""M22：天道反噬事件池（维度④）单元测试。

覆盖：事件池配置加载、min_gaze 阈值筛选、加权抽取、四类效果（修为折损 /
灵石损失 / 道心波动 / 心魔波动）应用与钳制、召来追夺者开战、roll_travel_hazard
集成、配置校验合法与非法、get_status 暴露。不依赖完整引擎。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

from game.player import Player
from game.item import Item
from game.heaven_retribution_manager import HeavenRetributionManager


def _make_player():
    p = Player(name="天道反噬试炼者")
    p.heaven_gaze = 0
    p.territory = None
    p.qi = 0
    p.mental_state = 50
    p.heart_demon = 0
    return p


def _make_mgr(player=None):
    return HeavenRetributionManager(player or _make_player())


def _give_stones(player, n):
    for _ in range(n):
        player.add_item(Item(
            item_id="spirit_stone", name="灵石", item_type="currency", value=1,
            description="", effects={}, stackable=True, max_stack=99, count=1,
        ))


class _RngSequence:
    """按序返回给定 random() 值的假 rng。"""

    def __init__(self, values):
        self._vals = list(values)
        self._i = 0

    def random(self):
        v = self._vals[self._i]
        self._i += 1
        return v


class _FakeEngine:
    """仅含反噬事件所需接口。"""

    def __init__(self):
        self.start_combat_calls = 0
        self.enemy_library = {"robber": object()}

    def start_combat(self, enemy):
        self.start_combat_calls += 1


class TestRetributionEventConfigAndFilter(unittest.TestCase):
    def test_events_loaded(self):
        mgr = _make_mgr()
        self.assertTrue(len(mgr.config.get_retribution_events()) >= 6)

    def test_min_gaze_filtering(self):
        mgr = _make_mgr()
        p = mgr.player
        p.heaven_gaze = 10
        eligible = [e["id"] for e in mgr.get_status()["eligible_events"]]
        self.assertIn("thunder_light", eligible)
        self.assertIn("treasure_dissipate", eligible)
        self.assertNotIn("heart_whisper", eligible)  # min_gaze 40

        p.heaven_gaze = 50
        eligible = [e["id"] for e in mgr.get_status()["eligible_events"]]
        self.assertIn("heart_whisper", eligible)
        self.assertIn("heaven_robber", eligible)
        self.assertNotIn("dao_crack", eligible)  # min_gaze 75

        p.heaven_gaze = 80
        eligible = [e["id"] for e in mgr.get_status()["eligible_events"]]
        self.assertIn("dao_crack", eligible)
        self.assertIn("great_cataclysm", eligible)


class TestRetributionEventRoll(unittest.TestCase):
    def test_no_event_when_gaze_zero(self):
        mgr = _make_mgr()
        logs = mgr.roll_retribution_event(_FakeEngine(), _RngSequence([0.0, 0.0]))
        self.assertEqual(logs, [])

    def test_event_skipped_when_chance_gate_fails(self):
        mgr = _make_mgr()
        mgr.player.heaven_gaze = 80
        logs = mgr.roll_retribution_event(_FakeEngine(), _RngSequence([0.9]))
        self.assertEqual(logs, [])

    def test_qi_loss_applied(self):
        mgr = _make_mgr()
        p = mgr.player
        p.heaven_gaze = 80
        p.qi = 100
        # rng1=0.1(<0.35 过关) rng2=0.0 → 首个事件 thunder_light(qi_loss 30)
        logs = mgr.roll_retribution_event(_FakeEngine(), _RngSequence([0.1, 0.0]))
        self.assertEqual(p.qi, 70)
        self.assertTrue(any("天道反噬" in l for l in logs))

    def test_stone_loss_consumes_items(self):
        mgr = _make_mgr()
        p = mgr.player
        p.heaven_gaze = 80
        _give_stones(p, 500)
        # rng1=0.1 过关; rng2=0.3 → pick=0.3*45=13.5 → treasure_dissipate(stone_loss 100)
        logs = mgr.roll_retribution_event(_FakeEngine(), _RngSequence([0.1, 0.3]))
        self.assertEqual(p.count_item("spirit_stone"), 400)

    def test_mental_and_heart_deltas(self):
        mgr = _make_mgr()
        p = mgr.player
        p.heaven_gaze = 50
        p.mental_state = 50
        p.heart_demon = 0
        # rng1=0.1(<0.20 过关); rng2=0.6 → pick=0.6*33=19.8 → heart_whisper
        mgr.roll_retribution_event(_FakeEngine(), _RngSequence([0.1, 0.6]))
        self.assertEqual(p.mental_state, 46)  # -4
        self.assertEqual(p.heart_demon, 8)    # +8

    def test_deltas_clamped_at_bounds(self):
        mgr = _make_mgr()
        p = mgr.player
        p.heaven_gaze = 80
        p.heart_demon = 95
        p.mental_state = 100
        # 选 great_cataclysm（min_gaze 75）：rng2=0.95 → pick=0.95*45=42.75 → 该事件
        mgr.roll_retribution_event(_FakeEngine(), _RngSequence([0.1, 0.95]))
        self.assertLessEqual(p.heart_demon, 100)
        self.assertLessEqual(p.mental_state, 100)

    def test_spawn_enemy_triggers_combat(self):
        mgr = _make_mgr()
        mgr.player.heaven_gaze = 50
        eng = _FakeEngine()
        # 选 heaven_robber（第4，min_gaze 40）：rng2=0.9 → pick=0.9*33=29.7 → robber
        mgr.roll_retribution_event(eng, _RngSequence([0.1, 0.9]))
        self.assertEqual(eng.start_combat_calls, 1)


class TestTravelHazardIntegration(unittest.TestCase):
    def test_travel_hazard_includes_retribution_event(self):
        import unittest.mock as mock
        mgr = _make_mgr()
        mgr.player.heaven_gaze = 80
        eng = _FakeEngine()
        with mock.patch.object(mgr, "roll_retribution_event",
                               return_value=["[red]天道反噬·单元测试"]):
            logs = mgr.roll_travel_hazard(eng)
        self.assertIn("[red]天道反噬·单元测试", logs)


class TestRetributionEventValidation(unittest.TestCase):
    def test_valid_config_has_no_errors(self):
        sys.path.insert(0, ".")
        from tools.validate_configs import validate_heaven_retribution
        errs = validate_heaven_retribution("config")
        self.assertEqual(errs, [], msg="\n".join(errs))

    def test_duplicate_event_id_flagged(self):
        sys.path.insert(0, ".")
        from tools.validate_configs import validate_heaven_retribution
        tmp = tempfile.mkdtemp()
        try:
            with open("config/heaven_retribution.json", encoding="utf-8") as f:
                data = json.load(f)
            data["retribution_events"].append(dict(data["retribution_events"][0]))
            with open(os.path.join(tmp, "heaven_retribution.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            errs = validate_heaven_retribution(tmp)
            self.assertTrue(any("重复" in e for e in errs), msg="\n".join(errs))
        finally:
            shutil.rmtree(tmp)

    def test_bad_weight_flagged(self):
        sys.path.insert(0, ".")
        from tools.validate_configs import validate_heaven_retribution
        tmp = tempfile.mkdtemp()
        try:
            with open("config/heaven_retribution.json", encoding="utf-8") as f:
                data = json.load(f)
            data["retribution_events"][0]["weight"] = -1
            with open(os.path.join(tmp, "heaven_retribution.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            errs = validate_heaven_retribution(tmp)
            self.assertTrue(any("weight" in e for e in errs), msg="\n".join(errs))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
