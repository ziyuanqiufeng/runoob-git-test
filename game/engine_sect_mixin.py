# -*- coding: utf-8 -*-
"""GameEngine 宗门域 Mixin（第六期拆分，2026-09-20）。

从 engine.py 迁入 34 个宗门系统方法：加入/职位/大比/设施/任务/商店/传承/
秘境/追随者/外交/悬赏/宣战/灵兽/同盟/洞府闭关/护山大阵/追杀/通缉衰减等。
由剪切脚本从 engine.py 原样迁出（tools/.sect_cut_backup_20260920.py 为切出备份）。
"""
import random

from game.enemy import Enemy


class SectMixin:
    """宗门系统方法集：依赖宿主 GameEngine 的 sect_manager / sect_library /
    sect_task_library / bounty_board_manager / world_boss_manager 等实例属性。"""

    def get_sect_price_multiplier(self, npc):
        """
        根据玩家宗门与 NPC 所属宗门的关系，计算交易价格修正。
        优先读取 NPC 的 sect_id，未配置则按所在 location 推断。
        无宗门或中立关系返回 (1.0, 1.0)。
        返回 (buy_multiplier, sell_multiplier)。
        """
        if not npc:
            return 1.0, 1.0

        target_sect = None
        # 显式宗门归属优先
        sect_id = getattr(npc, "sect_id", None)
        if sect_id:
            target_sect = self.sect_library.get(sect_id)
        # 兼容旧配置：按 location 推断
        if not target_sect and getattr(npc, "location", None):
            target_sect = self.sect_library.get_by_location(npc.location)
        if not target_sect:
            return 1.0, 1.0

        status = self.sect_manager.get_relation_status(target_sect.id)

        # 同宗门：保持原价
        if self.player.sect_id == target_sect.id:
            return 1.0, 1.0

        if status == "friendly":
            # 友好宗门：购买打折、出售提价
            return target_sect.friendly_discount, 1.2
        if status == "hostile":
            # 敌对宗门：购买加价、出售压价
            return 1.5, 0.5

        return 1.0, 1.0

    def _check_sect_daily_reset(self):
        """
        检查是否需要重置宗门每日任务计数。
        游戏内每月 1 号重置。
        """
        py = self.player
        wy, wm = self.world.year, self.world.month
        # 首次进入或跨月时重置
        if py.sect_id and (
            wy > py.sect_last_reset_year
            or (wy == py.sect_last_reset_year and wm > py.sect_last_reset_month)
        ):
            py.sect_tasks_today = 0
            py.sect_last_reset_year = wy
            py.sect_last_reset_month = wm
            # 重置本月祖师堂参悟次数
            self.sect_manager.reset_ancestral_hall_monthly_count()
            # 每月结算一次捐献排行榜奖励
            reward_ok, reward_msg = self.sect_manager.check_monthly_donation_rewards(wy, wm)
            if reward_msg:
                self.notify(reward_msg)
            # 推进追随者任务倒计时
            follower_messages = self.sect_manager.tick_followers(wy, wm)
            for msg in follower_messages:
                self.notify(msg)
            # 推进宗门外交任务倒计时
            diplomatic_messages = self.sect_manager.tick_diplomatic_mission(wy, wm)
            for msg in diplomatic_messages:
                self.notify(msg)
            # 推进宗门气运事件
            fortune_messages = self.sect_manager.tick_fortune_event(wy, wm)
            for msg in fortune_messages:
                self.notify(msg)
            # 检查同盟条约是否到期
            alliance_messages = self.sect_manager.tick_alliances(wy, wm)
            for msg in alliance_messages:
                self.notify(msg)
            # 推进护山大阵维护
            formation_messages = self.sect_manager.tick_formation(1)
            for msg in formation_messages:
                self.notify(msg)

    def sect_join(self, sect_id):
        """玩家加入宗门。"""
        ok, msg = self.sect_manager.join_sect(sect_id)
        self.notify(msg)
        if ok:
            sect = self.sect_library.get(sect_id)
            sect_name = sect.name if sect else sect_id
            self.chronicle_manager.record(
                f"加入宗门【{sect_name}】", category="sect"
            )
            self._check_main_story()
            self._auto_save()
            self.update_view()
        return ok

    def sect_leave(self):
        """玩家退出宗门，可能触发通缉。"""
        ok, msg = self.sect_manager.leave_sect_with_consequence()
        self.notify(msg)
        if ok:
            sect = self.sect_library.get(self.player.sect_id)
            sect_name = sect.name if sect else "宗门"
            self.chronicle_manager.record(
                f"退出【{sect_name}】", category="sect"
            )
            self._auto_save()
            self.update_view()
        return ok

    def sect_promote(self):
        """玩家申请职位晋升。"""
        ok, msg = self.sect_manager.promote()
        self.notify(msg)
        if ok:
            # 触发宗门职位成就钩子
            self._on_sect_rank_change(self.player.sect_rank)
            self._auto_save()
            self.update_view()
        return ok

    def sect_start_tournament(self):
        """
        检查并启动宗门大比。
        返回 (True, opponents) 表示可参加，opponents 为生成的对手列表；
        返回 (False, msg) 表示条件不满足。
        """
        ok, msg = self.sect_manager.can_start_tournament()
        if not ok:
            return False, msg
        opponents = self.sect_manager.get_tournament_opponents()
        return True, opponents

    def sect_complete_tournament(self, wins):
        """宗门大比结束后发放奖励。"""
        ok, msg = self.sect_manager.complete_tournament(wins)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def use_facility(self, facility_id):
        """使用宗门设施。"""
        ok, msg = self.sect_manager.use_facility(facility_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_accept_task(self, task_id):
        """接取宗门任务。"""
        ok, msg = self.sect_manager.accept_task(task_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_complete_active_task(self):
        """完成当前宗门任务。"""
        ok, msg = self.sect_manager.complete_task()
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_buy_item(self, item_id):
        """用贡献在宗门商店兑换物品。"""
        ok, msg = self.sect_manager.buy_shop_item(item_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_learn_skill(self, skill_id):
        """用贡献在藏经阁学习功法。"""
        ok, msg = self.sect_manager.learn_scripture_skill(skill_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_donate_item(self, item_id, count=1):
        """向宗门捐献物品换取贡献（物品会进入宗门仓库并参与排行榜）。"""
        ok, msg = self.sect_manager.donate_item(item_id, count)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_enter_secret_realm(self, realm_id):
        """进入宗门秘境/禁地，生成守关敌人并触发战斗。"""
        enemy, msg = self.sect_manager.enter_secret_realm(realm_id)
        if enemy is None:
            self.notify(msg)
            return False

        self.pending_secret_realm_id = realm_id
        self.notify(f"【宗门秘境】{msg}")
        self.start_combat(enemy)
        return True

    def sect_finish_secret_realm(self, result):
        """秘境战斗结束后结算奖励与冷却。"""
        realm_id = getattr(self, "pending_secret_realm_id", None)
        if not realm_id:
            return

        win = result == "win"
        ok, msg = self.sect_manager.finish_secret_realm(realm_id, win)
        if ok:
            self.notify(f"【宗门秘境】{msg}")
        self.pending_secret_realm_id = None
        self._auto_save()
        self.update_view()

    def sect_recruit_follower(self, follower_id):
        """招募宗门追随者。"""
        ok, msg = self.sect_manager.recruit_follower(follower_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_dispatch_follower(self, follower_id):
        """派遣追随者外出执行任务。"""
        ok, msg = self.sect_manager.dispatch_follower(follower_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_accept_diplomatic_mission(self, mission_id, target_sect_id):
        """接取宗门外交任务。"""
        ok, msg = self.sect_manager.accept_diplomatic_mission(mission_id, target_sect_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_cancel_diplomatic_mission(self):
        """取消当前宗门外交任务。"""
        ok, msg = self.sect_manager.cancel_diplomatic_mission()
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_accept_bounty(self, bounty_id):
        """接取宗门悬赏任务。"""
        ok, msg = self.sect_manager.accept_bounty(bounty_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_update_bounty_after_combat(self, enemy_id):
        """战斗胜利后更新悬赏进度并调整阵营值，达到目标时自动完成并发放奖励。"""
        # 根据敌人类型调整阵营值
        enemy = getattr(self, "current_enemy", None)
        killed_righteous = False
        if enemy:
            # 敌人 ID 含 righteous 视为正道弟子，击杀后增加魔道值
            if "righteous" in enemy.id:
                killed_righteous = True
        self.sect_manager.apply_camp_rewards(enemy_id=enemy_id, killed_righteous=killed_righteous)
        result = self.sect_manager.update_bounty_progress(enemy_id)
        if result:
            ok, msg = result
            self.notify(f"【宗门悬赏】{msg}")
            if ok:
                self._auto_save()
                self.update_view()
        return result

    def sect_start_war(self, target_sect_id):
        """对目标宗门发动宗门战。"""
        ok, msg = self.sect_manager.start_war(target_sect_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        self._check_death()
        return ok


    def sect_learn_inheritance(self, inheritance_id):
        """在祖师堂参悟传承，应用永久属性或技能奖励。"""
        ok, msg = self.sect_manager.learn_inheritance(inheritance_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_adopt_beast(self, beast_id):
        """在宗门灵兽园领养灵兽。"""
        ok, msg = self.sect_manager.adopt_beast(beast_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_release_beast(self, beast_id):
        """放生玩家拥有的灵兽。"""
        ok, msg = self.sect_manager.release_beast(beast_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_form_alliance(self, target_sect_id):
        """与目标宗门签订攻守同盟。"""
        ok, msg = self.sect_manager.form_alliance(target_sect_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_break_alliance(self, target_sect_id):
        """解除与目标宗门的同盟关系。"""
        ok, msg = self.sect_manager.break_alliance(target_sect_id)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok
    def sect_cave_seclusion(self, months=12):
        """在真传洞府闭关修炼。"""
        ok, msg = self.sect_manager.cave_seclusion(months)
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_upgrade_cave(self):
        """升级宗门洞府。"""
        ok, msg = self.sect_manager.upgrade_cave()
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_activate_formation(self):
        """激活宗门护山大阵。"""
        ok, msg = self.sect_manager.activate_formation()
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def sect_deactivate_formation(self):
        """关闭宗门护山大阵。"""
        ok, msg = self.sect_manager.deactivate_formation()
        self.notify(msg)
        if ok:
            self._auto_save()
            self.update_view()
        return ok

    def check_sect_hunt(self):
        """
        检查玩家进入宗门领地时是否触发追杀。
        进入对玩家发布追杀令的宗门领地时，高概率遭遇该宗门弟子/长老追杀。
        """
        wanted_sects = self.sect_manager.get_wanted_sects()
        if not wanted_sects:
            return False

        for sect_id in wanted_sects:
            if self.sect_manager.should_hunt_player(sect_id):
                sect = self.sect_library.get(sect_id)
                # 根据玩家境界选择追杀者
                player_order = self._get_realm_order()
                if player_order >= 14:  # 金丹期以上出长老
                    enemy_data = self.enemy_library.get("righteous_elder")
                    hunter_name = f"{sect.name}长老"
                else:
                    enemy_data = self.enemy_library.get("righteous_disciple")
                    hunter_name = f"{sect.name}弟子"

                if enemy_data:
                    enemy = Enemy.from_dict(enemy_data)
                    self.notify(
                        f"[red]你踏入【{sect.name}】领地，{hunter_name}奉命追杀！"
                    )
                    self.start_combat(enemy)
                    return True
        return False

    def provoke_sect_npc(self, npc):
        """
        挑衅敌对宗门 NPC：恶化宗门关系、加入通缉列表，
        并有 50% 概率直接引发一场与该宗门弟子/长老的战斗。
        返回 True 表示已触发战斗，False 表示仅关系恶化。
        """
        if not npc:
            self.notify("未选中目标。")
            return False

        # 定位 NPC 所属宗门：优先 sect_id，其次 location
        sect = None
        sect_id = getattr(npc, "sect_id", None)
        if sect_id:
            sect = self.sect_library.get(sect_id)
        if not sect and getattr(npc, "location", None):
            sect = self.sect_library.get_by_location(npc.location)
        if not sect:
            self.notify("无法确定该 NPC 所属宗门。")
            return False

        # 只有敌对宗门 NPC 才能挑衅
        if self.sect_manager.get_relation_status(sect.id) != "hostile":
            self.notify("对方并非敌对势力，挑衅只会显得无礼。")
            return False

        # 降低宗门关系并加入通缉
        self.sect_manager.adjust_sect_relationship(sect.id, -10)
        self.sect_manager.add_wanted_sect(sect.id)
        self.notify(
            f"你出言挑衅【{sect.name}】的 {npc.name}，双方关系恶化，"
            f"你已被该宗门列入追杀名单！"
        )

        # 50% 概率当场触发战斗
        if random.random() < 0.5:
            player_order = self._get_realm_order()
            if player_order >= 14:  # 金丹期以上遭遇长老
                enemy_data = self.enemy_library.get("righteous_elder")
                hunter_name = f"{sect.name}长老"
            else:
                enemy_data = self.enemy_library.get("righteous_disciple")
                hunter_name = f"{sect.name}弟子"

            if enemy_data:
                enemy = Enemy.from_dict(enemy_data)
                enemy.name = hunter_name
                self.notify(f"[red]{hunter_name} 被你激怒，拔剑相向！")
                self.start_combat(enemy)
                return True

        self.notify(f"{npc.name} 强忍怒火，但已将你的行径上报宗门。")
        return False

    def _check_sect_wanted_decay(self):
        """
        每年年初检查一次通缉状态，随时间降低通缉强度。
        """
        self.sect_manager.update_wanted_status()
