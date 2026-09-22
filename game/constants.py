# -*- coding: utf-8 -*-
"""引擎与各域 Mixin 共享的模块级常量与纯函数。"""

# 元素 ID → 中文名
ELEMENT_NAMES = {
    "metal": "金", "wood": "木", "water": "水",
    "fire": "火", "earth": "土",
    "thunder": "雷", "ice": "冰", "wind": "风",
    "none": "无", "all": "五行",
}

# 境界成长斜率：闭关月收入与静态 qi 奖励/惩罚共用（练气 1.8x → 元婴 15.4x）
REALM_QI_SLOPE = 0.8


def realm_qi_scale(order):
    """按境界序号（练气一层=1 … 元婴=18）返回 qi 缩放系数。"""
    return 1 + order * REALM_QI_SLOPE

