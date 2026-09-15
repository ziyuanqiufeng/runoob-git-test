# -*- coding: utf-8 -*-
"""
城池发展与建筑升级弹窗：显示城池声望、建筑等级，并可升级建筑。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QComboBox,
    QSpinBox, QDialogButtonBox
)
from PySide6.QtCore import Qt


class BuildingUpgradeDialog(QDialog):
    """城池建筑升级弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.building_manager = engine.building_manager

        self.setWindowTitle("城池发展")
        self.resize(560, 480)

        layout = QVBoxLayout(self)

        # 标题与声望
        location = engine.get_current_location()
        city_name = location.get("name", "城池") if location else "城池"
        city_id = location.get("id", "") if location else ""
        self.city_id = city_id

        title = QLabel(f"<h2>{city_name} 发展</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        rep = self.building_manager.get_city_reputation(city_id)
        rep_level = self.building_manager.get_reputation_level(city_id)
        self.rep_label = QLabel(
            f"城池声望：<b>{rep}</b>（{rep_level}）"
        )
        self.rep_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.rep_label)

        tip = QLabel(
            "完成城主府任务或捐赠物品可获得城池声望。声望与境界共同决定建筑升级上限。"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(tip)

        # 建筑列表
        layout.addWidget(QLabel("<b>城内建筑</b>"))
        self.building_list = QListWidget()
        self.building_list.currentItemChanged.connect(self._on_building_selected)
        layout.addWidget(self.building_list)

        # 详情与升级
        self.detail_label = QLabel("请选择一座建筑。")
        self.detail_label.setWordWrap(True)
        self.detail_label.setMinimumHeight(80)
        self.detail_label.setStyleSheet("background: #f5f5f5; padding: 8px; border-radius: 4px;")
        layout.addWidget(self.detail_label)

        self.upgrade_btn = QPushButton("升级")
        self.upgrade_btn.clicked.connect(self._upgrade_selected)
        layout.addWidget(self.upgrade_btn)

        # 城池捐赠按钮：用背包物品换声望
        self.donate_btn = QPushButton("捐赠物品")
        self.donate_btn.setToolTip("捐赠背包物品以提升当前城池声望。")
        self.donate_btn.clicked.connect(self._open_donation_dialog)
        layout.addWidget(self.donate_btn)

        self._refresh_building_list()

    def _refresh_building_list(self):
        """刷新建筑列表。"""
        self.building_list.clear()
        location = self.engine.get_current_location()
        if not location:
            return
        for building in location.get("buildings", []):
            bid = building.get("id", "")
            name = building.get("name", bid)
            level = self.building_manager.get_building_level(bid)
            text = f"{name}（等级 {level}）"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, bid)
            self.building_list.addItem(item)

    def _on_building_selected(self, current, previous):
        """选中建筑时显示详情。"""
        if not current:
            self.detail_label.setText("请选择一座建筑。")
            self.upgrade_btn.setEnabled(False)
            return

        bid = current.data(Qt.UserRole)
        level = self.building_manager.get_building_level(bid)
        max_level = self.building_manager.get_max_level(bid)
        effects = self.building_manager.get_current_effects(bid)
        can_upgrade, reason = self.building_manager.can_upgrade(bid, self.city_id)

        config = self.building_manager.get_building_config(bid)
        desc = config.get("description", "")

        text = (
            f"<b>{bid}</b><br>"
            f"{desc}<br>"
            f"当前等级：{level}/{max_level}<br>"
            f"当前效果：{effects}"
        )
        if level < max_level:
            next_cfg = self.building_manager.get_level_config(bid, level + 1)
            if next_cfg:
                cost = next_cfg.get("cost", {})
                cost_texts = []
                for item_id, count in cost.items():
                    item = self.engine.item_library.get(item_id)
                    item_name = item.name if item else item_id
                    owned = self.player.count_item(item_id)
                    color = "green" if owned >= count else "red"
                    cost_texts.append(
                        f"<span style='color:{color};'>{item_name}：{owned}/{count}</span>"
                    )
                text += (
                    f"<br>下一级需求：境界 order ≥ {next_cfg.get('required_realm_order', 1)}，"
                    f"声望 ≥ {next_cfg.get('required_reputation', 0)}"
                )
                if cost_texts:
                    text += f"<br>升级消耗：<br>{'<br>'.join(cost_texts)}"
        else:
            text += "<br>已达最高等级。"

        self.detail_label.setText(text)
        self.upgrade_btn.setEnabled(can_upgrade)
        if not can_upgrade and reason:
            self.upgrade_btn.setToolTip(reason)
        else:
            self.upgrade_btn.setToolTip("")
        self._current_building_id = bid

    def _upgrade_selected(self):
        """升级选中的建筑。"""
        bid = getattr(self, "_current_building_id", None)
        if not bid:
            return
        ok, msg = self.building_manager.upgrade_building(bid, self.city_id)
        if ok:
            QMessageBox.information(self, "升级成功", msg)
        else:
            QMessageBox.information(self, "无法升级", msg)
        self._refresh_building_list()
        self._on_building_selected(self.building_list.currentItem(), None)
        self._refresh_reputation_label()

    def _refresh_reputation_label(self):
        """刷新顶部城池声望显示。"""
        rep = self.building_manager.get_city_reputation(self.city_id)
        rep_level = self.building_manager.get_reputation_level(self.city_id)
        self.rep_label.setText(f"城池声望：<b>{rep}</b>（{rep_level}）")

    def _open_donation_dialog(self):
        """打开城池捐赠弹窗。"""
        dialog = CityDonationDialog(self.engine, self.city_id, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self._refresh_reputation_label()
            self._on_building_selected(self.building_list.currentItem(), None)


class CityDonationDialog(QDialog):
    """城池捐赠弹窗：选择背包物品与数量，换取城池声望。"""

    def __init__(self, engine, city_id, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.item_library = engine.item_library
        self.city_id = city_id

        self.setWindowTitle("城池捐赠")
        self.resize(360, 220)

        layout = QVBoxLayout(self)

        # 物品选择下拉框，仅显示背包中数量大于 0 的物品
        layout.addWidget(QLabel("选择要捐赠的物品："))
        self.item_combo = QComboBox()
        self._refresh_item_list()
        self.item_combo.currentIndexChanged.connect(self._update_preview)
        layout.addWidget(self.item_combo)

        # 捐赠数量
        layout.addWidget(QLabel("捐赠数量："))
        self.count_spin = QSpinBox()
        self.count_spin.setMinimum(1)
        self.count_spin.setMaximum(9999)
        self.count_spin.valueChanged.connect(self._update_preview)
        layout.addWidget(self.count_spin)

        # 声望预览
        self.preview_label = QLabel("预计获得声望：0")
        self.preview_label.setStyleSheet("color: #666;")
        layout.addWidget(self.preview_label)

        # 确定/取消按钮
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._update_preview()

    def _refresh_item_list(self):
        """刷新可捐赠物品列表。"""
        self.item_combo.clear()
        # 统计背包中每种物品的总数量
        counts = {}
        for item in self.player.inventory:
            counts[item.id] = counts.get(item.id, 0) + item.count
        if not counts:
            self.item_combo.addItem("背包为空", None)
            return
        for item_id, count in sorted(counts.items()):
            item = self.item_library.get(item_id)
            if not item:
                continue
            display = f"{item.name} x{count}（价值 {item.value}）"
            self.item_combo.addItem(display, item_id)

    def _current_item_id(self):
        """获取当前选中的物品 ID。"""
        return self.item_combo.currentData()

    def _max_count(self):
        """获取当前选中物品在背包中的总数量。"""
        item_id = self._current_item_id()
        if not item_id:
            return 0
        return self.player.count_item(item_id)

    def _update_preview(self):
        """根据当前选择更新预计声望。"""
        item_id = self._current_item_id()
        count = self.count_spin.value()
        max_count = self._max_count()
        self.count_spin.setMaximum(max(1, max_count))
        if not item_id or max_count <= 0:
            self.preview_label.setText("预计获得声望：0")
            self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
            return
        item = self.item_library.get(item_id)
        rep = max(1, item.value * min(count, max_count) // 10) if item else 0
        self.preview_label.setText(f"预计获得声望：{rep}")
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(count <= max_count)

    def _on_accept(self):
        """确认捐赠。"""
        item_id = self._current_item_id()
        count = self.count_spin.value()
        if not item_id or count <= 0:
            self.reject()
            return
        ok, _ = self.engine.donate_to_city(item_id, count, self.city_id)
        if ok:
            self.accept()
        else:
            self._refresh_item_list()
            self._update_preview()
