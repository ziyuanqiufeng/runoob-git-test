# -*- coding: utf-8 -*-
"""
炼器附魔弹窗：强化装备、附加词缀、重铸词缀。

左侧选择装备，右侧查看详情并执行强化 / 附魔 / 重铸操作。
所有消耗与成功率均从 equipment_affixes.json 配置读取。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QGroupBox,
    QSplitter, QWidget, QGridLayout,
)
from PySide6.QtCore import Qt


class EquipmentDialog(QDialog):
    """炼器附魔交互弹窗。"""

    # 装备类型中文映射
    TYPE_NAMES = {
        "weapon": "武器",
        "helmet": "头盔",
        "armor": "护甲",
        "accessory": "饰品",
        "life_treasure": "本命法宝",
    }

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.manager = engine.equipment_manager
        self.item_library = engine.item_library

        self.setWindowTitle("炼器附魔")
        self.resize(760, 560)

        # 主布局：左右分栏
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # 左侧面板：装备列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

        left_layout.addWidget(QLabel("<b>可炼器装备</b>"))
        self.equipment_list = QListWidget()
        self.equipment_list.setToolTip("选择背包或已装备的可炼器装备。")
        self.equipment_list.currentItemChanged.connect(self._on_equipment_selected)
        left_layout.addWidget(self.equipment_list)

        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.setToolTip("重新读取背包与已装备装备。")
        self.refresh_btn.clicked.connect(self._refresh_equipment_list)
        left_layout.addWidget(self.refresh_btn)

        splitter.addWidget(left_widget)

        # 右侧面板：详情与操作
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)

        # 装备详情
        self.detail_label = QLabel("请选择左侧装备。")
        self.detail_label.setWordWrap(True)
        self.detail_label.setMinimumHeight(140)
        self.detail_label.setStyleSheet(
            "background: #f8f9fa; padding: 10px; border-radius: 6px;"
        )
        right_layout.addWidget(self.detail_label)

        # 操作区
        ops_layout = QGridLayout()
        ops_layout.setSpacing(10)

        # 强化操作
        enhance_box = QGroupBox("装备强化")
        enhance_layout = QVBoxLayout(enhance_box)
        self.enhance_info = QLabel("")
        self.enhance_info.setWordWrap(True)
        enhance_layout.addWidget(self.enhance_info)
        self.enhance_btn = QPushButton("强化")
        self.enhance_btn.setToolTip("消耗灵石尝试提升强化等级。")
        self.enhance_btn.clicked.connect(self._on_enhance)
        enhance_layout.addWidget(self.enhance_btn)
        ops_layout.addWidget(enhance_box, 0, 0)

        # 附魔操作
        enchant_box = QGroupBox("附魔词缀")
        enchant_layout = QVBoxLayout(enchant_box)
        self.enchant_info = QLabel("")
        self.enchant_info.setWordWrap(True)
        enchant_layout.addWidget(self.enchant_info)
        self.enchant_btn = QPushButton("附魔")
        self.enchant_btn.setToolTip("为装备附加一条随机词缀。")
        self.enchant_btn.clicked.connect(self._on_enchant)
        enchant_layout.addWidget(self.enchant_btn)
        ops_layout.addWidget(enchant_box, 0, 1)

        # 重铸操作
        reforge_box = QGroupBox("词缀重铸")
        reforge_layout = QVBoxLayout(reforge_box)
        self.affix_list = QListWidget()
        self.affix_list.setToolTip("选择要重铸的词缀。")
        self.affix_list.currentItemChanged.connect(self._on_affix_selected)
        reforge_layout.addWidget(self.affix_list)
        self.reforge_info = QLabel("选择词缀查看消耗。")
        self.reforge_info.setWordWrap(True)
        reforge_layout.addWidget(self.reforge_info)
        self.reforge_btn = QPushButton("重铸")
        self.reforge_btn.setToolTip("替换选中的词缀为新的随机词缀。")
        self.reforge_btn.clicked.connect(self._on_reforge)
        reforge_layout.addWidget(self.reforge_btn)
        ops_layout.addWidget(reforge_box, 1, 0, 1, 2)

        right_layout.addLayout(ops_layout)

        # 操作日志
        self.log_label = QLabel("")
        self.log_label.setWordWrap(True)
        self.log_label.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
        right_layout.addWidget(self.log_label)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)
        right_layout.addWidget(close_btn)

        splitter.addWidget(right_widget)
        splitter.setSizes([240, 520])
        main_layout.addWidget(splitter)

        # 当前选中装备
        self._current_item = None

        self._refresh_equipment_list()

    def _get_equipment_items(self):
        """收集背包与已装备栏中的可炼器装备。"""
        items = []
        # 背包中符合类型的装备
        allowed = set(self.manager.config.get_affix_rules().get("allowed_types", []))
        for item in self.player.inventory:
            if item.type in allowed:
                items.append(item)
        # 已装备栏中的装备
        for slot, item in self.player.equipment.items():
            if item and item.type in allowed:
                items.append(item)
        return items

    def _format_effects(self, effects):
        """将效果字典格式化为可读文本。"""
        if not effects:
            return "无"
        parts = []
        key_names = {
            "attack": "攻击", "defense": "防御", "health": "生命",
            "wisdom": "悟性", "luck": "机缘", "constitution": "根骨",
            "fire_damage_bonus": "火伤加成", "water_damage_bonus": "水/冰伤加成",
            "thunder_damage_bonus": "雷伤加成", "poison_chance": "中毒概率",
            "dodge_chance": "闪避概率",
        }
        for key, value in effects.items():
            name = key_names.get(key, key)
            # 百分比效果保留一位小数
            if isinstance(value, float):
                parts.append(f"{name} {value*100:+.1f}%")
            else:
                parts.append(f"{name} +{value}")
        return ", ".join(parts)

    def _refresh_equipment_list(self):
        """刷新左侧装备列表。"""
        self.equipment_list.clear()
        self._item_map = {}  # QListWidgetItem -> Item 对象

        for item in self._get_equipment_items():
            # 构建显示文本：+强化等级 名称 [类型]
            enhance_mark = f"+{item.enhancement_level} " if item.enhancement_level else ""
            affix_mark = f" [{len(item.affixes)}词]" if item.affixes else ""
            type_name = self.TYPE_NAMES.get(item.type, item.type)
            text = f"{enhance_mark}{item.name}{affix_mark} [{type_name}]"

            list_item = QListWidgetItem(text)
            list_item.setData(Qt.UserRole, id(item))
            self.equipment_list.addItem(list_item)
            self._item_map[id(item)] = item

        self._current_item = None
        self._clear_detail()

    def _clear_detail(self):
        """清空右侧详情与操作状态。"""
        self.detail_label.setText("请选择左侧装备。")
        self.enhance_info.clear()
        self.enhance_btn.setEnabled(False)
        self.enchant_info.clear()
        self.enchant_btn.setEnabled(False)
        self.affix_list.clear()
        self.reforge_info.setText("选择词缀查看消耗。")
        self.reforge_btn.setEnabled(False)

    def _on_equipment_selected(self, current, previous):
        """选中装备时刷新详情与操作按钮。"""
        if not current:
            self._clear_detail()
            return

        item = self._item_map.get(current.data(Qt.UserRole))
        self._current_item = item
        self._refresh_detail()

    def _refresh_detail(self):
        """刷新选中装备的详情与操作区。"""
        item = self._current_item
        if not item:
            return

        type_name = self.TYPE_NAMES.get(item.type, item.type)
        total_effects = self.manager.get_total_effects(item)

        # 词缀文本
        affix_texts = []
        for idx, affix in enumerate(item.affixes, start=1):
            affix_texts.append(f"{idx}. {affix['name']}：{affix['description']}")
        affix_str = "<br>".join(affix_texts) if affix_texts else "无"

        self.detail_label.setText(
            f"<b>{item.name}</b> [{type_name}]<br>"
            f"强化等级：+{item.enhancement_level}<br>"
            f"总效果：{self._format_effects(total_effects)}<br>"
            f"<b>词缀：</b><br>{affix_str}"
        )

        # 刷新强化信息
        self._refresh_enhance_info()
        # 刷新附魔信息
        self._refresh_enchant_info()
        # 刷新词缀列表与重铸信息
        self._refresh_affix_list()

    def _refresh_enhance_info(self):
        """刷新强化区显示。"""
        item = self._current_item
        if not item:
            return

        ok, msg = self.manager.can_enhance(item)
        level = item.enhancement_level
        max_level = self.manager.config.get_enhancement_rules().get("max_level", 10)
        rate = self.manager._get_enhancement_success_rate(level)
        cost = self.manager._get_enhancement_cost(level)
        owned = self.player.count_item("spirit_stone")

        if ok:
            self.enhance_info.setText(
                f"当前 +{level} / 最高 +{max_level}<br>"
                f"成功率：{rate*100:.1f}%<br>"
                f"消耗灵石：{cost}（拥有 {owned}）"
            )
        else:
            self.enhance_info.setText(
                f"当前 +{level} / 最高 +{max_level}<br>"
                f"<span style='color:red;'>{msg}</span>"
            )
        self.enhance_btn.setEnabled(ok)

    def _refresh_enchant_info(self):
        """刷新附魔区显示。"""
        item = self._current_item
        if not item:
            return

        ok, msg = self.manager.can_enchant(item)
        cost = self.manager.config.get_affix_rules().get("enchant_cost", {})
        spirit_stone = cost.get("spirit_stone", 200)
        material_id = cost.get("material_id")
        material_count = cost.get("material_count", 1)
        max_affixes = self.manager.config.get_affix_rules().get("max_affixes", 4)
        owned_stone = self.player.count_item("spirit_stone")

        text = f"词缀：{len(item.affixes)}/{max_affixes}<br>消耗灵石：{spirit_stone}（拥有 {owned_stone}）"
        if material_id:
            material_name = self.item_library.get(material_id)
            material_name = material_name.name if material_name else material_id
            owned_mat = self.player.count_item(material_id)
            text += f"<br>消耗 {material_name}：{material_count}（拥有 {owned_mat}）"
        if not ok:
            text += f"<br><span style='color:red;'>{msg}</span>"

        self.enchant_info.setText(text)
        self.enchant_btn.setEnabled(ok)

    def _refresh_affix_list(self):
        """刷新词缀列表与重铸按钮状态。"""
        item = self._current_item
        self.affix_list.clear()
        self.reforge_btn.setEnabled(False)
        self.reforge_info.setText("选择词缀查看消耗。")
        if not item:
            return

        for idx, affix in enumerate(item.affixes):
            list_item = QListWidgetItem(f"{idx + 1}. {affix['name']}")
            list_item.setData(Qt.UserRole, idx)
            self.affix_list.addItem(list_item)

        if item.affixes:
            self.affix_list.setCurrentRow(0)

    def _on_affix_selected(self, current, previous):
        """选中词缀时刷新重铸信息。"""
        item = self._current_item
        if not item or not current:
            self.reforge_info.setText("选择词缀查看消耗。")
            self.reforge_btn.setEnabled(False)
            return

        affix_index = current.data(Qt.UserRole)
        ok, msg = self.manager.can_reforge(item, affix_index)
        cost = self.manager.config.get_affix_rules().get("reforge_cost", {})
        spirit_stone = cost.get("spirit_stone", 100)
        material_id = cost.get("material_id")
        material_count = cost.get("material_count", 2)
        owned_stone = self.player.count_item("spirit_stone")

        text = f"消耗灵石：{spirit_stone}（拥有 {owned_stone}）"
        if material_id:
            material_name = self.item_library.get(material_id)
            material_name = material_name.name if material_name else material_id
            owned_mat = self.player.count_item(material_id)
            text += f"<br>消耗 {material_name}：{material_count}（拥有 {owned_mat}）"
        if not ok:
            text += f"<br><span style='color:red;'>{msg}</span>"

        self.reforge_info.setText(text)
        self.reforge_btn.setEnabled(ok)
        self._current_affix_index = affix_index

    def _on_enhance(self):
        """执行强化。"""
        item = self._current_item
        if not item:
            return

        success, msg, destroyed = self.manager.enhance(item)
        self.log_label.setText(f"强化：{msg}")

        if destroyed:
            # 装备损毁，需要从背包或装备栏移除
            self._remove_destroyed_item(item)
            self._refresh_equipment_list()
        else:
            self._refresh_detail()

    def _on_enchant(self):
        """执行附魔。"""
        item = self._current_item
        if not item:
            return

        success, msg, affix = self.manager.enchant(item)
        self.log_label.setText(f"附魔：{msg}")
        if success:
            self._refresh_detail()

    def _on_reforge(self):
        """执行重铸。"""
        item = self._current_item
        if not item:
            return

        affix_index = getattr(self, "_current_affix_index", -1)
        if affix_index < 0:
            return

        success, msg, affix = self.manager.reforge(item, affix_index)
        self.log_label.setText(f"重铸：{msg}")
        if success:
            self._refresh_detail()

    def _remove_destroyed_item(self, item):
        """强化失败导致装备损毁时，从背包或装备栏移除该物品。"""
        # 先从背包移除
        if item in self.player.inventory:
            self.player.inventory.remove(item)
            return
        # 再从装备栏移除
        for slot, equipped in self.player.equipment.items():
            if equipped is item:
                self.player.equipment[slot] = None
                # 重新计算生命值上限
                self.player.max_health = self.player.max_health_base + self.player.max_health_equipped
                self.player.health = min(self.player.health, self.player.max_health)
                return
