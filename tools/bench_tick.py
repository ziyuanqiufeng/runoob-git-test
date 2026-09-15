# -*- coding: utf-8 -*-
"""月度结算与存档性能基准。

模拟推进 120 个游戏月（10 年）与 50 次自动存档，量化：
- 单月结算平均耗时（52 个 Manager 的月度 tick）
- 单次自动存档平均耗时（原子写 + 滚动备份）

用法：python tools/bench_tick.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager

MONTHS = 120
SAVES = 50


def build_engine(tmp):
    player = Player(name="基准道友")
    player.realm_id = "qi_refining_1"
    return GameEngine(
        player, World(config_dir="config"), EventPool(config_dir="config"),
        ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
        SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
        QuestLibrary(config_dir="config"),
        save_manager=SaveManager(save_path=os.path.join(tmp, "bench_save.json"),
                                 save_dir=os.path.join(tmp, "bench_saves")),
    )


def main():
    import tempfile
    tmp = tempfile.mkdtemp()
    engine = build_engine(tmp)
    engine.notify = lambda *_: None  # 基准不受日志影响

    print(f"模拟推进 {MONTHS} 个月（10 游戏年）...")
    t0 = time.perf_counter()
    for _ in range(MONTHS):
        engine.world.advance(1)
        engine.player.add_age_months(1)
        engine._check_sect_daily_reset()
        engine._run_registered_monthly_ticks()
    tick_ms = (time.perf_counter() - t0) * 1000 / MONTHS

    print(f"自动存档 {SAVES} 次（原子写 + 备份）...")
    t0 = time.perf_counter()
    for _ in range(SAVES):
        engine.save_manager.save(engine.player, engine.world)
    save_ms = (time.perf_counter() - t0) * 1000 / SAVES

    print(f"事件抽取 3000 次...")
    t0 = time.perf_counter()
    loc = engine.get_current_location()
    for _ in range(3000):
        engine.event_pool.draw("explore", location=loc)
    draw_ms = (time.perf_counter() - t0) * 1000 / 3000

    print("-" * 48)
    print(f"单月结算：    {tick_ms:.2f} ms/月（10 游戏年共 {tick_ms * 12 / 1000:.1f} 秒）")
    print(f"单次存档：    {save_ms:.2f} ms")
    print(f"单次事件抽取：{draw_ms * 1000:.1f} µs")


if __name__ == "__main__":
    main()
