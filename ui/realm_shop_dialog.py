# -*- coding: utf-8 -*-
"""秘境商店 / 秘境币兑换弹窗（F-03）。"""
from PySide6.QtWidgets import (
    QDialog, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QHBoxLayout, QVBoxLayout, QScrollArea, QWidget,
)


class ShopDialog(QDialog):
    def __init__(self, reward_mgr, player, title="秘境商店", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.reward_mgr = reward_mgr
        self.player = player
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        self.coin_label = QLabel()
        layout.addWidget(self.coin_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self.rows = QVBoxLayout(body)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        self.refresh()

    def refresh(self):
        self.coin_label.setText(f"持有秘境币：{self.player.realm_coins}")
        # 清空行
        while self.rows.count():
            item = self.rows.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for entry in self.reward_mgr.get_exchange_items():
            row = QHBoxLayout()
            info = QLabel(f"{entry.get('name', entry['id'])}  —  {entry['cost']} 币"
                          + ("（专属）" if entry.get("exclusive") else ""))
            info.setWordWrap(True)
            btn = QPushButton("兑换")
            btn.clicked.connect(lambda _checked, iid=entry["id"]: self._buy(iid))
            row.addWidget(info, 1)
            row.addWidget(btn)
            wrap = QWidget()
            wrap.setLayout(row)
            self.rows.addWidget(wrap)
        self.rows.addStretch(1)

    def _buy(self, item_id):
        ok, msg = self.reward_mgr.exchange(item_id)
        self.coin_label.setText(f"持有秘境币：{self.player.realm_coins}　|　{msg}")
        if ok:
            self.refresh()
