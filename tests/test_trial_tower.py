# -*- coding: utf-8 -*-
"""试炼塔测试：波次推进、三选一补给、通关/失败/撤退结算、纪录跨世。"""
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


def _make_engine():
    tmp = tempfile.mkdtemp()
    player = Player(name="试炼者")
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


class TestTrialTower(unittest.TestCase):

    def _per_floor(self, e):
        return e.trial_tower_manager.config["stone_reward_per_floor"]

    def test_start_run(self):
        e = _make_engine()
        mgr = e.trial_tower_manager
        enemy = mgr.start_run()
        self.assertTrue(mgr.active)
        self.assertEqual(mgr.floor, 1)
        self.assertIsNotNone(enemy)
        # 重复开始被拒
        self.assertIsNone(mgr.start_run())

    def test_floor_advance_and_rewards(self):
        e = _make_engine()
        mgr = e.trial_tower_manager
        mgr.start_run()
        stones = e.player.count_item("spirit_stone")
        with patch("game.trial_tower.random.choice", side_effect=lambda seq: seq[0]), \
             patch("game.trial_tower.random.shuffle", lambda seq: None):
            result = mgr.on_combat_won()
        self.assertEqual(result["floor_cleared"], 1)
        self.assertFalse(result["cleared"])
        self.assertEqual(mgr.floor, 2)
        per_floor = int(mgr.config["stone_reward_per_floor"])
        self.assertEqual(
            e.player.count_item("spirit_stone"), stones + per_floor)
        self.assertEqual(len(mgr.pending_buffs), 3)

    def test_choose_buff_item(self):
        e = _make_engine()
        mgr = e.trial_tower_manager
        mgr.start_run()
        with patch("game.trial_tower.random.choice", side_effect=lambda seq: seq[0]), \
             patch("game.trial_tower.random.shuffle", lambda seq: None):
            mgr.on_combat_won()
        buff = mgr.pending_buffs[0]
        ok, msg = mgr.choose_buff(buff["id"])
        self.assertTrue(ok)
        self.assertTrue(msg)
        self.assertEqual(mgr.pending_buffs, [])
        self.assertFalse(mgr.choose_buff("nonexistent")[0])

    def test_clear_run(self):
        e = _make_engine()
        mgr = e.trial_tower_manager
        mgr.max_floors  # 15
        with patch("game.trial_tower.random.choice", side_effect=lambda seq: seq[0]), \
             patch("game.trial_tower.random.shuffle", lambda seq: None):
            mgr.start_run()
            cleared = False
            for _ in range(15):
                result = mgr.on_combat_won()
                if result["cleared"]:
                    cleared = True
                    break
        self.assertTrue(cleared)
        self.assertFalse(mgr.active)
        self.assertEqual(mgr.best, 15)   # 纪录更新

    def test_lost_settlement(self):
        e = _make_engine()
        mgr = e.trial_tower_manager
        with patch("game.trial_tower.random.choice", side_effect=lambda seq: seq[0]), \
             patch("game.trial_tower.random.shuffle", lambda seq: None):
            mgr.start_run()
            mgr.on_combat_won()     # 通过 1 层 → floor=2
            stones = e.player.count_item("spirit_stone")
            lost = mgr.on_combat_lost()
        self.assertEqual(lost["reached"], 1)
        per_floor = int(self._per_floor(e))
        self.assertEqual(
            e.player.count_item("spirit_stone"), stones + per_floor // 2)
        self.assertFalse(mgr.active)
        self.assertEqual(mgr.best, 1)

    def test_retreat_full_settlement(self):
        e = _make_engine()
        mgr = e.trial_tower_manager
        with patch("game.trial_tower.random.choice", side_effect=lambda seq: seq[0]), \
             patch("game.trial_tower.random.shuffle", lambda seq: None):
            mgr.start_run()
            mgr.on_combat_won()
            mgr.on_combat_won()     # floor=3
            stones = e.player.count_item("spirit_stone")
            result = mgr.retreat()
        self.assertEqual(result["reached"], 2)
        per_floor = int(self._per_floor(e))
        self.assertEqual(
            e.player.count_item("spirit_stone"), stones + 2 * per_floor)

    def test_best_inherited_on_reincarnation(self):
        e = _make_engine()
        e.player.trial_tower_best = 9
        new_player, _ = e.start_reincarnation([])
        self.assertEqual(new_player.trial_tower_best, 9)


if __name__ == "__main__":
    unittest.main()


class TestMetaCollection(unittest.TestCase):
    """跨世图鉴：NPC 访问记录 / 结局记录 / 转世合并。"""

    def test_npc_visit_records_collection(self):
        e = _make_engine()
        npc_id = next(iter(e.npc_library.npcs))
        e.player.record_npc_visit(npc_id, e.world)
        self.assertIn(npc_id, e.player.meta_collection["npcs"])

    def test_collection_inherited(self):
        e = _make_engine()
        e.player.meta_collection = {"endings": ["ascend_immortal"],
                                    "npcs": ["npc_a", "npc_b"]}
        new_player, _ = e.start_reincarnation([])
        self.assertEqual(new_player.meta_collection["endings"],
                         ["ascend_immortal"])
        self.assertEqual(len(new_player.meta_collection["npcs"]), 2)


class TestLantern(unittest.TestCase):
    """灯会：奖励发放（答对数×灵石，全对加心境）与题库完整性。"""

    def test_award_per_correct(self):
        e = _make_engine()
        stones = e.player.count_item("spirit_stone")
        desc = e.award_lantern_reward(2, 3)
        self.assertEqual(e.player.count_item("spirit_stone"), stones + 60)
        self.assertIn("灵石", desc)

    def test_perfect_bonus(self):
        e = _make_engine()
        e.player.mental_state = 50
        e.award_lantern_reward(3, 3)
        self.assertGreater(e.player.mental_state, 50)

    def test_riddles_config_valid(self):
        import json
        path = os.path.join("config", "lantern_riddles.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertGreaterEqual(len(data.get("riddles", [])), 3)
        for r in data["riddles"]:
            self.assertTrue(r.get("question"))
            self.assertEqual(len(r.get("options", [])), 3)
            self.assertIn(r.get("answer"), (0, 1, 2))
