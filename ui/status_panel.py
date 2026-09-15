# -*- coding: utf-8 -*-
"""左侧状态面板，精简核心信息并提供可折叠的详情区域。"""
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QFrame, QPushButton,
    QMenu, QFileDialog, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont

from ui.portrait_label import PortraitLabel


# 境界 ID 前缀 → 边框颜色（用于头像框）
_REALM_BORDER_COLORS = {
    "qi_refining": "#95a5a6",   # 练气期：灰色
    "foundation": "#2ecc71",    # 筑基期：绿色
    "golden_core": "#f1c40f",   # 金丹期：金色
    "nascent_soul": "#9b59b6",  # 元婴期：紫色
}

# 修炼流派 ID → 文本颜色
_PATH_COLORS = {
    "fa": "#3498db", "ti": "#e67e22", "jian": "#f1c40f", "xie": "#9b59b6",
    "dan": "#2ecc71", "qi": "#95a5a6", "shou": "#d35400", "hun": "#8e44ad",
    "zhen": "#16a085", "fu": "#c0392b",
}

# 装备槽位 → 图标与中文名
_EQUIPMENT_SLOTS = {
    "weapon": ("⚔", "武器"),
    "helmet": ("🪖", "头盔"),
    "armor": ("🛡", "护甲"),
    "accessory": ("💍", "饰品"),
    "life_treasure": ("✦", "本命"),
}


def _get_realm_border_color(realm_id):
    """根据境界 ID 返回对应的头像边框颜色。"""
    for prefix, color in _REALM_BORDER_COLORS.items():
        if realm_id.startswith(prefix):
            return color
    return "#95a5a6"


