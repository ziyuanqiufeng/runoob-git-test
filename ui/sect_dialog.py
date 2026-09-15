from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QTabWidget,
    QWidget as BaseWidget, QSpinBox, QComboBox
)
from PySide6.QtCore import Qt

from ui.sect_tournament_dialog import SectTournamentDialog


class SectDialog(QDialog):
    """宗门主界面弹窗：信息、任务、商店、藏经阁、捐献、晋升。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("宗门")
        self.resize(650, 550)
        self.engine = engine
        self.player = engine.player
        self.item_library = engine.item_library
        self.skill_library = engine.skill_library

        self.layout = QVBoxLayout(self)

        # 顶部信息栏
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font: 14px 'Microsoft YaHei'; padding: 6px;")
        self.layout.addWidget(self.info_label)

        # 标签页
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # 宗门信息/操作页
        self.info_tab = BaseWidget()
        self._setup_info_tab()
        self.tabs.addTab(self.info_tab, "宗门")

        # 宗门大比
        self.tournament_tab = BaseWidget()
        self._setup_tournament_tab()
        self.tabs.addTab(self.tournament_tab, "大比")

        # 宗门设施
        self.facility_tab = BaseWidget()
        self._setup_facility_tab()
        self.tabs.addTab(self.facility_tab, "设施")

        # 任务大厅
        self.task_tab = BaseWidget()
        self._setup_task_tab()
        self.tabs.addTab(self.task_tab, "任务")

        # 贡献商店
        self.shop_tab = BaseWidget()
        self._setup_shop_tab()
        self.tabs.addTab(self.shop_tab, "商店")

        # 藏经阁
        self.scripture_tab = BaseWidget()
        self._setup_scripture_tab()
        self.tabs.addTab(self.scripture_tab, "藏经阁")

        # 捐献
        self.donate_tab = BaseWidget()
        self._setup_donate_tab()
        self.tabs.addTab(self.donate_tab, "捐献")

        # 宗门仓库与捐献排行榜
        self.warehouse_tab = BaseWidget()
        self._setup_warehouse_tab()
        self.tabs.addTab(self.warehouse_tab, "仓库")

        # 宗门悬赏榜
        self.bounty_tab = BaseWidget()
        self._setup_bounty_tab()
        self.tabs.addTab(self.bounty_tab, "悬赏")

        # 宗门秘境/禁地探索
        self.secret_realm_tab = BaseWidget()
        self._setup_secret_realm_tab()
        self.tabs.addTab(self.secret_realm_tab, "秘境")

        # 宗门传承与祖师堂
        self.ancestral_hall_tab = BaseWidget()
        self._setup_ancestral_hall_tab()
        self.tabs.addTab(self.ancestral_hall_tab, "祖师堂")

        # 宗门灵兽园与坐骑
        self.beast_garden_tab = BaseWidget()
        self._setup_beast_garden_tab()
        self.tabs.addTab(self.beast_garden_tab, "灵兽园")

        # 弟子招募与追随者
        self.follower_tab = BaseWidget()
        self._setup_follower_tab()
        self.tabs.addTab(self.follower_tab, "追随者")

        # 真传洞府
        self.cave_tab = BaseWidget()
        self._setup_cave_tab()
        self.tabs.addTab(self.cave_tab, "洞府")

        # 外交与宗门战
        self.diplomacy_tab = BaseWidget()
        self._setup_diplomacy_tab()
        self.tabs.addTab(self.diplomacy_tab, "外交")

        # 世界 BOSS
        self.world_boss_tab = BaseWidget()
        self._setup_world_boss_tab()
        self.tabs.addTab(self.world_boss_tab, "世界BOSS")

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        self.layout.addWidget(close_btn)

        self._refresh_all()

    # ==================== 信息页 ====================

    def _setup_info_tab(self):
        layout = QVBoxLayout(self.info_tab)

        self.sect_desc_label = QLabel()
        self.sect_desc_label.setWordWrap(True)
        layout.addWidget(self.sect_desc_label)

        self.promote_btn = QPushButton("申请晋升")
        self.promote_btn.setToolTip("满足贡献与境界条件后可晋升职位")
        self.promote_btn.clicked.connect(self._on_promote)
        layout.addWidget(self.promote_btn)

        self.leave_btn = QPushButton("退出宗门")
        self.leave_btn.setToolTip("退出后贡献清零，且可能被原宗门追杀")
        self.leave_btn.clicked.connect(self._on_leave)
        layout.addWidget(self.leave_btn)

        # 未加入宗门时显示可加入列表
        self.join_list = QListWidget()
        self.join_list.itemClicked.connect(self._on_join_item_selected)
        layout.addWidget(self.join_list)

        self.join_btn = QPushButton("拜入宗门")
        self.join_btn.setEnabled(False)
        self.join_btn.clicked.connect(self._on_join)
        layout.addWidget(self.join_btn)

        layout.addStretch()

    # ==================== 宗门大比页 ====================

    def _setup_tournament_tab(self):
        """设置宗门大比页：显示报名条件与打开大比弹窗。"""
        layout = QVBoxLayout(self.tournament_tab)

        self.tournament_info_label = QLabel()
        self.tournament_info_label.setWordWrap(True)
        layout.addWidget(self.tournament_info_label)

        self.tournament_btn = QPushButton("参加宗门大比")
        self.tournament_btn.setToolTip("满足条件后可与同门弟子逐轮切磋")
        self.tournament_btn.clicked.connect(self._on_open_tournament)
        layout.addWidget(self.tournament_btn)

        layout.addStretch()

    def _refresh_tournament_tab(self):
        """刷新宗门大比页显示。"""
        event = self.engine.sect_manager.get_sect_event("tournament")
        if not event:
            self.tournament_info_label.setText("当前宗门未举办宗门大比。")
            self.tournament_btn.setEnabled(False)
            return

        ok, msg = self.engine.sect_manager.can_start_tournament()
        if ok:
            self.tournament_info_label.setText(
                f"【{event.name}】即将开始！\n"
                f"共 {event.rounds} 轮，每轮胜利 +{event.rewards.get('contribution_per_win', 0)} 贡献。"
            )
            self.tournament_btn.setEnabled(True)
        else:
            self.tournament_info_label.setText(f"【{event.name}】\n{msg}")
            self.tournament_btn.setEnabled(False)

    def _on_open_tournament(self):
        """打开宗门大比弹窗。"""
        dialog = SectTournamentDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_all()

    # ==================== 宗门设施页 ====================

    def _setup_facility_tab(self):
        """设置宗门设施页：显示可租用设施与当前活跃效果。"""
        layout = QVBoxLayout(self.facility_tab)

        self.facility_info_label = QLabel()
        self.facility_info_label.setWordWrap(True)
        layout.addWidget(self.facility_info_label)

        self.facility_list = QListWidget()
        self.facility_list.itemClicked.connect(self._on_facility_selected)
        layout.addWidget(self.facility_list)

        self.facility_detail_label = QLabel("请选择设施")
        self.facility_detail_label.setWordWrap(True)
        layout.addWidget(self.facility_detail_label)

        self.use_facility_btn = QPushButton("使用设施")
        self.use_facility_btn.clicked.connect(self._on_use_facility)
        self.use_facility_btn.setEnabled(False)
        layout.addWidget(self.use_facility_btn)

        self.active_facility_label = QLabel()
        self.active_facility_label.setWordWrap(True)
        layout.addWidget(self.active_facility_label)

        layout.addStretch()

    def _refresh_facility_tab(self):
        """刷新宗门设施页。"""
        sect = self.engine.sect_manager.get_sect()
        if not sect:
            self.facility_info_label.setText("未加入宗门")
            self.facility_list.clear()
            self.facility_detail_label.setText("请先加入宗门")
            self.use_facility_btn.setEnabled(False)
            self.active_facility_label.setText("")
            return

        facilities = self.engine.sect_manager.get_facility_details()
        self.facility_list.clear()
        self.selected_facility = None
        self.use_facility_btn.setEnabled(False)
        self.facility_detail_label.setText("请选择设施")

        for facility in facilities:
            item = QListWidgetItem(
                f"{facility['name']} - {facility['cost']} 贡献"
            )
            item.setData(256, facility["id"])
            self.facility_list.addItem(item)

        # 显示当前活跃效果
        active = getattr(self.player, "active_facility_effects", {})
        if active:
            parts = []
            for fid, effects in active.items():
                name = effects.get("name", fid)
                remaining = effects.get("remaining_months", 0)
                parts.append(f"【{name}】剩余 {remaining} 个月")
            self.active_facility_label.setText("当前活跃设施效果：\n" + "\n".join(parts))
        else:
            self.active_facility_label.setText("当前无活跃设施效果")

        self.facility_info_label.setText(
            f"贡献：{self.player.sect_contribution}　"
            f"职位：{sect.get_rank_name(self.player.sect_rank)}"
        )

    def _on_facility_selected(self, item):
        """选中某个设施时显示详情。"""
        facility_id = item.data(256)
        facility = self.engine.sect_manager._get_facility(facility_id)
        self.selected_facility = facility
        if not facility:
            self.facility_detail_label.setText("设施数据异常")
            self.use_facility_btn.setEnabled(False)
            return

        effects = facility.get("effects", {})
        desc_parts = []
        if "cultivation_speed" in effects:
            desc_parts.append(
                f"修炼速度 +{int(effects['cultivation_speed'] * 100)}%"
            )
        if "give_items" in effects:
            items = ", ".join(
                f"{self.engine.item_library.get(iid).name} ×{count}"
                for iid, count in effects["give_items"].items()
            )
            desc_parts.append(f"立即获得：{items}")
        if "refine_success_bonus" in effects:
            desc_parts.append(
                f"炼器成功率 +{int(effects['refine_success_bonus'] * 100)}%"
            )
        if effects.get("duration_months"):
            desc_parts.append(f"持续 {effects['duration_months']} 个月")

        self.facility_detail_label.setText(
            f"{facility['name']}\n"
            f"消耗贡献：{facility['cost']}\n"
            f"效果：{'；'.join(desc_parts)}"
        )

        ok, _ = self.engine.sect_manager.can_use_facility(facility_id)
        self.use_facility_btn.setEnabled(ok)

    def _on_use_facility(self):
        """使用选中的设施。"""
        if not self.selected_facility:
            return
        facility_id = self.selected_facility["id"]
        self.engine.use_facility(facility_id)
        self._refresh_all()

    # ==================== 任务页 ====================

    def _setup_task_tab(self):
        layout = QVBoxLayout(self.task_tab)

        self.task_status_label = QLabel("今日任务：0/0")
        layout.addWidget(self.task_status_label)

        self.active_task_label = QLabel("当前任务：无")
        self.active_task_label.setWordWrap(True)
        layout.addWidget(self.active_task_label)

        self.task_list = QListWidget()
        self.task_list.itemClicked.connect(self._on_task_selected)
        layout.addWidget(self.task_list)

        self.task_info = QLabel("请选择任务")
        self.task_info.setWordWrap(True)
        layout.addWidget(self.task_info)

        btn_layout = QHBoxLayout()
        self.accept_task_btn = QPushButton("接取任务")
        self.accept_task_btn.clicked.connect(self._on_accept_task)
        self.accept_task_btn.setEnabled(False)
        btn_layout.addWidget(self.accept_task_btn)

        self.complete_task_btn = QPushButton("完成任务")
        self.complete_task_btn.clicked.connect(self._on_complete_task)
        self.complete_task_btn.setEnabled(False)
        btn_layout.addWidget(self.complete_task_btn)

        layout.addLayout(btn_layout)

    # ==================== 商店页 ====================

    def _setup_shop_tab(self):
        layout = QVBoxLayout(self.shop_tab)

        self.shop_list = QListWidget()
        self.shop_list.itemClicked.connect(self._on_shop_item_selected)
        layout.addWidget(self.shop_list)

        self.shop_info = QLabel("请选择商品")
        self.shop_info.setWordWrap(True)
        layout.addWidget(self.shop_info)

        self.buy_btn = QPushButton("兑换")
        self.buy_btn.clicked.connect(self._on_buy)
        self.buy_btn.setEnabled(False)
        layout.addWidget(self.buy_btn)

    # ==================== 藏经阁页 ====================

    def _setup_scripture_tab(self):
        layout = QVBoxLayout(self.scripture_tab)

        self.scripture_list = QListWidget()
        self.scripture_list.itemClicked.connect(self._on_scripture_selected)
        layout.addWidget(self.scripture_list)

        self.scripture_info = QLabel("请选择功法")
        self.scripture_info.setWordWrap(True)
        layout.addWidget(self.scripture_info)

        self.learn_btn = QPushButton("学习功法")
        self.learn_btn.clicked.connect(self._on_learn_skill)
        self.learn_btn.setEnabled(False)
        layout.addWidget(self.learn_btn)

    # ==================== 捐献页 ====================

    def _setup_donate_tab(self):
        layout = QVBoxLayout(self.donate_tab)

        layout.addWidget(QLabel("选择要捐献的物品："))
        self.donate_combo = QComboBox()
        self.donate_combo.currentIndexChanged.connect(self._on_donate_changed)
        layout.addWidget(self.donate_combo)

        layout.addWidget(QLabel("数量："))
        self.donate_spin = QSpinBox()
        self.donate_spin.setMinimum(1)
        self.donate_spin.setValue(1)
        layout.addWidget(self.donate_spin)

        self.donate_info = QLabel("请选择物品")
        self.donate_info.setWordWrap(True)
        layout.addWidget(self.donate_info)

        self.donate_btn = QPushButton("捐献")
        self.donate_btn.clicked.connect(self._on_donate)
        layout.addWidget(self.donate_btn)

        layout.addStretch()

    # ==================== 刷新逻辑 ====================

    def _refresh_all(self):
        """刷新弹窗所有显示内容。"""
        self._refresh_info()
        self._refresh_tournament_tab()
        self._refresh_facility_tab()
        self._refresh_task_tab()
        self._refresh_shop_tab()
        self._refresh_scripture_tab()
        self._refresh_donate_tab()
        self._refresh_warehouse_tab()
        self._refresh_bounty_tab()
        self._refresh_secret_realm_tab()
        self._refresh_ancestral_hall_tab()
        self._refresh_beast_garden_tab()
        self._refresh_follower_tab()
        self._refresh_cave_tab()
        self._refresh_diplomacy_tab()
        self._refresh_world_boss_tab()

    def _refresh_info(self):
        """刷新顶部信息栏与信息页。"""
        sect = self.engine.sect_manager.get_sect()
        if not sect:
            self.info_label.setText("当前未加入任何宗门，可在下方选择宗门拜入。")
            self.sect_desc_label.setText("")
            self.promote_btn.setVisible(False)
            self.leave_btn.setVisible(False)
            self.join_list.setVisible(True)
            self.join_btn.setVisible(True)
            self._refresh_join_list()
            return

        rank_name = sect.get_rank_name(self.player.sect_rank)
        info_text = (
            f"宗门：{sect.name}　职位：{rank_name}\n"
            f"贡献：{self.player.sect_contribution}　"
            f"忠诚度：{self.player.sect_loyalty}/100\n"
            f"今日任务：{self.player.sect_tasks_today}/"
            f"{self.engine.sect_manager.get_daily_limit()}"
        )
        # 显示当前宗门气运事件
        active_fortune = getattr(self.player, "active_sect_fortune", None)
        if active_fortune:
            info_text += f"\n宗门气运：【{active_fortune.get('name', '')}】"
        self.info_label.setText(info_text)
        self.sect_desc_label.setText(sect.description)
        self.promote_btn.setVisible(True)
        self.leave_btn.setVisible(True)
        self.join_list.setVisible(False)
        self.join_btn.setVisible(False)

    def _refresh_join_list(self):
        """刷新可加入宗门列表。"""
        self.join_list.clear()
        self.selected_join_sect = None
        self.join_btn.setEnabled(False)

        for sect in self.engine.sect_library.all_sects():
            item = QListWidgetItem(f"{sect.name} - {sect.description}")
            item.setData(256, sect.id)
            self.join_list.addItem(item)

    def _refresh_task_tab(self):
        """刷新任务页。"""
        sect = self.engine.sect_manager.get_sect()
        if not sect:
            self.task_status_label.setText("未加入宗门")
            self.active_task_label.setText("当前任务：无")
            self.task_list.clear()
            self.task_info.setText("请先加入宗门。")
            self.accept_task_btn.setEnabled(False)
            self.complete_task_btn.setEnabled(False)
            return

        self.task_status_label.setText(
            f"今日任务：{self.player.sect_tasks_today}/"
            f"{self.engine.sect_manager.get_daily_limit()}"
        )

        if self.player.sect_active_task:
            task = self.engine.sect_task_library.get(
                self.player.sect_active_task["task_id"]
            )
            progress = self.player.sect_active_task["progress"]
            self.active_task_label.setText(
                f"当前任务：【{task.name}】（{progress}/{task.target_count}）"
            )
            self.complete_task_btn.setEnabled(progress >= task.target_count)
        else:
            self.active_task_label.setText("当前任务：无")
            self.complete_task_btn.setEnabled(False)

        self.task_list.clear()
        self.selected_task = None
        self.accept_task_btn.setEnabled(False)
        self.task_info.setText("请选择任务")

        for task in self.engine.sect_manager.get_available_tasks():
            display = f"{task.name}（{task.contribution_reward} 贡献）"
            item = QListWidgetItem(display)
            item.setData(256, task.id)
            self.task_list.addItem(item)

    def _refresh_shop_tab(self):
        """刷新贡献商店。"""
        self.shop_list.clear()
        self.selected_shop_item = None
        self.shop_info.setText("请选择商品")
        self.buy_btn.setEnabled(False)

        sect = self.engine.sect_manager.get_sect()
        if not sect:
            return

        for shop_item in sect.shop_items:
            item_id = shop_item["item_id"]
            cost = shop_item["cost"]
            item = self.item_library.get(item_id)
            if not item:
                continue
            display = f"{item.name} - {cost} 贡献"
            list_item = QListWidgetItem(display)
            list_item.setData(256, item_id)
            self.shop_list.addItem(list_item)

    def _refresh_scripture_tab(self):
        """刷新藏经阁。"""
        self.scripture_list.clear()
        self.selected_scripture = None
        self.scripture_info.setText("请选择功法")
        self.learn_btn.setEnabled(False)

        sect = self.engine.sect_manager.get_sect()
        if not sect:
            return

        for sc in sect.scripture_skills:
            skill = self.skill_library.get(sc["skill_id"])
            if not skill:
                continue
            rank_name = sect.get_rank_name(sc["required_rank"])
            display = f"{skill.name} - {sc['cost']} 贡献（需{rank_name}）"
            list_item = QListWidgetItem(display)
            list_item.setData(256, sc["skill_id"])
            self.scripture_list.addItem(list_item)

    def _refresh_donate_tab(self):
        """刷新捐献页。"""
        self.donate_combo.clear()
        self.donate_map = {}

        # 合并同名物品（统计堆叠 count）
        counts = {}
        for item in self.player.inventory:
            counts[item.id] = counts.get(item.id, 0) + item.count

        for item_id, count in counts.items():
            item = self.item_library.get(item_id)
            if not item:
                continue
            # 装备类不建议捐献，但允许
            display = f"{item.name}（拥有 {count}）"
            self.donate_combo.addItem(display, item_id)
            self.donate_map[item_id] = item

        self._on_donate_changed()

    # ==================== 事件处理 ====================

    def _on_join_item_selected(self, item):
        self.selected_join_sect = item.data(256)
        self.join_btn.setEnabled(True)

    def _on_join(self):
        if not self.selected_join_sect:
            return
        reply = QMessageBox.question(
            self, "确认拜入宗门",
            f"确定要拜入该宗门吗？",
        )
        if reply == QMessageBox.Yes:
            self.engine.sect_join(self.selected_join_sect)
            self._refresh_all()

    def _on_leave(self):
        reply = QMessageBox.warning(
            self, "确认退出宗门",
            "退出宗门将清空所有贡献，并可能被原宗门追杀，确定吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.engine.sect_leave()
            self._refresh_all()

    def _on_promote(self):
        ok, msg = self.engine.sect_manager.check_promotion()
        if not ok:
            QMessageBox.information(self, "无法晋升", msg)
            return
        reply = QMessageBox.question(
            self, "确认晋升",
            f"满足晋升条件，是否晋升为【{msg}】？",
        )
        if reply == QMessageBox.Yes:
            self.engine.sect_promote()
            self._refresh_all()

    def _on_task_selected(self, item):
        task_id = item.data(256)
        task = self.engine.sect_task_library.get(task_id)
        self.selected_task = task
        self.task_info.setText(
            f"{task.name}\n{task.description}\n"
            f"奖励：贡献 +{task.contribution_reward}，声望 +{task.reputation_reward}\n"
            f"目标：{self._task_target_text(task)}"
        )
        self.accept_task_btn.setEnabled(not self.player.sect_active_task)

    def _task_target_text(self, task):
        if task.type == "kill":
            enemy = self.engine.enemy_library.get(task.target_enemy)
            name = enemy["name"] if enemy else task.target_enemy
            return f"击杀 {name} x{task.target_count}"
        if task.type == "collect":
            item = self.item_library.get(task.target_item)
            name = item.name if item else task.target_item
            return f"上缴 {name} x{task.target_count}"
        if task.type == "explore":
            loc = self.engine.world.get_location(task.target_location)
            name = loc["name"] if loc else task.target_location
            return f"前往 {name} x{task.target_count}"
        return "未知目标"

    def _on_accept_task(self):
        if not self.selected_task:
            return
        self.engine.sect_accept_task(self.selected_task.id)
        self._refresh_all()

    def _on_complete_task(self):
        self.engine.sect_complete_active_task()
        self._refresh_all()

    def _on_shop_item_selected(self, item):
        item_id = item.data(256)
        self.selected_shop_item = item_id
        item_obj = self.item_library.get(item_id)
        sect = self.engine.sect_manager.get_sect()
        cost = 0
        for si in sect.shop_items:
            if si["item_id"] == item_id:
                cost = si["cost"]
                break
        self.shop_info.setText(f"{item_obj.name}\n{item_obj.description}\n需要 {cost} 贡献")
        self.buy_btn.setEnabled(self.player.sect_contribution >= cost)

    def _on_buy(self):
        if not self.selected_shop_item:
            return
        self.engine.sect_buy_item(self.selected_shop_item)
        self._refresh_all()

    def _on_scripture_selected(self, item):
        skill_id = item.data(256)
        self.selected_scripture = skill_id
        skill = self.skill_library.get(skill_id)
        sect = self.engine.sect_manager.get_sect()
        cost = 0
        required_rank = "outer"
        for sc in sect.scripture_skills:
            if sc["skill_id"] == skill_id:
                cost = sc["cost"]
                required_rank = sc["required_rank"]
                break
        rank_name = sect.get_rank_name(required_rank)
        learned = "（已习得）" if self.player.has_skill(skill_id) else ""
        self.scripture_info.setText(
            f"{skill.name}{learned}\n{skill.description}\n"
            f"需要职位：{rank_name}，消耗 {cost} 贡献"
        )
        self.learn_btn.setEnabled(
            self.player.sect_contribution >= cost
            and not self.player.has_skill(skill_id)
        )

    def _on_learn_skill(self):
        if not self.selected_scripture:
            return
        self.engine.sect_learn_skill(self.selected_scripture)
        self._refresh_all()

    def _on_donate_changed(self):
        item_id = self.donate_combo.currentData()
        if not item_id or item_id not in self.donate_map:
            self.donate_info.setText("请选择物品")
            self.donate_btn.setEnabled(False)
            return

        item = self.donate_map[item_id]
        have = self.player.count_item(item_id)
        contribution = int(item.value * 0.5)
        self.donate_spin.setMaximum(have)
        self.donate_info.setText(
            f"{item.name}：价值 {item.value}，每份捐献可获得 {contribution} 贡献\n"
            f"当前拥有：{have}"
        )
        self.donate_btn.setEnabled(True)

    def _on_donate(self):
        item_id = self.donate_combo.currentData()
        count = self.donate_spin.value()
        if not item_id:
            return
        self.engine.sect_donate_item(item_id, count)
        self._refresh_all()

    # ==================== 仓库与排行榜页 ====================

    def _setup_warehouse_tab(self):
        """设置宗门仓库页：显示仓库物品、累计捐献与本月排行榜。"""
        layout = QVBoxLayout(self.warehouse_tab)

        self.warehouse_summary_label = QLabel()
        self.warehouse_summary_label.setWordWrap(True)
        layout.addWidget(self.warehouse_summary_label)

        layout.addWidget(QLabel("仓库物品："))
        self.warehouse_list = QListWidget()
        layout.addWidget(self.warehouse_list)

        layout.addWidget(QLabel("本月捐献排行榜："))
        self.leaderboard_list = QListWidget()
        layout.addWidget(self.leaderboard_list)

        layout.addStretch()

    def _refresh_warehouse_tab(self):
        """刷新仓库与排行榜显示。"""
        sect = self.engine.sect_manager.get_sect()
        if not sect:
            self.warehouse_summary_label.setText("未加入宗门，无法查看宗门仓库。")
            self.warehouse_list.clear()
            self.leaderboard_list.clear()
            return

        # 汇总信息
        total_value = self.engine.sect_manager.get_warehouse_total_value()
        donation_total = getattr(self.player, "sect_donation_total", 0)
        rank = self.engine.sect_manager.get_player_donation_rank()
        rank_text = f"第 {rank} 名" if rank else "未上榜"
        self.warehouse_summary_label.setText(
            f"累计捐献价值：{donation_total}　仓库总价值：{total_value}\n"
            f"本月排名：{rank_text}"
        )

        # 仓库物品
        self.warehouse_list.clear()
        warehouse_items = self.engine.sect_manager.get_warehouse_items()
        if warehouse_items:
            for item, count in warehouse_items:
                list_item = QListWidgetItem(f"{item.name} ×{count}（价值 {item.value}）")
                self.warehouse_list.addItem(list_item)
        else:
            self.warehouse_list.addItem("仓库空空如也")

        # 排行榜
        self.leaderboard_list.clear()
        for entry in self.engine.sect_manager.get_donation_leaderboard():
            rank = entry["rank"]
            name = entry["name"]
            total = entry["total"]
            text = f"第 {rank} 名：{name}　累计 {total}"
            list_item = QListWidgetItem(text)
            # 玩家条目用绿色高亮显示
            if entry.get("is_player"):
                list_item.setForeground(Qt.green)
                list_item.setData(256, "player")
            self.leaderboard_list.addItem(list_item)

    # ==================== 悬赏榜页 ====================

    def _setup_bounty_tab(self):
        """设置宗门悬赏榜页：显示可接取悬赏与当前进度。"""
        layout = QVBoxLayout(self.bounty_tab)

        self.bounty_info_label = QLabel()
        self.bounty_info_label.setWordWrap(True)
        layout.addWidget(self.bounty_info_label)

        layout.addWidget(QLabel("可接取悬赏："))
        self.bounty_list = QListWidget()
        self.bounty_list.itemClicked.connect(self._on_bounty_selected)
        layout.addWidget(self.bounty_list)

        self.bounty_detail_label = QLabel("请选择悬赏")
        self.bounty_detail_label.setWordWrap(True)
        layout.addWidget(self.bounty_detail_label)

        self.accept_bounty_btn = QPushButton("接取悬赏")
        self.accept_bounty_btn.setToolTip("接取后击杀指定目标即可领取奖励")
        self.accept_bounty_btn.clicked.connect(self._on_accept_bounty)
        self.accept_bounty_btn.setEnabled(False)
        layout.addWidget(self.accept_bounty_btn)

        layout.addStretch()

    def _refresh_bounty_tab(self):
        """刷新悬赏榜显示。"""
        sect = self.engine.sect_manager.get_sect()
        if not sect:
            self.bounty_info_label.setText("未加入宗门，无法查看悬赏榜。")
            self.bounty_list.clear()
            self.bounty_detail_label.setText("请选择悬赏")
            self.accept_bounty_btn.setEnabled(False)
            return

        # 显示当前进行中的悬赏
        active = getattr(self.player, "sect_active_bounty", None)
        if active:
            bounty = self.engine.sect_manager._get_bounty(active["bounty_id"])
            name = bounty["name"] if bounty else "未知悬赏"
            self.bounty_info_label.setText(
                f"当前悬赏：【{name}】\n"
                f"进度：{active['progress']}/{active['target_count']}"
            )
        else:
            self.bounty_info_label.setText("当前无进行中的悬赏任务。")

        self.bounty_list.clear()
        self._bounty_map = {}
        self.selected_bounty = None
        self.bounty_detail_label.setText("请选择悬赏")
        self.accept_bounty_btn.setEnabled(False)

        # 若已有进行中的悬赏，则不可再接取
        if active:
            self.bounty_list.addItem("请先完成当前悬赏")
            return

        bounties = self.engine.sect_manager.get_bounty_board()
        if not bounties:
            self.bounty_list.addItem("当前职位暂无可用悬赏")
            return

        for bounty in bounties:
            item = QListWidgetItem(bounty["name"])
            item.setData(256, bounty["id"])
            self.bounty_list.addItem(item)
            self._bounty_map[bounty["id"]] = bounty

    def _on_bounty_selected(self, item):
        """选中悬赏时显示详情。"""
        bounty_id = item.data(256)
        bounty = self._bounty_map.get(bounty_id)
        if not bounty:
            self.bounty_detail_label.setText("请选择悬赏")
            self.accept_bounty_btn.setEnabled(False)
            return

        self.selected_bounty = bounty
        enemy_data = self.engine.enemy_library.get(bounty.get("target_enemy"))
        enemy_name = enemy_data["name"] if enemy_data else bounty["target_enemy"]
        item_text = self._format_bounty_rewards(bounty)

        self.bounty_detail_label.setText(
            f"【{bounty['name']}】\n"
            f"{bounty.get('description', '')}\n"
            f"目标：击败 {enemy_name} x{bounty.get('target_count', 1)}\n"
            f"奖励：贡献 +{bounty.get('contribution_reward', 0)}，声望 +{bounty.get('reputation_reward', 0)}\n"
            f"物品奖励：{item_text}"
        )

        ok, _ = self.engine.sect_manager.can_accept_bounty(bounty_id)
        self.accept_bounty_btn.setEnabled(ok)
        self.accept_bounty_btn.setProperty("bounty_id", bounty_id)

    def _format_bounty_rewards(self, bounty):
        """格式化悬赏物品奖励为中文文本。"""
        rewards = bounty.get("item_reward", {})
        if not rewards:
            return "无"
        parts = []
        for item_id, count in rewards.items():
            item = self.item_library.get(item_id)
            name = item.name if item else item_id
            parts.append(f"{name}×{count}")
        return "、".join(parts)

    def _on_accept_bounty(self):
        """接取选中的悬赏。"""
        bounty_id = self.accept_bounty_btn.property("bounty_id")
        if not bounty_id:
            return
        self.engine.sect_accept_bounty(bounty_id)
        self._refresh_all()

    # ==================== 秘境页 ====================

    def _setup_secret_realm_tab(self):
        """设置宗门秘境/禁地页：列出可探索秘境与状态。"""
        layout = QVBoxLayout(self.secret_realm_tab)

        self.secret_realm_info_label = QLabel()
        self.secret_realm_info_label.setWordWrap(True)
        layout.addWidget(self.secret_realm_info_label)

        self.secret_realm_list = QListWidget()
        self.secret_realm_list.itemClicked.connect(self._on_secret_realm_selected)
        layout.addWidget(self.secret_realm_list)

        self.secret_realm_detail_label = QLabel("请选择秘境")
        self.secret_realm_detail_label.setWordWrap(True)
        layout.addWidget(self.secret_realm_detail_label)

        self.enter_secret_realm_btn = QPushButton("进入秘境")
        self.enter_secret_realm_btn.setToolTip("满足条件后挑战秘境守卫")
        self.enter_secret_realm_btn.clicked.connect(self._on_enter_secret_realm)
        self.enter_secret_realm_btn.setEnabled(False)
        layout.addWidget(self.enter_secret_realm_btn)

        layout.addStretch()

    def _refresh_secret_realm_tab(self):
        """刷新秘境列表与状态。"""
        sect = self.engine.sect_manager.get_sect()
        if not sect:
            self.secret_realm_info_label.setText("未加入宗门，无法查看秘境。")
            self.secret_realm_list.clear()
            self.secret_realm_detail_label.setText("请选择秘境")
            self.enter_secret_realm_btn.setEnabled(False)
            return

        self.secret_realm_info_label.setText(
            "宗门禁地需要一定职位方可进入，通关后可获得稀有奖励，但有冷却时间。"
        )
        self.secret_realm_list.clear()
        self._secret_realm_map = {}

        realms = self.engine.sect_manager.get_secret_realms()
        if not realms:
            self.secret_realm_list.addItem("当前职位暂无可用秘境")
            self.secret_realm_detail_label.setText("提升职位后解锁更多禁地。")
            self.enter_secret_realm_btn.setEnabled(False)
            return

        for realm in realms:
            realm_id = realm["id"]
            remaining = self.engine.sect_manager.get_secret_realm_remaining_cooldown(realm_id)
            rank_name = sect.get_rank_name(realm.get("required_rank", "outer"))
            status = f"（冷却 {remaining} 个月）" if remaining > 0 else "（可进入）"
            item = QListWidgetItem(f"{realm['name']}　需{rank_name}{status}")
            item.setData(256, realm_id)
            self.secret_realm_list.addItem(item)
            self._secret_realm_map[realm_id] = realm

        self.secret_realm_detail_label.setText("请选择秘境")
        self.enter_secret_realm_btn.setEnabled(False)

    def _on_secret_realm_selected(self, item):
        """选中秘境时显示详情并启用进入按钮。"""
        realm_id = item.data(256)
        realm = self._secret_realm_map.get(realm_id)
        if not realm:
            self.secret_realm_detail_label.setText("请选择秘境")
            self.enter_secret_realm_btn.setEnabled(False)
            return

        can_enter, reason = self.engine.sect_manager.can_enter_secret_realm(realm_id)
        enemy_id = realm.get("enemy_id", "未知")
        enemy_data = self.engine.enemy_library.get(enemy_id)
        enemy_name = enemy_data["name"] if enemy_data else enemy_id

        detail = (
            f"【{realm['name']}】\n"
            f"{realm.get('description', '')}\n\n"
            f"守关敌人：{enemy_name}\n"
            f"奖励物品：{self._format_realm_rewards(realm)}\n"
            f"奖励修为：{realm.get('reward_qi', 0)}\n"
        )
        if can_enter:
            detail += "当前可进入。"
        else:
            detail += f"不可进入：{reason}"

        self.secret_realm_detail_label.setText(detail)
        self.enter_secret_realm_btn.setEnabled(can_enter)
        self.enter_secret_realm_btn.setProperty("realm_id", realm_id)

    def _format_realm_rewards(self, realm):
        """格式化秘境奖励物品为中文文本。"""
        rewards = realm.get("reward_items", {})
        if not rewards:
            return "无"
        parts = []
        for item_id, count in rewards.items():
            item = self.item_library.get(item_id)
            name = item.name if item else item_id
            parts.append(f"{name}×{count}")
        return "、".join(parts)

    def _on_enter_secret_realm(self):
        """点击进入秘境，触发战斗。"""
        realm_id = self.enter_secret_realm_btn.property("realm_id")
        if not realm_id:
            return
        self.engine.sect_enter_secret_realm(realm_id)
        # 战斗弹窗由主窗口的 __COMBAT_START__ 监听打开
        self._refresh_secret_realm_tab()

    # ==================== 追随者页 ====================

    def _setup_follower_tab(self):
        """设置追随者页：显示已有追随者、招募与派遣。"""
        layout = QVBoxLayout(self.follower_tab)

        self.follower_info_label = QLabel()
        self.follower_info_label.setWordWrap(True)
        layout.addWidget(self.follower_info_label)

        layout.addWidget(QLabel("当前追随者："))
        self.follower_list = QListWidget()
        self.follower_list.itemClicked.connect(self._on_follower_selected)
        layout.addWidget(self.follower_list)

        self.follower_detail_label = QLabel("请选择追随者")
        self.follower_detail_label.setWordWrap(True)
        layout.addWidget(self.follower_detail_label)

        self.dispatch_follower_btn = QPushButton("派遣任务")
        self.dispatch_follower_btn.setToolTip("派遣空闲追随者外出收集资源")
        self.dispatch_follower_btn.clicked.connect(self._on_dispatch_follower)
        self.dispatch_follower_btn.setEnabled(False)
        layout.addWidget(self.dispatch_follower_btn)

        layout.addWidget(QLabel("可招募追随者："))
        self.recruit_follower_list = QListWidget()
        self.recruit_follower_list.itemClicked.connect(self._on_recruit_follower_selected)
        layout.addWidget(self.recruit_follower_list)

        self.recruit_follower_btn = QPushButton("招募")
        self.recruit_follower_btn.setToolTip("消耗宗门贡献招募追随者")
        self.recruit_follower_btn.clicked.connect(self._on_recruit_follower)
        self.recruit_follower_btn.setEnabled(False)
        layout.addWidget(self.recruit_follower_btn)

        layout.addStretch()

    def _refresh_follower_tab(self):
        """刷新追随者页。"""
        sect = self.engine.sect_manager.get_sect()
        capacity = self.engine.sect_manager.get_follower_capacity()
        current_count = len(self.player.followers)
        if not sect:
            self.follower_info_label.setText("未加入宗门，无法招募追随者。")
            self.follower_list.clear()
            self.recruit_follower_list.clear()
            self.follower_detail_label.setText("请选择追随者")
            self.dispatch_follower_btn.setEnabled(False)
            self.recruit_follower_btn.setEnabled(False)
            return

        self.follower_info_label.setText(
            f"追随者上限：{current_count}/{capacity}（随职位提升而增加）\n"
            f"空闲追随者提供被动修炼加成，派遣后可于数月后带回资源。"
        )

        # 当前追随者
        self.follower_list.clear()
        self._follower_map = {}
        if self.player.followers:
            for follower in self.player.followers:
                fid = follower["id"]
                status = "任务中" if follower.get("status") == "mission" else "空闲"
                remaining = 0
                if follower.get("status") == "mission":
                    remaining = self.engine.sect_manager.get_follower_remaining_months(follower)
                text = f"{follower['name']}　忠诚度 {follower.get('loyalty', 60)}　{status}"
                if remaining > 0:
                    text += f"（剩余 {remaining} 个月）"
                item = QListWidgetItem(text)
                item.setData(256, fid)
                self.follower_list.addItem(item)
                self._follower_map[fid] = follower
        else:
            self.follower_list.addItem("暂无追随者")

        self.follower_detail_label.setText("请选择追随者")
        self.dispatch_follower_btn.setEnabled(False)

        # 可招募列表
        self.recruit_follower_list.clear()
        self._recruit_follower_map = {}
        recruitable = self.engine.sect_manager.get_recruitable_followers()
        already_ids = {f["id"] for f in self.player.followers}
        available = [t for t in recruitable if t["id"] not in already_ids]
        if available:
            for template in available:
                fid = template["id"]
                cost = template.get("cost_contribution", 0)
                item = QListWidgetItem(f"{template['name']}　消耗 {cost} 贡献")
                item.setData(256, fid)
                self.recruit_follower_list.addItem(item)
                self._recruit_follower_map[fid] = template
        else:
            self.recruit_follower_list.addItem("当前无可用招募对象")

        self.recruit_follower_btn.setEnabled(False)

    def _on_follower_selected(self, item):
        """选中已有追随者时显示详情。"""
        fid = item.data(256)
        follower = self._follower_map.get(fid)
        if not follower:
            self.follower_detail_label.setText("请选择追随者")
            self.dispatch_follower_btn.setEnabled(False)
            return

        bonus = follower.get("passive_bonus", {})
        bonus_text = ""
        if bonus.get("cultivation_speed"):
            bonus_text += f"修炼速度 +{int(bonus['cultivation_speed'] * 100)}%"

        status = "任务中" if follower.get("status") == "mission" else "空闲"
        mission = follower.get("mission", {})
        detail = (
            f"【{follower['name']}】\n"
            f"{follower.get('description', '')}\n"
            f"属性：{follower.get('element', '无')}　流派：{follower.get('path', '无')}\n"
            f"忠诚度：{follower.get('loyalty', 60)}　状态：{status}\n"
            f"被动加成：{bonus_text or '无'}\n"
        )
        if mission:
            detail += f"任务时长：{mission.get('duration_months', 0)} 个月"

        self.follower_detail_label.setText(detail)

        can_dispatch, _ = self.engine.sect_manager.can_dispatch_follower(fid)
        self.dispatch_follower_btn.setEnabled(can_dispatch)
        self.dispatch_follower_btn.setProperty("follower_id", fid)

    def _on_dispatch_follower(self):
        """派遣选中的追随者。"""
        fid = self.dispatch_follower_btn.property("follower_id")
        if not fid:
            return
        self.engine.sect_dispatch_follower(fid)
        self._refresh_follower_tab()

    def _on_recruit_follower_selected(self, item):
        """选中可招募追随者时启用招募按钮。"""
        fid = item.data(256)
        template = self._recruit_follower_map.get(fid)
        if not template:
            self.recruit_follower_btn.setEnabled(False)
            return
        self.recruit_follower_btn.setEnabled(True)
        self.recruit_follower_btn.setProperty("follower_id", fid)

    def _on_recruit_follower(self):
        """招募选中的追随者。"""
        fid = self.recruit_follower_btn.property("follower_id")
        if not fid:
            return
        self.engine.sect_recruit_follower(fid)
        self._refresh_follower_tab()

    # ==================== 洞府页 ====================

    def _setup_cave_tab(self):
        """设置真传洞府页：显示加成、升级、闭关。"""
        layout = QVBoxLayout(self.cave_tab)

        self.cave_info_label = QLabel()
        self.cave_info_label.setWordWrap(True)
        layout.addWidget(self.cave_info_label)

        self.cave_vein_label = QLabel()
        self.cave_vein_label.setWordWrap(True)
        layout.addWidget(self.cave_vein_label)

        btn_layout = QHBoxLayout()
        self.upgrade_cave_btn = QPushButton("升级洞府")
        self.upgrade_cave_btn.setToolTip("消耗贡献提升洞府灵气浓度")
        self.upgrade_cave_btn.clicked.connect(self._on_upgrade_cave)
        btn_layout.addWidget(self.upgrade_cave_btn)

        self.seclusion_btn = QPushButton("洞府闭关（1年）")
        self.seclusion_btn.setToolTip("在洞府中闭关一年，获得额外修为")
        self.seclusion_btn.clicked.connect(self._on_cave_seclusion)
        btn_layout.addWidget(self.seclusion_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def _refresh_cave_tab(self):
        """刷新洞府页显示。"""
        sect = self.engine.sect_manager.get_sect()
        if not sect:
            self.cave_info_label.setText("未加入宗门，无法使用洞府。")
            self.cave_vein_label.setText("")
            self.upgrade_cave_btn.setEnabled(False)
            self.seclusion_btn.setEnabled(False)
            return

        rank_idx = self.engine.sect_manager.get_rank_index(self.player.sect_rank)
        cave_bonus = self.engine.sect_manager.get_cave_bonus()
        speed = cave_bonus.get("cultivation_speed", 0.0)
        max_qi = cave_bonus.get("max_qi_bonus", 0)
        upgrade_level = getattr(self.player, "cave_upgrade_level", 0)
        upgrade_cost = self.engine.sect_manager.get_cave_upgrade_cost()

        self.cave_info_label.setText(
            f"当前职位：{sect.get_rank_name(self.player.sect_rank)}\n"
            f"洞府等级：{upgrade_level}\n"
            f"修炼加成：+{int(speed * 100)}%\n"
            f"真气上限加成：+{max_qi}\n"
            f"下次升级消耗：{upgrade_cost} 贡献"
        )

        # 显示本宗门控制的灵脉
        veins = self.engine.sect_manager.get_controllable_veins(sect.id)
        if veins:
            texts = [f"• {v.get('name', '未知灵脉')}（+{int(v.get('bonus', 0) * 100)}%）" for v in veins]
            self.cave_vein_label.setText("宗门控制灵脉：\n" + "\n".join(texts))
        else:
            self.cave_vein_label.setText("宗门暂无控制灵脉，可通过宗门战夺取。")

        self.upgrade_cave_btn.setEnabled(rank_idx >= self.engine.sect_manager.get_rank_index("inner"))
        self.seclusion_btn.setEnabled(rank_idx >= self.engine.sect_manager.get_rank_index("core"))

    def _on_upgrade_cave(self):
        self.engine.sect_upgrade_cave()
        self._refresh_all()

    def _on_cave_seclusion(self):
        reply = QMessageBox.question(
            self, "确认闭关",
            "确定要在真传洞府闭关一年吗？",
        )
        if reply == QMessageBox.Yes:
            self.engine.sect_cave_seclusion(12)
            self._refresh_all()

    # ==================== 外交与宗门战页 ====================

    def _setup_diplomacy_tab(self):
        """设置外交页：显示关系、通缉状态、宗门战。"""
        layout = QVBoxLayout(self.diplomacy_tab)

        self.diplomacy_info = QLabel()
        self.diplomacy_info.setWordWrap(True)
        layout.addWidget(self.diplomacy_info)

        self.wanted_label = QLabel()
        self.wanted_label.setWordWrap(True)
        self.wanted_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        layout.addWidget(self.wanted_label)

        layout.addWidget(QLabel("选择目标宗门发动宗门战："))
        self.war_list = QListWidget()
        self.war_list.itemClicked.connect(self._on_war_target_selected)
        layout.addWidget(self.war_list)

        self.war_info = QLabel("请选择目标宗门")
        self.war_info.setWordWrap(True)
        layout.addWidget(self.war_info)

        self.war_btn = QPushButton("发动宗门战")
        self.war_btn.setToolTip("对敌对/中立宗门发动战争，胜利可夺取灵脉")
        self.war_btn.clicked.connect(self._on_start_war)
        self.war_btn.setEnabled(False)
        layout.addWidget(self.war_btn)

        # 同盟区域
        layout.addWidget(QLabel("当前同盟："))
        self.alliance_list = QListWidget()
        self.alliance_list.itemClicked.connect(self._on_alliance_selected)
        layout.addWidget(self.alliance_list)

        self.alliance_info = QLabel("请选择同盟")
        self.alliance_info.setWordWrap(True)
        layout.addWidget(self.alliance_info)

        self.break_alliance_btn = QPushButton("解除同盟")
        self.break_alliance_btn.setToolTip("撕毁同盟条约，关系降至中立")
        self.break_alliance_btn.clicked.connect(self._on_break_alliance)
        self.break_alliance_btn.setEnabled(False)
        layout.addWidget(self.break_alliance_btn)

        layout.addWidget(QLabel("可结盟宗门（需关系友好）："))
        self.form_alliance_list = QListWidget()
        self.form_alliance_list.itemClicked.connect(self._on_form_alliance_selected)
        layout.addWidget(self.form_alliance_list)

        self.form_alliance_btn = QPushButton("签订同盟")
        self.form_alliance_btn.setToolTip("消耗贡献与友好宗门缔结攻守同盟")
        self.form_alliance_btn.clicked.connect(self._on_form_alliance)
        self.form_alliance_btn.setEnabled(False)
        layout.addWidget(self.form_alliance_btn)

        # 外交任务区域
        layout.addWidget(QLabel("外交任务："))
        self.diplomatic_mission_active_label = QLabel("当前无进行中的外交任务")
        self.diplomatic_mission_active_label.setWordWrap(True)
        layout.addWidget(self.diplomatic_mission_active_label)

        self.cancel_diplomatic_mission_btn = QPushButton("取消任务")
        self.cancel_diplomatic_mission_btn.clicked.connect(self._on_cancel_diplomatic_mission)
        layout.addWidget(self.cancel_diplomatic_mission_btn)

        self.diplomatic_mission_list = QListWidget()
        self.diplomatic_mission_list.itemClicked.connect(self._on_diplomatic_mission_selected)
        layout.addWidget(self.diplomatic_mission_list)

        self.diplomatic_mission_target_combo = QComboBox()
        # 目标宗门切换时刷新接取按钮状态
        self.diplomatic_mission_target_combo.currentIndexChanged.connect(
            self._on_diplomatic_mission_target_changed
        )
        layout.addWidget(self.diplomatic_mission_target_combo)

        self.diplomatic_mission_info = QLabel("请选择外交任务与目标宗门")
        self.diplomatic_mission_info.setWordWrap(True)
        layout.addWidget(self.diplomatic_mission_info)

        self.accept_diplomatic_mission_btn = QPushButton("接取任务")
        self.accept_diplomatic_mission_btn.clicked.connect(self._on_accept_diplomatic_mission)
        self.accept_diplomatic_mission_btn.setEnabled(False)
        layout.addWidget(self.accept_diplomatic_mission_btn)

        layout.addStretch()

    def _refresh_diplomacy_tab(self):
        """刷新外交页显示。"""
        sect = self.engine.sect_manager.get_sect()
        if not sect:
            self.diplomacy_info.setText("未加入宗门。")
            self.wanted_label.setText("")
            self.war_list.clear()
            self.war_info.setText("请先加入宗门。")
            self.war_btn.setEnabled(False)
            return

        # 友好与敌对关系
        friendly = self.engine.sect_manager.get_friendly_sects()
        hostile = self.engine.sect_manager.get_hostile_sects()
        friendly_names = [self.engine.sect_library.get(sid).name for sid in friendly]
        hostile_names = [self.engine.sect_library.get(sid).name for sid in hostile]

        info_text = f"本宗：{sect.name}\n"
        info_text += f"友好宗门：{', '.join(friendly_names) if friendly_names else '无'}\n"
        info_text += f"敌对宗门：{', '.join(hostile_names) if hostile_names else '无'}"
        self.diplomacy_info.setText(info_text)

        # 通缉状态
        wanted = self.engine.sect_manager.get_wanted_sects()
        if wanted:
            names = [self.engine.sect_library.get(sid).name for sid in wanted]
            self.wanted_label.setText(f"你被以下宗门通缉：{', '.join(names)}\n进入其领地可能遭遇追杀！")
        else:
            self.wanted_label.setText("暂无宗门通缉你。")

        rank_idx = self.engine.sect_manager.get_rank_index(self.player.sect_rank)

        # 同盟列表
        self.alliance_list.clear()
        self.selected_alliance = None
        self.break_alliance_btn.setEnabled(False)
        self.alliance_info.setText("请选择同盟")
        for alliance in self.engine.sect_manager.get_alliance_list():
            target = self.engine.sect_library.get(alliance["sect_id"])
            item = QListWidgetItem(target.name if target else alliance["sect_id"])
            item.setData(256, alliance["sect_id"])
            self.alliance_list.addItem(item)

        # 可结盟宗门
        self.form_alliance_list.clear()
        self.selected_form_alliance = None
        self.form_alliance_btn.setEnabled(False)
        if rank_idx >= self.engine.sect_manager.get_rank_index("inner"):
            for other in self.engine.sect_library.all_sects():
                if other.id == sect.id:
                    continue
                if self.engine.sect_manager.is_allied(other.id):
                    continue
                if self.engine.sect_manager.get_relation_status(other.id) != "friendly":
                    continue
                item = QListWidgetItem(other.name)
                item.setData(256, other.id)
                self.form_alliance_list.addItem(item)

        # 可开战目标
        self.war_list.clear()
        self.selected_war_target = None
        self.war_btn.setEnabled(False)
        self.war_info.setText("请选择目标宗门")

        if rank_idx < self.engine.sect_manager.get_rank_index("inner"):
            self.war_info.setText("只有内门弟子及以上才能发动宗门战。")
            return

        for other in self.engine.sect_library.all_sects():
            if other.id == sect.id:
                continue
            status = self.engine.sect_manager.get_relation_status(other.id)
            if status == "friendly":
                continue
            display = f"{other.name}（关系：{'敌对' if status == 'hostile' else '中立'}）"
            item = QListWidgetItem(display)
            item.setData(256, other.id)
            self.war_list.addItem(item)

        # 刷新外交任务列表
        self._refresh_diplomatic_missions(sect, rank_idx)

    def _refresh_diplomatic_missions(self, sect, rank_idx):
        """刷新外交任务：当前任务、可接任务与目标宗门下拉框。"""
        # 当前进行中的任务
        active = getattr(self.player, "sect_diplomatic_mission", None)
        if active:
            mission = self.engine.sect_manager.diplomatic_mission_library.get(
                active.get("mission_id")
            )
            target = self.engine.sect_library.get(active.get("target_sect_id"))
            mission_name = mission["name"] if mission else "未知任务"
            target_name = target.name if target else "未知宗门"
            self.diplomatic_mission_active_label.setText(
                f"当前任务：【{mission_name}】\n目标宗门：{target_name}"
            )
            self.cancel_diplomatic_mission_btn.setEnabled(True)
            self.diplomatic_mission_list.setEnabled(False)
            self.diplomatic_mission_target_combo.setEnabled(False)
            self.accept_diplomatic_mission_btn.setEnabled(False)
            self.diplomatic_mission_info.setText("进行中任务可取消后重新接取。")
            self.diplomatic_mission_list.clear()
            self.diplomatic_mission_target_combo.clear()
            self.selected_diplomatic_mission = None
            return

        self.diplomatic_mission_active_label.setText("当前无进行中的外交任务")
        self.cancel_diplomatic_mission_btn.setEnabled(False)
        self.diplomatic_mission_list.setEnabled(True)
        self.diplomatic_mission_target_combo.setEnabled(True)

        # 可接任务
        self.diplomatic_mission_list.clear()
        self._diplomatic_mission_map = {}
        self.selected_diplomatic_mission = None
        self.diplomatic_mission_target_combo.clear()
        self.diplomatic_mission_info.setText("请选择外交任务与目标宗门")
        self.accept_diplomatic_mission_btn.setEnabled(False)

        missions = self.engine.sect_manager.get_available_diplomatic_missions()
        if not missions:
            self.diplomatic_mission_list.addItem("当前无可接外交任务")
            return

        for mission in missions:
            item = QListWidgetItem(
                f"{mission['name']}（{mission.get('duration_months', 6)}个月 / "
                f"{mission.get('cost_contribution', 0)}贡献）"
            )
            item.setData(256, mission["id"])
            self.diplomatic_mission_list.addItem(item)
            self._diplomatic_mission_map[mission["id"]] = mission

    def _on_diplomatic_mission_selected(self, item):
        """选中外交任务时，填充可选目标宗门。"""
        mission_id = item.data(256)
        mission = self._diplomatic_mission_map.get(mission_id)
        if not mission:
            return

        self.selected_diplomatic_mission = mission
        target_relation = mission.get("target_relation", "neutral")

        # 填充符合任务关系要求的目标宗门
        self.diplomatic_mission_target_combo.clear()
        self.diplomatic_mission_target_combo.setProperty("mission_id", mission_id)

        sect = self.engine.sect_manager.get_sect()
        has_target = False
        for other in self.engine.sect_library.all_sects():
            if other.id == sect.id:
                continue
            if self.engine.sect_manager.get_relation_status(other.id) != target_relation:
                continue
            self.diplomatic_mission_target_combo.addItem(other.name, other.id)
            has_target = True

        if not has_target:
            self.diplomatic_mission_target_combo.addItem("无符合条件宗门", None)

        self.diplomatic_mission_info.setText(
            f"【{mission['name']}】\n{mission.get('description', '')}\n"
            f"消耗贡献：{mission.get('cost_contribution', 0)}　"
            f"成功率：{int(mission.get('success_rate', 0) * 100)}%\n"
            f"关系变化：{mission.get('relation_delta', 0)}"
        )
        self._update_diplomatic_mission_accept_button()

    def _on_diplomatic_mission_target_changed(self):
        """目标宗门切换时刷新接取按钮。"""
        self._update_diplomatic_mission_accept_button()

    def _update_diplomatic_mission_accept_button(self):
        """根据当前选中的外交任务与目标宗门启用/禁用接取按钮。"""
        mission = getattr(self, "selected_diplomatic_mission", None)
        target_sect_id = self.diplomatic_mission_target_combo.currentData()
        if not mission or not target_sect_id:
            self.accept_diplomatic_mission_btn.setEnabled(False)
            return

        ok, _ = self.engine.sect_manager.can_accept_diplomatic_mission(
            mission["id"], target_sect_id
        )
        self.accept_diplomatic_mission_btn.setEnabled(ok)

    def _on_accept_diplomatic_mission(self):
        """接取选中的外交任务。"""
        mission = getattr(self, "selected_diplomatic_mission", None)
        target_sect_id = self.diplomatic_mission_target_combo.currentData()
        if not mission or not target_sect_id:
            return
        self.engine.sect_accept_diplomatic_mission(mission["id"], target_sect_id)
        self._refresh_all()

    def _on_cancel_diplomatic_mission(self):
        """取消当前进行中的外交任务。"""
        self.engine.sect_cancel_diplomatic_mission()
        self._refresh_all()

    def _on_war_target_selected(self, item):
        self.selected_war_target = item.data(256)
        target = self.engine.sect_library.get(self.selected_war_target)
        ok, msg = self.engine.sect_manager.can_start_war(self.selected_war_target)
        self.war_info.setText(f"目标：{target.name}\n{msg if not ok else '可发动宗门战，将消耗一定健康并尝试夺取灵脉。'}")
        self.war_btn.setEnabled(ok)

    def _on_start_war(self):
        if not self.selected_war_target:
            return
        target = self.engine.sect_library.get(self.selected_war_target)
        reply = QMessageBox.warning(
            self, "确认发动宗门战",
            f"确定要对【{target.name}】发动宗门战吗？\n战争有风险，失败会损失忠诚度与健康。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.engine.sect_start_war(self.selected_war_target)
            self._refresh_all()

    # ==================== 祖师堂页 ====================

    def _setup_ancestral_hall_tab(self):
        """设置祖师堂页：显示可参悟的传承列表。"""
        layout = QVBoxLayout(self.ancestral_hall_tab)

        self.ancestral_hall_info = QLabel()
        self.ancestral_hall_info.setWordWrap(True)
        layout.addWidget(self.ancestral_hall_info)

        self.inheritance_list = QListWidget()
        self.inheritance_list.itemClicked.connect(self._on_inheritance_selected)
        layout.addWidget(self.inheritance_list)

        self.inheritance_detail = QLabel("请选择传承")
        self.inheritance_detail.setWordWrap(True)
        layout.addWidget(self.inheritance_detail)

        self.learn_inheritance_btn = QPushButton("参悟传承")
        self.learn_inheritance_btn.clicked.connect(self._on_learn_inheritance)
        self.learn_inheritance_btn.setEnabled(False)
        layout.addWidget(self.learn_inheritance_btn)

        layout.addStretch()

    def _refresh_ancestral_hall_tab(self):
        """刷新祖师堂页显示。"""
        sect = self.engine.sect_manager.get_sect()
        if not sect:
            self.ancestral_hall_info.setText("未加入宗门。")
            self.inheritance_list.clear()
            self.inheritance_detail.setText("请先加入宗门")
            self.learn_inheritance_btn.setEnabled(False)
            return

        self.ancestral_hall_info.setText(
            f"本宗：{sect.name}\n"
            f"本月已参悟：{self.player.ancestral_hall_monthly_count} 次\n"
            f"已习得传承：{len(self.player.learned_inheritances)} 个"
        )
        self.inheritance_list.clear()
        self.selected_inheritance = None
        self.learn_inheritance_btn.setEnabled(False)
        self.inheritance_detail.setText("请选择传承")

        for inh in self.engine.sect_manager.get_inheritance_list():
            item = QListWidgetItem(f"{inh['name']} - {inh.get('cost_contribution', 0)} 贡献")
            item.setData(256, inh["id"])
            self.inheritance_list.addItem(item)

    def _on_inheritance_selected(self, item):
        self.selected_inheritance = item.data(256)
        inh = self.engine.sect_manager._get_inheritance(self.selected_inheritance)
        if not inh:
            return
        ok, msg = self.engine.sect_manager.can_learn_inheritance(self.selected_inheritance)
        detail = (
            f"【{inh['name']}】\n"
            f"需求职位：{self.engine.sect_manager.get_sect().get_rank_name(inh.get('required_rank', 'inner'))}\n"
            f"消耗：{inh.get('cost_contribution', 0)} 贡献、{inh.get('cost_loyalty', 0)} 忠诚度\n"
            f"每月限 {inh.get('max_monthly', 1)} 次\n"
            f"描述：{inh.get('description', '')}\n"
        )
        if not ok:
            detail += f"状态：{msg}"
        else:
            detail += "状态：满足参悟条件"
        self.inheritance_detail.setText(detail)
        self.learn_inheritance_btn.setEnabled(ok)

    def _on_learn_inheritance(self):
        if not self.selected_inheritance:
            return
        self.engine.sect_learn_inheritance(self.selected_inheritance)
        self._refresh_all()
    # ==================== 灵兽园页 ====================

    def _setup_beast_garden_tab(self):
        """设置灵兽园页：显示可领养灵兽与已拥有灵兽。"""
        layout = QVBoxLayout(self.beast_garden_tab)

        self.beast_garden_info = QLabel()
        self.beast_garden_info.setWordWrap(True)
        layout.addWidget(self.beast_garden_info)

        self.available_beast_list = QListWidget()
        self.available_beast_list.itemClicked.connect(self._on_available_beast_selected)
        layout.addWidget(self.available_beast_list)

        self.beast_detail = QLabel("请选择灵兽")
        self.beast_detail.setWordWrap(True)
        layout.addWidget(self.beast_detail)

        self.adopt_beast_btn = QPushButton("领养灵兽")
        self.adopt_beast_btn.clicked.connect(self._on_adopt_beast)
        self.adopt_beast_btn.setEnabled(False)
        layout.addWidget(self.adopt_beast_btn)

        self.owned_beast_label = QLabel("已拥有灵兽：")
        self.owned_beast_label.setWordWrap(True)
        layout.addWidget(self.owned_beast_label)

        self.owned_beast_list = QListWidget()
        self.owned_beast_list.itemClicked.connect(self._on_owned_beast_selected)
        layout.addWidget(self.owned_beast_list)

        self.release_beast_btn = QPushButton("放生灵兽")
        self.release_beast_btn.clicked.connect(self._on_release_beast)
        self.release_beast_btn.setEnabled(False)
        layout.addWidget(self.release_beast_btn)

        layout.addStretch()

    def _refresh_beast_garden_tab(self):
        """刷新灵兽园页显示。"""
        sect = self.engine.sect_manager.get_sect()
        if not sect:
            self.beast_garden_info.setText("未加入宗门。")
            self.available_beast_list.clear()
            self.owned_beast_list.clear()
            self.beast_detail.setText("请先加入宗门")
            self.adopt_beast_btn.setEnabled(False)
            self.release_beast_btn.setEnabled(False)
            return

        max_beasts = self.engine.sect_manager._get_max_beasts()
        owned = self.engine.sect_manager.get_player_beasts()
        self.beast_garden_info.setText(
            f"本宗：{sect.name}\n"
            f"灵兽栏：{len(owned)} / {max_beasts}"
        )

        self.available_beast_list.clear()
        self.selected_available_beast = None
        self.adopt_beast_btn.setEnabled(False)
        self.beast_detail.setText("请选择灵兽")

        for beast in self.engine.sect_manager.get_available_beasts():
            item = QListWidgetItem(f"{beast['name']} - {beast.get('cost_contribution', 0)} 贡献")
            item.setData(256, beast["id"])
            self.available_beast_list.addItem(item)

        self.owned_beast_list.clear()
        self.selected_owned_beast = None
        self.release_beast_btn.setEnabled(False)
        for beast in owned:
            item = QListWidgetItem(f"{beast['name']}（{beast['type']}）")
            item.setData(256, beast["beast_id"])
            self.owned_beast_list.addItem(item)

    def _on_available_beast_selected(self, item):
        self.selected_available_beast = item.data(256)
        beast = self.engine.sect_manager._get_beast_config(self.selected_available_beast)
        if not beast:
            return
        ok, msg = self.engine.sect_manager.can_adopt_beast(self.selected_available_beast)
        type_names = {"combat": "战斗", "mount": "坐骑", "resource": "资源"}
        detail = (
            f"【{beast['name']}】\n"
            f"类型：{type_names.get(beast.get('type', 'combat'), '战斗')}\n"
            f"需求职位：{self.engine.sect_manager.get_sect().get_rank_name(beast.get('required_rank', 'inner'))}\n"
            f"消耗：{beast.get('cost_contribution', 0)} 贡献\n"
            f"描述：{beast.get('description', '')}\n"
        )
        if not ok:
            detail += f"状态：{msg}"
        else:
            detail += "状态：可领养"
        self.beast_detail.setText(detail)
        self.adopt_beast_btn.setEnabled(ok)

    def _on_owned_beast_selected(self, item):
        self.selected_owned_beast = item.data(256)
        self.release_beast_btn.setEnabled(True)

    def _on_adopt_beast(self):
        if not self.selected_available_beast:
            return
        self.engine.sect_adopt_beast(self.selected_available_beast)
        self._refresh_all()

    def _on_release_beast(self):
        if not self.selected_owned_beast:
            return
        self.engine.sect_release_beast(self.selected_owned_beast)
        self._refresh_all()

    def _on_alliance_selected(self, item):
        self.selected_alliance = item.data(256)
        target = self.engine.sect_library.get(self.selected_alliance)
        self.alliance_info.setText(f"当前同盟：{target.name if target else self.selected_alliance}\n点击解除同盟将降低双方关系。")
        self.break_alliance_btn.setEnabled(True)

    def _on_break_alliance(self):
        if not self.selected_alliance:
            return
        self.engine.sect_break_alliance(self.selected_alliance)
        self._refresh_all()

    def _on_form_alliance_selected(self, item):
        self.selected_form_alliance = item.data(256)
        ok, msg = self.engine.sect_manager.can_form_alliance(self.selected_form_alliance)
        target = self.engine.sect_library.get(self.selected_form_alliance)
        info = f"目标：{target.name if target else self.selected_form_alliance}\n"
        info += msg if not ok else "满足结盟条件，签订后双方互为攻守同盟。"
        self.alliance_info.setText(info)
        self.form_alliance_btn.setEnabled(ok)

    def _on_form_alliance(self):
        if not self.selected_form_alliance:
            return
        self.engine.sect_form_alliance(self.selected_form_alliance)
        self._refresh_all()

    # ==================== 世界 BOSS 页 ====================

    def _setup_world_boss_tab(self):
        """设置世界 BOSS 页：显示当前可挑战的 BOSS 与挑战按钮。"""
        layout = QVBoxLayout(self.world_boss_tab)

        self.world_boss_info = QLabel()
        self.world_boss_info.setWordWrap(True)
        layout.addWidget(self.world_boss_info)

        self.world_boss_list = QListWidget()
        self.world_boss_list.itemClicked.connect(self._on_world_boss_selected)
        layout.addWidget(self.world_boss_list)

        self.world_boss_detail = QLabel("请选择世界 BOSS")
        self.world_boss_detail.setWordWrap(True)
        layout.addWidget(self.world_boss_detail)

        self.challenge_world_boss_btn = QPushButton("挑战 BOSS")
        self.challenge_world_boss_btn.setToolTip("挑战成功后获得稀有掉落与参与奖励")
        self.challenge_world_boss_btn.clicked.connect(self._on_challenge_world_boss)
        self.challenge_world_boss_btn.setEnabled(False)
        layout.addWidget(self.challenge_world_boss_btn)

        layout.addStretch()

    def _refresh_world_boss_tab(self):
        """刷新世界 BOSS 列表。"""
        self.world_boss_list.clear()
        self._world_boss_map = {}
        self.selected_world_boss = None
        self.challenge_world_boss_btn.setEnabled(False)
        self.world_boss_detail.setText("请选择世界 BOSS")

        bosses = self.engine.world_boss_manager.get_active_bosses()
        if not bosses:
            self.world_boss_info.setText(
                "当前世间暂无活跃的世界 BOSS。\n"
                "达到特定境界后，世界 BOSS 会随月份推移逐渐现身。"
            )
            self.world_boss_list.addItem("暂无活跃 BOSS")
            return

        self.world_boss_info.setText(
            f"当前共有 {len(bosses)} 个活跃的世界 BOSS。\n"
            f"挑战成功可获得稀有材料与修为奖励。"
        )

        for boss_cfg in bosses:
            boss_id = boss_cfg["id"]
            location = self.engine.world.get_location(boss_cfg.get("location", ""))
            loc_name = location["name"] if location else "未知地点"
            item = QListWidgetItem(f"{boss_cfg['name']} - 出没于{loc_name}")
            item.setData(256, boss_id)
            self.world_boss_list.addItem(item)
            self._world_boss_map[boss_id] = boss_cfg

    def _on_world_boss_selected(self, item):
        """选中世界 BOSS 时显示详情。"""
        boss_id = item.data(256)
        boss_cfg = self._world_boss_map.get(boss_id)
        if not boss_cfg:
            return

        self.selected_world_boss = boss_id
        location = self.engine.world.get_location(boss_cfg.get("location", ""))
        loc_name = location["name"] if location else "未知地点"

        # 境界要求文本：根据 order 反查境界名
        realm_name = "未知境界"
        for rid, order in self.engine.player.REALM_ORDER.items():
            if order == boss_cfg.get("min_realm_order", 1):
                realm_data = self.engine.world.get_realm(rid)
                if realm_data:
                    realm_name = realm_data.get("name", rid)
                break

        detail = (
            f"【{boss_cfg['name']}】\n"
            f"{boss_cfg.get('description', '')}\n"
            f"出没地点：{loc_name}\n"
            f"推荐境界：{realm_name}\n"
        )

        # 掉落预览
        loot_names = []
        for item_id in boss_cfg.get("loot", []):
            item = self.engine.item_library.get(item_id)
            loot_names.append(item.name if item else item_id)
        if loot_names:
            detail += f"可能掉落：{'、'.join(loot_names)}\n"

        # 参与奖励预览
        participation = boss_cfg.get("participation_rewards", {})
        if participation.get("qi"):
            detail += f"击败奖励修为：+{participation['qi']}\n"
        for item_id, count in participation.items():
            if item_id == "qi":
                continue
            item = self.engine.item_library.get(item_id)
            name = item.name if item else item_id
            detail += f"击败奖励物品：{name}×{count}\n"

        # 根据玩家境界决定是否允许挑战
        player_order = self.engine.player.REALM_ORDER.get(
            self.engine.player.realm_id, 0
        )
        min_order = boss_cfg.get("min_realm_order", 1)
        if player_order < min_order:
            detail += "\n（境界不足，无法挑战）"
            self.challenge_world_boss_btn.setEnabled(False)
        else:
            self.challenge_world_boss_btn.setEnabled(True)

        self.world_boss_detail.setText(detail)

    def _on_challenge_world_boss(self):
        """挑战选中的世界 BOSS，关闭弹窗后由主窗口打开战斗。"""
        if not self.selected_world_boss:
            return
        self.engine.start_world_boss_combat(self.selected_world_boss)
        self.accept()  # 关闭宗门弹窗，战斗弹窗由主窗口接管

