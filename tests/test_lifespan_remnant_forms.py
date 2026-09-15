# -*- coding: utf-8 -*-
"""残魂化身形态分化（M23）单元测试。

覆盖：形态选择优先级 / require_host 限制 / default 回退 / 月度 passive 应用 /
重塑几率加成 / 状态暴露 / 旧档 form 缺省兼容 / 配置合法与非法校验。
不依赖引擎。
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from game.lifespan_manager import LifespanManager
from game.player import Player


def _make_player(mental_state=50, heart_demon=0):
    p = Player(name="残魂试炼者")
    p.age = 16
    p.max_lifespan = 100
    p.realm_id = "nascent_soul"  # order 18，满足残魂门槛
    p.reincarnation_count = 0
    p.sit_pending = False
    p.past_life_arrangements = None
    p.past_life_relics = []
    p.remnant_soul = None
    p.is_remnant = False
    p.remnant_months = 0
    p.mental_state = mental_state
    p.heart_demon = heart_demon
    return p


def _make_mgr(player=None):
    return LifespanManager(player or _make_player())


class TestFormSelection(unittest.TestCase):
    def test_treasure_low_ms_falls_back_to_formless(self):
        # 低道心（<40）+ treasure：剑魂门槛不满足 → 无相残魂
        mgr = _make_mgr(_make_player(mental_state=20))
        ok, _ = mgr.become_remnant_soul("treasure")
        self.assertTrue(ok)
        self.assertEqual(mgr.player.remnant_soul["form"], "formless")

    def test_treasure_mid_ms_selects_sword(self):
        mgr = _make_mgr(_make_player(mental_state=50))
        ok, _ = mgr.become_remnant_soul("treasure")
        self.assertTrue(ok)
        self.assertEqual(mgr.player.remnant_soul["form"], "sword_soul")

    def test_beast_mid_ms_selects_beast(self):
        mgr = _make_mgr(_make_player(mental_state=50))
        ok, _ = mgr.become_remnant_soul("spirit_beast")
        self.assertTrue(ok)
        self.assertEqual(mgr.player.remnant_soul["form"], "beast_soul")

    def test_high_ms_selects_dao_over_sword(self):
        # 道心≥80 且 心魔≤20：道魂优先（min_mental_state 最高）
        mgr = _make_mgr(_make_player(mental_state=85, heart_demon=10))
        ok, _ = mgr.become_remnant_soul("treasure")
        self.assertTrue(ok)
        self.assertEqual(mgr.player.remnant_soul["form"], "dao_soul")

    def test_high_ms_beast_host_still_dao(self):
        mgr = _make_mgr(_make_player(mental_state=85, heart_demon=10))
        ok, _ = mgr.become_remnant_soul("spirit_beast")
        self.assertTrue(ok)
        self.assertEqual(mgr.player.remnant_soul["form"], "dao_soul")

    def test_high_ms_but_high_heart_blocks_dao(self):
        # 道心够但心魔>20 → 道魂不满足，treasure 回落剑魂
        mgr = _make_mgr(_make_player(mental_state=85, heart_demon=50))
        ok, _ = mgr.become_remnant_soul("treasure")
        self.assertTrue(ok)
        self.assertEqual(mgr.player.remnant_soul["form"], "sword_soul")


class TestFormMonthlyPassive(unittest.TestCase):
    def test_sword_passive_suppresses_heart(self):
        mgr = _make_mgr(_make_player(mental_state=50, heart_demon=10))
        mgr.become_remnant_soul("treasure")  # sword_soul: heart_delta -1
        with patch("game.lifespan_manager.random") as rng:
            rng.random.return_value = 0.99  # 不重塑
            mgr.tick_remnant_soul()
        self.assertEqual(mgr.player.heart_demon, 9)
        self.assertEqual(mgr.player.mental_state, 50)  # sword mental_delta 0
        self.assertEqual(mgr.player.remnant_months, 1)

    def test_beast_passive_nourishes_mental(self):
        mgr = _make_mgr(_make_player(mental_state=50, heart_demon=10))
        mgr.become_remnant_soul("spirit_beast")  # beast_soul: mental_delta +1
        with patch("game.lifespan_manager.random") as rng:
            rng.random.return_value = 0.99
            mgr.tick_remnant_soul()
        self.assertEqual(mgr.player.mental_state, 51)
        self.assertEqual(mgr.player.heart_demon, 10)

    def test_reshape_bonus_applied(self):
        # 道魂 reshape_bonus=0.05，基础 0.03；random=0.07 介于之间 → 应重塑
        mgr = _make_mgr(_make_player(mental_state=85, heart_demon=10))
        mgr.become_remnant_soul("treasure")  # dao_soul
        mgr.player.remnant_months = 3  # 越过 min_months
        with patch("game.lifespan_manager.random") as rng:
            rng.random.return_value = 0.07
            reshaped = mgr.tick_remnant_soul()
        self.assertTrue(reshaped)
        self.assertFalse(mgr.player.is_remnant)


class TestFormStatusAndCompat(unittest.TestCase):
    def test_get_status_exposes_form(self):
        mgr = _make_mgr(_make_player(mental_state=85, heart_demon=10))
        mgr.become_remnant_soul("treasure")
        fs = mgr.get_status()["remnant_form"]
        self.assertIsNotNone(fs)
        self.assertEqual(fs["id"], "dao_soul")
        self.assertIn("monthly_passive", fs)

    def test_old_save_without_form_compat(self):
        # 模拟旧档：remnant_soul 无 form 键，不应崩溃
        p = _make_player()
        p.is_remnant = True
        p.remnant_soul = {"host_type": "treasure", "host_id": None}  # 旧格式
        mgr = LifespanManager(p)
        with patch("game.lifespan_manager.random") as rng:
            rng.random.return_value = 0.99
            mgr.tick_remnant_soul()
        # form 缺省回退到 default，passive 全 0，无异常
        self.assertEqual(mgr.player.heart_demon, 0)
        fs = mgr._form_status()
        self.assertEqual(fs["id"], "formless")


class TestConfigValidation(unittest.TestCase):
    def test_real_config_valid(self):
        import sys
        sys.path.insert(0, ".")
        from tools.validate_configs import validate_lifespan
        errs = validate_lifespan("config")
        self.assertEqual(errs, [], msg="\n".join(errs))

    def test_invalid_form_rejected(self):
        import sys
        sys.path.insert(0, ".")
        from tools.validate_configs import validate_lifespan
        bad = {
            "sit_and_dissolve": {"near_end_years": 10, "arrangements": {"heir": {}}},
            "remnant_soul": {
                "min_realm_order": 18,
                "host_types": ["treasure", "spirit_beast"],
                "reshape_chance_per_month": 0.03,
                "min_months_as_remnant": 3,
                "default_form": "formless",
                "forms": [
                    {
                        "id": "bad", "name": "坏形态", "desc": "缺 min_mental_state",
                        "max_heart_demon": 99, "require_host": "treasure",
                        "monthly_passive": {"mental_delta": 0, "heart_delta": 0, "reshape_bonus": 0}
                    },
                    {"id": "formless", "name": "无相", "desc": "兜底",
                     "min_mental_state": 0, "max_heart_demon": 99, "require_host": None,
                     "monthly_passive": {}}
                ]
            },
            "past_life_relics": {"echo_chance_on_explore": 0.15, "relic_pool": []},
        }
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "lifespan.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bad, f)
            errs = validate_lifespan(d)
        self.assertTrue(any("min_mental_state" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
