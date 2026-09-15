from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QTabWidget, QWidget, QListWidget,
    QListWidgetItem
)


class QuestLogDialog(QDialog):
    """任务日志弹窗，显示已完成和进行中的任务详情。"""

    def __init__(self, player, quest_library, parent=None):
        super().__init__(parent)
        self.setWindowTitle("任务日志")
        self.resize(500, 450)
        self.player = player
        self.quest_library = quest_library

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # 进行中标签
        self.active_tab = QWidget()
        self._setup_active_tab()
        self.tabs.addTab(self.active_tab, f"进行中 ({len(player.quest_progress)})")

        # 已完成标签
        self.completed_tab = QWidget()
        self._setup_completed_tab()
        self.tabs.addTab(self.completed_tab, f"已完成 ({len(player.completed_quests)})")

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _setup_active_tab(self):
        layout = QVBoxLayout(self.active_tab)
        self.active_list = QListWidget()
        layout.addWidget(self.active_list)
        self.active_detail = QLabel("请选择任务查看详情")
        self.active_detail.setWordWrap(True)
        layout.addWidget(self.active_detail)

        for quest_id, progress in self.player.quest_progress.items():
            quest = self.quest_library.get(quest_id)
            if quest:
                item = QListWidgetItem(f"{quest.name} ({progress}/{quest.count})")
                item.setData(256, quest_id)
                self.active_list.addItem(item)

        self.active_list.itemClicked.connect(self._on_active_selected)

    def _setup_completed_tab(self):
        layout = QVBoxLayout(self.completed_tab)
        self.completed_list = QListWidget()
        layout.addWidget(self.completed_list)
        self.completed_detail = QLabel("请选择任务查看详情")
        self.completed_detail.setWordWrap(True)
        layout.addWidget(self.completed_detail)

        for quest_id in self.player.completed_quests:
            quest = self.quest_library.get(quest_id)
            if quest:
                item = QListWidgetItem(quest.name)
                item.setData(256, quest_id)
                self.completed_list.addItem(item)

        self.completed_list.itemClicked.connect(self._on_completed_selected)

    def _on_active_selected(self, item):
        quest_id = item.data(256)
        quest = self.quest_library.get(quest_id)
        progress = self.player.quest_progress.get(quest_id, 0)
        target_text = "击杀" if quest.target_type == "kill" else "收集"
        self.active_detail.setText(
            f"【{quest.name}】\n{quest.description}\n\n"
            f"目标：{target_text} {quest.target_id} {quest.count} 个/次\n"
            f"当前进度：{progress}/{quest.count}"
        )

    def _on_completed_selected(self, item):
        quest_id = item.data(256)
        quest = self.quest_library.get(quest_id)
        target_text = "击杀" if quest.target_type == "kill" else "收集"
        reward_items = ", ".join(quest.reward.get("items", [])) or "无"
        self.completed_detail.setText(
            f"【{quest.name}】\n{quest.description}\n\n"
            f"目标：{target_text} {quest.target_id} {quest.count} 个/次\n"
            f"奖励：修为 +{quest.reward.get('qi', 0)}，物品 {reward_items}"
        )
