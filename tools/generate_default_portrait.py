# -*- coding: utf-8 -*-
"""生成默认主角头像占位图。"""
import os
from PIL import Image, ImageDraw, ImageFont


def generate_default_portrait(output_path="assets/portraits/protagonist_default.png", size=128):
    """生成一个圆形蓝色渐变占位头像，中间写'主'字。"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img = Image.new("RGB", (size, size), color=(70, 130, 180))
    draw = ImageDraw.Draw(img)
    # 外圆
    draw.ellipse(
        [8, 8, size - 8, size - 8],
        fill=(100, 160, 210),
        outline=(200, 220, 255),
        width=3,
    )
    # 文字
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", size // 3)
    except Exception:
        font = ImageFont.load_default()
    draw.text((size // 2, size // 2), "主", fill=(255, 255, 255), font=font, anchor="mm")
    img.save(output_path)
    print(f"默认主角头像已生成：{output_path}")


if __name__ == "__main__":
    generate_default_portrait()
