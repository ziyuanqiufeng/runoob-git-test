# -*- coding: utf-8 -*-
"""体验深化五维度端到端平衡回归（M13）。

把 M8~M11 实现的五个体验维度（心魔道心/红尘炼心/百家争鸣/天道反噬/寿元轮回）
纳入统一的 playthrough 压测：
- 全维度动作在新档下可被演练且不抛异常；
- 月度结算零异常、耗时 ≤2s（沿用 M6/M7 门禁）；
- 维度字段存档 round-trip 一致（旧档兼容硬指标）；
- 晚年残魂化身化身后仍 is_alive。

直接复用 tools.balance_sim 的 build_engine / setup_playthrough / run_playthrough，
与本地一键校验（run_checks.py）保持同一驱动逻辑。
"""
import unittest

from tools.balance_sim import (
    build_engine,
    setup_playthrough,
    run_playthrough,
    save_load_roundtrip,
)


class TestE2EPlaythrough(unittest.TestCase):
    def _run(self, difficulty="hell", mode="standard", months=24, seed=20260804):
        engine, player = build_engine()
        summary = setup_playthrough(
            engine, player, difficulty_id=difficulty, mode_id=mode,
            rng_seed=seed, exercise_dimensions=True,
        )
        report = run_playthrough(
            engine, player, months=months,
            difficulty_id=difficulty, mode_id=mode, rng_seed=seed,
            exercise_dimensions=True,
        )
        return engine, player, summary, report

    def test_playthrough_runs_clean(self):
        """全维度动作演练 + 月度结算零异常 + 门禁达标 + 存档 round-trip。"""
        _, _, summary, report = self._run()

        # M6/M7 门禁：月度结算零异常、≤2s、全程无中断
        self.assertEqual(report["monthly_tick_errors"], 0,
                         msg=f"月度结算异常: {report['monthly_tick_error_samples']}")
        self.assertLessEqual(report["max_tick_seconds"], 2.0)
        self.assertEqual(report["months_run"], 24)
        self.assertTrue(report["final"]["alive"])

        # 维度动作确实被演练（非仅静默跳过）
        dims = summary["dimensions"]
        self.assertNotIn("error", str(dims.get("heart_demon", "")),
                         msg=f"心魔劫演练异常: {dims.get('heart_demon')}")
        self.assertNotIn("error", str(dims.get("red_dust", "")),
                         msg=f"红尘演练异常: {dims.get('red_dust')}")
        hs = dims.get("hundred_schools", {})
        self.assertNotIn("error", str(hs), msg=f"百家演练异常: {hs}")
        if isinstance(hs, dict):
            self.assertTrue(hs.get("sect"), "开宗立派未生效")
            self.assertGreaterEqual(hs.get("techniques", 0), 1, "自创功法未生成")
            self.assertTrue(hs.get("self_skill_in_library"),
                            "自创功法未注册为可施展 Skill")
            self.assertIsNotNone(hs.get("life_path"), "生活流派未选择")
        self.assertNotIn("error", str(dims.get("heaven_retribution", "")),
                         msg=f"天道演练异常: {dims.get('heaven_retribution')}")

        # 存档 round-trip 一致
        self.assertTrue(report["save_load_ok"],
                        msg=f"存档 round-trip 不一致: {report['save_load_mismatches']}")

    def test_save_load_roundtrip_explicit(self):
        """维度字段 to_dict → from_dict → to_dict 应完全一致。"""
        engine, player, _, _ = self._run()
        ok, mismatches = save_load_roundtrip(player, engine.item_library)
        self.assertTrue(ok, msg=f"不一致字段: {mismatches}")

    def test_lifespan_remnant_stays_alive(self):
        """晚年残魂化身演练：不抛异常，化身后仍 is_alive。"""
        _, _, _, report = self._run()
        life = report["lifespan_exercise"]
        self.assertNotIn("error", life, msg=f"残魂演练异常: {life}")
        if "become_remnant" in life:
            ok, msg = life["become_remnant"]
            self.assertTrue(ok, msg=f"残魂化身失败: {msg}")
            self.assertTrue(life.get("is_alive_after"), "化身後應仍存活")
            self.assertTrue(life.get("is_remnant"), "應標記為殘魂")

    def test_dimension_status_evolved(self):
        """维度状态在 playthrough 后被正确记录（开宗/自创/流派/天道注视）。"""
        _, _, _, report = self._run()
        ds = report["dimension_status"]
        self.assertTrue(ds["founded_sect"], "维度状态未记录开宗")
        self.assertGreaterEqual(ds["self_techniques"], 1, "维度状态未记录自创功法数")
        self.assertIsNotNone(ds["life_path"], "维度状态未记录生活流派")
        self.assertIsNotNone(ds["mental_state"], "道心值缺失")
        self.assertIsNotNone(ds["heart_demon"], "心魔值缺失")


if __name__ == "__main__":
    unittest.main()
