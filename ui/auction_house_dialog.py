# -*- coding: utf-8 -*-
"""拍卖行弹窗：查看拍品、出价、结算。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox, QInputDialog
)


class AuctionHouseDialog(QDialog):
    """展示本月拍卖品并支持出价。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("拍卖行")
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        stones = engine.player.count_item("spirit_stone")
        self.info_label = QLabel(f"持有灵石：{stones}")
        layout.addWidget(self.info_label)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.bid_btn = QPushButton("出价")
        self.bid_btn.clicked.connect(self._on_bid)
        btn_layout.addWidget(self.bid_btn)

        self.settle_btn = QPushButton("结算拍得")
        self.settle_btn.clicked.connect(self._on_settle)
        btn_layout.addWidget(self.settle_btn)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._refresh_list)
        btn_layout.addWidget(self.refresh_btn)

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)
        self._refresh_list()

    def _refresh_list(self):
        self.list_widget.clear()
        manager = self.engine.auction_house_manager
        manager.refresh()
        for idx, lot in enumerate(manager.get_lots()):
            bidder = lot.get("bidder")
            bidder_text = "（你的出价）" if bidder == "player" else ""
            text = (
                f"{lot['name']} | 底价 {lot['base_price']} | "
                f"当前 {lot['current_price']} 灵石{bidder_text}"
            )
            item = QListWidgetItem(text)
            item.setData(256, idx)
            self.list_widget.addItem(item)
        stones = self.engine.player.count_item("spirit_stone")
        self.info_label.setText(f"持有灵石：{stones}")

    def _selected_lot_index(self):
        item = self.list_widget.currentItem()
        if not item:
            return None
        return item.data(256)

    def _on_bid(self):
        idx = self._selected_lot_index()
        if idx is None:
            QMessageBox.information(self, "提示", "请选择一件拍品。")
            return
        lot = self.engine.auction_house_manager.get_lots()[idx]
        min_price = lot["current_price"] + 1
        amount, ok = QInputDialog.getInt(
            self, "出价", f"输入出价（最低 {min_price}）：",
            min_price, min_price, 999999
        )
        if not ok:
            return
        success, msg = self.engine.auction_house_manager.bid(idx, amount)
        self.engine.notify(msg)
        if success:
            self._refresh_list()

    def _on_settle(self):
        idx = self._selected_lot_index()
        if idx is None:
            QMessageBox.information(self, "提示", "请选择一件拍品。")
            return
        success, msg = self.engine.auction_house_manager.settle(idx)
        self.engine.notify(msg)
        if success:
            self._refresh_list()
