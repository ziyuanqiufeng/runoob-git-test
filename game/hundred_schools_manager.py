# -*- coding: utf-8 -*-
"""
维度③ 百家争鸣 / 非传统修仙路线（F-08 体验深化）。

修仙非止正道一途。百家争鸣，另辟蹊径亦可证道：
- 立派传道：金丹后开宗立派，弟子渐众、气运（qi_yun）累积，每月以灵石反哺道途，
  并可耗气运行「道韵灌顶」增益道心；
- 自创功法：推演独门功法（择流派与属性），明心见性，月度道心微涨；
- 生活流派御劫：择丹/器/阵/符一途精进，可于大境界突破时化解心魔之劫。

本系统纯加法式接入，复用 player 既有的 mental_state（道心 0-100）作为道心增益的
唯一真相源；立派/自创/流派状态持久化于 player 新字段：
- player.founded_sect / self_created_techniques / life_path / life_path_proficiency
未立派、未自创、未择流派时，tick 为 no-op，不影响任何旧系统行为。
"""

import json
import os
import random


class HundredSchoolsConfig:
    """加载维度③配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "hundred_schools.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_sect(self):
        return self.data.get("sect", {})

    def get_technique(self):
        return self.data.get("self_created_technique", {})

    def get_life_path(self):
        return self.data.get("life_path", {})


class HundredSchoolsManager:
    """百家争鸣 / 非传统修仙路线管理器。"""

    def __init__(self, player, config_dir="config", notify_callback=None):
        self.player = player
        self.config = HundredSchoolsConfig(config_dir)
        self.notify = notify_callback or (lambda x: None)

    # ---------------- 内部工具 ----------------
    def _realm_order(self):
        return getattr(self.player, "REALM_ORDER", {}).get(self.player.realm_id, 0)

    def _adjust_dao_heart(self, delta):
        """道心（mental_state）增减并钳制 0-100。"""
        ms = getattr(self.player, "mental_state", 50)
        ms = max(0, min(100, ms + delta))
        self.player.mental_state = ms

    # ==================== 立派传道 ====================
    def can_found_sect(self):
        if getattr(self.player, "founded_sect", None):
            return False, "已立派，不可重复开宗。"
        if self._realm_order() < self.config.get_sect().get("min_realm_order", 14):
            return False, "需达金丹期方可开宗立派。"
        if self.player.count_item("spirit_stone") < self.config.get_sect().get("found_cost_spirit_stone", 50):
            return False, "灵石不足，无法置办开派基业。"
        return True, "可开宗立派。"

    def found_sect(self, name):
        """开宗立派，开启气运反哺。返回 (ok, message)。"""
        ok, msg = self.can_found_sect()
        if not ok:
            return False, msg
        cost = self.config.get_sect().get("found_cost_spirit_stone", 50)
        self.player.consume_items("spirit_stone", cost)
        self.player.founded_sect = {
            "name": name or "无名小派",
            "founded_month": getattr(self.player, "age_months", 0),
            "disciples": 0,
            "qi_yun": 0.0,
            "pending_stones": 0.0,
        }
        return True, f"开宗立派成功：{name or '无名小派'}！气运反哺自此开启。"

    def get_sect_status(self):
        return getattr(self.player, "founded_sect", None)

    def spend_qi_yun_for_enlightenment(self):
        """耗气运行『道韵灌顶』，增益道心。返回 (ok, message)。"""
        sect = getattr(self.player, "founded_sect", None)
        if not sect:
            return False, "尚未立派，无气运可耗。"
        cfg = self.config.get_sect()
        cost = cfg.get("enlightenment_cost_qi_yun", 10)
        if sect["qi_yun"] < cost:
            return False, "气运不足，无法以道韵灌顶。"
        sect["qi_yun"] = round(sect["qi_yun"] - cost, 2)
        gain = cfg.get("enlightenment_dao_heart", 5)
        self._adjust_dao_heart(gain)
        return True, f"道韵灌顶！道心 +{gain}（耗气运 {cost}）。"

    # ==================== 自创功法 ====================
    def can_create_technique(self):
        if self._realm_order() < self.config.get_technique().get("min_realm_order", 14):
            return False, "需达金丹期方可自创功法。"
        techs = getattr(self.player, "self_created_techniques", [])
        if len(techs) >= self.config.get_technique().get("max_techniques", 5):
            return False, "自创功法已达上限。"
        if self.player.count_item("spirit_stone") < self.config.get_technique().get("cost_spirit_stone", 20):
            return False, "灵石不足，无法推演功法。"
        return True, "可自创功法。"

    def _make_technique_dict(self, name, school, attribute, quality=0):
        """构造一条自创功法 dict（含稳定 skill_id）。quality 为功法推演品质（M19）。"""
        techs = getattr(self.player, "self_created_techniques", [])
        return {
            "name": name or "无名功法",
            "school": school,
            "attribute": attribute,
            "level": 1,
            "quality": quality,
            # 稳定技能 id：读档后引擎据此从本 dict 重建 Skill 对象
            "skill_id": "self_tech_%d" % (len(techs) + 1),
        }

    def create_technique(self, name, school, attribute):
        """推演一门独门功法。返回 (ok, message)。

        除明心见性（月度道心微涨）外，自创功法会被引擎注册为真实可施展的
        Skill（见 engine.create_technique / _register_self_created_skills）。
        """
        ok, msg = self.can_create_technique()
        if not ok:
            return False, msg
        tech_cfg = self.config.get_technique()
        if attribute not in tech_cfg.get("allowed_attributes", []):
            return False, f"属性 {attribute} 不在可选范围。"
        if school not in tech_cfg.get("schools", []):
            return False, f"流派 {school} 不被认可。"
        cost = tech_cfg.get("cost_spirit_stone", 20)
        self.player.consume_items("spirit_stone", cost)
        tech = self._make_technique_dict(name, school, attribute, quality=0)
        techs = getattr(self.player, "self_created_techniques", [])
        techs.append(tech)
        self.player.self_created_techniques = techs
        return True, f"自创功法《{name or '无名功法'}》（{school}·{attribute}）推演而成！"

    def _tier_for_quality(self, quality):
        """依累计品质返回 (品质阶名, 乘算系数)。未达任何阈值为『凡·×1.0』。"""
        cfg = self.config.get_technique().get("deduction", {}).get("quality_tiers", [])
        tier, mult = "凡", 1.0
        for t in cfg:
            if quality >= t.get("min_quality", 0):
                tier, mult = t.get("tier", "凡"), t.get("mult", 1.0)
        return tier, mult

    def build_skill_kwargs(self, tech):
        """根据已存的自创功法 dict 构造一个 Skill 构造参数字典，供引擎注册使用。

        返回 None 表示该功法无法映射为技能（配置缺失流派模板）。
        维度③·M19：若功法带 quality，则按品质阶乘算各战斗参数并标注品阶。
        """
        if not tech:
            return None
        cfg = self.config.get_technique()
        tmpl = cfg.get("skill_templates", {}).get(tech.get("school"))
        if not tmpl:
            return None
        attr = tech.get("attribute")
        element = cfg.get("attribute_element", {}).get(attr, "none")
        name = tech.get("name", "无名功法")
        school = tech.get("school", "")
        kw = {
            "skill_id": tech.get("skill_id"),
            "name": name,
            "description": f"自创功法《{name}》（{school}·{attr}）",
            "base_damage": tmpl.get("base_damage", 0),
            "realm_multiplier": tmpl.get("realm_multiplier", 0),
            "weapon_multiplier": tmpl.get("weapon_multiplier", 0),
            "qi_cost": tmpl.get("qi_cost", 0),
            "cooldown": tmpl.get("cooldown", 0),
            "heal": tmpl.get("heal", 0),
            "heal_realm_multiplier": tmpl.get("heal_realm_multiplier", 0),
            "element": element,
            "path_exclusive": tmpl.get("path_exclusive"),
            "effects": tmpl.get("effects", []),
            "realm_id": None,
            "mastery_effects": tmpl.get("mastery_effects", []),
        }
        tier, mult = self._tier_for_quality(tech.get("quality", 0))
        if mult != 1.0:
            kw["base_damage"] = int(round(kw["base_damage"] * mult))
            kw["realm_multiplier"] = round(kw["realm_multiplier"] * mult, 2)
            kw["weapon_multiplier"] = round(kw["weapon_multiplier"] * mult, 2)
            kw["heal"] = int(round(kw["heal"] * mult))
            kw["heal_realm_multiplier"] = round(kw["heal_realm_multiplier"] * mult, 2)
            kw["description"] = f"自创功法《{name}》（{school}·{attr}·{tier}品）"
        return kw

    # ==================== 自创功法·功法推演（M19） ====================
    def start_deduction(self, name, school, attribute):
        """开启一门功法的『推演』。返回 (ok, message)。

        推演以「逐节点参悟」代替一次性注册：每参悟一节点累积『品质』，品质达阶位
        阈值即决定功法品质（凡/灵/仙/道），大成时乘算最终 Skill 强度。
        前置条件与 create_technique 相同（境界/未达上限/灵石），但灵石按节点另计。
        """
        if getattr(self.player, "pending_deduction", None):
            return False, "已有推演进行中，请先大成或放弃。"
        ok, msg = self.can_create_technique()
        if not ok:
            return False, msg
        tech_cfg = self.config.get_technique()
        if attribute not in tech_cfg.get("allowed_attributes", []):
            return False, f"属性 {attribute} 不在可选范围。"
        if school not in tech_cfg.get("schools", []):
            return False, f"流派 {school} 不被认可。"
        ded = tech_cfg.get("deduction", {})
        node_types = list(ded.get("node_types", {}).keys())
        if not node_types:
            return False, "推演配置缺失节点类型。"
        max_nodes = ded.get("max_nodes", 4)
        # 随机生成推演节点序列（可重复，体现不同侧重）
        nodes = [random.choice(node_types) for _ in range(max_nodes)]
        self.player.pending_deduction = {
            "name": name or "无名功法",
            "school": school,
            "attribute": attribute,
            "nodes": nodes,
            "idx": 0,
            "quality": 0,
            "resolved": [],
        }
        return True, f"开启功法推演《{name or '无名功法'}》（{school}·{attribute}）：共 {max_nodes} 节点待参悟。"

    def resolve_deduction_node(self, force_success=None):
        """参悟推演的下一节点。返回 (ok, message, detail)。

        force_success 为 None 时按节点成功率随机；否则强制成败（便于测试/确定化）。
        成功节点全额累积品质，滞涩节点半额累积；每节点消耗悟性 + 灵石。
        """
        pd = getattr(self.player, "pending_deduction", None)
        if not pd:
            return False, "当前没有进行中的功法推演。", None
        if pd["idx"] >= len(pd["nodes"]):
            return False, "推演节点已尽，可大成。", None
        ded = self.config.get_technique().get("deduction", {})
        cost_w = ded.get("cost_wisdom_per_node", 3)
        cost_s = ded.get("cost_spirit_stone_per_node", 5)
        if getattr(self.player, "wisdom", 0) < cost_w:
            return False, "悟性不足，无法继续参悟。", None
        if self.player.count_item("spirit_stone") < cost_s:
            return False, "灵石不足，无法继续参悟。", None
        self.player.wisdom -= cost_w
        self.player.consume_items("spirit_stone", cost_s)
        node_name = pd["nodes"][pd["idx"]]
        node = ded.get("node_types", {}).get(node_name, {})
        success = force_success if force_success is not None else (random.random() < node.get("success", 0.8))
        if success:
            gain = node.get("quality", 5)
            outcome = "妙悟"
        else:
            gain = node.get("quality", 5) // 2
            outcome = "滞涩"
        pd["quality"] += gain
        pd["idx"] += 1
        pd["resolved"].append({"node": node_name, "success": bool(success), "gain": gain, "outcome": outcome})
        msg = (f"参悟【{node_name}】：{outcome}！品质 +{gain}"
               f"（累计 {pd['quality']}，节点 {pd['idx']}/{len(pd['nodes'])}）")
        return True, msg, {"node": node_name, "outcome": outcome, "gain": gain,
                           "quality": pd["quality"], "idx": pd["idx"]}

    def commit_deduction(self):
        """大成：将推演中的功法落定为自创功法（含品质阶）。返回 (ok, message, tech)。"""
        pd = getattr(self.player, "pending_deduction", None)
        if not pd:
            return False, "没有进行中的功法推演。", None
        if pd["idx"] < len(pd["nodes"]):
            return False, "推演未竟，不可大成。", None
        tech = self._make_technique_dict(pd["name"], pd["school"], pd["attribute"], quality=pd["quality"])
        techs = getattr(self.player, "self_created_techniques", [])
        techs.append(tech)
        self.player.self_created_techniques = techs
        tier, _ = self._tier_for_quality(pd["quality"])
        self.player.pending_deduction = None
        return True, f"功法《{pd['name']}》推演大成！品质【{tier}】（累计品质 {pd['quality']}）", tech

    def get_deduction_status(self):
        """返回进行中推演的快照（含实时品质阶预览），无则返回 None。"""
        pd = getattr(self.player, "pending_deduction", None)
        if not pd:
            return None
        tier, mult = self._tier_for_quality(pd["quality"])
        return {
            "name": pd["name"],
            "school": pd["school"],
            "attribute": pd["attribute"],
            "nodes": list(pd["nodes"]),
            "idx": pd["idx"],
            "quality": pd["quality"],
            "tier": tier,
            "mult": mult,
            "resolved": list(pd["resolved"]),
        }

    # ==================== 生活流派御劫 ====================
    def choose_life_path(self, path):
        """择一生活流派精进（丹/器/阵/符）。返回 (ok, message)。"""
        types = self.config.get_life_path().get("types", {})
        if path not in types:
            return False, f"生活流派 {path} 不存在。"
        self.player.life_path = path
        self.player.life_path_proficiency = 0
        # 维度③·M17：择流派不再默认开启战斗自动部署——消除「选符箓/阵法即默认
        # 白嫖战斗增益」的流派不对称（丹道/器修产出为养成向，需手动服用/装备）。
        # 玩家可在百家争鸣面板主动勾选「战斗自动部署法宝」，或战斗中手动部署。
        self.player.lifepath_auto_deploy = False
        return True, f"择生活流派：{types[path]}。勤修可御心魔之劫。"

    def get_life_path_proficiency(self):
        return getattr(self.player, "life_path_proficiency", 0)

    def should_mitigate_heart_demon_tribulation(self):
        """生活流派精熟时，按概率化解心魔之劫。返回 bool。"""
        lp = self.get_life_path_proficiency()
        cfg = self.config.get_life_path()
        if lp < cfg.get("min_mitigation_level", 5):
            return False
        chance = min(
            cfg.get("max_mitigation", 0.6),
            lp * cfg.get("heart_demon_mitigation_per_level", 0.01),
        )
        return random.random() < chance

    def get_battle_deploy_cfg(self, item_id):
        """返回某物品的『战斗部署型』增益配置（维度③·M15）。

        仅 life_path.produce 中带 battle_buff 的物品可被部署为战斗临时增益。
        返回 dict（含 name/desc 与若干战斗 buff 槽）或 None。
        """
        for prod in self.config.get_life_path().get("produce", {}).values():
            if prod.get("item_id") == item_id and "battle_buff" in prod:
                return prod["battle_buff"]
        return None

    # ==================== 月度结算 ====================
    def tick_monthly(self):
        """维度③ 月度结算。返回本月的灵石反哺与产出物品（由引擎发放）。"""
        rewards = {"spirit_stone": 0, "produced_items": []}

        # 1. 立派传道：弟子增长 → 气运累积 → 灵石反哺
        sect = getattr(self.player, "founded_sect", None)
        if sect:
            cfg = self.config.get_sect()
            new_disciples = int(
                cfg.get("disciples_base", 1)
                + sect["qi_yun"] * cfg.get("disciples_per_qi_yun", 0.2)
            )
            sect["disciples"] = min(
                cfg.get("max_disciples", 200),
                sect["disciples"] + new_disciples,
            )
            gained_qi = new_disciples * cfg.get("qi_yun_per_new_disciple", 0.5)
            sect["qi_yun"] = min(
                cfg.get("max_qi_yun", 100),
                round(sect["qi_yun"] + gained_qi, 2),
            )
            # 灵石反哺：用累积小数余额累加，避免低气运期被 int 截断丢光
            base = sect["qi_yun"] * cfg.get("feedback_spirit_stone_per_qi_yun", 0.3)
            total = base + sect.get("pending_stones", 0.0)
            whole = int(total)
            sect["pending_stones"] = round(total - whole, 4)
            rewards["spirit_stone"] = whole

        # 2. 自创功法：明心见性，月度道心微涨
        techs = getattr(self.player, "self_created_techniques", [])
        if techs:
            bonus = self.config.get_technique().get("monthly_dao_heart_per_technique", 0.3) * len(techs)
            self._adjust_dao_heart(bonus)

        # 3. 生活流派：精进 proficiency，并按周期产出真实物品
        life_path = getattr(self.player, "life_path", None)
        if life_path:
            lp_cfg = self.config.get_life_path()
            prof = getattr(self.player, "life_path_proficiency", 0) + lp_cfg.get("proficiency_per_month", 1)
            self.player.life_path_proficiency = min(lp_cfg.get("max_proficiency", 50), prof)
            prod = lp_cfg.get("produce", {}).get(life_path)
            if prod and prof >= prod.get("min_proficiency", 0):
                every = prod.get("every_months", 0)
                age = getattr(self.player, "age_months", 0)
                if every and age % every == 0:
                    rewards["produced_items"].append(prod.get("item_id"))

        return rewards

    # ==================== 状态读取 ====================
    def get_status(self):
        return {
            "sect": getattr(self.player, "founded_sect", None),
            "techniques": getattr(self.player, "self_created_techniques", []),
            "life_path": getattr(self.player, "life_path", None),
            "life_path_proficiency": getattr(self.player, "life_path_proficiency", 0),
            "mental_state": getattr(self.player, "mental_state", 50),
        }
