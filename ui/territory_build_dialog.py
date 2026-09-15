# -*- coding: utf-8 -*-
"""领地建造 / 升级 / 拆除弹窗（F-02）。

左栏为建筑列表（点击选中待建造建筑），右栏为领地网格；在网格中点击空格
即可放置选中建筑，点击已有建筑再点「升级选中 / 拆除选中」进行调整。
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QFrame, QScrollArea,
)
from PySide6.QtCore import Qt

from ui.territory_grid_widget import TerritoryGridWidget


class TerritoryBuildDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.territory = manager.get_territory()
        self.selected_building = None
        self.setWindowTitle("领地建造")
        self.resize(720, 560)
        self.layout = QHBoxLayout(self)

        self._build_left()
        self._build_right()

    def _build_left(self):
        left = QFrame()
        left.setFrameShape(QFrame.Box)
        left.setStyleSheet("padding:8px; background:#fafafa;")
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel("<b>选择建筑</b>（点击后在右侧网格点空位放置）"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QFrame()
        iv = QVBoxLayout(inner)
        for b in self.manager.config.buildings():
            btn = QPushButton(self._building_summary(b))
            btn.setStyleSheet("text-align:left; padding:6px;")
            btn.clicked.connect(lambda _checked, bid=b["id"]: self._select_building(bid))
            iv.addWidget(btn)
        scroll.setWidget(inner)
        lv.addWidget(scroll)

        # 选中建筑提示
        self.sel_label = QLabel("当前未选择建筑")
        lv.addWidget(self.sel_label)

        # 操作按钮
        op_row = QHBoxLayout()
        up_btn = QPushButton("升级选中")
        up_btn.clicked.connect(self._on_upgrade)
        rm_btn = QPushButton("拆除选中")
        rm_btn.clicked.connect(self._on_remove)
        op_row.addWidget(up_btn)
        op_row.addWidget(rm_btn)
        lv.addLayout(op_row)

        lv.addStretch(1)
        self.layout.addWidget(left, 0)

    def _building_summary(self, b):
        eff = "、".join(f"{k}+{v}" for k, v in b.get("effect_per_level", {}).items())
        cost = b.get("base_cost", {}).get("spirit_stone", 0)
        maxlv = b.get("max_level", 1)
        return f"{b['name']}（{b['category']}）\n耗{cost}灵石·满级{maxlv}｜{eff}"

    def _select_building(self, bid):
        self.selected_building = bid
        b = self.manager.config.get_building(bid)
        self.sel_label.setText(f"已选择：{b['name']}")

    def _build_right(self):
        right = QVBoxLayout()
        right.addWidget(QLabel("<b>领地网格</b>（点击格子放置 / 选中）"))
        self.grid = TerritoryGridWidget(self.territory, self.manager.config)
        self.grid.cell_clicked.connect(self._on_cell_click)
        right.addWidget(self.grid, 1)
        hint = QLabel("提示：先选左侧建筑→点空格放置；点已有建筑→用下方按钮升级/拆除。")
        hint.setWordWrap(True)
        right.addWidget(hint)
        self.layout.addLayout(right, 1)

    def _on_cell_click(self, r, c):
        if self.selected_building:
            ok, msg = self.manager.build_mgr.place(self.territory, r, c, self.selected_building)
            QMessageBox.information(self, "建造", msg)
            if ok:
                self.grid.set_territory(self.territory, self.manager.config)
        else:
            cell = self.territory["grid"]["cells"][r][c]
            if cell:
                b = self.manager.config.get_building(cell["building_id"])
                QMessageBox.information(
                    self, "建筑信息",
                    f"{b['name']}（Lv{cell['level']}）\n"
                    f"可点「升级选中 / 拆除选中」操作。"
                )

    def _on_upgrade(self):
        if not self.grid.selected:
            QMessageBox.information(self, "升级", "请先在网格中点选一座建筑。")
            return
        r, c = self.grid.selected
        ok, msg = self.manager.build_mgr.upgrade(self.territory, r, c)
        QMessageBox.information(self, "升级", msg)
        if ok:
            self.grid.set_territory(self.territory, self.manager.config)

    def _on_remove(self):
        if not self.grid.selected:
            QMessageBox.information(self, "拆除", "请先在网格中点选一座建筑。")
            return
        r, c = self.grid.selected
        reply = QMessageBox.question(
            self, "拆除", "确定拆除该建筑吗？将返还一半灵石。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ok, msg = self.manager.build_mgr.remove(self.territory, r, c)
        QMessageBox.information(self, "拆除", msg)
        if ok:
            self.grid.set_territory(self.territory, self.manager.config)
