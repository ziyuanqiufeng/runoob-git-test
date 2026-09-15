# -*- coding: utf-8 -*-
"""心法管理弹窗：学习、装备、卸下心法。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox
)


class MindMethodDialog(QDialog):
    """显示玩家已学心法与可学心法，并支持装备操作。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("心法")
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        # 当前装备心法
        equipped = engine.player.equipped_mind_method
        equipped_name = "无"
        if equipped:
            cfg = engine.mind_method_manager.config.get(equipped)
            equipped_name = cfg["name"] if cfg else equipped
        self.equipped_label = QLabel(f"当前装备：{equipped_name}")
        layout.addWidget(self.equipped_label)

        # 心法列表
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # 按钮区
        btn_layout = QHBoxLayout()
        self.equip_btn = QPushButton("装备")
        self.equip_btn.clicked.connect(self._on_equip)
        btn_layout.addWidget(self.equip_btn)

        self.unequip_btn = QPushButton("卸下")
        self.unequip_btn.clicked.connect(self._on_unequip)
        btn_layout.addWidget(self.unequip_btn)

        self.learn_btn = QPushButton("学习新心法")
        self.learn_btn.clicked.connect(self._on_learn)
        btn_layout.addWidget(self.learn_btn)

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

        self._refresh_list()

    def _refresh_list(self):
        """刷新心法列表。"""
        self.list_widget.clear()
        manager = self.engine.mind_method_manager
        # 已学心法
        for mid in self.engine.player.learned_mind_methods:
            method = manager.config.get(mid)
            if not method:
                continue
            equipped_mark = " [已装备]" if mid == self.engine.player.equipped_mind_method else ""
            text = f"{method['name']}{equipped_mark} - {method.get('description', '')}"
            item = QListWidgetItem(text)
            item.setData(256, mid)  # 用户角色数据存心法 ID
            self.list_widget.addItem(item)

    def _selected_method_id(self):
        """获取当前选中心法 ID。"""
        item = self.list_widget.currentItem()
        if not item:
            return None
        return item.data(256)

    def _on_equip(self):
        mid = self._selected_method_id()
        if not mid:
            QMessageBox.information(self, "提示", "请先选择一门心法。")
            return
        ok, msg = self.engine.mind_method_manager.equip(mid)
        self.engine.notify(msg)
        self._refresh_list()
        self._refresh_equipped_label()

    def _on_unequip(self):
        ok, msg = self.engine.mind_method_manager.unequip()
        self.engine.notify(msg)
        self._refresh_list()
        self._refresh_equipped_label()

    def _on_learn(self):
        """弹出可学心法列表供选择。"""
        manager = self.engine.mind_method_manager
        learnable = [
            m for m in manager.config.get_all()
            if m["id"] not in self.engine.player.learned_mind_methods
            and manager.config.can_learn(m["id"], self.engine.player)
        ]
        if not learnable:
            QMessageBox.information(self, "提示", "当前没有可学的心法。")
            return
        # 简单使用输入框选择（实际可扩展为列表弹窗）
        from PySide6.QtWidgets import QInputDialog
        names = [m["name"] for m in learnable]
        name, ok = QInputDialog.getItem(self, "学习心法", "可选心法：", names, 0, False)
        if not ok:
            return
        method_id = next(m["id"] for m in learnable if m["name"] == name)
        success, msg = manager.learn(method_id)
        self.engine.notify(msg)
        if success:
            self._refresh_list()

    def _refresh_equipped_label(self):
        equipped = self.engine.player.equipped_mind_method
        equipped_name = "无"
        if equipped:
            cfg = self.engine.mind_method_manager.config.get(equipped)
            equipped_name = cfg["name"] if cfg else equipped
        self.equipped_label.setText(f"当前装备：{equipped_name}")
