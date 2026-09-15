import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

from ui.login_dialog import LoginDialog


app = QApplication.instance() or QApplication([])


class TestLoginDialog(unittest.TestCase):
    def test_construct_has_four_buttons(self):
        dlg = LoginDialog()
        self.assertIsNotNone(dlg.btn_new)
        self.assertIsNotNone(dlg.btn_load)
        self.assertIsNotNone(dlg.btn_settings)
        self.assertIsNotNone(dlg.btn_quit)
        self.assertIsNone(dlg.selected_action)

    def test_default_new_name(self):
        dlg = LoginDialog()
        name = dlg._default_new_name()
        self.assertTrue(name.startswith("修仙之旅"))

    def test_on_new_game_sets_action(self):
        dlg = LoginDialog()
        with patch("ui.login_dialog.QInputDialog.getText",
                   return_value=("我的存档", True)):
            dlg._on_new_game()
        self.assertEqual(dlg.selected_action, LoginDialog.NEW_GAME)
        self.assertEqual(dlg.new_slot_name, "我的存档")

    def test_on_new_game_cancel_keeps_none(self):
        dlg = LoginDialog()
        with patch("ui.login_dialog.QInputDialog.getText",
                   return_value=("忽略", False)):
            dlg._on_new_game()
        self.assertIsNone(dlg.selected_action)

    def test_on_quit_sets_action(self):
        dlg = LoginDialog()
        dlg._on_quit()
        self.assertEqual(dlg.selected_action, LoginDialog.QUIT)

    def test_on_load_no_saves_shows_message(self):
        dlg = LoginDialog()
        with patch("game.save_manager.SaveManager") as MockSM, \
                patch("ui.login_dialog.QMessageBox.information") as mock_msg:
            instance = MockSM.return_value
            instance.list_slots.return_value = []
            dlg._on_load()
        self.assertIsNone(dlg.selected_action)
        mock_msg.assert_called_once()

    def test_on_settings_opens_dialog(self):
        dlg = LoginDialog()
        with patch("ui.login_dialog.SettingsDialog") as MockSettings:
            instance = MockSettings.return_value
            dlg._on_settings()
        MockSettings.assert_called_once()
        instance.exec.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
