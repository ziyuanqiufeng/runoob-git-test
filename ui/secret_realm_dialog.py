# -*- coding: utf-8 -*-
"""Roguelike 秘境探索主弹窗（F-03）。

- 设置界面：选择秘境 / 难度 / 编成队伍，开启探索。
- 探索界面：节点连线图（杀戮尖塔风格），点击可达节点推进；
  战斗节点复用现有 CombatDialog 并临时应用卡牌增益；事件 / 商店节点各有子弹窗；
  击败 Boss 即通关，灵气值耗尽或战败则退出。秘境币可兑换稀有物品。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QMessageBox,
)

from ui.realm_card_dialog import CardSelectDialog
from ui.realm_event_dialog import EventDialog
from ui.realm_shop_dialog import ShopDialog
from ui.realm_party_dialog import PartyDialog

NODE_COLOR = {
    "battle": "#e74c3c",
    "elite": "#e67e22",
    "event": "#3498db",
    "shop": "#27ae60",
    "boss": "#f1c40f",
}
NODE_LABEL = {"battle": "战", "elite": "精", "event": "事", "shop": "商", "boss": "王"}


class MapView(QWidget):
    nodeClicked = Signal(str)

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setMinimumSize(620, 440)
        self.node_rects = {}
        self._compute_layout()

    def set_manager(self, manager):
        self.manager = manager
        self._compute_layout()
        self.update()

    def _compute_layout(self):
        self.node_rects = {}
        run = self.manager.current_run()
        if not run:
            return
        layers = run["map"]
        W = max(self.width(), 620)
        H = max(self.height(), 440)
        margin_x, margin_y = 40, 30
        cols = len(layers)
        col_gap = (W - 2 * margin_x) / max(1, cols - 1) if cols > 1 else 0
        for li, layer in enumerate(layers):
            x = margin_x + li * col_gap
            n = len(layer)
            row_gap = (H - 2 * margin_y) / max(1, n)
            for ni, node in enumerate(layer):
                y = margin_y + (ni + 0.5) * row_gap if n > 0 else H / 2
                self.node_rects[node["id"]] = (
                    int(x - 18), int(y - 18), 36, 36
                )

    def resizeEvent(self, event):
        self._compute_layout()
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        run = self.manager.current_run()
        if not run:
            return
        available = set(self.manager.get_available_node_ids())
        current = run.get("current_node_id")
        p.setPen(QPen(QColor("#bbb"), 1))
        for layer in run["map"]:
            for node in layer:
                r = self.node_rects.get(node["id"])
                if not r:
                    continue
                for tid in node["edges"]:
                    tr = self.node_rects.get(tid)
                    if tr:
                        p.drawLine(r[0] + 18, r[1] + 18, tr[0] + 18, tr[1] + 18)
        for layer in run["map"]:
            for node in layer:
                r = self.node_rects.get(node["id"])
                if not r:
                    continue
                color = QColor(NODE_COLOR.get(node["type"], "#888"))
                if node["id"] in available:
                    p.setBrush(color)
                    p.setPen(QPen(QColor("#222"), 2))
                elif node["id"] == current:
                    p.setBrush(color)
                    p.setPen(QPen(QColor("#000"), 3))
                else:
                    p.setBrush(color.lighter(165))
                    p.setPen(QPen(QColor("#999"), 1))
                p.drawEllipse(r[0], r[1], r[2], r[3])
                p.setPen(QColor("#fff"))
                p.drawText(r[0], r[1], r[2], r[3], Qt.AlignCenter,
                           NODE_LABEL.get(node["type"], "?"))

    def mousePressEvent(self, event):
        for nid, r in self.node_rects.items():
            if (r[0] <= event.position().x() <= r[0] + r[2] and
                    r[1] <= event.position().y() <= r[1] + r[3]):
                if nid in self.manager.get_available_node_ids():
                    self.nodeClicked.emit(nid)
                break


class SecretRealmDialog(QDialog):
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.manager = engine.secret_realm_manager
        self.setWindowTitle("秘境探索")
        self.resize(720, 560)
        self._party = None
        self._saved_mods = None
        self._combat_restored = True
        self._build()

    def _build(self):
        self.layout = QVBoxLayout(self)
        if self.manager.is_run_active():
            self._show_run_view()
        else:
            self._show_setup_view()

    # ---------------- 设置界面 ----------------
    def _show_setup_view(self):
        self._clear_layout()
        box = QFrame()
        box.setFrameShape(QFrame.Box)
        v = QVBoxLayout(box)
        v.addWidget(QLabel("选择秘境："))
        self.realm_combo = QComboBox()
        for realm in self.manager.list_realms():
            ok, _msg = self.manager.can_enter(realm["id"])
            label = f"{realm['name']}（{realm['floors']}层）" + ("" if ok else "  [未解锁]")
            self.realm_combo.addItem(label, realm["id"])
            if not ok:
                idx = self.realm_combo.count() - 1
                self.realm_combo.setItemData(idx, False, Qt.UserRole - 1)
        v.addWidget(self.realm_combo)

        v.addWidget(QLabel("选择难度："))
        self.diff_combo = QComboBox()
        for d in self.manager.get_difficulties():
            self.diff_combo.addItem(f"{d['name']} — {d.get('description','')}", d["id"])
        v.addWidget(self.diff_combo)

        self.party_label = QLabel("队伍：你本人（点击「编成队伍」可带至多 2 名追随者）")
        v.addWidget(self.party_label)
        party_btn = QPushButton("编成队伍")
        party_btn.clicked.connect(self._open_party)
        v.addWidget(party_btn)

        enter = QPushButton("进入秘境")
        enter.clicked.connect(self._start_run)
        v.addWidget(enter)

        self.layout.addWidget(box)
        self.layout.addStretch(1)

    def _open_party(self):
        dlg = PartyDialog(self.engine.player, self.engine.follower_library, parent=self)
        dlg.party_selected.connect(self._on_party_selected)
        dlg.exec()

    def _on_party_selected(self, party):
        self._party = party
        names = "、".join(m["name"] for m in party)
        self.party_label.setText(f"队伍：{names}")

    def _start_run(self):
        realm_id = self.realm_combo.currentData()
        diff_id = self.diff_combo.currentData()
        ok, msg = self.manager.can_enter(realm_id)
        if not ok:
            QMessageBox.information(self, "无法进入", msg)
            return
        ok, msg = self.manager.start_run(realm_id, diff_id, self._party)
        if not ok:
            QMessageBox.information(self, "无法进入", msg)
            return
        self._show_run_view()

    # ---------------- 探索界面 ----------------
    def _show_run_view(self):
        self._clear_layout()
        run = self.manager.current_run()
        # 状态栏
        self.status_label = QLabel()
        self.status_label.setFrameShape(QFrame.Box)
        self.status_label.setStyleSheet("padding:6px; background:#f7f7f7;")
        self.layout.addWidget(self.status_label)

        self.map_view = MapView(self.manager, parent=self)
        self.map_view.nodeClicked.connect(self._on_node_clicked)
        self.layout.addWidget(self.map_view, 1)

        btn_row = QHBoxLayout()
        exchange = QPushButton("兑换 / 商店")
        exchange.clicked.connect(self._open_shop)
        exit_btn = QPushButton("退出秘境")
        exit_btn.clicked.connect(self._exit_run)
        btn_row.addWidget(exchange)
        btn_row.addWidget(exit_btn)
        self.layout.addLayout(btn_row)
        self._refresh_status()

    def _refresh_status(self):
        run = self.manager.current_run()
        if not run:
            return
        mods = self.manager.get_combat_mods()
        cards_desc = f"攻击+{mods['attack_pct']*100:.0f}% 防御+{mods['defense_pct']*100:.0f}% 生命+{mods['max_hp_flat']}"
        self.status_label.setText(
            f"秘境：{run['realm_id']}　难度：{run['difficulty']}　"
            f"灵气值：{run['qi']}　秘境币：{run['coins']}　"
            f"已获卡：{len(run['cards'])}　增益：{cards_desc}"
        )
        if getattr(self, "map_view", None):
            self.map_view.update()

    def _on_node_clicked(self, node_id):
        descriptor = self.manager.enter_node(node_id)
        kind = descriptor.get("kind")
        if kind in ("battle", "elite", "boss"):
            enemy = descriptor.get("enemy")
            if enemy is None:
                QMessageBox.information(self, "提示", "该节点无敌人数据，已跳过。")
                self.manager.mark_cleared(node_id)
                self._refresh_status()
                return
            self._enter_node_combat(enemy, node_id)
        elif kind == "event":
            dlg = EventDialog(descriptor.get("event", {}), parent=self)
            dlg.chosen.connect(lambda i, nid=node_id: self._on_event_chosen(i, nid))
            dlg.exec()
        elif kind == "shop":
            self._open_shop()
            self.manager.mark_cleared(node_id)
            self._refresh_status()
        else:
            self._refresh_status()

    def _enter_node_combat(self, enemy, node_id):
        mods = self.manager.get_combat_mods()
        self._apply_combat_mods(mods)
        self._combat_restored = False
        from ui.combat_dialog import CombatDialog
        dlg = CombatDialog(self.engine.player, enemy, self.engine, parent=self)
        dlg.combat_finished.connect(
            lambda r, nid=node_id: self._on_node_combat_finished(r, nid)
        )
        dlg.exec()
        if not self._combat_restored:
            self._restore_combat_mods()

    def _on_node_combat_finished(self, result, node_id):
        victory = (result == "win")
        self._restore_combat_mods()
        res = self.manager.on_battle_cleared(node_id, victory)
        if res.get("defeated"):
            self._finish_run(False)
            return
        draws = res.get("draws")
        is_boss = res.get("is_boss", False)
        if draws:
            cd = CardSelectDialog(draws, parent=self)
            cd.chosen.connect(
                lambda cid, ib=is_boss: self._on_card_chosen(cid, ib)
            )
            cd.exec()
        else:
            self._after_battle(is_boss)

    def _on_card_chosen(self, card_id, is_boss):
        if card_id:
            self.manager.add_card(card_id)
        self._after_battle(is_boss)

    def _after_battle(self, is_boss):
        if is_boss:
            self._finish_run(True)
        else:
            self._refresh_status()

    def _on_event_chosen(self, choice_index, node_id):
        res = self.manager.choose_event(node_id, choice_index)
        applied = res.get("applied", {})
        if "draws" in applied:
            cd = CardSelectDialog(applied["draws"], parent=self)
            cd.chosen.connect(
                lambda cid: (self.manager.add_card(cid) if cid else None, self._refresh_status())
            )
            cd.exec()
        else:
            self._refresh_status()

    def _open_shop(self):
        dlg = ShopDialog(self.manager.reward_mgr, self.engine.player,
                         title="秘境兑换（消耗累计秘境币）", parent=self)
        dlg.exec()
        self._refresh_status()

    def _apply_combat_mods(self, mods):
        p = self.engine.player
        self._saved_mods = {
            "base_attack": p.base_attack,
            "base_defense": p.base_defense,
            "max_health": p.max_health,
            "health": p.health,
        }
        p.base_attack = int(p.base_attack * (1 + mods["attack_pct"]))
        p.base_defense = int(p.base_defense * (1 + mods["defense_pct"]))
        p.max_health = p.max_health + mods["max_hp_flat"]
        p.health = min(p.health + mods["max_hp_flat"], p.max_health)

    def _restore_combat_mods(self):
        if self._saved_mods is None:
            return
        p = self.engine.player
        p.base_attack = self._saved_mods["base_attack"]
        p.base_defense = self._saved_mods["base_defense"]
        p.max_health = self._saved_mods["max_health"]
        p.health = min(p.health, p.max_health)  # 保留战斗造成的真实损血
        self._saved_mods = None
        self._combat_restored = True

    def _exit_run(self):
        if self.manager.is_run_active():
            self._finish_run(False)
        else:
            self.reject()

    def _finish_run(self, victory):
        summary = self.manager.end_run(victory)
        lines = [
            f"秘境探索结束：{'通关！' if victory else '退出。'}",
            f"本局获得秘境币：{summary.get('coins_earned', 0)}",
            f"累计秘境币：{summary.get('total_realm_coins', 0)}",
            f"获得增益卡：{len(summary.get('cards_owned', []))} 张",
        ]
        QMessageBox.information(self, "秘境结算", "\n".join(lines))
        self.accept()

    def _clear_layout(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
