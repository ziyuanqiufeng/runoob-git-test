# -*- coding: utf-8 -*-
"""领地防御 / 阵眼弹窗（F-02）。

展示五行阵眼覆盖情况、综合防御率与护阵能量；若有待结算的妖兽袭扰，
提供「迎战」按钮（调用注入的战斗回调，缺省为轻量模拟）并应用结算结果。
"""
import random

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QFrame,
)
from PySide6.QtCore import Qt

from game.territory_manager import FIVE_ELEMENTS


_ELEMENT_CN = {
    "fire": "离火", "water": "坎水", "wood": "震木",
    "metal": "乾金", "earth": "坤土",
}


class TerritoryDefenseDialog(QDialog):
    def __init__(self, manager, parent=None, combat_callback=None):
        super().__init__(parent)
        self.manager = manager
        self.territory = manager.get_territory()
        self.combat_callback = combat_callback  # 可选：真实战斗函数 -> bool(win)
        self.setWindowTitle("领地防御与阵眼")
        self.resize(560, 460)
        self.layout = QVBoxLayout(self)
        self._build()

    def _build(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        dmgr = self.manager.defense_mgr
        covered = dmgr.formation_elements(self.territory)
        defense = dmgr.defense_rate(self.territory)
        synergy = dmgr.synergy_bonus(self.territory)

        header = QLabel(
            f"<b>领地防御</b>　综合防御率 {defense*100:.0f}%　"
            f"护阵能量 {self.territory.get('energy',0)}/{self.territory.get('max_energy',0)}　"
            f"阵眼协同 +{synergy*100:.0f}%"
        )
        header.setStyleSheet("padding:8px; background:#eef; border-radius:6px;")
        self.layout.addWidget(header)

        # 五行阵眼状态
        self.layout.addWidget(QLabel("<b>五行阵眼覆盖</b>"))
        eye_box = QFrame()
        eye_box.setFrameShape(QFrame.Box)
        eye_box.setStyleSheet("padding:8px; background:#fafafa;")
        ev = QVBoxLayout(eye_box)
        for elem in FIVE_ELEMENTS:
            on = elem in covered
            ev.addWidget(QLabel(
                f"{_ELEMENT_CN.get(elem, elem)}阵眼：{'✅ 已布置' if on else '⬜ 未布置'}"
            ))
        ev.addWidget(QLabel(
            "布置越多不同属性的阵眼，防御率加成越高（每属性 +3%）。"
        ))
        self.layout.addWidget(eye_box)

        # 袭扰状态
        if self.territory.get("pending_raid"):
            raid = self.territory["pending_raid"]
            raid_lbl = QLabel(
                f"<b style='color:#c0392b'>⚠ 妖兽袭扰：{raid['enemy_id']}</b>"
            )
            self.layout.addWidget(raid_lbl)
            fight_btn = QPushButton("迎战")
            fight_btn.clicked.connect(self._on_fight)
            self.layout.addWidget(fight_btn)
        else:
            self.layout.addWidget(QLabel("当前领地安宁，无袭扰。"))

        self.layout.addStretch(1)

    def _on_fight(self):
        raid = self.territory.get("pending_raid")
        if not raid:
            return
        if callable(self.combat_callback):
            win = bool(self.combat_callback(raid))
        else:
            win = self._simulate_win(raid)
        ok, msg = self.manager.defense_mgr.resolve_raid(self.territory, win)
        QMessageBox.information(self, "袭扰结算", msg)
        self._build()

    def _simulate_win(self, raid):
        """缺省轻量战斗模拟：以玩家境界为实力基准对抗来袭妖兽。"""
        order = self.manager.player.REALM_ORDER.get(self.manager.player.realm_id, 0)
        enemy = 18 + raid.get("strength_bonus", 0.0) * 10
        win_prob = max(0.05, min(0.95, 0.5 + (order - enemy) / 40.0))
        return random.random() < win_prob
