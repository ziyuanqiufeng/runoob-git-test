# -*- coding: utf-8 -*-
"""修行年谱弹窗：展示生涯大事记（ChronicleManager 数据的可视化）。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QLabel, QListWidgetItem,
)

from game.chronicle import ChronicleManager

# 分类 → 展示名/颜色
_CATEGORY_META = {
    "breakthrough": ("突破", "#b8860b"),
    "ending": ("结局", "#8e2d2d"),
    "achievement": ("成就", "#5b2d8e"),
    "quest": ("任务", "#185fa5"),
    "event": ("经历", "#444441"),
}


class CareerDialog(QDialog):
    """修行年谱：按时间倒序展示生涯大事，顶部显示生涯摘要。"""

    def __init__(self, player, world, parent=None):
        super().__init__(parent)
        self.setWindowTitle("修行年谱")
        self.resize(520, 480)
        self.manager = ChronicleManager(player, world)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        # 生涯摘要
        summary = self.manager.get_summary()
        cats = " · ".join(
            f"{_CATEGORY_META.get(cid, (cid, ''))[0]} {n}"
            for cid, n in sorted(summary.get("categories", {}).items())
        )
        summary_label = QLabel(
            f"生涯共记录 <b>{summary.get('total', 0)}</b> 件大事"
            + (f"（{cats}）" if cats else "")
        )
        summary_label.setStyleSheet("color: #2c3e50; font-size: 13px;")
        layout.addWidget(summary_label)

        # 年谱列表（倒序：最新在上）
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                font-size: 13px;
                padding: 6px;
            }
        """)
        entries = self.manager.get_entries(limit=200)
        entries = list(reversed(entries))
        if not entries:
            self.list_widget.addItem("尚无记录——去游历、突破，写下你的第一笔吧。")
            return

        # 跨世分组：以「第 N 世启程」（reincarnation 类）为界切分各世；
        # 单世玩家（无启程条目）保持平铺，不加分组头
        lives = []          # [(label 或 None, [entries])]
        current = []
        life_no = 0
        for entry in entries:
            text = entry.get("text", "")
            if (entry.get("category") == "reincarnation"
                    and "世启程" in text):
                life_no += 1
                lives.append((None, current))
                current = [entry]
            else:
                current.append(entry)
        lives.append((None, current))
        # 编号：启程条目「第 N 世启程」标记的是第 N+1 段人生（N=转世次数）
        labeled = []
        seg = 1
        for label, seg_entries in lives:
            if seg_entries and label is None and seg > 1:
                label = f"第 {seg} 世"
            labeled.append((label, seg_entries))
            seg += 1

        multi = life_no > 0
        for label, seg_entries in labeled:
            if multi and label:
                sep = QListWidgetItem(f"━━━━  ◈  {label}  ◈  ━━━━")
                sep.setForeground(QColor("#8a7ae8"))
                sep.setTextAlignment(Qt.AlignCenter)
                self.list_widget.addItem(sep)
            for entry in seg_entries:
                meta = _CATEGORY_META.get(entry.get("category", "event"),
                                          ("经历", "#444441"))
                text = (f"修真第 {entry.get('year', '?')} 年 "
                        f"{entry.get('month', '?')} 月 · "
                        f"[{meta[0]}] {entry.get('text', '')}")
                if entry.get("age") is not None:
                    text += f"（时年 {entry['age']} 岁）"
                item = QListWidgetItem(text)
                item.setForeground(QColor(meta[1]))
                self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)
