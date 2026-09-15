# -*- coding: utf-8 -*-
"""图鉴弹窗：展示已收录的敌人、物品、技能。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QLabel
)


class CompendiumDialog(QDialog):
    """分类展示玩家图鉴收集进度。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("图鉴")
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        self.info_label = QLabel(self._info_text())
        layout.addWidget(self.info_label)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.enemy_btn = QPushButton("敌人")
        self.enemy_btn.clicked.connect(lambda: self._show_category("enemy"))
        btn_layout.addWidget(self.enemy_btn)

        self.item_btn = QPushButton("物品")
        self.item_btn.clicked.connect(lambda: self._show_category("item"))
        btn_layout.addWidget(self.item_btn)

        self.skill_btn = QPushButton("技能")
        self.skill_btn.clicked.connect(lambda: self._show_category("skill"))
        btn_layout.addWidget(self.skill_btn)

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)
        self._show_category("enemy")

    def _info_text(self):
        completion = self.engine.compendium_manager.get_completion()
        return (
            f"敌人：{completion['enemies']} | "
            f"物品：{completion['items']} | "
            f"技能：{completion['skills']}"
        )

    def _show_category(self, category):
        self.list_widget.clear()
        engine = self.engine
        if category == "enemy":
            # 敌人图鉴：enemy_id -> 击杀数
            for enemy_id, count in sorted(engine.player.bestiary.items()):
                enemy_data = engine.enemy_library.get(enemy_id)
                name = enemy_data["name"] if enemy_data else enemy_id
                text = f"{name} - 击杀 {count} 次"
                from PySide6.QtWidgets import QListWidgetItem
                self.list_widget.addItem(QListWidgetItem(text))
        elif category == "item":
            for item_id in engine.player.item_compendium:
                item = engine.item_library.get(item_id)
                name = item.name if item else item_id
                self.list_widget.addItem(QListWidgetItem(name))
        elif category == "skill":
            for skill_id in engine.player.skill_compendium:
                skill = engine.skill_library.get(skill_id)
                name = skill.name if skill else skill_id
                self.list_widget.addItem(QListWidgetItem(name))
        self.info_label.setText(self._info_text())
