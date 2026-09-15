# -*- coding: utf-8 -*-
"""成就面板（F-06 扩展）：按品阶展示进度、隐藏成就脱敏与已获称号。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton
)
from PySide6.QtCore import Qt


class AchievementDialog(QDialog):
    """列出全部成就（分级 + 隐藏脱敏），顶部显示总进度与称号。"""

    # 品阶展示顺序与配色
    _TIER_ORDER = ["青铜", "白银", "黄金", "仙金", "无"]
    _TIER_COLORS = {
        "青铜": "#8c7853",
        "白银": "#9aa3ad",
        "黄金": "#c9a227",
        "仙金": "#e0b0ff",
        "无": "#888888",
    }

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("成就")
        self.resize(560, 560)

        layout = QVBoxLayout(self)

        summary = self.engine.achievement_manager.get_progress_summary()
        titles = summary["titles"]

        # 顶部总进度 + 称号
        header = QLabel(
            f"总进度：{summary['completed']} / {summary['total']}　"
            f"隐藏成就：{summary['hidden_completed']} / {summary['hidden_total']}"
        )
        header.setStyleSheet("font-weight: bold; font-size: 14px; padding: 4px;")
        layout.addWidget(header)

        title_text = "已获称号：" + ("、".join(titles) if titles else "无")
        title_label = QLabel(title_text)
        title_label.setStyleSheet("color: #b8860b; padding: 4px;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # 滚动区：按品阶分组
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignTop)

        by_tier = summary["by_tier"]
        ordered_tiers = [t for t in self._TIER_ORDER if t in by_tier]
        ordered_tiers += [t for t in by_tier if t not in ordered_tiers]

        for tier in ordered_tiers:
            stat = by_tier[tier]
            color = self._TIER_COLORS.get(tier, "#888888")
            tier_label = QLabel(f"【{tier}】  {stat['completed']} / {stat['total']}")
            tier_label.setStyleSheet(
                f"font-weight: bold; color: {color}; font-size: 13px; padding: 2px;"
            )
            content_layout.addWidget(tier_label)
            for item in summary["items"]:
                if item["tier"] != tier:
                    continue
                mark = "✓" if item["done"] else ("？" if item["hidden"] else "·")
                item_label = QLabel(f"  {mark} {item['name']} —— {item['desc']}")
                if item["done"]:
                    item_label.setStyleSheet("font-weight: bold; color: #2e7d32;")
                elif item["hidden"]:
                    item_label.setStyleSheet("color: #9e9e9e; font-style: italic;")
                content_layout.addWidget(item_label)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
