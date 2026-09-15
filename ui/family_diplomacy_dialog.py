# -*- coding: utf-8 -*-
"""家族外交弹窗（F-01）。

列出可外交的其他家族，设置结盟 / 对立 / 中立关系。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame, QMessageBox
)


class FamilyDiplomacyDialog(QDialog):
    def __init__(self, family_manager, parent=None):
        super().__init__(parent)
        self.manager = family_manager
        self.setWindowTitle("家族外交")
        self.resize(480, 360)
        self.layout = QVBoxLayout(self)
        self._build()

    def _build(self):
        family = self.manager.get_family()
        targets = self.manager.diplo_mgr.list_targets()
        if not targets:
            self.layout.addWidget(QLabel("暂无可外交的家族。"))
            return
        for t in targets:
            frame = QFrame()
            frame.setFrameShape(QFrame.Box)
            frame.setStyleSheet("padding:8px; margin:4px; background:#fafafa;")
            h = QHBoxLayout(frame)
            rel = self.manager.diplo_mgr.get_relation(family, t["id"])
            h.addWidget(QLabel(
                f"{t['name']}（{t.get('tendency','')}／实力 {t.get('strength',0)}）"
                f"　当前：{self._rel_name(rel)}"
            ))
            for r, label in (("ally", "结盟"), ("rival", "对立"), ("neutral", "中立")):
                btn = QPushButton(label)
                btn.clicked.connect(
                    lambda _checked, tid=t["id"], rr=r: self._set(tid, rr)
                )
                h.addWidget(btn)
            self.layout.addWidget(frame)
        self.layout.addStretch(1)

    @staticmethod
    def _rel_name(rel):
        return {"ally": "结盟", "rival": "对立", "neutral": "中立"}.get(rel, "中立")

    def _set(self, target_id, relation):
        family = self.manager.get_family()
        self.manager.diplo_mgr.set_relation(family, target_id, relation)
        QMessageBox.information(self, "外交", f"关系已设为{self._rel_name(relation)}。")
        self._clear()
        self._build()

    def _clear(self):
        while self.layout.count():
            w = self.layout.takeAt(0).widget()
            if w:
                w.deleteLater()
