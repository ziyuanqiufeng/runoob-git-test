# -*- coding: utf-8 -*-
"""轮回叙事层测试：前世羁绊收集、转世 NPC 注入、宿慧叙事、存档 round-trip。"""
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
from game.npc import NPCLibrary, NPC
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from game.reincarnation_manager import ReincarnationManager


def _make_engine():
    tmp = tempfile.mkdtemp()
    player = Player(name="测试道友")
    player.realm_id = "lianxu_peak"
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


class TestPastBondSelection(unittest.TestCase):
    """前世羁绊选择：道侣优先，其次好感最高 NPC，全无为 None。"""

    def _manager(self, player):
        return ReincarnationManager(player)

    def test_dao_lv_takes_priority(self):
        e = _make_engine()
        e.player.companions = [
            {"npc_id": "npc_a", "name": "甲", "intimacy": 60},
            {"npc_id": "npc_b", "name": "乙", "intimacy": 95},
        ]
        e.player.npc_relationships = {"npc_c": 100}
        bond = self._manager(e.player)._select_past_bond()
        self.assertEqual(bond["npc_id"], "npc_b")
        self.assertEqual(bond["bond_type"], "dao_lv")
        self.assertEqual(bond["name"], "乙")

    def test_friend_fallback(self):
        e = _make_engine()
        e.player.npc_relationships = {"npc_x": 30, "npc_y": 80}
        bond = self._manager(e.player)._select_past_bond()
        self.assertEqual(bond["npc_id"], "npc_y")
        self.assertEqual(bond["bond_type"], "friend")

    def test_none_when_no_bonds(self):
        e = _make_engine()
        self.assertIsNone(self._manager(e.player)._select_past_bond())

    def test_negative_only_relationships_ignored(self):
        """恩怨（负好感）不算羁绊。"""
        e = _make_engine()
        e.player.npc_relationships = {"npc_z": -50}
        self.assertIsNone(self._manager(e.player)._select_past_bond())


class TestBondPersist(unittest.TestCase):
    """past_bond 写入新 Player 并随存档 round-trip。"""

    def test_created_player_carries_bond(self):
        e = _make_engine()
        e.player.companions = [{"npc_id": "npc_b", "name": "乙", "intimacy": 95}]
        mgr = ReincarnationManager(e.player)
        new_data = mgr.apply_inheritance([])
        new_player = mgr.create_new_player(new_data, Player)
        self.assertIsNotNone(new_player.past_bond)
        self.assertEqual(new_player.past_bond["name"], "乙")

    def test_save_roundtrip(self):
        e = _make_engine()
        e.player.past_bond = {
            "npc_id": "npc_b", "name": "乙", "bond_type": "dao_lv", "intimacy": 95,
        }
        d = e.player.to_dict()
        restored = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(restored.past_bond["name"], "乙")
        self.assertEqual(restored.past_bond["bond_type"], "dao_lv")

    def test_old_save_without_bond(self):
        """旧存档无 past_bond 字段 → None（兼容）。"""
        e = _make_engine()
        d = e.player.to_dict()
        d.pop("past_bond", None)
        restored = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertIsNone(restored.past_bond)


class TestReincarnationFlow(unittest.TestCase):
    """start_reincarnation：转世 NPC 注入 + 宿慧叙事 + 年表。"""

    def test_bond_npc_injected(self):
        e = _make_engine()
        e.player.companions = [{"npc_id": "npc_b", "name": "乙", "intimacy": 95}]
        notify_log = []
        e.add_listener(notify_log.append)
        new_player, summary = e.start_reincarnation([])
        # 转世 NPC 注入
        reborn = e.npc_library.npcs.get("reborn_npc_b")
        self.assertIsNotNone(reborn)
        self.assertEqual(reborn.name, "乙")
        self.assertTrue(getattr(reborn, "past_life_bond", None))
        # 宿慧叙事
        self.assertTrue(any("宿慧" in m for m in notify_log))
        self.assertTrue(any("乙" in m for m in notify_log))
        # summary 带羁绊与灵根标记
        self.assertEqual(summary["past_bond"]["name"], "乙")
        self.assertIn("retain_roots", summary)

    def test_no_bond_still_narrates(self):
        e = _make_engine()
        notify_log = []
        e.add_listener(notify_log.append)
        new_player, summary = e.start_reincarnation([])
        self.assertIsNone(summary["past_bond"])
        self.assertTrue(any("宿慧" in m for m in notify_log))
        self.assertEqual(
            [n for n in e.npc_library.npcs if n.startswith("reborn_")], [])

    def test_new_player_engine_rebind(self):
        """模拟主窗口流程：start_reincarnation → _init_game(player=new)
        → npc_library 复用同实例，转世 NPC 仍在库中。"""
        e = _make_engine()
        e.player.companions = [{"npc_id": "npc_b", "name": "乙", "intimacy": 95}]
        new_player, _ = e.start_reincarnation([])
        # 模拟 main_window._init_game(player=new_player)：npc_library 传引用
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
        self.assertIsNotNone(engine2.npc_library.npcs.get("reborn_npc_b"))
        self.assertIs(engine2.player, new_player)


if __name__ == "__main__":
    unittest.main()
