"""离线平衡模拟与通关驱动工具（M6）。

用途：
1. 作为命令行工具：构建完整引擎、驱动月度结算、测量耗时、汇总各系统产出/消耗，
   输出平衡报告（月度结算是否 ≤2s、数值是否在合理区间）。
2. 作为集成测试的底层驱动：`run_playthrough` 可被 test_integration_playthrough.py 直接调用，
   以「最高难度 + 多周目模式」跑一份完整游戏，断言无阻断 Bug、存档可 round-trip。

设计原则：
- 不依赖 UI：所有战斗/事件均按「胜利/自动推进」处理，仅验证系统不抛异常、不中断。
- 通过引擎既有的 `cultivate(1)` 月度循环驱动全部已注册系统的 `tick_monthly`（受 feature_flags 控制）。
- 监听 `notify` 捕获「月度结算异常」告警，作为「阻断 Bug」的判定信号之一。
"""
import os
import sys
import time
import json
import random
import argparse

# 允许脚本直接 import 项目模块（项目根目录即 tools/ 的上一级）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from game.engine import GameEngine
from game.player import Player
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.world import World
from game.events import EventPool
from game.difficulty_manager import DifficultyManager
from game.meta_manager import MetaManager


def build_engine(config_dir="config"):
    """构建一份完整引擎（含 M0~M5 全部管理器）与玩家。"""
    item_lib = ItemLibrary(config_dir=config_dir)
    enemy_lib = EnemyLibrary(config_dir=config_dir)
    skill_lib = SkillLibrary(config_dir=config_dir)
    npc_lib = NPCLibrary(config_dir=config_dir)
    quest_lib = QuestLibrary(config_dir=config_dir)
    player = Player(name="平衡模拟修士")
    world = World(config_dir=config_dir)
    event_pool = EventPool(config_dir=config_dir)
    engine = GameEngine(
        player, world, event_pool,
        item_lib, enemy_lib, skill_lib, npc_lib, quest_lib,
        save_manager=None, config_dir=config_dir,
    )
    return engine, player


def _give_stones(player, count, item_lib):
    stone = item_lib.create("spirit_stone")
    if stone is None:
        return
    for _ in range(count):
        player.add_item(stone)


