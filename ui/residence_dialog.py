# -*- coding: utf-8 -*-
"""洞府管理弹窗。"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QWidget as BaseWidget,
    QGroupBox, QGridLayout
)
from PySide6.QtCore import Qt

from game.residence import ResidenceManager, ResidenceConfig


class ResidenceDialog(QDialog):
    """洞府界面：购买洞府、升级建筑、查看效果。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("洞府")
        self.resize(600, 500)
        self.engine = engine
        self.player = engine.player
        self.item_library = engine.item_library
        self.residence_manager = ResidenceManager(
            self.player, item_library=self.item_library
        )
        self.residence_config = ResidenceConfig()

        self.layout = QVBoxLayout(self)

        # 顶部信息
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font: 14px 'Microsoft YaHei'; padding: 6px;")
        self.layout.addWidget(self.info_label)

        # 购买洞府区域
        self.buy_group = QGroupBox("可购买洞府")
        buy_layout = QVBoxLayout(self.buy_group)
        self.buy_list = QListWidget()
        self.buy_list.itemClicked.connect(self._on_buy_item_selected)
        buy_layout.addWidget(self.buy_list)
        self.buy_btn = QPushButton("购买")
        self.buy_btn.clicked.connect(self._on_buy)
        buy_layout.addWidget(self.buy_btn)
        self.layout.addWidget(self.buy_group)

        # 建筑升级区域
        self.building_group = QGroupBox("洞府建筑")
        building_layout = QVBoxLayout(self.building_group)
        self.building_list = QListWidget()
        self.building_list.itemClicked.connect(self._on_building_selected)
        building_layout.addWidget(self.building_list)
        self.upgrade_btn = QPushButton("升级")
        self.upgrade_btn.clicked.connect(self._on_upgrade)
        building_layout.addWidget(self.upgrade_btn)
        self.layout.addWidget(self.building_group)

        # 效果汇总
        self.effect_label = QLabel()
        self.effect_label.setWordWrap(True)
        self.effect_label.setStyleSheet("color: #2c3e50; padding: 6px;")
        self.layout.addWidget(self.effect_label)

        self._refresh()

    def _refresh(self):
        """刷新界面状态。"""
        self.info_label.setText(self._build_info_text())
        self._refresh_buy_list()
        self._refresh_building_list()
        self.effect_label.setText(self._build_effect_text())

    def _build_info_text(self):
        """构建顶部信息文本。"""
        lines = [f"灵石：{self.player.count_item('spirit_stone')}  "
                 f"贡献：{self.player.sect_contribution}"]
        if self.player.residence:
            residence = self.residence_config.get_residence(self.player.residence["id"])
            lines.append(f"当前洞府：{residence['name'] if residence else '未知'}")
        else:
            lines.append("当前洞府：无")
        return "\n".join(lines)

    def _refresh_buy_list(self):
        """刷新可购买洞府列表。"""
        self.buy_list.clear()
        if self.player.residence is not None:
            self.buy_group.setEnabled(False)
            return
        self.buy_group.setEnabled(True)
        for residence in self.residence_config.get_residences():
            cost = residence.get("cost", {})
            text = (f"{residence['name']} - {residence.get('description', '')}  "
                    f"费用：灵石 {cost.get('spirit_stone', 0)}  "
                    f"贡献 {cost.get('contribution', 0)}")
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, residence["id"])
            self.buy_list.addItem(item)

    def _refresh_building_list(self):
        """刷新建筑升级列表。"""
        self.building_list.clear()
        if not self.player.residence:
            self.building_group.setEnabled(False)
            return
        self.building_group.setEnabled(True)
        residence_id = self.player.residence["id"]
        for building in self.residence_config.get_residence(residence_id).get("buildings", []):
            current = self.player.residence.get("buildings", {}).get(building["id"], 0)
            max_level = building.get("max_level", 0)
            cost = self.residence_manager._get_upgrade_cost(building, current)
            if current >= max_level:
                text = f"{building['name']}：{current}/{max_level}（已满级）"
            else:
                text = f"{building['name']}：{current}/{max_level}  升级需 {cost} 灵石"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, building["id"])
            self.building_list.addItem(item)

    def _build_effect_text(self):
        """构建效果汇总文本。"""
        if not self.player.residence:
            return ""
        parts = ["当前效果："]
        cultivation = self.residence_manager.get_cultivation_speed_bonus()
        if cultivation:
            parts.append(f"修炼速度 +{cultivation*100:.0f}%")
        water = self.residence_manager.get_water_damage_bonus()
        if water:
            parts.append(f"水属性伤害 +{water*100:.0f}%")
        refine = self.residence_manager.get_refine_bonus()
        if refine:
            parts.append(f"祭炼效果 +{refine*100:.0f}%")
        defense = self.residence_manager.get_raid_defense()
        if defense:
            parts.append(f"袭击防御 +{defense*100:.0f}%")
        herbs = self.residence_manager.get_herb_production()
        for herb in herbs:
            parts.append(f"药园产出 {herb['herb_id']} 概率 {herb['chance']*100:.0f}%")
        return "  ".join(parts)

    def _on_buy_item_selected(self, item):
        """选中要购买的洞府。"""
        self._selected_residence_id = item.data(Qt.UserRole)

    def _on_buy(self):
        """购买洞府。"""
        if not hasattr(self, "_selected_residence_id"):
            QMessageBox.information(self, "提示", "请先选择一处洞府。")
            return
        ok, msg = self.residence_manager.buy_residence(self._selected_residence_id)
        if ok:
            self.engine.notify(msg)
            self._refresh()
        else:
            QMessageBox.warning(self, "购买失败", msg)

    def _on_building_selected(self, item):
        """选中要升级的建筑。"""
        self._selected_building_id = item.data(Qt.UserRole)

    def _on_upgrade(self):
        """升级建筑。"""
        if not hasattr(self, "_selected_building_id"):
            QMessageBox.information(self, "提示", "请先选择一个建筑。")
            return
        ok, msg = self.residence_manager.upgrade_building(self._selected_building_id)
        if ok:
            self.engine.notify(msg)
            self._refresh()
        else:
            QMessageBox.warning(self, "升级失败", msg)
