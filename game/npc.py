import random


class NPC:
    """NPC 对象，支持好感度、昼夜作息、移动路径、节日对话、关系网与记忆对话。"""

    def __init__(
        self,
        npc_id,
        name,
        location,
        description,
        dialog,
        quests,
        shop_items=None,
        teach_skills=None,
        buy_multiplier=1.2,
        sell_multiplier=0.6,
        locked_shop_items=None,
        relationship_dialogs=None,
        shop_pool=None,
        shop_pool_count=5,
        path_switch=False,
        sect_id=None,
        can_be_master=False,
        portrait=None,
        schedule=None,
        movement=None,
        festival_dialogs=None,
        npc_relationships=None,
        faction_affinity=None,
        memory_dialogs=None,
        side_quests=None,
        dynamic_spawn=None,
        dialogue_id=None,
        gender=None,
        realm_id="qi_refining_1",
        wisdom=5,
        age=30,
        can_dual_cultivate=True,
    ):
        self.id = npc_id
        self.name = name
        self.location = location                    # NPC 默认/归属地点
        self.current_location = None                # 当前实际地点，None 表示在默认地点
        self.description = description
        self.dialog = dialog
        self.dialogue_id = dialogue_id              # 分支对话配置 ID
        self.quests = quests
        self.shop_items = shop_items or []          # 商店基础售卖物品
        self.teach_skills = teach_skills or []      # 可传授技能
        self.buy_multiplier = buy_multiplier        # 购买价格倍率（相对于物品价值）
        self.sell_multiplier = sell_multiplier      # 出售价格倍率（相对于物品价值）
        # 好感度门槛解锁的独家商品
        self.locked_shop_items = locked_shop_items or []
        # 好感度对话
        self.relationship_dialogs = relationship_dialogs or []
        # 随机商品池
        self.shop_pool = shop_pool or []
        self.shop_pool_count = shop_pool_count
        # 流派转换 NPC 标记
        self.path_switch = path_switch
        # 显式宗门归属
        self.sect_id = sect_id
        # 是否可拜其为师
        self.can_be_master = can_be_master
        # 头像/立绘资源路径
        self.portrait = portrait
        # 昼夜作息：{"active_hours": [start, end], "rest_location": str, "rest_dialog": str}
        self.schedule = schedule or {}
        # 随机移动路径：{"wandering": bool, "possible_locations": [...], "move_chance": float}
        self.movement = movement or {}
        # 节日特殊对话：[{"festival_id": str, "dialog": str}, ...]
        self.festival_dialogs = festival_dialogs or []
        # NPC 关系网：{"master": str, "apprentices": [...], "friends": [...], "enemies": [...], "lovers": [...]}
        self.npc_relationships = npc_relationships or {}
        # 阵营偏好：{"righteous": float, "evil": float, "neutral": float}
        self.faction_affinity = faction_affinity or {}
        # 记忆对话：[{"memory_key": str, "expected_value": Any, "dialog": str}, ...]
        self.memory_dialogs = memory_dialogs or []
        # 可发布的支线任务 ID 列表
        self.side_quests = side_quests or []
        # 动态出现条件：{"condition": str, "locations": [...], "chance": float}
        self.dynamic_spawn = dynamic_spawn or {}
        # 社交系统字段（可选，配置缺失时使用默认值）
        self.gender = gender or "male"          # 性别：male/female
        self.realm_id = realm_id                # 境界 ID
        self.wisdom = wisdom                    # 悟性，影响论道胜负
        self.age = age                          # 年龄，影响双修资格
        self.can_dual_cultivate = can_dual_cultivate  # 是否可双修

    @classmethod
    def from_dict(cls, data):
        return cls(
            npc_id=data["id"],
            name=data["name"],
            location=data["location"],
            description=data.get("description", ""),
            dialog=data.get("dialog", ""),
            quests=data.get("quests", []),
            shop_items=data.get("shop_items", []),
            teach_skills=data.get("teach_skills", []),
            buy_multiplier=data.get("buy_multiplier", 1.2),
            sell_multiplier=data.get("sell_multiplier", 0.6),
            locked_shop_items=data.get("locked_shop_items", []),
            relationship_dialogs=data.get("relationship_dialogs", []),
            shop_pool=data.get("shop_pool", []),
            shop_pool_count=data.get("shop_pool_count", 5),
            path_switch=data.get("path_switch", False),
            sect_id=data.get("sect_id"),
            can_be_master=data.get("can_be_master", False),
            portrait=data.get("portrait"),
            schedule=data.get("schedule"),
            movement=data.get("movement"),
            festival_dialogs=data.get("festival_dialogs", []),
            npc_relationships=data.get("npc_relationships", {}),
            faction_affinity=data.get("faction_affinity", {}),
            memory_dialogs=data.get("memory_dialogs", []),
            side_quests=data.get("side_quests", []),
            dynamic_spawn=data.get("dynamic_spawn"),
            dialogue_id=data.get("dialogue_id"),
            gender=data.get("gender"),
            realm_id=data.get("realm_id", "qi_refining_1"),
            wisdom=data.get("wisdom", 5),
            age=data.get("age", 30),
            can_dual_cultivate=data.get("can_dual_cultivate", True),
        )

    def get_unlocked_shop_items(self, relationship):
        """
        根据当前好感度返回所有可购买的物品列表（基础 + 解锁）。
        relationship: 玩家与该 NPC 的好感度等级。
        """
        result = list(self.shop_items)
        for locked in self.locked_shop_items:
            if relationship >= locked.get("min_relationship", 999):
                result.append({"item_id": locked["item_id"]})
        return result

    def get_dialog(self, relationship, festival_id=None, player_memory=None):
        """
        根据好感度、节日、玩家记忆返回对话文本。
        优先级：节日对话 > 记忆对话 > 好感度对话 > 默认对话。
        """
        # 节日对话优先级最高
        if festival_id:
            for entry in self.festival_dialogs:
                if entry.get("festival_id") == festival_id:
                    return entry["dialog"]
        # 记忆对话
        if player_memory:
            for entry in self.memory_dialogs:
                key = entry.get("memory_key")
                expected = entry.get("expected_value")
                if key is not None and player_memory.get(key) == expected:
                    return entry["dialog"]
        # 好感度对话
        best_dialog = self.dialog
        best_threshold = -1
        for entry in self.relationship_dialogs:
            threshold = entry.get("min_relationship", 0)
            if relationship >= threshold and threshold > best_threshold:
                best_dialog = entry["dialog"]
                best_threshold = threshold
        return best_dialog

    def is_active_at(self, hour):
        """判断 NPC 在当前时辰是否活跃（未配置作息则默认全天活跃）。"""
        if not self.schedule:
            return True
        active = self.schedule.get("active_hours", [0, 24])
        if len(active) < 2:
            return True
        start, end = active
        if start <= end:
            return start <= hour < end
        # 跨午夜的情况，例如 [22, 6]
        return hour >= start or hour < end

    def get_current_location(self, hour, default_location=None):
        """根据当前时辰返回 NPC 实际所在地点（考虑移动与作息）。

        优先级：当前实际地点 > 作息休息地点 > 默认地点 > 归属地点。
        """
        # 若有当前实际地点（移动或世界事件导致），优先返回
        if self.current_location is not None:
            return self.current_location
        # 未在活跃时段则前往休息地点
        if not self.is_active_at(hour):
            return self.schedule.get("rest_location", default_location or self.location)
        return default_location or self.location

    def update_location(self, world):
        """根据 movement 配置尝试随机移动，每月调用一次。

        仅当 NPC 配置了 wandering=true 且在 possible_locations 中才进行移动。
        移动概率由 move_chance 控制（0-1）。
        """
        movement = self.movement
        if not movement.get("wandering"):
            return
        possible = movement.get("possible_locations", [])
        if not possible:
            return
        chance = movement.get("move_chance", 0.0)
        if random.random() >= chance:
            return
        # 在可能地点中随机选择一个作为新位置
        self.current_location = random.choice(possible)

    def get_relationship_price_adjustment(self, player, npc_library):
        """
        根据玩家与该 NPC 关系网中其他 NPC 的关系，计算额外价格修正。
        与好友关系好则降价，与敌人关系好则加价。
        返回 (buy_mult, sell_mult)。
        """
        buy_mult, sell_mult = 1.0, 1.0
        if not npc_library:
            return buy_mult, sell_mult
        friends = self.npc_relationships.get("friends", [])
        enemies = self.npc_relationships.get("enemies", [])
        for fid in friends:
            f_rel = player.get_npc_relationship(fid)
            # 好友好感高，给玩家面子降价 5%；好友好感低则加价 5%
            if f_rel >= 5:
                buy_mult *= 0.95
            elif f_rel <= 2:
                buy_mult *= 1.05
        for eid in enemies:
            e_rel = player.get_npc_relationship(eid)
            # 与敌人关系好会引起该 NPC 反感，购买加价 8%，收购压价 8%
            if e_rel >= 5:
                buy_mult *= 1.08
                sell_mult *= 0.92
        return buy_mult, sell_mult

    def get_faction_price_multiplier(self, player_camp):
        """
        根据玩家阵营与 NPC 阵营偏好计算价格修正。
        返回 buy_multiplier 的额外系数。
        """
        if not self.faction_affinity or not player_camp:
            return 1.0
        affinity = self.faction_affinity.get(player_camp, 1.0)
        # 偏好值越高越便宜，最低 0.7，最高 1.5
        return max(0.7, min(1.5, 2.0 - affinity))


