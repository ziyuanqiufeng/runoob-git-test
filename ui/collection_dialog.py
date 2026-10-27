# -*- coding: utf-8 -*-
"""跨世图鉴：结局图鉴 + NPC 图鉴 + 试炼塔纪录（越玩越厚的 meta 收集）。"""
import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTabWidget, QScrollArea, QWidget,
    QGridLayout, QPushButton, QHBoxLayout,
)


def _load_endings(config_dir="config"):
    path = os.path.join(config_dir, "endings.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("endings", data if isinstance(data, list) else [])
    except (OSError, json.JSONDecodeError):
        return []


class CollectionDialog(QDialog):
    """修行图鉴（跨世继承）。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("修行图鉴")
        self.resize(560, 520)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        coll = getattr(self.engine.player, "meta_collection", {}) or {}
        endings_seen = set(coll.get("endings", []))
        npcs_seen = set(coll.get("npcs", []))
        npc_lib = getattr(self.engine, "npc_library", None)
        total_npcs = len(getattr(npc_lib, "npcs", {}) or {}) if npc_lib else 0
        all_endings = _load_endings(
            getattr(self.engine, "config_dir", "config"))

        head = QLabel(
            f"<h2>📖 修行图鉴</h2>"
            f"<span style='color:#6b7280;font-size:12px;'>"
            f"结局 {len(endings_seen)}/{len(all_endings)} · "
            f"人物 {len(npcs_seen)}/{total_npcs} · "
            f"试炼塔最高 {getattr(self.engine.player, 'trial_tower_best', 0)} 层"
            f"（跨世累计）</span>"
        )
        head.setAlignment(Qt.AlignCenter)
        layout.addWidget(head)

        tabs = QTabWidget()
        tabs.addTab(self._endings_tab(all_endings, endings_seen), "结局图鉴")
        tabs.addTab(self._npcs_tab(npc_lib, npcs_seen), "人物图鉴")
        layout.addWidget(tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("合上图鉴")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _endings_tab(self, all_endings, seen):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        grid = QGridLayout(w)
        grid.setSpacing(8)
        for i, ending in enumerate(all_endings):
            eid = ending.get("id")
            name = ending.get("name", eid)
            unlocked = eid in seen
            label = QLabel(
                (f"<b>{name}</b>" if unlocked else f"<span style='color:#aaa;'>？？？</span>")
                + ("" if unlocked else "<br><span style='font-size:11px;color:#bbb;'>未达成</span>")
            )
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                "padding:10px; border-radius:8px; font-size:13px;"
                + ("background:#f3e8ff; color:#6b21a8;" if unlocked
                   else "background:#f5f5f5;")
            )
            grid.addWidget(label, i // 2, i % 2)
        scroll.setWidget(w)
        return scroll

    def _npcs_tab(self, npc_lib, seen):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        grid = QGridLayout(w)
        grid.setSpacing(6)
        npcs = getattr(npc_lib, "npcs", {}) or {}
        items = sorted(npcs.items())
        for i, (nid, npc) in enumerate(items):
            unlocked = nid in seen
            name = getattr(npc, "name", nid)
            label = QLabel(
                f"<b>{name}</b>" if unlocked
                else "<span style='color:#bbb;'>未相识</span>"
            )
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                "padding:6px; font-size:12px;"
                + ("color:#1d4ed8;" if unlocked else "color:#ccc;")
            )
            grid.addWidget(label, i // 4, i % 4)
        scroll.setWidget(w)
        return scroll
