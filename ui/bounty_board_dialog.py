# -*- coding: utf-8 -*-
"""悬赏板弹窗：接取与查看悬赏任务。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox
)


class BountyBoardDialog(QDialog):
    """展示可接取的悬赏与已接取的悬赏进度。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("悬赏板")
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        self.info_label = QLabel("本月悬赏与已接取任务")
        layout.addWidget(self.info_label)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.accept_btn = QPushButton("接取")
        self.accept_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(self.accept_btn)

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
        manager = self.engine.bounty_board_manager
        manager.refresh()

        # 可接取悬赏
        for bounty in manager.get_available():
            text = (
                f"[可接取] 击杀 {bounty['count']} 只 {bounty['enemy_id']} "
                f"| 奖励 {bounty['reward_stones']} 灵石"
            )
            item = QListWidgetItem(text)
            item.setData(256, ("available", bounty["bounty_id"]))
            self.list_widget.addItem(item)

        # 已接取悬赏
        for bounty in getattr(self.engine.player, "active_bounties", []):
            text = (
                f"[进行中] 击杀 {bounty['enemy_id']} "
                f"| 进度 {bounty['progress']}/{bounty['count']} "
                f"| 奖励 {bounty['reward_stones']} 灵石"
            )
            item = QListWidgetItem(text)
            item.setData(256, ("active", bounty["bounty_id"]))
            self.list_widget.addItem(item)

        self.info_label.setText(
            f"可接取：{len(manager.get_available())} | "
            f"进行中：{len(getattr(self.engine.player, 'active_bounties', []))}"
        )

    def _selected_bounty(self):
        item = self.list_widget.currentItem()
        if not item:
            return None, None
        return item.data(256)

    def _on_accept(self):
        kind, bid = self._selected_bounty()
        if kind != "available":
            QMessageBox.information(self, "提示", "请选择一个可接取的悬赏。")
            return
        success, msg = self.engine.bounty_board_manager.accept(bid)
        self.engine.notify(msg)
        if success:
            self._refresh_list()
