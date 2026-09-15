# -*- coding: utf-8 -*-
"""
客栈弹窗：提供歇息与打听消息功能。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QComboBox
)
from PySide6.QtCore import Qt


class InnDialog(QDialog):
    """客栈交互弹窗。"""

    def __init__(self, engine, inn_name="客栈", parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.inn_name = inn_name

        self.setWindowTitle(inn_name)
        self.resize(420, 280)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel(f"<h2>{inn_name}</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 描述
        desc = QLabel("客栈不仅是歇脚之处，也是消息汇聚之地。")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 13px; padding: 6px;")
        layout.addWidget(desc)

        # 玩家灵石显示
        self.money_label = QLabel()
        self.money_label.setAlignment(Qt.AlignCenter)
        self.money_label.setStyleSheet("font-size: 14px; padding: 4px;")
        layout.addWidget(self.money_label)

        # 歇息按钮
        self.rest_btn = QPushButton("歇息一月（50 灵石）")
        self.rest_btn.setToolTip("恢复全部气血与心境，并推进 1 个月时间。")
        self.rest_btn.clicked.connect(self._rest)
        layout.addWidget(self.rest_btn)

        # 打听消息区域
        rumor_layout = QHBoxLayout()
        self.rumor_combo = QComboBox()
        self.rumor_combo.addItem("随机打听", None)
        self.rumor_combo.addItem("坊市传闻", "market")
        self.rumor_combo.addItem("秘境线索", "secret")
        self.rumor_combo.addItem("人物动向", "npc")
        self.rumor_combo.addItem("大事预警", "event")
        self.rumor_combo.addItem("坊间闲谈", "trivia")
        rumor_layout.addWidget(QLabel("打听方向："))
        rumor_layout.addWidget(self.rumor_combo, 1)

        self.rumor_btn = QPushButton("打听消息")
        self.rumor_btn.setToolTip("花费灵石向客栈掌柜或酒客打听消息。")
        self.rumor_btn.clicked.connect(self._gather_rumor)
        rumor_layout.addWidget(self.rumor_btn)
        layout.addLayout(rumor_layout)

        # 关闭按钮
        close_btn = QPushButton("离开")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        self._refresh_money()

    def _refresh_money(self):
        """刷新灵石显示。"""
        stones = self.player.count_item("spirit_stone")
        self.money_label.setText(f"当前灵石：<b>{stones}</b>")

    def _rest(self):
        """调用引擎歇息。"""
        if self.engine.rest_at_inn():
            self._refresh_money()
            self.accept()

    def _gather_rumor(self):
        """花费灵石打听消息。"""
        category = self.rumor_combo.currentData()
        rumor = self.engine.gather_rumor_at_inn(category=category)
        self._refresh_money()
        if rumor:
            # 直接弹窗展示情报内容
            cat_label = {
                "market": "坊市传闻",
                "secret": "秘境线索",
                "npc": "人物动向",
                "event": "大事预警",
                "trivia": "坊间闲谈",
            }.get(rumor.get("category"), "传闻")
            QMessageBox.information(
                self,
                cat_label,
                rumor.get("description", "你听到了一些似是而非的消息。")
            )
