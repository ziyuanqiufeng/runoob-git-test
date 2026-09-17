# -*- coding: utf-8 -*-
"""主线剧情章节测试。

覆盖：章节条件判定（sect/realm/ending）、章节推进、进度查询、存档持久化。
"""
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


def _make_engine(realm_id="qi_refining_1"):
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


class TestMainStory(unittest.TestCase):
    """主线章节推进。"""

    def test_initial_progress_is_ch1(self):
        e = _make_engine()
        p = e.get_main_story_progress()
        self.assertIsNotNone(p)
        self.assertEqual(p[2], 1)  # current = 1
        self.assertEqual(p[3], 5)  # total = 5
        self.assertIn("初入仙途", p[0])

    def test_sect_completes_ch1(self):
        e = _make_engine()
        e.player.sect_id = "qingyun_sect"
        e._check_main_story()
        self.assertEqual(e.player.main_story_step, 1)
        p = e.get_main_story_progress()
        self.assertIn("拜入宗门", p[0])

    def test_realm_completes_ch2(self):
        e = _make_engine("foundation_early")
        e.player.sect_id = "qingyun_sect"
        e._check_main_story()  # 完成第一章
        e._check_main_story()  # 检查第二章（realm order 10）
        self.assertEqual(e.player.main_story_step, 2)

    def test_ending_completes_last_chapter(self):
        e = _make_engine("nascent_soul")
        e.player.main_story_step = 4
        e.player.ending_id = "ascend_immortal"
        e._check_main_story()
        self.assertEqual(e.player.main_story_step, 5)
        self.assertIsNone(e.get_main_story_progress())

    def test_condition_not_met_no_advance(self):
        e = _make_engine()  # 练气一层，无宗门
        e._check_main_story()
        self.assertEqual(e.player.main_story_step, 0)


class TestStoryCondition(unittest.TestCase):
    """章节条件判定。"""

    def test_sect_condition(self):
        e = _make_engine()
        self.assertFalse(e._meet_story_condition({"type": "sect"}))
        e.player.sect_id = "s"
        self.assertTrue(e._meet_story_condition({"type": "sect"}))

    def test_realm_condition(self):
        e = _make_engine("foundation_early")
        self.assertTrue(e._meet_story_condition({"type": "realm", "order": 10}))
        self.assertFalse(e._meet_story_condition({"type": "realm", "order": 14}))

    def test_ending_condition(self):
        e = _make_engine()
        self.assertFalse(e._meet_story_condition({"type": "ending"}))
        e.player.ending_id = "ascend_immortal"
        self.assertTrue(e._meet_story_condition({"type": "ending"}))


class TestStoryHint(unittest.TestCase):
    """主线目标引导：条件翻译成玩家可读提示。"""

    def test_ch1_hint_sect(self):
        e = _make_engine()
        self.assertEqual(e.get_main_story_hint(), "加入一方宗门")

    def test_ch2_hint_realm_name(self):
        e = _make_engine("qi_refining_1")
        e.player.main_story_step = 1  # 第二章：realm order 10
        hint = e.get_main_story_hint()
        self.assertIn("修为达到", hint)

    def test_last_chapter_hint_ending(self):
        e = _make_engine("nascent_soul")
        e.player.main_story_step = 4
        self.assertEqual(e.get_main_story_hint(), "达成任意结局")

    def test_hint_none_when_all_done(self):
        e = _make_engine()
        e.player.main_story_step = 5
        self.assertIsNone(e.get_main_story_hint())


class TestStoryPersist(unittest.TestCase):
    """主线进度持久化。"""

    def test_persist_roundtrip(self):
        p = Player(name="测试")
        p.main_story_step = 3
        d = p.to_dict()
        self.assertEqual(d.get("main_story_step"), 3)
        restored = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(restored.main_story_step, 3)

    def test_persist_default_zero(self):
        p = Player(name="测试")
        d = p.to_dict()
        d.pop("main_story_step", None)
        restored = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(restored.main_story_step, 0)


if __name__ == "__main__":
    unittest.main()
