# -*- coding: utf-8 -*-
"""
为 config/skills.json 自动生成/补全 mastery_effects。

用法：
    python tools/generate_mastery_effects.py

行为：
1. 先应用 ICONIC_OVERRIDES 中标志性技能的专属满级特效；
2. 其余没有 mastery_effects 的技能按类型/属性规则自动生成；
3. 已有配置且不在覆盖表中的技能保持不变，因此可重复运行。
"""

import json
import os


CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
SKILLS_PATH = os.path.join(CONFIG_DIR, "skills.json")

CONTROL_TYPES = {"stun", "seal", "taunt", "attack_down", "defense_down", "immobilize"}
HEAL_TYPES = {"heal_over_time", "cleanse"}
SUPPORT_TYPES = {"shield", "reflect", "evasion_up", "attack_up", "defense_up"}


# 标志性技能专属满级特效，优先于批量规则
ICONIC_OVERRIDES = {
    "one_sword_break": [{
        "type": "seal",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【一剑破万法】满级有 30% 概率一剑封禁敌人万法，封印技能 2 回合"
    }],
    "ten_thousand_souls": [{
        "type": "attack_down",
        "target": "enemy",
        "ratio": 0.3,
        "turns": 3,
        "chance": 0.3,
        "description": "【万魂幡】满级有 30% 概率万魂哀嚎，降低敌人攻击 30%，持续 3 回合"
    }],
    "zhuxian_sword_formation": [{
        "type": "defense_down",
        "target": "enemy",
        "ratio": 0.4,
        "turns": 3,
        "chance": 0.3,
        "description": "【诛仙剑阵】满级有 30% 概率诛仙剑气绞碎敌甲，降低防御 40%，持续 3 回合"
    }],
    "five_elements_formation": [{
        "type": "stun",
        "target": "enemy",
        "turns": 1,
        "chance": 0.3,
        "description": "【五行大阵】满级有 30% 概率五行碾压，使敌人眩晕 1 回合"
    }],
    "five_elements_return": [{
        "type": "shield",
        "target": "player",
        "amount": 50,
        "chance": 0.3,
        "description": "【五行归元】满级有 30% 概率五行相生，额外获得 50 点护盾"
    }],
    "three_purities": [{
        "type": "attack_up",
        "target": "player",
        "ratio": 0.2,
        "turns": 3,
        "chance": 0.3,
        "description": "【一气化三清】满级有 30% 概率三清分身加持，攻击提升 20%，持续 3 回合"
    }],
    "indestructible_golden_body": [{
        "type": "reflect",
        "target": "player",
        "ratio": 0.3,
        "turns": 3,
        "chance": 0.3,
        "description": "【不灭金身】满级有 30% 概率金身反震，获得 30% 伤害反弹，持续 3 回合"
    }],
    "heavenly_demon": [{
        "type": "attack_up",
        "target": "player",
        "ratio": 0.25,
        "turns": 2,
        "chance": 0.3,
        "description": "【天魔解体】满级有 30% 概率天魔之力暴走，攻击提升 25%，持续 2 回合"
    }],
    "all_souls_return": [{
        "type": "stun",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【万魂归一】满级有 30% 概率万魂冲击神魂，眩晕 2 回合"
    }],
    "zhuxian_sword_intent": [{
        "type": "defense_down",
        "target": "enemy",
        "ratio": 0.4,
        "turns": 2,
        "chance": 0.3,
        "description": "【诛仙剑意】满级有 30% 概率剑意摧甲，降低敌人防御 40%，持续 2 回合"
    }],
    "sword_domain": [{
        "type": "attack_up",
        "target": "player",
        "ratio": 0.2,
        "turns": 3,
        "chance": 0.3,
        "description": "【剑域】满级有 30% 概率剑域共鸣，攻击提升 20%，持续 3 回合"
    }],
    "nine_turn_pill": [{
        "type": "shield",
        "target": "player",
        "amount": 40,
        "chance": 0.3,
        "description": "【九转金丹】满级有 30% 概率丹气护体，额外获得 40 点护盾"
    }],
    "blood_sacrifice": [{
        "type": "attack_up",
        "target": "player",
        "ratio": 0.25,
        "turns": 2,
        "chance": 0.3,
        "description": "【血祭大法】满级有 30% 概率血祭反补，攻击提升 25%，持续 2 回合"
    }],
    "soul_devour": [{
        "type": "seal",
        "target": "enemy",
        "turns": 1,
        "chance": 0.3,
        "description": "【噬魂术】满级有 30% 概率噬魂封窍，封印敌人技能 1 回合"
    }],
    "mountain_break": [{
        "type": "stun",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【破山裂地】满级有 30% 概率裂地震荡，眩晕 2 回合"
    }],
    "five_thunders": [{
        "type": "stun",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【五雷正法】满级有 30% 概率五雷轰顶，眩晕 2 回合"
    }],
    "ten_thousand_arts": [{
        "type": "seal",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【万法归宗】满级有 30% 概率万法封尽，封印敌人技能 2 回合"
    }],
    "vajra_body": [{
        "type": "reflect",
        "target": "player",
        "ratio": 0.3,
        "turns": 3,
        "chance": 0.3,
        "description": "【金刚不坏】满级有 30% 概率金刚反震，获得 30% 伤害反弹，持续 3 回合"
    }],
    "dragon_elephant": [{
        "type": "stun",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【龙象般若】满级有 30% 概率龙象之力震晕敌人，眩晕 2 回合"
    }],
    "blood_demon_art": [{
        "type": "dot",
        "target": "enemy",
        "damage": 15,
        "turns": 2,
        "chance": 0.3,
        "description": "【血魔大法】满级有 30% 概率血海侵蚀，每回合 15 点伤害，持续 2 回合"
    }],
    "myriad_souls_devour": [{
        "type": "attack_down",
        "target": "enemy",
        "ratio": 0.25,
        "turns": 3,
        "chance": 0.3,
        "description": "【万魂噬天】满级有 30% 概率冤魂噬志，降低敌人攻击 25%，持续 3 回合"
    }],
    "dan_qi_sword": [{
        "type": "defense_down",
        "target": "enemy",
        "ratio": 0.25,
        "turns": 2,
        "chance": 0.3,
        "description": "【丹气化剑】满级有 30% 概率丹气蚀甲，降低敌人防御 25%，持续 2 回合"
    }],
    "revival_pill": [{
        "type": "shield",
        "target": "player",
        "amount": 50,
        "chance": 0.3,
        "description": "【回天丹诀】满级有 30% 概率回天之力护体，额外获得 50 点护盾"
    }],
    "life_treasure": [{
        "type": "shield",
        "target": "player",
        "amount": 50,
        "chance": 0.3,
        "description": "【本命法宝】满级有 30% 概率本命法宝显灵，额外获得 50 点护盾"
    }],
    "beast_king": [{
        "type": "stun",
        "target": "enemy",
        "turns": 1,
        "chance": 0.3,
        "description": "【万兽之王】满级有 30% 概率兽王威压震慑，眩晕 1 回合"
    }],
    "soul_materialize": [{
        "type": "seal",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【神识化形】满级有 30% 概率神识封魂，封印敌人技能 2 回合"
    }],
    "possession": [{
        "type": "stun",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【夺舍】满级有 30% 概率夺舍冲击神魂，眩晕 2 回合"
    }],
    "dream_realm": [{
        "type": "heal_over_time",
        "target": "player",
        "amount": 15,
        "turns": 2,
        "chance": 0.3,
        "description": "【梦境领域】满级有 30% 概率梦境滋养，每回合恢复 15 点生命，持续 2 回合"
    }],
    "gengjin_sword_qi": [{
        "type": "defense_down",
        "target": "enemy",
        "ratio": 0.25,
        "turns": 2,
        "chance": 0.3,
        "description": "【庚金剑气】满级有 30% 概率庚金破甲，降低防御 25%，持续 2 回合"
    }],
    "myriad_swords": [{
        "type": "dot",
        "target": "enemy",
        "damage": 15,
        "turns": 3,
        "chance": 0.3,
        "description": "【万剑诀】满级有 30% 概率万剑穿心，每回合 15 点伤害，持续 3 回合"
    }],
    "xuanbing_dragon": [{
        "type": "stun",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【玄冰龙吟】满级有 30% 概率玄冰冻结经脉，眩晕 2 回合"
    }],
    "nanming_lihuo": [{
        "type": "dot",
        "target": "enemy",
        "damage": 20,
        "turns": 3,
        "chance": 0.3,
        "description": "【南明离火】满级有 30% 概率南明离火不灭，每回合 20 点伤害，持续 3 回合"
    }],
    "burning_heaven": [{
        "type": "dot",
        "target": "enemy",
        "damage": 25,
        "turns": 3,
        "chance": 0.3,
        "description": "【焚天烈焰】满级有 30% 概率焚天烈焰蔓延，每回合 25 点伤害，持续 3 回合"
    }],
    "wutu_thunder": [{
        "type": "stun",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【戊土神雷】满级有 30% 概率戊土震荡，眩晕 2 回合"
    }],
    "immovable_mountain": [{
        "type": "defense_up",
        "target": "player",
        "ratio": 0.25,
        "turns": 3,
        "chance": 0.3,
        "description": "【不动如山】满级有 30% 概率山岳之势加身，防御提升 25%，持续 3 回合"
    }],
    "starlight_zhouxin": [{
        "type": "attack_down",
        "target": "enemy",
        "ratio": 0.25,
        "turns": 3,
        "chance": 0.3,
        "description": "【周天星斗】满级有 30% 概率星斗威压，降低敌人攻击 25%，持续 3 回合"
    }],
    "taiyi_thunder": [{
        "type": "stun",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【太乙神雷】满级有 30% 概率太乙神雷诛邪，眩晕 2 回合"
    }],
    "flying_immortal_sword": [{
        "type": "stun",
        "target": "enemy",
        "turns": 2,
        "chance": 0.3,
        "description": "【天外飞仙】满级有 30% 概率一剑封喉，眩晕 2 回合"
    }],
    "dharma_body": [
        {
            "type": "attack_up",
            "target": "player",
            "ratio": 0.2,
            "turns": 3,
            "chance": 0.3,
            "description": "【法天象地】满级有 30% 概率法相擎天，攻击提升 20%，持续 3 回合"
        },
        {
            "type": "defense_up",
            "target": "player",
            "ratio": 0.2,
            "turns": 3,
            "chance": 0.3,
            "description": "【法天象地】满级有 30% 概率法相护体，防御提升 20%，持续 3 回合"
        }
    ],
    "sword_rain": [{
        "type": "dot",
        "target": "enemy",
        "damage": 12,
        "turns": 2,
        "chance": 0.3,
        "description": "【万剑归宗】满级有 30% 概率剑雨成河，每回合 12 点伤害，持续 2 回合"
    }],
    "quick_draw": [{
        "type": "stun",
        "target": "enemy",
        "turns": 1,
        "chance": 0.3,
        "description": "【拔剑术】满级有 30% 概率拔剑制敌，眩晕 1 回合"
    }],
}


