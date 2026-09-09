import json
import os

from PySide6.QtCore import QUrl


class SoundManager:
    """音效管理器，播放简单的游戏音效，支持静音与音量。"""

    # 与 UI 偏好共用的配置文件（含手风琴多开偏好等）
    PREFS_PATH = os.path.join("config", "ui_prefs.json")

    def __init__(self, assets_dir="assets"):
        self.assets_dir = assets_dir
        self._sound_effect = None
        self._has_sound = False
        self._muted = False
        self._volume = 1.0
        self._try_init_sound()
        self._load_prefs()

    def _try_init_sound(self):
        """尝试初始化 QSoundEffect，如果失败则使用系统 beep。"""
        try:
            from PySide6.QtMultimedia import QSoundEffect
            self._sound_effect = QSoundEffect()
            self._has_sound = True
        except Exception:
            self._has_sound = False

    def _load_prefs(self):
        """从 ui_prefs.json 读取静音/音量设置（不存在或异常时回退默认）。"""
        try:
            if os.path.exists(self.PREFS_PATH):
                with open(self.PREFS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._muted = bool(data.get("sound_muted", False))
                vol = float(data.get("sound_volume", 1.0))
                self._volume = max(0.0, min(1.0, vol))
        except Exception:
            self._muted = False
            self._volume = 1.0

    def play(self, sound_name):
        """播放指定音效；静音或音量 0 时直接跳过。"""
        if self._muted or self._volume <= 0.0:
            return
        path = os.path.join(self.assets_dir, f"{sound_name}.wav")
        if self._has_sound and os.path.exists(path):
            effect = self._sound_effect
            try:
                effect.setVolume(self._volume)
            except Exception:
                pass
            effect.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
            effect.play()
        else:
            # 没有音效文件时回退到系统提示音
            from PySide6.QtWidgets import QApplication
            QApplication.beep()

    def play_breakthrough(self):
        """突破成功音效。"""
        self.play("breakthrough")

    def play_victory(self):
        """战斗胜利音效。"""
        self.play("victory")

    def play_level_up(self):
        """升级/完成任务音效。"""
        self.play("level_up")

    # ---------------- 静音 / 音量 ----------------
    def set_muted(self, muted):
        """设置是否静音。"""
        self._muted = bool(muted)

    def is_muted(self):
        """返回当前是否静音。"""
        return self._muted

    def set_volume(self, volume):
        """设置音量（0.0~1.0，自动夹取范围）。"""
        try:
            vol = float(volume)
        except (TypeError, ValueError):
            vol = 1.0
        self._volume = max(0.0, min(1.0, vol))

    def get_volume(self):
        """返回当前音量。"""
        return self._volume
