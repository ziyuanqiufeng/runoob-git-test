# -*- coding: utf-8 -*-
"""M6 集成测试：以最高难度 + 多周目模式跑一份完整游戏，断言无阻断 Bug。

覆盖：
- 家族 / 领地 / 秘境 / 动态世界事件 / 成就 / 难度 / 多周目 全部月度 tick 串联无异常；
- 月度结算耗时 ≤ 2s（新系统注册插座）；
- 地狱难度「大境界突破 → 天道追杀」钩子确定性触发战斗；
- 成就系统随事件解锁；
- 新状态（family/territory/achievements/difficulty/meta）存档可 round-trip；
- 凡人挑战模式（无灵根）同样无阻断。
"""
import os
import sys
import random
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.balance_sim import (
    build_engine,
    setup_playthrough,
    run_playthrough,
)


class TestFullPlaythrough(unittest.TestCase):
    def test_hell_standard_full_run_no_blocking_bug(self):
        """地狱难度 + 正统模式：完整通关驱动，无阻断、无结算异常、月度耗时达标。"""
        engine, player = build_engine()
        setup = setup_playthrough(
            engine, player, difficulty_id="hell", mode_id="standard", rng_seed=7
        )
        # 前置系统应已就绪
        self.assertTrue(setup["family"][0], setup["family"])
        self.assertTrue(setup["territory"][0], setup["territory"])
        self.assertTrue(setup["secret_realm"].get("started"))

        report = run_playthrough(
            engine, player, months=24, difficulty_id="hell",
            mode_id="standard", rng_seed=7,
        )
        # 验收：月度结算 ≤2s、零结算异常、全程无中断
        self.assertLessEqual(report["max_tick_seconds"], 2.0,
                             f"月度结算耗时超标：{report['max_tick_seconds']}")
        self.assertEqual(report["monthly_tick_errors"], 0,
                         f"月度结算异常：{report['monthly_tick_error_samples']}")
        self.assertGreater(report["months_run"], 0)
        # 终态合理
        self.assertTrue(report["final"]["alive"])
        self.assertEqual(report["final"]["realm"], "nascent_soul")

    def test_mortal_challenge_mode_no_blocking_bug(self):
        """凡人挑战模式（无灵根、仅体修）：同样可完整驱动，无阻断。"""
        engine, player = build_engine()
        setup = setup_playthrough(
            engine, player, difficulty_id="hell", mode_id="mortal_challenge", rng_seed=3
        )
        self.assertEqual(player.cultivation_path, "ti")
        self.assertFalse(player.spiritual_roots)

        report = run_playthrough(
            engine, player, months=24, difficulty_id="hell",
            mode_id="mortal_challenge", rng_seed=3,
        )
        self.assertLessEqual(report["max_tick_seconds"], 2.0)
        self.assertEqual(report["monthly_tick_errors"], 0)
        self.assertTrue(report["final"]["alive"])

    def test_heaven_pursuit_triggered_on_major_breakthrough(self):
        """地狱难度大境界突破成功 → 确定性强制触发天道追杀战斗。"""
        engine, player = build_engine()
        # 应用地狱难度
        from game.difficulty_manager import DifficultyManager
        dm = DifficultyManager(config_dir=engine.config_dir)
        dm.apply_to_player(player, "hell")
        # 置于金丹巅峰，准备大境界（金丹→元婴）突破
        player.realm_id = "golden_core_peak"

        # 保证突破成功：monkey-patch random.random 恒为 0（成功率拉满）
        real_random = random.random
        random.random = lambda: 0.0
        try:
            player.qi = engine.world.get_realm("golden_core_peak")["max_qi"] + 1
            engine.current_enemy = None
            engine.breakthrough()
        finally:
            random.random = real_random

        # 突破应成功并触发天道追杀（current_enemy 被设置）
        self.assertEqual(player.realm_id, "nascent_soul")
        self.assertIsNotNone(engine.current_enemy, "天道追杀未触发战斗")
        self.assertEqual(engine.current_enemy.name, "天道追杀者")

    def test_achievement_unlocks_on_events(self):
        """成就系统随事件（击杀累计）自然解锁。"""
        engine, player = build_engine()
        setup_playthrough(engine, player, rng_seed=7)
        am = engine.achievement_manager
        before = len(player.achievements)
        # 累计击杀触发分级击杀成就
        for _ in range(60):
            am.check("kill", enemy_id="x")
        after = len(player.achievements)
        self.assertGreater(after, before, "击杀成就未解锁")
        self.assertIn("a_bronze_kill", player.achievements)

    def test_save_roundtrip_preserves_new_state(self):
        """新状态（家族/领地/成就/难度/模式）存档可 round-trip。

        旧存档（无这些字段）加载应为 None，向后兼容。
        """
        engine, player = build_engine()
        setup_playthrough(
            engine, player, difficulty_id="hell", mode_id="standard", rng_seed=7
        )
        run_playthrough(engine, player, months=12, rng_seed=7)

        data = player.to_dict()
        restored = player.from_dict(data, engine.item_library)

        # 家族 / 领地存在且关键字段保留
        self.assertIsNotNone(restored.family)
        self.assertEqual(restored.family["name"], player.family["name"])
        self.assertIsNotNone(restored.territory)
        self.assertEqual(restored.territory["territory_id"], player.territory["territory_id"])
        # 成就 / 难度 / 模式
        self.assertEqual(len(restored.achievements), len(player.achievements))
        self.assertEqual(restored.difficulty_modifiers, player.difficulty_modifiers)
        self.assertEqual(restored.game_mode, player.game_mode)
        # 领地金库数值保留
        self.assertEqual(restored.territory["treasury"], player.territory["treasury"])

        # 向后兼容：旧存档无 territory 字段时为 None
        legacy = player.to_dict()
        del legacy["territory"]
        legacy_player = player.from_dict(legacy, engine.item_library)
        self.assertIsNone(legacy_player.territory)


if __name__ == "__main__":
    unittest.main()
