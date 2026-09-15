# -*- coding: utf-8 -*-
"""
炼丹阁弹窗：购买丹方、炼制丹药。
左侧显示已习得丹方与材料，右侧显示炼丹操作与成功率。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QWidget
)
from PySide6.QtCore import Qt


class AlchemyDialog(QDialog):
    """炼丹阁交互弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.item_library = engine.item_library

        self.setWindowTitle("炼丹阁")
        self.resize(700, 480)

        main_layout = QHBoxLayout(self)

        # 左侧：已习得丹方列表
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("<b>已习得丹方</b>"))
        self.recipe_list = QListWidget()
        self.recipe_list.setToolTip("选择丹方后可在右侧查看材料与成功率。")
        self.recipe_list.currentItemChanged.connect(self._on_recipe_selected)
        left_panel.addWidget(self.recipe_list)

        # 购买丹方按钮
        self.buy_recipe_btn = QPushButton("购买丹方与材料")
        self.buy_recipe_btn.setToolTip("打开炼丹阁商店，购买丹方与基础材料。")
        self.buy_recipe_btn.clicked.connect(self._open_shop)
        left_panel.addWidget(self.buy_recipe_btn)

        main_layout.addLayout(left_panel, 1)

        # 右侧：丹方详情与炼丹操作
        right_panel = QVBoxLayout()
        self.detail_label = QLabel("请选择左侧丹方。")
        self.detail_label.setWordWrap(True)
        self.detail_label.setMinimumHeight(120)
        self.detail_label.setStyleSheet("background: #f5f5f5; padding: 8px; border-radius: 4px;")
        right_panel.addWidget(self.detail_label)

        # 材料显示
        self.materials_label = QLabel("")
        self.materials_label.setWordWrap(True)
        right_panel.addWidget(self.materials_label)

        # 成功率显示
        self.rate_label = QLabel("")
        right_panel.addWidget(self.rate_label)

        # 炼丹按钮
        self.craft_btn = QPushButton("开始炼丹")
        self.craft_btn.setToolTip("消耗材料与时间进行炼制。")
        self.craft_btn.setEnabled(False)
        self.craft_btn.clicked.connect(self._on_craft)
        right_panel.addWidget(self.craft_btn)

        # 提示标签
        tip = QLabel("提示：丹修流派炼丹成功率更高，失败后有几率挽回一半材料。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #666; font-size: 12px;")
        right_panel.addWidget(tip)

        right_panel.addStretch()
        main_layout.addLayout(right_panel, 2)

        self._refresh_recipe_list()

    def _refresh_recipe_list(self):
        """刷新左侧已习得丹方列表。"""
        self.recipe_list.clear()
        for recipe_id in self.player.learned_recipes:
            recipe = self.engine.world.get_recipe(recipe_id)
            if not recipe:
                continue
            name = recipe.get("name", recipe_id)
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, recipe_id)
            self.recipe_list.addItem(item)

    def _on_recipe_selected(self, current, previous):
        """选中丹方时更新详情、材料与成功率。"""
        if not current:
            self.detail_label.setText("请选择左侧丹方。")
            self.materials_label.clear()
            self.rate_label.clear()
            self.craft_btn.setEnabled(False)
            return

        recipe_id = current.data(Qt.UserRole)
        recipe = self.engine.world.get_recipe(recipe_id)
        if not recipe:
            return

        # 详情文本
        desc = recipe.get("description", "")
        product_id = recipe["result"]["item_id"]
        product_name = self.item_library.get(product_id).name
        self.detail_label.setText(
            f"<b>{recipe.get('name', recipe_id)}</b><br>"
            f"{desc}<br>"
            f"产物：{product_name}"
        )

        # 材料文本
        materials = recipe.get("materials", {})
        material_texts = []
        enough = True
        for item_id, count in materials.items():
            item = self.item_library.get(item_id)
            item_name = item.name if item else item_id
            owned = self.player.count_item(item_id)
            color = "green" if owned >= count else "red"
            material_texts.append(
                f"<span style='color:{color};'>{item_name}：{owned}/{count}</span>"
            )
            if owned < count:
                enough = False
        self.materials_label.setText(
            "<b>所需材料：</b><br>" + "<br>".join(material_texts)
        )

        # 成功率
        base_rate = recipe.get("success_rate", 0.7)
        bonus = 0.0
        if self.player.cultivation_path == "dan_xiu":
            bonus += recipe.get("dan_xiu_bonus", 0.0)
        bonus += self.player.wisdom * 0.005
        rate = min(0.99, base_rate + bonus)
        self.rate_label.setText(
            f"<b>成功率：</b>{rate*100:.1f}% "
            f"（基础 {base_rate*100:.1f}%"
            f"{' + 丹修加成' if self.player.cultivation_path == 'dan_xiu' else ''}"
            f" + 悟性 {self.player.wisdom*0.5:.1f}%）"
        )

        self.craft_btn.setEnabled(enough)
        self._current_recipe_id = recipe_id

    def _on_craft(self):
        """点击炼丹按钮。"""
        recipe_id = getattr(self, "_current_recipe_id", None)
        if not recipe_id:
            return
        self.engine.craft_pill(recipe_id)
        # 刷新材料与按钮状态
        self._on_recipe_selected(self.recipe_list.currentItem(), None)
        self._refresh_recipe_list()

    def _open_shop(self):
        """打开炼丹阁商店。"""
        from ui.npc_dialog import NPCDialog
        merchant = self.engine.open_alchemy_shop()
        dialog = NPCDialog(self.engine, preset_npc=merchant, parent=self)
        dialog.exec()
        # 关闭商店后刷新丹方列表（可能买了新丹方）
        self._refresh_recipe_list()
