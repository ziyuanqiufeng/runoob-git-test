# -*- coding: utf-8 -*-
"""GameEngine 城池生活域 Mixin（第八期拆分，2026-09-22）。

从 engine.py 迁入 34 个城池生活方法：客栈歇息/传闻、坊市/摆摊/拍卖、
城池政策/事件/防卫战/城池任务/捐献/声望、竞技场切磋/排位/每日奖励。
由剪切脚本从 engine.py 原样迁出（tools/.city_life_cut_backup_20260922.py 为切出备份）。
"""
import random

from game.city_policy_manager import CityPolicyManager
from game.constants import ELEMENT_NAMES
from game.enemy import Enemy


class CityLifeMixin:
    """城池生活方法集：依赖宿主 GameEngine 的 building_manager /
    reputation_manager / city_event_manager / arena_ranking_manager 等实例属性。"""

    def rest_at_inn(self, cost=50):
        """在客栈歇息，消耗灵石恢复气血与心境。"""
        # 检查是否还有需要恢复的状态
        if self.player.health >= self.player.max_health and self.player.mental_state >= 50:
            self.notify("你状态饱满，无需歇息。")
            return False

        # 检查灵石是否足够
        if self.player.count_item("spirit_stone") < cost:
            self.notify(f"客栈歇息需 {cost} 灵石，你的灵石不足。")
            return False

        self.player.consume_items("spirit_stone", cost)
        # 恢复气血至上限
        old_hp = self.player.health
        self.player.health = self.player.max_health
        # 恢复心境至平常心（50），若已更高则不变
        old_mental = self.player.mental_state
        self.player.mental_state = max(self.player.mental_state, 50)
        # 歇息一次视为度过 1 个月
        self.world.advance(1)
        self.player.add_age_months(1)
        self._check_sect_daily_reset()

        self.notify(
            f"你在客栈歇息一月，花费 {cost} 灵石，"
            f"恢复 {self.player.health - old_hp} 点气血，"
            f"心境恢复至 {self.player.mental_state}。"
        )
        self._auto_save()
        return True

    def gather_rumor_at_inn(self, category=None):
        """
        在客栈花费灵石打听消息。

        参数：
            category: 情报类别，可选 market/secret/npc/event/trivia。

        返回：
            rumor 字典；灵石不足或没有新传闻时返回 None。
        """
        rumor, cost = self.letter_rumor_manager.gather_rumor_at_inn(category=category)
        if rumor is None:
            if cost > 0:
                self.notify(f"打听消息需要 {cost} 灵石，你的灵石不足。")
            else:
                self.notify("客栈里暂时没有新的传闻了。")
            return None

        desc = rumor.get("description", "")
        cat_label = {
            "market": "【坊市传闻】",
            "secret": "【秘境线索】",
            "npc": "【人物动向】",
            "event": "【大事预警】",
            "trivia": "【坊间闲谈】",
        }.get(rumor.get("category"), "【传闻】")

        self.notify(f"你花费 {cost} 灵石打听消息，{cat_label} {desc}")
        # 应用传闻效果（如解锁秘境等）
        self.letter_rumor_manager.apply_rumor_effect(rumor["id"], self)
        self._auto_save()
        return rumor

    def open_city_market(self):
        """打开城中坊市商人，返回一个临时 NPC 供 NPCDialog 使用。"""
        from game.npc import NPC
        cfg = self.market_npc_manager.get_npc("city_merchant")
        if cfg:
            shop_items = cfg.get("shop_items", [])
            buy_mult = cfg.get("buy_multiplier", 1.0)
            sell_mult = cfg.get("sell_multiplier", 0.6)
            name = cfg.get("name", "坊市商人")
            description = cfg.get("description", "城中坊市的掌柜。")
            dialog = cfg.get("dialog", "客官想要点什么？")
        else:
            # 兜底：常见丹药、材料、符箓
            shop_items = [
                "healing_pill", "qi_pill", "spirit_stone", "herb",
                "talisman_attack", "talisman_defense"
            ]
            buy_mult = 1.0
            sell_mult = 0.6
            name = "坊市商人"
            description = "城中坊市的掌柜，门路颇多。"
            dialog = "客官想要点什么？"

        # 随机抽取 6~8 种商品上架
        available = random.sample(
            shop_items, min(len(shop_items), random.randint(6, 8))
        )
        merchant = NPC(
            npc_id="city_merchant",
            name=name,
            location=self.player.location_id,
            description=description,
            dialog=dialog,
            quests=[],
            shop_items=available,
            buy_multiplier=buy_mult,
            sell_multiplier=sell_mult,
        )
        self._advance_tutorial("market")
        return merchant

    def setup_stall(self, item_id, price, count=1):
        """
        在坊市摆摊出售物品。

        参数：
            item_id: 要出售的物品 ID。
            price: 单价（灵石）。
            count: 出售数量，默认 1。

        返回：
            (success, message) 元组。
        """
        ok, msg = self.stall_manager.setup_stall(item_id, price, count)
        if ok:
            self._auto_save()
        return ok, msg

    def collect_stall_revenue(self):
        """领取摆摊收入。"""
        amount = self.stall_manager.collect_revenue()
        if amount > 0:
            self.notify(f"你领取了摆摊收入 {amount} 灵石。")
            self._auto_save()
        else:
            self.notify("当前没有待领取的摆摊收入。")
        return amount

    def run_auction(self):
        """
        刷新并获取拍卖行当前拍品列表。

        返回拍品列表，每个元素包含 item_id、name、base_price、
        current_price、bidder 等字段。
        """
        self.auction_house_manager.refresh()
        return self.auction_house_manager.get_lots()

    def bid_auction(self, lot_index, amount):
        """对拍卖行指定拍品出价。"""
        ok, msg = self.auction_house_manager.bid(lot_index, amount)
        if ok:
            self.notify(msg)
            self._auto_save()
        return ok, msg

    def settle_auction(self, lot_index):
        """结算拍卖行指定拍品。"""
        ok, msg = self.auction_house_manager.settle(lot_index)
        if ok:
            self.notify(msg)
            self._auto_save()
        return ok, msg

    def _get_city_policy_manager(self, city_id=None):
        """获取指定城池的政策管理器，默认使用玩家当前所在城池。"""
        city_id = city_id or self.player.location_id
        return CityPolicyManager(self.player, city_id)

    def _tick_city_policies(self):
        """每月推进所有城池的政策与城主任期。"""
        if not hasattr(self.player, "city_policies"):
            return
        for city_id in list(self.player.city_policies.keys()):
            mgr = CityPolicyManager(self.player, city_id)
            expired = mgr.tick_monthly()
            for name in expired:
                self.notify(f"【{city_id}】政策【{name}】已到期。")

    def campaign_for_mayor(self, city_id=None):
        """
        参与指定城池的城主竞选。

        返回 (success, message)。
        """
        mgr = self._get_city_policy_manager(city_id)
        ok, msg = mgr.campaign()
        if ok:
            self.notify(msg)
            self._auto_save()
        return ok, msg

    def enact_city_policy(self, policy_id, city_id=None):
        """
        在指定城池颁布政策。

        返回 (success, message)。
        """
        mgr = self._get_city_policy_manager(city_id)
        ok, msg = mgr.enact_policy(policy_id)
        if ok:
            self.notify(msg)
            self._auto_save()
        return ok, msg

    def get_city_policy_info(self, city_id=None):
        """获取城池政策与城主信息，供 UI 展示。"""
        mgr = self._get_city_policy_manager(city_id)
        return {
            "is_mayor": mgr.is_mayor(),
            "mayor_until": mgr.get_mayor_until_month(),
            "active": mgr.get_active_policy_descriptions(),
            "can_campaign": mgr.can_campaign()[0],
        }

    def start_arena_combat(self):
        """在演武场触发一场普通切磋战斗，返回生成的对手 Enemy。"""
        location = self.get_current_location()
        enemy_ids = location.get("enemies", []) if location else []
        # 优先使用当前地点配置的敌人；若无则使用通用修士对手
        if enemy_ids:
            enemy_id = random.choice(enemy_ids)
        else:
            enemy_id = random.choice(["righteous_disciple", "evil_cultivator"])

        enemy_data = self.enemy_library.get(enemy_id)
        if not enemy_data:
            self.notify("演武场今日无人应战。")
            return None

        enemy = Enemy.from_dict(enemy_data)
        # 根据玩家境界微调对手属性，使其保持切磋强度
        player_order = self._get_realm_order()
        enemy_order = self._get_enemy_realm_order(enemy) or player_order
        diff = player_order - enemy_order
        if diff > 0:
            # 玩家境界高，提升对手属性
            scale = 1.0 + diff * 0.08
            enemy.max_hp = int(enemy.max_hp * scale)
            enemy.hp = enemy.max_hp
            enemy.attack = int(enemy.attack * scale)
            enemy.defense = int(enemy.defense * scale)
        elif diff < 0:
            # 玩家境界低，降低对手属性，避免秒杀
            scale = max(0.5, 1.0 + diff * 0.05)
            enemy.max_hp = int(enemy.max_hp * scale)
            enemy.hp = enemy.max_hp
            enemy.attack = int(enemy.attack * scale)
            enemy.defense = int(enemy.defense * scale)

        enemy.name = f"演武场·{enemy.name}"
        self.notify(f"你踏入演武场，一名{enemy.name}上前挑战！")
        return enemy

    def get_arena_ranking_opponents(self):
        """获取当前城池演武场中玩家可挑战的排名对手。"""
        city_id = self.player.location_id
        return self.arena_ranking_manager.get_challengeable_opponents(
            city_id, self.player.arena_rank
        )

    def start_arena_ranking_challenge(self, opponent_id):
        """
        发起一场演武场排名挑战。

        返回生成的 Enemy 对象；如果今日挑战次数已满或对手不可挑战，返回 None。
        """
        self._reset_arena_daily_if_needed()
        limit = self.arena_ranking_manager.get_daily_challenge_limit()
        if self.player.arena_daily_challenges >= limit:
            self.notify(f"今日演武场挑战次数已达上限（{limit} 次）。")
            return None

        city_id = self.player.location_id
        opponent = self.arena_ranking_manager.get_opponent(city_id, opponent_id)
        if not opponent:
            self.notify("该挑战者不存在。")
            return None

        # 检查是否可挑战
        challengeable = self.get_arena_ranking_opponents()
        if not any(o["id"] == opponent_id for o in challengeable):
            self.notify("该对手目前不在你的挑战范围内。")
            return None

        enemy_data = self.enemy_library.get(opponent["enemy_id"])
        if not enemy_data:
            self.notify("演武场今日无人应战。")
            return None

        enemy = Enemy.from_dict(enemy_data)
        enemy.name = f"{opponent['title']}·{opponent['name']}"

        # 根据对手配置的境界微调属性
        opponent_realm = self.world.get_realm(opponent.get("realm", ""))
        opponent_realm_order = opponent_realm["order"] if opponent_realm else self._get_realm_order()
        player_order = self._get_realm_order()
        if opponent_realm_order is not None:
            diff = player_order - opponent_realm_order
            if diff > 0:
                scale = 1.0 + diff * 0.06
            elif diff < 0:
                scale = max(0.5, 1.0 + diff * 0.04)
            else:
                scale = 1.0
            enemy.max_hp = int(enemy.max_hp * scale)
            enemy.hp = enemy.max_hp
            enemy.attack = int(enemy.attack * scale)
            enemy.defense = int(enemy.defense * scale)

        # 记录 pending 对手，战斗结束后结算排名
        self.pending_arena_opponent = opponent
        self.player.arena_daily_challenges += 1
        self.notify(f"你向【{enemy.name}】发起擂台挑战！")
        return enemy

    def _finish_arena_ranking_challenge(self, victory):
        """
        结算演武场排名挑战。

        胜利时根据对手排名提升玩家排名，并发放灵石、声望奖励；
        有概率提升随机技能熟练度。失败则排名不变。
        返回结算日志列表。
        """
        opponent = getattr(self, "pending_arena_opponent", None)
        if not opponent:
            return []
        logs = []
        city_id = self.player.location_id
        opponent_rank = self.arena_ranking_manager.get_opponent_rank(
            city_id, opponent["id"]
        )

        if victory:
            player_rank = self.player.arena_rank
            if self.arena_ranking_manager.should_increase_rank(
                player_rank, opponent_rank
            ):
                self.player.arena_rank = opponent_rank
                logs.append(
                    f"[gold]恭喜！你战胜 {opponent['title']}·{opponent['name']}，"
                    f"排名提升至第 {opponent_rank} 位！"
                )
            else:
                logs.append(
                    f"[green]你战胜了 {opponent['title']}·{opponent['name']}，"
                    f"但排名未发生变化。"
                )

            rewards = self.arena_ranking_manager.calculate_rewards(opponent_rank)
            spirit_stone = rewards.get("spirit_stone", 0)
            reputation = rewards.get("reputation", 0)
            if spirit_stone > 0:
                for _ in range(spirit_stone):
                    item = self.item_library.create("spirit_stone")
                    self.player.add_item(item)
                logs.append(f"[blue]获得灵石 ×{spirit_stone}。")
            if reputation > 0:
                self.reputation_manager.adjust(
                    f"{city_id}_reputation", reputation
                )
                loc_name = self.get_current_location().get("name", city_id)
                logs.append(f"[blue]{loc_name}声望 +{reputation}。")

            # 概率提升技能熟练度
            if (
                random.random()
                < rewards.get("skill_proficiency_chance", 0.3)
            ):
                skill_id = self.arena_ranking_manager.get_random_skill_for_proficiency(
                    self.player
                )
                if skill_id:
                    leveled_up = self.player.gain_skill_exp(skill_id, 1)
                    skill_name = getattr(
                        self.skill_library.get(skill_id), "name", skill_id
                    )
                    if leveled_up:
                        logs.append(
                            f"[purple]【顿悟】{skill_name} 熟练度提升一级！"
                        )
                    else:
                        logs.append(
                            f"[purple]【精进】{skill_name} 熟练度经验 +1。"
                        )
        else:
            logs.append(
                f"[red]挑战失败，{opponent['title']}·{opponent['name']} 守住了排名。"
            )

        # 清空 pending，避免重复结算
        self.pending_arena_opponent = None
        self._auto_save()
        return logs

    # ==================== 城池动态事件（妖兽攻城） ====================

    def get_active_city_event(self):
        """获取当前城池的活跃动态事件（如妖兽攻城）。"""
        return self.city_event_manager.get_active_event(self.player)

    def start_city_event(self, event_id):
        """手动触发一个城池事件。"""
        if self.city_event_manager.start_event(self.player, event_id):
            event = self.city_event_manager.get_event(event_id)
            self.notify(f"[red]【城池事件】{event['name']}：{event['description']}")
            self._auto_save()
            return True
        return False

    def join_city_defense(self):
        """
        参与当前城池的守城战斗。

        返回事件配置与敌人列表；若无活跃事件返回 (None, [])。
        """
        event = self.get_active_city_event()
        if not event:
            self.notify("当前城池暂无需要守城的事件。")
            return None, []

        enemies = self.city_event_manager.create_enemies(event["id"])
        if not enemies:
            self.notify("妖兽群已经退去，无需再战。")
            return None, []

        # 记录 pending 状态，便于 UI 依次推进波次
        self.pending_city_event = {
            "event_id": event["id"],
            "enemies": enemies,
            "current_wave": 0,
        }
        self.notify(
            f"[red]你加入守城战线，共有 {len(enemies)} 波妖兽来袭！"
        )
        return event, enemies

    def get_next_city_defense_enemy(self):
        """获取守城战斗中下一波敌人。"""
        pending = getattr(self, "pending_city_event", None)
        if not pending:
            return None
        idx = pending["current_wave"]
        if idx >= len(pending["enemies"]):
            return None
        return pending["enemies"][idx]

    def _advance_city_defense_wave(self):
        """推进到下一波妖兽，若全部击败则结算奖励。"""
        pending = getattr(self, "pending_city_event", None)
        if not pending:
            return []

        pending["current_wave"] += 1
        logs = []
        if pending["current_wave"] >= len(pending["enemies"]):
            rewards = self.city_event_manager.finish_event(
                self.player, pending["event_id"]
            )
            event = self.city_event_manager.get_event(pending["event_id"])
            city_id = event.get("city_id", "")
            loc_name = self.get_current_location().get("name", city_id)

            if rewards.get("spirit_stone", 0) > 0:
                logs.append(
                    f"[gold]守城成功！你获得灵石 ×{rewards['spirit_stone']}。"
                )
            if rewards.get("reputation", 0) > 0:
                self.reputation_manager.adjust(
                    f"{city_id}_reputation", rewards["reputation"]
                )
                logs.append(
                    f"[blue]{loc_name}声望 +{rewards['reputation']}。"
                )
            logs.append(f"[green]{event['name']}已成功平息。")
            self.pending_city_event = None
            self._auto_save()
        return logs

    def get_city_quests(self, refresh=False):
        """获取当前城池的动态任务列表；若 refresh 为 True 则重新生成。"""
        location = self.get_current_location()
        if not location:
            return []

        loc_id = location.get("id", "")
        loc_name = location.get("name", "")

        # 若切换了城池或要求刷新，则重新生成任务池
        if (
            refresh
            or not self.player.city_quest_pool
            or self.player.city_quest_pool[0].get("city_id") != loc_id
        ):
            self.player.city_quest_pool = self.city_quest_generator.generate(
                loc_id, loc_name, self.item_library, count=3
            )

        return self.player.city_quest_pool

    def accept_city_quest(self, quest_id):
        """在城主府接取一个城池动态任务。"""
        quest = None
        for q in self.player.city_quest_pool:
            if q["id"] == quest_id:
                quest = q
                break
        if not quest:
            self.notify("该任务已下架。")
            return False
        if quest_id in self.player.active_city_quests:
            self.notify("你已经接取了该任务。")
            return False

        self.player.active_city_quests[quest_id] = 0
        self.notify(f"接取城池任务：【{quest['name']}】{quest['description']}")
        self._auto_save()
        return True

    def _advance_city_kill_quests(self, enemy_id):
        """击杀敌人时推进城池动态击杀任务。"""
        for quest_id, progress in list(self.player.active_city_quests.items()):
            quest = self._get_active_city_quest(quest_id)
            if not quest:
                continue
            if quest["target_type"] == "kill" and quest["target_id"] == enemy_id:
                progress += 1
                self.player.active_city_quests[quest_id] = progress
                self.notify(f"城池任务进度：{quest['name']} ({progress}/{quest['count']})")
                if progress >= quest["count"]:
                    self.complete_city_quest(quest_id)

    def _advance_city_collect_quests(self, item_id):
        """获得物品时推进城池动态收集任务。"""
        for quest_id in list(self.player.active_city_quests.keys()):
            quest = self._get_active_city_quest(quest_id)
            if not quest:
                continue
            if quest["target_type"] == "collect" and quest["target_id"] == item_id:
                have = self.player.count_item(item_id)
                progress = min(have, quest["count"])
                self.player.active_city_quests[quest_id] = progress
                self.notify(f"城池任务进度：{quest['name']} ({progress}/{quest['count']})")
                if progress >= quest["count"]:
                    self.complete_city_quest(quest_id)

    def _get_active_city_quest(self, quest_id):
        """根据任务 ID 从任务池中查找任务定义。"""
        for q in self.player.city_quest_pool:
            if q["id"] == quest_id:
                return q
        # 已接取但不在当前池中的任务，可能来自旧城池；从所有可能的池中查找
        for q in self.player.city_quest_pool:
            if q["id"] == quest_id:
                return q
        return None

    def complete_city_quest(self, quest_id):
        """完成城池动态任务并发放奖励。"""
        quest = self._get_active_city_quest(quest_id)
        if not quest:
            return False
        if quest_id not in self.player.active_city_quests:
            return False

        reward = quest.get("reward", {})
        qi = int(reward.get("qi", 0) * self._realm_qi_scale())
        stones = reward.get("spirit_stone", 0)

        self.player.qi += qi
        for _ in range(stones):
            item = self.item_library.create("spirit_stone")
            self.player.add_item(item)

        # 清除任务
        del self.player.active_city_quests[quest_id]
        # 从任务池中移除，避免重复接取
        self.player.city_quest_pool = [
            q for q in self.player.city_quest_pool if q["id"] != quest_id
        ]

        # 增加城池声望
        city_id = quest.get("city_id")
        if city_id:
            rep_gain = 10 + quest.get("count", 1)
            self.building_manager.gain_city_reputation(city_id, rep_gain)
            self.notify(
                f"城池任务完成！{quest['name']} 奖励：修为 +{qi}，灵石 +{stones}，"
                f"{self.building_manager.get_reputation_level(city_id)}声望 +{rep_gain}。"
            )
        else:
            self.notify(
                f"城池任务完成！{quest['name']} 奖励：修为 +{qi}，灵石 +{stones}。"
            )
        self._auto_save()
        return True

    def donate_to_city(self, item_id, count=1, city_id=None):
        """向当前城池捐赠物品换取城池声望。"""
        if city_id is None:
            city_id = self.player.location_id
        # 校验物品存在性与数量
        item = self.item_library.get(item_id)
        if not item:
            self.notify(f"未知物品：{item_id}")
            return False, 0
        if self.player.count_item(item_id) < count:
            self.notify(f"背包中【{item.name}】数量不足 {count} 个。")
            return False, 0
        if count <= 0:
            self.notify("捐赠数量必须大于 0。")
            return False, 0
        # 扣除物品并计算声望：每 10 价值 = 1 声望，至少 1 点
        self.player.consume_items(item_id, count)
        rep_gain = max(1, item.value * count // 10)
        self.building_manager.gain_city_reputation(city_id, rep_gain)
        self.notify(
            f"你向城池捐赠了【{item.name}】x{count}，"
            f"{self.building_manager.get_reputation_level(city_id)}声望 +{rep_gain}。"
        )
        self._auto_save()
        return True, rep_gain

    def gain_city_reputation_from_defense(self, enemy, city_id=None):
        """击败来袭妖兽后获得城池声望。"""
        if city_id is None:
            city_id = self.player.location_id
        if not enemy:
            return 0
        # 声望收益基于敌人强度：攻击与生命越高，声望越多
        rep_gain = max(1, enemy.attack // 5 + enemy.max_hp // 100)
        self.building_manager.gain_city_reputation(city_id, rep_gain)
        self.notify(
            f"你成功击退来袭的【{enemy.name}】，"
            f"{self.building_manager.get_reputation_level(city_id)}声望 +{rep_gain}。"
        )
        self._auto_save()
        return rep_gain

    # ==================== 万兽园系统 ====================

    def _get_today_str(self):
        """返回当前世界日期的字符串标识，用于每日奖励刷新。"""
        return f"{self.world.year}-{self.world.month}-{self.world.day}"

    def _reset_arena_daily_if_needed(self):
        """若跨天，则重置演武场每日领奖状态与挑战次数。"""
        today = self._get_today_str()
        if self.player.arena_last_date != today:
            self.player.arena_daily_claimed = False
            self.player.arena_daily_challenges = 0
            self.player.arena_last_date = today

    def arena_fight_finished(self, victory):
        """演武场切磋结束后更新连胜状态。"""
        self._reset_arena_daily_if_needed()
        if victory:
            self.player.arena_streak += 1
            if self.player.arena_streak > self.player.arena_best_streak:
                self.player.arena_best_streak = self.player.arena_streak
            self.notify(
                f"演武场连胜达到 {self.player.arena_streak} 场！"
                f"最高连胜：{self.player.arena_best_streak} 场。"
            )
        else:
            if self.player.arena_streak > 0:
                self.notify(f"连胜终结！此前连胜 {self.player.arena_streak} 场。")
            self.player.arena_streak = 0
        self._auto_save()

    def claim_arena_daily_reward(self):
        """领取演武场每日奖励，奖励随连胜提升。"""
        self._reset_arena_daily_if_needed()
        if self.player.arena_daily_claimed:
            self.notify("今日演武场奖励已领取，明日再来吧。")
            return False

        # 基础奖励
        base_qi = 30
        base_stone = 20
        # 连胜加成：每连胜 1 场增加 5% 修为奖励，最多 100%
        streak_bonus = min(1.0, self.player.arena_streak * 0.05)
        # 演武场建筑等级加成
        arena_effects = self.building_manager.get_current_effects("arena")
        daily_bonus = arena_effects.get("daily_reward_bonus", 0.0)
        streak_building_bonus = arena_effects.get("streak_reward_bonus", 0.0)
        qi_reward = int(base_qi * (1 + streak_bonus + daily_bonus + streak_building_bonus * self.player.arena_streak))
        stone_reward = int(base_stone * (1 + streak_bonus * 0.5 + daily_bonus))

        self.player.qi += qi_reward
        # 发放灵石奖励
        for _ in range(stone_reward):
            item = self.item_library.create("spirit_stone")
            self.player.add_item(item)

        self.player.arena_daily_claimed = True
        self.notify(
            f"领取演武场每日奖励：修为 +{qi_reward}，灵石 +{stone_reward}。"
            f"（当前连胜 {self.player.arena_streak} 场）"
        )
        self._auto_save()
        return True

    # ==================== NPC 与任务系统 ====================

