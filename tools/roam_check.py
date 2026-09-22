"""游历流修为实测工具（与 curve_check.py 闭关流同框架对照）。

策略口径：每月体检 → 血低客栈调养 → 修为攒满即突破 → 否则外出游历
（explore 一次 6 个月，触发事件；事件 qi 已乘境界成长系数）。
用于验证「游历为主」的混合玩法在新曲线下的升级节奏与生存风险。
事件净修为/扣血 = 游历前后 player.qi / health 差值（突破清零不影响本口径）。

用法：
    python tools/roam_check.py              # 默认上限 800 游戏年
    python tools/roam_check.py --max-years 1200
"""
import os
import sys
import argparse
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.balance_sim import build_engine

MILESTONES = {10: "筑基初期", 14: "金丹初期", 18: "元婴期"}


def total_months(engine):
    """当前世界累计月份（从第 1 年 1 月起）。"""
    return (engine.world.year - 1) * 12 + (engine.world.month - 1)


def main():
    parser = argparse.ArgumentParser(description="游历流修为实测")
    parser.add_argument("--max-years", type=int, default=800, help="模拟年数上限")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    random.seed(args.seed)
    engine, player = build_engine()
    player.spiritual_roots = ["fire", "water"]
    player.cultivation_path = "jian"
    stone = engine.item_library.create("spirit_stone")
    if stone:
        for _ in range(2000):
            player.add_item(stone)

    stats = {"roams": 0, "events_qi": 0, "events_hp_loss": 0,
             "breakthroughs": 0, "bt_fails": 0, "rests": 0}
    reached = {}

    while (total_months(engine) < args.max_years * 12
           and len(reached) < len(MILESTONES)):
        # 心魔渡劫抉择自动选第一项（离线无 UI）
        sc = getattr(engine, "pending_heart_demon_scenario", None)
        if sc:
            engine.apply_heart_demon_tribulation_choice(sc["id"], sc["choices"][0]["id"])

        realm = engine.world.get_realm(player.realm_id)
        if player.health < player.max_health * 0.6:
            engine.rest_at_inn(cost=50)          # 1 个月调养
            stats["rests"] += 1
        elif realm and player.qi >= realm["max_qi"] and not engine.world.is_max_realm(player.realm_id):
            before = player.realm_id
            engine.breakthrough()
            if player.realm_id != before:
                stats["breakthroughs"] += 1
            else:
                stats["bt_fails"] += 1
        else:
            qi0, hp0 = player.qi, player.health
            engine.explore()                     # 6 个月游历
            stats["roams"] += 1
            stats["events_qi"] += player.qi - qi0
            stats["events_hp_loss"] += max(0, hp0 - player.health)

        order = engine.world.get_realm(player.realm_id)["order"]
        if order in MILESTONES and order not in reached:
            reached[order] = total_months(engine)

        if not player.is_alive():
            print(f"!! 游历修士于第 {engine.world.year} 年陨落"
                  f"（age={player.age}/{player.max_lifespan} hp={player.health}）")
            break
    else:
        pass

    print("=" * 64)
    print("游历流实测（游历为主 · 火水双灵根 · 剑修 · 事件qi已随境界缩放）")
    print("=" * 64)
    print(f"随机种子：{args.seed}   上限：{args.max_years} 游戏年")
    print(f"游历轮数：{stats['roams']}（每轮 6 月）  调养：{stats['rests']}")
    print(f"突破成功/失败：{stats['breakthroughs']}/{stats['bt_fails']}")
    print(f"游历事件净修为：{stats['events_qi']:+d}   事件扣血合计：-{stats['events_hp_loss']}")
    print("-" * 64)
    print("里程碑到达时间（累计游戏年）：")
    for order in sorted(reached):
        months = reached[order]
        print(f"  {MILESTONES[order]}: 第 {months // 12} 年 {months % 12} 月")
    if not reached:
        print("  （上限内未到达任何里程碑）")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
