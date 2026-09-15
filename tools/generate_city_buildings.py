# -*- coding: utf-8 -*-
"""
为 config/city_maps.json 中配置的热点生成独立建筑占位图。

生成规则：
- 每个建筑生成普通图 {building_id}.png 与高亮图 {building_id}_hover.png；
- 图片尺寸由热点 coords 宽高比例决定，基础宽度约 160px；
- 形状与 city_maps.json 中的 shape 一致（rect/circle/diamond/polygon）；
- 图片带透明通道，可直接被 CityBuildingWidget 加载；
- 图片不再自带文字，文字由 CityBuildingWidget.name_label 统一显示。

后续替换正式美术资源时，保持文件名一致即可。
"""
import json
import os

from PIL import Image, ImageDraw


CONFIG_PATH = os.path.join("config", "city_maps.json")
OUTPUT_ROOT = os.path.join("assets", "city_buildings")
BASE_WIDTH = 160  # 普通图基础宽度，实际按 coords 比例缩放

# 建筑 ID -> 配色
BUILDING_COLORS = {
    "city_lord_hall": (142, 68, 173),    # 紫
    "inn": (211, 84, 0),                 # 橙
    "market": (39, 174, 96),             # 绿
    "arena": (192, 57, 43),              # 红
    "alchemy_pavilion": (41, 128, 185),  # 蓝
    "library": (22, 160, 133),           # 青
    "smithy": (127, 140, 141),           # 灰
    "beast_park": (141, 110, 99),        # 棕
    "aquatic_shop": (2, 136, 209),       # 水蓝
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _lerp_color(c1, c2, ratio):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * ratio) for i in range(3))


def _make_image(width, height, draw_func, base_color):
    """创建一张带透明通道的建筑图。"""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # 统一绘制建筑投影（右下角椭圆）
    shadow_w = width * 0.7
    shadow_h = height * 0.2
    draw.ellipse(
        [(width - shadow_w) / 2, height - shadow_h - 2,
         (width + shadow_w) / 2, height - 2],
        fill=(0, 0, 0, 60)
    )
    draw_func(draw, width, height, base_color)
    return image


