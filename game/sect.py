import json
import os
import random

from game.enemy import Enemy


class Sect:
    """宗门对象，保存宗门配置与动态数据。"""

    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.location_id = data["location_id"]
        self.leader_npc_id = data.get("leader_npc_id")
        self.description = data.get("description", "")
        self.element = data.get("element", "none")
        self.alignment = data.get("alignment", "neutral")  # righteous / evil / neutral
        self.path_bonus = data.get("path_bonus", {})
        self.hostile_to = data.get("hostile_to", [])
        self.friendly_to = data.get("friendly_to", [])
        self.facilities = data.get("facilities", [])
        self.facility_details = data.get("facility_details", [])
        self.secret_realms = data.get("secret_realms", [])
        self.bounty_board = data.get("bounty_board", [])
        self.unique_skill = data.get("unique_skill")
        self.shop_items = data.get("shop_items", [])
        self.scripture_skills = data.get("scripture_skills", [])
        self.ranks = data.get("ranks", {})
        self.cave_bonus = data.get("cave_bonus", {})
        self.spirit_veins = data.get("spirit_veins", [])
        self.war_reward = data.get("war_reward", {"base_contribution": 1000, "base_reputation": 50, "health_cost": 20})
        self.war_difficulty = data.get("war_difficulty", 1.0)
        self.wanted_threshold = data.get("wanted_threshold", 30)
        self.friendly_discount = data.get("friendly_discount", 0.9)
        self.fortune_events = data.get("fortune_events", [])
        self.protective_formation = data.get("protective_formation", {})
        self.inheritance = data.get("inheritance", [])
        self.beast_garden = data.get("beast_garden", {"max_beasts_per_player": 0, "beasts": []})

    def get_rank_name(self, rank_id):
        """根据职位 ID 获取中文名。"""
        return self.ranks.get(rank_id, {}).get("name", rank_id)

    def get_rank_info(self, rank_id):
        """获取职位配置。"""
        return self.ranks.get(rank_id, {})

    def get_next_rank(self, current_rank):
        """获取当前职位的下一级职位 ID。"""
        rank_order = ["outer", "inner", "core", "elder", "leader"]
        if current_rank not in rank_order:
            return "outer"
        idx = rank_order.index(current_rank)
        if idx + 1 < len(rank_order):
            return rank_order[idx + 1]
        return None

    def get_path_bonus(self, path_id):
        """获取某流派在该宗门的加成倍率。"""
        return self.path_bonus.get(path_id, 0.0)

    def get_cave_bonus(self, rank_id):
        """获取某职位的洞府加成。"""
        return self.cave_bonus.get(rank_id, {"cultivation_speed": 0, "max_qi_bonus": 0})


