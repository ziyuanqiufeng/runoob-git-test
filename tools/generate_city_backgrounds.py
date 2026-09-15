# -*- coding: utf-8 -*-
"""
为所有配置 background_image 的城池生成统一的 2.5D 古风城镇全景背景图。

核心原则：
- 所有建筑绘制在同一张画布上，共享同一条地平线、同一组透视、同一方向光影；
- 不使用独立建筑图标，不在画面中悬浮任何“贴纸”；
- 色调统一为低饱和水墨国风，建筑之间有石板路、树木、围墙连接；
- 后续替换为正式美术资源时，保持文件名与建筑位置一致即可。
"""
import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont


CONFIG_PATH = os.path.join("config", "locations.json")
CITY_MAPS_PATH = os.path.join("config", "city_maps.json")
OUTPUT_DIR = os.path.join("assets", "city_bg")
WIDTH, HEIGHT = 800, 480

# 城池主题：天空、远山、地面主色、地面副色、建筑强调色
CITY_THEMES = {
    "luoxia_city": {
        "sky_top": (255, 190, 170),
        "sky_bottom": (245, 140, 115),
        "mountain": (195, 120, 110),
        "ground_far": (235, 205, 175),
        "ground_near": (210, 175, 145),
        "road": (195, 165, 140),
        "accent": (210, 150, 100),
    },
    "yunmeng_city": {
        "sky_top": (210, 225, 235),
        "sky_bottom": (175, 200, 220),
        "mountain": (150, 175, 195),
        "ground_far": (225, 235, 240),
        "ground_near": (200, 215, 225),
        "road": (185, 200, 210),
        "accent": (160, 190, 210),
    },
    "fufeng_city": {
        "sky_top": (215, 235, 215),
        "sky_bottom": (175, 210, 185),
        "mountain": (145, 180, 160),
        "ground_far": (220, 235, 220),
        "ground_near": (195, 220, 200),
        "road": (180, 205, 185),
        "accent": (150, 190, 160),
    },
    "wanyao_city": {
        "sky_top": (205, 195, 185),
        "sky_bottom": (170, 155, 145),
        "mountain": (140, 125, 115),
        "ground_far": (205, 190, 180),
        "ground_near": (180, 165, 155),
        "road": (165, 150, 140),
        "accent": (170, 145, 125),
    },
    "xuanshui_city": {
        "sky_top": (195, 220, 240),
        "sky_bottom": (150, 195, 225),
        "mountain": (130, 165, 190),
        "ground_far": (215, 230, 240),
        "ground_near": (190, 210, 225),
        "road": (175, 195, 210),
        "accent": (130, 180, 210),
    },
    "chiyan_city": {
        "sky_top": (250, 200, 190),
        "sky_bottom": (230, 140, 130),
        "mountain": (185, 110, 105),
        "ground_far": (235, 200, 170),
        "ground_near": (210, 170, 140),
        "road": (195, 160, 135),
        "accent": (220, 120, 100),
    },
    "wangchuan_town": {
        "sky_top": (190, 190, 190),
        "sky_bottom": (145, 145, 145),
        "mountain": (115, 115, 115),
        "ground_far": (180, 180, 180),
        "ground_near": (155, 155, 155),
        "road": (140, 140, 140),
        "accent": (130, 130, 130),
    },
    "yunlan_city": {
        "sky_top": (225, 210, 230),
        "sky_bottom": (195, 165, 210),
        "mountain": (165, 140, 185),
        "ground_far": (230, 220, 235),
        "ground_near": (210, 195, 220),
        "road": (195, 180, 205),
        "accent": (180, 150, 200),
    },
}

# 统一建筑配色：墙体、屋顶、阴影（所有建筑共用同一套低饱和色板）
BUILDING_PALETTES = {
    "city_lord_hall": {
        "wall": (165, 85, 80),
        "roof": (75, 105, 90),
        "pillar": (120, 75, 70),
        "shadow": (120, 100, 90, 90),
    },
    "inn": {
        "wall": (155, 125, 95),
        "roof": (115, 80, 65),
        "pillar": (130, 100, 75),
        "shadow": (110, 95, 80, 90),
    },
    "market": {
        "wall": (115, 130, 105),
        "roof": (95, 110, 90),
        "pillar": (105, 120, 100),
        "shadow": (100, 110, 95, 90),
    },
    "arena": {
        "wall": (140, 125, 110),
        "roof": (95, 90, 80),
        "pillar": (120, 105, 95),
        "shadow": (110, 100, 90, 90),
    },
    "alchemy_pavilion": {
        "wall": (100, 120, 140),
        "roof": (80, 100, 120),
        "pillar": (90, 110, 130),
        "shadow": (90, 105, 120, 90),
    },
    "beast_park": {
        "wall": (135, 120, 105),
        "roof": (105, 90, 80),
        "pillar": (120, 105, 95),
        "shadow": (110, 100, 90, 90),
    },
    "aquatic_shop": {
        "wall": (90, 125, 145),
        "roof": (75, 105, 125),
        "pillar": (85, 115, 135),
        "shadow": (85, 105, 125, 90),
    },
}

# 统一光源方向：左上角照入，阴影朝右下角
SHADOW_OFFSET_X = 8
SHADOW_OFFSET_Y = 10


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_font(size=20):
    candidates = ["msyh.ttc", "msyh.ttf", "simhei.ttf", "arial.ttf"]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _lerp_color(c1, c2, ratio):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * ratio) for i in range(3))


def _lerp_rgba(c1, c2, ratio):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * ratio) for i in range(4))


