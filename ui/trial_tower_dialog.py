# -*- coding: utf-8 -*-
"""试炼塔弹窗：挑战入口、层数进度、三选一补给与结算。

流程：开始挑战 → 每层走现有战斗界面（victory 后引擎推进）→
本弹窗在战斗结束后重新打开展示结果（层数/奖励/纪录）。
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
)


class TrialTowerDialog(QDialog):
    """试炼塔主面板。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.mgr = engine.trial_tower_manager
        self.setWindowTitle("试炼塔")
        self.resize(460, 380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("<h2>🗼 试炼塔</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "一层一敌，层数越高敌人越强。每层胜利可择一补给，"
            "主动撤退全额结算，战败则折半。最高纪录跨世保留。"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #6b7280; font-size: 12px;")
        layout.addWidget(desc)

        # 状态区
        status = QLabel()
        status.setAlignment(Qt.AlignCenter)
        if self.mgr.active:
            status.setText(
                f"<span style='color:#b8860b;font-size:15px;'>"
                f"挑战进行中 · 第 <b>{self.mgr.floor}</b> 层</span>"
            )
        else:
            status.setText(
                f"<span style='color:#374151;'>最高纪录："
                f"<b>{self.mgr.best}</b> / {self.mgr.max_floors} 层</span>"
            )
        layout.addWidget(status)

        # 三选一补给展示（待选择时）
        if self.mgr.pending_buffs:
            buff_label = QLabel("选择一项补给，继续深入：")
            buff_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(buff_label)
            for buff in self.mgr.pending_buffs:
                btn = QPushButton(
                    f"{buff.get('name')} —— {buff.get('desc')}"
                )
                btn.clicked.connect(
                    lambda _checked=False, bid=buff.get("id"): self._choose(bid))
                layout.addWidget(btn)

        layout.addStretch()

        # 操作按钮
        btn_row = QHBoxLayout()
        if self.mgr.active:
            continue_btn = QPushButton("继续下一层")
            continue_btn.clicked.connect(self._continue)
            btn_row.addWidget(continue_btn)
            retreat_btn = QPushButton("撤退结算")
            retreat_btn.clicked.connect(self._retreat)
            btn_row.addWidget(retreat_btn)
        else:
            start_btn = QPushButton("开始挑战")
            start_btn.clicked.connect(self._start)
            btn_row.addWidget(start_btn)
            close_btn = QPushButton("离开")
            close_btn.clicked.connect(self.reject)
            btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ---------- 动作 ----------
    def _start(self):
        enemy = self.mgr.start_run()
        if enemy is None:
            QMessageBox.information(self, "试炼塔", "无法开始挑战（请先确保角色存活）。")
            return
        self.engine.pending_trial = True
        self.accept()
        self.engine.start_combat(enemy)

    def _continue(self):
        if self.mgr.pending_buffs:
            QMessageBox.information(self, "试炼塔", "请先选择一项补给。")
            return
        enemy = self.mgr.next_floor_enemy()
        if enemy is None:
            QMessageBox.information(self, "试炼塔", "该层敌人暂不可用。")
            return
        self.engine.pending_trial = True
        self.accept()
        self.engine.start_combat(enemy)

    def _choose(self, buff_id):
        ok, msg = self.mgr.choose_buff(buff_id)
        if ok:
            self.engine.notify(f"[cyan]【试炼塔】{msg}")
        self._reopen()

    def _retreat(self):
        result = self.mgr.retreat()
        self.engine.notify(
            f"[cyan]【试炼塔】你选择撤退，止步第 {result.get('reached', 0)} 层，"
            f"奖励已按层结算。"
        )
        self.accept()

    def _reopen(self):
        """补给选择后刷新面板。"""
        self.accept()
        TrialTowerDialog(self.engine, parent=self.parent()).exec()
