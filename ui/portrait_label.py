# -*- coding: utf-8 -*-
"""统一头像组件。

封装头像加载、圆形裁剪、边框颜色、大境界光效等逻辑，
供状态面板、战斗界面、对话界面复用。
"""
import os

from PySide6.QtWidgets import QLabel, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QColor, QPainter, QPainterPath


class PortraitLabel(QLabel):
    """可复用的圆形头像标签。"""

    def __init__(
        self,
        size=96,
        border_color="#95a5a6",
        border_width=3,
        placeholder_text="无头像",
        circular=True,
        parent=None,
    ):
        super().__init__(parent)
        self._size = size
        self._border_color = border_color
        self._border_width = border_width
        self._placeholder_text = placeholder_text
        self._circular = circular
        self._glow_active = False
        self._glow_color = "#f1c40f"
        self._pixmap = QPixmap()

        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self._apply_style()

    def _apply_style(self):
        """应用边框样式。"""
        radius = self._size // 2 if self._circular else 6
        self.setStyleSheet(
            f"border: {self._border_width}px solid {self._border_color}; "
            f"border-radius: {radius}px; background: #f0f0f0;"
        )

    def set_border_color(self, color):
        """设置边框颜色。"""
        self._border_color = color
        self._apply_style()

    def set_glow(self, active, color="#f1c40f"):
        """开启/关闭外发光效果。"""
        self._glow_active = active
        self._glow_color = color
        if active:
            glow = QGraphicsDropShadowEffect(self)
            glow.setColor(QColor(color))
            glow.setBlurRadius(20)
            glow.setOffset(0, 0)
            self.setGraphicsEffect(glow)
        else:
            self.setGraphicsEffect(None)

    def set_circular(self, circular):
        """切换圆形/圆角矩形裁剪。"""
        self._circular = circular
        self._apply_style()
        self.update()

    def load_portrait(self, portrait_path):
        """加载头像图片；文件不存在则显示占位文字。"""
        if not portrait_path or not os.path.exists(portrait_path):
            self._pixmap = QPixmap()
            # 同步 QLabel 内部 pixmap，使外部 pixmap() 调用返回一致状态
            self.setPixmap(self._pixmap)
            self.setText(self._placeholder_text)
            self.update()
            return

        pixmap = QPixmap(portrait_path)
        scaled = pixmap.scaled(
            self._size,
            self._size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        self._pixmap = scaled
        # 同步 QLabel 内部 pixmap，让测试和外部调用可通过 pixmap() 获取
        self.setPixmap(scaled)
        self.setText("")
        self.update()

    def paintEvent(self, event):
        """自定义绘制：实现圆形/圆角裁剪。"""
        if self._pixmap.isNull():
            # 无图片时走默认 QLabel 绘制（显示占位文字）
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 创建圆形或圆角矩形裁剪路径
        path = QPainterPath()
        radius = self._size // 2 if self._circular else 6
        rect = self.rect()
        if self._circular:
            path.addEllipse(rect)
        else:
            path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)

        # 绘制缩放后的头像
        painter.drawPixmap(rect, self._pixmap)

        # 绘制边框覆盖（Qt 样式表 border 在圆形裁剪时可能被遮住，需手动补绘）
        pen = painter.pen()
        pen.setColor(QColor(self._border_color))
        pen.setWidth(self._border_width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        if self._circular:
            # 边框居中绘制
            offset = self._border_width / 2
            painter.drawEllipse(
                rect.adjusted(
                    int(offset), int(offset),
                    -int(offset), -int(offset)
                )
            )
        else:
            painter.drawRoundedRect(rect, radius, radius)

        painter.end()
