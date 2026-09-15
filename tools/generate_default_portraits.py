# -*- coding: utf-8 -*-
"""生成默认主角立绘资源包。

按 protagonist_{realm}_{path}_{gender}.png 规则，
为筑基/金丹/元婴 × 十大流派 × 男/女 生成占位立绘。
运行后可直接被 game.portrait_generator.find_best_portrait_resource 匹配。
"""
import os
import sys

# 兼容 tools/ 目录下直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.portrait_generator import generate_all_default_portrait_resources


def main():
    paths = generate_all_default_portrait_resources(output_dir="assets/portraits", size=128)
    print(f"已生成 {len(paths)} 张默认立绘：")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
