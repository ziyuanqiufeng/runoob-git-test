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
        self.assertEqual(
            e.player.count_item("spirit_stone"), stones + 20)   # 1 层 × 20
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
        self.assertEqual(
            e.player.count_item("spirit_stone"), stones + 20 // 2)  # 折半
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
        self.assertEqual(
            e.player.count_item("spirit_stone"), stones + 2 * 20)   # 全额

    def test_best_inherited_on_reincarnation(self):
        e = _make_engine()
        e.player.trial_tower_best = 9
        new_player, _ = e.start_reincarnation([])
        self.assertEqual(new_player.trial_tower_best, 9)


if __name__ == "__main__":
    unittest.main()
