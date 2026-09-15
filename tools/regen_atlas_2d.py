"""
按"中国地图集（湖南省自然地理图）"风格重新生成 2D 游戏地图。

要素清单：
- 白色底（1024x1024）
- 浅绿色植被晕渲斑块（随机斑点 + 高斯模糊，淡色调）
- 细密灰色等高线（多层不规则椭圆/曲线）
- 淡蓝色水域（洞庭湖式大湖 + 河流曲线）
- 灰色点状省/区域界线
- 灰色山脉文字散布（"山"字散落）
- 双层边框（内浅灰、外深绿）
- 顶部黑色粗体标题
- 左侧/右下角小字水印
- 28 个游戏地点：彩色圆点 + 黑字/白阴影 + 类型色块
- 左下角图例框：白底 + 黑细线 + 5 类图例项 + 比例尺
- 底部 SCALE 比例尺（0-320 KM）

输入：config/locations.json
输出：assets/maps/world_2d.png（游戏加载）+ assets/maps/world_2d_base.png（无标注底图，留档）

用法：python tools/regen_atlas_2d.py
可重复运行，改 locations.json 后一键重画。
"""
import json
import math
import os
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ============== 常量 ==============
W, H = 1024, 1024
random.seed(20260814)  # 可复现

# 颜色（按湖南省自然地理图采样调色，更接近原图）
BG_WHITE = (252, 250, 244)              # 暖白底（参考图略偏米色）
GREEN_LIGHT = (180, 220, 175)          # 浅绿晕渲
GREEN_MID = (150, 200, 145)            # 较深植被
WATER_BLUE = (190, 215, 232)           # 淡蓝水域
WATER_BLUE_DARK = (140, 180, 210)
CONTOUR_GRAY = (180, 175, 165)         # 等高线灰
PROVINCE_GRAY = (130, 130, 130)        # 区域界灰
TITLE_BLACK = (15, 15, 15)
WATERMARK_GRAY = (170, 170, 170)
TEXT_BLACK = (25, 25, 25)

# 游戏化图例颜色
TYPE_COLORS = {
    "city":  (180, 80, 160, 255),       # 紫红 = 城镇
    "sect":  (60, 110, 200, 255),       # 蓝 = 宗门
    "wild":  (200, 150, 50, 255),       # 金 = 野外
}

# 字体大小
TITLE_FONT_SIZE = 38
LEGEND_TITLE_SIZE = 18
LEGEND_ITEM_SIZE = 15
LABEL_FONT_SIZE = 17
LABEL_SHADOW_SIZE = 17
SCALE_LABEL_SIZE = 12
WATERMARK_SIZE = 12
SHAN_FONT_SIZE = 11

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOC_PATH = os.path.join(ROOT, "config", "locations.json")
OUT_DIR = os.path.join(ROOT, "assets", "maps")


# ============== 工具函数 ==============
def _font(size, bold=False):
    """获取系统中文字体（粗体）。"""
    cands = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for p in cands:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _font_thin(size):
    cands = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simsun.ttc"]
    for p in cands:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _rects_overlap(a, b, pad=0):
    return not (a[2] + pad < b[0] or b[2] + pad < a[0]
                or a[3] + pad < b[1] or b[3] + pad < a[1])


def _text_shadow(d, xy, text, font, fill, shadow, offset=(1, 1)):
    x, y = xy
    d.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow)
    d.text((x, y), text, font=font, fill=fill)


def load_locations():
    with open(LOC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ============== 底图绘制 ==============
def draw_white_base():
    return Image.new("RGB", (W, H), BG_WHITE)


def draw_green_vegetation(base_img):
    """叠加浅绿植被晕渲斑块（细密颗粒 + 轻度模糊，模拟参考图的植被晕点）。"""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # 140 个小块（更小更密）
    for _ in range(140):
        cx = random.randint(80, W - 80)
        cy = random.randint(80, H - 80)
        rx = random.randint(15, 40)
        ry = random.randint(10, 22)
        # 椭圆底色（极淡）
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                  fill=GREEN_LIGHT + (110,))
    # 内部密点（单像素、密集分布）
    for _ in range(4000):
        cx = random.randint(0, W)
        cy = random.randint(0, H)
        # 让点聚集在已有椭圆附近：两次重试落在椭圆内
        sz = 1
        col = GREEN_MID if random.random() < 0.4 else GREEN_LIGHT
        d.rectangle([cx, cy, cx, cy], fill=col + (140,))
    # 轻度模糊（保留颗粒感）
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=1.6))
    if base_img.mode != "RGBA":
        base_img = base_img.convert("RGBA")
    base_img.alpha_composite(overlay)
    return base_img.convert("RGBA")


