# -*- coding: utf-8 -*-
"""灵植药园管理弹窗：播种、浇水、收获。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox, QInputDialog
)


class FarmDialog(QDialog):
    """管理洞府药园的地块与作物。"""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("洞府药园")
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        self.info_label = QLabel(self._info_text())
        layout.addWidget(self.info_label)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.plant_btn = QPushButton("播种")
        self.plant_btn.clicked.connect(self._on_plant)
        btn_layout.addWidget(self.plant_btn)

        self.water_btn = QPushButton("浇水")
        self.water_btn.clicked.connect(self._on_water)
        btn_layout.addWidget(self.water_btn)

        self.harvest_btn = QPushButton("收获")
        self.harvest_btn.clicked.connect(self._on_harvest)
        btn_layout.addWidget(self.harvest_btn)

        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)
        self._refresh_list()

    def _info_text(self):
        manager = self.engine.farm_manager
        manager._ensure_default_plots()
        season = manager.config.get_season(self.engine.world.month)
        season_names = {
            "spring": "春", "summer": "夏",
            "autumn": "秋", "winter": "冬"
        }
        return f"当前季节：{season_names.get(season, season)} | 地块数：{len(self.engine.player.farm_plots)}"

    def _refresh_list(self):
        self.list_widget.clear()
        manager = self.engine.farm_manager
        manager._ensure_default_plots()
        for idx, plot in enumerate(self.engine.player.farm_plots):
            if plot is None:
                text = f"第{idx + 1}块地：空闲"
            else:
                crop = manager.config.get_crop(plot["crop_id"])
                crop_name = crop["name"] if crop else plot["crop_id"]
                state_names = {
                    "growing": "生长中",
                    "mature": "可收获",
                    "withered": "已枯萎"
                }
                state = state_names.get(plot["state"], plot["state"])
                water = "已浇水" if plot.get("watered") else "未浇水"
                text = f"第{idx + 1}块地：{crop_name} ({state}, {water}, 生长{plot['growth']})"
            item = QListWidgetItem(text)
            item.setData(256, idx)
            self.list_widget.addItem(item)
        self.info_label.setText(self._info_text())

    def _selected_plot_index(self):
        item = self.list_widget.currentItem()
        if not item:
            return None
        return item.data(256)

    def _on_plant(self):
        idx = self._selected_plot_index()
        if idx is None:
            QMessageBox.information(self, "提示", "请选择一块空地。")
            return
        manager = self.engine.farm_manager
        plantable = [
            c for c in manager.config.get_all_crops()
            if manager.can_plant(idx, c["id"])[0]
        ]
        if not plantable:
            QMessageBox.information(self, "提示", "当前没有可种植的作物（检查种子与境界）。")
            return
        names = [c["name"] for c in plantable]
        name, ok = QInputDialog.getItem(self, "播种", "选择作物：", names, 0, False)
        if not ok:
            return
        crop_id = next(c["id"] for c in plantable if c["name"] == name)
        success, msg = manager.plant(idx, crop_id)
        self.engine.notify(msg)
        if success:
            self._refresh_list()

    def _on_water(self):
        idx = self._selected_plot_index()
        if idx is None:
            QMessageBox.information(self, "提示", "请选择一块地。")
            return
        success, msg = self.engine.farm_manager.water(idx)
        self.engine.notify(msg)
        if success:
            self._refresh_list()

    def _on_harvest(self):
        idx = self._selected_plot_index()
        if idx is None:
            QMessageBox.information(self, "提示", "请选择一块地。")
            return
        success, msg = self.engine.farm_manager.harvest(idx)
        self.engine.notify(msg)
        if success:
            self._refresh_list()
