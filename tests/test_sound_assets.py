# -*- coding: utf-8 -*-
"""音效资源与 SoundManager 测试：文件存在、格式合法、静音/音量降级行为。"""
import os
import sys
import unittest
import wave

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")
SOUNDS = ["breakthrough", "victory", "level_up"]


class TestSoundAssets(unittest.TestCase):

    def test_sound_files_exist(self):
        for name in SOUNDS:
            path = os.path.join(ASSETS, f"{name}.wav")
            self.assertTrue(os.path.exists(path), f"缺少音效 {path}")

    def test_sound_format_valid(self):
        for name in SOUNDS:
            path = os.path.join(ASSETS, f"{name}.wav")
            with wave.open(path) as w:
                self.assertEqual(w.getnchannels(), 1)
                self.assertEqual(w.getsampwidth(), 2)
                self.assertEqual(w.getframerate(), 44100)
                self.assertGreater(w.getnframes(), 0)

    def test_manager_playback_graceful_when_muted(self):
        """静音/音量为 0 时 play 直接返回，不抛异常。"""
        from game.sound_manager import SoundManager
        mgr = SoundManager(assets_dir=ASSETS)
        mgr.set_muted(True)
        mgr.play("breakthrough")      # 不应抛异常
        mgr.set_muted(False)
        mgr.set_volume(0.0)
        mgr.play("victory")

    def test_manager_does_not_crash_missing_file(self):
        """缺失音效文件时回退（beep），不抛异常。"""
        from game.sound_manager import SoundManager
        mgr = SoundManager(assets_dir=os.path.join(ASSETS, "nonexistent"))
        mgr.play("not_a_sound")


if __name__ == "__main__":
    unittest.main()
