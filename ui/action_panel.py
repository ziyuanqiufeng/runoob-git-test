# -*- coding: utf-8 -*-
"""右侧操作面板：手风琴折叠面板（Accordion）。

设计要点（来自用户反馈）：
- 每个大分类是一个独立的可折叠模块，**收起时只显示一行**（组名 + 数量 + 箭头），不占空间；
- 展开时箭头变向下、下方平滑滑出具体子按钮（保持原栅格布局不变）；
- 默认**互斥**模式（点击新组时其他自动收起），保证界面整洁；
- 默认展开"修行"组（最常用的闭关+突破），其他折叠。
"""
import json
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QToolButton, QLabel,
    QCheckBox, QSizePolicy,
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap

from ui.cultivate_dialog import CultivateDialog


# 按钮配置：分组 → (按钮名, 显示文本, emoji 图标, tooltip, 信号/回调)
# 每组控制在 4-6 项内；展开时仍按 2 列栅格显示。
_BUTTON_GROUPS = [
    (
        "修行",
        [
            ("cultivate", "闭关", "🧘", "选择闭关月数吸收灵气", "cultivate"),
            ("breakthrough", "突破", "⚡", "修为满时尝试突破", "breakthrough"),
        ],
    ),
    (
        "行动",
        [
            ("explore", "游历", "🌄", "外出半年，可能遇到奇遇", "explore"),
            ("map", "地图", "🗺", "查看地点并前往其他区域", "open_map"),
            ("npc", "NPC", "🗣", "与当前地点 NPC 交谈", "open_npc"),
            ("secret_realm", "秘境探索", "🌀", "进入 Roguelike 秘境，组队探索节点地图", "open_secret_realm"),
        ],
    ),
    (
        "养成管理",
        [
            ("inventory", "背包", "🎒", "查看、使用物品和合成", "open_inventory"),
            ("sect", "宗门", "🏯", "宗门信息、任务、商店与藏经阁", "open_sect"),
            ("residence", "洞府", "🏠", "购买洞府、升级建筑", "open_residence"),
            ("mind_method", "心法", "📜", "学习、装备心法", "open_mind_method"),
            ("farm", "药园", "🌿", "种植、浇水、收获灵植", "open_farm"),
            ("equipment", "炼器", "🔨", "强化装备、附魔与重铸词缀", "open_equipment"),
        ],
    ),
    (
        "修行进阶",
        [
            ("craft_life_treasure", "本命法宝", "⚔", "金丹期解锁后炼制本命法宝", "open_craft_life_treasure"),
            ("family", "家族", "🏛", "金丹期后创立并管理修仙家族", "open_family"),
            ("territory", "领地", "🗺", "元婴期后占据领地、布阵兴业", "open_territory"),
            ("difficulty_mode", "难度·模式", "⚙", "选择修行难度与多周目模式", "open_difficulty_mode"),
        ],
    ),
    (
        "心境世界",
        [
            ("heart_demon", "心魔·道心", "🔥", "查看道心/心魔、性格标签与顿悟状态", "open_heart_demon"),
            ("heaven_retribution", "天道反噬", "🌩", "查看天道注视与灵脉枯竭，散财行善以消灾", "open_heaven_retribution"),
            ("lifespan", "寿元·轮回", "⏳", "查看寿元、安排坐化后事、凝练残魂化身", "open_lifespan"),
            ("red_dust", "红尘炼心", "🌆", "入世历练、结缘历劫以淬炼道心", "open_red_dust"),
            ("hundred_schools", "百家争鸣", "⚖", "立派传道、自创功法、生活流派御劫", "open_hundred_schools"),
        ],
    ),
    (
        "见闻",
        [
            ("achievement", "成就", "🏆", "查看已达成与未达成成就", "open_achievement"),
            ("side_quest", "支线", "📋", "接取并查看支线任务", "open_side_quest"),
            ("auction_house", "拍卖行", "🔨", "竞拍稀有物品", "open_auction_house"),
            ("bounty_board", "悬赏", "📜", "接取击杀悬赏", "open_bounty_board"),
            ("compendium", "图鉴", "📖", "查看已收录的敌人、物品、技能", "open_compendium"),
            ("world_events", "天下大事", "🌐", "查看世界动态、事件链与全局状态", "open_world_events"),
        ],
    ),
    (
        "系统",
        [
            ("save", "保存", "💾", "把当前进度保存到 save.json", "save_game"),
            ("load", "读取", "📂", "从 save.json 读取进度", "load_game"),
            ("reset", "重开", "🔄", "清空当前进度，重新开始修仙", "reset"),
        ],
    ),
]


