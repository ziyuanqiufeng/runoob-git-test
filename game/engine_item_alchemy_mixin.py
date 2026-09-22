# -*- coding: utf-8 -*-
"""GameEngine 物品·炼丹·商店域 Mixin（第九期纯净度修正，2026-09-22）。

物品使用/装备卸下、合成/炼丹、炼丹坊、通用商店买卖、技能使用判定与买卖定价。
方法原样迁出：第八期误并入 CityLifeMixin / 第六期误并入 SectMixin 的部分由本文件归位。
切出备份：tools/.purity_fix_backup_20260922.py。
"""
import random

from game.constants import ELEMENT_NAMES


class ItemAlchemyMixin:
    """依赖宿主 GameEngine 的对应 Manager 实例属性与跨 Mixin 方法。"""

    def use_item(self, item):
        """使用一个物品，丹药/功法消耗，装备则穿戴。"""
        if item not in self.player.inventory:
            self.notify("背包中没有该物品。")
            return False

        # 装备类物品：直接装备（含本命法宝）
        if item.type in self.player.EQUIPMENT_SLOTS or (
            item.type == "life_treasure" and self.player.has_feature("life_treasure")
        ):
            old = self.player.equip_item(item)
            if old is None and item.type == "life_treasure":
                self.notify("你尚未解锁本命法宝槽位，无法装备。")
                return False
            msg = f"你装备了【{item.name}】。"
            if old:
                msg += f" 替换下来的【{old.name}】放回背包。"
            self.notify(msg)
            return True

        effects = item.effects
        if not effects:
            self.notify(f"【{item.name}】无法直接使用。")
            return False

        # 处理功法类：可能学会技能
        if "skill" in effects:
            skill_id = effects["skill"]
            if self.player.learn_skill(skill_id):
                skill_name = self.skill_library.get(skill_id).name
                self.notify(f"你研读【{item.name}】，习得技能「{skill_name}」！")
                # 触发习得技能事件钩子
                self._on_learn_skill(skill_id)
            else:
                self.notify(f"你已经会这个技能了。")
            # 功法使用后消耗
            self.player.remove_item(item)
            return True

        # 处理丹方类：学会一条炼丹配方
        if item.type == "recipe":
            recipe_id = item.id
            if recipe_id in self.player.learned_recipes:
                self.notify(f"你已经掌握了【{item.name}】的内容。")
                return False
            # 校验配方是否真实存在
            recipe = self.world.get_recipe(recipe_id)
            if not recipe:
                self.notify(f"【{item.name}】上的内容已经模糊不清，无法学习。")
                return False
            self.player.learned_recipes.append(recipe_id)
            self.notify(f"你研读【{item.name}】，学会了炼制「{recipe['name']}」！")
            # 丹方使用后消耗
            self.player.remove_item(item)
            self._auto_save()
            return True

        # 处理洗髓丹：觉醒一项新的灵根属性
        if effects.get("awaken_root"):
            # 所有五行属性
            all_elements = ["metal", "wood", "water", "fire", "earth"]
            # 玩家尚未拥有的属性（融合灵根已包含的属性不应重复觉醒）
            expanded = getattr(self.player, "expanded_elements", self.player.spiritual_roots)
            remaining = [e for e in all_elements if e not in expanded]
            if not remaining:
                # 已经五行俱全，无法继续觉醒
                self.notify(f"你已五行灵根俱全，【{item.name}】无法再觉醒新的灵根。")
                return False
            # 随机选一项未觉醒的属性
            new_element = random.choice(remaining)
            old_roots = list(self.player.spiritual_roots)
            old_mult = self.player.cultivation_multiplier
            # 觉醒新灵根（set_spiritual_roots 会自动重算修炼倍率）
            new_roots = old_roots + [new_element]
            # 保留已有灵根纯度，为新灵根生成纯度（基于新灵根数量）
            new_purities = dict(getattr(self.player, "root_purities", {}))
            # 灵根数量 → 纯度范围
            purity_ranges = {
                1: [1.1, 1.5], 2: [0.9, 1.2], 3: [0.8, 1.1],
                4: [0.7, 1.0], 5: [0.6, 0.9],
            }
            min_p, max_p = purity_ranges.get(len(new_roots), [0.8, 1.0])
            new_purities[new_element] = round(random.uniform(min_p, max_p), 2)
            self.player.set_spiritual_roots(new_roots, new_purities)
            new_mult = self.player.cultivation_multiplier
            elem_cn = ELEMENT_NAMES.get(new_element, new_element)
            purity_val = new_purities[new_element]
            self.notify(
                f"你服下【{item.name}】，丹药之力洗髓伐骨，"
                f"觉醒了【{elem_cn}】灵根（纯度 {purity_val}）！"
                f"（修炼倍率 {old_mult}x → {new_mult}x）"
            )
            # 洗髓丹使用后消耗
            self.player.remove_item(item)
            self._auto_save()
            # 若觉醒后五行俱全，检查解锁阵法技能
            self.check_formation_unlock()
            return True

        # 应用常规效果
        if "qi" in effects:
            self.player.qi += effects["qi"]
        if "health" in effects:
            self.player.health += effects["health"]
            self.player.health = min(self.player.health, self.player.max_health)
        if "wisdom" in effects:
            self.player.wisdom += effects["wisdom"]
        if "constitution" in effects:
            self.player.constitution += effects["constitution"]
        if "luck" in effects:
            self.player.luck += effects["luck"]
        # 维度①② 联动：道心提振 / 心魔消解（钳制 0-100）
        if "mental_state" in effects:
            ms = getattr(self.player, "mental_state", 50)
            self.player.mental_state = max(0, min(100, ms + effects["mental_state"]))
        if "heart_demon" in effects:
            hd = getattr(self.player, "heart_demon", 0)
            self.player.heart_demon = max(0, min(100, hd + effects["heart_demon"]))
        # 维度③·M18：丹道「灵力温养」持续修炼增益（服用丹药后每月额外修为）
        if "cultivation_boost" in effects:
            cb = effects["cultivation_boost"]
            self.player.cultivation_boost_months = int(cb.get("months", 0))
            self.player.cultivation_boost_amount = int(cb.get("amount", 0))

        # 丹药/消耗品使用后消耗（带效果的 consumable 不再无限复用）
        if item.type in ("pill", "consumable"):
            self.player.remove_item(item)

        self.notify(f"你使用了【{item.name}】，{item.description}")
        self._check_death()
        return True

    def unequip_item(self, slot):
        """卸下指定槽位的装备。"""
        item = self.player.unequip_item(slot)
        if item:
            self.notify(f"你卸下了【{item.name}】。")
            return True
        return False

    def craft(self, recipe_id):
        """根据配方合成物品。"""
        recipe = self.world.get_recipe(recipe_id)
        if not recipe:
            self.notify("配方不存在。")
            return False

        # 检查材料是否足够
        materials = recipe["materials"]
        for item_id, count in materials.items():
            if self.player.count_item(item_id) < count:
                item_name = self.item_library.get(item_id).name
                self.notify(f"材料不足：{item_name} 需要 {count} 个。")
                return False

        # 消耗材料
        for item_id, count in materials.items():
            self.player.consume_items(item_id, count)

        # 生成产物
        result = recipe["result"]
        item_id = result["item_id"]
        count = result.get("count", 1)
        for _ in range(count):
            item = self.item_library.create(item_id)
            self.player.add_item(item)

        item_name = self.item_library.get(item_id).name
        self.notify(f"合成成功！获得 {item_name} x{count}。")
        # 合成获得物品也可能推进宗门收集任务
        self.sect_manager.update_task_progress("collect", item_id, count)
        # 触发获得物品事件钩子
        self._on_gain_item(item_id, count)
        self._auto_save()
        return True

    def craft_pill(self, recipe_id):
        """在炼丹阁炼丹，成功率受丹方、流派、悟性与炼丹室等级影响。

        为了保持与旧版 AlchemyDialog 的兼容，仍返回是否进入炼制流程，
        实际逻辑已委托给 AlchemyManager，并统一推进 7 日时间。
        """
        success, message, produced = self.alchemy_manager.craft(recipe_id)
        self.notify(message)
        if success and produced:
            product_id = produced[0].id
            total_count = sum(item.count for item in produced)
            self.sect_manager.update_task_progress("collect", product_id, total_count)
            self._on_gain_item(product_id, total_count)
        # 炼丹耗费 7 日（天级推进；不跨月则不推进年龄，跨月由下方钩子处理月度重置）
        self.world.advance(days=7)
        self._check_sect_daily_reset()
        self._auto_save()
        return success

    def open_alchemy_shop(self):
        """打开炼丹阁专属商店，根据建筑等级解锁丹方。"""
        from game.npc import NPC
        # 基础材料始终出售
        shop_items = ["low_herb", "spirit_liquid", "century_herb"]
        # 根据炼丹阁等级解锁丹方
        effects = self.building_manager.get_current_effects("alchemy_pavilion")
        unlock_recipes = effects.get("unlock_recipes", [])
        shop_items.extend(unlock_recipes)

        merchant = NPC(
            npc_id="alchemy_pavilion_keeper",
            name="炼丹阁管事",
            location=self.player.location_id,
            description="炼丹阁管事，手中握着不少珍稀丹方。",
            dialog="道友是来买丹方，还是采购材料？",
            quests=[],
            shop_items=shop_items,
            buy_multiplier=1.0,
            sell_multiplier=0.6,
        )
        return merchant

    # ==================== 演武场系统 ====================

    def buy_item(self, item_id, price=None, npc=None, quantity=1):
        """用灵石购买物品；支持指定数量。"""
        if not isinstance(quantity, int) or quantity < 1:
            self.notify("购买数量不合法。")
            return False

        unit_price = price if price is not None else self.get_buy_price(item_id, npc)
        total_price = unit_price * quantity
        if self.player.count_item("spirit_stone") < total_price:
            self.notify("灵石不足，无法购买。")
            return False

        item = self.item_library.create(item_id)
        if not item:
            self.notify("物品不存在。")
            return False

        self.player.consume_items("spirit_stone", total_price)
        item.count = quantity
        self.player.add_item(item)
        self.notify(f"你花费 {total_price} 灵石购买了【{item.name}】x{quantity}。")
        # 购买物品也可能推进宗门收集任务
        self.sect_manager.update_task_progress("collect", item_id, quantity)
        # 触发获得物品事件钩子
        self._on_gain_item(item_id)
        self._auto_save()
        return True

    def sell_item(self, item, npc=None, price=None, quantity=1):
        """出售背包中的物品；可指定 NPC、单价与数量，用于应用宗门关系修正。"""
        if not isinstance(quantity, int) or quantity < 1:
            self.notify("出售数量不合法。")
            return False

        # 装备类物品不允许出售
        if item.type in self.player.EQUIPMENT_SLOTS:
            self.notify("装备类物品请卸下后再出售。")
            return False

        if self.player.count_item(item.id) < quantity:
            self.notify("背包中该物品数量不足。")
            return False

        if not self.player.consume_items(item.id, quantity):
            return False

        actual_price = price if price is not None else self.get_sell_price(item, npc)
        total = actual_price * quantity
        for _ in range(total):
            self.player.add_item(self.item_library.create("spirit_stone"))
        self.notify(f"你出售了【{item.name}】x{quantity}，获得 {total} 灵石。")
        self._auto_save()
        return True

    # ==================== 存档读档 ====================

    def get_skill_success_rate(self, skill_id):
        """计算技能施展成功率。满足境界时为 1.0，否则随境界差递减。"""
        skill = self.skill_library.get(skill_id)
        if not skill or not skill.realm_id:
            return 1.0
        required_order = self.player.REALM_ORDER.get(skill.realm_id, 0)
        player_order = self._get_realm_order()
        diff = required_order - player_order
        if diff <= 0:
            return 1.0
        # 每低一个大境界成功率下降 25%，最低保留 10% 强行施展可能
        return max(0.1, 1.0 - diff * 0.25)

    def get_skill_usability(self, skill_id, in_combat=True):
        """检查技能是否可用，返回 (can_use: bool, reasons: list[str])。

        境界不足不再完全禁用，而是作为风险提示（含成功率），
        战斗中仍可选择强行施展，失败时会受到反噬。
        """
        reasons = []
        skill = self.skill_library.get(skill_id)
        if not skill:
            return False, ["技能不存在"]

        # 是否已习得
        if skill_id not in self.player.skills:
            return False, ["尚未习得该技能"]

        # 战斗中冷却判断
        if in_combat and self.player.get_skill_cooldown(skill_id) > 0:
            cd = self.player.get_skill_cooldown(skill_id)
            reasons.append(f"冷却中（{cd} 回合）")

        # 真气消耗（考虑熟练度减耗）
        effective_cost = self._get_effective_qi_cost(skill_id)
        if self.player.qi < effective_cost:
            reasons.append(f"真气不足（{self.player.qi}/{effective_cost}）")

        # 灵根属性
        if not self.player.has_element(skill.element):
            elem_cn = ELEMENT_NAMES.get(skill.element, skill.element)
            reasons.append(f"需要{elem_cn}属性灵根")

        # 境界要求：不足时提示成功率，仍允许尝试施展
        if skill.realm_id:
            required_order = self.player.REALM_ORDER.get(skill.realm_id, 0)
            if self._get_realm_order() < required_order:
                realm_data = self.world.get_realm(skill.realm_id)
                realm_name = realm_data.get("name", skill.realm_id) if realm_data else skill.realm_id
                rate = self.get_skill_success_rate(skill_id)
                reasons.append(f"境界不足（需{realm_name}，成功率 {int(rate * 100)}%）")

        # 流派专属
        if skill.path_exclusive and self.player.cultivation_path != skill.path_exclusive:
            path_names = {
                "fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
                "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
                "zhen": "阵修", "fu": "符修",
            }
            reasons.append(f"{path_names.get(skill.path_exclusive, skill.path_exclusive)}专属")

        # 剑修武器要求
        if skill.path_exclusive == "jian" and not self._player_has_sword():
            reasons.append("需要装备剑类武器")

        # 境界不足仅作为风险提示，不算作硬禁用
        hard_reasons = [r for r in reasons if "成功率" not in r]
        return len(hard_reasons) == 0, reasons

    # ==================== 商店系统 ====================

    def get_buy_price(self, item_id, npc=None):
        """
        计算购买价格 = 物品价值 × NPC 购买倍率 × 好感度折扣 × 关系网修正 × 阵营偏好修正 × 宗门关系修正 × 地点类型修正 × 节日折扣。
        好感度越高，购买越便宜；与 NPC 好友关系好也会降价，与敌人关系好则会加价。
        最终倍率限制在合理区间，防止极端价格。
        """
        item = self.item_library.get(item_id)
        if not item:
            return 0
        base_buy, _ = self.economy_config.get_base_multipliers()
        # 基础购买倍率
        multiplier = getattr(npc, "buy_multiplier", base_buy) if npc else base_buy
        # 好感度折扣
        buy_adjust, _ = self._get_relationship_discount(npc)
        # 宗门关系带来的价格波动（友好降价、敌对加价）
        sect_buy_mult, _ = self.get_sect_price_multiplier(npc)
        # NPC 关系网修正（朋友/敌人）
        rel_buy_mult, _ = npc.get_relationship_price_adjustment(self.player, self.npc_library) if npc else (1.0, 1.0)
        # 阵营偏好修正
        camp_mult = npc.get_faction_price_multiplier(self.player.get_camp()) if npc else 1.0
        # 地点类型修正（城市/宗门/荒野物价差异）
        loc_type_buy_mult = self._get_location_type_multiplier(npc, buy=True)
        final_multiplier = multiplier * buy_adjust * sect_buy_mult * rel_buy_mult * camp_mult * loc_type_buy_mult
        # 节日期间额外折扣：仅当 NPC 配置了当前节日的特殊对话时才生效
        current_festival = self.world.get_current_festival()
        if npc and current_festival:
            has_festival_dialog = any(
                entry.get("festival_id") == current_festival
                for entry in npc.festival_dialogs
            )
            if has_festival_dialog:
                final_multiplier *= self.economy_config.get_festival_discount()
        # 动态世界事件带来的地点价格修正
        if npc:
            location_id = getattr(npc, "current_location", None) or getattr(npc, "location", None)
            mods = self.player.world_event_price_mods.get(location_id)
            if mods:
                final_multiplier *= mods.get("buy_mult", 1.0)
        # 限制购买倍率在合理区间，避免经济失衡
        limits = self.economy_config.get_price_limits()
        buy_min = limits.get("buy_min", 0.75)
        buy_max = limits.get("buy_max", 3.0)
        final_multiplier = max(buy_min, min(buy_max, final_multiplier))
        return max(1, int(item.value * final_multiplier))

    def get_sell_price(self, item, npc=None):
        """
        计算出售价格 = 物品价值 × NPC 出售倍率 × 好感度加成 × 关系网修正 × 宗门关系修正 × 地点类型修正。
        好感度越高，出售价越高；敌对宗门会压低收购价，友好宗门则提高。
        最终倍率限制在合理区间，确保玩家无法通过倒卖无限获利。
        """
        _, base_sell = self.economy_config.get_base_multipliers()
        multiplier = getattr(npc, "sell_multiplier", base_sell) if npc else base_sell
        _, sell_adjust = self._get_relationship_discount(npc)
        _, sect_sell_mult = self.get_sect_price_multiplier(npc)
        _, rel_sell_mult = npc.get_relationship_price_adjustment(self.player, self.npc_library) if npc else (1.0, 1.0)
        # 地点类型修正
        loc_type_sell_mult = self._get_location_type_multiplier(npc, buy=False)
        final_multiplier = multiplier * sell_adjust * sect_sell_mult * rel_sell_mult * loc_type_sell_mult
        # 动态世界事件带来的地点价格修正
        if npc:
            location_id = getattr(npc, "current_location", None) or getattr(npc, "location", None)
            mods = self.player.world_event_price_mods.get(location_id)
            if mods:
                final_multiplier *= mods.get("sell_mult", 1.0)
        # 限制出售倍率，让高好感 NPC 愿意提高收购价，同时仍低于最低购买价
        limits = self.economy_config.get_price_limits()
        sell_min = limits.get("sell_min", 0.2)
        sell_max = limits.get("sell_max", 0.7)
        final_multiplier = max(sell_min, min(sell_max, final_multiplier))
        return max(1, int(item.value * final_multiplier))

    def _get_location_type_multiplier(self, npc, buy=True):
        """根据 NPC 当前所在地点类型返回价格修正倍率。"""
        if not npc:
            return 1.0
        # 优先使用当前实际位置，否则使用默认归属地点
        location_id = getattr(npc, "current_location", None) or getattr(npc, "location", None)
        if not location_id:
            return 1.0
        loc = self.world.get_location(location_id)
        if not loc:
            return 1.0
        loc_type = loc.get("type", "wild")
        buy_mult, sell_mult = self.economy_config.get_location_type_modifier(loc_type)
        return buy_mult if buy else sell_mult

