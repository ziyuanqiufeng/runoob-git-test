# -*- coding: utf-8 -*-
"""
拍卖行弹窗：显示本月拍品、出价与结算。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QListWidget, QListWidgetItem, QSpinBox
)
from PySide6.QtCore import Qt


class AuctionDialog(QDialog):
    """拍卖行交互弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player

        self.setWindowTitle("拍卖行")
        self.resize(480, 420)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("<h2>云海拍卖行</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 说明
        desc = QLabel("每月刷新一批稀有拍品，出价最高者可得。")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(desc)

        # 灵石显示
        self.money_label = QLabel()
        self.money_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.money_label)

        # 拍品列表
        self.lot_list = QListWidget()
        self.lot_list.setSpacing(4)
        self.lot_list.currentRowChanged.connect(self._on_lot_changed)
        layout.addWidget(self.lot_list)

        # 出价区域
        bid_layout = QHBoxLayout()
        bid_layout.addWidget(QLabel("出价："))
        self.bid_spin = QSpinBox()
        self.bid_spin.setRange(1, 999999)
        self.bid_spin.setSingleStep(10)
        bid_layout.addWidget(self.bid_spin, 1)

        self.bid_btn = QPushButton("出价")
        self.bid_btn.clicked.connect(self._on_bid)
        bid_layout.addWidget(self.bid_btn)

        self.settle_btn = QPushButton("结算拍得")
        self.settle_btn.setToolTip("结算当前选中的已竞得拍品。")
        self.settle_btn.clicked.connect(self._on_settle)
        bid_layout.addWidget(self.settle_btn)
        layout.addLayout(bid_layout)

        # 关闭按钮
        close_btn = QPushButton("离开")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        self._lots = []
        self._refresh()

    def _refresh(self):
        """刷新灵石与拍品列表。"""
        stones = self.player.count_item("spirit_stone")
        self.money_label.setText(f"当前灵石：<b>{stones}</b>")

        self._lots = self.engine.run_auction()
        self.lot_list.clear()
        for idx, lot in enumerate(self._lots):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, idx)
            bidder_text = "（你领先）" if lot.get("bidder") == "player" else ""
            item.setText(
                f"{lot.get('name', lot['item_id'])}　"
                f"底价：{lot['base_price']}　"
                f"当前：{lot['current_price']} 灵石{bidder_text}"
            )
            self.lot_list.addItem(item)

        if self._lots:
            self.lot_list.setCurrentRow(0)

    def _on_lot_changed(self, row):
        """切换拍品时更新默认出价。"""
        if row < 0 or row >= len(self._lots):
            return
        lot = self._lots[row]
        self.bid_spin.setValue(lot["current_price"] + 10)

    def _on_bid(self):
        """对选中拍品出价。"""
        row = self.lot_list.currentRow()
        if row < 0 or row >= len(self._lots):
            QMessageBox.warning(self, "未选择", "请先选择一件拍品。")
            return

        amount = self.bid_spin.value()
        ok, msg = self.engine.bid_auction(row, amount)
        if ok:
            QMessageBox.information(self, "出价成功", msg)
        else:
            QMessageBox.warning(self, "出价失败", msg)
        self._refresh()

    def _on_settle(self):
        """结算选中拍品。"""
        row = self.lot_list.currentRow()
        if row < 0 or row >= len(self._lots):
            QMessageBox.warning(self, "未选择", "请先选择一件拍品。")
            return

        ok, msg = self.engine.settle_auction(row)
        if ok:
            QMessageBox.information(self, "结算成功", msg)
        else:
            QMessageBox.warning(self, "结算失败", msg)
        self._refresh()
