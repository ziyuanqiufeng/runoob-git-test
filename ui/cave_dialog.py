# -*- coding: utf-8 -*-
"""洞府租赁与闭关修炼弹窗。"""

import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QGroupBox,
    QSpinBox, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt


# 洞府效果字段 → 中文显示名（配置驱动，支持策划/美术直接维护）
_EFFECT_LABELS = {}
_EFFECT_COLORS = {}


def _load_effect_labels(config_dir="config"):
    """从配置加载效果标签与徽章颜色。"""
    global _EFFECT_LABELS, _EFFECT_COLORS
    path = os.path.join(config_dir, "cave_effect_labels.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _EFFECT_LABELS = data.get("labels", {})
        _EFFECT_COLORS = data.get("badge_colors", {})
    else:
        _EFFECT_LABELS = {}
        _EFFECT_COLORS = {}


_load_effect_labels()

_ELEMENT_DAMAGE_SUFFIX = "_damage_bonus"
_ELEMENT_RESIST_SUFFIX = "_resist_bonus"


def _format_effect_key(key):
    """将未知效果 key 格式化为可读中文，优先使用配置映射表。"""
    if key in _EFFECT_LABELS:
        return _EFFECT_LABELS[key]
    # 匹配 *_damage_bonus / *_resist_bonus，自动提取元素名
    if key.endswith(_ELEMENT_DAMAGE_SUFFIX):
        element = key[: -len(_ELEMENT_DAMAGE_SUFFIX)]
        return f"{element}属性伤害"
    if key.endswith(_ELEMENT_RESIST_SUFFIX):
        element = key[: -len(_ELEMENT_RESIST_SUFFIX)]
        return f"{element}属性抗性"
    # 兜底：下划线转空格，首字母大写
    return key.replace("_", " ").title()


def _effect_color(key):
    """获取效果对应的徽章颜色。"""
    return _EFFECT_COLORS.get(key, _EFFECT_COLORS.get("default", "#7f8c8d"))


class CaveEffectBadge(QLabel):
    """彩色小徽章，用于展示洞府效果。"""

    def __init__(self, text, color, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"QLabel {{ color: #fff; background-color: {color}; "
            f"border-radius: 8px; padding: 2px 8px; font-size: 11px; }}"
        )
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class CaveListItemWidget(QWidget):
    """洞府列表自定义项：名称/租金/效果徽章/描述。"""

    def __init__(self, cave, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # 第一行：名称 + 租金 + 租期
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        name_label = QLabel(f"<b>{cave['name']}</b>")
        name_label.setStyleSheet("font-size: 14px;")
        top_layout.addWidget(name_label)

        remaining = cave.get("remaining_months", 0)
        if remaining > 0:
            lease_label = QLabel(f"已租赁 {remaining} 个月")
            lease_label.setStyleSheet("color: #27ae60; font-size: 12px;")
            top_layout.addWidget(lease_label)

        top_layout.addStretch()

        rent_label = QLabel(f"{cave['rent_per_month']} 灵石/月")
        rent_label.setStyleSheet("color: #f39c12; font-size: 12px;")
        top_layout.addWidget(rent_label)
        layout.addLayout(top_layout)

        # 第二行：效果徽章
        badge_layout = QHBoxLayout()
        badge_layout.setSpacing(6)
        effects = cave.get("effects", {})
        if effects:
            for key, value in effects.items():
                label_text = _format_effect_key(key)
                badge = CaveEffectBadge(
                    f"{label_text} +{value*100:.0f}%",
                    _effect_color(key)
                )
                badge_layout.addWidget(badge)
            badge_layout.addStretch()
        else:
            badge_layout.addWidget(QLabel("无特殊效果"))
            badge_layout.addStretch()
        layout.addLayout(badge_layout)

        # 第三行：描述
        desc_label = QLabel(cave.get("description", ""))
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #555; font-size: 12px;")
        layout.addWidget(desc_label)


class CaveDialog(QDialog):
    """洞府租赁与闭关修炼交互弹窗。"""

    def __init__(self, engine, location_id=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.location_id = location_id or self.player.location_id
        location = self.engine.world.get_location(self.location_id) or {}
        city_name = location.get("name", self.location_id)
        self.setWindowTitle(f"【{city_name}·洞府】")
        self.resize(520, 560)

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)

        # 顶部信息
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            "font-size: 14px; padding: 8px; background: #f8f9fa; border-radius: 6px;"
        )
        self.layout.addWidget(self.info_label)

        # 当前生效加成汇总
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            "font-size: 12px; padding: 6px; background: #eafaf1; "
            "border: 1px solid #a3e4c4; border-radius: 6px; color: #1e8449;"
        )
        self.layout.addWidget(self.summary_label)

        # 洞府列表
        cave_group = QGroupBox("城中洞府")
        cave_layout = QVBoxLayout(cave_group)
        self.cave_list = QListWidget()
        self.cave_list.setSpacing(4)
        self.cave_list.currentRowChanged.connect(self._on_cave_selected)
        cave_layout.addWidget(self.cave_list)

        # 租赁区域
        rent_layout = QHBoxLayout()
        rent_layout.addWidget(QLabel("租赁月数："))
        self.rent_spin = QSpinBox()
        self.rent_spin.setRange(1, 12)
        self.rent_spin.setValue(1)
        rent_layout.addWidget(self.rent_spin)
        self.rent_btn = QPushButton("租赁洞府")
        self.rent_btn.clicked.connect(self._on_rent)
        rent_layout.addWidget(self.rent_btn)
        cave_layout.addLayout(rent_layout)
        self.layout.addWidget(cave_group)

        # 闭关区域
        self.closed_door_group = QGroupBox("闭关修炼")
        cd_layout = QVBoxLayout(self.closed_door_group)
        self.closed_door_label = QLabel("选择洞府后可开始闭关。")
        self.closed_door_label.setWordWrap(True)
        cd_layout.addWidget(self.closed_door_label)

        months_layout = QHBoxLayout()
        months_layout.addWidget(QLabel("闭关月数："))
        self.cd_spin = QSpinBox()
        self.cd_spin.setRange(1, 12)
        self.cd_spin.setValue(1)
        months_layout.addWidget(self.cd_spin)
        self.cd_btn = QPushButton("开始闭关")
        self.cd_btn.clicked.connect(self._on_start_closed_door)
        months_layout.addWidget(self.cd_btn)
        cd_layout.addLayout(months_layout)
        self.layout.addWidget(self.closed_door_group)

        # 当前闭关状态
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #2c3e50; padding: 6px;")
        self.layout.addWidget(self.status_label)

        # 关闭按钮
        close_btn = QPushButton("离开")
        close_btn.clicked.connect(self.reject)
        self.layout.addWidget(close_btn)

        self._selected_cave_id = None
        self._caves = []
        self._refresh()

    def _refresh(self):
        """刷新洞府列表与玩家状态。"""
        stones = self.player.count_item("spirit_stone")
        self.info_label.setText(f"当前灵石：<b>{stones}</b>")
        self._update_summary()

        self._caves = self.engine.get_cave_info(self.location_id)
        self.cave_list.clear()
        for cave in self._caves:
            item = QListWidgetItem(self.cave_list)
            item.setData(Qt.UserRole, cave["id"])
            item_widget = CaveListItemWidget(cave)
            item.setSizeHint(item_widget.sizeHint())
            self.cave_list.addItem(item)
            self.cave_list.setItemWidget(item, item_widget)

        if self._caves:
            self.cave_list.setCurrentRow(0)

        # 刷新闭关状态
        if self.player.closed_door_remaining > 0:
            cave_id = getattr(self.player, "closed_door_cave_id", None)
            cave_name = "未知洞府"
            for cave in self._caves:
                if cave["id"] == cave_id:
                    cave_name = cave["name"]
                    break
            self.status_label.setText(
                f"正在【{cave_name}】闭关中，剩余 {self.player.closed_door_remaining} 个月。"
            )
            self.cd_btn.setEnabled(False)
        else:
            self.status_label.setText("当前未闭关。")
            self.cd_btn.setEnabled(True)

    def _update_summary(self):
        """刷新当前生效的洞府加成汇总。"""
        total_bonus = self.engine.cave_manager.get_cultivation_bonus()
        active_leases = [
            (cave_id, lease)
            for cave_id, lease in self.player.cave_leases.items()
            if lease.get("remaining_months", 0) > 0
        ]
        if not active_leases:
            self.summary_label.setText("当前无生效洞府加成。")
            return

        parts = []
        for cave_id, lease in active_leases:
            cave = self.engine.cave_manager.config.get_cave(cave_id)
            name = cave["name"] if cave else cave_id
            remaining = lease.get("remaining_months", 0)
            parts.append(f"【{name}】剩余 {remaining} 个月")

        self.summary_label.setText(
            f"生效洞府：{'，'.join(parts)} | "
            f"修炼速度合计 +{total_bonus*100:.0f}%"
        )

    def _on_cave_selected(self, row):
        """选中洞府时更新选中 ID 与闭关提示。"""
        if row < 0 or row >= len(self._caves):
            self._selected_cave_id = None
            return
        self._selected_cave_id = self._caves[row]["id"]
        cave = self._caves[row]
        bonus = cave.get("effects", {}).get("closed_door_qi_bonus", 0)
        self.closed_door_label.setText(
            f"在【{cave['name']}】闭关，每月基础修为收益提升 {bonus*100:.0f}%。"
        )

    def _on_rent(self):
        """租赁选中洞府。"""
        if not self._selected_cave_id:
            QMessageBox.warning(self, "未选择", "请先选择要租赁的洞府。")
            return
        months = self.rent_spin.value()
        ok, msg = self.engine.rent_cave(self._selected_cave_id, months)
        if ok:
            QMessageBox.information(self, "租赁成功", msg)
        else:
            QMessageBox.warning(self, "租赁失败", msg)
        self._refresh()

    def _on_start_closed_door(self):
        """在选中洞府开始闭关。"""
        if not self._selected_cave_id:
            QMessageBox.warning(self, "未选择", "请先选择要闭关的洞府。")
            return
        months = self.cd_spin.value()
        ok, msg, expected = self.engine.start_closed_door_cultivation(
            self._selected_cave_id, months
        )
        if ok:
            QMessageBox.information(
                self, "开始闭关",
                f"{msg}\n预计总收益：{expected} 点修为。"
            )
        else:
            QMessageBox.warning(self, "无法闭关", msg)
        self._refresh()
