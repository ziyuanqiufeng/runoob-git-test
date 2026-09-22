# -*- coding: utf-8 -*-
"""GameEngine 任务·对话·NPC 关系域 Mixin（第十期拆分收官，2026-09-22）。

从 engine.py 迁入 16 个方法：地点NPC查询/任务接取推进完成放弃/
对话开启状态选项结束/NPC对话ID/NPC选择与拜访记录/关系调整与折扣。
由剪切脚本从 engine.py 原样迁出（tools/.quest_dialogue_cut_backup_20260922.py 为切出备份）。
"""

class QuestDialogueMixin:
    """依赖宿主 GameEngine 的 quest_library / dialogue_manager /
    npc_library / world 等实例属性。"""

    def get_location_npcs(self, include_inactive=False):
        """
        获取当前地点的所有 NPC。
        默认根据当前世界时辰过滤掉正在休息的 NPC；include_inactive=True 则不过滤。
        """
        hour = None if include_inactive else self.world.hour
        return self.npc_library.get_by_location(self.player.location_id, hour=hour)

    def _find_quest_npc(self, quest_id):
        """根据任务 ID 查找关联的 NPC（谁的 quests 列表里有这个任务）。"""
        for npc in self.npc_library.npcs.values():
            if quest_id in npc.quests:
                return npc
        return None

    def accept_quest(self, quest_id):
        """接受一个任务。"""
        if quest_id in self.player.quest_progress or quest_id in self.player.completed_quests:
            return False

        quest = self.quest_library.get(quest_id)
        if not quest:
            return False

        self.player.quest_progress[quest_id] = 0
        self.notify(f"接受任务：【{quest.name}】{quest.description}")
        return True

    def _advance_kill_quests(self, enemy_id):
        """击杀敌人时推进主线任务与城池动态任务。"""
        for quest_id, progress in list(self.player.quest_progress.items()):
            quest = self.quest_library.get(quest_id)
            if quest and quest.target_type == "kill" and quest.target_id == enemy_id:
                self.player.quest_progress[quest_id] = progress + 1
                new_progress = self.player.quest_progress[quest_id]
                self.notify(f"任务进度：{quest.name} ({new_progress}/{quest.count})")
                if new_progress >= quest.count:
                    self.complete_quest(quest_id)
        # 同步推进城池动态击杀任务
        self._advance_city_kill_quests(enemy_id)

    def advance_collect_quest(self, item_id):
        """获得物品时推进主线收集任务与城池动态收集任务。"""
        for quest_id, progress in list(self.player.quest_progress.items()):
            quest = self.quest_library.get(quest_id)
            if quest and quest.target_type == "collect" and quest.target_id == item_id:
                have = self.player.count_item(item_id)
                self.player.quest_progress[quest_id] = min(have, quest.count)
                self.notify(f"任务进度：{quest.name} ({self.player.quest_progress[quest_id]}/{quest.count})")
                if self.player.quest_progress[quest_id] >= quest.count:
                    self.complete_quest(quest_id)
        # 同步推进城池动态收集任务
        self._advance_city_collect_quests(item_id)

    def complete_quest(self, quest_id):
        """完成任务并发放奖励，解锁后续任务和地点。"""
        quest = self.quest_library.get(quest_id)
        if not quest:
            return False

        if quest_id in self.player.completed_quests:
            return False

        # 从进行中的任务移除，加入已完成
        self.player.quest_progress.pop(quest_id, None)
        self.player.completed_quests.append(quest_id)

        # 发放奖励
        reward = quest.reward
        if "qi" in reward:
            self.player.qi += reward["qi"]
        for item_id in reward.get("items", []):
            item = self.item_library.create(item_id)
            self.player.add_item(item)

        messages = [f"任务完成！{quest.name} 奖励：修为 +{reward.get('qi', 0)}，物品 {len(reward.get('items', []))} 件。"]

        # 提升关联 NPC 的好感度（完成任务 +2）
        related_npc = self._find_quest_npc(quest_id)
        if related_npc:
            old_rel = self.player.get_npc_relationship(related_npc.id)
            new_rel = self.player.increase_npc_relationship(related_npc.id, 2)
            if new_rel > old_rel:
                messages.append(
                    f"与 {related_npc.name} 的好感度提升至 {new_rel} 级，交易更优惠了！"
                )

        # 解锁下一个任务（自动接取或仅提示）
        next_quest_id = getattr(quest, "next_quest", None)
        if next_quest_id:
            next_quest = self.quest_library.get(next_quest_id)
            if next_quest:
                # 自动接取下一个任务
                self.player.quest_progress[next_quest_id] = 0
                messages.append(f"新任务解锁：【{next_quest.name}】{next_quest.description}")

        # 解锁地点
        unlocks = getattr(quest, "unlocks", {})
        unlock_location = unlocks.get("location")
        if unlock_location:
            loc = self.world.get_location(unlock_location)
            if loc:
                messages.append(f"新地点解锁：【{loc['name']}】")

        for msg in messages:
            self.notify(msg)

        # 触发完成任务事件钩子
        self._on_complete_quest(quest_id)

        self._auto_save()
        return True

    def abandon_quest(self, quest_id):
        """放弃一个进行中的任务。"""
        if quest_id not in self.player.quest_progress:
            return False

        quest = self.quest_library.get(quest_id)
        self.player.quest_progress.pop(quest_id, None)
        self.notify(f"你已放弃任务：【{quest.name if quest else quest_id}】。")
        return True

    # ==================== 对话系统 ====================

    def start_dialogue(self, dialogue_id, npc_id=None, node_id=None):
        """开始一段分支对话，返回当前对话状态。"""
        self.dialogue_manager.start_dialogue(dialogue_id, npc_id=npc_id, node_id=node_id)
        return self.dialogue_manager.get_current_state()

    def get_dialogue_state(self):
        """获取当前对话状态。"""
        return self.dialogue_manager.get_current_state()

    def choose_dialogue_option(self, option_index):
        """选择当前对话的一个选项，返回 (next_state, logs)。"""
        return self.dialogue_manager.choose_option(option_index)

    def end_dialogue(self):
        """结束当前对话。"""
        self.dialogue_manager.end_dialogue()

    def get_npc_dialogue_id(self, npc):
        """获取 NPC 关联的对话配置 ID。优先使用 dialogue_id，否则返回 None。"""
        return getattr(npc, "dialogue_id", None)

    def record_npc_choice(self, npc_id, choice_key, choice_value=True):
        """记录玩家对某 NPC 的关键选择，供记忆对话与后续剧情使用。"""
        self.player.record_npc_choice(npc_id, choice_key, choice_value)

    def record_npc_visit(self, npc_id):
        """记录玩家访问某 NPC 的时间与次数。"""
        self.player.record_npc_visit(npc_id, self.world)
        self._advance_tutorial("npc")

    def adjust_npc_relationship(self, npc_id, amount=1):
        """
        调整与某 NPC 的好感度，并按其关系网传播影响。

        - 与该 NPC 为友/恋人/师徒关系者，好感同向变化 30%；
        - 与该 NPC 为敌者，好感反向变化 30%。
        返回提升后的主 NPC 好感度值。
        """
        new_val = self.player.increase_npc_relationship(npc_id, amount)
        npc = self.npc_library.get(npc_id)
        if not npc or not npc.npc_relationships:
            return new_val

        propagation = amount * 0.3
        rel_net = npc.npc_relationships
        # 正向关系列表
        positive_keys = ("friends", "lovers", "apprentices")
        for key in positive_keys:
            for related_id in rel_net.get(key, []):
                self.player.increase_npc_relationship(related_id, propagation)
        # master 可能是字符串
        master_id = rel_net.get("master")
        if master_id:
            self.player.increase_npc_relationship(master_id, propagation)
        # 敌对关系反向传播
        for enemy_id in rel_net.get("enemies", []):
            self.player.increase_npc_relationship(enemy_id, -propagation)
        return new_val

    def _get_relationship_discount(self, npc):
        """
        根据好感度计算价格折扣系数。
        返回 (buy_adjust, sell_adjust)，用于乘到原倍率上。
        """
        if not npc:
            return 1.0, 1.0
        rel = self.player.get_npc_relationship(npc.id)
        params = self.economy_config.get_relationship_params()
        buy_per_level = params.get("buy_per_level", 0.02)
        sell_per_level = params.get("sell_per_level", 0.015)
        buy_min = params.get("buy_min", 0.8)
        sell_max = params.get("sell_max", 1.15)
        # 购买：好感越高越便宜
        buy_adjust = max(buy_min, 1.0 - rel * buy_per_level)
        # 出售：好感越高收购价越高
        sell_adjust = min(sell_max, 1.0 + rel * sell_per_level)
        return buy_adjust, sell_adjust

