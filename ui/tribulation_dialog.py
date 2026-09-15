import random

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient


class TribulationCanvas(QWidget):
    """渡劫过程画布：雷劫/天劫动画或心魔氛围背景。"""

    def __init__(self, tribulation_name, is_heart_demon=False, parent=None):
        super().__init__(parent)
        self.tribulation_name = tribulation_name
        self.is_heart_demon = is_heart_demon
        self.setMinimumSize(480, 420)
        self.frame = 0
        self.lightning_bolts = []
        self.flash_alpha = 0
        self.heart_demon_labels = []

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next_frame)
        self.timer.start(80)

        if self.is_heart_demon:
            self._init_heart_demons()

    def _init_heart_demons(self):
        """心魔氛围：漂浮的执念文字。"""
        texts = ["心魔", "执念", "幻象", "恐惧", "欲望", "因果", "轮回"]
        for text in texts:
            label = QLabel(text, self)
            alpha = random.randint(50, 180)
            label.setStyleSheet(
                f"color: rgba(200, 120, 255, {alpha}); "
                f"font: bold {random.randint(18, 30)}px 'Microsoft YaHei';"
            )
            label.adjustSize()
            start_x = random.randint(20, max(30, self.width() - label.width() - 20))
            start_y = random.randint(60, max(80, self.height() - label.height() - 20))
            label.move(start_x, start_y)
            label.show()
            self.heart_demon_labels.append(label)

            anim = QPropertyAnimation(label, b"pos", self)
            anim.setDuration(random.randint(2000, 4000))
            end_x = random.randint(20, max(30, self.width() - label.width() - 20))
            end_y = random.randint(60, max(80, self.height() - label.height() - 20))
            anim.setStartValue(QPoint(start_x, start_y))
            anim.setEndValue(QPoint(end_x, end_y))
            anim.setEasingCurve(QEasingCurve.InOutSine)
            anim.setLoopCount(-1)
            anim.start()

    def _next_frame(self):
        """每帧更新特效。"""
        self.frame += 1

        if self.is_heart_demon:
            if self.heart_demon_labels and random.random() < 0.12:
                label = random.choice(self.heart_demon_labels)
                alpha = random.randint(50, 200)
                label.setStyleSheet(
                    f"color: rgba({random.randint(180, 255)}, 80, {random.randint(180, 255)}, {alpha}); "
                    f"font: bold {random.randint(18, 30)}px 'Microsoft YaHei';"
                )
        else:
            if random.random() < 0.45:
                self._spawn_lightning()
            self.lightning_bolts = [
                (x, y, life - 1) for x, y, life in self.lightning_bolts if life > 1
            ]
            self.flash_alpha = max(0, self.flash_alpha - 40)
            if random.random() < 0.08:
                self.flash_alpha = random.randint(60, 180)

        self.update()

    def _spawn_lightning(self):
        x = random.randint(60, self.width() - 60)
        y = random.randint(20, 100)
        self.lightning_bolts.append((x, y, random.randint(2, 5)))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self.is_heart_demon:
            gradient = QLinearGradient(0, 0, 0, h)
            gradient.setColorAt(0, QColor(25, 5, 35, 240))
            gradient.setColorAt(1, QColor(55, 15, 75, 240))
        else:
            gradient = QLinearGradient(0, 0, 0, h)
            gradient.setColorAt(0, QColor(5, 10, 25, 240))
            gradient.setColorAt(1, QColor(25, 35, 60, 240))
        painter.fillRect(self.rect(), gradient)

        # 标题
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Microsoft YaHei", 24, QFont.Bold))
        painter.drawText(
            self.rect().adjusted(0, 30, 0, 0),
            Qt.AlignTop | Qt.AlignHCenter,
            f"【{self.tribulation_name}】",
        )

        if not self.is_heart_demon:
            for x, y, life in self.lightning_bolts:
                pen = QPen(QColor(220, 240, 255))
                pen.setWidth(random.randint(2, 5))
                painter.setPen(pen)
                segments = random.randint(2, 4)
                cur_x, cur_y = x, y
                for _ in range(segments):
                    next_x = cur_x + random.randint(-35, 35)
                    next_y = cur_y + random.randint(40, 100)
                    painter.drawLine(cur_x, cur_y, next_x, next_y)
                    cur_x, cur_y = next_x, next_y
                painter.setPen(QPen(QColor(100, 180, 255, 120), 8))
                painter.drawLine(x, y, cur_x, cur_y)

            if self.flash_alpha > 0:
                painter.fillRect(self.rect(), QColor(255, 255, 255, self.flash_alpha))

        painter.end()


