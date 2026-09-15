import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QInputDialog,
    QMessageBox, QSpacerItem, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

from ui.save_select_dialog import SaveSelectDialog
from ui.settings_dialog import SettingsDialog


class LoginDialog(QDialog):
    """游戏启动主菜单：新的开始 / 选择存档 / 设置 / 退出。"""

    NEW_GAME = "new_game"
    LOAD = "load"
    SETTINGS = "settings"
    QUIT = "quit"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("问道长生")
        self.setFixedSize(420, 520)
        self.selected_action = None
        self.selected_slot = None
        self.new_slot_name = None
        self.recent_slot = self._load_recent_slot()
        self._bg_pixmap = self._load_background()
        self._setup_ui()

    def _load_background(self):
        """加载登录背景图；缺失则返回空 QPixmap（回退纯色）。"""
        for candidate in (
            os.path.join("assets", "maps", "world_2d.png"),
            os.path.join("assets", "maps", "world_3d.png"),
        ):
            if os.path.exists(candidate):
                pix = QPixmap(candidate)
                if not pix.isNull():
                    return pix
        return QPixmap()

    def paintEvent(self, event):
        """绘制背景图 + 半透明深色遮罩，保证按钮/文字可读。"""
        super().paintEvent(event)
        painter = QPainter(self)
        if not self._bg_pixmap.isNull():
            painter.drawPixmap(self.rect(), self._bg_pixmap)
            painter.fillRect(self.rect(), QColor(13, 21, 38, 190))
        else:
            painter.fillRect(self.rect(), QColor(27, 42, 74))
        painter.end()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 48, 40, 40)
        layout.setSpacing(18)

        # 标题区
        title = QLabel("问 道 长 生")
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("— 修仙模拟器 —")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacerItem(
            QSpacerItem(20, 24, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        # 最近存档快捷入口（无存档时隐藏）
        self.btn_continue = QPushButton()
        self.btn_continue.setObjectName("continueButton")
        self.btn_continue.setMinimumHeight(60)
        self.btn_continue.clicked.connect(self._on_continue)
        self._refresh_continue_btn()
        layout.addWidget(self.btn_continue)

        # 功能按钮
        self.btn_new = QPushButton("新的开始")
        self.btn_load = QPushButton("选择存档")
        self.btn_settings = QPushButton("设置")
        self.btn_quit = QPushButton("退出")
        for btn in (self.btn_new, self.btn_load, self.btn_settings, self.btn_quit):
            btn.setObjectName("loginButton")
            btn.setMinimumHeight(46)
            layout.addWidget(btn)

        self.btn_new.clicked.connect(self._on_new_game)
        self.btn_load.clicked.connect(self._on_load)
        self.btn_settings.clicked.connect(self._on_settings)
        self.btn_quit.clicked.connect(self._on_quit)

        layout.addSpacerItem(
            QSpacerItem(20, 16, QSizePolicy.Minimum, QSizePolicy.Minimum)
        )

        hint = QLabel("道友，请选择你的修行之路")
        hint.setObjectName("loginHint")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("""
            QLabel#loginTitle {
                color: #e8c97a;
                font-size: 40px;
                font-weight: bold;
                letter-spacing: 6px;
            }
            QLabel#loginSubtitle {
                color: #9fb3d1;
                font-size: 16px;
                letter-spacing: 3px;
            }
            QLabel#loginHint {
                color: #6b7d99;
                font-size: 12px;
            }
            QPushButton#loginButton {
                background-color: rgba(232, 201, 122, 0.12);
                color: #e8c97a;
                border: 1px solid rgba(232, 201, 122, 0.5);
                border-radius: 10px;
                font-size: 17px;
                letter-spacing: 2px;
            }
            QPushButton#loginButton:hover {
                background-color: rgba(232, 201, 122, 0.28);
                border-color: #e8c97a;
            }
            QPushButton#loginButton:pressed {
                background-color: rgba(232, 201, 122, 0.4);
            }
            QPushButton#continueButton {
                background-color: rgba(232, 201, 122, 0.28);
                color: #e8c97a;
                border: 2px solid #e8c97a;
                border-radius: 10px;
                font-size: 15px;
                letter-spacing: 1px;
            }
            QPushButton#continueButton:hover {
                background-color: rgba(232, 201, 122, 0.45);
            }
        """)

    def _load_recent_slot(self):
        """读取最近存档的元信息；无存档返回 None。"""
        try:
            from game.save_manager import SaveManager
            slots = SaveManager().list_slots()
            return slots[0] if slots else None
        except Exception:
            return None

    def _realm_name(self, realm_id):
        """境界 ID → 中文名；未知/无 ID 返回空串。"""
        if not realm_id:
            return ""
        try:
            with open(os.path.join("config", "realms.json"), "r", encoding="utf-8") as f:
                realms = json.load(f)
            for r in realms:
                if r.get("id") == realm_id:
                    return r.get("name", "")
        except (json.JSONDecodeError, OSError):
            pass
        return ""

    def _refresh_continue_btn(self):
        """刷新「继续上次」按钮文案与可见性。"""
        if not self.recent_slot:
            self.btn_continue.setVisible(False)
            return
        name = self.recent_slot.get("player_name", "无名散修")
        realm = self._realm_name(self.recent_slot.get("realm_id"))
        saved_at = self.recent_slot.get("saved_at", "")
        text = f"继续修行 · {name}"
        if realm:
            text += f" · {realm}"
        if saved_at:
            text += f"\n上次退出：{saved_at}"
        self.btn_continue.setText(text)
        self.btn_continue.setVisible(True)

    def _on_continue(self):
        """继续最近存档：直接以 LOAD 方式载入。"""
        if not self.recent_slot:
            return
        self.selected_slot = self.recent_slot.get("name")
        self.selected_action = self.LOAD
        self.accept()

    def _default_new_name(self):
        """为新存档提供默认名称（基于已有存档数量）。"""
        try:
            from game.save_manager import SaveManager
            sm = SaveManager()
            n = len(sm.list_slots())
            return f"修仙之旅 {n + 1}"
        except Exception:
            return "修仙之旅 1"

    def _on_new_game(self):
        name, ok = QInputDialog.getText(
            self, "新的开始", "为这趟修仙之旅取个存档名：",
            text=self._default_new_name(),
        )
        if not ok or not name.strip():
            return
        self.new_slot_name = name.strip()
        self.selected_action = self.NEW_GAME
        self.accept()

    def _on_load(self):
        from game.save_manager import SaveManager
        sm = SaveManager()
        if not sm.list_slots():
            QMessageBox.information(self, "选择存档", "暂无存档，请先『新的开始』。")
            return
        dlg = SaveSelectDialog(self, save_manager=sm)
        if dlg.exec() == QDialog.Accepted:
            self.selected_slot = dlg.selected_slot
            self.selected_action = self.LOAD
            self.accept()

    def _on_settings(self):
        # 登录阶段无 engine/player：仅音效/音量可用
        dlg = SettingsDialog(parent=self)
        dlg.exec()

    def _on_quit(self):
        self.selected_action = self.QUIT
        self.accept()
