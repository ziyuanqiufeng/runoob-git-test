# -*- coding: utf-8 -*-
"""分支对话弹窗。

显示当前对话节点文本、NPC 立绘，以及可选的回复选项。
选择选项后自动推进到下一节点，直到对话结束。
"""
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget as BaseWidget, QSizePolicy,
)
from PySide6.QtCore import Qt
from ui.status_panel import _get_realm_border_color, _PATH_COLORS
from ui.portrait_label import PortraitLabel


class DialogueDialog(QDialog):
    """分支对话窗口。"""

    def __init__(self, engine, dialogue_id, npc_id=None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.dialogue_id = dialogue_id
        self.npc_id = npc_id
        self.setWindowTitle("对话")
        self.resize(560, 480)

        self.main_layout = QVBoxLayout(self)

        # 顶部：NPC 立绘 + 名称 + 玩家头像（均使用统一头像组件）
        self.header_layout = QHBoxLayout()
        self.portrait_label = PortraitLabel(
            size=96,
            border_color="#aaaaaa",
            border_width=1,
            placeholder_text="无头像",
            circular=True,
        )

        self.name_label = QLabel("NPC")
        self.name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # 玩家头像（对话中代表主角），边框颜色与境界联动
        player_border = _get_realm_border_color(
            getattr(self.engine.player, "realm_id", "qi_refining_1")
        )
        self.player_portrait_label = PortraitLabel(
            size=80,
            border_color=player_border,
            border_width=2,
            placeholder_text="我",
            circular=True,
        )

        self.header_layout.addWidget(self.portrait_label)
        self.header_layout.addWidget(self.name_label, 1)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.player_portrait_label)
        self.main_layout.addLayout(self.header_layout)

        # 中部：对话文本滚动区
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = BaseWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.text_label = QLabel("")
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text_label.setStyleSheet(
            "font-size: 14px; padding: 8px; background: #fafafa; border: 1px solid #ddd;"
        )
        self.text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_layout.addWidget(self.text_label)
        self.scroll_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_widget)
        self.main_layout.addWidget(self.scroll_area, 1)

        # 底部：选项按钮容器
        self.options_layout = QVBoxLayout()
        self.main_layout.addLayout(self.options_layout)

        # 关闭按钮
        self.close_btn = QPushButton("结束对话")
        self.close_btn.clicked.connect(self._on_close)
        self.close_btn.setVisible(False)
        self.main_layout.addWidget(self.close_btn)

        # 启动对话
        self._start()

    def _start(self):
        """开始对话并渲染首节点。"""
        self._load_player_portrait()
        state = self.engine.start_dialogue(self.dialogue_id, npc_id=self.npc_id)
        self._render_state(state)

    def _load_player_portrait(self):
        """加载玩家头像到对话界面右上角，并同步境界边框颜色。"""
        player_border = _get_realm_border_color(
            getattr(self.engine.player, "realm_id", "qi_refining_1")
        )
        self.player_portrait_label.set_border_color(player_border)
        self.player_portrait_label.load_portrait(
            getattr(self.engine.player, "portrait", None)
        )

    def _render_state(self, state):
        """根据当前状态刷新 UI。"""
        if not state:
            self._show_end()
            return

        # 刷新说话者与头像
        speaker_id = state.get("speaker", self.npc_id)
        npc = self.engine.npc_library.get(speaker_id)
        if npc:
            self.name_label.setText(npc.name)
            portrait = getattr(npc, "portrait", None)
            # 使用统一头像组件加载 NPC 头像
            self.portrait_label.load_portrait(portrait)
        else:
            self.name_label.setText(speaker_id or "未知")

        # 设置文本
        self.text_label.setText(state.get("text", ""))

        # 清空旧选项
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        options = state.get("options", [])
        if state.get("is_end") or not options:
            self._show_end()
            return

        for opt in options:
            btn = QPushButton(opt["text"])
            btn.setStyleSheet(
                "text-align: left; padding: 8px; font-size: 13px;"
            )
            btn.clicked.connect(lambda checked, idx=opt["index"]: self._on_option_clicked(idx))
            self.options_layout.addWidget(btn)

    def _on_option_clicked(self, option_index):
        """玩家点击选项后的回调。"""
        next_state, logs = self.engine.choose_dialogue_option(option_index)
        # 将效果日志追加到对话文本中
        for log in logs:
            current = self.text_label.text()
            self.text_label.setText(f"{current}\n\n[系统] {log}")
        self._render_state(next_state)

    def _show_end(self):
        """对话结束时隐藏选项，显示结束按钮。"""
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        end_label = QLabel("—— 对话结束 ——")
        end_label.setAlignment(Qt.AlignCenter)
        end_label.setStyleSheet("color: #7f8c8d; padding: 8px;")
        self.options_layout.addWidget(end_label)
        self.close_btn.setVisible(True)

    def _on_close(self):
        """结束对话并关闭窗口。"""
        self.engine.end_dialogue()
        self.accept()

    def closeEvent(self, event):
        """关闭窗口时同步结束对话状态。"""
        self.engine.end_dialogue()
        event.accept()