def _draw_rect_building(draw, width, height, color):
    """绘制带屋顶的矩形建筑（客栈/炼丹阁风格）。"""
    body_top = int(height * 0.25)
    body_bottom = int(height * 0.85)
    left = int(width * 0.15)
    right = int(width * 0.85)

    # 墙体
    body_color = (*color, 200)
    outline = (*_lerp_color(color, (0, 0, 0), 0.3), 230)
    draw.rectangle([left, body_top, right, body_bottom], fill=body_color, outline=outline, width=2)

    # 屋顶
    roof_points = [
        (left - 8, body_top),
        (width // 2, int(height * 0.08)),
        (right + 8, body_top),
    ]
    roof_color = (*_lerp_color(color, (80, 60, 50), 0.35), 220)
    draw.polygon(roof_points, fill=roof_color, outline=outline)

    # 门
    door_w = (right - left) // 3
    door_h = (body_bottom - body_top) // 2
    door_x = (width - door_w) // 2
    door_y = body_bottom - door_h - 2
    draw.rectangle([door_x, door_y, door_x + door_w, body_bottom - 2],
                   fill=(60, 40, 30, 180), outline=(40, 25, 20, 200))

    # 窗户
    win_size = min(door_w // 2, 14)
    for wx in (left + 10, right - 10 - win_size):
        draw.rectangle([wx, body_top + 10, wx + win_size, body_top + 10 + win_size],
                       fill=(255, 240, 180, 160), outline=(80, 70, 50, 180))


def _draw_circle_building(draw, width, height, color):
    """绘制圆顶建筑（坊市/演武场风格）。"""
    cx, cy = width // 2, int(height * 0.55)
    r = min(width, height) // 2 - 8

    # 主体圆顶
    dome_color = (*color, 200)
    outline = (*_lerp_color(color, (0, 0, 0), 0.3), 230)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=dome_color, outline=outline, width=2)

    # 顶部尖顶
    spire_points = [
        (cx, int(height * 0.08)),
        (cx - 6, cy - r),
        (cx + 6, cy - r),
    ]
    spire_color = (*_lerp_color(color, (255, 255, 255), 0.3), 220)
    draw.polygon(spire_points, fill=spire_color, outline=outline)

    # 拱门
    arch_r = r // 2
    draw.pieslice([cx - arch_r, cy + r // 4, cx + arch_r, cy + r // 4 + arch_r * 2],
                  start=0, end=180, fill=(60, 40, 30, 180), outline=(40, 25, 20, 200))


def _draw_diamond_building(draw, width, height, color):
    """绘制菱形多层建筑（城主府风格）。"""
    cx = width // 2
    layers = 3
    layer_h = int(height * 0.6 / layers)
    max_w = int(width * 0.75)

    outline = (*_lerp_color(color, (0, 0, 0), 0.3), 230)
    for i in range(layers):
        top = int(height * 0.15) + i * layer_h
        w = max_w - i * (max_w // (layers + 1))
        left = cx - w // 2
        right = cx + w // 2
        bottom = top + layer_h
        layer_color = (*_lerp_color(color, (0, 0, 0), i * 0.1), 200)
        draw.polygon([
            (cx, top - 4),
            (right + 4, top + layer_h // 2),
            (cx, bottom + 4),
            (left - 4, top + layer_h // 2),
        ], fill=layer_color, outline=outline)

    # 中心装饰
    draw.ellipse([cx - 6, int(height * 0.45), cx + 6, int(height * 0.55)],
                 fill=(255, 215, 0, 180), outline=(180, 140, 0, 200))


def _draw_polygon_building(draw, width, height, color, mask_points):
    """按 mask_points 填充并加高光边线的多边形建筑。"""
    points = [(int(p[0] * width), int(p[1] * height)) for p in mask_points]
    fill = (*color, 190)
    outline = (*_lerp_color(color, (255, 255, 255), 0.3), 230)
    draw.polygon(points, fill=fill, outline=outline, width=2)


def generate_building_images(city_id, hotspot, output_dir):
    """为单个热点生成普通图与高亮图。"""
    bid = hotspot["id"]
    shape = hotspot.get("shape", "rect")
    x1, y1, x2, y2 = hotspot["coords"]
    aspect = ((y2 - y1) / (x2 - x1)) if (x2 - x1) > 0 else 1.0

    width = max(80, int(BASE_WIDTH))
    height = max(80, int(width * aspect))
    color = BUILDING_COLORS.get(bid, (120, 120, 120))

    if shape == "circle":
        draw_func = _draw_circle_building
        args = ()
    elif shape == "diamond":
        draw_func = _draw_diamond_building
        args = ()
    elif shape == "polygon":
        draw_func = _draw_polygon_building
        args = (hotspot.get("mask_points", [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]]),)
    else:
        draw_func = _draw_rect_building
        args = ()

    normal = _make_image(width, height, draw_func, color, *args)
    hover = _make_image(width, height, draw_func, _lerp_color(color, (255, 255, 255), 0.25), *args)

    normal_path = os.path.join(output_dir, f"{bid}.png")
    hover_path = os.path.join(output_dir, f"{bid}_hover.png")
    normal.save(normal_path, "PNG")
    hover.save(hover_path, "PNG")
    return normal_path, hover_path


def main():
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    city_maps = load_json(CONFIG_PATH)

    generated = 0
    for cfg in city_maps:
        city_id = cfg["city_id"]
        output_dir = os.path.join(OUTPUT_ROOT, city_id)
        os.makedirs(output_dir, exist_ok=True)

        for hotspot in cfg.get("hotspots", []):
            bid = hotspot.get("id")
            if not bid:
                continue
            normal_path, hover_path = generate_building_images(city_id, hotspot, output_dir)
            generated += 1
            print(f"已生成：{normal_path}、{hover_path}")

    print(f"共生成 {generated} 组建筑占位图（含普通图与高亮图）。")


if __name__ == "__main__":
    main()
