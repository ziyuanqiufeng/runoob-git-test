# -*- coding: utf-8 -*-
"""拼装捏脸合成器（路线 A）：按部件参数用 PIL 图层合成头像。

纯 PIL 实现（不依赖 Qt），可离线单测。部件为透明底 PNG，
tintable 层（脸型）按肤色 tint 整体调色。
"""
import json
import os
import random

from PIL import Image, ImageDraw

# 脸型部件的基准肤色（占位部件按此色绘制，调色按比例换算）
_BASE_SKIN = (240, 220, 200)

# 脸部保护区域（椭圆，x0,y0,x1,y1）：发型层合成时清空此区域的 alpha，
# 防止发型图（尤其 AI 生成件）盖住眉/眼/鼻/嘴。
_FACE_HOLE = (86, 92, 170, 210)


def load_parts_config(config_dir="config"):
    """加载部件配置 config/face_parts.json；失败返回 None。"""
    path = os.path.join(config_dir, "face_parts.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data.get("layers"):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _tint_image(img, tint):
    """把非透明像素的 RGB 按 tint/基准肤色比例缩放（alpha 不变）。"""
    if not tint:
        return img
    r, g, b, a = img.split()
    scale = [t / max(base, 1) for t, base in zip(tint, _BASE_SKIN)]
    r = r.point(lambda v: min(255, int(v * scale[0])))
    g = g.point(lambda v: min(255, int(v * scale[1])))
    b = b.point(lambda v: min(255, int(v * scale[2])))
    return Image.merge("RGBA", (r, g, b, a))


def _punch_face_hole(img):
    """清空脸部椭圆区域的 alpha（发型层专用，幂等）。"""
    from PIL import ImageChops
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse(_FACE_HOLE, fill=255)
    r, g, b, a = img.split()
    a = ImageChops.subtract(a, mask)
    return Image.merge("RGBA", (r, g, b, a))


def random_face_params(config_dir="config", rng=None):
    """随机生成一套拼装参数（optional 层也可能随机到 none）。"""
    cfg = load_parts_config(config_dir)
    if not cfg:
        return {}
    rng = rng or random
    params = {}
    for layer in cfg.get("layers", []):
        options = [p["id"] for p in layer.get("parts", [])]
        if options:
            params[layer["id"]] = rng.choice(options)
    skins = cfg.get("skins", [])
    if skins:
        params["skin"] = rng.choice(skins)["id"]
    return params


def compose(face_params, out_path, config_dir="config"):
    """按参数合成头像 PNG，返回输出路径；配置缺失返回 None。

    face_params: {层id: 部件id, ..., "skin": 肤色id}
    容错策略：缺失层/部件文件缺失时跳过该层，不抛异常。
    """
    cfg = load_parts_config(config_dir)
    if not cfg:
        return None
    root = os.path.dirname(os.path.abspath(config_dir))
    size = int(cfg.get("canvas", 256))
    canvas = Image.new("RGBA", (size, size), (30, 40, 62, 255))
    params = face_params or {}
    skin_id = params.get("skin")
    tint = None
    for s in cfg.get("skins", []):
        if s.get("id") == skin_id:
            tint = s.get("tint")
            break

    for layer in sorted(cfg.get("layers", []), key=lambda l: l.get("z", 0)):
        part_id = params.get(layer["id"])
        if not part_id:
            continue
        part = next((p for p in layer.get("parts", []) if p.get("id") == part_id), None)
        if not part or not part.get("file"):
            continue  # none / 空文件：跳过
        fpath = part["file"]
        if not os.path.isabs(fpath):
            fpath = os.path.join(root, fpath)
        if not os.path.exists(fpath):
            continue
        try:
            img = Image.open(fpath).convert("RGBA")
        except OSError:
            continue
        if img.size != (size, size):
            img = img.resize((size, size))
        if layer.get("tintable"):
            img = _tint_image(img, tint)
        if layer["id"] == "hair":
            img = _punch_face_hole(img)
        canvas.alpha_composite(img)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    canvas.save(out_path)
    return out_path
