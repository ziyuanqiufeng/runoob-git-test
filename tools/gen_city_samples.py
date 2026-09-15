# -*- coding: utf-8 -*-
"""生成城市背景样本（落霞城、云岚城），供用户确认风格。

直接 import agnes-image-gen 技能的 call_api/download_image，
逐城生成 1024x1024 写实古风图并落盘为 assets/city_bg/<id>_sample.png。
幂等：已存在则跳过。
"""
import os
import sys
import datetime

ROOT = r"D:/ziyuanqiufeng"
SKILL_SCRIPTS = os.path.join(
    os.environ.get("USERPROFILE", r"C:\Users\14374"),
    ".workbuddy", "skills", "agnes-image-gen", "scripts",
)
OUT_DIR = os.path.join(ROOT, "assets", "city_bg")
_TMP_DIR = os.path.join(ROOT, "assets", "city_bg", "_tmp")

sys.path.insert(0, SKILL_SCRIPTS)
import generate_image as gen  # noqa: E402


SAMPLES = [
    {
        "id": "luoxia_city",
        "prompt": (
            "Ancient Chinese xianxia fantasy merchant city bathed in golden sunset light, "
            "warm orange and crimson sky afterglow, bustling riverside marketplace with "
            "ornate tiered pagoda roofs and curved eaves, rows of traditional wooden "
            "shophouses with red lanterns hanging along the canals, wide stone plaza "
            "filled with merchants and travelers, wooden arch bridges over gentle water, "
            "layered architecture receding into misty distant mountains, soft cinematic "
            "lighting, photorealistic, painterly composition, beautiful scene"
        ),
    },
    {
        "id": "yunlan_city",
        "prompt": (
            "Ancient Chinese xianxia floating city suspended in a vast sea of clouds above "
            "mountain peaks, ethereal white and gold palaces with traditional curved roofs "
            "sitting on giant floating rock islands, waterfalls cascading from the islands "
            "into the clouds below, jade bridges connecting the floating islands, ancient "
            "pagodas with subtle glowing runes, soft heavenly golden light filtering through "
            "the clouds, breathtaking aerial perspective view, photorealistic, epic fantasy, "
            "beautiful scene"
        ),
    },
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(_TMP_DIR, exist_ok=True)
    for s in SAMPLES:
        out_path = os.path.join(OUT_DIR, f"{s['id']}_sample.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"[skip] {s['id']} 已存在 -> {out_path}")
            continue
        print(f"[gen] {s['id']} ...")
        parsed = gen.call_api(
            s["prompt"], gen.DEFAULT_MODEL, gen.DEFAULT_API_KEY, "1024x1024", 1
        )
        url = parsed["data"][0]["url"]
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        tmp = gen.download_image(url, _TMP_DIR, 0)
        final = os.path.join(OUT_DIR, f"{s['id']}_sample.png")
        os.replace(tmp, final)
        print(f"[ok] {s['id']} -> {final}")


if __name__ == "__main__":
    main()