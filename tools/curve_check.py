"""修为曲线实测工具（M6 配套）。

纯闭关口径（默认难度），从练气一层开始连续闭关+突破，
记录到达各境界里程碑的实际游戏年数与各境界月均收入。
月收入从 notify 日志逐月提取真实增量（不受突破清零干扰）。

用法：
    python tools/curve_check.py            # 默认上限 800 游戏年
    python tools/curve_check.py --max-years 1200
"""
import os
import re
import sys
import argparse
import random

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.balance_sim import build_engine

MILESTONES = {10: "筑基初期", 14: "金丹初期", 18: "元婴期"}
_GAIN_RE = re.compile(r"修为增加 (\d+) 点")


def total_months(engine):
    """当前世界累计月份（从第 1 年 1 月起）。"""
    return (engine.world.year - 1) * 12 + (engine.world.month - 1)


def main():
    parser = argparse.ArgumentParser(description="修为曲线实测（纯闭关口径）")
    parser.add_argument("--max-years", type=int, default=800, help="模拟年数上限")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--verbose", action="store_true", help="打印每次突破明细")
    args = parser.parse_args()

    random.seed(args.seed)
    engine, player = build_engine()
    # 与 balance_report 口径一致：火水双灵根 + 剑修
    player.spiritual_roots = ["fire", "water"]
    player.cultivation_path = "jian"
    # 真实玩家会有游历/任务灵石收入；纯闭关口径给一笔基础盘供客栈调养
    stone = engine.item_library.create("spirit_stone")
    if stone:
        for _ in range(2000):
            player.add_item(stone)

    reached = {}          # order -> 到达时累计月数
    seg_gain = {}         # realm_id -> 该境界段累计真实修为增量（来自闭关日志）
    seg_months = {}       # realm_id -> 该境界段月数
    bt_fail = 0           # 突破失败次数
    bt_ok = 0

    def on_notify(msg):
        m = _GAIN_RE.search(msg or "")
        if m:
            rid = player.realm_id
            seg_gain[rid] = seg_gain.get(rid, 0) + int(m.group(1))

    engine.listeners.append(on_notify)

    cur_realm = player.realm_id
    seg_start = total_months(engine)
    seg_months[cur_realm] = 0

    while total_months(engine) < args.max_years * 12 and len(reached) < len(MILESTONES):
        # 受伤优先调养（渡劫/突破失败反噬会掉血，真玩家不会带残血硬闯）
        if player.health < player.max_health * 0.6:
            engine.rest_at_inn(cost=50)
        else:
            engine.cultivate(1)
            seg_months[player.realm_id] = seg_months.get(player.realm_id, 0) + 1

            # 心魔渡劫抉择自动选第一项（离线无 UI）
            sc = getattr(engine, "pending_heart_demon_scenario", None)
            if sc:
                engine.apply_heart_demon_tribulation_choice(sc["id"], sc["choices"][0]["id"])

            # 修为攒满即尝试突破（失败受罚后继续攒，正是真实游戏体验）
            realm = engine.world.get_realm(player.realm_id)
            if (realm and player.qi >= realm["max_qi"]
                    and not engine.world.is_max_realm(player.realm_id)):
                before = player.realm_id
                engine.breakthrough()
                if player.realm_id != before:
                    bt_ok += 1
                    if args.verbose:
                        months = total_months(engine)
                        print(f"  [突破] {before} -> {player.realm_id}"
                              f" @ 第 {months // 12} 年 {months % 12} 月")
                else:
                    bt_fail += 1

        # 境界切换：记录里程碑
        order = engine.world.get_realm(player.realm_id)["order"]
        if order in MILESTONES and order not in reached:
            reached[order] = total_months(engine)
        if player.realm_id != cur_realm:
            cur_realm = player.realm_id

        if not player.is_alive():
            print(f"!! 修士于第 {engine.world.year} 年寿终/陨落"
                  f"（age={player.age}/{player.max_lifespan} hp={player.health}，未走完曲线）")
            break

    print("=" * 64)
    print("修为曲线实测（纯闭关口径 · 火水双灵根 · 剑修）")
    print("=" * 64)
    print(f"随机种子：{args.seed}   上限：{args.max_years} 游戏年   "
          f"突破成功/失败：{bt_ok}/{bt_fail}")
    print("-" * 64)
    print("各境界月均真实收入（闭关日志口径，含天气/心境/顿悟加成）：")
    for rid, gain in seg_gain.items():
        months = seg_months.get(rid, 0)
        name = engine.world.get_realm(rid)["name"] if rid else "（未知）"
        if months > 0:
            print(f"  {name}: {gain} qi / {months} 月 = {gain / months:.1f} qi/月")
    print("-" * 64)
    print("里程碑到达时间（累计游戏年）：")
    for order in sorted(reached):
        months = reached[order]
        print(f"  {MILESTONES[order]}: 第 {months // 12} 年 {months % 12} 月"
              f"（累计 {months} 月）")
    if not reached:
        print("  （上限内未到达任何里程碑）")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
