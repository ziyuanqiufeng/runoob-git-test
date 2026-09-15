# -*- coding: utf-8 -*-
"""捏脸一期（AI 提示词捏脸）测试。"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

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
from game import face_traits as ft
from ui.face_customize_dialog import FaceCustomizeDialog


class TestTraitsConfig(unittest.TestCase):
    """特征表加载与解析。"""

    def test_load_valid(self):
        cfg = ft.load_traits_config("config")
        self.assertIsNotNone(cfg)
        self.assertEqual(len(cfg["dimensions"]), 5)
        for dim in cfg["dimensions"]:
            self.assertTrue(dim.get("options"))

    def test_resolve_all_selected(self):
        traits = {"face_shape": "sharp", "eyes": "fierce", "aura": "cold",
                  "hair_style": "topknot", "outfit": "white"}
        prompts = ft.resolve_trait_prompts(traits)
        self.assertEqual(len(prompts), 5)
        self.assertIn("sharp eyebrows", prompts[0])

    def test_resolve_missing_falls_back_to_first(self):
        prompts = ft.resolve_trait_prompts({})
        self.assertEqual(len(prompts), 5)


class TestBuildPrompt(unittest.TestCase):
    """prompt 拼接。"""

    def test_contains_gender_traits_negative(self):
        pos, neg = ft.build_trait_prompt({"face_shape": "sharp"}, gender="female")
        self.assertIn("beautiful young woman", pos)
        self.assertIn("sharp eyebrows", pos)
        self.assertIn("low quality", neg)
        self.assertNotIn(",,", pos)  # 无双逗号

    def test_with_player_includes_path_and_realm(self):
        p = Player(name="t")
        p.cultivation_path = "jian"
        p.realm_id = "foundation_early"
        pos, _ = ft.build_trait_prompt({}, gender="male", player=p)
        self.assertIn("sword cultivator", pos)
        self.assertIn("Foundation Establishment", pos)

    def test_missing_config_returns_none(self):
        pos, neg = ft.build_trait_prompt({}, config_dir="不存在的目录")
        self.assertIsNone(pos)
        self.assertIsNone(neg)


class TestFaceTraitsPersist(unittest.TestCase):
    """face_traits 存档持久化。"""

    def test_roundtrip(self):
        p = Player(name="t")
        p.face_traits = {"face_shape": "sharp", "aura": "cold"}
        d = p.to_dict()
        r = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(r.face_traits, {"face_shape": "sharp", "aura": "cold"})

    def test_default_empty(self):
        p = Player(name="t")
        d = p.to_dict()
        d.pop("face_traits", None)
        r = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(r.face_traits, {})


class TestFaceCustomizeDialog(unittest.TestCase):
    """捏脸弹窗交互（offscreen）。"""

    def _dlg(self, traits=None):
        player = Player(name="t")
        if traits:
            player.face_traits = dict(traits)
        return FaceCustomizeDialog(gender="male", player=player)

    def test_construct_has_five_combos(self):
        dlg = self._dlg()
        self.assertEqual(len(dlg.combos), 5)
        self.assertEqual(len(dlg._current_traits), 5)

    def test_initial_traits_restored_from_player(self):
        dlg = self._dlg({"face_shape": "ethereal"})
        self.assertEqual(dlg._current_traits["face_shape"], "ethereal")

    def test_generate_success_enables_adopt(self):
        dlg = self._dlg()
        dlg._on_generated(True, "some/path.png", "")
        self.assertTrue(dlg.adopt_btn.isEnabled())
        self.assertEqual(dlg._generated_path, "some/path.png")

    def test_generate_failure_no_adopt(self):
        dlg = self._dlg()
        dlg._on_generated(False, "", "服务不可用")
        self.assertFalse(dlg.adopt_btn.isEnabled())
        self.assertIsNone(dlg.adopted_path)

    def test_adopt_sets_result(self):
        dlg = self._dlg()
        dlg._generated_path = "assets/portraits/generated_x.png"
        dlg._current_traits = {"face_shape": "sharp"}
        dlg._on_adopt_ai()
        self.assertEqual(dlg.adopted_path, "assets/portraits/generated_x.png")
        self.assertEqual(dlg.adopted_traits, {"face_shape": "sharp"})


class TestBreakthroughPortraitCompat(unittest.TestCase):
    """捏过脸后大境界突破不自动替换头像。"""

    def _make_engine(self):
        tmp = tempfile.mkdtemp()
        player = Player(name="t")
        player.realm_id = "qi_refining_9"   # 练气九层 → 筑基（大境界渡劫）
        player.qi = 10 ** 9
        return GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=SaveManager(save_path=os.path.join(tmp, "s.json"),
                                     save_dir=os.path.join(tmp, "sv")),
        )

    def test_no_traits_auto_replaces(self):
        engine = self._make_engine()
        with patch("game.engine.random.random", return_value=0.0), \
             patch("game.engine.find_best_portrait_resource",
                   return_value="assets/portraits/protagonist_foundation.png") as mock_find:
            engine.breakthrough()
        self.assertEqual(mock_find.call_count, 1)
        self.assertEqual(engine.player.portrait,
                         "assets/portraits/protagonist_foundation.png")

    def test_with_traits_keeps_custom_portrait(self):
        engine = self._make_engine()
        engine.player.face_traits = {"face_shape": "sharp"}
        engine.player.portrait = "assets/portraits/custom.png"
        with patch("game.engine.random.random", return_value=0.0), \
             patch("game.engine.find_best_portrait_resource",
                   return_value="assets/portraits/protagonist_foundation.png") as mock_find:
            engine.breakthrough()
        self.assertEqual(mock_find.call_count, 0)
        self.assertEqual(engine.player.portrait, "assets/portraits/custom.png")


if __name__ == "__main__":
    unittest.main()
