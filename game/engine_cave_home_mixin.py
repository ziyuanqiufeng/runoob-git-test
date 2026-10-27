# -*- coding: utf-8 -*-
"""GameEngine 洞府·居所·轮回域 Mixin（第九期纯净度修正，2026-09-22）。

洞府租用/闭关/信息、野居所占/维护/袭击、轮回转世。
方法原样迁出：第八期误并入 CityLifeMixin / 第六期误并入 SectMixin 的部分由本文件归位。
切出备份：tools/.purity_fix_backup_20260922.py。
"""
import json


class CaveHomeMixin:
    """依赖宿主 GameEngine 的对应 Manager 实例属性与跨 Mixin 方法。"""

    def _tick_caves(self):
        """每月推进洞府租期与闭关修炼。"""
        # 若玩家处于闭关中，优先推进闭关收益
        if self.cave_manager.is_in_closed_door():
            qi_gain = self.cave_manager.tick_closed_door()
            if qi_gain > 0:
                self.notify(f"[cyan]闭关一月，获得修为 {qi_gain} 点。")
        # 推进所有洞府租期
        expired = self.cave_manager.tick_monthly()
        for name in expired:
            self.notify(f"【{name}】租期已到期。")

    def rent_cave(self, cave_id, months):
        """
        租赁城中洞府。

        返回 (success, message)。
        """
        ok, msg = self.cave_manager.rent_cave(cave_id, months)
        if ok:
            self._auto_save()
        return ok, msg

    def start_closed_door_cultivation(self, cave_id, months):
        """
        在租赁洞府中开始闭关修炼。

        返回 (success, message, expected_qi_gain)。
        """
        ok, msg, expected = self.cave_manager.start_closed_door(cave_id, months)
        if ok:
            self.notify(msg)
            self._auto_save()
        return ok, msg, expected

    def get_cave_info(self, location_id=None):
        """获取指定地点洞府信息，供 UI 展示。"""
        location_id = location_id or self.player.location_id
        caves = self.cave_manager.get_available_caves(location_id)
        result = []
        for cave in caves:
            cave_id = cave["id"]
            lease = self.cave_manager.get_current_lease(cave_id)
            result.append({
                "id": cave_id,
                "name": cave["name"],
                "description": cave["description"],
                "rent_per_month": cave.get("rent_per_month", 0),
                "max_lease_months": cave.get("max_lease_months", 12),
                "remaining_months": lease["remaining_months"] if lease else 0,
                "effects": cave.get("effects", {}),
            })
        return result

    # ==================== 私人洞府占领 ====================

    def can_occupy_wild_residence(self, location_id):
        """检查是否可以在指定地点占领野外洞府。"""
        return self.residence_manager.can_occupy(location_id)

    def start_residence_occupation(self, location_id):
        """发起野外洞府占领，返回 (success, message, guard_enemy_id)。

        占领成功发起后会在引擎中记录 pending_residence_occupation_location_id，
        便于 UI 层在战斗结束后调用 finish_residence_occupation 完成所有权转移。
        """
        # 调用 ResidenceManager 检查占领条件并返回守卫敌人 ID
        success, message, guard_enemy_id = self.residence_manager.occupy(location_id)
        if success:
            # 标记当前有待处理的占领战斗，记录目标地点 ID
            self.pending_residence_occupation_location_id = location_id
        return success, message, guard_enemy_id

    def finish_residence_occupation(self, location_id, win):
        """完成占领战斗，成功则获得洞府所有权。"""
        # 无论胜负，先清除占领战斗的待处理标记，避免重复结算
        if hasattr(self, "pending_residence_occupation_location_id"):
            del self.pending_residence_occupation_location_id
        ok, msg = self.residence_manager.finish_occupation(location_id, win)
        if ok:
            self.notify(msg)
            self._auto_save()
        return ok, msg

    def pay_residence_maintenance(self):
        """手动缴纳洞府维护费。"""
        ok, msg = self.residence_manager.pay_maintenance()
        if ok:
            self.notify(msg)
            self._auto_save()
        return ok, msg

    def resolve_residence_raid(self, win):
        """结算洞府袭击战斗结果。"""
        if not getattr(self, "pending_residence_raid", False):
            return
        self.pending_residence_raid = False
        ok, msg = self.residence_manager.resolve_raid(win)
        self.notify(msg)
        self._auto_save()

    def get_residence_info(self):
        """获取当前洞府状态摘要，供 UI 展示。"""
        if not self.player.residence:
            return None
        return {
            "id": self.player.residence["id"],
            "maintenance_cost": self.residence_manager.get_maintenance_cost(),
            "maintenance_debt": self.player.residence.get("maintenance_debt", 0),
            "energy": self.residence_manager.get_formation_energy(),
            "max_energy": self.residence_manager.get_max_formation_energy(),
            "defense_rate": self.residence_manager.get_defense_rate(),
            "spirit_vein_quality": self.residence_manager.get_spirit_vein_quality(),
        }

    # ==================== 社交系统接口 ====================

    def compute_reincarnation_options(self):
        """
        计算转世时可用的继承选项与点数。

        返回字典，包含 points、karma_category、options 等。
        """
        return self.reincarnation_manager.compute_available_options()

    def start_reincarnation(self, selected_option_ids):
        """转世重修：应用继承选择，生成新周目 Player 并注入前世羁绊。

        - new_player.past_bond 已由转世结算写入（道侣优先，其次好感最高 NPC）；
        - 向 NPC 库运行时注入"转世重逢"NPC（前世羁绊者转世现身于新周目）；
        - 输出宿慧叙事并记入年表。
        返回 (new_player, summary)。
        """
        from game.npc import NPC
        new_player, summary = self.apply_reincarnation(selected_option_ids)
        summary["past_bond"] = getattr(new_player, "past_bond", None)

        bond = getattr(new_player, "past_bond", None)
        if bond:
            bond_type_cn = "道侣" if bond["bond_type"] == "dao_lv" else "挚友"
            reborn_id = f"reborn_{bond['npc_id']}"
            if reborn_id not in self.npc_library.npcs:
                reborn_npc = NPC(
                    npc_id=reborn_id,
                    name=bond["name"],
                    location=new_player.location_id,
                    description=(
                        f"一位眉眼间似曾相识的修士。恍惚之间，你想起前世与"
                        f"{bond['name']}（{bond_type_cn}，情分 {bond['intimacy']}）"
                        f"的种种过往——如今TA转世重临，却已不记得你。"
                    ),
                    dialog=[
                        f"（{bond['name']}望着你，眼中闪过一丝迷惘）我们……是否在哪里见过？",
                        "总觉得你的气息莫名熟悉，像是很久很久以前的旧梦。",
                    ],
                    quests=[],
                    can_dual_cultivate=(bond["bond_type"] == "dao_lv"),
                )
                reborn_npc.past_life_bond = bond  # 供对话/AI 剧情引用前世信息
                self.npc_library.npcs[reborn_id] = reborn_npc
                # 前世羁绊写入新周目的 NPC 记忆（宿慧的具象化）
                new_player.record_npc_moment(
                    reborn_id,
                    f"前世：TA曾是我的{bond_type_cn}，情分深笃（亲密度 "
                    f"{bond['intimacy']}），一世纠葛未竟。",
                )
            self.notify(
                f"[purple]【宿慧】一缕前尘掠过心间：前世{bond_type_cn}"
                f"{bond['name']}的情分犹未了断——TA已转世重临人间，"
                f"或就在这方天地之间。"
            )
            # 年表记录写 new_player（chronicle_manager 仍绑定旧 player，
            # 直接 append 确保条目随新世存档延续）
            new_player.chronicle.append({
                "year": self.world.year, "month": self.world.month,
                "age": new_player.age,
                "text": (
                    f"第 {new_player.reincarnation_count} 世启程：前世"
                    f"{bond_type_cn}{bond['name']}转世重逢的宿慧苏醒"
                ),
                "category": "reincarnation",
            })
        else:
            self.notify(
                f"[purple]【宿慧】前尘如烟，你于轮回中保住一缕真灵，"
                f"重踏修仙之路。"
            )
            new_player.chronicle.append({
                "year": self.world.year, "month": self.world.month,
                "age": new_player.age,
                "text": f"第 {new_player.reincarnation_count} 世启程（无前世羁绊）",
                "category": "reincarnation",
            })
        return new_player, summary

    _MODE_OPENINGS = {
        "seize_rebirth": (
            "【夺舍】",
            "你在别人的躯壳中醒来。经脉滞涩、旧忆纷扰——但这一世，"
            "由你做主。夺舍者的路，注定无人同行。",
        ),
        "heaven_cycle": (
            "【轮回】",
            "飞升的刹那，天道却将你送回了起点。前世的功法感悟历历在目，"
            "而天道注视，也如影随形——再来一世，你仍要问那长生。",
        ),
        "mortal_challenge": (
            "【凡人】",
            "测灵石黯淡无光——你天生无灵根。但修仙界从不缺逆天改命的传说，"
            "以肉身硬撼天地，以凡人之躯比肩神明，此生便做这个传说。",
        ),
        "demonic_lone": (
            "【魔道】",
            "魔气入体，杀伐果断——你选择了这条无人祝福的路。"
            "正道的刀悬在头顶，而力量是唯一的真理。",
        ),
    }

    def start_npc_combat_quest(self, npc_id):
        """发动战斗型 NPC 委托（护法/复仇）：创建敌人并开战。

        返回 (ok, message)；胜利后由战斗钩子调用 npc_quest_manager 结算。
        """
        enemy_id = self.npc_quest_manager.get_combat_enemy_id(npc_id)
        if not enemy_id:
            return False, "这不是战斗委托。"
        data = self.enemy_library.get(enemy_id)
        if not data:
            return False, "敌人数据缺失。"
        from game.enemy import Enemy
        enemy = Enemy.from_dict(data)
        self.pending_npc_quest = npc_id
        self.start_combat(enemy)
        return True, f"【{getattr(enemy, 'name', enemy_id)}】现身了！"

    def award_lantern_reward(self, correct_count, total):
        """灯会奖励发放（节日灯谜）。返回奖励描述。

        correct_count 题答对：每题 reward_per_correct 灵石；
        全对额外心境 +perfect_mental_bonus。
        """
        import os
        cfg = {"reward_per_correct": 30, "perfect_mental_bonus": 5}
        try:
            import json as _json
            path = os.path.join("config", "lantern_riddles.json")
            with open(path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            cfg["reward_per_correct"] = data.get(
                "reward_per_correct", cfg["reward_per_correct"])
            cfg["perfect_mental_bonus"] = data.get(
                "perfect_mental_bonus", cfg["perfect_mental_bonus"])
        except (OSError, ValueError):
            pass
        stone = int(correct_count) * int(cfg["reward_per_correct"])
        if stone > 0:
            item = self.item_library.create("spirit_stone")
            for _ in range(stone):
                self.player.add_item(item)
        lines = [f"灵石 ×{stone}"]
        if total > 0 and correct_count >= total:
            bonus = int(cfg["perfect_mental_bonus"])
            self.player.mental_state = min(100, self.player.mental_state + bonus)
            lines.append(f"心境 +{bonus}（全对）")
        return "、".join(lines)

    def consume_pending_start_items(self):
        """发放模式开局赠礼（pending_start_items 真实到手）。

        返回发放的物品名列表（空列表表示无赠礼）。
        """
        pending = list(getattr(self.player, "pending_start_items", []) or [])
        if not pending:
            return []
        names = []
        for item_id in pending:
            try:
                item = self.item_library.create(item_id)
            except Exception:
                continue
            if item is None:      # 无效 id：create 返回 None
                continue
            self.player.add_item(item)
            names.append(item.name)
        self.player.pending_start_items = []
        if names:
            self.notify(f"[cyan]【开局赠礼】{('、'.join(names))} 已入行囊。")
        return names

    def apply_hostile_factions(self):
        """将模式的敌对阵营落到 NPC 关系上（正道皆敌等）。

        当前实现：对 faction_affinity 中正道倾向为正的 NPC，
        初始好感降至 -30（敌视）。返回受影响 NPC 数量。
        """
        hostile = getattr(self.player, "hostile_factions", []) or []
        if not hostile or "righteous" not in hostile:
            return 0
        count = 0
        for npc_id, npc in (self.npc_library.npcs or {}).items():
            affinity = getattr(npc, "faction_affinity", {}) or {}
            if affinity.get("righteous", 0) > 0:
                self.player.npc_relationships[npc_id] = min(
                    -30, self.player.npc_relationships.get(npc_id, 0))
                count += 1
        if count:
            self.notify(
                f"[red]【魔道】正道中人视你为魔头——{count} 位正道修士与你结下梁子。"
            )
        return count

    def trigger_mode_opening(self):
        """多周目模式开场演出：新档首次进入时触发（一次性）。

        standard 模式无演出（也置标记，避免后续误触发）。
        返回 True 表示本次触发了演出。
        """
        p = self.player
        if getattr(p, "mode_opening_done", False):
            return False
        p.mode_opening_done = True
        mode = getattr(p, "game_mode", "standard")
        opening = self._MODE_OPENINGS.get(mode)
        if not opening:
            return False
        title, text = opening
        self.notify(f"[purple]{title}{text}")
        self.chronicle_manager.record(
            f"以此世之道启程：{title.strip('【】')}之路",
            category="mode",
        )
        return True

    def trigger_past_life_reunion(self, npc_id):
        """转世重逢初见演出：首次与转世 NPC 对话时触发（一次性）。

        - 前世情分转化为今生的初始好感加成（道侣 +15 / 挚友 +10）；
        - 写入"重逢"共同经历记忆；
        - 以 npc_memory["first_met"] 标记防重复触发。
        返回 True 表示本次触发了初见演出。
        """
        bond = getattr(self.player, "past_bond", None)
        if not bond:
            return False
        expected_reborn_id = f"reborn_{bond['npc_id']}"
        if npc_id != expected_reborn_id:
            return False
        memory = self.player.get_npc_memory(npc_id)
        if memory.get("first_met"):
            return False
        memory["first_met"] = True

        bonus = 15 if bond["bond_type"] == "dao_lv" else 10
        bond_type_cn = "道侣" if bond["bond_type"] == "dao_lv" else "挚友"
        current = self.player.npc_relationships.get(npc_id, 0)
        self.player.npc_relationships[npc_id] = min(100, current + bonus)

        year = self.world.year
        self.player.record_npc_moment(
            npc_id, f"第{year}年：重逢——前世{bond_type_cn}情分未了，TA似有所感"
        )
        # 重逢演出面板数据（UI 经 __PAST_LIFE_REUNION__ 弹面板；
        # 引擎直跑/测试无监听则无副作用）
        try:
            report = {
                "bond_name": bond["name"],
                "bond_type": bond_type_cn,
                "intimacy": bond["intimacy"],
                "bonus": bonus,
                "year": year,
                "reborn_id": npc_id,
            }
            self.notify(
                "__PAST_LIFE_REUNION__:"
                + json.dumps(report, ensure_ascii=False)
            )
        except Exception:
            pass  # 演出通知失败不影响重逢结算本身
        self.notify(
            f"[purple]【重逢】四目相对的刹那，前尘往事如潮涌来——"
            f"TA正是你前世的{bond_type_cn}【{bond['name']}】！"
            f"虽然TA已不记得前世，但那份情分化作了此刻的默契"
            f"（好感 +{bonus}）。"
        )
        self.chronicle_manager.record(
            f"与前世{bond_type_cn}【{bond['name']}】的转世之身重逢",
            category="reincarnation",
        )
        return True

    def apply_reincarnation(self, selected_option_ids):
        """
        应用玩家选择的继承项，生成新一世 Player。

        返回新 Player 实例与转世摘要信息。
        """
        from game.player import Player
        new_data = self.reincarnation_manager.apply_inheritance(selected_option_ids)
        new_player = self.reincarnation_manager.create_new_player(new_data, Player)
        summary = {
            "reincarnation_count": new_player.reincarnation_count,
            "karma": new_player.karma,
            "new_talents": new_data["new_talents"],
            "attribute_bonuses": new_data["attribute_bonuses"],
            "starting_items": new_data["starting_items"],
            "relationship_bonuses": new_data["relationship_bonuses"],
            "relic_chain_bonuses": new_data["relic_chain_bonuses"],
            "retain_roots": new_data.get("retain_roots", False),
            "past_bond": new_data.get("past_bond"),
            "negative_event": (
                new_data["negative_event"]["name"]
                if new_data["negative_event"]
                else None
            ),
        }
        return new_player, summary

