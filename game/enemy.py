import json
import os
import random


class EnemyLibrary:
    """敌人库，从 JSON 加载所有敌人模板。"""

    def __init__(self, config_dir="config"):
        enemies_path = os.path.join(config_dir, "enemies.json")
        with open(enemies_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 用敌人 ID 做索引
        self.enemies = {d["id"]: d for d in data}

    def get(self, enemy_id):
        """根据 ID 获取敌人配置。"""
        return self.enemies.get(enemy_id)


class Enemy:
    """敌人类，代表战斗中的妖兽或修士。内置 AI 状态机决策。"""

    def __init__(
        self,
        enemy_id,
        name,
        level,
        hp,
        attack,
        defense,
        description,
        loot,
        exp,
        skills=None,
        ai_config=None,
        element="none",
        cultivation_path=None,
        alignment="neutral",
        realm_id=None,
        special=None,
    ):
        self.id = enemy_id
        self.name = name
        self.level = level    # 敌人等级，用于境界压制计算
        self.max_hp = hp
        self.hp = hp
        self.attack = attack
        self.defense = defense
        self.description = description
        self.loot = loot      # 击败后掉落物品列表
        self.exp = exp        # 击败后获得修为
        self.skills = skills or []  # 敌人技能列表
        # AI 行为配置：治疗、逃跑、集火等阈值
        self.ai_config = ai_config or {}
        # 五行属性：metal/wood/water/fire/earth/none，用于五行相克判定
        self.element = element
        # 修炼流派：fa/ti/jian/xie（人形敌人专属），用于流派克制判定
        self.cultivation_path = cultivation_path
        # 阵营：righteous/evil/neutral，用于心境系统击杀影响
        self.alignment = alignment
        # 敌人境界 ID，用于境界压制与掉落难度计算
        self.realm_id = realm_id
        # 高阶敌人专属机制：召唤、专属技能等
        self.special = special

    @classmethod
    def from_dict(cls, data):
        """从 JSON 数据创建 Enemy 对象。"""
        return cls(
            enemy_id=data["id"],
            name=data["name"],
            level=data.get("level", 1),
            hp=data["hp"],
            attack=data["attack"],
            defense=data["defense"],
            description=data.get("description", ""),
            loot=data.get("loot", []),
            exp=data.get("exp", 0),
            skills=data.get("skills", []),
            ai_config=data.get("ai", {}),
            element=data.get("element", "none"),
            cultivation_path=data.get("cultivation_path"),
            alignment=data.get("alignment", "neutral"),
            realm_id=data.get("realm_id"),
            special=data.get("special"),
        )

    def is_alive(self):
        """敌人是否还活着。"""
        return self.hp > 0

    def take_damage(self, damage):
        """受到伤害，防御会减少伤害。"""
        actual = max(1, damage - self.defense)
        self.hp -= actual
        return actual

    def get_loot(self, player_realm_order=None, enemy_realm_order=None):
        """根据概率计算掉落物品。

        Args:
            player_realm_order: 玩家当前境界 order，传入后可根据境界差
                调整掉落概率。越级挑战敌人掉落概率提升，压级碾压则下降。
            enemy_realm_order: 敌人当前境界 order，优先于 self.level 用于
                计算境界差与妖核品质。
        """
        result = []
        if player_realm_order is not None:
            enemy_order = enemy_realm_order if enemy_realm_order is not None else getattr(self, "level", 1)
            diff = enemy_order - player_realm_order
        else:
            diff = None

        for entry in self.loot:
            chance = entry["chance"]
            if diff is not None:
                # 敌人境界高于玩家时，掉落概率提升（每高 1 阶 +10%，上限 100%）
                # 敌人境界低于玩家时，掉落概率下降（每低 1 阶 -5%，下限 10%）
                if diff > 0:
                    chance = min(1.0, chance + diff * 0.10)
                elif diff < 0:
                    chance = max(0.1, chance + diff * 0.05)
            if random.random() < chance:
                # 妖核按境界差映射品质：高阶→上品，同阶/略高→中品，低阶→下品
                final_item_id = self._resolve_demon_core_quality(entry["item_id"], diff)
                result.append(final_item_id)
                # 高阶敌人有概率额外掉落一次（模拟数量提升）
                if diff is not None and self.level >= 8:
                    if random.random() < 0.3:
                        result.append(final_item_id)
        return result

    def _resolve_demon_core_quality(self, item_id, diff):
        """将基础妖核 ID 按境界差映射为下品/中品/上品。"""
        if item_id != "demon_core":
            return item_id
        if diff is None:
            return item_id
        if diff >= 3:
            return "demon_core_high"
        if diff >= 0:
            return "demon_core_mid"
        return "demon_core_low"

    # ==================== AI 状态机 ====================

    def decide_action(self, player):
        """
        根据状态机决定本回合行动。
        优先级：逃跑 > 治疗 > buff(自身低血时强化) > 集火(玩家残血) > 狂暴 > 正常技能/攻击。
        返回字典：{"action": "attack"/"skill"/"heal"/"buff"/"flee", "skill": {...}}
        """
        my_hp_ratio = self.hp / self.max_hp if self.max_hp > 0 else 0
        player_hp_ratio = (
            player.health / player.max_health if player.max_health > 0 else 0
        )

        # —— 1. 逃跑判定：血量极低时尝试逃离 ——
        flee_threshold = self.ai_config.get("flee_hp_ratio", 0)
        if flee_threshold > 0 and my_hp_ratio <= flee_threshold:
            flee_chance = self.ai_config.get("flee_chance", 0.3)
            if random.random() < flee_chance:
                return {"action": "flee"}

        # —— 2. 治疗判定：血量低于阈值且有治疗技能 ——
        heal_skill = self.ai_config.get("heal_skill")
        heal_threshold = self.ai_config.get("heal_hp_ratio", 0)
        if heal_skill and heal_threshold > 0 and my_hp_ratio <= heal_threshold:
            heal_chance = heal_skill.get("chance", 0.5)
            if random.random() < heal_chance:
                return {"action": "heal", "skill": heal_skill}

        # —— 3. buff/debuff 判定：血量低于阈值时使用强化/削弱技能 ——
        buff_skill = self.ai_config.get("buff_skill")
        buff_threshold = self.ai_config.get("buff_hp_ratio", 0)
        if buff_skill and buff_threshold > 0 and my_hp_ratio <= buff_threshold:
            buff_chance = buff_skill.get("chance", 0.4)
            if random.random() < buff_chance:
                return {"action": "buff", "skill": buff_skill}

        # —— 4. 集火判定：玩家残血时优先使用高伤害技能 ——
        focus_threshold = self.ai_config.get("focus_player_hp_ratio", 0)
        if focus_threshold > 0 and player_hp_ratio <= focus_threshold:
            aggressive_skill = self._choose_aggressive_skill()
            if aggressive_skill:
                return {"action": "skill", "skill": aggressive_skill}

        # —— 5. 狂暴判定：自身血量低于 30% 时攻击提升（仍走正常攻击流程） ——
        # 狂暴不单独返回，由 engine 在计算伤害时叠加，这里仅提示

        # —— 6. 正常行为：按概率使用技能，否则普通攻击 ——
        skill = self.choose_skill()
        if skill:
            return {"action": "skill", "skill": skill}

        return {"action": "attack"}

    def _choose_aggressive_skill(self):
        """集火模式下优先选择伤害倍率最高的技能。"""
        if not self.skills:
            return None
        # 按 damage_multiplier 降序排列，选第一个触发概率达标的
        sorted_skills = sorted(
            self.skills,
            key=lambda s: s.get("damage_multiplier", 1.0),
            reverse=True,
        )
        for skill in sorted_skills:
            if random.random() < skill.get("chance", 0):
                return skill
        return None

    def choose_skill(self):
        """根据血量和概率选择一个可释放的技能（仅攻击型，供正常状态使用）。"""
        hp_ratio = self.hp / self.max_hp
        available = []
        for skill in self.skills:
            # 跳过 buff/debuff 类技能，它们由 decide_action 的 buff 分支处理
            if skill.get("type") in ("buff", "debuff"):
                continue
            trigger = skill.get("trigger_hp_ratio", 1.0)
            if hp_ratio <= trigger and random.random() < skill.get("chance", 0):
                available.append(skill)
        # 返回第一个触发的技能，没有则返回 None
        return available[0] if available else None