def draw_contour_lines(base_img):
    """细密灰色等高线（更明显、稍深一点，置于晕渲之上保持可见）。"""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # 7 组，每组 5-7 条椭圆（不同位置/大小）
    for group in range(7):
        cx = random.randint(220, W - 220)
        cy = random.randint(220, H - 220)
        rx_base = random.randint(70, 180)
        ry_base = random.randint(45, 110)
        n_lines = random.randint(5, 7)
        for i in range(n_lines):
            rx = rx_base + i * 12
            ry = ry_base + i * 8
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                      outline=(130, 130, 120, 200), width=1)
    # 散布短曲线模拟山脊碎线
    for _ in range(60):
        x1 = random.randint(60, W - 60)
        y1 = random.randint(60, H - 60)
        segs = random.randint(3, 6)
        px, py = x1, y1
        for _ in range(segs):
            nx = px + random.randint(-25, 25)
            ny = py + random.randint(-25, 25)
            d.line([px, py, nx, ny], fill=(140, 130, 110, 180), width=1)
            px, py = nx, ny
    if base_img.mode != "RGBA":
        base_img = base_img.convert("RGBA")
    base_img.alpha_composite(overlay)
    return base_img.convert("RGBA")


def draw_water(base_img):
    """淡蓝水域：湖泊（洞庭湖式大块） + 河流（4 条曲线）。"""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # 湖泊（3 个不规则大小）
    lakes = [(620, 320, 160, 90), (780, 380, 80, 50), (350, 480, 70, 40)]
    for cx, cy, rx, ry in lakes:
        # 双层叠加（深底 + 浅面）
        d.ellipse([cx - rx - 6, cy - ry - 4, cx + rx + 6, cy + ry + 4],
                  fill=WATER_BLUE_DARK + (255,))
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                  fill=WATER_BLUE + (255,))
        # 内部水波点
        for _ in range(40):
            px = cx + random.randint(-rx + 10, rx - 10)
            py = cy + random.randint(-ry + 5, ry - 5)
            d.line([px - 3, py, px + 3, py], fill=(255, 255, 255, 130), width=1)
    # 河流（平滑贝塞尔曲线）
    for _ in range(4):
        sx = random.choice([random.randint(50, 200), random.randint(W - 200, W - 50)])
        sy = random.choice([random.randint(80, H - 80)])
        ex = W - sx + random.randint(-60, 60)
        ey = H - sy + random.randint(-60, 60)
        cx1, cy1 = (sx + ex) / 2 + random.randint(-80, 80), sy + random.randint(-30, 30)
        cx2, cy2 = (sx + ex) / 2 + random.randint(-80, 80), ey + random.randint(-30, 30)
        # 取贝塞尔离散点
        bezier_pts = []
        for t_int in range(0, 41):
            t = t_int / 40
            x = (1-t)**3 * sx + 3*(1-t)**2*t*cx1 + 3*(1-t)*t**2*cx2 + t**3*ex
            y = (1-t)**3 * sy + 3*(1-t)**2*t*cy1 + 3*(1-t)*t**2*cy2 + t**3*ey
            bezier_pts.append((x, y))
        d.line(bezier_pts, fill=WATER_BLUE_DARK + (220,), width=3, joint="curve")
        d.line(bezier_pts, fill=WATER_BLUE + (255,), width=2, joint="curve")
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=0.6))
    if base_img.mode != "RGBA":
        base_img = base_img.convert("RGBA")
    base_img.alpha_composite(overlay)
    return base_img


