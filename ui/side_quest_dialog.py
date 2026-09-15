# -*- coding: utf-8 -*-
"""支线任务弹窗：接取任务与查看进度。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox
)


class SideQuestDialog(QDialog):
    """展示当前地点可接取的支线任务与进行中的任务。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("支线任务")
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        self.info_label = QLabel("可接取 / 进行中任务")
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
        manager = self.engine.side_quest_manager
        location_id = self.engine.player.location_id

        # 可接取任务
        available = manager.get_available_quests(location_id)
        for quest in available:
            text = f"[可接取] {quest['name']} - {quest.get('description', '')}"
            item = QListWidgetItem(text)
            item.setData(256, ("available", quest["id"]))
            self.list_widget.addItem(item)

        # 进行中任务
        for qid, state in self.engine.player.active_side_quests.items():
            quest = manager.config.get(qid)
            if not quest:
                continue
            progress_parts = []
            for obj in state.get("objectives", []):
                progress = obj.get("progress", 0)
                count = obj.get("count", 1)
                progress_parts.append(f"{progress}/{count}")
            progress_text = " | ".join(progress_parts)
            text = f"[进行中] {quest['name']} - 进度：{progress_text}"
            item = QListWidgetItem(text)
            item.setData(256, ("active", qid))
            self.list_widget.addItem(item)

        self.info_label.setText(
            f"当前地点：{self.engine.get_current_location().get('name', '')} | "
            f"可接取：{len(available)}，进行中：{len(self.engine.player.active_side_quests)}"
        )

    def _selected_quest(self):
        item = self.list_widget.currentItem()
        if not item:
            return None, None
        return item.data(256)

    def _on_accept(self):
        kind, qid = self._selected_quest()
        if kind != "available":
            QMessageBox.information(self, "提示", "请选择一个可接取的任务。")
            return
        success, msg = self.engine.side_quest_manager.accept(qid)
        self.engine.notify(msg)
        if success:
            self._refresh_list()