def get_skill_category(skill):
    """判断技能类型：伤害 / 治疗 / 控制 / 辅助。"""
    if skill.get("heal", 0) > 0:
        return "heal"
    effects = skill.get("effects", [])
    for effect in effects:
        etype = effect.get("type")
        if etype in CONTROL_TYPES:
            return "control"
        if etype in HEAL_TYPES:
            return "heal"
        if etype in SUPPORT_TYPES:
            return "support"
    return "damage"


def generate_for_skill(skill):
    """为普通技能按规则生成一个满级特效。"""
    category = get_skill_category(skill)
    element = skill.get("element", "none")
    effects = skill.get("effects", [])
    name = skill["name"]

    if category == "damage":
        if element in ("metal", "thunder"):
            return [{
                "type": "stun",
                "target": "enemy",
                "turns": 1,
                "chance": 0.3,
                "description": f"【{name}】满级有 30% 概率以雷霆之势麻痹敌人 1 回合"
            }]
        if element in ("water", "ice"):
            return [{
                "type": "attack_down",
                "target": "enemy",
                "ratio": 0.2,
                "turns": 2,
                "chance": 0.3,
                "description": f"【{name}】满级有 30% 概率以寒气蚀骨，降低敌人攻击 20%，持续 2 回合"
            }]
        if element == "fire":
            dot_damage = max(8, int(skill.get("base_damage", 10) * 0.35))
            return [{
                "type": "dot",
                "target": "enemy",
                "damage": dot_damage,
                "turns": 2,
                "chance": 0.3,
                "description": f"【{name}】满级有 30% 概率附加灼烧，每回合 {dot_damage} 点伤害，持续 2 回合"
            }]
        if element in ("wood", "wind"):
            return [{
                "type": "evasion_up",
                "target": "player",
                "ratio": 0.25,
                "turns": 2,
                "chance": 0.3,
                "description": f"【{name}】满级有 30% 概率借风木之势提升闪避 25%，持续 2 回合"
            }]
        if element == "earth":
            return [{
                "type": "defense_down",
                "target": "enemy",
                "ratio": 0.2,
                "turns": 2,
                "chance": 0.3,
                "description": f"【{name}】满级有 30% 概率以山岳之力震裂敌防，降低防御 20%，持续 2 回合"
            }]
        return [{
            "type": "attack_down",
            "target": "enemy",
            "ratio": 0.2,
            "turns": 2,
            "chance": 0.3,
            "description": f"【{name}】满级有 30% 概率蕴含大道威压，降低敌人攻击 20%，持续 2 回合"
        }]

    if category == "heal":
        has_cleanse = any(e.get("type") == "cleanse" for e in effects)
        if has_cleanse:
            return [{
                "type": "heal_over_time",
                "target": "player",
                "amount": 10,
                "turns": 2,
                "chance": 0.3,
                "description": f"【{name}】满级有 30% 概率留下生机，每回合恢复 10 点生命，持续 2 回合"
            }]
        return [{
            "type": "cleanse",
            "target": "player",
            "chance": 0.3,
            "description": f"【{name}】满级有 30% 概率在治疗时净化自身负面状态"
        }]

    if category == "control":
        hard_cc = {"stun", "seal", "taunt", "immobilize"}
        has_hard_cc = any(e.get("type") in hard_cc for e in effects)
        has_attack_down = any(e.get("type") == "attack_down" for e in effects)
        has_defense_down = any(e.get("type") == "defense_down" for e in effects)

        if has_hard_cc:
            return [{
                "type": "seal",
                "target": "enemy",
                "turns": 1,
                "chance": 0.3,
                "description": f"【{name}】满级有 30% 概率趁势封印敌人技能 1 回合"
            }]
        if has_attack_down and not has_defense_down:
            return [{
                "type": "defense_down",
                "target": "enemy",
                "ratio": 0.2,
                "turns": 2,
                "chance": 0.3,
                "description": f"【{name}】满级有 30% 概率追加防御削弱 20%，持续 2 回合"
            }]
        if has_defense_down and not has_attack_down:
            return [{
                "type": "attack_down",
                "target": "enemy",
                "ratio": 0.2,
                "turns": 2,
                "chance": 0.3,
                "description": f"【{name}】满级有 30% 概率追加攻击削弱 20%，持续 2 回合"
            }]
        return [{
            "type": "stun",
            "target": "enemy",
            "turns": 1,
            "chance": 0.3,
            "description": f"【{name}】满级有 30% 概率追加眩晕 1 回合"
        }]

    if category == "support":
        for stype in SUPPORT_TYPES:
            for effect in effects:
                if effect.get("type") != stype:
                    continue
                if stype == "shield":
                    amount = max(15, int(effect.get("amount", 30) * 0.5))
                    return [{
                        "type": "shield",
                        "target": "player",
                        "amount": amount,
                        "chance": 0.3,
                        "description": f"【{name}】满级有 30% 概率额外生成 {amount} 点护盾"
                    }]
                if stype == "reflect":
                    ratio = min(0.5, round(effect.get("ratio", 0.3) + 0.1, 2))
                    turns = effect.get("turns", 2)
                    return [{
                        "type": "reflect",
                        "target": "player",
                        "ratio": ratio,
                        "turns": turns,
                        "chance": 0.3,
                        "description": f"【{name}】满级有 30% 概率提升反弹比例至 {int(ratio * 100)}%，持续 {turns} 回合"
                    }]
                if stype == "evasion_up":
                    ratio = min(0.6, round(effect.get("ratio", 0.3) + 0.15, 2))
                    turns = effect.get("turns", 2)
                    return [{
                        "type": "evasion_up",
                        "target": "player",
                        "ratio": ratio,
                        "turns": turns,
                        "chance": 0.3,
                        "description": f"【{name}】满级有 30% 概率大幅提升闪避至 {int(ratio * 100)}%，持续 {turns} 回合"
                    }]
                if stype == "attack_up":
                    ratio = min(0.5, round(effect.get("ratio", 0.2) + 0.1, 2))
                    turns = effect.get("turns", 2)
                    return [{
                        "type": "attack_up",
                        "target": "player",
                        "ratio": ratio,
                        "turns": turns,
                        "chance": 0.3,
                        "description": f"【{name}】满级有 30% 概率攻击力进一步提升 {int(ratio * 100)}%，持续 {turns} 回合"
                    }]
                if stype == "defense_up":
                    ratio = min(0.6, round(effect.get("ratio", 0.2) + 0.1, 2))
                    turns = effect.get("turns", 2)
                    return [{
                        "type": "defense_up",
                        "target": "player",
                        "ratio": ratio,
                        "turns": turns,
                        "chance": 0.3,
                        "description": f"【{name}】满级有 30% 概率防御力进一步提升 {int(ratio * 100)}%，持续 {turns} 回合"
                    }]
        return [{
            "type": "shield",
            "target": "player",
            "amount": 20,
            "chance": 0.3,
            "description": f"【{name}】满级有 30% 概率额外生成 20 点护盾"
        }]

    return []


def main():
    with open(SKILLS_PATH, "r", encoding="utf-8") as f:
        skills = json.load(f)

    override_count = 0
    generated_count = 0
    for skill in skills:
        sid = skill["id"]
        if sid in ICONIC_OVERRIDES:
            skill["mastery_effects"] = ICONIC_OVERRIDES[sid]
            override_count += 1
        elif not skill.get("mastery_effects"):
            skill["mastery_effects"] = generate_for_skill(skill)
            generated_count += 1

    with open(SKILLS_PATH, "w", encoding="utf-8") as f:
        json.dump(skills, f, ensure_ascii=False, indent=2)

    print(
        f"处理完成：覆盖标志性技能 {override_count} 个，"
        f"自动生成 {generated_count} 个，保留原有 {len(skills) - override_count - generated_count} 个。"
    )


if __name__ == "__main__":
    main()
