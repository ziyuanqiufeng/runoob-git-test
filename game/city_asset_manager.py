# -*- coding: utf-8 -*-
"""
城池场景化 UI 资源管理。

启动时检查城市背景图与建筑图是否存在；缺失则自动调用生成脚本补齐占位资源，
保证新版 CityMapWidget 首次运行即可正常显示。
"""
import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "locations.json")
CITY_MAPS_PATH = os.path.join(PROJECT_ROOT, "config", "city_maps.json")
CITY_BG_DIR = os.path.join(PROJECT_ROOT, "assets", "city_bg")
CITY_BUILDINGS_DIR = os.path.join(PROJECT_ROOT, "assets", "city_buildings")


def _load_json(path):
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _city_ids_with_background():
    """返回所有配置了 background_image 的城池 ID 列表。"""
    locations = _load_json(CONFIG_PATH)
    return [
        loc["id"]
        for loc in locations
        if loc.get("background_image")
    ]


def _expected_building_counts():
    """返回每个城池期望生成的建筑组数。"""
    if not os.path.exists(CITY_MAPS_PATH):
        return {}
    city_maps = _load_json(CITY_MAPS_PATH)
    return {
        cfg["city_id"]: len(cfg.get("hotspots", []))
        for cfg in city_maps
    }


def _missing_backgrounds():
    """检查缺少哪些城市背景图。"""
    locations = _load_json(CONFIG_PATH)
    missing = []
    for loc in locations:
        bg = loc.get("background_image")
        if not bg:
            continue
        path = os.path.join(CITY_BG_DIR, bg)
        if not os.path.exists(path):
            missing.append(loc["id"])
    return missing


def _missing_buildings():
    """检查缺少哪些建筑图（按城市聚合）。"""
    if not os.path.exists(CITY_MAPS_PATH):
        return []
    city_maps = _load_json(CITY_MAPS_PATH)
    missing_cities = []
    for cfg in city_maps:
        city_id = cfg["city_id"]
        output_dir = os.path.join(CITY_BUILDINGS_DIR, city_id)
        for hotspot in cfg.get("hotspots", []):
            bid = hotspot.get("id")
            if not bid:
                continue
            normal = os.path.join(output_dir, f"{bid}.png")
            hover = os.path.join(output_dir, f"{bid}_hover.png")
            if not os.path.exists(normal) or not os.path.exists(hover):
                if city_id not in missing_cities:
                    missing_cities.append(city_id)
                break
    return missing_cities


def ensure_city_assets():
    """
    确保城市场景化 UI 所需占位资源存在。

    返回 (backgrounds_generated, buildings_generated) 表示本次生成数量。
    """
    # 把 tools 目录加入 sys.path，以便直接导入生成脚本
    tools_dir = os.path.join(PROJECT_ROOT, "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)

    backgrounds_generated = 0
    buildings_generated = 0

    missing_bg = _missing_backgrounds()
    if missing_bg:
        import generate_city_backgrounds
        # 临时重定向输出目录到项目根目录下的 assets
        generate_city_backgrounds.OUTPUT_DIR = CITY_BG_DIR
        generate_city_backgrounds.CONFIG_PATH = CONFIG_PATH
        generate_city_backgrounds.main()
        backgrounds_generated = len(missing_bg)

    missing_building_cities = _missing_buildings()
    if missing_building_cities:
        import generate_city_buildings
        generate_city_buildings.OUTPUT_ROOT = CITY_BUILDINGS_DIR
        generate_city_buildings.CONFIG_PATH = CITY_MAPS_PATH
        generate_city_buildings.main()
        buildings_generated = sum(
            count for city_id, count in _expected_building_counts().items()
            if city_id in missing_building_cities
        )

    return backgrounds_generated, buildings_generated
