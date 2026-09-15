# -*- coding: utf-8 -*-
"""
批量更新 locations.json：
1. 为所有城池建筑添加 action 字段。
2. 为万妖城添加特色建筑"万兽园"。
3. 为玄水城添加特色建筑"水族商行"。
4. 为每个城池配置 background_image 字段（指向 assets/city_bg/ 下的占位图）。
"""

import json
import os

CONFIG_PATH = os.path.join("config", "locations.json")

# 建筑 ID 到 action 的映射
ACTION_MAP = {
    "city_lord_hall": "quest",
    "inn": "rest",
    "market": "market",
    "arena": "arena",
    "alchemy_pavilion": "alchemy",
}

# 城池 ID 到背景图片名的映射（图片放在 assets/city_bg/ 下）
BACKGROUND_MAP = {
    "luoxia_city": "luoxia_city.png",
    "yunmeng_city": "yunmeng_city.png",
    "fufeng_city": "fufeng_city.png",
    "wanyao_city": "wanyao_city.png",
    "xuanshui_city": "xuanshui_city.png",
    "chiyan_city": "chiyan_city.png",
    "wangchuan_town": "wangchuan_town.png",
    "yunlan_city": "yunlan_city.png",
}


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        locations = json.load(f)

    for loc in locations:
        if loc.get("type") != "city":
            continue

        loc_id = loc.get("id", "")

        # 配置背景图
        if loc_id in BACKGROUND_MAP:
            loc["background_image"] = BACKGROUND_MAP[loc_id]

        # 确保存在 buildings 列表
        buildings = loc.setdefault("buildings", [])

        # 为已有建筑添加 action
        for b in buildings:
            bid = b.get("id", "")
            if "action" not in b and bid in ACTION_MAP:
                b["action"] = ACTION_MAP[bid]

        # 万妖城添加万兽园
        if loc_id == "wanyao_city":
            if not any(b.get("id") == "beast_park" for b in buildings):
                buildings.append({
                    "id": "beast_park",
                    "name": "万兽园",
                    "description": "万妖城特色建筑，饲养各种奇珍异兽，可购买妖兽材料与灵兽契约。",
                    "action": "beast_park"
                })

        # 玄水城添加水族商行
        if loc_id == "xuanshui_city":
            if not any(b.get("id") == "aquatic_shop" for b in buildings):
                buildings.append({
                    "id": "aquatic_shop",
                    "name": "水族商行",
                    "description": "玄水城特色建筑，专营水系灵材、疗伤丹药与湖中奇珍。",
                    "action": "aquatic_shop"
                })

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(locations, f, ensure_ascii=False, indent=2)

    print("locations.json 更新完成。")


if __name__ == "__main__":
    main()
