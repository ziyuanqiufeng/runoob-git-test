# -*- coding: utf-8 -*-
"""秘境随机事件弹窗（F-03）。"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QPushButton,
)


class EventDialog(QDialog):
    chosen = Signal(int)  # 选中的选项下标

    def __init__(self, event, parent=None):
        super().__init__(parent)
        self.setWindowTitle(event.get("name", "秘境事件"))
        self._build(event)

    def _build(self, event):
        layout = QVBoxLayout(self)
        title = QLabel(event.get("name", ""))
        title.setStyleSheet("font-weight:bold; font-size:15px;")
        layout.addWidget(title)
        desc = QLabel(event.get("description", ""))
        desc.setWordWrap(True)
        layout.addWidget(desc)
        for i, ch in enumerate(event.get("choices", [])):
            btn = QPushButton(f"{ch.get('text', '选项')}\n（{ch.get('desc', '')}）")
            btn.setToolTip(ch.get("desc", ""))
            btn.setStyleSheet("text-align:left; padding:6px;")
            btn.clicked.connect(lambda _checked, i=i: (self.chosen.emit(i), self.accept()))
            layout.addWidget(btn)
