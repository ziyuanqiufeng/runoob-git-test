import re
import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox
)
from PySide6.QtCore import Signal, QEvent, Qt
from PySide6.QtGui import QPixmap
from ui.status_panel import _get_realm_border_color, _PATH_COLORS
from ui.portrait_label import PortraitLabel
from ui.deploy_treasure_dialog import DeployPreviewDialog


# 默认颜色配置（当配置文件不存在或读取失败时使用）
_DEFAULT_COLORS = {
    "red": "#e74c3c",
    "green": "#27ae60",
    "yellow": "#f39c12",
    "orange": "#e67e22",
    "cyan": "#00b7b3",
    "blue": "#3498db",
    "default": "#ecf0f1",
}

_DEFAULT_LABELS = {
    "red": "敌人攻击/伤害",
    "green": "治疗行为",
    "yellow": "逃跑行为",
    "orange": "狂暴状态",
    "cyan": "玩家攻击行为",
    "blue": "获得奖励",
}


def _load_color_config(config_dir="config"):
    """
    从 combat_colors.json 加载颜色配置。
    若文件不存在或格式错误，返回默认配置。
    """
    colors = dict(_DEFAULT_COLORS)
    labels = dict(_DEFAULT_LABELS)
    config_path = os.path.join(config_dir, "combat_colors.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 合并用户配置（用户只需写想修改的颜色）
            colors.update(data.get("colors", {}))
            labels.update(data.get("labels", {}))
        except (json.JSONDecodeError, IOError):
            pass
    return colors, labels


# 模块级加载，避免每次解析日志都读文件
_COLOR_MAP, _COLOR_LABELS = _load_color_config()


def _parse_color_tag(text):
    """
    解析日志中的颜色标记前缀 [color]，返回 (纯文本, html)。
    无标记则返回 (原文本, 转义后的 html)。
    """
    match = re.match(r"^\[(\w+)\](.*)$", text)
    if match and match.group(1) in _COLOR_MAP:
        color_key = match.group(1)
        content = match.group(2)
        color_hex = _COLOR_MAP[color_key]
        # 转义 HTML 特殊字符后着色
        safe = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return content, f'<span style="color:{color_hex}">{safe}</span>'
    # 无标记，使用 default 颜色
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    default_color = _COLOR_MAP.get("default", "#ecf0f1")
    return text, f'<span style="color:{default_color}">{safe}</span>'


def _build_legend_html():
    """根据当前颜色配置生成图例 HTML。"""
    # 按固定顺序展示核心颜色
    order = ["cyan", "green", "red", "orange", "yellow", "blue"]
    parts = []
    for key in order:
        if key in _COLOR_MAP and key in _COLOR_LABELS:
            parts.append(
                f'<span style="color:{_COLOR_MAP[key]}">■</span>{_COLOR_LABELS[key]}'
            )
    return "  ".join(parts)


class CombatDialog(QDialog):
    """战斗弹窗，进行回合制战斗，支持技能。"""

    combat_finished = Signal(str)  # 战斗结束时发出结果：win / lose / flee / enemy_flee

    def __init__(self, player, enemy, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("战斗")
        self.resize(500, 500)
        self.player = player
        self.enemy = enemy
        self.engine = engine

        # 主布局
        layout = QVBoxLayout(self)

        # 顶部状态栏：头像 + 名称/状态
        status_layout = QHBoxLayout()

        # 玩家侧（使用统一头像组件）
        player_side = QVBoxLayout()
        border_color = _get_realm_border_color(getattr(player, "realm_id", "qi_refining_1"))
        self.player_portrait = PortraitLabel(
            size=80,
            border_color=border_color,
            border_width=2,
            placeholder_text="我",
            circular=True,
        )
        self.player_label = QLabel()
        self.player_label.setAlignment(Qt.AlignCenter)
        player_side.addWidget(self.player_portrait, alignment=Qt.AlignCenter)
        player_side.addWidget(self.player_label)

        # 敌人侧
        enemy_side = QVBoxLayout()
        self.enemy_portrait = QLabel()
        self.enemy_portrait.setFixedSize(80, 80)
        self.enemy_portrait.setAlignment(Qt.AlignCenter)
        self.enemy_portrait.setStyleSheet(
            "border: 2px solid #e74c3c; border-radius: 4px; background: #f0f0f0;"
        )
        self.enemy_portrait.setText("敌")
        self.enemy_label = QLabel()
        self.enemy_label.setAlignment(Qt.AlignCenter)
        enemy_side.addWidget(self.enemy_portrait, alignment=Qt.AlignCenter)
        enemy_side.addWidget(self.enemy_label)

        status_layout.addLayout(player_side)
        status_layout.addStretch()
        status_layout.addLayout(enemy_side)
        layout.addLayout(status_layout)

        # 真气显示
        self.qi_label = QLabel()
        layout.addWidget(self.qi_label)

        # 真气/技能消耗提示栏（鼠标悬停在技能按钮上时显示具体消耗）
        self.qi_cost_label = QLabel("当前真气：— / 技能消耗：—")
        self.qi_cost_label.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(self.qi_cost_label)

        # buff/debuff 状态显示栏
        self.buff_label = QLabel()
        layout.addWidget(self.buff_label)

        # 战斗日志（用 HTML 渲染着色）
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setHtml("")
        layout.addWidget(self.log_edit, 1)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.attack_btn = QPushButton("普通攻击")
        self.attack_btn.clicked.connect(self._on_attack)
        btn_layout.addWidget(self.attack_btn)

        self.flee_btn = QPushButton("逃跑")
        self.flee_btn.clicked.connect(self._on_flee)
        btn_layout.addWidget(self.flee_btn)

        # 维度③·M16：战斗中手动部署生活法宝（符箓/阵盘）为临时增益
        self.deploy_btn = QPushButton("部署法宝")
        self.deploy_btn.clicked.connect(self._on_deploy_treasure)
        btn_layout.addWidget(self.deploy_btn)

        layout.addLayout(btn_layout)

        # 技能按钮区域：每行一个按钮 + 经验进度条
        self.skill_layout = QVBoxLayout()
        self.skill_layout.setSpacing(4)
        self.skill_buttons = []
        self._skill_progress_bars = {}
        self._create_skill_buttons()
        layout.addLayout(self.skill_layout)

        # 图例提示（从配置文件动态生成）
        legend = QLabel(_build_legend_html())
        layout.addWidget(legend)

        # 初始刷新
        self._refresh_status()
        self._load_player_portrait()
        self._append_log(f"战斗开始！你遭遇了 {enemy.name}。")

    def _append_log(self, text):
        """追加一条日志，自动解析颜色标记。"""
        _, html = _parse_color_tag(text)
        self.log_edit.append(html)

    def _create_skill_buttons(self):
        """根据玩家已学技能创建技能按钮与进度条，标注属性前缀并用颜色/图标标识状态。"""
        # 属性中文名
        element_names = {
            "metal": "金", "wood": "木", "water": "水",
            "fire": "火", "earth": "土", "none": "无", "all": "五行",
        }
        # 清空旧按钮与进度条
        while self.skill_layout.count():
            item = self.skill_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # 递归清理子布局
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
        self.skill_buttons = []
        self._skill_btn_map = {}       # 按钮 -> skill_id，用于悬停提示
        self._skill_progress_bars = {} # skill_id -> QProgressBar

        if not self.player.skills:
            label = QLabel("尚未习得技能")
            self.skill_layout.addWidget(label)
            return

        for skill_id in self.player.skills:
            skill = self.engine.skill_library.get(skill_id)
            if not skill:
                continue
            # 属性前缀
            elem_name = element_names.get(skill.element, "?")
            btn_text = f"[{elem_name}]{skill.name}"
            btn = QPushButton(btn_text)

            # 使用引擎统一接口判断可用性并收集原因
            can_use, reasons = self.engine.get_skill_usability(skill_id, in_combat=True)
            btn.setEnabled(can_use)

            # 构建 tooltip：基础信息 + 使用条件 + 熟练度进度条与加成 + 不可用原因/成功率
            effective_cost = self.engine._get_effective_qi_cost(skill_id)
            prof_level = self.player.get_skill_proficiency(skill_id)
            prof_exp = self.player.skill_proficiency.get(skill_id, {}).get("exp", 0)
            need_exp = (
                prof_level * self.player.SKILL_PROFICIENCY_LEVEL_EXP
                if prof_level < self.player.SKILL_PROFICIENCY_MAX_LEVEL else 0
            )
            # 计算经验百分比并生成简易 HTML 进度条
            pct = int(prof_exp / need_exp * 100) if need_exp > 0 else 100
            bar_html = (
                f'<div style="background:#ecf0f1;border-radius:3px;height:10px;width:120px;">'
                f'<div style="background:#27ae60;border-radius:3px;height:10px;width:{pct}%;"></div></div>'
            )
            # 根据技能类型显示对应的熟练度加成
            category = self.engine._get_skill_category(skill)
            cat_names = {"damage": "伤害", "heal": "治疗", "control": "控制", "support": "辅助"}
            if category == "damage":
                bonus_text = f"伤害 +{int((self.player.get_skill_damage_multiplier(skill_id) - 1) * 100)}%"
            elif category == "heal":
                bonus_text = f"治疗 +{int((self.player.get_skill_heal_multiplier(skill_id) - 1) * 100)}%"
            elif category == "control":
                bonus_text = f"控制 +{int(self.player.get_skill_control_bonus(skill_id) * 100)}%"
            else:
                bonus_text = f"buff 持续 +{int((prof_level - 1) * self.player.SKILL_PROFICIENCY_SUPPORT_EXTRA_TURN_PER_LEVEL)} 回合"

            tooltip_lines = [
                f"<b>{skill.name}</b>",
                skill.description,
                f"类型：{cat_names.get(category, '伤害')}",
                f"熟练度：Lv.{prof_level} {bonus_text}",
                bar_html,
                f"消耗真气：{effective_cost}（熟练减耗后，基础 {skill.qi_cost}）",
                f"冷却：{skill.cooldown} 回合",
            ]
            # 在 tooltip 中展示该技能的满级专属特效说明，方便玩家提前了解收益
            mastery_lines = []
            for me in getattr(skill, "mastery_effects", []) or []:
                desc = me.get("description")
                if desc:
                    mastery_lines.append(
                        f"<span style='color:#e67e22'>★ 满级：{desc}</span>"
                    )
            if not mastery_lines:
                mastery_lines.append(
                    "<span style='color:#e67e22'>★ 满级特效：概率免冷却、附加额外效果</span>"
                )
            tooltip_lines.extend(mastery_lines)
            if skill.realm_id:
                realm_data = self.engine.world.get_realm(skill.realm_id)
                realm_name = realm_data.get("name", skill.realm_id) if realm_data else skill.realm_id
                tooltip_lines.append(f"需要境界：{realm_name}")
                rate = self.engine.get_skill_success_rate(skill_id)
                if rate < 1.0:
                    tooltip_lines.append(f"跨境界成功率：{int(rate * 100)}%")
            if skill.path_exclusive:
                path_names = {
                    "fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
                    "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
                    "zhen": "阵修", "fu": "符修",
                }
                tooltip_lines.append(f"需要流派：{path_names.get(skill.path_exclusive, skill.path_exclusive)}")
            if skill.element != "none":
                tooltip_lines.append(f"需要灵根：{element_names.get(skill.element, skill.element)}")
            if reasons:
                tooltip_lines.append("<br>⚠ " + "<br>⚠ ".join(reasons))
            btn.setToolTip("<html><body style='white-space:pre;'>" + "<br>".join(tooltip_lines) + "</body></html>")

            # 安装事件过滤器以响应鼠标悬停，实时显示技能消耗并高亮进度条
            btn.installEventFilter(self)
            self._skill_btn_map[btn] = skill_id

            btn.clicked.connect(lambda checked, sid=skill_id: self._on_skill(sid))

            # 为该技能创建可视经验进度条
            from PySide6.QtWidgets import QProgressBar
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(pct)
            progress.setTextVisible(False)
            progress.setFixedSize(80, 8)
            progress.setStyleSheet(
                "QProgressBar { border: 1px solid #bdc3c7; border-radius: 4px; background: #ecf0f1; }"
                "QProgressBar::chunk { background: #27ae60; border-radius: 4px; }"
            )
            self._skill_progress_bars[skill_id] = progress

            row_layout = QHBoxLayout()
            row_layout.addWidget(btn)
            row_layout.addWidget(progress)
            row_layout.addStretch()
            self.skill_layout.addLayout(row_layout)
            self.skill_buttons.append((btn, skill_id))

    def eventFilter(self, obj, event):
        """监听技能按钮的鼠标悬停事件，更新顶部真气/消耗提示并高亮进度条。"""
        if obj in self._skill_btn_map:
            skill_id = self._skill_btn_map[obj]
            if event.type() == QEvent.Type.Enter:
                self._update_qi_cost_label(skill_id)
                self._highlight_progress(skill_id, True)
            elif event.type() == QEvent.Type.Leave:
                self._update_qi_cost_label(None)
                self._highlight_progress(skill_id, False)
        return super().eventFilter(obj, event)

    def _highlight_progress(self, skill_id, active):
        """高亮/取消高亮指定技能的进度条。"""
        progress = self._skill_progress_bars.get(skill_id)
        if not progress:
            return
        if active:
            progress.setStyleSheet(
                "QProgressBar { border: 1px solid #2980b9; border-radius: 4px; background: #ecf0f1; }"
                "QProgressBar::chunk { background: #2980b9; border-radius: 4px; }"
            )
        else:
            progress.setStyleSheet(
                "QProgressBar { border: 1px solid #bdc3c7; border-radius: 4px; background: #ecf0f1; }"
                "QProgressBar::chunk { background: #27ae60; border-radius: 4px; }"
            )

    def _update_qi_cost_label(self, skill_id=None):
        """更新顶部真气/技能消耗提示。skill_id 为 None 时恢复默认提示。"""
        current_qi = self.player.qi
        if skill_id is None:
            self.qi_cost_label.setText(
                f"当前真气：{current_qi} / 将鼠标悬停在技能上查看消耗"
            )
            self.qi_cost_label.setStyleSheet("color: #7f8c8d;")
            return
        skill = self.engine.skill_library.get(skill_id)
        if not skill:
            return
        cost = self.engine._get_effective_qi_cost(skill_id)
        color = "#27ae60" if current_qi >= cost else "#e74c3c"
        self.qi_cost_label.setText(
            f"当前真气：{current_qi} / 技能消耗：{cost}"
        )
        self.qi_cost_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _refresh_status(self):
        """刷新双方血条、真气显示、buff 状态。"""
        # 玩家主灵根中文名（用于状态栏展示）
        element_names = {
            "metal": "金", "wood": "木", "water": "水",
            "fire": "火", "earth": "土", "none": "无", "all": "五行",
        }
        # 玩家主灵根：取第一个灵根属性，若无则显示"无"
        player_main_elem = (
            self.player.spiritual_roots[0]
            if self.player.spiritual_roots
            else "none"
        )
        player_elem_name = element_names.get(player_main_elem, "?")
        # 流派简称
        path_names = {"fa": "法", "ti": "体", "jian": "剑", "xie": "邪"}
        path_short = path_names.get(getattr(self.player, "cultivation_path", "fa"), "")
        self.player_label.setText(
            f"{self.player.name}[{player_elem_name}/{path_short}]\nHP: {self.player.health}/{self.player.max_health}"
        )
        # 敌人属性前缀显示
        enemy_elem_name = element_names.get(getattr(self.enemy, "element", "none"), "?")
        self.enemy_label.setText(
            f"{self.enemy.name}[{enemy_elem_name}]\nHP: {self.enemy.hp}/{self.enemy.max_hp}"
        )
        self.qi_label.setText(f"真气：{self.player.qi}")
        # 重置真气/消耗提示为默认状态
        self._update_qi_cost_label(None)

        # 构建 buff/debuff 状态提示文本
        buff_parts = []

        # 敌人防御 buff
        enemy_def_total = 0
        enemy_def_turns = 0
        for buff in getattr(self.engine, "enemy_defense_buffs", []):
            enemy_def_total += buff["amount"]
            enemy_def_turns = max(enemy_def_turns, buff["turns"])
        if enemy_def_total > 0:
            buff_parts.append(
                f'<span style="color:#e67e22">▲ 敌方防御 +{enemy_def_total}（{enemy_def_turns}回合）</span>'
            )

        # 玩家攻击削弱
        player_debuff_total = 0
        player_debuff_turns = 0
        for buff in getattr(self.engine, "player_attack_debuffs", []):
            player_debuff_total += buff["amount"]
            player_debuff_turns = max(player_debuff_turns, buff["turns"])
        if player_debuff_total > 0:
            buff_parts.append(
                f'<span style="color:#e74c3c">▼ 我方攻击 -{player_debuff_total}（{player_debuff_turns}回合）</span>'
            )

        # 毒素 DOT 效果
        dot_count = len(getattr(self.engine, "combat_dot_effects", []))
        if dot_count > 0:
            buff_parts.append(
                f'<span style="color:#9b59b6">☠ 中毒×{dot_count}</span>'
            )

        # 流派专属资源显示（战斗中实时更新）
        path_id = getattr(self.player, "cultivation_path", "fa")
        path_info = {
            "fa": ("护盾", "#3498db"),
            "ti": ("怒气", "#e67e22"),
            "jian": ("剑意", "#f1c40f"),
            "xie": ("邪气", "#9b59b6"),
        }
        if path_id in path_info:
            res_name, res_color = path_info[path_id]
            resource_info = self.player.get_path_resource()
            if resource_info:
                _, current, max_val = resource_info
                buff_parts.append(
                    f'<span style="color:{res_color}">◈ {res_name} {current}/{max_val}</span>'
                )

        if buff_parts:
            self.buff_label.setText("  ".join(buff_parts))
        else:
            self.buff_label.setText('<span style="color:#7f8c8d">无异常状态</span>')

        # 维度③·M16：战斗中「部署法宝」按钮按持有可部署法宝动态调整可用性
        if hasattr(self, "deploy_btn"):
            self.deploy_btn.setEnabled(
                len(self.engine.get_deployable_battle_consumables()) > 0
            )

        # 更新技能按钮状态，并用颜色/图标直观标识不可用原因
        for btn, skill_id in self.skill_buttons:
            cooldown = self.player.get_skill_cooldown(skill_id)
            skill = self.engine.skill_library.get(skill_id)
            elem_name = element_names.get(skill.element, "?")
            can_use, reasons = self.engine.get_skill_usability(skill_id, in_combat=True)
            btn.setEnabled(can_use)
            if cooldown > 0:
                btn.setText(f"[{elem_name}]{skill.name}({cooldown})")
            else:
                btn.setText(f"[{elem_name}]{skill.name}")

            # 根据不可用原因设置视觉样式：真气不足=红，境界不足=紫/警告，其他=灰
            style = ""
            effective_cost = self.engine._get_effective_qi_cost(skill_id)
            if self.player.qi < effective_cost:
                style = (
                    "QPushButton { color: #e74c3c; border: 1px solid #e74c3c; }"
                    "QPushButton:disabled { color: #c0392b; border: 1px solid #c0392b; }"
                )
            elif any("成功率" in r for r in reasons):
                # 跨境界：按钮可用但标紫边框和警告图标
                icon = "⚠"
                if not btn.text().startswith(icon):
                    btn.setText(f"{icon} {btn.text()}")
                style = (
                    "QPushButton { color: #8e44ad; border: 2px solid #8e44ad; }"
                    "QPushButton:disabled { color: #7d3c98; border: 2px solid #7d3c98; }"
                )
            elif reasons:
                # 冷却、流派、灵根、武器等原因：置灰
                style = (
                    "QPushButton { color: #7f8c8d; border: 1px solid #7f8c8d; }"
                    "QPushButton:disabled { color: #95a5a6; border: 1px solid #95a5a6; }"
                )
            else:
                style = "QPushButton { color: #2c3e50; border: 1px solid #bdc3c7; }"
            btn.setStyleSheet(style)

        # 同步更新每个技能的经验进度条
        for skill_id, progress in self._skill_progress_bars.items():
            prof_level = self.player.get_skill_proficiency(skill_id)
            prof_exp = self.player.skill_proficiency.get(skill_id, {}).get("exp", 0)
            need_exp = (
                prof_level * self.player.SKILL_PROFICIENCY_LEVEL_EXP
                if prof_level < self.player.SKILL_PROFICIENCY_MAX_LEVEL else 0
            )
            pct = int(prof_exp / need_exp * 100) if need_exp > 0 else 100
            progress.setValue(pct)

    def _load_player_portrait(self):
        """加载玩家头像到战斗界面的玩家侧，并同步边框颜色。"""
        # 同步边框颜色：战斗中境界可能变化，刷新时重新读取
        border_color = _get_realm_border_color(
            getattr(self.player, "realm_id", "qi_refining_1")
        )
        self.player_portrait.set_border_color(border_color)
        self.player_portrait.load_portrait(getattr(self.player, "portrait", None))

    def _on_attack(self):
        """玩家选择普通攻击。"""
        logs, result = self.engine.combat_round(self.enemy, action="attack")
        for log in logs:
            self._append_log(log)
        self._refresh_status()
        self._check_result(result)

    def _on_flee(self):
        """玩家选择逃跑。"""
        logs, result = self.engine.combat_round(self.enemy, action="flee")
        for log in logs:
            self._append_log(log)
        self._refresh_status()
        self._check_result(result)

    def _on_deploy_treasure(self):
        """维度③·M24：打开部署法宝预览确认弹窗，多选后确认部署。

        替代原「只部署持有最多的一类」逻辑，让玩家在战斗中也能预览每件法宝的
        增益描述并自行勾选，确认后逐件消耗并施加临时增益，刷新日志与状态栏。
        """
        deployed = DeployPreviewDialog.run(self.engine, self)
        if deployed:
            self._append_log(
                f"[cyan]你部署了 {len(deployed)} 件法宝，增益已生效。"
            )
        else:
            self._append_log("[gray]你暂未部署任何法宝。")
        self._refresh_status()

    def _on_skill(self, skill_id):
        """玩家选择技能。"""
        # 万魂归一反噬预警：使用后神识归零，下回合眩晕
        # 在确认施放前提示玩家，避免误用导致危险
        if skill_id == "all_souls_return":
            player = self.engine.player
            # 仅当玩家有神识时才提示（神识为0时无反噬风险）
            if getattr(player, "hun_sense", 0) > 0:
                reply = QMessageBox.warning(
                    self, "神识反噬警告",
                    f"万魂归一将消耗全部 {player.hun_sense} 点神识，\n"
                    f"下回合你将陷入眩晕，期间敌人攻击伤害 ×1.2！\n\n"
                    f"是否确认施放？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    self._append_log("[yellow]你收回了万魂归一之力，暂未施放。")
                    return
        logs, result = self.engine.combat_round(self.enemy, action="skill", skill_id=skill_id)
        for log in logs:
            self._append_log(log)
        self._refresh_status()
        self._check_result(result)

    def _check_result(self, result):
        """判断战斗是否结束，结束时触发技能熟练度衰减并可视化提示。"""
        decay_msg = ""
        if result in ("win", "flee", "enemy_flee", "lose"):
            decay_msg = self.engine.end_combat()
            if decay_msg:
                self._append_log(decay_msg)
                # 掉级时额外弹窗提示，去掉颜色标记用于纯文本弹窗
                if "掉级" in decay_msg:
                    plain_msg = re.sub(r"\[(\w+)\]", "", decay_msg)
                    QMessageBox.information(self, "技能熟练度衰减", plain_msg)

        if result == "win":
            self.attack_btn.setEnabled(False)
            self.flee_btn.setEnabled(False)
            for btn, _ in self.skill_buttons:
                btn.setEnabled(False)
            self._append_log("你赢得了这场战斗！")
            self.combat_finished.emit("win")
            # 把逃跑按钮改成关闭
            self.flee_btn.setText("关闭")
            self.flee_btn.setEnabled(True)
            self.flee_btn.clicked.disconnect(self._on_flee)
            self.flee_btn.clicked.connect(self.accept)
        elif result == "flee":
            self.combat_finished.emit("flee")
            self.accept()
        elif result == "enemy_flee":
            # 敌人逃跑，战斗结束但不掉落战利品
            self.attack_btn.setEnabled(False)
            for btn, _ in self.skill_buttons:
                btn.setEnabled(False)
            self._append_log(f"{self.enemy.name} 逃走了，战斗结束。")
            self.combat_finished.emit("enemy_flee")
            self.flee_btn.setText("关闭")
            self.flee_btn.setEnabled(True)
            self.flee_btn.clicked.disconnect(self._on_flee)
            self.flee_btn.clicked.connect(self.accept)
        elif result == "lose":
            self.attack_btn.setEnabled(False)
            self.flee_btn.setEnabled(False)
            for btn, _ in self.skill_buttons:
                btn.setEnabled(False)
            self._append_log("你倒下了...")
            self.combat_finished.emit("lose")
            self.flee_btn.setText("关闭")
            self.flee_btn.setEnabled(True)
            self.flee_btn.clicked.disconnect(self._on_flee)
            self.flee_btn.clicked.connect(self.accept)
