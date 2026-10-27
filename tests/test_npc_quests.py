# -*- coding: utf-8 -*-
"""NPC 个人支线（寻物型）测试：确定性生成、状态机、交付奖励、防重复。"""
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
    player = Player(name="委托人")
    engine = GameEngine(
        player,
        World(config_dir="config"),
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


class TestNPCQuest(unittest.TestCase):

    def _npc_id(self, e):
        return next(iter(e.npc_library.npcs))

    def test_deterministic_generation(self):
        e = _make_engine()
        nid = self._npc_id(e)
        q1 = e.npc_quest_manager.get_quest(nid)
        q2 = e.npc_quest_manager.get_quest(nid)
        self.assertEqual(q1["item_id"], q2["item_id"])
        self.assertEqual(q1["count"], q2["count"])
        self.assertGreaterEqual(q1["count"], 1)
        self.assertLessEqual(q1["count"], 3)

    def test_state_machine(self):
        e = _make_engine()
        nid = self._npc_id(e)
        mgr = e.npc_quest_manager
        self.assertEqual(mgr.get_state(nid), "none")
        ok, _ = mgr.accept(nid)
        self.assertTrue(ok)
        self.assertEqual(mgr.get_state(nid), "accepted")
        # 二次接取被拒
        self.assertFalse(mgr.accept(nid)[0])
        # 补齐材料 → ready
        quest = mgr.get_quest(nid)
        item = e.item_library.create(quest["item_id"])
        for _ in range(quest["count"]):
            e.player.add_item(item)
        self.assertEqual(mgr.get_state(nid), "ready")

    def test_turn_in_rewards(self):
        e = _make_engine()
        nid = self._npc_id(e)
        mgr = e.npc_quest_manager
        mgr.accept(nid)
        quest = mgr.get_quest(nid)
        item = e.item_library.create(quest["item_id"])
        for _ in range(quest["count"]):
            e.player.add_item(item)
        favor_before = e.player.npc_relationships.get(nid, 0)
        stones = e.player.count_item("spirit_stone")
        ok, msg = mgr.turn_in(nid)
        self.assertTrue(ok)
        self.assertIn("灵石", msg)
        self.assertEqual(mgr.get_state(nid), "done")
        self.assertEqual(e.player.count_item("spirit_stone"),
                         stones + quest["stone_reward"])
        self.assertEqual(e.player.npc_relationships.get(nid, 0),
                         favor_before + quest["favor_reward"])
        # 记忆有记录
        moments = e.player.get_npc_memory(nid)["moments"]
        self.assertTrue(any("委托" in m for m in moments))

    def test_turn_in_without_items_rejected(self):
        e = _make_engine()
        nid = self._npc_id(e)
        mgr = e.npc_quest_manager
        mgr.accept(nid)
        ok, msg = mgr.turn_in(nid)
        self.assertFalse(ok)
        self.assertIn("材料不足", msg)

    def test_double_turn_in_rejected(self):
        e = _make_engine()
        nid = self._npc_id(e)
        mgr = e.npc_quest_manager
        mgr.accept(nid)
        quest = mgr.get_quest(nid)
        item = e.item_library.create(quest["item_id"])
        for _ in range(quest["count"]):
            e.player.add_item(item)
        mgr.turn_in(nid)
        self.assertFalse(mgr.turn_in(nid)[0])   # 已完成不可重复交付


if __name__ == "__main__":
    unittest.main()
