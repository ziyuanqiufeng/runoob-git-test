from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QButtonGroup, QRadioButton, QMessageBox,
)
from PySide6.QtCore import Qt


class LifeTreasureCraftDialog(QDialog):
    """本命法宝炼制弹窗：选择属性方向后消耗材料炼制。"""

    # 炼制配方：每种方向消耗相同材料，产出不同属性
    RECIPE = {
        "attack": {
            "name": "焚天本命珠",
            "description": "以火灵淬炼的本命法宝，攻击凌厉。",
            "effects": {"attack": 15, "health": 10},
            "materials": {"spirit_stone": 10, "demon_core": 3},
        },
        "defense": {
            "name": "玄铁本命盾",
            "description": "以妖核精华铸就的本命法宝，防御厚重。",
            "effects": {"defense": 8, "health": 20},
            "materials": {"spirit_stone": 10, "demon_core": 3},
        },
        "health": {
            "name": "长生本命玉",
            "description": "以灵石生气滋养的本命法宝，延年益寿。",
            "effects": {"attack": 5, "health": 50},
            "materials": {"spirit_stone": 10, "demon_core": 3},
        },
        "balanced": {
            "name": "混沌本命珠",
            "description": "阴阳平衡的本命法宝，攻守兼备。",
            "effects": {"attack": 8, "defense": 4, "health": 25},
            "materials": {"spirit_stone": 10, "demon_core": 3},
        },
    }

    # 方向中文名
    DIRECTION_NAMES = {
        "attack": "攻击型",
        "defense": "防御型",
        "health": "生命型",
        "balanced": "均衡型",
    }

    def __init__(self, player, item_library, engine, parent=None):
        super().__init__(parent)
        self.player = player
        self.item_library = item_library
        self.engine = engine
        self.setWindowTitle("炼制本命法宝")
        self.resize(360, 300)

        layout = QVBoxLayout(self)

        # 说明文字
        info = QLabel(
            "金丹期方可炼制本命法宝。选择属性方向，消耗材料进行炼制。\n"
            "所需材料：灵石×10、妖核×3"
        )
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        # 当前材料显示
        self.material_label = QLabel(self._material_text())
        self.material_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.material_label)

        # 属性方向选择
        self.direction_group = QButtonGroup(self)
        self.radio_buttons = {}
        for direction in ["attack", "defense", "health", "balanced"]:
            rb = QRadioButton(self.DIRECTION_NAMES[direction])
            self.radio_buttons[direction] = rb
            self.direction_group.addButton(rb)
            layout.addWidget(rb)
        # 默认选中均衡型
        self.radio_buttons["balanced"].setChecked(True)

        # 炼制按钮
        self.craft_btn = QPushButton("开始炼制")
        self.craft_btn.clicked.connect(self._on_craft)
        layout.addWidget(self.craft_btn)

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _material_text(self):
        """生成当前材料数量文本。"""
        stone = self.player.count_item("spirit_stone")
        core = self.player.count_item("demon_core")
        return f"当前拥有：灵石×{stone}、妖核×{core}"

    def _get_selected_direction(self):
        """获取当前选中的属性方向。"""
        for direction, rb in self.radio_buttons.items():
            if rb.isChecked():
                return direction
        return "balanced"

    def _on_craft(self):
        """执行炼制。"""
        direction = self._get_selected_direction()
        recipe = self.RECIPE[direction]

        # 检查是否已装备本命法宝（炼制会替换旧的）
        old = self.player.equipment.get("life_treasure")

        # 检查材料
        for item_id, need in recipe["materials"].items():
            if self.player.count_item(item_id) < need:
                QMessageBox.warning(
                    self,
                    "材料不足",
                    f"炼制{self.DIRECTION_NAMES[direction]}本命法宝需要 "
                    f"{item_id}×{need}，你当前只有 "
                    f"{self.player.count_item(item_id)} 个。",
                )
                return

        # 消耗材料
        for item_id, need in recipe["materials"].items():
            self.player.consume_items(item_id, need)

        # 创建本命法宝物品
        item = self.item_library.create_custom_item(
            item_id=f"life_treasure_{direction}",
            name=recipe["name"],
            item_type="life_treasure",
            value=500,
            description=recipe["description"],
            effects=recipe["effects"],
        )
        self.player.add_item(item)

        # 自动装备（金丹期已解锁槽位）
        self.player.equip_item(item)

        # 提示
        msg = f"你成功炼制了【{recipe['name']}】并收入本命法宝槽位！"
        if old:
            msg += f"\n原本命法宝【{old.name}】已卸下并放入背包。"
        QMessageBox.information(self, "炼制成功", msg)

        # 推进时间：炼制消耗 3 个月
        self.engine.world.advance(3)
        self.player.add_age_months(3)
        self.engine._auto_save()

        self.accept()
