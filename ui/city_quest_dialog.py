# -*- coding: utf-8 -*-
"""
城主府动态任务弹窗：展示当前城池可接任务与已接任务进度。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt


class CityQuestDialog(QDialog):
    """城主府任务交互弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player

        self.setWindowTitle("城主府任务")
        self.resize(600, 450)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("<h2>城主府布告栏</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 可接任务
        layout.addWidget(QLabel("<b>可接取任务</b>"))
        self.available_list = QListWidget()
        self.available_list.setToolTip("双击或选中后点击接取。")
        layout.addWidget(self.available_list)

        # 已接任务
        layout.addWidget(QLabel("<b>已接取任务</b>"))
        self.active_list = QListWidget()
        self.active_list.setToolTip("显示当前进行中的城池任务进度。")
        layout.addWidget(self.active_list)

        # 按钮区
        btn_layout = QHBoxLayout()
        self.accept_btn = QPushButton("接取选中任务")
        self.accept_btn.clicked.connect(self._accept_selected)
        btn_layout.addWidget(self.accept_btn)

        self.refresh_btn = QPushButton("刷新任务")
        self.refresh_btn.setToolTip("重新生成一批城池任务（每月限一次或消耗少量灵石）。")
        self.refresh_btn.clicked.connect(self._refresh_quests)
        btn_layout.addWidget(self.refresh_btn)

        layout.addLayout(btn_layout)

        self._refresh_lists()

    def _refresh_lists(self):
        """刷新可接与已接任务列表。"""
        # 获取当前城池任务（自动按城池生成）
        quests = self.engine.get_city_quests()

        # 可接任务
        self.available_list.clear()
        for quest in quests:
            qid = quest["id"]
            if qid in self.player.active_city_quests:
                continue
            text = f"{quest['name']} — {quest['description']} " \
                   f"（奖励：修为+{quest['reward']['qi']} 灵石+{quest['reward']['spirit_stone']}）"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, qid)
            self.available_list.addItem(item)

        # 已接任务
        self.active_list.clear()
        for qid, progress in self.player.active_city_quests.items():
            quest = self.engine._get_active_city_quest(qid)
            if not quest:
                continue
            text = f"{quest['name']} — 进度 {progress}/{quest['count']}"
            self.active_list.addItem(text)

    def _accept_selected(self):
        """接取选中的可接任务。"""
        item = self.available_list.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选择一个任务。")
            return
        quest_id = item.data(Qt.UserRole)
        if self.engine.accept_city_quest(quest_id):
            QMessageBox.information(self, "接取成功", "任务已接取。")
        self._refresh_lists()

    def _refresh_quests(self):
        """手动刷新任务池。"""
        # 简单实现：直接重新生成，后续可加入每月限制或灵石消耗
        reply = QMessageBox.question(
            self,
            "刷新任务",
            "刷新将替换当前所有未接取的任务，是否继续？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.engine.get_city_quests(refresh=True)
        self._refresh_lists()
