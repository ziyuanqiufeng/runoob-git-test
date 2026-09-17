# -*- coding: utf-8 -*-
"""FaceCompositor 边界测试（纯 PIL，离线，不触 UI）。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image

from game.face_compositor import (
    load_parts_config, random_face_params, compose, _tint_image,
)


def _cfg_with_parts():
    """构造一份最小可用的部件配置 + 对应 PNG 文件。"""
    tmp = tempfile.mkdtemp()
    parts_dir = os.path.join(tmp, "assets", "faces")
    os.makedirs(parts_dir, exist_ok=True)
    for part in ("face_a.png", "hair_a.png"):
        Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(os.path.join(parts_dir, part))
    cfg = {
        "canvas": 64,
        "skins": [{"id": "s1", "tint": [200, 180, 160]}],
        "layers": [
            {"id": "face", "z": 1, "tintable": True,
             "parts": [{"id": "face_a", "file": "assets/faces/face_a.png"}]},
            {"id": "hair", "z": 2,
             "parts": [{"id": "hair_a", "file": "assets/faces/hair_a.png"}]},
        ],
    }
    cfg_dir = os.path.join(tmp, "config")
    os.makedirs(cfg_dir, exist_ok=True)
    with open(os.path.join(cfg_dir, "face_parts.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    return cfg_dir, tmp


class TestCompose(unittest.TestCase):
    def test_compose_writes_png(self):
        cfg_dir, root = _cfg_with_parts()
        out = os.path.join(root, "out.png")
        res = compose({"face": "face_a", "hair": "hair_a", "skin": "s1"}, out, cfg_dir)
        self.assertEqual(res, out)
        self.assertTrue(os.path.exists(out))
        with Image.open(out) as im:
            self.assertEqual(im.size, (64, 64))

    def test_compose_no_config_returns_none(self):
        empty = tempfile.mkdtemp()
        self.assertIsNone(
            compose({"face": "x"}, os.path.join(empty, "o.png"), empty)
        )

    def test_compose_missing_files_skips_gracefully(self):
        cfg_dir, root = _cfg_with_parts()
        os.remove(os.path.join(root, "assets", "faces", "face_a.png"))  # 脸型图丢了
        out = os.path.join(root, "out2.png")
        res = compose({"face": "face_a", "hair": "hair_a"}, out, cfg_dir)
        # 脸型缺失仍应合成（跳过该层），不抛异常
        self.assertEqual(res, out)
        self.assertTrue(os.path.exists(out))

    def test_compose_corrupt_image_skipped(self):
        cfg_dir, root = _cfg_with_parts()
        # 把发型图写成非法字节 → compose 应跳过该层而非崩溃
        with open(os.path.join(root, "assets", "faces", "hair_a.png"), "wb") as f:
            f.write(b"not a png")
        out = os.path.join(root, "out3.png")
        self.assertEqual(compose({"face": "face_a", "hair": "hair_a"}, out, cfg_dir), out)

    def test_empty_params_only_canvas(self):
        cfg_dir, root = _cfg_with_parts()
        out = os.path.join(root, "out4.png")
        res = compose({}, out, cfg_dir)
        self.assertTrue(os.path.exists(out))
        with Image.open(out) as im:
            self.assertEqual(im.size, (64, 64))


class TestRandomParams(unittest.TestCase):
    def test_random_params_covers_layers(self):
        cfg_dir, _ = _cfg_with_parts()
        params = random_face_params(cfg_dir)
        self.assertIn("face", params)
        self.assertIn("skin", params)

    def test_random_params_no_config_empty(self):
        self.assertEqual(random_face_params(tempfile.mkdtemp()), {})


class TestTint(unittest.TestCase):
    def test_tint_scales_rgb(self):
        img = Image.new("RGBA", (4, 4), (240, 220, 200, 255))
        out = _tint_image(img, [200, 180, 160])
        # 调色后像素应低于基准（tint < base 时变暗），alpha 不变
        self.assertEqual(out.size, img.size)
        r, g, b, a = out.split()
        self.assertEqual(a.getpixel((0, 0)), 255)

    def test_tint_none_returns_same(self):
        img = Image.new("RGBA", (4, 4), (10, 20, 30, 255))
        self.assertIs(_tint_image(img, None), img)


if __name__ == "__main__":
    unittest.main()
