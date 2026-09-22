# -*- coding: utf-8 -*-
"""GameEngine 战斗主流程 Mixin（第七期拆分，2026-09-20）。

从 engine.py 迁入 31 个战斗主流程方法：敌人生成/邪气猎杀/天道追杀者/
战斗状态机（start_combat/end_combat）/战斗消耗品部署/地形战斗/环境效果/
DOT/buff tick/流派协同/技能效果应用/精通加成/攻防倍率/战斗状态推进/
专属技能效果/防御机制/护盾反弹/流派攻击机制/combat_round 回合主流程。
由剪切脚本从 engine.py 原样迁出（tools/.combat_flow_cut_backup_20260920.py 为切出备份）。
与 engine_combat_mixin.py（CombatMixin，战斗辅助计算）互补，无同名方法。
"""
import random

from game.companion import CompanionManager
from game.constants import ELEMENT_NAMES
from game.enemy import Enemy


class CombatFlowMixin:
    """战斗主流程方法集：依赖宿主 GameEngine 的 combat_extension_manager /
    sect_manager / weather_manager / mental_state_manager 等实例属性。"""

    def _spawn_enemy(self, location):
        """在当前地点随机生成一个敌人。"""
        enemy_ids = location.get("enemies", [])
        if not enemy_ids:
            return None

        enemy_id = random.choice(enemy_ids)
        enemy_data = self.enemy_library.get(enemy_id)
        if not enemy_data:
            return None

        return Enemy.from_dict(enemy_data)

    def _check_evil_qi_hunt(self):
        """
        邪修正道追杀检测：邪气 ≥50 时有概率触发正道追杀事件。
        使用 _evil_hunt_cooldown 防止连续触发。
        """
        if self.player.cultivation_path != "xie":
            return
        if self.player.evil_qi < 50:
            return
        # 冷却标记（避免连续触发）
        if getattr(self, "_evil_hunt_cooldown", False):
            return
        # 邪气越高触发概率越高
        trigger_rate = 0.15 + (self.player.evil_qi - 50) * 0.005
        if random.random() < trigger_rate:
            self._evil_hunt_cooldown = True
            # 邪气 ≥80 出长老，否则出弟子
            if self.player.evil_qi >= 80:
                enemy_data = self.enemy_library.get("righteous_elder")
                enemy_name = "正道长老"
            else:
                enemy_data = self.enemy_library.get("righteous_disciple")
                enemy_name = "正道弟子"
            if enemy_data:
                enemy = Enemy.from_dict(enemy_data)
                self.notify(
                    f"你的邪气已引起正道注意，{enemy_name}前来追杀！"
                )
                self.start_combat(enemy)
        else:
            self._evil_hunt_cooldown = False

    def create_heaven_pursuer(self, player):
        """构造一名「天道追杀者」敌人（地狱难度突破大境界时调用）。"""
        from game.enemy import Enemy

        order = self.player.REALM_ORDER.get(player.realm_id, 1)
        level = max(1, order + 2)
        base = 30 + level * 12
        return Enemy(
            enemy_id="heaven_pursuer",
            name="天道追杀者",
            level=level,
            hp=120 + level * 40,
            attack=base + 6,
            defense=max(1, base - 4),
            description="天地杀机凝成的追杀者，誓要抹杀逆天而行之人。",
            loot=[],
            exp=0,
            skills=[],
            element="none",
            cultivation_path=None,
            alignment="neutral",
            realm_id=player.realm_id,
            special=None,
        )

    def start_combat(self, enemy, is_city_defense=False):
        """开始一场战斗。is_city_defense=True 表示该战斗为城池防卫战（如兽潮来袭）。"""
        # 标记当前战斗是否为城池防卫战，战斗结束后据此结算城池声望
        self.current_combat_is_city_defense = is_city_defense
        # 战斗扩展系统：重置 buff/连携/统计状态
        self.combat_extension_manager.start_battle()
        # 重置技能冷却
        self.player.skill_cooldowns = {sid: 0 for sid in self.player.skills}
        # 记录本场战斗使用过的技能，用于战斗结束后的熟练度衰减
        self._combat_used_skills = set()
        # 重置 DOT 效果
        self.combat_dot_effects = []
        # 重置 buff/debuff 状态：每项为 {"amount": int, "turns": int}
        self.enemy_defense_buffs = []      # 敌人临时防御加成列表
        self.player_attack_debuffs = []    # 玩家攻击削弱列表
        # 道侣战斗加成（百分比），整场战斗生效
        companion_mgr = CompanionManager(
            self.player, self.world, npc_library=self.npc_library
        )
        self.companion_atk_bonus, self.companion_def_bonus = companion_mgr.get_battle_bonus()
        # 每场战斗重置元婴替死标记
        self.player.nascent_soul_revive_used = False
        # 重置战斗内临时资源（部分流派资源每场战斗清零；邪气/兽魂/符箓长期保留）
        path = self.player.cultivation_path
        if path == "jian":
            self.player.sword_intent = 0
        elif path == "ti":
            self.player.rage = 0
        elif path == "dan":
            self.player.dan_fire = 0       # 丹火每场战斗从 0 开始积累
        elif path == "qi":
            self.player.qi_spirit = 0      # 器灵每场战斗从 0 开始积累
        elif path == "hun":
            self.player.hun_sense = 0      # 神识每场战斗从 0 开始积累
        elif path == "zhen":
            self.player.zhen_rune = 0      # 阵纹每场战斗从 0 开始积累
        # 符修的符箓是预制资源，战斗开始时不重置；但战斗内用完只能普攻
        # 阵修战斗内布阵状态初始化
        self.formation_active = None       # 当前激活的阵法效果：{"type": "trap"/"weaken", "turns": int, ...}
        self.formation_just_activated = False  # 本回合刚布阵成功标记（敌人当回合即被困）
        self.enemy_skill_sealed = 0        # 敌人技能被封印的剩余回合数（符修镇妖符）
        self.player_stunned = 0            # 玩家眩晕剩余回合（魂修反噬用）
        self.enemy_special_cooldown = 0    # 高阶敌人专属技能冷却回合
        self.enemy_summons = []            # 高阶敌人召唤的协助单位 [{name, attack, turns}]
        # 战斗状态机扩展：控制与增益状态
        self.enemy_stunned = 0             # 敌人眩晕剩余回合
        self.enemy_taunted = 0             # 敌人被嘲讽剩余回合
        self.enemy_attack_down = []        # 敌人攻击削弱列表 [{"ratio": float, "turns": int}]
        self.enemy_defense_down = []       # 敌人防御削弱列表 [{"ratio": float, "turns": int}]
        self.player_shield = 0             # 玩家护盾值
        self.player_reflect_ratio = 0.0    # 玩家反弹伤害比例
        self.player_evasion_bonus = 0.0    # 玩家闪避加成
        self.player_attack_up = []         # 玩家攻击增益列表 [{"ratio": float, "turns": int}]
        self.player_defense_up = []        # 玩家防御增益列表 [{"ratio": float, "turns": int}]
        self.player_hot = []               # 玩家持续恢复 [{"amount": int, "turns": int}]
        self.player_cleanse = False        # 本回合是否触发净化
        # 法修战斗开始时激活真气护盾（满值 100）
        if path == "fa":
            self.player.shield_qi = 100
        # 御兽修战斗开始时给 1 只初始兽魂（保证机制可触发）
        if path == "shou" and self.player.shou_soul < 1:
            self.player.shou_soul = 1
        # 特殊地形环境效果提示
        # 不同地点会为战斗带来额外环境加成，增强地图探索的代入感
        terrain_msg = self._get_terrain_combat_message()
        if terrain_msg:
            self.notify(terrain_msg)
        # 应用境界差距对敌人属性的动态缩放（越级挑战/压级碾压）
        self._apply_realm_scaling(enemy)
        # 应用宗门气运事件的敌人强度加成
        enemy_strength_bonus = self.sect_manager.get_fortune_enemy_strength_bonus()
        if enemy_strength_bonus > 0:
            enemy.max_hp = int(enemy.max_hp * (1 + enemy_strength_bonus))
            enemy.hp = enemy.max_hp
            enemy.attack = int(enemy.attack * (1 + enemy_strength_bonus))
            enemy.defense = int(enemy.defense * (1 + enemy_strength_bonus))
            self.notify(
                f"[orange]宗门气运影响，{enemy.name} 受到强化，"
                f"全属性提升 {int(enemy_strength_bonus * 100)}%！"
            )
        # 天时环境敌人强度加成
        weather_strength_bonus = self.weather_manager.get_enemy_strength_bonus()
        if weather_strength_bonus > 0:
            enemy.max_hp = int(enemy.max_hp * (1 + weather_strength_bonus))
            enemy.hp = enemy.max_hp
            enemy.attack = int(enemy.attack * (1 + weather_strength_bonus))
            enemy.defense = int(enemy.defense * (1 + weather_strength_bonus))
            self.notify(
                f"[red]天象异变，{enemy.name} 受到强化，"
                f"全属性提升 {int(weather_strength_bonus * 100)}%！"
            )
        # 道侣助战加成提示
        if getattr(self, "companion_atk_bonus", 0.0) > 0 or getattr(self, "companion_def_bonus", 0.0) > 0:
            self.notify(
                f"[pink]道侣默默相助，攻击提升 {int(self.companion_atk_bonus * 100)}%，"
                f"防御提升 {int(self.companion_def_bonus * 100)}%。"
            )
        # 把战斗对象暂存，方便 UI 弹窗使用
        self.current_enemy = enemy
        # 维度③·M15：战斗开始时自动部署生活流派法宝为临时增益（flag 门控）
        if self.is_feature_enabled("hundred_schools"):
            self._auto_deploy_lifepath_consumables()
        self.notify("__COMBAT_START__")

    def end_combat(self):
        """结束战斗：对整场战斗未使用的技能进行熟练度衰减，并返回提示信息。"""
        # 清除城池防卫战标记，避免误带入下一场战斗
        self.current_combat_is_city_defense = False
        used = getattr(self, "_combat_used_skills", set())
        decay_amount = getattr(self.player, "SKILL_PROFICIENCY_DECAY_PER_COMBAT", 1)
        decayed = []
        level_dropped = []
        for sid in self.player.skills:
            if sid not in used:
                decayed_flag, dropped_flag = self.player.decay_skill_proficiency(sid, decay_amount)
                if decayed_flag:
                    decayed.append(sid)
                    if dropped_flag:
                        level_dropped.append(sid)
        self._combat_used_skills = set()
        if not decayed:
            return ""
        names = [getattr(self.skill_library.get(sid), "name", sid) for sid in decayed]
        msg = f"[gray]战斗结束，以下技能久未施展，熟练度略有消退：{', '.join(names)}"
        if level_dropped:
            drop_names = [getattr(self.skill_library.get(sid), "name", sid) for sid in level_dropped]
            msg += f"  [red]其中 {', '.join(drop_names)} 熟练度掉级！"
        self.notify(msg)
        return msg

    # ==================== 维度③·M15 生活法宝战斗部署 ====================
    # ==================== 维度③·M15 生活法宝战斗部署 ====================
    def deploy_battle_consumable(self, item_id):
        """将生活流派自产的法宝部署为战斗临时增益。

        仅 life_path.produce 中带 battle_buff 的物品可被部署（符箓/阵盘）。
        消耗 1 个该物品，按配置施加战斗 buff（削敌攻/增己攻/护盾等），
        随 _tick_buffs 衰减，下一场 start_combat 自动重置。
        返回 (ok, message)。
        """
        if not self.is_feature_enabled("hundred_schools"):
            return False, "百家争鸣未开启，无法部署生活法宝。"
        cfg = self.hundred_schools_manager.get_battle_deploy_cfg(item_id)
        if not cfg:
            return False, "该物品不可在战斗中部署。"
        if self.player.count_item(item_id) < 1:
            return False, "背包中没有该法宝，无法部署。"
        # 消耗 1 个法宝
        self.player.consume_items(item_id, 1)
        buff_name = cfg.get("name", "法宝")
        buff_desc = cfg.get("desc", "")
        applied = []
        turns = 3
        if "player_attack_up" in cfg:
            b = cfg["player_attack_up"]
            self.player_attack_up.append({"ratio": b["ratio"], "turns": b["turns"]})
            applied.append("攻击")
            turns = b["turns"]
        if "player_defense_up" in cfg:
            b = cfg["player_defense_up"]
            self.player_defense_up.append({"ratio": b["ratio"], "turns": b["turns"]})
            applied.append("防御")
            turns = b["turns"]
        if "enemy_attack_down" in cfg:
            b = cfg["enemy_attack_down"]
            self.enemy_attack_down.append({"ratio": b["ratio"], "turns": b["turns"]})
            applied.append("削敌攻")
            turns = b["turns"]
        if "enemy_defense_down" in cfg:
            b = cfg["enemy_defense_down"]
            self.enemy_defense_down.append({"ratio": b["ratio"], "turns": b["turns"]})
            applied.append("破敌防")
            turns = b["turns"]
        if "player_shield" in cfg:
            self.player_shield += cfg["player_shield"]
            applied.append("护盾")
        msg = (
            f"[cyan]你展开{buff_name}！{buff_desc}"
            f"（{'、'.join(applied)}加成已生效，持续 {turns} 回合）"
        )
        self.notify(msg)
        return True, msg

    def get_deployable_battle_consumables(self):
        """维度③·M16：返回玩家持有且『可战斗部署』的生活法宝清单。

        仅 life_path.produce 中带 battle_buff 的物品（符箓/阵盘）计入。
        每项：{"item_id", "name", "count", "desc"}，用于战斗中手动部署 UI 与发现提示。
        flag 未开启或无货时返回空列表。
        """
        result = []
        if not self.is_feature_enabled("hundred_schools"):
            return result
        for prod in self.hundred_schools_manager.config.get_life_path().get("produce", {}).values():
            item_id = prod.get("item_id")
            if item_id and "battle_buff" in prod:
                cnt = self.player.count_item(item_id)
                if cnt >= 1:
                    cfg = prod["battle_buff"]
                    result.append({
                        "item_id": item_id,
                        "name": cfg.get("name", item_id),
                        "count": cnt,
                        "desc": cfg.get("desc", ""),
                    })
        return result

    def _auto_deploy_lifepath_consumables(self):
        """维度③·M15：战斗开始时，若为生活流派法宝持有者且开启自动部署，则各部署 1 个。

        仅对 talisman/array 流派（lifepath_auto_deploy 为真）生效。该开关默认随
        choose_life_path 开启，可由玩家在「百家争鸣」面板关闭，避免无脑自动消耗；
        其余流派与旧档玩家 lifepath_auto_deploy 默认 False，不触发，对既有战斗数值基线零影响。
        """
        if not getattr(self.player, "lifepath_auto_deploy", False):
            return
        for prod in self.hundred_schools_manager.config.get_life_path().get("produce", {}).values():
            item_id = prod.get("item_id")
            if item_id and "battle_buff" in prod and self.player.count_item(item_id) >= 1:
                self.deploy_battle_consumable(item_id)

    def _get_terrain_combat_message(self):
        """
        获取当前地点特殊地形环境提示信息。
        寒冰原：水灵根玩家获得冰灵气加成
        雷泽：体修可借雷电淬体
        忘川河：魂修神识凝聚速度大增
        """
        location_id = self.player.location_id
        path = self.player.cultivation_path
        roots = self.player.spiritual_roots

        if location_id == "hanbing_yuan" and "water" in roots:
            return "[cyan]寒冰原冰灵气充沛，你的水灵根与此共鸣，伤害+10%！"
        if location_id == "leize" and path == "ti":
            return "[yellow]雷泽雷电交加，你借雷霆淬炼肉身，每回合怒气+2！"
        if location_id == "wangchuan_river" and path == "hun":
            return "[purple]忘川河畔亡魂游荡，你的神识汲取阴气，每回合神识翻倍！"
        return None

    def _apply_terrain_damage_bonus(self, damage):
        """
        应用地形伤害加成。
        寒冰原：有水灵根时水属性相关伤害 +10%（任意伤害均受冰灵气加持）
        """
        if self.player.location_id == "hanbing_yuan" and "water" in self.player.spiritual_roots:
            return int(damage * 1.1)
        return damage

    def _apply_terrain_resource_bonus(self, resource_name, amount):
        """
        应用地形资源加成。
        雷泽：体修怒气额外 +2
        忘川河：魂修神识额外翻倍（+amount 即等效翻倍）
        """
        if self.player.location_id == "leize" and self.player.cultivation_path == "ti" and resource_name == "rage":
            return amount + 2
        if self.player.location_id == "wangchuan_river" and self.player.cultivation_path == "hun" and resource_name == "hun_sense":
            return amount + amount  # 翻倍
        return amount

    def _apply_dot_effects(self, logs):
        """应用持续伤害效果。"""
        remaining_dots = []
        for dot in self.combat_dot_effects:
            damage = dot["damage"]
            self.player.health -= damage
            logs.append(f"[red]{dot['source']} 的毒素发作，你受到 {damage} 点持续伤害。")
            dot["turns"] -= 1
            if dot["turns"] > 0:
                remaining_dots.append(dot)
        self.combat_dot_effects = remaining_dots

    def _apply_environmental_effects(self, enemy, logs):
        """结算当前地点的环境效果（寒冰原霜冻、雷泽雷击、玄水祝福等）。"""
        location = self.world.get_location(self.player.location_id)
        if not location:
            return

        effects = location.get("environmental_effects", [])
        for effect in effects:
            if random.random() >= effect.get("chance", 0):
                continue

            effect_type = effect.get("type")
            if effect_type == "frost_slow":
                # 霜冻减速：降低玩家攻击力若干回合
                amount = effect.get("value", 0)
                turns = effect.get("turns", 1)
                if amount > 0:
                    self.player_attack_debuffs.append({"amount": amount, "turns": turns})
                    logs.append(effect["description"].format(value=amount, turns=turns))
            elif effect_type == "thunder_strike":
                # 雷击：随机轰击玩家或敌人
                damage = effect.get("value", 0)
                if damage <= 0:
                    continue
                if random.random() < 0.5:
                    actual = max(1, damage - self.player.defense // 2)
                    self.player.health -= actual
                    logs.append(f"{effect['description']}你遭到雷击，受到 {actual} 点伤害！")
                else:
                    actual = max(1, damage - enemy.defense // 2)
                    enemy.hp -= actual
                    logs.append(f"{effect['description']}{enemy.name} 遭到雷击，受到 {actual} 点伤害！")
            elif effect_type == "water_blessing":
                # 水灵祝福：对应属性玩家每回合恢复生命
                required_element = effect.get("element")
                if required_element and not self.player.has_element(required_element):
                    continue
                heal = effect.get("value", 0)
                if heal > 0:
                    self.player.health = min(self.player.max_health, self.player.health + heal)
                    logs.append(effect["description"].format(value=heal))

    def _get_enemy_defense_buff(self):
        """获取敌人当前所有防御 buff 的总值。"""
        return sum(b["amount"] for b in self.enemy_defense_buffs)

    def _get_player_attack_debuff(self):
        """获取玩家当前所有攻击削弱的总值。"""
        return sum(b["amount"] for b in self.player_attack_debuffs)

    def _tick_buffs(self, logs):
        """
        每回合结束时递减 buff 剩余回合数，过期则移除并提示。
        """
        # 递减敌人防御 buff
        remaining = []
        for buff in self.enemy_defense_buffs:
            buff["turns"] -= 1
            if buff["turns"] <= 0:
                logs.append(f"[orange]{self.current_enemy.name} 的防御强化消失了。")
            else:
                remaining.append(buff)
        self.enemy_defense_buffs = remaining

        # 递减玩家攻击削弱
        remaining = []
        for buff in self.player_attack_debuffs:
            buff["turns"] -= 1
            if buff["turns"] <= 0:
                logs.append("[green]你的力量恢复了，攻击削弱消失。")
            else:
                remaining.append(buff)
        self.player_attack_debuffs = remaining
        # 同步推进新增的战斗状态机
        self._tick_combat_states(logs)

    def _get_path_synergy(self, skill_element):
        """
        获取玩家流派与技能属性的协同倍率。
        例：剑修+金属性技能 → 1.2
        取玩家所有灵根中与该技能属性协同的最大值。
        """
        path_id = self.player.cultivation_path
        if not path_id:
            return 1.0
        # 取玩家主灵根（第一个）与流派的协同；融合灵根展开后取首个元素
        if not self.player.spiritual_roots:
            return 1.0
        main_elem = self.player.expanded_elements[0] if self.player.expanded_elements else self.player.spiritual_roots[0]
        return self.path_config.get_synergy_multiplier(path_id, main_elem)

    def _player_has_sword(self):
        """判断玩家是否装备了剑类武器（id 含 sword 或 name 含剑）。"""
        weapon = self.player.equipment.get("weapon")
        if not weapon:
            return False
        # 通过物品 ID 或名称判断是否为剑类
        if "sword" in weapon.id.lower() or "剑" in weapon.name:
            return True
        return False

    def _apply_skill_effects(self, skill, enemy, logs):
        """解析并应用技能的通用 effects 字段（控制、增益、持续伤害、护盾等）。"""
        effects = getattr(skill, "effects", None)
        if not effects:
            return
        for effect in effects:
            etype = effect.get("type")
            target = effect.get("target", "enemy")
            turns = effect.get("turns", 1)

            # 控制技能满级时额外持续 1 回合；辅助技能按熟练度延长 buff 持续
            control_extra_turn = 0
            support_extra_turn = 0
            skill_id_for_mastery = getattr(skill, "id", None)
            if skill_id_for_mastery:
                if self.player.is_skill_max_proficiency(skill_id_for_mastery):
                    control_extra_turn = self.player.SKILL_PROFICIENCY_MAX_CONTROL_EXTRA_TURN
                if self._get_skill_category(skill) == "support":
                    level = self.player.get_skill_proficiency(skill_id_for_mastery)
                    support_extra_turn = int((level - 1) * self.player.SKILL_PROFICIENCY_SUPPORT_EXTRA_TURN_PER_LEVEL)

            if etype == "stun" and target == "enemy":
                self.enemy_stunned = max(self.enemy_stunned, turns + control_extra_turn)
                logs.append(f"[purple]【{skill.name}】命中，敌人陷入眩晕 {turns + control_extra_turn} 回合！")

            elif etype == "seal" and target == "enemy":
                self.enemy_skill_sealed = max(self.enemy_skill_sealed, turns + control_extra_turn)
                logs.append(f"[purple]【{skill.name}】封印敌人技能 {turns + control_extra_turn} 回合！")

            elif etype == "taunt" and target == "enemy":
                self.enemy_taunted = max(self.enemy_taunted, turns + control_extra_turn)
                logs.append(f"[orange]【{skill.name}】嘲讽成功，敌人下回合只能攻击你！")

            elif etype == "attack_down" and target == "enemy":
                ratio = effect.get("ratio", 0.2)
                self.enemy_attack_down.append({"ratio": ratio, "turns": turns + control_extra_turn})
                logs.append(f"[orange]【{skill.name}】使敌人攻击力下降 {int(ratio * 100)}%，持续 {turns + control_extra_turn} 回合。")

            elif etype == "defense_down" and target == "enemy":
                ratio = effect.get("ratio", 0.2)
                self.enemy_defense_down.append({"ratio": ratio, "turns": turns + control_extra_turn})
                logs.append(f"[orange]【{skill.name}】使敌人防御力下降 {int(ratio * 100)}%，持续 {turns + control_extra_turn} 回合。")

            elif etype == "dot" and target == "enemy":
                damage_per_turn = effect.get("damage", 5)
                self.combat_dot_effects.append({
                    "source": skill.name,
                    "damage": damage_per_turn,
                    "turns": turns,
                })
                logs.append(f"[red]【{skill.name}】使敌人中毒，每回合受到 {damage_per_turn} 点伤害，持续 {turns} 回合。")

            elif etype == "shield" and target == "player":
                amount = effect.get("amount", 30)
                self.player_shield += amount
                logs.append(f"[green]【{skill.name}】为你生成 {amount} 点护盾（剩余 {self.player_shield} 点）。")

            elif etype == "reflect" and target == "player":
                ratio = effect.get("ratio", 0.3)
                self.player_reflect_ratio = max(self.player_reflect_ratio, ratio)
                logs.append(f"[green]【{skill.name}】使你获得 {int(ratio * 100)}% 伤害反弹，持续 {turns + support_extra_turn} 回合。")

            elif etype == "evasion_up" and target == "player":
                ratio = effect.get("ratio", 0.3)
                self.player_evasion_bonus = max(self.player_evasion_bonus, ratio)
                logs.append(f"[green]【{skill.name}】使你的闪避大幅提升 {int(ratio * 100)}%，持续 {turns + support_extra_turn} 回合。")

            elif etype == "attack_up" and target == "player":
                ratio = effect.get("ratio", 0.2)
                self.player_attack_up.append({"ratio": ratio, "turns": turns + support_extra_turn})
                logs.append(f"[green]【{skill.name}】使你的攻击力提升 {int(ratio * 100)}%，持续 {turns + support_extra_turn} 回合。")

            elif etype == "defense_up" and target == "player":
                ratio = effect.get("ratio", 0.2)
                self.player_defense_up.append({"ratio": ratio, "turns": turns + support_extra_turn})
                logs.append(f"[green]【{skill.name}】使你的防御力提升 {int(ratio * 100)}%，持续 {turns + support_extra_turn} 回合。")

            elif etype == "heal_over_time" and target == "player":
                amount = effect.get("amount", 10)
                self.player_hot.append({"amount": amount, "turns": turns})
                logs.append(f"[green]【{skill.name}】使你每回合恢复 {amount} 点生命，持续 {turns} 回合。")

            elif etype == "cleanse" and target == "player":
                self.player_cleanse = True
                logs.append(f"[green]【{skill.name}】净化了你身上的负面状态。")

    def _get_skill_category(self, skill):
        """根据技能属性与 effects 判断技能类型：伤害/治疗/控制/辅助。"""
        # 有治疗量或治疗类效果 => 治疗
        if getattr(skill, "heal", 0) > 0:
            return "heal"
        effects = getattr(skill, "effects", []) or []
        control_types = {"stun", "seal", "taunt", "attack_down", "defense_down", "immobilize"}
        heal_types = {"heal_over_time", "cleanse"}
        support_types = {"shield", "reflect", "evasion_up", "attack_up", "defense_up"}
        for effect in effects:
            etype = effect.get("type")
            if etype in control_types:
                return "control"
            if etype in heal_types:
                return "heal"
            if etype in support_types:
                return "support"
        return "damage"

    def _apply_mastery_max_level_bonus(self, skill_id, skill, enemy, logs):
        """满级熟练度特效：概率免冷却、技能专属特效、类别默认特效。"""
        if not self.player.is_skill_max_proficiency(skill_id):
            return

        # 所有满级技能共享：概率不进入冷却
        if random.random() < self.player.SKILL_PROFICIENCY_MAX_NO_COOLDOWN_CHANCE:
            self.player.set_skill_cooldown(skill_id, 0)
            logs.append(
                f"[gold]【{skill.name}】已达化境，施展后真气回流，本回合不进入冷却！"
            )
            return  # 已触发免冷却，不再触发其他满级特效

        # 优先应用 skills.json 中配置的专属满级特效
        mastery_effects = getattr(skill, "mastery_effects", []) or []
        if mastery_effects:
            for me in mastery_effects:
                chance = me.get("chance", 1.0)
                if random.random() < chance:
                    effect = {k: v for k, v in me.items() if k not in ("chance", "description")}
                    # 复用通用效果逻辑应用特效
                    self._apply_skill_effects(
                        type("_", (), {
                            "id": skill_id,
                            "name": skill.name,
                            "heal": 0,
                            "effects": [effect]
                        })(),
                        enemy, logs
                    )
                    desc = me.get("description", "触发专属化境效果")
                    logs.append(f"[purple]【{skill.name}】{desc}！")
            return

        # 没有专属特效时，按类别触发默认特效
        category = self._get_skill_category(skill)

        # 伤害技能：概率附加随机异常
        if category == "damage":
            if random.random() < self.player.SKILL_PROFICIENCY_MAX_DAMAGE_DEBUFF_CHANCE:
                debuffs = [
                    {"type": "stun", "turns": 1, "name": "眩晕"},
                    {"type": "seal", "turns": 1, "name": "封印"},
                    {"type": "dot", "damage": 10, "turns": 2, "name": "灼烧"},
                    {"type": "attack_down", "ratio": 0.2, "turns": 2, "name": "攻击削弱"},
                    {"type": "defense_down", "ratio": 0.2, "turns": 2, "name": "防御削弱"},
                ]
                debuff = random.choice(debuffs)
                self._apply_skill_effects(
                    type("_", (), {
                        "id": skill_id,
                        "name": skill.name,
                        "heal": 0,
                        "effects": [{"type": debuff["type"], "target": "enemy", **{k: v for k, v in debuff.items() if k not in ("type", "name")}}]
                    })(),
                    enemy, logs
                )
                logs.append(
                    f"[purple]【{skill.name}】已达化境，招式中蕴含玄机，"
                    f"敌人额外受到 {debuff['name']} 影响！"
                )

        # 治疗技能：概率净化自身负面状态
        elif category == "heal":
            if random.random() < self.player.SKILL_PROFICIENCY_MAX_HEAL_CLEANSE_CHANCE:
                self.player_cleanse = True
                logs.append(
                    f"[gold]【{skill.name}】已达化境，治疗之力涤荡身心，净化负面状态！"
                )

    def _get_enemy_attack_multiplier(self):
        """汇总敌人攻击削弱效果，返回剩余攻击比例。"""
        ratio = 1.0
        for buff in self.enemy_attack_down:
            ratio -= buff["ratio"]
        return max(0.1, ratio)

    def _get_enemy_defense_multiplier(self):
        """汇总敌人防御削弱效果，返回剩余防御比例。"""
        ratio = 1.0
        for buff in self.enemy_defense_down:
            ratio -= buff["ratio"]
        return max(0.1, ratio)

    def _get_player_attack_multiplier(self):
        """汇总玩家攻击增益效果。"""
        ratio = 1.0
        for buff in self.player_attack_up:
            ratio += buff["ratio"]
        return ratio

    def _get_player_defense_multiplier(self):
        """汇总玩家防御增益效果。"""
        ratio = 1.0
        for buff in self.player_defense_up:
            ratio += buff["ratio"]
        return ratio

    def _tick_combat_states(self, logs):
        """每回合结束时推进所有战斗状态持续时间。"""
        # 眩晕、嘲讽、封印
        if self.enemy_stunned > 0:
            self.enemy_stunned -= 1
            if self.enemy_stunned == 0:
                logs.append("[green]敌人从眩晕中恢复过来。")
        if self.enemy_taunted > 0:
            self.enemy_taunted -= 1
        if self.enemy_skill_sealed > 0:
            self.enemy_skill_sealed -= 1
            if self.enemy_skill_sealed == 0:
                logs.append("[yellow]敌人的技能封印解除。")
        if self.enemy_special_cooldown > 0:
            self.enemy_special_cooldown -= 1

        # 玩家眩晕
        if self.player_stunned > 0:
            self.player_stunned -= 1
            if self.player_stunned == 0:
                logs.append("[green]你的眩晕解除。")

        # 增益/减益持续回合
        def tick_list(buff_list, expire_msg):
            remaining = []
            expired = False
            for buff in buff_list:
                buff["turns"] -= 1
                if buff["turns"] > 0:
                    remaining.append(buff)
                else:
                    expired = True
            if expired:
                logs.append(expire_msg)
            return remaining

        self.enemy_attack_down = tick_list(self.enemy_attack_down, "[green]敌人的攻击削弱效果消失。")
        self.enemy_defense_down = tick_list(self.enemy_defense_down, "[green]敌人的防御削弱效果消失。")
        self.player_attack_up = tick_list(self.player_attack_up, "[orange]你的攻击提升效果消失。")
        self.player_defense_up = tick_list(self.player_defense_up, "[orange]你的防御提升效果消失。")

        # 持续恢复
        remaining_hot = []
        for hot in self.player_hot:
            heal = hot["amount"]
            self.player.health = min(self.player.max_health, self.player.health + heal)
            logs.append(f"[green]你恢复 {heal} 点生命（持续恢复）。")
            hot["turns"] -= 1
            if hot["turns"] > 0:
                remaining_hot.append(hot)
        self.player_hot = remaining_hot

        # 闪避加成仅持续当回合，此处清空（由技能在当回合设置）
        self.player_evasion_bonus = 0.0
        # 净化标记每回合重置
        self.player_cleanse = False

    def _apply_exclusive_skill_effects(self, skill, damage, enemy, logs):
        """
        处理流派专属技能的特殊效果，返回修正后伤害。
        旧流派：
        - true_qi_shield（真气护体）：恢复真气护盾至满（在 heal 分支处理，此处跳过）
        - mountain_break（破山裂地）：消耗全部怒气，每点怒气 +5% 伤害
        - one_sword_break（一剑破万法）：消耗全部剑意，每层 +10% 伤害
        - blood_sacrifice（血祭大法）：消耗自身 20% 生命，伤害 ×2
        - soul_devour（噬魂术）：造成伤害的 50% 转为自身真气
        - ten_thousand_souls（万魂幡）：邪气越高伤害越高（每点 +2%）
        新流派：
        - poison_pill（毒丹术）：附加 3 回合中毒 DOT
        - ten_thousand_weapons（万器归宗）：器灵每点 +5% 伤害
        - refine_artifact（祭炼诀）：永久 +5 基础攻击
        - beast_charge（万兽奔腾）：每只兽魂 +30% 伤害，消耗所有兽魂
        - beast_contract（灵兽契约）：造成伤害的 40% 转为自身生命
        - all_souls_return（万魂归一）：神识每点 +3% 伤害，消耗所有神识
        - soul_seize（摄魂术）：造成伤害的 60% 转为自身生命
        - dream_realm（梦境领域）：造成伤害的 30% 转为自身生命
        """
        sid = skill.id

        # ===== 老流派专属技能 =====
        # 破山裂地：消耗全部怒气，每点 +5% 伤害
        if sid == "mountain_break":
            rage = self.player.rage
            if rage > 0:
                damage = int(damage * (1.0 + rage * 0.05))
                logs.append(f"[orange]消耗 {rage} 点怒气，伤害激增！")
                self.player.rage = 0

        # 一剑破万法：消耗全部剑意，每层 +10% 伤害
        elif sid == "one_sword_break":
            intent = self.player.sword_intent
            if intent > 0:
                damage = int(damage * (1.0 + intent * 0.10))
                logs.append(f"[cyan]消耗 {intent} 层剑意，一剑破万法！")
                self.player.sword_intent = 0

        # 血祭大法：消耗自身 20% 生命，伤害 ×2
        elif sid == "blood_sacrifice":
            health_cost = int(self.player.max_health * 0.20)
            self.player.health -= health_cost
            damage = int(damage * 2.0)
            logs.append(f"[red]血祭大法！你消耗 {health_cost} 点生命，伤害翻倍！")

        # 噬魂术：造成伤害的 50% 转为自身真气
        elif sid == "soul_devour":
            qi_gain = int(damage * 0.5)
            self.player.qi += qi_gain
            logs.append(f"[green]噬魂术吸取灵力，你恢复 {qi_gain} 点真气。")

        # 万魂幡：邪气越高伤害越高（每点 +2%）
        elif sid == "ten_thousand_souls":
            evil = self.player.evil_qi
            damage = int(damage * (1.0 + evil * 0.02))
            logs.append(f"[red]万魂幡怨气冲天，邪气加持伤害！")

        # ===== 丹修专属技能 =====
        # 毒丹术：附加 3 回合中毒 DOT（每回合 8 点伤害）
        elif sid == "poison_pill":
            self.combat_dot_effects.append({
                "damage": 8 + self._get_realm_order() * 2,
                "turns": 3,
                "source": "毒丹",
            })
            logs.append(f"[red]毒丹入体！敌人将在 3 回合内持续受到毒害。")

        # ===== 器修专属技能 =====
        # 万器归宗：器灵每点 +5% 伤害，消耗所有器灵
        elif sid == "ten_thousand_weapons":
            spirit = self.player.qi_spirit
            if spirit > 0:
                damage = int(damage * (1.0 + spirit * 0.05))
                logs.append(f"[cyan]器灵共鸣！消耗 {spirit} 点器灵，伤害激增！")
                self.player.qi_spirit = 0

        # 祭炼诀：永久提升基础攻击 +5（每件武器仅可祭炼一次）
        elif sid == "refine_artifact":
            weapon = self.player.equipment.get("weapon")
            if not weapon:
                logs.append(f"[red]你未装备任何武器，无法祭炼！")
            elif weapon.id in self.player.refined_weapon_ids:
                # 该武器已祭炼过，不可重复祭炼
                logs.append(f"[red]这把【{weapon.name}】已祭炼过，无法再次祭炼！")
            else:
                self.player.base_attack += 5
                self.player.refined_weapon_ids.append(weapon.id)
                logs.append(f"[green]祭炼成功！【{weapon.name}】共鸣，你的基础攻击永久 +5。")

        # ===== 御兽修专属技能 =====
        # 万兽奔腾：每只兽魂 +30% 伤害，消耗所有兽魂
        elif sid == "beast_charge":
            souls = self.player.shou_soul
            if souls > 0:
                damage = int(damage * (1.0 + souls * 0.30))
                logs.append(f"[orange]万兽奔腾！消耗 {souls} 只兽魂，每只 +30% 伤害！")
                self.player.shou_soul = 0

        # 灵兽契约：造成伤害的 40% 转为自身生命
        elif sid == "beast_contract":
            heal_amount = int(damage * 0.4)
            self.player.health = min(self.player.max_health, self.player.health + heal_amount)
            logs.append(f"[green]灵兽契约生效，你恢复 {heal_amount} 点生命。")

        # ===== 魂修专属技能 =====
        # 万魂归一：神识每点 +3% 伤害，消耗所有神识
        elif sid == "all_souls_return":
            sense = self.player.hun_sense
            if sense > 0:
                damage = int(damage * (1.0 + sense * 0.03))
                logs.append(f"[purple]万魂归一！消耗 {sense} 点神识，伤害暴涨！")
                self.player.hun_sense = 0
                # 魂修反噬：神识归零后下回合眩晕
                if self.player.hun_sense == 0:
                    self.player_stunned = 1
                    logs.append(f"[red]神识枯竭，反噬将至！下回合你将陷入眩晕。")

        # 摄魂术：造成伤害的 60% 转为自身生命
        elif sid == "soul_seize":
            heal_amount = int(damage * 0.6)
            self.player.health = min(self.player.max_health, self.player.health + heal_amount)
            logs.append(f"[purple]摄魂夺魄！你吸取 {heal_amount} 点生命。")

        # 梦境领域：造成伤害的 30% 转为自身生命
        elif sid == "dream_realm":
            heal_amount = int(damage * 0.3)
            self.player.health = min(self.player.max_health, self.player.health + heal_amount)
            logs.append(f"[purple]梦境领域！你吸取 {heal_amount} 点生命。")

        # ===== 阵修专属技能 =====
        # 九宫八卦阵：消耗 5 阵纹，概率困住敌人 2 回合（当回合立即生效）
        elif sid == "bagua_formation":
            cost = 5
            if self.player.zhen_rune >= cost:
                self.player.zhen_rune -= cost
                # 控制成功率 = 70% + 流派控制加成 + 熟练度控制加成
                success_rate = 0.7 + self.player.control_bonus + self.player.get_skill_control_bonus(sid)
                # 显示成功率百分比，提升玩家策略感（阵纹越多越稳）
                rate_pct = int(success_rate * 100)
                logs.append(f"[cyan]八卦阵成功率: {rate_pct}%（消耗 5 阵纹，剩余 {self.player.zhen_rune}）")
                if random.random() < success_rate:
                    # 困敌 2 回合：本回合+下回合（turns=2，本回合敌人不行动）
                    self.formation_active = {"type": "trap", "turns": 2}
                    # 标记本回合刚布阵成功，敌人立即被困
                    self.formation_just_activated = True
                    logs.append(f"[purple]九宫八卦阵成！敌人被困 2 回合无法行动！")
                else:
                    logs.append(f"[purple]八卦阵未能困住敌人，但仍造成伤害。")
            else:
                logs.append(f"[red]阵纹不足，阵法威力减弱。")

        # 困仙阵：消耗 4 阵纹，敌人 3 回合内攻防下降 40%
        elif sid == "trap_immortal":
            cost = 4
            if self.player.zhen_rune >= cost:
                self.player.zhen_rune -= cost
                self.formation_active = {"type": "weaken", "turns": 3, "ratio": 0.4}
                logs.append(f"[purple]困仙阵成！敌人 3 回合内攻防下降 40%！")
            else:
                logs.append(f"[red]阵纹不足，阵法威力减弱。")

        # 万阵归一：消耗所有阵纹，每点 +10% 伤害
        elif sid == "all_formations_return":
            runes = self.player.zhen_rune
            if runes > 0:
                damage = int(damage * (1.0 + runes * 0.10))
                logs.append(f"[purple]万阵归一！消耗 {runes} 阵纹，伤害激增！")
                self.player.zhen_rune = 0

        # 五行阵法：需要五行灵根，造成全属性伤害（已在元素检查中处理 "all" 属性需求）
        elif sid == "five_element_formation_zhen":
            # 五行灵根检查在元素限制逻辑中处理，这里仅记录特效
            logs.append(f"[purple]五行阵法启动，天地之力汇聚！")

        # ===== 符修专属技能 =====
        # 五雷符：消耗 1 符箓，高暴击
        elif sid == "thunder_seal":
            if self.player.fu_seal >= 1:
                self.player.fu_seal -= 1
                # 50% 暴击率
                if random.random() < 0.5:
                    damage = int(damage * 2.0)
                    logs.append(f"[yellow]五雷符暴击！伤害翻倍！")
            else:
                logs.append(f"[red]符箓不足，技能威力大减！")
                damage = int(damage * 0.3)

        # 镇妖符：消耗 2 符箓，封印敌人技能 2 回合
        elif sid == "demon_seal":
            if self.player.fu_seal >= 2:
                self.player.fu_seal -= 2
                self.enemy_skill_sealed = 2
                logs.append(f"[yellow]镇妖符生效！敌人技能被封印 2 回合！")
            else:
                logs.append(f"[red]符箓不足，无法封印敌人技能。")

        # 万符诀：消耗 5 符箓，伤害 ×5
        elif sid == "ten_thousand_seals":
            if self.player.fu_seal >= 5:
                self.player.fu_seal -= 5
                damage = damage * 5
                logs.append(f"[yellow]万符诀！连发 5 张符箓，伤害暴涨！")
            else:
                logs.append(f"[red]符箓不足 {self.player.fu_seal}/5，威力大减！")
                damage = int(damage * 0.2)

        # 血符术：消耗 1 符箓 + 20% 生命，伤害 ×3 + 吸血
        elif sid == "blood_seal":
            if self.player.fu_seal >= 1:
                self.player.fu_seal -= 1
                health_cost = int(self.player.max_health * 0.20)
                self.player.health -= health_cost
                damage = int(damage * 3.0)
                # 吸血 50%
                heal_amount = int(damage * 0.5)
                self.player.health = min(self.player.max_health, self.player.health + heal_amount)
                logs.append(
                    f"[red]血符术！消耗 {health_cost} 生命+1 符箓，伤害 ×3，吸血 {heal_amount}！"
                )
            else:
                logs.append(f"[red]符箓不足，血符术失效！")
                damage = int(damage * 0.3)

        return damage

    def _apply_player_defense_mechanics(self, damage, enemy, logs):
        """
        应用玩家流派防御机制，返回实际扣血量。
        - 法修：真气护盾优先抵消（2 点护盾抵 1 点伤害）
        - 体修：受击积累怒气，20% 概率反震 50% 伤害
        - 邪修：受击积累邪气
        - 丹修：受击积累丹火（每回合 +2）
        - 器修：受击积累器灵（每次 +3）
        - 御兽修：受击时兽魂有概率抵挡（每只兽魂抵挡 5% 伤害）
        - 魂修：受击积累神识（+5），但血量低抗性差
        """
        path_id = self.player.cultivation_path

        # 法修：真气护盾抵消
        if path_id == "fa" and self.player.shield_qi > 0:
            # 2 点护盾抵 1 点伤害
            absorbable = self.player.shield_qi // 2
            absorbed = min(damage, absorbable)
            if absorbed > 0:
                self.player.shield_qi -= absorbed * 2
                damage -= absorbed
                logs.append(
                    f"[cyan]真气护盾抵消了 {absorbed} 点伤害"
                    f"（剩余护盾 {self.player.shield_qi}）。"
                )

        # 体修：受击积累怒气 + 20% 概率反震 50% 伤害
        if path_id == "ti":
            rage_gain = max(5, damage // 10)
            old_rage = self.player.rage
            self.player.add_path_resource(rage_gain)
            if self.player.rage > old_rage and self.player.rage >= 50 and old_rage < 50:
                logs.append("[orange]怒气沸腾，你的攻击力大增！")
            # 反震判定：20% 概率反弹 50% 伤害
            if random.random() < 0.20 and damage > 0:
                reflect = max(1, int(damage * 0.5))
                actual_reflect = enemy.take_damage(reflect)
                logs.append(
                    f"[orange]体修反震！你反弹 {actual_reflect} 点伤害给 {enemy.name}！"
                )

        # 邪修：受击积累邪气
        if path_id == "xie":
            self.player.add_path_resource(3)

        # 丹修：受击积累丹火（+2）
        if path_id == "dan":
            self.player.add_path_resource(2)
            # 丹修自带 10% 减伤（药石之躯）
            damage = int(damage * 0.9)

        # 器修：受击积累器灵（+3），装备防御加成已在 defense 属性中生效
        if path_id == "qi":
            self.player.add_path_resource(3)

        # 御兽修：兽魂抵挡（每只兽魂抵挡 5% 伤害，不消耗兽魂）
        if path_id == "shou" and self.player.shou_soul > 0:
            block_ratio = min(0.5, self.player.shou_soul * 0.05)
            blocked = int(damage * block_ratio)
            if blocked > 0:
                damage -= blocked
                logs.append(
                    f"[green]灵兽护主！抵挡 {blocked} 点伤害"
                    f"（兽魂 {self.player.shou_soul} 只）。"
                )

        # 魂修：受击积累神识（+5），血薄无减伤
        if path_id == "hun":
            self.player.add_path_resource(5)

        # 宗门护山大阵：在宗门领地激活时提供额外减伤
        formation_def = self.sect_manager.get_formation_defense_bonus()
        if formation_def > 0:
            damage = int(damage * (1.0 - formation_def))

        # 确保伤害不为负
        return max(0, damage)

    def _apply_player_shield_and_reflect(self, damage, enemy, logs):
        """应用玩家护盾抵消与反弹伤害，返回实际扣血量。"""
        # 护盾抵消
        if self.player_shield > 0:
            absorbed = min(damage, self.player_shield)
            self.player_shield -= absorbed
            damage -= absorbed
            logs.append(f"[cyan]护盾抵消 {absorbed} 点伤害（剩余 {self.player_shield} 点）。")
        # 反弹伤害
        if damage > 0 and self.player_reflect_ratio > 0 and enemy and hasattr(enemy, "take_damage"):
            reflect = max(1, int(damage * self.player_reflect_ratio))
            actual_reflect = enemy.take_damage(reflect)
            logs.append(f"[orange]反弹 {actual_reflect} 点伤害给 {enemy.name}！")
        return max(0, damage)

    def _apply_path_attack_mechanics(self, damage, enemy, logs, is_skill=False):
        """
        应用玩家流派攻击机制，返回修正后伤害。
        - 剑修：剑意加成（每层 +5%）+ 暴击（普通攻击和技能均可暴击）
        - 体修：怒气加成（怒气越高攻击越强）
        - 邪修：邪气加成（每点邪气 +1% 攻击）
        - 法修：技能伤害 ×1.3（来自 skill_damage_mult）
        - 丹修：丹火加成（每点丹火 +0.5% 攻击）
        - 器修：器灵加成（每点器灵 +1% 攻击）
        - 御兽修：兽魂加成（每只兽魂 +5% 攻击）
        - 魂修：神识加成（每点神识 +1.5% 技能伤害）
        - 所有流派：技能伤害应用 skill_damage_mult
        """
        path_id = self.player.cultivation_path

        # 技能伤害流派修正（法修 ×1.3、剑修 ×1.2、邪修 ×1.2、体修 ×0.8、魂修 ×1.8 等）
        if is_skill:
            damage = int(damage * self.player.skill_damage_mult)

        # 流派+灵根协同（对技能和普攻均生效）
        synergy = self._get_path_synergy(path_id if is_skill else path_id)
        if synergy > 1.0 and is_skill:
            damage = int(damage * synergy)

        # 剑修：剑意加成
        if path_id == "jian":
            intent_bonus = 1.0 + self.player.sword_intent * 0.05
            damage = int(damage * intent_bonus)
            # 剑修装备依赖：无剑时伤害 ×0.6
            if not self._player_has_sword():
                damage = int(damage * 0.6)
                logs.append(f"[red]你未装备剑类武器，剑意难以发挥，伤害削弱！")
            # 剑修暴击判定
            if random.random() < self.player.crit_rate_bonus:
                damage = int(damage * self.player.crit_damage_mult)
                logs.append(f"[cyan]暴击！剑光一闪，伤害暴增！")

        # 体修：怒气加成（每点怒气 +0.5% 攻击）
        if path_id == "ti":
            rage_bonus = 1.0 + self.player.rage * 0.005
            damage = int(damage * rage_bonus)

        # 邪修：邪气加成（每点邪气 +1% 攻击）
        if path_id == "xie":
            evil_bonus = 1.0 + self.player.evil_qi * 0.01
            damage = int(damage * evil_bonus)

        # 丹修：丹火加成（每点丹火 +0.5% 攻击，丹火越高炼丹越精纯）
        if path_id == "dan":
            dan_bonus = 1.0 + self.player.dan_fire * 0.005
            damage = int(damage * dan_bonus)

        # 器修：器灵加成（每点器灵 +1% 攻击，器灵越高法宝越强）
        if path_id == "qi":
            spirit_bonus = 1.0 + self.player.qi_spirit * 0.01
            damage = int(damage * spirit_bonus)

        # 御兽修：兽魂加成（每只兽魂 +5% 攻击，灵兽助战）
        if path_id == "shou":
            soul_bonus = 1.0 + self.player.shou_soul * 0.05
            damage = int(damage * soul_bonus)

        # 魂修：神识加成（每点神识 +1.5% 技能伤害，仅技能生效）
        if path_id == "hun" and is_skill:
            sense_bonus = 1.0 + self.player.hun_sense * 0.015
            damage = int(damage * sense_bonus)

        # 本命法宝：已解锁并装备时，所有伤害 +10%
        if self.player.has_feature("life_treasure") and self.player.equipment.get("life_treasure"):
            damage = int(damage * 1.1)

        # 正道 / 魔道阵营克制：对对立阵营敌人伤害 +10%
        camp_mult = self.sect_manager.get_camp_combat_multiplier(enemy)
        if camp_mult != 1.0:
            damage = int(damage * camp_mult)
            camp_name = self.player.get_camp_name()
            logs.append(f"[white]【{camp_name}】阵营之力，你对该敌人造成额外伤害！")

        return damage

    def combat_round(self, enemy, action="attack", skill_id=None):
        """进行一个战斗回合，返回本回合日志和战斗状态。"""
        # element_multiplier 定义于 engine 模块级，方法内延迟导入避免循环依赖
        # （与 engine_combat_mixin._apply_enemy_element_multiplier 同一约定）
        from game.engine import element_multiplier

        logs = []

        # 计算境界压制系数
        player_modifier = self._combat_damage_modifier(enemy)
        enemy_modifier = 2.0 - player_modifier  # 玩家越强，敌人越弱

        # 回合开始时先结算 DOT 伤害
        self._apply_dot_effects(logs)
        if not self.player.is_alive():
            if self._try_nascent_soul_revive(logs):
                return logs, "continue"
            return logs, "lose"

        # 结算当前地点的环境效果（霜冻、雷击、水灵祝福等）
        self._apply_environmental_effects(enemy, logs)
        if not self.player.is_alive():
            if self._try_nascent_soul_revive(logs):
                return logs, "continue"
            return logs, "lose"
        if not enemy.is_alive():
            # 环境效果直接击杀敌人时按胜利结算
            return logs, "win"

        if action == "skill" and skill_id:
            skill = self.skill_library.get(skill_id)
            if not skill or skill_id not in self.player.skills:
                logs.append("你不会这个技能。")
                return logs, "continue"

            if self.player.get_skill_cooldown(skill_id) > 0:
                logs.append(f"【{skill.name}】还在冷却中。")
                return logs, "continue"

            # 根据熟练度计算实际消耗，越熟练消耗越少
            effective_cost = self._get_effective_qi_cost(skill_id)
            if self.player.qi < effective_cost:
                logs.append(f"真气不足，无法施展【{skill.name}】！")
                return logs, "continue"

            # 灵根属性检查：玩家灵根必须包含技能属性才能施展
            if not self.player.has_element(skill.element):
                elem_cn = ELEMENT_NAMES.get(skill.element, skill.element)
                logs.append(
                    f"你的灵根无法驾驭【{skill.name}】（需{elem_cn}属性灵根）！"
                )
                return logs, "continue"

            # 境界要求检查：未达境界仍可强行施展，按成功率判定
            if skill.realm_id and self._get_realm_order() < self.player.REALM_ORDER.get(skill.realm_id, 0):
                success_rate = self.get_skill_success_rate(skill_id)
                realm_data = self.world.get_realm(skill.realm_id)
                realm_name = realm_data.get("name", skill.realm_id) if realm_data else skill.realm_id
                if random.random() > success_rate:
                    # 施展失败：消耗部分真气并受到反噬伤害
                    cost = max(1, int(effective_cost * 0.5))
                    self.player.qi -= cost
                    diff = self.player.REALM_ORDER.get(skill.realm_id, 0) - self._get_realm_order()
                    backlash = max(5, int(effective_cost * 0.2 * diff))
                    self.player.health -= backlash
                    logs.append(
                        f"[red]你强行施展【{skill.name}】失败！境界差距过大，"
                        f"真气反噬，损失 {cost} 点真气并受到 {backlash} 点反噬伤害。"
                    )
                    if not self.player.is_alive():
                        if self._try_nascent_soul_revive(logs):
                            return logs, "continue"
                        return logs, "lose"
                    return logs, "continue"
                else:
                    logs.append(
                        f"[cyan]你以低境界强行催动【{skill.name}】，竟一举成功！"
                        f"（需{realm_name}，成功率 {int(success_rate * 100)}%）"
                    )

            # 流派专属技能检查：需对应流派才能施展
            if skill.path_exclusive and self.player.cultivation_path != skill.path_exclusive:
                path_names = {"fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
                              "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
                              "zhen": "阵修", "fu": "符修"}
                need_path = path_names.get(skill.path_exclusive, skill.path_exclusive)
                logs.append(
                    f"【{skill.name}】为{need_path}专属技能，你的流派无法施展！"
                )
                return logs, "continue"

            # 剑修专属技能装备检查：需装备剑类武器
            if skill.path_exclusive == "jian" and not self._player_has_sword():
                logs.append(f"【{skill.name}】需要装备剑类武器才能施展！")
                return logs, "continue"

            # 记录本场战斗已使用过该技能
            self._combat_used_skills.add(skill_id)

            # 消耗真气并进入冷却，同时增加该技能熟练度
            self.player.qi -= effective_cost
            self.player.set_skill_cooldown(skill_id, skill.cooldown + 1)
            leveled_up = self.player.gain_skill_exp(skill_id)
            if leveled_up:
                logs.append(
                    f"[gold]【{skill.name}】熟练度提升至 Lv.{self.player.get_skill_proficiency(skill_id)}！"
                )

            # 法修专属：真气护体 - 恢复真气护盾至满
            if skill_id == "true_qi_shield":
                self.player.shield_qi = 100
                logs.append(f"[green]你施展【{skill.name}】，真气护盾恢复至 100！")
                self.notify("__EFFECT_HEAL__")
                # 通用技能效果（如配置中的 shield/reflect 等）同步生效
                self._apply_skill_effects(skill, enemy, logs)
                # 满级熟练度特效（免冷却/净化等）
                self._apply_mastery_max_level_bonus(skill_id, skill, enemy, logs)
            elif skill.heal > 0:
                heal_amount = self._calculate_skill_heal(skill)
                self.player.health += heal_amount
                self.player.health = min(self.player.health, self.player.max_health)
                # [green] 玩家治疗行为
                logs.append(f"[green]你施展【{skill.name}】，恢复 {heal_amount} 点健康。")
                # 治疗特效
                self.notify("__EFFECT_HEAL__")
                # 治疗技能也可能附带控制、增益、护盾等效果
                self._apply_skill_effects(skill, enemy, logs)
                # 满级熟练度特效（免冷却/净化等）
                self._apply_mastery_max_level_bonus(skill_id, skill, enemy, logs)
            else:
                # 闪避判定
                if self._enemy_dodged(enemy):
                    logs.append(f"{enemy.name} 身形一闪，躲过了【{skill.name}】！")
                else:
                    # 动态技能伤害，再乘境界修正
                    skill_damage = self._calculate_skill_damage(skill)
                    # 考虑玩家被削弱的攻击力（debuff 影响武器加成部分）
                    skill_damage -= self._get_player_attack_debuff() * 0.5
                    damage = int(skill_damage * player_modifier)
                    # 应用玩家攻击增益
                    damage = int(damage * self._get_player_attack_multiplier())
                    # 五行相克判定：技能属性 vs 敌人属性
                    elem_mult = element_multiplier(skill.element, enemy.element)
                    if elem_mult > 1.0:
                        logs.append(
                            f"[cyan]五行相克！你的{ELEMENT_NAMES.get(skill.element, '?')}属性"
                            f"克制对方{ELEMENT_NAMES.get(enemy.element, '?')}属性，伤害激增！"
                        )
                    elif elem_mult < 1.0:
                        logs.append(
                            f"[red]五行受制！你的{ELEMENT_NAMES.get(skill.element, '?')}属性"
                            f"被对方{ELEMENT_NAMES.get(enemy.element, '?')}属性克制，伤害削弱。"
                        )
                    damage = int(damage * elem_mult)
                    # 灵根纯度加成：纯度越高，该属性技能伤害越高
                    purity = self.player.get_root_purity(skill.element)
                    damage = int(damage * purity)
                    # 天时环境元素伤害加成（天气、季节、灵气潮汐）
                    weather_elem_bonus = self.weather_manager.get_element_damage_bonus(
                        skill.element
                    )
                    if weather_elem_bonus > 0:
                        damage = int(damage * (1 + weather_elem_bonus))
                        logs.append(
                            f"[cyan]天象相助，{ELEMENT_NAMES.get(skill.element, '?')}属性"
                            f"伤害提升 {int(weather_elem_bonus * 100)}%！"
                        )
                    elif weather_elem_bonus < 0:
                        damage = int(damage * (1 + weather_elem_bonus))
                        logs.append(
                            f"[red]天象不利，{ELEMENT_NAMES.get(skill.element, '?')}属性"
                            f"伤害降低 {int(-weather_elem_bonus * 100)}%。"
                        )
                    # 地形元素加成（来自 combat_extension）
                    terrain_bonus = self.combat_extension_manager.get_terrain_element_bonus(
                        skill.element
                    )
                    if terrain_bonus > 0:
                        damage = int(damage * (1 + terrain_bonus))
                        terrain_name = self.combat_extension_manager.get_terrain_name()
                        logs.append(
                            f"[cyan]{terrain_name}灵气相助，"
                            f"{ELEMENT_NAMES.get(skill.element, '?')}属性伤害提升 "
                            f"{int(terrain_bonus * 100)}%！"
                        )
                    elif terrain_bonus < 0:
                        damage = int(damage * (1 + terrain_bonus))
                        terrain_name = self.combat_extension_manager.get_terrain_name()
                        logs.append(
                            f"[red]{terrain_name}灵气不利，"
                            f"{ELEMENT_NAMES.get(skill.element, '?')}属性伤害降低 "
                            f"{int(-terrain_bonus * 100)}%。"
                        )
                    # 心法与神通元素伤害加成
                    mind_elem_bonus = self.mind_method_manager.get_element_damage_bonus(
                        skill.element
                    )
                    divine_elem_bonus = self.divine_art_manager.get_element_damage_bonus(
                        skill.element
                    )
                    total_elem_bonus = mind_elem_bonus + divine_elem_bonus
                    if total_elem_bonus > 0:
                        damage = int(damage * (1 + total_elem_bonus))
                    # 连携加成
                    combo_bonus = self.combat_extension_manager.check_combo(skill_id)
                    if combo_bonus > 0:
                        damage = int(damage * (1 + combo_bonus))
                        logs.append(f"[gold]连招触发！伤害提升 {int(combo_bonus * 100)}%。")
                    # 记录本回合使用的技能，用于下回合连携判定
                    self.combat_extension_manager.record_skill_used(skill_id)
                    # 流派攻击机制：技能伤害修正、协同、剑意/怒气/邪气加成、暴击
                    damage = self._apply_path_attack_mechanics(
                        damage, enemy, logs, is_skill=True
                    )
                    # 流派克制判定（仅对有流派的人形敌人生效）
                    path_counter = self.path_config.get_counter_multiplier(
                        self.player.cultivation_path, enemy.cultivation_path
                    )
                    # 流派中文名映射（含新流派）
                    path_names = {
                        "fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
                        "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
                        "zhen": "阵修", "fu": "符修",
                    }
                    if path_counter > 1.0:
                        logs.append(
                            f"[cyan]流派克制！你的{path_names.get(self.player.cultivation_path, '')}"
                            f"克制对方{path_names.get(enemy.cultivation_path, '')}，伤害激增！"
                        )
                    elif path_counter < 1.0:
                        logs.append(
                            f"[red]流派受制！对方{path_names.get(enemy.cultivation_path, '')}"
                            f"克制你的{path_names.get(self.player.cultivation_path, '')}，伤害削弱。"
                        )
                    damage = int(damage * path_counter)
                    # 专属技能特殊效果处理
                    damage = self._apply_exclusive_skill_effects(
                        skill, damage, enemy, logs
                    )
                    # 通用技能效果处理（控制、增益、持续伤害等）
                    self._apply_skill_effects(skill, enemy, logs)
                    # 满级熟练度特效（免冷却/附加异常等）
                    self._apply_mastery_max_level_bonus(skill_id, skill, enemy, logs)
                    # 应用特殊地形伤害加成（如寒冰原水灵根+10%）
                    damage = self._apply_terrain_damage_bonus(damage)
                    # 魂修无视防御：直接以伤害扣血，不应用敌人物理防御
                    if self.player.ignore_defense:
                        actual = max(1, damage)
                        enemy.hp = max(0, enemy.hp - actual)
                        logs.append(f"[purple]神识攻击无视防御！")
                    else:
                        # 考虑敌人临时防御加成（法术 buff 仍生效）
                        damage -= self._get_enemy_defense_buff()
                        # 应用敌人防御削弱
                        damage = int(damage * self._get_enemy_defense_multiplier())
                        actual = enemy.take_damage(max(1, damage))
                    # [cyan] 玩家攻击行为
                    logs.append(f"[cyan]你施展【{skill.name}】，对 {enemy.name} 造成 {actual} 点伤害。")
                    # 战斗扩展：记录造成伤害
                    self.combat_extension_manager.record_damage(actual, is_player=True)
                    # 发送技能特效标记
                    if skill.id == "sword_art":
                        self.notify("__EFFECT_SWORD__")
                    elif skill.id == "thunder_palm":
                        self.notify("__EFFECT_THUNDER__")

        elif action == "attack":
            # 玩家普通攻击
            if self._enemy_dodged(enemy):
                logs.append(f"{enemy.name} 躲开了你的攻击！")
            else:
                # 考虑玩家被削弱的攻击力
                # 玩家攻击力叠加道侣助战百分比加成与灵兽助战固定加成
                companion_atk = getattr(self, "companion_atk_bonus", 0.0)
                effective_attack = max(
                    1,
                    int(self.player.attack * (1 + companion_atk))
                    + self.sect_manager.get_beast_combat_bonus()
                    - self._get_player_attack_debuff(),
                )
                damage = int(effective_attack * player_modifier)
                # 应用玩家攻击增益
                damage = int(damage * self._get_player_attack_multiplier())
                # 流派攻击机制：剑意/怒气/邪气加成、暴击（普攻不应用 skill_damage_mult）
                damage = self._apply_path_attack_mechanics(
                    damage, enemy, logs, is_skill=False
                )
                # 应用特殊地形伤害加成（如寒冰原水灵根+10%）
                damage = self._apply_terrain_damage_bonus(damage)
                # 考虑敌人临时防御加成
                damage -= self._get_enemy_defense_buff()
                # 应用敌人防御削弱
                damage = int(damage * self._get_enemy_defense_multiplier())
                actual = enemy.take_damage(max(1, damage))
                # [cyan] 玩家攻击行为
                logs.append(f"[cyan]你出手攻击，对 {enemy.name} 造成 {actual} 点伤害。")
                # 战斗扩展：记录造成伤害
                self.combat_extension_manager.record_damage(actual, is_player=True)
                if player_modifier > 1.1:
                    logs.append("境界压制，伤害提升！")
                elif player_modifier < 0.9:
                    logs.append("对方境界高于你，伤害被削弱！")

        elif action == "flee":
            # 逃跑，有概率成功
            if random.random() < 0.5:
                logs.append("你趁乱脱身，成功逃离战斗。")
                self._auto_save()
                return logs, "flee"
            else:
                logs.append("你试图逃跑，但妖兽追了上来！")

        # 每回合结束减少冷却
        self.player.update_skill_cooldowns()
        # 递减 buff/debuff 剩余回合数
        self._tick_buffs(logs)
        # 各流派每回合资源积累（受特殊地形加成影响）
        path = self.player.cultivation_path
        # 资源名 → 基础积累量 的映射
        resource_base = {
            "jian": ("sword_intent", 1),
            "dan": ("dan_fire", 5),
            "qi": ("qi_spirit", 3),
            "hun": ("hun_sense", 10),
            "zhen": ("zhen_rune", 1),
        }
        if path in resource_base:
            res_name, base_amount = resource_base[path]
            # 应用地形资源加成（如雷泽体修怒气+2、忘川河魂修神识翻倍）
            bonus_amount = self._apply_terrain_resource_bonus(res_name, base_amount)
            self.player.add_path_resource(bonus_amount)

        if not enemy.is_alive():
            # 敌人死亡，结算战利品
            logs.append(f"[cyan]{enemy.name} 倒下了！")
            self.player.qi += enemy.exp
            logs.append(f"[blue]你获得 {enemy.exp} 点修为。")

            # 邪修专属：击杀回血 + 积累邪气
            if self.player.cultivation_path == "xie":
                heal_amount = int(self.player.max_health * 0.3)
                self.player.health = min(
                    self.player.max_health, self.player.health + heal_amount
                )
                self.player.add_path_resource(10)
                logs.append(
                    f"[green]邪修之力吞噬生灵，你恢复 {heal_amount} 点生命，邪气上升！"
                )
            # 魂修专属：击杀吸收神魂，神识 +20
            elif self.player.cultivation_path == "hun":
                self.player.add_path_resource(20)
                logs.append(f"[purple]神魂消散，你吸收其魂力，神识 +20！")
            # 御兽修专属：击败野兽类敌人有概率获得兽魂
            elif self.player.cultivation_path == "shou":
                # 30% 概率收服兽魂（仅野兽类敌人）
                if random.random() < 0.3 and self.player.shou_soul < 5:
                    self.player.add_path_resource(1)
                    logs.append(f"[green]你收服了 {enemy.name} 的兽魂！")

            # 击杀影响心境：根据敌人阵营调整道心与心魔
            alignment = getattr(enemy, "alignment", "neutral")
            mental_delta, heart_delta = self.mental_state_manager.on_killing(alignment)
            if mental_delta != 0 or heart_delta != 0:
                logs.append(
                    f"[purple]击杀 {enemy.name}，道心变化 {mental_delta:+d}，"
                    f"心魔变化 {heart_delta:+d}。"
                )

            # 推进杀怪任务
            self._advance_kill_quests(enemy.id)
            # 推进宗门击杀任务
            self.sect_manager.update_task_progress("kill", enemy.id, 1)

            loot_ids = enemy.get_loot(
                player_realm_order=self._get_realm_order(),
                enemy_realm_order=self._get_enemy_realm_order(enemy),
            )
            for item_id in loot_ids:
                item = self.item_library.create(item_id)
                self.player.add_item(item)
                logs.append(f"[blue]掉落：{item.name}")
                # 获得掉落物品触发收集类钩子
                self._on_gain_item(item_id)

            # 战斗胜利：触发击杀/胜利相关事件钩子与统计
            self._on_kill_enemy(enemy)
            self.combat_extension_manager.end_battle(won=True)

            # 演武场排名挑战结算
            if getattr(self, "pending_arena_opponent", None):
                logs.extend(self._finish_arena_ranking_challenge(True))

            # 城池守城战推进波次
            if getattr(self, "pending_city_event", None):
                logs.extend(self._advance_city_defense_wave())

            self._auto_save()
            return logs, "win"

        # ===== 敌人行动：使用 AI 状态机决策 =====
        # 敌人眩晕：跳过本回合行动
        if self.enemy_stunned > 0:
            logs.append(f"[purple]{enemy.name} 陷入眩晕，无法行动！")
            self.enemy_stunned -= 1
            if self.enemy_stunned == 0:
                logs.append("[green]敌人从眩晕中恢复过来。")
            self.player.update_skill_cooldowns()
            self._tick_buffs(logs)
            self._tick_combat_states(logs)
            return logs, "continue"

        # 阵修布阵效果：困敌时敌人无法行动
        # - formation_just_activated=True 表示本回合刚布阵成功，敌人立即被困（当回合生效）
        # - 后续回合 formation_active 仍存在时，继续跳过敌人行动
        if self.formation_active and self.formation_active.get("type") == "trap":
            if getattr(self, "formation_just_activated", False):
                logs.append(f"[purple]阵法当场困敌！{enemy.name} 来不及反应。")
                self.formation_just_activated = False
            else:
                logs.append(f"[purple]阵法困敌！{enemy.name} 无法行动。")
            # 递减困敌回合
            self.formation_active["turns"] -= 1
            if self.formation_active["turns"] <= 0:
                self.formation_active = None
                logs.append(f"[purple]阵法效果消散。")
            # 跳过敌人行动，但仍递减玩家技能冷却等
            self.player.update_skill_cooldowns()
            self._tick_buffs(logs)
            return logs, "continue"

        # 魂修反噬：神识归零时玩家眩晕 1 回合（玩家本回合无法主动行动，但敌人仍会攻击）
        # 这是上一回合使用万魂归一导致的反噬效果
        if self.player_stunned > 0:
            logs.append(f"[red]【神识反噬】万魂归一的后遗症发作！你陷入眩晕，本回合无法行动。")
            self.player_stunned -= 1
            # 眩晕时敌人普通攻击（玩家无法防御，伤害 ×1.2）
            enemy_attack = enemy.attack
            actual_damage = max(1, int(enemy_attack * 1.2))
            self.player.health -= actual_damage
            logs.append(f"[red]{enemy.name} 趁你眩晕，对你造成 {actual_damage} 点伤害。")
            # 反噬结束提示
            if self.player_stunned == 0:
                logs.append(f"[green]神识逐渐恢复，眩晕解除。")
            self.player.update_skill_cooldowns()
            self._tick_buffs(logs)
            if not self.player.is_alive():
                if self._try_nascent_soul_revive(logs):
                    return logs, "continue"
                logs.append(f"[red]你被 {enemy.name} 击败了……")
                return logs, "lose"
            return logs, "continue"

        # 召唤物协同攻击
        self._process_enemy_summons(logs)
        if not self.player.is_alive():
            if self._try_nascent_soul_revive(logs):
                return logs, "continue"
            logs.append(f"[red]你被 {enemy.name} 的召唤物击败了……")
            return logs, "lose"

        # 高阶敌人专属技能（优先于普通 AI）
        if self._try_enemy_special_skill(enemy, logs):
            self.player.update_skill_cooldowns()
            self._tick_buffs(logs)
            self._tick_combat_states(logs)
            if not self.player.is_alive():
                if self._try_nascent_soul_revive(logs):
                    return logs, "continue"
                logs.append(f"[red]你被 {enemy.name} 击败了……")
                return logs, "lose"
            return logs, "continue"

        # 高阶敌人召唤机制（在普通行动前尝试）
        self._try_enemy_summon(enemy, logs)

        decision = enemy.decide_action(self.player)
        action_type = decision["action"]

        if action_type == "flee":
            # 敌人尝试逃跑，玩家获得部分修为作为安慰奖励
            reward_qi = max(1, enemy.exp // 3)
            self.player.qi += reward_qi
            # [yellow] 标记逃跑行为
            logs.append(f"[yellow]{enemy.name} 见势不妙，转身逃走了！")
            logs.append(f"[blue]虽未能斩杀，你仍从战斗中有所领悟，获得 {reward_qi} 点修为。")
            self._auto_save()
            return logs, "enemy_flee"

        if action_type == "heal":
            # 敌人使用治疗技能恢复生命
            heal_skill = decision["skill"]
            heal_amount = heal_skill.get("heal_amount", 20)
            enemy.hp = min(enemy.hp + heal_amount, enemy.max_hp)
            # [green] 标记治疗行为
            logs.append(
                f"[green]{enemy.name} 使用【{heal_skill['name']}】！{heal_skill['description']} "
                f"恢复 {heal_amount} 点生命。"
            )

        elif action_type == "buff":
            # 敌人使用 buff/debuff 技能
            buff_skill = decision["skill"]
            buff_type = buff_skill.get("buff_type", "defense_up")
            buff_amount = buff_skill.get("buff_amount", 5)
            buff_turns = buff_skill.get("buff_turns", 3)

            if buff_type == "defense_up":
                # 提升自身防御（加入列表，带回合数）
                self.enemy_defense_buffs.append({"amount": buff_amount, "turns": buff_turns})
                logs.append(
                    f"[orange]{enemy.name} 使用【{buff_skill['name']}】！{buff_skill['description']} "
                    f"防御力提升 {buff_amount} 点，持续 {buff_turns} 回合。"
                )
            elif buff_type == "player_attack_down":
                # 削弱玩家攻击力（加入列表，带回合数）
                self.player_attack_debuffs.append({"amount": buff_amount, "turns": buff_turns})
                logs.append(
                    f"[orange]{enemy.name} 使用【{buff_skill['name']}】！{buff_skill['description']} "
                    f"你的攻击力被削弱 {buff_amount} 点，持续 {buff_turns} 回合。"
                )

        elif action_type == "skill":
            # 敌人使用攻击/辅助技能
            enemy_skill = decision["skill"]
            # 符修镇妖符效果：敌人技能被封印
            if self.enemy_skill_sealed > 0:
                logs.append(f"[yellow]镇妖符压制！{enemy.name} 无法施展技能，转为普通攻击。")
                enemy_attack = enemy.attack
            else:
                # [red] 标记攻击技能
                logs.append(
                    f"[red]{enemy.name} 使用【{enemy_skill['name']}】！{enemy_skill['description']}"
                )
                enemy_attack = int(enemy.attack * enemy_skill.get("damage_multiplier", 1.0))
                # 应用敌人攻击削弱
                enemy_attack = int(enemy_attack * self._get_enemy_attack_multiplier())

                # 毒液类 DOT 效果
                dot_damage = enemy_skill.get("dot_damage")
                dot_turns = enemy_skill.get("dot_turns")
                if dot_damage and dot_turns:
                    self.combat_dot_effects.append({
                        "source": enemy.name,
                        "damage": dot_damage,
                        "turns": dot_turns,
                    })
                    logs.append(f"[red]你中了 {enemy.name} 的毒，将持续 {dot_turns} 回合！")

            # 狂暴叠加：血量低于 30% 时额外提升 50% 伤害
            if self._enemy_rage_attack(enemy):
                enemy_attack = int(enemy_attack * 1.5)
                logs.append(f"[orange]{enemy.name} 陷入狂暴，攻击力暴涨！")

            # 阵修困仙阵削弱：敌人攻击下降 40%
            if self.formation_active and self.formation_active.get("type") == "weaken":
                weaken_ratio = self.formation_active.get("ratio", 0.4)
                enemy_attack = int(enemy_attack * (1.0 - weaken_ratio))

            # 五行相克判定：敌人属性 vs 玩家主灵根
            enemy_attack = self._apply_enemy_element_multiplier(enemy_attack, enemy, logs)
            # 阵修困仙阵削弱：敌人防御下降 40%（影响玩家受伤计算）
            enemy_def_for_calc = enemy.defense
            if self.formation_active and self.formation_active.get("type") == "weaken":
                weaken_ratio = self.formation_active.get("ratio", 0.4)
                enemy_def_for_calc = int(enemy_def_for_calc * (1.0 - weaken_ratio))
            # 玩家防御受道侣防御加成影响
            effective_defense = int(
                self.player.defense * (1 + getattr(self, "companion_def_bonus", 0.0))
                * self._get_player_defense_multiplier()
            )
            actual_damage = max(1, int((enemy_attack - effective_defense) * enemy_modifier))
            # 宗门护山大阵：削弱入侵之敌伤害
            formation_reduce = self.sect_manager.get_formation_enemy_damage_reduction()
            if formation_reduce > 0:
                actual_damage = int(actual_damage * (1.0 - formation_reduce))
            # 流派防御机制：法修真气护盾、体修怒气积累等
            actual_damage = self._apply_player_defense_mechanics(actual_damage, enemy, logs)
            # 应用护盾与反弹
            actual_damage = self._apply_player_shield_and_reflect(actual_damage, enemy, logs)
            self.player.health -= actual_damage
            logs.append(f"[red]{enemy.name} 反击，对你造成 {actual_damage} 点伤害。")
            # 战斗扩展：记录受到伤害
            self.combat_extension_manager.record_damage(actual_damage, is_player=False)

        else:
            # 普通攻击
            enemy_attack = enemy.attack
            # 应用敌人攻击削弱
            enemy_attack = int(enemy_attack * self._get_enemy_attack_multiplier())
            if self._enemy_rage_attack(enemy):
                enemy_attack = int(enemy_attack * 1.5)
                logs.append(f"[orange]{enemy.name} 陷入狂暴，攻击力暴涨！")

            # 阵修困仙阵削弱：敌人攻击下降 40%
            if self.formation_active and self.formation_active.get("type") == "weaken":
                weaken_ratio = self.formation_active.get("ratio", 0.4)
                enemy_attack = int(enemy_attack * (1.0 - weaken_ratio))

            # 五行相克判定：敌人属性 vs 玩家主灵根
            enemy_attack = self._apply_enemy_element_multiplier(enemy_attack, enemy, logs)
            # 玩家防御受道侣防御加成影响
            effective_defense = int(
                self.player.defense * (1 + getattr(self, "companion_def_bonus", 0.0))
                * self._get_player_defense_multiplier()
            )
            actual_damage = max(1, int((enemy_attack - effective_defense) * enemy_modifier))
            # 宗门护山大阵：削弱入侵之敌伤害
            formation_reduce = self.sect_manager.get_formation_enemy_damage_reduction()
            if formation_reduce > 0:
                actual_damage = int(actual_damage * (1.0 - formation_reduce))
            # 流派防御机制：法修真气护盾、体修怒气积累等
            actual_damage = self._apply_player_defense_mechanics(actual_damage, enemy, logs)
            # 应用护盾与反弹
            actual_damage = self._apply_player_shield_and_reflect(actual_damage, enemy, logs)
            self.player.health -= actual_damage
            logs.append(f"[red]{enemy.name} 反击，对你造成 {actual_damage} 点伤害。")
            # 战斗扩展：记录受到伤害
            self.combat_extension_manager.record_damage(actual_damage, is_player=False)

        # 递减阵法削弱回合数
        if self.formation_active and self.formation_active.get("type") == "weaken":
            self.formation_active["turns"] -= 1
            if self.formation_active["turns"] <= 0:
                self.formation_active = None
                logs.append(f"[purple]困仙阵效果消散。")
        # 递减镇妖符封印回合
        if self.enemy_skill_sealed > 0:
            self.enemy_skill_sealed -= 1
            if self.enemy_skill_sealed == 0:
                logs.append(f"[yellow]镇妖符封印解除。")

        if not self.player.is_alive():
            if self._try_nascent_soul_revive(logs):
                return logs, "continue"
            # 战斗失败统计
            self.combat_extension_manager.end_battle(won=False)
            self.chronicle_manager.record(
                f"败于 {enemy.name} 之手", category="combat"
            )
            # 演武场排名挑战结算
            if getattr(self, "pending_arena_opponent", None):
                logs.extend(self._finish_arena_ranking_challenge(False))

            # 城池守城战失败：清空 pending 状态
            if getattr(self, "pending_city_event", None):
                logs.append("[red]守城失败，妖兽突破防线……")
                self.pending_city_event = None

            return logs, "lose"

        return logs, "continue"

    # ==================== 物品与装备系统 ====================

