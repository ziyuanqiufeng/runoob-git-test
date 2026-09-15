# -*- coding: utf-8 -*-
"""引擎战斗域 Mixin：境界缩放、元婴替死、敌人技能/召唤、伤害公式等战斗辅助。

GameEngine 继承本 Mixin。方法通过鸭子类型访问引擎成员
（player/enemy_library/notify/combat_dot_effects 等）。
"""
import random

from game.constants import ELEMENT_NAMES


class CombatMixin:

    def _get_realm_order(self):
        """获取玩家当前境界的 order。"""
        realm = self.world.get_realm(self.player.realm_id)
        return realm["order"] if realm else 1

    def _try_nascent_soul_revive(self, logs):
        """
        元婴替死判定：玩家生命归零且未使用过替死时，
        元婴离体替死一次，恢复 30% 生命并清除所有 DOT。
        替死后元婴受损，全属性下降 10%，持续 12 个月。
        返回 True 表示触发替死，战斗继续。
        """
        if (
            self.player.has_feature("nascent_soul_revive")
            and not self.player.nascent_soul_revive_used
            and self.player.health <= 0
        ):
            self.player.nascent_soul_revive_used = True
            # 元婴受损：替死代价
            self.player.nascent_soul_weakened = True
            self.player.weakened_remaining_months = 12
            # 先记录原生命上限用于计算恢复量
            old_max_health = self.player.max_health
            revive_health = int(old_max_health * 0.3)
            self.player.health = max(1, revive_health)
            self.combat_dot_effects = []
            logs.append(
                "[gold]元婴离体！在生死一线之际，你的元婴替你挡下致命一击，"
                f"你恢复 {self.player.health} 点生命！"
            )
            logs.append(
                "[red]元婴受损！你的全属性下降 10%，需调养 12 个月方可恢复。"
            )
            return True
        return False

    def _get_enemy_realm_order(self, enemy):
        """获取敌人的境界 order，优先使用 realm_id。"""
        enemy_realm_id = getattr(enemy, "realm_id", None)
        if enemy_realm_id:
            enemy_realm = self.world.get_realm(enemy_realm_id)
            return enemy_realm.get("order", enemy.level) if enemy_realm else enemy.level
        return getattr(enemy, "level", 1)

    def _apply_realm_scaling(self, enemy):
        """根据玩家与敌人境界差动态缩放敌人 HP/攻击/防御。

        敌人境界高于玩家时属性增强，低于玩家时属性削弱，
        实现越级挑战与压级碾压的手感差异。
        """
        player_order = self._get_realm_order()
        enemy_order = self._get_enemy_realm_order(enemy)
        diff = enemy_order - player_order
        if diff == 0:
            return

        # 每差 1 个境界，属性增减 10%，限制在 [0.5, 2.0] 区间
        ratio = 1.0 + diff * 0.1
        ratio = max(0.5, min(2.0, ratio))

        enemy.max_hp = int(enemy.max_hp * ratio)
        enemy.hp = enemy.max_hp
        enemy.attack = int(enemy.attack * ratio)
        enemy.defense = int(enemy.defense * ratio)

        if diff > 0:
            self.notify(
                f"[red]{enemy.name} 境界压制！其属性提升 "
                f"{int((ratio - 1.0) * 100)}%"
            )
        else:
            self.notify(
                f"[cyan]你境界碾压 {enemy.name}，其属性削弱 "
                f"{int((1.0 - ratio) * 100)}%"
            )

    def _combat_damage_modifier(self, enemy):
        """根据玩家与敌人的境界差计算伤害修正系数。"""
        player_order = self._get_realm_order()
        enemy_order = self._get_enemy_realm_order(enemy)
        diff = player_order - enemy_order
        # 每差 1 个境界，伤害增减 20%，最低 0.5 倍，最高 2 倍
        multiplier = 1.0 + diff * 0.2
        return max(0.5, min(2.0, multiplier))

    def _try_enemy_special_skill(self, enemy, logs):
        """尝试触发高阶敌人专属技能，成功返回 True。

        专属技能冷却期间不会再次触发，使用后会进入冷却。
        """
        special = getattr(enemy, "special", {}) or {}
        special_skill = special.get("special_skill")
        if not special_skill:
            return False
        if self.enemy_special_cooldown > 0:
            return False
        if random.random() >= special_skill.get("chance", 0):
            return False

        # [red] 标记专属技能
        logs.append(
            f"[red]{enemy.name} 施展【{special_skill['name']}】！"
            f"{special_skill.get('description', '')}"
        )
        self.enemy_special_cooldown = special_skill.get("cooldown", 3)

        # 计算技能伤害并乘境界修正
        enemy_attack = int(
            enemy.attack * special_skill.get("damage_multiplier", 1.0)
        )
        enemy_attack = int(enemy_attack * self._get_enemy_attack_multiplier())
        actual = max(1, enemy_attack - self.player.defense // 2)
        self.player.health -= actual
        logs.append(f"[red]你受到 {actual} 点伤害。")

        # 处理各类特效
        effect = special_skill.get("effect")
        if effect == "stun":
            turns = special_skill.get("turns", 1)
            self.player_stunned = max(self.player_stunned, turns)
            logs.append(f"[red]你陷入眩晕，持续 {turns} 回合！")
        elif effect == "player_attack_down":
            amount = special_skill.get("amount", 10)
            turns = special_skill.get("turns", 2)
            self.player_attack_debuffs.append({"amount": amount, "turns": turns})
            logs.append(f"[red]你的攻击力被削弱 {amount} 点，持续 {turns} 回合！")
        elif effect == "life_drain":
            drain = int(actual * special_skill.get("drain_ratio", 0.5))
            enemy.hp = min(enemy.max_hp, enemy.hp + drain)
            logs.append(f"[red]{enemy.name} 吸取 {drain} 点生命！")
        elif effect == "heal":
            heal = int(enemy.max_hp * special_skill.get("heal_ratio", 0.15))
            enemy.hp = min(enemy.max_hp, enemy.hp + heal)
            logs.append(f"[green]{enemy.name} 恢复 {heal} 点生命！")

        # 毒液类 DOT
        dot_damage = special_skill.get("dot_damage")
        dot_turns = special_skill.get("dot_turns")
        if dot_damage and dot_turns:
            self.combat_dot_effects.append({
                "source": "enemy",
                "damage": dot_damage,
                "turns": dot_turns,
                "name": special_skill["name"],
            })
            logs.append(f"[red]你受到 {special_skill['name']} 灼烧，每回合损失 {dot_damage} 点生命！")

        return True

    def _try_enemy_summon(self, enemy, logs):
        """尝试触发高阶敌人召唤机制，成功返回 True。"""
        special = getattr(enemy, "special", {}) or {}
        summon = special.get("summon")
        if not summon:
            return False
        # 同一敌人同时只能存在一种召唤物
        if any(s.get("source") == enemy.id for s in self.enemy_summons):
            return False
        if random.random() >= summon.get("chance", 0):
            return False

        summon_name = summon.get("name", "召唤物")
        attack = int(enemy.attack * summon.get("attack_ratio", 0.5))
        turns = summon.get("turns", 3)
        self.enemy_summons.append({
            "source": enemy.id,
            "name": summon_name,
            "attack": attack,
            "turns": turns,
        })
        logs.append(
            f"[red]{enemy.name} 召唤出【{summon_name}】，将在 {turns} 回合内协同攻击！"
        )
        return True

    def _process_enemy_summons(self, logs):
        """结算召唤物每回合对玩家的攻击，并移除持续回合耗尽的召唤物。"""
        remaining = []
        for summon in self.enemy_summons:
            attack = summon.get("attack", 0)
            actual = max(1, attack - self.player.defense // 3)
            self.player.health -= actual
            logs.append(
                f"[red]【{summon['name']}】协同攻击，对你造成 {actual} 点伤害。"
            )
            summon["turns"] -= 1
            if summon["turns"] > 0:
                remaining.append(summon)
            else:
                logs.append(f"[cyan]【{summon['name']}】力量耗尽，消散于空中。")
        self.enemy_summons = remaining

    def _get_effective_qi_cost(self, skill_id):
        """根据技能熟练度计算实际真气消耗。"""
        skill = self.skill_library.get(skill_id)
        if not skill:
            return 0
        multiplier = self.player.get_skill_qi_cost_multiplier(skill_id)
        return max(0, int(skill.qi_cost * multiplier))

    def _calculate_skill_damage(self, skill):
        """根据境界、武器加成和技能熟练度动态计算技能伤害。"""
        realm_order = self._get_realm_order()
        # 武器攻击力 = 总攻击 - 基础攻击，并受道侣攻击加成影响
        weapon_attack = int(
            (self.player.attack - self.player.base_attack) *
            (1 + getattr(self, "companion_atk_bonus", 0.0))
        )

        damage = skill.base_damage
        damage += realm_order * skill.realm_multiplier
        damage += weapon_attack * skill.weapon_multiplier
        # 灵兽助战加成（战斗型灵兽）
        damage += self.sect_manager.get_beast_combat_bonus()
        # 技能熟练度加成：越熟练伤害越高
        damage *= self.player.get_skill_damage_multiplier(skill.id)
        return int(damage)

    def _calculate_skill_heal(self, skill):
        """
        根据境界与熟练度计算技能治疗量。
        丹修的 heal_bonus_mult=1.5 会让治疗效果提升 50%。
        """
        realm_order = self._get_realm_order()
        base = skill.heal + realm_order * skill.heal_realm_multiplier
        # 应用流派治疗加成（丹修 ×1.5，其他默认 ×1.0）
        amount = base * self.player.heal_bonus_mult
        # 熟练度加成：越熟练治疗量越高
        amount *= self.player.get_skill_heal_multiplier(skill.id)
        return int(amount)

    def _enemy_dodged(self, enemy):
        """判断敌人是否闪避本次攻击，等级越高闪避率越高；玩家闪避加成额外叠加。"""
        # 基础闪避 5%，每高一级加 3%，最高 20%
        dodge_rate = min(0.2, 0.05 + enemy.level * 0.03)
        # 叠加玩家主动闪避加成（如剑舞、影遁）
        dodge_rate += self.player_evasion_bonus
        return random.random() < min(0.9, dodge_rate)

    def _enemy_rage_attack(self, enemy):
        """判断敌人是否进入狂暴状态（血量低于 30% 时攻击提升 50%）。"""
        if enemy.hp / enemy.max_hp < 0.3:
            return True
        return False

    def _apply_enemy_element_multiplier(self, enemy_attack, enemy, logs):
        # element_multiplier 定义于 engine 模块级，方法内延迟导入避免循环依赖
        from game.engine import element_multiplier
        """
        计算敌人攻击玩家时的五行相克伤害修正。
        以玩家主灵根（spiritual_roots[0]）作为防御属性。
        克制时伤害 ×1.5，被克时 ×0.7，无属性或同属性 ×1.0。
        返回修正后的攻击力，并在 logs 中追加提示。
        """
        # 玩家主灵根作为防御属性；融合灵根展开后取首个元素，无灵根则视为无属性
        if self.player.spiritual_roots:
            player_def_element = (
                self.player.expanded_elements[0]
                if self.player.expanded_elements
                else self.player.spiritual_roots[0]
            )
        else:
            player_def_element = "none"
        elem_mult = element_multiplier(enemy.element, player_def_element)
        if elem_mult > 1.0:
            logs.append(
                f"[red]五行相克！对方{ELEMENT_NAMES.get(enemy.element, '?')}属性"
                f"克制你的{ELEMENT_NAMES.get(player_def_element, '?')}主灵根，伤害激增！"
            )
        elif elem_mult < 1.0:
            logs.append(
                f"[green]五行受制！你的{ELEMENT_NAMES.get(player_def_element, '?')}主灵根"
                f"克制对方{ELEMENT_NAMES.get(enemy.element, '?')}属性，伤害削弱。"
            )
        return int(enemy_attack * elem_mult)

