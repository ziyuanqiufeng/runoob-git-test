# -*- coding: utf-8 -*-
"""动态世界事件系统。

世界事件是跨越玩家个人行为的宏观事件，例如魔道入侵、灵气潮汐、兽潮等。
事件通过 config/world_events.json 配置，由 WorldEventManager 每月 tick 驱动，
具备触发条件判断、持续效果、到期恢复等完整生命周期。
"""
import json
import os
import random


class WorldEventConfig:
    """加载并索引 world_events.json 配置。"""

    def __init__(self, config_dir="config"):
        path = os.path.join(config_dir, "world_events.json")
        with open(path, "r", encoding="utf-8") as f:
            self.events = json.load(f)
        self.event_map = {e["id"]: e for e in self.events}

    def get(self, event_id):
        return self.event_map.get(event_id)


class WorldEventManager:
    """世界事件管理器：触发、推进、结束世界事件，并应用/恢复效果。"""

    def __init__(
        self,
        player,
        world,
        npc_library,
        enemy_library,
        item_library=None,
        notify_callback=None,
        config_dir="config",
        world_state_manager=None,
        is_feature_enabled=None,
    ):
        self.player = player
        self.world = world
        self.npc_library = npc_library
        self.enemy_library = enemy_library
        self.item_library = item_library
        # 通知回调，通常使用 engine.notify
        self.notify = notify_callback or (lambda x: None)
        self.config = WorldEventConfig(config_dir)
        # F-04 事件链相关
        self.config_dir = config_dir
        self.world_state_manager = world_state_manager
        self._is_feature_enabled = is_feature_enabled
        self._chains = self._load_chains(config_dir)
        self._chain_map = {c["id"]: c for c in self._chains if "id" in c}

    def tick(self):
        """每月调用一次：推进持续时间、结束过期事件、尝试触发新事件。"""
        self._tick_chains()
        self._advance_events()
        self._expire_events()
        self._try_trigger_events()

    # ==================== 触发判断 ====================

    def _try_trigger_events(self):
        """遍历所有事件配置，尝试触发满足条件的新事件。"""
        for event in self.config.events:
            event_id = event["id"]
            # 已活跃的事件不再触发
            if event_id in self.player.active_world_events:
                continue
            # 冷却中不触发
            if self._is_on_cooldown(event):
                continue
            # 触发器与条件判断
            if not self._check_trigger(event):
                continue
            if not self._check_conditions(event):
                continue
            self._start_event(event)

    def _is_on_cooldown(self, event):
        """检查事件是否处于冷却期。"""
        trigger = event.get("trigger", {})
        cooldown_years = trigger.get("cooldown_years", 0)
        if cooldown_years <= 0:
            return False
        history = self.player.world_event_history.get(event["id"])
        if not history:
            return False
        ended_month = history.get("ended_month", 0)
        current_month = self.world.year * 12 + self.world.month
        return (current_month - ended_month) < cooldown_years * 12

    def _check_trigger(self, event):
        """判断事件触发器是否满足。"""
        trigger = event.get("trigger", {})
        ttype = trigger.get("type", "random")
        if ttype == "scheduled":
            # 指定月/日触发
            month = trigger.get("month")
            day = trigger.get("day", 1)
            return self.world.month == month and self.world.day == day
        if ttype == "random":
            chance = trigger.get("chance", 0.0)
            min_year = trigger.get("min_year", 0)
            return self.world.year >= min_year and random.random() < chance
        return False

    def _check_conditions(self, event):
        """判断事件附加条件是否全部满足。"""
        for cond in event.get("conditions", []):
            ctype = cond.get("type")
            if ctype == "camp":
                if not self._check_camp_condition(cond):
                    return False
            elif ctype == "reputation":
                if not self._check_reputation_condition(cond):
                    return False
            elif ctype == "year":
                if not self._check_year_condition(cond):
                    return False
            elif ctype == "chance":
                if random.random() >= cond.get("value", 1.0):
                    return False
        return True

    def _check_camp_condition(self, cond):
        """检查正道/魔道阵营值条件，例如 evil_value: '>30'。"""
        if "evil_value" in cond:
            return self._compare(self.player.evil_value, cond["evil_value"])
        if "righteous_value" in cond:
            return self._compare(self.player.righteous_value, cond["righteous_value"])
        return True

    def _check_reputation_condition(self, cond):
        """检查声望条件，例如 rep_id: 'demonic_reputation', value: '>100'。"""
        rep_id = cond.get("rep_id")
        op = cond.get("value", "")
        val = self.player.reputation.get(rep_id, 0)
        return self._compare(val, op)

    def _check_year_condition(self, cond):
        """检查世界年份条件。"""
        return self._compare(self.world.year, cond.get("value", ""))

    @staticmethod
    def _compare(value, op_str):
        """解析 '>=3'、'>30' 等比较字符串。"""
        op_str = str(op_str).strip()
        if op_str.startswith(">="):
            return value >= int(op_str[2:])
        if op_str.startswith("<="):
            return value <= int(op_str[2:])
        if op_str.startswith(">"):
            return value > int(op_str[1:])
        if op_str.startswith("<"):
            return value < int(op_str[1:])
        if op_str.startswith("="):
            return value == int(op_str[1:])
        # 默认按相等处理
        return value == int(op_str)

    # ==================== 事件生命周期 ====================

    def _start_event(self, event):
        """启动一个事件：记录状态、发布公告、应用效果。"""
        event_id = event["id"]
        current_month = self.world.year * 12 + self.world.month
        self.player.active_world_events[event_id] = {
            "started_year": self.world.year,
            "started_month": self.world.month,
            "started_world_month": current_month,
            "remaining_months": event.get("duration_months", 1),
            "effects_applied": False,
        }

        announcement = event.get("announcement")
        if announcement:
            self.notify(f"[world]{announcement}")

        self._apply_effects(event)
        self.player.active_world_events[event_id]["effects_applied"] = True

        # 记录年表
        from game.chronicle import ChronicleManager

        ChronicleManager(self.player, self.world).record(
            f"世界事件【{event.get('name', event_id)}】发生：{event.get('description', '')}",
            category="world_event",
        )

    def _advance_events(self):
        """推进所有活跃事件的剩余月数。"""
        for state in self.player.active_world_events.values():
            state["remaining_months"] -= 1

    def _expire_events(self):
        """结束剩余月数 <= 0 的活跃事件。"""
        expired = [
            event_id
            for event_id, state in self.player.active_world_events.items()
            if state.get("remaining_months", 0) <= 0
        ]
        for event_id in expired:
            self._end_event(event_id)

    def _end_event(self, event_id):
        """结束事件：恢复可逆效果、移入历史、发送通知。"""
        event = self.config.get(event_id)
        if event:
            self._revert_effects(event)
        self.player.active_world_events.pop(event_id, None)
        current_month = self.world.year * 12 + self.world.month
        self.player.world_event_history[event_id] = {"ended_month": current_month}
        self.notify(f"[world]世界事件【{event.get('name', event_id)}】结束。")

    # ==================== 效果应用 ====================

    def _apply_effects(self, event):
        """应用事件效果列表。"""
        for effect in event.get("effects", []):
            etype = effect.get("type")
            if etype == "spawn_enemy":
                self._apply_spawn_enemy(effect, event["id"])
            elif etype == "change_npc_location":
                self._apply_change_npc_location(effect)
            elif etype == "add_reputation":
                self._apply_add_reputation(effect)
            elif etype == "modify_price_multiplier":
                self._apply_modify_price_multiplier(effect)
            elif etype == "notify":
                self._apply_notify(effect)

    def _apply_spawn_enemy(self, effect, event_id):
        """生成事件敌人。

        - is_boss=true 时尝试作为世界 BOSS 生成；
        - 否则加入玩家待遭遇列表，进入对应地点时触发战斗。
        """
        enemy_id = effect.get("enemy_id")
        location_id = effect.get("location")
        count = effect.get("count", 1)
        is_boss = effect.get("is_boss", False)

        if is_boss:
            from game.world_boss import WorldBossManager

            mgr = WorldBossManager(self.world, self.enemy_library)
            if mgr.config.get(enemy_id):
                mgr.spawn(enemy_id)
                return

        # 普通敌人作为地点遭遇暂存
        self.player.world_event_encounters.append(
            {
                "enemy_id": enemy_id,
                "location_id": location_id,
                "event_id": event_id,
                "count": count,
            }
        )

    def _apply_change_npc_location(self, effect):
        """临时改变 NPC 当前所在地点，记录原位置以便事件结束后恢复。"""
        npc_id = effect.get("npc_id")
        location_id = effect.get("location")
        npc = self.npc_library.get(npc_id)
        if not npc:
            return
        # 使用栈记录当前位置变化，支持多个事件连续移动同一 NPC
        if not hasattr(npc, "_event_location_stack"):
            npc._event_location_stack = []
        # 记录当前实际位置（current_location 为 None 表示在默认 location）
        npc._event_location_stack.append(npc.current_location)
        npc.current_location = location_id

    def _apply_add_reputation(self, effect):
        """调整玩家声望。"""
        rep_id = effect.get("rep_id")
        value = effect.get("value", 0)
        from game.reputation import ReputationManager

        mgr = ReputationManager(self.player)
        mgr.adjust(rep_id, value)

    def _apply_modify_price_multiplier(self, effect):
        """临时修改某地点的商品价格倍率。"""
        location_id = effect.get("location")
        self.player.world_event_price_mods[location_id] = {
            "buy_mult": effect.get("buy_mult", 1.0),
            "sell_mult": effect.get("sell_mult", 1.0),
        }

    def _apply_notify(self, effect):
        """发送事件相关通知。"""
        message = effect.get("message", "")
        if message:
            self.notify(f"[world]{message}")

    def _revert_effects(self, event):
        """恢复事件中可逆的效果（NPC 位置、价格倍率）。"""
        for effect in event.get("effects", []):
            etype = effect.get("type")
            if etype == "change_npc_location":
                npc_id = effect.get("npc_id")
                npc = self.npc_library.get(npc_id)
                if npc and hasattr(npc, "_event_location_stack") and npc._event_location_stack:
                    npc.current_location = npc._event_location_stack.pop()
            elif etype == "modify_price_multiplier":
                location_id = effect.get("location")
                self.player.world_event_price_mods.pop(location_id, None)

    # ==================== 事件链（F-04 扩展） ====================

    def _load_chains(self, config_dir):
        """加载 config/world/world_event_chains.json（事件链配置）。缺失则无链。"""
        path = os.path.join(config_dir, "world", "world_event_chains.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("chains", [])
        except (json.JSONDecodeError, OSError):
            return []

    def _chains_enabled(self):
        if self._is_feature_enabled is None:
            return True
        return self._is_feature_enabled("dynamic_world_event")

    def _tick_chains(self):
        if not self._chains_enabled():
            return
        for chain_id in list(self.player.active_event_chains.keys()):
            self._advance_chain(chain_id)
        self._try_start_chains()

    def _advance_chain(self, chain_id):
        chain = self._chain_map.get(chain_id)
        if chain is None:
            self._finalize_chain(chain_id)
            return
        st = self.player.active_event_chains[chain_id]
        if st.get("awaiting_choice"):
            return  # 等待玩家在 UI 中选择
        st["remaining_months"] -= 1
        if st["remaining_months"] > 0:
            return
        stage = chain["stages"].get(st["current_stage"], {})
        if stage.get("player_choices"):
            st["awaiting_choice"] = True
            self.notify(
                f"[world]事件链【{chain.get('name', chain_id)}】"
                f"进入决策节点：{stage.get('name', '')}"
            )
            return
        if stage.get("auto_next"):
            self._enter_stage(chain_id, stage["auto_next"])
            return
        if stage.get("ending"):
            self._finalize_chain(chain_id)
            return
        self._finalize_chain(chain_id)

    def _enter_stage(self, chain_id, stage_id):
        chain = self._chain_map.get(chain_id)
        if chain is None:
            self._finalize_chain(chain_id)
            return
        stage = chain["stages"].get(stage_id)
        st = self.player.active_event_chains[chain_id]
        if stage is None:
            self._finalize_chain(chain_id)
            return
        st["current_stage"] = stage_id
        st["remaining_months"] = int(stage.get("duration_months", 1))
        st["awaiting_choice"] = False
        applied = []
        if self.world_state_manager is not None:
            applied = self.world_state_manager.apply_effects(stage.get("global_effects"))
        st["applied_effects"].extend(applied)
        self.notify(
            f"[world]事件链【{chain.get('name', chain_id)}】"
            f"推进至：{stage.get('name', '')}"
        )
        if stage.get("trigger_battle"):
            self._resolve_chain_battle(chain_id, stage)

    def _resolve_chain_battle(self, chain_id, stage):
        enemy_id = stage.get("battle_enemy_id")
        success_rate = float(stage.get("battle_success_rate", 0.7))
        if enemy_id:
            from game.world_boss import WorldBossManager

            mgr = WorldBossManager(self.world, self.enemy_library)
            if mgr.config.get(enemy_id):
                mgr.spawn(enemy_id)
                self.notify("[world]事件链战斗触发：强敌现身！")
                return
        # 无具体敌人则按概率结算胜负
        if random.random() < success_rate:
            reward = stage.get("reward", {})
            rep = reward.get("reputation", 0)
            if rep:
                from game.reputation import ReputationManager

                ReputationManager(self.player).adjust("qingyun_reputation", rep)
            loot = reward.get("loot")
            if loot and self.item_library:
                item = self.item_library.create(loot)
                if item:
                    self.player.add_item(item)
                    self.notify(f"[world]事件链大捷，获得【{item.name}】！")
            self.notify("[world]事件链战斗胜利！")
        else:
            fc = stage.get("failure_consequence", {})
            if fc and self.world_state_manager is not None:
                applied = self.world_state_manager.apply_effects(fc)
                st = self.player.active_event_chains[chain_id]
                st["applied_effects"].extend(applied)
                self.notify("[world]事件链战斗失利，局势恶化……")

    def _finalize_chain(self, chain_id):
        st = self.player.active_event_chains.pop(chain_id, None)
        if st and self.world_state_manager is not None:
            self.world_state_manager.revert_effects(st.get("applied_effects", []))
        self.player.world_event_chain_history[chain_id] = {
            "ended_month": self.world.year * 12 + self.world.month
        }
        chain = self._chain_map.get(chain_id)
        name = chain.get("name", chain_id) if chain else chain_id
        self.notify(f"[world]事件链【{name}】落幕。")

    def _try_start_chains(self):
        current_month = self.world.year * 12 + self.world.month
        for chain in self._chains:
            cid = chain["id"]
            if cid in self.player.active_event_chains:
                continue
            ended = self.player.world_event_chain_history.get(cid, {}).get("ended_month", 0)
            if ended and current_month - ended < 12:
                continue  # 简单冷却：已结束的链 12 个月内不再触发
            min_year = chain.get("min_year", 0)
            if self.world.year < min_year:
                continue
            weight = chain.get("start_weight", 0)
            if weight <= 0:
                continue
            if random.random() < weight / 100.0:
                self._start_chain(cid)

    def _start_chain(self, chain_id):
        chain = self._chain_map[chain_id]
        self.player.active_event_chains[chain_id] = {
            "current_stage": "1",
            "remaining_months": int(chain["stages"]["1"].get("duration_months", 1)),
            "applied_effects": [],
            "awaiting_choice": False,
        }
        self.notify(f"[world]重大事件链【{chain.get('name', chain_id)}】拉开序幕！")
        self._enter_stage(chain_id, "1")

    def get_active_chains(self):
        """返回活跃事件链摘要，供 UI 展示与决策。"""
        result = []
        for cid, st in self.player.active_event_chains.items():
            chain = self._chain_map.get(cid)
            if not chain:
                continue
            stage = chain["stages"].get(st["current_stage"], {})
            choices = []
            if st.get("awaiting_choice") and stage.get("player_choices"):
                for i, c in enumerate(stage["player_choices"]):
                    choices.append({"index": i, "text": c.get("text", f"选项{i + 1}")})
            result.append({
                "id": cid,
                "name": chain.get("name", cid),
                "stage_id": st["current_stage"],
                "stage_name": stage.get("name", ""),
                "remaining_months": st.get("remaining_months", 0),
                "awaiting_choice": st.get("awaiting_choice", False),
                "choices": choices,
            })
        return result

    def choose_chain_option(self, chain_id, choice_index):
        """玩家在决策节点选择一个选项，应用效果并推进到下一阶段。"""
        st = self.player.active_event_chains.get(chain_id)
        if not st or not st.get("awaiting_choice"):
            return False
        chain = self._chain_map.get(chain_id)
        if not chain:
            return False
        stage = chain["stages"].get(st["current_stage"], {})
        choices = stage.get("player_choices", [])
        if choice_index < 0 or choice_index >= len(choices):
            return False
        choice = choices[choice_index]
        for k, v in choice.get("effects", {}).items():
            if k == "reputation":
                from game.reputation import ReputationManager

                ReputationManager(self.player).adjust("qingyun_reputation", v)
            elif self.world_state_manager is not None:
                applied = self.world_state_manager.apply_effects({k: v})
                st["applied_effects"].extend(applied)
        st["awaiting_choice"] = False
        self.notify(f"[world]你选择了：{choice.get('text', '')}")
        self._enter_stage(chain_id, choice.get("next_stage"))
        return True

    # ==================== 查询接口 ====================

    def get_active_events(self):
        """返回当前活跃事件 ID 列表。"""
        return list(self.player.active_world_events.keys())

    def get_event_descriptions(self):
        """返回活跃事件的名称与描述列表，供 UI 展示。"""
        result = []
        for event_id in self.get_active_events():
            event = self.config.get(event_id)
            if event:
                result.append(
                    {
                        "id": event_id,
                        "name": event.get("name", event_id),
                        "description": event.get("description", ""),
                        "remaining_months": self.player.active_world_events[event_id].get(
                            "remaining_months", 0
                        ),
                    }
                )
        return result

    def get_encounter_for_location(self, location_id):
        """获取指定地点待触发的事件遭遇，若无返回 None。"""
        for enc in self.player.world_event_encounters:
            if enc.get("location_id") == location_id:
                return enc
        return None

    def remove_encounter(self, encounter):
        """移除一个已触发的事件遭遇。"""
        if encounter in self.player.world_event_encounters:
            self.player.world_event_encounters.remove(encounter)
