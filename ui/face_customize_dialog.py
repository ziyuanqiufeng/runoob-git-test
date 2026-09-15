# -*- coding: utf-8 -*-
"""捏脸弹窗（双路线：AI 提示词捏脸 + 拼装捏脸）。

Tab1「AI 立绘」：选特征 → Agnes 文生图（异步）。
Tab2「拼装捏脸」：逐层选部件 → PIL 实时合成（即时预览）。
两个 Tab 各自"采用"后写 adopted_*，由调用方读取；未采用不覆盖当前头像。
"""
import os
import time

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QWidget, QTabWidget,
)
from PySide6.QtCore import Qt, QObject, QRunnable, QThreadPool, Signal

from game.face_traits import (
    load_traits_config, build_trait_prompt,
)
from game.face_compositor import (
    load_parts_config, compose, random_face_params,
)
from game.portrait_generator import generate_portrait_from_prompt
from ui.portrait_label import PortraitLabel


class _FaceGenSignals(QObject):
    """生成工作线程信号：finished(success, path, error_message)。"""
    finished = Signal(bool, str, str)


class _FaceGenWorker(QRunnable):
    """在子线程调用 Agnes 文生图，避免阻塞界面。"""

    def __init__(self, prompt, output_dir="assets/portraits", config_dir="config"):
        super().__init__()
        self.prompt = prompt
        self.output_dir = output_dir
        self.config_dir = config_dir
        self.signals = _FaceGenSignals()

    def run(self):
        try:
            ok, path = generate_portrait_from_prompt(
                self.prompt, output_dir=self.output_dir, config_dir=self.config_dir
            )
            if ok and path and os.path.exists(path):
                self.signals.finished.emit(True, path, "")
            else:
                self.signals.finished.emit(False, "", "生成失败：服务暂时不可用或未配置 API key。")
        except Exception as e:
            self.signals.finished.emit(False, "", str(e))


