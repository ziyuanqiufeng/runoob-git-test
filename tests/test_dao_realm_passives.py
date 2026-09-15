# -*- coding: utf-8 -*-
"""维度① 道境被动深化测试。

验证 mental_state_levels 顶部两阶（道心通明≥80 / 心境平和≥60）携带的道境被动：
- 无漏之境：心魔事件免疫 + 天人合一月几率乘算
- 护道之境：突破失败不折损道心 + 游历道心增长乘算
以及 get_dao_realm_status() 供 UI 的道境状态查询。
所有用例确定性（MagicMock 控制 rng），不依赖随机。
"""
import unittest
from unittest.mock import MagicMock

from game.player import Player
from game.mental_state import MentalStateManager


class TestDaoRealmPassives(unittest.TestCase):
    """道境被动行为测试。"""

    def setUp(self):
        self.player = Player(name="道境测试")
        self.mgr = MentalStateManager(self.player)

    # ---------- 无漏之境（道心≥80）：心魔事件免疫 ----------
    def test_heart_demon_event_immunity_at_high_realm(self):
        """道心通明阶：即使心魔达标且 rng 强制触发，也不产生任何心魔事件。"""
        self.player.heart_demon = 80
        self.player.health = 100
        self.player.max_health = 100
        self.player.mental_state = 85
        rng = MagicMock()
        rng.random.return_value = 0.0  # 本应强制触发
        events = self.mgr.check_heart_demon_events(rng=rng)
        self.assertEqual(events, [])
        self.assertEqual(self.player.health, 100)  # 未受伤

    def test_heart_demon_event_still_triggers_without_immunity(self):
        """非无漏之境：同样条件下仍正常触发心魔事件。"""
        self.player.heart_demon = 80
        self.player.health = 100
        self.player.max_health = 100
        self.player.mental_state = 50
        rng = MagicMock()
        rng.random.return_value = 0.0
        events = self.mgr.check_heart_demon_events(rng=rng)
        self.assertEqual(len(events), 1)
        self.assertLess(self.player.health, 100)

    # ---------- 无漏之境：天人合一月几率乘算 ----------
    def test_unity_enlightenment_chance_multiplied_triggers(self):
        """道心通明阶：chance 0.05 × 1.5 = 0.075，0.05 < 0.075 触发（qi）。"""
        self.player.mental_state = 85
        rng = MagicMock()
        rng.random.side_effect = [0.05, 0.9]  # 不返回 None；非 technique -> qi
        res = self.mgr.maybe_unity_enlightenment(rng=rng)
        self.assertIsNotNone(res)
        self.assertEqual(res["type"], "qi")

    def test_unity_enlightenment_chance_multiplied_no_trigger(self):
        """道心通明阶：0.08 ≥ 0.075 不触发。"""
        self.player.mental_state = 85
        rng = MagicMock()
        rng.random.side_effect = [0.08]
        self.assertIsNone(self.mgr.maybe_unity_enlightenment(rng=rng))

    def test_unity_enlightenment_below_min_no_trigger(self):
        """道心不足阈值（<80）即便 rng 命中也不触发。"""
        self.player.mental_state = 70
        rng = MagicMock()
        rng.random.side_effect = [0.0, 0.0]
        self.assertIsNone(self.mgr.maybe_unity_enlightenment(rng=rng))

    # ---------- 护道之境（道心≥60）：突破失败不折损道心 ----------
    def test_breakthrough_failure_protected(self):
        """心境平和阶：突破失败不再折损道心，仍正常积攒心魔。"""
        self.player.mental_state = 65
        self.player.heart_demon = 20
        self.mgr.on_breakthrough(success=False)
        self.assertEqual(self.player.mental_state, 65)
        self.assertEqual(self.player.heart_demon, 30)

    def test_breakthrough_failure_unprotected(self):
        """非护道之境：突破失败仍折损道心 5 点。"""
        self.player.mental_state = 50
        self.player.heart_demon = 20
        self.mgr.on_breakthrough(success=False)
        self.assertEqual(self.player.mental_state, 45)
        self.assertEqual(self.player.heart_demon, 30)

    def test_breakthrough_success_uses_passive_tier_normally(self):
        """心境平和阶：突破成功仍正常 +道心/-心魔（被动只改失败分支）。"""
        self.player.mental_state = 65
        self.player.heart_demon = 20
        self.mgr.on_breakthrough(success=True)
        self.assertEqual(self.player.mental_state, 70)
        self.assertEqual(self.player.heart_demon, 15)

    # ---------- 护道之境：游历道心增长乘算 ----------
    def test_travel_dao_heart_gain_multiplied(self):
        """心境平和阶：名山道心 famous_gain=5 × 1.5 = 7。"""
        self.player.mental_state = 65
        before = self.player.mental_state
        delta = self.mgr.on_travel(location_id="qingyun")
        self.assertEqual(delta, 7)
        self.assertEqual(self.player.mental_state, before + 7)

    def test_travel_dao_heart_gain_unmultiplied(self):
        """非护道之境：名山道心按基础 5 点。"""
        self.player.mental_state = 50
        before = self.player.mental_state
        delta = self.mgr.on_travel(location_id="qingyun")
        self.assertEqual(delta, 5)
        self.assertEqual(self.player.mental_state, before + 5)

    # ---------- 道境状态查询（UI 用） ----------
    def test_dao_realm_status_highest_no_next(self):
        """道心通明为最高阶，next_tier 应为 None，且携带被动。"""
        self.player.mental_state = 85
        status = self.mgr.get_dao_realm_status()
        self.assertEqual(status["name"], "道心通明")
        self.assertIsNotNone(status["passive"])
        self.assertIsNone(status["next_tier"])

    def test_dao_realm_status_mid_has_next(self):
        """心境平和阶应能看到下一阶「道心通明」。"""
        self.player.mental_state = 65
        status = self.mgr.get_dao_realm_status()
        self.assertEqual(status["name"], "心境平和")
        self.assertIsNotNone(status["next_tier"])
        self.assertEqual(status["next_tier"]["name"], "道心通明")
        self.assertEqual(status["next_tier"]["min"], 80)

    def test_dao_realm_status_low_no_passive(self):
        """道心蒙尘（<60）无被动。"""
        self.player.mental_state = 30
        status = self.mgr.get_dao_realm_status()
        self.assertEqual(status["name"], "道心蒙尘")
        self.assertIsNone(status["passive"])


if __name__ == "__main__":
    unittest.main()
