from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem
)


class QuestDialog(QDialog):
    """任务管理弹窗，显示进行中的任务详情并支持放弃。"""

    def __init__(self, player, quest_library, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("任务")
        self.resize(450, 350)
        self.player = player
        self.quest_library = quest_library
        self.engine = engine

        layout = QVBoxLayout(self)

        # 任务列表
        self.quest_list = QListWidget()
        self.quest_list.itemClicked.connect(self._on_quest_selected)
        layout.addWidget(self.quest_list)

        # 详情
        self.info_label = QLabel("请选择任务")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # 按钮
        btn_layout = QHBoxLayout()
        self.abandon_btn = QPushButton("放弃任务")
        self.abandon_btn.clicked.connect(self._on_abandon)
        self.abandon_btn.setEnabled(False)
        btn_layout.addWidget(self.abandon_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.selected_quest_id = None
        self._refresh_list()

    def _refresh_list(self):
        """刷新任务列表。"""
        self.quest_list.clear()
        self.selected_quest_id = None
        self.abandon_btn.setEnabled(False)
        self.info_label.setText("请选择任务")

        if not self.player.quest_progress:
            item = QListWidgetItem("当前没有进行中的任务")
            self.quest_list.addItem(item)
            return

        for quest_id, progress in self.player.quest_progress.items():
            quest = self.quest_library.get(quest_id)
            if quest:
                display = f"{quest.name} ({progress}/{quest.count})"
                item = QListWidgetItem(display)
                item.setData(256, quest_id)
                item.setToolTip(quest.description)
                self.quest_list.addItem(item)

    def _on_quest_selected(self, item):
        """选中任务时显示详情。"""
        quest_id = item.data(256)
        if not quest_id:
            return
        self.selected_quest_id = quest_id
        quest = self.quest_library.get(quest_id)
        progress = self.player.quest_progress.get(quest_id, 0)
        self.info_label.setText(
            f"任务：{quest.name}\n描述：{quest.description}\n进度：{progress}/{quest.count}\n类型：{quest.target_type}"
        )
        self.abandon_btn.setEnabled(True)

    def _on_abandon(self):
        """放弃选中的任务。"""
        if not self.selected_quest_id:
            return
        self.engine.abandon_quest(self.selected_quest_id)
        self._refresh_list()
