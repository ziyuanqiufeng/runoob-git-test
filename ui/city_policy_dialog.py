# -*- coding: utf-8 -*-
"""城池治理弹窗：城主竞选、政策颁布与生效政策查看。"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QWidget, QGroupBox,
    QGridLayout
)
from PySide6.QtCore import Qt

from game.city_policy_manager import CityPolicyConfig


class CityPolicyDialog(QDialog):
    """城池政策与城主竞选交互弹窗。"""

    def __init__(self, engine, city_id=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.city_id = city_id or self.player.location_id
        location = self.engine.world.get_location(self.city_id) or {}
        city_name = location.get("name", self.city_id)
        self.setWindowTitle(f"【{city_name}·城主府】")
        self.resize(520, 560)

        self.config = CityPolicyConfig()
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)

        # 顶部城主状态
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "font-size: 14px; padding: 8px; background: #f8f9fa; border-radius: 6px;"
        )
        self.layout.addWidget(self.status_label)

        # 竞选按钮
        self.campaign_btn = QPushButton("参与城主竞选")
        self.campaign_btn.setToolTip("消耗灵石与城池声望参与竞选，成功后成为城主。")
        self.campaign_btn.clicked.connect(self._on_campaign)
        self.layout.addWidget(self.campaign_btn)

        # 生效政策区域
        active_group = QGroupBox("生效中的政策")
        active_layout = QVBoxLayout(active_group)
        self.active_list = QListWidget()
        self.active_list.setSpacing(4)
        active_layout.addWidget(self.active_list)
        self.layout.addWidget(active_group)

        # 可颁布政策区域（仅城主可见）
        self.policy_group = QGroupBox("可颁布政策")
        policy_layout = QVBoxLayout(self.policy_group)
        self.policy_list = QListWidget()
        self.policy_list.setSpacing(4)
        policy_layout.addWidget(self.policy_list)

        desc = QLabel("颁布政策需消耗灵石与城池声望，同时生效政策有数量上限。")
        desc.setStyleSheet("color: #666; font-size: 11px;")
        desc.setWordWrap(True)
        policy_layout.addWidget(desc)

        self.enact_btn = QPushButton("颁布选中政策")
        self.enact_btn.clicked.connect(self._on_enact)
        policy_layout.addWidget(self.enact_btn)
        self.layout.addWidget(self.policy_group)

        # 关闭按钮
        close_btn = QPushButton("离开")
        close_btn.clicked.connect(self.reject)
        self.layout.addWidget(close_btn)

        self._refresh()

    def _refresh(self):
        """刷新城主状态、政策列表。"""
        info = self.engine.get_city_policy_info(self.city_id)
        city_rep = self.player.city_reputation.get(self.city_id, 0)
        stones = self.player.count_item("spirit_stone")

        if info["is_mayor"]:
            until = info["mayor_until"]
            status_text = (
                f"你当前是本城城主（任期至世界第 {until} 个月）。\n"
                f"城池声望：{city_rep}　灵石：{stones}"
            )
        else:
            can, reason = self.engine._get_city_policy_manager(self.city_id).can_campaign()
            status_text = (
                f"你并非本城城主。城池声望：{city_rep}　灵石：{stones}\n"
            )
            if not can:
                status_text += f"暂时无法竞选：{reason}"
        self.status_label.setText(status_text)

        self.campaign_btn.setEnabled(not info["is_mayor"])
        self.policy_group.setEnabled(info["is_mayor"])

        # 刷新生效政策
        self.active_list.clear()
        for policy in info["active"]:
            item = QListWidgetItem(
                f"{policy['name']}（剩余 {policy['remaining_months']} 个月）\n"
                f"{policy['description']}"
            )
            self.active_list.addItem(item)

        # 刷新可颁布政策
        self.policy_list.clear()
        if info["is_mayor"]:
            mgr = self.engine._get_city_policy_manager(self.city_id)
            for policy in self.config.get_policies():
                pid = policy["id"]
                cost = policy.get("cost", {})
                can, reason = mgr.can_enact_policy(pid)
                status = "" if can else f"[{reason}]"
                item = QListWidgetItem(
                    f"{policy['name']} {status}\n"
                    f"费用：灵石 {cost.get('spirit_stone', 0)} "
                    f"声望 {cost.get('reputation', 0)} | "
                    f"持续 {policy.get('duration_months', 1)} 个月"
                )
                item.setData(Qt.UserRole, pid)
                item.setToolTip(policy.get("description", ""))
                self.policy_list.addItem(item)

    def _on_campaign(self):
        """参与城主竞选。"""
        ok, msg = self.engine.campaign_for_mayor(self.city_id)
        if ok:
            QMessageBox.information(self, "竞选结果", msg)
        else:
            QMessageBox.warning(self, "竞选失败", msg)
        self._refresh()

    def _on_enact(self):
        """颁布选中政策。"""
        item = self.policy_list.currentItem()
        if not item:
            QMessageBox.warning(self, "未选择", "请先选择要颁布的政策。")
            return
        policy_id = item.data(Qt.UserRole)
        ok, msg = self.engine.enact_city_policy(policy_id, self.city_id)
        if ok:
            QMessageBox.information(self, "颁布成功", msg)
        else:
            QMessageBox.warning(self, "颁布失败", msg)
        self._refresh()
