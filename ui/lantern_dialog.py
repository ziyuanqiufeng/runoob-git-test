# -*- coding: utf-8 -*-
"""灯会猜谜：节日限定小玩法（3 道灯谜，答对得灵石，全对加心境）。"""
import json
import os
import random

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QMessageBox,
)


def _load_riddles(config_dir="config"):
    path = os.path.join(config_dir, "lantern_riddles.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("riddles", [])
    except (OSError, json.JSONDecodeError):
        return []


class LanternDialog(QDialog):
    """灯会猜谜（随机 3 题）。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("灯会猜谜")
        self.resize(460, 420)
        self.riddles = _load_riddles(getattr(engine, "config_dir", "config"))
        random.shuffle(self.riddles)
        self.riddles = self.riddles[:3]
        self.index = 0
        self.correct = 0
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(12)

        title = QLabel("<h2>🏮 灯会猜谜</h2>")
        title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title)

        self.progress = QLabel()
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("color:#6b7280;font-size:12px;")
        self.layout.addWidget(self.progress)

        self.question = QLabel()
        self.question.setWordWrap(True)
        self.question.setAlignment(Qt.AlignCenter)
        self.question.setStyleSheet(
            "font-size:15px; color:#374151; padding:12px;"
            "background:#fef9e7; border-radius:8px;"
        )
        self.layout.addWidget(self.question)

        self.option_buttons = []
        for i in range(3):
            btn = QPushButton()
            btn.clicked.connect(lambda _c=False, idx=i: self._answer(idx))
            self.layout.addWidget(btn)
            self.option_buttons.append(btn)

        self.footer = QLabel()
        self.footer.setAlignment(Qt.AlignCenter)
        self.footer.setStyleSheet("color:#b8860b; font-size:12px;")
        self.layout.addWidget(self.footer)

        self._render()

    def _render(self):
        if self.index >= len(self.riddles):
            self._finish()
            return
        riddle = self.riddles[self.index]
        self.progress.setText(f"第 {self.index + 1} / {len(self.riddles)} 盏")
        self.question.setText(
            riddle.get("question", "")
            + f"<br><span style='font-size:11px;color:#9ca3af;'>提示："
              f"{riddle.get('hint', '')}</span>"
        )
        options = riddle.get("options", [])
        for i, btn in enumerate(self.option_buttons):
            if i < len(options):
                btn.setText(options[i])
                btn.setVisible(True)
            else:
                btn.setVisible(False)

    def _answer(self, idx):
        riddle = self.riddles[self.index]
        if idx == riddle.get("answer", 0):
            self.correct += 1
            self.footer.setText("灯影摇曳，谜底揭晓——答对了！")
        else:
            options = riddle.get("options", [])
            right = options[riddle.get("answer", 0)] if options else "?"
            self.footer.setText(f"谜底是「{right}」，此灯留待来年。")
        self.index += 1
        self._render()

    def _finish(self):
        for btn in self.option_buttons:
            btn.setVisible(False)
        result = self.engine.award_lantern_reward(self.correct, len(self.riddles))
        self.question.setText(
            f"<b>三灯已尽，你答对了 {self.correct} / {len(self.riddles)} 题。</b><br>"
            f"<span style='color:#6b21a8;'>{result}</span>"
        )
        self.progress.setText("灯会散场")
        close_btn = QPushButton("尽兴而归")
        close_btn.clicked.connect(self.accept)
        self.layout.addWidget(close_btn)