def draw_province_boundary(base_img):
    """灰色点线省/区域界线（地图形状边界 + 内部分割）。"""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # 模拟地图外缘（不规则闭合曲线）
    margin = 70
    pts_outer = []
    n = 60
    for i in range(n):
        ang = i / n * 2 * math.pi
        r_factor = 1 + 0.04 * math.sin(i * 0.6) + 0.02 * math.cos(i * 1.3)
        x = int(W / 2 + math.cos(ang) * (W / 2 - margin) * r_factor)
        y = int(H / 2 + math.sin(ang) * (H / 2 - margin) * r_factor)
        pts_outer.append((x, y))
    pts_outer.append(pts_outer[0])
    # 主外缘（细黑实线，参考图）
    d.line(pts_outer, fill=(40, 40, 40, 220), width=2)
    d.line(pts_outer, fill=PROVINCE_GRAY + (140,), width=1)
    # 内部 3 条点状分割线（虚线模拟）
    for _ in range(3):
        sx = random.randint(120, W - 240)
        sy = random.randint(80, 200)
        ex = random.randint(sx + 100, W - 120)
        ey = random.randint(sy + 150, H - 120)
        # 虚线
        d.line([sx, sy, ex, ey], fill=PROVINCE_GRAY + (200,), width=1)
        # 加点
        dx_v = (ex - sx) / 30
        dy_v = (ey - sy) / 30
        for i in range(0, 30, 3):
            d.ellipse([sx + dx_v * i - 1, sy + dy_v * i - 1,
                       sx + dx_v * i + 1, sy + dy_v * i + 1],
                      fill=PROVINCE_GRAY + (220,))
    if base_img.mode != "RGBA":
        base_img = base_img.convert("RGBA")
    base_img.alpha_composite(overlay)
    return base_img


def draw_shan_text(base_img):
    """在地图内散布灰色「山」字（参考图特征）。"""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    font = _font_thin(SHAN_FONT_SIZE)
    # 18 个散布点（避开中央）
    spots = [
        (180, 170), (320, 130), (260, 280), (420, 200), (520, 280),
        (680, 170), (780, 250), (180, 460), (350, 580), (520, 620),
        (700, 540), (820, 440), (260, 720), (430, 780), (620, 760),
        (760, 720), (180, 850), (820, 840),
    ]
    for x, y in spots:
        d.text((x, y), "山", font=font, fill=PROVINCE_GRAY + (160,))
    if base_img.mode != "RGBA":
        base_img = base_img.convert("RGBA")
    base_img.alpha_composite(overlay)
    return base_img


def draw_border_and_title(base_img):
    """绘制边框（内浅灰、外深绿双层）+ 顶部标题。"""
    draw = ImageDraw.Draw(base_img)
    font = _font(TITLE_FONT_SIZE, bold=True)
    # 双层边框
    # 内细深绿
    draw.rectangle([4, 4, W - 5, H - 5], outline=(46, 110, 60), width=3)
    # 外粗深绿
    draw.rectangle([0, 0, W - 1, H - 1], outline=(30, 80, 45), width=6)
    # 标题
    title = "问道长生 · 修仙世界地图"
    tw = draw.textlength(title, font=font)
    draw.text(((W - tw) / 2, 14), title, font=font, fill=TITLE_BLACK)
    return base_img