class FaceCustomizeDialog(QDialog):
    """捏脸弹窗（AI 立绘 / 拼装捏脸 双 Tab）。"""

    def __init__(self, gender="male", player=None, parent=None, config_dir="config"):
        super().__init__(parent)
        self.setWindowTitle("捏脸 · 打造你的道友面容")
        self.resize(640, 460)
        self.gender = gender
        self.player = player
        self.config_dir = config_dir

        self._ai_cfg = load_traits_config(config_dir)
        self._parts_cfg = load_parts_config(config_dir)
        self._current_traits = self._initial_traits()
        self._assembly_params = self._initial_params()
        self._generated_path = None    # AI Tab 候选图
        self._composed_path = None     # 拼装 Tab 预览图
        self._active_worker = None

        self.adopted_path = None       # 采用后供调用方读取
        self.adopted_traits = None
        self.adopted_params = None

        self._setup_ui()

    # ---------------- 通用 ----------------

    def _initial_traits(self):
        """AI 特征初始值：优先恢复 player.face_traits，否则每维度取第一项。"""
        saved = dict(getattr(self.player, "face_traits", {}) or {}) if self.player else {}
        if self._ai_cfg:
            for dim in self._ai_cfg.get("dimensions", []):
                options = dim.get("options", [])
                if options and dim["id"] not in saved:
                    saved[dim["id"]] = options[0].get("id")
        return saved

    def _initial_params(self):
        """拼装参数初始值：优先恢复 player.face_params，否则每层取第一项。"""
        saved = dict(getattr(self.player, "face_params", {}) or {}) if self.player else {}
        if self._parts_cfg:
            for layer in self._parts_cfg.get("layers", []):
                options = layer.get("parts", [])
                if options and layer["id"] not in saved:
                    saved[layer["id"]] = options[0].get("id")
            skins = self._parts_cfg.get("skins", [])
            if skins and "skin" not in saved:
                saved["skin"] = skins[0]["id"]
        return saved

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        tabs = QTabWidget()
        tabs.addTab(self._build_ai_tab(), "AI 立绘")
        tabs.addTab(self._build_assembly_tab(), "拼装捏脸")
        layout.addWidget(tabs, 1)

    # ---------------- Tab 1：AI 立绘 ----------------

    def _build_ai_tab(self):
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(18)

        # 左：预览与操作
        left = QVBoxLayout()
        self.preview_label = PortraitLabel(
            size=170, border_color="#cccccc", border_width=2,
            placeholder_text="尚未生成", circular=False,
        )
        left.addWidget(self.preview_label, alignment=Qt.AlignCenter)

        self.status_label = QLabel("选择特征后点击「生成立绘」。")
        self.status_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        left.addWidget(self.status_label)

        self.gen_btn = QPushButton("🎨 生成立绘")
        self.gen_btn.setMinimumHeight(38)
        self.gen_btn.clicked.connect(self._on_generate)
        left.addWidget(self.gen_btn)

        self.adopt_btn = QPushButton("✔ 采用这张")
        self.adopt_btn.setMinimumHeight(38)
        self.adopt_btn.setEnabled(False)
        self.adopt_btn.clicked.connect(self._on_adopt_ai)
        left.addWidget(self.adopt_btn)
        layout.addLayout(left, 2)

        # 右：特征维度下拉
        right = QVBoxLayout()
        right.addWidget(QLabel("捏脸特征（每项都会写进生成提示词）："))
        self.combos = {}
        if not self._ai_cfg:
            right.addWidget(QLabel("⚠ 特征表缺失（config/face_traits.json）。"))
        for dim in (self._ai_cfg or {}).get("dimensions", []):
            right.addWidget(QLabel(dim.get("name", dim.get("id", ""))))
            combo = QComboBox()
            for opt in dim.get("options", []):
                combo.addItem(opt.get("name", opt.get("id")), opt.get("id"))
            saved = (self._current_traits or {}).get(dim.get("id"))
            idx = combo.findData(saved)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.currentIndexChanged.connect(self._on_trait_changed)
            right.addWidget(combo)
            self.combos[dim["id"]] = combo
        right.addStretch(1)
        layout.addLayout(right, 3)
        return w

    def _on_trait_changed(self, _index):
        self._current_traits = {
            dim_id: combo.currentData() for dim_id, combo in self.combos.items()
        }

    def _on_generate(self):
        """按当前特征生成 AI 立绘（异步，不阻塞界面）。"""
        if not self._ai_cfg:
            return
        self._current_traits = {
            dim_id: combo.currentData() for dim_id, combo in self.combos.items()
        }
        prompt, _negative = build_trait_prompt(
            self._current_traits, gender=self.gender,
            config_dir=self.config_dir, player=self.player,
        )
        if not prompt:
            QMessageBox.warning(self, "捏脸", "特征表缺失，无法生成。")
            return
        self.gen_btn.setEnabled(False)
        self.adopt_btn.setEnabled(False)
        self.gen_btn.setText("生成中…")
        self.status_label.setText("正在调用 Agnes 文生图（约 1 分钟，服务繁忙会自动重试）…")

        worker = _FaceGenWorker(prompt, config_dir=self.config_dir)
        worker.signals.finished.connect(self._on_generated)
        self._active_worker = worker
        QThreadPool.globalInstance().start(worker)

    def _on_generated(self, success, path, error_message):
        """生成回调（主线程）。失败信息在状态栏展示，不用模态弹窗。"""
        self.gen_btn.setEnabled(True)
        self.gen_btn.setText("🎨 生成立绘")
        self._active_worker = None
        if success:
            self._generated_path = path
            self.preview_label.load_portrait(path)
            self.status_label.setText("生成完成！满意请点「采用这张」。")
            self.adopt_btn.setEnabled(True)
        else:
            self._generated_path = None
            self.status_label.setText(f"生成失败：{error_message}")

    def _on_adopt_ai(self):
        """采用 AI 生成的立绘与特征。"""
        if not self._generated_path:
            return
        self.adopted_path = self._generated_path
        self.adopted_traits = dict(self._current_traits)
        self.adopted_params = None
        self.accept()

    # ---------------- Tab 2：拼装捏脸 ----------------

    def _build_assembly_tab(self):
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(18)

        # 左：实时预览 + 操作
        left = QVBoxLayout()
        self.assembly_preview = PortraitLabel(
            size=170, border_color="#cccccc", border_width=2,
            placeholder_text="部件缺失", circular=False,
        )
        left.addWidget(self.assembly_preview, alignment=Qt.AlignCenter)

        self.assembly_status = QLabel("调整部件，实时预览。")
        self.assembly_status.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        self.assembly_status.setAlignment(Qt.AlignCenter)
        self.assembly_status.setWordWrap(True)
        left.addWidget(self.assembly_status)

        btn_row = QHBoxLayout()
        btn_random = QPushButton("🎲 随机")
        btn_random.clicked.connect(self._on_assembly_random)
        btn_adopt = QPushButton("✔ 采用这个形象")
        btn_adopt.setMinimumHeight(38)
        btn_adopt.clicked.connect(self._on_adopt_assembly)
        btn_row.addWidget(btn_random)
        btn_row.addWidget(btn_adopt)
        left.addLayout(btn_row)
        layout.addLayout(left, 2)

        # 右：每层部件下拉 + 肤色
        right = QVBoxLayout()
        right.addWidget(QLabel("逐层挑选部件（即时合成）："))
        self.part_combos = {}
        if not self._parts_cfg:
            right.addWidget(QLabel("⚠ 部件配置缺失（config/face_parts.json）。"))
        for layer in (self._parts_cfg or {}).get("layers", []):
            right.addWidget(QLabel(layer.get("name", layer.get("id", ""))))
            combo = QComboBox()
            for part in layer.get("parts", []):
                combo.addItem(part.get("name", part.get("id")), part.get("id"))
            saved = (self._assembly_params or {}).get(layer["id"])
            idx = combo.findData(saved)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.currentIndexChanged.connect(self._on_assembly_changed)
            right.addWidget(combo)
            self.part_combos[layer["id"]] = combo

        right.addWidget(QLabel("肤色"))
        self.skin_combo = QComboBox()
        for skin in (self._parts_cfg or {}).get("skins", []):
            self.skin_combo.addItem(skin.get("name", skin["id"]), skin["id"])
        saved_skin = (self._assembly_params or {}).get("skin")
        idx = self.skin_combo.findData(saved_skin)
        self.skin_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.skin_combo.currentIndexChanged.connect(self._on_assembly_changed)
        right.addWidget(self.skin_combo)
        right.addStretch(1)
        layout.addLayout(right, 3)

        # 初始预览
        self._refresh_assembly_preview()
        return w

    def _read_assembly_params(self):
        params = {
            layer_id: combo.currentData() for layer_id, combo in self.part_combos.items()
        }
        params["skin"] = self.skin_combo.currentData()
        return params

    def _on_assembly_changed(self, _index=None):
        self._assembly_params = self._read_assembly_params()
        self._refresh_assembly_preview()

    def _on_assembly_random(self):
        rng_params = random_face_params(self.config_dir)
        if not rng_params:
            return
        self._assembly_params = rng_params
        for layer_id, combo in self.part_combos.items():
            idx = combo.findData(rng_params.get(layer_id))
            if idx >= 0:
                combo.setCurrentIndex(idx)
        skin_idx = self.skin_combo.findData(rng_params.get("skin"))
        if skin_idx >= 0:
            self.skin_combo.setCurrentIndex(skin_idx)
        self._refresh_assembly_preview()

    def _refresh_assembly_preview(self):
        """用当前参数合成预览图并刷新。"""
        out = os.path.join("assets", "faces", "_compose_preview.png")
        path = compose(self._assembly_params, out, self.config_dir)
        if path and os.path.exists(path):
            self._composed_path = path
            self.assembly_preview.load_portrait(path)
            self.assembly_status.setText("实时预览中，满意请点「采用这个形象」。")

    def _on_adopt_assembly(self):
        """采用拼装形象：合成图另存为正式头像，避免预览文件被后续覆盖。"""
        if not getattr(self, "_composed_path", None):
            return
        final_dir = os.path.join("assets", "portraits")
        os.makedirs(final_dir, exist_ok=True)
        final_path = os.path.join(final_dir, f"generated_{int(time.time())}.png")
        out = compose(self._assembly_params, final_path, self.config_dir)
        if not out:
            return
        self.adopted_path = out
        self.adopted_params = dict(self._assembly_params)
        self.adopted_traits = None
        self.accept()
