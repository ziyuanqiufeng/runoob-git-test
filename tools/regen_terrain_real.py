"""
按「真实地貌 + 真实坐标」重画 2D 地形图。

与旧版 regen_satellite_2d.py（四角缩略图、位置对不上）不同：
- 为 11 个真实地貌分区各生成一张对应实景卫星图（火山/湖岛/密林/雪峰/冰原/沼泽/云海/幽冥河…）
- 按分区成员地点的真实图片坐标计算包围盒，用柔和椭圆羽化（biome blob）贴到主图上
- 再叠加 28 个地点圆点 + 标签 + 当前位置 + 图例

输入：config/locations.json
输出：assets/maps/world_2d.png（游戏加载）+ world_2d_base.png（无标注底图）

用法：D:/ziyuanqiufeng/.venv/Scripts/python.exe tools/regen_terrain_real.py
"""
import datetime
import json
import os
import urllib.error
import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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

TYPE_COLORS = {
    "city": (220, 50, 50, 255),
    "sect": (50, 90, 220, 255),
    "wild": (255, 200, 50, 255),
}
TYPE_RING_COLORS = {
    "city": (180, 0, 0, 255),
    "sect": (20, 50, 160, 255),
    "wild": (200, 140, 0, 255),
}

# 11 个真实地貌分区（成员 id + 对应地貌实景 prompt，全部正向描述避免内容审核）
REGIONS = [
    {
        "name": "天空云海",
        "ids": ["yunlan_city", "tianji_pavilion", "yaowang_valley"],
        "theme": "Satellite aerial view of a floating sky city above a vast sea of "
                 "clouds, mountain peaks breaking through the clouds, ethereal "
                 "high-altitude fantasy landscape, photorealistic, pristine wilderness",
    },
    {
        "name": "扶风雪峰",
        "ids": ["fufeng_city", "fufeng_wind_sect", "luoxia_city", "qingyun"],
        "theme": "Satellite aerial view of wind-swept snow-capped mountain peaks with "
                 "sharp cliffs, sparse high-altitude vegetation, low drifting clouds, "
                 "dramatic terrain, photorealistic landscape photography",
    },
    {
        "name": "万妖密林",
        "ids": ["wanyao_city", "wanyao_sect", "lingyao_fudi", "wanyao"],
        "theme": "Satellite aerial view of a mysterious dense mountain forest with thick "
                 "fog hiding deep valleys, dark green canopy, ancient giant trees, "
                 "photorealistic wilderness",
    },
    {
        "name": "火山剑域",
        "ids": ["chiyan_city", "chiyan_gate", "huoyan_gu", "tianjian_sect", "jianzhong"],
        "theme": "Satellite aerial view of a volcanic mountain valley with glowing red "
                 "rocks and lava rivers, surrounded by dark forest, a sword-shaped cliff, "
                 "dramatic, photorealistic landscape photography",
    },
    {
        "name": "玄水湖群",
        "ids": ["xuanshui_city", "xuanshui_palace", "zixiao_palace", "xuankong_ge"],
        "theme": "Satellite aerial view of a crystal clear large lake with many floating "
                 "islands and a water city of bridges and pavilions, surrounded by green "
                 "mountains, photorealistic landscape photography",
    },
    {
        "name": "幽冥河域",
        "ids": ["wangchuan_town", "youming_sect", "wangchuan_river"],
        "theme": "Satellite aerial view of a dark misty river valley with dead twisted "
                 "trees, faint ghostly lights, eerie fog, desaturated cold tones, "
                 "photorealistic landscape photography",
    },
    {
        "name": "寒冰荒原",
        "ids": ["hanbing_yuan"],
        "theme": "Satellite aerial view of a frozen arctic tundra with glaciers, ice "
                 "plains and snowfields, barren and cold, photorealistic landscape "
                 "photography",
    },
    {
        "name": "雷泽沼泽",
        "ids": ["leize"],
        "theme": "Satellite aerial view of a thunder marsh swamp with dark water, "
                 "frequent lightning over storm clouds, wet barren peatland, "
                 "photorealistic landscape photography",
    },
    {
        "name": "黑风荒岭",
        "ids": ["heifeng"],
        "theme": "Satellite aerial view of a rugged barren mountain ridge with sparse "
                 "dry shrubs, rocky slopes, wild dangerous terrain, photorealistic "
                 "landscape photography",
    },
    {
        "name": "幽冥古林",
        "ids": ["jiuyuan_senlin"],
        "theme": "Satellite aerial view of an ancient dark forest with dense shadowy "
                 "canopy, misty, eerie, photorealistic wilderness",
    },
    {
        "name": "云梦雾城",
        "ids": ["yunmeng_city"],
        "theme": "Satellite aerial view of a misty lowland basin with a small walled "
                 "cultivation city among clouds and wetlands, photorealistic landscape "
                 "photography",
    },
]