def setup_playthrough(engine, player, difficulty_id=None, mode_id=None,
                      rng_seed=None, exercise_dimensions=False):
    """构造一份可玩到家族/领地/秘境/突破的完整初始状态。

    返回 setup 摘要字典。

    exercise_dimensions：是否演练体验深化五维度（心魔劫/红尘/百家/天道/残魂）的
    专属玩家动作。默认关——保持对集成/性能共享 harness 的零侵入；仅 M13 E2E 测试
    与 run_checks 显式开启。
    """
    if rng_seed is not None:
        random.seed(rng_seed)

    item_lib = engine.item_library
    dm = DifficultyManager(config_dir=engine.config_dir)
    mm = MetaManager(config_dir=engine.config_dir)

    # 应用难度（默认最高难度：地狱）
    if difficulty_id is None:
        difficulty_id = "hell"
    if dm.get_modifiers(difficulty_id):
        dm.apply_to_player(player, difficulty_id)

    # 应用多周目模式（默认正统求道 standard，始终可用）
    if mode_id is None:
        mode_id = "standard"
    if mm.config.get_mode(mode_id):
        mm.apply_to_player(player, mode_id)

    # 凡人挑战模式无灵根，仅限体修/符修；其余模式给灵根+剑修
    if getattr(player, "spiritual_roots", None) is None or not player.spiritual_roots:
        if mode_id == "mortal_challenge":
            player.spiritual_roots = []
            player.cultivation_path = "ti"
        else:
            player.spiritual_roots = ["fire", "water"]
            player.cultivation_path = "jian"

    # 起始境界：金丹初期（order 14）——满足家族(金丹)与秘境门槛，
    # 但领地需元婴期，故稍后在突破演练后再抬升。
    player.realm_id = "golden_core_early"

    # 给予资源：灵石 + 声望（满足创建家族门槛）
    _give_stones(player, 60000, item_lib)
    if not hasattr(player, "reputation") or not player.reputation:
        player.reputation = {}
    player.reputation["righteous"] = 300  # 累计 ≥200 即可

    summary = {"difficulty": difficulty_id, "mode": mode_id, "realm": player.realm_id}

    # 创建家族
    fam_ok, fam_msg = engine.family_manager.create(
        "问天盟", "道心不昧，逆天而行", "xiao_yao"
    )
    summary["family"] = (fam_ok, fam_msg)

    # 解锁并跑一局秘境（自动推进至胜利）
    engine.secret_realm_manager.unlock("fire_realm")
    sr = run_secret_realm_once(engine, player, realm_id="fire_realm", difficulty_id="normal")
    summary["secret_realm"] = sr

    # 突破演练：抬到金丹巅峰，尝试大境界突破（地狱难度下可能触发天道追杀）
    player.realm_id = "golden_core_peak"
    summary["breakthroughs_preview"] = _exercise_breakthroughs(engine, player, max_attempts=3)

    # 占据领地需元婴期：无论突破是否成功，强制抬升以保证后续演练
    player.realm_id = "nascent_soul"
    terr_ok, terr_msg = engine.territory_manager.claim("qingyun_lingmai")
    summary["territory"] = (terr_ok, terr_msg)
    if terr_ok:
        # 放置净正的产灵石建筑组合（聚灵塔 25/-8 + 坊市 15/-7 = 净 +25/月），
        # 用于观察金库累积；再补一座守卫塔验证防御协同。
        engine.territory_manager.build_mgr.place(player.territory, 0, 0, "spirit_gathering_tower")
        engine.territory_manager.build_mgr.place(player.territory, 0, 1, "market_pavilion")
        engine.territory_manager.build_mgr.place(player.territory, 1, 0, "guard_tower")

    # 体验深化五维度动作演练（M13 平衡回归）：心魔劫/红尘/百家/天道
    # 仅当显式开启时执行，避免污染集成/性能共享 harness 的玩家终态。
    if exercise_dimensions:
        summary["dimensions"] = setup_dimension_systems(
            engine, player, item_lib, rng_seed=rng_seed
        )
    else:
        summary["dimensions"] = {}

    return summary


def run_secret_realm_once(engine, player, realm_id="fire_realm", difficulty_id="normal", max_steps=60):
    """驱动一局 Roguelike 秘境至结束（战斗一律记为胜利）。返回摘要。"""
    srm = engine.secret_realm_manager
    ok, msg = srm.start_run(realm_id, difficulty_id)
    if not ok:
        return {"started": False, "msg": msg}
    steps = 0
    while srm.is_run_active() and steps < max_steps:
        avail = srm.get_available_node_ids()
        if not avail:
            break
        nid = avail[0]
        res = srm.enter_node(nid)
        kind = res.get("kind")
        if kind in ("battle", "elite", "boss"):
            srm.on_battle_cleared(nid, victory=True)
        steps += 1
    summary = srm.end_run(victory=True)
    return {"started": True, "steps": steps, "end": summary}


def _exercise_breakthroughs(engine, player, max_attempts=3):
    """演练若干次突破，覆盖「大境界突破 + 地狱难度天道追杀」钩子。

    返回列表：每项含 {before, after, success, combat_started}。
    避免修改全局随机：直接 set 高修为后调用引擎突破，成功与否取决于概率；
    若地狱难度大境界突破成功，钩子会触发 start_combat（current_enemy 被设置）。
    """
    results = []
    for _ in range(max_attempts):
        realm = engine.world.get_realm(player.realm_id)
        if realm is None:
            break
        next_id = engine.world.next_realm(player.realm_id)
        if next_id is None:
            break
        player.qi = realm["max_qi"] + 1
        before = player.realm_id
        engine.current_enemy = None
        engine.breakthrough()
        after = player.realm_id
        advanced = (after != before)
        combat_started = engine.current_enemy is not None
        results.append({
            "before": before, "after": after,
            "success": advanced, "combat_started": combat_started,
        })
        if not advanced:
            # 突破失败则结束演练（避免无意义重试）
            break
    return results


