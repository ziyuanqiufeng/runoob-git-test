"""
按「东亚卫星图」风格生成 2D 游戏地图。

主图 + 4 个聚集区局部放大图，全部由 agnes-image-2.1-flash AI 生成，
再用 PIL 合成：主图作底 + 4 个局部图放四角 + 引线 + 28 个游戏地点标注。

输入：config/locations.json
输出：assets/maps/world_2d.png（游戏加载）+ 5 张 AI 生成图留档

用法：D:/ziyuanqiufeng/.venv/Scripts/python.exe tools/regen_satellite_2d.py
"""
import datetime
import json
import math
import os
import sys
import urllib.error
import urllib.request
from PIL import Image, ImageDraw, ImageFont

# ============== Agnes AI 接口（同 skill/generate_image.py）==============
API_URL = "https://apihub.agnes-ai.com/v1/images/generations"
DEFAULT_MODEL = "agnes-image-2.1-flash"
DEFAULT_API_KEY = "sk-RvcmSFxJ8Qt6Hg1uSRvYk9iVzvcjcw7j7FEVsdO3Fx4GDOEh"


def call_api(prompt, size, n=1):
    payload = {"model": DEFAULT_MODEL, "prompt": prompt, "n": n, "size": size}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=data,
        headers={"Authorization": "Bearer " + DEFAULT_API_KEY,
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API HTTP {e.code}: {e.read().decode('utf-8', 'replace')}")


def download_image(url, out_dir, prefix):
    os.makedirs(out_dir, exist_ok=True)
    ext = ".png"
    for c in (".png", ".jpg", ".jpeg", ".webp"):
        if url.lower().split("?")[0].endswith(c):
            ext = c
            break
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"{prefix}_{ts}{ext}")
    with urllib.request.urlopen(url, timeout=120) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


def gen_one(prompt, size, prefix, out_dir):
    print(f"[*] 生成 {prefix} ({size})...")
    resp = call_api(prompt, size, 1)
    url = resp["data"][0]["url"]
    path = download_image(url, out_dir, prefix)
    print(f"[ok] {path}")
    return path


# ============== 路径与常量 ==============
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOC_PATH = os.path.join(ROOT, "config", "locations.json")
OUT_DIR = os.path.join(ROOT, "assets", "maps")
AI_DIR = os.path.join(OUT_DIR, "_ai_sources")

W, H = 1024, 1024

# 地点类型颜色（卫星图风格：白色文字 + 红色城市圆点（参考图）
TYPE_COLORS = {
    "city":  (220, 50, 50, 255),     # 红色 = 城镇（参考图风格）
    "sect":  (50, 90, 220, 255),     # 蓝色 = 宗门
    "wild":  (255, 200, 50, 255),    # 金色 = 野外
}
TYPE_RING_COLORS = {
    "city": (180, 0, 0, 255),
    "sect": (20, 50, 160, 255),
    "wild": (200, 140, 0, 255),
}

# 4 个聚集区定义（id 列表 + 主题 + 引线锚点）
CLUSTERS = [
    {
        "name": "玄水湖群",
        "ids": ["xuanshui_city", "xuanshui_palace", "zixiao_palace", "xuankong_ge"],
        "theme": "Crystal clear lake with floating islands, water city with bridges, surrounded by green mountain forest, satellite aerial view, photorealistic landscape photography",
        "anchor": "br",   # 局部图放在右下角
        "target_label": "玄水湖群",
    },
    {
        "name": "火山剑域",
        "ids": ["chiyan_city", "chiyan_gate", "huoyan_gu", "tianjian_sect", "jianzhong"],
        "theme": "Volcanic mountain valley with red rocks and lava rivers, surrounded by dark forest, dramatic cliffs, satellite aerial view, photorealistic landscape photography",
        "anchor": "tl",
        "target_label": "火山剑域",
    },
    {
        "name": "万妖山脉",
        "ids": ["wanyao_city", "wanyao_sect", "lingyao_fudi", "wanyao"],
        "theme": "Mysterious dense mountain forest with thick fog hiding deep valleys, dark green canopy, ancient trees, satellite aerial view, photorealistic landscape photography",
        "anchor": "tr",
        "target_label": "万妖山脉",
    },
    {
        "name": "扶风山脉",
        "ids": ["fufeng_city", "fufeng_wind_sect", "luoxia_city", "qingyun"],
        "theme": "Wind-swept mountain peaks with sharp cliffs, sparse high-altitude vegetation, low clouds, dramatic terrain, satellite aerial view, photorealistic landscape photography",
        "anchor": "bl",
        "target_label": "扶风山脉",
    },
]

# 锚点对应角落坐标（局部图位置）
ANCHOR_POS = {
    "tl": (60, 60, 240, 200),     # 左上角
    "tr": (W - 240, 60, W - 60, 200),  # 右上角
    "bl": (60, H - 200, 240, H - 60),  # 左下角
    "br": (W - 240, H - 200, W - 60, H - 60),  # 右下角
}


