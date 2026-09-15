# -*- coding: utf-8 -*-
"""登录界面「继续上次」快捷入口测试。"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

from game.save_manager import SaveManager
from ui.login_dialog import LoginDialog

app = QApplication.instance() or QApplication([])


class TestSaveManagerRealmMeta(unittest.TestCase):
    """SaveManager 读取境界元信息。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.save_dir = os.path.join(self.tmp, "saves")
        os.makedirs(self.save_dir, exist_ok=True)
        self.sm = SaveManager(
            save_path=os.path.join(self.tmp, "save.json"),
            save_dir=self.save_dir,
        )

    def _write_save(self, path, name="甲", realm_id="foundation_early"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "version": 1,
                "player": {"name": name, "realm_id": realm_id},
                "world": {},
                "player_name": name,
                "saved_at": "2026-08-31 10:00:00",
            }, f, ensure_ascii=False)

    def test_read_meta_returns_realm_id(self):
        p = os.path.join(self.save_dir, "s1.json")
        self._write_save(p, realm_id="foundation_early")
        meta = self.sm._read_meta(p)
        self.assertEqual(meta["realm_id"], "foundation_early")

    def test_list_slots_has_realm_id(self):
        self._write_save(os.path.join(self.save_dir, "s1.json"), realm_id="golden_core_early")
        slots = self.sm.list_slots()
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]["realm_id"], "golden_core_early")


class TestLoginContinue(unittest.TestCase):
    """登录界面「继续上次」按钮。"""

    def test_realm_name_mapping(self):
        dlg = LoginDialog()
        self.assertEqual(dlg._realm_name("qi_refining_1"), "练气期一层")
        self.assertEqual(dlg._realm_name("nascent_soul"), "元婴期")

    def test_realm_name_unknown(self):
        dlg = LoginDialog()
        self.assertEqual(dlg._realm_name("不存在"), "")
        self.assertEqual(dlg._realm_name(None), "")

    def test_on_continue_sets_slot(self):
        dlg = LoginDialog()
        dlg.recent_slot = {"name": "slot_a", "player_name": "甲"}
        dlg._on_continue()
        self.assertEqual(dlg.selected_action, LoginDialog.LOAD)
        self.assertEqual(dlg.selected_slot, "slot_a")

    def test_no_recent_slot_hides_button(self):
        with patch("game.save_manager.SaveManager") as MockSM:
            MockSM.return_value.list_slots.return_value = []
            dlg = LoginDialog()
        self.assertTrue(dlg.btn_continue.isHidden())

    def test_recent_slot_shows_button(self):
        with patch("game.save_manager.SaveManager") as MockSM:
            MockSM.return_value.list_slots.return_value = [
                {"name": "slot_a", "player_name": "甲", "realm_id": "foundation_early", "saved_at": "2026-08-31 10:00:00"}
            ]
            dlg = LoginDialog()
        self.assertFalse(dlg.btn_continue.isHidden())
        self.assertIn("甲", dlg.btn_continue.text())
        self.assertIn("筑基", dlg.btn_continue.text())


if __name__ == "__main__":
    unittest.main()
