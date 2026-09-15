# -*- coding: utf-8 -*-
"""秘境增益卡三选一弹窗（F-03）。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QPushButton,
)

RARITY_COLOR = {
    "common": "#9e9e9e",
    "uncommon": "#4caf50",
    "rare": "#2196f3",
    "immortal_gold": "#ff9800",
}
RARITY_NAME = {
    "common": "普通", "uncommon": "精良", "rare": "稀有", "immortal_gold": "仙金",
}


class CardSelectDialog(QDialog):
    chosen = Signal(str)  # 选中的 card_id；空串表示跳过

    def __init__(self, draws, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择增益卡")
        self.draws = draws or []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("通关节点！选择一张增益卡（三选一）："))
        row = QHBoxLayout()
        for card in self.draws:
            row.addWidget(self._card_widget(card))
        layout.addLayout(row)
        skip = QPushButton("跳过（不选）")
        skip.clicked.connect(lambda: (self.chosen.emit(""), self.accept()))
        layout.addWidget(skip)

    def _card_widget(self, card):
        w = QFrame()
        w.setFrameShape(QFrame.Box)
        w.setFixedSize(160, 210)
        w.setCursor(Qt.PointingHandCursor)
        color = RARITY_COLOR.get(card.get("rarity", "common"), "#999")
        w.setStyleSheet(
            f"QFrame{{border:2px solid {color}; border-radius:8px; background:#fff;}}"
        )
        v = QVBoxLayout(w)
        name = QLabel(card.get("name", ""))
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignCenter)
        rarity = QLabel(RARITY_NAME.get(card.get("rarity", "common"), ""))
        rarity.setAlignment(Qt.AlignCenter)
        rarity.setStyleSheet(f"color:{color}; font-weight:bold;")
        eff = QLabel(self._effect_text(card))
        eff.setWordWrap(True)
        eff.setAlignment(Qt.AlignCenter)
        flavor = QLabel(card.get("flavor_text", ""))
        flavor.setWordWrap(True)
        flavor.setAlignment(Qt.AlignCenter)
        flavor.setStyleSheet("color:#888; font-size:11px;")
        v.addWidget(name)
        v.addWidget(rarity)
        v.addWidget(eff)
        v.addStretch(1)
        v.addWidget(flavor)
        cid = card["id"]

        def _on_click(_event, cid=cid):
            self.chosen.emit(cid)
            self.accept()

        w.mousePressEvent = _on_click
        return w

    @staticmethod
    def _effect_text(card):
        eff = card.get("effect", {})
        label = {"attack": "攻击", "defense": "防御", "hp": "生命",
                 "skill_damage": "技能伤害"}
        parts = []
        for k, v in eff.items():
            if k == "apply_to":
                continue
            parts.append(f"{label.get(k, k)} {v}")
        return "\n".join(parts)
