# -*- coding: utf-8 -*-
"""渐进解锁 + 新手引导任务链测试。

覆盖：
- engine.is_action_unlocked / get_unlock_hint：各境界下的按钮解锁判定
- engine._advance_tutorial / get_tutorial_progress：引导步骤推进与进度查询
- player.tutorial_step：存档字段持久化
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
    """构造一个临时目录下的引擎，玩家境界可指定。"""
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


class TestActionUnlock(unittest.TestCase):
    """渐进解锁：按钮境界门槛判定。"""

    def test_default_unlocked_when_no_entry(self):
        """未配置门槛的按钮（如闭关）默认解锁。"""
        e = _make_engine("qi_refining_1")
        self.assertTrue(e.is_action_unlocked("cultivate"))
        self.assertTrue(e.is_action_unlocked("inventory"))
        self.assertTrue(e.is_action_unlocked("save"))

    def test_order_gate_locked_at_low_realm(self):
        """练气一层时，练气五层门槛的按钮应未解锁。"""
        e = _make_engine("qi_refining_1")
        self.assertFalse(e.is_action_unlocked("residence"))
        self.assertFalse(e.is_action_unlocked("auction_house"))
        self.assertEqual(e.get_unlock_hint("residence"), "练气五层解锁")

    def test_order_gate_unlocked_at_realm(self):
        """练气五层时，练气五层门槛的按钮应解锁。"""
        e = _make_engine("qi_refining_5")
        self.assertTrue(e.is_action_unlocked("residence"))
        self.assertTrue(e.is_action_unlocked("mind_method"))

    def test_foundation_gate(self):
        """筑基期解锁秘境/图鉴/成就/心魔。"""
        e_low = _make_engine("qi_refining_9")
        self.assertFalse(e_low.is_action_unlocked("secret_realm"))
        e_found = _make_engine("foundation_early")
        self.assertTrue(e_found.is_action_unlocked("secret_realm"))
        self.assertTrue(e_found.is_action_unlocked("heart_demon"))
        self.assertFalse(e_found.is_action_unlocked("family"))

    def test_golden_core_gate(self):
        """金丹期解锁家族/红尘/百家，但未到元婴不能开领地。"""
        e = _make_engine("golden_core_early")
        self.assertTrue(e.is_action_unlocked("family"))
        self.assertTrue(e.is_action_unlocked("red_dust"))
        self.assertTrue(e.is_action_unlocked("hundred_schools"))
        self.assertFalse(e.is_action_unlocked("territory"))

    def test_nascent_soul_gate(self):
        """元婴期解锁领地/天道反噬/寿元。"""
        e = _make_engine("nascent_soul")
        self.assertTrue(e.is_action_unlocked("territory"))
        self.assertTrue(e.is_action_unlocked("heaven_retribution"))
        self.assertTrue(e.is_action_unlocked("lifespan"))

    def test_feature_gate(self):
        """craft_life_treasure 用 feature 门槛：未解锁 life_treasure 前未解锁。"""
        e = _make_engine("golden_core_early")
        self.assertFalse(e.is_action_unlocked("craft_life_treasure"))
        e.player.unlock_feature("life_treasure")
        self.assertTrue(e.is_action_unlocked("craft_life_treasure"))


class TestTutorialChain(unittest.TestCase):
    """新手引导任务链：步骤推进与进度查询。"""

    def test_initial_progress(self):
        e = _make_engine("qi_refining_1")
        p = e.get_tutorial_progress()
        self.assertIsNotNone(p)
        self.assertEqual(p[0], 1)
        self.assertEqual(p[1], 5)
        self.assertEqual(p[2], "初入仙途")

    def test_advance_in_order(self):
        e = _make_engine("qi_refining_1")
        e._advance_tutorial("cultivate")
        self.assertEqual(e.player.tutorial_step, 1)
        p = e.get_tutorial_progress()
        self.assertEqual(p[2], "灵气满溢")

    def test_wrong_trigger_does_not_advance(self):
        e = _make_engine("qi_refining_1")
        e._advance_tutorial("explore")  # 第一步应是 cultivate
        self.assertEqual(e.player.tutorial_step, 0)

    def test_full_chain(self):
        e = _make_engine("qi_refining_1")
        for trigger in ("cultivate", "breakthrough", "market", "npc", "explore"):
            e._advance_tutorial(trigger)
        self.assertEqual(e.player.tutorial_step, 5)
        self.assertIsNone(e.get_tutorial_progress())

    def test_completed_no_side_effect(self):
        e = _make_engine("qi_refining_1")
        for trigger in ("cultivate", "breakthrough", "market", "npc", "explore"):
            e._advance_tutorial(trigger)
        e._advance_tutorial("cultivate")  # 已完成，不应再变
        self.assertEqual(e.player.tutorial_step, 5)


class TestTutorialPersist(unittest.TestCase):
    """引导进度存档持久化。"""

    def test_to_dict_contains_tutorial_step(self):
        p = Player(name="测试")
        p.tutorial_step = 3
        d = p.to_dict()
        self.assertEqual(d.get("tutorial_step"), 3)

    def test_from_dict_reads_tutorial_step(self):
        p = Player(name="测试")
        d = p.to_dict()
        d["tutorial_step"] = 4
        restored = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(restored.tutorial_step, 4)

    def test_from_dict_default_zero(self):
        p = Player(name="测试")
        d = p.to_dict()
        d.pop("tutorial_step", None)
        restored = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(restored.tutorial_step, 0)


if __name__ == "__main__":
    unittest.main()
