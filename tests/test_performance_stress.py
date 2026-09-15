# -*- coding: utf-8 -*-
"""M7 性能压测与全模式验收。

设计目标（对应需求文档 §七「月度结算 ≤2s」与「通关无阻断 Bug」验收项）：
- 以「最大难度 + 全部多周目模式」驱动 balance_sim，断言月度结算耗时 ≤2s、零结算异常、全程无中断；
- 在 setup_playthrough 基础上追加最大负载（大量家族成员 + 铺满领地网格建筑），验证 M0 月度结算
  插座（world_state / family / territory 的 tick_monthly）在重载下单次纯 tick 仍远低于 2s。

本文件是「CI 自动跑 balance_sim」的核心用例：tools/run_checks.py 与 .github/workflows/ci.yml
均会调用同一套驱动逻辑。
"""
import os
import sys
import time
import random
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.balance_sim import (
    build_engine,
    setup_playthrough,
    run_playthrough,
)

# 全难度 × 全模式矩阵：地狱难度压力最大（含大境界突破后的天道追杀战斗）。
DIFFICULTY_MODE_MATRIX = [
    ("hell", "standard"),
    ("hell", "mortal_challenge"),
    ("hell", "seize_rebirth"),
    ("hell", "heaven_cycle"),
    ("hell", "demonic_lone"),
    ("ordinary", "standard"),
    ("peace", "heaven_cycle"),
]

STRESS_MONTHS = 60
TIME_BUDGET_SECONDS = 2.0


def _building_ids(territory_mgr):
    """从领地配置读取全部建筑 id（兼容 dict / list 两种配置形态）。"""
    raw = territory_mgr.config.buildings()
    if isinstance(raw, dict):
        return [b for b in raw.keys() if b != "_comment"]
    if isinstance(raw, list):
        return [b.get("id") for b in raw if isinstance(b, dict) and b.get("id")]
    return []


def _amplify_load(engine, player, family_members=15):
    """在 setup_playthrough 基础上追加负载：招募家族成员并派发任务、铺满领地网格建筑。

    所有调用均包裹异常保护，单条失败不影响整体负载构造（真实游戏内这些操作已被
    can_* 前置校验拦截，此处仅用于放大月度 tick 的工作量）。
    """
    # 1) 招募家族成员并派发任务，放大 family.tick_monthly 的工作量
    fm = engine.family_manager
    for _ in range(family_members):
        try:
            fm.recruit_member(quality="normal")
        except Exception:
            pass
    fam = getattr(player, "family", None)
    if fam:
        tasks = ["cultivate", "manage", "explore", "trade"]
        for i, m in enumerate(fam.get("members", [])):
            try:
                fm.assign_task(m["id"], tasks[i % len(tasks)])
            except Exception:
                pass

    # 2) 铺满领地网格建筑，放大 territory.tick_monthly / settle_monthly 的工作量
    terr = getattr(player, "territory", None)
    tm = engine.territory_manager
    if terr and tm and getattr(tm, "build_mgr", None) is not None:
        rows = terr["grid"]["rows"]
        cols = terr["grid"]["cols"]
        bids = _building_ids(tm)
        idx = 0
        if bids:
            for r in range(rows):
                for c in range(cols):
                    if terr["grid"]["cells"][r][c] is not None:
                        continue
                    bid = bids[idx % len(bids)]
                    idx += 1
                    try:
                        ok, _ = tm.build_mgr.can_place(terr, r, c, bid)
                        if ok:
                            tm.build_mgr.place(terr, r, c, bid)
                    except Exception:
                        pass


class TestPerformanceStress(unittest.TestCase):
    def test_all_modes_settlement_within_budget(self):
        """全模式矩阵：月度结算 ≤2s、零结算异常、全程无中断。"""
        for difficulty_id, mode_id in DIFFICULTY_MODE_MATRIX:
            with self.subTest(difficulty=difficulty_id, mode=mode_id):
                engine, player = build_engine()
                setup_playthrough(
                    engine, player,
                    difficulty_id=difficulty_id, mode_id=mode_id,
                    rng_seed=20260804,
                )
                report = run_playthrough(
                    engine, player, months=STRESS_MONTHS,
                    difficulty_id=difficulty_id, mode_id=mode_id,
                    rng_seed=20260804,
                )
                # M0 月度结算插座纯 tick 耗时
                self.assertLessEqual(
                    report["max_tick_seconds"], TIME_BUDGET_SECONDS,
                    f"[{difficulty_id}/{mode_id}] 月度结算插座耗时超标: "
                    f"{report['max_tick_seconds']:.6f}s",
                )
                # cultivate(1) 整月（含旧系统直接 tick）耗时
                self.assertLessEqual(
                    report["max_monthly_seconds"], TIME_BUDGET_SECONDS,
                    f"[{difficulty_id}/{mode_id}] cultivate(1) 月度耗时超标: "
                    f"{report['max_monthly_seconds']:.6f}s",
                )
                # 新系统月度结算零异常（>0 即视为阻断 Bug）
                self.assertEqual(
                    report["monthly_tick_errors"], 0,
                    f"[{difficulty_id}/{mode_id}] 月度结算异常: "
                    f"{report['monthly_tick_error_samples']}",
                )
                # 角色全程正常存活（无崩溃/无死锁导致提前退出）
                self.assertTrue(
                    report["final"]["alive"],
                    f"[{difficulty_id}/{mode_id}] 角色非正常存活",
                )

    def test_heavy_load_settlement_within_budget(self):
        """最大负载（20 名家族成员 + 铺满建筑）：月度结算仍 ≤2s、零异常。"""
        engine, player = build_engine()
        setup_playthrough(
            engine, player, difficulty_id="hell", mode_id="standard",
            rng_seed=20260804,
        )
        _amplify_load(engine, player, family_members=20)

        report = run_playthrough(
            engine, player, months=STRESS_MONTHS,
            difficulty_id="hell", mode_id="standard", rng_seed=20260804,
        )
        self.assertLessEqual(
            report["max_tick_seconds"], TIME_BUDGET_SECONDS,
            f"重载下月度结算插座耗时超标: {report['max_tick_seconds']:.6f}s",
        )
        self.assertLessEqual(
            report["max_monthly_seconds"], TIME_BUDGET_SECONDS,
            f"重载下 cultivate(1) 月度耗时超标: {report['max_monthly_seconds']:.6f}s",
        )
        self.assertEqual(
            report["monthly_tick_errors"], 0,
            f"重载下月度结算异常: {report['monthly_tick_error_samples']}",
        )

    def test_monthly_tick_socket_scaling_under_load(self):
        """M0 月度结算插座在最大负载下连续 120 次纯 tick，单次峰值仍远低于 2s。"""
        engine, player = build_engine()
        setup_playthrough(
            engine, player, difficulty_id="hell", mode_id="standard",
            rng_seed=20260804,
        )
        _amplify_load(engine, player, family_members=30)

        times = []
        for _ in range(120):
            t0 = time.perf_counter()
            engine._run_registered_monthly_ticks()
            times.append(time.perf_counter() - t0)

        peak = max(times)
        self.assertLessEqual(
            peak, TIME_BUDGET_SECONDS,
            f"重载下纯 tick 峰值耗时超标: {peak:.6f}s（均值 {sum(times)/len(times):.6f}s）",
        )


if __name__ == "__main__":
    unittest.main()
