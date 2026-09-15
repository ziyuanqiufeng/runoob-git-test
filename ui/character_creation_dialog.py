# -*- coding: utf-8 -*-
"""角色创建弹窗：输入道号、选择头像路径。

新游戏开始时调用，完成基础信息录入后再进入灵根觉醒与流派选择。
"""
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QDialogButtonBox, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, QObject, QRunnable, QThreadPool, Signal
from game.portrait_generator import generate_portrait
from game.player import Player
from ui.portrait_label import PortraitLabel


class _PortraitGenerationSignals(QObject):
    """AI 生成工作线程信号：finished(success, path, error_message)。"""
    finished = Signal(bool, str, str)


class _PortraitGenerationWorker(QRunnable):
    """在 QThreadPool 中异步执行 AI 立绘生成的工作对象。"""

    def __init__(self, name, gender, roots, path_id, realm_id, output_dir="assets/portraits"):
        super().__init__()
        self.name = name
        self.gender = gender
        self.roots = roots
        self.path_id = path_id
        self.realm_id = realm_id
        self.output_dir = output_dir
        self.signals = _PortraitGenerationSignals()

    def run(self):
        """子线程中构造临时玩家并生成头像。"""
        try:
            temp_player = Player(name=self.name or "无名散修")
            temp_player.gender = self.gender
            temp_player.set_spiritual_roots(self.roots)
            temp_player.cultivation_path = self.path_id
            temp_player.realm_id = self.realm_id
            ok, path = generate_portrait(temp_player, output_dir=self.output_dir, use_ai=True)
            if ok and path and os.path.exists(path):
                self.signals.finished.emit(True, path, "")
            else:
                self.signals.finished.emit(False, "", "生成失败，未得到有效图片路径。")
        except Exception as e:
            self.signals.finished.emit(False, "", str(e))


