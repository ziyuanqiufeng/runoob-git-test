# -*- coding: utf-8 -*-
"""天下大事弹窗（F-04）：展示全局世界状态、活跃事件链与决策节点。

通过 engine.world_state_manager 读取全局状态，通过 engine.world_event_manager
读取活跃事件链；决策节点提供按钮，点击即调用 choose_chain_option 推进事件链。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PySide6.QtCore import Qt


_STATE_LABELS = {
    "lingqi": "灵气浓度",
    "safety": "世界安全度",
    "price_index": "物价系数",
    "npc_mood": "阵营态度",
    "dark_qi": "魔气浓度",
}

_STATE_BOUNDS = {
    "lingqi": (0.0, 300.0),
    "safety": (0.0, 200.0),
    "price_index": (0.0, 400.0),
    "npc_mood": (0.0, 100.0),
    "dark_qi": (0.0, 100.0),
}


class _StateBar(QFrame):
    """简单的标签 + 数值状态行（以颜色条近似展示）。"""

    def __init__(self, label, value, vmin=0.0, vmax=100.0, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        name = QLabel(label)
        name.setFixedWidth(80)
        name.setStyleSheet("font-size:12px; color:#2c3e50;")
        self._bar = QFrame()
        self._bar.setFixedHeight(14)
        self._bar.setStyleSheet("background-color:#e9ecef; border-radius:7px;")
        val = QLabel(f"{value:.1f}")
        val.setFixedWidth(60)
        val.setAlignment(Qt.AlignRight)
        val.setStyleSheet("font-size:12px; color:#2c3e50;")
        layout.addWidget(name)
        layout.addWidget(self._bar, 1)
        layout.addWidget(val)

    def set_value(self, value, vmin=0.0, vmax=100.0):
        ratio = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
        color = "#27ae60" if ratio > 0.6 else ("#f39c12" if ratio > 0.3 else "#e74c3c")
        self._bar.setStyleSheet(
            "background-color: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {color}, stop:{ratio:.2f} {color}, stop:{ratio:.2f} #e9ecef);"
            "border-radius:7px;"
        )


class WorldEventsDialog(QDialog):
    """天下大事弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("天下大事 · 世界动态")
        self.setMinimumSize(520, 480)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        title = QLabel("🌐 天下大事")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#2c3e50;")
        root.addWidget(title)

        # 全局世界状态
        state_frame = QFrame()
        state_frame.setStyleSheet(
            "QFrame{background-color:#f8f9fa; border:1px solid #dee2e6; "
            "border-radius:10px; padding:8px;}"
        )
        state_layout = QVBoxLayout(state_frame)
        state_layout.setContentsMargins(10, 8, 10, 8)
        state_layout.setSpacing(4)
        state_layout.addWidget(self._section_label("全局世界状态"))
        self._state_bars = {}
        for key, lab in _STATE_LABELS.items():
            vmin, vmax = _STATE_BOUNDS.get(key, (0.0, 100.0))
            bar = _StateBar(lab, 0.0, vmin, vmax)
            self._state_bars[key] = bar
            state_layout.addWidget(bar)
        self._tide_label = QLabel("")
        self._tide_label.setStyleSheet("font-size:12px; color:#7f8c8d;")
        state_layout.addWidget(self._tide_label)
        root.addWidget(state_frame)

        # 事件链区
        chain_frame = QFrame()
        chain_frame.setStyleSheet(
            "QFrame{background-color:#f8f9fa; border:1px solid #dee2e6; border-radius:10px;}"
        )
        chain_layout = QVBoxLayout(chain_frame)
        chain_layout.setContentsMargins(10, 8, 10, 8)
        chain_layout.setSpacing(6)
        chain_layout.addWidget(self._section_label("事件链 / 世界事件"))
        self._chain_area = QVBoxLayout()
        chain_layout.addLayout(self._chain_area)
        root.addWidget(chain_frame, 1)

        # 刷新按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet(
            "QPushButton{background-color:#3498db; color:white; border-radius:6px; "
            "padding:6px 16px;} QPushButton:hover{background-color:#2980b9;}"
        )
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(refresh_btn)
        root.addLayout(btn_row)

    @staticmethod
    def _section_label(text):
        lab = QLabel(text)
        lab.setStyleSheet(
            "font-weight:bold; font-size:13px; color:#2c3e50; "
            "border-bottom:1px solid #bdc3c7; padding-bottom:2px;"
        )
        return lab

    def refresh(self):
        summary = self.engine.world_state_manager.summary()
        for key, bar in self._state_bars.items():
            vmin, vmax = _STATE_BOUNDS.get(key, (0.0, 100.0))
            bar.set_value(summary.get(key, 0.0), vmin, vmax)
        self._tide_label.setText(
            f"灵气潮汐相位 {summary.get('tide_phase')} · 修炼倍率 "
            f"×{summary.get('tide_multiplier')}"
        )

        self._clear_layout(self._chain_area)
        chains = self.engine.world_event_manager.get_active_chains()
        if not chains:
            hint = QLabel("当前风平浪静，暂无重大事件链。")
            hint.setStyleSheet("font-size:12px; color:#7f8c8d;")
            self._chain_area.addWidget(hint)
        for ch in chains:
            self._chain_area.addWidget(self._build_chain_widget(ch))
        for ev in self.engine.world_event_manager.get_event_descriptions():
            lab = QLabel(f"· {ev['name']}（剩余 {ev['remaining_months']} 月）")
            lab.setStyleSheet("font-size:12px; color:#34495e;")
            self._chain_area.addWidget(lab)
        self._chain_area.addStretch()

    def _build_chain_widget(self, ch):
        w = QFrame()
        w.setStyleSheet(
            "QFrame{background-color:#ffffff; border:1px solid #ced6e0; "
            "border-radius:8px; padding:6px;}"
        )
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        header = QLabel(
            f"⚡ {ch['name']} — {ch['stage_name']}（剩余 {ch['remaining_months']} 月）"
        )
        header.setStyleSheet("font-weight:bold; font-size:13px; color:#c0392b;")
        layout.addWidget(header)
        if ch["awaiting_choice"]:
            layout.addWidget(QLabel("需要你的抉择："))
            for c in ch["choices"]:
                btn = QPushButton(c["text"])
                btn.setStyleSheet(
                    "QPushButton{background-color:#27ae60; color:white; "
                    "border-radius:6px; padding:4px 10px;} "
                    "QPushButton:hover{background-color:#219150;}"
                )
                btn.clicked.connect(
                    lambda _checked=False, cid=ch["id"], idx=c["index"]: self._choose(cid, idx)
                )
                layout.addWidget(btn)
        return w

    def _choose(self, chain_id, idx):
        self.engine.world_event_manager.choose_chain_option(chain_id, idx)
        self.refresh()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
