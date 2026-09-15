# -*- coding: utf-8 -*-
"""M7 本地一键检查：验证整套扩展的可运行性与性能门禁。

用法：
    python tools/run_checks.py            # 完整：pytest + 全模式 balance_sim 压测
    python tools/run_checks.py --quick    # 精简：pytest + 1 个高压力场景（CI 用）
    python tools/run_checks.py --no-tests # 仅跑 balance_sim 压测，跳过 pytest

行为：
- 自动检测 coverage 是否可用；可用则附带「新模块」覆盖率报告，不可用则优雅降级为纯 pytest
  （不强制依赖 coverage/pytest-cov，避免污染运行环境）。
- 全模式矩阵复用 test_performance_stress 的同一驱动逻辑，保证本地与 CI 一致。
- 性能门禁（硬指标）：月度结算（纯 tick 插座 + cultivate 整月）≤2s 且零结算异常，
  否则以非零退出码结束——这是 CI 自动跑 balance_sim 的核心断言。
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.balance_sim import build_engine, setup_playthrough, run_playthrough

# 与 test_performance_stress.py 同源的矩阵（地狱难度含天道追杀，压力最大）
MODE_MATRIX = [
    ("hell", "standard"),
    ("hell", "mortal_challenge"),
    ("hell", "seize_rebirth"),
    ("hell", "heaven_cycle"),
    ("hell", "demonic_lone"),
    ("ordinary", "standard"),
]
TIME_BUDGET = 2.0

# 仅统计「新增/扩展」模块，避免被旧的 47 个弹窗稀释覆盖率数字
NEW_MODULES = [
    "game.territory_manager",
    "game.achievement",
    "game.difficulty_manager",
    "game.meta_manager",
    "game.world_state",
    "game.family",
    "game.realm_card",
    "game.realm_node",
    "game.realm_reward",
    "game.world_event",
    "game.mental_state",
    "game.red_dust_manager",
    "game.hundred_schools_manager",
    "game.heaven_retribution_manager",
    "game.lifespan_manager",
    "game.reincarnation_manager",
    "game.reincarnation",
]


def _have_coverage():
    try:
        import coverage  # noqa: F401
        return True
    except Exception:
        return False


def run_pytest(quick):
    print("\n=== 1) pytest ===")
    if _have_coverage():
        cmd = [
            sys.executable, "-m", "coverage", "run",
            "--source=" + ",".join(NEW_MODULES),
            "-m", "pytest", "tests/", "-q",
        ]
    else:
        cmd = [sys.executable, "-m", "pytest", "tests/", "-q"]
        if quick:
            cmd.append("-x")  # 精简模式遇首错即停，加速反馈

    t0 = time.perf_counter()
    rc = subprocess.call(cmd, cwd=PROJECT_ROOT)
    dt = time.perf_counter() - t0
    print(f"pytest 退出码={rc}, 耗时 {dt:.1f}s")

    if _have_coverage():
        print("\n--- 新模块覆盖率 ---")
        subprocess.call([sys.executable, "-m", "coverage", "report", "-m"],
                        cwd=PROJECT_ROOT)
    elif not quick:
        print("(提示: 未检测到 coverage，跳过覆盖率统计；可在 CI 中 `pip install coverage` 开启)")
    return rc


def run_balance_sweep(quick):
    print("\n=== 2) balance_sim 全模式压测 ===")
    matrix = [("hell", "standard")] if quick else MODE_MATRIX
    months = 30 if quick else 60
    all_ok = True
    worst_tick = 0.0
    worst_monthly = 0.0
    worst_case = "-"

    for difficulty_id, mode_id in matrix:
        engine, player = build_engine()
        setup_playthrough(
            engine, player, difficulty_id=difficulty_id,
            mode_id=mode_id, rng_seed=20260804, exercise_dimensions=True,
        )
        report = run_playthrough(
            engine, player, months=months,
            difficulty_id=difficulty_id, mode_id=mode_id,
            rng_seed=20260804, exercise_dimensions=True,
        )
        tick = report["max_tick_seconds"]
        monthly = report["max_monthly_seconds"]
        errs = report["monthly_tick_errors"]
        ok = (tick <= TIME_BUDGET and monthly <= TIME_BUDGET
              and errs == 0 and report["final"]["alive"])
        all_ok = all_ok and ok
        if tick > worst_tick:
            worst_tick, worst_monthly, worst_case = tick, monthly, f"{difficulty_id}/{mode_id}"
        flag = "OK " if ok else "FAIL"
        print(f"  [{flag}] {difficulty_id:8s}/{mode_id:14s} "
              f"tick={tick:.6f}s monthly={monthly:.6f}s errors={errs} "
              f"alive={report['final']['alive']}")

    print(f"\n峰值: {worst_case} tick={worst_tick:.6f}s monthly={worst_monthly:.6f}s "
          f"(门禁 ≤{TIME_BUDGET}s)")
    return 0 if all_ok else 1


def main():
    ap = argparse.ArgumentParser(description="M7 本地一键检查")
    ap.add_argument("--quick", action="store_true",
                    help="精简模式（CI 用，仅 1 个高压场景 + 遇错即停）")
    ap.add_argument("--no-tests", action="store_true",
                    help="仅跑 balance_sim 压测，跳过 pytest")
    args = ap.parse_args()

    print(">>> 问道长生 · M7 验证与交付加固 <<<")
    rc = 0
    if not args.no_tests:
        rc = run_pytest(args.quick)
    rc2 = run_balance_sweep(args.quick)

    if rc != 0:
        print("\n结果: pytest 失败（见上）")
        sys.exit(rc)
    if rc2 != 0:
        print("\n结果: 性能/阻断门禁失败（月度结算 > 2s 或存在结算异常）")
        sys.exit(rc2)
    print("\n结果: 全部通过 ✅（月度结算 ≤2s、零阻断、零结算异常）")
    sys.exit(0)


if __name__ == "__main__":
    main()
