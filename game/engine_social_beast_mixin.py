# -*- coding: utf-8 -*-
"""GameEngine 社交·灵兽域 Mixin（第九期纯净度修正，2026-09-22）。

论道/双修/收徒/传艺/恩怨、灵兽园捕捉/喂养/训练/派遣、水族商铺。
方法原样迁出：第八期误并入 CityLifeMixin / 第六期误并入 SectMixin 的部分由本文件归位。
切出备份：tools/.purity_fix_backup_20260922.py。
"""
import random

from game.enemy import Enemy


class SocialBeastMixin:
    """依赖宿主 GameEngine 的对应 Manager 实例属性与跨 Mixin 方法。"""

    def debate_with_npc(self, npc_id):
        """与 NPC 论道。"""
        success, message, win = self.social_manager.debate(npc_id)
        self.notify(message)
        if success:
            self._auto_save()
        return success, win

    def dual_cultivate_with_npc(self, npc_id):
        """与 NPC 双修。"""
        success, message = self.social_manager.dual_cultivate(npc_id)
        self.notify(message)
        if success:
            self._auto_save()
        return success, message

    def accept_npc_as_disciple(self, npc_id):
        """收 NPC 为徒。"""
        success, message = self.social_manager.accept_disciple(npc_id)
        self.notify(message)
        if success:
            self._auto_save()
        return success, message

    def teach_disciple(self, npc_id):
        """传授徒弟技艺。"""
        success, message = self.social_manager.teach_disciple(npc_id)
        self.notify(message)
        if success:
            self._auto_save()
        return success, message

    def add_grudge_with_npc(self, npc_id, reason=""):
        """与 NPC 结怨。"""
        success, message = self.social_manager.add_grudge(npc_id, reason)
        self.notify(message)
        if success:
            self._auto_save()
        return success, message

    def resolve_grudge_with_npc(self, npc_id):
        """与 NPC 化解恩怨。"""
        success, message = self.social_manager.resolve_grudge(npc_id)
        self.notify(message)
        if success:
            self._auto_save()
        return success, message

    def visit_beast_park(self):
        """万兽园：售卖妖兽材料与灵兽契约。"""
        from game.npc import NPC
        shop_items = ["demon_core", "beast_blood", "beast_hide", "beast_tendon"]
        # 随机补充一种灵兽契约（若配置存在）
        if self.item_library.get("beast_contract"):
            shop_items.append("beast_contract")
        available = random.sample(shop_items, min(len(shop_items), random.randint(3, 5)))
        merchant = NPC(
            npc_id="beast_park_keeper",
            name="万兽园管事",
            location=self.player.location_id,
            description="万兽园管事，对各种妖兽了如指掌。",
            dialog="道友可是来挑选灵兽材料的？",
            quests=[],
            shop_items=available,
            buy_multiplier=1.1,
            sell_multiplier=0.7,
        )
        return merchant

    def get_capturable_enemies(self):
        """获取当前地点可捕捉的妖兽列表（取地点 enemies 配置）。"""
        location = self.get_current_location()
        enemy_ids = location.get("enemies", []) if location else []
        result = []
        for eid in enemy_ids:
            data = self.enemy_library.get(eid)
            if data:
                result.append({
                    "id": eid,
                    "name": data.get("name", eid),
                    "difficulty": data.get("realm_id", "未知"),
                })
        return result

    def start_beast_capture(self, enemy_id):
        """开始捕捉指定妖兽，进入战斗。"""
        enemy_data = self.enemy_library.get(enemy_id)
        if not enemy_data:
            self.notify("该妖兽已逃离万兽园。")
            return None
        enemy = Enemy.from_dict(enemy_data)
        enemy.name = f"野生·{enemy.name}"
        self.notify(f"你悄悄接近一只{enemy.name}，准备尝试收服！")
        return enemy

    def try_capture_beast(self, enemy_id, enemy_name, victory):
        """战斗胜利后尝试捕捉妖兽。"""
        if not victory:
            self.notify("未能击败妖兽，捕捉失败。")
            return False

        # 基础捕捉率 50%，根据当前地点安全等级与妖兽境界微调
        base_rate = 0.5
        location = self.get_current_location()
        safety = location.get("safety_level", 5) if location else 5
        # 安全等级越高（城市越安全），园内妖兽越温顺，捕捉率越高
        rate = min(0.9, base_rate + safety * 0.02)
        # 万兽园建筑等级加成
        beast_effects = self.building_manager.get_current_effects("beast_park")
        rate = min(0.95, rate + beast_effects.get("capture_rate_bonus", 0.0))

        if random.random() < rate:
            # 默认捕捉为战斗型灵兽
            self.personal_beast_manager.capture(enemy_id, enemy_name, beast_type="combat")
            self.notify(f"捕捉成功！你收服了【{enemy_name}】。")
            self._auto_save()
            return True
        else:
            self.notify("妖兽挣脱了束缚，捕捉失败。")
            return False

    def feed_beast(self, index, food_item_id="spirit_herb"):
        """喂养指定灵兽。"""
        ok, msg = self.personal_beast_manager.feed(index, food_item_id)
        self.notify(msg)
        if ok:
            self._auto_save()
        return ok

    def train_beast(self, index):
        """训练指定灵兽，消耗 1 个月时间。"""
        ok, msg = self.personal_beast_manager.train(index)
        self.notify(msg)
        if ok:
            # 训练消耗 1 个月
            self.world.advance(1)
            self.player.add_age_months(1)
            self._check_sect_daily_reset()
            self._auto_save()
        return ok

    def dispatch_beast(self, index, months=1):
        """派遣灵兽外出历练，建筑等级可减少历练时间。"""
        # 应用万兽园建筑等级的时间缩减
        beast_effects = self.building_manager.get_current_effects("beast_park")
        reduction = beast_effects.get("dispatch_time_reduction", 0.0)
        actual_months = max(1, int(months * (1 - reduction)))
        ok, msg = self.personal_beast_manager.dispatch(index, self.world, actual_months)
        self.notify(msg)
        if ok:
            self._auto_save()
        return ok

    def visit_aquatic_shop(self):
        """水族商行：根据建筑等级解锁商品与折扣。"""
        from game.npc import NPC
        effects = self.building_manager.get_current_effects("aquatic_shop")
        unlock_items = effects.get("unlock_items", ["water_essence", "healing_pill", "spirit_stone", "pearl"])
        # 过滤掉不存在的物品
        shop_items = [item_id for item_id in unlock_items if self.item_library.get(item_id)]
        available = random.sample(shop_items, min(len(shop_items), random.randint(3, 5)))
        price_reduction = effects.get("price_reduction", 0.0)
        merchant = NPC(
            npc_id="aquatic_shop_keeper",
            name="水族商行掌柜",
            location=self.player.location_id,
            description="玄水城特产水族商行掌柜，手中多有水系奇珍。",
            dialog="道友需要水系材料还是疗伤丹药？",
            quests=[],
            shop_items=available,
            buy_multiplier=1.0 - price_reduction,
            sell_multiplier=0.6,
        )
        return merchant

    # ==================== 战斗系统 ====================

