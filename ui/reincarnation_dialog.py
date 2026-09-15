# -*- coding: utf-8 -*-
"""
转世轮回结算弹窗。

用于玩家死亡或飞升后，展示前世成就、业力影响、可用继承点与可选继承项，
并确认转世。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QGridLayout, QMessageBox, QCheckBox,
    QGroupBox
)
from PySide6.QtCore import Qt

from game.lifespan_manager import compute_relic_chain_bonus


class ReincarnationDialog(QDialog):
    """转世结算与继承选择弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("轮回转世")
        self.resize(620, 700)

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(12)

        # 标题
        title = QLabel("<h2>一世终了，轮回再启</h2>")
        title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title)

        # 获取转世数据
        self.reincarnation_data = engine.compute_reincarnation_options()
        self.points = self.reincarnation_data["points"]
        self.options = self.reincarnation_data["options"]

        # 信息汇总区
        info_group = QGroupBox("前世因果")
        info_layout = QGridLayout(info_group)
        info_layout.addWidget(QLabel("可用继承点："), 0, 0)
        self.points_label = QLabel(f"<b>{self.points}</b>")
        info_layout.addWidget(self.points_label, 0, 1)
        info_layout.addWidget(QLabel("当前业力："), 1, 0)
        karma_text = self._karma_text(self.reincarnation_data["karma_category"])
        info_layout.addWidget(QLabel(karma_text), 1, 1)
        info_layout.addWidget(QLabel("转世次数："), 2, 0)
        info_layout.addWidget(
            QLabel(str(engine.player.reincarnation_count + 1)), 2, 1
        )
        info_layout.addWidget(QLabel("前世遗物链："), 3, 0)
        chain_bonus = compute_relic_chain_bonus(engine.player.relic_chain)
        info_layout.addWidget(
            QLabel(self._chain_bonus_text(chain_bonus)), 3, 1
        )
        self.layout.addWidget(info_group)

        # 继承选项区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.options_widget = QWidget()
        self.options_layout = QVBoxLayout(self.options_widget)
        self.options_layout.setSpacing(8)
        self.checkboxes = []
        self._build_options()
        scroll.setWidget(self.options_widget)
        self.layout.addWidget(scroll)

        # 已选消耗与确认
        bottom_layout = QHBoxLayout()
        self.cost_label = QLabel("已选消耗：0 点")
        bottom_layout.addWidget(self.cost_label)
        bottom_layout.addStretch()
        self.confirm_btn = QPushButton("确认转世")
        self.confirm_btn.clicked.connect(self._on_confirm)
        bottom_layout.addWidget(self.confirm_btn)
        self.layout.addLayout(bottom_layout)

        self._update_cost()

    def _karma_text(self, category):
        """根据业力等级返回中文描述。"""
        mapping = {
            "benevolent": "功德深厚（继承点 +3）",
            "neutral": "因果平平",
            "evil": "业力缠身（继承点 -3，可能触发负面事件）",
        }
        return mapping.get(category, "未知")

    def _chain_bonus_text(self, chain_bonus):
        """把遗物链加成字典格式化为可读文本。"""
        bits = []
        for k in ("wisdom", "luck", "constitution", "max_health"):
            v = chain_bonus.get(k, 0)
            if v:
                bits.append(f"{k}{v:+d}")
        for k in ("cultivation_speed", "breakthrough_bonus"):
            v = chain_bonus.get(k, 0.0)
            if v:
                bits.append(f"{k}{v:+.0%}")
        return "、".join(bits) if bits else "（暂无，转世后无链之加持）"

    def _build_options(self):
        """构建继承选项卡片。"""
        for opt in self.options:
            card = QGroupBox(opt["name"])
            card.setCheckable(False)
            card_layout = QGridLayout(card)

            desc = QLabel(opt["description"])
            desc.setWordWrap(True)
            card_layout.addWidget(desc, 0, 0, 1, 2)

            card_layout.addWidget(QLabel(f"消耗：{opt['cost']} 点"), 1, 0)
            card_layout.addWidget(
                QLabel(f"剩余可选：{opt['remaining_times']} 次"), 1, 1
            )

            checkbox = QCheckBox("选择此继承")
            checkbox.setEnabled(opt["available"])
            checkbox.setProperty("option_id", opt["id"])
            checkbox.setProperty("option_cost", opt["cost"])
            checkbox.stateChanged.connect(self._update_cost)
            self.checkboxes.append(checkbox)
            card_layout.addWidget(checkbox, 2, 0, 1, 2)

            if not opt["available"]:
                card.setStyleSheet("QGroupBox { color: #999; }")

            self.options_layout.addWidget(card)

    def _update_cost(self):
        """更新已选消耗与确认按钮状态。"""
        total = 0
        for cb in self.checkboxes:
            if cb.isChecked():
                total += cb.property("option_cost")
        self.cost_label.setText(f"已选消耗：{total} / {self.points} 点")
        self.confirm_btn.setEnabled(total <= self.points and total > 0)
        if total > self.points:
            self.cost_label.setStyleSheet("color: #e74c3c;")
        else:
            self.cost_label.setStyleSheet("color: #2c3e50;")

    def _on_confirm(self):
        """确认转世，返回选择的继承项。"""
        selected = []
        for cb in self.checkboxes:
            if cb.isChecked():
                selected.append(cb.property("option_id"))
        if not selected:
            QMessageBox.warning(self, "未选择", "请至少选择一项继承。")
            return
        self.selected_options = selected
        self.accept()

    def get_selected_options(self):
        """获取玩家选择的继承项 ID 列表。"""
        return getattr(self, "selected_options", [])
