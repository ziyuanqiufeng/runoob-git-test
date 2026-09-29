# -*- coding: utf-8 -*-
"""天门试炼（炼虚圆满冲击飞升）三阶段判定测试。"""
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
    """炼虚圆满玩家（无心魔/天道污染）。"""
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
    p = engine.player
    p.heart_demon = 10
    p.heaven_gaze = 10
    p.mental_state = 90
    p.karma = 10
    p.qi = 460000
    p.spirit_stones = 10000
    p.health = p.max_health
    p.max_lifespan = p.age + 3000
    return engine


class TestGateRedLines(unittest.TestCase):
    """阶段一/二红线：直接对应坏结局。"""

    def test_heart_demon_80_falls(self):
        e = _make_engine()
        e.player.heart_demon = 80
        ending = e._attempt_ascension()
        self.assertIsNotNone(ending)
        self.assertEqual(ending["context"], "ascend_fail")
        self.assertFalse(e.player.has_won)

    def test_heaven_gaze_90_punished(self):
        e = _make_engine()
        e.player.heaven_gaze = 90
        ending = e._attempt_ascension()
        self.assertIsNotNone(ending)
        self.assertEqual(ending["context"], "ascend_fail")

    def test_wound_below_50_survives_line(self):
        """心魔 49 不触红线（只吃减益），stub 成功时仍飞升。"""
        e = _make_engine()
        e.player.heart_demon = 49
        with patch("game.engine.random.random", return_value=0.0):
            ending = e._attempt_ascension()
        self.assertIsNotNone(ending)
        self.assertTrue(e.player.has_won)


class TestGateLeap(unittest.TestCase):
    """阶段三·天门一跃：资源豪赌 + 概率。"""

    def test_success_ascend(self):
        e = _make_engine()
        with patch("game.engine.random.random", return_value=0.0):
            ending = e._attempt_ascension()
        self.assertIsNotNone(ending)
        self.assertTrue(e.player.has_won)
        self.assertIsNotNone(e.player.ending_id)

    def test_failure_survivable(self):
        e = _make_engine()
        with patch("game.engine.random.random", return_value=1.0):
            ending = e._attempt_ascension()
        self.assertIsNone(ending)          # 不触发结局
        self.assertTrue(e.player.is_alive())
        self.assertEqual(e.player.realm_id, "lianxu_peak")
        self.assertEqual(e.player.spirit_stones, 5000)   # 燃烧一半灵石
        self.assertLess(e.player.qi, 460000)             # 修为折损七成
        self.assertGreater(e.player.heaven_gaze, 10)     # 天道注视加深

    def test_pill_consumed_and_bonus(self):
        """飞升丹被消耗且 +30% 生效：同一随机数 0.6，无丹失败 / 有丹成功。

        实际 rate（道心 90、心魔 10、天道 10）：
        无丹 = 0.5 - 0.05 - 0.04 + 0.10 = 0.51；有丹 = 0.51 + 0.30 = 0.81。
        """
        base = _make_engine()
        with patch("game.engine.random.random", return_value=0.6):
            ret = base._attempt_ascension()
        self.assertIsNone(ret)                          # 无丹：0.6 > 0.51 失败（可再战，不结局）
        self.assertFalse(base.player.has_won)

        e = _make_engine()
        pill = e.item_library.create("ascension_pill")
        e.player.add_item(pill)
        with patch("game.engine.random.random", return_value=0.6):
            ending = e._attempt_ascension()
        self.assertIsNotNone(ending)                    # 有丹：0.6 < 0.81 成功
        self.assertTrue(e.player.has_won)
        self.assertEqual(
            sum(1 for i in e.player.inventory if i.id == "ascension_pill"), 0,
            "飞升丹应被消耗")

    def test_stone_burn_ratio(self):
        e = _make_engine()
        e.player.spirit_stones = 999
        with patch("game.engine.random.random", return_value=1.0):
            e._attempt_ascension()
        self.assertEqual(e.player.spirit_stones, 500)    # 999 - int(999*0.5=499) = 500

    def test_config_override(self):
        """config/ascension.json 的参数被引擎读取（红线改 10 即 10 生效）。"""
        import json, os
        cfg_path = os.path.join("config", "ascension.json")
        bak = open(cfg_path, encoding="utf-8").read()
        try:
            cfg = json.load(open(cfg_path, encoding="utf-8"))
            cfg["heart_demon_fail"] = 5
            json.dump(cfg, open(cfg_path, "w", encoding="utf-8"), ensure_ascii=False)
            e = _make_engine()
            e.player.heart_demon = 5
            ending = e._attempt_ascension()
            self.assertIsNotNone(ending)
            self.assertEqual(ending["context"], "ascend_fail")
        finally:
            open(cfg_path, "w", encoding="utf-8").write(bak)


if __name__ == "__main__":
    unittest.main()
