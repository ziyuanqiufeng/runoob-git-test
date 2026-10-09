# -*- coding: utf-8 -*-
"""轮回全链路集成测试：结缘 → 冲终局 → 天门试炼 → 飞升 → 转世 → 新周目运行。

把终局境界链 / 天门试炼 / 轮回叙事层 / NPC 记忆 / 主动事件的衔接
固化为一条确定性回归链。
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

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
from game.companion import CompanionManager


def _make_engine():
    tmp = tempfile.mkdtemp()
    player = Player(name="测试道友")
    player.realm_id = "golden_core_peak"
    player.npc_relationships.update({
        "npc_b": 60,   # 结道侣用（id 会在测试里替换为库中真实 NPC）
    })
    world = World(config_dir="config")
    engine = GameEngine(
        player,
        world,
        EventPool(config_dir="config"),
        ItemLibrary(config_dir="config"),
        EnemyLibrary(config_dir="config"),
        SkillLibrary(config_dir="config"),
        NPCLibrary(config_dir="config"),
        QuestLibrary(config_dir="config"),
        save_manager=SaveManager(
            save_path=os.path.join(tmp, "save.json"),
            save_dir=os.path.join(tmp, "saves"),
        ),
    )
    return engine


class TestFullReincarnationCycle(unittest.TestCase):
    """完整轮回周期（单链确定性）。"""

    def test_full_cycle(self):
        e = _make_engine()

        # ---- 阶段 A：攒羁绊（结道侣 + 双修写记忆）----
        npc_id = next(iter(e.npc_library.npcs))   # 库中真实 NPC
        e.player.npc_relationships[npc_id] = 60
        mgr = CompanionManager(e.player, e.world, npc_library=e.npc_library)
        ok, _ = mgr.form_companion(npc_id)
        self.assertTrue(ok, "阶段A：结为道侣应成功")
        ok, _ = mgr.dual_cultivate(npc_id)
        self.assertTrue(ok, "阶段A：双修应成功")
        self.assertTrue(
            any("结为道侣" in m for m in e.player.get_npc_memory(npc_id)["moments"]))
        self.assertTrue(
            any("双修" in m for m in e.player.get_npc_memory(npc_id)["moments"]))

        # ---- 阶段 B：冲终局（天门试炼先败后成）----
        e.player.realm_id = "lianxu_peak"
        e.player.qi = 460000
        e.player.karma = 10
        e.player.heart_demon = 10
        e.player.heaven_gaze = 10
        e.player.mental_state = 90
        e.player.max_lifespan = e.player.age + 3000
        hp0 = e.player.health

        # 第一次：兵解失败
        with patch("game.engine.random.random", return_value=1.0):
            ret = e._attempt_ascension()
        self.assertIsNone(ret, "第一次试炼失败不触发结局")
        self.assertLess(e.player.qi, 460000)
        self.assertLess(e.player.health, hp0)
        self.assertGreater(e.player.heaven_gaze, 10)

        # 第二次：飞升成功
        e.player.qi = 460000
        with patch("game.engine.random.random", return_value=0.0):
            ending = e._attempt_ascension()
        self.assertIsNotNone(ending)
        self.assertTrue(e.player.has_won)
        self.assertIsNotNone(e.player.ending_id)

        # ---- 阶段 C：轮回转世 ----
        old_karma = e.player.karma
        new_player, summary = e.start_reincarnation([])
        self.assertEqual(new_player.reincarnation_count, 1)
        self.assertEqual(new_player.karma, old_karma, "业力应跨世继承")
        self.assertIsNotNone(new_player.past_bond)
        self.assertEqual(new_player.past_bond["npc_id"], npc_id)
        self.assertEqual(new_player.past_bond["bond_type"], "dao_lv")

        # ---- 模拟 main_window 重绑（npc_library 同实例复用）----
        library = e.npc_library
        engine2 = GameEngine(
            new_player,
            World(config_dir="config"),
            EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"),
            EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"),
            library,
            QuestLibrary(config_dir="config"),
        )
        reborn_id = f"reborn_{npc_id}"
        reborn = engine2.npc_library.npcs.get(reborn_id)
        self.assertIsNotNone(reborn, "转世 NPC 应注入新周目 NPC 库")
        self.assertTrue(getattr(reborn, "past_life_bond", None))
        # 新周目记忆：前世羁绊条目已预写
        self.assertTrue(any(
            "前世" in m for m in new_player.get_npc_memory(reborn_id)["moments"]))

        # ---- 阶段 D：新周目月度运行（主动事件插座零异常）----
        for _ in range(3):
            engine2._run_registered_monthly_ticks()
        self.assertTrue(new_player.is_alive())
        # 新周目冷却状态为全新（social_event_state 空 dict）
        self.assertEqual(new_player.social_event_state, {})

        # ---- 阶段 E：二周目再结缘（记忆跨世延续）----
        new_player.npc_relationships[reborn_id] = 60
        new_player.realm_id = "golden_core_peak"
        mgr2 = CompanionManager(new_player, engine2.world, npc_library=library)
        ok, _ = mgr2.form_companion(reborn_id)
        self.assertTrue(ok, "二周目与转世道侣再结缘应成功")
        moments = new_player.get_npc_memory(reborn_id)["moments"]
        self.assertTrue(any("前世" in m for m in moments))
        self.assertTrue(any("结为道侣" in m for m in moments))
        self.assertGreaterEqual(len(moments), 2)


if __name__ == "__main__":
    unittest.main()
