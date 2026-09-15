from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QButtonGroup, QRadioButton, QFrame, QMessageBox, QListWidget,
    QListWidgetItem, QSplitter, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from game.cultivation_path import CultivationPathConfig


# 流派详细描述（用于详情面板展示）
_PATH_DETAILS = {
    "fa": {
        "feature": "真气护盾：受到伤害时优先扣真气（2:1）\n技能伤害 ×1.3，血量 ×0.8",
        "playstyle": "远程术法流，脆皮高伤",
    },
    "ti": {
        "feature": "怒气积累：受击加怒，怒气越高攻击越强\n反震：20% 概率反弹 50% 伤害\n血量 ×1.6、防御 ×1.5、真气 ×0.7",
        "playstyle": "肉盾近战流，抗打能反",
    },
    "jian": {
        "feature": "剑意积累：每回合 +1 层剑意，每层 +5% 伤害\n暴击率 +25%，暴击伤害 ×2\n需装备剑类武器（无剑伤害 ×0.6）",
        "playstyle": "爆发刺客流，剑出必杀",
    },
    "xie": {
        "feature": "邪气积累：修炼/战斗加邪气，每点 +1% 攻击\n击杀回血 30%\n邪气 ≥50 触发正道追杀",
        "playstyle": "高风险高回报，吞噬流",
    },
    "dan": {
        "feature": "丹火积累：每回合 +5，受击 +2\n治疗效果 ×1.5（含所有治疗技能）\n丹火越高攻击越强（每点 +0.5%）\n自带 10% 减伤（药石之躯）",
        "playstyle": "续航型，现场炼丹，治疗 buff",
    },
    "qi": {
        "feature": "器灵积累：每回合 +3，受击 +3\n装备加成 ×2（攻击+防御均翻倍）\n器灵越高攻击越强（每点 +1%）\n可永久祭炼武器（+5 基础攻击）",
        "playstyle": "装备流，法宝共鸣，攻防一体",
    },
    "shou": {
        "feature": "兽魂收集：击败野兽 30% 概率获得兽魂（上限 5）\n兽魂抵挡：每只兽魂抵挡 5% 伤害\n每只兽魂 +5% 攻击\n修炼有概率获得兽魂",
        "playstyle": "召唤流，人兽协同，数量压制",
    },
    "hun": {
        "feature": "神识积累：每回合 +10，受击 +5\n技能伤害 ×1.8（全流派最高）\n无视敌人防御（神识攻击）\n神识越高技能越强（每点 +1.5%）\n血量 ×0.6（玻璃大炮）\n击杀吸收神魂（+20 神识）\n万魂归一后神识归零，下回合眩晕（反噬）",
        "playstyle": "玻璃大炮，无视防御，精神控制",
    },
    "zhen": {
        "feature": "阵纹积累：每回合 +1（上限 9）\n布阵困敌：八卦阵概率困住敌人 2 回合\n布阵削弱：困仙阵 3 回合内敌人攻防 -40%\n万阵归一：消耗所有阵纹，每点 +10% 伤害\n五行阵法：需五行灵根，巨额全属性伤害\n控制成功率 +30%",
        "playstyle": "控场型，布阵困敌，越战越强",
    },
    "fu": {
        "feature": "符箓预制：修炼时每月 +2 张（上限 20）\n战斗瞬发：专属技能无冷却、无真气消耗\n五雷符：50% 暴击率\n镇妖符：封印敌人技能 2 回合\n万符诀：连发 5 符，伤害 ×5\n血符术：消耗生命+符箓，伤害 ×3 并吸血\n符箓用尽时技能威力大减",
        "playstyle": "爆发型，符箓囤积，瞬发连击",
    },
}

# 难度星级映射
_DIFFICULTY_STARS = {1: "★", 2: "★★", 3: "★★★", 4: "★★★★", 5: "★★★★★"}

# 灵根属性中文映射
_ELEMENT_NAMES = {
    "metal": "金", "wood": "木", "water": "水",
    "fire": "火", "earth": "土", "none": "无", "all": "五行",
}


