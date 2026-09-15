from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QMessageBox,
    QMenuBar, QMenu, QFileDialog, QScrollArea, QPushButton,
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QRect,
    QObject, QRunnable, QThreadPool, Signal,
)
from PySide6.QtGui import QAction

from game.player import Player
from game.world import World
from game.events import EventPool
from game.item import ItemLibrary
from game.enemy import EnemyLibrary
from game.skill import SkillLibrary
from game.npc import NPCLibrary
from game.quest import QuestLibrary
from game.engine import GameEngine
from game.save_manager import SaveManager
from game.sound_manager import SoundManager
from ui.status_panel import StatusPanel
from ui.log_panel import LogPanel
from ui.action_panel import ActionPanel
from ui.map_panel import MapDialog
from ui.combat_dialog import CombatDialog
from ui.deploy_treasure_dialog import DeployPreviewDialog
from ui.inventory_dialog import InventoryDialog
from ui.npc_dialog import NPCDialog
from ui.quest_dialog import QuestDialog
from ui.quest_log_dialog import QuestLogDialog
from ui.map_widget import MapWidget
from ui.city_dialog import CityDialog
from ui.skill_effect_overlay import SkillEffectOverlay
from ui.spiritual_root_dialog import SpiritualRootDialog
from ui.cultivation_path_dialog import CultivationPathDialog
from ui.life_treasure_craft_dialog import LifeTreasureCraftDialog
from ui.equipment_dialog import EquipmentDialog
from ui.tribulation_dialog import TribulationDialog, TribulationResultDialog
from ui.sect_dialog import SectDialog
from ui.private_residence_dialog import PrivateResidenceDialog
from ui.mind_method_dialog import MindMethodDialog
from ui.farm_dialog import FarmDialog
from ui.achievement_dialog import AchievementDialog
from ui.side_quest_dialog import SideQuestDialog
from ui.auction_house_dialog import AuctionHouseDialog
from ui.bounty_board_dialog import BountyBoardDialog
from ui.compendium_dialog import CompendiumDialog
from ui.world_events_dialog import WorldEventsDialog
from ui.secret_realm_dialog import SecretRealmDialog
from ui.family_dialog import FamilyDialog
from ui.territory_dialog import TerritoryDialog
from ui.difficulty_mode_dialog import DifficultyModeDialog
from ui.heart_demon_dialog import HeartDemonDialog
from ui.heart_demon_tribulation_dialog import HeartDemonTribulationDialog
from ui.heaven_retribution_dialog import HeavenRetributionDialog
from ui.lifespan_dialog import LifespanDialog
from ui.red_dust_dialog import RedDustDialog
from ui.hundred_schools_dialog import HundredSchoolsDialog
from ui.character_creation_dialog import CharacterCreationDialog
from ui.face_customize_dialog import FaceCustomizeDialog
from game.cultivation_path import CultivationPathConfig


class _AIStorySignals(QObject):
    """AI 剧情生成工作线程信号：finished(text)。"""
    finished = Signal(str)


class _AIStoryWorker(QRunnable):
    """后台调用 Agnes LLM 生成 AI 剧情文案，避免阻塞界面。"""

    def __init__(self, engine, ctx):
        super().__init__()
        self.engine = engine
        self.ctx = ctx or {}
        self.signals = _AIStorySignals()

    def run(self):
        try:
            realm = self.engine.world.get_realm(self.engine.player.realm_id)
            realm_name = realm.get("name") if realm else None
            text = self.engine.ai_story_generator.generate_story(
                self.ctx.get("event") or {},
                self.engine.player,
                self.ctx.get("location"),
                realm_name,
            )
            self.signals.finished.emit(text or "")
        except Exception:
            self.signals.finished.emit("")


