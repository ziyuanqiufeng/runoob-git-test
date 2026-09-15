# -*- coding: utf-8 -*-
"""维度③ 百家争鸣 数值平衡审计（M17）。

复用 tools.balance_sim.build_engine 构建无头引擎，对维度③三支柱做受控模拟，
量化关键月度指标，输出报告。本工具只读模拟、不改游戏逻辑，仅为平衡调优提供数据。

运行：
    python tools/balance_audit.py [--months 120] [--json audit_summary.json]
"""
import os
import sys
import json
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.balance_sim import build_engine


def _fund(player, engine, n=500):
    """给玩家灵石（found_sect / create_technique 需要）。"""
    stone = engine.item_library.create("spirit_stone")
    if stone is None:
        return
    for _ in range(n):
        player.add_item(stone)


def audit_sect(months):
    """支柱① 立派传道·气运反哺：立派后模拟 months 月，采集气运/弟子/灵石反哺轨迹。"""
    engine, player = build_engine()
    player.realm_id = "golden_core_early"
    _fund(player, engine, 500)
    ok, msg = engine.found_sect("审计宗门")
    if not ok:
        return {"error": msg}
    traj = []
    qi_cap_month = None
    for m in range(months):
        rewards = engine.hundred_schools_manager.tick_monthly()
        sect = player.founded_sect
        qi = sect["qi_yun"]
        traj.append({
            "month": m + 1,
            "qi_yun": round(qi, 2),
            "disciples": sect["disciples"],
            "feedback_stones": rewards["spirit_stone"],
        })
        if qi_cap_month is None and qi >= 99.9:
            qi_cap_month = m + 1
    steady = traj[-1]["feedback_stones"] if traj else 0
    return {
        "qi_cap_month": qi_cap_month,
        "final_disciples": traj[-1]["disciples"] if traj else 0,
        "steady_feedback": steady,
        "traj": traj,
    }


def audit_techniques(months):
    """支柱② 自创功法·道心增长：自创满门功法后量化道心月度增长。"""
    engine, player = build_engine()
    player.realm_id = "golden_core_early"
    _fund(player, engine, 500)
    for i in range(5):
        engine.create_technique("诀%d" % i, "剑修", "attack")
    start = player.mental_state
    for m in range(months):
        engine.hundred_schools_manager.tick_monthly()
    end = player.mental_state
    per_month = (end - start) / months if months else 0
    cap_from_50 = (100 - 50) / per_month if per_month > 0 else None
    return {
        "techniques": 5,
        "dao_heart_start": start,
        "dao_heart_end": end,
        "dao_heart_per_month": round(per_month, 4),
        "months_50_to_100": round(cap_from_50, 1) if cap_from_50 else None,
    }


def audit_lifepath(path, months):
    """支柱③ 生活流派产出：某流派 months 月产出统计。"""
    engine, player = build_engine()
    player.realm_id = "golden_core_early"
    engine.choose_life_path(path)
    counts = {}
    for m in range(1, months + 1):
        # 还原真实周期：age_months 在游戏中由 cultivate 循环递增，
        # 否则 0 % every == 0 恒成立会高估产出。
        player.age_months = m
        rewards = engine.hundred_schools_manager.tick_monthly()
        for iid in rewards["produced_items"]:
            counts[iid] = counts.get(iid, 0) + 1
    return {"path": path, "months": months, "produced": counts}


def audit_battle_buff():
    """战斗增益（自动部署等效）强度对比。"""
    engine, player = build_engine()
    cfg = engine.hundred_schools_manager.config.get_life_path().get("produce", {})
    rows = []
    for pk, prod in cfg.items():
        bb = prod.get("battle_buff")
        rows.append({
            "path": pk,
            "item": prod.get("item_id"),
            "name": bb.get("name") if bb else None,
            "buff": bb,
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description="维度③ 数值平衡审计（M17）")
    parser.add_argument("--months", type=int, default=120)
    parser.add_argument("--json", type=str, default=None,
                        help="可选：把 sect 轨迹与汇总导出到此 JSON 路径")
    args = parser.parse_args()

    print("=" * 64)
    print("维度③ 百家争鸣 数值平衡审计（M17）")
    print("=" * 64)

    sect = audit_sect(args.months)
    print("\n【支柱① 立派传道·气运反哺】")
    if "error" in sect:
        print("  错误:", sect["error"])
    else:
        print(f"  气运封顶(≈100)月 : {sect['qi_cap_month']}")
        print(f"  最终弟子数       : {sect['final_disciples']}")
        print(f"  稳态灵石反哺/月  : {sect['steady_feedback']}")
        print("  轨迹(前 12 月):")
        for r in sect["traj"][:12]:
            print(f"    月{r['month']:>3}  气运 {r['qi_yun']:>6}  弟子 {r['disciples']:>4}  反哺 {r['feedback_stones']:>3}")

    tech = audit_techniques(args.months)
    print("\n【支柱② 自创功法·道心增长】")
    print(f"  自创门数         : {tech['techniques']}")
    print(f"  道心 起→终       : {tech['dao_heart_start']} → {tech['dao_heart_end']}")
    print(f"  道心增长/月      : {tech['dao_heart_per_month']}")
    print(f"  仅自创功法 50→100: {tech['months_50_to_100']} 月")

    print("\n【支柱③ 生活流派产出（%d 月总产量）】" % args.months)
    for path in ("alchemy", "artifact", "talisman", "array"):
        lp = audit_lifepath(path, args.months)
        print(f"  {path:>8}: {lp['produced']}")

    bb = audit_battle_buff()
    print("\n【战斗增益（自动部署等效·每场）】")
    for r in bb:
        if not r["buff"]:
            print(f"  {r['path']:>8} ({r['item']}): 无战斗增益")
        else:
            ea = r["buff"].get("enemy_attack_down")
            pa = r["buff"].get("player_attack_up")
            sh = r["buff"].get("player_shield")
            print(f"  {r['path']:>8} ({r['item']}) {r['name']}: "
                  f"敌攻-{ea['ratio'] if ea else 0} 己攻+{pa['ratio'] if pa else 0} 护盾{sh or 0}")

    if args.json:
        out = {"sect": sect, "techniques": tech}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n汇总已导出: {args.json}")

    print("\n审计完成。")


if __name__ == "__main__":
    main()
