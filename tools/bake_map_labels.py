"""把 config/locations.json 中的 28 个地点名称（带类型色点、锁定标记）
用代码合成进 assets/maps/world_2d.png 与 world_3d.png，使图片本身即带标注。

设计要点：
- AI 文生图对中文支持差（会乱码），故背景图刻意不含文字；
  标注由本脚本用 PIL + 系统中文字体精确绘制，保证清晰可读。
- 坐标变换与 ui/map_widget.py 的 _to_screen 对齐：
  数据 (x,y) -> 归一化 -> 图片像素 (ix,iy)，margin=120，
  游戏内再按 KeepAspectRatioByExpanding+居中还原到屏幕，二者一致。
- 运行：项目 venv 的 python tools/bake_map_labels.py（从项目根目录）
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCS_PATH = os.path.join(ROOT, "config", "locations.json")
MAPS_DIR = os.path.join(ROOT, "assets", "maps")

FONT_PATH = "C:/Windows/Fonts/msyhbd.ttc"  # 微软雅黑 Bold
FONT_SIZE = 26

# 与 ui/map_widget.py 中的类型配色保持一致
TYPE_COLORS = {
    "city": (155, 89, 182),   # 城市：紫
    "sect": (52, 152, 219),   # 宗门：蓝
    "wild": (241, 196, 15),   # 野外：金
}

IMG_SIZE = 1024          # 背景图为 1024x1024
MARGIN = 120             # 标注安全边距（像素）


def load_locations():
    with open(LOCS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def bake(src_name, dst_name):
    locs = load_locations()
    xs = [l["x"] for l in locs]
    ys = [l["y"] for l in locs]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    img = Image.open(os.path.join(MAPS_DIR, src_name)).convert("RGBA")
    overlay = Image.new("RGBA", (IMG_SIZE, IMG_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    for loc in locs:
        nx = (loc["x"] - xmin) / (xmax - xmin) if xmax > xmin else 0.5
        ny = (loc["y"] - ymin) / (ymax - ymin) if ymax > ymin else 0.5
        ix = MARGIN + nx * (IMG_SIZE - 2 * MARGIN)
        iy = MARGIN + ny * (IMG_SIZE - 2 * MARGIN)

        color = TYPE_COLORS.get(loc.get("type", "wild"), TYPE_COLORS["wild"])

        # 外发光（柔和彩色光晕）
        d.ellipse([ix - 26, iy - 26, ix + 26, iy + 26],
                  fill=(color[0], color[1], color[2], 60))

        # 标签文字（锁定地点追加「（锁）」）
        label = loc["name"]
        if loc.get("locked"):
            label += "（锁）"
        tw = d.textlength(label, font=font)
        pw = tw + 24
        ph = 40
        px0 = ix - pw / 2
        py0 = iy + 16
        # 半透明深色底板，保证在写实背景上也清晰可读
        d.rounded_rectangle([px0, py0, px0 + pw, py0 + ph],
                            radius=10, fill=(0, 0, 0, 155))

        # 实心圆点 + 白色描边
        d.ellipse([ix - 13, iy - 13, ix + 13, iy + 13],
                  fill=(color[0], color[1], color[2], 255),
                  outline=(255, 255, 255, 255), width=3)

        # 白色文字（垂直居中于底板）
        d.text((ix - tw / 2, py0 + (ph - FONT_SIZE) / 2),
               label, font=font, fill=(255, 255, 255, 255))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(os.path.join(MAPS_DIR, dst_name))
    print(f"[ok] 标注已烧录 -> {dst_name}  ({len(locs)} 个地点)")


if __name__ == "__main__":
    bake("world_2d.png", "world_2d.png")
    bake("world_3d.png", "world_3d.png")