class SectLibrary:
    """宗门库，从 JSON 加载所有宗门。"""

    def __init__(self, config_dir="config"):
        sects_path = os.path.join(config_dir, "sects.json")
        with open(sects_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.sects = {d["id"]: Sect(d) for d in data}

    def get(self, sect_id):
        return self.sects.get(sect_id)

    def get_by_location(self, location_id):
        """根据地点 ID 查找宗门。"""
        for sect in self.sects.values():
            if sect.location_id == location_id:
                return sect
        return None

    def all_sects(self):
        return list(self.sects.values())


class SectTask:
    """宗门任务对象。"""

    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.description = data.get("description", "")
        self.type = data["type"]  # collect / kill / explore
        self.target_item = data.get("target_item")
        self.target_enemy = data.get("target_enemy")
        self.target_location = data.get("target_location")
        self.target_count = data.get("target_count", 1)
        self.required_rank = data.get("required_rank", "outer")
        self.contribution_reward = data.get("contribution_reward", 0)
        self.reputation_reward = data.get("reputation_reward", 0)
        self.item_reward = data.get("item_reward", {})


class SectTaskLibrary:
    """宗门任务库。"""

    def __init__(self, config_dir="config"):
        tasks_path = os.path.join(config_dir, "sect_tasks.json")
        with open(tasks_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.tasks = {d["id"]: SectTask(d) for d in data}

    def get(self, task_id):
        return self.tasks.get(task_id)

    def get_available_tasks(self, rank_id):
        """根据职位筛选可接取的任务。"""
        rank_order = {"outer": 0, "inner": 1, "core": 2, "elder": 3, "leader": 4}
        current_idx = rank_order.get(rank_id, 0)
        result = []
        for task in self.tasks.values():
            task_idx = rank_order.get(task.required_rank, 0)
            if task_idx <= current_idx:
                result.append(task)
        return result


class SectEvent:
    """宗门周期性活动，例如宗门大比、晋升考核。"""

    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.sect_id = data["sect_id"]
        self.interval_months = data.get("interval_months", 12)
        self.min_rank = data.get("min_rank", "outer")
        self.min_realm = data.get("min_realm")
        self.required_location = data.get("required_location")
        self.rounds = data.get("rounds", 3)
        self.base_enemy_level = data.get("base_enemy_level", 3)
        self.rewards = data.get("rewards", {})


class SectEventLibrary:
    """宗门活动库。"""

    def __init__(self, config_dir="config"):
        events_path = os.path.join(config_dir, "sect_events.json")
        with open(events_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.events = {d["id"]: SectEvent(d) for d in data}
        # 按宗门 ID 建立索引，方便快速查找
        self._sect_events = {}
        for event in self.events.values():
            self._sect_events.setdefault(event.sect_id, []).append(event)

    def get(self, event_id):
        return self.events.get(event_id)

    def get_by_sect(self, sect_id):
        """获取某宗门的所有活动（通常只有一个大比）。"""
        return self._sect_events.get(sect_id, [])


class SectManager:
    """宗门管理器：处理加入、退出、晋升、任务、兑换等逻辑。"""

    RANK_ORDER = ["outer", "inner", "core", "elder", "leader"]

    def __init__(
        self,
        player,
        sect_library,
        item_library,
        skill_library,
        enemy_library,
        follower_library,
        diplomatic_mission_library,
        world,
        sect_event_library=None,
    ):
        self.player = player
        self.sect_library = sect_library
        self.item_library = item_library
        self.skill_library = skill_library
        self.enemy_library = enemy_library
        self.follower_library = follower_library
        self.diplomatic_mission_library = diplomatic_mission_library
        self.world = world
        # 宗门活动库，外部未传入时自动创建
        self.sect_event_library = sect_event_library or SectEventLibrary()

    def get_sect(self):
        """获取玩家当前所属宗门对象。"""
        if not self.player.sect_id:
            return None
        return self.sect_library.get(self.player.sect_id)

    def can_join_sect(self, sect_id):
        """判断玩家是否可以加入某宗门。"""
        sect = self.sect_library.get(sect_id)
        if not sect:
            return False, "宗门不存在。"
        if self.player.sect_id:
            return False, "你已加入宗门，需先退出。"
        return True, ""

    def join_sect(self, sect_id):
        """加入宗门，成为外门弟子。"""
        ok, msg = self.can_join_sect(sect_id)
        if not ok:
            return False, msg
        sect = self.sect_library.get(sect_id)
        self.player.sect_id = sect_id
        self.player.sect_rank = "outer"
        self.player.sect_contribution = 0
        self.player.sect_loyalty = 50
        self.player.sect_tasks_today = 0
        # 新入宗门时清空个人仓库、累计捐献、秘境冷却、悬赏进度与气运事件（不同宗门独立计算）
        self.player.sect_warehouse = {}
        self.player.sect_donation_total = 0
        self.player.sect_donation_last_reward_month = -1
        self.player.sect_secret_realm_cooldowns = {}
        self.player.sect_active_bounty = None
        self.player.active_sect_fortune = None
        return True, f"你拜入【{sect.name}】，成为外门弟子。"

    def leave_sect(self):
        """退出宗门，损失部分贡献与忠诚度清零。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"
        old_name = sect.name
        self.player.sect_id = None
        self.player.sect_rank = "none"
        self.player.sect_contribution = 0
        self.player.sect_loyalty = 0
        self.player.sect_tasks_today = 0
        self.player.sect_active_task = None
        # 退出宗门后，该宗门仓库、累计捐献、秘境冷却、悬赏进度与气运事件清零
        self.player.sect_warehouse = {}
        self.player.sect_donation_total = 0
        self.player.sect_donation_last_reward_month = -1
        self.player.sect_secret_realm_cooldowns = {}
        self.player.sect_active_bounty = None
        self.player.active_sect_fortune = None
        return True, f"你退出【{old_name}】，贡献清零，从此漂泊江湖。"

    def get_rank_index(self, rank_id):
        """获取职位在等级序列中的索引。"""
        if rank_id in self.RANK_ORDER:
            return self.RANK_ORDER.index(rank_id)
        return -1

    def check_promotion(self):
        """检查玩家是否满足晋升条件。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入宗门。"

        next_rank = sect.get_next_rank(self.player.sect_rank)
        if not next_rank:
            return False, "你已是宗门最高职位。"

        rank_info = sect.get_rank_info(next_rank)
        min_contribution = rank_info.get("min_contribution", 0)
        required_realm = rank_info.get("required_realm")

        if self.player.sect_contribution < min_contribution:
            return False, f"贡献不足，需要 {min_contribution} 点。"

        if required_realm:
            current_order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
            required_order = self.player.REALM_ORDER.get(required_realm, 0)
            if current_order < required_order:
                return False, f"境界不足，需要 {required_realm}。"

        return True, next_rank

    def promote(self):
        """执行晋升。"""
        ok, msg = self.check_promotion()
        if not ok:
            return False, msg

        sect = self.get_sect()
        old_rank_name = sect.get_rank_name(self.player.sect_rank)
        self.player.sect_rank = msg
        new_rank_name = sect.get_rank_name(self.player.sect_rank)
        return True, f"你由【{old_rank_name}】晋升为【{new_rank_name}】！"

    # ==================== 宗门大比 ====================

    def get_sect_event(self, event_type="tournament"):
        """获取玩家宗门指定类型的活动（默认宗门大比）。"""
        sect = self.get_sect()
        if not sect:
            return None
        for event in self.sect_event_library.get_by_sect(sect.id):
            if event.id.endswith("_tournament"):
                return event
        return None

    def can_start_tournament(self):
        """检查是否满足参加宗门大比的条件。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        event = self.get_sect_event("tournament")
        if not event:
            return False, "你所在的宗门未举办宗门大比。"

        # 检查举办周期：按月份取模，且本月未参加过
        current_month = self.world.year * 12 + self.world.month
        if (current_month % event.interval_months) != 0:
            return False, "本月并非宗门大比之期。"

        last_month = getattr(self.player, "sect_tournament_last_month", -1)
        if last_month == current_month:
            return False, "你本月已参加过宗门大比。"

        # 检查地点
        if event.required_location and self.player.location_id != event.required_location:
            location_data = self.world.get_location(event.required_location)
            location_name = location_data.get("name", event.required_location) if location_data else event.required_location
            return False, f"需前往【{location_name}】方可参加大比。"

        # 检查职位
        rank_idx = self.get_rank_index(self.player.sect_rank)
        min_rank_idx = self.get_rank_index(event.min_rank)
        if rank_idx < min_rank_idx:
            rank_name = sect.get_rank_name(event.min_rank)
            return False, f"职位不足，需【{rank_name}】及以上。"

        # 检查境界
        if event.min_realm:
            current_order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
            min_order = self.player.REALM_ORDER.get(event.min_realm, 0)
            if current_order < min_order:
                realm_name = self.world.get_realm(event.min_realm).get("name", event.min_realm)
                return False, f"境界不足，需达到【{realm_name}】。"

        return True, ""

    def get_tournament_opponents(self):
        """生成宗门大比对手列表。"""
        event = self.get_sect_event("tournament")
        if not event:
            return []

        sect = self.get_sect()
        opponents = []
        for i in range(event.rounds):
            level = max(1, event.base_enemy_level + i)
            enemy_data = self._create_tournament_enemy_data(level, sect, event)
            enemy = Enemy.from_dict(enemy_data)
            opponents.append(enemy)
        return opponents

    def _create_tournament_enemy_data(self, level, sect, event):
        """根据等级与宗门属性生成大比弟子数据。"""
        # 基础属性随轮次递增
        base_hp = 80 + level * 35
        base_attack = 10 + level * 7
        base_defense = 2 + level * 2
        # 按宗门元素微调
        element_bonus = {
            "metal": {"hp": 1.0, "attack": 1.1, "defense": 1.0},
            "wood": {"hp": 1.1, "attack": 1.0, "defense": 1.0},
            "water": {"hp": 1.0, "attack": 1.0, "defense": 1.1},
            "fire": {"hp": 0.9, "attack": 1.2, "defense": 0.9},
            "earth": {"hp": 1.2, "attack": 0.9, "defense": 1.1},
        }.get(sect.element, {"hp": 1.0, "attack": 1.0, "defense": 1.0})

        return {
            "id": f"tournament_enemy_{sect.id}_{level}",
            "name": f"{sect.name}弟子",
            "element": sect.element,
            "level": level,
            "hp": int(base_hp * element_bonus["hp"]),
            "attack": int(base_attack * element_bonus["attack"]),
            "defense": int(base_defense * element_bonus["defense"]),
            "description": "参加宗门大比的同门弟子，实力不俗。",
            "loot": [],
            "exp": 0,
            "skills": [
                {
                    "name": "宗门招式",
                    "trigger_hp_ratio": 1.0,
                    "chance": 0.3,
                    "damage_multiplier": 1.3,
                    "description": f"{sect.name}弟子施展出宗门所学招式！",
                }
            ],
            "ai": {},
        }

    def complete_tournament(self, wins):
        """根据大比胜场发放奖励。"""
        event = self.get_sect_event("tournament")
        if not event:
            return False, "宗门大比信息异常。"

        rewards = event.rewards
        contribution = wins * rewards.get("contribution_per_win", 0)
        reputation = wins * rewards.get("reputation_per_win", 0)

        self.player.sect_contribution += contribution
        # 忠诚度随胜场小幅提升
        self.player.sect_loyalty = min(100, self.player.sect_loyalty + wins)

        # 记录参加时间，避免本月重复参加
        current_month = self.world.year * 12 + self.world.month
        self.player.sect_tournament_last_month = current_month

        msg = f"宗门大比结束，你连胜 {wins}/{event.rounds} 场，获得 {contribution} 贡献。"
        if reputation:
            msg += f" 宗门声望 +{reputation}。"

        # 全胜额外技能奖励
        bonus_skill = rewards.get("bonus_skill")
        learned_name = None
        if bonus_skill and wins >= bonus_skill.get("required_wins", event.rounds):
            skill_id = bonus_skill["skill_id"]
            skill = self.skill_library.get(skill_id)
            if skill and not self.player.has_skill(skill_id):
                if random.random() < bonus_skill.get("chance", 0):
                    self.player.learn_skill(skill_id)
                    learned_name = skill.name

        if learned_name:
            msg += f" 你在大比中表现出色，领悟了【{learned_name}】！"

        return True, msg

    # ==================== 宗门设施 ====================

    def get_facility_details(self):
        """获取玩家当前职位可使用的宗门设施列表。"""
        sect = self.get_sect()
        if not sect:
            return []
        rank_idx = self.get_rank_index(self.player.sect_rank)
        result = []
        for facility in sect.facility_details:
            required_idx = self.get_rank_index(facility.get("required_rank", "outer"))
            if rank_idx >= required_idx:
                result.append(facility)
        return result

    def _get_facility(self, facility_id):
        """根据 ID 查找当前宗门设施配置。"""
        sect = self.get_sect()
        if not sect:
            return None
        for facility in sect.facility_details:
            if facility["id"] == facility_id:
                return facility
        return None

    def can_use_facility(self, facility_id):
        """检查是否可以使用某宗门设施。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        facility = self._get_facility(facility_id)
        if not facility:
            return False, "该设施不在本宗门中。"

        rank_idx = self.get_rank_index(self.player.sect_rank)
        required_idx = self.get_rank_index(facility.get("required_rank", "outer"))
        if rank_idx < required_idx:
            required_name = sect.get_rank_name(facility["required_rank"])
            return False, f"职位不足，需【{required_name}】及以上。"

        cost = facility.get("cost", 0)
        if self.player.sect_contribution < cost:
            return False, f"贡献不足，需要 {cost} 点。"

        return True, ""

    def use_facility(self, facility_id):
        """使用宗门设施，消耗贡献并应用效果。"""
        ok, msg = self.can_use_facility(facility_id)
        if not ok:
            return False, msg

        facility = self._get_facility(facility_id)
        cost = facility["cost"]
        effects = facility.get("effects", {})

        self.player.sect_contribution -= cost
        gained_items = []

        # 立即获得物品类效果
        give_items = effects.get("give_items")
        if give_items:
            for item_id, count in give_items.items():
                for _ in range(count):
                    item = self.item_library.create(item_id)
                    if item:
                        self.player.add_item(item)
                        gained_items.append(item.name)

        # 持续类效果（如聚灵阵修炼加成、炼器室成功率加成）
        duration = effects.get("duration_months", 0)
        if duration > 0:
            active = dict(effects)
            active["remaining_months"] = duration
            active["name"] = facility["name"]
            self.player.active_facility_effects[facility_id] = active

        msg = f"你使用【{facility['name']}】，消耗 {cost} 贡献。"
        if gained_items:
            msg += f" 获得：{', '.join(gained_items)}。"
        if duration > 0:
            msg += f" 设施效果将持续 {duration} 个月。"
        return True, msg

    def get_facility_cultivation_bonus(self):
        """获取宗门设施带来的当前修炼速度加成总和。"""
        total = 0.0
        for effects in getattr(self.player, "active_facility_effects", {}).values():
            total += effects.get("cultivation_speed", 0)
        return total

    def tick_facility_effects(self, months=1):
        """推进宗门设施效果的剩余时间，到期自动移除。"""
        active = getattr(self.player, "active_facility_effects", {})
        expired = []
        for fid, effects in active.items():
            effects["remaining_months"] -= months
            if effects["remaining_months"] <= 0:
                expired.append(fid)
        for fid in expired:
            del active[fid]

    # ==================== 宗门仓库与捐献排行榜 ====================

    def donate_item(self, item_id, count=1):
        """
        向宗门捐献物品：消耗背包中的物品，换取贡献并进入宗门仓库。
        贡献 = 物品价值 × 数量 × 0.5；累计捐献价值用于排行榜。
        """
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        if count <= 0:
            return False, "捐献数量必须大于 0。"

        if self.player.count_item(item_id) < count:
            item_name = self.item_library.get(item_id)
            item_name = item_name.name if item_name else item_id
            return False, f"{item_name} 数量不足。"

        item = self.item_library.get(item_id)
        if not item:
            return False, "物品不存在。"

        # 消耗物品
        self.player.consume_items(item_id, count)
        # 计算贡献
        contribution = int(item.value * count * 0.5)
        self.player.sect_contribution += contribution
        self.player.sect_loyalty = min(100, self.player.sect_loyalty + 1)
        # 进入宗门仓库
        self.player.sect_warehouse[item_id] = self.player.sect_warehouse.get(item_id, 0) + count
        # 累计捐献价值
        self.player.sect_donation_total += item.value * count
        # 推进宗门收集任务
        self.update_task_progress("collect", item_id, count)

        msg = (
            f"你向宗门捐献【{item.name}】x{count}，获得 {contribution} 贡献，"
            f"忠诚度小幅上升。物品已存入宗门仓库。"
        )
        return True, msg

    def get_warehouse_items(self):
        """
        获取宗门仓库中的物品列表。
        返回 [(Item 对象, 数量), ...]，按物品名称排序。
        """
        result = []
        warehouse = getattr(self.player, "sect_warehouse", {})
        for item_id, count in warehouse.items():
            item = self.item_library.get(item_id)
            if item and count > 0:
                result.append((item, count))
        # 按物品名称排序，便于 UI 稳定展示
        result.sort(key=lambda x: x[0].name)
        return result

    def get_warehouse_total_value(self):
        """计算宗门仓库中所有物品的总价值。"""
        total = 0
        for item_id, count in getattr(self.player, "sect_warehouse", {}).items():
            item = self.item_library.get(item_id)
            if item:
                total += item.value * count
        return total

    # 模拟同门弟子的名字池，用于生成捐献排行榜
    _DONATION_NPC_NAMES = ["张师兄", "李师姐", "王师弟", "赵师妹", "孙执事", "周堂主"]

    def get_donation_leaderboard(self):
        """
        生成本月宗门捐献排行榜。
        返回 [{"rank": int, "name": str, "total": int, "is_player": bool}, ...]
        同门弟子的捐献额按当前游戏年月与宗门做确定性随机，保证同月内刷新结果一致。
        """
        sect = self.get_sect()
        if not sect:
            return []

        # 使用独立随机源，避免影响全局随机序列
        seed = (self.world.year * 100 + self.world.month) * 31 + hash(sect.id) % 10000
        rng = random.Random(seed)

        # 生成 4 名同门弟子
        npc_names = rng.sample(self._DONATION_NPC_NAMES, min(4, len(self._DONATION_NPC_NAMES)))
        player_total = getattr(self.player, "sect_donation_total", 0)
        # NPC 捐献上限不超过玩家，相同额度时玩家排名优先，
        # 这样高捐献可稳定争夺榜首，低捐献时仍有竞争空间
        max_npc_total = max(500, player_total)
        entries = []
        for name in npc_names:
            # 弟子捐献额在 100 到 max_npc_total 之间随机
            total = rng.randint(100, max_npc_total)
            entries.append({"name": name, "total": total, "is_player": False})

        # 插入玩家自身
        entries.append({"name": self.player.name, "total": player_total, "is_player": True})

        # 按捐献额降序排列，相同额度时玩家排在前面（提升代入感）
        entries.sort(key=lambda e: (e["total"], 1 if e["is_player"] else 0), reverse=True)

        # 分配名次
        for idx, entry in enumerate(entries, start=1):
            entry["rank"] = idx
        return entries

    def get_player_donation_rank(self):
        """获取玩家在本月捐献排行榜中的名次，未入宗返回 None。"""
        for entry in self.get_donation_leaderboard():
            if entry.get("is_player"):
                return entry["rank"]
        return None

    def check_monthly_donation_rewards(self, year, month):
        """
        检查并发放本月捐献排行榜奖励。
        每月仅结算一次，排名第一的玩家获得额外贡献与忠诚度奖励。
        返回 (是否发放奖励, 消息)。
        """
        sect = self.get_sect()
        if not sect:
            return False, ""

        current_month = year * 12 + month
        last_month = getattr(self.player, "sect_donation_last_reward_month", -1)
        if last_month >= current_month:
            return False, ""

        # 标记本月已结算
        self.player.sect_donation_last_reward_month = current_month

        rank = self.get_player_donation_rank()
        if rank == 1:
            # 排名第一奖励
            reward_contribution = 100
            self.player.sect_contribution += reward_contribution
            self.player.sect_loyalty = min(100, self.player.sect_loyalty + 5)
            return True, (
                f"本月宗门捐献排行榜公布，你位列第一！"
                f"获得 {reward_contribution} 贡献奖励，忠诚度 +5。"
            )

        return False, f"本月宗门捐献排行榜公布，你排名第 {rank}，未能获得榜首奖励。"

    # ==================== 宗门秘境/禁地探索 ====================

    def get_secret_realms(self):
        """获取玩家当前职位可探索的宗门秘境列表。"""
        sect = self.get_sect()
        if not sect:
            return []
        rank_idx = self.get_rank_index(self.player.sect_rank)
        result = []
        for realm in sect.secret_realms:
            required_idx = self.get_rank_index(realm.get("required_rank", "outer"))
            if rank_idx >= required_idx:
                result.append(realm)
        return result

    def _get_secret_realm(self, realm_id):
        """根据 ID 查找当前宗门秘境配置。"""
        sect = self.get_sect()
        if not sect:
            return None
        for realm in sect.secret_realms:
            if realm["id"] == realm_id:
                return realm
        return None

    def _get_secret_realm_cooldown(self, realm_id):
        """获取秘境可再次进入的世界月份。"""
        return getattr(self.player, "sect_secret_realm_cooldowns", {}).get(realm_id, 0)

    def can_enter_secret_realm(self, realm_id):
        """检查是否满足进入某宗门秘境的条件。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        realm = self._get_secret_realm(realm_id)
        if not realm:
            return False, "该秘境不在本宗门中。"

        rank_idx = self.get_rank_index(self.player.sect_rank)
        required_idx = self.get_rank_index(realm.get("required_rank", "outer"))
        if rank_idx < required_idx:
            required_name = sect.get_rank_name(realm["required_rank"])
            return False, f"职位不足，需【{required_name}】及以上。"

        current_month = self.world.year * 12 + self.world.month
        cooldown = self._get_secret_realm_cooldown(realm_id)
        if current_month < cooldown:
            remaining = cooldown - current_month
            return False, f"秘境尚在冷却恢复中，还需 {remaining} 个月方可再次进入。"

        if not self.player.is_alive():
            return False, "你当前状态不佳，无法进入秘境。"

        return True, ""

    def _create_secret_realm_enemy(self, realm):
        """根据秘境配置生成守关敌人（属性按玩家境界适当缩放）。"""
        enemy_id = realm.get("enemy_id")
        enemy_data = None
        if enemy_id:
            enemy_data = self.enemy_library.get(enemy_id)
        if not enemy_data:
            return None

        # 深拷贝敌人数据，避免修改模板
        data = dict(enemy_data)
        data["name"] = f"{realm.get('name', '禁地')}·{data.get('name', '守卫')}"

        # 按玩家境界提升敌人等级与属性
        player_order = self.player.REALM_ORDER.get(self.player.realm_id, 1)
        level_bonus = realm.get("enemy_level_bonus", 0)
        data["level"] = data.get("level", 1) + level_bonus + max(0, player_order - 9) // 3

        scale = 1.0 + (player_order - 1) * 0.04
        data["hp"] = int(data.get("hp", 100) * scale)
        data["attack"] = int(data.get("attack", 10) * scale)
        data["defense"] = int(data.get("defense", 2) * scale)

        return Enemy.from_dict(data)

    def enter_secret_realm(self, realm_id):
        """
        进入宗门秘境，返回 (敌人对象, 提示消息)。
        若条件不满足，返回 (None, 失败消息)。
        """
        ok, msg = self.can_enter_secret_realm(realm_id)
        if not ok:
            return None, msg

        realm = self._get_secret_realm(realm_id)
        enemy = self._create_secret_realm_enemy(realm)
        if not enemy:
            return None, "秘境守卫数据异常，无法进入。"

        return enemy, f"你进入【{realm['name']}】，遭遇 {enemy.name}！"

    def finish_secret_realm(self, realm_id, win):
        """
        秘境战斗结束后结算奖励与冷却。
        胜利时发放奖励并设置冷却；失败或逃跑时仅设置冷却。
        返回 (是否成功结算, 消息)。
        """
        realm = self._get_secret_realm(realm_id)
        if not realm:
            return False, "秘境数据异常。"

        current_month = self.world.year * 12 + self.world.month
        cooldown = realm.get("cooldown_months", 12)
        self.player.sect_secret_realm_cooldowns[realm_id] = current_month + cooldown

        if not win:
            return True, f"你未能通过【{realm['name']}】的考验，需等待 {cooldown} 个月后再来。"

        # 发放奖励
        gained_items = []
        for item_id, count in realm.get("reward_items", {}).items():
            for _ in range(count):
                item = self.item_library.create(item_id)
                if item:
                    self.player.add_item(item)
                    gained_items.append(item.name)

        reward_qi = realm.get("reward_qi", 0)
        if reward_qi:
            self.player.qi += reward_qi

        # 忠诚度小幅提升
        self.player.sect_loyalty = min(100, self.player.sect_loyalty + 2)

        item_text = "、".join(gained_items) if gained_items else "无"
        msg = (
            f"你成功通关【{realm['name']}】！\n"
            f"获得：{item_text}，修为 +{reward_qi}，忠诚度 +2。"
        )
        return True, msg

    def get_secret_realm_remaining_cooldown(self, realm_id):
        """获取秘境剩余冷却月数，未在冷却返回 0。"""
        current_month = self.world.year * 12 + self.world.month
        cooldown = self._get_secret_realm_cooldown(realm_id)
        return max(0, cooldown - current_month)

    # ==================== 弟子招募与追随者系统 ====================

    def get_follower_capacity(self):
        """根据当前宗门职位计算可拥有的追随者上限。"""
        rank_idx = self.get_rank_index(self.player.sect_rank)
        # 外门 0，内门 1，真传 2，长老 3，掌教 4
        return max(0, rank_idx)

    def get_recruitable_followers(self):
        """获取当前宗门中玩家职位可招募的追随者模板。"""
        sect = self.get_sect()
        if not sect:
            return []
        rank_idx = self.get_rank_index(self.player.sect_rank)
        result = []
        for template in self.follower_library.get_by_sect(sect.id):
            required_idx = self.get_rank_index(template.get("required_rank", "outer"))
            if rank_idx >= required_idx:
                result.append(template)
        return result

    def can_recruit_follower(self, follower_id):
        """检查是否可以招募指定追随者。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        template = self.follower_library.get(follower_id)
        if not template:
            return False, "追随者模板不存在。"

        if template.get("sect_id") != sect.id:
            return False, "该追随者不属于你当前宗门。"

        rank_idx = self.get_rank_index(self.player.sect_rank)
        required_idx = self.get_rank_index(template.get("required_rank", "outer"))
        if rank_idx < required_idx:
            required_name = sect.get_rank_name(template["required_rank"])
            return False, f"职位不足，需【{required_name}】及以上。"

        capacity = self.get_follower_capacity()
        if len(self.player.followers) >= capacity:
            return False, f"追随者数量已达上限（{capacity} 名），提升职位可增加名额。"

        # 检查是否已招募
        if any(f.get("id") == follower_id for f in self.player.followers):
            return False, "该追随者已在你身边。"

        cost = template.get("cost_contribution", 0)
        if self.player.sect_contribution < cost:
            return False, f"宗门贡献不足，需要 {cost} 贡献。"

        return True, ""

    def recruit_follower(self, follower_id):
        """招募追随者，消耗贡献并加入玩家追随者列表。"""
        ok, msg = self.can_recruit_follower(follower_id)
        if not ok:
            return False, msg

        template = self.follower_library.get(follower_id)
        cost = template.get("cost_contribution", 0)
        self.player.sect_contribution -= cost

        follower = {
            "id": template["id"],
            "name": template["name"],
            "element": template.get("element", "none"),
            "path": template.get("path", "fa"),
            "description": template.get("description", ""),
            "loyalty": 60,  # 初始忠诚度 60
            "status": "idle",  # idle / mission
            "mission_end_month": -1,
            "passive_bonus": dict(template.get("passive_bonus", {})),
            "mission": dict(template.get("mission", {})) if template.get("mission") else {},
        }
        self.player.followers.append(follower)
        return True, f"你成功招募【{follower['name']}】为追随者，消耗 {cost} 贡献。"

    def get_follower_passive_bonus(self):
        """计算所有追随者提供的被动修炼加成总和。"""
        total = 0.0
        for follower in getattr(self.player, "followers", []):
            if follower.get("status") == "idle":
                total += follower.get("passive_bonus", {}).get("cultivation_speed", 0.0)
        return total

    def can_dispatch_follower(self, follower_id):
        """检查是否可以派遣追随者执行任务。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        for follower in self.player.followers:
            if follower.get("id") == follower_id:
                if follower.get("status") == "mission":
                    return False, "该追随者正在执行任务中。"
                if not follower.get("mission"):
                    return False, "该追随者没有可执行的任务。"
                return True, ""
        return False, "追随者不在身边。"

    def dispatch_follower(self, follower_id):
        """派遣追随者外出执行任务，并设置回归月份。"""
        ok, msg = self.can_dispatch_follower(follower_id)
        if not ok:
            return False, msg

        for follower in self.player.followers:
            if follower.get("id") == follower_id:
                duration = follower.get("mission", {}).get("duration_months", 6)
                current_month = self.world.year * 12 + self.world.month
                follower["status"] = "mission"
                follower["mission_end_month"] = current_month + duration
                return True, f"你派遣【{follower['name']}】外出执行任务，预计 {duration} 个月后归来。"
        return False, "追随者不在身边。"

    def get_follower_remaining_months(self, follower):
        """获取某追随者任务剩余月数，未在任务中返回 0。"""
        if follower.get("status") != "mission":
            return 0
        current_month = self.world.year * 12 + self.world.month
        return max(0, follower.get("mission_end_month", -1) - current_month)

    def tick_followers(self, year, month):
        """
        推进追随者任务倒计时，任务完成时发放奖励并返回消息列表。
        由 Engine 在每月推进时调用。
        """
        current_month = year * 12 + month
        messages = []
        for follower in getattr(self.player, "followers", []):
            if follower.get("status") != "mission":
                continue
            if current_month >= follower.get("mission_end_month", -1):
                # 任务完成，发放奖励
                follower["status"] = "idle"
                follower["mission_end_month"] = -1
                follower["loyalty"] = min(100, follower.get("loyalty", 60) + 5)

                reward_items = follower.get("mission", {}).get("reward_items", {})
                gained = []
                for item_id, count in reward_items.items():
                    for _ in range(count):
                        item = self.item_library.create(item_id)
                        if item:
                            self.player.add_item(item)
                            gained.append(item.name)

                item_text = "、".join(gained) if gained else "无"
                messages.append(
                    f"【追随者】{follower['name']} 完成任务归来，带回 {item_text}，忠诚度 +5。"
                )
        return messages

    # ==================== 宗门外交任务 ====================

    def get_available_diplomatic_missions(self):
        """根据当前宗门关系状态，返回可接取的外交任务模板列表。"""
        sect = self.get_sect()
        if not sect:
            return []

        result = []
        rank_idx = self.get_rank_index(self.player.sect_rank)
        for mission in self.diplomatic_mission_library.all_missions():
            required_idx = self.get_rank_index(mission.get("required_rank", "outer"))
            if rank_idx < required_idx:
                continue
            target_relation = mission.get("target_relation", "neutral")
            # 找到至少一个符合目标关系状态的宗门
            for other in self.sect_library.all_sects():
                if other.id == sect.id:
                    continue
                if self.get_relation_status(other.id) == target_relation:
                    result.append(mission)
                    break
        return result

    def can_accept_diplomatic_mission(self, mission_id, target_sect_id):
        """检查是否可以接取指定外交任务并指定目标宗门。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        mission = self.diplomatic_mission_library.get(mission_id)
        if not mission:
            return False, "外交任务不存在。"

        if getattr(self.player, "sect_diplomatic_mission", None):
            return False, "你已有进行中的外交任务。"

        rank_idx = self.get_rank_index(self.player.sect_rank)
        required_idx = self.get_rank_index(mission.get("required_rank", "outer"))
        if rank_idx < required_idx:
            required_name = sect.get_rank_name(mission["required_rank"])
            return False, f"职位不足，需【{required_name}】及以上。"

        target = self.sect_library.get(target_sect_id)
        if not target:
            return False, "目标宗门不存在。"
        if target.id == sect.id:
            return False, "不能对本宗门执行外交任务。"

        expected_relation = mission.get("target_relation", "neutral")
        actual_relation = self.get_relation_status(target.id)
        if actual_relation != expected_relation:
            return False, "目标宗门关系类型与任务要求不符。"

        cost = mission.get("cost_contribution", 0)
        if self.player.sect_contribution < cost:
            return False, f"宗门贡献不足，需要 {cost} 贡献。"

        return True, ""

    def accept_diplomatic_mission(self, mission_id, target_sect_id):
        """接取外交任务，消耗贡献并设置任务结束月份。"""
        ok, msg = self.can_accept_diplomatic_mission(mission_id, target_sect_id)
        if not ok:
            return False, msg

        mission = self.diplomatic_mission_library.get(mission_id)
        cost = mission.get("cost_contribution", 0)
        self.player.sect_contribution -= cost

        current_month = self.world.year * 12 + self.world.month
        duration = mission.get("duration_months", 6)
        self.player.sect_diplomatic_mission = {
            "mission_id": mission_id,
            "target_sect_id": target_sect_id,
            "end_month": current_month + duration,
        }
        target_name = self.sect_library.get(target_sect_id).name
        return True, (
            f"你接取外交任务【{mission['name']}】，目标宗门：{target_name}，"
            f"预计 {duration} 个月后回报结果。"
        )

    def tick_diplomatic_mission(self, year, month):
        """
        推进外交任务倒计时，到期后判定成败并结算。
        返回消息列表，由 Engine 通知玩家。
        """
        active = getattr(self.player, "sect_diplomatic_mission", None)
        if not active:
            return []

        current_month = year * 12 + month
        if current_month < active.get("end_month", -1):
            return []

        mission = self.diplomatic_mission_library.get(active.get("mission_id"))
        target_sect_id = active.get("target_sect_id")
        self.player.sect_diplomatic_mission = None

        if not mission:
            return ["【外交任务】任务记录异常，已取消。"]

        target = self.sect_library.get(target_sect_id)
        target_name = target.name if target else "未知宗门"
        success = random.random() < mission.get("success_rate", 0.5)

        messages = []
        if success:
            # 调整关系值
            delta = mission.get("relation_delta", 0)
            self.adjust_sect_relationship(target_sect_id, delta)
            # 奖励
            reward_contribution = mission.get("reward_contribution", 0)
            reward_loyalty = mission.get("reward_loyalty", 0)
            self.player.sect_contribution += reward_contribution
            self.player.sect_loyalty = min(100, self.player.sect_loyalty + reward_loyalty)
            # 根据任务类型调整阵营值
            self.apply_camp_rewards(mission=active)
            rel_word = "提升" if delta > 0 else "降低"
            messages.append(
                f"【外交任务】{mission['name']} 成功！与【{target_name}】关系 {rel_word} {abs(delta)}，"
                f"获得 {reward_contribution} 贡献，忠诚度 +{reward_loyalty}。"
            )
        else:
            # 失败时关系向反方向微调（成功是 + 则失败为 -，反之亦然）
            delta = mission.get("relation_delta", 0)
            fail_delta = -int(delta * 0.3) if delta != 0 else 0
            if fail_delta != 0:
                self.adjust_sect_relationship(target_sect_id, fail_delta)
            messages.append(
                f"【外交任务】{mission['name']} 失败，与【{target_name}】关系变化不及预期。"
            )

        return messages

    def cancel_diplomatic_mission(self):
        """取消当前外交任务，不退还贡献。"""
        active = getattr(self.player, "sect_diplomatic_mission", None)
        if not active:
            return False, "没有进行中的外交任务。"
        self.player.sect_diplomatic_mission = None
        return True, "你已取消当前外交任务。"

    # ==================== 宗门悬赏榜 ====================

    def get_bounty_board(self):
        """获取玩家当前职位可接取的悬赏任务列表。"""
        sect = self.get_sect()
        if not sect:
            return []
        rank_idx = self.get_rank_index(self.player.sect_rank)
        result = []
        for bounty in sect.bounty_board:
            required_idx = self.get_rank_index(bounty.get("required_rank", "outer"))
            if rank_idx >= required_idx:
                result.append(bounty)
        return result

    def _get_bounty(self, bounty_id):
        """根据 ID 在当前宗门悬赏榜中查找悬赏任务。"""
        sect = self.get_sect()
        if not sect:
            return None
        for bounty in sect.bounty_board:
            if bounty["id"] == bounty_id:
                return bounty
        return None

    def can_accept_bounty(self, bounty_id):
        """检查是否可接取指定悬赏任务。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        if getattr(self.player, "sect_active_bounty", None):
            return False, "你已有一个进行中的悬赏任务。"

        bounty = self._get_bounty(bounty_id)
        if not bounty:
            return False, "该悬赏不存在。"

        rank_idx = self.get_rank_index(self.player.sect_rank)
        required_idx = self.get_rank_index(bounty.get("required_rank", "outer"))
        if rank_idx < required_idx:
            required_name = sect.get_rank_name(bounty["required_rank"])
            return False, f"职位不足，需【{required_name}】及以上。"

        return True, ""

    def accept_bounty(self, bounty_id):
        """接取悬赏任务。"""
        ok, msg = self.can_accept_bounty(bounty_id)
        if not ok:
            return False, msg

        bounty = self._get_bounty(bounty_id)
        self.player.sect_active_bounty = {
            "bounty_id": bounty_id,
            "target_enemy": bounty["target_enemy"],
            "target_count": bounty.get("target_count", 1),
            "progress": 0,
        }
        return True, f"你接取悬赏任务【{bounty['name']}】：击败 {bounty.get('target_count', 1)} 名目标。"

    def update_bounty_progress(self, enemy_id):
        """战斗胜利后更新悬赏击杀进度，达到目标时自动完成并发放奖励。"""
        active = getattr(self.player, "sect_active_bounty", None)
        if not active:
            return None

        if active.get("target_enemy") != enemy_id:
            return None

        active["progress"] = active.get("progress", 0) + 1
        if active["progress"] >= active.get("target_count", 1):
            return self.complete_bounty()
        return None

    def complete_bounty(self):
        """完成当前悬赏任务并发放奖励。"""
        active = getattr(self.player, "sect_active_bounty", None)
        if not active:
            return False, "没有进行中的悬赏任务。"

        bounty = self._get_bounty(active["bounty_id"])
        if not bounty:
            self.player.sect_active_bounty = None
            return False, "悬赏数据异常，已取消。"

        # 发放贡献
        contribution = bounty.get("contribution_reward", 0)
        reputation = bounty.get("reputation_reward", 0)
        self.player.sect_contribution += contribution
        self.player.sect_loyalty = min(100, self.player.sect_loyalty + 2)

        # 发放物品奖励
        gained_items = []
        for item_id, count in bounty.get("item_reward", {}).items():
            for _ in range(count):
                item = self.item_library.create(item_id)
                if item:
                    self.player.add_item(item)
                    gained_items.append(item.name)

        self.player.sect_active_bounty = None
        item_text = "、".join(gained_items) if gained_items else "无"
        return True, (
            f"完成悬赏【{bounty['name']}】！贡献 +{contribution}，"
            f"宗门声望 +{reputation}，获得 {item_text}。"
        )

    # ==================== 宗门气运/运势事件 ====================

    def get_fortune_events(self):
        """获取当前宗门的气运事件配置列表。"""
        sect = self.get_sect()
        if not sect:
            return []
        return sect.fortune_events

    def tick_fortune_event(self, year, month):
        """
        推进宗门气运事件：到期移除，并按月概率触发新事件。
        返回消息列表，由 Engine 通知玩家。
        """
        messages = []
        current_month = year * 12 + month

        # 检查当前事件是否到期
        active = getattr(self.player, "active_sect_fortune", None)
        if active and current_month >= active.get("end_month", -1):
            self.player.active_sect_fortune = None
            messages.append(f"【宗门气运】{active.get('name', '未知气运')} 已结束。")

        # 当前无事件时，按概率触发新事件
        if not getattr(self.player, "active_sect_fortune", None):
            events = self.get_fortune_events()
            if events and random.random() < 0.3:  # 每月 30% 概率触发
                total_weight = sum(e.get("weight", 10) for e in events)
                pick = random.uniform(0, total_weight)
                chosen = None
                accumulated = 0
                for event in events:
                    accumulated += event.get("weight", 10)
                    if accumulated >= pick:
                        chosen = event
                        break

                if chosen:
                    duration = chosen.get("duration_months", 3)
                    self.player.active_sect_fortune = {
                        "event_id": chosen["id"],
                        "name": chosen["name"],
                        "end_month": current_month + duration,
                        "effects": dict(chosen.get("effects", {})),
                    }
                    messages.append(
                        f"【宗门气运】{chosen['name']} 降临！{chosen.get('description', '')}"
                    )

        return messages

    def get_active_fortune_effects(self):
        """获取当前生效的气运事件效果字典。"""
        active = getattr(self.player, "active_sect_fortune", None)
        if not active:
            return {}
        return active.get("effects", {})

    def get_fortune_cultivation_bonus(self):
        """获取气运事件带来的修炼速度加成。"""
        return self.get_active_fortune_effects().get("cultivation_speed_bonus", 0.0)

    def get_fortune_shop_discount(self):
        """获取气运事件带来的商店折扣倍率（与宗门关系折扣叠加为乘积）。"""
        return self.get_active_fortune_effects().get("shop_discount", 1.0)

    def get_fortune_task_reward_bonus(self):
        """获取气运事件带来的任务奖励加成比例。"""
        return self.get_active_fortune_effects().get("task_reward_bonus", 0.0)

    def get_fortune_enemy_strength_bonus(self):
        """获取气运事件带来的敌人强度加成。"""
        return self.get_active_fortune_effects().get("enemy_strength_bonus", 0.0)

    def get_available_tasks(self):
        """获取玩家当前可接取的宗门任务。"""
        sect = self.get_sect()
        if not sect:
            return []
        return SectTaskLibrary().get_available_tasks(self.player.sect_rank)

    def get_daily_limit(self):
        """获取当前职位的每日任务上限。"""
        sect = self.get_sect()
        if not sect:
            return 0
        return sect.get_rank_info(self.player.sect_rank).get("daily_task_limit", 0)

    def accept_task(self, task_id):
        """接取宗门任务。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入宗门。"

        if self.player.sect_tasks_today >= self.get_daily_limit():
            return False, "今日宗门任务已达上限。"

        if self.player.sect_active_task:
            return False, "你已有一个进行中的宗门任务，请先完成。"

        task = SectTaskLibrary().get(task_id)
        if not task:
            return False, "任务不存在。"

        self.player.sect_active_task = {
            "task_id": task_id,
            "progress": 0,
        }
        return True, f"接取宗门任务：【{task.name}】"

    def complete_task(self):
        """完成当前宗门任务。"""
        if not self.player.sect_active_task:
            return False, "没有进行中的宗门任务。"

        task = SectTaskLibrary().get(self.player.sect_active_task["task_id"])
        if not task:
            self.player.sect_active_task = None
            return False, "任务数据异常。"

        # 检查目标是否达成
        progress = self.player.sect_active_task["progress"]
        if progress < task.target_count:
            return False, f"任务进度不足（{progress}/{task.target_count}）。"

        # 收集类任务需要上缴物品
        if task.type == "collect":
            have = self.player.count_item(task.target_item)
            if have < task.target_count:
                item_name = self.item_library.get(task.target_item).name
                return False, f"{item_name} 数量不足（{have}/{task.target_count}），无法完成任务。"
            self.player.consume_items(task.target_item, task.target_count)

        # 应用气运事件的任务奖励加成
        reward_bonus = 1.0 + self.get_fortune_task_reward_bonus()
        contribution = int(task.contribution_reward * reward_bonus)
        reputation = int(task.reputation_reward * reward_bonus)

        # 击杀类任务根据目标类型调整阵营值
        if task.type == "kill" and task.target_enemy:
            killed_righteous = "righteous" in task.target_enemy
            self.apply_camp_rewards(enemy_id=task.target_enemy, killed_righteous=killed_righteous)

        # 发放奖励
        self.player.sect_contribution += contribution
        self.player.sect_loyalty = min(100, self.player.sect_loyalty + 2)
        self.player.sect_tasks_today += 1

        for item_id, count in task.item_reward.items():
            for _ in range(count):
                item = self.item_library.create(item_id)
                if item:
                    self.player.add_item(item)

        self.player.sect_active_task = None
        return True, (
            f"完成【{task.name}】，贡献 +{contribution}，"
            f"宗门声望 +{reputation}。"
        )

    def update_task_progress(self, task_type, target_id, amount=1):
        """
        更新宗门任务进度。
        task_type: kill / collect / explore
        target_id: 敌人/物品/地点 ID
        """
        if not self.player.sect_active_task:
            return
        task = SectTaskLibrary().get(self.player.sect_active_task["task_id"])
        if not task:
            return

        match = False
        if task.type == "kill" and task_type == "kill" and task.target_enemy == target_id:
            match = True
        elif task.type == "collect" and task_type == "collect" and task.target_item == target_id:
            match = True
        elif task.type == "explore" and task_type == "explore" and task.target_location == target_id:
            match = True

        if match:
            self.player.sect_active_task["progress"] = min(
                task.target_count,
                self.player.sect_active_task["progress"] + amount,
            )

    def buy_shop_item(self, item_id):
        """用贡献兑换宗门商店物品。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入宗门。"

        shop_item = None
        for si in sect.shop_items:
            if si["item_id"] == item_id:
                shop_item = si
                break
        if not shop_item:
            return False, "该物品不在宗门商店中。"

        # 计算最终价格：宗门关系折扣 × 气运事件折扣 × 同盟折扣
        base_cost = shop_item["cost"]
        relation_discount = self.get_shop_discount()
        fortune_discount = self.get_fortune_shop_discount()
        alliance_discount = 1.0 - self.get_alliance_shop_discount(sect.id)
        cost = max(1, int(base_cost * relation_discount * fortune_discount * alliance_discount))

        if self.player.sect_contribution < cost:
            return False, f"贡献不足，需要 {cost} 点。"

        item = self.item_library.create(item_id)
        if not item:
            return False, "物品创建失败。"

        self.player.sect_contribution -= cost
        self.player.add_item(item)
        return True, f"花费 {cost} 贡献兑换【{item.name}】。"

    def learn_scripture_skill(self, skill_id):
        """用功法阁学习宗门技能。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入宗门。"

        scripture = None
        for sc in sect.scripture_skills:
            if sc["skill_id"] == skill_id:
                scripture = sc
                break
        if not scripture:
            return False, "该功法不在藏经阁中。"

        # 检查职位
        rank_idx = self.get_rank_index(self.player.sect_rank)
        required_idx = self.get_rank_index(scripture["required_rank"])
        if rank_idx < required_idx:
            return False, "职位不足，无法学习该功法。"

        # 检查贡献
        cost = scripture["cost"]
        if self.player.sect_contribution < cost:
            return False, f"贡献不足，需要 {cost} 点。"

        # 检查是否已学会
        if self.player.has_skill(skill_id):
            return False, "你已经学会该技能。"

        skill = self.skill_library.get(skill_id)
        if not skill:
            return False, "技能不存在。"

        self.player.sect_contribution -= cost
        self.player.learn_skill(skill_id)
        return True, f"花费 {cost} 贡献习得【{skill.name}】。"


    # ==================== 宗门传承与祖师堂 ====================

    def get_inheritance_list(self):
        """获取当前宗门的祖师堂传承列表。"""
        sect = self.get_sect()
        if not sect:
            return []
        return getattr(sect, "inheritance", [])

    def _get_inheritance(self, inheritance_id):
        """根据 ID 查找传承配置。"""
        for inh in self.get_inheritance_list():
            if inh.get("id") == inheritance_id:
                return inh
        return None

    def can_learn_inheritance(self, inheritance_id):
        """
        检查玩家是否满足参悟传承的条件：
        已加入宗门、职位足够、本月次数未超限、
        贡献与忠诚度足够、未重复学习。
        """
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"
        inh = self._get_inheritance(inheritance_id)
        if not inh:
            return False, "传承不存在。"
        if inheritance_id in self.player.learned_inheritances:
            return False, "你已经参悟过该传承。"
        required = inh.get("required_rank", "inner")
        if self.get_rank_index(self.player.sect_rank) < self.get_rank_index(required):
            return False, f"需要职位：{sect.get_rank_name(required)}"
        if self.player.ancestral_hall_monthly_count >= inh.get("max_monthly", 1):
            return False, "本月参悟次数已用尽。"
        if self.player.sect_contribution < inh.get("cost_contribution", 0):
            return False, "宗门贡献不足。"
        if self.player.sect_loyalty < inh.get("cost_loyalty", 0):
            return False, "宗门忠诚度不足。"
        return True, ""

    def learn_inheritance(self, inheritance_id):
        """参悟传承，扣除消耗并应用奖励。"""
        ok, msg = self.can_learn_inheritance(inheritance_id)
        if not ok:
            return False, msg
        inh = self._get_inheritance(inheritance_id)
        cost_con = inh.get("cost_contribution", 0)
        cost_loy = inh.get("cost_loyalty", 0)
        rewards = inh.get("rewards", {})
        # 扣除消耗
        self.player.sect_contribution -= cost_con
        self.player.sect_loyalty -= cost_loy
        self.player.ancestral_hall_monthly_count += 1
        self.player.learned_inheritances.append(inheritance_id)
        # 应用奖励
        result_parts = []
        if "permanent_attack" in rewards:
            self.player.base_attack += rewards["permanent_attack"]
            result_parts.append(f"攻击永久 +{rewards['permanent_attack']}")
        if "permanent_defense" in rewards:
            self.player.base_defense += rewards["permanent_defense"]
            result_parts.append(f"防御永久 +{rewards['permanent_defense']}")
        if "qi" in rewards:
            self.player.qi += rewards["qi"]
            result_parts.append(f"修为 +{rewards['qi']}")
        if "skill_id" in rewards:
            skill_id = rewards["skill_id"]
            skill = self.skill_library.get(skill_id)
            if skill and not self.player.has_skill(skill_id):
                self.player.learn_skill(skill_id)
                result_parts.append(f"习得技能【{skill.name}】")
        reward_text = "、".join(result_parts) if result_parts else "无"
        return True, f"你参悟了【{inh['name']}】，{reward_text}。"

    def reset_ancestral_hall_monthly_count(self):
        """重置本月祖师堂参悟次数。"""
        self.player.ancestral_hall_monthly_count = 0

    def get_cultivation_bonus(self):
        """获取宗门洞府带来的修炼速度加成。"""
        sect = self.get_sect()
        if not sect:
            return 0.0
        return sect.get_cave_bonus(self.player.sect_rank).get("cultivation_speed", 0)

    def is_hostile_to(self, other_sect_id):
        """判断玩家所在宗门是否与目标宗门敌对。"""
        sect = self.get_sect()
        if not sect:
            return False
        return other_sect_id in sect.hostile_to



    # ==================== 宗门关系与外交 ====================

    def _sect_rel_key(self, sect_id):
        """生成宗门关系在 player.npc_relationships 中的键。"""
        return f"sect_{sect_id}"

    def get_sect_relationship(self, sect_id):
        """获取玩家与某宗门的关系值（-100 到 100，默认 0）。"""
        key = self._sect_rel_key(sect_id)
        return self.player.npc_relationships.get(key, 0)

    def set_sect_relationship(self, sect_id, value):
        """设置玩家与某宗门的关系值，并限制范围。"""
        key = self._sect_rel_key(sect_id)
        self.player.npc_relationships[key] = max(-100, min(100, value))

    def adjust_sect_relationship(self, sect_id, delta):
        """调整与某宗门的关系值。"""
        old = self.get_sect_relationship(sect_id)
        self.set_sect_relationship(sect_id, old + delta)
        return self.get_sect_relationship(sect_id)

    def get_relation_status(self, sect_id):
        """
        判断玩家与目标宗门的关系状态。
        宗门关系为双向：任一宗门将对方列入 hostile_to / friendly_to 即生效。
        再叠加玩家个人关系值进行微调。
        返回 'hostile'（敌对）、'friendly'（友好）、'neutral'（中立）。
        """
        sect = self.get_sect()
        if sect and sect.id == sect_id:
            return "friendly"

        # 配置层面敌对/友好（双向检查）
        config_status = "neutral"
        player_sect = self.get_sect()
        target_sect = self.sect_library.get(sect_id)
        if player_sect and target_sect:
            # 任一方向声明敌对即为敌对
            if (sect_id in player_sect.hostile_to or
                    player_sect.id in target_sect.hostile_to):
                config_status = "hostile"
            # 敌对优先；未敌对时，任一方向声明友好即为友好
            elif (sect_id in player_sect.friendly_to or
                  player_sect.id in target_sect.friendly_to):
                config_status = "friendly"

        # 玩家个人关系值微调（可覆盖配置层面的中立）
        rel = self.get_sect_relationship(sect_id)
        if rel <= -50:
            return "hostile"
        if rel >= 50:
            return "friendly"
        return config_status

    def get_friendly_sects(self):
        """获取与玩家宗门友好的宗门 ID 列表。"""
        return [sid for sid in self.sect_library.sects if self.get_relation_status(sid) == "friendly"]

    def get_hostile_sects(self):
        """获取与玩家宗门敌对的宗门 ID 列表。"""
        return [sid for sid in self.sect_library.sects if self.get_relation_status(sid) == "hostile"]

    def get_shop_discount(self, sect_id=None):
        """
        获取宗门商店购买折扣倍率。
        对友好宗门应用 friendly_discount；自身宗门无折扣；敌对宗门无法购买。
        此外，玩家阵营与目标宗门阵营一致时额外九折（最低 0.7）。
        """
        sect = self.get_sect()
        if not sect:
            return 1.0
        target_id = sect_id or sect.id
        if target_id == sect.id:
            discount = 1.0
        else:
            status = self.get_relation_status(target_id)
            discount = 1.0
            if status == "friendly":
                target = self.sect_library.get(target_id)
                if target:
                    discount = target.friendly_discount

        # 阵营一致额外折扣
        target = self.sect_library.get(target_id)
        if target and target.alignment == self.player.get_camp():
            discount = max(0.7, discount * 0.9)
        return discount

    # ==================== 正道 / 魔道阵营值 ====================

    def get_sect_alignment(self, sect_id=None):
        """获取某宗门阵营，未指定则返回玩家当前宗门阵营。"""
        sid = sect_id or getattr(self.get_sect(), "id", None)
        if not sid:
            return "neutral"
        sect = self.sect_library.get(sid)
        return sect.alignment if sect else "neutral"

    def adjust_camp_value(self, righteous=0, evil=0):
        """统一调整玩家正道/魔道阵营值。"""
        if righteous:
            self.player.adjust_righteous(righteous)
        if evil:
            self.player.adjust_evil(evil)

    def apply_camp_rewards(self, mission=None, enemy_id=None, killed_righteous=False):
        """
        根据行为调整阵营值。
        - 完成外交任务：友好/结交任务加正道，破坏任务加魔道
        - 击杀敌人：默认加正道； killed_righteous=True 时加魔道
        """
        if mission:
            mid = mission.get("mission_id", "")
            # 破坏敌对宗门属于魔道行为
            if "sabotage" in mid:
                self.adjust_camp_value(evil=20)
            # 结交友好宗门属于正道行为
            elif "gift_to_friend" in mid:
                self.adjust_camp_value(righteous=20)
            # 游说中立为轻微正道
            elif "mediate_neutral" in mid:
                self.adjust_camp_value(righteous=10)

        if enemy_id:
            if killed_righteous:
                self.adjust_camp_value(evil=15)
            else:
                self.adjust_camp_value(righteous=10)

    def get_camp_combat_multiplier(self, enemy=None):
        """
        根据玩家阵营与敌人阵营返回伤害倍率。
        正道对魔道 +10%，魔道对正道 +10%，阵营相同无额外。
        """
        player_camp = self.player.get_camp()
        if player_camp == "neutral":
            return 1.0
        # 敌人阵营：优先读取敌人 cultivation_path 为 xie 视为魔道，否则按所在宗门判断
        enemy_camp = "neutral"
        if enemy:
            if getattr(enemy, "cultivation_path", None) == "xie":
                enemy_camp = "evil"
            elif getattr(enemy, "element", None) == "fire" and getattr(enemy, "id", "").startswith("xie"):
                enemy_camp = "evil"
            else:
                # 根据当前所在地点推断宗门阵营
                loc = self.world.get_location(self.player.location_id)
                if loc:
                    sect = self.sect_library.get_by_location(loc.get("id"))
                    if sect:
                        enemy_camp = sect.alignment
        if player_camp == "righteous" and enemy_camp == "evil":
            return 1.1
        if player_camp == "evil" and enemy_camp == "righteous":
            return 1.1
        return 1.0

    # ==================== 宗门护山大阵 ====================

    def get_protective_formation(self):
        """获取当前宗门护山大阵配置。"""
        sect = self.get_sect()
        if not sect:
            return None
        return sect.protective_formation

    def is_in_sect_location(self):
        """判断玩家是否位于本宗门领地。"""
        sect = self.get_sect()
        if not sect:
            return False
        return self.player.location_id == sect.location_id

    def can_activate_formation(self):
        """检查是否可激活护山大阵。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"
        formation = sect.protective_formation
        if not formation:
            return False, "本宗门没有护山大阵。"
        if self.player.sect_formation_active:
            return False, "护山大阵已经激活。"
        cost = formation.get("activation_cost", 500)
        if self.player.sect_contribution < cost:
            return False, f"激活大阵需要 {cost} 贡献。"
        if not self.is_in_sect_location():
            return False, "需返回宗门领地方可激活大阵。"
        return True, ""

    def activate_formation(self):
        """激活护山大阵，消耗贡献并充满能量。"""
        ok, msg = self.can_activate_formation()
        if not ok:
            return False, msg
        formation = self.get_protective_formation()
        cost = formation.get("activation_cost", 500)
        self.player.sect_contribution -= cost
        self.player.sect_formation_active = True
        self.player.sect_formation_energy = formation.get("max_energy", 1000)
        return True, f"【{formation.get('name')}】已激活，山门笼罩在阵法光辉之中。"

    def deactivate_formation(self):
        """关闭护山大阵。"""
        if not self.player.sect_formation_active:
            return False, "护山大阵未激活。"
        self.player.sect_formation_active = False
        return True, "你已关闭护山大阵。"

    def tick_formation(self, months=1):
        """
        每月维护护山大阵：扣除维护贡献并衰减能量。
        贡献不足或能量耗尽时自动关闭。
        返回消息列表。
        """
        messages = []
        if not self.player.sect_formation_active:
            return messages

        formation = self.get_protective_formation()
        if not formation:
            self.player.sect_formation_active = False
            return messages

        monthly_cost = formation.get("monthly_cost", 50)
        decay = formation.get("energy_decay", 10) * months
        total_cost = monthly_cost * months

        # 能量衰减
        self.player.sect_formation_energy = max(0, self.player.sect_formation_energy - decay)

        # 贡献不足时关闭
        if self.player.sect_contribution < total_cost:
            self.player.sect_formation_active = False
            messages.append("【护山大阵】宗门贡献不足，大阵已自动关闭。")
            return messages

        self.player.sect_contribution -= total_cost

        # 能量耗尽时关闭
        if self.player.sect_formation_energy <= 0:
            self.player.sect_formation_active = False
            messages.append("【护山大阵】阵法能量耗尽，已自动关闭。")

        return messages

    def get_formation_cultivation_bonus(self):
        """护山大阵带来的修炼速度加成（仅在宗门领地且激活时生效）。"""
        if not self.player.sect_formation_active or not self.is_in_sect_location():
            return 0.0
        formation = self.get_protective_formation()
        return formation.get("cultivation_speed_bonus", 0.0) if formation else 0.0

    def get_formation_defense_bonus(self):
        """护山大阵带来的玩家防御加成比例（仅在宗门领地且激活时生效）。"""
        if not self.player.sect_formation_active or not self.is_in_sect_location():
            return 0.0
        formation = self.get_protective_formation()
        return formation.get("defense_bonus", 0.0) if formation else 0.0

    def get_formation_enemy_damage_reduction(self):
        """护山大阵削弱敌人伤害的比例（仅在宗门领地且激活时生效）。"""
        if not self.player.sect_formation_active or not self.is_in_sect_location():
            return 0.0
        formation = self.get_protective_formation()
        return formation.get("enemy_damage_reduction", 0.0) if formation else 0.0

    # ==================== 真传洞府系统 ====================

    def get_cave_bonus(self):
        """
        获取完整洞府加成，包含职位洞府与灵脉控制加成。
        返回 {"cultivation_speed": float, "max_qi_bonus": int}
        """
        sect = self.get_sect()
        if not sect:
            return {"cultivation_speed": 0.0, "max_qi_bonus": 0}

        base = sect.get_cave_bonus(self.player.sect_rank)
        result = {
            "cultivation_speed": base.get("cultivation_speed", 0.0),
            "max_qi_bonus": base.get("max_qi_bonus", 0),
        }

        # 加上玩家宗门控制的所有灵脉加成（包括从其他宗门夺取的灵脉）
        for other_sect in self.sect_library.all_sects():
            for vein in other_sect.spirit_veins:
                if vein.get("controlled_by") == sect.id:
                    result["cultivation_speed"] += vein.get("bonus", 0.0)

        # 洞府升级额外加成（通过贡献升级，存储在 player.cave_upgrade_level 中）
        upgrade_level = getattr(self.player, "cave_upgrade_level", 0)
        result["cultivation_speed"] += upgrade_level * 0.02
        result["max_qi_bonus"] += upgrade_level * 10

        return result


    # ==================== 宗门传承与祖师堂 ====================

    def get_inheritance_list(self):
        """获取当前宗门的祖师堂传承列表。"""
        sect = self.get_sect()
        if not sect:
            return []
        return getattr(sect, "inheritance", [])

    def _get_inheritance(self, inheritance_id):
        """根据 ID 查找传承配置。"""
        for inh in self.get_inheritance_list():
            if inh.get("id") == inheritance_id:
                return inh
        return None

    def can_learn_inheritance(self, inheritance_id):
        """
        检查玩家是否满足参悟传承的条件：
        已加入宗门、职位足够、本月次数未超限、
        贡献与忠诚度足够、未重复学习。
        """
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"
        inh = self._get_inheritance(inheritance_id)
        if not inh:
            return False, "传承不存在。"
        if inheritance_id in self.player.learned_inheritances:
            return False, "你已经参悟过该传承。"
        required = inh.get("required_rank", "inner")
        if self.get_rank_index(self.player.sect_rank) < self.get_rank_index(required):
            return False, f"需要职位：{sect.get_rank_name(required)}"
        if self.player.ancestral_hall_monthly_count >= inh.get("max_monthly", 1):
            return False, "本月参悟次数已用尽。"
        if self.player.sect_contribution < inh.get("cost_contribution", 0):
            return False, "宗门贡献不足。"
        if self.player.sect_loyalty < inh.get("cost_loyalty", 0):
            return False, "宗门忠诚度不足。"
        return True, ""

    def learn_inheritance(self, inheritance_id):
        """参悟传承，扣除消耗并应用奖励。"""
        ok, msg = self.can_learn_inheritance(inheritance_id)
        if not ok:
            return False, msg
        inh = self._get_inheritance(inheritance_id)
        cost_con = inh.get("cost_contribution", 0)
        cost_loy = inh.get("cost_loyalty", 0)
        rewards = inh.get("rewards", {})
        # 扣除消耗
        self.player.sect_contribution -= cost_con
        self.player.sect_loyalty -= cost_loy
        self.player.ancestral_hall_monthly_count += 1
        self.player.learned_inheritances.append(inheritance_id)
        # 应用奖励
        result_parts = []
        if "permanent_attack" in rewards:
            self.player.base_attack += rewards["permanent_attack"]
            result_parts.append(f"攻击永久 +{rewards['permanent_attack']}")
        if "permanent_defense" in rewards:
            self.player.base_defense += rewards["permanent_defense"]
            result_parts.append(f"防御永久 +{rewards['permanent_defense']}")
        if "qi" in rewards:
            self.player.qi += rewards["qi"]
            result_parts.append(f"修为 +{rewards['qi']}")
        if "skill_id" in rewards:
            skill_id = rewards["skill_id"]
            skill = self.skill_library.get(skill_id)
            if skill and not self.player.has_skill(skill_id):
                self.player.learn_skill(skill_id)
                result_parts.append(f"习得技能【{skill.name}】")
        reward_text = "、".join(result_parts) if result_parts else "无"
        return True, f"你参悟了【{inh['name']}】，{reward_text}。"

    def reset_ancestral_hall_monthly_count(self):
        """重置本月祖师堂参悟次数。"""
        self.player.ancestral_hall_monthly_count = 0

    def get_cultivation_bonus(self):
        """获取宗门洞府带来的修炼速度加成（仅 cultivation_speed）。"""
        return self.get_cave_bonus().get("cultivation_speed", 0.0)

    def get_max_qi_bonus(self):
        """获取宗门洞府带来的真气上限加成。"""
        return self.get_cave_bonus().get("max_qi_bonus", 0)

    def cave_seclusion(self, months):
        """
        在宗门洞府中闭关修炼，额外获得修为。
        仅真传弟子及以上可使用。
        """
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        rank_idx = self.get_rank_index(self.player.sect_rank)
        if rank_idx < self.get_rank_index("core"):
            return False, "只有真传弟子及以上才能使用真传洞府。"

        bonus = self.get_cultivation_bonus()
        total_bonus_qi = 0
        for _ in range(months):
            base = 5 + self.player.wisdom
            total_bonus_qi += int(base * (1 + bonus))

        self.player.qi += total_bonus_qi
        # 闭关也消耗时间
        for _ in range(months):
            self.world.advance(1)
            self.player.add_age_months(1)
            self._check_sect_daily_reset()

        return True, f"你在真传洞府闭关 {months} 个月，额外获得 {total_bonus_qi} 修为。"

    def get_cave_upgrade_cost(self):
        """计算下一次洞府升级所需贡献。"""
        level = getattr(self.player, "cave_upgrade_level", 0)
        return 500 + level * 500

    def upgrade_cave(self):
        """消耗贡献升级洞府。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        rank_idx = self.get_rank_index(self.player.sect_rank)
        if rank_idx < self.get_rank_index("inner"):
            return False, "只有内门弟子及以上才能升级洞府。"

        cost = self.get_cave_upgrade_cost()
        if self.player.sect_contribution < cost:
            return False, f"贡献不足，升级洞府需要 {cost} 点贡献。"

        if not hasattr(self.player, "cave_upgrade_level"):
            self.player.cave_upgrade_level = 0

        self.player.sect_contribution -= cost
        self.player.cave_upgrade_level += 1
        return True, f"洞府升级成功！当前洞府等级：{self.player.cave_upgrade_level}"

    # ==================== 宗门战与灵脉争夺 ====================

    def can_start_war(self, target_sect_id):
        """判断是否可以对该宗门发动宗门战。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        target = self.sect_library.get(target_sect_id)
        if not target:
            return False, "目标宗门不存在。"

        if target_sect_id == sect.id:
            return False, "不能对自己宗门开战。"

        # 只有内门弟子及以上可参与宗门战
        rank_idx = self.get_rank_index(self.player.sect_rank)
        if rank_idx < self.get_rank_index("inner"):
            return False, "只有内门弟子及以上才能参与宗门战。"

        # 同盟宗门不能开战
        if self.is_allied(target_sect_id):
            return False, "不能对同盟宗门开战。"

        # 同阵营友好宗门不能开战
        if self.get_relation_status(target_sect_id) == "friendly":
            return False, "不能对友好宗门开战。"

        return True, ""

    def start_war(self, target_sect_id):
        """
        发动宗门战，计算胜负并发放奖励/惩罚。
        胜负与玩家境界、贡献、宗门战参与次数、目标难度有关。
        """
        ok, msg = self.can_start_war(target_sect_id)
        if not ok:
            return False, msg

        sect = self.get_sect()
        target = self.sect_library.get(target_sect_id)

        # 计算胜率
        player_order = self.player.REALM_ORDER.get(self.player.realm_id, 1)
        base_rate = 0.3 + player_order * 0.04  # 境界越高基础胜率越高
        contribution_bonus = min(0.2, self.player.sect_contribution / 20000)
        war_exp_bonus = min(0.15, self.player.sect_war_participation * 0.01)
        difficulty = target.war_difficulty

        success_rate = base_rate + contribution_bonus + war_exp_bonus
        # 同盟宗门协助，提升战争成功率
        success_rate += self.get_alliance_war_bonus()
        success_rate /= difficulty
        success_rate = max(0.1, min(0.9, success_rate))

        self.player.sect_war_participation += 1

        # 健康消耗
        health_cost = sect.war_reward.get("health_cost", 20)
        self.player.health -= health_cost

        # 随机判定胜负
        import random
        if random.random() < success_rate:
            # 胜利
            base_contribution = sect.war_reward.get("base_contribution", 1000)
            base_reputation = sect.war_reward.get("base_reputation", 50)
            contribution_reward = int(base_contribution * (1 + player_order * 0.05))
            reputation_reward = int(base_reputation * (1 + player_order * 0.03))

            self.player.sect_contribution += contribution_reward
            self.player.sect_loyalty = min(100, self.player.sect_loyalty + 5)
            # 与目标宗门关系恶化
            self.adjust_sect_relationship(target_sect_id, -20)

            # 尝试夺取一条目标宗门控制的灵脉
            seized_vein_name = None
            for vein in target.spirit_veins:
                if vein.get("controlled_by") == target_sect_id:
                    vein["controlled_by"] = sect.id
                    seized_vein_name = vein.get("name", "灵脉")
                    break

            msg = (
                f"宗门战大获全胜！你获得 {contribution_reward} 贡献、"
                f"{reputation_reward} 声望，忠诚度 +5。"
            )
            if seized_vein_name:
                msg += f"并成功夺取【{seized_vein_name}】！"
            else:
                msg += "目标宗门已无灵脉可夺。"

            return True, msg
        else:
            # 失败
            self.player.sect_loyalty = max(0, self.player.sect_loyalty - 10)
            # 与目标宗门关系略微恶化
            self.adjust_sect_relationship(target_sect_id, -10)
            return False, (
                f"宗门战失利，你身负重伤（健康 -{health_cost}），"
                f"忠诚度 -10，与【{target.name}】关系恶化。"
            )

    def get_controllable_veins(self, sect_id):
        """获取某宗门当前控制的灵脉列表。"""
        sect = self.sect_library.get(sect_id)
        if not sect:
            return []
        return [v for v in sect.spirit_veins if v.get("controlled_by") == sect_id]

    # ==================== 叛出与通缉 ====================

    def leave_sect_with_consequence(self):
        """
        退出宗门并计算后果。
        忠诚度低于阈值或职位较高时，会被原宗门通缉。
        """
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"

        old_sect_id = sect.id
        old_rank = self.player.sect_rank
        old_loyalty = self.player.sect_loyalty
        old_name = sect.name

        # 执行退出
        self.player.sect_id = None
        self.player.sect_rank = "none"
        self.player.sect_contribution = 0
        self.player.sect_loyalty = 0
        self.player.sect_tasks_today = 0
        self.player.sect_active_task = None
        # 退出宗门后，该宗门仓库、累计捐献、秘境冷却、悬赏进度与气运事件清零
        self.player.sect_warehouse = {}
        self.player.sect_donation_total = 0
        self.player.sect_donation_last_reward_month = -1
        self.player.sect_secret_realm_cooldowns = {}
        self.player.sect_active_bounty = None
        self.player.active_sect_fortune = None

        # 判断是否被通缉
        rank_idx = self.get_rank_index(old_rank)
        wanted = False
        if old_loyalty < sect.wanted_threshold or rank_idx >= self.get_rank_index("core"):
            wanted = True
            if not hasattr(self.player, "sect_wanted_by"):
                self.player.sect_wanted_by = []
            if old_sect_id not in self.player.sect_wanted_by:
                self.player.sect_wanted_by.append(old_sect_id)

        msg = f"你退出【{old_name}】，贡献清零，从此漂泊江湖。"
        if wanted:
            msg += f"\n[red]由于你忠诚度不足或职位过高，{old_name}已对你发布追杀令！"
        return True, msg

    def is_wanted_by(self, sect_id):
        """判断玩家是否被某宗门通缉。"""
        return sect_id in getattr(self.player, "sect_wanted_by", [])

    def get_wanted_sects(self):
        """获取所有通缉玩家的宗门 ID 列表。"""
        return list(getattr(self.player, "sect_wanted_by", []))

    def update_wanted_status(self):
        """
        随时间降低通缉强度。每过一年，与通缉宗门关系恢复 5 点；
        关系回到 0 以上时，解除通缉。
        """
        wanted = getattr(self.player, "sect_wanted_by", [])
        if not wanted:
            return

        removed = []
        for sect_id in wanted:
            rel = self.get_sect_relationship(sect_id)
            # 每年自动恢复 5 点关系
            new_rel = rel + 5
            self.set_sect_relationship(sect_id, new_rel)
            if new_rel >= 0:
                removed.append(sect_id)

        if removed:
            for sect_id in removed:
                wanted.remove(sect_id)
            self.player.sect_wanted_by = wanted

    def clear_wanted_by(self, sect_id):
        """手动解除某宗门的通缉（如完成和解任务）。"""
        wanted = getattr(self.player, "sect_wanted_by", [])
        if sect_id in wanted:
            wanted.remove(sect_id)
            self.player.sect_wanted_by = wanted
            return True
        return False

    def add_wanted_sect(self, sect_id):
        """将某宗门加入通缉列表（若尚未通缉）。"""
        wanted = getattr(self.player, "sect_wanted_by", [])
        if sect_id not in wanted:
            wanted.append(sect_id)
            self.player.sect_wanted_by = wanted
            return True
        return False

    def should_hunt_player(self, sect_id):
        """
        判断某宗门是否应该在该地点追杀玩家。
        进入敌对/通缉宗门领地时触发。
        """
        if not self.is_wanted_by(sect_id):
            return False
        # 进入该宗门领地时高概率触发追杀
        loc = self.world.get_location(self.player.location_id)
        target = self.sect_library.get(sect_id)
        if target and loc and loc.get("id") == target.location_id:
            import random
            return random.random() < 0.6
        return False
    # ==================== 宗门灵兽园与坐骑 ====================

    def get_beast_garden(self):
        """获取当前宗门灵兽园配置。"""
        sect = self.get_sect()
        if not sect:
            return None
        return getattr(sect, "beast_garden", {"max_beasts_per_player": 0, "beasts": []})

    def get_available_beasts(self):
        """获取当前宗门可领养的灵兽列表。"""
        garden = self.get_beast_garden()
        if not garden:
            return []
        return garden.get("beasts", [])

    def _get_beast_config(self, beast_id):
        """根据 ID 查找灵兽配置。"""
        for beast in self.get_available_beasts():
            if beast.get("id") == beast_id:
                return beast
        return None

    def get_player_beasts(self):
        """获取玩家已拥有的灵兽列表。"""
        return getattr(self.player, "beasts", [])

    def _get_max_beasts(self):
        """玩家最多可同时拥有的灵兽数量。"""
        garden = self.get_beast_garden()
        return garden.get("max_beasts_per_player", 0) if garden else 0

    def can_adopt_beast(self, beast_id):
        """检查是否满足领养灵兽条件。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"
        garden = self.get_beast_garden()
        if not garden or not garden.get("beasts"):
            return False, "本宗没有灵兽园。"
        beast = self._get_beast_config(beast_id)
        if not beast:
            return False, "灵兽不存在。"
        required = beast.get("required_rank", "inner")
        if self.get_rank_index(self.player.sect_rank) < self.get_rank_index(required):
            return False, f"需要职位：{sect.get_rank_name(required)}"
        if len(self.get_player_beasts()) >= self._get_max_beasts():
            return False, "灵兽栏已满，请先放生。"
        owned_ids = {b["beast_id"] for b in self.get_player_beasts()}
        if beast_id in owned_ids:
            return False, "你已经拥有该灵兽。"
        if self.player.sect_contribution < beast.get("cost_contribution", 0):
            return False, "宗门贡献不足。"
        return True, ""

    def adopt_beast(self, beast_id):
        """领养灵兽，扣除贡献并加入玩家灵兽栏。"""
        ok, msg = self.can_adopt_beast(beast_id)
        if not ok:
            return False, msg
        beast = self._get_beast_config(beast_id)
        self.player.sect_contribution -= beast.get("cost_contribution", 0)
        self.player.beasts.append({
            "beast_id": beast_id,
            "name": beast["name"],
            "type": beast.get("type", "combat"),
            "level": 1,
            "exp": 0,
            "active": True,
            "bonus": beast.get("bonus", {}),
        })
        return True, f"你领养了【{beast['name']}】，它将成为你的助力。"

    def release_beast(self, beast_id):
        """放生指定灵兽。"""
        beasts = self.get_player_beasts()
        for i, beast in enumerate(beasts):
            if beast.get("beast_id") == beast_id:
                beasts.pop(i)
                return True, f"你放生了【{beast['name']}】。"
        return False, "未找到该灵兽。"

    def get_beast_combat_bonus(self):
        """计算所有战斗型灵兽提供的攻击加成。"""
        total = 0
        for beast in self.get_player_beasts():
            if beast.get("type") == "combat" and beast.get("active", True):
                total += beast.get("bonus", {}).get("attack", 0)
        return total

    def get_beast_resource_bonus(self):
        """获取资源型灵兽每月产出（返回 [(item_id, count)] 列表）。"""
        results = []
        for beast in self.get_player_beasts():
            if beast.get("type") != "resource" or not beast.get("active", True):
                continue
            bonus = beast.get("bonus", {})
            if bonus.get("herb_chance") and random.random() < bonus["herb_chance"]:
                results.append((bonus.get("herb_id", "century_herb"), 1))
            if bonus.get("spirit_stone_chance") and random.random() < bonus["spirit_stone_chance"]:
                results.append((bonus.get("spirit_stone_id", "spirit_stone"), bonus.get("spirit_stone_count", 1)))
            if bonus.get("demon_core_chance") and random.random() < bonus["demon_core_chance"]:
                results.append((bonus.get("demon_core_id", "demon_core"), bonus.get("demon_core_count", 1)))
        return results

    def get_beast_mount_bonus(self):
        """计算坐骑型灵兽提供的赶路月份减免。"""
        total = 0
        for beast in self.get_player_beasts():
            if beast.get("type") == "mount" and beast.get("active", True):
                total += beast.get("bonus", {}).get("travel_months", 0)
        return total

    # ==================== 宗门结盟与攻守同盟 ====================

    ALLIANCE_COST = 5000           # 签订同盟消耗的贡献
    ALLIANCE_DURATION_MONTHS = 60  # 同盟有效期（月）
    ALLIANCE_SHOP_DISCOUNT = 0.1   # 同盟额外折扣 10%
    ALLIANCE_WAR_BONUS = 0.1       # 同盟协助战争成功率 +10%

    def get_alliance_list(self):
        """获取当前有效的同盟列表。"""
        return getattr(self.player, "sect_alliances", [])

    def _get_alliance_record(self, target_sect_id):
        """查找指定宗门的同盟记录。"""
        for alliance in self.get_alliance_list():
            if alliance.get("sect_id") == target_sect_id:
                return alliance
        return None

    def is_allied(self, target_sect_id):
        """判断是否与指定宗门结盟。"""
        return self._get_alliance_record(target_sect_id) is not None

    def can_form_alliance(self, target_sect_id):
        """检查是否满足签订同盟条件。"""
        sect = self.get_sect()
        if not sect:
            return False, "你尚未加入任何宗门。"
        target = self.sect_library.get(target_sect_id)
        if not target:
            return False, "目标宗门不存在。"
        if target_sect_id == sect.id:
            return False, "不能与本宗结盟。"
        if self.is_allied(target_sect_id):
            return False, "已与该宗门结盟。"
        if self.get_relation_status(target_sect_id) != "friendly":
            return False, "双方关系需达到友好方可结盟。"
        if self.player.sect_contribution < self.ALLIANCE_COST:
            return False, f"宗门贡献不足，签订同盟需要 {self.ALLIANCE_COST} 贡献。"
        return True, ""

    def form_alliance(self, target_sect_id):
        """与目标宗门签订同盟条约。"""
        ok, msg = self.can_form_alliance(target_sect_id)
        if not ok:
            return False, msg
        self.player.sect_contribution -= self.ALLIANCE_COST
        self.player.sect_alliances.append({
            "sect_id": target_sect_id,
            "formed_year": self.world.year,
            "formed_month": self.world.month,
            "duration_months": self.ALLIANCE_DURATION_MONTHS,
        })
        target = self.sect_library.get(target_sect_id)
        return True, f"你与【{target.name}】缔结攻守同盟，双方互为臂助。"

    def break_alliance(self, target_sect_id):
        """解除与目标宗门的同盟关系。"""
        alliances = self.get_alliance_list()
        for i, alliance in enumerate(alliances):
            if alliance.get("sect_id") == target_sect_id:
                alliances.pop(i)
                # 关系下降为中立
                self.set_sect_relationship(target_sect_id, 0)
                target = self.sect_library.get(target_sect_id)
                return True, f"你撕毁了与【{target.name}】的同盟条约，双方关系降至中立。"
        return False, "未与该宗门结盟。"

    def tick_alliances(self, year, month):
        """检查并移除过期的同盟条约。"""
        alliances = self.get_alliance_list()
        expired = []
        for alliance in alliances:
            formed_year = alliance.get("formed_year", year)
            formed_month = alliance.get("formed_month", month)
            duration = alliance.get("duration_months", self.ALLIANCE_DURATION_MONTHS)
            # 计算经过的月份
            elapsed = (year - formed_year) * 12 + (month - formed_month)
            if elapsed >= duration:
                expired.append(alliance)
        messages = []
        for alliance in expired:
            alliances.remove(alliance)
            target = self.sect_library.get(alliance.get("sect_id"))
            messages.append(f"与【{target.name}】的同盟条约已到期，双方自动恢复中立关系。")
        return messages

    def get_alliance_shop_discount(self, target_sect_id):
        """获取同盟带来的额外商店折扣。"""
        if self.is_allied(target_sect_id):
            return self.ALLIANCE_SHOP_DISCOUNT
        return 0.0

    def get_alliance_war_bonus(self):
        """获取同盟协助带来的宗门战成功率加成。"""
        return len(self.get_alliance_list()) * self.ALLIANCE_WAR_BONUS

