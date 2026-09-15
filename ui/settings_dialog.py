import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSlider, QFileDialog, QMessageBox, QWidget,
)
from PySide6.QtCore import Qt, QObject, QRunnable, QThreadPool, Signal

from game.sound_manager import SoundManager


class _AIDiagSignals(QObject):
    """AI 诊断工作线程信号：finished(result dict)。"""
    finished = Signal(dict)


class _AIDiagWorker(QRunnable):
    """后台执行 AI 服务诊断，避免阻塞界面。"""

    def __init__(self, config_dir="config"):
        super().__init__()
        self.config_dir = config_dir
        self.signals = _AIDiagSignals()

    def run(self):
        from game.ai_diag import diagnose_ai
        self.signals.finished.emit(diagnose_ai(self.config_dir))


class SettingsDialog(QDialog):
    """设置：音效开关 / 音量 / 更换立绘 / 难度模式。

    engine 与 player 在登录阶段为 None，此时「更换立绘」「难度模式」禁用；
    进入游戏后由主窗口以 engine/player 打开时可启用。
    """

    PREFS_PATH = os.path.join("config", "ui_prefs.json")
    FLAGS_PATH = os.path.join("config", "feature_flags.json")

    def __init__(self, parent=None, engine=None, player=None, sound_manager=None):
        super().__init__(parent)
        self.engine = engine
        self.player = player
        self.sound_manager = sound_manager
        self.setWindowTitle("设置")
        self.setMinimumSize(420, 340)
        self._muted = False
        self._volume = 1.0
        # AI 诊断读取 key 的配置目录：游戏内跟随 engine，登录态用默认 config
        self._diag_config_dir = (
            getattr(engine, "config_dir", "config") if engine is not None else "config"
        )
        self._ai_diag_worker = None
        self._load_prefs()
        self._setup_ui()
        self._apply_runtime_sound()

    def _load_prefs(self):
        try:
            if os.path.exists(self.PREFS_PATH):
                with open(self.PREFS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._muted = bool(data.get("sound_muted", False))
                vol = float(data.get("sound_volume", 1.0))
                self._volume = max(0.0, min(1.0, vol))
        except Exception:
            self._muted = False
            self._volume = 1.0

    def _save_prefs(self):
        """持久化音效设置，保留 ui_prefs.json 中其他键（如手风琴多开偏好）。"""
        try:
            data = {}
            if os.path.exists(self.PREFS_PATH):
                with open(self.PREFS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["sound_muted"] = self._muted
            data["sound_volume"] = self._volume
            os.makedirs(os.path.dirname(self.PREFS_PATH), exist_ok=True)
            with open(self.PREFS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 静音开关
        sound_row = QHBoxLayout()
        sound_label = QLabel("静音")
        self.mute_check = QCheckBox()
        self.mute_check.setChecked(self._muted)
        self.mute_check.toggled.connect(self._on_mute_toggled)
        sound_row.addWidget(sound_label)
        sound_row.addStretch(1)
        sound_row.addWidget(self.mute_check)
        layout.addLayout(sound_row)

        # 音量
        vol_row = QHBoxLayout()
        vol_label = QLabel("音量")
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(int(self._volume * 100))
        self.vol_value = QLabel(f"{int(self._volume * 100)}%")
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        vol_row.addWidget(vol_label)
        vol_row.addWidget(self.vol_slider, 1)
        vol_row.addWidget(self.vol_value)
        layout.addLayout(vol_row)

        layout.addSpacing(8)

        # 更换立绘（仅游戏内有 player 时可用）
        self.btn_portrait = QPushButton("更换主角立绘")
        self.btn_portrait.setEnabled(self.player is not None)
        if self.player is None:
            self.btn_portrait.setToolTip("进入游戏后可在设置中更换立绘")
        self.btn_portrait.clicked.connect(self._on_change_portrait)
        layout.addWidget(self.btn_portrait)

        # 难度/模式（仅游戏内有 engine/player 时可用）
        self.btn_difficulty = QPushButton("游戏难度 / 多周目模式")
        self.btn_difficulty.setEnabled(
            self.engine is not None and self.player is not None
        )
        if self.engine is None:
            self.btn_difficulty.setToolTip("新游戏开局时或进入游戏后可调整")
        self.btn_difficulty.clicked.connect(self._on_difficulty)
        layout.addWidget(self.btn_difficulty)

        # 功能开关管理（读写 feature_flags.json；有 engine 时内存即时生效）
        self._build_feature_flags_section(layout)

        # AI 服务诊断
        self.btn_ai_diag = QPushButton("测试 AI 连接")
        self.btn_ai_diag.clicked.connect(self._on_ai_diag)
        layout.addWidget(self.btn_ai_diag)
        self.ai_diag_result = QLabel("")
        self.ai_diag_result.setStyleSheet("color: #495057; font-size: 12px;")
        self.ai_diag_result.setWordWrap(True)
        layout.addWidget(self.ai_diag_result)

        layout.addStretch(1)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        close_row.addWidget(btn_close)
        layout.addLayout(close_row)

        self.setStyleSheet("""
            QLabel { font-size: 14px; }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 14px;
            }
            QPushButton:disabled {
                color: #adb5bd;
                background-color: #f1f3f5;
            }
            QPushButton:hover:!disabled { background-color: #f8f9fa; }
        """)

    def _on_mute_toggled(self, checked):
        self._muted = bool(checked)
        self._save_prefs()
        self._apply_runtime_sound()

    def _on_volume_changed(self, value):
        self._volume = value / 100.0
        self.vol_value.setText(f"{value}%")
        self._save_prefs()
        self._apply_runtime_sound()

    def _apply_runtime_sound(self):
        """即时应用到运行时 SoundManager（若可用）。"""
        if self.sound_manager is not None:
            self.sound_manager.set_muted(self._muted)
            self.sound_manager.set_volume(self._volume)

    def _on_change_portrait(self):
        if self.player is None:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择主角头像", "assets/portraits",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if file_path:
            self.player.portrait = file_path
            parent = self.parent()
            if parent is not None and hasattr(parent, "_refresh_status"):
                parent._refresh_status()
            QMessageBox.information(self, "立绘", "已更换主角立绘。")

    def _on_difficulty(self):
        if self.engine is None or self.player is None:
            return
        from ui.difficulty_mode_dialog import DifficultyModeDialog
        dlg = DifficultyModeDialog(
            self.engine, self.player, parent=self, new_game=False
        )
        dlg.exec()
        parent = self.parent()
        if parent is not None and hasattr(parent, "_refresh_status"):
            parent._refresh_status()

    # ---------------- 功能开关管理 ----------------

    def _load_flags_data(self):
        """读取 feature_flags.json（flags/names/descriptions）。"""
        try:
            data = {}
            if os.path.exists(self.FLAGS_PATH):
                with open(self.FLAGS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except (json.JSONDecodeError, OSError):
            data = {}
        return data

    def _build_feature_flags_section(self, outer):
        """功能开关区块：网格复选框 + 滚动，切换即时生效并保存。"""
        from PySide6.QtWidgets import QGroupBox, QScrollArea, QGridLayout

        data = self._load_flags_data()
        flags = data.get("flags") if isinstance(data.get("flags"), dict) else {}
        names = data.get("names", {})
        descriptions = data.get("descriptions", {})
        if not flags:
            return

        box = QGroupBox("功能开关")
        inner = QVBoxLayout(box)
        hint = QLabel("切换后即时生效并自动保存；关闭 AI 类开关可减少联网与等待。")
        hint.setStyleSheet("color: #868e96; font-size: 12px;")
        hint.setWordWrap(True)
        inner.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(210)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(18)
        self._flag_checks = {}
        for i, flag_id in enumerate(sorted(flags)):
            row, col = divmod(i, 2)
            cb = QCheckBox(str(names.get(flag_id, flag_id)))
            cb.setChecked(bool(flags[flag_id]))
            tip = str(descriptions.get(flag_id, ""))
            if tip:
                cb.setToolTip(tip)
            cb.toggled.connect(
                lambda checked, fid=flag_id: self._on_flag_toggled(fid, checked)
            )
            grid.addWidget(cb, row, col)
            self._flag_checks[flag_id] = cb
        scroll.setWidget(content)
        inner.addWidget(scroll)
        outer.addWidget(box, 1)

    def _on_flag_toggled(self, flag_id, checked):
        """切换功能开关：有 engine 时内存即时生效；统一写回 JSON。"""
        if self.engine is not None:
            self.engine.set_feature_flag(flag_id, checked)
            return
        # 登录阶段（无游戏会话）：直接写 JSON，下次启动生效
        try:
            data = self._load_flags_data()
            flags = data.get("flags") if isinstance(data.get("flags"), dict) else {}
            flags = dict(flags)
            flags[flag_id] = bool(checked)
            data["flags"] = flags
            with open(self.FLAGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, OSError):
            pass

    # ---------------- AI 服务诊断 ----------------

    def _on_ai_diag(self):
        """发起 AI 服务诊断（后台线程）。"""
        self.btn_ai_diag.setEnabled(False)
        self.ai_diag_result.setStyleSheet("color: #495057; font-size: 12px;")
        self.ai_diag_result.setText("诊断中…")
        worker = _AIDiagWorker(self._diag_config_dir)
        worker.signals.finished.connect(self._on_ai_diag_done)
        self._ai_diag_worker = worker  # 防回收
        QThreadPool.globalInstance().start(worker)

    def _on_ai_diag_done(self, result):
        """诊断完成（主线程）：按结果着色展示。"""
        self.btn_ai_diag.setEnabled(True)
        self._ai_diag_worker = None
        ok = result.get("reachable") and result.get("image_model_ok")
        color = "#2f9e44" if ok else "#c92a2a"
        self.ai_diag_result.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.ai_diag_result.setText(result.get("detail", ""))
