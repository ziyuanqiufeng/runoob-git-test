# -*- coding: utf-8 -*-
"""难度与多周目模式选择弹窗（F-06 / F-07）。

新游戏开局时由主窗口调用以选择难度与周目模式；游戏内也可打开以查看/调整难度。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup,
    QRadioButton, QFrame, QScrollArea, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt

from game.difficulty_manager import DifficultyManager
from game.meta_manager import MetaManager


class DifficultyModeDialog(QDialog):
    """选择难度与多周目模式，并在确认时应用。"""

    def __init__(self, engine, player, parent=None, new_game=False):
        super().__init__(parent)
        self.engine = engine
        self.player = player
        self.new_game = new_game
        self.difficulty_manager = DifficultyManager(config_dir="config")
        self.meta_manager = MetaManager(config_dir="config")
        self.setWindowTitle("难度与周目模式" if new_game else "难度 · 模式")
        self.resize(560, 520)

        self._selected_difficulty = getattr(player, "difficulty", "normal")
        self._selected_mode = getattr(player, "game_mode", "standard")

        layout = QVBoxLayout(self)

        # 难度选择
        diff_group = QGroupBox("修行难度")
        diff_layout = QVBoxLayout(diff_group)
        self._diff_group = QButtonGroup(self)
        self._diff_radios = {}
        for d in self.difficulty_manager.get_difficulties():
            rb = QRadioButton(f"{d['name']} —— {d.get('desc', '')}")
            self._diff_radios[d["id"]] = rb
            self._diff_group.addButton(rb)
            diff_layout.addWidget(rb)
            if d["id"] == self._selected_difficulty:
                rb.setChecked(True)
        layout.addWidget(diff_group)

        # 模式选择
        mode_group = QGroupBox("多周目模式（开局选择）")
        mode_layout = QVBoxLayout(mode_group)
        self._mode_group = QButtonGroup(self)
        self._mode_radios = {}
        for m in self.meta_manager.get_modes_with_availability(player):
            rb = QRadioButton(f"{m['name']} —— {m.get('desc', '')}")
            self._mode_radios[m["id"]] = rb
            self._mode_group.addButton(rb)
            if not m["available"]:
                rb.setEnabled(False)
                rb.setText(rb.text() + f"  [🔒 {m['lock_reason']}]")
            if m["id"] == self._selected_mode:
                rb.setChecked(True)
            mode_layout.addWidget(rb)
        layout.addWidget(mode_group)

        # 当前称号提示
        titles = getattr(player, "titles", [])
        title_label = QLabel(
            "已获称号：" + ("、".join(titles) if titles else "无")
        )
        title_label.setStyleSheet("color: #b8860b;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        if not new_game:
            tip = QLabel("提示：难度可随时调整并立即生效；多周目模式仅在开局时确定。")
            tip.setStyleSheet("color: #666; font-size: 12px;")
            tip.setWordWrap(True)
            layout.addWidget(tip)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("确认")
        ok_btn.clicked.connect(self._on_accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_accept(self):
        # 应用难度（随时可改）
        for did, rb in self._diff_radios.items():
            if rb.isChecked():
                self._selected_difficulty = did
                break
        self.difficulty_manager.apply_to_player(self.player, self._selected_difficulty)

        # 应用模式（仅当可用）
        selected_mode = self._selected_mode
        for mid, rb in self._mode_radios.items():
            if rb.isChecked():
                selected_mode = mid
                break
        mode = self.meta_manager.config.get_mode(selected_mode)
        if mode:
            ok, reason = self.meta_manager.is_available(mode, self.player)
            if ok:
                self.meta_manager.apply_to_player(self.player, selected_mode)
            else:
                QMessageBox.warning(self, "模式不可用", reason)
                return
        self.accept()

    def get_difficulty_id(self):
        return self._selected_difficulty

    def get_mode_id(self):
        return self._selected_mode
