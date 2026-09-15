# -*- coding: utf-8 -*-
"""生成拼装捏脸部件资源。

默认模式：PIL 程序化绘制占位部件（形状朴素但结构/命名/尺寸与正式
部件完全一致，可立即驱动整条捏脸管线；后续用正式资源替换同名文件即可）。

--via-ai 模式：调 Agnes 文生图批量生成（纯白底 → 色键抠图 → 透明 PNG），
生成较慢（每张数十秒），建议分批筛图后替换占位部件。

用法：
    python tools/gen_face_parts.py                # 补齐缺失的占位部件
    python tools/gen_face_parts.py --force        # 覆盖已有占位部件
    python tools/gen_face_parts.py --via-ai       # AI 批量生成（全部）
    python tools/gen_face_parts.py --via-ai --only hair   # 只生成发型层
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(os.path.join(os.path.dirname(__file__))))
CANVAS = 256
# 占位部件基准肤色（与 face_compositor._BASE_SKIN 一致）
_SKIN = (240, 220, 200)
_HAIR = (40, 34, 30)
_LINE = (30, 26, 24)


def _new():
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _ellipse(draw, box, fill):
    draw.ellipse(box, fill=fill)


# ---------------- 脸型（tintable：基准肤色绘制） ----------------

def _draw_face(part_id):
    img, d = _new()
    if part_id == "oval_1":       # 鹅蛋
        _ellipse(d, (68, 56, 188, 216), _SKIN)
    elif part_id == "oval_2":     # 瓜子（略窄+下巴收）
        _ellipse(d, (78, 58, 178, 200), _SKIN)
        d.polygon([(98, 170), (158, 170), (128, 214)], fill=_SKIN)
    elif part_id == "round_1":    # 圆润
        _ellipse(d, (66, 66, 190, 190), _SKIN)
    else:                         # square_1 方正（圆角矩形）
        d.rounded_rectangle((72, 62, 184, 204), radius=36, fill=_SKIN)
    return img


# ---------------- 眉 ----------------

def _draw_brow(part_id):
    img, d = _new()
    y = 108
    if part_id == "sword_1":      # 剑眉（外挑粗线）
        d.line([(88, y + 8), (116, y - 2), (152, y + 4)], fill=_LINE, width=6)
    elif part_id == "willow_1":   # 柳叶（细弯）
        d.arc((88, y - 6, 152, y + 16), 200, 340, fill=_LINE, width=4)
    elif part_id == "straight_1": # 平眉
        d.line([(90, y + 2), (150, y + 2)], fill=_LINE, width=5)
    else:                         # thick_1 浓眉
        d.line([(88, y + 4), (152, y - 2)], fill=_LINE, width=10)
    return img


# ---------------- 眼 ----------------

def _draw_eye(part_id):
    img, d = _new()
    y = 130
    def _pair(box_w, box_h, offset=(0, 0)):
        for cx in (104, 152):
            x0, y0 = cx - box_w // 2 + offset[0], y - box_h // 2 + offset[1]
            _ellipse(d, (x0, y0, x0 + box_w, y0 + box_h), (250, 248, 244))
            px, py = cx - box_w // 6 + offset[0], y - box_h // 6 + offset[1]
            _ellipse(d, (px, py, px + box_w // 2, py + box_h // 2), (25, 22, 20))
    if part_id == "phoenix_1":
        _pair(28, 14)
        d.line([(94, y), (118, y - 6)], fill=_LINE, width=3)
        d.line([(138, y - 6), (162, y)], fill=_LINE, width=3)
    elif part_id == "round_1":
        _pair(22, 22)
    elif part_id == "narrow_1":
        _pair(30, 10)
    else:                          # big_1 杏眼
        _pair(26, 26)
    return img


# ---------------- 嘴 ----------------

def _draw_mouth(part_id):
    img, d = _new()
    y = 176
    if part_id == "smile_1":
        d.arc((112, y - 8, 144, y + 10), 20, 160, fill=_LINE, width=4)
    elif part_id == "neutral_1":
        d.line([(114, y), (142, y)], fill=_LINE, width=4)
    elif part_id == "pout_1":
        d.arc((116, y - 10, 140, y + 8), 200, 340, fill=_LINE, width=4)
    else:                          # grin_1 咧嘴
        d.arc((108, y - 12, 148, y + 12), 15, 165, fill=_LINE, width=5)
    return img


# ---------------- 发型（z 在脸型之上） ----------------

def _draw_hair(part_id):
    img, d = _new()
    if part_id == "high_ponytail":
        _ellipse(d, (58, 34, 198, 132), _HAIR)
        _ellipse(d, (178, 40, 226, 150), _HAIR)   # 后脑束起
    elif part_id == "loose":
        _ellipse(d, (54, 34, 202, 136), _HAIR)
        d.rectangle((54, 100, 84, 220), fill=_HAIR)
        d.rectangle((172, 100, 202, 220), fill=_HAIR)
    elif part_id == "topknot":
        _ellipse(d, (58, 40, 198, 128), _HAIR)
        _ellipse(d, (104, 14, 152, 56), _HAIR)    # 头顶髻
    elif part_id == "half_up":
        _ellipse(d, (56, 36, 200, 132), _HAIR)
        _ellipse(d, (166, 44, 216, 132), _HAIR)
    elif part_id == "short_bob":
        _ellipse(d, (56, 38, 200, 150), _HAIR)
    else:                                          # twin_buns 双丫髻
        _ellipse(d, (58, 44, 198, 130), _HAIR)
        _ellipse(d, (62, 8, 118, 58), _HAIR)
        _ellipse(d, (138, 8, 194, 58), _HAIR)
    # 露出脸部区域（挖空脸位）
    hole = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hole)
    hd.ellipse((86, 92, 170, 210), fill=(0, 0, 0, 255))
    r, g, b, a = img.split()
    from PIL import ImageChops
    a = ImageChops.subtract(a, hole.split()[3])
    return Image.merge("RGBA", (r, g, b, a))


# ---------------- 饰品 ----------------

def _draw_accessory(part_id):
    img, d = _new()
    if part_id == "jade_crown":
        _ellipse(d, (108, 48, 148, 80), (96, 200, 160))
        d.ellipse((108, 48, 148, 80), outline=(212, 180, 100), width=4)
    elif part_id == "flower_pin":
        for dx, dy in ((-8, 0), (8, 0), (0, -8), (0, 8)):
            _ellipse(d, (172 + dx - 7, 96 + dy - 7, 172 + dx + 7, 96 + dy + 7),
                     (240, 150, 180))
        _ellipse(d, (168, 92, 180, 104), (250, 230, 120))
    elif part_id == "scar_mark":
        d.line([(150, 150), (166, 180)], fill=(196, 120, 110), width=4)
    return img


_DRAWERS = {
    "face": _draw_face, "brow": _draw_brow, "eye": _draw_eye,
    "mouth": _draw_mouth, "hair": _draw_hair, "accessory": _draw_accessory,
}


# ---------------- 主流程 ----------------

def _resolve(root, rel):
    return os.path.join(root, rel) if rel else None


def gen_placeholder(force=False):
    """按 config/face_parts.json 程序化补齐缺失的占位部件。"""
    import json
    cfg = json.load(open(os.path.join(ROOT, "config", "face_parts.json"),
                         encoding="utf-8"))
    made = skipped = 0
    for layer in cfg.get("layers", []):
        drawer = _DRAWERS.get(layer["id"])
        for part in layer.get("parts", []):
            rel = part.get("file")
            if not rel or not drawer:
                continue
            out = os.path.join(ROOT, rel)
            if os.path.exists(out) and not force:
                skipped += 1
                continue
            os.makedirs(os.path.dirname(out), exist_ok=True)
            drawer(part["id"]).save(out)
            made += 1
    print(f"占位部件：生成 {made} 个，跳过已有 {skipped} 个。")


def gen_via_ai(only=None):
    """AI 模式：按部件逐个调 Agnes 文生图（纯白底）→ 色键抠图 → 覆盖保存。"""
    import json
    from game.portrait_generator import generate_portrait_from_prompt

    cfg = json.load(open(os.path.join(ROOT, "config", "face_parts.json"),
                         encoding="utf-8"))
    style = ("game asset, single {name} on pure white background, "
             "centered, no text, no border, ink wash style")
    made = 0
    for layer in cfg.get("layers", []):
        if only and layer["id"] != only:
            continue
        for part in layer.get("parts", []):
            rel = part.get("file")
            if not rel or part["id"] == "none":
                continue
            prompt = style.format(name=part["name"])
            ok, path = generate_portrait_from_prompt(prompt, config_dir="config")
            if not ok:
                print(f"[失败] {layer['id']}/{part['id']}")
                continue
            img = Image.open(path).convert("RGBA").resize((CANVAS, CANVAS))
            # 色键抠白底：接近纯白的像素转透明（通道运算，避免弃用的 getdata）
            from PIL import ImageChops
            r, g, b, a = img.split()
            mask = ImageChops.multiply(
                ImageChops.multiply(
                    r.point(lambda v: 255 if v > 240 else 0),
                    g.point(lambda v: 255 if v > 240 else 0)),
                b.point(lambda v: 255 if v > 240 else 0))
            a = ImageChops.subtract(a, mask)
            img = Image.merge("RGBA", (r, g, b, a))
            out = os.path.join(ROOT, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            img.save(out)
            os.remove(path)
            made += 1
            print(f"[完成] {layer['id']}/{part['id']} -> {rel}")
    print(f"AI 生成完成：{made} 个部件。")


def main():
    parser = argparse.ArgumentParser(description="捏脸部件资源生成")
    parser.add_argument("--force", action="store_true", help="覆盖已有占位部件")
    parser.add_argument("--via-ai", action="store_true", help="用 Agnes 文生图生成正式部件")
    parser.add_argument("--only", default=None, help="--via-ai 时只生成指定层（如 hair）")
    args = parser.parse_args()
    if args.via_ai:
        gen_via_ai(args.only)
    else:
        gen_placeholder(force=args.force)


if __name__ == "__main__":
    main()