# ==================== 体验深化五维度演练（M13） ====================
# 这些维度系统（心魔道心/红尘炼心/百家争鸣/天道反噬/寿元轮回）在 M8~M11
# 以「M0 月度插座 + feature_flags 门控」加法式接入。平衡模拟需显式演练它们的
# 专属玩家动作，才能确保跨系统不抛异常、存档可 round-trip。
DIM_FIELDS = [
    "red_dust_active", "red_dust_bonds", "red_dust_months", "red_dust_pending_qingjie",
    "founded_sect", "self_created_techniques", "life_path", "life_path_proficiency",
    "heaven_watch", "heaven_watch_level", "spirit_vein_depletion",
    "is_remnant", "remnant_type", "remnant_months", "past_life_relics",
    "personality_tags", "tribulation_effects",
]


def setup_dimension_systems(engine, player, item_lib, rng_seed=None):
    """演练五个体验维度的专属玩家动作。

    返回各维度演练摘要；单个维度失败不应阻断其余（异常被捕获并记入 summary），
    目的是在平衡压测中尽早暴露跨系统崩溃。
    """
    if rng_seed is not None:
        random.seed(rng_seed)
    summary = {}

    # ① 心魔劫：抬高心魔值 → 大境界突破 → 若触发则应用首个抉择
    try:
        player.heart_demon = 70
        realm = engine.world.get_realm(player.realm_id)
        nxt = engine.world.next_realm(player.realm_id)
        if realm and nxt:
            player.qi = realm["max_qi"] + 1
            engine.current_enemy = None
            engine.breakthrough()
        sc = getattr(engine, "pending_heart_demon_scenario", None)
        if sc:
            cid = sc["choices"][0]["id"]
            engine.apply_heart_demon_tribulation_choice(sc["id"], cid)
            summary["heart_demon"] = "applied"
        else:
            summary["heart_demon"] = "not_triggered"
    except Exception as e:
        summary["heart_demon"] = f"error:{e}"

    # ② 红尘炼心：入世 → 历红尘 → （若有情劫）抉择 → 出尘沉淀心境
    try:
        engine.enter_red_dust()
        engine.red_dust_experience()
        engine.red_dust_experience()
        if getattr(player, "red_dust_pending_qingjie", None):
            q = player.red_dust_pending_qingjie
            engine.apply_qingjie_choice(q["choices"][0]["id"])
        engine.exit_red_dust()
        summary["red_dust"] = {
            "bonds": len(getattr(player, "red_dust_bonds", []) or []),
            "months": getattr(player, "red_dust_months", 0),
        }
    except Exception as e:
        summary["red_dust"] = f"error:{e}"

    # ③ 百家争鸣：开宗 → （月度累积气运）→ 推演自创功法 → 择生活流派 → 道韵灌顶
    try:
        engine.found_sect("问道书院")
        for _ in range(6):
            engine._tick_hundred_schools()
        engine.create_technique("无名诀", "剑修", "attack")
        engine.choose_life_path("alchemy")
        engine.spend_qi_yun_for_enlightenment()  # 气运不足会失败，记录即可
        summary["hundred_schools"] = {
            "sect": bool(getattr(player, "founded_sect", None)),
            "techniques": len(getattr(player, "self_created_techniques", []) or []),
            "self_skill_in_library": any(
                sid.startswith("self_tech_") for sid in engine.skill_library.skills
            ),
            "life_path": getattr(player, "life_path", None),
        }
    except Exception as e:
        summary["hundred_schools"] = f"error:{e}"

    # ④ 天道反噬：游历累积天道注视，可能触发无妄之灾/杀人夺宝
    try:
        for _ in range(3):
            engine.explore()
        summary["heaven_retribution"] = {
            "gaze_level": engine.heaven_retribution_manager.get_gaze_level(),
        }
    except Exception as e:
        summary["heaven_retribution"] = f"error:{e}"

    return summary