class CharacterCreationDialog(QDialog):
    """角色创建对话框。"""

    def __init__(self, default_portrait="assets/portraits/protagonist_default.png", parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建角色")
        self.resize(420, 280)

        self._default_portrait = default_portrait
        self._selected_portrait = default_portrait
        self._active_worker = None  # 当前运行的 AI 生成工作对象
        self._generation_cancelled = False  # 用户关闭弹窗后忽略生成结果
        self.face_traits = {}   # 捏脸选择的特征（AI 路线，采用后记录）
        self.face_params = {}   # 拼装捏脸参数（拼装路线，采用后记录）

        layout = QVBoxLayout(self)

        # 道号输入
        layout.addWidget(QLabel("请输入道号："))
        self.name_edit = QLineEdit("无名散修")
        self.name_edit.setMaxLength(12)
        layout.addWidget(self.name_edit)

        # 性别选择
        layout.addWidget(QLabel("请选择性别："))
        self.gender_combo = QComboBox()
        self.gender_combo.addItem("男", "male")
        self.gender_combo.addItem("女", "female")
        layout.addWidget(self.gender_combo)

        # 头像路径选择
        layout.addWidget(QLabel("请选择主角头像："))
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit(default_portrait)
        self.path_edit.setReadOnly(True)
        path_layout.addWidget(self.path_edit, 1)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self._browse_portrait)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)

        # AI 生成立绘按钮（基于当前默认属性生成，后续可在状态面板重新生成）
        self.ai_btn = QPushButton("🎨 AI 生成立绘")
        self.ai_btn.setToolTip("根据性别、灵根、流派、境界生成主角头像。")
        self.ai_btn.clicked.connect(self._generate_ai_portrait)
        layout.addWidget(self.ai_btn)

        # 捏脸入口（AI 提示词捏脸：按特征生成专属立绘）
        self.face_btn = QPushButton("捏脸…")
        self.face_btn.setToolTip("选择脸型、眼神、气质等特征，生成专属立绘。")
        self.face_btn.clicked.connect(self._open_face_customize)
        layout.addWidget(self.face_btn)

        # 生成状态提示标签（显示进度/连接状态）
        self.ai_status_label = QLabel("")
        self.ai_status_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        self.ai_status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.ai_status_label)

        # 头像预览（使用统一头像组件，创建角色时展示为圆角矩形更直观）
        preview_layout = QHBoxLayout()
        preview_layout.addStretch()
        self.preview_label = PortraitLabel(
            size=96,
            border_color="#aaaaaa",
            border_width=2,
            placeholder_text="无头像",
            circular=False,
        )
        preview_layout.addWidget(self.preview_label)
        preview_layout.addStretch()
        layout.addLayout(preview_layout)

        # 提示
        tip = QLabel("提示：可在游戏文件夹 assets/portraits/ 中放入自定义立绘。")
        tip.setStyleSheet("color: #666; font-size: 12px;")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        # 确定/取消
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._load_preview()

    def _browse_portrait(self):
        """打开文件选择对话框挑选头像。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择主角头像",
            "assets/portraits",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if file_path:
            self._selected_portrait = file_path
            self.path_edit.setText(file_path)
            self._load_preview()

    def _load_preview(self):
        """加载并显示头像预览。"""
        self.preview_label.load_portrait(self._selected_portrait)

    def _on_accept(self):
        """确认创建，校验道号非空。"""
        name = self.name_edit.text().strip()
        if not name:
            return
        self.accept()

    def get_name(self):
        """获取输入的道号。"""
        return self.name_edit.text().strip() or "无名散修"

    def get_portrait(self):
        """获取选择的头像路径。"""
        return self._selected_portrait

    def get_gender(self):
        """获取选择的性别。"""
        return self.gender_combo.currentData()

    def get_face_traits(self):
        """获取捏脸选择的特征（未使用捏脸时为空 dict）。"""
        return dict(self.face_traits)

    def get_face_params(self):
        """获取拼装捏脸参数（未使用时为空 dict）。"""
        return dict(self.face_params)

    def _open_face_customize(self):
        """打开捏脸弹窗；采用后把立绘与参数回填到创建界面。"""
        from ui.face_customize_dialog import FaceCustomizeDialog
        dlg = FaceCustomizeDialog(gender=self.get_gender(), parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.adopted_path:
            self._selected_portrait = dlg.adopted_path
            self.path_edit.setText(dlg.adopted_path)
            self.face_traits = dict(dlg.adopted_traits or {})
            self.face_params = dict(dlg.adopted_params or {})
            self._load_preview()

    def _generate_ai_portrait(self):
        """根据当前选择的性别异步生成 AI 立绘，避免阻塞界面。"""
        # 重置取消标志，并更新界面状态
        self._generation_cancelled = False
        self.ai_btn.setEnabled(False)
        self.ai_btn.setText("生成中...")
        self.ai_status_label.setText("正在连接文生图服务，请稍候...")
        self.button_box.setEnabled(False)

        worker = _PortraitGenerationWorker(
            name=self.get_name(),
            gender=self.get_gender(),
            roots=["fire"],
            path_id="fa",
            realm_id="qi_refining_1",
            output_dir="assets/portraits",
        )
        worker.signals.finished.connect(self._on_portrait_generated)
        # 保留引用，防止生成过程中 Python 回收工作对象
        self._active_worker = worker
        QThreadPool.globalInstance().start(worker)

    def _on_portrait_generated(self, success, path, error_message):
        """AI 生成完成后的回调（在主线程执行）。"""
        self.ai_btn.setEnabled(True)
        self.ai_btn.setText("🎨 AI 生成立绘")
        self.button_box.setEnabled(True)
        self.ai_status_label.setText("")
        self._active_worker = None

        # 若用户已在生成期间关闭弹窗，则不再更新界面或弹出提示
        if self._generation_cancelled:
            return

        if success and path and os.path.exists(path):
            self._selected_portrait = path
            self.path_edit.setText(path)
            self._load_preview()
            QMessageBox.information(self, "立绘生成", f"已生成专属立绘：\n{path}")
        else:
            QMessageBox.warning(self, "立绘生成", f"生成失败：{error_message}")

    def closeEvent(self, event):
        """生成任务运行时关闭弹窗，提示用户是否取消。"""
        if self._active_worker is not None:
            reply = QMessageBox.question(
                self,
                "生成中",
                "AI 立绘正在生成，关闭窗口将取消本次生成。\n是否继续关闭？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._generation_cancelled = True
                # QThreadPool 无法安全中止已运行任务，这里仅忽略其结果
                self._active_worker = None
                event.accept()
            else:
                event.ignore()
            return
        event.accept()