def _create_emoji_icon(emoji, size=32):
    """将 emoji 渲染为 QIcon，供 QToolButton 使用。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    font = QFont("Segoe UI Emoji", size * 2 // 3)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, emoji)
    painter.end()
    return QIcon(pixmap)


class _AccordionGroup(QWidget):
    """单个手风琴分组：可点击头部 + 子按钮栅格容器。

    收起时整组只占一行（高度 ≈ 36px），不显示子按钮。
    展开时显示头部（带 ▼ 箭头）+ 子按钮栅格。
    """

    toggled = Signal(str, bool)  # (group_name, expanded)

    def __init__(self, group_name, buttons, parent=None):
        super().__init__(parent)
        self.group_name = group_name
        self._buttons = buttons  # 原始配置（暂留，便于后续扩展）

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        # 折叠头：可 checkable 的 QToolButton，整行可点击
        self.header = QToolButton()
        self.header.setCheckable(True)
        self.header.setChecked(False)
        self.header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header.setMinimumHeight(36)
        self._update_header_text(expanded=False)
        self.header.setStyleSheet(
            "QToolButton {"
            "  background-color: #eef1f5;"
            "  border: 1px solid #cfd6dd;"
            "  border-radius: 6px;"
            "  padding: 4px 10px;"
            "  font-size: 13px;"
            "  font-weight: bold;"
            "  color: #2c3e50;"
            "  text-align: left;"
            "}"
            "QToolButton:hover {"
            "  background-color: #e2e8ee;"
            "  border-color: #adb5bd;"
            "}"
            "QToolButton:checked {"
            "  background-color: #d6e3f1;"
            "  border-color: #6c8ebf;"
            "  color: #1f3b6b;"
            "}"
        )
        self.header.toggled.connect(self._on_toggled)
        layout.addWidget(self.header)

        # 容器：子按钮栅格（默认隐藏）
        self.body = QWidget()
        self.body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        body_layout = QGridLayout(self.body)
        body_layout.setSpacing(6)
        body_layout.setContentsMargins(2, 6, 2, 6)

        self._child_buttons = []  # 顺序保留，便于 layout 调整
        for idx, (name, text, emoji, tooltip, _action) in enumerate(buttons):
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tooltip)
            btn.setIcon(_create_emoji_icon(emoji))
            btn.setIconSize(QSize(24, 24))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setMinimumHeight(58)
            btn.setProperty("action_name", name)
            btn.setStyleSheet(
                "QToolButton {"
                "  background-color: #f8f9fa;"
                "  border: 1px solid #dee2e6;"
                "  border-radius: 8px;"
                "  padding: 4px;"
                "  font-size: 12px;"
                "  color: #2c3e50;"
                "}"
                "QToolButton:hover {"
                "  background-color: #e9ecef;"
                "  border-color: #adb5bd;"
                "}"
                "QToolButton:pressed {"
                "  background-color: #dee2e6;"
                "}"
                "QToolButton:disabled {"
                "  color: #adb5bd;"
                "  background-color: #f1f3f5;"
                "}"
            )
            row = idx // 2
            col = idx % 2
            body_layout.addWidget(btn, row, col)
            self._child_buttons.append(btn)

        self.body.setVisible(False)
        layout.addWidget(self.body)

    def _update_header_text(self, expanded):
        arrow = "▼" if expanded else "▶"
        self.header.setText(f"  {arrow}  {self.group_name}  ({len(self._buttons)})")

    def is_expanded(self):
        return self.header.isChecked()

    def set_expanded(self, expanded, emit_signal=True):
        """设置展开/折叠状态。emit_signal=False 时不触发 toggled 信号（用于互斥模式收起其他组）。"""
        if not emit_signal:
            self.header.blockSignals(True)
        self.header.setChecked(expanded)
        if not emit_signal:
            self.header.blockSignals(False)
        # 同步显示状态
        self.body.setVisible(expanded)
        self._update_header_text(expanded=expanded)

    def _on_toggled(self, checked):
        self.body.setVisible(checked)
        self._update_header_text(expanded=checked)
        self.toggled.emit(self.group_name, checked)


class ActionPanel(QWidget):
    """右侧操作面板：手风琴折叠面板（Accordion）。

    API 完全兼容旧版：
    - _button_map: dict[str, QToolButton]（子按钮）
    - 所有 open_*/save_game/load_game Signal
    - refresh_buttons() / _on_cultivate / _on_breakthrough / _on_explore / _on_reset
    """

    # 自定义信号：与旧版完全一致
    open_inventory = Signal()
    open_map = Signal()
    open_npc = Signal()
    open_craft_life_treasure = Signal()
    open_equipment = Signal()
    open_sect = Signal()
    open_residence = Signal()
    open_mind_method = Signal()
    open_farm = Signal()
    open_achievement = Signal()
    open_side_quest = Signal()
    open_auction_house = Signal()
    open_bounty_board = Signal()
    open_compendium = Signal()
    open_world_events = Signal()
    open_secret_realm = Signal()
    open_family = Signal()
    open_territory = Signal()
    open_difficulty_mode = Signal()
    open_heart_demon = Signal()
    open_heaven_retribution = Signal()
    open_lifespan = Signal()
    open_red_dust = Signal()
    open_hundred_schools = Signal()
    save_game = Signal()
    load_game = Signal()

    # 互斥模式常量
    MODE_EXCLUSIVE = "exclusive"  # 默认：点击新组时自动收起其他
    MODE_MULTI = "multi"          # 可选：允许多个同时展开

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._mode_pref_key = "accordion_multi_expand"
        # 初始模式：优先读持久化偏好（config/ui_prefs.json），缺省互斥
        self._mode = self._load_mode_pref()
        self._default_group = "修行"  # 默认展开的最常用组

        # 主布局
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(4)
        self.layout.setContentsMargins(8, 8, 8, 8)

        # 顶部模式开关：勾选后允许多个分类同时展开
        self._mode_toggle = QCheckBox("允许多组同时展开")
        self._mode_toggle.setToolTip(
            "勾选：可同时展开多个分类；不勾选：互斥模式（展开一个自动收起其他）"
        )
        self._mode_toggle.setChecked(self._mode == self.MODE_MULTI)
        self._mode_toggle.setStyleSheet(
            "QCheckBox { font-size: 12px; color: #4a5568; padding: 2px 2px; }"
        )
        self._mode_toggle.toggled.connect(self._on_mode_toggle)
        self.layout.addWidget(self._mode_toggle)

        self._groups = {}        # group_name -> _AccordionGroup
        self._button_map = {}    # action_name -> QToolButton（兼容旧 API）

        # 构建所有手风琴组
        for group_name, buttons in _BUTTON_GROUPS:
            group = _AccordionGroup(group_name, buttons, parent=self)
            group.toggled.connect(self._on_group_toggled)
            self.layout.addWidget(group)
            self._groups[group_name] = group
            # 收集子按钮到 _button_map（兼容旧 API）
            for btn in group._child_buttons:
                action_name = btn.property("action_name")
                self._button_map[action_name] = btn

        self.layout.addStretch()

        # 默认展开最常用组
        if self._default_group in self._groups:
            self._groups[self._default_group].set_expanded(True, emit_signal=False)

        # 绑定内部回调（与旧版完全一致）
        self._bind_internal_callbacks()

    def set_mode(self, mode):
        """切换互斥/多展开模式。"""
        if mode in (self.MODE_EXCLUSIVE, self.MODE_MULTI):
            self._mode = mode

    def _load_mode_pref(self):
        """从 config/ui_prefs.json 读取模式偏好；缺省/异常时回退互斥。"""
        try:
            cfg_dir = getattr(self.engine, "config_dir", None)
            if not cfg_dir:
                return self.MODE_EXCLUSIVE
            path = os.path.join(cfg_dir, "ui_prefs.json")
            if not os.path.exists(path):
                return self.MODE_EXCLUSIVE
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return self.MODE_EXCLUSIVE
            return self.MODE_MULTI if data.get(self._mode_pref_key, False) else self.MODE_EXCLUSIVE
        except (json.JSONDecodeError, OSError, AttributeError):
            return self.MODE_EXCLUSIVE

    def _save_mode_pref(self, multi):
        """把模式偏好写回 config/ui_prefs.json（缺省文件时新建）。"""
        try:
            cfg_dir = getattr(self.engine, "config_dir", None)
            if not cfg_dir:
                return
            path = os.path.join(cfg_dir, "ui_prefs.json")
            data = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        data = {}
                except (json.JSONDecodeError, OSError):
                    data = {}
            data[self._mode_pref_key] = bool(multi)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _on_mode_toggle(self, checked):
        """顶部勾选框切换：更新模式并持久化偏好。"""
        self.set_mode(self.MODE_MULTI if checked else self.MODE_EXCLUSIVE)
        self._save_mode_pref(checked)

    def _on_group_toggled(self, group_name, expanded):
        """组切换时：互斥模式下收起其他组。"""
        if self._mode == self.MODE_EXCLUSIVE and expanded:
            for name, group in self._groups.items():
                if name != group_name and group.is_expanded():
                    group.set_expanded(False, emit_signal=False)

    def _bind_internal_callbacks(self):
        """绑定需要内部处理的按钮（闭关、突破、游历、重开）。"""
        self._button_map["cultivate"].clicked.connect(self._on_cultivate)
        self._button_map["breakthrough"].clicked.connect(self._on_breakthrough)
        self._button_map["explore"].clicked.connect(self._on_explore)
        self._button_map["reset"].clicked.connect(self._on_reset)

        # 其余按钮直接发射对应信号
        signal_map = {
            "inventory": self.open_inventory,
            "map": self.open_map,
            "npc": self.open_npc,
            "craft_life_treasure": self.open_craft_life_treasure,
            "equipment": self.open_equipment,
            "sect": self.open_sect,
            "residence": self.open_residence,
            "mind_method": self.open_mind_method,
            "farm": self.open_farm,
            "achievement": self.open_achievement,
            "side_quest": self.open_side_quest,
            "auction_house": self.open_auction_house,
            "bounty_board": self.open_bounty_board,
            "compendium": self.open_compendium,
            "world_events": self.open_world_events,
            "secret_realm": self.open_secret_realm,
            "family": self.open_family,
            "territory": self.open_territory,
            "difficulty_mode": self.open_difficulty_mode,
            "heart_demon": self.open_heart_demon,
            "heaven_retribution": self.open_heaven_retribution,
            "lifespan": self.open_lifespan,
            "red_dust": self.open_red_dust,
            "hundred_schools": self.open_hundred_schools,
            "save": self.save_game,
            "load": self.load_game,
        }
        for name, signal in signal_map.items():
            self._button_map[name].clicked.connect(signal.emit)

    def _on_cultivate(self):
        """点击修炼按钮时调用，弹出闭关弹窗选择月数。"""
        dialog = CultivateDialog(self.engine, parent=self)
        if dialog.exec() == CultivateDialog.Accepted:
            months = getattr(dialog, "selected_months", 12)
            self.engine.cultivate(months=months)

    def _on_breakthrough(self):
        """点击突破按钮时调用。"""
        self.engine.breakthrough()

    def _on_explore(self):
        """点击游历按钮时调用。"""
        self.engine.explore()

    def _on_reset(self):
        """点击重置按钮时调用，通知主窗口重新初始化。"""
        self.engine.notify("__RESET__")

    def refresh_buttons(self):
        """根据玩家状态刷新按钮可见性与可用性（与旧版完全一致）。"""
        player = self.engine.player
        craft_btn = self._button_map["craft_life_treasure"]
        # 本命法宝按钮：境界门槛由末尾统一解锁遍历处理
        craft_btn.setEnabled(True)
        craft_btn.setToolTip("消耗材料炼制本命法宝")

        # 秘境探索按钮：Roguelike 功能未开启时禁用
        sr_btn = self._button_map["secret_realm"]
        sr_enabled = self.engine.is_feature_enabled("roguelike_secret_realm")
        sr_btn.setEnabled(sr_enabled)
        if sr_enabled:
            sr_btn.setToolTip("进入 Roguelike 秘境，组队探索节点地图")
        else:
            sr_btn.setToolTip("秘境探索功能暂未开启")

        # 家族按钮：family 开关控制；境界门槛由末尾统一解锁遍历处理
        fam_btn = self._button_map["family"]
        fam_enabled = self.engine.is_feature_enabled("family")
        fam_btn.setEnabled(fam_enabled)
        fam_btn.setToolTip("管理修仙家族：成员、建筑、外交" if fam_enabled else "家族功能未开启")

        # 领地按钮：territory 开关控制；境界门槛由末尾统一解锁遍历处理
        ter_btn = self._button_map["territory"]
        ter_enabled = self.engine.is_feature_enabled("territory")
        ter_btn.setEnabled(ter_enabled)
        ter_btn.setToolTip("占据领地、布置建筑与五行阵眼、扩张升阶" if ter_enabled else "领地功能未开启")

        # 心魔·道心按钮：开启心魔系统即常驻（属修心本征，无境界门槛）
        hd_btn = self._button_map["heart_demon"]
        hd_enabled = self.engine.is_feature_enabled("heart_demon")
        hd_btn.setEnabled(hd_enabled)
        if hd_enabled:
            hd_btn.setToolTip("查看道心/心魔、性格标签与顿悟状态")
        else:
            hd_btn.setToolTip("心魔·道心系统未开启")

        # 天道反噬按钮：常驻（属世界对玩家的反馈）
        hr_btn = self._button_map["heaven_retribution"]
        hr_enabled = self.engine.is_feature_enabled("heaven_retribution")
        hr_btn.setEnabled(hr_enabled)
        if hr_enabled:
            gaze = getattr(self.engine.player, "heaven_gaze", 0)
            hr_btn.setToolTip(f"天道注视 {gaze}/100；散财行善可消灾")
        else:
            hr_btn.setToolTip("天道反噬系统未开启")

        # 寿元·轮回按钮：常驻（属晚年玩法本征）
        ls_btn = self._button_map["lifespan"]
        ls_enabled = self.engine.is_feature_enabled("lifespan_reincarnation")
        ls_btn.setEnabled(ls_enabled)
        if ls_enabled:
            ls_btn.setToolTip("查看寿元、安排坐化后事、凝练残魂化身")
        else:
            ls_btn.setToolTip("寿元·轮回系统未开启")

        # 红尘炼心按钮：常驻（属心境淬炼本征，无境界门槛）
        rd_btn = self._button_map["red_dust"]
        rd_enabled = self.engine.is_feature_enabled("red_dust")
        rd_btn.setEnabled(rd_enabled)
        if rd_enabled:
            active = getattr(self.engine.player, "red_dust_active", False)
            suffix = "（历练中）" if active else ""
            rd_btn.setToolTip(f"入世历练、结缘历劫以淬炼道心{suffix}")
        else:
            rd_btn.setToolTip("红尘炼心系统未开启")

        # 百家争鸣按钮：常驻（属非传统修仙本征，无境界门槛）
        hs_btn = self._button_map["hundred_schools"]
        hs_enabled = self.engine.is_feature_enabled("hundred_schools")
        hs_btn.setEnabled(hs_enabled)
        if hs_enabled:
            sect = getattr(self.engine.player, "founded_sect", None)
            suffix = f"（{sect['name']}）" if sect else ""
            hs_btn.setToolTip(f"立派传道、自创功法、生活流派御劫{suffix}")
        else:
            hs_btn.setToolTip("百家争鸣系统未开启")

        # 统一境界解锁门槛（渐进解锁）：未达门槛的按钮禁用并显示锁提示
        for action_name, btn in self._button_map.items():
            if self.engine.is_action_unlocked(action_name):
                continue
            btn.setEnabled(False)
            hint = self.engine.get_unlock_hint(action_name)
            btn.setToolTip(hint or "境界不足，暂未解锁")
