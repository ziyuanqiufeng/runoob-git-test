# -*- coding: utf-8 -*-
"""红尘炼心 / 入世弹窗（维度②）。

展示当前是否入世、历练月数、道心/心魔、红尘羁绊与待了断的情劫；
提供「入世历练」「归隐出尘」「历红尘」「了却情劫」四项动作。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFrame, QTextEdit,
    QHBoxLayout, QMessageBox, QScrollArea, QWidget,
)
from PySide6.QtCore import Qt


class RedDustDialog(QDialog):
    """红尘炼心交互弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.mgr = engine.red_dust_manager
        self.setWindowTitle("红尘炼心")
        self.resize(540, 560)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self._layout = QVBoxLayout(inner)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        status = self.mgr.get_status()

        # 入世状态
        if status["active"]:
            self._layout.addWidget(QLabel(
                f"🌆 你正入世历练（已 {status['months']} 月）。于凡尘中淬炼心境。"
            ))
        else:
            self._layout.addWidget(QLabel("🏔 你暂未入世，闭关清修之中。"))

        # 道心 / 心魔
        self._layout.addWidget(self._bar(
            "道心", status["mental_state"], 100, "#27ae60"
        ))
        self._layout.addWidget(self._bar(
            "心魔", status["heart_demon"], 100, "#c0392b"
        ))

        # 红尘羁绊 + 共鸣
        self._layout.addWidget(self._section_label("红尘羁绊 · 共鸣"))
        resonances = status.get("resonances", [])
        if resonances:
            for r in resonances:
                bname = r.get("name", r.get("type", "羁绊"))
                self._layout.addWidget(QLabel(
                    f"· {bname}：亲密度 {r.get('intimacy', 0)}"
                ))
                res = r.get("resonance")
                nxt = r.get("next")
                if res:
                    self._layout.addWidget(QLabel(
                        f"　↳ 共鸣【{res.get('name', '')}】{res.get('desc', '')}"
                    ))
                elif nxt:
                    gap = max(0, nxt.get("min_intimacy", 0) - r.get("intimacy", 0))
                    self._layout.addWidget(QLabel(
                        f"　↳ 距共鸣「{nxt.get('name', '')}」尚差 {gap} 亲密度"
                    ))
                else:
                    self._layout.addWidget(QLabel("　↳ 已臻至情深义重，再无更高共鸣"))
                if status["active"]:
                    warm_btn = QPushButton(
                        f"温养（{status['warmth'].get('cost_count', 0)}灵石 +"
                        f"{status['warmth'].get('intimacy_gain', 0)}亲密度）"
                    )
                    warm_btn.clicked.connect(
                        lambda _checked, bt=r.get("type"): self._on_warm(bt)
                    )
                    self._layout.addWidget(warm_btn)
        else:
            self._layout.addWidget(QLabel("（暂无羁绊，入世后可于红尘中结缘）"))

        # 待了断情劫
        pending = status["pending_qingjie"]
        if pending:
            self._layout.addWidget(self._section_label("情劫 · 待了断"))
            self._layout.addWidget(QLabel(
                f"⚠ {pending.get('name', '')}：{pending.get('description', '')}"
            ))
            for c in pending.get("choices", []):
                btn = QPushButton(c.get("text", "抉择"))
                btn.clicked.connect(
                    lambda _checked, cid=c.get("id"): self._on_qingjie(cid)
                )
                self._layout.addWidget(btn)

        # 动作按钮
        self._layout.addWidget(self._section_label("历练"))
        if status["active"]:
            exit_btn = QPushButton("归隐出尘（沉淀心境）")
            exit_btn.clicked.connect(self._on_exit)
            self._layout.addWidget(exit_btn)
            exp_btn = QPushButton("历红尘（主动经历一事）")
            exp_btn.clicked.connect(self._on_experience)
            self._layout.addWidget(exp_btn)
        else:
            enter_btn = QPushButton("入世历练")
            enter_btn.clicked.connect(self._on_enter)
            self._layout.addWidget(enter_btn)

        close = QPushButton("合卷")
        close.clicked.connect(self.accept)
        self._layout.addWidget(close)

    def _on_enter(self):
        ok, msg = self.engine.enter_red_dust()
        QMessageBox.information(self, "入世", msg)
        if ok:
            self._refresh()

    def _on_exit(self):
        ok, msg = self.engine.exit_red_dust()
        QMessageBox.information(self, "出尘", msg)
        if ok:
            self._refresh()

    def _on_experience(self):
        ok, msg = self.engine.red_dust_experience()
        QMessageBox.information(self, "历红尘", msg)
        self._refresh()

    def _on_qingjie(self, choice_id):
        ok, msg = self.engine.apply_qingjie_choice(choice_id)
        QMessageBox.information(self, "情劫", msg)
        if ok:
            self._refresh()

    def _on_warm(self, bond_type):
        ok, msg = self.engine.red_dust_warm(bond_type)
        QMessageBox.information(self, "温养羁绊", msg)
        if ok:
            self._refresh()

    def _refresh(self):
        # 清空并重建
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
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
