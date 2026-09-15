# -*- coding: utf-8 -*-
"""
演武场弹窗：显示连胜、最高连胜、每日奖励与开始切磋。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt


class ArenaDialog(QDialog):
    """演武场交互弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player

        self.setWindowTitle("演武场")
        self.resize(420, 260)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("<h2>演武场</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 状态显示
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; padding: 8px;")
        layout.addWidget(self.status_label)

        # 每日奖励按钮
        self.reward_btn = QPushButton("领取每日奖励")
        self.reward_btn.setToolTip("每日可领取一次，连胜越高奖励越丰厚。")
        self.reward_btn.clicked.connect(self._claim_reward)
        layout.addWidget(self.reward_btn)

        # 开始切磋按钮
        self.fight_btn = QPushButton("开始切磋")
        self.fight_btn.setToolTip("与同境界修士切磋，胜利可提升连胜。")
        self.fight_btn.clicked.connect(self._start_fight)
        layout.addWidget(self.fight_btn)

        # 擂台排名挑战入口
        self.ranking_btn = QPushButton("擂台排名挑战")
        self.ranking_btn.setToolTip("挑战本城演武场排名，胜利可提升名次并获得奖励。")
        self.ranking_btn.clicked.connect(self._open_ranking)
        layout.addWidget(self.ranking_btn)

        # 排行榜（简易占位，显示本城虚构强者）
        rank_label = QLabel(
            "<b>本城强者榜（虚构）</b><br>"
            "1. 无名剑修 — 连胜 37 场<br>"
            "2. 散修李青 — 连胜 21 场<br>"
            "3. 铁掌张横 — 连胜 15 场"
        )
        rank_label.setAlignment(Qt.AlignCenter)
        rank_label.setStyleSheet("color: #666; font-size: 12px; margin-top: 10px;")
        layout.addWidget(rank_label)

        self._refresh_status()

    def _refresh_status(self):
        """刷新连胜与领奖状态显示。"""
        self.engine._reset_arena_daily_if_needed()
        streak = self.player.arena_streak
        best = self.player.arena_best_streak
        claimed = self.player.arena_daily_claimed

        text = (
            f"当前连胜：<b>{streak}</b> 场<br>"
            f"最高连胜：<b>{best}</b> 场<br>"
            f"今日奖励：{'已领取' if claimed else '未领取'}"
        )
        self.status_label.setText(text)
        self.reward_btn.setEnabled(not claimed)
        if claimed:
            self.reward_btn.setText("今日奖励已领取")
        else:
            self.reward_btn.setText("领取每日奖励")

    def _claim_reward(self):
        """领取每日奖励。"""
        if self.engine.claim_arena_daily_reward():
            QMessageBox.information(self, "领取成功", "奖励已发放，请查看修为与背包。")
        self._refresh_status()

    def _start_fight(self):
        """开始一场切磋战斗。"""
        from ui.combat_dialog import CombatDialog
        enemy = self.engine.start_arena_combat()
        if not enemy:
            return
        dialog = CombatDialog(self.engine.player, enemy, self.engine, parent=self)
        # 连接战斗结束信号，更新连胜状态
        dialog.combat_finished.connect(self._on_combat_finished)
        dialog.exec()
        self._refresh_status()

    def _open_ranking(self):
        """打开擂台排名挑战弹窗。"""
        from ui.arena_ranking_dialog import ArenaRankingDialog
        dialog = ArenaRankingDialog(self.engine, parent=self)
        dialog.exec()
        self._refresh_status()

    def _on_combat_finished(self, result):
        """战斗结束后根据结果更新连胜。"""
        victory = result == "win"
        self.engine.arena_fight_finished(victory)
