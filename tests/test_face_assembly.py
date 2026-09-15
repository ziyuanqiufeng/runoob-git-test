# -*- coding: utf-8 -*-
"""捏脸二期（拼装路线）测试：配置/合成器/持久化/UI 交互/突破兼容。"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from PIL import Image

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
from game import face_compositor as fc
from ui.face_customize_dialog import FaceCustomizeDialog


class TestPartsConfig(unittest.TestCase):
    def test_load_valid(self):
        cfg = fc.load_parts_config("config")
        self.assertIsNotNone(cfg)
        self.assertEqual(int(cfg["canvas"]), 256)
        self.assertEqual(len(cfg["layers"]), 6)
        self.assertEqual(len(cfg["skins"]), 3)
        for layer in cfg["layers"]:
            self.assertTrue(layer.get("parts"))


class TestCompositor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "face.png")

    def test_random_params_complete(self):
        params = fc.random_face_params("config")
        self.assertEqual(len(params), 7)  # 6 层 + skin
        self.assertIn(params["skin"], ("fair", "wheat", "bronzed"))

    def test_compose_produces_valid_png(self):
        params = fc.random_face_params("config")
        out = fc.compose(params, self.out, "config")
        self.assertEqual(out, self.out)
        with Image.open(self.out) as img:
            self.assertEqual(img.size, (256, 256))

    def test_compose_empty_params_still_valid(self):
        out = fc.compose({}, self.out, "config")
        self.assertTrue(os.path.exists(self.out))
        with Image.open(self.out) as img:
            self.assertEqual(img.size, (256, 256))

    def test_compose_accessory_none_skipped(self):
        params = fc.random_face_params("config")
        params["accessory"] = "none"
        out = fc.compose(params, self.out, "config")  # 不应报错
        self.assertTrue(os.path.exists(self.out))

    def test_tint_changes_pixels(self):
        base = fc.compose({"face": "oval_1", "skin": "fair"},
                          self.out, "config")
        p1 = Image.open(base).convert("RGBA").getpixel((128, 180))
        out2 = os.path.join(self.tmp, "face2.png")
        fc.compose({"face": "oval_1", "skin": "bronzed"}, out2, "config")
        p2 = Image.open(out2).convert("RGBA").getpixel((128, 180))
        self.assertNotEqual(p1[:3], p2[:3])  # 古铜肤色应明显不同


class TestFaceParamsPersist(unittest.TestCase):
    def test_roundtrip(self):
        p = Player(name="t")
        p.face_params = {"face": "oval_1", "skin": "fair"}
        d = p.to_dict()
        r = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(r.face_params, {"face": "oval_1", "skin": "fair"})

    def test_default_empty(self):
        p = Player(name="t")
        d = p.to_dict()
        d.pop("face_params", None)
        r = Player.from_dict(d, ItemLibrary(config_dir="config"))
        self.assertEqual(r.face_params, {})


class TestAssemblyDialog(unittest.TestCase):
    """拼装 Tab UI 交互（offscreen）。"""

    def _dlg(self, params=None):
        player = Player(name="t")
        if params:
            player.face_params = dict(params)
        return FaceCustomizeDialog(gender="male", player=player)

    def test_construct_combos(self):
        dlg = self._dlg()
        self.assertEqual(len(dlg.part_combos), 6)
        self.assertIsNotNone(dlg.skin_combo)
        self.assertEqual(len(dlg._assembly_params), 7)

    def test_initial_params_restored(self):
        dlg = self._dlg({"face": "round_1", "skin": "wheat"})
        self.assertEqual(dlg._assembly_params["face"], "round_1")
        self.assertEqual(dlg._assembly_params["skin"], "wheat")

    def test_preview_composed_on_init(self):
        dlg = self._dlg()
        self.assertTrue(getattr(dlg, "_composed_path", None))
        self.assertTrue(os.path.exists(dlg._composed_path))

    def test_random_fills_params(self):
        dlg = self._dlg()
        dlg._on_assembly_random()
        self.assertEqual(len(dlg._assembly_params), 7)

    def test_adopt_assembly_saves_final_portrait(self):
        dlg = self._dlg()
        dlg._on_adopt_assembly()
        self.assertIsNotNone(dlg.adopted_path)
        self.assertTrue(os.path.exists(dlg.adopted_path))
        self.assertIn("assets/portraits", dlg.adopted_path.replace("\\", "/"))
        self.assertIsNotNone(dlg.adopted_params)
        self.assertIsNone(dlg.adopted_traits)


class TestBreakthroughCompatParams(unittest.TestCase):
    """拼装过形象后突破同样不自动替换头像。"""

    def _make_engine(self):
        tmp = tempfile.mkdtemp()
        player = Player(name="t")
        player.realm_id = "qi_refining_9"
        player.qi = 10 ** 9
        player.portrait = "assets/portraits/custom.png"
        return GameEngine(
            player, World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=SaveManager(save_path=os.path.join(tmp, "s.json"),
                                     save_dir=os.path.join(tmp, "sv")),
        )

    def test_face_params_block_auto_replace(self):
        engine = self._make_engine()
        engine.player.face_params = {"face": "oval_1"}
        with patch("game.engine.random.random", return_value=0.0), \
             patch("game.engine.find_best_portrait_resource",
                   return_value="assets/portraits/protagonist_foundation.png") as mock_find:
            engine.breakthrough()
        self.assertEqual(mock_find.call_count, 0)
        self.assertEqual(engine.player.portrait, "assets/portraits/custom.png")


if __name__ == "__main__":
    unittest.main()
