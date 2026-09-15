from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QRadialGradient, QPolygonF,
)

import json
import os


def _load_feature_flags():
    """读取 feature_flags.json；缺省/解析失败视为全部开启。"""
    try:
        with open("config/feature_flags.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("flags", {})
    except Exception:
        return {}


def _is_3d_bg_enabled():
    """是否启用 3D 写实地图背景（feature_flags 主开关）。"""
    flags = _load_feature_flags()
    return flags.get("map_3d_background", True)


_PREFS_PATH = os.path.join("config", "ui_prefs.json")


def _load_ui_pref_3d(default):
    """读取用户持久化的地图风格偏好（config/ui_prefs.json 的 map_3d_enabled）。"""
    try:
        if os.path.exists(_PREFS_PATH):
            with open(_PREFS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            val = data.get("map_3d_enabled")
            if isinstance(val, bool):
                return val
    except Exception:
        pass
    return default


def _save_ui_pref_3d(enabled):
    """把地图风格偏好写回 config/ui_prefs.json（保留其他键）。"""
    try:
        data = {}
        if os.path.exists(_PREFS_PATH):
            with open(_PREFS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["map_3d_enabled"] = bool(enabled)
        os.makedirs(os.path.dirname(_PREFS_PATH), exist_ok=True)
        with open(_PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class MapWidget(QWidget):
    """简易地图控件，用不同颜色、形状标记不同类型地点，支持缩放。"""

    location_clicked = Signal(str)  # 点击地点时发出 location_id
    style_changed = Signal(bool)    # 2D/3D 风格切换时发出（True=3D）

    # 境界 ID → 中文名映射（用于地图推荐境界提示）
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

    # 地点类型 → 形状标识
    # wild: 圆形（野外）, city: 圆角矩形（城市）, sect: 菱形（宗门）
    _TYPE_SHAPES = {
        "wild": "circle",
        "city": "square",
        "sect": "diamond",
    }

    # 地点类型 → 中文名（用于图例）
    _TYPE_NAMES = {
        "wild": "野外",
        "city": "城市",
        "sect": "宗门",
    }

    def __init__(self, world, engine=None, parent=None, use_3d=None):
        super().__init__(parent)
        self.world = world
        self.engine = engine
        self.current_location_id = "qingyun"
        self.hovered_location_id = None
        # 缩放因子：初始为 1.0，滚轮可缩放范围 0.5 ~ 2.0
        self.zoom_factor = 1.0
        self.setMinimumSize(760, 680)
        self.setMouseTracking(True)  # 开启鼠标追踪，用于悬停提示

        # 3D 写实背景主开关（来自 feature_flags 的 map_3d_background）
        self._feature_3d = _is_3d_bg_enabled()
        # 运行时风格：优先用传入值；否则读持久化偏好，缺省跟随功能开关
        if use_3d is None:
            self._use_3d = _load_ui_pref_3d(default=self._feature_3d)
            if not self._feature_3d:
                self._use_3d = False
        else:
            self._use_3d = bool(use_3d) and self._feature_3d

        # 仅在功能开启时加载 3D 背景图（运行时切换无需重新加载）
        self._bg_image = None
        if self._feature_3d:
            self._load_3d_background()
        # 2D 写实背景图（独立于 feature_flags 开关，缺图自动回退渐变）
        self._bg_2d_image = None
        self._load_2d_background()

        # 数据坐标范围（用于与 tools/bake_map_labels.py 烧录的标注对齐）
        self._IMG_SIZE = 1024
        self._IMG_MARGIN = 120
        _locs = list(self.world.locations.values())
        self._xmin = min(l["x"] for l in _locs)
        self._xmax = max(l["x"] for l in _locs)
        self._ymin = min(l["y"] for l in _locs)
        self._ymax = max(l["y"] for l in _locs)

    # ---- 2D / 3D 风格运行时节切换 ----
    def is_3d_enabled(self):
        """当前是否使用 3D 写实背景风格。"""
        return self._use_3d

    def is_feature_available(self):
        """3D 写实背景功能是否可用（受 feature_flags 控制）。"""
        return self._feature_3d

    def set_3d_enabled(self, enabled, persist=True):
        """运行时切换 2D/3D 风格；persist=True 时写回 ui_prefs.json。"""
        new_state = bool(enabled) and self._feature_3d
        if new_state == self._use_3d:
            return
        self._use_3d = new_state
        if persist and self._feature_3d:
            _save_ui_pref_3d(new_state)
        self.update()
        self.style_changed.emit(self._use_3d)

    def _load_3d_background(self):
        """加载 3D 地图背景图，失败时静默回退为 2D 渐变。

        加载的是 world_3d_unlabeled.png（原始 AI 图，未烧录文字），
        避免与烧录进 world_3d.png 的标签在游戏中重复叠加。
        """
        try:
            from PySide6.QtGui import QPixmap
            bg_path = os.path.join("assets", "maps", "world_3d_unlabeled.png")
            if os.path.exists(bg_path):
                self._bg_image = QPixmap(bg_path)
        except Exception:
            self._bg_image = None

    def _load_2d_background(self):
        """加载 2D 写实地图背景图（world_2d_unlabeled.png，原始未标注图），失败时静默回退为淡雅渐变。

        加载的是未烧录文字的原图，游戏内的地点名称仍由 Qt 在运行时叠加绘制；
        烧录进 world_2d.png 的标注图作为独立成品用于预览/分享。
        """
        try:
            from PySide6.QtGui import QPixmap
            bg_path = os.path.join("assets", "maps", "world_2d_unlabeled.png")
            if os.path.exists(bg_path):
                self._bg_2d_image = QPixmap(bg_path)
        except Exception:
            self._bg_2d_image = None

    def set_current_location(self, location_id):
        """设置当前位置并重绘。"""
        self.current_location_id = location_id
        self.update()

    def _is_unlocked(self, location_id):
        """判断地点是否已解锁。"""
        if self.engine:
            return self.engine.is_location_unlocked(location_id)
        return True

    def _to_screen(self, x, y):
        """将地点逻辑坐标转换为屏幕坐标。

        与 tools/bake_map_labels.py 的变换对齐：保证游戏内绘制的
        当前位置光环、悬停高亮恰好落在已烧录进图片的圆点上。
        """
        W = self.width()
        H = self.height()
        IW = IH = self._IMG_SIZE
        # 与 paintEvent 中背景绘制（KeepAspectRatioByExpanding + 居中）一致
        scale = max(W / IW, H / IH)
        off_x = (W - IW * scale) / 2
        off_y = (H - IH * scale) / 2
        nx = (x - self._xmin) / (self._xmax - self._xmin) if self._xmax > self._xmin else 0.5
        ny = (y - self._ymin) / (self._ymax - self._ymin) if self._ymax > self._ymin else 0.5
        ix = self._IMG_MARGIN + nx * (IW - 2 * self._IMG_MARGIN)
        iy = self._IMG_MARGIN + ny * (IH - 2 * self._IMG_MARGIN)
        return off_x + ix * scale, off_y + iy * scale

    def paintEvent(self, event):
        """绘制地图：3D 写实背景 + 流光路径 + 节点 + 当前位置光环。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1) 背景：根据当前风格（3D/2D）选择对应写实背景图；都没有时回退渐变+网格
        bg = None
        mask_alpha = 25  # 蒙版透明度：写实背景上加一层薄蒙版让节点标注清晰
        if self._use_3d and self._bg_image is not None and not self._bg_image.isNull():
            bg = self._bg_image
            mask_alpha = 40  # 3D 背景略亮，蒙版稍深
        elif not self._use_3d and self._bg_2d_image is not None and not self._bg_2d_image.isNull():
            bg = self._bg_2d_image

        if bg is not None:
            scaled = bg.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
            )
            # 居中绘制（scaled 可能比控件大，按中心对齐）
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            # 覆盖一层半透蒙版，让节点在亮处也能看清
            painter.fillRect(self.rect(), QColor(20, 30, 50, mask_alpha))
        else:
            gradient = QLinearGradient(0, 0, 0, self.height())
            gradient.setColorAt(0, QColor(245, 247, 250))
            gradient.setColorAt(1, QColor(235, 240, 245))
            painter.fillRect(self.rect(), gradient)
            # 仅在无背景图时画网格纹理
            self._draw_grid(painter)

        # 字体
        font = QFont("Microsoft YaHei", 10)
        painter.setFont(font)

        # 绘制地点之间的连线：金色虚线 + 柔光（在 3D 背景上更醒目）
        locations = list(self.world.locations.values())
        line_pen = QPen(QColor(232, 201, 122, 200))
        line_pen.setWidth(int(2 * self.zoom_factor))
        line_pen.setStyle(Qt.DotLine)
        line_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(line_pen)
        for i in range(len(locations) - 1):
            x1, y1 = self._to_screen(locations[i]["x"], locations[i]["y"])
            x2, y2 = self._to_screen(locations[i + 1]["x"], locations[i + 1]["y"])
            painter.drawLine(x1, y1, x2, y2)

        # 绘制地点
        for loc_id, loc in self.world.locations.items():
            x, y = self._to_screen(loc["x"], loc["y"])
            is_current = loc_id == self.current_location_id
            is_unlocked = self._is_unlocked(loc_id)
            is_hovered = loc_id == self.hovered_location_id
            loc_type = loc.get("type", "wild")

            if is_current:
                base_color = QColor(46, 204, 113)  # 绿色：当前位置
                glow_color = QColor(46, 204, 113, 80)
            elif not is_unlocked:
                base_color = QColor(149, 165, 166)  # 灰色：未解锁
                glow_color = QColor(149, 165, 166, 40)
            elif is_hovered:
                base_color = QColor(241, 196, 15)  # 金色：悬停
                glow_color = QColor(241, 196, 15, 100)
            else:
                # 根据类型分配不同基础色调
                if loc_type == "city":
                    base_color = QColor(155, 89, 182)  # 紫色：城市
                    glow_color = QColor(155, 89, 182, 80)
                elif loc_type == "sect":
                    base_color = QColor(52, 152, 219)  # 蓝色：宗门
                    glow_color = QColor(52, 152, 219, 80)
                else:
                    base_color = QColor(241, 196, 15)  # 金色：野外
                    glow_color = QColor(241, 196, 15, 60)

            radius = int(18 * self.zoom_factor)

            # 外发光
            if is_current or is_hovered or is_unlocked:
                glow_radius = radius + int(10 * self.zoom_factor)
                radial = QRadialGradient(x, y, glow_radius)
                radial.setColorAt(0, glow_color)
                radial.setColorAt(1, QColor(0, 0, 0, 0))
                painter.setBrush(QBrush(radial))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(x - glow_radius, y - glow_radius,
                                    glow_radius * 2, glow_radius * 2)

            # 统一绘制发光圆点（更现代、更易识别）
            painter.setBrush(QBrush(base_color))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)

            # 内部高光点
            inner_r = int(radius * 0.35)
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(x - inner_r, y - inner_r, inner_r * 2, inner_r * 2)

            # 当前位置：额外绘制一个旋转的光环（用同心圆模拟）
            if is_current:
                ring_pen = QPen(QColor(46, 204, 113), 3)
                ring_pen.setStyle(Qt.DashLine)
                painter.setPen(ring_pen)
                painter.setBrush(Qt.NoBrush)
                ring_r = radius + int(8 * self.zoom_factor)
                painter.drawEllipse(x - ring_r, y - ring_r, ring_r * 2, ring_r * 2)

            # 地点名称（白色文字 + 黑色描边，确保 3D 背景上清晰可读）
            text = loc["name"]
            if not is_unlocked:
                text += "（锁）"
            text_width = int(90 * self.zoom_factor)
            text_height = int(24 * self.zoom_factor)
            # 先画一层深色描边作为阴影
            painter.setPen(QPen(QColor(0, 0, 0, 200), 3))
            painter.drawText(int(x - text_width / 2), int(y + radius + 10),
                             text_width, text_height, Qt.AlignCenter, text)
            # 再覆盖白色文字
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(int(x - text_width / 2), int(y + radius + 10),
                             text_width, text_height, Qt.AlignCenter, text)

        # 绘制 subtle 图例
        self._draw_legend(painter)

        painter.end()

    def _draw_grid(self, painter):
        """绘制淡色网格作为背景纹理。"""
        grid_pen = QPen(QColor(189, 195, 199, 40))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        step = 40
        for x in range(0, self.width(), step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            painter.drawLine(0, y, self.width(), y)

    def _draw_legend(self, painter):
        """在右下角绘制 subtle 图例。"""
        legend_x = self.width() - 110
        legend_y = self.height() - 80
        painter.setBrush(QBrush(QColor(255, 255, 255, 160)))
        painter.setPen(QPen(QColor(189, 195, 199, 120), 1))
        painter.drawRoundedRect(legend_x - 10, legend_y - 10, 100, 70, 8, 8)

        painter.setPen(QPen(QColor(44, 62, 80)))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(legend_x, legend_y, "图例")

        items = [
            (QColor(46, 204, 113), "当前"),
            (QColor(155, 89, 182), "城市"),
            (QColor(52, 152, 219), "宗门"),
            (QColor(241, 196, 15), "野外"),
        ]
        for i, (color, name) in enumerate(items):
            row = i // 2
            col = i % 2
            x = legend_x + col * 45
            y = legend_y + 18 + row * 20
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(x, y - 5, 10, 10)
            painter.setPen(QPen(QColor(44, 62, 80)))
            painter.drawText(int(x + 14), int(y - 10), 30, 20, Qt.AlignVCenter, name)

    def wheelEvent(self, event):
        """鼠标滚轮缩放地图。"""
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_factor = min(2.0, self.zoom_factor + 0.1)
        else:
            self.zoom_factor = max(0.5, self.zoom_factor - 0.1)
        self.update()

    def mousePressEvent(self, event):
        """点击地点时触发。"""
        click_x = event.pos().x()
        click_y = event.pos().y()

        # 找到点击位置最近的地点（考虑缩放后的半径）
        for loc_id, loc in self.world.locations.items():
            sx, sy = self._to_screen(loc["x"], loc["y"])
            dx = click_x - sx
            dy = click_y - sy
            if dx * dx + dy * dy <= (22 * self.zoom_factor) ** 2:
                self.location_clicked.emit(loc_id)
                break

    def mouseMoveEvent(self, event):
        """鼠标移动时检测悬停。"""
        x = event.pos().x()
        y = event.pos().y()
        old_hover = self.hovered_location_id
        self.hovered_location_id = None

        for loc_id, loc in self.world.locations.items():
            sx, sy = self._to_screen(loc["x"], loc["y"])
            dx = x - sx
            dy = y - sy
            if dx * dx + dy * dy <= (22 * self.zoom_factor) ** 2:
                self.hovered_location_id = loc_id
                # 设置工具提示：名称 + 类型 + 描述 + 推荐境界 + 解锁状态
                loc_type = loc.get("type", "wild")
                type_name = self._TYPE_NAMES.get(loc_type, loc_type)
                tooltip = f"{loc['name']} [{type_name}]\n{loc['description']}"
                # 推荐境界标识（帮助玩家判断是否已具备进入实力）
                rec_realm = loc.get("recommended_realm")
                if rec_realm:
                    realm_name = self._REALM_NAMES.get(rec_realm, rec_realm)
                    tooltip += f"\n[建议境界: {realm_name}]"
                if not self._is_unlocked(loc_id):
                    tooltip += "\n[未解锁]"
                else:
                    # 非当前地点时显示旅行耗时预览
                    if loc_id != self.current_location_id and self.engine:
                        preview = self.engine.travel_cost_model.get_cost_preview(loc_id)
                        if preview["free"]:
                            if preview["can_flight"]:
                                tooltip += "\n[旅行: 御剑飞行，不耗时]"
                            elif preview["has_mount"]:
                                tooltip += "\n[旅行: 坐骑代步，不耗时]"
                        else:
                            base = preview["base_months"]
                            actual = preview["actual_months"]
                            stones = preview["consumed_stones"]
                            cost_text = f"[旅行: 约 {actual} 个月"
                            if actual < base:
                                cost_text += f"，基础 {base} 个月"
                            if stones > 0:
                                cost_text += f"，消耗 {stones} 灵石"
                            cost_text += "]"
                            tooltip += f"\n{cost_text}"
                self.setToolTip(tooltip)
                break
        else:
            self.setToolTip("滚动鼠标滚轮可缩放地图，点击地点可快速前往")

        if old_hover != self.hovered_location_id:
            self.update()