def exercise_lifespan_events(engine, player, item_lib):
    """演练维度⑤ 晚年路径：残魂夺舍/器灵化身 + 月度重塑，验证化身后仍 is_alive。"""
    res = {}
    try:
        min_order = engine.lifespan_manager.config.get_remnant().get("min_realm_order", 18)
        order = getattr(player, "REALM_ORDER", {}).get(player.realm_id, 0)
        if order < min_order:
            # 抬升到满足残魂门槛的境界，仅用于演练
            for rid, o in getattr(player, "REALM_ORDER", {}).items():
                if o >= min_order:
                    player.realm_id = rid
                    break
        ok, msg = engine.become_remnant_soul("treasure")
        res["become_remnant"] = (ok, msg)
        if ok:
            for _ in range(3):
                engine._tick_lifespan()
            res["is_alive_after"] = player.is_alive()
            res["is_remnant"] = getattr(player, "is_remnant", False)
    except Exception as e:
        res["error"] = str(e)
    return res


def save_load_roundtrip(player, item_lib):
    """维度字段存档 round-trip 校验：to_dict → from_dict → to_dict 应一致。"""
    d1 = player.to_dict()
    reloaded = Player.from_dict(d1, item_lib)
    d2 = reloaded.to_dict()
    mismatches = []
    for k in DIM_FIELDS:
        a = d1.get(k)
        b = d2.get(k)
        if json.dumps(a, sort_keys=True, default=str) != json.dumps(b, sort_keys=True, default=str):
            mismatches.append(k)
    return (len(mismatches) == 0, mismatches)


def run_playthrough(engine, player, months=24, difficulty_id=None, mode_id=None,
                    rng_seed=None, capture_errors=True, exercise_dimensions=False):
    """驱动一份完整游戏 months 个月，返回平衡报告字典。

    报告包含：
    - per_month_seconds：每月 cultivate(1) 耗时列表
    - max_monthly_seconds / avg_monthly_seconds
    - tick_run_seconds：单独测量 _run_registered_monthly_ticks 的耗时（新系统月度结算）
    - monthly_tick_errors：捕获到的「月度结算异常」告警数（>0 即视为阻断 Bug）
    - final：关键终态（qi/realm/stones/成就数/家族等级/领地金库）
    """
    if rng_seed is not None:
        random.seed(rng_seed)

    errors = []
    combat_starts = []

    def _listener(msg):
        if isinstance(msg, str):
            if "月度结算异常" in msg:
                errors.append(msg)
            if "__COMBAT_START__" in msg:
                combat_starts.append(msg)

    if capture_errors:
        engine.add_listener(_listener)

    # 突破演练：覆盖「大境界突破 + 地狱难度天道追杀」钩子
    breakthroughs = _exercise_breakthroughs(engine, player)

    per_month = []
    for _ in range(months):
        if not player.is_alive():
            break
        t0 = time.perf_counter()
        engine.cultivate(1)
        t1 = time.perf_counter()
        per_month.append(t1 - t0)

    # 单独测量新系统月度结算耗时（纯 tick，无修为/天气等旧逻辑干扰）
    tick_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        engine._run_registered_monthly_ticks()
        t1 = time.perf_counter()
        tick_times.append(t1 - t0)

    final = {
        "qi": player.qi,
        "realm": player.realm_id,
        "alive": player.is_alive(),
        "spirit_stones": player.count_item("spirit_stone"),
        "achievements": len(getattr(player, "achievements", []) or []),
        "family_level": (
            (getattr(player, "family", None) or {}).get("level")
        ),
        "territory_treasury": (
            (getattr(player, "territory", None) or {}).get("treasury", 0)
        ),
        "realm_coins": getattr(player, "realm_coins", 0),
        "difficulty_modifiers": getattr(player, "difficulty_modifiers", None),
        "game_mode": getattr(player, "game_mode", None),
    }

    # 体验深化：晚年残魂化身演练 + 维度字段存档 round-trip 校验（M13）
    # 仅当显式开启时执行，避免污染集成/性能共享 harness 的玩家终态；
    # 关闭时给出中性默认值（集成/性能测试不校验这些字段）。
    if exercise_dimensions:
        lifespan_ex = exercise_lifespan_events(engine, player, engine.item_library)
        sl_ok, sl_mismatch = save_load_roundtrip(player, engine.item_library)
    else:
        lifespan_ex = {}
        sl_ok, sl_mismatch = True, []

    dimension_status = {
        "red_dust_active": getattr(player, "red_dust_active", False),
        "founded_sect": bool(getattr(player, "founded_sect", None)),
        "self_techniques": len(getattr(player, "self_created_techniques", []) or []),
        "life_path": getattr(player, "life_path", None),
        "life_path_proficiency": getattr(player, "life_path_proficiency", 0),
        "heaven_gaze_level": engine.heaven_retribution_manager.get_gaze_level(),
        "is_remnant": getattr(player, "is_remnant", False),
        "mental_state": getattr(player, "mental_state", None),
        "heart_demon": getattr(player, "heart_demon", None),
    }

    return {
        "months_run": len(per_month),
        "per_month_seconds": per_month,
        "max_monthly_seconds": max(per_month) if per_month else 0.0,
        "avg_monthly_seconds": (sum(per_month) / len(per_month)) if per_month else 0.0,
        "tick_run_seconds": tick_times,
        "max_tick_seconds": max(tick_times) if tick_times else 0.0,
        "monthly_tick_errors": len(errors),
        "monthly_tick_error_samples": errors[:3],
        "combat_starts": len(combat_starts),
        "breakthroughs": breakthroughs,
        "final": final,
        "dimension_status": dimension_status,
        "lifespan_exercise": lifespan_ex,
        "save_load_ok": sl_ok,
        "save_load_mismatches": sl_mismatch,
    }


