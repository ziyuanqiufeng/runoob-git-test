# -*- coding: utf-8 -*-
"""为所有 type=city 的地点批量添加默认 buildings 数据。"""

import json
import os
import sys


def main(config_dir="config"):
    path = os.path.join(config_dir, "locations.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    default_buildings = [
        {"id": "city_lord_hall", "name": "城主府", "description": "城主处理政务之地，可接取城池任务与领取赏格。", "action": "quest"},
        {"id": "inn", "name": "客栈", "description": "可供歇息恢复，也能听到不少江湖传闻。", "action": "rest"},
        {"id": "market", "name": "坊市", "description": "修仙者买卖丹药、材料与法宝的热闹集市。", "action": "market"},
        {"id": "arena", "name": "演武场", "description": "供修士切磋技艺、磨炼战斗经验之地。", "action": "arena"},
        {"id": "alchemy_pavilion", "name": "炼丹阁", "description": "出售丹方与珍稀药材，常有丹师驻足。", "action": "shop"},
    ]

    changed = 0
    for loc in data:
        if loc.get("type") == "city" and "buildings" not in loc:
            loc["buildings"] = list(default_buildings)
            changed += 1
            print(f"added buildings to {loc['id']}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\ntotal cities updated: {changed}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "config")
