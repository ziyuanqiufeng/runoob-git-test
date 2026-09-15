# -*- coding: utf-8 -*-
"""存档详情预览测试。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

from game.save_manager import SaveManager
from ui.save_select_dialog import SaveSelectDialog

app = QApplication.instance() or QApplication([])


class TestReadSlotDetail(unittest.TestCase):
    """SaveManager.read_slot_detail。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.save_dir = os.path.join(self.tmp, "saves")
        os.makedirs(self.save_dir, exist_ok=True)
        self.sm = SaveManager(
            save_path=os.path.join(self.tmp, "save.json"),
            save_dir=self.save_dir,
        )

    def _write(self, name="s1", **player_kw):
        player = {
            "name": "逍遥子",
            "realm_id": "foundation_early",
            "location_id": "luoxia_city",
            "inventory": [{"id": "spirit_stone", "count": 1234}],
            "age": 36,
            "ending_id": "ascend_immortal",
            "main_story_step": 3,
        }
        player.update(player_kw)
        data = {
            "version": 1,
            "player": player,
            "world": {"year": 3, "month": 5},
            "saved_at": "2026-08-31 10:00:00",
        }
        with open(os.path.join(self.save_dir, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def test_read_full_detail(self):
        self._write()
        d = self.sm.read_slot_detail("s1")
        self.assertEqual(d["player_name"], "逍遥子")
        self.assertEqual(d["realm_id"], "foundation_early")
        self.assertEqual(d["location_id"], "luoxia_city")
        self.assertEqual(d["spirit_stones"], 1234)
        self.assertEqual(d["age"], 36)
        self.assertEqual(d["year"], 3)
        self.assertEqual(d["month"], 5)
        self.assertEqual(d["ending_id"], "ascend_immortal")
        self.assertEqual(d["main_story_step"], 3)

    def test_read_missing_returns_none(self):
        self.assertIsNone(self.sm.read_slot_detail("不存在"))

    def test_spirit_stones_summed(self):
        self._write(inventory=[
            {"id": "spirit_stone", "count": 100},
            {"id": "spirit_stone", "count": 50},
            {"id": "herb", "count": 3},
        ])
        d = self.sm.read_slot_detail("s1")
        self.assertEqual(d["spirit_stones"], 150)


class TestSaveSelectDetail(unittest.TestCase):
    """存档详情栏渲染。"""

    def test_load_name_map(self):
        dlg = SaveSelectDialog(save_manager=SaveManager(
            save_path=os.path.join(tempfile.mkdtemp(), "save.json"),
            save_dir=os.path.join(tempfile.mkdtemp(), "saves"),
        ))
        self.assertEqual(dlg._realm_names.get("foundation_early"), "筑基初期")
        self.assertIn("luoxia_city", dlg._location_names)
        self.assertIn("ascend_immortal", dlg._ending_names)

    def test_render_detail_contains_key_fields(self):
        tmp = tempfile.mkdtemp()
        save_dir = os.path.join(tmp, "saves")
        os.makedirs(save_dir, exist_ok=True)
        with open(os.path.join(save_dir, "s1.json"), "w", encoding="utf-8") as f:
            json.dump({
                "version": 1,
                "player": {"name": "逍遥子", "realm_id": "foundation_early",
                           "location_id": "luoxia_city",
                           "inventory": [{"id": "spirit_stone", "count": 888}],
                           "age": 30},
                "world": {"year": 2, "month": 3},
                "saved_at": "2026-08-31 10:00:00",
            }, f, ensure_ascii=False)
        dlg = SaveSelectDialog(save_manager=SaveManager(
            save_path=os.path.join(tmp, "save.json"), save_dir=save_dir))
        text = dlg._render_detail("s1")
        self.assertIn("逍遥子", text)
        self.assertIn("筑基初期", text)
        self.assertIn("落霞城", text)
        self.assertIn("888", text)


if __name__ == "__main__":
    unittest.main()