class TribulationDialog(QDialog):
    """
    渡劫过程弹窗：
    - 雷劫/天劫：播放动画，自动关闭。
    - 元婴心魔劫：显示小游戏，选择“破幻/守心/斩念”，正确则提升成功率。
    """

    # 心魔选项：key 为按钮文本，value 为描述
    HEART_DEMON_OPTIONS = {
        "破幻": "以道心识破虚妄",
        "守心": "固守本心不为所动",
        "斩念": "挥剑斩断执念",
    }

    def __init__(self, engine, tribulation_name, base_rate, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.tribulation_name = tribulation_name
        self.base_rate = base_rate
        self.is_heart_demon = "心魔" in tribulation_name
        self.setModal(True)
        self.resize(520, 620)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # 动画/氛围画布
        self.canvas = TribulationCanvas(tribulation_name, self.is_heart_demon, self)
        self.layout.addWidget(self.canvas)

        # 状态说明文字
        self.status_label = QLabel(self._status_text(), self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "color: white; font: 15px 'Microsoft YaHei'; background-color: rgba(0,0,0,180); padding: 8px;"
        )
        self.layout.addWidget(self.status_label)

        # 心魔小游戏按钮区
        self.game_widget = QWidget(self)
        self.game_layout = QHBoxLayout(self.game_widget)
        self.game_layout.setContentsMargins(10, 5, 10, 5)
        self.option_buttons = []
        if self.is_heart_demon:
            # 随机设定一个正确选项
            self.correct_option = random.choice(list(self.HEART_DEMON_OPTIONS.keys()))
            for option, desc in self.HEART_DEMON_OPTIONS.items():
                btn = QPushButton(f"{option}\n{desc}", self.game_widget)
                btn.setStyleSheet(
                    "color: white; background-color: rgba(80, 30, 100, 200); "
                    "font: 14px 'Microsoft YaHei'; padding: 8px;"
                )
                btn.setToolTip(desc)
                btn.clicked.connect(lambda checked, op=option: self._on_heart_demon_choice(op))
                self.option_buttons.append(btn)
                self.game_layout.addWidget(btn)
            self.game_widget.show()
        else:
            self.game_widget.hide()
        self.layout.addWidget(self.game_widget)

        # 倒计时自动关闭（雷劫 2.5 秒，心魔由玩家操作）
        if not self.is_heart_demon:
            self._countdown = 32  # 80ms * 32 ≈ 2.56 秒
            self._close_timer = QTimer(self)
            self._close_timer.timeout.connect(self._tick)
            self._close_timer.start(80)

    def _status_text(self):
        if self.is_heart_demon:
            return (
                f"当前渡劫成功率：{int(self.base_rate * 100)}%\n"
                "心魔幻象丛生，请选择应对之法。选对可提升成功率，选错则无加成。"
            )
        return "劫云汇聚，雷光轰鸣，天道考验降临……"

    def _tick(self):
        """雷劫/天劫自动关闭倒计时。"""
        self._countdown -= 1
        if self._countdown <= 0:
            self._close_timer.stop()
            self.accept()

    def _on_heart_demon_choice(self, option):
        """玩家选择心魔应对选项后的处理。"""
        for btn in self.option_buttons:
            btn.setEnabled(False)

        if option == self.correct_option:
            bonus = 0.10
            result_text = (
                f"你以【{option}】破开心魔幻象，道心更加通明，"
                f"渡劫成功率提升 {int(bonus * 100)}%！"
            )
        else:
            bonus = 0.0
            result_text = (
                f"你选择了【{option}】，但未能撼动心魔根本，"
                f"正确之法应为【{self.correct_option}】。"
            )

        # 把加成写回引擎，供后续判定使用
        self.engine.tribulation_bonus = bonus
        self.status_label.setText(
            f"{result_text}\n当前渡劫成功率：{int(min(0.95, self.base_rate + bonus) * 100)}%"
        )

        # 1 秒后自动关闭，让玩家看清结果
        QTimer.singleShot(1000, self.accept)


class ResultCanvas(QWidget):
    """渡劫结果画布：成功祥云 / 失败血雷。"""

    def __init__(self, tribulation_name, success, parent=None):
        super().__init__(parent)
        self.tribulation_name = tribulation_name
        self.success = success
        self.setMinimumSize(480, 420)
        self.frame = 0
        self.lightning_bolts = []
        self.flash_alpha = 0
        self.cloud_y = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next_frame)
        self.timer.start(80)

    def _next_frame(self):
        self.frame += 1
        self.cloud_y = (self.cloud_y + 1) % 40

        if not self.success:
            if random.random() < 0.5:
                self._spawn_blood_lightning()
            self.lightning_bolts = [
                (x, y, life - 1) for x, y, life in self.lightning_bolts if life > 1
            ]
            self.flash_alpha = max(0, self.flash_alpha - 35)
            if random.random() < 0.12:
                self.flash_alpha = random.randint(60, 160)

        self.update()

    def _spawn_blood_lightning(self):
        x = random.randint(60, self.width() - 60)
        y = random.randint(20, 100)
        self.lightning_bolts.append((x, y, random.randint(2, 5)))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self.success:
            # 成功：金橙渐变 + 祥云
            gradient = QLinearGradient(0, 0, 0, h)
            gradient.setColorAt(0, QColor(40, 30, 10, 240))
            gradient.setColorAt(1, QColor(100, 80, 30, 240))
            painter.fillRect(self.rect(), gradient)

            # 光柱
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 220, 100, 60))
            painter.drawRect(int(w * 0.3), 0, int(w * 0.4), h)
            painter.setBrush(QColor(255, 240, 150, 90))
            painter.drawRect(int(w * 0.4), 0, int(w * 0.2), h)

            # 祥云（用半透明椭圆模拟）
            painter.setBrush(QColor(255, 255, 220, 120))
            for i in range(5):
                cx = int(w * (0.2 + i * 0.15))
                cy = int(h * 0.75 + (i % 2) * 20 - self.cloud_y)
                painter.drawEllipse(cx, cy, 80, 40)
        else:
            # 失败：血红渐变 + 血雷
            gradient = QLinearGradient(0, 0, 0, h)
            gradient.setColorAt(0, QColor(40, 5, 5, 240))
            gradient.setColorAt(1, QColor(90, 10, 10, 240))
            painter.fillRect(self.rect(), gradient)

            for x, y, life in self.lightning_bolts:
                pen = QPen(QColor(255, 60, 60))
                pen.setWidth(random.randint(2, 5))
                painter.setPen(pen)
                cur_x, cur_y = x, y
                for _ in range(random.randint(2, 4)):
                    next_x = cur_x + random.randint(-35, 35)
                    next_y = cur_y + random.randint(40, 100)
                    painter.drawLine(cur_x, cur_y, next_x, next_y)
                    cur_x, cur_y = next_x, next_y

            if self.flash_alpha > 0:
                painter.fillRect(self.rect(), QColor(150, 20, 20, self.flash_alpha))

        # 标题
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Microsoft YaHei", 28, QFont.Bold))
        title = "渡劫成功" if self.success else "渡劫失败"
        painter.drawText(self.rect().adjusted(0, 40, 0, 0), Qt.AlignTop | Qt.AlignHCenter, title)

        # 劫名
        painter.setFont(QFont("Microsoft YaHei", 14))
        painter.setPen(QPen(QColor(220, 220, 220)))
        sub = f"【{self.tribulation_name}】"
        painter.drawText(self.rect().adjusted(0, 90, 0, 0), Qt.AlignTop | Qt.AlignHCenter, sub)

        painter.end()


