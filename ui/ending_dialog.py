# -*- coding: utf-8 -*-
"""结局结算画面：展示达成的结局，提供转世重修 / 返回主菜单。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
)
from PySide6.QtCore import Qt, Signal


# 结局类型 → 主题色（金=圆满 / 蓝=中性 / 红=悲剧）
_TYPE_COLORS = {
    "good": ("#e8c97a", "#1b2a4a"),
    "neutral": ("#85b7eb", "#0c447c"),
    "bad": ("#e24b4a", "#501313"),
}


class EndingDialog(QDialog):
    """结局结算弹窗。"""

    reincarnate_requested = Signal()
    main_menu_requested = Signal()

    def __init__(self, ending, parent=None):
        super().__init__(parent)
        self.ending = ending or {}
        self.setWindowTitle("结局")
        self.setFixedSize(520, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 32)
        layout.setSpacing(16)

        title = QLabel("结 局")
        title.setObjectName("endingTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        etype = self.ending.get("type", "neutral")
        accent, text_color = _TYPE_COLORS.get(etype, _TYPE_COLORS["neutral"])

        name = QLabel(self.ending.get("name", "未知结局"))
        name.setObjectName("endingName")
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet(f"color: {accent}; font-size: 28px; font-weight: bold;")
        layout.addWidget(name)

        desc = QLabel(self.ending.get("desc", ""))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet(f"color: {text_color}; font-size: 14px; line-height: 1.6;")
        layout.addWidget(desc)

        layout.addStretch(1)

        btn_row = QHBoxLayout()
        self.btn_reincarnate = QPushButton("转世重修")
        self.btn_reincarnate.setStyleSheet(
            f"QPushButton {{ background-color: {accent}; color: #1b2a4a; "
            "border-radius: 8px; padding: 10px 24px; font-size: 15px; font-weight: bold; }}"
        )
        self.btn_reincarnate.clicked.connect(self._on_reincarnate)
        self.btn_main = QPushButton("返回主菜单")
        self.btn_main.setStyleSheet(
            "QPushButton { background-color: transparent; color: #888; "
            "border: 1px solid #ccc; border-radius: 8px; padding: 10px 24px; font-size: 15px; }"
        )
        self.btn_main.clicked.connect(self._on_main_menu)
        btn_row.addWidget(self.btn_reincarnate)
        btn_row.addWidget(self.btn_main)
        layout.addLayout(btn_row)

        self.setStyleSheet(
            "QDialog { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "stop:0 #1b2a4a, stop:1 #0d1526); }"
            "QLabel#endingTitle { color: #6b7d99; font-size: 16px; letter-spacing: 8px; }"
        )

    def _on_reincarnate(self):
        self.reincarnate_requested.emit()
        self.accept()

    def _on_main_menu(self):
        self.main_menu_requested.emit()
        self.accept()