def main():
    parser = argparse.ArgumentParser(description="修仙模拟器平衡模拟（M6）")
    parser.add_argument("--months", type=int, default=24, help="模拟月数")
    parser.add_argument("--difficulty", default="hell", help="难度 id（太平/寻常/凶险/地狱）")
    parser.add_argument("--mode", default="standard", help="多周目模式 id")
    parser.add_argument("--seed", type=int, default=1234, help="随机种子")
    parser.add_argument("--config-dir", default="config", help="配置目录")
    args = parser.parse_args()

    engine, player = build_engine(config_dir=args.config_dir)
    setup = setup_playthrough(
        engine, player, difficulty_id=args.difficulty, mode_id=args.mode,
        rng_seed=args.seed, exercise_dimensions=True,
    )
    report = run_playthrough(
        engine, player, months=args.months, difficulty_id=args.difficulty,
        mode_id=args.mode, rng_seed=args.seed, exercise_dimensions=True,
    )

    print("=" * 60)
    print("修仙模拟器 · 平衡模拟报告（M6）")
    print("=" * 60)
    print(f"难度/模式：{setup['difficulty']} / {setup['mode']}")
    print(f"家族创建：{setup['family']}")
    print(f"领地占据：{setup['territory']}")
    print(f"秘境：{setup['secret_realm']}")
    print("-" * 60)
    print(f"运行月数：{report['months_run']}")
    print(f"单月 cultivate 耗时：max={report['max_monthly_seconds']:.4f}s "
          f"avg={report['avg_monthly_seconds']:.4f}s")
    print(f"新系统月度结算(_run_registered_monthly_ticks) 耗时：max={report['max_tick_seconds']:.6f}s")
    print(f"月度结算异常次数：{report['monthly_tick_errors']}")
    print("-" * 60)
    print("终态：")
    for k, v in report["final"].items():
        print(f"  {k}: {v}")
    print("-" * 60)
    print("体验深化维度状态：")
    for k, v in report["dimension_status"].items():
        print(f"  {k}: {v}")
    print(f"晚年残魂化身演练：{report['lifespan_exercise']}")
    print(f"存档 round-trip：{'通过 ✅' if report['save_load_ok'] else '失败 ❌'} "
          f"{report['save_load_mismatches']}")
    print("=" * 60)

    # 验收判定
    ok = (
        report["max_tick_seconds"] <= 2.0
        and report["monthly_tick_errors"] == 0
        and report["months_run"] == args.months
        and report["save_load_ok"]
    )
    print(f"验收：{'通过 ✅' if ok else '未通过 ❌'} "
          f"（月度结算≤2s 且零结算异常 且 全程无中断 且 存档 round-trip 一致）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
