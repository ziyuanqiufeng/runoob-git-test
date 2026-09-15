"""游戏内地图预览：用 PySide6 离屏渲染 map_widget，输出 PNG 用于视觉验证。

确认 _to_screen 新变换下全部 28 个地点都在画面内，且 Qt 绘制的
圆点/标签与 tools/bake_map_labels.py 烧录位置一致。
"""
import json
import os
import sys

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ui.map_widget import MapWidget  # noqa: E402


class FakeWorld:
    def __init__(self, locs):
        self.locations = locs


def main():
    with open(os.path.join(ROOT, "config", "locations.json"), encoding="utf-8") as f:
        data = json.load(f)
    locs = {item["id"]: item for item in data}
    app = QApplication.instance() or QApplication(sys.argv)

    # 2D 风格预览
    w2d = MapWidget(FakeWorld(locs), engine=None, parent=None, use_3d=False)
    w2d.resize(800, 720)
    img2d = QImage(QSize(800, 720), QImage.Format_ARGB32)
    img2d.fill(0)
    w2d.render(img2d)
    out2d = os.path.join(ROOT, "outputs", "map_ingame_2d.png")
    os.makedirs(os.path.dirname(out2d), exist_ok=True)
    img2d.save(out2d)
    print(f"[ok] 2D in-game preview -> {out2d}")

    # 3D 风格预览
    w3d = MapWidget(FakeWorld(locs), engine=None, parent=None, use_3d=True)
    w3d.resize(800, 720)
    img3d = QImage(QSize(800, 720), QImage.Format_ARGB32)
    img3d.fill(0)
    w3d.render(img3d)
    out3d = os.path.join(ROOT, "outputs", "map_ingame_3d.png")
    img3d.save(out3d)
    print(f"[ok] 3D in-game preview -> {out3d}")


if __name__ == "__main__":
    main()