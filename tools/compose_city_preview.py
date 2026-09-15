# -*- coding: utf-8 -*-
"""合成「城市界面实际效果预览图」：真实背景图 + 界面元素叠加。

以赤焰城为例，读取 assets/city_bg/chiyan_city@2x.png 作背景，
在其上叠加标题栏、6 个建筑名牌、详情提示栏、底部操作栏，模拟游戏内实际效果。
输出 outputs/city_preview_chiyan.png。
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = r"D:/ziyuanqiufeng"
BG = os.path.join(ROOT, "assets", "city_bg", "chiyan_city@2x.png")
OUT = os.path.join(ROOT, "outputs", "city_preview_chiyan.png")

FONT_BOLD = r"C:/Windows/Fonts/msyhbd.ttc"
FONT_REG = r"C:/Windows/Fonts/msyh.ttc"

# 建筑热点：id, 名称, 功能标签, 归一化 coords [x1,y1,x2,y2]
BUILDINGS = [
    ("city_lord_hall", "城主府", "城市任务", [0.30, 0.10, 0.55, 0.35]),
    ("inn", "客栈", "歇息", [0.60, 0.15, 0.85, 0.40]),
    ("market", "坊市", "交易", [0.05, 0.40, 0.35, 0.65]),
    ("arena", "演武场", "切磋", [0.40, 0.55, 0.70, 0.85]),
    ("alchemy_pavilion", "炼丹阁", "炼丹", [0.70, 0.50, 0.95, 0.80]),
    ("cave", "城中洞府", "闭关", [0.02, 0.02, 0.22, 0.22]),
]


def draw_rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def main():
    img = Image.open(BG).convert("RGB")
    W, H = img.size  # 1600 x 960
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    f_name = ImageFont.truetype(FONT_BOLD, 34)
    f_action = ImageFont.truetype(FONT_REG, 24)
    f_bar = ImageFont.truetype(FONT_BOLD, 30)
    f_bar_sub = ImageFont.truetype(FONT_REG, 22)
    f_hint = ImageFont.truetype(FONT_REG, 22)

    # === 顶部标题栏 ===
    draw_rounded(d, [20, 16, W - 20, 84], 16, (255, 255, 255, 200))
    d.text((52, 36), "赤焰城", font=f_name, fill=(44, 62, 80, 255))
    # 展开介绍按钮
    draw_rounded(d, [W - 300, 34, W - 56, 72], 12, (52, 152, 219, 60))
    d.text((W - 268, 43), "展开介绍", font=f_bar_sub, fill=(24, 95, 165, 255))

    # === 建筑名牌（半透明黑底 + 白字，仿 name_label 样式）===
    for _id, name, action, (x1, y1, x2, y2) in BUILDINGS:
        cx = int((x1 + x2) / 2 * W)
        cy = int((y1 + y2) / 2 * H)
        tw = max(text_size(d, name, f_name)[0], text_size(d, action, f_action)[0])
        box_w = tw + 40
        box_h = 66
        # 名牌放热点中心上方
        bx0 = cx - box_w // 2
        by0 = cy - box_h - 14
        draw_rounded(d, [bx0, by0, bx0 + box_w, by0 + box_h], 12, (0, 0, 0, 175))
        d.text((cx, by0 + 8), name, font=f_name, fill=(255, 255, 255, 255), anchor="ma")
        d.text((cx, by0 + 42), action, font=f_action, fill=(220, 220, 220, 255), anchor="ma")

    # === 建筑详情提示栏 ===
    draw_rounded(d, [20, H - 140, W - 20, H - 104], 12, (248, 249, 250, 215))
    d.text((48, H - 128), "将鼠标移到建筑上查看详情，点击建筑进入功能", font=f_hint, fill=(85, 85, 85, 255))

    # === 底部操作栏 ===
    draw_rounded(d, [20, H - 96, W - 20, H - 20], 16, (255, 255, 255, 210))
    # 城池发展
    draw_rounded(d, [48, H - 78, 232, H - 36], 10, (52, 152, 219, 55))
    d.text((140, H - 66), "城池发展", font=f_bar_sub, fill=(24, 95, 165, 255), anchor="mm")
    # 拜访城中人物
    draw_rounded(d, [256, H - 78, 470, H - 36], 10, (52, 152, 219, 55))
    d.text((363, H - 66), "拜访城中人物", font=f_bar_sub, fill=(24, 95, 165, 255), anchor="mm")
    # 离开
    draw_rounded(d, [W - 220, H - 78, W - 52, H - 36], 10, (141, 110, 99, 255))
    d.text((W - 136, H - 66), "离开", font=f_bar_sub, fill=(255, 255, 255, 255), anchor="mm")

    # 合成
    result = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    result.save(OUT, "PNG")
    print(f"[ok] -> {OUT}  ({result.size})")


if __name__ == "__main__":
    main()
