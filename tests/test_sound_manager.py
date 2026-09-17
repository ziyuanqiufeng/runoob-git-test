# -*- coding: utf-8 -*-
"""SoundManager 边界测试（offscreen，不触发真实音频）。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from game.sound_manager import SoundManager


class TestSoundManager(unittest.TestCase):
    def _mk(self, prefs=None):
        tmp = tempfile.mkdtemp()
        sm = SoundManager(assets_dir=os.path.join(tmp, "audio"))
        sm._muted = False
        sm._volume = 1.0
        if prefs is not None:
            sm.PREFS_PATH = os.path.join(tmp, "prefs.json")
            with open(sm.PREFS_PATH, "w", encoding="utf-8") as f:
                json.dump(prefs, f)
            sm._load_prefs()
        return sm

    def test_default_volume(self):
        sm = self._mk()
        self.assertEqual(sm.get_volume(), 1.0)
        self.assertFalse(sm.is_muted())

    def test_set_volume_clamps_high(self):
        sm = self._mk()
        sm.set_volume(2.5)
        self.assertEqual(sm.get_volume(), 1.0)

    def test_set_volume_clamps_negative(self):
        sm = self._mk()
        sm.set_volume(-0.5)
        self.assertEqual(sm.get_volume(), 0.0)

    def test_set_volume_rejects_bad_type(self):
        sm = self._mk()
        sm.set_volume("abc")
        self.assertEqual(sm.get_volume(), 1.0)  # 回退默认

    def test_mute_roundtrip(self):
        sm = self._mk()
        sm.set_muted(True)
        self.assertTrue(sm.is_muted())
        sm.set_muted(False)
        self.assertFalse(sm.is_muted())

    def test_load_prefs_applies(self):
        sm = self._mk(prefs={"sound_muted": True, "sound_volume": 0.3})
        self.assertTrue(sm.is_muted())
        self.assertAlmostEqual(sm.get_volume(), 0.3)

    def test_load_prefs_clamps_volume(self):
        sm = self._mk(prefs={"sound_volume": 99.0})
        self.assertEqual(sm.get_volume(), 1.0)

    def test_load_prefs_bad_json_fallback(self):
        sm = self._mk()
        sm.PREFS_PATH = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(sm.PREFS_PATH, "w", encoding="utf-8") as f:
            f.write("{not json")
        sm._load_prefs()
        self.assertFalse(sm.is_muted())
        self.assertEqual(sm.get_volume(), 1.0)

    def test_play_silent_no_crash(self):
        """静音或音量 0 时 play 直接跳过（不触达音频，安全可测）。"""
        sm = self._mk()
        sm.set_muted(True)
        sm.play("breakthrough")  # 不应抛
        sm.set_muted(False)
        sm.set_volume(0.0)
        sm.play("victory")       # 音量 0 也跳过


if __name__ == "__main__":
    unittest.main()
