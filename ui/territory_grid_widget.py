# -*- coding: utf-8 -*-
"""领地网格控件（F-02）。

自定义 QWidget，绘制 N×M 网格；每个格子根据是否有建筑上色，并支持点击
选中格子（cell_clicked 信号携带行列坐标）。用于领地总览与建造放置。
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
)


# 建筑类别 → 颜色（浅色主题，文字深）
_CATEGORY_COLORS = {
    "production": QColor(46, 204, 113),    # 绿：生产
    "economy": QColor(241, 196, 15),       # 金：经济
    "defense": QColor(231, 76, 60),        # 红：防御
    "formation": QColor(52, 152, 219),     # 蓝：阵眼
    "none": QColor(149, 165, 166),         # 灰：占位
}


class TerritoryGridWidget(QWidget):
    """领地网格绘制控件。"""

    cell_clicked = Signal(int, int)  # (row, col)

    def __init__(self, territory=None, config=None, parent=None):
        super().__init__(parent)
        self.territory = territory
        self.config = config
        self.selected = None  # (row, col)
        self.cell_size = 48
        self.setMinimumSize(8 * (self.cell_size + 4), 8 * (self.cell_size + 4))
        self.setMouseTracking(True)

    def set_territory(self, territory, config=None):
        self.territory = territory
        if config is not None:
            self.config = config
        self.selected = None
        self._update_size()
        self.update()

    def _update_size(self):
        if not self.territory:
            return
        grid = self.territory["grid"]
        w = grid["cols"] * (self.cell_size + 4) + 8
        h = grid["rows"] * (self.cell_size + 4) + 8
        self.setMinimumSize(w, h)
        self.resize(w, h)

    def _cell_rect(self, r, c):
        x = 4 + c * (self.cell_size + 4)
        y = 4 + r * (self.cell_size + 4)
        return x, y, self.cell_size, self.cell_size

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 淡雅渐变背景
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(245, 247, 250))
        gradient.setColorAt(1, QColor(235, 240, 245))
        painter.fillRect(self.rect(), gradient)

        if not self.territory:
            painter.setPen(QPen(QColor(44, 62, 80)))
            painter.setFont(QFont("Microsoft YaHei", 12))
            painter.drawText(self.rect(), Qt.AlignCenter, "尚未占据领地")
            painter.end()
            return

        grid = self.territory["grid"]
        font = QFont("Microsoft YaHei", 9)
        painter.setFont(font)

        for r in range(grid["rows"]):
            for c in range(grid["cols"]):
                x, y, w, h = self._cell_rect(r, c)
                cell = grid["cells"][r][c]
                color = QColor(255, 255, 255)
                label = ""
                if cell:
                    b = self.config.get_building(cell["building_id"]) if self.config else None
                    cat = b.get("category", "none") if b else "none"
                    color = _CATEGORY_COLORS.get(cat, _CATEGORY_COLORS["none"])
                    label = (b["name"] if b else cell["building_id"]) + f"\nLv{cell['level']}"
                # 选中高亮
                if self.selected == (r, c):
                    pen = QPen(QColor(44, 62, 80), 3)
                else:
                    pen = QPen(QColor(189, 195, 199), 1)
                painter.setPen(pen)
                painter.setBrush(QBrush(color.lighter(150) if cell else color))
                painter.drawRoundedRect(x, y, w, h, 6, 6)
                if label:
                    painter.setPen(QPen(QColor(44, 62, 80)))
                    painter.drawText(x, y, w, h, Qt.AlignCenter, label)

        painter.end()

    def mousePressEvent(self, event):
        if not self.territory:
            return
        grid = self.territory["grid"]
        for r in range(grid["rows"]):
            for c in range(grid["cols"]):
                x, y, w, h = self._cell_rect(r, c)
                if x <= event.pos().x() <= x + w and y <= event.pos().y() <= y + h:
                    self.selected = (r, c)
                    self.update()
                    self.cell_clicked.emit(r, c)
                    return
