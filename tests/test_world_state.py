# -*- coding: utf-8 -*-
"""F-04 WorldStateManager 单元测试。

验证全局世界状态的读写钳制、事件链效果应用/回滚、灵气潮汐推进与倍率、存档持久化。
"""
import unittest

from game.player import Player
from game.world import World
from game.world_state import WorldStateManager, DEFAULT_STATE


class TestWorldStateManager(unittest.TestCase):
    def setUp(self):
        self.player = Player(name="t")
        self.world = World(config_dir="config")
        self.notifies = []
        self.wsm = WorldStateManager(
            self.player, config_dir="config", notify_callback=self.notifies.append
        )

    def test_defaults_initialized(self):
        for k in DEFAULT_STATE:
            self.assertIn(k, self.wsm.state)
        self.assertEqual(self.wsm.get("dark_qi"), 0.0)

    def test_bounds_clamp(self):
        self.wsm.set("dark_qi", 500)
        self.assertEqual(self.wsm.get("dark_qi"), 100.0)
        self.wsm.set("dark_qi", -50)
        self.assertEqual(self.wsm.get("dark_qi"), 0.0)

    def test_apply_effects_percent_as_points(self):
        # "+30%" 理解为 +30 个百分点；"-10" 为绝对 -10
        applied = self.wsm.apply_effects({"dark_qi": "+30%", "npc_mood": -10})
        self.assertEqual(self.wsm.get("dark_qi"), 30.0)
        self.assertEqual(self.wsm.get("npc_mood"), 40.0)
        self.wsm.revert_effects(applied)
        self.assertEqual(self.wsm.get("dark_qi"), 0.0)
        self.assertEqual(self.wsm.get("npc_mood"), 50.0)

    def test_apply_effects_absolute(self):
        applied = self.wsm.apply_global_effect("safety", 8)
        self.assertEqual(self.wsm.get("safety"), 108.0)
        self.wsm.revert_effects([applied])
        self.assertEqual(self.wsm.get("safety"), 100.0)

    def test_tick_tides_advances_phase_and_moves_lingqi(self):
        phase0 = self.wsm.state["tide_phase"]
        self.wsm.tick_tides()
        self.assertEqual(self.wsm.state["tide_phase"], (phase0 + 1) % 24)
        # 灵气浓度被潮汐牵引，偏离初始基准
        self.assertNotEqual(self.wsm.get("lingqi"), 100.0)

    def test_multipliers_in_range(self):
        tm = self.wsm.tide_multiplier()
        self.assertGreaterEqual(tm, 0.8)
        self.assertLessEqual(tm, 1.2)
        cm = self.wsm.cultivation_multiplier()
        self.assertGreaterEqual(cm, 0.5)
        self.assertLessEqual(cm, 2.0)

    def test_summary_keys(self):
        s = self.wsm.summary()
        for k in ("lingqi", "safety", "price_index", "npc_mood", "dark_qi",
                  "tide_phase", "tide_multiplier"):
            self.assertIn(k, s)

    def test_state_persisted_on_player(self):
        self.wsm.apply_global_effect("dark_qi", 30)
        self.assertEqual(self.player.world_state["dark_qi"], 30.0)


if __name__ == "__main__":
    unittest.main()
