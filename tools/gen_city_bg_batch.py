# -*- coding: utf-8 -*-
"""批量生成 8 城「全貌鸟瞰图」背景并覆盖到 assets/city_bg。

用户要求：城市图为整座城市全貌（2D 鸟瞰全景），尽量不出现人物。
做法：prompt 统一改为 aerial panoramic bird's eye view（俯瞰全城），
用 tranquil/serene 等正向描述营造无人氛围（避免否定词触发内容审核）。

流程：8 城各生成 1024x1024 → 中心裁 5:3 → 输出 800x480 与 1600x960 覆盖。
原程序化图已备份到 _programmatic_backup/。
"""
import os
import sys

from PIL import Image

ROOT = r"D:/ziyuanqiufeng"
SKILL_SCRIPTS = os.path.join(
    os.environ.get("USERPROFILE", r"C:\Users\14374"),
    ".workbuddy", "skills", "agnes-image-gen", "scripts",
)
OUT_DIR = os.path.join(ROOT, "assets", "city_bg")
_TMP_DIR = os.path.join(ROOT, "assets", "city_bg", "_tmp")

sys.path.insert(0, SKILL_SCRIPTS)
import generate_image as gen  # noqa: E402

ASPECT = 5.0 / 3.0
OUT_SIZES = {"normal": (800, 480), "2x": (1600, 960)}

# 全貌鸟瞰 prompt（正向描述，聚焦建筑与地貌，营造静谧无人氛围）
CITIES = [
    (
        "luoxia_city",
        "Aerial panoramic bird's eye view of an entire ancient Chinese merchant city at "
        "sunset, golden warm light bathing the full cityscape, complete urban layout with "
        "grid of streets, tiered pagoda roofs and curved eaves covering the whole city, "
        "riverside canals with arched bridges, city walls and gates, warm orange sky "
        "afterglow, emphasizing architecture and terrain, tranquil and serene, wide "
        "horizontal composition showing the whole city, photorealistic, painterly",
    ),
    (
        "yunlan_city",
        "Aerial panoramic view of an entire floating xianxia city suspended in a sea of "
        "clouds, full cityscape of white and gold palaces with traditional curved roofs "
        "sitting on multiple floating rock islands, waterfalls cascading into clouds below, "
        "jade bridges connecting the islands, ancient pagodas, soft heavenly light, seen "
        "from high above showing the whole city layout, tranquil and serene, wide "
        "horizontal composition, photorealistic, epic fantasy",
    ),
    (
        "fufeng_city",
        "Aerial panoramic view of an entire ancient Chinese mountain fortress city perched "
        "atop a high windy ridge, full cityscape of sturdy stone walls and watchtowers "
        "along the mountain crest, strong winds and low clouds streaming over the peaks, "
        "hardy pine trees, dramatic high-altitude light, seen from above showing the "
        "complete city layout, emphasizing architecture and terrain, tranquil and serene, "
        "wide horizontal composition, photorealistic",
    ),
    (
        "wanyao_city",
        "Aerial panoramic view of an entire ancient Chinese frontier fortress city at the "
        "edge of a vast dark primeval forest, full cityscape of rugged log and stone walls, "
        "watchfires and torchlight, watchtowers, dense ancient trees surrounding the walls, "
        "seen from high above showing the complete city layout, emphasizing architecture "
        "and forest terrain, tranquil and serene, wide horizontal composition, photorealistic",
    ),
    (
        "xuanshui_city",
        "Aerial panoramic view of an entire ancient Chinese water city built across a "
        "cluster of islands in a deep blue lake, full cityscape of elegant pavilions and "
        "tiered pagodas connected by arched stone bridges, lotus and willow trees, calm "
        "shimmering water, seen from high above showing the complete island city layout, "
        "cool blue-green palette, tranquil and serene, wide horizontal composition, "
        "photorealistic",
    ),
    (
        "chiyan_city",
        "Aerial panoramic view of an entire ancient Chinese city at the foot of an active "
        "volcano, full cityscape of dark red walls, steam vents and sulfur fumes rising "
        "between buildings, lava fissures glowing in blackened rock slopes behind, "
        "ember-orange lighting, seen from high above showing the complete city layout "
        "against the volcano, emphasizing architecture and volcanic terrain, tranquil and "
        "serene, wide horizontal composition, photorealistic",
    ),
    (
        "wangchuan_town",
        "Aerial panoramic view of an entire ancient Chinese gloomy riverside ghost town, "
        "full townscape of dark wooden houses with faded paper lanterns, white fog rolling "
        "over the river, faint ghostly blue-green wisps, overcast twilight, seen from high "
        "above showing the complete town layout along the riverbank, tranquil mysterious "
        "mood, emphasizing architecture, wide horizontal composition, photorealistic",
    ),
    (
        "yunmeng_city",
        "Aerial panoramic view of an entire ancient Chinese fairy city shrouded in soft low "
        "clouds and mist, full cityscape of white and jade pavilions and pagodas half-hidden "
        "in drifting fog, quiet lakes, seen from high above showing the complete city "
        "layout, dreamy ethereal light, tranquil and serene, emphasizing architecture, wide "
        "horizontal composition, photorealistic",
    ),
]


def center_crop_5x3(img):
    """从方图中心裁剪为 5:3 横向。"""
    w, h = img.size
    target_h = int(round(w / ASPECT))
    if target_h > h:
        target_w = int(round(h * ASPECT))
        left = (w - target_w) // 2
        return img.crop((left, 0, left + target_w, h))
    top = (h - target_h) // 2
    return img.crop((0, top, w, top + target_h))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(_TMP_DIR, exist_ok=True)
    for city_id, prompt in CITIES:
        print(f"[gen] {city_id} ...")
        parsed = gen.call_api(prompt, gen.DEFAULT_MODEL, gen.DEFAULT_API_KEY, "1024x1024", 1)
        url = parsed["data"][0]["url"]
        tmp = gen.download_image(url, _TMP_DIR, 0)
        sample = os.path.join(OUT_DIR, f"{city_id}_sample.png")
        os.replace(tmp, sample)
        print(f"[ok]  {city_id} 原图 -> {sample}")

        img = Image.open(sample).convert("RGB")
        img = center_crop_5x3(img)
        for key, (w, h) in OUT_SIZES.items():
            suffix = "" if key == "normal" else "@2x"
            out = os.path.join(OUT_DIR, f"{city_id}{suffix}.png")
            img.resize((w, h), Image.LANCZOS).save(out, "PNG")
            print(f"[save] {out}")
    print("[done] 8 城全貌鸟瞰图已覆盖完成")


if __name__ == "__main__":
    main()