# -*- coding: utf-8 -*-
"""引擎游历/事件域 Mixin：explore 入口、事件效果应用与 AI 增强上下文。

GameEngine 继承本 Mixin。方法通过鸭子类型访问引擎其余成员
（player/notify/item_library/sect_manager/chronicle_manager 等）。
"""
import random

from game.constants import ELEMENT_NAMES


class EventMixin:
    """游历与事件域：explore / _apply_event / pop_pending_ai_event /
    _try_sense_scan / _handle_secret_realm。"""

    def explore(self):
        """在当前地点外出游历，随机触发事件。"""
        if not self.player.is_alive():
            self.notify("你已陨落，无法游历。")
            return

        location = self.get_current_location()

        # 游历一次消耗 6 个月（逐月推进，保证月度结算每月正确执行一次）
        for _ in range(6):
            self.world.advance(1)
            self.player.add_age_months(1)
            self._check_sect_daily_reset()
            self._run_registered_monthly_ticks()

        # 按当前地点权重抽取事件
        event = self.event_pool.draw("explore", location=location)

        # 元婴期神识扫描：探索时有概率洞察当前地点妖兽弱点
        self._try_sense_scan(location)

        if event:
            self._apply_event(event, location)
        else:
            self.notify("你外出游历半年，无所获，但心境略有提升。")

        # 记录游历年表
        self.chronicle_manager.record(
            f"在【{location['name']}】外出游历", category="explore"
        )

        # 维度①：游历名山大川增长道心
        if self.is_feature_enabled("heart_demon"):
            self.mental_state_manager.on_travel(self.player.location_id)

        # 维度④：天道注视下的无妄之灾 / 杀人夺宝
        if self.is_feature_enabled("heaven_retribution"):
            for log in self.heaven_retribution_manager.roll_travel_hazard(self):
                self.notify(log)

        # 维度⑤：前世遗迹回响
        if self.is_feature_enabled("lifespan_reincarnation"):
            self.lifespan_manager.roll_past_life_echo()

        # 概率听闻当地传闻
        if random.random() < 0.3:
            rumor = self.letter_rumor_manager.hear_rumor(location_id=self.player.location_id)
            if rumor:
                self.notify(
                    f"[cyan]你听闻一则传闻：{rumor.get('description', '')}"
                )

        self._check_death()
        self._advance_tutorial("explore")

    def _try_sense_scan(self, location):
        """
        元婴期神识扫描：探索时概率洞察当前地点某敌人的弱点。
        扫描成功后，下一场对目标敌人的战斗伤害 +20%。
        """
        if not self.player.has_feature("nascent_soul_revive"):
            return
        if random.random() >= 0.3:
            return

        enemy_ids = location.get("enemies", [])
        if not enemy_ids:
            return

        target_id = random.choice(enemy_ids)
        enemy_data = self.enemy_library.get(target_id)
        if not enemy_data:
            return

        self.player.sense_scan_target = target_id
        self.notify(
            f"[purple]神识外放！你洞察到【{enemy_data['name']}】的弱点，"
            f"下一场对其战斗伤害 +20%！"
        )

    def _apply_event(self, event, location):
        """应用事件效果到玩家。

        AI 动态剧情采用「离线秒渲染 + AI 增强补发」两段式：
        1. 立即用离线模板渲染文案并 notify（玩家秒见结果，界面零阻塞）；
        2. 若 ai_llm_story 开启，把事件上下文存为 pending 并通知 UI
           （__AI_STORY_PENDING__），由 UI 层后台线程生成 AI 增强文案。
        战斗/商人/秘境事件有自己的交互弹窗，不做 AI 增强。
        """
        if self.is_feature_enabled("ai_dynamic_event"):
            event = dict(event)
            event["description"] = self.story_generator.render_event(
                event, self.player, location
            )
            if self.is_feature_enabled("ai_llm_story"):
                self._pending_ai_event = {"event": event, "location": location}
        # 如果事件触发战斗，进入战斗流程
        if event.get("trigger_combat"):
            enemy = self._spawn_enemy(location)
            if enemy:
                self.notify(f"【{event['name']}】{enemy.description}")
                self.start_combat(enemy)
            else:
                self.notify(f"【{event['name']}】你感受到了妖气，但妖兽已经离去。")
            return

        # 如果事件触发云游商人，通知 UI 打开交易弹窗
        if event.get("trigger_merchant"):
            self.notify(f"【{event['name']}】{event['description']}")
            self.notify("__MERCHANT_ENCOUNTER__")
            return

        # 如果事件触发属性秘境，按灵根属性给予对应技能书
        if event.get("trigger_secret_realm"):
            self._handle_secret_realm(event)
            return

        effects = event.get("effects", {})

        # 修为变化
        if "qi" in effects:
            self.player.qi += effects["qi"]

        # 健康变化
        if "health" in effects:
            self.player.health += effects["health"]
            self.player.health = min(self.player.health, self.player.max_health)

        # 获得物品
        if "item" in effects:
            item_id = effects["item"]
            count = effects.get("item_count", 1)
            for _ in range(count):
                item = self.item_library.create(item_id)
                self.player.add_item(item)
            item_name = self.item_library.get(item_id).name
            self.notify(f"【{event['name']}】{event['description']} 获得 {item_name} x{count}。")
            # 推进收集类任务
            self.advance_collect_quest(item_id)
            # 推进宗门收集任务
            self.sect_manager.update_task_progress("collect", item_id, count)
            # 触发获得物品事件钩子
            self._on_gain_item(item_id, count)
        else:
            self.notify(f"【{event['name']}】{event['description']}")

        # AI 增强补发：通知 UI 层后台生成 AI 剧情文案（不阻塞当前流程）
        if getattr(self, "_pending_ai_event", None):
            self.notify("__AI_STORY_PENDING__")

    def pop_pending_ai_event(self):
        """取走待 AI 增强的游历事件上下文（UI 层发起后台生成用）。

        返回 {"event": dict, "location": dict}；无待处理事件返回 None。
        取走即清空，避免重复生成。
        """
        ctx = getattr(self, "_pending_ai_event", None)
        self._pending_ai_event = None
        return ctx

    def _handle_secret_realm(self, event):
        """
        处理属性秘境事件：按玩家灵根属性触发不同奇遇，赠送对应技能书。
        若玩家所有灵根对应技能均已习得，则转化为修为奖励。
        """
        # 属性 → 技能书 ID 和技能 ID 的映射
        element_manuals = {
            "metal": ("sword_manual", "sword_art"),
            "wood": ("vine_manual", "vine_whip"),
            "water": ("ice_manual", "ice_blade"),
            "fire": ("fireball_manual", "fireball"),
            "earth": ("stone_manual", "stone_fist"),
        }

        # 筛选玩家灵根对应、且尚未习得的技能书
        available = []
        for elem in self.player.spiritual_roots:
            manual_id, skill_id = element_manuals.get(elem, (None, None))
            if manual_id and not self.player.has_skill(skill_id):
                available.append((elem, manual_id, skill_id))

        if not available:
            # 所有灵根对应技能均已习得，转化为修为奖励
            bonus_qi = 80 + len(self.player.spiritual_roots) * 20
            self.player.qi += bonus_qi
            self.notify(
                f"【{event['name']}】{event['description']}"
                f"你已参悟本命灵根之道，秘境灵气化为你修为，增加 {bonus_qi} 点。"
            )
            return

        # 随机选一项未习得的技能书
        elem, manual_id, skill_id = random.choice(available)
        item = self.item_library.create(manual_id)
        if item:
            self.player.add_item(item)
            elem_cn = ELEMENT_NAMES.get(elem, elem)
            manual_name = self.item_library.get(manual_id).name
            self.notify(
                f"【{event['name']}】{event['description']}"
                f"你的{elem_cn}灵根与秘境共鸣，获得【{manual_name}】！"
                f"可在背包中研读习得技能。"
            )
            self._auto_save()
        else:
            # 物品库缺失，降级为修为奖励
            self.player.qi += 50
            self.notify(f"【{event['name']}】秘境中似有空灵之气，你静坐感悟，修为增加 50 点。")
