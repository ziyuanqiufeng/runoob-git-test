"""宗门大比弹窗：报名、逐轮战斗、结算奖励。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox,
)

from ui.combat_dialog import CombatDialog


class SectTournamentDialog(QDialog):
    """宗门大比界面。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.setWindowTitle("宗门大比")
        self.resize(500, 450)
        self.engine = engine
        self.player = engine.player

        self.opponents = []
        self.current_round = 0
        self.wins = 0

        layout = QVBoxLayout(self)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.opponent_list = QListWidget()
        layout.addWidget(self.opponent_list)

        self.result_label = QLabel()
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始大比")
        self.start_btn.clicked.connect(self._on_start)
        btn_layout.addWidget(self.start_btn)

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

        self._refresh_info()

    def _refresh_info(self):
        """刷新大比信息与对手列表。"""
        event = self.engine.sect_manager.get_sect_event("tournament")
        if not event:
            self.info_label.setText("当前宗门未举办大比。")
            self.start_btn.setEnabled(False)
            return

        ok, msg = self.engine.sect_manager.can_start_tournament()
        if not ok:
            self.info_label.setText(f"【{event.name}】\n{msg}")
            self.start_btn.setEnabled(False)
        else:
            self.info_label.setText(
                f"【{event.name}】\n"
                f"共 {event.rounds} 轮，每轮胜利可获得 "
                f"{event.rewards.get('contribution_per_win', 0)} 贡献；"
                f"全胜有概率领悟宗门绝技。"
            )
            self.start_btn.setEnabled(True)

        # 预显示对手信息（此时可能尚未生成，先生成一次用于展示）
        self.opponents = self.engine.sect_manager.get_tournament_opponents()
        self.opponent_list.clear()
        for idx, enemy in enumerate(self.opponents, start=1):
            item = QListWidgetItem(
                f"第 {idx} 轮：{enemy.name}（等级 {enemy.level}）"
            )
            item.setToolTip(enemy.description)
            self.opponent_list.addItem(item)

    def _on_start(self):
        """开始宗门大比，启动第一轮战斗。"""
        ok, msg = self.engine.sect_start_tournament()
        if not ok:
            QMessageBox.information(self, "无法参加", msg)
            return

        self.current_round = 0
        self.wins = 0
        self.start_btn.setEnabled(False)
        self.result_label.setText("大比开始！")
        self._start_next_round()

    def _start_next_round(self):
        """开始下一轮战斗。"""
        if self.current_round >= len(self.opponents):
            self._finish_tournament()
            return

        enemy = self.opponents[self.current_round]
        self.result_label.setText(
            f"第 {self.current_round + 1}/{len(self.opponents)} 轮：对战 {enemy.name}"
        )

        dialog = CombatDialog(self.player, enemy, self.engine, parent=self)
        dialog.combat_finished.connect(self._on_round_finished)
        dialog.show()

    def _on_round_finished(self, result):
        """单轮战斗结束后的回调。"""
        # 关闭当前战斗弹窗
        sender = self.sender()
        if isinstance(sender, QDialog):
            sender.accept()

        if result == "win":
            self.wins += 1
            self.result_label.setText(
                f"第 {self.current_round + 1} 轮胜利！累计 {self.wins} 胜。"
            )
        else:
            self.result_label.setText(
                f"第 {self.current_round + 1} 轮失利（{result}），大比结束。"
            )
            self._finish_tournament()
            return

        self.current_round += 1
        self._start_next_round()

    def _finish_tournament(self):
        """大比结束，发放奖励并刷新信息。"""
        self.engine.sect_complete_tournament(self.wins)
        self.start_btn.setEnabled(False)
        self.result_label.setText(
            f"大比结束，你最终获得 {self.wins}/{len(self.opponents)} 场胜利。"
        )
        self._refresh_info()
