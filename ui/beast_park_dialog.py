# -*- coding: utf-8 -*-
"""
万兽园弹窗：捕捉妖兽、驯养灵兽、派遣历练与购买材料。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QTabWidget,
    QWidget, QSpinBox, QComboBox
)
from PySide6.QtCore import Qt


class BeastParkDialog(QDialog):
    """万兽园交互弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player

        self.setWindowTitle("万兽园")
        self.resize(650, 520)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("<h2>万兽园</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 标签页
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # 捕捉标签页
        self.capture_tab = self._build_capture_tab()
        self.tabs.addTab(self.capture_tab, "捕捉妖兽")

        # 我的灵兽标签页
        self.my_beasts_tab = self._build_my_beasts_tab()
        self.tabs.addTab(self.my_beasts_tab, "我的灵兽")

        # 商店标签页
        self.shop_tab = self._build_shop_tab()
        self.tabs.addTab(self.shop_tab, "灵兽商店")

    def _build_capture_tab(self):
        """构建捕捉妖兽标签页。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("<b>可捕捉妖兽</b>（当前地点附近出没）"))
        self.enemy_list = QListWidget()
        self.enemy_list.setToolTip("选中妖兽后点击捕捉按钮，进入战斗。")
        layout.addWidget(self.enemy_list)

        self.capture_btn = QPushButton("开始捕捉")
        self.capture_btn.clicked.connect(self._start_capture)
        layout.addWidget(self.capture_btn)

        tip = QLabel("提示：战斗胜利后有概率收服妖兽，城市安全等级越高捕捉率越高。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(tip)

        self._refresh_enemy_list()
        return widget

    def _refresh_enemy_list(self):
        """刷新可捕捉妖兽列表。"""
        self.enemy_list.clear()
        enemies = self.engine.get_capturable_enemies()
        if not enemies:
            self.enemy_list.addItem("当前地点附近没有可捕捉的妖兽。")
            self.capture_btn.setEnabled(False)
            return
        self.capture_btn.setEnabled(True)
        for enemy in enemies:
            text = f"{enemy['name']}（境界：{enemy['difficulty']}）"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, enemy["id"])
            item.setData(Qt.UserRole + 1, enemy["name"])
            self.enemy_list.addItem(item)

    def _start_capture(self):
        """开始捕捉战斗。"""
        item = self.enemy_list.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选择一只妖兽。")
            return
        enemy_id = item.data(Qt.UserRole)
        enemy_name = item.data(Qt.UserRole + 1)

        enemy = self.engine.start_beast_capture(enemy_id)
        if not enemy:
            return

        from ui.combat_dialog import CombatDialog
        dialog = CombatDialog(self.engine.player, enemy, self.engine, parent=self)
        dialog.combat_finished.connect(
            lambda result, eid=enemy_id, ename=enemy_name: self._on_capture_finished(result, eid, ename)
        )
        dialog.exec()
        self._refresh_enemy_list()
        self._refresh_beast_list()

    def _on_capture_finished(self, result, enemy_id, enemy_name):
        """战斗结束后尝试捕捉。"""
        victory = result == "win"
        self.engine.try_capture_beast(enemy_id, enemy_name, victory)

    def _build_my_beasts_tab(self):
        """构建我的灵兽标签页。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel("<b>我的灵兽</b>"))
        self.beast_list = QListWidget()
        self.beast_list.currentItemChanged.connect(self._on_beast_selected)
        layout.addWidget(self.beast_list)

        # 详情与操作
        self.beast_detail = QLabel("请选择一只灵兽。")
        self.beast_detail.setWordWrap(True)
        self.beast_detail.setMinimumHeight(60)
        layout.addWidget(self.beast_detail)

        btn_layout = QHBoxLayout()
        self.feed_btn = QPushButton("喂养")
        self.feed_btn.setToolTip("消耗 1 株灵韵草提升忠诚度。")
        self.feed_btn.clicked.connect(self._feed_selected)
        btn_layout.addWidget(self.feed_btn)

        self.train_btn = QPushButton("训练")
        self.train_btn.setToolTip("消耗 1 个月时间提升成长。")
        self.train_btn.clicked.connect(self._train_selected)
        btn_layout.addWidget(self.train_btn)

        # 派遣历练
        dispatch_layout = QHBoxLayout()
        dispatch_layout.addWidget(QLabel("派遣月数："))
        self.dispatch_spin = QSpinBox()
        self.dispatch_spin.setRange(1, 12)
        self.dispatch_spin.setValue(1)
        dispatch_layout.addWidget(self.dispatch_spin)
        self.dispatch_btn = QPushButton("派遣历练")
        self.dispatch_btn.setToolTip("派遣灵兽外出历练，到期后带回资源。")
        self.dispatch_btn.clicked.connect(self._dispatch_selected)
        dispatch_layout.addWidget(self.dispatch_btn)
        btn_layout.addLayout(dispatch_layout)

        layout.addLayout(btn_layout)
        self._refresh_beast_list()
        return widget

    def _refresh_beast_list(self):
        """刷新我的灵兽列表。"""
        self.beast_list.clear()
        if not self.player.personal_beasts:
            self.beast_list.addItem("你还没有灵兽，快去万兽园捕捉吧。")
            return
        for index, beast in enumerate(self.player.personal_beasts):
            dispatch = beast.get("dispatch")
            status = "（历练中）" if dispatch else ""
            text = f"{index + 1}. {beast['name']} {status} — 成长 {beast['growth']} 忠诚 {beast['loyalty']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, index)
            self.beast_list.addItem(item)

    def _on_beast_selected(self, current, previous):
        """选中灵兽时更新详情。"""
        if not current:
            self.beast_detail.setText("请选择一只灵兽。")
            return
        index = current.data(Qt.UserRole)
        beast = self.player.personal_beasts[index]
        dispatch = beast.get("dispatch")
        dispatch_text = ""
        if dispatch:
            dispatch_text = (
                f"<br>历练中：预计 {dispatch['return_year']}年"
                f"{dispatch['return_month']}月{dispatch['return_day']}日 归来"
            )
        self.beast_detail.setText(
            f"<b>{beast['name']}</b>（{self._type_name(beast['type'])}）"
            f"<br>成长：{beast['growth']} | 忠诚度：{beast['loyalty']}"
            f"{dispatch_text}"
        )

    def _type_name(self, beast_type):
        """灵兽类型中文名。"""
        return {"combat": "战斗型", "mount": "坐骑型", "resource": "资源型"}.get(beast_type, beast_type)

    def _feed_selected(self):
        """喂养选中灵兽。"""
        index = self._selected_beast_index()
        if index is None:
            return
        self.engine.feed_beast(index)
        self._refresh_beast_list()

    def _train_selected(self):
        """训练选中灵兽。"""
        index = self._selected_beast_index()
        if index is None:
            return
        self.engine.train_beast(index)
        self._refresh_beast_list()

    def _dispatch_selected(self):
        """派遣选中灵兽历练。"""
        index = self._selected_beast_index()
        if index is None:
            return
        months = self.dispatch_spin.value()
        self.engine.dispatch_beast(index, months)
        self._refresh_beast_list()

    def _selected_beast_index(self):
        """获取当前选中的灵兽索引。"""
        item = self.beast_list.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选择一只灵兽。")
            return None
        return item.data(Qt.UserRole)

    def _build_shop_tab(self):
        """构建灵兽商店标签页。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<b>万兽园商店</b>"))

        open_btn = QPushButton("打开万兽园商店")
        open_btn.clicked.connect(self._open_shop)
        layout.addWidget(open_btn)

        tip = QLabel("可购买妖兽材料与灵兽契约。")
        tip.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(tip)
        layout.addStretch()
        return widget

    def _open_shop(self):
        """打开万兽园商店。"""
        from ui.npc_dialog import NPCDialog
        merchant = self.engine.visit_beast_park()
        dialog = NPCDialog(self.engine, preset_npc=merchant, parent=self)
        dialog.exec()
