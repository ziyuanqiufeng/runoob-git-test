# -*- coding: utf-8 -*-
"""玩法指南弹窗测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from ui.help_dialog import HelpDialog


class TestHelpDialog(unittest.TestCase):
    def test_tab_count_and_titles(self):
        from PySide6.QtWidgets import QTabWidget
        dlg = HelpDialog()
        tabs = dlg.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        self.assertEqual(tabs.count(), 4)
        titles = [tabs.tabText(i) for i in range(4)]
        self.assertEqual(titles, ["快速上手", "系统总览", "AI 功能", "常见问题"])

    def test_tabs_have_content(self):
        from PySide6.QtWidgets import QTabWidget, QTextBrowser
        dlg = HelpDialog()
        tabs = dlg.findChild(QTabWidget)
        for i in range(tabs.count()):
            page = tabs.widget(i)
            self.assertIsInstance(page, QTextBrowser)
            self.assertTrue(len(page.toPlainText()) > 50)  # 每页都有实质内容

    def test_faq_mentions_key_topics(self):
        from PySide6.QtWidgets import QTabWidget, QTextBrowser
        dlg = HelpDialog()
        tabs = dlg.findChild(QTabWidget)
        faq = tabs.widget(3)
        self.assertIsInstance(faq, QTextBrowser)
        text = faq.toPlainText()
        self.assertIn("AI 剧情", text)
        self.assertIn("导出", text)
        self.assertIn("备份", text)


if __name__ == "__main__":
    unittest.main()