def _darken(color, ratio=0.2):
    """将颜色按比例变暗。"""
    return _lerp_color(color, (0, 0, 0), ratio)


def _lighten(color, ratio=0.15):
    """将颜色按比例提亮。"""
    return _lerp_color(color, (255, 255, 255), ratio)


def _draw_gradient(draw, width, height, start, end, direction="v"):
    if direction == "v":
        for y in range(height):
            ratio = y / height
            color = _lerp_color(start, end, ratio)
            draw.line([(0, y), (width, y)], fill=color)
    else:
        for x in range(width):
            ratio = x / width
            color = _lerp_color(start, end, ratio)
            draw.line([(x, 0), (x, height)], fill=color)


def _draw_soft_cloud(image, draw, cx, cy, r, color=(255, 255, 255), alpha=40):
    """绘制柔和融合的云雾团，边缘带高斯模糊。"""
    # 在临时图层上绘制，再模糊叠加，避免生硬的椭圆边缘
    size = int(r * 3)
    cloud = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(cloud)
    ox, oy = size // 2, size // 2
    for i, offset in enumerate([(0, 0), (r * 0.45, 0), (-r * 0.35, r * 0.12), (r * 0.2, -r * 0.12)]):
        rr = r * (0.7 + i * 0.08)
        cdraw.ellipse(
            [ox + offset[0] - rr, oy + offset[1] - rr // 2,
             ox + offset[0] + rr, oy + offset[1] + rr // 2],
            fill=(*color, alpha)
        )
    cloud = cloud.filter(ImageFilter.GaussianBlur(radius=max(4, r // 8)))
    image.alpha_composite(cloud, (int(cx - size // 2), int(cy - size // 2)))


def _draw_mountain_range(draw, width, horizon_y, color, peaks=5, seed=0):
    rng = random.Random(seed)
    points = [(0, horizon_y)]
    for i in range(peaks + 1):
        x = int(width * i / peaks)
        peak_h = rng.randint(50, 100)
        points.append((x, horizon_y - peak_h))
    points.append((width, horizon_y))
    draw.polygon(points, fill=(*color, 180))


def _draw_ground_plane(draw, width, height, horizon_y, theme, seed=0):
    """绘制带有透视感的石板地面，使用不规则石板与柔和边缘。"""
    rng = random.Random(seed)
    far = theme["ground_far"]
    near = theme["ground_near"]
    road = theme["road"]

    # 基础渐变：从远到近的自然过渡
    for y in range(horizon_y, height):
        ratio = (y - horizon_y) / max(1, height - horizon_y)
        color = _lerp_color(far, near, ratio)
        # 加入轻微水平噪点，打破纯色平涂感
        noise = rng.randint(-4, 4)
        c = _lerp_color(color, (255, 255, 255), 0.02) if noise > 0 else _lerp_color(color, (0, 0, 0), 0.02)
        draw.line([(0, y), (width, y)], fill=c)

    # 远处石板较小、较近石板较大，形成透视；边缘不规则，颜色带自然变化
    y = horizon_y + 12
    while y < height - 10:
        ratio = (y - horizon_y) / max(1, height - horizon_y)
        tile_h = int(8 + ratio * 18)
        tile_w = int(22 + ratio * 40)
        gap = int(2 + ratio * 2)
        x = -tile_w
        while x < width:
            base = _lerp_color(road, near, 0.25 + rng.uniform(-0.1, 0.1))
            lightness = rng.choice([-0.08, -0.04, 0, 0.04, 0.08])
            c = _lerp_color(base, (255, 255, 255), lightness) if lightness > 0 else _lerp_color(base, (0, 0, 0), -lightness)
            # 石板边缘 slight jitter，避免机械方格
            jitter_x = rng.randint(-2, 2)
            jitter_y = rng.randint(-1, 1)
            rect = [
                x + gap + jitter_x,
                y + gap + jitter_y,
                x + tile_w - gap + jitter_x,
                y + tile_h - gap + jitter_y,
            ]
            draw.rectangle(rect, fill=(*c, 160), outline=(*_darken(c, 0.12), 90))
            x += tile_w
        y += tile_h


def _draw_road(draw, points, width, theme):
    """绘制连接建筑的石板路，带有统一色调。"""
    if len(points) < 2:
        return
    road_color = theme["road"]
    # 主路
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        draw.line([(x1, y1), (x2, y2)], fill=_lighten(road_color, 0.1), width=width)
        draw.line([(x1 - 1, y1), (x2 - 1, y2)], fill=_darken(road_color, 0.1), width=2)
        draw.line([(x1 + 1, y1), (x2 + 1, y2)], fill=_darken(road_color, 0.1), width=2)


def _draw_shadow(draw, cx, cy, w, h, color):
    """绘制统一方向的柔和阴影（右下角），边缘带渐变淡出。"""
    # 主阴影区
    points = [
        (cx - w // 2 + SHADOW_OFFSET_X, cy + SHADOW_OFFSET_Y),
        (cx + w // 2 + SHADOW_OFFSET_X, cy + SHADOW_OFFSET_Y),
        (cx + w // 2 + SHADOW_OFFSET_X * 2, cy + h // 3 + SHADOW_OFFSET_Y),
        (cx - w // 2 + SHADOW_OFFSET_X * 2, cy + h // 3 + SHADOW_OFFSET_Y),
    ]
    draw.polygon(points, fill=color)


def _draw_roof_tiles(draw, x1, y1, x2, y2, roof_color, tile_h=6):
    """在屋顶区域绘制瓦片纹理。"""
    dark = _darken(roof_color, 0.2)
    for y in range(y1, y2, tile_h):
        draw.line([(x1, y), (x2, y)], fill=dark, width=1)
    for x in range(x1, x2, tile_h * 2):
        draw.line([(x, y1), (x, y2)], fill=dark, width=1)


def _draw_wall_texture(draw, x1, y1, x2, y2, wall_color, brick_w=10, brick_h=6):
    """在墙体区域绘制砖块纹理，降低平涂感。"""
    dark = _darken(wall_color, 0.18)
    for y in range(y1, y2, brick_h):
        offset = (y // brick_h % 2) * (brick_w // 2)
        for x in range(x1 - offset, x2, brick_w):
            draw.line([(x, y), (x, y + brick_h)], fill=dark, width=1)
    for y in range(y1, y2, brick_h):
        draw.line([(x1, y), (x2, y)], fill=dark, width=1)


def _draw_tree(draw, cx, cy, size, color, shadow_color, rng=None):
    """绘制水墨风格树：不规则树冠、柔和阴影、自然姿态。"""
    if rng is None:
        rng = random.Random(cx * 100 + cy)
    # 柔和投影
    draw.ellipse([cx - size // 2 + 4, cy - 3, cx + size // 2 + 8, cy + 5], fill=shadow_color)
    # 树干
    trunk_w = max(3, size // 7)
    trunk_h = size // 2
    draw.polygon([
        (cx - trunk_w // 2, cy),
        (cx + trunk_w // 2, cy),
        (cx + trunk_w // 3, cy - trunk_h),
        (cx - trunk_w // 3, cy - trunk_h),
    ], fill=(95, 78, 65))

    # 树冠：用多个不规则圆团组成，边缘略有抖动
    clusters = [
        (0, -trunk_h - size // 3, size // 2),
        (-size // 3, -trunk_h - size // 8, size // 3),
        (size // 3, -trunk_h - size // 8, size // 3),
        (0, -trunk_h - size // 2, size // 4),
    ]
    for ox, oy, r in clusters:
        # 生成不规则多边形模拟水墨晕染
        points = []
        steps = 12
        for i in range(steps):
            angle = 2 * math.pi * i / steps
            rr = r * rng.uniform(0.75, 1.05)
            px = cx + ox + math.cos(angle) * rr
            py = cy + oy + math.sin(angle) * rr * 0.85
            points.append((px, py))
        draw.polygon(points, fill=(*color, 180))
        # 内部深色点缀增加层次
        inner = _lerp_color(color, (0, 0, 0), 0.15)
        draw.ellipse([cx + ox - r // 3, cy + oy - r // 3, cx + ox + r // 3, cy + oy + r // 3], fill=(*inner, 120))


def _draw_palace(draw, cx, cy, w, h, palette):
    """城主府：双层大殿，统一透视与光影。"""
    wall = palette["wall"]
    roof = palette["roof"]
    shadow = palette["shadow"]

    base_h = h // 8
    body_h = h // 2
    w2 = int(w * 0.72)
    h2 = h // 3

    # 投影
    _draw_shadow(draw, cx, cy, w, h, shadow)

    # 台基
    draw.rectangle([cx - w // 2, cy - base_h, cx + w // 2, cy], fill=_darken(wall, 0.25))

    # 一层墙体（带侧墙形成 2.5D 厚度）
    depth = w // 12
    left = cx - w // 2
    right = cx + w // 2
    top1 = cy - base_h - body_h
    # 右侧面（背光，较暗）
    draw.polygon([
        (right, cy - base_h), (right + depth, cy - base_h - depth),
        (right + depth, top1 - depth), (right, top1)
    ], fill=_darken(wall, 0.15))
    # 正面
    draw.rectangle([left, top1, right, cy - base_h], fill=wall, outline=_darken(wall, 0.2))
    # 墙体砖块纹理
    _draw_wall_texture(draw, left + 2, top1 + 2, right - 2, cy - base_h - 2, wall, brick_w=max(8, w // 12), brick_h=max(4, h // 18))

    # 一层屋檐
    roof1_y = top1
    roof_points = [
        (left - 14, roof1_y),
        (cx, roof1_y - h // 7),
        (right + 14, roof1_y),
        (right + 8, roof1_y + 7),
        (left - 8, roof1_y + 7),
    ]
    draw.polygon(roof_points, fill=roof, outline=_darken(roof, 0.15))
    # 屋顶瓦片纹理
    _draw_roof_tiles(draw, left - 10, roof1_y - h // 7, right + 10, roof1_y + 5, roof)

    # 二层
    left2 = cx - w2 // 2
    right2 = cx + w2 // 2
    top2 = roof1_y - h2
    draw.polygon([
        (right2, roof1_y), (right2 + depth, roof1_y - depth),
        (right2 + depth, top2 - depth), (right2, top2)
    ], fill=_darken(wall, 0.1))
    draw.rectangle([left2, top2, right2, roof1_y], fill=_lighten(wall, 0.05), outline=_darken(wall, 0.2))
    _draw_wall_texture(draw, left2 + 2, top2 + 2, right2 - 2, roof1_y - 2, wall, brick_w=max(6, w2 // 12), brick_h=max(3, h2 // 10))

    # 二层屋檐
    draw.polygon([
        (left2 - 10, top2),
        (cx, top2 - h // 10),
        (right2 + 10, top2),
        (right2 + 5, top2 + 5),
        (left2 - 5, top2 + 5),
    ], fill=_lighten(roof, 0.08), outline=_darken(roof, 0.15))
    _draw_roof_tiles(draw, left2 - 8, top2 - h // 10, right2 + 8, top2 + 4, _lighten(roof, 0.08))

    # 大门
    door_w = w // 6
    door_h = body_h // 2
    draw.rectangle([cx - door_w // 2, cy - base_h - door_h, cx + door_w // 2, cy - base_h],
                   fill=_darken(wall, 0.35), outline=(80, 60, 50))

    # 匾额
    sign_w, sign_h = w // 3, h // 12
    draw.rectangle([cx - sign_w // 2, roof1_y + 8, cx + sign_w // 2, roof1_y + 8 + sign_h],
                   fill=(220, 195, 140), outline=(120, 100, 60))


def _draw_inn(draw, cx, cy, w, h, palette):
    """客栈：两层木楼，酒旗灯笼，统一透视。"""
    wall = palette["wall"]
    roof = palette["roof"]
    shadow = palette["shadow"]
    depth = w // 10

    left = cx - w // 2
    right = cx + w // 2
    bottom = cy
    top = cy - h
    mid = cy - h // 2

    _draw_shadow(draw, cx, cy, w, h, shadow)

    # 右侧面
    draw.polygon([
        (right, bottom), (right + depth, bottom - depth),
        (right + depth, top - depth), (right, top)
    ], fill=_darken(wall, 0.12))

    # 一层
    draw.rectangle([left, mid, right, bottom], fill=wall, outline=_darken(wall, 0.2))
    _draw_wall_texture(draw, left + 2, mid + 2, right - 2, bottom - 2, wall, brick_w=max(8, w // 10), brick_h=max(4, h // 16))
    # 二层
    draw.rectangle([left + 3, top, right - 3, mid], fill=_lighten(wall, 0.05), outline=_darken(wall, 0.2))
    _draw_wall_texture(draw, left + 5, top + 2, right - 5, mid - 2, wall, brick_w=max(7, w // 11), brick_h=max(3, h // 18))

    # 屋顶
    draw.polygon([
        (left - 8, top),
        (cx, top - h // 5),
        (right + 8, top),
        (right + 3, top + 5),
        (left - 3, top + 5),
    ], fill=roof, outline=_darken(roof, 0.15))
    _draw_roof_tiles(draw, left - 6, top - h // 5, right + 6, top + 4, roof)

    # 门
    door_w = w // 5
    draw.rectangle([cx - door_w // 2, mid - door_w, cx + door_w // 2, mid],
                   fill=_darken(wall, 0.3), outline=(80, 55, 45))

    # 窗户（暖光）
    win_w = w // 6
    win_h = h // 8
    for wx in (left + 8, right - 8 - win_w):
        draw.rectangle([wx, top + h // 4, wx + win_w, top + h // 4 + win_h],
                       fill=(255, 235, 195, 160), outline=(90, 75, 60))

    # 酒旗
    flag_x = right + depth + 2
    draw.line([(flag_x, top + 4), (flag_x, top + h // 3)], fill=(130, 60, 60), width=2)
    draw.polygon([
        (flag_x, top + 4),
        (flag_x + 22, top + 10),
        (flag_x, top + 18),
    ], fill=(195, 75, 75), outline=(130, 60, 60))

    # 灯笼
    for lx in (left - 5, right + 5):
        draw.ellipse([lx - 5, mid - 8, lx + 5, mid + 2], fill=(210, 95, 75), outline=(130, 60, 55))


def _draw_market(draw, cx, cy, w, h, palette):
    """坊市：沿街道排列的摊位群，与道路融合。"""
    wall = palette["wall"]
    roof = palette["roof"]
    shadow = palette["shadow"]
    rng = random.Random(cx * 100 + cy)

    # 摊位阴影区
    draw.ellipse([cx - w // 2 + 10, cy - h // 4, cx + w // 2 - 10, cy + h // 8], fill=shadow)

    stalls = 4
    for i in range(stalls):
        sx = cx - w // 2 + (w * (i + 0.5) // stalls) + rng.randint(-10, 10)
        sy = cy - h // 3 + rng.randint(-8, 8)
        sw = w // 5
        sh = h // 2
        # 棚顶（统一朝右下阴影方向）
        canopy = [
            (sx - sw // 2, sy),
            (sx + sw // 2, sy),
            (sx + sw // 2 + 6, sy - sh // 2),
            (sx - sw // 2 - 6, sy - sh // 2),
        ]
        draw.polygon(canopy, fill=_lighten(roof, 0.1), outline=_darken(roof, 0.15))
        # 棚顶布褶纹理
        for yy in range(int(sy - sh // 2), int(sy), 4):
            draw.line([(sx - sw // 2 - 6, yy), (sx + sw // 2 + 6, yy)], fill=_darken(roof, 0.1), width=1)
        # 摊位桌
        draw.rectangle([sx - sw // 3, sy, sx + sw // 3, sy + sh // 3], fill=wall,
                       outline=_darken(wall, 0.2))
        # 货物
        cargo_c = _lighten(wall, 0.25)
        for idx in range(3):
            cw = sw // 5
            ch = sh // 6
            cxx = sx - sw // 4 + idx * cw
            draw.rectangle([cxx, sy - ch, cxx + cw - 1, sy], fill=cargo_c,
                           outline=_darken(cargo_c, 0.15))


def _draw_arena(draw, cx, cy, w, h, palette):
    """演武场：木质擂台与兵器架。"""
    wall = palette["wall"]
    roof = palette["roof"]
    shadow = palette["shadow"]

    _draw_shadow(draw, cx, cy, w, h, shadow)

    # 擂台台面（2.5D 厚度）
    platform_top = cy - h // 3
    thickness = 10
    draw.polygon([
        (cx - w // 2, platform_top),
        (cx + w // 2, platform_top),
        (cx + w // 2 + 10, platform_top + thickness),
        (cx - w // 2 - 10, platform_top + thickness),
    ], fill=_darken(wall, 0.1))
    draw.polygon([
        (cx - w // 2 - 10, platform_top + thickness),
        (cx + w // 2 + 10, platform_top + thickness),
        (cx + w // 2 + 10, cy),
        (cx - w // 2 - 10, cy),
    ], fill=wall)
    # 擂台侧面木纹理
    _draw_wall_texture(draw, cx - w // 2 - 8, platform_top + thickness + 2,
                       cx + w // 2 + 8, cy - 2, wall, brick_w=max(10, w // 6), brick_h=max(4, h // 16))

    # 立柱
    post_w = 5
    for px in (cx - w // 2 + 10, cx + w // 2 - 10):
        draw.rectangle([px - post_w // 2, cy - h, px + post_w // 2, platform_top],
                       fill=(115, 90, 70), outline=(80, 65, 50))

    # 兵器架
    rack_x = cx + w // 3
    draw.rectangle([rack_x, cy - h // 2, rack_x + 6, cy], fill=(110, 90, 75))
    draw.line([(rack_x + 3, cy - h // 2), (rack_x + 3, cy - h + 4)], fill=(150, 150, 160), width=2)


def _draw_alchemy(draw, cx, cy, w, h, palette):
    """炼丹阁：多层塔楼与丹烟。"""
    wall = palette["wall"]
    roof = palette["roof"]
    shadow = palette["shadow"]
    depth = w // 10

    left = cx - w // 2
    right = cx + w // 2

    _draw_shadow(draw, cx, cy, w, h, shadow)

    # 塔身
    draw.polygon([
        (right, cy), (right + depth, cy - depth),
        (right + depth, cy - h - depth), (right, cy - h)
    ], fill=_darken(wall, 0.12))
    draw.rectangle([left, cy - h, right, cy], fill=wall, outline=_darken(wall, 0.2))
    _draw_wall_texture(draw, left + 2, cy - h + 2, right - 2, cy - 2, wall, brick_w=max(6, w // 10), brick_h=max(3, h // 14))

    # 三层屋檐
    for i in range(3):
        y = cy - h + i * (h // 4)
        rw = w - i * (w // 5)
        rcolor = _lighten(roof, i * 0.04)
        draw.polygon([
            (cx - rw // 2 - 8, y),
            (cx, y - h // 10),
            (cx + rw // 2 + 8, y),
            (cx + rw // 2 - 2, y + 4),
            (cx - rw // 2 + 2, y + 4),
        ], fill=rcolor, outline=_darken(roof, 0.15))
        _draw_roof_tiles(draw, cx - rw // 2 - 6, y - h // 10, cx + rw // 2 + 6, y + 3, rcolor)

    # 烟囱
    pipe_x = right - 10
    draw.rectangle([pipe_x, cy - h - 14, pipe_x + 7, cy - h + 4], fill=(85, 85, 85))

    # 丹烟
    smoke_color = (140, 200, 140)
    for i in range(4):
        r = 8 + i * 5
        alpha = 90 - i * 15
        draw.ellipse([pipe_x - r // 2, cy - h - 18 - i * 12, pipe_x + r // 2, cy - h - 6 - i * 12],
                     fill=(*smoke_color, alpha))

    # 门
    door_w = w // 5
    draw.rectangle([cx - door_w // 2, cy - h // 3, cx + door_w // 2, cy], fill=_darken(wall, 0.3))


def _draw_building_by_id(draw, cx, cy, w, h, bid, palette):
    if bid == "city_lord_hall":
        _draw_palace(draw, cx, cy, w, h, palette)
    elif bid == "inn":
        _draw_inn(draw, cx, cy, w, h, palette)
    elif bid == "market":
        _draw_market(draw, cx, cy, w, h, palette)
    elif bid == "arena":
        _draw_arena(draw, cx, cy, w, h, palette)
    elif bid == "alchemy_pavilion":
        _draw_alchemy(draw, cx, cy, w, h, palette)
    else:
        _draw_inn(draw, cx, cy, w, h, palette)


def _draw_atmosphere(image, width, height, theme, loc_id=None):
    """添加全局薄雾，让远景更柔和、统一；部分城市使用特色雾气。"""
    mist = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mist_draw = ImageDraw.Draw(mist)

    # 特色雾气颜色
    mist_color = theme["ground_near"]
    if loc_id == "wangchuan_town":
        mist_color = (90, 95, 100)  # 忘川镇：阴冷青灰雾气
    elif loc_id == "wanyao_city":
        mist_color = (160, 145, 130)  # 万妖城：黄褐尘雾
    elif loc_id == "yunmeng_city":
        mist_color = (190, 205, 215)  # 云梦城：淡蓝云雾
    elif loc_id == "yunlan_city":
        mist_color = (210, 200, 220)  # 云岚城：淡紫云海

    for y in range(height // 2, height):
        alpha = int(18 * (y - height // 2) / (height // 2))
        mist_draw.line([(0, y), (width, y)], fill=(*mist_color, alpha))
    image.alpha_composite(mist)


def _draw_water_river(draw, image, width, height, horizon_y, theme, seed=0):
    """玄水城：绘制蜿蜒河流与水波纹。"""
    rng = random.Random(seed)
    water_c = _lerp_color(theme["accent"], (120, 160, 185), 0.4)

    # 河流区域：从左上蜿蜒到右下
    points = []
    segments = 6
    for i in range(segments + 1):
        x = int(width * i / segments)
        base_y = horizon_y + int((height - horizon_y) * 0.45)
        y = base_y + rng.randint(-25, 25)
        points.append((x, y))

    # 绘制主河道
    river_top = []
    river_bottom = []
    river_w = max(30, width // 12)
    for x, y in points:
        river_top.append((x, y - river_w // 2))
        river_bottom.append((x, y + river_w // 2))

    river_poly = river_top + river_bottom[::-1]
    draw.polygon(river_poly, fill=(*water_c, 200), outline=(*_darken(water_c, 0.15), 160))

    # 水波纹
    for _ in range(20):
        wx = rng.randint(0, width)
        wy = rng.randint(horizon_y + 50, height - 30)
        ww = rng.randint(15, 40)
        draw.arc([wx, wy, wx + ww, wy + 6], start=0, end=180, fill=(*_lighten(water_c, 0.2), 120), width=1)


def _draw_small_bridge(draw, cx, cy, w, theme):
    """玄水城：绘制拱形石桥。"""
    wood_c = (140, 120, 100)
    # 桥身
    draw.polygon([
        (cx - w // 2, cy), (cx + w // 2, cy),
        (cx + w // 2 - 8, cy - 12), (cx - w // 2 + 8, cy - 12)
    ], fill=wood_c, outline=_darken(wood_c, 0.2))
    # 桥洞阴影
    draw.pieslice([cx - 10, cy - 4, cx + 10, cy + 16], start=0, end=180, fill=_darken(wood_c, 0.25))


def _draw_volcano(draw, image, width, height, horizon_y, theme, seed=0):
    """赤焰城：绘制远景火山与熔岩裂纹。"""
    rng = random.Random(seed)
    peak_x = width - 120
    peak_y = horizon_y - 60

    # 火山锥
    draw.polygon([
        (peak_x - 80, horizon_y), (peak_x, peak_y),
        (peak_x + 70, horizon_y)
    ], fill=theme["mountain"], outline=_darken(theme["mountain"], 0.2))

    # 火山口
    draw.ellipse([peak_x - 18, peak_y - 6, peak_x + 18, peak_y + 10], fill=(90, 50, 45))
    # 熔岩光
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([peak_x - 30, peak_y - 20, peak_x + 30, peak_y + 25], fill=(230, 100, 60, 80))
    image.alpha_composite(glow)

    # 地面熔岩裂纹
    for _ in range(8):
        sx = rng.randint(20, width - 20)
        sy = rng.randint(horizon_y + 40, height - 10)
        length = rng.randint(20, 50)
        draw.line([(sx, sy), (sx + length, sy + rng.randint(-5, 5))],
                  fill=(210, 90, 50, 150), width=2)


def _draw_sulfur_smoke(image, width, horizon_y, seed=0):
    """赤焰城：绘制硫磺烟雾。"""
    rng = random.Random(seed)
    smoke = Image.new("RGBA", (width, horizon_y + 30), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(smoke)
    for _ in range(5):
        x = rng.randint(50, width - 50)
        y = rng.randint(horizon_y - 40, horizon_y)
        r = rng.randint(20, 45)
        sdraw.ellipse([x - r, y - r // 2, x + r, y + r // 2], fill=(180, 160, 140, 50))
    smoke = smoke.filter(ImageFilter.GaussianBlur(radius=6))
    image.alpha_composite(smoke)


def _draw_beast_fence(draw, cx, cy, w, h, theme):
    """万妖城：绘制兽栏围栏。"""
    wood_c = (130, 110, 90)
    post_w = 4
    for x in range(cx - w // 2, cx + w // 2, 12):
        draw.rectangle([x, cy - h, x + post_w, cy], fill=wood_c, outline=_darken(wood_c, 0.2))
    # 横梁
    draw.rectangle([cx - w // 2, cy - h + 4, cx + w // 2, cy - h + 8], fill=wood_c)
    draw.rectangle([cx - w // 2, cy - 10, cx + w // 2, cy - 6], fill=wood_c)


def _draw_totem_pole(draw, cx, cy, h):
    """万妖城：绘制图腾柱。"""
    wood_c = (120, 95, 75)
    draw.rectangle([cx - 4, cy - h, cx + 4, cy], fill=wood_c, outline=_darken(wood_c, 0.2))
    # 图腾纹路
    for i in range(3):
        y = cy - h + 10 + i * (h // 3)
        draw.ellipse([cx - 8, y - 4, cx + 8, y + 4], fill=(170, 110, 80))
        draw.ellipse([cx - 3, y - 1, cx + 3, y + 1], fill=(60, 45, 35))


def _draw_dead_tree(draw, cx, cy, size, rng=None):
    """忘川镇：绘制枯树。"""
    if rng is None:
        rng = random.Random(cx * 100 + cy)
    # 扭曲树干
    points = [(cx, cy)]
    for i in range(5):
        points.append((cx + rng.randint(-size // 4, size // 4), cy - size + i * size // 5))
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=(75, 70, 65), width=max(3, size // 10))
    # 枯枝
    for _ in range(4):
        angle = rng.uniform(0, 2 * math.pi)
        length = rng.randint(size // 3, size // 2)
        ex = cx + math.cos(angle) * length
        ey = cy - size + math.sin(angle) * length * 0.5
        draw.line([(cx, cy - size), (ex, ey)], fill=(75, 70, 65), width=2)


def _draw_ghost_fire(image, width, height, horizon_y, seed=0):
    """忘川镇：绘制漂浮鬼火。"""
    rng = random.Random(seed)
    fires = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(fires)
    for _ in range(6):
        x = rng.randint(30, width - 30)
        y = rng.randint(horizon_y + 30, height - 20)
        r = rng.randint(4, 8)
        fdraw.ellipse([x - r, y - r, x + r, y + r], fill=(120, 220, 180, 120))
    fires = fires.filter(ImageFilter.GaussianBlur(radius=4))
    image.alpha_composite(fires)


def _draw_sea_of_clouds(image, width, height, horizon_y, theme, seed=0):
    """云岚城：绘制云海。"""
    rng = random.Random(seed)
    clouds = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(clouds)
    for _ in range(12):
        x = rng.randint(0, width)
        y = rng.randint(horizon_y - 20, height - 10)
        r = rng.randint(30, 70)
        cdraw.ellipse([x - r, y - r // 2, x + r, y + r // 2], fill=(*theme["ground_near"], 90))
    clouds = clouds.filter(ImageFilter.GaussianBlur(radius=8))
    image.alpha_composite(clouds)


def _draw_floating_island(draw, cx, cy, w, h, theme):
    """云岚城：绘制悬浮小岛。"""
    # 岛底
    draw.polygon([
        (cx - w // 2, cy), (cx + w // 2, cy),
        (cx + w // 3, cy + h // 2), (cx - w // 3, cy + h // 2)
    ], fill=_darken(theme["ground_near"], 0.1))
    # 岛面
    draw.ellipse([cx - w // 2, cy - h // 2, cx + w // 2, cy], fill=theme["ground_far"])
    # 小建筑/石块
    draw.rectangle([cx - 4, cy - h // 2 - 8, cx + 4, cy - h // 2], fill=(145, 135, 150))


def _draw_wind_flags(draw, cx, cy, h):
    """扶风城：绘制飘动的风旗。"""
    pole_c = (120, 110, 95)
    flag_c = (190, 210, 195)
    draw.line([(cx, cy), (cx, cy - h)], fill=pole_c, width=2)
    # 旗面波浪形
    draw.polygon([
        (cx, cy - h + 2), (cx + 22, cy - h + 6),
        (cx + 20, cy - h + 16), (cx, cy - h + 12)
    ], fill=flag_c, outline=_darken(flag_c, 0.2))


def _draw_red_leaves(draw, cx, cy, size, rng=None):
    """落霞城：绘制红叶树。"""
    if rng is None:
        rng = random.Random(cx * 100 + cy)
    # 树干
    draw.line([(cx, cy), (cx, cy - size)], fill=(95, 75, 65), width=3)
    # 红叶团
    for _ in range(8):
        lx = cx + rng.randint(-size // 2, size // 2)
        ly = cy - size + rng.randint(0, size // 2)
        r = rng.randint(4, 9)
        leaf_c = rng.choice([(195, 95, 75), (210, 120, 80), (180, 85, 65)])
        draw.ellipse([lx - r, ly - r, lx + r, ly + r], fill=leaf_c)


def _draw_heavy_mist(image, width, height, theme, seed=0):
    """云梦城：绘制浓雾仙境效果。"""
    rng = random.Random(seed)
    mist = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(mist)
    for _ in range(15):
        x = rng.randint(0, width)
        y = rng.randint(height // 3, height)
        r = rng.randint(40, 90)
        mdraw.ellipse([x - r, y - r // 3, x + r, y + r // 3], fill=(*theme["ground_near"], 70))
    mist = mist.filter(ImageFilter.GaussianBlur(radius=12))
    image.alpha_composite(mist)


def generate_city_overview(loc_id, loc_name, hotspots, width=WIDTH, height=HEIGHT):
    """生成一张统一的 2.5D 古风城镇全景图。"""
    theme = CITY_THEMES.get(loc_id, CITY_THEMES["luoxia_city"])

    image = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)

    # 天空渐变
    _draw_gradient(draw, width, height, theme["sky_top"], theme["sky_bottom"], direction="v")

    # 地平线
    horizon_y = int(height * 0.30)

    # 远山（带雾气）
    _draw_mountain_range(draw, width, horizon_y, theme["mountain"], peaks=5, seed=hash(loc_id) % 10000)

    # 远景城墙（淡色，增强空间层次）
    wall_y = horizon_y + 8
    wall_color = _lerp_color(theme["mountain"], theme["ground_far"], 0.5)
    draw.rectangle([0, wall_y, width, wall_y + 16], fill=(*wall_color, 160))
    for x in range(0, width, 20):
        draw.rectangle([x, wall_y - 6, x + 10, wall_y], fill=(*wall_color, 160))

    # 地面
    _draw_ground_plane(draw, width, height, horizon_y, theme, seed=hash(loc_id) % 10000)

    # 城市特色背景元素（在建筑之前绘制）
    if loc_id == "xuanshui_city":
        _draw_water_river(draw, image, width, height, horizon_y, theme, seed=hash(loc_id) % 10000)
        # 在河流上绘制小桥
        _draw_small_bridge(draw, width // 3, horizon_y + (height - horizon_y) * 0.45, 50, theme)
    elif loc_id == "chiyan_city":
        _draw_volcano(draw, image, width, height, horizon_y, theme, seed=hash(loc_id) % 10000)
        _draw_sulfur_smoke(image, width, horizon_y, seed=hash(loc_id) % 10000)
    elif loc_id == "yunlan_city":
        _draw_sea_of_clouds(image, width, height, horizon_y, theme, seed=hash(loc_id) % 10000)
        # 远景悬浮小岛
        _draw_floating_island(draw, width - 100, horizon_y - 20, 60, 40, theme)
        _draw_floating_island(draw, 80, horizon_y + 10, 45, 30, theme)
    elif loc_id == "yunmeng_city":
        _draw_heavy_mist(image, width, height, theme, seed=hash(loc_id) % 10000)

    # 计算建筑中心，用于绘制道路
    centers = []
    for hotspot in hotspots:
        x1, y1, x2, y2 = hotspot["coords"]
        cx = int((x1 + x2) / 2 * width)
        cy = int((y1 + y2) / 2 * height)
        centers.append((cx, cy))

    # 主街道：连接最左到最右
    if len(centers) >= 2:
        centers_sorted = sorted(centers, key=lambda p: p[0])
        road_w = max(10, width // 60)
        _draw_road(draw, centers_sorted, road_w, theme)

    # 背景树木（较小的远景树）
    rng = random.Random(hash(loc_id) % 10000)
    tree_color = _lerp_color(theme["ground_near"], (50, 90, 55), 0.35)
    for _ in range(10):
        tx = rng.randint(20, width - 20)
        ty = rng.randint(horizon_y + 30, height - 20)
        _draw_tree(draw, tx, ty, rng.randint(18, 32), tree_color, (0, 0, 0, 35), rng=rng)

    # 绘制建筑
    for hotspot in hotspots:
        bid = hotspot["id"]
        x1, y1, x2, y2 = hotspot["coords"]
        cx = int((x1 + x2) / 2 * width)
        cy = int((y1 + y2) / 2 * height)
        bw = int((x2 - x1) * width * 0.80)
        bh = int((y2 - y1) * height * 0.80)
        palette = BUILDING_PALETTES.get(bid, BUILDING_PALETTES["inn"])
        _draw_building_by_id(draw, cx, cy, bw, bh, bid, palette)

    # 前景点缀树木/花坛（根据城市特色选择树木类型）
    if loc_id == "wangchuan_town":
        for _ in range(8):
            tx = rng.randint(20, width - 20)
            ty = rng.randint(horizon_y + height // 3, height - 10)
            _draw_dead_tree(draw, tx, ty, rng.randint(28, 45), rng=rng)
    elif loc_id == "luoxia_city":
        for _ in range(6):
            tx = rng.randint(20, width - 20)
            ty = rng.randint(horizon_y + height // 3, height - 10)
            _draw_red_leaves(draw, tx, ty, rng.randint(25, 40), rng=rng)
    else:
        for _ in range(6):
            tx = rng.randint(20, width - 20)
            ty = rng.randint(horizon_y + height // 3, height - 10)
            _draw_tree(draw, tx, ty, rng.randint(22, 38), tree_color, (0, 0, 0, 45), rng=rng)

    # 城市特色前景元素
    if loc_id == "wanyao_city":
        # 兽栏
        _draw_beast_fence(draw, width // 6, height - 50, 80, 35, theme)
        _draw_beast_fence(draw, width * 5 // 6, height - 60, 70, 30, theme)
        # 图腾柱
        _draw_totem_pole(draw, width // 4, height - 40, 45)
        _draw_totem_pole(draw, width * 3 // 4, height - 35, 40)
    elif loc_id == "fufeng_city":
        # 风中飘动的旗帜
        _draw_wind_flags(draw, width - 50, height - 80, 35)
        _draw_wind_flags(draw, 45, height - 70, 30)
    elif loc_id == "wangchuan_town":
        # 漂浮鬼火
        _draw_ghost_fire(image, width, height, horizon_y, seed=hash(loc_id) % 10000)

    # 云雾氛围
    for i in range(5):
        _draw_soft_cloud(image, draw, rng.randint(50, width - 50), rng.randint(horizon_y - 30, horizon_y + 30),
                         rng.randint(40, 70), alpha=40)

    _draw_atmosphere(image, width, height, theme, loc_id=loc_id)

    # 城池名称
    title_font = get_font(size=max(22, width // 30))
    bbox = draw.textbbox((0, 0), loc_name, font=title_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    bar_padding = 10
    draw.rounded_rectangle(
        [16 - bar_padding, 16 - bar_padding,
         16 + text_w + bar_padding, 16 + text_h + bar_padding],
        radius=6,
        fill=(0, 0, 0, 130),
    )
    draw.text((16, 16), loc_name, fill=(255, 255, 255), font=title_font)

    return image.convert("RGB")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    locations = load_json(CONFIG_PATH)
    city_maps = load_json(CITY_MAPS_PATH) if os.path.exists(CITY_MAPS_PATH) else []
    hotspot_by_city = {cfg["city_id"]: cfg.get("hotspots", []) for cfg in city_maps}

    generated = 0
    for loc in locations:
        bg = loc.get("background_image")
        if not bg:
            continue
        loc_id = loc["id"]
        hotspots = hotspot_by_city.get(loc_id, [])

        image_1x = generate_city_overview(loc_id, loc["name"], hotspots, WIDTH, HEIGHT)
        path_1x = os.path.join(OUTPUT_DIR, bg)
        image_1x.save(path_1x, "PNG")

        image_2x = generate_city_overview(loc_id, loc["name"], hotspots, WIDTH * 2, HEIGHT * 2)
        name_2x = os.path.splitext(bg)[0] + "@2x.png"
        path_2x = os.path.join(OUTPUT_DIR, name_2x)
        image_2x.save(path_2x, "PNG")

        generated += 1
        print(f"已生成：{path_1x}、{path_2x}")

    print(f"共生成 {generated} 座城市全景图（含 1x 与 2x），建筑已统一绘制在背景中。")


if __name__ == "__main__":
    main()
