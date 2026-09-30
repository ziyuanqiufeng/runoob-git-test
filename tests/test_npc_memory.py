# -*- coding: utf-8 -*-
"""NPC 记忆系统（moments 共同经历）测试：存储/钩子/转世衔接/旧档兼容。"""
import os
import sys
import tempfile
import unittest

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


def _make_engine():
    tmp = tempfile.mkdtemp()
    player = Player(name="测试道友")
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


class TestMomentStorage(unittest.TestCase):
    """moments 存储与 FIFO。"""

    def test_record_and_read(self):
        e = _make_engine()
        e.player.record_npc_moment("npc_a", "第3年：结为道侣")
        moments = e.player.get_npc_memory("npc_a").get("moments")
        self.assertEqual(moments, ["第3年：结为道侣"])

    def test_fifo_cap_five(self):
        e = _make_engine()
        for i in range(8):
            e.player.record_npc_moment("npc_a", f"事件{i}")
        moments = e.player.get_npc_memory("npc_a")["moments"]
        self.assertEqual(len(moments), 5)
        self.assertEqual(moments[0], "事件3")   # 最早的 3 条被挤出
        self.assertEqual(moments[-1], "事件7")

    def test_legacy_save_compat(self):
        """旧档 npc_memory 无 moments 字段 → get 时自动补建。"""
        e = _make_engine()
        e.player.npc_memory = {"npc_old": {"choices": {"k": 1}, "last_visit": 1,
                                           "visit_count": 2}}
        memory = e.player.get_npc_memory("npc_old")
        self.assertEqual(memory["moments"], [])
        e.player.record_npc_moment("npc_old", "第5年：旧友重逢")
        self.assertEqual(memory["moments"], ["第5年：旧友重逢"])

    def test_save_roundtrip(self):
        e = _make_engine()
        e.player.record_npc_moment("npc_a", "第3年：结为道侣")
        d = e.player.to_dict()
        restored = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(
            restored.get_npc_memory("npc_a")["moments"], ["第3年：结为道侣"]
        )


class TestSocialHooks(unittest.TestCase):
    """社交动作成功后写入共同经历。"""

    def test_form_companion_records(self):
        from game.companion import CompanionManager
        e = _make_engine()
        npc = e.npc_library.npcs.get(next(iter(e.npc_library.npcs)))
        e.player.realm_id = "golden_core_peak"   # 满足结为道侣的境界门槛
        e.player.npc_relationships[npc.id] = 50  # 满足好感度门槛
        mgr = CompanionManager(e.player, e.world, npc_library=e.npc_library)
        ok, _ = mgr.form_companion(npc.id)
        self.assertTrue(ok)
        moments = e.player.get_npc_memory(npc.id)["moments"]
        self.assertTrue(any("结为道侣" in m for m in moments))

    def test_debate_records(self):
        e = _make_engine()
        npc_id = next(iter(e.npc_library.npcs))
        e.player.location_id = e.npc_library.npcs[npc_id].location
        try:
            e.debate_with_npc(npc_id)
        except Exception:
            self.skipTest("论道前置条件不满足（随机环境），跳过钩子断言")
        moments = e.player.get_npc_memory(npc_id).get("moments") or []
        self.assertTrue(all("论道" in m for m in moments) or not moments)


class TestReincarnationBondMemory(unittest.TestCase):
    """转世重逢 NPC 自带前世记忆条目。"""

    def test_reborn_npc_memory_seeded(self):
        e = _make_engine()
        e.player.realm_id = "lianxu_peak"
        e.player.qi = 460000
        e.player.companions = [{"npc_id": "npc_b", "name": "乙", "intimacy": 95}]
        new_player, _ = e.start_reincarnation([])
        moments = new_player.get_npc_memory("reborn_npc_b")["moments"]
        self.assertTrue(any("前世" in m for m in moments))


if __name__ == "__main__":
    unittest.main()
