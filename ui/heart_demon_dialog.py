# -*- coding: utf-8 -*-
"""心魔·道心状态弹窗（维度①）。

查看道心值 / 心魔值、性格标签（由心魔劫抉择塑造）、
天人合一顿悟资格，以及已领悟的心境特质。纯展示，无写操作。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFrame, QTextEdit,
)
from PySide6.QtCore import Qt


class HeartDemonDialog(QDialog):
    """展示玩家当前的心魔/道心内在状态。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.mgr = engine.mental_state_manager
        self.setWindowTitle("心魔·道心")
        self.resize(480, 460)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        p = self.player
        mgr = self.mgr

        layout.addWidget(self._bar("道心", p.mental_state, 100, "#27ae60"))
        layout.addWidget(self._bar("心魔", p.heart_demon, 100, "#c0392b"))

        # 心魔劫阈值提示
        threshold = mgr.config.get_heart_demon_tribulation().get("threshold", 60)
        if p.heart_demon >= threshold:
            warn = QLabel(
                f"⚠ 心魔值已达 {p.heart_demon}，大境界突破将强制触发心魔劫！"
            )
            warn.setStyleSheet("color:#c0392b; font-weight:bold;")
            layout.addWidget(warn)
        else:
            ok = QLabel(f"心魔 {p.heart_demon}/{threshold}，尚属安稳。")
            ok.setStyleSheet("color:#7f8c8d;")
            layout.addWidget(ok)

        # 天人合一资格
        unity = mgr.config.get_unity_enlightenment()
        min_ms = unity.get("min_mental_state", 80)
        if p.mental_state >= min_ms:
            unity_lbl = QLabel(
                f"✨ 道心已达 {p.mental_state}（≥{min_ms}），闭关有概率触发天人合一顿悟！"
            )
            unity_lbl.setStyleSheet("color:#8e44ad; font-weight:bold;")
        else:
            unity_lbl = QLabel(f"道心 {p.mental_state}/{min_ms}，未达天人合一之境。")
            unity_lbl.setStyleSheet("color:#7f8c8d;")
        layout.addWidget(unity_lbl)

        # 道境分层与被动（维度① 深化）
        realm = mgr.get_dao_realm_status()
        layout.addWidget(self._section_label("道境"))
        realm_lbl = QLabel(
            f"当前道境：【{realm['name']}】（道心 {realm['mental_state']}）"
        )
        realm_lbl.setStyleSheet("font-weight:bold;")
        layout.addWidget(realm_lbl)

        passive = realm.get("passive")
        if passive:
            pname = passive.get("name", "未知道境")
            pdesc = passive.get("desc", "")
            plbl = QLabel(f"◈ 道境被动【{pname}】：{pdesc}")
            plbl.setStyleSheet("color:#16a085; font-weight:bold;")
            plbl.setWordWrap(True)
            layout.addWidget(plbl)
        else:
            none_lbl = QLabel("（此道境无特殊被动，提升道心可入更高道境）")
            none_lbl.setStyleSheet("color:#7f8c8d;")
            layout.addWidget(none_lbl)

        next_tier = realm.get("next_tier")
        if next_tier:
            need = max(0, next_tier.get("min", 0) - realm["mental_state"])
            nxt_lbl = QLabel(
                f"距下一阶【{next_tier.get('name')}】（道心≥{next_tier.get('min')}）还需 {need} 点道心"
            )
            nxt_lbl.setStyleSheet("color:#8e44ad;")
            layout.addWidget(nxt_lbl)

        layout.addWidget(self._section_label("性格标签（由心魔劫抉择塑造）"))
        tags = getattr(p, "personality_tags", [])
        layout.addWidget(self._box("、".join(tags) if tags else "（暂无）"))

        layout.addWidget(self._section_label("心境特质"))
        traits = getattr(p, "mental_state_traits", [])
        layout.addWidget(self._box("、".join(traits) if traits else "（暂无）"))

        close = QPushButton("闭目凝神")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _bar(self, name, value, max_v, color):
        pct = max(0, min(100, int(100 * value / max_v)))
        filled = pct // 10
        bar = "█" * filled + "░" * (10 - filled)
        label = QLabel(f"{name}：[{bar}] {value}/{max_v}")
        label.setStyleSheet(f"color:{color}; font-family:monospace; font-size:13px;")
        return label

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight:bold; margin-top:8px;")
        return lbl

    def _box(self, text):
        box = QTextEdit()
        box.setPlainText(text)
        box.setReadOnly(True)
        box.setFixedHeight(38)
        return box
