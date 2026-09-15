# -*- coding: utf-8 -*-
"""
演武场擂台排名挑战弹窗。

显示当前城池排名榜、玩家排名、今日剩余挑战次数，
并允许玩家选择可挑战的对手进行擂台战。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QListWidget, QListWidgetItem, QWidget
)
from PySide6.QtCore import Qt


class ArenaRankingDialog(QDialog):
    """演武场擂台排名挑战弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player
        self.arena = engine.arena_ranking_manager

        self.setWindowTitle("演武场·擂台排名")
        self.resize(520, 520)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("<h2>演武场·擂台排名</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 状态栏：玩家排名与剩余次数
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; padding: 6px;")
        layout.addWidget(self.status_label)

        # 说明
        desc = QLabel(
            "各城池独立设榜。未上榜者可挑战前 3 名；"
            "已上榜者每次最多向上挑战 2 个名次。每日限挑战 5 次。"
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
        layout.addWidget(desc)

        # 排行榜列表
        self.rank_list = QListWidget()
        self.rank_list.setSpacing(4)
        layout.addWidget(self.rank_list)

        # 挑战按钮
        self.challenge_btn = QPushButton("发起挑战")
        self.challenge_btn.setToolTip("选中对手后点击发起擂台挑战。")
        self.challenge_btn.clicked.connect(self._on_challenge)
        layout.addWidget(self.challenge_btn)

        # 关闭按钮
        close_btn = QPushButton("离开")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        self._refresh()

    def _refresh(self):
        """刷新状态栏与排行榜。"""
        self.engine._reset_arena_daily_if_needed()

        city_id = self.player.location_id
        city_name = self.engine.get_current_location_name()
        player_rank = self.player.arena_rank
        limit = self.arena.get_daily_challenge_limit()
        used = self.player.arena_daily_challenges
        remaining = max(0, limit - used)

        rank_text = "未上榜" if player_rank <= 0 else f"第 {player_rank} 名"
        self.status_label.setText(
            f"当前城池：<b>{city_name}</b>　"
            f"我的排名：<b>{rank_text}</b>　"
            f"今日剩余次数：<b>{remaining}</b>/{limit}"
        )

        # 填充排行榜与可挑战标记
        self.rank_list.clear()
        opponents = self.arena.get_opponents(city_id)
        challengeable = {
            o["id"] for o in self.engine.get_arena_ranking_opponents()
        }

        for idx, opp in enumerate(opponents, start=1):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, opp)

            rank_mark = "👑" if idx == 1 else f"第 {idx} 名"
            if player_rank == idx:
                rank_mark += "（你）"
            challenge_mark = "【可挑战】" if opp["id"] in challengeable else ""

            text = (
                f"{rank_mark}　{opp['title']}·{opp['name']}　"
                f"境界：{self._format_realm(opp.get('realm', ''))}　"
                f"{challenge_mark}"
            )
            item.setText(text)

            # 不可挑战的条目置灰
            if opp["id"] not in challengeable:
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                item.setForeground(Qt.gray)

            self.rank_list.addItem(item)

        self.challenge_btn.setEnabled(
            remaining > 0 and len(challengeable) > 0
        )

    @staticmethod
    def _format_realm(realm_id):
        """将境界 ID 转换为可读中文。"""
        mapping = {
            "qi_refining_early": "炼气初期",
            "qi_refining_mid": "炼气中期",
            "qi_refining_late": "炼气后期",
            "foundation_early": "筑基初期",
            "foundation_mid": "筑基中期",
            "foundation_late": "筑基后期",
            "foundation_peak": "筑基巅峰",
            "golden_core_early": "金丹初期",
            "golden_core_mid": "金丹中期",
            "golden_core_late": "金丹后期",
            "golden_core_peak": "金丹巅峰",
            "nascent_soul_early": "元婴初期",
            "nascent_soul": "元婴期",
        }
        return mapping.get(realm_id, realm_id)

    def _on_challenge(self):
        """对选中对手发起挑战。"""
        item = self.rank_list.currentItem()
        if not item:
            QMessageBox.warning(self, "未选择对手", "请先在排行榜中选中一位挑战者。")
            return

        opponent = item.data(Qt.UserRole)
        opponent_id = opponent.get("id")

        # 再次校验是否可挑战
        challengeable = self.engine.get_arena_ranking_opponents()
        if not any(o["id"] == opponent_id for o in challengeable):
            QMessageBox.warning(self, "不可挑战", "该对手目前不在你的挑战范围内。")
            self._refresh()
            return

        enemy = self.engine.start_arena_ranking_challenge(opponent_id)
        if not enemy:
            self._refresh()
            return

        from ui.combat_dialog import CombatDialog
        dialog = CombatDialog(self.player, enemy, self.engine, parent=self)
        dialog.combat_finished.connect(self._on_combat_finished)
        dialog.exec()
        self._refresh()

    def _on_combat_finished(self, result):
        """战斗结束后刷新连胜与排名状态。"""
        victory = result == "win"
        # 普通切磋连胜逻辑仍由 engine.arena_fight_finished 维护
        self.engine.arena_fight_finished(victory)
