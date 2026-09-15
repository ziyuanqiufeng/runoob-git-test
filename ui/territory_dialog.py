# -*- coding: utf-8 -*-
"""领地建设与扩张总览 / 占领弹窗（F-02）。

两态：
- 未占据地：显示可选领地列表（品阶 / 消耗 / 所需境界），展示占据按钮（元婴期 + flag 门控）。
- 已占据地：显示总览（品阶 / 护阵能量 / 金库 / 资源 / 防御率 / 袭扰状态），
  并提供 建造 / 防御 / 升阶 / 收取灵石 入口与网格俯视图。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QMessageBox, QFrame, QTextEdit,
)
from PySide6.QtCore import Qt

from game.territory_manager import (
    TERRITORY_MIN_REALM_ORDER, TIER_NAMES,
)
from ui.territory_grid_widget import TerritoryGridWidget
from ui.territory_build_dialog import TerritoryBuildDialog
from ui.territory_defense_dialog import TerritoryDefenseDialog


class TerritoryDialog(QDialog):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.manager = engine.territory_manager
        self.setWindowTitle("领地建设与扩张")
        self.resize(820, 600)
        self.layout = QVBoxLayout(self)
        self._build()

    def _build(self):
        self._clear_layout()
        if not self.manager.is_claimed():
            self._build_claim_view()
        else:
            self._build_overview()

    def _clear_layout(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ---------------- 占领视图 ----------------
    def _build_claim_view(self):
        box = QFrame()
        box.setFrameShape(QFrame.Box)
        box.setStyleSheet("padding:12px; background:#fafafa;")
        v = QVBoxLayout(box)

        order = self.engine.player.REALM_ORDER.get(self.engine.player.realm_id, 0)
        if order < TERRITORY_MIN_REALM_ORDER:
            v.addWidget(QLabel("需达到元婴期方可占据领地（当前境界不足）。"))
            self.layout.addWidget(box)
            return

        v.addWidget(QLabel("<b>占据一处野外领地</b>"))
        v.addWidget(QLabel(
            "占据领地后可布置聚灵塔、灵田、坊市、守卫塔与五行阵眼，"
            "每月产出灵石灵材，并可升阶为福地、洞天以扩大网格。"
        ))

        self.map_combo = QComboBox()
        maps = self.manager.config.maps()
        for m in maps:
            tier_name = TIER_NAMES.get(m.get("tier", "spirit_vein"), m.get("tier"))
            cost = m.get("claim_cost", {}).get("spirit_stone", 0)
            self.map_combo.addItem(
                f"{m['name']}（{tier_name}，占据需 {cost} 灵石）", m["id"]
            )
        v.addWidget(self.map_combo)

        self.map_desc = QLabel("")
        self.map_desc.setWordWrap(True)
        v.addWidget(self.map_desc)
        self.map_combo.currentIndexChanged.connect(self._on_map_change)
        if maps:
            self._on_map_change()

        claim_btn = QPushButton("占据领地")
        claim_btn.clicked.connect(self._on_claim)
        v.addWidget(claim_btn)

        self.layout.addWidget(box)
        self.layout.addStretch(1)

    def _on_map_change(self):
        tid = self.map_combo.currentData()
        m = self.manager.config.get_map(tid)
        if m:
            self.map_desc.setText(m.get("desc", ""))

    def _on_claim(self):
        tid = self.map_combo.currentData()
        ok, msg = self.manager.claim(tid)
        QMessageBox.information(self, "占据领地", msg)
        if ok:
            self._build()

    # ---------------- 总览视图 ----------------
    def _build_overview(self):
        t = self.manager.get_territory()
        tier_name = TIER_NAMES.get(t["tier"], t["tier"])
        defense = self.manager.get_defense_rate()
        cultivation = self.manager.get_cultivation_speed_bonus()

        header = QLabel(
            f"<b>{t['name']}</b>　品阶 {tier_name}　"
            f"护阵能量 {t.get('energy',0)}/{t.get('max_energy',0)}　"
            f"金库灵石 {t.get('treasury',0)}　"
            f"灵草 {t['resources'].get('herb',0)}　灵矿 {t['resources'].get('ore',0)}"
        )
        header.setStyleSheet("padding:8px; background:#eef; border-radius:6px;")
        self.layout.addWidget(header)

        sub = QLabel(
            f"防御率 {defense*100:.0f}%　修炼速度加成 +{cultivation*100:.0f}%　"
            f"已击退 {t.get('defended_count',0)} 次　遭劫 {t.get('raided_count',0)} 次"
        )
        self.layout.addWidget(sub)

        # 袭扰状态
        if t.get("pending_raid"):
            raid = t["pending_raid"]
            raid_lbl = QLabel(
                f"<b style='color:#c0392b'>⚠ 妖兽袭扰中：{raid['enemy_id']}</b>（请前往「防御」处置）"
            )
            self.layout.addWidget(raid_lbl)

        # 网格俯视图
        self.layout.addWidget(QLabel("<b>领地网格</b>"))
        self.grid = TerritoryGridWidget(t, self.manager.config)
        self.layout.addWidget(self.grid, 1)

        # 建筑统计
        placed = self.manager.build_mgr.placed(t)
        btext = "、".join(
            f"{self.manager.config.get_building(bid)['name']}({lvl})"
            for _r, _c, bid, lvl in placed
        ) or "（暂无建筑）"
        self.layout.addWidget(QLabel(f"建筑（{len(placed)}）：{btext}"))

        # 按钮行
        btn_row = QHBoxLayout()
        build_btn = QPushButton("建造 / 升级")
        build_btn.clicked.connect(self._on_build)
        defense_btn = QPushButton("防御 / 阵眼")
        defense_btn.clicked.connect(self._on_defense)
        upgrade_btn = QPushButton("升阶领地")
        upgrade_btn.clicked.connect(self._on_upgrade)
        collect_btn = QPushButton("收取灵石")
        collect_btn.clicked.connect(self._on_collect)
        hist_btn = QPushButton("领地史册")
        hist_btn.clicked.connect(self._on_history)
        for b in (build_btn, defense_btn, upgrade_btn, collect_btn, hist_btn):
            btn_row.addWidget(b)
        self.layout.addLayout(btn_row)

    def _on_build(self):
        dlg = TerritoryBuildDialog(self.manager, parent=self)
        dlg.finished.connect(lambda _: self._build())
        dlg.exec()

    def _on_defense(self):
        dlg = TerritoryDefenseDialog(self.manager, parent=self)
        dlg.finished.connect(lambda _: self._build())
        dlg.exec()

    def _on_upgrade(self):
        ok, msg = self.manager.upgrade_tier()
        QMessageBox.information(self, "升阶领地", msg)
        if ok:
            self._build()

    def _on_collect(self):
        t = self.manager.get_territory()
        ok, msg = self.manager.withdraw(t.get("treasury", 0))
        QMessageBox.information(self, "收取灵石", msg)
        if ok:
            self._build()

    def _on_history(self):
        t = self.manager.get_territory()
        text = "\n".join(
            f"第{rec['month']}月：{rec['text']}" for rec in t.get("history", [])
        ) or "暂无记录。"
        box = QTextEdit()
        box.setPlainText(text)
        box.setReadOnly(True)
        dlg = QDialog(self)
        dlg.setWindowTitle("领地史册")
        dlg.resize(420, 360)
        dl = QVBoxLayout(dlg)
        dl.addWidget(box)
        dlg.exec()
