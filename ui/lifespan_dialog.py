# -*- coding: utf-8 -*-
"""寿元与轮回晚年弹窗（维度⑤）。

展示当前寿元、是否临近大限、已安排的后事、残魂 / 器灵状态与前世遗物；
提供「安排坐化后事」与「凝为残魂化身」两项动作。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFrame, QTextEdit,
    QCheckBox, QHBoxLayout, QMessageBox,
)
from PySide6.QtCore import Qt


class LifespanDialog(QDialog):
    """寿元与轮回晚年交互弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.mgr = engine.lifespan_manager
        self.setWindowTitle("寿元·轮回")
        self.resize(520, 540)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        status = self.mgr.get_status()

        layout.addWidget(self._bar(
            "寿元", status["age"], status["max_lifespan"], "#2980b9"
        ))
        if status["is_near_end"]:
            layout.addWidget(QLabel("⏳ 已临近大限，可安排坐化后事。"))
        else:
            remain = status["max_lifespan"] - status["age"]
            layout.addWidget(QLabel(f"尚可修行约 {remain} 年。"))

        # 坐化安排
        layout.addWidget(self._section_label("坐化后事安排"))
        if status["sit_pending"]:
            arranged = "、".join(status["arrangements"].keys()) if status["arrangements"] else "（已安排）"
            layout.addWidget(QLabel(f"✓ 已安排：{arranged}"))
        else:
            arrangements = self.mgr.config.get_sit().get("arrangements", {})
            self._checks = {}
            for key, spec in arrangements.items():
                cb = QCheckBox(f"{spec.get('name', key)}：{spec.get('desc', '')}")
                self._checks[key] = cb
                layout.addWidget(cb)
            sit_btn = QPushButton("安排坐化")
            sit_btn.clicked.connect(self._on_arrange_sit)
            layout.addWidget(sit_btn)

        # 残魂 / 器灵化身
        layout.addWidget(self._section_label("残魂 / 器灵化身"))
        if status["is_remnant"]:
            soul = status["remnant_soul"] or {}
            layout.addWidget(QLabel(
                f"🌟 你正以残魂之姿依附于「{soul.get('host_type', '未知')}」"
                f"（已存续 {status['remnant_months']} 月），伺机重塑肉身。"
            ))
            form = status.get("remnant_form")
            if form:
                p = form.get("monthly_passive", {}) or {}
                bits = []
                if p.get("mental_delta"):
                    bits.append(f"道心{p['mental_delta']:+d}/月")
                if p.get("heart_delta"):
                    bits.append(f"心魔{p['heart_delta']:+d}/月")
                if p.get("reshape_bonus"):
                    bits.append(f"重塑+{p['reshape_bonus']:.0%}")
                passive_txt = "、".join(bits) if bits else "无月度被动"
                layout.addWidget(QLabel(
                    f"◈ 形态【{form.get('name', '残魂')}】：{form.get('desc', '')}（{passive_txt}）"
                ))
        elif self.mgr.can_become_remnant():
            remnant_btn = QPushButton("凝为残魂（依附本命法宝）")
            remnant_btn.clicked.connect(lambda: self._on_remnant("treasure"))
            layout.addWidget(remnant_btn)
            beast_btn = QPushButton("凝为残魂（依附灵兽）")
            beast_btn.clicked.connect(lambda: self._on_remnant("spirit_beast"))
            layout.addWidget(beast_btn)
        else:
            layout.addWidget(QLabel("神魂尚弱，暂无法凝为残魂（需更高境界）。"))

        # 前世遗物
        layout.addWidget(self._section_label("前世遗物"))
        relics = status["past_life_relics"]
        layout.addWidget(self._box(
            "、".join(r.get("name", str(r)) for r in relics) if relics else "（暂无）"
        ))

        # 前世遗物链（跨世累积，转世时授予链之加持）
        layout.addWidget(self._section_label("前世遗物链"))
        for ch in status.get("relic_chains_status", []):
            mark = "✓" if ch["complete"] else "◌"
            bits = []
            per = ch.get("per_link", {}) or {}
            if per:
                bits.append("每环：" + "、".join(f"{k}{v:+g}" for k, v in per.items()))
            sset = ch.get("set", {}) or {}
            if sset:
                bits.append("圆满：" + "、".join(f"{k}{v:+g}" for k, v in sset.items()))
            bonus_txt = "；".join(bits) if bits else "无加成"
            layout.addWidget(QLabel(
                f"{mark} 【{ch['name']}】已集 {ch['found']}/{ch['total']}　{bonus_txt}"
            ))
            layout.addWidget(QLabel(f"　{ch.get('desc', '')}"))

        close = QPushButton("合卷")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _on_arrange_sit(self):
        chosen = [k for k, cb in self._checks.items() if cb.isChecked()]
        if not chosen:
            QMessageBox.information(self, "坐化", "请至少选择一项后事安排。")
            return
        ok, msg = self.engine.sit_and_dissolve(chosen)
        QMessageBox.information(self, "坐化", msg)
        if ok:
            self._refresh()

    def _on_remnant(self, host_type):
        ok, msg = self.engine.become_remnant_soul(host_type)
        QMessageBox.information(self, "残魂", msg)
        if ok:
            self._refresh()

    def _refresh(self):
        for i in reversed(range(self.layout().count())):
            w = self.layout().itemAt(i).widget()
            if w:
                w.deleteLater()
        self._build()

    def _bar(self, name, value, max_v, color):
        pct = max(0, min(100, int(100 * value / max_v))) if max_v else 0
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
