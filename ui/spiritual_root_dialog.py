import random

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QButtonGroup, QRadioButton, QMessageBox
)
from PySide6.QtCore import Qt


# 五行属性中文名
_ELEMENT_NAMES = {
    "metal": "金", "wood": "木", "water": "水",
    "fire": "火", "earth": "土",
}

# 灵根数量 → 称谓
_ROOT_NAMES = {1: "天灵根", 2: "真灵根", 3: "异灵根", 4: "伪灵根", 5: "五行灵根"}

# 灵根数量 → 修炼倍率
_MULTIPLIER = {1: 1.0, 2: 1.5, 3: 2.0, 4: 2.8, 5: 4.0}

# 灵根数量 → 纯度范围 [min, max]，灵根越少纯度越高
_PURITY_RANGES = {
    1: [1.1, 1.5],
    2: [0.9, 1.2],
    3: [0.8, 1.1],
    4: [0.7, 1.0],
    5: [0.6, 0.9],
}

# 纯度阈值：>= 1.2 为"纯"，< 0.9 为"杂"
_PURITY_PURE_THRESHOLD = 1.2
_PURITY_MIXED_THRESHOLD = 0.9


def _purity_label(purity):
    """根据纯度值返回标签：纯/空/杂。"""
    if purity >= _PURITY_PURE_THRESHOLD:
        return "纯"
    if purity < _PURITY_MIXED_THRESHOLD:
        return "杂"
    return ""


class SpiritualRootDialog(QDialog):
    """
    开局灵根选择弹窗。
    玩家可以选择「天命随机」或「自选灵根」两种模式。
    觉醒时随机生成各灵根纯度，纯度影响该属性技能伤害。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("灵根觉醒")
        self.resize(450, 450)
        self.selected_roots = None     # 最终选定的灵根列表
        self.selected_purities = None  # 灵根纯度字典 {"fire": 1.3, ...}

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("== 灵根觉醒 ==")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 说明文字
        info = QLabel(
            "修仙之路，灵根为本。\n"
            "灵根越多，修炼越慢，但可驾驭的属性术法越丰富。\n"
            "灵根越少，修炼越快，专精一道，且纯度更高。\n\n"
            "天灵根（1属性）：修炼 1.0x，纯度 1.1~1.5\n"
            "真灵根（2属性）：修炼 1.5x，纯度 0.9~1.2\n"
            "异灵根（3属性）：修炼 2.0x，纯度 0.8~1.1\n"
            "伪灵根（4属性）：修炼 2.8x，纯度 0.7~1.0\n"
            "五行灵根（5属性）：修炼 4.0x，纯度 0.6~0.9\n\n"
            "纯度 ≥ 1.2 为「纯」灵根，技能伤害加成；\n"
            "纯度 < 0.9 为「杂」灵根，技能伤害削弱。"
        )
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        # 模式选择
        mode_label = QLabel("\n请选择觉醒方式：")
        mode_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(mode_label)

        self.mode_group = QButtonGroup(self)
        self.random_radio = QRadioButton("天命随机（按概率随机觉醒灵根）")
        self.random_radio.setChecked(True)
        self.mode_group.addButton(self.random_radio)
        layout.addWidget(self.random_radio)

        self.choose_radio = QRadioButton("自选灵根（选择 1~3 个属性）")
        self.mode_group.addButton(self.choose_radio)
        layout.addWidget(self.choose_radio)

        # 自选灵根的复选按钮
        self.element_layout = QVBoxLayout()
        self.element_buttons = {}
        self.element_group = QButtonGroup(self)
        self.element_group.setExclusive(False)  # 允许多选
        for element, name in _ELEMENT_NAMES.items():
            btn = QRadioButton(f"{name}（{element}）")
            self.element_buttons[element] = btn
            self.element_group.addButton(btn)
            self.element_layout.addWidget(btn)
        layout.addLayout(self.element_layout)

        # 初始禁用自选区域
        self._update_element_enabled()

        # 切换模式时更新自选区域可用状态
        self.choose_radio.toggled.connect(self._update_element_enabled)

        # 确认按钮
        btn_layout = QHBoxLayout()
        self.confirm_btn = QPushButton("确认觉醒")
        self.confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addStretch()
        btn_layout.addWidget(self.confirm_btn)
        layout.addLayout(btn_layout)

    def _update_element_enabled(self):
        """自选模式启用属性选择，随机模式禁用。"""
        enabled = self.choose_radio.isChecked()
        for btn in self.element_buttons.values():
            btn.setEnabled(enabled)

    def _generate_purities(self, root_count):
        """
        根据灵根数量生成各灵根的纯度值。
        灵根越少，纯度范围越高（专精路线）；灵根越多，纯度越低（全面路线）。
        返回字典：{element: purity}
        """
        min_p, max_p = _PURITY_RANGES.get(root_count, [0.8, 1.0])
        return {
            e: round(random.uniform(min_p, max_p), 2)
            for e in self.selected_roots
        }

    def _on_confirm(self):
        """确认选择灵根。"""
        if self.random_radio.isChecked():
            # 天命随机：按权重抽取灵根数量
            counts = [1, 2, 3, 4, 5]
            weights = [20, 30, 30, 15, 5]
            root_count = random.choices(counts, weights=weights, k=1)[0]
            # 从五行中随机抽取
            self.selected_roots = random.sample(
                list(_ELEMENT_NAMES.keys()), root_count
            )
        else:
            # 自选模式：收集选中的属性
            selected = [
                e for e, btn in self.element_buttons.items() if btn.isChecked()
            ]
            if not selected:
                QMessageBox.warning(self, "提示", "请至少选择一个属性灵根！")
                return
            if len(selected) > 3:
                QMessageBox.warning(self, "提示", "自选最多 3 个属性灵根！")
                return
            self.selected_roots = selected

        # 生成各灵根纯度
        self.selected_purities = self._generate_purities(len(self.selected_roots))

        # 显示觉醒结果（含纯度信息）
        root_name = _ROOT_NAMES.get(len(self.selected_roots), "杂灵根")
        mult = _MULTIPLIER.get(len(self.selected_roots), 4.0)
        # 构建灵根详情文本：属性名+纯度标签+纯度值
        detail_parts = []
        for e in self.selected_roots:
            purity = self.selected_purities[e]
            label = _purity_label(purity)
            detail_parts.append(f"{label}{_ELEMENT_NAMES[e]}({purity})")
        detail_text = "、".join(detail_parts)

        QMessageBox.information(
            self, "灵根觉醒",
            f"你觉醒了【{root_name}】！\n"
            f"灵根属性：{detail_text}\n"
            f"修炼倍率：{mult}x\n\n"
            f"纯度 ≥ 1.2 为纯灵根（伤害加成），< 0.9 为杂灵根（伤害削弱）。"
        )
        self.accept()

    def get_roots(self):
        """获取选定的灵根列表。"""
        return self.selected_roots

    def get_purities(self):
        """获取灵根纯度字典。"""
        return self.selected_purities
