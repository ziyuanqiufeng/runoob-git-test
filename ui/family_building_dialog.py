# -*- coding: utf-8 -*-
"""家族建筑建造 / 升级弹窗（F-01）。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFrame, QMessageBox
)


class FamilyBuildingDialog(QDialog):
    def __init__(self, family_manager, parent=None):
        super().__init__(parent)
        self.manager = family_manager
        self.setWindowTitle("家族建筑")
        self.resize(480, 380)
        self.layout = QVBoxLayout(self)
        self._build()

    def _build(self):
        family = self.manager.get_family()
        treasury = family.get("treasury", 0)
        self.layout.addWidget(QLabel(f"家族金库灵石：{treasury}"))
        for b in self.manager.config.buildings():
            cur = family["buildings"].get(b["id"], 0)
            max_lvl = b.get("max_level", 5)
            frame = QFrame()
            frame.setFrameShape(QFrame.Box)
            frame.setStyleSheet("padding:8px; margin:4px; background:#fafafa;")
            v = QVBoxLayout(frame)
            v.addWidget(QLabel(
                f"<b>{b['name']}</b>（{cur}/{max_lvl} 级）— {b.get('desc','')}"
            ))
            if cur >= max_lvl:
                v.addWidget(QLabel("已达最高等级。"))
            else:
                cost = self.manager.build_cost(b["id"], cur)
                stone = cost.get("spirit_stone", 0)
                btn = QPushButton(f"升级（消耗 {stone} 灵石）")
                btn.setEnabled(treasury >= stone)
                btn.clicked.connect(lambda _checked, bid=b["id"]: self._upgrade(bid))
                v.addWidget(btn)
            self.layout.addWidget(frame)
        self.layout.addStretch(1)

    def _upgrade(self, building_id):
        ok, msg = self.manager.build_or_upgrade(building_id)
        QMessageBox.information(self, "建造", msg)
        if ok:
            self._clear()
            self._build()

    def _clear(self):
        while self.layout.count():
            w = self.layout.takeAt(0).widget()
            if w:
                w.deleteLater()
