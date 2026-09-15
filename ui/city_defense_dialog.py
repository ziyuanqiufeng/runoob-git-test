# -*- coding: utf-8 -*-
"""
城池守城战弹窗：妖兽攻城事件参与界面。

显示当前城池活跃事件信息，并引导玩家逐波参与守城战斗。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt


class CityDefenseDialog(QDialog):
    """城池守城战参与弹窗。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.player = engine.player

        self.setWindowTitle("城池守城")
        self.resize(460, 320)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("<h2>城池守城</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 事件信息显示
        self.event_label = QLabel()
        self.event_label.setAlignment(Qt.AlignCenter)
        self.event_label.setWordWrap(True)
        self.event_label.setStyleSheet("font-size: 14px; padding: 8px;")
        layout.addWidget(self.event_label)

        # 状态提示
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
        layout.addWidget(self.status_label)

        # 加入守城按钮
        self.defend_btn = QPushButton("加入守城")
        self.defend_btn.setToolTip("参与守城，连续击败多波妖兽以保卫城池。")
        self.defend_btn.clicked.connect(self._on_defend)
        layout.addWidget(self.defend_btn)

        # 关闭按钮
        close_btn = QPushButton("离开")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)

        self._refresh()

    def _refresh(self):
        """刷新事件信息与按钮状态。"""
        event = self.engine.get_active_city_event()
        if not event:
            self.event_label.setText(
                "<span style='color:#666;'>当前城池风平浪静，暂无妖兽攻城事件。</span>"
            )
            self.status_label.setText("")
            self.defend_btn.setEnabled(False)
            return

        self.event_label.setText(
            f"<b style='color:#c0392b;'>【{event['name']}】</b><br>"
            f"{event['description']}"
        )
        enemy_count = event.get("enemy_count", 1)
        self.status_label.setText(f"预计来袭波次：<b>{enemy_count}</b>")
        self.defend_btn.setEnabled(True)

    def _on_defend(self):
        """加入守城并开始逐波战斗。"""
        event, enemies = self.engine.join_city_defense()
        if not event or not enemies:
            self._refresh()
            return

        self.defend_btn.setEnabled(False)
        self.status_label.setText(f"守城开始，共 {len(enemies)} 波妖兽！")

        # 依次进行多场战斗
        wave = 0
        while True:
            enemy = self.engine.get_next_city_defense_enemy()
            if enemy is None:
                break

            wave += 1
            self.status_label.setText(f"当前第 {wave}/{len(enemies)} 波战斗中……")

            from ui.combat_dialog import CombatDialog
            self.engine.start_combat(enemy, is_city_defense=True)
            dialog = CombatDialog(
                self.player, enemy, self.engine, parent=self
            )
            dialog.exec()

            # 检查玩家是否存活
            if not self.player.is_alive():
                QMessageBox.warning(
                    self, "守城失败", "你在守城战中负伤，妖兽突破防线。"
                )
                self._refresh()
                return

        # 全部波次胜利
        event_after = self.engine.get_active_city_event()
        if not event_after:
            QMessageBox.information(
                self, "守城成功", "你成功击退兽潮，奖励已发放。"
            )
        else:
            QMessageBox.information(
                self, "守城暂停", "当前波次已击退，事件仍在进行中。"
            )
        self._refresh()
