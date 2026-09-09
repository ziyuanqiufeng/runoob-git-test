# -*- coding: utf-8 -*-
"""心境 / 道心系统。

管理玩家的道心值、心魔值，以及因行为（如杀戮、突破、悟道）产生的心境变化。
"""

import json
import os
import random


class MentalStateConfig:
    """心境系统配置加载器。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "mental_state.json")
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def get_level(self, mental_state):
        """根据道心值返回匹配的心境等级配置。"""
        levels = self.data.get("mental_state_levels", [])
        matched = levels[-1] if levels else {}
        for level in levels:
            if mental_state >= level.get("min", 0):
                matched = level
                break
        return matched

    def get_killing_effect(self, alignment):
        """获取击杀指定阵营目标时的心境变化。"""
        return self.data.get("killing_effects", {}).get(alignment, {})

    def get_heart_demon_events(self):
        """获取所有心魔事件配置。"""
        return self.data.get("heart_demon_events", [])

    def get_traits(self):
        """获取可领悟的心境特质配置。"""
        return self.data.get("traits", [])

    def get_monthly_changes(self):
        """获取每月自然恢复/衰减配置。"""
        return self.data.get("monthly_changes", {})

    def get_precept_violations(self):
        """获取违戒（正道修魔功）配置。"""
        return self.data.get("precept_violations", {})

    def get_major_setbacks(self):
        """获取重大挫折（家族覆灭/道侣陨落）配置。"""
        return self.data.get("major_setbacks", {})

    def get_travel_dao_heart(self):
        """获取游历名山大川增长道心配置。"""
        return self.data.get("travel_dao_heart", {})

    def get_heart_demon_tribulation(self):
        """获取突破心魔劫幻境配置（阈值 + 幻境场景）。"""
        return self.data.get("heart_demon_tribulation", {})

    def get_unity_enlightenment(self):
        """获取天人合一顿悟配置。"""
        return self.data.get("unity_enlightenment", {})


class MentalStateManager:
    """心境 / 道心系统管理器。"""

    MENTAL_STATE_MIN = 0
    MENTAL_STATE_MAX = 100
    HEART_DEMON_MIN = 0
    HEART_DEMON_MAX = 100

    def __init__(self, player, config=None):
        self.player = player
        self.config = config or MentalStateConfig()

    def _clamp(self, value, min_val, max_val):
        """将数值限制在 [min_val, max_val] 范围内。"""
        return max(min_val, min(max_val, value))

    def adjust_mental_state(self, delta):
        """调整道心值并返回实际变化量。"""
        old = self.player.mental_state
        self.player.mental_state = self._clamp(
            old + delta, self.MENTAL_STATE_MIN, self.MENTAL_STATE_MAX
        )
        return self.player.mental_state - old

    def adjust_heart_demon(self, delta):
        """调整心魔值并返回实际变化量。"""
        old = self.player.heart_demon
        # 特质可能提供心魔抗性
        resistance = self.get_trait_effect("heart_demon_resistance")
        if delta > 0:
            delta = int(delta * (1 - resistance))
        self.player.heart_demon = self._clamp(
            old + delta, self.HEART_DEMON_MIN, self.HEART_DEMON_MAX
        )
        return self.player.heart_demon - old

    def get_level(self):
        """获取当前心境等级配置。"""
        return self.config.get_level(self.player.mental_state)

    def get_passive(self):
        """返回当前道境等级的被动配置（无则空字典）。

        道境被动由 config/mental_state.json 的 mental_state_levels[].passive
        定义，仅最高两阶（道心通明 / 心境平和）携带。缺失或为空时返回 {}，
        保证旧配置与低道心档位行为不变。
        """
        return self.get_level().get("passive", {}) or {}

    def get_breakthrough_bonus(self):
        """获取当前心境对突破成功率的加成。"""
        return self.get_level().get("breakthrough_bonus", 0.0)

    def get_cultivation_speed_bonus(self):
        """获取当前心境对修炼速度的加成。"""
        return self.get_level().get("cultivation_speed_bonus", 0.0)

    def get_trait_effect(self, effect_key):
        """获取已领悟特质对指定效果的累加值。"""
        total = 0.0
        traits = self.config.get_traits()
        trait_map = {t["id"]: t for t in traits}
        for trait_id in self.player.mental_state_traits:
            trait = trait_map.get(trait_id, {})
            total += trait.get("effect", {}).get(effect_key, 0.0)
        return total

    def on_killing(self, target_alignment):
        """击杀目标后调整心境。

        target_alignment 可取 "righteous"（正道）、"evil"（魔道）、"neutral"（中立）。
        返回 (mental_delta, heart_demon_delta)。
        """
        effect = self.config.get_killing_effect(target_alignment)
        mental_delta = effect.get("mental_state_delta", 0)
        heart_delta = effect.get("heart_demon_delta", 0)
        self.adjust_mental_state(mental_delta)
        self.adjust_heart_demon(heart_delta)
        return mental_delta, heart_delta

    def on_breakthrough(self, success):
        """突破成功后提升道心，失败则降低道心并增加心魔。

        护道之境（道心≥60）被动：突破失败不再折损道心，仍正常积攒心魔。
        """
        if success:
            self.adjust_mental_state(5)
            self.adjust_heart_demon(-5)
        else:
            if not self.get_passive().get("breakthrough_failure_mental_protect"):
                self.adjust_mental_state(-5)
            self.adjust_heart_demon(10)

    def meditate(self, months=1):
        """悟道/冥想，消耗时间提升道心、降低心魔。"""
        mental_gain = 2 * months
        heart_decay = 3 * months
        self.adjust_mental_state(mental_gain)
        self.adjust_heart_demon(-heart_decay)
        return mental_gain, heart_decay

    def check_heart_demon_events(self, rng=None):
        """检查并触发心魔事件，返回触发的事件列表。

        无漏之境（道心≥80）被动：心魔事件免疫，直接返回空列表。
        """
        if self.get_passive().get("heart_demon_event_immunity"):
            return []
        rng = rng or random
        events = []
        for event_cfg in self.config.get_heart_demon_events():
            if self.player.heart_demon >= event_cfg.get("trigger_min", 100):
                chance = event_cfg.get("trigger_chance", 0.0)
                if rng.random() < chance:
                    effect = event_cfg.get("effect", {})
                    health_pct = effect.get("health_loss_percent", 0.0)
                    mental_loss = effect.get("mental_state_loss", 0)
                    if health_pct:
                        self.player.health = max(
                            1,
                            int(self.player.health - self.player.max_health * health_pct),
                        )
                    self.adjust_mental_state(-mental_loss)
                    events.append(event_cfg)
        return events

    def try_learn_trait(self, trait_id, kill_count=0, save_lives=0):
        """尝试领悟心境特质，满足条件时加入特质列表。"""
        traits = self.config.get_traits()
        trait_map = {t["id"]: t for t in traits}
        trait = trait_map.get(trait_id)
        if not trait:
            return False, "特质不存在。"
        if trait_id in self.player.mental_state_traits:
            return False, "已领悟该特质。"

        req = trait.get("requirement", {})
        mental_min = req.get("mental_state_min", self.MENTAL_STATE_MIN)
        mental_max = req.get("mental_state_max", self.MENTAL_STATE_MAX)
        if not (mental_min <= self.player.mental_state <= mental_max):
            return False, "当前道心值不满足领悟条件。"
        if kill_count < req.get("kills", 0):
            return False, "杀戮数量不足。"
        if save_lives < req.get("save_lives", 0):
            return False, "救人数量不足。"

        self.player.mental_state_traits.append(trait_id)
        return True, f"领悟心境特质【{trait['name']}】"

    # ==================== 维度①：心魔与道心 体验深化 =================

    def on_precept_violation(self, skill_id):
        """正道（非魔道路线）修习魔功时滋生心魔。

        返回 (triggered, heart_demon_delta)。
        """
        cfg = self.config.get_precept_violations()
        demonic_paths = set(cfg.get("demonic_paths", []))
        demonic_skills = set(cfg.get("demonic_skill_ids", []))
        if skill_id in demonic_skills and getattr(self.player, "cultivation_path", None) not in demonic_paths:
            hd = cfg.get("heart_demon_delta", 0)
            md = cfg.get("mental_state_delta", 0)
            self.adjust_heart_demon(hd)
            self.adjust_mental_state(md)
            return True, hd
        return False, 0

    def on_major_setback(self, setback_id):
        """重大挫折（家族覆灭 / 道侣陨落）积攒心魔。

        返回 (triggered, heart_demon_delta)。
        """
        cfg = self.config.get_major_setbacks().get(setback_id)
        if not cfg:
            return False, 0
        hd = cfg.get("heart_demon_delta", 0)
        md = cfg.get("mental_state_delta", 0)
        self.adjust_heart_demon(hd)
        self.adjust_mental_state(md)
        return True, hd

    def on_travel(self, location_id=None, famous=False):
        """游历名山大川增长道心。famous 或 location_id 在名山列表中时增益更高。

        护道之境（道心≥60）被动：道心增长额外乘算 dao_heart_gain_mult。
        """
        cfg = self.config.get_travel_dao_heart()
        famous_ids = set(cfg.get("famous_location_ids", []))
        if famous or (location_id in famous_ids):
            gain = cfg.get("famous_gain", 5)
        else:
            gain = cfg.get("normal_gain", 1)
        mult = self.get_passive().get("dao_heart_gain_mult", 1.0)
        return self.adjust_mental_state(int(gain * mult))

    def should_trigger_heart_demon_tribulation(self):
        """大境界突破且心魔值达到阈值时，应强制触发心魔劫幻境。"""
        cfg = self.config.get_heart_demon_tribulation()
        threshold = cfg.get("threshold", 60)
        return self.player.heart_demon >= threshold

    def get_heart_demon_tribulation_scenario(self, rng=None):
        """随机取一个心魔劫幻境场景（供 UI 展示抉择）。"""
        rng = rng or random
        scenarios = self.config.get_heart_demon_tribulation().get("scenarios", [])
        if not scenarios:
            return None
        return rng.choice(scenarios)

    def apply_tribulation_choice(self, scenario_id, choice_id):
        """应用心魔劫幻境中的抉择：调整心魔/道心，永久改变性格标签与后续概率。"""
        cfg = self.config.get_heart_demon_tribulation()
        scenario = next(
            (s for s in cfg.get("scenarios", []) if s["id"] == scenario_id), None
        )
        if not scenario:
            return False, "幻境不存在。"
        choice = next(
            (c for c in scenario.get("choices", []) if c["id"] == choice_id), None
        )
        if not choice:
            return False, "抉择不存在。"

        effects = choice.get("effects", {})
        self.adjust_heart_demon(effects.get("heart_demon_delta", 0))
        self.adjust_mental_state(effects.get("mental_state_delta", 0))

        tag = effects.get("personality_tag")
        if tag:
            tags = getattr(self.player, "personality_tags", None)
            if tags is None:
                tags = []
                self.player.personality_tags = tags
            if tag not in tags:
                tags.append(tag)

        mod = effects.get("subsequent_modifier")
        if isinstance(mod, dict) and "key" in mod:
            te = getattr(self.player, "tribulation_effects", None)
            if te is None:
                te = {}
                self.player.tribulation_effects = te
            te[mod["key"]] = te.get(mod["key"], 0) + mod.get("delta", 0)

        return True, choice.get("result_text", "你做出了抉择。")

    def maybe_unity_enlightenment(self, rng=None):
        """高道心闭关时概率触发天人合一顿悟。

        返回 None（未触发）或 {"type": "qi", "multiplier": x} / {"type": "technique"}。
        无漏之境（道心≥80）被动：月几率乘算 unity_enlightenment_chance_mult。
        """
        cfg = self.config.get_unity_enlightenment()
        min_ms = cfg.get("min_mental_state", 80)
        if self.player.mental_state < min_ms:
            return None
        rng = rng or random
        chance = cfg.get("chance_per_month", 0.0)
        chance *= self.get_passive().get("unity_enlightenment_chance_mult", 1.0)
        if rng.random() >= chance:
            return None
        if rng.random() < cfg.get("technique_chance", 0.0):
            return {"type": "technique"}
        return {"type": "qi", "multiplier": cfg.get("qi_multiplier", 2.0)}

    def tick_monthly(self):
        """每月自然恢复：道心缓慢恢复，心魔自然衰减。

        返回 (mental_delta, heart_demon_delta, events)。
        """
        monthly = self.config.get_monthly_changes()
        base_recovery = monthly.get("mental_state_recovery", 1)
        base_decay = monthly.get("heart_demon_decay", 2)

        # 特质加成
        recovery_bonus = self.get_trait_effect("mental_state_recovery")
        decay_bonus = self.get_trait_effect("heart_demon_decay_bonus")
        level_bonus = self.get_level().get("heart_demon_decay_bonus", 0.0)

        mental_gain = self.adjust_mental_state(int(base_recovery + recovery_bonus))
        heart_decay = self.adjust_heart_demon(
            -int(base_decay * (1 + decay_bonus + level_bonus))
        )
        events = self.check_heart_demon_events()
        return mental_gain, heart_decay, events

    def get_dao_realm_status(self):
        """返回当前道境阶位、被动与下一阶信息，供 UI 展示。

        返回 dict：{name, min, mental_state, passive, next_tier}。
        next_tier 为下一更高阶配置（已臻最高阶时为 None）。
        """
        level = self.get_level()
        levels = self.config.data.get("mental_state_levels", [])
        current_min = level.get("min", 0)
        higher = [l for l in levels if l.get("min", 0) > current_min]
        next_tier = None
        if higher:
            next_tier = min(higher, key=lambda l: l.get("min", 0))
        return {
            "name": level.get("name", "凡境"),
            "min": current_min,
            "mental_state": self.player.mental_state,
            "passive": level.get("passive"),
            "next_tier": next_tier,
        }
