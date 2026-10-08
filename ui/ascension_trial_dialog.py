# -*- coding: utf-8 -*-
"""天门试炼结算面板：三阶段逐段展示问心/渡雷/天门一跃的结果。

数据由引擎 _attempt_ascension 组装并经 __ASCENSION_TRIAL__:{json} 通知，
本面板为只读演出层，成败后续（结局弹窗/继续游戏）由既有流程处理。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
)
from PySide6.QtCore import Qt

# 结果徽标样式：通过/受损/失败/成功
_RESULT_STYLE = {
    "pass": ("✓ 通过", "#27ae60"),
    "wound": ("△ 道基不稳", "#8e44ad"),
    "fail": ("✗ 失败", "#c0392b"),
    "success": ("★ 跨越天门", "#f39c12"),
}

_OUTCOME_TEXT = {
    "ascend": ("白日飞升", "天门洞开，你位列仙班——这一世的修行，至此圆满。"),
    "survive": ("折戟天门", "兵解重创，道基犹存。整理行囊，天门仍为你而开。"),
    "ending": ("试炼终局", "天门之前，因果清算——这一世的道，止步于此。"),
}


class AscensionTrialDialog(QDialog):
    """天门试炼三阶段结算面板。"""

    def __init__(self, report, parent=None):
        super().__init__(parent)
        self.setWindowTitle("天门试炼")
        self.setModal(True)
        self.resize(460, 380)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("<h2>⚖ 天门试炼</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        stages = report.get("stages", []) or []
        for i, stage in enumerate(stages, start=1):
            result = stage.get("result", "pass")
            label_text, color = _RESULT_STYLE.get(
                result, ("·", "#7f8c8d")
            )
            rate = stage.get("rate")
            rate_text = f"（成功率 {rate}%）" if rate is not None else ""
            extras = []
            if stage.get("burn"):
                extras.append(f"燃灵石 {stage['burn']}")
            if stage.get("pill"):
                extras.append("飞升丹已服")
            extra_text = f"　{'、'.join(extras)}" if extras else ""
            row = QLabel(
                f"<b>第{i}关 · {stage.get('name', '')}</b>"
                f"　<span style='color:{color}; font-weight:bold;'>{label_text}</span>"
                f"<br><span style='color:#555;'>{stage.get('text', '')}"
                f"{rate_text}{extra_text}</span>"
            )
            row.setWordWrap(True)
            layout.addWidget(row)

        outcome = report.get("outcome", "survive")
        out_title, out_desc = _OUTCOME_TEXT.get(
            outcome, ("试炼结束", "")
        )
        out_color = {"ascend": "#f39c12", "survive": "#c0392b",
                     "ending": "#7f8c8d"}.get(outcome, "#333")
        summary = QLabel(
            f"<h3 style='color:{out_color};'>{out_title}</h3>"
            f"<span style='color:#555;'>{out_desc}</span>"
        )
        summary.setAlignment(Qt.AlignCenter)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("确认")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