class TribulationResultDialog(QDialog):
    """渡劫结果弹窗：根据成功/失败播放不同结果动画。"""

    def __init__(self, tribulation_name, success, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.resize(520, 620)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = ResultCanvas(tribulation_name, success, self)
        layout.addWidget(self.canvas)

        hint = "祥云普照，大道可期" if success else "血色雷暴，根基受创"
        self.status_label = QLabel(hint, self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "color: white; font: 16px 'Microsoft YaHei'; background-color: rgba(0,0,0,180); padding: 8px;"
        )
        layout.addWidget(self.status_label)

        # 失败时模拟咳血震动：在弹窗显示后启动
        self._need_shake = not success

        # 2.5 秒后自动关闭
        self._countdown = 32
        self._close_timer = QTimer(self)
        self._close_timer.timeout.connect(self._tick)
        self._close_timer.start(80)

    def showEvent(self, event):
        """弹窗显示后再启动震动，确保基准位置正确。"""
        super().showEvent(event)
        if getattr(self, "_need_shake", False):
            self._need_shake = False
            self._shake_animation()

    def _shake_animation(self):
        """失败时短暂震动弹窗，模拟被雷劫劈中。"""
        self._shake_anim = QPropertyAnimation(self, b"pos", self)
        self._shake_anim.setDuration(300)
        base = self.pos()
        self._shake_anim.setKeyValueAt(0.0, base)
        self._shake_anim.setKeyValueAt(0.2, base + QPoint(-8, 6))
        self._shake_anim.setKeyValueAt(0.4, base + QPoint(8, -6))
        self._shake_anim.setKeyValueAt(0.6, base + QPoint(-6, 8))
        self._shake_anim.setKeyValueAt(0.8, base + QPoint(6, -8))
        self._shake_anim.setKeyValueAt(1.0, base)
        self._shake_anim.setLoopCount(2)
        self._shake_anim.start()

    def _tick(self):
        self._countdown -= 1
        if self._countdown <= 0:
            self._close_timer.stop()
            self.accept()
