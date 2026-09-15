# -*- coding: utf-8 -*-
"""转世弹窗 UI 测试。"""
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from game.player import Player
from game.reincarnation_manager import ReincarnationManager
from ui.reincarnation_dialog import ReincarnationDialog


class TestReincarnationDialog(unittest.TestCase):
    """转世弹窗测试。"""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _make_engine(self):
        """构造一个仅包含必要属性的 mock Engine。"""
        player = Player(name="测试修士")
        # 提高境界以获得足够继承点
        player.realm_id = "golden_core_peak"
        engine = MagicMock()
        engine.player = player
        engine.reincarnation_manager = ReincarnationManager(player)
        engine.compute_reincarnation_options = (
            engine.reincarnation_manager.compute_available_options
        )
        return engine

    def test_dialog_shows_options(self):
        """转世弹窗应显示继承选项。"""
        dialog = ReincarnationDialog(self._make_engine())
        self.assertGreater(len(dialog.checkboxes), 0)
        dialog.close()

    def test_select_option_updates_cost(self):
        """选择继承项后应更新消耗显示。"""
        dialog = ReincarnationDialog(self._make_engine())
        # 勾选第一个可用选项
        for cb in dialog.checkboxes:
            if cb.isEnabled():
                cb.setChecked(True)
                break
        text = dialog.cost_label.text()
        self.assertIn("已选消耗", text)
        self.assertNotEqual(text, "已选消耗：0 点")
        dialog.close()

    @patch("ui.reincarnation_dialog.QMessageBox.warning")
    def test_confirm_without_selection_warns(self, mock_warning):
        """未选择时确认应弹出警告。"""
        dialog = ReincarnationDialog(self._make_engine())
        # 不勾选任何选项直接确认
        dialog._on_confirm()
        # 应弹出 QMessageBox 警告
        mock_warning.assert_called_once()
        # 未产生有效选择结果
        self.assertFalse(hasattr(dialog, "selected_options"))
        dialog.close()


if __name__ == "__main__":
    unittest.main()
