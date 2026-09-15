from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QScrollArea, QFrame
)
from PySide6.QtCore import Qt


# 境界 ID → 中文名映射（用于地点卡片显示推荐境界）
_REALM_NAMES = {
    "qi_refining_1": "练气期一层",
    "qi_refining_2": "练气期二层",
    "qi_refining_3": "练气期三层",
    "qi_refining_4": "练气期四层",
    "qi_refining_5": "练气期五层",
    "qi_refining_6": "练气期六层",
    "qi_refining_7": "练气期七层",
    "qi_refining_8": "练气期八层",
    "qi_refining_9": "练气期九层",
    "foundation_early": "筑基初期",
    "foundation_mid": "筑基中期",
    "foundation_late": "筑基后期",
    "foundation_peak": "筑基圆满",
    "golden_core_early": "金丹初期",
    "golden_core_mid": "金丹中期",
    "golden_core_late": "金丹后期",
    "golden_core_peak": "金丹圆满",
    "nascent_soul": "元婴期",
}


class MapDialog(QDialog):
    """地图弹窗，显示所有地点并允许玩家前往。"""

    def __init__(self, world, current_location_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("地图")
        self.resize(450, 560)
        self.world = world
        self.current_location_id = current_location_id
        self.selected_location_id = None

        # 主布局
        layout = QVBoxLayout(self)

        # 说明文字
        info = QLabel("选择你要前往的地点：")
        layout.addWidget(info)

        # 使用滚动区域包裹地点卡片，地点较多时可滚动查看
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QFrame()
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignTop)

        # 为每个地点创建一个卡片
        for loc_id, location in world.locations.items():
            group = QGroupBox(location["name"])
            vbox = QVBoxLayout(group)

            desc = QLabel(location["description"])
            desc.setWordWrap(True)
            vbox.addWidget(desc)

            # 推荐境界标识（提醒玩家进入该地点的推荐修为）
            rec_realm = location.get("recommended_realm")
            if rec_realm:
                realm_name = _REALM_NAMES.get(rec_realm, rec_realm)
                realm_label = QLabel(f"[建议境界: {realm_name}]")
                realm_label.setStyleSheet("color: #9b59b6; font-style: italic;")
                vbox.addWidget(realm_label)

            status = QLabel()
            if loc_id == current_location_id:
                status.setText("当前位置")
                status.setStyleSheet("color: green; font-weight: bold;")
            vbox.addWidget(status)

            btn = QPushButton("前往" if loc_id != current_location_id else "已在该地")
            btn.setEnabled(loc_id != current_location_id)
            btn.clicked.connect(lambda checked, lid=loc_id: self._select(lid))
            vbox.addWidget(btn)

            container_layout.addWidget(group)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _select(self, location_id):
        """选择目标地点并关闭弹窗。"""
        self.selected_location_id = location_id
        self.accept()
