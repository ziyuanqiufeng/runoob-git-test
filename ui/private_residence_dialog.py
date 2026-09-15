# -*- coding: utf-8 -*-
"""私人洞府交互弹窗。

整合城中洞府购买、野外灵脉占领、建筑升级、维护缴费与护山大阵能量查看。
作为模块一「私人洞府占领与设施升级」的主 UI 入口。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QTabWidget,
    QGroupBox, QProgressBar, QWidget, QSpacerItem, QSizePolicy,
    QSpinBox, QLineEdit
)
from PySide6.QtCore import Qt

from game.residence import ResidenceManager, ResidenceConfig
from game.enemy import Enemy


class PrivateResidenceDialog(QDialog):
    """私人洞府管理弹窗。

    参数:
        engine: 游戏引擎实例，提供玩家、物品库、敌人库与战斗接口。
        parent: 父窗口，用于模态弹窗居中显示。
    """

    def __init__(self, engine, parent=None):
        # 调用父类构造，初始化模态对话框
        super().__init__(parent)
        # 设置窗口标题与默认尺寸
        self.setWindowTitle("私人洞府")
        self.resize(650, 520)

        # 保存引擎与常用对象的引用，避免后续重复访问
        self.engine = engine
        self.player = engine.player
        self.item_library = engine.item_library
        # 初始化洞府管理器与配置加载器
        self.residence_manager = ResidenceManager(
            self.player, item_library=self.item_library
        )
        self.residence_config = ResidenceConfig()

        # 顶部信息栏：显示灵石、贡献、当前洞府、维护与阵法状态
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            "font: 14px 'Microsoft YaHei'; padding: 8px; "
            "background-color: #f8f9fa; border-radius: 6px;"
        )

        # 标签页容器：按功能分区展示洞府信息
        self.tab_widget = QTabWidget()
        # 创建六个标签页
        self.overview_tab = QWidget()
        self.building_tab = QWidget()
        self.maintenance_tab = QWidget()
        self.farm_tab = QWidget()
        self.alchemy_tab = QWidget()
        self.smithy_tab = QWidget()
        self.tab_widget.addTab(self.overview_tab, "洞府")
        self.tab_widget.addTab(self.building_tab, "建筑")
        self.tab_widget.addTab(self.maintenance_tab, "维护")
        self.tab_widget.addTab(self.farm_tab, "药园")
        self.tab_widget.addTab(self.alchemy_tab, "炼丹室")
        self.tab_widget.addTab(self.smithy_tab, "炼器台")

        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)

        # 主布局：垂直排列信息栏、标签页、关闭按钮
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.info_label)
        main_layout.addWidget(self.tab_widget)
        main_layout.addWidget(self.close_btn)

        # 初始化各标签页的内部控件
        self._setup_overview_tab()
        self._setup_building_tab()
        self._setup_maintenance_tab()
        self._setup_farm_tab()
        self._setup_alchemy_tab()
        self._setup_smithy_tab()

        # 最后刷新界面数据
        self._refresh()

    # ==================== 标签页初始化 ====================

    def _setup_overview_tab(self):
        """初始化「洞府」标签页：当前洞府信息或购买/占领入口。"""
        layout = QVBoxLayout(self.overview_tab)

        # 当前洞府信息分组
        self.current_group = QGroupBox("当前洞府")
        current_layout = QVBoxLayout(self.current_group)
        self.current_detail_label = QLabel()
        self.current_detail_label.setWordWrap(True)
        current_layout.addWidget(self.current_detail_label)
        layout.addWidget(self.current_group)

        # 购买城中洞府分组
        self.buy_group = QGroupBox("可购买洞府")
        buy_layout = QVBoxLayout(self.buy_group)
        self.buy_list = QListWidget()
        self.buy_list.itemClicked.connect(self._on_buy_item_selected)
        buy_layout.addWidget(self.buy_list)
        self.buy_btn = QPushButton("购买")
        self.buy_btn.clicked.connect(self._on_buy)
        buy_layout.addWidget(self.buy_btn)
        layout.addWidget(self.buy_group)

        # 占领野外灵脉分组
        self.occupy_group = QGroupBox("可占领灵脉")
        occupy_layout = QVBoxLayout(self.occupy_group)
        self.occupy_list = QListWidget()
        self.occupy_list.itemClicked.connect(self._on_occupy_item_selected)
        occupy_layout.addWidget(self.occupy_list)
        self.occupy_btn = QPushButton("占领")
        self.occupy_btn.clicked.connect(self._on_occupy)
        occupy_layout.addWidget(self.occupy_btn)
        layout.addWidget(self.occupy_group)

        # 在标签页底部添加弹性空间，避免控件过度拉伸
        layout.addSpacerItem(QSpacerItem(
            20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding
        ))

    def _setup_building_tab(self):
        """初始化「建筑」标签页：列出洞府建筑并提供升级按钮。"""
        layout = QVBoxLayout(self.building_tab)

        self.building_list = QListWidget()
        self.building_list.itemClicked.connect(self._on_building_selected)
        layout.addWidget(self.building_list)

        self.upgrade_btn = QPushButton("升级")
        self.upgrade_btn.clicked.connect(self._on_upgrade)
        layout.addWidget(self.upgrade_btn)

        # 建筑效果汇总说明
        self.building_effect_label = QLabel()
        self.building_effect_label.setWordWrap(True)
        self.building_effect_label.setStyleSheet(
            "color: #2c3e50; padding: 6px; background-color: #ffffff; "
            "border-radius: 6px;"
        )
        layout.addWidget(self.building_effect_label)

    def _setup_maintenance_tab(self):
        """初始化「维护」标签页：维护费、欠费、护山大阵能量。"""
        layout = QVBoxLayout(self.maintenance_tab)

        # 维护费信息
        self.maintenance_label = QLabel()
        self.maintenance_label.setWordWrap(True)
        layout.addWidget(self.maintenance_label)

        # 缴纳维护费按钮
        self.pay_maintenance_btn = QPushButton("缴纳本月维护费")
        self.pay_maintenance_btn.clicked.connect(self._on_pay_maintenance)
        layout.addWidget(self.pay_maintenance_btn)

        # 护山大阵能量进度条
        energy_group = QGroupBox("护山大阵")
        energy_layout = QVBoxLayout(energy_group)
        self.energy_bar = QProgressBar()
        self.energy_bar.setRange(0, 100)
        self.energy_bar.setTextVisible(True)
        energy_layout.addWidget(self.energy_bar)
        self.energy_label = QLabel()
        self.energy_label.setWordWrap(True)
        energy_layout.addWidget(self.energy_label)
        layout.addWidget(energy_group)

        # 防御率说明
        self.defense_label = QLabel()
        self.defense_label.setWordWrap(True)
        layout.addWidget(self.defense_label)

        layout.addSpacerItem(QSpacerItem(
            20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding
        ))

    def _setup_farm_tab(self):
        """初始化「药园」标签页：播种、浇水、收获。"""
        layout = QVBoxLayout(self.farm_tab)

        # 季节与地块数信息
        self.farm_info_label = QLabel()
        self.farm_info_label.setWordWrap(True)
        layout.addWidget(self.farm_info_label)

        # 地块列表
        self.farm_list = QListWidget()
        self.farm_list.itemClicked.connect(self._on_farm_item_selected)
        layout.addWidget(self.farm_list)

        # 操作按钮行
        btn_layout = QHBoxLayout()
        self.plant_btn = QPushButton("播种")
        self.plant_btn.clicked.connect(self._on_plant)
        btn_layout.addWidget(self.plant_btn)

        self.water_btn = QPushButton("浇水")
        self.water_btn.clicked.connect(self._on_water)
        btn_layout.addWidget(self.water_btn)

        self.harvest_btn = QPushButton("收获")
        self.harvest_btn.clicked.connect(self._on_harvest)
        btn_layout.addWidget(self.harvest_btn)

        layout.addLayout(btn_layout)

    def _setup_alchemy_tab(self):
        """初始化「炼丹室」标签页：选择丹方、批量炼制。"""
        layout = QVBoxLayout(self.alchemy_tab)

        # 左侧：丹方列表；右侧：详情与操作
        h_layout = QHBoxLayout()

        # 丹方列表
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("已习得丹方"))
        self.alchemy_recipe_list = QListWidget()
        self.alchemy_recipe_list.itemClicked.connect(
            self._on_alchemy_recipe_selected
        )
        left_layout.addWidget(self.alchemy_recipe_list)
        h_layout.addLayout(left_layout, 1)

        # 详情与操作
        right_layout = QVBoxLayout()
        self.alchemy_detail_label = QLabel("请选择丹方。")
        self.alchemy_detail_label.setWordWrap(True)
        self.alchemy_detail_label.setStyleSheet(
            "background-color: #f8f9fa; padding: 8px; border-radius: 6px;"
        )
        right_layout.addWidget(self.alchemy_detail_label)

        self.alchemy_materials_label = QLabel()
        self.alchemy_materials_label.setWordWrap(True)
        right_layout.addWidget(self.alchemy_materials_label)

        self.alchemy_rate_label = QLabel()
        right_layout.addWidget(self.alchemy_rate_label)

        # 批量次数输入
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("炼制次数："))
        self.alchemy_batch_spin = QSpinBox()
        self.alchemy_batch_spin.setRange(1, 99)
        self.alchemy_batch_spin.setValue(1)
        self.alchemy_batch_spin.valueChanged.connect(
            self._on_alchemy_batch_changed
        )
        batch_layout.addWidget(self.alchemy_batch_spin)
        right_layout.addLayout(batch_layout)

        self.alchemy_craft_btn = QPushButton("开始炼丹")
        self.alchemy_craft_btn.setEnabled(False)
        self.alchemy_craft_btn.clicked.connect(self._on_alchemy_craft)
        right_layout.addWidget(self.alchemy_craft_btn)

        right_layout.addStretch()
        h_layout.addLayout(right_layout, 2)
        layout.addLayout(h_layout)

    def _setup_smithy_tab(self):
        """初始化「炼器台」标签页：装备强化。"""
        layout = QVBoxLayout(self.smithy_tab)

        # 装备列表
        self.smithy_list = QListWidget()
        self.smithy_list.itemClicked.connect(self._on_smithy_item_selected)
        layout.addWidget(self.smithy_list)

        # 强化信息
        self.smithy_info_label = QLabel("请选择要强化的装备。")
        self.smithy_info_label.setWordWrap(True)
        self.smithy_info_label.setStyleSheet(
            "background-color: #f8f9fa; padding: 8px; border-radius: 6px;"
        )
        layout.addWidget(self.smithy_info_label)

        # 强化按钮
        self.smithy_enhance_btn = QPushButton("强化")
        self.smithy_enhance_btn.setEnabled(False)
        self.smithy_enhance_btn.clicked.connect(self._on_smithy_enhance)
        layout.addWidget(self.smithy_enhance_btn)

        layout.addStretch()

    # ==================== 刷新逻辑 ====================

    def _refresh(self):
        """刷新整个弹窗的显示状态。"""
        # 刷新顶部信息栏
        self.info_label.setText(self._build_info_text())
        # 根据是否拥有洞府决定各标签页的可用状态
        has_residence = self.player.residence is not None
        self.building_tab.setEnabled(has_residence)
        self.maintenance_tab.setEnabled(has_residence)
        self.farm_tab.setEnabled(has_residence)
        self.alchemy_tab.setEnabled(has_residence)
        self.smithy_tab.setEnabled(has_residence)
        # 刷新六个标签页内容
        self._refresh_overview_tab()
        self._refresh_building_tab()
        self._refresh_maintenance_tab()
        self._refresh_farm_tab()
        self._refresh_alchemy_tab()
        self._refresh_smithy_tab()

    def _build_info_text(self):
        """构建顶部信息栏文本。"""
        # 第一行显示灵石与宗门贡献
        lines = [
            f"灵石：{self.player.count_item('spirit_stone')}  "
            f"贡献：{self.player.sect_contribution}"
        ]
        if self.player.residence:
            # 若已拥有洞府，显示名称与类型
            residence = self.residence_config.get_residence(
                self.player.residence["id"]
            )
            name = residence["name"] if residence else "未知"
            lines.append(f"当前洞府：{name}")
        else:
            lines.append("当前洞府：无")
        return "\n".join(lines)

    def _refresh_overview_tab(self):
        """刷新「洞府」标签页：根据是否有洞府显示不同分组。"""
        has_residence = self.player.residence is not None
        # 已有洞府时显示详情，否则隐藏
        self.current_group.setVisible(has_residence)
        # 没有洞府时才显示购买与占领选项
        self.buy_group.setVisible(not has_residence)
        self.occupy_group.setVisible(not has_residence)

        if has_residence:
            self._refresh_current_detail()
        else:
            self._refresh_buy_list()
            self._refresh_occupy_list()

    def _refresh_current_detail(self):
        """刷新当前洞府详情文本。"""
        residence_id = self.player.residence["id"]
        residence = self.residence_config.get_residence(residence_id)
        if not residence:
            self.current_detail_label.setText("洞府配置异常。")
            return
        # 洞府类型中文映射
        type_names = {"city": "城中洞府", "wild": "野外灵脉"}
        rtype = type_names.get(residence.get("type"), "未知")
        quality = self.residence_manager.get_spirit_vein_quality()
        lines = [
            f"名称：{residence['name']}",
            f"类型：{rtype}",
            f"灵脉品质：{quality:.2f}",
            f"位置：{residence.get('description', '')}",
        ]
        self.current_detail_label.setText("\n".join(lines))

    def _refresh_buy_list(self):
        """刷新可购买洞府列表（仅城中洞府）。"""
        self.buy_list.clear()
        # 遍历所有洞府配置，筛选出 city 类型
        for residence in self.residence_config.get_residences():
            if residence.get("type") != "city":
                continue
            cost = residence.get("cost", {})
            text = (
                f"{residence['name']} - {residence.get('description', '')}  "
                f"费用：灵石 {cost.get('spirit_stone', 0)}  "
                f"贡献 {cost.get('contribution', 0)}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, residence["id"])
            self.buy_list.addItem(item)

    def _refresh_occupy_list(self):
        """刷新当前地点可占领野外灵脉列表。"""
        self.occupy_list.clear()
        # 获取玩家当前所在地点 ID
        current_location = self.player.location_id
        # 查询该地点关联的野外洞府配置
        wild_list = self.residence_config.get_residences_by_location(
            current_location
        )
        for residence in wild_list:
            if residence.get("type") != "wild":
                continue
            occupation = residence.get("occupation", {})
            required_order = occupation.get("required_realm_order", 1)
            # 将境界顺序转换为可读文本
            realm_text = self._realm_order_to_text(required_order)
            text = (
                f"{residence['name']} - {residence.get('description', '')}  "
                f"需要境界：{realm_text}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, residence["id"])
            # 如果境界不足，置灰提示
            player_order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
            if player_order < required_order:
                item.setForeground(Qt.gray)
                item.setToolTip("境界不足，无法占领")
            self.occupy_list.addItem(item)

    def _realm_order_to_text(self, order):
        """根据境界顺序数字返回可读的境界名称；找不到时返回顺序号。"""
        # 遍历玩家类中境界顺序映射，寻找对应顺序的境界 ID
        for realm_id, realm_order in self.player.REALM_ORDER.items():
            if realm_order == order:
                return self._realm_id_to_name(realm_id)
        return f"顺序 {order}"

    def _realm_id_to_name(self, realm_id):
        """将境界 ID 转换为中文名。"""
        # 项目内常用境界中文名映射
        names = {
            "qi_refining_1": "练气期一层",
            "qi_refining_2": "练气期二层",
            "qi_refining_3": "练气期三层",
            "qi_refining_4": "练气期四层",
            "qi_refining_5": "练气期五层",
            "qi_refining_6": "练气期六层",
            "qi_refining_7": "练气期七层",
            "qi_refining_8": "练气期八层",
            "qi_refining_9": "练气期九层",
            "foundation_early": "筑基初期",
            "foundation_mid": "筑基中期",
            "foundation_late": "筑基后期",
            "foundation_peak": "筑基圆满",
            "golden_core_early": "金丹初期",
            "golden_core_mid": "金丹中期",
            "golden_core_late": "金丹后期",
            "golden_core_peak": "金丹圆满",
            "nascent_soul": "元婴期",
        }
        return names.get(realm_id, realm_id)

    def _refresh_building_tab(self):
        """刷新「建筑」标签页：列出建筑等级与升级消耗。"""
        self.building_list.clear()
        if not self.player.residence:
            self.building_effect_label.setText("尚未拥有洞府。")
            return
        # 获取当前洞府的建筑配置
        residence_id = self.player.residence["id"]
        for building in self.residence_config.get_residence(residence_id).get("buildings", []):
            current = self.player.residence.get("buildings", {}).get(
                building["id"], 0
            )
            max_level = building.get("max_level", 0)
            cost = self.residence_manager._get_upgrade_cost(building, current)
            if current >= max_level:
                text = f"{building['name']}：{current}/{max_level}（已满级）"
            else:
                text = (
                    f"{building['name']}：{current}/{max_level}  "
                    f"升级需 {cost} 灵石"
                )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, building["id"])
            item.setToolTip(building.get("description", ""))
            self.building_list.addItem(item)
        # 同步刷新效果汇总
        self.building_effect_label.setText(self._build_effect_text())

    def _build_effect_text(self):
        """构建当前洞府效果汇总文本。"""
        if not self.player.residence:
            return ""
        parts = ["当前效果："]
        # 修炼速度加成
        cultivation = self.residence_manager.get_cultivation_speed_bonus()
        if cultivation:
            parts.append(f"修炼速度 +{cultivation*100:.0f}%")
        # 水属性伤害加成
        water = self.residence_manager.get_water_damage_bonus()
        if water:
            parts.append(f"水属性伤害 +{water*100:.0f}%")
        # 祭炼效果加成
        refine = self.residence_manager.get_refine_bonus()
        if refine:
            parts.append(f"祭炼效果 +{refine*100:.0f}%")
        # 炼丹成功率与品质加成
        alchemy_success = self.residence_manager.get_alchemy_success_bonus()
        if alchemy_success:
            parts.append(f"炼丹成功率 +{alchemy_success*100:.0f}%")
        alchemy_quality = self.residence_manager.get_alchemy_quality_bonus()
        if alchemy_quality:
            parts.append(f"炼丹品质 +{alchemy_quality*100:.0f}%")
        # 炼器成功率加成
        smith_success = self.residence_manager.get_smith_success_bonus()
        if smith_success:
            parts.append(f"炼器成功率 +{smith_success*100:.0f}%")
        # 袭击防御率
        defense = self.residence_manager.get_raid_defense()
        if defense:
            parts.append(f"袭击防御 +{defense*100:.0f}%")
        # 药园产出
        herbs = self.residence_manager.get_herb_production()
        for herb in herbs:
            parts.append(
                f"药园产出 {herb['herb_id']} 概率 {herb['chance']*100:.0f}%"
            )
        return "  ".join(parts)

    def _refresh_maintenance_tab(self):
        """刷新「维护」标签页：维护费、欠费、能量与防御率。"""
        if not self.player.residence:
            self.maintenance_label.setText("尚未拥有洞府。")
            self.energy_bar.setValue(0)
            self.energy_label.setText("")
            self.defense_label.setText("")
            return
        # 计算维护费与欠费月数
        cost = self.residence_manager.get_maintenance_cost()
        debt = self.player.residence.get("maintenance_debt", 0)
        debt_text = ""
        if debt > 0:
            debt_text = f"（欠费 {debt} 个月，达到 3 个月设施将停摆）"
        self.maintenance_label.setText(
            f"本月维护费：{cost} 灵石  {debt_text}"
        )

        # 护山大阵能量
        energy = self.residence_manager.get_formation_energy()
        max_energy = self.residence_manager.get_max_formation_energy()
        # 防御阵未建造时上限可能为 0
        if max_energy > 0:
            self.energy_bar.setRange(0, max_energy)
            self.energy_bar.setValue(energy)
            self.energy_bar.setFormat(f"{energy} / {max_energy}")
            self.energy_label.setText(
                f"当前能量 {energy} / 上限 {max_energy}"
            )
        else:
            self.energy_bar.setRange(0, 1)
            self.energy_bar.setValue(0)
            self.energy_bar.setFormat("未建造护山大阵")
            self.energy_label.setText("尚未建造护山大阵，无法储备能量。")

        # 综合防御率
        defense_rate = self.residence_manager.get_defense_rate()
        self.defense_label.setText(
            f"当前综合防御率：{defense_rate*100:.1f}%  "
            f"（能量越充足，防御越高）"
        )

    def _refresh_farm_tab(self):
        """刷新「药园」标签页：季节、地块与作物状态。"""
        if not self.player.residence:
            self.farm_info_label.setText("尚未拥有洞府。")
            self.farm_list.clear()
            return
        farm_manager = self.engine.farm_manager
        farm_manager._ensure_default_plots()
        season = farm_manager.config.get_season(self.engine.world.month)
        season_names = {
            "spring": "春", "summer": "夏",
            "autumn": "秋", "winter": "冬"
        }
        self.farm_info_label.setText(
            f"当前季节：{season_names.get(season, season)} | "
            f"地块数：{len(self.player.farm_plots)}"
        )
        self.farm_list.clear()
        for idx, plot in enumerate(self.player.farm_plots):
            if plot is None:
                text = f"第{idx + 1}块地：空闲"
            else:
                crop = farm_manager.config.get_crop(plot["crop_id"])
                crop_name = crop["name"] if crop else plot["crop_id"]
                state_names = {
                    "growing": "生长中",
                    "mature": "可收获",
                    "withered": "已枯萎"
                }
                state = state_names.get(plot["state"], plot["state"])
                water = "已浇水" if plot.get("watered") else "未浇水"
                text = (
                    f"第{idx + 1}块地：{crop_name} "
                    f"({state}, {water}, 生长{plot['growth']})"
                )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, idx)
            self.farm_list.addItem(item)

    def _refresh_alchemy_tab(self):
        """刷新「炼丹室」标签页：丹方列表。"""
        self.alchemy_recipe_list.clear()
        if not self.player.residence:
            self.alchemy_detail_label.setText("尚未拥有洞府。")
            self.alchemy_materials_label.clear()
            self.alchemy_rate_label.clear()
            self.alchemy_craft_btn.setEnabled(False)
            return
        alchemy_manager = self.engine.alchemy_manager
        for recipe in alchemy_manager.get_learned_recipes():
            item = QListWidgetItem(recipe.get("name", recipe["id"]))
            item.setData(Qt.UserRole, recipe["id"])
            self.alchemy_recipe_list.addItem(item)
        # 若当前有选中丹方，刷新右侧详情
        current = self.alchemy_recipe_list.currentItem()
        if current:
            self._on_alchemy_recipe_selected(current, None)

    def _refresh_smithy_tab(self):
        """刷新「炼器台」标签页：可强化装备列表。"""
        self.smithy_list.clear()
        if not self.player.residence:
            self.smithy_info_label.setText("尚未拥有洞府。")
            self.smithy_enhance_btn.setEnabled(False)
            return
        smithy_manager = self.engine.smithy_manager
        for item in smithy_manager.list_enhanceable_items():
            text = (
                f"{item.name} "
                f"(+{getattr(item, 'enhancement_level', 0)})"
            )
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.UserRole, id(item))
            self.smithy_list.addItem(list_item)
        self.smithy_info_label.setText("请选择要强化的装备。")
        self.smithy_enhance_btn.setEnabled(False)

    # ==================== 事件处理 ====================

    def _on_buy_item_selected(self, item):
        """记录选中的购买洞府 ID。"""
        self._selected_residence_id = item.data(Qt.UserRole)

    def _on_buy(self):
        """购买选中的城中洞府。"""
        if not hasattr(self, "_selected_residence_id"):
            QMessageBox.information(self, "提示", "请先选择一处洞府。")
            return
        ok, msg = self.residence_manager.buy_residence(
            self._selected_residence_id
        )
        if ok:
            self.engine.notify(msg)
            self._refresh()
        else:
            QMessageBox.warning(self, "购买失败", msg)

    def _on_occupy_item_selected(self, item):
        """记录选中的占领洞府 ID。"""
        self._selected_occupy_id = item.data(Qt.UserRole)

    def _on_occupy(self):
        """对选中的野外灵脉发起占领战斗。"""
        if not hasattr(self, "_selected_occupy_id"):
            QMessageBox.information(self, "提示", "请先选择一处灵脉。")
            return
        residence_id = self._selected_occupy_id
        residence = self.residence_config.get_residence(residence_id)
        if not residence:
            QMessageBox.warning(self, "错误", "洞府配置不存在。")
            return
        location_id = residence.get("location_id")
        # 调用引擎接口检查并发起占领，返回守卫敌人 ID
        success, message, guard_enemy_id = self.engine.start_residence_occupation(
            location_id
        )
        if not success:
            QMessageBox.warning(self, "无法占领", message)
            return
        # 守卫敌人 ID 必须存在，否则无法进入战斗
        if not guard_enemy_id:
            QMessageBox.warning(self, "配置错误", "该灵脉没有配置守卫敌人。")
            return
        # 从敌人库加载守卫数据
        enemy_data = self.engine.enemy_library.get(guard_enemy_id)
        if not enemy_data:
            QMessageBox.warning(self, "配置错误", f"找不到敌人 {guard_enemy_id}。")
            return
        # 创建敌人战斗对象
        enemy = Enemy.from_dict(enemy_data)
        # 显示占领引导文本
        if message:
            QMessageBox.information(self, "占领", message)
        # 关闭当前弹窗，让主窗口打开战斗界面
        self.accept()
        # 触发引擎战斗；战斗结束后由 main_window 调用 finish_residence_occupation
        self.engine.start_combat(enemy)

    def _on_building_selected(self, item):
        """记录选中的建筑 ID。"""
        self._selected_building_id = item.data(Qt.UserRole)

    def _on_upgrade(self):
        """升级选中的建筑。"""
        if not hasattr(self, "_selected_building_id"):
            QMessageBox.information(self, "提示", "请先选择一个建筑。")
            return
        ok, msg = self.residence_manager.upgrade_building(
            self._selected_building_id
        )
        if ok:
            self.engine.notify(msg)
            self._refresh()
        else:
            QMessageBox.warning(self, "升级失败", msg)

    def _on_pay_maintenance(self):
        """手动缴纳本月维护费。"""
        ok, msg = self.engine.pay_residence_maintenance()
        if ok:
            self.engine.notify(msg)
            self._refresh()
        else:
            QMessageBox.warning(self, "缴费失败", msg)

    # ------------------ 药园事件 ------------------

    def _on_farm_item_selected(self, item):
        """记录选中的药园地块索引。"""
        self._selected_farm_plot = item.data(Qt.UserRole)

    def _on_plant(self):
        """在选中药园地块播种。"""
        if not hasattr(self, "_selected_farm_plot"):
            QMessageBox.information(self, "提示", "请选择一块空地。")
            return
        idx = self._selected_farm_plot
        farm_manager = self.engine.farm_manager
        plantable = [
            c for c in farm_manager.config.get_all_crops()
            if farm_manager.can_plant(idx, c["id"])[0]
        ]
        if not plantable:
            QMessageBox.information(
                self, "提示", "当前没有可种植的作物（检查种子与境界）。"
            )
            return
        names = [c["name"] for c in plantable]
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getItem(
            self, "播种", "选择作物：", names, 0, False
        )
        if not ok:
            return
        crop_id = next(c["id"] for c in plantable if c["name"] == name)
        success, msg = farm_manager.plant(idx, crop_id)
        self.engine.notify(msg)
        if success:
            self._refresh_farm_tab()

    def _on_water(self):
        """对选中药园地块浇水。"""
        if not hasattr(self, "_selected_farm_plot"):
            QMessageBox.information(self, "提示", "请选择一块地。")
            return
        success, msg = self.engine.farm_manager.water(
            self._selected_farm_plot
        )
        self.engine.notify(msg)
        if success:
            self._refresh_farm_tab()

    def _on_harvest(self):
        """收获选中药园地块的作物。"""
        if not hasattr(self, "_selected_farm_plot"):
            QMessageBox.information(self, "提示", "请选择一块地。")
            return
        success, msg = self.engine.farm_manager.harvest(
            self._selected_farm_plot
        )
        self.engine.notify(msg)
        if success:
            self._refresh_farm_tab()

    # ------------------ 炼丹室事件 ------------------

    def _on_alchemy_recipe_selected(self, current, previous):
        """选中丹方时刷新详情、材料与成功率。"""
        if not current:
            self.alchemy_detail_label.setText("请选择丹方。")
            self.alchemy_materials_label.clear()
            self.alchemy_rate_label.clear()
            self.alchemy_craft_btn.setEnabled(False)
            return
        recipe_id = current.data(Qt.UserRole)
        self._current_alchemy_recipe_id = recipe_id
        batch = self.alchemy_batch_spin.value()
        self._update_alchemy_preview(recipe_id, batch)

    def _on_alchemy_batch_changed(self, value):
        """批量次数变化时刷新材料与按钮状态。"""
        if hasattr(self, "_current_alchemy_recipe_id"):
            self._update_alchemy_preview(
                self._current_alchemy_recipe_id, value
            )

    def _update_alchemy_preview(self, recipe_id, batch):
        """根据丹方与次数更新右侧详情。"""
        alchemy_manager = self.engine.alchemy_manager
        ok, msg, info = alchemy_manager.preview(recipe_id, batch)
        if not ok:
            self.alchemy_detail_label.setText(msg)
            self.alchemy_materials_label.clear()
            self.alchemy_rate_label.clear()
            self.alchemy_craft_btn.setEnabled(False)
            return
        recipe = alchemy_manager.get_recipe(recipe_id)
        product_id = info["product_id"]
        product = self.item_library.get(product_id)
        product_name = product.name if product else product_id
        self.alchemy_detail_label.setText(
            f"<b>{recipe.get('name', recipe_id)}</b><br>"
            f"{recipe.get('description', '')}<br>"
            f"产物：{product_name} x{info['product_count']}"
        )
        material_texts = []
        all_enough = True
        for mat in info["materials"]:
            color = "green" if mat["enough"] else "red"
            material_texts.append(
                f"<span style='color:{color};'>"
                f"{mat['name']}：{mat['owned']}/{mat['required']}"
                f"</span>"
            )
            if not mat["enough"]:
                all_enough = False
        self.alchemy_materials_label.setText(
            "<b>所需材料：</b><br>" + "<br>".join(material_texts)
        )
        self.alchemy_rate_label.setText(
            f"<b>成功率：</b>{info['success_rate']*100:.1f}%"
        )
        self.alchemy_craft_btn.setEnabled(all_enough)

    def _on_alchemy_craft(self):
        """开始炼丹。"""
        if not hasattr(self, "_current_alchemy_recipe_id"):
            return
        recipe_id = self._current_alchemy_recipe_id
        batch = self.alchemy_batch_spin.value()
        success, message, produced = self.engine.alchemy_manager.craft(
            recipe_id, batch
        )
        self.engine.notify(message)
        if success:
            # 炼丹推进 7 日，触发 sect 任务进度
            product_id = produced[0].id if produced else recipe_id
            total_count = sum(item.count for item in produced)
            self.engine.sect_manager.update_task_progress(
                "collect", product_id, total_count
            )
            self.engine._on_gain_item(product_id, total_count)
            self.engine.world.advance(7)
            self.engine.player.add_age_months(7)
            self.engine._check_sect_daily_reset()
            self.engine._auto_save()
        self._refresh()

    # ------------------ 炼器台事件 ------------------

    def _on_smithy_item_selected(self, item):
        """选中装备时显示强化预览。"""
        item_id = item.data(Qt.UserRole)
        for inv_item in self.player.inventory:
            if id(inv_item) == item_id:
                self._selected_smithy_item = inv_item
                break
        else:
            self._selected_smithy_item = None
        self._update_smithy_preview()

    def _update_smithy_preview(self):
        """刷新炼器台强化预览信息。"""
        item = getattr(self, "_selected_smithy_item", None)
        if not item:
            self.smithy_info_label.setText("请选择要强化的装备。")
            self.smithy_enhance_btn.setEnabled(False)
            return
        smithy_manager = self.engine.smithy_manager
        ok, msg, info = smithy_manager.preview_enhance(item)
        if not ok:
            self.smithy_info_label.setText(msg)
            self.smithy_enhance_btn.setEnabled(False)
            return
        self.smithy_info_label.setText(
            f"{item.name} (+{info['current_level']} -> +{info['next_level']})<br>"
            f"强化消耗：{info['cost']} 灵石<br>"
            f"成功率：{info['success_rate']*100:.1f}%"
        )
        self.smithy_enhance_btn.setEnabled(True)

    def _on_smithy_enhance(self):
        """强化选中的装备。"""
        item = getattr(self, "_selected_smithy_item", None)
        if not item:
            return
        success, message, destroyed = self.engine.smithy_manager.enhance(item)
        self.engine.notify(message)
        if destroyed:
            # 装备损毁，从背包移除
            if item in self.player.inventory:
                self.player.inventory.remove(item)
            self._selected_smithy_item = None
        if success:
            self.engine.sect_manager.update_task_progress(
                "enhance", item.id, 1
            )
            self.engine._auto_save()
        self._refresh()