def draw_scale_bar(base_img):
    """底部比例尺：黑色实线 + 等距分隔 + 标签 0/80/160/320 KM。"""
    draw = ImageDraw.Draw(base_img)
    font = _font_thin(SCALE_LABEL_SIZE)
    bar_x, bar_y = 80, H - 50
    bar_w = 240
    # 主标尺
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 6], fill=(40, 40, 40))
    # 4 段
    for i in range(5):
        x = bar_x + i * (bar_w // 4)
        draw.line([x, bar_y, x, bar_y + 9], fill=(40, 40, 40), width=2)
    # 标签
    for i, txt in enumerate(["0", "80", "160", "240", "320"]):
        x = bar_x + i * (bar_w // 4)
        tw = draw.textlength(txt, font=font)
        draw.text((x - tw / 2, bar_y + 12), txt, font=font, fill=(40, 40, 40))
    draw.text((bar_x + bar_w + 12, bar_y - 1), "KM",
              font=font, fill=(40, 40, 40))
    return base_img


def draw_watermark(base_img):
    """右下角小字游戏版水印。"""
    draw = ImageDraw.Draw(base_img)
    font = _font_thin(WATERMARK_SIZE)
    txt = "Cultivation World Atlas · 问道长生制图"
    tw = draw.textlength(txt, font=font)
    draw.text((W - tw - 20, H - 22), txt, font=font, fill=WATERMARK_GRAY)
    return base_img


def draw_legend(base_img):
    """左下角图例框（白底 + 黑细线 + 5 类游戏化条目 + 比例尺说明）。"""
    draw = ImageDraw.Draw(base_img)
    lx, ly = 50, H - 232  # 图例框左上角
    lw, lh = 232, 188
    # 框背景（盖住底图）
    draw.rectangle([lx, ly, lx + lw, ly + lh], fill=(252, 250, 240),
                   outline=(40, 40, 40), width=2)
    # 框内边距
    f_title = _font(LEGEND_TITLE_SIZE, bold=True)
    f_item = _font_thin(LEGEND_ITEM_SIZE)
    # 标题
    title = "图  例"
    tw = draw.textlength(title, font=f_title)
    draw.text((lx + (lw - tw) / 2, ly + 8), title, font=f_title, fill=(20, 20, 20))
    # 分隔线
    draw.line([lx + 20, ly + 36, lx + lw - 20, ly + 36],
              fill=(180, 180, 180), width=1)
    # 5 类条目
    items = [
        ("city", "凡俗城镇"),
        ("sect", "仙门宗派"),
        ("wild", "野外秘境"),
        ("river", "灵脉水域"),
        ("road", "驿道  (虚线)"),
    ]
    item_y = ly + 48
    for tag, label in items:
        # 标签图标
        cx, cy = lx + 30, item_y + 9
        if tag in ("city", "sect", "wild"):
            col = TYPE_COLORS[tag]
            # 双圈/单圈区分 sect 与 city
            if tag == "sect":
                draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8],
                             outline=(60, 110, 200, 255), width=2)
            draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5],
                         fill=col, outline=(255, 255, 255), width=1)
        elif tag == "river":
            draw.line([cx - 8, cy, cx + 8, cy], fill=WATER_BLUE_DARK, width=3)
            draw.line([cx - 8, cy, cx + 8, cy], fill=WATER_BLUE, width=2)
        elif tag == "road":
            # 虚线
            dash_w = 3
            gap = 2
            x = cx - 8
            while x < cx + 8:
                draw.line([x, cy, x + dash_w, cy], fill=(150, 110, 60), width=2)
                x += dash_w + gap
        # 标签文字
        draw.text((cx + 16, cy - 8), label, font=f_item, fill=(40, 40, 40))
        item_y += 22
    # 比例尺说明
    scale_txt = "SCALE  1 : 1 000 000"
    tw = draw.textlength(scale_txt, font=f_item)
    draw.text((lx + (lw - tw) / 2, ly + lh - 24),
              scale_txt, font=f_item, fill=(40, 40, 40))
    return base_img


