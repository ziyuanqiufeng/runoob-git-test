# -*- coding: utf-8 -*-
"""多结局系统测试。

覆盖：结局判定（飞升成功/失败/死亡）、走火入魔/天道降罚分支、has_won 设置、存档持久化。
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


def _make_engine(realm_id="nascent_soul"):
    tmp = tempfile.mkdtemp()
    player = Player(name="测试道友")
    player.realm_id = realm_id
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


class TestJudgeEnding(unittest.TestCase):
    """结局判定逻辑。"""

    def test_ascend_immortal_for_righteous(self):
        e = _make_engine()
        e.player.karma = 10
        e.player.heart_demon = 20
        e.player.heaven_gaze = 20
        ending = e._judge_ending("ascend")
        self.assertEqual(ending["id"], "ascend_immortal")

    def test_ascend_demon_for_evil(self):
        e = _make_engine()
        e.player.karma = -50
        e.player.heart_demon = 20
        e.player.heaven_gaze = 20
        ending = e._judge_ending("ascend")
        self.assertEqual(ending["id"], "ascend_demon")

    def test_heart_demon_fall(self):
        e = _make_engine()
        e.player.heart_demon = 90
        ending = e._judge_ending("ascend_fail")
        self.assertEqual(ending["id"], "heart_demon_fall")

    def test_heaven_punish(self):
        e = _make_engine()
        e.player.heart_demon = 10
        e.player.heaven_gaze = 95
        ending = e._judge_ending("ascend_fail")
        self.assertEqual(ending["id"], "heaven_punish")

    def test_death_red_dust_retire(self):
        e = _make_engine()
        e.player.red_dust_bonds = [{"type": "love", "name": "甲"}, {"type": "friend", "name": "乙"}, {"type": "kin", "name": "丙"}]
        ending = e._judge_ending("death")
        self.assertEqual(ending["id"], "red_dust_retire")

    def test_death_ordinary(self):
        e = _make_engine()
        ending = e._judge_ending("death")
        self.assertEqual(ending["id"], "ordinary_death")


class TestAscension(unittest.TestCase):
    """飞升流程与 has_won 设置。"""

    def test_heart_demon_triggers_fall(self):
        e = _make_engine()
        e.player.heart_demon = 90
        ending = e._attempt_ascension()
        self.assertIsNotNone(ending)
        self.assertEqual(ending["id"], "heart_demon_fall")
        self.assertFalse(e.player.has_won)

    def test_heaven_gaze_triggers_punish(self):
        e = _make_engine()
        e.player.heart_demon = 10
        e.player.heaven_gaze = 95
        ending = e._attempt_ascension()
        self.assertEqual(ending["id"], "heaven_punish")
        self.assertFalse(e.player.has_won)

    def test_success_sets_has_won(self):
        e = _make_engine()
        e.player.karma = 10
        e.player.heart_demon = 10
        e.player.heaven_gaze = 10
        with patch("game.engine.random.random", return_value=0.0):
            ending = e._attempt_ascension()
        self.assertIsNotNone(ending)
        self.assertTrue(e.player.has_won)
        self.assertIsNotNone(e.player.ending_id)

    def test_fail_reincarnate_no_win(self):
        e = _make_engine()
        e.player.heart_demon = 10
        e.player.heaven_gaze = 10
        with patch("game.engine.random.random", return_value=1.0):
            ending = e._attempt_ascension()
        self.assertIsNotNone(ending)
        self.assertEqual(ending["context"], "ascend_fail")
        self.assertFalse(e.player.has_won)


class TestEndingPersist(unittest.TestCase):
    """结局存档持久化。"""

    def test_ending_id_persist(self):
        p = Player(name="测试")
        p.ending_id = "ascend_immortal"
        p.has_won = True
        d = p.to_dict()
        self.assertEqual(d.get("ending_id"), "ascend_immortal")
        restored = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(restored.ending_id, "ascend_immortal")
        self.assertTrue(restored.has_won)

    def test_ending_default_none(self):
        p = Player(name="测试")
        d = p.to_dict()
        d.pop("ending_id", None)
        restored = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertIsNone(restored.ending_id)


if __name__ == "__main__":
    unittest.main()