class StatusPanel(QWidget):
    """左侧状态面板，显示玩家核心属性，支持详情折叠。"""

    open_quest_dialog = Signal()
    open_quest_log = Signal()
    face_customize_requested = Signal()

    def __init__(self, player, world, quest_library=None):
        super().__init__()
        self.player = player
        self.world = world
        self.quest_library = quest_library

        # 垂直布局，控件之间留一点间距
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setAlignment(Qt.AlignTop)

        # === 人物卡 ===
        self._setup_character_card()

        # === 核心进度条：修为 / 健康 ===
        self._setup_core_bars()

        # === 详情折叠区 ===
        self._setup_details_panel()

        # === 境界神通 ===
        self._setup_feature_section()

        # === 装备槽位 ===
        self._setup_equipment_slots()

        # === 任务 ===
        self._setup_quest_section()

        # 初始刷新一次
        self.update_status()

    def _setup_character_card(self):
        """顶部紧凑人物卡：头像 + 道号/境界。"""
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #f8f9fa; border-radius: 10px; border: 1px solid #dee2e6; }"
        )
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(10)

        # 主角头像（使用统一头像组件，默认圆形裁剪）
        self.portrait_label = PortraitLabel(
            size=80,
            border_color="#95a5a6",
            border_width=3,
            placeholder_text="无头像",
            circular=True,
        )
        # 右键菜单：更换立绘
        self.portrait_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.portrait_label.customContextMenuRequested.connect(
            self._on_portrait_context_menu
        )
        card_layout.addWidget(self.portrait_label)

        # 文字信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        self.info_card_name = QLabel()
        self.info_card_name.setStyleSheet("font-weight: bold; font-size: 15px;")
        self.info_card_realm = QLabel()
        self.info_card_realm.setStyleSheet("color: #7f8c8d; font-size: 13px;")

        info_layout.addWidget(self.info_card_name)
        info_layout.addWidget(self.info_card_realm)
        info_layout.addStretch()
        card_layout.addLayout(info_layout, 1)

        self.layout.addWidget(card)

    def _setup_core_bars(self):
        """修为、健康两条核心进度条。"""
        bars_widget = QWidget()
        bars_layout = QVBoxLayout(bars_widget)
        bars_layout.setSpacing(6)
        bars_layout.setContentsMargins(0, 0, 0, 0)

        # 修为
        self.qi_label = QLabel("修为")
        self.qi_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        bars_layout.addWidget(self.qi_label)
        self.qi_bar = QProgressBar()
        self.qi_bar.setTextVisible(True)
        self.qi_bar.setRange(0, 100)
        self.qi_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 6px; background: #e9ecef; text-align: center; }"
            "QProgressBar::chunk { border-radius: 6px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #74b9ff, stop:1 #0984e3); }"
        )
        bars_layout.addWidget(self.qi_bar)

        # 健康
        self.health_label = QLabel("健康")
        self.health_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
        bars_layout.addWidget(self.health_label)
        self.health_bar = QProgressBar()
        self.health_bar.setTextVisible(True)
        self.health_bar.setRange(0, 100)
        self.health_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 6px; background: #e9ecef; text-align: center; }"
            "QProgressBar::chunk { border-radius: 6px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff7675, stop:1 #d63031); }"
        )
        bars_layout.addWidget(self.health_bar)

        self.layout.addWidget(bars_widget)

    def _setup_details_panel(self):
        """可折叠的详细属性面板。"""
        self.toggle_details_btn = QPushButton("展开详情 ▼")
        self.toggle_details_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #3498db; border: none; text-align: left; }"
            "QPushButton:hover { color: #2980b9; }"
        )
        self.toggle_details_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_details_btn.clicked.connect(self._toggle_details)
        self.layout.addWidget(self.toggle_details_btn)

        self.details_panel = QWidget()
        self.details_panel.setVisible(False)
        details_layout = QVBoxLayout(self.details_panel)
        details_layout.setSpacing(4)
        details_layout.setContentsMargins(6, 0, 6, 0)

        # 各项详细属性标签
        self.name_label = QLabel()
        self.realm_label = QLabel()
        self.age_label = QLabel()
        self.lifespan_label = QLabel()
        self.attack_label = QLabel()
        self.defense_label = QLabel()
        self.location_label = QLabel()
        self.talent_label = QLabel()
        self.spiritual_root_label = QLabel()
        self.spiritual_root_label.setWordWrap(True)
        self.spiritual_root_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #9b59b6;")
        self.cultivation_path_label = QLabel()
        self.cultivation_path_label.setWordWrap(True)
        self.cultivation_path_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #e67e22;")
        self.sect_label = QLabel()
        self.sect_label.setWordWrap(True)
        self.sect_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #1abc9c;")
        self.camp_label = QLabel()
        self.camp_label.setWordWrap(True)
        self.camp_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #3498db;")
        self.time_label = QLabel()
        self.inventory_label = QLabel()
        self.inventory_label.setWordWrap(True)

        for widget in [
            self.age_label,
            self.lifespan_label,
            self.attack_label,
            self.defense_label,
            self.location_label,
            self.talent_label,
            self.spiritual_root_label,
            self.cultivation_path_label,
            self.sect_label,
            self.camp_label,
            self.time_label,
            self.inventory_label,
        ]:
            details_layout.addWidget(widget)

        self.layout.addWidget(self.details_panel)

    def _setup_feature_section(self):
        """境界神通紧凑显示。"""
        title = QLabel("境界神通")
        title.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #2c3e50; "
            "border-bottom: 1px solid #bdc3c7; padding-bottom: 2px; margin-top: 4px;"
        )
        self.layout.addWidget(title)

        self.feature_label = QLabel("无")
        self.feature_label.setWordWrap(True)
        self.feature_label.setStyleSheet("color: #555; font-size: 12px;")
        self.layout.addWidget(self.feature_label)

    def _setup_equipment_slots(self):
        """装备栏图形化：图标槽位 + 名称。"""
        title = QLabel("装备")
        title.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #2c3e50; "
            "border-bottom: 1px solid #bdc3c7; padding-bottom: 2px; margin-top: 4px;"
        )
        self.layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(0, 4, 0, 4)

        self.equipment_labels = {}
        for idx, (slot, (icon, cn_name)) in enumerate(_EQUIPMENT_SLOTS.items()):
            slot_widget = QFrame()
            slot_widget.setStyleSheet(
                "QFrame { background-color: #f1f3f5; border-radius: 6px; border: 1px solid #dee2e6; }"
            )
            slot_layout = QHBoxLayout(slot_widget)
            slot_layout.setContentsMargins(6, 4, 6, 4)
            slot_layout.setSpacing(6)

            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 16px;")
            slot_layout.addWidget(icon_label)

            text_label = QLabel(f"{cn_name}：无")
            text_label.setStyleSheet("font-size: 12px; color: #2c3e50;")
            text_label.setWordWrap(False)
            slot_layout.addWidget(text_label, 1)

            self.equipment_labels[slot] = text_label

            row = idx // 2
            col = idx % 2
            grid.addWidget(slot_widget, row, col)

        self.layout.addLayout(grid)

    def _setup_quest_section(self):
        """任务区域。"""
        title = QLabel("任务")
        title.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #2c3e50; "
            "border-bottom: 1px solid #bdc3c7; padding-bottom: 2px; margin-top: 4px;"
        )
        self.layout.addWidget(title)

        self.quest_label = QLabel("无")
        self.quest_label.setWordWrap(True)
        self.quest_label.setStyleSheet("color: #555; font-size: 12px;")
        self.layout.addWidget(self.quest_label)

        # 任务管理按钮
        quest_btn_layout = QHBoxLayout()
        self.quest_btn = QPushButton("任务管理")
        self.quest_btn.setToolTip("查看任务详情并放弃任务")
        self.quest_btn.clicked.connect(self.open_quest_dialog.emit)
        quest_btn_layout.addWidget(self.quest_btn)

        self.quest_log_btn = QPushButton("任务日志")
        self.quest_log_btn.setToolTip("查看所有已完成和进行中的任务")
        self.quest_log_btn.clicked.connect(self.open_quest_log.emit)
        quest_btn_layout.addWidget(self.quest_log_btn)
        self.layout.addLayout(quest_btn_layout)

    def _toggle_details(self):
        """切换详情面板的展开/收起状态。"""
        visible = not self.details_panel.isVisible()
        self.details_panel.setVisible(visible)
        self.toggle_details_btn.setText("收起详情 ▲" if visible else "展开详情 ▼")

    def update_status(self):
        """根据最新数据刷新面板显示。"""
        realm = self.world.get_realm(self.player.realm_id)
        realm_name = realm["name"] if realm else "未知境界"
        max_qi = realm["max_qi"] if realm else 1

        location = self.world.get_location(self.player.location_id)
        location_name = location["name"] if location else "未知之地"

        # 人物卡
        self.info_card_name.setText(self.player.name)
        self.info_card_realm.setText(realm_name)
        self._load_portrait()

        # 核心进度条
        self.qi_label.setText(f"修为：{self.player.qi} / {max_qi}")
        self.qi_bar.setMaximum(max_qi)
        self.qi_bar.setValue(min(self.player.qi, max_qi))

        self.health_label.setText(f"健康：{self.player.health} / {self.player.max_health}")
        self.health_bar.setMaximum(self.player.max_health)
        self.health_bar.setValue(min(self.player.health, self.player.max_health))

        # 详情面板
        self.name_label.setText(f"道号：{self.player.name}")
        self.realm_label.setText(f"境界：{realm_name}")
        self.age_label.setText(f"年龄：{self.player.age} 岁")
        self.lifespan_label.setText(f"寿元：{self.player.max_lifespan} 年")
        self.attack_label.setText(f"攻击：{self.player.attack}")
        self.defense_label.setText(f"防御：{self.player.defense}")
        self.location_label.setText(f"地点：{location_name}")
        self.talent_label.setText(
            f"悟性 {self.player.wisdom} | 根骨 {self.player.constitution} | 机缘 {self.player.luck}"
        )

        # 灵根信息
        roots = self.player.spiritual_roots
        purities = getattr(self.player, "root_purities", {})
        element_names = {
            "metal": "金", "wood": "木", "water": "水",
            "fire": "火", "earth": "土",
        }
        root_names = {1: "天灵根", 2: "真灵根", 3: "异灵根", 4: "伪灵根", 5: "五行灵根"}
        pure_threshold = 1.2
        mixed_threshold = 0.9
        detail_parts = []
        for e in roots:
            purity = purities.get(e, 1.0)
            if purity >= pure_threshold:
                label = "纯"
            elif purity < mixed_threshold:
                label = "杂"
            else:
                label = ""
            detail_parts.append(f"{label}{element_names.get(e, e)}({purity})")
        names = "、".join(detail_parts)
        root_name = root_names.get(len(roots), "杂灵根")
        mult = self.player.cultivation_multiplier
        self.spiritual_root_label.setText(
            f"灵根：{names}（{root_name}）\n修炼倍率：{mult}x"
        )

        # 修炼流派
        path_id = getattr(self.player, "cultivation_path", "fa")
        path_names = {
            "fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
            "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
            "zhen": "阵修", "fu": "符修",
        }
        path_colors = {
            "fa": "#3498db", "ti": "#e67e22", "jian": "#f1c40f", "xie": "#9b59b6",
            "dan": "#2ecc71", "qi": "#95a5a6", "shou": "#d35400", "hun": "#8e44ad",
            "zhen": "#16a085", "fu": "#c0392b",
        }
        resource_names = {
            "fa": "真气护盾", "ti": "怒气", "jian": "剑意", "xie": "邪气",
            "dan": "丹火", "qi": "器灵", "shou": "兽魂", "hun": "神识",
            "zhen": "阵纹", "fu": "符箓",
        }
        path_name = path_names.get(path_id, "未入门")
        path_color = path_colors.get(path_id, "#e67e22")
        self.cultivation_path_label.setStyleSheet(
            f"font-weight: bold; font-size: 12px; color: {path_color};"
        )
        resource_info = self.player.get_path_resource()
        if resource_info:
            _, current, max_val = resource_info
            res_name = resource_names.get(path_id, "")
            self.cultivation_path_label.setText(
                f"流派：{path_name}\n{res_name}：{current}/{max_val}"
            )
        else:
            self.cultivation_path_label.setText(f"流派：{path_name}")

        self.sect_label.setText(f"宗门：{getattr(self.player, 'sect_name', '无')}")
        self.camp_label.setText(f"阵营：{getattr(self.player, 'camp', '中立')} ({getattr(self.player, 'camp_value', 0)})")
        self.time_label.setText(f"时间：第 {self.world.year} 年 {self.world.month} 月")

        # 背包
        if self.player.inventory:
            counts = {}
            for item in self.player.inventory:
                counts[item.name] = counts.get(item.name, 0) + item.count
            items = ", ".join(f"{name}x{count}" for name, count in counts.items())
        else:
            items = "无"
        self.inventory_label.setText(f"背包：{items}")

        # 境界神通
        feature_names = {
            "flight": "御剑飞行",
            "life_treasure": "本命法宝",
            "nascent_soul_revive": "元婴替死",
        }
        if self.player.unlocked_features:
            features = "、".join(
                feature_names.get(f, f) for f in sorted(self.player.unlocked_features)
            )
            if self.player.nascent_soul_weakened:
                features += f"\n[元婴受损：剩余 {self.player.weakened_remaining_months} 个月，全属性 -10%]"
            self.feature_label.setText(features)
        else:
            text = "无"
            if self.player.nascent_soul_weakened:
                text += f"\n[元婴受损：剩余 {self.player.weakened_remaining_months} 个月，全属性 -10%]"
            self.feature_label.setText(text)

        # 装备槽位
        for slot, label in self.equipment_labels.items():
            icon, cn_name = _EQUIPMENT_SLOTS[slot]
            if slot == "life_treasure" and not self.player.has_feature("life_treasure"):
                label.setText(f"{cn_name}：未解锁")
                continue
            item = self.player.equipment.get(slot)
            if item:
                label.setText(f"{cn_name}：{item.name}")
            else:
                label.setText(f"{cn_name}：无")

        # 任务
        completed_count = len(self.player.completed_quests)
        if self.player.quest_progress and self.quest_library:
            texts = [f"已完成：{completed_count} 个"]
            for quest_id, progress in self.player.quest_progress.items():
                quest = self.quest_library.get(quest_id)
                if quest:
                    target_text = "击杀" if quest.target_type == "kill" else "收集"
                    texts.append(f"• {quest.name} ({progress}/{quest.count})\n  {target_text}: {quest.target_id}")
            self.quest_label.setText("\n".join(texts))
        else:
            self.quest_label.setText(f"无\n已完成：{completed_count} 个")

        # 如果玩家已陨落，给出醒目提示
        if not self.player.is_alive():
            self.info_card_name.setStyleSheet(
                "font-weight: bold; font-size: 15px; color: red;"
            )

    def _on_portrait_context_menu(self, pos):
        """头像右键菜单：提供更换立绘 / 捏脸选项。"""
        menu = QMenu(self)
        face_action = QAction("捏脸…", self)
        face_action.triggered.connect(self.face_customize_requested.emit)
        menu.addAction(face_action)
        change_action = QAction("更换立绘", self)
        change_action.triggered.connect(self._change_portrait)
        menu.addAction(change_action)
        menu.exec(self.portrait_label.mapToGlobal(pos))

    def _change_portrait(self):
        """弹出文件选择对话框，更换玩家头像。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择主角头像",
            "assets/portraits",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if file_path:
            self.player.portrait = file_path
            self._load_portrait()

    def _load_portrait(self):
        """加载并显示主角头像；若文件缺失则显示默认占位文字。

        头像边框颜色随当前境界变化，道号颜色随修炼流派变化。
        大境界突破后若光效仍在持续，则添加发光阴影效果。
        """
        portrait_path = getattr(self.player, "portrait", None)
        realm_id = getattr(self.player, "realm_id", "qi_refining_1")
        path_id = getattr(self.player, "cultivation_path", "fa")
        border_color = _get_realm_border_color(realm_id)
        path_color = _PATH_COLORS.get(path_id, "#e67e22")

        # 统一头像组件设置边框颜色与光效
        self.portrait_label.set_border_color(border_color)
        total_months = (self.world.year - 1) * 12 + (self.world.month - 1)
        glow_active = getattr(self.player, "is_portrait_glow_active", lambda x: False)(total_months)
        self.portrait_label.set_glow(glow_active, color="#f1c40f")

        # 同步道号颜色
        self.info_card_name.setStyleSheet(
            f"font-weight: bold; font-size: 15px; color: {path_color};"
        )

        self.portrait_label.load_portrait(portrait_path)