class CultivationPathDialog(QDialog):
    """
    修炼流派选择弹窗。
    支持滚动列表+详情面板布局，可展示 8+ 个流派。
    玩家在灵根觉醒后选择修炼方向。
    """

    def __init__(self, spiritual_roots=None, allowed_paths=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("求道之路")
        self.resize(900, 640)
        self.selected_path = None  # 最终选定的流派 ID
        self.spiritual_roots = spiritual_roots or []
        self.allowed_paths = allowed_paths or []  # 非空时仅展示这些流派

        # 加载流派配置
        self.path_config = CultivationPathConfig()

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("== 求道之路 ==")
        title.setStyleSheet("font-weight: bold; font-size: 18px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 说明
        info = QLabel(
            "道友，灵根已觉醒，现在请选择你的修炼之道。\n"
            "不同流派有不同的属性修正、专属资源和战斗机制，选择与灵根协同的流派可获额外加成。"
        )
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        # 左右分栏：左侧流派列表 + 右侧详情面板
        splitter = QSplitter(Qt.Horizontal)

        # ===== 左侧：流派列表（滚动） =====
        left_widget = QFrame()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("流派列表（点击选择）："))
        self.path_list = QListWidget()
        # 遍历所有流派添加到列表
        all_paths = self.path_config.get_all_path_ids()
        for path_id in all_paths:
            # 模式限制：allowed_paths 非空时仅展示被允许的流派
            if self.allowed_paths and path_id not in self.allowed_paths:
                continue
            path_data = self.path_config.get_path(path_id)
            if not path_data:
                continue
            name = path_data["name"]
            diff = path_data.get("difficulty", 1)
            diff_stars = _DIFFICULTY_STARS.get(diff, "★")
            # 协同提示
            synergy_hint = self._get_synergy_hint(path_id)
            synergy_tag = f"  [协同]" if synergy_hint else ""
            display = f"{name}  {diff_stars}{synergy_tag}"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, path_id)
            # 根据流派主题色设置列表项字体颜色，提升视觉辨识度
            color = path_data.get("color", "#888888")
            item.setForeground(QColor(color))
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            self.path_list.addItem(item)

        self.path_list.setCurrentRow(0)
        self.path_list.itemClicked.connect(self._on_path_selected)
        left_layout.addWidget(self.path_list)
        splitter.addWidget(left_widget)

        # ===== 右侧：详情面板（滚动） =====
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)

        self.detail_widget = QFrame()
        self.detail_layout = QVBoxLayout(self.detail_widget)
        self.detail_layout.setAlignment(Qt.AlignTop)

        # 详情标签（动态更新内容）
        self.detail_title = QLabel("")
        self.detail_title.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.detail_title.setWordWrap(True)
        self.detail_layout.addWidget(self.detail_title)

        self.detail_desc = QLabel("")
        self.detail_desc.setWordWrap(True)
        self.detail_desc.setStyleSheet("padding: 4px;")
        self.detail_layout.addWidget(self.detail_desc)

        self.detail_modifiers = QLabel("")
        self.detail_modifiers.setWordWrap(True)
        self.detail_modifiers.setStyleSheet("color: #3498db; padding: 4px;")
        self.detail_layout.addWidget(self.detail_modifiers)

        self.detail_feature = QLabel("")
        self.detail_feature.setWordWrap(True)
        self.detail_feature.setStyleSheet("color: #bdc3c7; padding: 4px;")
        self.detail_layout.addWidget(self.detail_feature)

        self.detail_playstyle = QLabel("")
        self.detail_playstyle.setWordWrap(True)
        self.detail_playstyle.setStyleSheet("color: #f39c12; padding: 4px;")
        self.detail_layout.addWidget(self.detail_playstyle)

        self.detail_skills = QLabel("")
        self.detail_skills.setWordWrap(True)
        self.detail_skills.setStyleSheet("color: #9b59b6; padding: 4px;")
        self.detail_layout.addWidget(self.detail_skills)

        self.detail_synergy = QLabel("")
        self.detail_synergy.setWordWrap(True)
        self.detail_synergy.setStyleSheet("color: #27ae60; padding: 4px;")
        self.detail_layout.addWidget(self.detail_synergy)

        right_scroll.setWidget(self.detail_widget)
        splitter.addWidget(right_scroll)

        # 左右比例 1:2
        splitter.setSizes([300, 600])
        layout.addWidget(splitter, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.confirm_btn = QPushButton("确认入道")
        self.confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self.confirm_btn)
        layout.addLayout(btn_layout)

        # 初始化显示第一个流派
        if all_paths:
            self._on_path_selected(self.path_list.item(0))

    def _on_path_selected(self, item):
        """选中流派时更新右侧详情面板。"""
        path_id = item.data(Qt.UserRole)
        path = self.path_config.get_path(path_id)
        if not path:
            return
        self.selected_path = path_id

        # 标题
        color = path.get("color", "#888")
        diff = path.get("difficulty", 1)
        diff_stars = _DIFFICULTY_STARS.get(diff, "★")
        self.detail_title.setText(f"【{path['name']}】  难度 {diff_stars}")
        self.detail_title.setStyleSheet(
            f"font-weight: bold; font-size: 16px; color: {color}; padding: 4px;"
        )

        # 描述
        self.detail_desc.setText(f"{path['description']}")

        # 属性修正
        mods = path.get("modifiers", {})
        mod_lines = []
        mod_names = {
            "max_qi_mult": "真气上限",
            "max_health_mult": "生命上限",
            "attack_mult": "攻击",
            "defense_mult": "防御",
            "skill_damage_mult": "技能伤害",
            "crit_rate_bonus": "暴击率加成",
            "crit_damage_mult": "暴击伤害",
            "heal_bonus_mult": "治疗加成",
            "equipment_bonus_mult": "装备加成",
            "ignore_defense": "无视防御",
            "no_cooldown": "无冷却",
            "summon_bonus": "召唤加成",
            "control_bonus": "控制加成",
        }
        for k, v in mods.items():
            name_cn = mod_names.get(k, k)
            if isinstance(v, bool):
                mod_lines.append(f"  {name_cn}: {'✓' if v else '✗'}")
            elif isinstance(v, float) and v > 1.0:
                mod_lines.append(f"  {name_cn}: ×{v}")
            elif isinstance(v, float) and v < 1.0:
                mod_lines.append(f"  {name_cn}: ×{v}")
            else:
                mod_lines.append(f"  {name_cn}: {v}")
        self.detail_modifiers.setText("属性修正：\n" + "\n".join(mod_lines))

        # 核心机制
        detail = _PATH_DETAILS.get(path_id, {})
        feature = detail.get("feature", "")
        self.detail_feature.setText(f"核心机制：\n{feature}" if feature else "")

        # 玩法风格
        playstyle = detail.get("playstyle", "")
        self.detail_playstyle.setText(f"玩法风格：{playstyle}" if playstyle else "")

        # 专属技能
        skills = path.get("exclusive_skills", [])
        if skills:
            self.detail_skills.setText(f"专属技能：{', '.join(skills)}")
        else:
            self.detail_skills.setText("专属技能：无")

        # 灵根协同
        synergy_hint = self._get_synergy_hint(path_id)
        if synergy_hint:
            self.detail_synergy.setText(f"灵根协同：{synergy_hint}")
        else:
            self.detail_synergy.setText("灵根协同：无")

    def _get_synergy_hint(self, path_id):
        """检查玩家灵根与该流派是否有协同，有则返回提示文本。"""
        if not self.spiritual_roots:
            return ""
        hints = []
        for elem in self.spiritual_roots:
            mult = self.path_config.get_synergy_multiplier(path_id, elem)
            if mult > 1.0:
                elem_cn = _ELEMENT_NAMES.get(elem, elem)
                hints.append(f"{elem_cn}灵根 ×{mult}")
        return "  ".join(hints) if hints else ""

    def _on_confirm(self):
        """确认选择流派。"""
        if not self.selected_path:
            QMessageBox.warning(self, "提示", "请选择一个修炼流派！")
            return

        path = self.path_config.get_path(self.selected_path)
        QMessageBox.information(
            self, "入道",
            f"你选择了【{path['name']}】之道！\n"
            f"{path['description']}\n\n"
            f"愿你在修仙之路上走出自己的道。"
        )
        self.accept()

    def get_path(self):
        """获取选定的流派 ID。"""
        return self.selected_path
