from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QTabWidget, QWidget as BaseWidget, QComboBox, QSpinBox,
    QAbstractItemView, QFormLayout, QDialogButtonBox
)
from PySide6.QtCore import Qt

from game.companion import CompanionManager
from ui.dialogue_dialog import DialogueDialog


class NPCDialog(QDialog):
    """NPC 交互弹窗，显示当前地点 NPC、接任务、拜师学技、买卖物品。"""

    def __init__(self, engine, preset_npc=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NPC")
        self.resize(550, 520)
        self.engine = engine
        self.preset_npc = preset_npc  # 预设 NPC（如偶遇的云游商人）

        layout = QVBoxLayout(self)

        # NPC 列表
        self.npc_list = QListWidget()
        self.npc_list.itemClicked.connect(self._on_npc_selected)
        layout.addWidget(QLabel("当前地点人物："))
        layout.addWidget(self.npc_list)

        # 头像与详情水平布局
        self.portrait_label = QLabel()
        self.portrait_label.setFixedSize(80, 80)
        self.portrait_label.setStyleSheet("border: 1px solid #aaa; background: #f0f0f0;")
        self.portrait_label.setAlignment(Qt.AlignCenter)
        self.portrait_label.setText("无头像")

        self.info_label = QLabel("请选择一位 NPC")
        self.info_label.setWordWrap(True)

        info_layout = QHBoxLayout()
        info_layout.addWidget(self.portrait_label)
        info_layout.addWidget(self.info_label, 1)
        layout.addLayout(info_layout)

        # 对话按钮：NPC 配置 dialogue_id 时显示
        self.talk_btn = QPushButton("对话")
        self.talk_btn.setToolTip("与该 NPC 进行分支对话")
        self.talk_btn.clicked.connect(self._on_talk)
        self.talk_btn.setVisible(False)
        layout.addWidget(self.talk_btn)

        # 挑衅按钮：仅对敌对宗门 NPC 显示
        self.provoke_btn = QPushButton("挑衅")
        self.provoke_btn.setToolTip("对敌对宗门 NPC 出言挑衅，可能引发战斗")
        self.provoke_btn.clicked.connect(self._on_provoke)
        self.provoke_btn.setVisible(False)
        layout.addWidget(self.provoke_btn)

        # 结为道侣按钮：满足条件时显示
        self.form_companion_btn = QPushButton("结为道侣")
        self.form_companion_btn.setToolTip("与该 NPC 结为道侣，共同修仙")
        self.form_companion_btn.clicked.connect(self._on_form_companion)
        self.form_companion_btn.setVisible(False)
        layout.addWidget(self.form_companion_btn)

        # 标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # 任务标签
        self.quest_tab = BaseWidget()
        self._setup_quest_tab()
        self.tabs.addTab(self.quest_tab, "任务")

        # 技能标签
        self.skill_tab = BaseWidget()
        self._setup_skill_tab()
        self.tabs.addTab(self.skill_tab, "拜师")

        # 商店标签
        self.shop_tab = BaseWidget()
        self._setup_shop_tab()
        self.tabs.addTab(self.shop_tab, "交易")

        # 流派转换标签（仅道师 NPC 显示，先创建并隐藏）
        self.path_tab = BaseWidget()
        self._setup_path_tab()
        self.path_tab_index = self.tabs.addTab(self.path_tab, "转换流派")
        # 初始没有选中 NPC 时隐藏该 tab
        self.tabs.setTabVisible(self.path_tab_index, False)

        # 道侣标签（仅当选中 NPC 为道侣时显示）
        self.companion_tab = BaseWidget()
        self._setup_companion_tab()
        self.companion_tab_index = self.tabs.addTab(self.companion_tab, "道侣")
        self.tabs.setTabVisible(self.companion_tab_index, False)

        # 社交标签（论道、双修、收徒、恩怨）
        self.social_tab = BaseWidget()
        self._setup_social_tab()
        self.social_tab_index = self.tabs.addTab(self.social_tab, "社交")

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.selected_npc = None
        self._refresh_npc_list()

    def _setup_quest_tab(self):
        layout = QVBoxLayout(self.quest_tab)

        # 主线任务
        layout.addWidget(QLabel("主线任务："))
        self.quest_list = QListWidget()
        self.quest_list.itemClicked.connect(self._on_quest_selected)
        layout.addWidget(self.quest_list)

        self.accept_quest_btn = QPushButton("接受任务")
        self.accept_quest_btn.clicked.connect(self._on_accept_quest)
        self.accept_quest_btn.setEnabled(False)
        layout.addWidget(self.accept_quest_btn)

        # 支线任务
        layout.addWidget(QLabel("支线任务："))
        self.side_quest_list = QListWidget()
        self.side_quest_list.itemClicked.connect(self._on_side_quest_selected)
        layout.addWidget(self.side_quest_list)

        self.accept_side_quest_btn = QPushButton("接受支线任务")
        self.accept_side_quest_btn.clicked.connect(self._on_accept_side_quest)
        self.accept_side_quest_btn.setEnabled(False)
        layout.addWidget(self.accept_side_quest_btn)

    def _setup_skill_tab(self):
        layout = QVBoxLayout(self.skill_tab)

        # 技能分类筛选：配合伤害/治疗/控制/辅助新体系
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("分类筛选："))
        self.skill_filter_combo = QComboBox()
        self.skill_filter_combo.addItem("全部", "all")
        self.skill_filter_combo.addItem("伤害", "damage")
        self.skill_filter_combo.addItem("治疗", "heal")
        self.skill_filter_combo.addItem("控制", "control")
        self.skill_filter_combo.addItem("辅助", "support")
        self.skill_filter_combo.currentIndexChanged.connect(self._on_skill_filter_changed)
        filter_layout.addWidget(self.skill_filter_combo)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        self.skill_list = QListWidget()
        self.skill_list.itemClicked.connect(self._on_skill_selected)
        layout.addWidget(self.skill_list)

        self.learn_skill_btn = QPushButton("拜师学技")
        self.learn_skill_btn.clicked.connect(self._on_learn_skill)
        self.learn_skill_btn.setEnabled(False)
        layout.addWidget(self.learn_skill_btn)

    def _on_skill_filter_changed(self):
        """分类筛选下拉框变化时刷新技能列表。"""
        if not getattr(self, "selected_npc", None):
            return
        # 复用 _on_npc_selected 中的敌对判断逻辑
        status, _, _, is_wanted = self._get_sect_relation_info(self.selected_npc)
        is_hostile = status == "hostile"
        self._refresh_skill_list(self.selected_npc, is_hostile)

    def _refresh_skill_list(self, npc, is_hostile):
        """根据当前分类筛选刷新拜师技能列表。"""
        self.skill_list.clear()
        self.learn_skill_btn.setEnabled(False)
        self.selected_skill_id = None

        if is_hostile:
            disabled_item = QListWidgetItem("该宗门与你敌对，无法拜师学技。")
            disabled_item.setFlags(disabled_item.flags() & ~Qt.ItemIsEnabled)
            self.skill_list.addItem(disabled_item)
            return

        filter_category = self.skill_filter_combo.currentData()
        for info in getattr(npc, "teach_skills", []):
            skill_id = info["skill_id"]
            if skill_id in self.engine.player.skills:
                continue
            skill = self.engine.skill_library.get(skill_id)
            if not skill:
                continue
            # 按伤害/治疗/控制/辅助分类筛选
            if filter_category and filter_category != "all":
                category = self.engine._get_skill_category(skill)
                if category != filter_category:
                    continue
            requirement = info.get("requirement", "")
            req_quest = info.get("requirement_value", "")
            req_name = ""
            # 流派要求：requirement = "path_XX"
            if requirement and requirement.startswith("path_"):
                path_id = requirement[5:]
                path_names = {"fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
                              "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
                              "zhen": "阵修", "fu": "符修"}
                req_name = f"（需流派：{path_names.get(path_id, path_id)}）"
            elif req_quest:
                q = self.engine.quest_library.get(req_quest)
                req_name = f"（需完成：{q.name if q else req_quest}）"
            s_item = QListWidgetItem(f"{skill.name} {req_name}")
            s_item.setData(256, skill_id)
            s_item.setToolTip(skill.description)
            self.skill_list.addItem(s_item)

    def _setup_shop_tab(self):
        layout = QVBoxLayout(self.shop_tab)

        # 购买
        buy_layout = QHBoxLayout()
        self.shop_list = QListWidget()
        self.shop_list.itemClicked.connect(self._on_shop_item_selected)
        buy_layout.addWidget(self.shop_list)

        buy_btn_layout = QVBoxLayout()
        self.buy_quantity_spin = QSpinBox()
        self.buy_quantity_spin.setRange(1, 1)
        self.buy_quantity_spin.setEnabled(False)
        self.buy_quantity_spin.setToolTip("选择购买数量")
        self.buy_quantity_spin.valueChanged.connect(self._update_buy_total_preview)
        buy_btn_layout.addWidget(QLabel("数量："))
        buy_btn_layout.addWidget(self.buy_quantity_spin)
        self.buy_total_label = QLabel("预计花费：—")
        self.buy_total_label.setToolTip("根据单价与数量实时计算")
        buy_btn_layout.addWidget(self.buy_total_label)
        self.buy_btn = QPushButton("购买")
        self.buy_btn.clicked.connect(self._on_buy)
        self.buy_btn.setEnabled(False)
        buy_btn_layout.addWidget(self.buy_btn)
        buy_btn_layout.addStretch()
        buy_layout.addLayout(buy_btn_layout)
        layout.addLayout(buy_layout)

        # 出售
        layout.addWidget(QLabel("出售背包物品（材料/丹药 → 灵石）："))
        sell_layout = QHBoxLayout()
        self.sell_list = QListWidget()
        # 支持 Ctrl+A、Shift+点击多选后批量出售
        self.sell_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.sell_list.itemSelectionChanged.connect(self._on_sell_selection_changed)
        sell_layout.addWidget(self.sell_list)

        sell_btn_layout = QVBoxLayout()
        self.sell_quantity_spin = QSpinBox()
        self.sell_quantity_spin.setRange(1, 1)
        self.sell_quantity_spin.setEnabled(False)
        self.sell_quantity_spin.setToolTip("选择要出售的数量")
        self.sell_quantity_spin.valueChanged.connect(self._update_sell_total_preview)
        sell_btn_layout.addWidget(QLabel("数量："))
        sell_btn_layout.addWidget(self.sell_quantity_spin)
        self.sell_total_label = QLabel("预计获得：—")
        self.sell_total_label.setToolTip("根据单价与数量实时计算")
        sell_btn_layout.addWidget(self.sell_total_label)
        self.sell_btn = QPushButton("出售")
        self.sell_btn.clicked.connect(self._on_sell)
        self.sell_btn.setEnabled(False)
        sell_btn_layout.addWidget(self.sell_btn)

        self.bulk_sell_btn = QPushButton("批量出售")
        self.bulk_sell_btn.setToolTip("出售所有选中的物品堆栈")
        self.bulk_sell_btn.clicked.connect(self._on_bulk_sell)
        self.bulk_sell_btn.setEnabled(False)
        sell_btn_layout.addWidget(self.bulk_sell_btn)
        sell_btn_layout.addStretch()
        sell_layout.addLayout(sell_btn_layout)
        layout.addLayout(sell_layout)

    def _setup_path_tab(self):
        """搭建流派转换界面：流派列表 + 代价提示 + 转换按钮。"""
        layout = QVBoxLayout(self.path_tab)

        # 顶部说明：转换代价
        warn_label = QLabel(
            "转换流派代价：\n"
            "  • 遗忘当前流派的全部专属技能\n"
            "  • 流派专属资源清零（真气护盾/怒气/剑意/邪气）\n"
            "请慎重选择。"
        )
        warn_label.setWordWrap(True)
        warn_label.setStyleSheet("color: #c0392b; padding: 4px;")
        layout.addWidget(warn_label)

        # 当前流派显示
        self.path_current_label = QLabel("当前流派：—")
        self.path_current_label.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self.path_current_label)

        # 可选流派列表
        layout.addWidget(QLabel("可选择的目标流派："))
        self.path_list = QListWidget()
        self.path_list.itemClicked.connect(self._on_path_selected)
        layout.addWidget(self.path_list)

        # 选中流派详情
        self.path_info_label = QLabel("请选择目标流派")
        self.path_info_label.setWordWrap(True)
        layout.addWidget(self.path_info_label)

        # 转换按钮
        self.switch_path_btn = QPushButton("转换流派")
        self.switch_path_btn.clicked.connect(self._on_switch_path)
        self.switch_path_btn.setEnabled(False)
        layout.addWidget(self.switch_path_btn)

    def _setup_companion_tab(self):
        """搭建道侣界面：亲密度显示 + 双修按钮。"""
        layout = QVBoxLayout(self.companion_tab)

        self.companion_info_label = QLabel("请选择道侣")
        self.companion_info_label.setWordWrap(True)
        self.companion_info_label.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self.companion_info_label)

        self.dual_cultivate_btn = QPushButton("双修")
        self.dual_cultivate_btn.setToolTip("与道侣双修，提升修为与亲密度")
        self.dual_cultivate_btn.clicked.connect(self._on_dual_cultivate)
        layout.addWidget(self.dual_cultivate_btn)

    def _setup_social_tab(self):
        """搭建社交界面：关系、论道、双修、收徒、恩怨。"""
        layout = QVBoxLayout(self.social_tab)

        # 当前关系与恩怨状态
        self.social_info_label = QLabel("请选择一位 NPC。")
        self.social_info_label.setWordWrap(True)
        self.social_info_label.setStyleSheet(
            "font-weight: bold; padding: 6px; background-color: #f8f9fa; "
            "border-radius: 6px;"
        )
        layout.addWidget(self.social_info_label)

        # 操作按钮
        btn_layout = QHBoxLayout()

        self.debate_btn = QPushButton("论道")
        self.debate_btn.setToolTip("与 NPC 论道，胜者提升悟性与好感度")
        self.debate_btn.clicked.connect(self._on_debate)
        btn_layout.addWidget(self.debate_btn)

        self.social_dual_cultivate_btn = QPushButton("双修")
        self.social_dual_cultivate_btn.setToolTip("与 NPC 阴阳调和，提升修为")
        self.social_dual_cultivate_btn.clicked.connect(
            self._on_social_dual_cultivate
        )
        btn_layout.addWidget(self.social_dual_cultivate_btn)

        self.accept_disciple_btn = QPushButton("收徒")
        self.accept_disciple_btn.setToolTip("收 NPC 为徒")
        self.accept_disciple_btn.clicked.connect(self._on_accept_disciple)
        btn_layout.addWidget(self.accept_disciple_btn)

        self.teach_disciple_btn = QPushButton("教导徒弟")
        self.teach_disciple_btn.setToolTip("传授徒弟技艺")
        self.teach_disciple_btn.clicked.connect(self._on_teach_disciple)
        btn_layout.addWidget(self.teach_disciple_btn)

        layout.addLayout(btn_layout)

        # 恩怨操作
        grudge_layout = QHBoxLayout()
        self.add_grudge_btn = QPushButton("结怨")
        self.add_grudge_btn.setToolTip("与 NPC 结下恩怨")
        self.add_grudge_btn.clicked.connect(self._on_add_grudge)
        grudge_layout.addWidget(self.add_grudge_btn)

        self.resolve_grudge_btn = QPushButton("化解恩怨")
        self.resolve_grudge_btn.setToolTip("在好感度非负时化解恩怨")
        self.resolve_grudge_btn.clicked.connect(self._on_resolve_grudge)
        grudge_layout.addWidget(self.resolve_grudge_btn)

        layout.addLayout(grudge_layout)
        layout.addStretch()

    def _refresh_social_tab(self, npc_id):
        """刷新社交标签页内容。"""
        social_mgr = self.engine.social_manager
        npc = self.engine.npc_library.get(npc_id)
        if not npc:
            self.social_info_label.setText("NPC 不存在。")
            return

        rel = self.engine.player.get_npc_relationship(npc_id)
        rel_stars = "★" * max(0, rel) + "☆" * (10 - max(0, rel))
        rel_text = f"好感度：{rel_stars} ({rel})"

        # 恩怨状态
        grudge = self.engine.player.grudges.get(npc_id)
        if grudge:
            grudge_text = (
                f"恩怨等级：{grudge['level']} "
                f"（{grudge.get('reason', '无') }）"
            )
        else:
            grudge_text = "无恩怨"

        # 关系标签
        relation_tags = []
        if self.engine.player.master_id == npc_id:
            relation_tags.append("师父")
        if npc_id in [d["npc_id"] for d in self.engine.player.disciples]:
            relation_tags.append("徒弟")
        if npc_id in getattr(self.engine.player, "sworn_brothers", []):
            relation_tags.append("结拜兄弟")
        if npc_id in getattr(self.engine.player, "revenge_targets", []):
            relation_tags.append("复仇目标")
        tag_text = "　".join(relation_tags) if relation_tags else "无特殊关系"

        self.social_info_label.setText(
            f"{npc.name}<br>{rel_text}<br>"
            f"恩怨：{grudge_text}<br>关系：{tag_text}"
        )

        # 各按钮可用性
        can_debate, _ = social_mgr.can_debate(npc_id)
        self.debate_btn.setEnabled(can_debate)

        can_dual, _ = social_mgr.can_dual_cultivate(npc_id)
        self.social_dual_cultivate_btn.setEnabled(can_dual)

        can_accept, _ = social_mgr.can_accept_disciple(npc_id)
        self.accept_disciple_btn.setEnabled(can_accept)

        is_disciple = npc_id in [
            d["npc_id"] for d in self.engine.player.disciples
        ]
        self.teach_disciple_btn.setVisible(is_disciple)
        self.teach_disciple_btn.setEnabled(is_disciple)

        self.add_grudge_btn.setEnabled(
            not self.engine.player.has_grudge(npc_id)
        )
        can_resolve = (
            self.engine.player.has_grudge(npc_id)
            and self.engine.player.get_npc_relationship(npc_id) >= 0
        )
        self.resolve_grudge_btn.setEnabled(can_resolve)

    def _on_debate(self):
        """论道按钮回调。"""
        if not self.selected_npc:
            return
        self.engine.debate_with_npc(self.selected_npc.id)
        self._on_npc_selected(self.npc_list.currentItem())

    def _on_social_dual_cultivate(self):
        """社交标签页双修按钮回调。"""
        if not self.selected_npc:
            return
        self.engine.dual_cultivate_with_npc(self.selected_npc.id)
        self._on_npc_selected(self.npc_list.currentItem())

    def _on_accept_disciple(self):
        """收徒按钮回调。"""
        if not self.selected_npc:
            return
        self.engine.accept_npc_as_disciple(self.selected_npc.id)
        self._on_npc_selected(self.npc_list.currentItem())

    def _on_teach_disciple(self):
        """教导徒弟按钮回调。"""
        if not self.selected_npc:
            return
        self.engine.teach_disciple(self.selected_npc.id)
        self._on_npc_selected(self.npc_list.currentItem())

    def _on_add_grudge(self):
        """结怨按钮回调。"""
        if not self.selected_npc:
            return
        self.engine.add_grudge_with_npc(self.selected_npc.id, "言语冲突")
        self._on_npc_selected(self.npc_list.currentItem())

    def _on_resolve_grudge(self):
        """化解恩怨按钮回调。"""
        if not self.selected_npc:
            return
        self.engine.resolve_grudge_with_npc(self.selected_npc.id)
        self._on_npc_selected(self.npc_list.currentItem())

    def _refresh_companion_tab(self, npc_id):
        """刷新道侣界面内容。"""
        companion_mgr = CompanionManager(
            self.engine.player, self.engine.world, npc_library=self.engine.npc_library
        )
        companion = companion_mgr._get_companion(npc_id)
        if not companion:
            self.companion_info_label.setText("该 NPC 不是你的道侣。")
            self.dual_cultivate_btn.setEnabled(False)
            return
        intimacy = companion.get("intimacy", 0)
        level_name = companion_mgr.get_intimacy_level_name(intimacy)
        alive_text = "在世" if companion.get("is_alive", True) else "已逝"
        self.companion_info_label.setText(
            f"亲密度：{intimacy}（{level_name}）　状态：{alive_text}"
        )
        can_dual, _ = companion_mgr.can_dual_cultivate(npc_id)
        self.dual_cultivate_btn.setEnabled(can_dual)

    def _on_form_companion(self):
        """结为道侣按钮回调。"""
        if not self.selected_npc:
            return
        companion_mgr = CompanionManager(
            self.engine.player, self.engine.world, npc_library=self.engine.npc_library
        )
        ok, msg = companion_mgr.form_companion(self.selected_npc.id)
        if ok:
            self.engine.notify(msg)
            self._on_npc_selected(self.npc_list.currentItem())
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "结为道侣失败", msg)

    def _on_dual_cultivate(self):
        """双修按钮回调。"""
        if not self.selected_npc:
            return
        companion_mgr = CompanionManager(
            self.engine.player, self.engine.world, npc_library=self.engine.npc_library
        )
        ok, msg = companion_mgr.dual_cultivate(self.selected_npc.id)
        if ok:
            self.engine.notify(msg)
            self._refresh_companion_tab(self.selected_npc.id)
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "无法双修", msg)

    def _refresh_path_tab(self):
        """刷新流派转换界面内容（选中道师时调用）。"""
        path_cfg = self.engine.path_config
        current_id = self.engine.player.cultivation_path
        current_name = path_cfg.get_path_name(current_id)
        self.path_current_label.setText(f"当前流派：【{current_name}】")

        self.path_list.clear()
        self.path_info_label.setText("请选择目标流派")
        self.switch_path_btn.setEnabled(False)
        self.selected_path_id = None

        # 列出所有流派，跳过当前流派
        for pid in path_cfg.get_all_path_ids():
            if pid == current_id:
                continue
            name = path_cfg.get_path_name(pid)
            item = QListWidgetItem(name)
            item.setData(256, pid)
            self.path_list.addItem(item)

    def _on_path_selected(self, item):
        """选中目标流派时显示详情。"""
        pid = item.data(256)
        self.selected_path_id = pid
        path_cfg = self.engine.path_config
        name = path_cfg.get_path_name(pid)
        path_data = path_cfg.get_path(pid) or {}
        desc = path_data.get("description", "")
        difficulty = path_data.get("difficulty", 0)
        resource_name = path_data.get("resource_name", "")
        exclusive = path_data.get("exclusive_skills", [])
        excl_text = "、".join(exclusive) if exclusive else "无"

        self.path_info_label.setText(
            f"【{name}】\n"
            f"难度：{'★' * difficulty}{'☆' * (5 - difficulty)}\n"
            f"特点：{desc}\n"
            f"专属资源：{resource_name}\n"
            f"专属技能：{excl_text}\n"
            f"\n转换后将遗忘当前流派专属技能，资源清零。"
        )
        self.switch_path_btn.setEnabled(True)

    def _on_switch_path(self):
        """执行流派转换。"""
        if not getattr(self, "selected_path_id", None):
            return
        # 调用 engine 执行转换
        ok = self.engine.switch_cultivation_path(self.selected_path_id)
        if ok:
            self.accept()

    def _refresh_npc_list(self):
        """刷新当前地点 NPC 列表。"""
        self.npc_list.clear()

        # 如果有预设 NPC（如偶遇的云游商人），只显示它
        if self.preset_npc:
            item = QListWidgetItem(self.preset_npc.name)
            item.setData(256, self.preset_npc)
            self.npc_list.addItem(item)
            # 自动选中
            self.npc_list.setCurrentRow(0)
            self._on_npc_selected(item)
            return

        npcs = self.engine.get_location_npcs()
        if not npcs:
            self.info_label.setText("此地杳无人烟。")
            return

        for npc in npcs:
            item = QListWidgetItem(npc.name)
            item.setData(256, npc)
            self.npc_list.addItem(item)

    def _get_sect_relation_info(self, npc):
        """
        获取 NPC 所属宗门与玩家宗门的关系信息。
        优先使用 NPC 的 sect_id，未配置则按 location 推断。
        返回 (status, sect, display_text, is_wanted)。
        """
        sect = None
        sect_id = getattr(npc, "sect_id", None)
        if sect_id:
            sect = self.engine.sect_library.get(sect_id)
        if not sect and getattr(npc, "location", None):
            sect = self.engine.sect_library.get_by_location(npc.location)
        if not sect:
            return "neutral", None, "", False

        status = self.engine.sect_manager.get_relation_status(sect.id)
        status_names = {"friendly": "友好", "hostile": "敌对", "neutral": "中立"}
        relation_name = status_names.get(status, status)
        display_text = f"所属势力：【{sect.name}】（关系：{relation_name}）"

        is_wanted = sect.id in getattr(self.engine.player, "sect_wanted_by", [])
        if is_wanted:
            display_text += "　[通缉] 你已被该宗门追杀！"

        return status, sect, display_text, is_wanted

    def _on_npc_selected(self, item):
        """选中 NPC 时显示详情和相关选项，并根据宗门关系调整交互。"""
        npc = item.data(256)
        self.selected_npc = npc

        # 记录玩家访问该 NPC（记忆系统）
        self.engine.player.record_npc_visit(npc.id, self.engine.world)

        # 获取好感度信息
        rel = self.engine.player.get_npc_relationship(npc.id)
        rel_text = f"好感度：{'★' * rel}{'☆' * (10 - rel)}" if rel > 0 else "好感度：☆☆☆☆☆☆☆☆☆☆（陌生）"
        # 宗门关系信息
        status, sect, sect_text, is_wanted = self._get_sect_relation_info(npc)

        # 节日与记忆对话
        festival_id = self.engine.world.get_current_festival()
        player_memory = self.engine.player.get_npc_memory(npc.id).get("choices", {})
        dialog = npc.get_dialog(rel, festival_id=festival_id, player_memory=player_memory)

        # 根据关系状态给势力文本染色：友好绿色、敌对红色、中立灰色
        status_color = {
            "friendly": "#27ae60",
            "hostile": "#c0392b",
            "neutral": "#7f8c8d",
        }.get(status, "#7f8c8d")
        sect_html = (
            f'<span style="color:{status_color}; font-weight:bold;">{sect_text}</span>'
            if sect_text else ""
        )

        # 作息状态
        time_label = self.engine.world.get_time_label()
        active = npc.is_active_at(self.engine.world.hour)
        schedule_text = f"当前时辰：{time_label}　{'【可交互】' if active else '【休息中】'}"
        if not active and npc.schedule:
            schedule_text += f"（{npc.schedule.get('rest_dialog', 'NPC 正在休息')}）"

        # 关系网展示
        rel_net = npc.npc_relationships
        rel_net_text = ""
        if rel_net:
            parts = []
            if rel_net.get("master"):
                parts.append(f"师尊：{self._get_npc_name(rel_net['master'])}")
            if rel_net.get("lovers"):
                parts.append(f"道侣：{', '.join(self._get_npc_name(x) for x in rel_net['lovers'])}")
            if rel_net.get("friends"):
                parts.append(f"好友：{', '.join(self._get_npc_name(x) for x in rel_net['friends'])}")
            if rel_net.get("enemies"):
                parts.append(f"宿敌：{', '.join(self._get_npc_name(x) for x in rel_net['enemies'])}")
            if parts:
                rel_net_text = "<br>" + "　".join(parts)

        # 头像显示
        portrait = getattr(npc, "portrait", None)
        if portrait:
            self.portrait_label.setText("")
            self.portrait_label.setStyleSheet(
                f"border: 1px solid #aaa; background: #f0f0f0; "
                f"background-image: url({portrait}); background-position: center; background-repeat: no-repeat;"
            )
        else:
            self.portrait_label.setText("无头像")
            self.portrait_label.setStyleSheet("border: 1px solid #aaa; background: #f0f0f0;")

        info_html = f"<b>{npc.name}</b><br>{npc.description}<br>{rel_text}<br>{schedule_text}"
        if sect_html:
            info_html += "<br>" + sect_html
        if rel_net_text:
            info_html += rel_net_text
        if festival_id:
            festival_name = self.engine.world.festivals.get(festival_id, {}).get("name", festival_id)
            info_html += f"<br><span style='color:#e67e22;'>今日节日：{festival_name}</span>"
        info_html += f"<br><br>「{dialog}」"
        self.info_label.setText(info_html)

        # 敌对宗门 NPC：禁止接任务与学技能，并显示挑衅按钮
        is_hostile = status == "hostile"
        self.provoke_btn.setVisible(is_hostile)

        # 对话按钮：NPC 有 dialogue_id 且非敌对时显示
        has_dialogue = bool(getattr(npc, "dialogue_id", None))
        self.talk_btn.setVisible(has_dialogue and not is_hostile)

        # 道侣按钮与标签
        companion_mgr = CompanionManager(
            self.engine.player, self.engine.world, npc_library=self.engine.npc_library
        )
        is_companion = companion_mgr._get_companion(npc.id) is not None
        can_form, _ = companion_mgr.can_form_companion(npc.id)
        self.form_companion_btn.setVisible(not is_hostile and not is_companion and can_form)
        self.tabs.setTabVisible(self.companion_tab_index, is_companion)
        if is_companion:
            self._refresh_companion_tab(npc.id)

        # 任务
        self.quest_list.clear()
        self.accept_quest_btn.setEnabled(False)
        if is_hostile:
            disabled_item = QListWidgetItem("该宗门与你敌对，无法接取任务。")
            disabled_item.setFlags(disabled_item.flags() & ~Qt.ItemIsEnabled)
            self.quest_list.addItem(disabled_item)
        else:
            for quest_id in npc.quests:
                if quest_id in self.engine.player.quest_progress or quest_id in self.engine.player.completed_quests:
                    continue
                quest = self.engine.quest_library.get(quest_id)
                if quest:
                    q_item = QListWidgetItem(quest.name)
                    q_item.setData(256, quest_id)
                    q_item.setToolTip(quest.description)
                    self.quest_list.addItem(q_item)

        # 支线任务
        self.side_quest_list.clear()
        self.accept_side_quest_btn.setEnabled(False)
        if is_hostile:
            disabled_item = QListWidgetItem("该宗门与你敌对，无法接取支线任务。")
            disabled_item.setFlags(disabled_item.flags() & ~Qt.ItemIsEnabled)
            self.side_quest_list.addItem(disabled_item)
        else:
            side_mgr = self.engine.side_quest_manager
            available = side_mgr.get_available_quests(npc.location)
            # 仅显示该 NPC 发布的支线任务
            for sq in available:
                if sq.get("giver_npc_id") == npc.id:
                    item = QListWidgetItem(sq["name"])
                    item.setData(256, sq["id"])
                    item.setToolTip(sq.get("description", ""))
                    self.side_quest_list.addItem(item)
            if self.side_quest_list.count() == 0:
                disabled_item = QListWidgetItem("当前无可用支线任务。")
                disabled_item.setFlags(disabled_item.flags() & ~Qt.ItemIsEnabled)
                self.side_quest_list.addItem(disabled_item)

        # 技能
        self._refresh_skill_list(npc, is_hostile)

        # 商店：使用好感度解锁的完整商品列表
        self.shop_list.clear()
        self.buy_btn.setEnabled(False)
        available_items = npc.get_unlocked_shop_items(rel)
        # 宗门关系对价格的影响，用于 tooltip 说明
        buy_mult, sell_mult = self.engine.get_sect_price_multiplier(npc)
        for info in available_items:
            item_id = info["item_id"]
            price = self.engine.get_buy_price(item_id, npc)
            shop_item_obj = self.engine.item_library.get(item_id)
            if shop_item_obj:
                # 好感度解锁的商品标注「独家」
                is_locked = any(
                    l["item_id"] == item_id for l in getattr(npc, "locked_shop_items", [])
                )
                prefix = "[独家] " if is_locked else ""
                shop_item = QListWidgetItem(f"{prefix}{shop_item_obj.name} - {price} 灵石")
                # 存储动态计算后的价格，避免再次计算不一致
                shop_item.setData(256, {"item_id": item_id, "price": price})
                # 价格说明：基础描述 + 宗门关系影响
                price_note = ""
                if buy_mult != 1.0:
                    price_note = f"\n[宗门关系] 购买价格 ×{buy_mult:.1f}"
                elif sell_mult != 1.0:
                    price_note = f"\n[宗门关系] 出售价格 ×{sell_mult:.1f}"
                shop_item.setToolTip(f"{shop_item_obj.description}{price_note}")
                self.shop_list.addItem(shop_item)

        # 刷新出售列表
        self._refresh_sell_list()

        # 流派转换 tab：仅道师 NPC（path_switch=True）可见
        is_path_master = bool(getattr(npc, "path_switch", False))
        self.tabs.setTabVisible(self.path_tab_index, is_path_master)
        if is_path_master:
            self._refresh_path_tab()

        # 刷新社交标签页
        self._refresh_social_tab(npc.id)

    def _refresh_sell_list(self):
        """刷新可出售物品列表：按物品 ID 聚合，并显示总数与总价。"""
        self.sell_list.clear()
        self.sell_btn.setEnabled(False)
        self.bulk_sell_btn.setEnabled(False)
        self.selected_sell_item = None
        self.selected_sell_items = []
        self.sell_quantity_spin.setValue(1)
        self.sell_quantity_spin.setRange(1, 1)
        self.sell_quantity_spin.setEnabled(False)
        self.sell_total_label.setText("预计获得：—")

        # 按物品 ID 统计可出售数量（装备类不可出售）
        counts = {}
        for item in self.engine.player.inventory:
            if item.type in self.engine.player.EQUIPMENT_SLOTS:
                continue
            if item.id not in counts:
                counts[item.id] = {"item": item, "count": 0}
            counts[item.id]["count"] += 1

        for entry in counts.values():
            item = entry["item"]
            count = entry["count"]
            price = self.engine.get_sell_price(item, self.selected_npc)
            total = price * count
            display = f"{item.name} x{count} → {total} 灵石"
            list_item = QListWidgetItem(display)
            list_item.setData(256, item)
            self.sell_list.addItem(list_item)

    def _get_npc_name(self, npc_id):
        """根据 NPC ID 获取名称，不存在则返回 ID。"""
        npc = self.engine.npc_library.get(npc_id)
        return npc.name if npc else npc_id

    def _on_quest_selected(self, item):
        """选中任务。"""
        self.selected_quest_id = item.data(256)
        quest = self.engine.quest_library.get(self.selected_quest_id)
        self.info_label.setText(
            f"任务：{quest.name}\n{quest.description}\n目标：{quest.count} 个/次"
        )
        self.accept_quest_btn.setEnabled(True)

    def _on_side_quest_selected(self, item):
        """选中支线任务。"""
        self.selected_side_quest_id = item.data(256)
        sq = self.engine.side_quest_manager.config.get(self.selected_side_quest_id)
        if sq:
            self.info_label.setText(
                f"支线任务：{sq['name']}\n{sq.get('description', '')}\n奖励：{sq.get('rewards', {})}"
            )
            self.accept_side_quest_btn.setEnabled(True)

    def _on_accept_side_quest(self):
        """接受选中的支线任务。"""
        sqid = getattr(self, "selected_side_quest_id", None)
        if not sqid:
            return
        ok, msg = self.engine.side_quest_manager.accept(sqid)
        self.engine.notify(msg)
        if ok:
            self.accept()

    def _on_skill_selected(self, item):
        """选中技能：显示详情并判断玩家是否满足学习条件。"""
        self.selected_skill_id = item.data(256)
        skill = self.engine.skill_library.get(self.selected_skill_id)
        effective_cost = self.engine._get_effective_qi_cost(self.selected_skill_id)
        category = self.engine._get_skill_category(skill)
        cat_names = {"damage": "伤害", "heal": "治疗", "control": "控制", "support": "辅助"}
        prof_level = self.engine.player.get_skill_proficiency(self.selected_skill_id)
        prof_exp = self.engine.player.skill_proficiency.get(self.selected_skill_id, {}).get("exp", 0)
        need_exp = (
            prof_level * self.engine.player.SKILL_PROFICIENCY_LEVEL_EXP
            if prof_level < self.engine.player.SKILL_PROFICIENCY_MAX_LEVEL else 0
        )
        pct = int(prof_exp / need_exp * 100) if need_exp > 0 else 100
        bar_html = (
            f'<div style="background:#ecf0f1;border-radius:3px;height:10px;width:120px;">'
            f'<div style="background:#3498db;border-radius:3px;height:10px;width:{pct}%;"></div></div>'
        )
        if category == "damage":
            bonus_text = f"伤害 +{int((self.engine.player.get_skill_damage_multiplier(self.selected_skill_id) - 1) * 100)}%"
        elif category == "heal":
            bonus_text = f"治疗 +{int((self.engine.player.get_skill_heal_multiplier(self.selected_skill_id) - 1) * 100)}%"
        elif category == "control":
            bonus_text = f"控制 +{int(self.engine.player.get_skill_control_bonus(self.selected_skill_id) * 100)}%"
        else:
            prof_level = self.engine.player.get_skill_proficiency(self.selected_skill_id)
            bonus_text = f"buff 持续 +{int((prof_level - 1) * self.engine.player.SKILL_PROFICIENCY_SUPPORT_EXTRA_TURN_PER_LEVEL)} 回合"

        lines = [
            f"技能：{skill.name}",
            f"类型：{cat_names.get(category, '伤害')}",
            f"{skill.description}",
            f"消耗真气：{effective_cost}（基础 {skill.qi_cost}）",
            f"冷却：{skill.cooldown} 回合",
        ]
        # 若已习得，显示当前熟练度与进度条
        if self.engine.player.has_skill(self.selected_skill_id):
            lines.append(f"当前熟练度：Lv.{prof_level} {bonus_text}")
            lines.append(bar_html)
        if skill.realm_id:
            realm_data = self.engine.world.get_realm(skill.realm_id)
            realm_name = realm_data.get("name", skill.realm_id) if realm_data else skill.realm_id
            lines.append(f"需要境界：{realm_name}")
        if skill.path_exclusive:
            path_names = {
                "fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
                "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
                "zhen": "阵修", "fu": "符修",
            }
            lines.append(f"需要流派：{path_names.get(skill.path_exclusive, skill.path_exclusive)}")
        if skill.element != "none":
            elem_names = {
                "metal": "金", "wood": "木", "water": "水", "fire": "火", "earth": "土",
                "thunder": "雷", "ice": "冰", "wind": "风", "all": "五行",
            }
            lines.append(f"需要灵根：{elem_names.get(skill.element, skill.element)}")

        # 调用引擎接口检查学习条件，避免玩家花资源后无法使用
        can_learn, learn_reasons = self.engine.can_learn_skill(self.selected_npc, self.selected_skill_id)
        if can_learn:
            lines.append("\n✅ 学习条件：已满足")
            self.learn_skill_btn.setEnabled(True)
        else:
            lines.append("\n❌ 学习条件未满足：")
            lines.extend(f"  • {r}" for r in learn_reasons)
            self.learn_skill_btn.setEnabled(False)

        self.info_label.setText("\n".join(lines))

    def _on_shop_item_selected(self, item):
        """选中商店物品，并初始化数量选择器与花费预览。"""
        self.selected_shop_item = item.data(256)
        item_info = self.engine.item_library.get(self.selected_shop_item["item_id"])
        unit_price = self.selected_shop_item["price"]
        stones = self.engine.player.count_item("spirit_stone")
        max_by_money = max(1, stones // unit_price) if unit_price > 0 else 1
        # 可堆叠物品：优先填满背包中已有的未满堆，避免买超
        if item_info and item_info.stackable:
            owned = self.engine.player.count_item(item_info.id)
            remainder = owned % item_info.max_stack
            space = item_info.max_stack - remainder if remainder else item_info.max_stack
            max_quantity = min(max_by_money, space)
        else:
            max_quantity = 1
        self.buy_quantity_spin.setRange(1, max(1, max_quantity))
        self.buy_quantity_spin.setValue(1)
        self.buy_quantity_spin.setEnabled(True)
        self._update_buy_total_preview()
        self.info_label.setText(
            f"{item_info.name}\n{item_info.description}\n单价：{unit_price} 灵石"
        )
        self.buy_btn.setEnabled(True)

    def _update_buy_total_preview(self):
        """根据当前选择的商品与数量更新预计花费。"""
        shop_item = getattr(self, "selected_shop_item", None)
        if not shop_item:
            self.buy_total_label.setText("预计花费：—")
            return
        unit_price = shop_item["price"]
        quantity = self.buy_quantity_spin.value()
        self.buy_total_label.setText(f"预计花费：{unit_price * quantity} 灵石")

    def _update_sell_total_preview(self):
        """根据当前选中的出售物品与数量更新预计获得灵石。"""
        item = getattr(self, "selected_sell_item", None)
        if not item or not self.selected_npc:
            self.sell_total_label.setText("预计获得：—")
            return
        unit_price = self.engine.get_sell_price(item, self.selected_npc)
        quantity = self.sell_quantity_spin.value()
        self.sell_total_label.setText(f"预计获得：{unit_price * quantity} 灵石")

    def _on_sell_item_selected(self, item):
        """选中要出售的物品，并同步设置数量选择器上限。"""
        self.selected_sell_item = item.data(256)
        max_count = self.engine.player.count_item(self.selected_sell_item.id)
        self.sell_quantity_spin.setRange(1, max_count)
        self.sell_quantity_spin.setValue(1)
        self.sell_quantity_spin.setEnabled(True)
        self.sell_btn.setEnabled(True)
        self._update_sell_total_preview()

    def _on_accept_quest(self):
        """接受选中的任务。"""
        if not getattr(self, "selected_quest_id", None):
            return
        self.engine.accept_quest(self.selected_quest_id)
        self.accept()

    def _on_learn_skill(self):
        """学习选中的技能。"""
        if not getattr(self, "selected_skill_id", None) or not self.selected_npc:
            return
        self.engine.learn_from_npc(self.selected_npc, self.selected_skill_id)
        self.accept()

    def _on_buy(self):
        """购买选中的物品；传入 NPC、单价与数量。"""
        if not getattr(self, "selected_shop_item", None) or not self.selected_npc:
            return
        quantity = self.buy_quantity_spin.value()
        self.engine.buy_item(
            self.selected_shop_item["item_id"],
            self.selected_shop_item["price"],
            self.selected_npc,
            quantity=quantity,
        )
        # 购买后重新计算数量上限与花费预览（灵石已变化）
        current_item = self.shop_list.currentItem()
        if current_item:
            self._on_shop_item_selected(current_item)

    def _on_sell(self):
        """出售选中的物品；传入 NPC 与数量以应用宗门关系修正。"""
        if not getattr(self, "selected_sell_item", None) or not self.selected_npc:
            return
        quantity = self.sell_quantity_spin.value()
        self.engine.sell_item(
            self.selected_sell_item, self.selected_npc, quantity=quantity
        )
        self._refresh_sell_list()

    def _on_sell_selection_changed(self):
        """出售列表选择变化时，区分单选/多选状态并更新按钮与预览。"""
        selected = self.sell_list.selectedItems()
        if not selected:
            self.sell_btn.setEnabled(False)
            self.bulk_sell_btn.setEnabled(False)
            self.sell_quantity_spin.setEnabled(False)
            self.sell_total_label.setText("预计获得：—")
            self.selected_sell_item = None
            self.selected_sell_items = []
            return

        if len(selected) == 1:
            # 单选：走普通出售流程
            self._on_sell_item_selected(selected[0])
            self.bulk_sell_btn.setEnabled(False)
            return

        # 多选：禁用数量微调，启用批量出售
        self.selected_sell_item = None
        self.selected_sell_items = [item.data(256) for item in selected]
        self.sell_quantity_spin.setEnabled(False)
        self.sell_btn.setEnabled(False)
        self.bulk_sell_btn.setEnabled(True)
        total = 0
        for item in self.selected_sell_items:
            count = self.engine.player.count_item(item.id)
            price = self.engine.get_sell_price(item, self.selected_npc)
            total += price * count
        self.sell_total_label.setText(f"预计获得：{total} 灵石")

    def _on_bulk_sell(self):
        """批量出售：弹出逐类数量调整对话框，确认后按设定数量出售。"""
        if not getattr(self, "selected_sell_items", []) or not self.selected_npc:
            return
        dialog = BulkSellDialog(
            self.engine, self.selected_npc, self.selected_sell_items, parent=self
        )
        if dialog.exec() != QDialog.Accepted:
            return
        quantities = dialog.get_quantities()
        for item, count in quantities.items():
            self.engine.sell_item(item, self.selected_npc, quantity=count)
        self._refresh_sell_list()

    def _on_talk(self):
        """打开分支对话窗口。"""
        if not self.selected_npc:
            return
        dialogue_id = getattr(self.selected_npc, "dialogue_id", None)
        if not dialogue_id:
            return
        dialog = DialogueDialog(
            self.engine,
            dialogue_id,
            npc_id=self.selected_npc.id,
            parent=self,
        )
        dialog.exec()
        # 对话结束后刷新 NPC 详情（好感度、任务状态等可能已变化）
        current_item = self.npc_list.currentItem()
        if current_item:
            self._on_npc_selected(current_item)

    def _on_provoke(self):
        """挑衅敌对宗门 NPC：恶化关系、加入通缉，并可能触发战斗。"""
        if not self.selected_npc:
            return

        reply = QMessageBox.warning(
            self,
            "确认挑衅",
            f"挑衅【{self.selected_npc.name}】会恶化宗门关系，"
            f"并可能被该宗门追杀，确定吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        combat_started = self.engine.provoke_sect_npc(self.selected_npc)
        if combat_started:
            # 已触发战斗，关闭 NPC 对话框，由主窗口接管战斗弹窗
            self.accept()
        else:
            # 未触发战斗也刷新信息，体现关系恶化与通缉状态
            current_item = self.npc_list.currentItem()
            if current_item:
                self._on_npc_selected(current_item)


class BulkSellDialog(QDialog):
    """批量出售数量调整弹窗：为每类选中的物品单独设置出售数量。"""

    def __init__(self, engine, npc, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量出售")
        self.resize(320, 200)
        self.engine = engine
        self.npc = npc
        self.items = items

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("请为下列物品调整出售数量："))

        form_layout = QFormLayout()
        self.spin_map = {}
        for item in items:
            max_count = self.engine.player.count_item(item.id)
            unit_price = self.engine.get_sell_price(item, self.npc)
            spin = QSpinBox()
            spin.setRange(0, max_count)
            spin.setValue(max_count)
            spin.setSuffix(f" / {max_count}")
            spin.setToolTip(f"单价 {unit_price} 灵石")
            spin.valueChanged.connect(self._update_total)
            self.spin_map[item] = spin
            form_layout.addRow(f"{item.name}", spin)
        layout.addLayout(form_layout)

        self.total_label = QLabel("预计获得：0 灵石")
        self.total_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.total_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_total()

    def _update_total(self):
        """根据所有数量选择器实时更新总收益。"""
        total = 0
        for item, spin in self.spin_map.items():
            unit_price = self.engine.get_sell_price(item, self.npc)
            total += unit_price * spin.value()
        self.total_label.setText(f"预计获得：{total} 灵石")

    def get_quantities(self):
        """返回 {item: quantity} 字典（数量为 0 的项已过滤）。"""
        return {item: spin.value() for item, spin in self.spin_map.items() if spin.value() > 0}
