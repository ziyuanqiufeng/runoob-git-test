# -*- coding: utf-8 -*-
"""家族事件处理弹窗（F-01）。

展示待处理事件，玩家选择其一后调用 FamilyEventManager 应用效果，
并从 pending_events 中移除已处理事件。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFrame, QMessageBox
)
from PySide6.QtCore import Signal


class FamilyEventDialog(QDialog):
    resolved = Signal()

    def __init__(self, family_manager, parent=None):
        super().__init__(parent)
        self.manager = family_manager
        self.setWindowTitle("家族事件")
        self.resize(460, 420)
        self.layout = QVBoxLayout(self)
        self._build()

    def _build(self):
        family = self.manager.get_family()
        events = family.get("pending_events", [])
        if not events:
            self.layout.addWidget(QLabel("当前没有待处理事件。"))
            return
        for ev in events:
            self.layout.addWidget(self._event_block(ev))
        self.layout.addStretch(1)

    def _event_block(self, ev):
        frame = QFrame()
        frame.setFrameShape(QFrame.Box)
        frame.setStyleSheet("padding:10px; margin:4px; background:#fffaf0;")
        v = QVBoxLayout(frame)
        v.addWidget(QLabel(f"<b>{ev['name']}</b>"))
        v.addWidget(QLabel(ev.get("desc", "")))
        for i, choice in enumerate(ev.get("choices", [])):
            btn = QPushButton(choice.get("text", f"选项{i+1}"))
            btn.clicked.connect(lambda _checked, e=ev, idx=i: self._on_choose(e, idx))
            v.addWidget(btn)
        return frame

    def _on_choose(self, ev, idx):
        family = self.manager.get_family()
        log = self.manager.event_mgr.resolve_event(
            family, ev, idx, rng=None, family_manager=self.manager
        )
        # 从待处理中移除
        family["pending_events"] = [
            e for e in family["pending_events"] if e is not ev
        ]
        QMessageBox.information(self, "事件结果", log)
        self.resolved.emit()
        # 重建剩余事件
        self._clear()
        self._build()

    def _clear(self):
        while self.layout.count():
            w = self.layout.takeAt(0).widget()
            if w:
                w.deleteLater()
