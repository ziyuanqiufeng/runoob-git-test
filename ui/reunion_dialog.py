# -*- coding: utf-8 -*-
"""转世重逢演出面板：前世羁绊跨世重逢的情感高光时刻。

数据由引擎 trigger_past_life_reunion 组装并经 __PAST_LIFE_REUNION__:{json}
通知，本面板为只读演出层（宿慧的具象化演出）。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
)
from PySide6.QtCore import Qt

_BOND_STYLE = {
    "道侣": ("💜", "#8e44ad"),
    "挚友": ("🌿", "#27ae60"),
}


class PastLifeReunionDialog(QDialog):
    """转世重逢演出面板。"""

    def __init__(self, report, parent=None):
        super().__init__(parent)
        self.setWindowTitle("前世重逢")
        self.setModal(True)
        self.resize(440, 340)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("<h2>✨ 前世重逢</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        bond_type = report.get("bond_type", "挚友")
        icon, color = _BOND_STYLE.get(bond_type, ("✦", "#8a7ae8"))
        name = report.get("bond_name", "故人")
        intimacy = report.get("intimacy", 0)
        year = report.get("year", "?")
        bonus = report.get("bonus", 0)

        card = QLabel(
            f"<div style='text-align:center;'>"
            f"<span style='font-size:28px;'>{icon}</span><br>"
            f"<b style='font-size:16px;'>TA 正是你前世的{bond_type}"
            f"——【{name}】</b><br>"
            f"<span style='color:#888;'>前世情分（亲密度 {intimacy}），"
            f"一世纠葛未竟</span></div>"
        )
        card.setAlignment(Qt.AlignCenter)
        card.setWordWrap(True)
        layout.addWidget(card)

        quote = QLabel(
            "<i style='color:#6b5b95;'>「我们……是否在哪里见过？」</i><br>"
            "<span style='color:#888;'>TA 已不记得前世，但那份情分并未消散——"
            f"它化作了此刻的默契。</span>"
        )
        quote.setAlignment(Qt.AlignCenter)
        quote.setWordWrap(True)
        layout.addWidget(quote)

        gain = QLabel(
            f"<b style='color:{color};'>第{year}年 · 重逢</b>　"
            f"好感 +{bonus}"
        )
        gain.setAlignment(Qt.AlignCenter)
        layout.addWidget(gain)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("此生再会")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
