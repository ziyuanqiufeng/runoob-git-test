class Skill:
    """技能对象，新增 element 属性用于灵根匹配，path_exclusive 用于流派限制。"""

    def __init__(
        self,
        skill_id,
        name,
        description,
        base_damage=0,
        realm_multiplier=0,
        weapon_multiplier=0,
        qi_cost=0,
        cooldown=0,
        heal=0,
        heal_realm_multiplier=0,
        element="none",
        path_exclusive=None,
        effects=None,
        realm_id=None,
        mastery_effects=None,
    ):
        self.id = skill_id
        self.name = name
        self.description = description
        self.base_damage = base_damage
        self.realm_multiplier = realm_multiplier
        self.weapon_multiplier = weapon_multiplier
        self.qi_cost = qi_cost
        self.cooldown = cooldown
        self.heal = heal
        self.heal_realm_multiplier = heal_realm_multiplier
        # 技能属性：metal/wood/water/fire/earth/none/all（all 为五行阵法，需五行俱全）
        self.element = element
        # 流派专属限制：fa/ti/jian/xie，需对应流派才能学习/施展
        self.path_exclusive = path_exclusive
        # 技能附加效果列表（控制、增益、持续伤害等）
        self.effects = effects or []
        # 境界要求：玩家境界 order 需不低于该值才能施展（None 表示无要求）
        self.realm_id = realm_id
        # 满级熟练度特效：技能专属，优先级高于类别默认特效
        self.mastery_effects = mastery_effects or []

    @classmethod
    def from_dict(cls, data):
        return cls(
            skill_id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            base_damage=data.get("base_damage", 0),
            realm_multiplier=data.get("realm_multiplier", 0),
            weapon_multiplier=data.get("weapon_multiplier", 0),
            qi_cost=data.get("qi_cost", 0),
            cooldown=data.get("cooldown", 0),
            heal=data.get("heal", 0),
            heal_realm_multiplier=data.get("heal_realm_multiplier", 0),
            element=data.get("element", "none"),
            path_exclusive=data.get("path_exclusive"),
            effects=data.get("effects", []),
            realm_id=data.get("realm_id"),
            mastery_effects=data.get("mastery_effects", []),
        )


import copy


class SkillLibrary:
    """技能库，从 JSON 加载所有技能模板。"""

    def __init__(self, config_dir="config"):
        import json
        import os

        skills_path = os.path.join(config_dir, "skills.json")
        with open(skills_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.skills = {d["id"]: Skill.from_dict(d) for d in data}

    def get(self, skill_id):
        return self.skills.get(skill_id)

    def create(self, skill_id):
        """创建技能副本。"""
        template = self.get(skill_id)
        if not template:
            return None
        return Skill(
            skill_id=template.id,
            name=template.name,
            description=template.description,
            base_damage=template.base_damage,
            realm_multiplier=template.realm_multiplier,
            weapon_multiplier=template.weapon_multiplier,
            qi_cost=template.qi_cost,
            cooldown=template.cooldown,
            heal=template.heal,
            heal_realm_multiplier=template.heal_realm_multiplier,
            element=template.element,
            path_exclusive=template.path_exclusive,
            effects=copy.deepcopy(template.effects),
            realm_id=template.realm_id,
            mastery_effects=copy.deepcopy(template.mastery_effects),
        )