# 境界 ID → 中文名映射（用于推荐境界警告弹窗）
_REALM_NAMES = {
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


class MainWindow(QMainWindow):
    """修仙模拟器主窗口，负责组装所有 UI 组件和游戏逻辑。"""

    def __init__(self, start_mode="auto", slot=None):
        super().__init__()
        self.setWindowTitle("修仙模拟器")
        self.resize(1200, 800)

        # 公共资源库
        self.item_library = ItemLibrary(config_dir="config")
        self.enemy_library = EnemyLibrary(config_dir="config")
        self.skill_library = SkillLibrary(config_dir="config")
        self.npc_library = NPCLibrary(config_dir="config")
        self.quest_library = QuestLibrary(config_dir="config")
        # 修炼流派配置库
        self.path_config = CultivationPathConfig(config_dir="config")
        self.save_manager = SaveManager(save_path="save.json")
        # 当前存档槽位（由登录界面传入）；None 表示沿用旧 save.json
        self._desired_slot_name = None
        if start_mode == "load" and slot:
            # 读档：login 传入的是 SaveSelectDialog 选定的已存在槽位，直接用
            self.current_slot = slot
            self.save_manager.active_slot = slot
        elif start_mode == "new" and slot:
            # 新游戏：login 传入的是期望存档名，仅作命名基准，分配时再做冲突去重
            self._desired_slot_name = slot
            self.current_slot = None
        else:
            self.current_slot = None
        self.sound_manager = SoundManager(assets_dir="assets")

        # 初始化游戏数据与引擎
        self._init_game()

        # 创建顶部菜单栏
        self._setup_menu_bar()

        # 应用全局视觉风格
        self._setup_global_style()

        # 创建中心部件和主布局
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # 左侧：状态面板
        self.status_panel = StatusPanel(self.player, self.world, self.quest_library)
        self.status_panel.open_quest_dialog.connect(self._open_quest_dialog)
        self.status_panel.open_quest_log.connect(self._open_quest_log)
        self.status_panel.face_customize_requested.connect(self._open_face_customize)
        main_layout.addWidget(self.status_panel, 1)

        # 中间：地图 + 日志
        center_layout = QVBoxLayout()

        # 简易地图
        self.map_widget = MapWidget(self.world, engine=self.engine)
        self.map_widget.set_current_location(self.player.location_id)
        self.map_widget.location_clicked.connect(self._on_map_location_clicked)

        # 地图区顶部工具条：标题 + 主线进度 + 新手引导进度 + 2D/3D 切换按钮
        map_header = QHBoxLayout()
        map_title = QLabel("修仙世界地图")
        map_title.setStyleSheet("font-weight: bold; font-size: 13px;")
        map_header.addWidget(map_title)
        self.main_story_label = QLabel()
        self.main_story_label.setStyleSheet(
            "color: #6d28d9; font-size: 12px; padding: 2px 10px;"
            "background: #ede9fe; border: 1px solid #c4b5fd; border-radius: 4px;"
        )
        self.main_story_label.setVisible(False)
        map_header.addWidget(self.main_story_label)
        self.tutorial_label = QLabel()
        self.tutorial_label.setStyleSheet(
            "color: #b45309; font-size: 12px; padding: 2px 10px;"
            "background: #fef3c7; border: 1px solid #fcd34d; border-radius: 4px;"
        )
        self.tutorial_label.setVisible(False)
        map_header.addWidget(self.tutorial_label)
        map_header.addStretch(1)
        self.map_style_btn = QPushButton()
        self.map_style_btn.setMinimumWidth(130)
        self.map_style_btn.clicked.connect(self._on_toggle_map_style)
        self.map_widget.style_changed.connect(lambda _b: self._update_map_style_btn())
        map_header.addWidget(self.map_style_btn)
        center_layout.addLayout(map_header)

        center_layout.addWidget(self.map_widget, 2)
        self._update_map_style_btn()

        # 技能特效覆盖层（放在地图上方）
        self.effect_overlay = SkillEffectOverlay(self.map_widget)
        self.effect_overlay.setGeometry(self.map_widget.rect())

        # AI 剧情增强状态（后台生成中标志，防重入）
        self._ai_story_busy = False
        self._ai_story_worker = None

        # 底部日志面板
        self.log_panel = LogPanel()
        center_layout.addWidget(self.log_panel, 1)
        main_layout.addLayout(center_layout, 3)

        # 右侧：操作面板（用 QScrollArea 包住，多组展开时可滚动；避免内容撑大布局）
        self.action_panel = ActionPanel(self.engine)
        self.action_scroll = QScrollArea()
        self.action_scroll.setWidgetResizable(True)
        self.action_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.action_scroll.setFrameShape(QScrollArea.NoFrame)
        self.action_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.action_scroll.setWidget(self.action_panel)
        main_layout.addWidget(self.action_scroll, 1)

        # 连接操作面板的信号
        self.action_panel.open_inventory.connect(self._open_inventory)
        self.action_panel.open_map.connect(self._open_map)
        self.action_panel.open_npc.connect(self._open_npc)
        self.action_panel.open_craft_life_treasure.connect(self._open_craft_life_treasure)
        self.action_panel.open_equipment.connect(self._open_equipment)
        self.action_panel.open_sect.connect(self._open_sect)
        self.action_panel.open_residence.connect(self._open_residence)
        self.action_panel.open_mind_method.connect(self._open_mind_method)
        self.action_panel.open_farm.connect(self._open_farm)
        self.action_panel.open_achievement.connect(self._open_achievement)
        self.action_panel.open_side_quest.connect(self._open_side_quest)
        self.action_panel.open_auction_house.connect(self._open_auction_house)
        self.action_panel.open_bounty_board.connect(self._open_bounty_board)
        self.action_panel.open_compendium.connect(self._open_compendium)
        self.action_panel.open_world_events.connect(self._open_world_events)
        self.action_panel.open_secret_realm.connect(self._open_secret_realm)
        self.action_panel.open_family.connect(self._open_family)
        self.action_panel.open_territory.connect(self._open_territory)
        self.action_panel.open_difficulty_mode.connect(self._open_difficulty_mode)
        self.action_panel.open_heart_demon.connect(self._open_heart_demon)
        self.action_panel.open_heaven_retribution.connect(self._open_heaven_retribution)
        self.action_panel.open_lifespan.connect(self._open_lifespan)
        self.action_panel.open_red_dust.connect(self._open_red_dust)
        self.action_panel.open_hundred_schools.connect(self._open_hundred_schools)
        self.action_panel.save_game.connect(self._save_game)
        self.action_panel.load_game.connect(self._load_game)

        # 注册游戏事件监听器
        self.engine.add_listener(self._on_game_event)

        # 初始欢迎日志 / 启动方式（由登录界面控制：new / load / auto）
        if start_mode == "new":
            self._show_character_creation_dialog()
        elif start_mode == "load":
            self._load_game(slot=slot)
        elif self.save_manager.exists():
            self.log_panel.append("检测到存档，可点击「读取存档」继续上次的修行。")
        else:
            self.log_panel.append("欢迎来到修仙世界，道友请开始你的修行。")
            # 新游戏时先弹出角色创建，再进入灵根觉醒
            self._show_character_creation_dialog()
        self._refresh_status()

    def _setup_menu_bar(self):
        """初始化顶部菜单栏：设置、更换立绘等入口。"""
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        settings_menu = QMenu("设置", self)
        change_portrait_action = QAction("更换立绘", self)
        change_portrait_action.setStatusTip("更换主角头像")
        change_portrait_action.triggered.connect(self._change_portrait_from_menu)
        settings_menu.addAction(change_portrait_action)

        # 综合设置入口：音效 / 音量 / 立绘 / 难度（游戏内可用）
        open_settings_action = QAction("设置", self)
        open_settings_action.setStatusTip("音效、立绘与游戏难度设置")
        open_settings_action.triggered.connect(self._open_settings_dialog)
        settings_menu.addAction(open_settings_action)

        menu_bar.addMenu(settings_menu)

        help_menu = QMenu("帮助", self)
        career_action = QAction("修行年谱", self)
        career_action.setStatusTip("回顾你的生涯大事记")
        career_action.triggered.connect(self._open_career_dialog)
        help_menu.addAction(career_action)
        guide_action = QAction("玩法指南", self)
        guide_action.setStatusTip("快速上手、系统总览、AI 功能与常见问题")
        guide_action.triggered.connect(self._open_help_dialog)
        help_menu.addAction(guide_action)
        menu_bar.addMenu(help_menu)

    def _open_help_dialog(self):
        """打开玩法指南弹窗。"""
        from ui.help_dialog import HelpDialog
        HelpDialog(parent=self).exec()

    def _open_career_dialog(self):
        """打开修行年谱弹窗。"""
        from ui.career_dialog import CareerDialog
        CareerDialog(self.player, self.world, parent=self).exec()

    def _setup_global_style(self):
        """配置全局 QSS，统一圆角、配色与去黑边风格。"""
        style = """
        QMainWindow {
            background-color: #f0f2f5;
        }
        QWidget {
            font-family: "Microsoft YaHei", "SimHei", sans-serif;
            color: #2c3e50;
        }
        QPushButton {
            background-color: #ffffff;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: #f8f9fa;
            border-color: #adb5bd;
        }
        QPushButton:pressed {
            background-color: #e9ecef;
        }
        QPushButton:disabled {
            color: #adb5bd;
            background-color: #f1f3f5;
            border-color: #e9ecef;
        }
        QToolButton {
            background-color: #ffffff;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 4px;
        }
        QToolButton:hover {
            background-color: #f8f9fa;
            border-color: #adb5bd;
        }
        QProgressBar {
            border: none;
            border-radius: 6px;
            background: #e9ecef;
            text-align: center;
            font-size: 11px;
        }
        QProgressBar::chunk {
            border-radius: 6px;
        }
        QFrame {
            border: none;
        }
        QTextEdit {
            background-color: #ffffff;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 6px;
            font-size: 13px;
        }
        QMenuBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }
        QMenuBar::item:selected {
            background-color: #e9ecef;
            border-radius: 4px;
        }
        QMenu {
            background-color: #ffffff;
            border: 1px solid #dee2e6;
            border-radius: 6px;
        }
        QMenu::item:selected {
            background-color: #e9ecef;
        }
        """
        self.setStyleSheet(style)

    def _change_portrait_from_menu(self):
        """从菜单栏触发头像更换，与状态面板右键菜单逻辑一致。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择主角头像",
            "assets/portraits",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if file_path:
            self.player.portrait = file_path
            self._refresh_status()
            self.log_panel.append(f"已更换主角立绘：{file_path}")

    def _open_settings_dialog(self):
        """打开综合设置对话框（音效 / 音量 / 立绘 / 难度）。"""
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(
            parent=self,
            engine=self.engine,
            player=self.player,
            sound_manager=self.sound_manager,
        )
        dlg.exec()
        self._refresh_status()

    def _show_character_creation_dialog(self):
        """新游戏时弹出角色创建弹窗，设置道号与头像。"""
        dialog = CharacterCreationDialog(parent=self)
        if dialog.exec() == CharacterCreationDialog.Accepted:
            self.player.name = dialog.get_name()
            self.player.portrait = dialog.get_portrait()
            self.player.gender = dialog.get_gender()
            self.player.face_traits = dialog.get_face_traits()
            self.player.face_params = dialog.get_face_params()
            self._refresh_status()
            self.log_panel.append(f"道号已定：{self.player.name}")
            self.engine.chronicle_manager.record(
                f"道号已定「{self.player.name}」，踏上修行路", category="event"
            )
        else:
            # 取消则使用默认道号与头像
            self.log_panel.append("使用默认道号与头像开始游戏。")
        # 新游戏：分配存档槽位（若尚未指定）。命名基准优先用 login 期望名，冲突时去重
        if self.current_slot is None:
            base = self._desired_slot_name or self.player.name or "修仙之旅"
            self.current_slot = self.save_manager.allocate_slot(base)
            self.save_manager.active_slot = self.current_slot
            self.log_panel.append(f"已创建存档槽位：{self.current_slot}")
        # 角色创建后进入难度与多周目模式选择（F-06 / F-07）
        self._show_difficulty_mode_dialog()

    def _show_difficulty_mode_dialog(self):
        """新游戏时选择修行难度与多周目模式。"""
        dialog = DifficultyModeDialog(
            self.engine, self.player, parent=self, new_game=True
        )
        dialog.exec()  # 取消则沿用默认 normal/standard
        # 凡人挑战（天生无灵根）跳过灵根觉醒，直接进入流派选择
        if getattr(self.player, "no_spiritual_roots", False):
            self.player.set_spiritual_roots([], {})
            self._show_cultivation_path_dialog()
        else:
            self._show_spiritual_root_dialog()

    def _show_spiritual_root_dialog(self):
        """新游戏时弹出灵根觉醒选择弹窗。"""
        dialog = SpiritualRootDialog(parent=self)
        if dialog.exec() == SpiritualRootDialog.Accepted:
            roots = dialog.get_roots()
            purities = dialog.get_purities()
            if roots:
                self.player.set_spiritual_roots(roots, purities)
                self._refresh_status()
                self.log_panel.append("灵根觉醒完成，你的修仙之路正式开始。")
                self.engine._auto_save()
                # 检查是否五行俱全，解锁阵法技能
                self.engine.check_formation_unlock()
                # 灵根觉醒后弹出流派选择弹窗
                self._show_cultivation_path_dialog()

    def _show_cultivation_path_dialog(self):
        """灵根觉醒后弹出修炼流派选择弹窗。"""
        dialog = CultivationPathDialog(
            spiritual_roots=self.player.spiritual_roots,
            allowed_paths=getattr(self.player, "allowed_paths", []),
            parent=self
        )
        if dialog.exec() == CultivationPathDialog.Accepted:
            path_id = dialog.get_path()
            if path_id:
                # 获取流派属性修正
                modifiers = self.path_config.get_modifiers(path_id)
                self.player.set_cultivation_path(path_id, modifiers)
                self._refresh_status()
                path_name = self.path_config.get_path_name(path_id)
                self.log_panel.append(f"你选择了【{path_name}】之道，踏上专属修炼之路。")
                self.engine._auto_save()

    def _init_game(self, player=None, world=None):
        """初始化或重置游戏数据。"""
        if player is None:
            player = Player(name="无名散修")
        if world is None:
            world = World(config_dir="config")

        self.player = player
        self.world = world
        self.event_pool = EventPool(config_dir="config")
        self.engine = GameEngine(
            self.player,
            self.world,
            self.event_pool,
            self.item_library,
            self.enemy_library,
            self.skill_library,
            self.npc_library,
            self.quest_library,
            save_manager=self.save_manager,
        )

    def _on_game_event(self, message):
        """监听引擎通知，刷新界面或处理特殊事件。"""
        if message == "__RESET__":
            self._reset_game()
            return

        if message == "__COMBAT_START__":
            enemy = getattr(self.engine, "current_enemy", None)
            if enemy:
                self._open_combat(enemy)
            return

        # 渡劫开始标记：显示渡劫过程弹窗（心魔小游戏 / 雷劫动画）
        if message.startswith("__TRIBULATION_START__:"):
            parts = message.split(":")
            tribulation_name = parts[2]
            base_rate = float(parts[3]) if len(parts) > 3 else 0.0
            self._show_tribulation_dialog(tribulation_name, base_rate)
            return

        # 渡劫结果标记：根据成功/失败播放结果动画
        if message.startswith("__TRIBULATION_RESULT__:"):
            parts = message.split(":")
            success = parts[2] == "success"
            tribulation_name = parts[3] if len(parts) > 3 else ""
            self._show_tribulation_result_dialog(tribulation_name, success)
            return

        # 维度①：大境界突破后心魔值过高 → 强制触发心魔劫幻境（异步展示抉择）
        if message.startswith("__HEART_DEMON_TRIBULATION__:"):
            scenario_id = message.split(":", 1)[1]
            self._show_heart_demon_tribulation_dialog(scenario_id)
            return

        # 技能特效标记
        if message == "__EFFECT_SWORD__":
            self.effect_overlay.show_sword_slash()
            return
        elif message == "__EFFECT_THUNDER__":
            self.effect_overlay.show_thunder_flash()
            return
        elif message == "__EFFECT_HEAL__":
            self.effect_overlay.show_heal_glow()
            return

        # 云游商人偶遇事件：打开交易弹窗
        if message == "__MERCHANT_ENCOUNTER__":
            self._open_merchant()
            return

        # 结局达成：弹出结局结算画面
        if message.startswith("__ENDING__:"):
            ending_id = message.split(":", 1)[1]
            self._show_ending_dialog(ending_id)
            return

        # AI 剧情增强：后台生成完成后追加日志（不阻塞游历主流程）
        if message == "__AI_STORY_PENDING__":
            self._start_ai_story_enhancement()
            return

        # 普通事件：追加日志并刷新状态
        self.log_panel.append(message)
        self._refresh_status()

        # 特定事件触发音效/动画反馈
        if "突破成功" in message:
            self._play_breakthrough_animation()
        elif "赢得了这场战斗" in message or "你赢得了这场战斗" in message:
            self._play_victory_animation()
        elif "任务完成" in message:
            self.sound_manager.play_level_up()

        # 玩家死亡时弹出提示
        if not self.player.is_alive():
            self._show_death_message()

    def _refresh_status(self):
        """刷新左侧状态面板、地图和操作面板按钮状态。"""
        self.status_panel.update_status()
        self.map_widget.set_current_location(self.player.location_id)
        self.action_panel.refresh_buttons()
        self._update_main_story_label()
        self._update_tutorial_label()

    def _update_main_story_label(self):
        """刷新主线章节进度提示条（主线完成时隐藏）。"""
        progress = self.engine.get_main_story_progress()
        if not progress:
            self.main_story_label.setVisible(False)
            return
        title, desc, current, total = progress
        self.main_story_label.setText(f"主线 {current}/{total} · {title}：{desc}")
        self.main_story_label.setVisible(True)

    def _update_tutorial_label(self):
        """刷新新手引导进度提示条（未开启或已完成时隐藏）。"""
        progress = self.engine.get_tutorial_progress()
        if not progress:
            self.tutorial_label.setVisible(False)
            return
        current, total, title, desc = progress
        self.tutorial_label.setText(f"引导 {current}/{total} · {title}：{desc}")
        self.tutorial_label.setVisible(True)

    def _reset_game(self):
        """重新开始游戏。"""
        self._init_game()
        self._reconnect_after_load_or_reset()

        self.log_panel.clear()
        self.log_panel.append("轮回转世，你重新开始修仙之路。")
        # 重新开始时也弹出灵根觉醒
        self._show_spiritual_root_dialog()
        self._refresh_status()

    def _show_ending_dialog(self, ending_id):
        """弹出结局结算画面。"""
        ending = None
        endings_cfg = getattr(self.engine, "_endings", {}) or {}
        for e in endings_cfg.get("endings", []):
            if e.get("id") == ending_id:
                ending = e
                break
        if not ending:
            return
        from ui.ending_dialog import EndingDialog
        dialog = EndingDialog(ending, parent=self)
        dialog.reincarnate_requested.connect(self._reset_game)
        dialog.main_menu_requested.connect(self.close)
        dialog.exec()

    def _on_ending_main_menu(self):
        """结局后返回主菜单：关闭主窗口。"""
        self.close()

    def _start_ai_story_enhancement(self):
        """发起后台 AI 剧情生成（生成中则丢弃本次增强，避免堆积）。"""
        if getattr(self, "_ai_story_busy", False):
            self.engine.pop_pending_ai_event()
            return
        ctx = self.engine.pop_pending_ai_event()
        if not ctx:
            return
        self._ai_story_busy = True
        worker = _AIStoryWorker(self.engine, ctx)
        worker.signals.finished.connect(self._on_ai_story_ready)
        self._ai_story_worker = worker  # 保留引用，防止生成中被回收
        QThreadPool.globalInstance().start(worker)

    def _on_ai_story_ready(self, text):
        """AI 剧情生成完成（主线程回调）：追加到日志。"""
        self._ai_story_busy = False
        self._ai_story_worker = None
        if text:
            import html
            safe = html.escape(text)
            self.log_panel.append(
                f'<span style="color:#8a7ae8;">✨ <b>AI 剧情</b>：{safe}</span>'
            )

    def _open_face_customize(self):
        """打开捏脸弹窗（游戏中）；采用后更新玩家形象并保存。"""
        dialog = FaceCustomizeDialog(
            gender=getattr(self.player, "gender", "male"),
            player=self.player, parent=self,
        )
        if dialog.exec() == FaceCustomizeDialog.Accepted and dialog.adopted_path:
            self.player.portrait = dialog.adopted_path
            self.player.face_traits = dialog.adopted_traits or {}
            self.player.face_params = dialog.adopted_params or {}
            self._refresh_status()
            self.engine._auto_save()
            self.log_panel.append("你的形象已焕然一新。")
            self.engine.chronicle_manager.record(
                "重新捏脸，换了新形象", category="event"
            )

    def _reconnect_after_load_or_reset(self):
        """重新连接引擎、面板、信号之间的引用。"""
        self.action_panel.engine = self.engine
        self.status_panel.player = self.player
        self.status_panel.world = self.world
        self.map_widget.world = self.world
        self.map_widget.engine = self.engine
        self.map_widget.set_current_location(self.player.location_id)
        self.engine.add_listener(self._on_game_event)

    def _on_map_location_clicked(self, location_id):
        """点击地图上的地点时前往；若目标是城池，则进入城池内部界面。"""
        location = self.world.get_location(location_id)
        is_city = location and location.get("type") == "city"

        if location_id != self.player.location_id:
            # 推荐境界检查：境界不足时警告但仍允许进入
            if not self._confirm_realm_if_needed(location_id):
                return
            self.engine.travel(location_id)

        # 点击城池（包括当前所在城池）后打开城内建筑界面
        if is_city and self.player.location_id == location_id:
            self._open_city_dialog(location_id)

    def _on_toggle_map_style(self):
        """点击按钮：在 2D / 3D 地图风格之间切换（并持久化偏好）。"""
        self.map_widget.set_3d_enabled(not self.map_widget.is_3d_enabled(), persist=True)

    def _update_map_style_btn(self):
        """根据当前地图风格刷新按钮文案与可用状态。"""
        if not self.map_widget.is_feature_available():
            # feature_flags 关闭 3D 时禁用按钮
            self.map_style_btn.setEnabled(False)
            self.map_style_btn.setText("3D 已禁用")
            return
        self.map_style_btn.setEnabled(True)
        if self.map_widget.is_3d_enabled():
            self.map_style_btn.setText("切换到 2D 风格")
        else:
            self.map_style_btn.setText("切换到 3D 风格")

    def _confirm_realm_if_needed(self, location_id):
        """
        若目标地点推荐境界高于玩家当前境界，弹出警告确认。
        玩家点击「仍然前往」则返回 True；点击取消或无需警告返回 True。
        """
        location = self.world.get_location(location_id)
        if not location:
            return True
        rec_realm_id = location.get("recommended_realm")
        if not rec_realm_id:
            return True
        current_realm = self.world.get_realm(self.player.realm_id)
        rec_realm = self.world.get_realm(rec_realm_id)
        if not current_realm or not rec_realm:
            return True
        # 当前境界 order 小于推荐境界时提示风险
        if current_realm["order"] < rec_realm["order"]:
            current_name = _REALM_NAMES.get(self.player.realm_id, self.player.realm_id)
            rec_name = _REALM_NAMES.get(rec_realm_id, rec_realm_id)
            reply = QMessageBox.warning(
                self,
                "修为不足",
                f"【{location['name']}】建议境界为 {rec_name}，\n"
                f"你当前仅为 {current_name}，进入此地风险极大！\n\n"
                f"是否仍然前往？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            return reply == QMessageBox.Yes
        return True

    def _open_inventory(self):
        """打开背包与合成弹窗。"""
        dialog = InventoryDialog(
            self.player, self.world, self.item_library, self.engine, parent=self
        )
        dialog.exec()
        self._refresh_status()

    def _open_craft_life_treasure(self):
        """打开本命法宝炼制弹窗。"""
        if not self.player.has_feature("life_treasure"):
            QMessageBox.information(
                self, "尚未解锁", "本命法宝需达到金丹期方可炼制。"
            )
            return
        dialog = LifeTreasureCraftDialog(
            self.player, self.item_library, self.engine, parent=self
        )
        dialog.exec()
        self._refresh_status()

    def _open_equipment(self):
        """打开炼器附魔弹窗。"""
        dialog = EquipmentDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_sect(self):
        """打开宗门弹窗。"""
        dialog = SectDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_residence(self):
        """打开私人洞府管理弹窗。"""
        dialog = PrivateResidenceDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_mind_method(self):
        """打开心法管理弹窗。"""
        dialog = MindMethodDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_farm(self):
        """打开洞府药园弹窗。"""
        dialog = FarmDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_achievement(self):
        """打开成就面板弹窗。"""
        dialog = AchievementDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_side_quest(self):
        """打开支线任务弹窗。"""
        dialog = SideQuestDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_auction_house(self):
        """打开拍卖行弹窗。"""
        dialog = AuctionHouseDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_bounty_board(self):
        """打开悬赏板弹窗。"""
        dialog = BountyBoardDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_compendium(self):
        """打开图鉴弹窗。"""
        dialog = CompendiumDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_world_events(self):
        """打开天下大事弹窗（F-04 动态世界事件）。"""
        dialog = WorldEventsDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_secret_realm(self):
        """打开 Roguelike 秘境探索弹窗（F-03）。"""
        dialog = SecretRealmDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_family(self):
        """打开修仙家族弹窗（F-01）。"""
        dialog = FamilyDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_territory(self):
        """打开领地建设弹窗（F-02）。"""
        dialog = TerritoryDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_difficulty_mode(self):
        """打开难度与多周目模式弹窗（F-06 / F-07，游戏内查看/调整难度）。"""
        dialog = DifficultyModeDialog(self.engine, self.player, parent=self, new_game=False)
        dialog.exec()
        self._refresh_status()

    def _open_heart_demon(self):
        """打开心魔·道心状态弹窗（维度①）。"""
        dialog = HeartDemonDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_heaven_retribution(self):
        """打开天道反噬与生态平衡弹窗（维度④）。"""
        dialog = HeavenRetributionDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_lifespan(self):
        """打开寿元与轮回晚年弹窗（维度⑤）。"""
        dialog = LifespanDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_red_dust(self):
        """打开红尘炼心 / 入世弹窗（维度②）。"""
        dialog = RedDustDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_hundred_schools(self):
        """打开百家争鸣 / 非传统修仙路线弹窗（维度③）。"""
        dialog = HundredSchoolsDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _show_heart_demon_tribulation_dialog(self, scenario_id):
        """显示心魔劫幻境弹窗：玩家在幻境中做出抉择，永久改变性格与后续概率。"""
        dialog = HeartDemonTribulationDialog(self.engine, scenario_id, parent=self)
        dialog.scenario_resolved.connect(self._on_heart_demon_choice_applied)
        dialog.exec()
        self._refresh_status()

    def _on_heart_demon_choice_applied(self, scenario_id, choice_id):
        """心魔劫幻境抉择已应用：刷新状态面板。"""
        self._refresh_status()

    def _show_tribulation_dialog(self, tribulation_name, base_rate):
        """显示渡劫过程弹窗：雷劫/天劫自动播放，心魔劫进入小游戏。"""
        dialog = TribulationDialog(
            self.engine, tribulation_name, base_rate, parent=self
        )
        dialog.exec()

    def _show_tribulation_result_dialog(self, tribulation_name, success):
        """显示渡劫结果动画：成功祥云/失败血雷。"""
        dialog = TribulationResultDialog(tribulation_name, success, parent=self)
        dialog.exec()

    def _open_map(self):
        """打开地图弹窗，选择地点后前往；若选中城池，进入城池内部。"""
        dialog = MapDialog(self.world, self.player.location_id, parent=self)
        if dialog.exec() == MapDialog.Accepted and dialog.selected_location_id:
            # 推荐境界检查：境界不足时警告但仍允许进入
            if self._confirm_realm_if_needed(dialog.selected_location_id):
                self.engine.travel(dialog.selected_location_id)
                if self.player.location_id == dialog.selected_location_id:
                    location = self.world.get_location(dialog.selected_location_id)
                    if location and location.get("type") == "city":
                        self._open_city_dialog(dialog.selected_location_id)

    def _open_city_dialog(self, location_id):
        """打开城池内部建筑界面。"""
        dialog = CityDialog(self.engine, location_id, parent=self)
        dialog.exec()

    def _open_npc(self):
        """打开 NPC 交互弹窗。"""
        dialog = NPCDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_merchant(self):
        """偶遇云游商人时，从物品池随机抽取商品后打开交易弹窗。"""
        merchant = self.npc_library.get("wandering_merchant")
        if not merchant:
            return
        # 如果配置了随机商品池，每次偶遇从中随机抽取若干件
        if merchant.shop_pool:
            import random as _random
            count = min(merchant.shop_pool_count, len(merchant.shop_pool))
            merchant.shop_items = _random.sample(merchant.shop_pool, count)
        # 复用 NPC 对话弹窗，预设选中云游商人
        dialog = NPCDialog(self.engine, preset_npc=merchant, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_quest_dialog(self):
        """打开任务管理弹窗。"""
        dialog = QuestDialog(self.player, self.quest_library, self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _open_quest_log(self):
        """打开任务日志弹窗。"""
        dialog = QuestLogDialog(self.player, self.quest_library, parent=self)
        dialog.exec()

    def _open_combat(self, enemy):
        """打开战斗弹窗。"""
        # 维度③·M24：开战前，若未开启自动部署且持有可部署法宝，弹出预览确认弹窗，
        # 让玩家在战斗动作之前自行决定部署哪些生活法宝（避免与 lifepath_auto_deploy 重复）。
        if (self.engine.is_feature_enabled("hundred_schools")
                and not getattr(self.player, "lifepath_auto_deploy", False)):
            if self.engine.get_deployable_battle_consumables():
                DeployPreviewDialog.run(self.engine, self)
        dialog = CombatDialog(self.player, enemy, self.engine, parent=self)
        dialog.combat_finished.connect(self._on_combat_finished)
        dialog.exec()
        self._refresh_status()
        if not self.player.is_alive():
            self._show_death_message()

    def _on_combat_finished(self, result):
        """战斗结束时触发反馈。"""
        # 若是宗门秘境/禁地战斗，先结算奖励
        if getattr(self.engine, "pending_secret_realm_id", None):
            self.engine.sect_finish_secret_realm(result)

        # 洞府袭击战斗结算
        if getattr(self.engine, "pending_residence_raid", False):
            self.engine.resolve_residence_raid(result == "win")

        # 私人洞府占领战斗结算
        occupy_location_id = getattr(
            self.engine, "pending_residence_occupation_location_id", None
        )
        if occupy_location_id:
            self.engine.finish_residence_occupation(
                occupy_location_id, result == "win"
            )

        # 世界 BOSS 战斗结算
        if getattr(self.engine, "pending_world_boss_id", None):
            self.engine.finish_world_boss_combat(result)

        if result == "win":
            enemy = getattr(self.engine, "current_enemy", None)
            # 更新宗门悬赏击杀进度
            if enemy:
                self.engine.sect_update_bounty_after_combat(enemy.id)
            # 城池防卫战胜利：奖励城池声望
            if getattr(self.engine, "current_combat_is_city_defense", False) and enemy:
                self.engine.gain_city_reputation_from_defense(enemy)
            self._play_victory_animation()

    def _save_game(self):
        """保存游戏。"""
        self.engine.save_game()

    def _load_game(self, slot=None):
        """读取存档（可指定槽位；未指定则沿用当前槽位）。"""
        slot = slot or self.current_slot
        result = self.save_manager.load(self.item_library, config_dir="config", slot=slot)
        if result is None:
            QMessageBox.information(self, "读取存档", "没有找到存档文件。")
            return

        player, world = result
        self.current_slot = slot
        self.save_manager.active_slot = slot
        self._init_game(player=player, world=world)
        self._reconnect_after_load_or_reset()

        self.log_panel.clear()
        self.log_panel.append("存档读取成功，继续你的修仙之路。")
        self._refresh_status()
        # 读档后检查是否需要补发阵法技能（兼容旧存档）
        self.engine.check_formation_unlock()

    def closeEvent(self, event):
        """关闭主窗口时自动保存当前进度（不覆盖旧 save.json 兼容档）。"""
        try:
            slot = getattr(self, "current_slot", None)
            if (slot and slot != SaveManager.LEGACY_SLOT
                    and getattr(self, "player", None) is not None):
                self.engine.save_game()
        except Exception:
            pass
        event.accept()

    def _show_death_message(self):
        """弹出陨落提示。"""
        QMessageBox.information(
            self,
            "道消身殒",
            "你未能求得大道，已陨落于修仙路上。\n点击「重新开始」再来一局。"
        )

    def _play_breakthrough_animation(self):
        """突破成功时的动画：地图闪烁放大。"""
        self.sound_manager.play_breakthrough()
        anim = QPropertyAnimation(self.map_widget, b"geometry")
        original = self.map_widget.geometry()
        anim.setDuration(500)
        anim.setStartValue(original)
        # 先放大再恢复
        enlarged = QRect(
            original.x() - 20,
            original.y() - 15,
            original.width() + 40,
            original.height() + 30,
        )
        anim.setEndValue(enlarged)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        anim.finished.connect(lambda: self.map_widget.setGeometry(original))
        anim.start()
        # 保持引用，防止被垃圾回收
        self._animation = anim

    def _play_victory_animation(self):
        """战斗胜利时的音效。"""
        self.sound_manager.play_victory()

    def resizeEvent(self, event):
        """窗口大小变化时更新特效覆盖层尺寸。"""
        super().resizeEvent(event)
        if hasattr(self, "effect_overlay"):
            self.effect_overlay.setGeometry(self.map_widget.rect())
