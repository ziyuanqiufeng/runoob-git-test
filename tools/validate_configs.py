# -*- coding: utf-8 -*-
"""
配置校验工具。

用法：
    python tools/validate_configs.py [config_dir]

校验项：
1. 所有 JSON 文件是否为合法 JSON；
2. 配置数组中 id 是否唯一；
3. 跨文件引用（location_id、npc_id、item_id、skill_id、enemy_id 等）是否指向存在的配置。
"""

import json
import os
import sys


def load_json(path):
    """加载 JSON 文件，失败时抛出可读性较好的异常。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_ids(config_dir, filename):
    """读取指定配置文件，返回其中所有 'id' 字段的集合。"""
    path = os.path.join(config_dir, filename)
    if not os.path.exists(path):
        return set()
    data = load_json(path)
    ids = set()
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and "id" in entry:
                ids.add(entry["id"])
    elif isinstance(data, dict):
        # 某些配置文件顶层为字典，内部嵌套数组
        for value in data.values():
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and "id" in entry:
                        ids.add(entry["id"])
    return ids


def check_unique_ids(config_dir, filename):
    """检查配置文件中的 id 是否唯一，返回错误列表。"""
    path = os.path.join(config_dir, filename)
    if not os.path.exists(path):
        return [f"文件不存在：{filename}"]

    errors = []
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        return [f"{filename} JSON 解析失败：{e}"]

    seen = {}
    entries = []
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        # 收集所有嵌套数组中的 dict
        for value in data.values():
            if isinstance(value, list):
                entries.extend(value)

    for entry in entries:
        if isinstance(entry, dict) and "id" in entry:
            eid = entry["id"]
            if eid in seen:
                errors.append(f"{filename} 中存在重复 id：{eid}")
            else:
                seen[eid] = True
    return errors


def validate_references(config_dir):
    """执行跨配置引用校验，返回错误列表。"""
    errors = []

    # 预加载各配置 ID 集合
    location_ids = collect_ids(config_dir, "locations.json")
    npc_ids = collect_ids(config_dir, "npcs.json")
    realm_ids = collect_ids(config_dir, "realms.json")
    item_ids = collect_ids(config_dir, "items.json")
    skill_ids = collect_ids(config_dir, "skills.json")
    enemy_ids = collect_ids(config_dir, "enemies.json")
    quest_ids = collect_ids(config_dir, "quests.json")
    sect_ids = collect_ids(config_dir, "sects.json")
    recipe_ids = collect_ids(config_dir, "recipes.json")

    # 加载灵根配置，获取合法属性列表（含无属性 none 与五行阵法 all）
    spiritual_roots_path = os.path.join(config_dir, "spiritual_roots.json")
    spiritual_roots_data = load_json(spiritual_roots_path) if os.path.exists(spiritual_roots_path) else {}
    valid_elements = set(spiritual_roots_data.get("elements", []))
    valid_elements.update({"none", "all"})

    # 校验融合灵根引用的元素是否合法
    for fid, fcfg in spiritual_roots_data.get("fusion_roots", {}).items():
        for elem in fcfg.get("elements", []):
            if elem not in valid_elements:
                errors.append(f"spiritual_roots.json: 融合灵根 '{fid}' 包含非法元素 '{elem}'")

    # 校验 npcs.json 中的 location（NPC 所在地点字段为 location）
    npcs = load_json(os.path.join(config_dir, "npcs.json"))
    for npc in npcs:
        loc_id = npc.get("location")
        if not loc_id:
            continue
        # 跳过特殊占位地点（如云游商人）
        if loc_id.startswith("__") and loc_id.endswith("__"):
            continue
        if loc_id not in location_ids:
            errors.append(f"npcs.json: NPC '{npc.get('id')}' 的 location '{loc_id}' 不存在")

        # 校验头像/立绘路径格式
        portrait = npc.get("portrait")
        if portrait is not None:
            if not isinstance(portrait, str) or not portrait:
                errors.append(f"npcs.json: NPC '{npc.get('id')}' 的 portrait 必须是有效字符串")
            elif not portrait.startswith("assets/portraits/"):
                errors.append(f"npcs.json: NPC '{npc.get('id')}' 的 portrait 路径应以 assets/portraits/ 开头")
            elif not portrait.endswith(".png"):
                errors.append(f"npcs.json: NPC '{npc.get('id')}' 的 portrait 路径应以 .png 结尾")

        # 校验社交系统字段（可选，若配置则必须合法）
        gender = npc.get("gender")
        if gender and gender not in {"male", "female"}:
            errors.append(
                f"npcs.json: NPC '{npc.get('id')}' 的 gender '{gender}' 不合法，"
                f"应为 male 或 female"
            )
        realm_id = npc.get("realm_id")
        if realm_id and realm_id not in realm_ids:
            errors.append(
                f"npcs.json: NPC '{npc.get('id')}' 的 realm_id '{realm_id}' 不存在"
            )
        wisdom = npc.get("wisdom")
        if wisdom is not None and (not isinstance(wisdom, int) or wisdom < 1 or wisdom > 20):
            errors.append(
                f"npcs.json: NPC '{npc.get('id')}' 的 wisdom 应为 1-20 的整数"
            )
        age = npc.get("age")
        if age is not None and (not isinstance(age, int) or age < 1):
            errors.append(
                f"npcs.json: NPC '{npc.get('id')}' 的 age 应为正整数"
            )

    # 加载对话配置 ID 集合
    dialogue_ids = collect_ids(config_dir, "dialogues.json")

    # 校验 npcs.json 中的 dialogue_id 是否指向存在的对话配置
    for npc in npcs:
        dialogue_id = npc.get("dialogue_id")
        if dialogue_id and dialogue_id not in dialogue_ids:
            errors.append(
                f"npcs.json: NPC '{npc.get('id')}' 的 dialogue_id '{dialogue_id}' 不存在"
            )

    # 校验 sects.json 中的 location_id 与 leader_npc_id
    sects = load_json(os.path.join(config_dir, "sects.json"))
    for sect in sects:
        loc_id = sect.get("location_id")
        if loc_id and loc_id not in location_ids:
            errors.append(f"sects.json: 宗门 '{sect.get('id')}' 的 location_id '{loc_id}' 不存在")
        leader_id = sect.get("leader_npc_id")
        if leader_id and leader_id not in npc_ids:
            errors.append(f"sects.json: 宗门 '{sect.get('id')}' 的 leader_npc_id '{leader_id}' 不存在")

    # 校验 enemies.json 中的 realm_id 与 element
    enemies = load_json(os.path.join(config_dir, "enemies.json"))
    for enemy in enemies:
        realm_id = enemy.get("realm_id")
        if not realm_id:
            errors.append(f"enemies.json: 敌人 '{enemy.get('id')}' 缺少 realm_id")
        elif realm_id not in realm_ids:
            errors.append(f"enemies.json: 敌人 '{enemy.get('id')}' 的 realm_id '{realm_id}' 不存在")
        element = enemy.get("element", "none")
        if element not in valid_elements:
            errors.append(f"enemies.json: 敌人 '{enemy.get('id')}' 的 element '{element}' 不合法")
        # 校验高阶敌人 special 机制字段
        special = enemy.get("special")
        if special:
            if "summon" in special:
                summon = special["summon"]
                if summon.get("enemy_id") not in enemy_ids:
                    errors.append(
                        f"enemies.json: 敌人 '{enemy.get('id')}' 的 special.summon.enemy_id "
                        f"'{summon.get('enemy_id')}' 不存在"
                    )
                for key in ("chance", "hp_ratio", "attack_ratio", "turns"):
                    if key not in summon:
                        errors.append(
                            f"enemies.json: 敌人 '{enemy.get('id')}' 的 special.summon 缺少 {key}"
                        )
            if "special_skill" in special:
                skill = special["special_skill"]
                for key in ("name", "chance", "damage_multiplier", "cooldown", "description"):
                    if key not in skill:
                        errors.append(
                            f"enemies.json: 敌人 '{enemy.get('id')}' 的 special.special_skill 缺少 {key}"
                        )

    # 校验 skills.json 中 element 字段与 effects 字段合法性
    valid_skill_elements = valid_elements.copy()
    valid_effect_types = {
        "stun", "seal", "taunt", "attack_down", "defense_down", "dot",
        "shield", "reflect", "evasion_up", "attack_up", "defense_up",
        "heal_over_time", "cleanse",
    }
    valid_effect_targets = {"enemy", "player"}
    skills = load_json(os.path.join(config_dir, "skills.json"))
    for skill in skills:
        sid = skill.get("id", "<未知>")
        element = skill.get("element", "none")
        if element not in valid_skill_elements:
            errors.append(f"skills.json: 技能 '{sid}' 的 element '{element}' 不合法")
        realm_id = skill.get("realm_id")
        if realm_id and realm_id not in realm_ids:
            errors.append(f"skills.json: 技能 '{sid}' 的 realm_id '{realm_id}' 不存在")
        for effect in skill.get("effects", []):
            etype = effect.get("type")
            target = effect.get("target", "enemy")
            if etype not in valid_effect_types:
                errors.append(f"skills.json: 技能 '{sid}' 的 effect.type '{etype}' 不合法")
            if target not in valid_effect_targets:
                errors.append(f"skills.json: 技能 '{sid}' 的 effect.target '{target}' 不合法")

        # 校验满级熟练度专属特效
        for me in skill.get("mastery_effects", []):
            etype = me.get("type")
            target = me.get("target", "enemy")
            if etype not in valid_effect_types:
                errors.append(f"skills.json: 技能 '{sid}' 的 mastery_effect.type '{etype}' 不合法")
            if target not in valid_effect_targets:
                errors.append(f"skills.json: 技能 '{sid}' 的 mastery_effect.target '{target}' 不合法")
            if "chance" in me and not isinstance(me["chance"], (int, float)):
                errors.append(f"skills.json: 技能 '{sid}' 的 mastery_effect.chance 必须是数字")

    # 校验 quests.json 中的 reward.items（当前为 item_id 列表）
    quests = load_json(os.path.join(config_dir, "quests.json"))
    for quest in quests:
        reward = quest.get("reward", {})
        items = reward.get("items", [])
        for item_id in items:
            if item_id not in item_ids:
                errors.append(f"quests.json: 任务 '{quest.get('id')}' 的奖励物品 '{item_id}' 不存在")

    # 校验 recipes.json 中的 material_id 与 result_id
    recipes = load_json(os.path.join(config_dir, "recipes.json"))
    for recipe in recipes:
        rid = recipe.get("id", "<未知>")
        for mat_id in recipe.get("materials", {}).keys():
            if mat_id and mat_id not in item_ids:
                errors.append(f"recipes.json: 配方 '{rid}' 的材料 '{mat_id}' 不存在")
        result_id = recipe.get("result", {}).get("item_id")
        if result_id and result_id not in item_ids:
            errors.append(f"recipes.json: 配方 '{rid}' 的产物 '{result_id}' 不存在")

        # 炼丹配方字段校验
        category = recipe.get("category")
        if category is not None and category not in {"alchemy", "craft"}:
            errors.append(f"recipes.json: 配方 '{rid}' 的 category '{category}' 不合法")
        if category == "alchemy":
            success_rate = recipe.get("success_rate")
            if success_rate is None or not (0 < success_rate <= 1):
                errors.append(f"recipes.json: 炼丹配方 '{rid}' 的 success_rate 必须在 (0, 1] 区间")
            dan_bonus = recipe.get("dan_xiu_bonus")
            if dan_bonus is not None and not (0 <= dan_bonus <= 1):
                errors.append(f"recipes.json: 炼丹配方 '{rid}' 的 dan_xiu_bonus 必须在 [0, 1] 区间")

    # 校验 city_quests.json 模板字段
    city_quests_path = os.path.join(config_dir, "city_quests.json")
    if os.path.exists(city_quests_path):
        city_quests = load_json(city_quests_path)
        valid_target_types = {"collect", "kill", "escort"}
        for template in city_quests:
            tid = template.get("template_id", "<未知>")
            ttype = template.get("target_type")
            if ttype not in valid_target_types:
                errors.append(f"city_quests.json: 模板 '{tid}' 的 target_type '{ttype}' 不合法")
            # 击杀/收集类任务需要验证目标是否存在；护送类可不验证
            if ttype in {"collect", "kill"}:
                for target_id in template.get("target_pool", []):
                    if target_id and target_id not in item_ids and target_id not in enemy_ids:
                        errors.append(f"city_quests.json: 模板 '{tid}' 的目标 '{target_id}' 在 items/enemies 中不存在")
            count_range = template.get("count_range", [])
            if len(count_range) != 2 or count_range[0] > count_range[1]:
                errors.append(f"city_quests.json: 模板 '{tid}' 的 count_range 不合法")

    # 校验 building_unlocks.json 的跨引用
    building_unlocks_path = os.path.join(config_dir, "building_unlocks.json")
    if os.path.exists(building_unlocks_path):
        building_unlocks = load_json(building_unlocks_path)
        for bid, bcfg in building_unlocks.items():
            levels = bcfg.get("levels", [])
            for lv in levels:
                # 消耗物品存在性
                for item_id in lv.get("cost", {}).keys():
                    if item_id and item_id not in item_ids:
                        errors.append(
                            f"building_unlocks.json: 建筑 '{bid}' 等级 {lv.get('level')} "
                            f"消耗物品 '{item_id}' 不存在"
                        )
                # 解锁丹方存在性
                for recipe_id in lv.get("effects", {}).get("unlock_recipes", []):
                    if recipe_id not in recipe_ids:
                        errors.append(
                            f"building_unlocks.json: 建筑 '{bid}' 等级 {lv.get('level')} "
                            f"解锁丹方 '{recipe_id}' 不存在"
                        )
                # 解锁商店物品存在性
                for item_id in lv.get("effects", {}).get("unlock_items", []):
                    if item_id and item_id not in item_ids:
                        errors.append(
                            f"building_unlocks.json: 建筑 '{bid}' 等级 {lv.get('level')} "
                            f"解锁物品 '{item_id}' 不存在"
                        )

    # 校验 world_events.json 中的跨引用与字段合法性
    valid_trigger_types = {"random", "scheduled"}
    valid_condition_types = {"camp", "reputation", "year", "chance"}
    valid_effect_types = {"spawn_enemy", "change_npc_location", "add_reputation", "modify_price_multiplier", "notify"}
    world_events = load_json(os.path.join(config_dir, "world_events.json"))
    for event in world_events:
        eid = event.get("id", "<未知>")
        trigger = event.get("trigger", {})
        ttype = trigger.get("type")
        if ttype not in valid_trigger_types:
            errors.append(f"world_events.json: 事件 '{eid}' 的 trigger.type '{ttype}' 不合法")
        if ttype == "scheduled":
            month = trigger.get("month")
            if month is None or not (1 <= int(month) <= 12):
                errors.append(f"world_events.json: 事件 '{eid}' 的 scheduled month 不合法")
        for cond in event.get("conditions", []):
            ctype = cond.get("type")
            if ctype not in valid_condition_types:
                errors.append(f"world_events.json: 事件 '{eid}' 的 condition.type '{ctype}' 不合法")
        for effect in event.get("effects", []):
            etype = effect.get("type")
            if etype not in valid_effect_types:
                errors.append(f"world_events.json: 事件 '{eid}' 的 effect.type '{etype}' 不合法")
            if etype == "spawn_enemy":
                enemy_id = effect.get("enemy_id")
                if enemy_id and enemy_id not in enemy_ids:
                    errors.append(f"world_events.json: 事件 '{eid}' 的 enemy_id '{enemy_id}' 不存在")
            elif etype == "change_npc_location":
                npc_id = effect.get("npc_id")
                loc_id = effect.get("location")
                if npc_id and npc_id not in npc_ids:
                    errors.append(f"world_events.json: 事件 '{eid}' 的 npc_id '{npc_id}' 不存在")
                if loc_id and loc_id not in location_ids:
                    errors.append(f"world_events.json: 事件 '{eid}' 的 location '{loc_id}' 不存在")
            elif etype == "modify_price_multiplier":
                loc_id = effect.get("location")
                if loc_id and loc_id not in location_ids:
                    errors.append(f"world_events.json: 事件 '{eid}' 的 location '{loc_id}' 不存在")

    # 校验 world_bosses.json 中的跨引用与字段合法性
    world_bosses_path = os.path.join(config_dir, "world_bosses.json")
    if os.path.exists(world_bosses_path):
        world_bosses = load_json(world_bosses_path)
        for boss in world_bosses:
            bid = boss.get("id", "<未知>")
            base_enemy_id = boss.get("base_enemy_id")
            if base_enemy_id and base_enemy_id not in enemy_ids:
                errors.append(f"world_bosses.json: BOSS '{bid}' 的 base_enemy_id '{base_enemy_id}' 不存在")
            location_id = boss.get("location")
            if location_id and location_id not in location_ids:
                errors.append(f"world_bosses.json: BOSS '{bid}' 的 location '{location_id}' 不存在")
            # 校验掉落物品存在性
            for item_id in boss.get("loot", []):
                if item_id and item_id not in item_ids:
                    errors.append(f"world_bosses.json: BOSS '{bid}' 的掉落物品 '{item_id}' 不存在")
            # 校验参与奖励物品存在性
            for item_id in boss.get("participation_rewards", {}).keys():
                if item_id == "qi":
                    continue
                if item_id and item_id not in item_ids:
                    errors.append(f"world_bosses.json: BOSS '{bid}' 的参与奖励物品 '{item_id}' 不存在")
            min_realm_order = boss.get("min_realm_order")
            if min_realm_order is not None and not isinstance(min_realm_order, int):
                errors.append(f"world_bosses.json: BOSS '{bid}' 的 min_realm_order 必须是整数")
            respawn_months = boss.get("respawn_months")
            if respawn_months is not None and not isinstance(respawn_months, int):
                errors.append(f"world_bosses.json: BOSS '{bid}' 的 respawn_months 必须是整数")

    # 校验 diplomatic_missions.json 中的字段合法性
    diplomatic_missions_path = os.path.join(config_dir, "diplomatic_missions.json")
    if os.path.exists(diplomatic_missions_path):
        diplomatic_missions = load_json(diplomatic_missions_path)
        valid_target_relations = {"friendly", "hostile", "neutral"}
        valid_required_ranks = {"outer", "inner", "core", "elder", "leader"}
        for mission in diplomatic_missions:
            mid = mission.get("id", "<未知>")
            target_relation = mission.get("target_relation")
            if target_relation not in valid_target_relations:
                errors.append(
                    f"diplomatic_missions.json: 任务 '{mid}' 的 target_relation "
                    f"'{target_relation}' 不合法，应为 {valid_target_relations}"
                )
            required_rank = mission.get("required_rank")
            if required_rank not in valid_required_ranks:
                errors.append(
                    f"diplomatic_missions.json: 任务 '{mid}' 的 required_rank "
                    f"'{required_rank}' 不合法，应为 {valid_required_ranks}"
                )
            success_rate = mission.get("success_rate")
            if success_rate is None or not (0 < success_rate <= 1):
                errors.append(f"diplomatic_missions.json: 任务 '{mid}' 的 success_rate 必须在 (0, 1] 区间")
            duration_months = mission.get("duration_months")
            if duration_months is not None and (not isinstance(duration_months, int) or duration_months <= 0):
                errors.append(f"diplomatic_missions.json: 任务 '{mid}' 的 duration_months 必须是正整数")
            cost_contribution = mission.get("cost_contribution")
            if cost_contribution is not None and (not isinstance(cost_contribution, int) or cost_contribution < 0):
                errors.append(f"diplomatic_missions.json: 任务 '{mid}' 的 cost_contribution 必须是非负整数")

    # 校验 equipment_affixes.json 的跨引用与字段合法性
    equipment_affixes_path = os.path.join(config_dir, "equipment_affixes.json")
    if os.path.exists(equipment_affixes_path):
        equip_cfg = load_json(equipment_affixes_path)
        # 强化规则字段校验
        enh_rules = equip_cfg.get("enhancement_rules", {})
        if not isinstance(enh_rules.get("max_level"), int) or enh_rules.get("max_level", 0) <= 0:
            errors.append("equipment_affixes.json: enhancement_rules.max_level 必须是正整数")
        base_rate = enh_rules.get("base_success_rate")
        if base_rate is None or not (0 < base_rate <= 1):
            errors.append("equipment_affixes.json: enhancement_rules.base_success_rate 必须在 (0, 1] 区间")
        decay = enh_rules.get("success_rate_decay_per_level")
        if decay is None or not (0 <= decay <= 1):
            errors.append("equipment_affixes.json: enhancement_rules.success_rate_decay_per_level 必须在 [0, 1] 区间")
        # 附魔规则字段校验
        affix_rules = equip_cfg.get("affix_rules", {})
        max_affixes = affix_rules.get("max_affixes")
        if not isinstance(max_affixes, int) or max_affixes <= 0:
            errors.append("equipment_affixes.json: affix_rules.max_affixes 必须是正整数")
        for cost_key in ("enchant_cost", "reforge_cost"):
            cost = affix_rules.get(cost_key, {})
            spirit_stone = cost.get("spirit_stone")
            if spirit_stone is not None and not isinstance(spirit_stone, int):
                errors.append(f"equipment_affixes.json: affix_rules.{cost_key}.spirit_stone 必须是整数")
            material_id = cost.get("material_id")
            if material_id and material_id not in item_ids:
                errors.append(
                    f"equipment_affixes.json: affix_rules.{cost_key}.material_id "
                    f"'{material_id}' 在 items.json 中不存在"
                )
            material_count = cost.get("material_count")
            if material_count is not None and not isinstance(material_count, int):
                errors.append(f"equipment_affixes.json: affix_rules.{cost_key}.material_count 必须是整数")
        # 词缀池字段校验
        valid_slots = {"weapon", "helmet", "armor", "accessory"}
        for affix in equip_cfg.get("affix_pool", []):
            aid = affix.get("id", "<未知>")
            slots = affix.get("slots", [])
            if not slots:
                errors.append(f"equipment_affixes.json: 词缀 '{aid}' 的 slots 不能为空")
            for slot in slots:
                if slot not in valid_slots:
                    errors.append(
                        f"equipment_affixes.json: 词缀 '{aid}' 的 slot '{slot}' 不合法，"
                        f"应为 {valid_slots}"
                    )
            weight = affix.get("weight", 1)
            if not isinstance(weight, int) or weight <= 0:
                errors.append(f"equipment_affixes.json: 词缀 '{aid}' 的 weight 必须是正整数")
            value_range = affix.get("value_range", [])
            if len(value_range) != 2 or value_range[0] > value_range[1]:
                errors.append(f"equipment_affixes.json: 词缀 '{aid}' 的 value_range 不合法")

    # 校验 locations.json 中环境属性字段
    locations = load_json(os.path.join(config_dir, "locations.json"))
    valid_location_types = {"city", "sect", "wild"}
    for loc in locations:
        loc_id = loc.get("id", "<未知>")
        loc_type = loc.get("type")
        if loc_type not in valid_location_types:
            errors.append(f"locations.json: 地点 '{loc_id}' 的 type '{loc_type}' 未知，应为 {valid_location_types}")
        spirit_bonus = loc.get("spirit_bonus")
        if spirit_bonus is None or not isinstance(spirit_bonus, (int, float)):
            errors.append(f"locations.json: 地点 '{loc_id}' 的 spirit_bonus 必须是数字")
        elif not (0.0 <= float(spirit_bonus) <= 1.0):
            errors.append(f"locations.json: 地点 '{loc_id}' 的 spirit_bonus {spirit_bonus} 超出 [0.0, 1.0] 范围")
        safety_level = loc.get("safety_level")
        if safety_level is None or not isinstance(safety_level, int):
            errors.append(f"locations.json: 地点 '{loc_id}' 的 safety_level 必须是整数")
        elif not (0 <= safety_level <= 10):
            errors.append(f"locations.json: 地点 '{loc_id}' 的 safety_level {safety_level} 超出 [0, 10] 范围")
        travel_difficulty = loc.get("travel_difficulty")
        if travel_difficulty is None or not isinstance(travel_difficulty, (int, float)):
            errors.append(f"locations.json: 地点 '{loc_id}' 的 travel_difficulty 必须是数字")
        elif float(travel_difficulty) <= 0:
            errors.append(f"locations.json: 地点 '{loc_id}' 的 travel_difficulty 必须大于 0")

        # 校验环境效果字段
        valid_env_effect_types = {"frost_slow", "thunder_strike", "water_blessing"}
        for effect in loc.get("environmental_effects", []):
            etype = effect.get("type")
            if etype not in valid_env_effect_types:
                errors.append(
                    f"locations.json: 地点 '{loc_id}' 的环境效果类型 '{etype}' 不合法，"
                    f"应为 {valid_env_effect_types}"
                )
                continue
            if not isinstance(effect.get("chance"), (int, float)):
                errors.append(
                    f"locations.json: 地点 '{loc_id}' 的环境效果 '{etype}' 缺少合法 chance"
                )
            if "value" not in effect:
                errors.append(
                    f"locations.json: 地点 '{loc_id}' 的环境效果 '{etype}' 缺少 value"
                )
            if etype == "frost_slow" and "turns" not in effect:
                errors.append(
                    f"locations.json: 地点 '{loc_id}' 的环境效果 '{etype}' 缺少 turns"
                )
            if etype == "water_blessing" and "element" not in effect:
                errors.append(
                    f"locations.json: 地点 '{loc_id}' 的环境效果 '{etype}' 缺少 element"
                )

        # 校验城池建筑配置
        valid_building_actions = {
            "market", "rest", "arena", "quest",
            "beast_park", "aquatic_shop", "shop", "cave",
        }
        for building in loc.get("buildings", []):
            bid = building.get("id", "<未知>")
            bname = building.get("name", "")
            if not bname:
                errors.append(f"locations.json: 地点 '{loc_id}' 的建筑 '{bid}' 缺少 name")
            action = building.get("action")
            if action is not None and action not in valid_building_actions:
                errors.append(
                    f"locations.json: 地点 '{loc_id}' 的建筑 '{bid}' action '{action}' 不合法，"
                    f"应为 {valid_building_actions}"
                )

        # 校验城池背景图路径（若配置则仅检查格式，不要求图片一定存在）
        bg_image = loc.get("background_image")
        if bg_image is not None:
            if not isinstance(bg_image, str) or not bg_image:
                errors.append(f"locations.json: 地点 '{loc_id}' 的 background_image 必须是有效字符串")
            elif not bg_image.endswith(".png"):
                errors.append(f"locations.json: 地点 '{loc_id}' 的 background_image 应以 .png 结尾")

    # 校验 economy.json 中地点类型是否均已知
    economy = load_json(os.path.join(config_dir, "economy.json"))
    for loc_type in economy.get("location_type_modifiers", {}).keys():
        if loc_type not in valid_location_types:
            errors.append(f"economy.json: 地点类型 '{loc_type}' 未知，应为 {valid_location_types}")

    # 校验 city_maps.json 热点配置
    city_maps_path = os.path.join(config_dir, "city_maps.json")
    if os.path.exists(city_maps_path):
        city_maps = load_json(city_maps_path)
        # 构建地点 ID -> 建筑 ID 集合
        location_building_ids = {}
        for loc in locations:
            loc_id = loc.get("id")
            if loc_id:
                location_building_ids[loc_id] = {
                    b.get("id") for b in loc.get("buildings", []) if b.get("id")
                }

        seen_city_ids = set()
        for cfg in city_maps:
            city_id = cfg.get("city_id")
            if not city_id:
                errors.append("city_maps.json: 存在缺少 city_id 的条目")
                continue
            if city_id in seen_city_ids:
                errors.append(f"city_maps.json: 城市 '{city_id}' 存在重复配置")
            seen_city_ids.add(city_id)
            if city_id not in location_ids:
                errors.append(f"city_maps.json: 城市 '{city_id}' 在 locations.json 中不存在")
                continue

            map_image = cfg.get("map_image")
            if map_image is not None and (not isinstance(map_image, str) or not map_image.endswith(".png")):
                errors.append(f"city_maps.json: 城市 '{city_id}' 的 map_image 应为 .png 路径")

            seen_hotspot_ids = set()
            for hotspot in cfg.get("hotspots", []):
                hid = hotspot.get("id")
                if not hid:
                    errors.append(f"city_maps.json: 城市 '{city_id}' 存在缺少 id 的热点")
                    continue
                if hid in seen_hotspot_ids:
                    errors.append(f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' 重复")
                seen_hotspot_ids.add(hid)
                if hid not in location_building_ids.get(city_id, set()):
                    errors.append(
                        f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' 不是该城市的建筑"
                    )

                shape = hotspot.get("shape", "rect")
                if shape not in ("rect", "circle", "diamond", "polygon"):
                    errors.append(
                        f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' shape '{shape}' 不合法，"
                        f"应为 rect/circle/diamond/polygon"
                    )

                if shape == "polygon":
                    points = hotspot.get("points", [])
                    if not isinstance(points, list) or len(points) < 3:
                        errors.append(
                            f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' polygon 至少需要 3 个点"
                        )
                    else:
                        for point in points:
                            if not isinstance(point, (list, tuple)) or len(point) != 2:
                                errors.append(
                                    f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' points 格式错误"
                                )
                                break
                            for c in point:
                                if not isinstance(c, (int, float)) or not (0.0 <= float(c) <= 1.0):
                                    errors.append(
                                        f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' 多边形坐标 {c} 不在 [0,1] 区间"
                                    )
                                    break

                coords = hotspot.get("coords")
                if not isinstance(coords, list) or len(coords) != 4:
                    errors.append(
                        f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' coords 应为 4 个数值"
                    )
                else:
                    for c in coords:
                        if not isinstance(c, (int, float)) or not (0.0 <= float(c) <= 1.0):
                            errors.append(
                                f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' 坐标 {c} 不在 [0,1] 区间"
                            )
                            break

                # 校验建筑图片路径（若配置）
                image = hotspot.get("image")
                if image is not None:
                    if not isinstance(image, str) or not image:
                        errors.append(
                            f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' image 必须是有效字符串"
                        )
                    elif not image.endswith(".png"):
                        errors.append(
                            f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' image 应以 .png 结尾"
                        )

                image_hover = hotspot.get("image_hover")
                if image_hover is not None:
                    if not isinstance(image_hover, str) or not image_hover:
                        errors.append(
                            f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' image_hover 必须是有效字符串"
                        )
                    elif not image_hover.endswith(".png"):
                        errors.append(
                            f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' image_hover 应以 .png 结尾"
                        )

                # 校验名牌偏移
                nameplate_offset = hotspot.get("nameplate_offset")
                if nameplate_offset is not None:
                    if not isinstance(nameplate_offset, (list, tuple)) or len(nameplate_offset) != 2:
                        errors.append(
                            f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' nameplate_offset 应为两个数值"
                        )
                    else:
                        for off in nameplate_offset:
                            if not isinstance(off, (int, float)):
                                errors.append(
                                    f"city_maps.json: 城市 '{city_id}' 的热点 '{hid}' nameplate_offset 必须是数字"
                                )
                                break

    # 校验 treasure_maps.json 中的 location_hints 地点是否都存在
    treasure_maps = load_json(os.path.join(config_dir, "treasure_maps.json"))
    for loc_id in treasure_maps.get("location_hints", {}).keys():
        if loc_id not in location_ids:
            errors.append(f"treasure_maps.json: location_hints 中的地点 '{loc_id}' 不存在")

    # 校验 secret_realms.json 中的 enemy_pool / boss / rewards 引用
    secret_realms = load_json(os.path.join(config_dir, "secret_realms.json"))
    for realm in secret_realms:
        rid = realm.get("id", "<未知>")
        for eid in realm.get("enemy_pool", []):
            if eid not in enemy_ids:
                errors.append(f"secret_realms.json: 秘境 '{rid}' 的 enemy_pool 敌人 '{eid}' 不存在")
        boss_id = realm.get("boss")
        if boss_id and boss_id not in enemy_ids:
            errors.append(f"secret_realms.json: 秘境 '{rid}' 的 boss '{boss_id}' 不存在")
        for item_id in realm.get("rewards", []):
            if item_id not in item_ids:
                errors.append(f"secret_realms.json: 秘境 '{rid}' 的奖励物品 '{item_id}' 不存在")

    # 校验 residences.json 的结构与跨引用
    valid_residence_types = {"city", "wild"}
    valid_building_ids = {
        "spirit_gathering_array", "herb_garden", "refining_room",
        "defense_formation", "alchemy_room", "smithy",
    }
    valid_building_effect_keys = {
        "cultivation_speed", "water_damage", "refine_bonus",
        "raid_defense", "max_energy", "herb_chance", "herb_id",
        "alchemy_success", "alchemy_quality", "smith_success",
    }
    residences_path = os.path.join(config_dir, "residences.json")
    if os.path.exists(residences_path):
        residences = load_json(residences_path)
        for residence in residences.get("residences", []):
            rid = residence.get("id", "<未知>")
            rtype = residence.get("type")
            if rtype not in valid_residence_types:
                errors.append(
                    f"residences.json: 洞府 '{rid}' 的 type '{rtype}' 不合法，"
                    f"应为 {valid_residence_types}"
                )
            loc_id = residence.get("location_id")
            if loc_id and loc_id not in location_ids:
                errors.append(f"residences.json: 洞府 '{rid}' 的 location_id '{loc_id}' 不存在")
            # 野外洞府必须有 occupation 字段
            if rtype == "wild":
                occupation = residence.get("occupation")
                if not occupation:
                    errors.append(f"residences.json: 野外洞府 '{rid}' 缺少 occupation 字段")
                else:
                    guard_id = occupation.get("guard_enemy_id")
                    if guard_id and guard_id not in enemy_ids:
                        errors.append(
                            f"residences.json: 野外洞府 '{rid}' 的 guard_enemy_id "
                            f"'{guard_id}' 不存在"
                        )
                    required_order = occupation.get("required_realm_order")
                    if required_order is not None and not isinstance(required_order, int):
                        errors.append(
                            f"residences.json: 野外洞府 '{rid}' 的 required_realm_order 必须是整数"
                        )
            # 校验建筑字段
            for building in residence.get("buildings", []):
                bid = building.get("id", "<未知>")
                if bid not in valid_building_ids:
                    errors.append(
                        f"residences.json: 洞府 '{rid}' 建筑 '{bid}' 不在合法建筑列表 "
                        f"{valid_building_ids} 中"
                    )
                if not isinstance(building.get("max_level"), int) or building["max_level"] <= 0:
                    errors.append(
                        f"residences.json: 洞府 '{rid}' 建筑 '{bid}' 的 max_level 必须是正整数"
                    )
                if not isinstance(building.get("base_cost", {}).get("spirit_stone", 0), int):
                    errors.append(
                        f"residences.json: 洞府 '{rid}' 建筑 '{bid}' 的 base_cost.spirit_stone 必须是整数"
                    )
                for effect_key in building.get("effect_per_level", {}).keys():
                    if effect_key not in valid_building_effect_keys:
                        errors.append(
                            f"residences.json: 洞府 '{rid}' 建筑 '{bid}' 的 effect key "
                            f"'{effect_key}' 不合法"
                        )
        # 校验袭击配置
        raid_cfg = residences.get("raid", {})
        for enemy_id in raid_cfg.get("enemy_pool", []):
            if enemy_id not in enemy_ids:
                errors.append(
                    f"residences.json: raid.enemy_pool 中的敌人 '{enemy_id}' 不存在"
                )

    # 校验 world_bosses.json 中的 base_enemy_id / location / loot 引用
    world_bosses = load_json(os.path.join(config_dir, "world_bosses.json"))
    for boss in world_bosses:
        bid = boss.get("id", "<未知>")
        base_id = boss.get("base_enemy_id")
        if base_id and base_id not in enemy_ids:
            errors.append(f"world_bosses.json: BOSS '{bid}' 的 base_enemy_id '{base_id}' 不存在")
        loc_id = boss.get("location")
        if loc_id and loc_id not in location_ids:
            errors.append(f"world_bosses.json: BOSS '{bid}' 的 location '{loc_id}' 不存在")
        for item_id in boss.get("loot", []):
            if item_id not in item_ids:
                errors.append(f"world_bosses.json: BOSS '{bid}' 的 loot 物品 '{item_id}' 不存在")

    # 校验 dialogues.json 结构、节点引用、条件与效果字段
    valid_condition_types = {
        "realm_min", "realm_max", "reputation_min", "quest_active",
        "quest_completed", "has_item", "cultivation_path", "dialogue_flag",
        "npc_choice",
    }
    valid_effect_types = {
        "start_quest", "advance_quest", "complete_quest", "modify_reputation",
        "give_item", "take_item", "set_flag", "teach_skill",
        "change_npc_location", "notify", "record_choice",
    }
    dialogues = load_json(os.path.join(config_dir, "dialogues.json"))
    for dialogue in dialogues:
        did = dialogue.get("id", "<未知>")
        npc_id = dialogue.get("npc_id")
        if npc_id and npc_id not in npc_ids:
            errors.append(f"dialogues.json: 对话 '{did}' 的 npc_id '{npc_id}' 不存在")
        entry = dialogue.get("entry_node")
        nodes = dialogue.get("nodes", {})
        if entry and entry not in nodes:
            errors.append(f"dialogues.json: 对话 '{did}' 的 entry_node '{entry}' 不存在")

        # 收集所有被引用的节点 ID
        referenced_nodes = set()
        for node_id, node in nodes.items():
            for opt in node.get("options", []):
                next_node = opt.get("next_node")
                if next_node:
                    referenced_nodes.add(next_node)
                for cond in opt.get("conditions", []):
                    if cond.get("type") not in valid_condition_types:
                        errors.append(
                            f"dialogues.json: 对话 '{did}' 节点 '{node_id}' 选项条件类型 "
                            f"'{cond.get('type')}' 不合法"
                        )
                for effect in opt.get("effects", []):
                    etype = effect.get("type")
                    if etype not in valid_effect_types:
                        errors.append(
                            f"dialogues.json: 对话 '{did}' 节点 '{node_id}' 选项效果类型 "
                            f"'{etype}' 不合法"
                        )
                    if etype in ("start_quest", "advance_quest", "complete_quest"):
                        qid = effect.get("quest_id")
                        if qid and qid not in quest_ids:
                            errors.append(
                                f"dialogues.json: 对话 '{did}' 节点 '{node_id}' 引用任务 '{qid}' 不存在"
                            )
                    if etype in ("give_item", "take_item"):
                        iid = effect.get("item_id")
                        if iid and iid not in item_ids:
                            errors.append(
                                f"dialogues.json: 对话 '{did}' 节点 '{node_id}' 引用物品 '{iid}' 不存在"
                            )
                    if etype == "teach_skill":
                        sid = effect.get("skill_id")
                        if sid and sid not in skill_ids:
                            errors.append(
                                f"dialogues.json: 对话 '{did}' 节点 '{node_id}' 引用技能 '{sid}' 不存在"
                            )
                    if etype == "change_npc_location":
                        ref_npc = effect.get("npc_id")
                        loc = effect.get("location")
                        if ref_npc and ref_npc not in npc_ids:
                            errors.append(
                                f"dialogues.json: 对话 '{did}' 节点 '{node_id}' 引用 NPC '{ref_npc}' 不存在"
                            )
                        if loc and loc not in location_ids:
                            errors.append(
                                f"dialogues.json: 对话 '{did}' 节点 '{node_id}' 引用地点 '{loc}' 不存在"
                            )

        for ref in referenced_nodes:
            if ref not in nodes:
                errors.append(f"dialogues.json: 对话 '{did}' 的 next_node '{ref}' 不存在")

    return errors


def validate_feature_flags(config_dir):
    """校验 config/feature_flags.json 结构。文件不存在则跳过。"""
    errors = []
    path = os.path.join(config_dir, "feature_flags.json")
    if not os.path.exists(path):
        return errors
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        return [f"feature_flags.json JSON 解析失败：{e}"]

    flags = data.get("flags", data) if isinstance(data, dict) else None
    if not isinstance(flags, dict):
        errors.append("feature_flags.json 顶层应为对象，或包含 'flags' 对象")
        return errors
    for flag, val in flags.items():
        if not isinstance(flag, str):
            errors.append(f"feature_flags.json 的开关名应为字符串：{flag!r}")
        if not isinstance(val, bool):
            errors.append(
                f"feature_flags.json 开关 '{flag}' 的值应为布尔类型：{val!r}"
            )
    return errors


def validate_world_event_chains(config_dir):
    """校验 config/world/world_event_chains.json 的事件链结构。文件不存在则跳过。"""
    errors = []
    path = os.path.join(config_dir, "world", "world_event_chains.json")
    if not os.path.exists(path):
        return errors
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        return [f"world_event_chains.json JSON 解析失败：{e}"]

    chains = data.get("chains", []) if isinstance(data, dict) else []
    if not isinstance(chains, list):
        errors.append("world_event_chains.json 顶层应包含 chains 数组")
        return errors
    seen_ids = set()
    for chain in chains:
        cid = chain.get("id", "<未知>")
        if cid in seen_ids:
            errors.append(f"world_event_chains.json 事件链 id 重复：{cid}")
        seen_ids.add(cid)
        stages = chain.get("stages")
        if not isinstance(stages, dict) or "1" not in stages:
            errors.append(f"world_event_chains.json 链 '{cid}' 须有 stages 且含起始阶段 '1'")
            continue
        for sid, stage in stages.items():
            if "name" not in stage:
                errors.append(f"world_event_chains.json 链 '{cid}' 阶段 '{sid}' 缺少 name")
            if "duration_months" not in stage:
                errors.append(f"world_event_chains.json 链 '{cid}' 阶段 '{sid}' 缺少 duration_months")
            has_choices = bool(stage.get("player_choices"))
            has_auto = bool(stage.get("auto_next"))
            is_ending = bool(stage.get("ending"))
            # 阶段结束条件应互斥且至少满足其一
            if not (has_choices or has_auto or is_ending):
                errors.append(
                    f"world_event_chains.json 链 '{cid}' 阶段 '{sid}' 需有 "
                    f"player_choices / auto_next / ending 之一"
                )
            if has_choices:
                for i, c in enumerate(stage["player_choices"]):
                    if "next_stage" not in c:
                        errors.append(
                            f"world_event_chains.json 链 '{cid}' 阶段 '{sid}' 选项 {i} 缺少 next_stage"
                        )
                    elif c["next_stage"] not in stages:
                        errors.append(
                            f"world_event_chains.json 链 '{cid}' 阶段 '{sid}' 选项指向不存在的阶段 "
                            f"'{c['next_stage']}'"
                        )
            if has_auto and stage["auto_next"] not in stages:
                errors.append(
                    f"world_event_chains.json 链 '{cid}' 阶段 '{sid}' 的 auto_next "
                    f"'{stage['auto_next']}' 不存在"
                )
    return errors


def validate_secret_realm(config_dir):
    """校验 config/secret_realm/ 下 Roguelike 秘境（F-03）相关配置。目录不存在则跳过。"""
    errors = []
    sr_dir = os.path.join(config_dir, "secret_realm")
    if not os.path.isdir(sr_dir):
        return errors

    # 1. 增益卡
    cards_path = os.path.join(sr_dir, "realm_cards.json")
    if os.path.exists(cards_path):
        try:
            cards = load_json(cards_path)
        except json.JSONDecodeError as e:
            errors.append(f"realm_cards.json JSON 解析失败：{e}")
            cards = []
        if not isinstance(cards, list):
            errors.append("realm_cards.json 顶层应为数组")
        else:
            seen = set()
            for c in cards:
                cid = c.get("id", "<未知>")
                if cid in seen:
                    errors.append(f"realm_cards.json 卡 id 重复：{cid}")
                seen.add(cid)
                if "name" not in c:
                    errors.append(f"realm_cards.json 卡 '{cid}' 缺少 name")
                if "effect" not in c or not isinstance(c.get("effect"), dict):
                    errors.append(f"realm_cards.json 卡 '{cid}' 缺少 effect 对象")
                if c.get("stackable") and not isinstance(c.get("max_stack"), int):
                    errors.append(f"realm_cards.json 卡 '{cid}' 可叠加但缺少整数 max_stack")

    # 2. 楼层模板
    floors_path = os.path.join(sr_dir, "realm_floors.json")
    if os.path.exists(floors_path):
        try:
            floors = load_json(floors_path)
        except json.JSONDecodeError as e:
            errors.append(f"realm_floors.json JSON 解析失败：{e}")
            floors = {}
        if not isinstance(floors, dict) or "floor_templates" not in floors:
            errors.append("realm_floors.json 顶层应为含 floor_templates 的对象")
        else:
            for i, t in enumerate(floors["floor_templates"]):
                if "floor_range" not in t or "node_count" not in t or "node_weights" not in t:
                    errors.append(f"realm_floors.json floor_templates[{i}] 缺少必要字段")
                if "boss" not in t.get("node_weights", {}) and isinstance(t.get("node_weights"), dict):
                    errors.append(f"realm_floors.json floor_templates[{i}].node_weights 缺少 boss 权重")

    # 3. 难度
    diff_path = os.path.join(sr_dir, "realm_difficulty.json")
    if os.path.exists(diff_path):
        try:
            diffs = load_json(diff_path)
        except json.JSONDecodeError as e:
            errors.append(f"realm_difficulty.json JSON 解析失败：{e}")
            diffs = []
        if not isinstance(diffs, list):
            errors.append("realm_difficulty.json 顶层应为数组")
        else:
            seen = set()
            for d in diffs:
                did = d.get("id", "<未知>")
                if did in seen:
                    errors.append(f"realm_difficulty.json 难度 id 重复：{did}")
                seen.add(did)
                mods = d.get("modifiers", {})
                if not isinstance(mods, dict):
                    errors.append(f"realm_difficulty.json 难度 '{did}' 的 modifiers 应为对象")
                elif "enemy_strength" not in mods or "reward_mult" not in mods:
                    errors.append(f"realm_difficulty.json 难度 '{did}' 的 modifiers 缺少 enemy_strength/reward_mult")

    # 4. 事件
    ev_path = os.path.join(sr_dir, "realm_events.json")
    if os.path.exists(ev_path):
        try:
            ev = load_json(ev_path)
        except json.JSONDecodeError as e:
            errors.append(f"realm_events.json JSON 解析失败：{e}")
            ev = {}
        events = ev.get("events", []) if isinstance(ev, dict) else []
        seen = set()
        for e in events:
            eid = e.get("id", "<未知>")
            if eid in seen:
                errors.append(f"realm_events.json 事件 id 重复：{eid}")
            seen.add(eid)
            if "choices" not in e or not isinstance(e.get("choices"), list):
                errors.append(f"realm_events.json 事件 '{eid}' 缺少 choices 数组")

    # 5. 兑换
    ex_path = os.path.join(sr_dir, "realm_exchange.json")
    if os.path.exists(ex_path):
        try:
            ex = load_json(ex_path)
        except json.JSONDecodeError as e:
            errors.append(f"realm_exchange.json JSON 解析失败：{e}")
            ex = {}
        items = ex.get("exchange", []) if isinstance(ex, dict) else []
        for it in items:
            if "id" not in it:
                errors.append("realm_exchange.json 兑换项缺少 id")
            if not isinstance(it.get("cost"), int):
                errors.append(f"realm_exchange.json 兑换项 '{it.get('id')}' 的 cost 必须是整数")

    return errors


def validate_all(config_dir):
    """执行全部校验，返回错误列表。"""
    errors = []

    json_files = [
        f for f in os.listdir(config_dir)
        if f.endswith(".json") and os.path.isfile(os.path.join(config_dir, f))
    ]

    # 1. JSON 合法性与 id 唯一性
    for filename in json_files:
        path = os.path.join(config_dir, filename)
        try:
            load_json(path)
        except json.JSONDecodeError as e:
            errors.append(f"{filename} JSON 解析失败：{e}")
            continue
        errors.extend(check_unique_ids(config_dir, filename))

    # 2. 跨文件引用
    try:
        errors.extend(validate_references(config_dir))
    except Exception as e:
        errors.append(f"跨文件引用校验异常：{e}")

    # 3. 功能开关配置
    try:
        errors.extend(validate_feature_flags(config_dir))
    except Exception as e:
        errors.append(f"功能开关校验异常：{e}")

    # 4. 事件链配置
    try:
        errors.extend(validate_world_event_chains(config_dir))
    except Exception as e:
        errors.append(f"事件链校验异常：{e}")

    # 4. Roguelike 秘境配置
    try:
        errors.extend(validate_secret_realm(config_dir))
    except Exception as e:
        errors.append(f"秘境配置校验异常：{e}")

    # 5. 修仙家族配置（F-01）
    try:
        errors.extend(validate_family(config_dir))
    except Exception as e:
        errors.append(f"家族配置校验异常：{e}")

    # 6. 领地建设配置（F-02）
    try:
        errors.extend(validate_territory(config_dir))
    except Exception as e:
        errors.append(f"领地配置校验异常：{e}")

    # 7. 成就分级 / 难度配置（F-06）
    try:
        errors.extend(validate_achievement(config_dir))
    except Exception as e:
        errors.append(f"成就配置校验异常：{e}")
    try:
        errors.extend(validate_difficulty(config_dir))
    except Exception as e:
        errors.append(f"难度配置校验异常：{e}")

    # 8. 多周目模式配置（F-07）
    try:
        errors.extend(validate_meta(config_dir))
    except Exception as e:
        errors.append(f"多周目配置校验异常：{e}")

    # 9. 心魔·道心配置（维度①）
    try:
        errors.extend(validate_mental_state(config_dir))
    except Exception as e:
        errors.append(f"心魔·道心配置校验异常：{e}")

    # 10. 天道反噬与生态平衡配置（维度④）
    try:
        errors.extend(validate_heaven_retribution(config_dir))
    except Exception as e:
        errors.append(f"天道反噬配置校验异常：{e}")

    # 11. 寿元与轮回晚年配置（维度⑤）
    try:
        errors.extend(validate_lifespan(config_dir))
    except Exception as e:
        errors.append(f"寿元·轮回配置校验异常：{e}")

    # 12. 红尘炼心 / 入世配置（维度②）
    try:
        errors.extend(validate_red_dust(config_dir))
    except Exception as e:
        errors.append(f"红尘炼心配置校验异常：{e}")

    # 13. 百家争鸣 / 非传统修仙路线配置（维度③）
    try:
        errors.extend(validate_hundred_schools(config_dir))
    except Exception as e:
        errors.append(f"百家争鸣配置校验异常：{e}")

    # 14. 物品 effects 合法性（含维度③·M18 丹道「灵力温养」持续增益）
    try:
        errors.extend(validate_item_effects(config_dir))
    except Exception as e:
        errors.append(f"物品 effects 校验异常：{e}")

    return errors


def validate_item_effects(config_dir):
    """校验 config/items.json 物品 effects（维度③·M18 丹道灵力温养）。"""
    errors = []
    path = os.path.join(config_dir, "items.json")
    if not os.path.exists(path):
        return errors
    try:
        items = load_json(path)
    except json.JSONDecodeError as e:
        errors.append(f"items.json JSON 解析失败：{e}")
        return errors
    if not isinstance(items, list):
        errors.append("items.json 顶层应为数组")
        return errors
    for it in items:
        eff = it.get("effects")
        if not eff:
            continue
        cb = eff.get("cultivation_boost")
        if cb is None:
            continue
        if not isinstance(cb, dict):
            errors.append(
                f"items.json 物品 '{it.get('id')}' effects.cultivation_boost 应为对象"
            )
            continue
        amt = cb.get("amount")
        mos = cb.get("months")
        if not isinstance(amt, int) or amt <= 0:
            errors.append(
                f"items.json 物品 '{it.get('id')}' cultivation_boost.amount 应为正整数"
            )
        if not isinstance(mos, int) or mos <= 0:
            errors.append(
                f"items.json 物品 '{it.get('id')}' cultivation_boost.months 应为正整数"
            )
    return errors


def validate_achievement(config_dir):
    """校验 config/achievement/achievements_v2.json（F-06 分级/隐藏成就）。"""
    errors = []
    path = os.path.join(config_dir, "achievement", "achievements_v2.json")
    if not os.path.exists(path):
        return errors
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        errors.append(f"achievements_v2.json JSON 解析失败：{e}")
        return errors
    if not isinstance(data, list):
        errors.append("achievements_v2.json 顶层应为数组")
        return errors

    known_types = {
        "kill", "realm", "item_total", "companion", "sect_rank",
        "skill_learn", "quest_complete", "win",
    }
    seen = set()
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            errors.append(f"achievements_v2[{i}] 应为对象")
            continue
        aid = entry.get("id")
        if not aid:
            errors.append(f"achievements_v2[{i}] 缺少 id")
        elif aid in seen:
            errors.append(f"成就 id 重复：{aid}")
        else:
            seen.add(aid)
        cond = entry.get("condition", {})
        if not isinstance(cond, dict) or cond.get("type") not in known_types:
            errors.append(f"成就 {aid} 的 condition.type 非法或缺失")
        if entry.get("hidden") and not isinstance(entry.get("hidden"), bool):
            errors.append(f"成就 {aid} 的 hidden 应为布尔")
        reward = entry.get("reward", {})
        if not isinstance(reward, dict):
            errors.append(f"成就 {aid} 的 reward 应为对象")
    return errors


def validate_difficulty(config_dir):
    """校验 config/difficulty/difficulty_settings.json（F-06 难度系统）。"""
    errors = []
    path = os.path.join(config_dir, "difficulty", "difficulty_settings.json")
    if not os.path.exists(path):
        return errors
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        errors.append(f"difficulty_settings.json JSON 解析失败：{e}")
        return errors
    if not isinstance(data, dict):
        errors.append("difficulty_settings.json 顶层应为对象")
        return errors
    default = data.get("default")
    diffs = data.get("difficulties", [])
    if not isinstance(diffs, list) or not diffs:
        errors.append("difficulty_settings.json difficulties 应为非空数组")
        return errors
    valid_keys = {
        "enemy_strength", "player_combat", "production_mult",
        "exp_mult", "drop_mult",
    }
    ids = set()
    for i, d in enumerate(diffs):
        if not isinstance(d, dict) or not d.get("id"):
            errors.append(f"difficulties[{i}] 缺少 id")
            continue
        if d["id"] in ids:
            errors.append(f"难度 id 重复：{d['id']}")
        ids.add(d["id"])
        mods = d.get("modifiers", {})
        for k in mods:
            if k not in valid_keys:
                errors.append(f"难度 {d['id']} 的修正项 {k} 未识别")
    if default and default not in ids:
        errors.append(f"默认难度 {default} 不存在于 difficulties")
    return errors


def validate_meta(config_dir):
    """校验 config/meta/new_game_modes.json（F-07 多周目模式）。"""
    errors = []
    path = os.path.join(config_dir, "meta", "new_game_modes.json")
    if not os.path.exists(path):
        return errors
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        errors.append(f"new_game_modes.json JSON 解析失败：{e}")
        return errors
    if not isinstance(data, dict):
        errors.append("new_game_modes.json 顶层应为对象")
        return errors
    modes = data.get("modes", [])
    if not isinstance(modes, list) or not modes:
        errors.append("new_game_modes.json modes 应为非空数组")
        return errors
    valid_requires = {"reincarnation_count_min", "has_won"}
    ids = set()
    for i, m in enumerate(modes):
        if not isinstance(m, dict) or not m.get("id"):
            errors.append(f"modes[{i}] 缺少 id")
            continue
        if m["id"] in ids:
            errors.append(f"模式 id 重复：{m['id']}")
        ids.add(m["id"])
        req = m.get("require", {})
        if not isinstance(req, dict):
            errors.append(f"模式 {m['id']} 的 require 应为对象")
        else:
            for k in req:
                if k not in valid_requires:
                    errors.append(f"模式 {m['id']} 的 require.{k} 未识别")
    if "standard" not in ids:
        errors.append("多周目模式缺少 standard（正统求道）基准模式")
    return errors


def validate_family(config_dir):
    """校验 config/family/ 下修仙家族（F-01）相关配置。目录不存在则跳过。"""
    errors = []
    fam_dir = os.path.join(config_dir, "family")
    if not os.path.isdir(fam_dir):
        return errors

    def _load(name):
        path = os.path.join(fam_dir, name)
        if not os.path.exists(path):
            return None
        try:
            return load_json(path)
        except json.JSONDecodeError as e:
            errors.append(f"{name} JSON 解析失败：{e}")
            return None

    # 1. 成员模板
    data = _load("family_members.json")
    if isinstance(data, dict):
        tmpls = data.get("member_templates", [])
        if not isinstance(tmpls, list):
            errors.append("family_members.json member_templates 应为数组")
        else:
            seen = set()
            for t in tmpls:
                tid = t.get("id", "<未知>")
                if tid in seen:
                    errors.append(f"family_members.json 成员模板 id 重复：{tid}")
                seen.add(tid)
                if not isinstance(t.get("name_pool"), list) or not t.get("name_pool"):
                    errors.append(f"family_members.json 模板 '{tid}' 缺少非空 name_pool")
                if not isinstance(t.get("aptitude_range"), (list, tuple)) or len(t.get("aptitude_range", [])) != 2:
                    errors.append(f"family_members.json 模板 '{tid}' 的 aptitude_range 应为长度 2 的数组")

    # 2. 建筑
    data = _load("family_buildings.json")
    if isinstance(data, dict):
        blds = data.get("buildings", [])
        if not isinstance(blds, list):
            errors.append("family_buildings.json buildings 应为数组")
        else:
            seen = set()
            for b in blds:
                bid = b.get("id", "<未知>")
                if bid in seen:
                    errors.append(f"family_buildings.json 建筑 id 重复：{bid}")
                seen.add(bid)
                if not isinstance(b.get("base_cost"), dict):
                    errors.append(f"family_buildings.json 建筑 '{bid}' 缺少 base_cost 对象")
                if not isinstance(b.get("maintenance"), (int, float)):
                    errors.append(f"family_buildings.json 建筑 '{bid}' 缺少数值 maintenance")

    # 3. 事件
    data = _load("family_events.json")
    if isinstance(data, dict):
        evs = data.get("events", [])
        if not isinstance(evs, list):
            errors.append("family_events.json events 应为数组")
        else:
            seen = set()
            for e in evs:
                eid = e.get("id", "<未知>")
                if eid in seen:
                    errors.append(f"family_events.json 事件 id 重复：{eid}")
                seen.add(eid)
                if not isinstance(e.get("choices"), list) or not e.get("choices"):
                    errors.append(f"family_events.json 事件 '{eid}' 缺少 choices 数组")
                for i, c in enumerate(e.get("choices", [])):
                    if "text" not in c or "effect" not in c:
                        errors.append(f"family_events.json 事件 '{eid}' 选项[{i}] 缺少 text/effect")

    # 4. 名称/阵营
    data = _load("family_names.json")
    if isinstance(data, dict):
        if not isinstance(data.get("faction_options"), list):
            errors.append("family_names.json faction_options 应为数组")

    # 5. 其他家族（外交目标）
    data = _load("other_families.json")
    if isinstance(data, dict):
        if not isinstance(data.get("other_families"), list):
            errors.append("other_families.json other_families 应为数组")

    return errors


def validate_territory(config_dir):
    """校验 config/territory/ 下领地建设（F-02）相关配置。目录不存在则跳过。"""
    errors = []
    ter_dir = os.path.join(config_dir, "territory")
    if not os.path.isdir(ter_dir):
        return errors

    def _load(name):
        path = os.path.join(ter_dir, name)
        if not os.path.exists(path):
            return None
        try:
            return load_json(path)
        except json.JSONDecodeError as e:
            errors.append(f"{name} JSON 解析失败：{e}")
            return None

    valid_categories = {"production", "economy", "defense", "formation"}

    # 1. 品阶与可占领地图
    data = _load("territory_maps.json")
    if isinstance(data, dict):
        tiers = data.get("tiers", [])
        if not isinstance(tiers, list):
            errors.append("territory_maps.json tiers 应为数组")
        else:
            seen = set()
            for t in tiers:
                tid = t.get("id", "<未知>")
                if tid in seen:
                    errors.append(f"territory_maps.json 品阶 id 重复：{tid}")
                seen.add(tid)
                grid = t.get("grid")
                if not isinstance(grid, (list, tuple)) or len(grid) != 2:
                    errors.append(f"territory_maps.json 品阶 '{tid}' 的 grid 应为长度 2 的数组")
                if not isinstance(t.get("max_energy"), int):
                    errors.append(f"territory_maps.json 品阶 '{tid}' 的 max_energy 应为整数")
                up = t.get("upgrade_cost")
                if up is not None and not isinstance(up.get("spirit_stone"), int):
                    errors.append(f"territory_maps.json 品阶 '{tid}' 的 upgrade_cost.spirit_stone 应为整数")

        maps = data.get("maps", [])
        if not isinstance(maps, list):
            errors.append("territory_maps.json maps 应为数组")
        else:
            seen = set()
            for m in maps:
                mid = m.get("id", "<未知>")
                if mid in seen:
                    errors.append(f"territory_maps.json 地图 id 重复：{mid}")
                seen.add(mid)
                if not isinstance(m.get("name"), str) or not m.get("name"):
                    errors.append(f"territory_maps.json 地图 '{mid}' 缺少 name")
                if not isinstance(m.get("tier"), str):
                    errors.append(f"territory_maps.json 地图 '{mid}' 的 tier 应为字符串")
                if not isinstance(m.get("required_realm_order"), int):
                    errors.append(f"territory_maps.json 地图 '{mid}' 的 required_realm_order 应为整数")
                cc = m.get("claim_cost")
                if not isinstance(cc, dict) or not isinstance(cc.get("spirit_stone"), int):
                    errors.append(f"territory_maps.json 地图 '{mid}' 的 claim_cost.spirit_stone 应为整数")

    # 2. 建筑
    data = _load("buildings.json")
    if isinstance(data, dict):
        blds = data.get("buildings", [])
        if not isinstance(blds, list):
            errors.append("buildings.json buildings 应为数组")
        else:
            seen = set()
            for b in blds:
                bid = b.get("id", "<未知>")
                if bid in seen:
                    errors.append(f"buildings.json 建筑 id 重复：{bid}")
                seen.add(bid)
                if not isinstance(b.get("name"), str) or not b.get("name"):
                    errors.append(f"buildings.json 建筑 '{bid}' 缺少 name")
                if b.get("category") not in valid_categories:
                    errors.append(
                        f"buildings.json 建筑 '{bid}' 的 category 不合法，"
                        f"应为 {valid_categories}"
                    )
                if not isinstance(b.get("base_cost"), dict):
                    errors.append(f"buildings.json 建筑 '{bid}' 缺少 base_cost 对象")
                elif not isinstance(b["base_cost"].get("spirit_stone"), int):
                    errors.append(f"buildings.json 建筑 '{bid}' 的 base_cost.spirit_stone 应为整数")
                if not isinstance(b.get("max_level"), int) or b.get("max_level") <= 0:
                    errors.append(f"buildings.json 建筑 '{bid}' 的 max_level 应为正整数")
                if not isinstance(b.get("effect_per_level"), dict):
                    errors.append(f"buildings.json 建筑 '{bid}' 的 effect_per_level 应为对象")

    return errors


def validate_mental_state(config_dir):
    """校验 config/mental_state.json（维度① 心魔·道心系统）。

    覆盖：违戒心魔、重大挫折、游历道心、心魔劫幻境、天人合一顿悟。
    文件不存在则跳过（系统可由 feature_flags.heart_demon 关闭）。
    """
    errors = []
    path = os.path.join(config_dir, "mental_state.json")
    if not os.path.exists(path):
        return errors
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        errors.append(f"mental_state.json JSON 解析失败：{e}")
        return errors
    if not isinstance(data, dict):
        errors.append("mental_state.json 顶层应为对象")
        return errors

    # 1. 月度自然变化
    mc = data.get("monthly_changes", {})
    if not isinstance(mc, dict):
        errors.append("mental_state.json monthly_changes 应为对象")

    # 2. 违戒（正道修魔功）
    pv = data.get("precept_violations", {})
    if not isinstance(pv, dict):
        errors.append("mental_state.json precept_violations 应为对象")
    else:
        if not isinstance(pv.get("demonic_paths"), list):
            errors.append("mental_state.json precept_violations.demonic_paths 应为数组")
        if not isinstance(pv.get("demonic_skill_ids"), list):
            errors.append("mental_state.json precept_violations.demonic_skill_ids 应为数组")
        if not isinstance(pv.get("heart_demon_delta"), int):
            errors.append("mental_state.json precept_violations.heart_demon_delta 应为整数")
        if not isinstance(pv.get("mental_state_delta"), int):
            errors.append("mental_state.json precept_violations.mental_state_delta 应为整数")

    # 3. 重大挫折
    ms = data.get("major_setbacks", {})
    if not isinstance(ms, dict):
        errors.append("mental_state.json major_setbacks 应为对象")
    else:
        for sid, scfg in ms.items():
            if sid.startswith("_"):  # 跳过 _comment 等元信息键
                continue
            if not isinstance(scfg, dict):
                errors.append(f"mental_state.json major_setbacks.{sid} 应为对象")
                continue
            if "heart_demon_delta" not in scfg or not isinstance(scfg.get("heart_demon_delta"), int):
                errors.append(f"mental_state.json major_setbacks.{sid}.heart_demon_delta 应为整数")
            if "mental_state_delta" not in scfg or not isinstance(scfg.get("mental_state_delta"), int):
                errors.append(f"mental_state.json major_setbacks.{sid}.mental_state_delta 应为整数")

    # 4. 游历道心
    td = data.get("travel_dao_heart", {})
    if not isinstance(td, dict):
        errors.append("mental_state.json travel_dao_heart 应为对象")
    else:
        if not isinstance(td.get("famous_location_ids"), list):
            errors.append("mental_state.json travel_dao_heart.famous_location_ids 应为数组")
        if not isinstance(td.get("famous_gain"), int):
            errors.append("mental_state.json travel_dao_heart.famous_gain 应为整数")
        if not isinstance(td.get("normal_gain"), int):
            errors.append("mental_state.json travel_dao_heart.normal_gain 应为整数")

    # 5. 心魔劫幻境
    hdt = data.get("heart_demon_tribulation", {})
    if not isinstance(hdt, dict):
        errors.append("mental_state.json heart_demon_tribulation 应为对象")
    else:
        threshold = hdt.get("threshold")
        if not isinstance(threshold, int) or not (0 <= threshold <= 100):
            errors.append("mental_state.json heart_demon_tribulation.threshold 应为 0-100 的整数")
        scenarios = hdt.get("scenarios", [])
        if not isinstance(scenarios, list) or not scenarios:
            errors.append("mental_state.json heart_demon_tribulation.scenarios 应为非空数组")
        else:
            seen = set()
            for s in scenarios:
                sid = s.get("id", "<未知>")
                if sid in seen:
                    errors.append(f"mental_state.json 心魔劫场景 id 重复：{sid}")
                seen.add(sid)
                if not isinstance(s.get("name"), str) or not s.get("name"):
                    errors.append(f"mental_state.json 心魔劫场景 '{sid}' 缺少 name")
                if not isinstance(s.get("description"), str):
                    errors.append(f"mental_state.json 心魔劫场景 '{sid}' 缺少 description")
                choices = s.get("choices", [])
                if not isinstance(choices, list) or not choices:
                    errors.append(f"mental_state.json 心魔劫场景 '{sid}' 缺少 choices 数组")
                    continue
                for c in choices:
                    if not isinstance(c.get("id"), str):
                        errors.append(f"mental_state.json 心魔劫场景 '{sid}' 选项缺少 id")
                    if not isinstance(c.get("text"), str):
                        errors.append(f"mental_state.json 心魔劫场景 '{sid}' 选项缺少 text")
                    if not isinstance(c.get("result_text"), str):
                        errors.append(f"mental_state.json 心魔劫场景 '{sid}' 选项缺少 result_text")
                    eff = c.get("effects", {})
                    if not isinstance(eff, dict):
                        errors.append(f"mental_state.json 心魔劫场景 '{sid}' 选项 effects 应为对象")
                    else:
                        if "heart_demon_delta" in eff and not isinstance(eff["heart_demon_delta"], int):
                            errors.append(f"mental_state.json 心魔劫场景 '{sid}' 选项 effects.heart_demon_delta 应为整数")
                        if "mental_state_delta" in eff and not isinstance(eff["mental_state_delta"], int):
                            errors.append(f"mental_state.json 心魔劫场景 '{sid}' 选项 effects.mental_state_delta 应为整数")
                        mod = eff.get("subsequent_modifier")
                        if mod is not None:
                            if not isinstance(mod, dict) or "key" not in mod or "delta" not in mod:
                                errors.append(f"mental_state.json 心魔劫场景 '{sid}' 选项 subsequent_modifier 需含 key/delta")

    # 6. 天人合一顿悟
    ue = data.get("unity_enlightenment", {})
    if not isinstance(ue, dict):
        errors.append("mental_state.json unity_enlightenment 应为对象")
    else:
        if not isinstance(ue.get("min_mental_state"), int):
            errors.append("mental_state.json unity_enlightenment.min_mental_state 应为整数")
        if not isinstance(ue.get("chance_per_month"), (int, float)) or not (0 <= ue.get("chance_per_month", -1) <= 1):
            errors.append("mental_state.json unity_enlightenment.chance_per_month 应在 [0, 1]")
        if not isinstance(ue.get("qi_multiplier"), (int, float)) or ue.get("qi_multiplier", 0) <= 0:
            errors.append("mental_state.json unity_enlightenment.qi_multiplier 应为正数")
        if not isinstance(ue.get("technique_chance"), (int, float)) or not (0 <= ue.get("technique_chance", -1) <= 1):
            errors.append("mental_state.json unity_enlightenment.technique_chance 应在 [0, 1]")

    # 7. 心境等级与道境被动
    levels = data.get("mental_state_levels")
    if levels is not None:
        if not isinstance(levels, list) or not levels:
            errors.append("mental_state.json mental_state_levels 应为非空数组")
        else:
            for idx, lv in enumerate(levels):
                if not isinstance(lv, dict):
                    errors.append(f"mental_state.json mental_state_levels[{idx}] 应为对象")
                    continue
                if "min" not in lv or not isinstance(lv.get("min"), int):
                    errors.append(f"mental_state.json mental_state_levels[{idx}].min 应为整数")
                if not isinstance(lv.get("name"), str) or not lv.get("name"):
                    errors.append(f"mental_state.json mental_state_levels[{idx}].name 应为非空字符串")
                passive = lv.get("passive")
                if passive is not None:
                    if not isinstance(passive, dict):
                        errors.append(f"mental_state.json mental_state_levels[{idx}].passive 应为对象")
                    else:
                        allowed = {
                            "name", "desc",
                            "heart_demon_event_immunity",
                            "unity_enlightenment_chance_mult",
                            "breakthrough_failure_mental_protect",
                            "dao_heart_gain_mult",
                        }
                        for k in passive:
                            if k not in allowed:
                                errors.append(
                                    f"mental_state.json mental_state_levels[{idx}].passive 含未知键：{k}"
                                )
                        if "name" not in passive or not isinstance(passive.get("name"), str):
                            errors.append(f"mental_state.json mental_state_levels[{idx}].passive.name 应为字符串")
                        if "desc" not in passive or not isinstance(passive.get("desc"), str):
                            errors.append(f"mental_state.json mental_state_levels[{idx}].passive.desc 应为字符串")
                        for mk in ("unity_enlightenment_chance_mult", "dao_heart_gain_mult"):
                            v = passive.get(mk)
                            if v is not None and (not isinstance(v, (int, float)) or v <= 0):
                                errors.append(
                                    f"mental_state.json mental_state_levels[{idx}].passive.{mk} 应为正数"
                                )
                        for bk in ("heart_demon_event_immunity", "breakthrough_failure_mental_protect"):
                            v = passive.get(bk)
                            if v is not None and not isinstance(v, bool):
                                errors.append(
                                    f"mental_state.json mental_state_levels[{idx}].passive.{bk} 应为布尔值"
                                )

    return errors


def validate_heaven_retribution(config_dir):
    """校验 config/heaven_retribution.json（维度④ 天道反噬与生态平衡）。"""
    errors = []
    path = os.path.join(config_dir, "heaven_retribution.json")
    if not os.path.exists(path):
        return errors
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        errors.append(f"heaven_retribution.json JSON 解析失败：{e}")
        return errors
    if not isinstance(data, dict):
        errors.append("heaven_retribution.json 顶层应为对象")
        return errors

    # 1. 灵脉枯竭
    sd = data.get("spirit_vein_depletion", {})
    if not isinstance(sd, dict):
        errors.append("heaven_retribution.json spirit_vein_depletion 应为对象")
    else:
        if not isinstance(sd.get("extraction_keys"), list):
            errors.append("heaven_retribution.json spirit_vein_depletion.extraction_keys 应为数组")
        if not isinstance(sd.get("tier_capacity"), dict):
            errors.append("heaven_retribution.json spirit_vein_depletion.tier_capacity 应为对象")
        for k in ("gain_per_excess_unit", "recover_per_month", "output_multiplier_at_full", "monster_chance_at_full"):
            if not isinstance(sd.get(k), (int, float)):
                errors.append(f"heaven_retribution.json spirit_vein_depletion.{k} 应为数字")

    # 2. 天道注视
    hg = data.get("heaven_gaze", {})
    if not isinstance(hg, dict):
        errors.append("heaven_retribution.json heaven_gaze 应为对象")
    else:
        for k in ("power_spike_min", "wealth_spike_multiplier", "gaze_per_spike", "decay_per_month", "max"):
            if not isinstance(hg.get(k), (int, float)):
                errors.append(f"heaven_retribution.json heaven_gaze.{k} 应为数字")
        levels = hg.get("levels", {})
        if not isinstance(levels, dict) or not levels:
            errors.append("heaven_retribution.json heaven_gaze.levels 应为非空对象")
        else:
            for lvl, spec in levels.items():
                if not isinstance(spec, dict):
                    errors.append(f"heaven_retribution.json heaven_gaze.levels.{lvl} 应为对象")
                    continue
                if not isinstance(spec.get("threshold"), (int, float)):
                    errors.append(f"heaven_retribution.json heaven_gaze.levels.{lvl}.threshold 应为数字")
                for m in ("misfortune", "kill_for_treasure", "trade_refuse"):
                    if not isinstance(spec.get(m), (int, float)) or not (0 <= spec.get(m, -1) <= 1):
                        errors.append(f"heaven_retribution.json heaven_gaze.levels.{lvl}.{m} 应在 [0,1]")
        relief = hg.get("relief", {})
        if not isinstance(relief, dict):
            errors.append("heaven_retribution.json heaven_gaze.relief 应为对象")
        for lvl, spec in levels.items():
            if not isinstance(spec, dict):
                continue
            rc = spec.get("retribution_event_chance")
            if rc is not None and (not isinstance(rc, (int, float)) or not (0 <= rc <= 1)):
                errors.append(
                    f"heaven_retribution.json heaven_gaze.levels.{lvl}.retribution_event_chance 应在 [0,1]"
                )

    # 3. 天道反噬事件池
    events = data.get("retribution_events", [])
    if events is not None and not isinstance(events, list):
        errors.append("heaven_retribution.json retribution_events 应为数组（可空）")
    else:
        seen_ids = set()
        for i, ev in enumerate(events):
            if not isinstance(ev, dict):
                errors.append(f"heaven_retribution.json retribution_events[{i}] 应为对象")
                continue
            eid = ev.get("id")
            if not isinstance(eid, str):
                errors.append(f"heaven_retribution.json retribution_events[{i}].id 应为字符串")
            elif eid in seen_ids:
                errors.append(f"heaven_retribution.json retribution_events id 重复：{eid}")
            else:
                seen_ids.add(eid)
            for k in ("name", "desc"):
                if not isinstance(ev.get(k), str):
                    errors.append(f"heaven_retribution.json retribution_events[{i}].{k} 应为字符串")
            if not isinstance(ev.get("min_gaze"), int):
                errors.append(f"heaven_retribution.json retribution_events[{i}].min_gaze 应为整数")
            w = ev.get("weight")
            if not isinstance(w, (int, float)) or w <= 0:
                errors.append(f"heaven_retribution.json retribution_events[{i}].weight 应为正数")
            eff = ev.get("effects", {})
            if not isinstance(eff, dict):
                errors.append(f"heaven_retribution.json retribution_events[{i}].effects 应为对象")
            else:
                for ek in ("qi_loss", "stone_loss", "mental_delta", "heart_delta"):
                    if ek in eff and not isinstance(eff[ek], int):
                        errors.append(
                            f"heaven_retribution.json retribution_events[{i}].effects.{ek} 应为整数"
                        )
                if "spawn_enemy" in eff and not isinstance(eff["spawn_enemy"], bool):
                    errors.append(
                        f"heaven_retribution.json retribution_events[{i}].effects.spawn_enemy 应为布尔"
                    )
    return errors


def validate_lifespan(config_dir):
    """校验 config/lifespan.json（维度⑤ 寿元与轮回晚年）。"""
    errors = []
    path = os.path.join(config_dir, "lifespan.json")
    if not os.path.exists(path):
        return errors
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        errors.append(f"lifespan.json JSON 解析失败：{e}")
        return errors
    if not isinstance(data, dict):
        errors.append("lifespan.json 顶层应为对象")
        return errors

    # 1. 坐化安排
    sit = data.get("sit_and_dissolve", {})
    if not isinstance(sit, dict):
        errors.append("lifespan.json sit_and_dissolve 应为对象")
    else:
        if not isinstance(sit.get("near_end_years"), int):
            errors.append("lifespan.json sit_and_dissolve.near_end_years 应为整数")
        arrangements = sit.get("arrangements", {})
        if not isinstance(arrangements, dict) or not arrangements:
            errors.append("lifespan.json sit_and_dissolve.arrangements 应为非空对象")

    # 2. 残魂
    rs = data.get("remnant_soul", {})
    if not isinstance(rs, dict):
        errors.append("lifespan.json remnant_soul 应为对象")
    else:
        if not isinstance(rs.get("min_realm_order"), int):
            errors.append("lifespan.json remnant_soul.min_realm_order 应为整数")
        if not isinstance(rs.get("host_types"), list):
            errors.append("lifespan.json remnant_soul.host_types 应为数组")
        if not isinstance(rs.get("reshape_chance_per_month"), (int, float)) or not (0 <= rs.get("reshape_chance_per_month", -1) <= 1):
            errors.append("lifespan.json remnant_soul.reshape_chance_per_month 应在 [0,1]")
        # 2.1 残魂形态 forms
        forms = rs.get("forms")
        if not isinstance(forms, list) or not forms:
            errors.append("lifespan.json remnant_soul.forms 应为非空数组")
        else:
            seen = set()
            valid_hosts = set(rs.get("host_types", []) or []) | {None}
            for f in forms:
                if not isinstance(f, dict):
                    errors.append("lifespan.json remnant_soul.forms 元素应为对象")
                    continue
                fid = f.get("id")
                if not isinstance(fid, str) or fid in seen:
                    errors.append("lifespan.json remnant_soul.forms.id 应唯一且为字符串")
                seen.add(fid)
                if not isinstance(f.get("name"), str) or not isinstance(f.get("desc"), str):
                    errors.append(f"lifespan.json remnant_soul.forms '{fid}' name/desc 应为字符串")
                if not isinstance(f.get("min_mental_state"), int):
                    errors.append(f"lifespan.json remnant_soul.forms '{fid}' min_mental_state 应为整数")
                if not isinstance(f.get("max_heart_demon"), int):
                    errors.append(f"lifespan.json remnant_soul.forms '{fid}' max_heart_demon 应为整数")
                if f.get("require_host") is not None and f.get("require_host") not in valid_hosts:
                    errors.append(f"lifespan.json remnant_soul.forms '{fid}' require_host 应为合法 host_type 或 null")
                mp = f.get("monthly_passive", {})
                if not isinstance(mp, dict):
                    errors.append(f"lifespan.json remnant_soul.forms '{fid}' monthly_passive 应为对象")
                else:
                    for k in ("mental_delta", "heart_delta"):
                        if k in mp and not isinstance(mp[k], int):
                            errors.append(f"lifespan.json remnant_soul.forms '{fid}' monthly_passive.{k} 应为整数")
                    if "reshape_bonus" in mp and not isinstance(mp["reshape_bonus"], (int, float)):
                        errors.append(f"lifespan.json remnant_soul.forms '{fid}' monthly_passive.reshape_bonus 应为数字")
            default_form = rs.get("default_form")
            if default_form is not None and default_form not in seen:
                errors.append("lifespan.json remnant_soul.default_form 应指向存在的 form id")

    # 3. 前世遗物
    relics = data.get("past_life_relics", {})
    if not isinstance(relics, dict):
        errors.append("lifespan.json past_life_relics 应为对象")
    else:
        if not isinstance(relics.get("echo_chance_on_explore"), (int, float)) or not (0 <= relics.get("echo_chance_on_explore", -1) <= 1):
            errors.append("lifespan.json past_life_relics.echo_chance_on_explore 应在 [0,1]")
        if not isinstance(relics.get("relic_pool"), list):
            errors.append("lifespan.json past_life_relics.relic_pool 应为数组")

    # 4. 前世遗物链
    _RElic_CHAIN_KEYS = (
        "wisdom", "luck", "constitution", "max_health",
        "cultivation_speed", "breakthrough_bonus",
    )
    chains_block = data.get("relic_chains", {})
    if chains_block and not isinstance(chains_block, dict):
        errors.append("lifespan.json relic_chains 应为对象")
    else:
        chains = chains_block.get("chains", []) if isinstance(chains_block, dict) else []
        pool_ids = {
            r.get("id") for r in relics.get("relic_pool", []) if isinstance(r, dict)
        } | {"legacy_manual"}
        seen_ids = set()
        for ch in chains:
            if not isinstance(ch, dict):
                errors.append("lifespan.json relic_chains.chains 元素应为对象")
                continue
            cid = ch.get("id")
            if not isinstance(cid, str) or cid in seen_ids:
                errors.append("lifespan.json relic_chains.chains.id 应唯一且为字符串")
            seen_ids.add(cid)
            if not isinstance(ch.get("name"), str) or not isinstance(ch.get("desc"), str):
                errors.append(f"lifespan.json relic_chains.chains '{cid}' name/desc 应为字符串")
            links = ch.get("links")
            if not isinstance(links, list) or not links:
                errors.append(f"lifespan.json relic_chains.chains '{cid}' links 应为非空数组")
            else:
                for lid in links:
                    if lid not in pool_ids:
                        errors.append(
                            f"lifespan.json relic_chains.chains '{cid}' link '{lid}' 未指向已知遗物 id"
                        )
            for bk in ("per_link", "set"):
                b = ch.get(bk)
                if b is not None and not isinstance(b, dict):
                    errors.append(f"lifespan.json relic_chains.chains '{cid}' {bk} 应为对象")
                elif isinstance(b, dict):
                    for key, val in b.items():
                        if key not in _RElic_CHAIN_KEYS:
                            errors.append(
                                f"lifespan.json relic_chains.chains '{cid}' {bk}.{key} 非法加成键"
                            )
                        elif key in ("wisdom", "luck", "constitution", "max_health"):
                            if not isinstance(val, int):
                                errors.append(
                                    f"lifespan.json relic_chains.chains '{cid}' {bk}.{key} 应为整数"
                                )
                        else:
                            if not isinstance(val, (int, float)):
                                errors.append(
                                    f"lifespan.json relic_chains.chains '{cid}' {bk}.{key} 应为数字"
                                )
    return errors


def validate_red_dust(config_dir):
    """校验 config/red_dust.json（维度② 红尘炼心 / 入世）。

    覆盖：入世/出尘参数、羁绊类型、月度衰减、红尘事件、情劫场景。
    文件不存在则跳过（系统可由 feature_flags.red_dust 关闭）。
    """
    errors = []
    path = os.path.join(config_dir, "red_dust.json")
    if not os.path.exists(path):
        return errors
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        errors.append(f"red_dust.json JSON 解析失败：{e}")
        return errors
    if not isinstance(data, dict):
        errors.append("red_dust.json 顶层应为对象")
        return errors

    # 1. 入世 / 出尘
    enter = data.get("enter", {})
    if not isinstance(enter, dict):
        errors.append("red_dust.json enter 应为对象")
    else:
        for k in ("bond_gain_chance", "event_chance", "qingjie_chance"):
            if not isinstance(enter.get(k), (int, float)) or not (0 <= enter.get(k, -1) <= 1):
                errors.append(f"red_dust.json enter.{k} 应为 [0,1] 的数值")
    exit_cfg = data.get("exit", {})
    if not isinstance(exit_cfg, dict):
        errors.append("red_dust.json exit 应为对象")
    else:
        for k in ("dao_heart_per_bond", "heart_demon_per_bond"):
            if not isinstance(exit_cfg.get(k), int):
                errors.append(f"red_dust.json exit.{k} 应为整数")

    # 2. 羁绊类型
    btypes = data.get("bond_types", {})
    if not isinstance(btypes, dict) or not btypes:
        errors.append("red_dust.json bond_types 应为非空对象")
    else:
        for btid, spec in btypes.items():
            if not isinstance(spec, dict):
                errors.append(f"red_dust.json bond_types.{btid} 应为对象")
                continue
            for k in ("mental_gain", "heart_gain", "intimacy_max"):
                if not isinstance(spec.get(k), int):
                    errors.append(f"red_dust.json bond_types.{btid}.{k} 应为整数")
            if not isinstance(spec.get("name"), str) or not spec.get("name"):
                errors.append(f"red_dust.json bond_types.{btid} 缺少 name")

    # 3. 月度衰减
    decay = data.get("monthly_decay", {})
    if not isinstance(decay, dict):
        errors.append("red_dust.json monthly_decay 应为对象")
    elif not isinstance(decay.get("intimacy_decay_per_month"), int):
        errors.append("red_dust.json monthly_decay.intimacy_decay_per_month 应为整数")

    # 4. 红尘事件
    events = data.get("red_dust_events", [])
    if not isinstance(events, list) or not events:
        errors.append("red_dust.json red_dust_events 应为非空数组")
    else:
        seen = set()
        valid_bond_types = set(btypes.keys())
        for e in events:
            eid = e.get("id", "<未知>")
            if eid in seen:
                errors.append(f"red_dust.json 红尘事件 id 重复：{eid}")
            seen.add(eid)
            if not isinstance(e.get("name"), str) or not e.get("name"):
                errors.append(f"red_dust.json 红尘事件 '{eid}' 缺少 name")
            if not isinstance(e.get("description"), str):
                errors.append(f"red_dust.json 红尘事件 '{eid}' 缺少 description")
            for k in ("mental_delta", "heart_delta"):
                if not isinstance(e.get(k), int):
                    errors.append(f"red_dust.json 红尘事件 '{eid}'.{k} 应为整数")
            if "bond_chance" in e and not (0 <= e.get("bond_chance", -1) <= 1):
                errors.append(f"red_dust.json 红尘事件 '{eid}'.bond_chance 应在 [0,1]")
            if "bond_type" in e and e.get("bond_type") not in valid_bond_types:
                errors.append(
                    f"red_dust.json 红尘事件 '{eid}'.bond_type "
                    f"'{e.get('bond_type')}' 不是合法羁绊类型"
                )

    # 5. 情劫场景
    qjs = data.get("qingjie_scenarios", [])
    if not isinstance(qjs, list) or not qjs:
        errors.append("red_dust.json qingjie_scenarios 应为非空数组")
    else:
        seen = set()
        for q in qjs:
            qid = q.get("id", "<未知>")
            if qid in seen:
                errors.append(f"red_dust.json 情劫场景 id 重复：{qid}")
            seen.add(qid)
            if not isinstance(q.get("name"), str) or not q.get("name"):
                errors.append(f"red_dust.json 情劫场景 '{qid}' 缺少 name")
            if not isinstance(q.get("description"), str):
                errors.append(f"red_dust.json 情劫场景 '{qid}' 缺少 description")
            choices = q.get("choices", [])
            if not isinstance(choices, list) or not choices:
                errors.append(f"red_dust.json 情劫场景 '{qid}' 缺少 choices 数组")
                continue
            for c in choices:
                if not isinstance(c.get("id"), str):
                    errors.append(f"red_dust.json 情劫场景 '{qid}' 选项缺少 id")
                if not isinstance(c.get("text"), str):
                    errors.append(f"red_dust.json 情劫场景 '{qid}' 选项缺少 text")
                if not isinstance(c.get("result_text"), str):
                    errors.append(f"red_dust.json 情劫场景 '{qid}' 选项缺少 result_text")
                eff = c.get("effects", {})
                if not isinstance(eff, dict):
                    errors.append(f"red_dust.json 情劫场景 '{qid}' 选项 effects 应为对象")
                else:
                    for k in ("mental_delta", "heart_delta"):
                        if k in eff and not isinstance(eff[k], int):
                            errors.append(
                                f"red_dust.json 情劫场景 '{qid}' 选项 effects.{k} 应为整数"
                            )

    # 第 8 节：羁绊共鸣 + 温养（M21 新增）
    resonance = data.get("bond_resonance")
    if resonance is not None:
        if not isinstance(resonance, dict):
            errors.append("red_dust.json bond_resonance 应为对象")
        else:
            bond_types = data.get("bond_types", {})
            for bt, tiers in resonance.items():
                if bt.startswith("_"):
                    continue
                if bt not in bond_types:
                    errors.append(f"red_dust.json bond_resonance.{bt} 不是已知羁绊类型")
                    continue
                if not isinstance(tiers, list) or not tiers:
                    errors.append(f"red_dust.json bond_resonance.{bt} 应为非空数组")
                    continue
                last_min = -1
                for t in tiers:
                    if not isinstance(t, dict):
                        errors.append(f"red_dust.json bond_resonance.{bt} 档位应为对象")
                        continue
                    if not isinstance(t.get("min_intimacy"), int):
                        errors.append(f"red_dust.json bond_resonance.{bt} 档位 min_intimacy 应为整数")
                    else:
                        if t["min_intimacy"] <= last_min:
                            errors.append(
                                f"red_dust.json bond_resonance.{bt} 档位应按 min_intimacy 升序且唯一"
                            )
                        last_min = t["min_intimacy"]
                    if not isinstance(t.get("name"), str) or not t.get("name"):
                        errors.append(f"red_dust.json bond_resonance.{bt} 档位缺少 name")
                    if not isinstance(t.get("desc"), str):
                        errors.append(f"red_dust.json bond_resonance.{bt} 档位缺少 desc")
                    for k in ("monthly_mental", "monthly_heart"):
                        if k in t and not isinstance(t[k], int):
                            errors.append(
                                f"red_dust.json bond_resonance.{bt} 档位 {k} 应为整数"
                            )
    warmth = data.get("warmth")
    if warmth is not None:
        if not isinstance(warmth, dict):
            errors.append("red_dust.json warmth 应为对象")
        else:
            if not isinstance(warmth.get("cost_item"), str) or not warmth.get("cost_item"):
                errors.append("red_dust.json warmth.cost_item 应为非空字符串")
            if not isinstance(warmth.get("cost_count"), int) or warmth.get("cost_count", 0) <= 0:
                errors.append("red_dust.json warmth.cost_count 应为正整数")
            if not isinstance(warmth.get("intimacy_gain"), int) or warmth.get("intimacy_gain", 0) <= 0:
                errors.append("red_dust.json warmth.intimacy_gain 应为正整数")
    return errors


def validate_hundred_schools(config_dir):
    """校验 config/hundred_schools.json（维度③ 百家争鸣 / 非传统修仙路线）。

    覆盖：立派传道、自创功法、生活流派三支柱。
    文件不存在则跳过（系统可由 feature_flags.hundred_schools 关闭）。
    """
    errors = []
    path = os.path.join(config_dir, "hundred_schools.json")
    if not os.path.exists(path):
        return errors
    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        errors.append(f"hundred_schools.json JSON 解析失败：{e}")
        return errors
    if not isinstance(data, dict):
        errors.append("hundred_schools.json 顶层应为对象")
        return errors

    # 1. 立派传道
    sect = data.get("sect", {})
    if not isinstance(sect, dict):
        errors.append("hundred_schools.json sect 应为对象")
    else:
        int_keys = (
            "min_realm_order", "found_cost_spirit_stone", "disciples_base",
            "max_disciples", "enlightenment_cost_qi_yun",
            "enlightenment_dao_heart",
        )
        for k in int_keys:
            if not isinstance(sect.get(k), int):
                errors.append(f"hundred_schools.json sect.{k} 应为整数")
        for k in ("disciples_per_qi_yun", "max_qi_yun", "feedback_spirit_stone_per_qi_yun", "qi_yun_per_new_disciple"):
            if not isinstance(sect.get(k), (int, float)):
                errors.append(f"hundred_schools.json sect.{k} 应为数值")

    # 2. 自创功法
    tech = data.get("self_created_technique", {})
    if not isinstance(tech, dict):
        errors.append("hundred_schools.json self_created_technique 应为对象")
    else:
        for k in ("min_realm_order", "cost_spirit_stone", "max_techniques"):
            if not isinstance(tech.get(k), int):
                errors.append(f"hundred_schools.json self_created_technique.{k} 应为整数")
        if not isinstance(tech.get("allowed_attributes"), list) or not tech.get("allowed_attributes"):
            errors.append("hundred_schools.json self_created_technique.allowed_attributes 应为非空数组")
        if not isinstance(tech.get("schools"), list) or not tech.get("schools"):
            errors.append("hundred_schools.json self_created_technique.schools 应为非空数组")
        if not isinstance(tech.get("monthly_dao_heart_per_technique"), (int, float)):
            errors.append("hundred_schools.json self_created_technique.monthly_dao_heart_per_technique 应为数值")

    # 3. 生活流派
    lp = data.get("life_path", {})
    if not isinstance(lp, dict):
        errors.append("hundred_schools.json life_path 应为对象")
    else:
        if not isinstance(lp.get("types"), dict) or not lp.get("types"):
            errors.append("hundred_schools.json life_path.types 应为非空对象")
        for k in ("proficiency_per_month", "max_proficiency", "min_mitigation_level", "max_mitigation"):
            if not isinstance(lp.get(k), (int, float)):
                errors.append(f"hundred_schools.json life_path.{k} 应为数值")
        if not (0 <= lp.get("max_mitigation", -1) <= 1):
            errors.append("hundred_schools.json life_path.max_mitigation 应在 [0,1]")
        # 3b. 生活流派产出（M12）：每条流派可周期产出真实物品
        produce = lp.get("produce", {})
        if produce and not isinstance(produce, dict):
            errors.append("hundred_schools.json life_path.produce 应为对象")
        else:
            for pk, pv in (produce or {}).items():
                if pk not in lp.get("types", {}):
                    errors.append(f"hundred_schools.json life_path.produce.{pk} 不在 life_path.types 中")
                if not isinstance(pv, dict):
                    errors.append(f"hundred_schools.json life_path.produce.{pk} 应为对象")
                    continue
                if not isinstance(pv.get("item_id"), str) or not pv.get("item_id"):
                    errors.append(f"hundred_schools.json life_path.produce.{pk}.item_id 应为非空字符串")
                if not isinstance(pv.get("every_months"), int) or pv.get("every_months", 0) <= 0:
                    errors.append(f"hundred_schools.json life_path.produce.{pk}.every_months 应为正整数")
                if not isinstance(pv.get("min_proficiency"), int) or pv.get("min_proficiency", -1) < 0:
                    errors.append(f"hundred_schools.json life_path.produce.{pk}.min_proficiency 应为非负整数")
                # 3c. 战斗部署型增益（M15）：battle_buff 若存在则校验其结构
                bb = pv.get("battle_buff")
                if bb is not None:
                    if not isinstance(bb, dict):
                        errors.append(f"hundred_schools.json life_path.produce.{pk}.battle_buff 应为对象")
                    else:
                        if not isinstance(bb.get("name"), str) or not bb.get("name"):
                            errors.append(f"hundred_schools.json life_path.produce.{pk}.battle_buff.name 应为非空字符串")
                        valid_slots = {"player_attack_up", "player_defense_up",
                                       "enemy_attack_down", "enemy_defense_down", "player_shield"}
                        has_slot = False
                        for sk in valid_slots:
                            if sk in bb:
                                has_slot = True
                                if sk == "player_shield":
                                    if not isinstance(bb[sk], int) or bb[sk] <= 0:
                                        errors.append(f"hundred_schools.json life_path.produce.{pk}.battle_buff.player_shield 应为正整数")
                                else:
                                    sb = bb[sk]
                                    if not isinstance(sb, dict):
                                        errors.append(f"hundred_schools.json life_path.produce.{pk}.battle_buff.{sk} 应为对象")
                                    elif not isinstance(sb.get("ratio"), (int, float)) or not (0 < sb.get("ratio", 0) < 1):
                                        errors.append(f"hundred_schools.json life_path.produce.{pk}.battle_buff.{sk}.ratio 应在 (0,1)")
                                    elif not isinstance(sb.get("turns"), int) or sb.get("turns", 0) <= 0:
                                        errors.append(f"hundred_schools.json life_path.produce.{pk}.battle_buff.{sk}.turns 应为正整数")
                        if not has_slot:
                            errors.append(f"hundred_schools.json life_path.produce.{pk}.battle_buff 至少需含一个战斗增益槽")

    # 2b. 自创功法 → 技能模板（M12）：把自创功法注册为真实可施展 Skill
    tech = data.get("self_created_technique", {})
    if isinstance(tech, dict):
        schools = tech.get("schools", [])
        # attribute_element：键需在 allowed_attributes，值在已知五行/无属性集合
        attr_elem = tech.get("attribute_element", {})
        if attr_elem and not isinstance(attr_elem, dict):
            errors.append("hundred_schools.json self_created_technique.attribute_element 应为对象")
        else:
            known_elements = {"metal", "wood", "water", "fire", "earth", "none", "all"}
            for ak, av in (attr_elem or {}).items():
                if ak not in tech.get("allowed_attributes", []):
                    errors.append(f"hundred_schools.json attribute_element.{ak} 不在 allowed_attributes 中")
                if av not in known_elements:
                    errors.append(f"hundred_schools.json attribute_element.{ak} 元素值 {av} 非法")
        # skill_templates：每个 school 需有数值化战斗参数
        tmpls = tech.get("skill_templates", {})
        if tmpls and not isinstance(tmpls, dict):
            errors.append("hundred_schools.json self_created_technique.skill_templates 应为对象")
        else:
            for sk_name in (tmpls or {}):
                if sk_name not in schools:
                    errors.append(f"hundred_schools.json skill_templates.{sk_name} 不在 schools 中")
            for sk_name, t in (tmpls or {}).items():
                if not isinstance(t, dict):
                    errors.append(f"hundred_schools.json skill_templates.{sk_name} 应为对象")
                    continue
                for k in ("base_damage", "realm_multiplier", "weapon_multiplier",
                          "qi_cost", "cooldown", "heal", "heal_realm_multiplier"):
                    if not isinstance(t.get(k), (int, float)):
                        errors.append(f"hundred_schools.json skill_templates.{sk_name}.{k} 应为数值")

    # 2c. 功法推演（M19）：逐节点参悟 → 品质 → 品质阶乘算 Skill 强度
    ded = tech.get("deduction")
    if ded is not None:
        if not isinstance(ded, dict):
            errors.append("hundred_schools.json self_created_technique.deduction 应为对象")
        else:
            for k in ("cost_wisdom_per_node", "cost_spirit_stone_per_node", "max_nodes"):
                if not isinstance(ded.get(k), int) or ded.get(k, 0) <= 0:
                    errors.append(f"hundred_schools.json deduction.{k} 应为正整数")
            node_types = ded.get("node_types")
            if not isinstance(node_types, dict) or not node_types:
                errors.append("hundred_schools.json deduction.node_types 应为非空对象")
            else:
                valid_stats = {"base_damage", "realm_multiplier", "weapon_multiplier",
                               "heal", "heal_realm_multiplier"}
                for nk, nv in node_types.items():
                    if not isinstance(nv, dict):
                        errors.append(f"hundred_schools.json deduction.node_types.{nk} 应为对象")
                        continue
                    if nv.get("stat") not in valid_stats:
                        errors.append(
                            f"hundred_schools.json deduction.node_types.{nk}.stat "
                            f"'{nv.get('stat')}' 非法（应为 {sorted(valid_stats)}）"
                        )
                    if not isinstance(nv.get("quality"), int) or nv.get("quality", -1) <= 0:
                        errors.append(f"hundred_schools.json deduction.node_types.{nk}.quality 应为正整数")
                    if not isinstance(nv.get("success"), (int, float)) or not (0 < nv.get("success", 0) <= 1):
                        errors.append(f"hundred_schools.json deduction.node_types.{nk}.success 应在 (0,1]")
            tiers = ded.get("quality_tiers")
            if not isinstance(tiers, list) or not tiers:
                errors.append("hundred_schools.json deduction.quality_tiers 应为非空数组")
            else:
                for tk in tiers:
                    if not isinstance(tk, dict):
                        errors.append("hundred_schools.json deduction.quality_tiers 元素应为对象")
                        continue
                    if not isinstance(tk.get("tier"), str) or not tk.get("tier"):
                        errors.append("hundred_schools.json deduction.quality_tiers 元素缺少 tier")
                    if not isinstance(tk.get("min_quality"), int) or tk.get("min_quality", -1) < 0:
                        errors.append("hundred_schools.json deduction.quality_tiers.min_quality 应为非负整数")
                    if not isinstance(tk.get("mult"), (int, float)) or tk.get("mult", 0) <= 0:
                        errors.append("hundred_schools.json deduction.quality_tiers.mult 应为正数")
    return errors


def main():
    config_dir = sys.argv[1] if len(sys.argv) > 1 else "config"
    if not os.path.isdir(config_dir):
        print(f"配置目录不存在：{config_dir}")
        sys.exit(1)

    errors = validate_all(config_dir)
    if errors:
        print(f"配置校验失败，共 {len(errors)} 处错误：")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print(f"配置校验通过：{config_dir}")


if __name__ == "__main__":
    main()
