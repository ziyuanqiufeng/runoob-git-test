# -*- coding: utf-8 -*-
"""功能开关管理测试：engine 写回 / 设置面板切换 / 辅助字段保留。"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

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
from ui.settings_dialog import SettingsDialog


def _make_tmp_config():
    """构造 tmp/config 目录并复制真实 feature_flags.json。"""
    tmp = tempfile.mkdtemp()
    cfg = os.path.join(tmp, "config")
    os.makedirs(cfg, exist_ok=True)
    shutil.copy("config/feature_flags.json", os.path.join(cfg, "feature_flags.json"))
    return tmp, cfg


def _read_flags(cfg_dir):
    with open(os.path.join(cfg_dir, "feature_flags.json"), encoding="utf-8") as f:
        return json.load(f)


class TestEngineSetFlag(unittest.TestCase):
    """engine.set_feature_flag：内存生效 + JSON 持久化 + 辅助字段保留。"""

    def setUp(self):
        self.tmp, self.cfg = _make_tmp_config()
        # engine 用真实 config_dir 构造（各 Manager 需读其他配置），
        # 构造完成后把 config_dir 指向 tmp，使 set_feature_flag 写回 tmp副本
        self.engine = GameEngine(
            Player(name="t"), World(config_dir="config"), EventPool(config_dir="config"),
            ItemLibrary(config_dir="config"), EnemyLibrary(config_dir="config"),
            SkillLibrary(config_dir="config"), NPCLibrary(config_dir="config"),
            QuestLibrary(config_dir="config"),
            save_manager=SaveManager(save_path=os.path.join(self.tmp, "s.json"),
                                     save_dir=os.path.join(self.tmp, "sv")),
        )
        self.engine.config_dir = self.cfg

    def test_memory_effect(self):
        self.engine.set_feature_flag("heart_demon", False)
        self.assertFalse(self.engine.is_feature_enabled("heart_demon"))
        self.engine.set_feature_flag("heart_demon", True)
        self.assertTrue(self.engine.is_feature_enabled("heart_demon"))

    def test_persisted_to_json(self):
        self.engine.set_feature_flag("heart_demon", False)
        data = _read_flags(self.cfg)
        self.assertFalse(data["flags"]["heart_demon"])

    def test_aux_fields_preserved(self):
        self.engine.set_feature_flag("heart_demon", False)
        data = _read_flags(self.cfg)
        self.assertIn("_comment", data)
        self.assertIn("names", data)
        self.assertEqual(data["names"]["family"], "家族系统")
        self.assertIn("descriptions", data)


class TestSettingsFlagsSection(unittest.TestCase):
    """设置面板功能开关区（offscreen）。"""

    def setUp(self):
        self.tmp, self.cfg = _make_tmp_config()
        self.flags_path = os.path.join(self.cfg, "feature_flags.json")
        self._patcher = patch.object(SettingsDialog, "FLAGS_PATH", self.flags_path)
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def test_construct_lists_all_flags(self):
        dlg = SettingsDialog()  # 登录态：无 engine
        data = _read_flags(self.cfg)
        self.assertEqual(len(dlg._flag_checks), len(data["flags"]))
        for flag_id, enabled in data["flags"].items():
            self.assertEqual(dlg._flag_checks[flag_id].isChecked(), enabled)

    def test_toggle_no_engine_writes_json(self):
        dlg = SettingsDialog()
        dlg._flag_checks["heart_demon"].setChecked(False)
        data = _read_flags(self.cfg)
        self.assertFalse(data["flags"]["heart_demon"])

    def test_toggle_with_engine_memory(self):
        engine = MagicMock()
        dlg = SettingsDialog(engine=engine)
        dlg._flag_checks["family"].setChecked(False)
        engine.set_feature_flag.assert_called_once_with("family", False)

    def test_flag_has_chinese_name(self):
        dlg = SettingsDialog()
        text = dlg._flag_checks["family"].text()
        self.assertEqual(text, "家族系统")


if __name__ == "__main__":
    unittest.main()
