# -*- coding: utf-8 -*-
"""UI 冒烟（v1.1.0 新增界面）：离屏构造 + 关键控件存在性。

覆盖：试炼塔弹窗 / 修行图鉴 / 灯会 / 设置试听按钮 / 行动面板新入口。
目的：抓布局错误、属性拼写、信号连接缺失（不测像素级外观）。
"""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QPushButton

_app = QApplication.instance() or QApplication([])

from game.player import Player  # noqa: E402
from game.world import World  # noqa: E402
from game.events import EventPool  # noqa: E402
from game.item import ItemLibrary  # noqa: E402
from game.enemy import EnemyLibrary  # noqa: E402
from game.skill import SkillLibrary  # noqa: E402
from game.npc import NPCLibrary  # noqa: E402
from game.quest import QuestLibrary  # noqa: E402
from game.engine import GameEngine  # noqa: E402
from game.save_manager import SaveManager  # noqa: E402


def _make_engine():
    tmp = tempfile.mkdtemp()
    player = Player(name="UI测试")
    return GameEngine(
        player,
        World(config_dir="config"),
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


class TestTrialTowerDialogUI(unittest.TestCase):

    def test_construct_and_controls(self):
        from ui.trial_tower_dialog import TrialTowerDialog
        e = _make_engine()
        dlg = TrialTowerDialog(e)
        self.assertIn("试炼塔", dlg.windowTitle())
        texts = [b.text() for b in dlg.findChildren(QPushButton)]
        self.assertTrue(any("开始挑战" in t for t in texts), texts)
        self.assertTrue(any("离开" in t for t in texts), texts)
        dlg.close()

    def test_active_state_shows_continue(self):
        from ui.trial_tower_dialog import TrialTowerDialog
        e = _make_engine()
        e.trial_tower_manager.start_run()
        dlg = TrialTowerDialog(e)
        texts = [b.text() for b in dlg.findChildren(QPushButton)]
        self.assertTrue(any("继续下一层" in t for t in texts), texts)
        self.assertTrue(any("撤退结算" in t for t in texts), texts)
        dlg.close()


class TestCollectionDialogUI(unittest.TestCase):

    def test_construct_with_tabs(self):
        from ui.collection_dialog import CollectionDialog
        from PySide6.QtWidgets import QTabWidget
        e = _make_engine()
        dlg = CollectionDialog(e)
        tabs = dlg.findChildren(QTabWidget)
        self.assertEqual(len(tabs), 1)
        self.assertEqual(tabs[0].count(), 2)   # 结局图鉴 / 人物图鉴
        self.assertEqual(tabs[0].tabText(0), "结局图鉴")
        self.assertEqual(tabs[0].tabText(1), "人物图鉴")
        dlg.close()

    def test_locked_state_shows_placeholder(self):
        from ui.collection_dialog import CollectionDialog
        e = _make_engine()
        e.player.meta_collection = {"endings": [], "npcs": []}
        dlg = CollectionDialog(e)
        self.assertIsNotNone(dlg)   # 空收集不崩
        dlg.close()


class TestLanternDialogUI(unittest.TestCase):

    def test_construct_three_options(self):
        from ui.lantern_dialog import LanternDialog
        e = _make_engine()
        dlg = LanternDialog(e)
        self.assertEqual(len(dlg.riddles), 3)   # 随机 3 题
        self.assertEqual(len(dlg.option_buttons), 3)
        dlg.close()

    def test_answer_flow_advances(self):
        from ui.lantern_dialog import LanternDialog
        e = _make_engine()
        dlg = LanternDialog(e)
        dlg._answer(0)
        self.assertEqual(dlg.index, 1)
        dlg.close()


class TestSettingsSoundTestButton(unittest.TestCase):

    def test_vol_test_button_exists(self):
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        texts = [b.text() for b in dlg.findChildren(QPushButton)]
        self.assertTrue(any("试听" in t for t in texts), texts)
        dlg.close()


class TestActionPanelNewEntries(unittest.TestCase):

    def test_trial_and_lantern_buttons(self):
        from ui.action_panel import ActionPanel
        e = _make_engine()
        panel = ActionPanel(e)
        # 新版入口应注册在 button_map 中
        self.assertIn("trial_tower", panel._button_map)
        self.assertIn("lantern", panel._button_map)
        panel.close()


if __name__ == "__main__":
    unittest.main()