class NPCLibrary:
    """NPC 库，从 JSON 加载，并支持按地点、时辰、动态条件查询。"""

    def __init__(self, config_dir="config"):
        import json
        import os

        npcs_path = os.path.join(config_dir, "npcs.json")
        with open(npcs_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.npcs = {d["id"]: NPC.from_dict(d) for d in data}

    def get(self, npc_id):
        return self.npcs.get(npc_id)

    def get_by_location(self, location_id, hour=None):
        """
        获取某个地点的所有 NPC。
        传入 hour 时，会按 NPC 作息与当前实际位置过滤。
        """
        result = []
        for npc in self.npcs.values():
            current_loc = npc.get_current_location(hour) if hour is not None else (npc.current_location or npc.location)
            if current_loc == location_id:
                result.append(npc)
        return result

    def get_wandering_npcs(self):
        """获取所有配置了移动路径的 NPC。"""
        return [npc for npc in self.npcs.values() if npc.movement.get("wandering")]

    def update_movements(self, world):
        """推进所有 NPC 的移动状态，每月调用一次。"""
        for npc in self.npcs.values():
            npc.update_location(world)

    def get_dynamic_spawn_candidates(self, player, world):
        """
        根据玩家状态和世界条件，返回可能动态出现的 NPC 列表。
        目前支持的条件：
        - "always": 总是满足
        - "festival": 当前是节日
        - "night": 夜间（hour < 6 或 hour >= 22）
        - "high_reputation": 玩家总好感度较高（暂定 >= 30）
        """
        import random
        candidates = []
        for npc in self.npcs.values():
            spawn = npc.dynamic_spawn
            if not spawn:
                continue
            condition = spawn.get("condition", "always")
            chance = spawn.get("chance", 0.0)
            if random.random() > chance:
                continue
            satisfied = False
            if condition == "always":
                satisfied = True
            elif condition == "festival":
                satisfied = world.get_current_festival() is not None
            elif condition == "night":
                satisfied = world.hour < 6 or world.hour >= 22
            elif condition == "high_reputation":
                total_rel = sum(player.npc_relationships.values())
                satisfied = total_rel >= 30
            if satisfied:
                candidates.append(npc)
        return candidates