# ============== 工具函数（与 regen_satellite_2d.py 一致的坐标变换）==============
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


def _global_ranges(locs):
    xs = [l["x"] for l in locs]
    ys = [l["y"] for l in locs]
    return min(xs), max(xs), min(ys), max(ys)


def _to_map_xy(x, y, xmin, xmax, ymin, ymax):
    margin_left = 260 if xmin < 100 else 100
    margin_right = 260 if xmax > 700 else 100
    margin_top = 250 if ymin < 0 else 60
    margin_bottom = 250 if ymax > 500 else 80
    nx = (x - xmin) / (xmax - xmin) if xmax > xmin else 0.5
    ny = (y - ymin) / (ymax - ymin) if ymax > ymin else 0.5
    ix = margin_left + nx * (W - margin_left - margin_right)
    iy = margin_top + ny * (H - margin_top - margin_bottom)
    return int(ix), int(iy)


def region_rect(ids, locs_by_id, xmin, xmax, ymin, ymax, expand=1.8):
    pts = []
    for lid in ids:
        if lid in locs_by_id:
            l = locs_by_id[lid]
            pts.append(_to_map_xy(l["x"], l["y"], xmin, xmax, ymin, ymax))
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    half_w = max((max(xs) - min(xs)) / 2 * expand, 130)
    half_h = max((max(ys) - min(ys)) / 2 * expand, 130)
    x0 = max(0, int(cx - half_w))
    y0 = max(0, int(cy - half_h))
    x1 = min(W, int(cx + half_w))
    y1 = min(H, int(cy + half_h))
    return x0, y0, x1, y1


def feather_blob(base, patch_path, rect):
    x0, y0, x1, y1 = rect
    rw, rh = x1 - x0, y1 - y0
    if rw <= 0 or rh <= 0:
        return base
    patch = Image.open(patch_path).convert("RGB").resize((rw, rh), Image.LANCZOS)
    patch = patch.convert("RGBA")
    mask = Image.new("L", (rw, rh), 0)
    md = ImageDraw.Draw(mask)
    inset = min(rw, rh) * 0.12
    md.ellipse([inset, inset, rw - inset, rh - inset], fill=255)
    blur = int(min(rw, rh) * 0.18)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    base.paste(patch, (x0, y0), mask)
    return base


