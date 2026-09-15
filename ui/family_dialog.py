# -*- coding: utf-8 -*-
"""修仙家族总览 / 创建弹窗（F-01）。

主弹窗负责两态：
- 未建家族：显示创建表单（名称 / 家训 / 阵营倾向，展示消耗）。
- 已建家族：显示总览（等级 / 声望 / 金库 / 资源 / 成员表 / 建筑），
  并提供 招募 / 成员任务 / 建造 / 外交 / 处理事件 / 解散 入口。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QComboBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QFrame, QHeaderView,
)
from PySide6.QtCore import Qt

from game.family import TASK_NAMES, FAMILY_MIN_REALM_ORDER, CREATE_COST_STONE, CREATE_COST_REPUTATION
from ui.family_member_dialog import FamilyMemberDialog
from ui.family_event_dialog import FamilyEventDialog
from ui.family_diplomacy_dialog import FamilyDiplomacyDialog
from ui.family_building_dialog import FamilyBuildingDialog


class FamilyDialog(QDialog):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.manager = engine.family_manager
        self.setWindowTitle("修仙家族")
        self.resize(780, 580)
        self.layout = QVBoxLayout(self)
        self._build()

    def _build(self):
        self._clear_layout()
        if not self.manager.is_created():
            self._build_create_view()
        else:
            self._build_overview()

    def _clear_layout(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ---------------- 创建视图 ----------------
    def _build_create_view(self):
        box = QFrame()
        box.setFrameShape(QFrame.Box)
        box.setStyleSheet("padding:12px; background:#fafafa;")
        v = QVBoxLayout(box)

        order = self.engine.player.REALM_ORDER.get(self.engine.player.realm_id, 0)
        if order < FAMILY_MIN_REALM_ORDER:
            v.addWidget(QLabel(
                f"需达到金丹期方可创立家族（当前境界不足）。"
            ))
            self.layout.addWidget(box)
            return

        ok, _ = self.manager.can_create()
        v.addWidget(QLabel("<b>创立修仙家族</b>"))

        v.addWidget(QLabel("家族名称："))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如：苏氏 / 云族")
        v.addWidget(self.name_edit)

        v.addWidget(QLabel("家训："))
        self.motto_edit = QLineEdit()
        self.motto_edit.setPlaceholderText("如：修仙问道，泽被苍生")
        v.addWidget(self.motto_edit)

        v.addWidget(QLabel("阵营倾向："))
        self.faction_combo = QComboBox()
        names = self.manager.config.names()
        for opt in names.get("faction_options", []):
            self.faction_combo.addItem(f"{opt['name']} — {opt.get('desc','')}", opt["id"])
        v.addWidget(self.faction_combo)

        v.addWidget(QLabel(
            f"创立消耗：灵石 {CREATE_COST_STONE}、累计声望 {CREATE_COST_REPUTATION}（声望为门槛，不消耗）。"
        ))

        create_btn = QPushButton("创立家族")
        create_btn.clicked.connect(self._on_create)
        create_btn.setEnabled(ok)
        v.addWidget(create_btn)

        self.layout.addWidget(box)
        self.layout.addStretch(1)

    def _on_create(self):
        name = self.name_edit.text().strip() or "无名家族"
        motto = self.motto_edit.text().strip() or "道心不移"
        faction = self.faction_combo.currentData()
        ok, msg = self.manager.create(name, motto, faction)
        QMessageBox.information(self, "创立家族", msg)
        if ok:
            self._build()

    # ---------------- 总览视图 ----------------
    def _build_overview(self):
        family = self.manager.get_family()
        # 头部状态
        header = QLabel(
            f"<b>{family['name']}</b>　等级 {family.get('level',1)}　"
            f"声望 {family.get('reputation',0)}　金库灵石 {family.get('treasury',0)}　"
            f"灵植 {family['resources'].get('herb',0)}　矿材 {family['resources'].get('ore',0)}"
        )
        header.setStyleSheet("padding:8px; background:#eef; border-radius:6px;")
        self.layout.addWidget(header)

        motto = QLabel(f"家训：{family.get('motto','')}")
        self.layout.addWidget(motto)

        # 成员表
        self.layout.addWidget(QLabel("<b>家族成员</b>"))
        self.member_table = QTableWidget()
        self.member_table.setColumnCount(7)
        self.member_table.setHorizontalHeaderLabels(
            ["姓名", "灵根", "资质", "忠诚", "修为", "性格", "任务"]
        )
        self.member_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._refresh_members()
        self.member_table.cellDoubleClicked.connect(self._on_member_double_click)
        self.layout.addWidget(self.member_table, 1)

        # 建筑概览
        bld = family.get("buildings", {})
        btext = "、".join(
            f"{self.manager.config.get_building(bid)['name']}({lvl})"
            for bid, lvl in bld.items() if lvl > 0
        ) or "（暂无建筑）"
        self.layout.addWidget(QLabel(f"建筑：{btext}"))

        # 按钮行
        btn_row = QHBoxLayout()
        recruit = QPushButton("招募成员")
        recruit.clicked.connect(self._on_recruit)
        member_btn = QPushButton("成员任务")
        member_btn.clicked.connect(self._on_member_manage)
        build_btn = QPushButton("建造/升级")
        build_btn.clicked.connect(self._on_build)
        diplo_btn = QPushButton("外交")
        diplo_btn.clicked.connect(self._on_diplomacy)
        event_btn = QPushButton("处理事件")
        event_btn.clicked.connect(self._on_events)
        disband = QPushButton("解散家族")
        disband.clicked.connect(self._on_disband)
        for b in (recruit, member_btn, build_btn, diplo_btn, event_btn, disband):
            btn_row.addWidget(b)
        self.layout.addLayout(btn_row)

    def _refresh_members(self):
        family = self.manager.get_family()
        self.member_table.setRowCount(len(family["members"]))
        for i, m in enumerate(family["members"]):
            self.member_table.setItem(i, 0, QTableWidgetItem(m["name"]))
            self.member_table.setItem(i, 1, QTableWidgetItem(m.get("spirit_root", "none")))
            self.member_table.setItem(i, 2, QTableWidgetItem(str(m.get("aptitude", 0))))
            self.member_table.setItem(i, 3, QTableWidgetItem(str(m.get("loyalty", 0))))
            self.member_table.setItem(i, 4, QTableWidgetItem(f"{m.get('cultivation',0):.1f}"))
            self.member_table.setItem(i, 5, QTableWidgetItem("、".join(m.get("personality", []))))
            self.member_table.setItem(i, 6, QTableWidgetItem(TASK_NAMES.get(m.get("task"), "待命")))

    def _on_member_double_click(self, row, _col):
        family = self.manager.get_family()
        if row < 0 or row >= len(family["members"]):
            return
        member = family["members"][row]
        dlg = FamilyMemberDialog(self.manager, member, parent=self)
        dlg.task_changed.connect(lambda: self._refresh_members())
        dlg.exec()

    def _on_recruit(self):
        mem = self.manager.recruit_member(quality="normal")
        if mem:
            QMessageBox.information(self, "招募", f"新成员【{mem['name']}】加入家族。")
            self._build()
        else:
            QMessageBox.information(self, "招募", "招募失败。")

    def _on_member_manage(self):
        family = self.manager.get_family()
        if not family["members"]:
            QMessageBox.information(self, "成员任务", "尚无成员。")
            return
        dlg = FamilyMemberDialog(self.manager, family["members"][0], parent=self)
        dlg.task_changed.connect(lambda: self._refresh_members())
        dlg.exec()

    def _on_build(self):
        dlg = FamilyBuildingDialog(self.manager, parent=self)
        dlg.finished.connect(lambda _: self._build())
        dlg.exec()

    def _on_diplomacy(self):
        dlg = FamilyDiplomacyDialog(self.manager, parent=self)
        dlg.exec()

    def _on_events(self):
        family = self.manager.get_family()
        if not family.get("pending_events"):
            QMessageBox.information(self, "家族事件", "当前没有待处理事件。")
            return
        dlg = FamilyEventDialog(self.manager, parent=self)
        dlg.resolved.connect(lambda: self._build())
        dlg.exec()

    def _on_disband(self):
        reply = QMessageBox.question(
            self, "解散家族",
            "确定要解散家族吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ok, msg = self.manager.disband()
        QMessageBox.information(self, "解散家族", msg)
        if ok:
            self._build()
            # 维度①：家族覆灭属重大挫折，滋生心魔
            if self.engine.is_feature_enabled("heart_demon"):
                self.engine.mental_state_manager.on_major_setback("family_collapse")
                self.engine.notify("[red]家族覆灭，心中剧痛，心魔滋生！")
            self.engine._refresh_status()
