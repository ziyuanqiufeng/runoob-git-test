import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

from ui.settings_dialog import SettingsDialog


app = QApplication.instance() or QApplication([])


class TestSettingsDialog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.prefs = os.path.join(self.tmp, "ui_prefs.json")

    def _make(self, **kwargs):
        with patch.object(SettingsDialog, "PREFS_PATH", self.prefs):
            return SettingsDialog(**kwargs)

    def test_construct_no_player_disables_portrait_and_difficulty(self):
        dlg = self._make()
        self.assertFalse(dlg.btn_portrait.isEnabled())
        self.assertFalse(dlg.btn_difficulty.isEnabled())

    def test_construct_with_engine_player_enables(self):
        dlg = self._make(engine=object(), player=object())
        self.assertTrue(dlg.btn_portrait.isEnabled())
        self.assertTrue(dlg.btn_difficulty.isEnabled())

    def test_mute_persists(self):
        with patch.object(SettingsDialog, "PREFS_PATH", self.prefs):
            dlg = SettingsDialog()
            dlg._on_mute_toggled(True)
        self.assertTrue(os.path.exists(self.prefs))
        with open(self.prefs, encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(data["sound_muted"])

    def test_volume_persists(self):
        with patch.object(SettingsDialog, "PREFS_PATH", self.prefs):
            dlg = SettingsDialog()
            dlg._on_volume_changed(50)
        with open(self.prefs, encoding="utf-8") as f:
            data = json.load(f)
        self.assertAlmostEqual(data["sound_volume"], 0.5)

    def test_runtime_sound_applies(self):
        sm = MagicMock()
        with patch.object(SettingsDialog, "PREFS_PATH", self.prefs):
            dlg = SettingsDialog(sound_manager=sm)
            dlg._on_mute_toggled(True)
        sm.set_muted.assert_called_with(True)

    def test_prefs_merge_keeps_other_keys(self):
        # 预置一个含手风琴偏好的 ui_prefs.json，确认设置不会覆盖它
        with open(self.prefs, "w", encoding="utf-8") as f:
            json.dump({"accordion_multi_expand": True}, f, ensure_ascii=False)
        with patch.object(SettingsDialog, "PREFS_PATH", self.prefs):
            dlg = SettingsDialog()
            dlg._on_volume_changed(30)
        with open(self.prefs, encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(data["accordion_multi_expand"])
        self.assertAlmostEqual(data["sound_volume"], 0.3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
