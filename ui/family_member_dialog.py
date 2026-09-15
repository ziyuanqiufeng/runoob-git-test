# -*- coding: utf-8 -*-
"""家族成员详情与任务分配弹窗（F-01）。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QFrame
)
from PySide6.QtCore import Signal

from game.family import TASKS, TASK_NAMES


class FamilyMemberDialog(QDialog):
    task_changed = Signal()

    def __init__(self, family_manager, member, parent=None):
        super().__init__(parent)
        self.manager = family_manager
        self.member = member
        self.setWindowTitle(f"成员：{member['name']}")
        self.resize(360, 320)
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        info = QFrame()
        info.setFrameShape(QFrame.Box)
        info.setStyleSheet("padding:10px; background:#fafafa;")
        iv = QVBoxLayout(info)
        iv.addWidget(QLabel(f"<b>{self.member['name']}</b>"))
        iv.addWidget(QLabel(f"灵根：{self.member.get('spirit_root','none')}"))
        iv.addWidget(QLabel(f"资质：{self.member.get('aptitude',0)}"))
        iv.addWidget(QLabel(f"忠诚：{self.member.get('loyalty',0)}"))
        iv.addWidget(QLabel(f"修为：{self.member.get('cultivation',0):.1f}"))
        iv.addWidget(QLabel(f"性格：{'、'.join(self.member.get('personality',[]))}"))
        trait = self.member.get("special_trait") or "无"
        iv.addWidget(QLabel(f"特质：{trait}"))
        v.addWidget(info)

        v.addWidget(QLabel("分配任务："))
        self.task_combo = QComboBox()
        self.task_combo.addItem("待命", None)
        for t in TASKS:
            self.task_combo.addItem(TASK_NAMES[t], t)
        # 选中当前任务
        cur = self.member.get("task")
        idx = 0
        for i in range(self.task_combo.count()):
            if self.task_combo.itemData(i) == cur:
                idx = i
                break
        self.task_combo.setCurrentIndex(idx)
        v.addWidget(self.task_combo)

        apply_btn = QPushButton("确定分配")
        apply_btn.clicked.connect(self._on_apply)
        v.addWidget(apply_btn)
        v.addStretch(1)

    def _on_apply(self):
        task = self.task_combo.currentData()
        self.manager.assign_task(self.member["id"], task)
        self.task_changed.emit()
        self.accept()