# ============== 工具函数 ==============
def _font(size, bold=False):
    cands = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for p in cands:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def load_locations():
    with open(LOC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _cluster_centroid(cluster, locs_by_id):
    xs, ys = [], []
    for lid in cluster["ids"]:
        if lid in locs_by_id:
            xs.append(locs_by_id[lid]["x"])
            ys.append(locs_by_id[lid]["y"])
    return sum(xs) / len(xs), sum(ys) / len(ys)


# ============== 合成主图 ==============
def compose_main(main_img_path, inset_paths, locs):
    """把主图作底，4 张局部放大图放四角，加引线 + 28 个地点标注。"""
    base = Image.open(main_img_path).convert("RGBA")
    # 主图缩放成 W x H（API 默认 1024x1024 应该一致）
    if base.size != (W, H):
        base = base.resize((W, H), Image.LANCZOS)

    locs_by_id = {l["id"]: l for l in locs}

    # 半透明黑色蒙版层（让文字更可读）
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # 1) 4 张局部图放四角 + 标题 + 引线
    for cluster, inset_path in zip(CLUSTERS, inset_paths):
        anchor = cluster["anchor"]
        x0, y0, x1, y1 = ANCHOR_POS[anchor]
        # 缩放 inset 到 180x140
        inset = Image.open(inset_path).convert("RGBA")
        iw, ih = inset.size
        iw2, ih2 = x1 - x0, y1 - y0
        # 等比 cover
        scale = max(iw2 / iw, ih2 / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        inset = inset.resize((nw, nh), Image.LANCZOS)
        # 中心 crop
        inset = inset.crop(((nw - iw2) // 2, (nh - ih2) // 2,
                            (nw + iw2) // 2, (nh + ih2) // 2))
        # 圆角蒙版（用 PIL alpha 通道）— 用矩形 + 半透明白边即可
        # 局部图边框
        d.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2],
                    outline=(255, 255, 255, 220), width=3)
        d.rectangle([x0 - 5, y0 - 5, x1 + 5, y1 + 5],
                    outline=(0, 0, 0, 200), width=2)
        # 合成 inset
        base.paste(inset, (x0, y0))
        # 标题：局部图上方
        title = cluster["target_label"]
        f_title = _font(14, bold=True)
        tw = d.textlength(title, font=f_title)
        d.rectangle([x0 + (x1 - x0 - tw) / 2 - 6, y0 - 22,
                     x0 + (x1 - x0 + tw) / 2 + 6, y0 - 4],
                    fill=(0, 0, 0, 200))
        d.text((x0 + (x1 - x0 - tw) / 2, y0 - 19),
               title, font=f_title, fill=(255, 255, 255, 255))

        # 引线：局部图框中心 -> 聚集区中心（地图坐标）
        cx_map, cy_map = _cluster_centroid(cluster, locs_by_id)
        cx_img, cy_img = _to_map_xy(cx_map, cy_map)
        # 框中心
        if anchor == "tl":
            fx, fy = x1, y1
        elif anchor == "tr":
            fx, fy = x0, y1
        elif anchor == "bl":
            fx, fy = x1, y0
        else:  # br
            fx, fy = x0, y0
        # 白色虚线引线
        d.line([fx, fy, cx_img, cy_img], fill=(255, 255, 255, 220), width=2)
        # 引线起止点白圈
        d.ellipse([fx - 4, fy - 4, fx + 4, fy + 4],
                  fill=(255, 255, 255, 255), outline=(0, 0, 0), width=1)
        d.ellipse([cx_img - 4, cy_img - 4, cx_img + 4, cy_img + 4],
                  fill=(255, 200, 50, 255), outline=(255, 255, 255), width=1)

    # 2) 28 个地点标注
    # 计算坐标范围 + 缩放
    xs = [l["x"] for l in locs]
    ys = [l["y"] for l in locs]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)

    f_label = _font(13, bold=True)
    f_label_shadow = _font(13, bold=True)
    for loc in locs:
        ix, iy = _to_map_xy(loc["x"], loc["y"], xmin, xmax, ymin, ymax)
        # 排除落入 4 个角落框的地点（避免遮挡）
        in_corner = False
        for (ax0, ay0, ax1, ay1) in ANCHOR_POS.values():
            if ax0 - 8 <= ix <= ax1 + 8 and ay0 - 8 <= iy <= ay1 + 8:
                in_corner = True
                break
        if in_corner:
            continue
        col = TYPE_COLORS.get(loc.get("type", "wild"), TYPE_COLORS["wild"])
        ring = TYPE_RING_COLORS.get(loc.get("type", "wild"), TYPE_RING_COLORS["wild"])
        # 卫星图风格：白底圆点（参考图）+ 黑色描边 + 类型色环
        d.ellipse([ix - 7, iy - 7, ix + 7, iy + 7],
                  fill=(255, 255, 255, 255), outline=ring, width=2)
        d.ellipse([ix - 3, iy - 3, ix + 3, iy + 3],
                  fill=col, outline=(255, 255, 255, 255), width=1)
        # 标签（黑字 + 白描边阴影）
        label = loc["name"] + ("（锁）" if loc.get("locked") else "")
        tx = ix + 10
        ty = iy - 8
        # 文字阴影（白边描边效果用 4 次描边）
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            d.text((tx + dx, ty + dy), label, font=f_label_shadow, fill=(255, 255, 255, 255))
        d.text((tx, ty), label, font=f_label, fill=(20, 20, 20, 255))

    # 3) 主标题（顶部白底黑字）
    title = "问道长生 · 修仙世界卫星图"
    f_main = _font(26, bold=True)
    tw = d.textlength(title, font=f_main)
    d.rectangle([(W - tw) / 2 - 16, 8, (W + tw) / 2 + 16, 46],
                fill=(255, 255, 255, 235), outline=(0, 0, 0, 180), width=2)
    d.text(((W - tw) / 2, 14), title, font=f_main, fill=(15, 15, 15, 255))

    # 4) 当前位置标记（青云山绿环）
    qy = next((l for l in locs if l["id"] == "qingyun"), None)
    if qy:
        ix, iy = _to_map_xy(qy["x"], qy["y"], xmin, xmax, ymin, ymax)
        # 绿色脉冲环（双圈）
        d.ellipse([ix - 18, iy - 18, ix + 18, iy + 18],
                  outline=(50, 220, 80, 220), width=3)
        d.ellipse([ix - 26, iy - 26, ix + 26, iy + 26],
                  outline=(50, 220, 80, 150), width=2)
        d.text((ix + 18, iy + 14), "当前位置",
               font=_font(11, bold=True), fill=(50, 220, 80, 255))

    # 5) 底部图例条
    legend_y = H - 28
    legend_x = 30
    legend_items = [
        ("城镇", (220, 50, 50)),
        ("宗门", (50, 90, 220)),
        ("野外", (255, 200, 50)),
    ]
    for label, col in legend_items:
        d.ellipse([legend_x - 7, legend_y - 7, legend_x + 7, legend_y + 7],
                  fill=(255, 255, 255, 255), outline=col, width=2)
        d.ellipse([legend_x - 3, legend_y - 3, legend_x + 3, legend_y + 3],
                  fill=col, outline=(255, 255, 255), width=1)
        d.text((legend_x + 12, legend_y - 8), label,
               font=_font(12, bold=True), fill=(255, 255, 255, 255))
        # 阴影
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            d.text((legend_x + 12 + dx, legend_y - 8 + dy), label,
                   font=_font(12, bold=True), fill=(0, 0, 0, 200))
        d.text((legend_x + 12, legend_y - 8), label,
               font=_font(12, bold=True), fill=(255, 255, 255, 255))
        legend_x += 70

    # 合成
    final = Image.alpha_composite(base, overlay).convert("RGB")
    return final


def _to_map_xy(x, y, xmin=None, xmax=None, ymin=None, ymax=None):
    """地点坐标 -> 图片坐标。地图区域留出四角色块区（避免遮挡）。"""
    if xmin is None:
        locs = load_locations()
        xs = [l["x"] for l in locs]
        ys = [l["y"] for l in locs]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
    margin_x, margin_y = 100, 80  # 上下左右各留
    # 角落预留区
    margin_left = 260 if xmin < 100 else 100
    margin_right = 260 if xmax > 700 else 100
    margin_top = 250 if ymin < 0 else 60
    margin_bottom = 250 if ymax > 500 else 80
    nx = (x - xmin) / (xmax - xmin) if xmax > xmin else 0.5
    ny = (y - ymin) / (ymax - ymin) if ymax > ymin else 0.5
    # x 方向：左 margin_left，右 margin_right
    ix = margin_left + nx * (W - margin_left - margin_right)
    iy = margin_top + ny * (H - margin_top - margin_bottom)
    return int(ix), int(iy)


# ============== 主流程 ==============
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(AI_DIR, exist_ok=True)
    locs = load_locations()

    # 1. 5 张 AI 生成图
    main_prompt = (
        "Satellite aerial view of vast fantasy xianxia cultivation world, "
        "photorealistic landscape photography. Mixed terrain with dark green "
        "mountain forests, light green plains, beige highland deserts, deep "
        "blue lakes, white clouds, realistic topography and natural lighting"
    )
    main_path = gen_one(main_prompt, "1024x1024", "world_satellite", AI_DIR)

    inset_paths = []
    for cluster in CLUSTERS:
        path = gen_one(cluster["theme"], "1024x1024",
                       f"inset_{cluster['name']}", AI_DIR)
        inset_paths.append(path)

    # 2. PIL 合成
    final = compose_main(main_path, inset_paths, locs)
    out_path = os.path.join(OUT_DIR, "world_2d.png")
    final.save(out_path, "PNG", optimize=True)
    print(f"[ok] final map -> {out_path}")

    # 备份无标注主图（游戏内部用未标注版避免与合成层重复）
    base_no_label = os.path.join(OUT_DIR, "world_2d_base.png")
    Image.open(main_path).convert("RGB").save(base_no_label, "PNG", optimize=True)
    print(f"[ok] base (no labels) -> {base_no_label}")


if __name__ == "__main__":
    main()
