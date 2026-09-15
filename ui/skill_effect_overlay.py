from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QFont


class SkillEffectOverlay(QWidget):
    """技能特效覆盖层，显示在地图区域上方。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.hide()
        self._current_effect = None

    def show_sword_slash(self):
        """显示御剑术剑光特效。"""
        self._current_effect = "sword"
        self.show()
        self.update()
        self._fade_out(400)

    def show_thunder_flash(self):
        """显示掌心雷白屏闪烁特效。"""
        self._current_effect = "thunder"
        self.show()
        self.update()
        self._fade_out(250)

    def show_heal_glow(self):
        """显示治疗绿光特效。"""
        self._current_effect = "heal"
        self.show()
        self.update()
        self._fade_out(600)

    def _fade_out(self, duration):
        """简单延迟后隐藏。"""
        QTimer.singleShot(duration, self.hide)

    def paintEvent(self, event):
        """根据当前特效类型绘制。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        if self._current_effect == "thunder":
            # 白屏闪烁
            painter.fillRect(self.rect(), QColor(255, 255, 255, 180))

        elif self._current_effect == "heal":
            # 绿色光晕
            painter.fillRect(self.rect(), QColor(76, 175, 80, 80))
            painter.setPen(QPen(QColor(76, 175, 80), 4))
            painter.drawRect(10, 10, w - 20, h - 20)

        elif self._current_effect == "sword":
            # 剑光：一条从左上到右下的白色斜线
            pen = QPen(QColor(255, 255, 255))
            pen.setWidth(8)
            painter.setPen(pen)
            painter.drawLine(int(w * 0.2), int(h * 0.2), int(w * 0.8), int(h * 0.8))

            pen.setWidth(3)
            pen.setColor(QColor(200, 230, 255))
            painter.setPen(pen)
            painter.drawLine(int(w * 0.25), int(h * 0.15), int(w * 0.85), int(h * 0.75))

            # 文字
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont("Microsoft YaHei", 24, QFont.Bold))
            painter.drawText(self.rect(), Qt.AlignCenter, "御剑术")

        painter.end()
