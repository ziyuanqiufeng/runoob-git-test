# -*- coding: utf-8 -*-
"""
玩家摆摊弹窗：上架、下架物品与领取收入。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QListWidget, QListWidgetItem, QComboBox,
    QSpinBox
)
from PySide6.QtCore import Qt


class StallDialog(QDialog):
    """玩家摆摊交互弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player

        self.setWindowTitle("坊市摆摊")
        self.resize(480, 500)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("<h2>坊市摆摊</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 说明
        desc = QLabel("将背包物品上架到坊市，每月有概率被其他修士买走。")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(desc)

        # 待领取收入
        self.revenue_label = QLabel()
        self.revenue_label.setAlignment(Qt.AlignCenter)
        self.revenue_label.setStyleSheet("font-size: 14px; padding: 6px;")
        layout.addWidget(self.revenue_label)

        # 领取收入按钮
        self.collect_btn = QPushButton("领取摆摊收入")
        self.collect_btn.clicked.connect(self._on_collect)
        layout.addWidget(self.collect_btn)

        # 摊位商品列表
        layout.addWidget(QLabel("当前摊位："))
        self.stall_list = QListWidget()
        self.stall_list.setSpacing(4)
        layout.addWidget(self.stall_list)

        # 下架按钮
        self.cancel_btn = QPushButton("下架选中商品")
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)

        # 上架区域
        layout.addWidget(QLabel("上架新商品："))
        setup_layout = QHBoxLayout()
        self.item_combo = QComboBox()
        self.item_combo.setMinimumWidth(140)
        setup_layout.addWidget(self.item_combo)

        setup_layout.addWidget(QLabel("单价："))
        self.price_spin = QSpinBox()
        self.price_spin.setRange(1, 999999)
        self.price_spin.setValue(10)
        setup_layout.addWidget(self.price_spin)

        setup_layout.addWidget(QLabel("数量："))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 999)
        self.count_spin.setValue(1)
        setup_layout.addWidget(self.count_spin)

        self.setup_btn = QPushButton("上架")
        self.setup_btn.clicked.connect(self._on_setup)
        setup_layout.addWidget(self.setup_btn)
        layout.addLayout(setup_layout)

        # 关闭按钮
        close_btn = QPushButton("离开")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        self._refresh()

    def _get_inventory_items(self):
        """获取背包中可出售的物品 ID 与数量映射。"""
        counts = {}
        names = {}
        for item in self.player.inventory:
            counts[item.id] = counts.get(item.id, 0) + item.count
            names[item.id] = item.name
        return counts, names

    def _refresh(self):
        """刷新收入、摊位列表与可上架物品下拉框。"""
        revenue = self.engine.stall_manager.get_pending_revenue()
        self.revenue_label.setText(f"待领取收入：<b>{revenue}</b> 灵石")
        self.collect_btn.setEnabled(revenue > 0)

        # 刷新摊位列表
        self.stall_list.clear()
        for entry in self.engine.stall_manager.get_stall_items():
            item = self.engine.item_library.create(entry["item_id"])
            name = getattr(item, "name", entry["item_id"])
            item_text = (
                f"{name} ×{entry['count']}　"
                f"单价：{entry['price']} 灵石"
            )
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, entry)
            self.stall_list.addItem(list_item)

        # 刷新可上架物品
        current_id = self.item_combo.currentData()
        self.item_combo.clear()
        counts, names = self._get_inventory_items()
        for item_id, count in counts.items():
            display = f"{names.get(item_id, item_id)} ({count})"
            self.item_combo.addItem(display, item_id)
        if current_id and self.item_combo.findData(current_id) >= 0:
            self.item_combo.setCurrentIndex(self.item_combo.findData(current_id))

    def _on_setup(self):
        """上架选中物品。"""
        item_id = self.item_combo.currentData()
        if not item_id:
            QMessageBox.warning(self, "无物品", "背包中没有可上架的物品。")
            return

        price = self.price_spin.value()
        count = self.count_spin.value()
        ok, msg = self.engine.setup_stall(item_id, price, count)
        if ok:
            QMessageBox.information(self, "上架成功", msg)
        else:
            QMessageBox.warning(self, "上架失败", msg)
        self._refresh()

    def _on_cancel(self):
        """下架选中商品。"""
        item = self.stall_list.currentItem()
        if not item:
            QMessageBox.warning(self, "未选择", "请先选择要下架的商品。")
            return

        entry = item.data(Qt.UserRole)
        ok, msg = self.engine.stall_manager.cancel_stall(
            entry["item_id"], entry["price"]
        )
        if ok:
            QMessageBox.information(self, "下架成功", msg)
        else:
            QMessageBox.warning(self, "下架失败", msg)
        self._refresh()

    def _on_collect(self):
        """领取摆摊收入。"""
        amount = self.engine.collect_stall_revenue()
        if amount > 0:
            QMessageBox.information(
                self, "领取成功", f"已领取 {amount} 灵石。"
            )
        self._refresh()