# ============== 合成 ==============
def compose(base_img, region_patches, locs, xmin, xmax, ymin, ymax):
    base = base_img.convert("RGBA")
    locs_by_id = {l["id"]: l for l in locs}

    # 1) 真实地貌 biome blob 贴图（按真实坐标）
    for region, patch_path in zip(REGIONS, region_patches):
        rect = region_rect(region["ids"], locs_by_id, xmin, xmax, ymin, ymax)
        if rect:
            base = feather_blob(base, patch_path, rect)
            # 分区名小标注（弱化，白色描边）
            cx = (rect[0] + rect[2]) // 2
            cy = rect[1] + 14
            nm = region["name"]
            f = _font(13, bold=True)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ImageDraw.Draw(base).text((cx - 30 + dx, cy + dy), nm,
                                          font=f, fill=(0, 0, 0, 180))
            ImageDraw.Draw(base).text((cx - 30, cy), nm, font=f,
                                      fill=(255, 255, 255, 230))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # 2) 28 个地点标注
    f_label = _font(13, bold=True)
    for loc in locs:
        ix, iy = _to_map_xy(loc["x"], loc["y"], xmin, xmax, ymin, ymax)
        col = TYPE_COLORS.get(loc.get("type", "wild"), TYPE_COLORS["wild"])
        ring = TYPE_RING_COLORS.get(loc.get("type", "wild"), TYPE_RING_COLORS["wild"])
        d.ellipse([ix - 7, iy - 7, ix + 7, iy + 7],
                  fill=(255, 255, 255, 255), outline=ring, width=2)
        d.ellipse([ix - 3, iy - 3, ix + 3, iy + 3],
                  fill=col, outline=(255, 255, 255, 255), width=1)
        label = loc["name"] + ("（锁）" if loc.get("locked") else "")
        tx = ix + 10
        ty = iy - 8
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            d.text((tx + dx, ty + dy), label, font=f_label, fill=(255, 255, 255, 255))
        d.text((tx, ty), label, font=f_label, fill=(20, 20, 20, 255))

    # 3) 主标题
    title = "问道长生 · 修仙世界地形图"
    f_main = _font(26, bold=True)
    tw = d.textlength(title, font=f_main)
    d.rectangle([(W - tw) / 2 - 16, 8, (W + tw) / 2 + 16, 46],
                fill=(255, 255, 255, 235), outline=(0, 0, 0, 180), width=2)
    d.text(((W - tw) / 2, 14), title, font=f_main, fill=(15, 15, 15, 255))

    # 4) 当前位置（青云山绿环）
    qy = next((l for l in locs if l["id"] == "qingyun"), None)
    if qy:
        ix, iy = _to_map_xy(qy["x"], qy["y"], xmin, xmax, ymin, ymax)
        d.ellipse([ix - 18, iy - 18, ix + 18, iy + 18],
                  outline=(50, 220, 80, 220), width=3)
        d.ellipse([ix - 26, iy - 26, ix + 26, iy + 26],
                  outline=(50, 220, 80, 150), width=2)
        d.text((ix + 18, iy + 14), "当前位置",
               font=_font(11, bold=True), fill=(50, 220, 80, 255))

    # 5) 底部图例条
    legend_y = H - 28
    legend_x = 30
    for label, col in [("城镇", (220, 50, 50)), ("宗门", (50, 90, 220)), ("野外", (255, 200, 50))]:
        d.ellipse([legend_x - 7, legend_y - 7, legend_x + 7, legend_y + 7],
                  fill=(255, 255, 255, 255), outline=col, width=2)
        d.ellipse([legend_x - 3, legend_y - 3, legend_x + 3, legend_y + 3],
                  fill=col, outline=(255, 255, 255), width=1)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            d.text((legend_x + 12 + dx, legend_y - 8 + dy), label,
                   font=_font(12, bold=True), fill=(0, 0, 0, 200))
        d.text((legend_x + 12, legend_y - 8), label,
               font=_font(12, bold=True), fill=(255, 255, 255, 255))
        legend_x += 70

    return Image.alpha_composite(base, overlay).convert("RGB")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(AI_DIR, exist_ok=True)
    locs = load_locations()
    xmin, xmax, ymin, ymax = _global_ranges(locs)

    # 1) 底图（通用混合地形，负责填补 blob 之间的空隙）
    base_prompt = (
        "Satellite aerial view of a vast fantasy xianxia cultivation world, "
        "photorealistic landscape photography. Mixed terrain with dark green "
        "mountain forests, light green plains, beige highland, deep blue lakes, "
        "white clouds, realistic natural lighting, seamless"
    )
    base_path = gen_one(base_prompt, "1024x1024", "world_base", AI_DIR)

    # 2) 11 个真实地貌分区
    region_patches = []
    for region in REGIONS:
        region_patches.append(gen_one(region["theme"], "1024x1024",
                                      f"region_{region['name']}", AI_DIR))

    # 3) 合成
    base_img = Image.open(base_path).convert("RGB")
    if base_img.size != (W, H):
        base_img = base_img.resize((W, H), Image.LANCZOS)
    final = compose(base_img, region_patches, locs, xmin, xmax, ymin, ymax)
    out_path = os.path.join(OUT_DIR, "world_2d.png")
    final.save(out_path, "PNG", optimize=True)
    print(f"[ok] final map -> {out_path}")

    base_no_label = os.path.join(OUT_DIR, "world_2d_base.png")
    base_img.save(base_no_label, "PNG", optimize=True)
    print(f"[ok] base (no labels) -> {base_no_label}")


if __name__ == "__main__":
    main()
