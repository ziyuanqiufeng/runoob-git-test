# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock

from game.player import Player
from game.mental_state import MentalStateManager, MentalStateConfig


class TestMentalStateManager(unittest.TestCase):
    """心境 / 道心系统测试。"""

    def setUp(self):
        self.player = Player(name="测试修士")
        self.manager = MentalStateManager(self.player)

    def test_initial_values(self):
        """初始道心值与心魔值应符合默认值。"""
        self.assertEqual(self.player.mental_state, 50)
        self.assertEqual(self.player.heart_demon, 0)

    def test_adjust_mental_state_clamping(self):
        """道心值应在 0-100 之间裁剪。"""
        self.manager.adjust_mental_state(100)
        self.assertEqual(self.player.mental_state, 100)
        self.manager.adjust_mental_state(-200)
        self.assertEqual(self.player.mental_state, 0)

    def test_adjust_heart_demon_clamping(self):
        """心魔值应在 0-100 之间裁剪。"""
        self.manager.adjust_heart_demon(200)
        self.assertEqual(self.player.heart_demon, 100)
        self.manager.adjust_heart_demon(-200)
        self.assertEqual(self.player.heart_demon, 0)

    def test_get_level(self):
        """根据道心值返回正确的心境等级。"""
        self.player.mental_state = 85
        level = self.manager.get_level()
        self.assertEqual(level["name"], "道心通明")
        self.player.mental_state = 30
        level = self.manager.get_level()
        self.assertEqual(level["name"], "道心蒙尘")

    def test_breakthrough_bonus(self):
        """高道心提升突破成功率，低道心降低。"""
        self.player.mental_state = 85
        self.assertGreater(self.manager.get_breakthrough_bonus(), 0)
        self.player.mental_state = 10
        self.assertLess(self.manager.get_breakthrough_bonus(), 0)

    def test_on_killing_righteous(self):
        """击杀正道目标降低道心、增加心魔。"""
        self.player.mental_state = 50
        self.player.heart_demon = 0
        mental_delta, heart_delta = self.manager.on_killing("righteous")
        self.assertLess(mental_delta, 0)
        self.assertGreater(heart_delta, 0)

    def test_on_killing_evil(self):
        """击杀魔道目标提升道心、降低心魔。"""
        self.player.mental_state = 50
        self.player.heart_demon = 20
        mental_delta, heart_delta = self.manager.on_killing("evil")
        self.assertGreater(mental_delta, 0)
        self.assertLess(heart_delta, 0)

    def test_on_breakthrough_success(self):
        """突破成功提升道心、降低心魔。"""
        self.player.mental_state = 50
        self.player.heart_demon = 20
        self.manager.on_breakthrough(success=True)
        self.assertGreater(self.player.mental_state, 50)
        self.assertLess(self.player.heart_demon, 20)

    def test_on_breakthrough_failure(self):
        """突破失败降低道心、增加心魔。"""
        self.player.mental_state = 50
        self.player.heart_demon = 20
        self.manager.on_breakthrough(success=False)
        self.assertLess(self.player.mental_state, 50)
        self.assertGreater(self.player.heart_demon, 20)

    def test_meditate(self):
        """悟道提升道心、降低心魔。"""
        self.player.mental_state = 30
        self.player.heart_demon = 30
        mental_gain, heart_decay = self.manager.meditate(months=2)
        self.assertGreater(mental_gain, 0)
        self.assertGreater(heart_decay, 0)

    def test_heart_demon_event_trigger(self):
        """心魔值达到阈值后概率触发事件。"""
        self.player.heart_demon = 80
        self.player.health = 100
        self.player.max_health = 100
        rng = MagicMock()
        rng.random.return_value = 0.0  # 强制触发
        events = self.manager.check_heart_demon_events(rng=rng)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["id"], "inner_demon_attack")
        self.assertLess(self.player.health, 100)

    def test_heart_demon_event_not_triggered(self):
        """心魔值未达阈值时不触发事件。"""
        self.player.heart_demon = 30
        rng = MagicMock()
        rng.random.return_value = 0.0
        events = self.manager.check_heart_demon_events(rng=rng)
        self.assertEqual(len(events), 0)

    def test_tick_monthly(self):
        """每月 tick 应恢复道心、衰减心魔。"""
        self.player.mental_state = 30
        self.player.heart_demon = 30
        mental_gain, heart_decay, events = self.manager.tick_monthly()
        self.assertGreater(mental_gain, 0)
        self.assertLess(heart_decay, 0)  # 返回的是负值

    def test_try_learn_trait_success(self):
        """满足条件时成功领悟特质。"""
        self.player.mental_state = 20
        ok, msg = self.manager.try_learn_trait("ruthless", kill_count=10)
        self.assertTrue(ok)
        self.assertIn("无情", msg)
        self.assertIn("ruthless", self.player.mental_state_traits)

    def test_try_learn_trait_already_learned(self):
        """重复领悟同一特质应失败。"""
        self.player.mental_state = 20
        self.manager.try_learn_trait("ruthless", kill_count=10)
        ok, msg = self.manager.try_learn_trait("ruthless", kill_count=10)
        self.assertFalse(ok)
        self.assertIn("已领悟", msg)

    def test_trait_heart_demon_resistance(self):
        """无情特质应降低心魔增长。"""
        self.player.mental_state = 20
        self.player.heart_demon = 0
        self.manager.try_learn_trait("ruthless", kill_count=10)
        self.manager.on_killing("righteous")
        # 基础增加 8，抗性 0.2，实际增加 6
        self.assertEqual(self.player.heart_demon, 6)


if __name__ == "__main__":
    unittest.main()
