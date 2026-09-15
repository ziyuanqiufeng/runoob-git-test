from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QMessageBox, QTabWidget, QWidget as BaseWidget
)


class InventoryDialog(QDialog):
    """背包弹窗，查看、使用物品、装备穿戴/卸下和根据配方合成。"""

    def __init__(self, player, world, item_library, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("背包与合成")
        self.resize(550, 500)
        self.player = player
        self.world = world
        self.item_library = item_library
        self.engine = engine

        # 主布局
        layout = QVBoxLayout(self)

        # 标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # 背包标签
        self.inventory_tab = BaseWidget()
        self._setup_inventory_tab()
        self.tabs.addTab(self.inventory_tab, "背包")

        # 装备标签
        self.equipment_tab = BaseWidget()
        self._setup_equipment_tab()
        self.tabs.addTab(self.equipment_tab, "装备")

        # 合成标签
        self.craft_tab = BaseWidget()
        self._setup_craft_tab()
        self.tabs.addTab(self.craft_tab, "合成")

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    # ==================== 背包标签 ====================

    def _setup_inventory_tab(self):
        tab_layout = QVBoxLayout(self.inventory_tab)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_selected)
        tab_layout.addWidget(self.list_widget)

        self.info_label = QLabel("请选择物品")
        self.info_label.setWordWrap(True)
        tab_layout.addWidget(self.info_label)

        self.use_btn = QPushButton("使用 / 装备")
        self.use_btn.clicked.connect(self._on_use)
        self.use_btn.setEnabled(False)
        tab_layout.addWidget(self.use_btn)

        self._refresh_inventory()

    def _refresh_inventory(self):
        """刷新物品列表。"""
        self.list_widget.clear()
        self.selected_item = None
        self.use_btn.setEnabled(False)
        self.info_label.setText("请选择物品")

        # 合并同名物品计数
        counts = {}
        for item in self.player.inventory:
            counts[item] = counts.get(item, 0) + 1

        for item, count in counts.items():
            display = f"{item.name} x{count}"
            list_item = QListWidgetItem(display)
            list_item.setData(256, item)
            self.list_widget.addItem(list_item)

    def _on_item_selected(self, item):
        """选中物品时显示详情。"""
        obj = item.data(256)
        self.selected_item = obj
        self.info_label.setText(f"{obj.name}\n类型：{obj.type}\n{obj.description}")
        # 丹药、功法、普通装备以及已解锁的本命法宝都可以使用/装备
        usable_types = {"pill", "manual", "weapon", "helmet", "armor", "accessory"}
        if obj.type == "life_treasure" and self.player.has_feature("life_treasure"):
            usable_types.add("life_treasure")
        self.use_btn.setEnabled(obj.type in usable_types)

    def _on_use(self):
        """使用/装备选中物品。"""
        if not self.selected_item:
            return
        self.engine.use_item(self.selected_item)
        self._refresh_inventory()
        self._refresh_equipment()

    # ==================== 装备标签 ====================

    def _setup_equipment_tab(self):
        tab_layout = QVBoxLayout(self.equipment_tab)

        self.equipment_list = QListWidget()
        self.equipment_list.itemClicked.connect(self._on_equipment_selected)
        tab_layout.addWidget(self.equipment_list)

        self.equip_info_label = QLabel("请选择已装备的物品")
        self.equip_info_label.setWordWrap(True)
        tab_layout.addWidget(self.equip_info_label)

        self.unequip_btn = QPushButton("卸下装备")
        self.unequip_btn.clicked.connect(self._on_unequip)
        self.unequip_btn.setEnabled(False)
        tab_layout.addWidget(self.unequip_btn)

        self._refresh_equipment()

    def _refresh_equipment(self):
        """刷新已装备列表。"""
        self.equipment_list.clear()
        self.selected_slot = None
        self.unequip_btn.setEnabled(False)
        self.equip_info_label.setText("请选择已装备的物品")

        slot_names = {
            "weapon": "武器",
            "helmet": "头盔",
            "armor": "护甲",
            "accessory": "饰品",
            "life_treasure": "本命法宝",
        }
        for slot, item in self.player.equipment.items():
            # 本命法宝槽位未解锁时不显示
            if slot == "life_treasure" and not self.player.has_feature("life_treasure"):
                continue
            name = slot_names.get(slot, slot)
            display = f"{name}：{item.name if item else '无'}"
            list_item = QListWidgetItem(display)
            list_item.setData(256, slot)
            self.equipment_list.addItem(list_item)

    def _on_equipment_selected(self, item):
        """选中装备槽位。"""
        slot = item.data(256)
        self.selected_slot = slot
        equip = self.player.equipment.get(slot)
        if equip:
            self.equip_info_label.setText(f"{equip.name}\n{equip.description}")
            self.unequip_btn.setEnabled(True)
        else:
            self.equip_info_label.setText("该槽位没有装备。")
            self.unequip_btn.setEnabled(False)

    def _on_unequip(self):
        """卸下选中装备。"""
        if not self.selected_slot:
            return
        self.engine.unequip_item(self.selected_slot)
        self._refresh_equipment()
        self._refresh_inventory()

    # ==================== 合成标签 ====================

    def _setup_craft_tab(self):
        tab_layout = QVBoxLayout(self.craft_tab)

        self.recipe_list = QListWidget()
        self.recipe_list.itemClicked.connect(self._on_recipe_selected)
        tab_layout.addWidget(self.recipe_list)

        self.recipe_info = QLabel("请选择配方")
        self.recipe_info.setWordWrap(True)
        tab_layout.addWidget(self.recipe_info)

        self.craft_btn = QPushButton("合成")
        self.craft_btn.clicked.connect(self._on_craft)
        self.craft_btn.setEnabled(False)
        tab_layout.addWidget(self.craft_btn)

        self._refresh_recipes()

    def _refresh_recipes(self):
        """刷新配方列表。"""
        self.recipe_list.clear()
        self.selected_recipe = None
        self.craft_btn.setEnabled(False)
        self.recipe_info.setText("请选择配方")

        for recipe in self.world.recipes:
            display = recipe["name"]
            item = QListWidgetItem(display)
            item.setData(256, recipe)
            self.recipe_list.addItem(item)

    def _on_recipe_selected(self, item):
        """选中配方时显示材料需求。"""
        recipe = item.data(256)
        self.selected_recipe = recipe

        material_texts = []
        for item_id, count in recipe["materials"].items():
            item_name = self.item_library.get(item_id).name
            have = self.player.count_item(item_id)
            material_texts.append(f"{item_name}: {have}/{count}")

        result_name = self.item_library.get(recipe["result"]["item_id"]).name
        self.recipe_info.setText(
            f"{recipe['description']}\n材料：{', '.join(material_texts)}\n产物：{result_name}"
        )
        self.craft_btn.setEnabled(True)

    def _on_craft(self):
        """执行合成。"""
        if not self.selected_recipe:
            return
        success = self.engine.craft(self.selected_recipe["id"])
        if success:
            self._refresh_inventory()
            self._refresh_recipes()
