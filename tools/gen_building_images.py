# -*- coding: utf-8 -*-
"""生成 6 个修仙建筑的功能图（风格统一、东方古典修仙风）。

每个建筑一张 1024x1024 图，体现功能属性 + 建筑外观/牌匾/内部陈设。
输出到 assets/buildings/<bid>.png。
"""
import os
import sys

ROOT = r"D:/ziyuanqiufeng"
SKILL_SCRIPTS = os.path.join(
    os.environ.get("USERPROFILE", r"C:\Users\14374"),
    ".workbuddy", "skills", "agnes-image-gen", "scripts",
)
OUT_DIR = os.path.join(ROOT, "assets", "buildings")

sys.path.insert(0, SKILL_SCRIPTS)
import generate_image as gen  # noqa: E402

# 统一风格基调（保证 6 张画风一致、色彩和谐）
STYLE = (
    "traditional Chinese xianxia architecture, elegant curved roofs with upturned eaves, "
    "ornate wooden details and carved beams, stone and timber construction, warm harmonious "
    "color palette with jade green and gold accents, soft misty atmosphere, detailed "
    "textures, tranquil and serene, photorealistic, high detail"
)

BUILDINGS = [
    (
        "city_lord_hall",
        "城主府",
        "magnificent city lord hall, grand main gate with a large hanging wooden plaque, "
        "solemn administrative chamber, a notice board with posted task scrolls and bounty "
        "decrees, red pillars and gold roof ornaments, majestic and dignified, ",
    ),
    (
        "inn",
        "客栈",
        "cozy traditional inn, wine flags and warm red lanterns hanging under the eaves, "
        "inviting guest rooms with simple wooden beds, a quiet inner courtyard with a well, "
        "warm welcoming resting atmosphere, ",
    ),
    (
        "market",
        "坊市",
        "bustling cultivation marketplace, a grand market archway, rows of vendor stalls "
        "displaying herbs, pills, talismans and treasures on wooden shelves, colorful "
        "canopies, lively trading atmosphere, ",
    ),
    (
        "arena",
        "演武场",
        "open martial arts arena, a central elevated dueling platform, weapon racks lined "
        "with swords and spears, stone training ground with practice dummies, banners, "
        "competitive sparring atmosphere, ",
    ),
    (
        "alchemy_pavilion",
        "炼丹阁",
        "alchemy pavilion with a large bronze pill furnace at its heart, walls of wooden "
        "cabinets storing herbs and recipe scrolls, mystical smoke curling from the furnace, "
        "soft warm glow, refining atmosphere, ",
    ),
    (
        "cave",
        "城中洞府",
        "secluded meditation cave dwelling, a stone chamber with a sealed stone door carved "
        "with talismans, a simple meditation cushion and incense burner, soft spiritual "
        "energy glow from jade lamps, quiet peaceful cultivation atmosphere, ",
    ),
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for bid, name, body in BUILDINGS:
        out_path = os.path.join(OUT_DIR, f"{bid}.png")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"[skip] {name} 已存在 -> {out_path}")
            continue
        prompt = body + STYLE
        print(f"[gen] {name} ({bid}) ...")
        parsed = gen.call_api(prompt, gen.DEFAULT_MODEL, gen.DEFAULT_API_KEY, "1024x1024", 1)
        url = parsed["data"][0]["url"]
        tmp = gen.download_image(url, OUT_DIR, 0)
        os.replace(tmp, out_path)
        print(f"[ok]  {name} -> {out_path}")


if __name__ == "__main__":
    main()
