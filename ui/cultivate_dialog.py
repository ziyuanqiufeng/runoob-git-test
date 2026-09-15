# -*- coding: utf-8 -*-
"""闭关修炼弹窗：允许玩家自选闭关月数并查看地点加成。"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QMessageBox
)
from PySide6.QtCore import Qt


class CultivateDialog(QDialog):
    """闭关修炼界面：选择闭关时长，显示当前地点灵气与安全信息。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("闭关修炼")
        self.resize(400, 280)
        self.engine = engine
        self.player = engine.player
        self.world = engine.world

        self.layout = QVBoxLayout(self)

        # 当前地点信息
        location = engine.get_current_location()
        loc_name = location["name"] if location else "未知"
        self.loc_label = QLabel(f"当前地点：{loc_name}")
        self.loc_label.setStyleSheet("font: 14px 'Microsoft YaHei'; padding: 6px;")
        self.layout.addWidget(self.loc_label)

        # 灵气与安全信息
        spirit_bonus = engine.get_location_spirit_bonus()
        safety = engine.get_location_safety_level()
        raid_chance = engine.get_location_raid_chance()
        self.info_label = QLabel(
            f"灵气浓度：+{int(spirit_bonus * 100)}% 修炼速度\n"
            f"安全等级：{safety}/10（每月遇袭概率约 {int(raid_chance * 100)}%）"
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #2c3e50; padding: 6px;")
        self.layout.addWidget(self.info_label)

        # 闭关月数选择
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("闭关月数："))
        self.months_spin = QSpinBox()
        self.months_spin.setRange(1, 120)
        self.months_spin.setValue(12)
        self.months_spin.setSuffix(" 个月")
        self.months_spin.valueChanged.connect(self._update_estimate)
        input_layout.addWidget(self.months_spin)
        self.layout.addLayout(input_layout)

        # 预估收益
        self.estimate_label = QLabel()
        self.estimate_label.setWordWrap(True)
        self.estimate_label.setStyleSheet("color: #16a085; padding: 6px;")
        self.layout.addWidget(self.estimate_label)
        self._update_estimate()

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.cultivate_btn = QPushButton("开始闭关")
        self.cultivate_btn.setStyleSheet("font-weight: bold;")
        self.cultivate_btn.clicked.connect(self._on_cultivate)
        btn_layout.addWidget(self.cultivate_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        self.layout.addLayout(btn_layout)

    def _update_estimate(self):
        """根据当前月数估算可获得修为。"""
        months = self.months_spin.value()
        # 简化估算：使用 cultivate 的基础逻辑，不推进实际时间
        base_gain = 10 + self.player.wisdom * 2
        actual_gain = int(base_gain / self.player.cultivation_multiplier)
        spirit_bonus = self.engine.get_location_spirit_bonus()
        # 仅估算灵气加成，其他加成不计入预览
        estimated_month = int(actual_gain * (1 + spirit_bonus))
        total = estimated_month * months
        self.estimate_label.setText(
            f"预估修为收益：约 {total} 点（受天气、心境、洞府等影响会浮动）"
        )

    def _on_cultivate(self):
        """确认闭关。"""
        months = self.months_spin.value()
        if months <= 0:
            QMessageBox.warning(self, "提示", "闭关月数必须大于 0。")
            return
        self.selected_months = months
        self.accept()
