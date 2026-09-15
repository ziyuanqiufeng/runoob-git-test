# -*- coding: utf-8 -*-
"""天道反噬与生态平衡状态弹窗（维度④）。

展示天道注视值与等级、各领地灵脉枯竭度，并提供消除注视的方式
（散财 / 行善 / 隐世）。与「天道追杀」（突破触发）不同，本模块的注视
由战力 / 财富暴涨触发，玩家可主动消弭。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QFrame, QTextEdit, QHBoxLayout,
)
from PySide6.QtCore import Qt


class HeavenRetributionDialog(QDialog):
    """展示天道反噬状态并提供消灾手段。"""

    DONATE_COST = 500  # 散财消灾消耗的灵石

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.mgr = engine.heaven_retribution_manager
        self.setWindowTitle("天道反噬")
        self.resize(500, 480)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        status = self.mgr.get_status()
        gaze = status["gaze"]
        level = status["gaze_level"] or "无"
        layout.addWidget(self._bar("天道注视", gaze, 100, "#8e44ad"))
        layout.addWidget(QLabel(f"当前等级：{level}"))

        # 灵脉枯竭
        layout.addWidget(self._section_label("领地灵脉枯竭"))
        terr = getattr(self.player, "territory", None)
        terrs = [terr] if isinstance(terr, dict) else (terr or [])
        if not terrs:
            layout.addWidget(QLabel("（尚未占据领地）"))
        else:
            for t in terrs:
                dep = int(t.get("depletion", 0) or 0)
                layout.addWidget(self._bar(f"【{t.get('name', '领地')}】枯竭", dep, 100, "#d35400"))

        # 消除方式
        layout.addWidget(self._section_label("消弭天道注视"))
        relief_row = QHBoxLayout()
        donate = QPushButton(f"散财消灾（-{self.DONATE_COST} 灵石）")
        donate.clicked.connect(self._on_donate)
        good = QPushButton("行善积德")
        good.clicked.connect(lambda: self._on_relief("good_deed"))
        seclude = QPushButton("隐世闭关")
        seclude.clicked.connect(lambda: self._on_relief("seclude"))
        relief_row.addWidget(donate)
        relief_row.addWidget(good)
        relief_row.addWidget(seclude)
        layout.addLayout(relief_row)

        # 天道反噬事件（当前注视下可能触发的事件池）
        layout.addWidget(self._section_label("天道反噬事件（外出时可能降临）"))
        eligible = status.get("eligible_events", [])
        chance = int(100 * (status.get("event_chance", 0) or 0))
        if eligible:
            layout.addWidget(QLabel(f"触发概率：约 {chance}%/次外出"))
            for ev in eligible:
                layout.addWidget(QLabel(f"· {ev.get('name', '未知')}：{ev.get('desc', '')}"))
        else:
            layout.addWidget(QLabel("（天道未注视，暂无反噬之虞）"))

        layout.addWidget(self._section_label("说明"))
        layout.addWidget(self._box(
            "战力或财富短时间暴涨会惊动天道，招致无妄之灾、坊市拒交易、"
            "乃至杀人夺宝。散财、行善、隐世皆可削减注视。\n"
            "领地过度抽取灵气将致灵脉枯竭，产出归零并引来地脉怨气化形攻城。"
        ))

        close = QPushButton("了然")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _on_donate(self):
        if self.player.count_item("spirit_stone") < self.DONATE_COST:
            self.engine.notify("[yellow]灵石不足，无法散财消灾。")
            return
        self.player.consume_items("spirit_stone", self.DONATE_COST)
        self.mgr.relieve("donate")
        self._refresh()

    def _on_relief(self, method):
        self.mgr.relieve(method)
        self._refresh()

    def _refresh(self):
        """消灾后清空并重建界面以刷新数值。"""
        for i in reversed(range(self.layout().count())):
            item = self.layout().itemAt(i)
            w = item.widget()
            if w:
                w.deleteLater()
        self._build()

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
        box.setFixedHeight(70)
        return box