# ============== 地点烧录 ==============
def bake_locations(base_img):
    """将 28 个游戏地点烧录到地图上。

    风格参考地图集：彩色实心圆 + 黑色等线字体地名（白底黑字文字阴影）。
    智能避让：8 方向候选，按邻居密度贪心。
    """
    locs = load_locations()
    xs = [l["x"] for l in locs]
    ys = [l["y"] for l in locs]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    font = _font(LABEL_FONT_SIZE, bold=True)
    font_shadow = _font(LABEL_SHADOW_SIZE, bold=True)

    MARGIN = 130  # 地图主体边缘
    prepared = []
    for loc in locs:
        nx = (loc["x"] - xmin) / (xmax - xmin) if xmax > xmin else 0.5
        ny = (loc["y"] - ymin) / (ymax - ymin) if ymax > ymin else 0.5
        ix = MARGIN + nx * (W - 2 * MARGIN)
        # 注意地图坐标系 y 轴向下为正，但参考图纬度向下增加
        iy = MARGIN + ny * (H - 2 * MARGIN)
        label = loc["name"] + ("（锁）" if loc.get("locked") else "")
        tw = d.textlength(label, font=font)
        ph = LABEL_FONT_SIZE + 6
        pw = int(tw + 14)
        prepared.append({
            "id": loc["id"], "label": label, "ix": ix, "iy": iy,
            "pw": pw, "ph": ph, "tw": tw,
            "col": TYPE_COLORS.get(loc.get("type", "wild"), TYPE_COLORS["wild"]),
        })

    # 按邻居数从多到少（密集区先选位）
    def neighbor_count(p):
        cnt = 0
        for q in prepared:
            if q is p:
                continue
            dx, dy = q["ix"] - p["ix"], q["iy"] - p["iy"]
            if dx * dx + dy * dy < 180 * 180:
                cnt += 1
        return cnt

    for p in prepared:
        p["nd"] = neighbor_count(p)
    prepared.sort(key=lambda p: -p["nd"])

    # 8 方向候选
    candidates_directions = [
        (0, 1, "bottom"),     # 下
        (0, -1, "top"),       # 上
        (1, 0, "right"),      # 右
        (-1, 0, "left"),      # 左
        (1, 1, "br"),         # 右下
        (-1, 1, "bl"),        # 左下
        (1, -1, "tr"),        # 右上
        (-1, -1, "tl"),       # 左上
    ]
    OFFSET = 14

    occupied = []
    # 预留图例框区域为占用区
    legend_box = (50, H - 232, 50 + 232, H - 232 + 188)
    occupied.append(legend_box)

    for p in prepared:
        ix, iy = p["ix"], p["iy"]
        pw, ph = p["pw"], p["ph"]
        chosen = None
        for vx, vy, _ in candidates_directions:
            ox = vx * OFFSET
            oy = vy * OFFSET
            if vx == 0 and vy == 0:
                continue
            if ox > 0:
                px0 = ix + ox
            elif ox < 0:
                px0 = ix + ox - pw
            else:
                px0 = ix - pw / 2
            if oy > 0:
                py0 = iy + oy
            elif oy < 0:
                py0 = iy + oy - ph
            else:
                py0 = iy - ph / 2
            rect = (px0, py0, px0 + pw, py0 + ph)
            if rect[0] < 130 or rect[1] < 80 or rect[2] > W - 30 or rect[3] > H - 90:
                continue
            if any(_rects_overlap(rect, r, pad=4) for r in occupied):
                continue
            chosen = (px0, py0, rect)
            break
        if chosen is None:
            px0 = ix - pw / 2
            py0 = iy + OFFSET
            chosen = (px0, py0, (px0, py0, px0 + pw, py0 + ph))
        p["px0"], p["py0"], p["rect"] = chosen
        occupied.append(chosen[2])

    # 绘制：先光晕、再圆点、再白底标签、再黑字
    for p in prepared:
        ix, iy = p["ix"], p["iy"]
        col = p["col"]
        d.ellipse([ix - 14, iy - 14, ix + 14, iy + 14],
                  fill=(col[0], col[1], col[2], 80))
        d.ellipse([ix - 6, iy - 6, ix + 6, iy + 6],
                  fill=(col[0], col[1], col[2], 255),
                  outline=(255, 255, 255), width=2)
        # 中心白点
        d.ellipse([ix - 2, iy - 2, ix + 2, iy + 2], fill=(255, 255, 255, 255))

    for p in prepared:
        px0, py0, (rx0, ry0, rx1, ry1) = p["px0"], p["py0"], p["rect"]
        d.rectangle([rx0, ry0, rx1, ry1], fill=(255, 255, 255, 245),
                    outline=(180, 180, 180), width=1)

    for p in prepared:
        px0, py0, (rx0, ry0, rx1, ry1) = p["px0"], p["py0"], p["rect"]
        # 阴影
        d.text((rx0 + 7 + 1, ry0 + (ry1 - ry0 - LABEL_FONT_SIZE) / 2 + 1),
               p["label"], font=font_shadow, fill=(180, 180, 180, 255))
        # 文字
        d.text((rx0 + 7, ry0 + (ry1 - ry0 - LABEL_FONT_SIZE) / 2),
               p["label"], font=font, fill=(20, 20, 20, 255))
        col = p["col"]
        d.rectangle([rx0, ry0, rx0 + 4, ry1], fill=(col[0], col[1], col[2], 255))

    return Image.alpha_composite(base_img.convert("RGBA"), overlay).convert("RGB")


# ============== 主流程 ==============
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    img = draw_white_base()
    img = draw_green_vegetation(img)
    img = draw_contour_lines(img)
    img = draw_water(img)
    img = draw_province_boundary(img)
    img = draw_shan_text(img)
    img = draw_border_and_title(img)
    img = draw_scale_bar(img)
    img = draw_watermark(img)
    img = draw_legend(img)

    # 先存一份不带地点标注的底图
    base_out = os.path.join(OUT_DIR, "world_2d_base.png")
    img.convert("RGB").save(base_out, "PNG", optimize=True)
    print(f"[base] {base_out}")

    # 烧录地点
    final = bake_locations(img)
    out = os.path.join(OUT_DIR, "world_2d.png")
    final.save(out, "PNG", optimize=True)
    print(f"[ok]   {out}")


if __name__ == "__main__":
    main()
