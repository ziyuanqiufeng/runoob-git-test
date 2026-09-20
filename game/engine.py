import json
import math
import os
import random

from game.enemy import Enemy
from game.skill import Skill
from game.cultivation_path import CultivationPathConfig
from game.sect import SectLibrary, SectTaskLibrary, SectEventLibrary, SectManager
from game.follower import FollowerLibrary
from game.diplomatic_mission import DiplomaticMissionLibrary
from game.mental_state import MentalStateManager
from game.weather import WeatherManager
from game.residence import ResidenceManager
from game.companion import CompanionManager
from game.mind_method import MindMethodManager
from game.divine_art import DivineArtManager
from game.farm import FarmManager
from game.achievement import AchievementManager
from game.difficulty_manager import DifficultyManager
from game.meta_manager import MetaManager
from game.combat_extension import CombatExtensionManager
from game.secret_realm import SecretRealmManager
from game.ruin import RuinManager
from game.world_boss import WorldBossManager
from game.auction_house import AuctionHouseManager
from game.market_npc_manager import MarketNPCManager
from game.stall_manager import StallManager
from game.bounty_board import BountyBoardManager
from game.chronicle import ChronicleManager
from game.side_quest import SideQuestManager
from game.city_quest import CityQuestGenerator
from game.building_manager import BuildingManager
from game.reputation import ReputationManager
from game.personal_beast import PersonalBeastManager
from game.teleport import TeleportManager
from game.travel_cost import TravelCostModel
from game.compendium import CompendiumManager
from game.letter_rumor import LetterRumorManager
from game.arena_ranking_manager import ArenaRankingManager
from game.city_event_manager import CityEventManager
from game.city_policy_manager import CityPolicyManager
from game.cave_manager import CaveManager
from game.reincarnation_manager import ReincarnationManager
from game.equipment_manager import EquipmentManager
from game.alchemy_manager import AlchemyManager
from game.smithy_manager import SmithyManager
from game.social_manager import SocialManager
from game.master_disciple import MasterDiscipleManager
from game.world_event import WorldEventManager
from game.world_state import WorldStateManager
from game.family import FamilyManager
from game.territory_manager import TerritoryManager
from game.heaven_retribution_manager import HeavenRetributionManager
from game.lifespan_manager import LifespanManager
from game.red_dust_manager import RedDustManager
from game.hundred_schools_manager import HundredSchoolsManager
from game.economy import EconomyConfig
from game.treasure_map import TreasureMapManager
from game.spiritual_root import SpiritualRootConfig
from game.dialogue import DialogueLibrary, DialogueManager
from game.portrait_generator import find_best_portrait_resource


# 五行相克关系：金克木、木克土、土克水、水克火、火克金
# 变异灵根克制关系：雷克金、冰克火、风克木
# key 为攻击方属性，value 为被其克制的防御方属性
ELEMENT_COUNTERS = {
    "metal": "wood",    # 金克木
    "wood": "earth",    # 木克土
    "earth": "water",   # 土克水
    "water": "fire",    # 水克火
    "fire": "metal",    # 火克金
    "thunder": "metal", # 雷克金
    "ice": "fire",      # 冰克火
    "wind": "wood",     # 风克木
}

# 属性中文名映射（用于日志显示）
from game.constants import ELEMENT_NAMES  # noqa: F401  (供本模块与子模块共用)
from game.engine_event_mixin import EventMixin
from game.engine_ending_mixin import EndingMixin, MainStoryMixin
from game.engine_combat_mixin import CombatMixin
from game.engine_master_mixin import MentorMixin
from game.engine_sect_mixin import SectMixin

# 模块级灵根配置，用于展开融合灵根
_SPIRITUAL_ROOT_CONFIG = SpiritualRootConfig()


def _expand_element_for_counter(element):
    """将元素或融合灵根展开为基础/变异元素列表。"""
    return _SPIRITUAL_ROOT_CONFIG.expand_root(element)


def element_multiplier(attacker_element, defender_element):
    """
    计算五行相克伤害系数（支持融合灵根）：
    - 攻击方任意元素克制防御方任意元素：×1.5
    - 攻击方任意元素被防御方任意元素克制：×0.7
    - 无属性、五行阵法（all）或同属性：×1.0
    - 同时存在克制与被克制时，优先取克制（1.5）
    """
    # "none" 和 "all" 不参与五行相克
    if attacker_element in ("none", "all") or defender_element in ("none", "all"):
        return 1.0

    attacker_elems = _expand_element_for_counter(attacker_element)
    defender_elems = _expand_element_for_counter(defender_element)

    has_counter = False
    has_countered = False
    for atk in attacker_elems:
        for dfn in defender_elems:
            if ELEMENT_COUNTERS.get(atk) == dfn:
                has_counter = True
            if ELEMENT_COUNTERS.get(dfn) == atk:
                has_countered = True

    if has_counter:
        return 1.5
    if has_countered:
        return 0.7
    return 1.0


class GameEngine(EventMixin, EndingMixin, MainStoryMixin, CombatMixin, MentorMixin, SectMixin):
    """游戏核心引擎，连接玩家、世界、事件，处理所有玩法逻辑。"""

    def __init__(
        self,
        player,
        world,
        event_pool,
        item_library,
        enemy_library,
        skill_library,
        npc_library,
        quest_library,
        save_manager=None,
        config_dir="config",
    ):
        self.player = player
        self.world = world
        self.event_pool = event_pool
        self.item_library = item_library
        self.enemy_library = enemy_library
        self.skill_library = skill_library
        self.npc_library = npc_library
        self.quest_library = quest_library
        self.save_manager = save_manager
        self.listeners = []   # UI 更新回调列表
        # 功能开关与月度结算订阅注册表（M0 前置改造：新系统按月结算的统一插座）
        self.config_dir = config_dir
        self._feature_flags = self._load_feature_flags()
        self._unlock_map = self._load_unlocks()
        self._tutorial_steps = self._load_tutorial_steps()
        self._endings = self._load_endings()
        self._main_story = self._load_main_story()
        from game.story_generator import StoryGenerator
        self.story_generator = StoryGenerator(config_dir=config_dir)
        from game.ai_story_generator import AIStoryGenerator
        self.ai_story_generator = AIStoryGenerator(config_dir=config_dir)
        self._pending_ai_event = None   # 待 AI 增强的游历事件上下文（UI 层异步消费）
        self._monthly_tick_hooks = []
        # 修炼流派配置（用于查询流派+灵根协同倍率）
        self.path_config = CultivationPathConfig(config_dir="config")
        # 对话系统
        self.dialogue_library = DialogueLibrary(config_dir="config")
        self.dialogue_manager = DialogueManager(self)
        # 渡劫小游戏/弹窗带来的额外成功率加成（由 UI 设置后 engine 读取）
        self.tribulation_bonus = 0.0
        # 维度①：待处理的心魔劫幻境场景（突破时若心魔过高则写入，UI 展示抉择后清除）
        self.pending_heart_demon_scenario = None
        # 宗门秘境/禁地 pending ID（战斗结束后据此结算奖励）
        self.pending_secret_realm_id = None
        # 世界 BOSS pending ID（战斗结束后据此结算奖励）
        self.pending_world_boss_id = None
        # 演武场排名挑战 pending 对手
        self.pending_arena_opponent = None
        # 宗门系统
        self.sect_library = SectLibrary(config_dir="config")
        self.sect_task_library = SectTaskLibrary(config_dir="config")
        self.sect_event_library = SectEventLibrary(config_dir="config")
        self.follower_library = FollowerLibrary(config_dir="config")
        self.diplomatic_mission_library = DiplomaticMissionLibrary(config_dir="config")
        self.sect_manager = SectManager(
            self.player, self.sect_library, self.item_library,
            self.skill_library, self.enemy_library, self.follower_library,
            self.diplomatic_mission_library,
            self.world,
            sect_event_library=self.sect_event_library,
        )
        # 新增子系统管理器
        self.mental_state_manager = MentalStateManager(self.player)
        self.weather_manager = WeatherManager(self.world)
        self.residence_manager = ResidenceManager(
            self.player, item_library=self.item_library
        )
        # 修炼成长扩展
        self.mind_method_manager = MindMethodManager(self.player)
        self.divine_art_manager = DivineArtManager(self.player)
        # 经济生产扩展
        self.economy_config = EconomyConfig(config_dir="config")
        self.farm_manager = FarmManager(
            self.player, item_library=self.item_library, world=self.world
        )
        self.auction_house_manager = AuctionHouseManager(
            self.player, self.item_library, self.world
        )
        # 坊市 NPC 配置与玩家摆摊系统
        self.market_npc_manager = MarketNPCManager(config_dir="config")
        self.stall_manager = StallManager(self.player, self.item_library)
        # 洞府租赁与闭关修炼系统
        self.cave_manager = CaveManager(self.player)
        # 转世轮回与多周目继承系统
        self.reincarnation_manager = ReincarnationManager(self.player)
        # 炼器附魔与装备词缀系统
        self.equipment_manager = EquipmentManager(self.player, self.item_library)
        self.player.equipment_manager = self.equipment_manager
        # 洞府炼丹室与炼器台管理器
        self.alchemy_manager = AlchemyManager(
            self.player, self.item_library, self.residence_manager
        )
        self.smithy_manager = SmithyManager(
            self.player, self.item_library, self.residence_manager
        )
        # 社交管理器：论道、双修、收徒、恩怨链
        self.social_manager = SocialManager(
            self.player, self.npc_library, self.world
        )
        self.bounty_board_manager = BountyBoardManager(
            self.player, self.item_library, self.world
        )
        # 战斗扩展
        self.combat_extension_manager = CombatExtensionManager(self.player, self.world)
        # 探索扩展
        self.secret_realm_manager = SecretRealmManager(
            self.player,
            self.enemy_library,
            self.item_library,
            feature_enabled=self.is_feature_enabled,
        )
        self.ruin_manager = RuinManager(
            self.player, self.enemy_library, self.item_library, self.world
        )
        self.world_boss_manager = WorldBossManager(
            self.world, self.enemy_library
        )
        self.treasure_map_manager = TreasureMapManager(
            self.player, self.item_library, self.world
        )
        self.teleport_manager = TeleportManager(self.player, self.world)
        self.travel_cost_model = TravelCostModel(
            self.player, self.world, self.sect_manager
        )
        # 叙事沉浸扩展
        self.achievement_manager = AchievementManager(
            self.player, self.item_library
        )
        # F-06 难度系统 / F-07 多周目模式
        self.difficulty_manager = DifficultyManager(config_dir="config")
        self.meta_manager = MetaManager(config_dir="config")
        self.chronicle_manager = ChronicleManager(self.player, self.world)
        self.side_quest_manager = SideQuestManager(
            self.player, self.item_library
        )
        # 城池动态任务生成器
        self.city_quest_generator = CityQuestGenerator(config_dir="config")
        # 城池建筑与声望管理器
        self.building_manager = BuildingManager(
            self.player, self.world, config_dir="config"
        )
        self.letter_rumor_manager = LetterRumorManager(self.player, self.world)
        # 城池演武场排名系统
        self.arena_ranking_manager = ArenaRankingManager(config_dir="config")
        # 城池动态事件系统（妖兽攻城等）
        self.city_event_manager = CityEventManager(
            self.enemy_library, self.item_library, config_dir="config"
        )
        # 社交关系扩展
        self.master_disciple_manager = MasterDiscipleManager(
            self.player, self.npc_library
        )
        self.reputation_manager = ReputationManager(self.player)
        # 策略经营扩展
        self.personal_beast_manager = PersonalBeastManager(
            self.player, self.item_library
        )
        self.compendium_manager = CompendiumManager(self.player)
        # 动态世界事件系统（F-04：传入全局世界状态管理器与功能开关回调）
        self.world_state_manager = WorldStateManager(
            self.player, config_dir=config_dir, notify_callback=self.notify
        )
        self.world_event_manager = WorldEventManager(
            self.player,
            self.world,
            self.npc_library,
            self.enemy_library,
            self.item_library,
            notify_callback=self.notify,
            world_state_manager=self.world_state_manager,
            is_feature_enabled=self.is_feature_enabled,
        )
        # 注册全局世界状态的月度结算（受 dynamic_world_event 开关控制）
        self.register_monthly_tick(
            self.world_state_manager.tick_monthly, flag="dynamic_world_event"
        )
        # 修仙家族系统（F-01）
        self.family_manager = FamilyManager(
            self.player,
            npc_library=self.npc_library,
            social_manager=self.social_manager,
            item_library=self.item_library,
            config_dir=config_dir,
            is_feature_enabled=self.is_feature_enabled,
            notify_callback=self.notify,
            get_month_callback=lambda: (self.world.year - 1) * 12
            + (self.world.month - 1),
        )
        # 家族月度结算（受 family 开关控制；未建家族时纯 no-op）
        self.register_monthly_tick(
            self.family_manager.tick_monthly, flag="family"
        )
        # 领地建设与扩张系统（F-02）
        self.territory_manager = TerritoryManager(
            self.player,
            config_dir=config_dir,
            is_feature_enabled=self.is_feature_enabled,
            notify_callback=self.notify,
            get_month_callback=lambda: (self.world.year - 1) * 12
            + (self.world.month - 1),
            item_library=self.item_library,
        )
        # 领地月度结算（受 territory 开关控制；未占据领地时纯 no-op）
        self.register_monthly_tick(
            self.territory_manager.tick_monthly, flag="territory"
        )
        # 维度④ 天道反噬与生态平衡（F-08）
        self.heaven_retribution_manager = HeavenRetributionManager(
            self.player, config_dir=config_dir, notify_callback=self.notify
        )
        self.register_monthly_tick(
            self._tick_heaven_retribution, flag="heaven_retribution"
        )
        # 维度⑤ 寿元与轮回晚年（F-09）
        self.lifespan_manager = LifespanManager(
            self.player, config_dir=config_dir, notify_callback=self.notify
        )
        self.register_monthly_tick(
            self._tick_lifespan, flag="lifespan_reincarnation"
        )
        # 维度② 红尘炼心 / 入世（F-08 体验深化）
        self.red_dust_manager = RedDustManager(
            self.player, config_dir=config_dir, notify_callback=self.notify
        )
        self.register_monthly_tick(
            self._tick_red_dust, flag="red_dust"
        )
        # 维度③ 百家争鸣 / 非传统修仙路线（F-08 体验深化）
        self.hundred_schools_manager = HundredSchoolsManager(
            self.player, config_dir=config_dir, notify_callback=self.notify
        )
        self.register_monthly_tick(
            self._tick_hundred_schools, flag="hundred_schools"
        )
        # 心境 / 道心系统月度结算（核心系统，常开；维度①深度特性由 heart_demon 开关门控）
        self.register_monthly_tick(self._tick_mental_state)
        # 维度③：读档后 skill_library 由 skills.json 重建，需把已自创功法重新注册为可用技能
        self._register_self_created_skills()

    def add_listener(self, callback):
        """注册一个状态变化监听器。"""
        self.listeners.append(callback)

    def notify(self, message):
        """通知所有监听器，通常是刷新 UI 或追加日志。"""
        for callback in self.listeners:
            callback(message)

    def update_view(self):
        """专门触发一次界面刷新，不带新日志。"""
        self.notify("")

    # ==================== 功能开关与月度结算插座（M0） ====================

    def _load_feature_flags(self):
        """读取功能开关配置 config/feature_flags.json。

        文件缺失或解析失败时默认全部开启（保证旧存档/旧配置可正常运行）。
        支持 {"flags": {...}} 或顶层直接为 {flag: bool} 两种结构。
        """
        path = os.path.join(self.config_dir, "feature_flags.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self.notify(f"[red]feature_flags.json 解析失败，已默认全开：{e}")
            return {}
        if isinstance(data, dict) and isinstance(data.get("flags"), dict):
            return dict(data["flags"])
        if isinstance(data, dict):
            return data
        return {}

    def is_feature_enabled(self, flag):
        """查询某功能开关是否开启；未配置该 flag 时默认开启。"""
        if not self._feature_flags:
            return True
        return bool(self._feature_flags.get(flag, True))

    def set_feature_flag(self, flag, enabled):
        """设置功能开关：内存即时生效，并持久化到 feature_flags.json。

        保留文件中的 _comment/names/descriptions 等辅助字段；
        写入失败（权限/磁盘）时内存状态仍生效，返回 False 供调用方提示。
        """
        self._feature_flags[flag] = bool(enabled)
        path = os.path.join(self.config_dir, "feature_flags.json")
        try:
            data = {}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            flags = data.get("flags") if isinstance(data.get("flags"), dict) else {}
            flags = dict(flags)
            flags[flag] = bool(enabled)
            data["flags"] = flags
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except (json.JSONDecodeError, OSError) as e:
            self.notify(f"[red]功能开关保存失败（内存状态已生效）：{e}")
            return False

    def _load_unlocks(self):
        """读取功能按钮的境界解锁门槛 config/unlocks.json。

        文件缺失或解析失败时返回空映射（所有按钮默认解锁，保证旧配置可运行）。
        支持 {"unlocks": {...}} 或顶层直接为 {action: {...}} 两种结构。
        """
        path = os.path.join(self.config_dir, "unlocks.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
        if isinstance(data, dict) and isinstance(data.get("unlocks"), dict):
            return dict(data["unlocks"])
        if isinstance(data, dict):
            return data
        return {}

    def is_action_unlocked(self, action_name):
        """判断某功能按钮是否已达境界解锁门槛；未配置门槛视为已解锁。

        支持两种条件（可同时存在，需全部满足）：
        - order：当前境界序号（REALM_ORDER）需 >= 该值；
        - feature：需存在于 player.unlocked_features 中。
        """
        entry = self._unlock_map.get(action_name)
        if not entry:
            return True
        if "order" in entry:
            order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
            if order < int(entry["order"]):
                return False
        if "feature" in entry:
            if not self.player.has_feature(entry["feature"]):
                return False
        return True

    def get_unlock_hint(self, action_name):
        """返回某功能按钮未解锁时的提示文案；无提示返回空串。"""
        entry = self._unlock_map.get(action_name)
        return entry.get("hint", "") if entry else ""

    def _load_tutorial_steps(self):
        """读取新手引导步骤 config/tutorial_quests.json；失败返回空列表。"""
        path = os.path.join(self.config_dir, "tutorial_quests.json")
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
        steps = data.get("steps", []) if isinstance(data, dict) else []
        return [s for s in steps if isinstance(s, dict)]

    def _tutorial_enabled(self):
        """引导是否开启：ui_prefs.json 的 tutorial_enabled，默认开启。"""
        try:
            path = os.path.join(self.config_dir, "ui_prefs.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "tutorial_enabled" in data:
                    return bool(data["tutorial_enabled"])
        except (json.JSONDecodeError, OSError):
            pass
        return True

    def _advance_tutorial(self, trigger):
        """按触发动作推进新手引导步骤；未开启或已完成则无副作用。"""
        if not self._tutorial_enabled() or not self._tutorial_steps:
            return
        step = getattr(self.player, "tutorial_step", 0)
        if step >= len(self._tutorial_steps):
            return
        expected = self._tutorial_steps[step]
        if expected.get("trigger") == trigger:
            self.player.tutorial_step = step + 1
            self.notify(f"[cyan]【新手引导】{expected.get('title', '')} 完成！")
            if step + 1 >= len(self._tutorial_steps):
                self.notify("[cyan]【新手引导】全部完成，修仙之路就此展开！")

    def get_tutorial_progress(self):
        """返回引导进度 (current, total, title, desc)；未开启或已完成返回 None。"""
        if not self._tutorial_enabled() or not self._tutorial_steps:
            return None
        step = getattr(self.player, "tutorial_step", 0)
        if step >= len(self._tutorial_steps):
            return None
        cur = self._tutorial_steps[step]
        return (step + 1, len(self._tutorial_steps),
                cur.get("title", ""), cur.get("desc", ""))

    def register_monthly_tick(self, callback, flag=None):
        """注册按月结算回调（无参可调用），作为新系统的统一月度插座。

        callback: 形如 manager.tick_monthly 的绑定方法。
        flag: 关联的功能开关名；为 None 时不受开关控制、始终执行。
        返回该 hook 的索引，便于后续 unregister。
        """
        self._monthly_tick_hooks.append((callback, flag))
        return len(self._monthly_tick_hooks) - 1

    def unregister_monthly_tick(self, index):
        """注销指定索引的月度结算回调（以空函数占位，避免索引错位）。"""
        if 0 <= index < len(self._monthly_tick_hooks):
            self._monthly_tick_hooks[index] = (lambda: None, None)

    def _run_registered_monthly_ticks(self):
        """运行所有已注册且功能开启的月度结算回调。

        单系统异常被隔离，不影响其他系统或整月结算（对应风险应对中的容错）。
        纯新增插座：注册表为空时无任何副作用，旧系统行为不变。
        """
        for callback, flag in self._monthly_tick_hooks:
            if flag is not None and not self.is_feature_enabled(flag):
                continue
            try:
                callback()
            except Exception as e:  # 防御性：单系统异常不应中断整月结算
                name = getattr(callback, "__qualname__", repr(callback))
                self.notify(f"[red]月度结算异常（{flag or name}）：{e}")

    def _tick_mental_state(self):
        """心境/道心月度结算：自然恢复、心魔衰减，并检查被动心魔事件。"""
        mental_gain, heart_decay, hd_events = self.mental_state_manager.tick_monthly()
        if hd_events:
            for event in hd_events:
                self.notify(
                    f"[red]{event.get('name', '心魔事件')}触发！"
                    f"{event.get('description', '')}"
                )

    def _tick_heaven_retribution(self):
        """维度④ 天道反噬月度结算：注视衰减 + 暴涨监测 + 灵脉枯竭。"""
        hr = self.heaven_retribution_manager
        # 1. 天道注视自然衰减
        hr.tick_monthly()
        # 2. 暴涨监测：与上月基线比较，战力/财富激增则增注视
        power = hr.estimate_power()
        wealth = hr.estimate_wealth()
        base_power = getattr(self.player, "_gaze_power_base", None)
        base_wealth = getattr(self.player, "_gaze_wealth_base", None)
        if base_power is not None and power - base_power >= hr.config.get_gaze().get("power_spike_min", 500):
            hr.on_power_spike(power - base_power)
        if base_wealth is not None and base_wealth > 0 and wealth >= base_wealth * hr.config.get_gaze().get("wealth_spike_multiplier", 1.5):
            hr.on_wealth_spike(base_wealth, wealth)
        self.player._gaze_power_base = power
        self.player._gaze_wealth_base = wealth
        # 3. 灵脉枯竭：对每块领地比对抽取与承载力
        terr = getattr(self.player, "territory", None)
        for t in ([terr] if isinstance(terr, dict) else (terr or [])):
            if not isinstance(t, dict):
                continue
            extraction = self.territory_manager.monthly_extraction(t, "spirit_stone")
            depletion, monster = hr.check_territory_depletion(t, extraction)
            if depletion >= hr.config.get_depletion().get("max", 100):
                # 产出归零：扣回本月已入金库的灵石产出
                t["treasury"] = max(0, t.get("treasury", 0) - extraction)
                self.notify(
                    f"[red]【{t.get('name', '领地')}】灵脉枯竭！本月灵石产出归零。"
                )
                if monster and hasattr(self, "start_combat") and hasattr(self, "enemy_library"):
                    foe = self._spawn_vein_wraith(t)
                    if foe:
                        self.start_combat(foe)

    def _spawn_vein_wraith(self, territory):
        """生成『地脉怨气』化形怪物攻城。"""
        try:
            enemies = list(self.enemy_library.values()) if hasattr(self.enemy_library, "values") else []
            if not enemies:
                return None
            enemies.sort(key=lambda e: getattr(e, "power", getattr(e, "level", 0) or 0), reverse=True)
            return enemies[0]
        except Exception:
            return None

    def _tick_lifespan(self):
        """维度⑤ 寿元与轮回月度结算：推进残魂重塑。"""
        self.lifespan_manager.tick_remnant_soul()

    def _tick_red_dust(self):
        """维度② 红尘炼心月度结算：羁绊衰减 + 红尘事件 + 情劫。"""
        self.red_dust_manager.tick_monthly()

    def _tick_hundred_schools(self):
        """维度③ 百家争鸣月度结算：立派传道气运反哺 + 自创功法明心 + 生活流派精进产出。"""
        rewards = self.hundred_schools_manager.tick_monthly()
        stones = rewards.get("spirit_stone", 0)
        if stones > 0 and hasattr(self, "item_library"):
            for _ in range(stones):
                self.player.add_item(self.item_library.create("spirit_stone"))
        # 生活流派月度产出真实物品（丹/器/符/阵）
        for item_id in rewards.get("produced_items", []) or []:
            item = self.item_library.create(item_id) if hasattr(self, "item_library") else None
            if item:
                self.player.add_item(item)
                self.notify(f"[green]生活流派精进，制得【{getattr(item, 'name', item_id)}】。")

    # ==================== 维度④⑤ 玩家动作 ====================
    def sit_and_dissolve(self, arrangements):
        """坐化：安排后事（维度⑤）。"""
        return self.lifespan_manager.arrange_sit(arrangements)

    def become_remnant_soul(self, host_type, host_id=None):
        """残魂夺舍 / 器灵化身（维度⑤）。"""
        return self.lifespan_manager.become_remnant_soul(host_type, host_id)

    # ==================== 维度② 玩家动作 ====================
    def enter_red_dust(self):
        """入世历练：开启红尘淬心（维度②）。"""
        return self.red_dust_manager.enter_red_dust()

    def exit_red_dust(self):
        """归隐出尘：结束历练，红尘羁绊沉淀为心境（维度②）。"""
        return self.red_dust_manager.exit_red_dust()

    def red_dust_experience(self):
        """主动历红尘：触发一次红尘事件（维度②）。"""
        return self.red_dust_manager.experience()

    def apply_qingjie_choice(self, choice_id):
        """应用情劫抉择（维度②，由 UI 弹窗调用）。返回 (ok, message)。"""
        ok, msg = self.red_dust_manager.apply_qingjie_choice(choice_id)
        if ok:
            self.notify(f"[purple]{msg}")
        return ok, msg

    def red_dust_warm(self, bond_type):
        """温养羁绊：以灵石提升某段羁绊亲密度（维度②，由 UI 弹窗调用）。返回 (ok, message)。"""
        ok, msg = self.red_dust_manager.warm_bond(bond_type)
        if ok:
            self.notify(f"[magenta]{msg}")
        return ok, msg

    # ==================== 维度③ 玩家动作 ====================
    def found_sect(self, name):
        """开宗立派（维度③ 立派传道）。"""
        ok, msg = self.hundred_schools_manager.found_sect(name)
        if ok:
            self.notify(f"[gold]{msg}")
        return ok, msg

    def create_technique(self, name, school, attribute):
        """自创功法（维度③）。成功后将其注册为真实可施展的 Skill 并学会。"""
        ok, msg = self.hundred_schools_manager.create_technique(name, school, attribute)
        if ok:
            tech = self.player.self_created_techniques[-1]
            self._register_one_self_created_skill(tech)
            self.notify(f"[gold]{msg}（已纳入可施展功法）")
        return ok, msg

    # ---------------- 维度③·M19 功法推演（养成式自创功法） ----------------
    def start_technique_deduction(self, name, school, attribute):
        """开启功法推演（return (ok, msg)）。"""
        ok, msg = self.hundred_schools_manager.start_deduction(name, school, attribute)
        if ok:
            self.notify(f"[gold]{msg}")
        else:
            self.notify(f"[red]{msg}")
        return ok, msg

    def resolve_technique_deduction_node(self, force_success=None):
        """参悟推演下一节点（return (ok, msg, detail)）。"""
        ok, msg, detail = self.hundred_schools_manager.resolve_deduction_node(force_success)
        self.notify(f"[cyan]{msg}")
        return ok, msg, detail

    def commit_technique_deduction(self):
        """功法推演大成：落定自创功法并注册为可施展 Skill。return (ok, msg, tech)。"""
        ok, msg, tech = self.hundred_schools_manager.commit_deduction()
        if ok:
            self._register_one_self_created_skill(tech)
            self.notify(f"[gold]{msg}（已纳入可施展功法）")
        else:
            self.notify(f"[red]{msg}")
        return ok, msg, tech

    def _register_one_self_created_skill(self, tech):
        """把一条自创功法 dict 注册为一个 Skill 对象（幂等）。"""
        if not tech:
            return
        kw = self.hundred_schools_manager.build_skill_kwargs(tech)
        if not kw:
            return
        sk = Skill(**kw)
        self.skill_library.skills[sk.id] = sk
        if sk.id not in self.player.skills:
            self.player.learn_skill(sk.id)

    def _register_self_created_skills(self):
        """读档后 skill_library 被重建，需把所有已自创功法重新注册为可用 Skill。"""
        for tech in getattr(self.player, "self_created_techniques", []) or []:
            self._register_one_self_created_skill(tech)

    def choose_life_path(self, path):
        """择生活流派精进（维度③ 生活流派御劫）。"""
        ok, msg = self.hundred_schools_manager.choose_life_path(path)
        if ok:
            self.notify(f"[gold]{msg}")
        return ok, msg

    def spend_qi_yun_for_enlightenment(self):
        """耗气运行道韵灌顶（维度③ 立派传道）。"""
        ok, msg = self.hundred_schools_manager.spend_qi_yun_for_enlightenment()
        if ok:
            self.notify(f"[gold]{msg}")
        return ok, msg

    def apply_heart_demon_tribulation_choice(self, scenario_id, choice_id):
        """应用心魔劫幻境抉择（由 UI 幻境弹窗调用）。返回 (ok, message)。"""
        ok, msg = self.mental_state_manager.apply_tribulation_choice(scenario_id, choice_id)
        if ok:
            self.notify(f"[purple]{msg}")
        self.pending_heart_demon_scenario = None
        return ok, msg

    def _unity_enlightenment_technique(self):
        """天人合一顿悟：领悟一门尚未习得的高阶神通。"""
        learned = set(getattr(self.player, "learned_skills", []))
        candidates = [
            sid for sid in self.skill_library.skills
            if sid not in learned
        ]
        if not candidates:
            return
        skill_id = random.choice(candidates)
        skill = self.skill_library.get(skill_id)
        if self.player.learn_skill(skill_id):
            self.notify(f"[cyan]天人合一！你于顿悟中领悟神通【{skill.name}】！")
            self._on_learn_skill(skill_id)
        self._auto_save()

    def _auto_save(self):
        """自动存档，重大事件后调用。"""
        if self.save_manager:
            self.save_manager.save(self.player, self.world)

    # 五行阵法技能 ID 列表（需五行俱全方可解锁）
    FORMATION_SKILL_IDS = ["five_elements_formation", "five_elements_return"]

    def check_formation_unlock(self):
        """
        检查玩家是否五行俱全，若是且尚未习得阵法技能，则自动解锁。
        作为"全面但缓慢"路线（5 灵根 4.0x 修炼倍率）的补偿奖励。
        """
        # 未达五行俱全，不处理
        if len(self.player.spiritual_roots) < 5:
            return
        # 检查是否有未习得的阵法技能
        newly_learned = []
        for skill_id in self.FORMATION_SKILL_IDS:
            if not self.player.has_skill(skill_id):
                # 确认技能库中存在该技能
                skill = self.skill_library.get(skill_id)
                if skill:
                    self.player.learn_skill(skill_id)
                    newly_learned.append(skill.name)
        if newly_learned:
            names = "、".join(newly_learned)
            self.notify(
                f"五行灵根俱全，你感悟五行相生相克之理，"
                f"领悟了阵法技能【{names}】！"
            )
            self._auto_save()

    # ==================== 事件钩子 ====================

    def _on_kill_enemy(self, enemy):
        """
        击杀敌人后触发各扩展系统事件钩子：
        图鉴、悬赏板、支线任务、成就、年表、声望。
        """
        # 记录图鉴击杀数
        self.compendium_manager.record_enemy(enemy.id)
        # 推进悬赏板并通知完成的悬赏
        completed_bounties = self.bounty_board_manager.update_kill(enemy.id)
        for bounty in completed_bounties:
            self.notify(
                f"[gold]悬赏完成：击杀 {bounty['count']} 只 {enemy.name}，"
                f"获得 {bounty['reward_stones']} 灵石。"
            )
        # 推进支线任务进度
        side_rewards = self.side_quest_manager.update_progress("kill", enemy_id=enemy.id)
        self._grant_side_quest_rewards(side_rewards)
        # 检查击杀相关成就（附带 world_boss 标记，供隐藏成就判定）
        unlocked = self.achievement_manager.check(
            "kill", enemy_id=enemy.id, world_boss=getattr(enemy, "world_boss", False)
        )
        for aid, name in unlocked:
            self.notify(f"[gold]达成成就：【{name}】！")
        # 记录年表
        self.chronicle_manager.record(
            f"斩杀 {enemy.name}", category="combat"
        )
        # 根据敌人阵营调整声望
        alignment = getattr(enemy, "alignment", "neutral")
        if alignment == "righteous":
            self.reputation_manager.adjust("demonic_reputation", 10)
            self.reputation_manager.adjust("qingyun_reputation", -5)
        elif alignment == "evil":
            self.reputation_manager.adjust("qingyun_reputation", 10)
            self.reputation_manager.adjust("demonic_reputation", -5)

    def _on_gain_item(self, item_id, count=1):
        """获得物品后触发图鉴、成就、支线任务钩子。"""
        self.compendium_manager.record_item(item_id)
        # 成就仅对累计数量类物品触发一次即可
        self.achievement_manager.check("item_change", item_id=item_id)
        # 推进收集类支线任务
        side_rewards = self.side_quest_manager.update_progress(
            "collect_item", item_id=item_id
        )
        self._grant_side_quest_rewards(side_rewards)

    def _on_learn_skill(self, skill_id):
        """习得技能后触发图鉴、成就钩子。

        维度①：若开启心魔系统，正道（非魔道路线）修习魔功视为违戒，滋生心魔。
        """
        self.compendium_manager.record_skill(skill_id)
        self.achievement_manager.check("skill_learn", skill_id=skill_id)
        if self.is_feature_enabled("heart_demon"):
            triggered, delta = self.mental_state_manager.on_precept_violation(skill_id)
            if triggered:
                self.notify(
                    f"[red]你修习了与自身道途相悖的功法，心魔滋生（+{delta}）！"
                )

    def _on_travel(self, location_id):
        """抵达新地点后触发年表、支线任务钩子。"""
        location = self.world.get_location(location_id)
        loc_name = location["name"] if location else location_id
        self.chronicle_manager.record(
            f"抵达【{loc_name}】", category="explore"
        )
        side_rewards = self.side_quest_manager.update_progress(
            "visit_location", location_id=location_id
        )
        self._grant_side_quest_rewards(side_rewards)

    def _grant_side_quest_rewards(self, rewards_map):
        """
        根据支线任务奖励映射发放灵石、物品奖励。
        rewards_map: {quest_id: rewards_dict}
        """
        if not rewards_map:
            return
        for qid, rewards in rewards_map.items():
            quest = self.side_quest_manager.config.get(qid)
            quest_name = quest["name"] if quest else qid
            # 灵石奖励（转换为灵石物品）
            stones = rewards.get("spirit_stones", 0)
            if stones:
                for _ in range(stones):
                    self.player.add_item(self.item_library.create("spirit_stone"))
                self.notify(f"[gold]支线任务【{quest_name}】奖励：灵石 +{stones}")
            # 物品奖励
            item_id = rewards.get("item_id")
            if item_id:
                item = self.item_library.create(item_id)
                if item:
                    self.player.add_item(item)
                    self.notify(f"[gold]支线任务【{quest_name}】奖励：{item.name} x1")
            # 修为奖励已在 SideQuestManager.complete 中发放，这里仅通知
            qi_reward = rewards.get("qi", 0)
            if qi_reward:
                self.notify(f"[gold]支线任务【{quest_name}】奖励：修为 +{qi_reward}")
            # 宗门贡献与好感度已在 complete 中处理
            contrib = rewards.get("sect_contribution", 0)
            if contrib:
                self.notify(f"[gold]支线任务【{quest_name}】奖励：宗门贡献 +{contrib}")
            rel = rewards.get("relationship", 0)
            if rel:
                self.notify(f"[gold]支线任务【{quest_name}】奖励：与发布者好感度 +{rel}")

    def _on_complete_quest(self, quest_id):
        """完成任务后触发年表、成就钩子。"""
        quest = self.quest_library.get(quest_id)
        quest_name = quest.name if quest else quest_id
        self.chronicle_manager.record(
            f"完成任务【{quest_name}】", category="quest"
        )
        self.achievement_manager.check("quest_complete", quest_id=quest_id)

    # ==================== 地点环境与旅行 ====================

    def get_location_spirit_bonus(self, location_id=None):
        """获取某地点的灵气浓度对修炼速度的加成。

        优先读取 locations.json 中的 spirit_bonus 字段；
        若未配置，则按地点类型返回默认基础值。
        """
        if location_id is None:
            location_id = self.player.location_id
        location = self.world.get_location(location_id)
        if not location:
            return 0.0

        # 配置化灵气浓度，未配置时按类型回退
        if "spirit_bonus" in location:
            return float(location["spirit_bonus"])
        loc_type = location.get("type", "wild")
        return {"sect": 0.20, "city": 0.12, "wild": 0.05}.get(loc_type, 0.05)

    def get_location_safety_level(self, location_id=None):
        """获取某地点的安全等级（0-10，越高越安全）。

        安全等级影响闭关时遭遇妖兽/敌人袭击的概率。
        优先读取 locations.json 中的 safety_level 字段。
        """
        if location_id is None:
            location_id = self.player.location_id
        location = self.world.get_location(location_id)
        if not location:
            return 5

        if "safety_level" in location:
            return max(0, min(10, int(location["safety_level"])))
        loc_type = location.get("type", "wild")
        return {"sect": 10, "city": 8, "wild": 5}.get(loc_type, 5)

    def get_location_raid_chance(self, location_id=None):
        """根据安全等级计算闭关期间每月遭遇袭击的概率。"""
        safety = self.get_location_safety_level(location_id)
        # 安全等级 10 时约 0%，安全等级 0 时约 20%
        chance = 0.20 - safety * 0.02
        return max(0.01, min(0.20, chance))

    def calculate_travel_time(self, to_location_id, from_location_id=None):
        """计算从当前地点前往目标地点所需的基础月数。"""
        return self.travel_cost_model.calculate_base_time(
            to_location_id, from_location_id
        )

    def get_travel_reduction(self):
        """获取玩家当前可提供的旅行时间减免（来自坐骑、技能等）。"""
        # 坐骑型灵兽：全额免除赶路时间
        if self.travel_cost_model.has_mount():
            return "mount", 1.0

        # 拥有疾风步等技能可缩短 30% 赶路时间
        if self.travel_cost_model.get_skill_reduction() > 0:
            return "skill", 0.30

        return None, 0.0

    def _on_form_companion(self, npc_id):
        """结为道侣后触发成就钩子。"""
        self.achievement_manager.check("companion", npc_id=npc_id)

    def _on_sect_rank_change(self, rank):
        """宗门职位变动后触发成就钩子。"""
        self.achievement_manager.check("sect_rank", rank=rank)

    def _notify_chronicle(self, text, category="event"):
        """便捷方法：记录年表并触发刷新。"""
        self.chronicle_manager.record(text, category=category)

    # ==================== 修炼与突破 ====================

    def cultivate(self, months=1):
        """修炼指定月数，增加修为并消耗时间。灵根越多修炼越慢。"""
        total_gain = 0
        path = self.player.cultivation_path
        # 宗门洞府加成、设施加成、追随者加成、气运事件加成与护山大阵加成合并计算
        cave_bonus = self.sect_manager.get_cultivation_bonus()
        facility_bonus = self.sect_manager.get_facility_cultivation_bonus()
        follower_bonus = self.sect_manager.get_follower_passive_bonus()
        fortune_bonus = self.sect_manager.get_fortune_cultivation_bonus()
        formation_bonus = self.sect_manager.get_formation_cultivation_bonus()
        residence_bonus = self.residence_manager.get_cultivation_speed_bonus()
        mental_bonus = self.mental_state_manager.get_cultivation_speed_bonus()
        # 心法与神通带来的修炼加成
        mind_method_bonus = self.mind_method_manager.get_cultivation_speed_bonus()
        divine_effects = self.divine_art_manager.get_effects()
        divine_art_bonus = divine_effects.get("cultivation_speed", 0.0)
        # 地点灵气浓度加成
        location_spirit_bonus = self.get_location_spirit_bonus()
        total_bonus = (
            cave_bonus + facility_bonus + follower_bonus + fortune_bonus +
            formation_bonus + residence_bonus + mental_bonus +
            mind_method_bonus + divine_art_bonus + location_spirit_bonus
        )
        # 每月固定加成在循环外先取一次，天气变化在循环内动态更新
        weather_bonus = self.weather_manager.get_cultivation_speed_bonus(path)
        total_bonus += weather_bonus
        for month_index in range(months):
            if not self.player.is_alive():
                break
            # 基础修为受悟性影响
            base_gain = 10 + self.player.wisdom * 2
            # 灵根越多倍率越高，实际获得修为越少
            actual_gain = int(base_gain / self.player.cultivation_multiplier)
            # 境界成长系数：高境界灵气更浓郁，月修为收入随境界增长
            # （练气 1.8x → 元婴 15.4x），避免"收入恒定、需求指数涨"的曲线卡死
            realm = self.world.get_realm(self.player.realm_id)
            realm_order = realm["order"] if realm else 1
            actual_gain = int(actual_gain * (1 + realm_order * 0.8))
            # 动态天气加成：每月可能变化，重新计算
            current_weather_bonus = self.weather_manager.get_cultivation_speed_bonus(path)
            current_total_bonus = total_bonus - weather_bonus + current_weather_bonus
            # 洞府 + 设施 + 心境 + 天气等综合加成
            if current_total_bonus > 0:
                actual_gain = int(actual_gain * (1 + current_total_bonus))
            self.player.qi += actual_gain
            total_gain += actual_gain
            # 维度③·M18：丹道「灵力温养」持续修炼增益（每月附加，到期递减）
            if self.player.cultivation_boost_months > 0 and self.player.cultivation_boost_amount > 0:
                self.player.qi += self.player.cultivation_boost_amount
                total_gain += self.player.cultivation_boost_amount
                self.player.cultivation_boost_months -= 1
            # 维度①：高道心闭关概率触发天人合一顿悟（海量修为 / 顿悟神通）
            if self.is_feature_enabled("heart_demon"):
                epiphany = self.mental_state_manager.maybe_unity_enlightenment()
                if epiphany and epiphany.get("type") == "qi":
                    bonus = int(actual_gain * (epiphany.get("multiplier", 2.0) - 1))
                    if bonus > 0:
                        self.player.qi += bonus
                        total_gain += bonus
                        self.notify(
                            f"[cyan]天人合一！你于闭关中顿悟天地法则，修为暴涨 +{bonus}！"
                        )
                elif epiphany and epiphany.get("type") == "technique":
                    self._unity_enlightenment_technique()
            self.world.advance(1)
            self.player.add_age_months(1)
            # 推进天气与灵气潮汐
            changed, prev_w, new_w, prev_t, new_t = self.weather_manager.advance()
            if changed:
                self.notify(
                    f"[sky]天时变换：{self.weather_manager.get_description()}"
                )
            # 推进宗门设施效果的持续时间
            self.sect_manager.tick_facility_effects(1)
            # 进入新月时重置宗门每日任务计数
            self._check_sect_daily_reset()
            # 每年年初检查通缉衰减
            if self.world.month == 1:
                self._check_sect_wanted_decay()
            # 每月心境自然变化与心魔事件检查（改由月度插座 _tick_mental_state 统一驱动，
            # 使 cultivate / explore / travel 三处时间推进行为一致）
            # 洞府每月产出、维护费与袭击判定
            residence_result = self.residence_manager.tick_monthly()
            for log in residence_result.get("logs", []):
                self.notify(f"[gray]{log}")
            # 社交恩怨链月度推进
            social_events = self.social_manager.tick_grudges()
            for event in social_events:
                self.notify(f"[red]{event['message']}")
            for herb_id in residence_result.get("production", []):
                herb = self.item_library.create(herb_id)
                if herb:
                    self.player.add_item(herb)
                    self.notify(f"洞府药园收获【{herb.name}】。")
            raid = residence_result.get("raid")
            if raid:
                enemy_data = self.enemy_library.get(raid["enemy_id"])
                if enemy_data:
                    enemy = Enemy.from_dict(enemy_data)
                    bonus = raid.get("strength_bonus", 0.0)
                    if bonus:
                        enemy.max_hp = int(enemy.max_hp * (1 + bonus))
                        enemy.hp = enemy.max_hp
                        enemy.attack = int(enemy.attack * (1 + bonus))
                        enemy.defense = int(enemy.defense * (1 + bonus))
                    self.notify("[red]洞府遭到袭击，你被迫中断修炼迎战！")
                    # 标记待处理的洞府袭击，战斗结束后在 UI 层结算
                    self.pending_residence_raid = True
                    self.start_combat(enemy)
                    # 袭击打断修炼，total_gain 已包含本月修为
                    break
            # 地点安全度带来的袭击判定（荒郊野外闭关更易被打扰）
            location = self.get_current_location()
            if location and location.get("type") == "wild":
                raid_chance = self.get_location_raid_chance()
                if random.random() < raid_chance:
                    enemy_ids = location.get("enemies", [])
                    if enemy_ids:
                        enemy_id = random.choice(enemy_ids)
                        enemy_data = self.enemy_library.get(enemy_id)
                        if enemy_data:
                            enemy = Enemy.from_dict(enemy_data)
                            self.notify("[red]你在闭关时遭遇妖兽袭击，被迫中断修炼迎战！")
                            self.start_combat(enemy)
                            break
            # 邪修修炼时积累邪气（每月 +2）
            if path == "xie":
                self.player.add_path_resource(2)
            # 御兽修修炼时与灵兽沟通，有概率获得兽魂（每月 20% 概率 +1）
            elif path == "shou":
                if random.random() < 0.2:
                    self.player.add_path_resource(1)
            # 符修修炼时绘制符箓（每月 +2 张，消耗少量真气）
            elif path == "fu":
                self.player.add_path_resource(2)

            # 资源型灵兽每月产出
            resource_drops = self.sect_manager.get_beast_resource_bonus()
            for item_id, count in resource_drops:
                item = self.item_library.get(item_id)
                if item:
                    for _ in range(count):
                        self.player.add_item(item)
                    self.notify(f"灵兽为你衔来【{item.name}】x{count}。")

            # 推进洞府药园作物生长
            farm_logs = self.farm_manager.tick_monthly()
            for log in farm_logs:
                self.notify(log)

            # 推进个人灵兽成长与产出
            beast_logs = self.personal_beast_manager.tick_monthly()
            for log in beast_logs:
                self.notify(log)
            # 检查灵兽历练归来
            _, dispatch_logs = self.personal_beast_manager.check_dispatch_return(self.world)
            for log in dispatch_logs:
                self.notify(log)

            # 推进徒弟成长
            disciple_logs = self.master_disciple_manager.tick_disciples()
            for log in disciple_logs:
                self.notify(log)

            # 刷新拍卖行与悬赏板（按世界月份）
            self.auction_house_manager.refresh()
            self.bounty_board_manager.refresh()
            # 推进摆摊销售
            city_rep = self.player.city_reputation.get(self.player.location_id, 0)
            stall_logs = self.stall_manager.tick_monthly(city_reputation=city_rep)
            for log in stall_logs:
                self.notify(log)
            # 推进城池政策（城主任期与政策到期）
            self._tick_city_policies()
            # 推进洞府租期与闭关
            self._tick_caves()
            # 推进 NPC 自主移动
            self.npc_library.update_movements(self.world)
            # 推进世界 BOSS 刷新链
            self.world_boss_manager.tick(self.player)
            # 推进动态世界事件
            self.world_event_manager.tick()
            # 运行新注册系统的月度结算（受 feature_flags 控制，如 F-04 等）
            self._run_registered_monthly_ticks()

        # 显示修炼倍率信息
        mult = self.player.cultivation_multiplier
        bonus_parts = []
        if cave_bonus > 0:
            bonus_parts.append(f"洞府加成 {int(cave_bonus * 100)}%")
        if facility_bonus > 0:
            bonus_parts.append(f"设施加成 {int(facility_bonus * 100)}%")
        if follower_bonus > 0:
            bonus_parts.append(f"追随者加成 {int(follower_bonus * 100)}%")
        if fortune_bonus > 0:
            bonus_parts.append(f"气运加成 {int(fortune_bonus * 100)}%")
        if formation_bonus > 0:
            bonus_parts.append(f"大阵加成 {int(formation_bonus * 100)}%")
        if residence_bonus > 0:
            bonus_parts.append(f"洞府加成 {int(residence_bonus * 100)}%")
        if mental_bonus > 0:
            bonus_parts.append(f"心境加成 {int(mental_bonus * 100)}%")
        if mind_method_bonus > 0:
            bonus_parts.append(f"心法加成 {int(mind_method_bonus * 100)}%")
        if divine_art_bonus > 0:
            bonus_parts.append(f"神通加成 {int(divine_art_bonus * 100)}%")
        if weather_bonus != 0:
            bonus_parts.append(f"天象加成 {int(weather_bonus * 100)}%")
        if location_spirit_bonus > 0:
            bonus_parts.append(f"灵气加成 {int(location_spirit_bonus * 100)}%")
        bonus_text = "、".join(bonus_parts)
        if bonus_text:
            bonus_text = "、" + bonus_text
        self.notify(
            f"闭关修炼 {months} 个月，修为增加 {total_gain} 点。"
            f"（修炼倍率 {mult}x{bonus_text}）"
        )
        # 邪修正道追杀检测
        self._check_evil_qi_hunt()
        self._check_death()
        self._advance_tutorial("cultivate")

    # 大境界渡劫：圆满期突破到下一境界时触发
    MAJOR_BREAKTHROUGH_NAMES = {
        "qi_refining_9": "筑基天劫",
        "foundation_peak": "金丹雷劫",
        "golden_core_peak": "元婴心魔劫",
    }

    def _is_major_breakthrough(self, realm_id):
        """判断当前境界是否为大境界圆满，突破时需渡劫。"""
        return realm_id in self.player.MAJOR_REALM_IDS

    def _world_total_months(self):
        """计算当前世界总月份，用于头像光效等限时效果。"""
        return (self.world.year - 1) * 12 + (self.world.month - 1)

    def breakthrough(self):
        """尝试突破到下一个境界。大境界圆满时需先渡劫。"""
        if not self.player.is_alive():
            self.notify("你已陨落，无法继续突破。")
            return

        realm = self.world.get_realm(self.player.realm_id)
        if self.player.qi < realm["max_qi"]:
            need = realm["max_qi"] - self.player.qi
            self.notify(f"修为不足，还需 {need} 点方可尝试突破。")
            return

        next_id = self.world.next_realm(self.player.realm_id)
        if next_id is None:
            # 已达最高境界（元婴圆满）：尝试飞升，判定结局
            self._attempt_ascension()
            return

        # 判断是否需要渡劫
        is_major = self._is_major_breakthrough(self.player.realm_id)
        tribulation_name = self.MAJOR_BREAKTHROUGH_NAMES.get(self.player.realm_id, "")

        # 计算突破成功率：基础成功率 + 根骨加成
        rate = realm["breakthrough_rate"] + self.player.constitution * 0.01
        # 心境等级与天时环境提供额外成功率修正
        mental_bonus = self.mental_state_manager.get_breakthrough_bonus()
        weather_bonus = self.weather_manager.get_breakthrough_bonus()
        # 心法与神通带来的突破加成
        mind_method_bonus = self.mind_method_manager.get_breakthrough_bonus()
        divine_effects = self.divine_art_manager.get_effects()
        divine_art_bonus = divine_effects.get("breakthrough_bonus", 0.0)
        rate += mental_bonus + weather_bonus + mind_method_bonus + divine_art_bonus
        rate = min(rate, 0.95)  # 最高不超过 95%

        # 大境界渡劫：成功率降低 20%，失败惩罚更重
        if is_major:
            rate = max(0.05, rate - 0.20)

        # 检查是否有对应突破丹药并自动服用
        pill_boost = 0.0
        consumed_pill_name = None
        for item in list(self.player.inventory):
            if item.type != "pill":
                continue
            boost_target = item.effects.get("breakthrough_boost")
            boost_rate = item.effects.get("boost_rate", 0.0)
            if boost_target == self.player.realm_id:
                pill_boost = boost_rate
                self.player.remove_item(item)
                consumed_pill_name = item.name
                break

        if is_major:
            self.notify(
                f"[red]你引动【{tribulation_name}】，乌云翻滚、雷光隐现！"
            )
            if consumed_pill_name:
                rate = min(0.95, rate + pill_boost)
                self.notify(
                    f"[green]你提前服下【{consumed_pill_name}】，渡劫成功率提升 {int(pill_boost * 100)}%！"
                )
            # 触发渡劫开始弹窗（心魔劫小游戏 / 雷劫动画）
            # UI 弹窗关闭后会写回 self.tribulation_bonus
            self.tribulation_bonus = 0.0
            self.notify(f"__TRIBULATION_START__:{tribulation_name}:{rate:.2f}")
            rate = min(0.95, rate + self.tribulation_bonus)

        success = random.random() < rate

        # 大境界渡劫结束后通知 UI 播放结果动画
        if is_major:
            result_flag = "success" if success else "fail"
            self.notify(f"__TRIBULATION_RESULT__:{result_flag}:{tribulation_name}")

        # 维度①：大境界突破且心魔值过高 → 强制触发心魔劫幻境（UI 异步展示抉择）
        if is_major and self.is_feature_enabled("heart_demon"):
            trigger = self.mental_state_manager.should_trigger_heart_demon_tribulation()
            # 维度③：生活流派精熟可化解心魔之劫
            if trigger and self.is_feature_enabled("hundred_schools"):
                if self.hundred_schools_manager.should_mitigate_heart_demon_tribulation():
                    trigger = False
                    self.notify("[cyan]生活流派精熟，心魔之劫被悄然化解。")
            if trigger:
                scenario = self.mental_state_manager.get_heart_demon_tribulation_scenario()
                if scenario:
                    self.pending_heart_demon_scenario = scenario
                    self.notify(f"__HEART_DEMON_TRIBULATION__:{scenario['id']}")

        # 突破结果影响道心与心魔
        self.mental_state_manager.on_breakthrough(success)

        if success:
            # 突破成功
            self.player.realm_id = next_id
            self.player.qi = 0
            new_realm = self.world.get_realm(next_id)
            self.player.max_lifespan += new_realm["lifespan_bonus"]

            # 大境界成功额外奖励：生命上限、攻防小幅提升
            if is_major:
                self.player.max_health += 20
                self.player.health += 20
                self.player.base_attack += 5
                self.player.base_defense += 2
                # 大境界突破后尝试按 境界/流派/性别 匹配更丰富的头像资源
                # （玩家捏过脸/拼装过形象则不自动替换，尊重自定义形象）
                customized = (getattr(self.player, "face_traits", None)
                              or getattr(self.player, "face_params", None))
                if customized:
                    self.notify("[cyan]大境界突破，如需更新立绘可前往捏脸界面重新生成。")
                else:
                    higher_portrait = find_best_portrait_resource(self.player)
                    if higher_portrait and higher_portrait != self.player.portrait:
                        self.player.portrait = higher_portrait
                        self.notify(f"[cyan]大境界突破，头像已自动切换为高阶立绘。")
                # 开启头像光效边框，持续 12 个月
                self.player.portrait_glow_until_month = self._world_total_months() + 12
                self.notify(
                    f"[gold]渡劫成功！你抗过【{tribulation_name}】，踏入【{new_realm['name']}】！\n"
                    f"寿元增加 {new_realm['lifespan_bonus']} 年，肉身经雷劫洗礼，"
                    f"生命上限 +20、攻击 +5、防御 +2。"
                )
            else:
                self.notify(
                    f"突破成功！你踏入【{new_realm['name']}】，寿元增加 {new_realm['lifespan_bonus']} 年。"
                )

            # 检查并解锁新境界功能
            feature_name = self.player.check_realm_feature_unlock(next_id)
            if feature_name:
                self.notify(f"[cyan]你领悟了【{feature_name}】！")

            # 记录年表与成就
            self.chronicle_manager.record(
                f"突破至【{new_realm['name']}】", category="breakthrough"
            )
            unlocked = self.achievement_manager.check(
                "breakthrough", realm_id=next_id
            )
            for aid, name in unlocked:
                self.notify(f"[gold]达成成就：【{name}】！")
                self.chronicle_manager.record(
                    f"达成成就【{name}】", category="achievement"
                )

            # F-06 难度系统：地狱难度的大境界突破触发天道追杀
            if self.is_feature_enabled("achievement_tier"):
                self.difficulty_manager.on_breakthrough(self, self.player, is_major)

            self._check_main_story()
            self._auto_save()
        else:
            # 突破失败
            if is_major:
                # 渡劫失败：修为跌落 50%，健康 -30，并伤及根基
                penalty = int(realm["max_qi"] * 0.5)
                self.player.qi -= penalty
                self.player.health -= 30
                self.notify(
                    f"[red]渡劫失败！你被【{tribulation_name}】反噬，"
                    f"修为跌落 {penalty} 点，健康大幅下降，需调养数月再战。"
                )
            else:
                penalty = int(realm["max_qi"] * 0.3)
                self.player.qi -= penalty
                self.player.health -= 15
                self.notify(f"突破失败，修为跌落 {penalty} 点，健康下降。")

        self._check_death()
        self._advance_tutorial("breakthrough")

    # ==================== 地图与游历 ====================

    def get_current_location(self):
        """获取玩家当前所在地点配置。"""
        return self.world.get_location(self.player.location_id)

    def is_location_unlocked(self, location_id):
        """判断地点是否已解锁。"""
        location = self.world.get_location(location_id)
        if not location:
            return False

        if not location.get("locked", False):
            return True

        req = location.get("unlock_requirement", {})
        quest_id = req.get("quest")
        if quest_id:
            return quest_id in self.player.completed_quests
        return False

    def travel(self, location_id, use_teleport=False, use_spirit_stones=0):
        """玩家前往另一个地点，支持传送阵、御剑飞行、坐骑与灵石加速。"""
        location = self.world.get_location(location_id)
        if not location:
            self.notify("目的地不存在。")
            return

        if location_id == self.player.location_id:
            self.notify(f"你已经在【{location['name']}】了。")
            return

        if not self.is_location_unlocked(location_id):
            req = location.get("unlock_requirement", {})
            quest_id = req.get("quest")
            quest = self.quest_library.get(quest_id) if quest_id else None
            self.notify(f"【{location['name']}】尚未解锁，需完成任务：{quest.name if quest else quest_id}")
            return

        # 若选择使用传送阵，先尝试传送
        if use_teleport:
            ok, msg = self.teleport_manager.teleport(location_id)
            if not ok:
                self.notify(f"[red]{msg}")
                return
            self.notify(f"[cyan]{msg}")
        else:
            # 使用 TravelCostModel 统一计算移动方式与耗时
            cost = self.travel_cost_model
            if cost.can_flight():
                self.player.location_id = location_id
                self.notify(f"[cyan]你御剑而行，转瞬即至【{location['name']}】")
            elif cost.has_mount():
                self.player.location_id = location_id
                self.notify("[cyan]灵兽带你疾行，赶路不再耗时。")
            else:
                months = cost.calculate_base_time(location_id)
                months, consumed, messages = cost.apply_speedups(
                    months, use_spirit_stones=use_spirit_stones
                )
                for msg in messages:
                    self.notify(f"[cyan]{msg}")

                # 逐月推进，保证每月月度结算恰好执行一次（与 cultivate 一致）
                for _ in range(months):
                    self.world.advance(1)
                    self.player.add_age_months(1)
                    self._check_sect_daily_reset()
                    self._run_registered_monthly_ticks()
                self.notify(f"你赶路 {months} 个月，抵达【{location['name']}】")
                # 移动完成后再更新玩家位置
                self.player.location_id = location_id
        self.notify(f"你抵达了【{location['name']}】。{location['description']}")
        # 检查是否有可结算的藏宝图
        pending_maps = self.treasure_map_manager.get_pending_maps()
        if pending_maps:
            for idx, tm in pending_maps:
                self.notify(f"[yellow]你身上的藏宝图在此地产生了感应（{tm['hint']}）！")
        # 更新探索类宗门任务进度
        self.sect_manager.update_task_progress("explore", location_id, 1)
        # 触发抵达地点事件钩子
        self._on_travel(location_id)
        # 检查动态世界事件产生的敌人遭遇
        encounter = self.world_event_manager.get_encounter_for_location(location_id)
        if encounter:
            enemy_data = self.enemy_library.get(encounter["enemy_id"])
            if enemy_data:
                enemy = Enemy.from_dict(enemy_data)
                self.notify(f"[red]你遭遇了事件敌人【{enemy.name}】！")
                # 若事件敌人出现在城池中，则视为城池防卫战
                is_city_defense = location.get("type") == "city"
                self.start_combat(enemy, is_city_defense=is_city_defense)
                self.world_event_manager.remove_encounter(encounter)
        # 检查是否有 NPC 因动态条件出现在此地
        dynamic_npcs = self.check_dynamic_npcs(location_id)
        for npc in dynamic_npcs:
            self.notify(f"[yellow]你在此地偶遇了【{npc.name}】。")
        # 进入宗门领地时检查是否被追杀
        if location.get("type") == "sect":
            self.check_sect_hunt()
        self._auto_save()
        self._check_death()

    # ==================== 城池建筑交互 ====================

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

    def compute_reincarnation_options(self):
        """
        计算转世时可用的继承选项与点数。

        返回字典，包含 points、karma_category、options 等。
        """
        return self.reincarnation_manager.compute_available_options()

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
            "negative_event": (
                new_data["negative_event"]["name"]
                if new_data["negative_event"]
                else None
            ),
        }
        return new_player, summary

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
        qi = reward.get("qi", 0)
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

    def use_item(self, item):
        """使用一个物品，丹药/功法消耗，装备则穿戴。"""
        if item not in self.player.inventory:
            self.notify("背包中没有该物品。")
            return False

        # 装备类物品：直接装备（含本命法宝）
        if item.type in self.player.EQUIPMENT_SLOTS or (
            item.type == "life_treasure" and self.player.has_feature("life_treasure")
        ):
            old = self.player.equip_item(item)
            if old is None and item.type == "life_treasure":
                self.notify("你尚未解锁本命法宝槽位，无法装备。")
                return False
            msg = f"你装备了【{item.name}】。"
            if old:
                msg += f" 替换下来的【{old.name}】放回背包。"
            self.notify(msg)
            return True

        effects = item.effects
        if not effects:
            self.notify(f"【{item.name}】无法直接使用。")
            return False

        # 处理功法类：可能学会技能
        if "skill" in effects:
            skill_id = effects["skill"]
            if self.player.learn_skill(skill_id):
                skill_name = self.skill_library.get(skill_id).name
                self.notify(f"你研读【{item.name}】，习得技能「{skill_name}」！")
                # 触发习得技能事件钩子
                self._on_learn_skill(skill_id)
            else:
                self.notify(f"你已经会这个技能了。")
            # 功法使用后消耗
            self.player.remove_item(item)
            return True

        # 处理丹方类：学会一条炼丹配方
        if item.type == "recipe":
            recipe_id = item.id
            if recipe_id in self.player.learned_recipes:
                self.notify(f"你已经掌握了【{item.name}】的内容。")
                return False
            # 校验配方是否真实存在
            recipe = self.world.get_recipe(recipe_id)
            if not recipe:
                self.notify(f"【{item.name}】上的内容已经模糊不清，无法学习。")
                return False
            self.player.learned_recipes.append(recipe_id)
            self.notify(f"你研读【{item.name}】，学会了炼制「{recipe['name']}」！")
            # 丹方使用后消耗
            self.player.remove_item(item)
            self._auto_save()
            return True

        # 处理洗髓丹：觉醒一项新的灵根属性
        if effects.get("awaken_root"):
            # 所有五行属性
            all_elements = ["metal", "wood", "water", "fire", "earth"]
            # 玩家尚未拥有的属性（融合灵根已包含的属性不应重复觉醒）
            expanded = getattr(self.player, "expanded_elements", self.player.spiritual_roots)
            remaining = [e for e in all_elements if e not in expanded]
            if not remaining:
                # 已经五行俱全，无法继续觉醒
                self.notify(f"你已五行灵根俱全，【{item.name}】无法再觉醒新的灵根。")
                return False
            # 随机选一项未觉醒的属性
            new_element = random.choice(remaining)
            old_roots = list(self.player.spiritual_roots)
            old_mult = self.player.cultivation_multiplier
            # 觉醒新灵根（set_spiritual_roots 会自动重算修炼倍率）
            new_roots = old_roots + [new_element]
            # 保留已有灵根纯度，为新灵根生成纯度（基于新灵根数量）
            new_purities = dict(getattr(self.player, "root_purities", {}))
            # 灵根数量 → 纯度范围
            purity_ranges = {
                1: [1.1, 1.5], 2: [0.9, 1.2], 3: [0.8, 1.1],
                4: [0.7, 1.0], 5: [0.6, 0.9],
            }
            min_p, max_p = purity_ranges.get(len(new_roots), [0.8, 1.0])
            new_purities[new_element] = round(random.uniform(min_p, max_p), 2)
            self.player.set_spiritual_roots(new_roots, new_purities)
            new_mult = self.player.cultivation_multiplier
            elem_cn = ELEMENT_NAMES.get(new_element, new_element)
            purity_val = new_purities[new_element]
            self.notify(
                f"你服下【{item.name}】，丹药之力洗髓伐骨，"
                f"觉醒了【{elem_cn}】灵根（纯度 {purity_val}）！"
                f"（修炼倍率 {old_mult}x → {new_mult}x）"
            )
            # 洗髓丹使用后消耗
            self.player.remove_item(item)
            self._auto_save()
            # 若觉醒后五行俱全，检查解锁阵法技能
            self.check_formation_unlock()
            return True

        # 应用常规效果
        if "qi" in effects:
            self.player.qi += effects["qi"]
        if "health" in effects:
            self.player.health += effects["health"]
            self.player.health = min(self.player.health, self.player.max_health)
        if "wisdom" in effects:
            self.player.wisdom += effects["wisdom"]
        if "constitution" in effects:
            self.player.constitution += effects["constitution"]
        if "luck" in effects:
            self.player.luck += effects["luck"]
        # 维度①② 联动：道心提振 / 心魔消解（钳制 0-100）
        if "mental_state" in effects:
            ms = getattr(self.player, "mental_state", 50)
            self.player.mental_state = max(0, min(100, ms + effects["mental_state"]))
        if "heart_demon" in effects:
            hd = getattr(self.player, "heart_demon", 0)
            self.player.heart_demon = max(0, min(100, hd + effects["heart_demon"]))
        # 维度③·M18：丹道「灵力温养」持续修炼增益（服用丹药后每月额外修为）
        if "cultivation_boost" in effects:
            cb = effects["cultivation_boost"]
            self.player.cultivation_boost_months = int(cb.get("months", 0))
            self.player.cultivation_boost_amount = int(cb.get("amount", 0))

        # 丹药/消耗品使用后消耗（带效果的 consumable 不再无限复用）
        if item.type in ("pill", "consumable"):
            self.player.remove_item(item)

        self.notify(f"你使用了【{item.name}】，{item.description}")
        self._check_death()
        return True

    def unequip_item(self, slot):
        """卸下指定槽位的装备。"""
        item = self.player.unequip_item(slot)
        if item:
            self.notify(f"你卸下了【{item.name}】。")
            return True
        return False

    def craft(self, recipe_id):
        """根据配方合成物品。"""
        recipe = self.world.get_recipe(recipe_id)
        if not recipe:
            self.notify("配方不存在。")
            return False

        # 检查材料是否足够
        materials = recipe["materials"]
        for item_id, count in materials.items():
            if self.player.count_item(item_id) < count:
                item_name = self.item_library.get(item_id).name
                self.notify(f"材料不足：{item_name} 需要 {count} 个。")
                return False

        # 消耗材料
        for item_id, count in materials.items():
            self.player.consume_items(item_id, count)

        # 生成产物
        result = recipe["result"]
        item_id = result["item_id"]
        count = result.get("count", 1)
        for _ in range(count):
            item = self.item_library.create(item_id)
            self.player.add_item(item)

        item_name = self.item_library.get(item_id).name
        self.notify(f"合成成功！获得 {item_name} x{count}。")
        # 合成获得物品也可能推进宗门收集任务
        self.sect_manager.update_task_progress("collect", item_id, count)
        # 触发获得物品事件钩子
        self._on_gain_item(item_id, count)
        self._auto_save()
        return True

    def craft_pill(self, recipe_id):
        """在炼丹阁炼丹，成功率受丹方、流派、悟性与炼丹室等级影响。

        为了保持与旧版 AlchemyDialog 的兼容，仍返回是否进入炼制流程，
        实际逻辑已委托给 AlchemyManager，并统一推进 7 日时间。
        """
        success, message, produced = self.alchemy_manager.craft(recipe_id)
        self.notify(message)
        if success and produced:
            product_id = produced[0].id
            total_count = sum(item.count for item in produced)
            self.sect_manager.update_task_progress("collect", product_id, total_count)
            self._on_gain_item(product_id, total_count)
        # 炼丹耗费 7 日（天级推进；不跨月则不推进年龄，跨月由下方钩子处理月度重置）
        self.world.advance(days=7)
        self._check_sect_daily_reset()
        self._auto_save()
        return success

    def open_alchemy_shop(self):
        """打开炼丹阁专属商店，根据建筑等级解锁丹方。"""
        from game.npc import NPC
        # 基础材料始终出售
        shop_items = ["low_herb", "spirit_liquid", "century_herb"]
        # 根据炼丹阁等级解锁丹方
        effects = self.building_manager.get_current_effects("alchemy_pavilion")
        unlock_recipes = effects.get("unlock_recipes", [])
        shop_items.extend(unlock_recipes)

        merchant = NPC(
            npc_id="alchemy_pavilion_keeper",
            name="炼丹阁管事",
            location=self.player.location_id,
            description="炼丹阁管事，手中握着不少珍稀丹方。",
            dialog="道友是来买丹方，还是采购材料？",
            quests=[],
            shop_items=shop_items,
            buy_multiplier=1.0,
            sell_multiplier=0.6,
        )
        return merchant

    # ==================== 演武场系统 ====================

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

    def get_skill_success_rate(self, skill_id):
        """计算技能施展成功率。满足境界时为 1.0，否则随境界差递减。"""
        skill = self.skill_library.get(skill_id)
        if not skill or not skill.realm_id:
            return 1.0
        required_order = self.player.REALM_ORDER.get(skill.realm_id, 0)
        player_order = self._get_realm_order()
        diff = required_order - player_order
        if diff <= 0:
            return 1.0
        # 每低一个大境界成功率下降 25%，最低保留 10% 强行施展可能
        return max(0.1, 1.0 - diff * 0.25)

    def get_skill_usability(self, skill_id, in_combat=True):
        """检查技能是否可用，返回 (can_use: bool, reasons: list[str])。

        境界不足不再完全禁用，而是作为风险提示（含成功率），
        战斗中仍可选择强行施展，失败时会受到反噬。
        """
        reasons = []
        skill = self.skill_library.get(skill_id)
        if not skill:
            return False, ["技能不存在"]

        # 是否已习得
        if skill_id not in self.player.skills:
            return False, ["尚未习得该技能"]

        # 战斗中冷却判断
        if in_combat and self.player.get_skill_cooldown(skill_id) > 0:
            cd = self.player.get_skill_cooldown(skill_id)
            reasons.append(f"冷却中（{cd} 回合）")

        # 真气消耗（考虑熟练度减耗）
        effective_cost = self._get_effective_qi_cost(skill_id)
        if self.player.qi < effective_cost:
            reasons.append(f"真气不足（{self.player.qi}/{effective_cost}）")

        # 灵根属性
        if not self.player.has_element(skill.element):
            elem_cn = ELEMENT_NAMES.get(skill.element, skill.element)
            reasons.append(f"需要{elem_cn}属性灵根")

        # 境界要求：不足时提示成功率，仍允许尝试施展
        if skill.realm_id:
            required_order = self.player.REALM_ORDER.get(skill.realm_id, 0)
            if self._get_realm_order() < required_order:
                realm_data = self.world.get_realm(skill.realm_id)
                realm_name = realm_data.get("name", skill.realm_id) if realm_data else skill.realm_id
                rate = self.get_skill_success_rate(skill_id)
                reasons.append(f"境界不足（需{realm_name}，成功率 {int(rate * 100)}%）")

        # 流派专属
        if skill.path_exclusive and self.player.cultivation_path != skill.path_exclusive:
            path_names = {
                "fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
                "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
                "zhen": "阵修", "fu": "符修",
            }
            reasons.append(f"{path_names.get(skill.path_exclusive, skill.path_exclusive)}专属")

        # 剑修武器要求
        if skill.path_exclusive == "jian" and not self._player_has_sword():
            reasons.append("需要装备剑类武器")

        # 境界不足仅作为风险提示，不算作硬禁用
        hard_reasons = [r for r in reasons if "成功率" not in r]
        return len(hard_reasons) == 0, reasons

    # ==================== 商店系统 ====================

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

    def get_buy_price(self, item_id, npc=None):
        """
        计算购买价格 = 物品价值 × NPC 购买倍率 × 好感度折扣 × 关系网修正 × 阵营偏好修正 × 宗门关系修正 × 地点类型修正 × 节日折扣。
        好感度越高，购买越便宜；与 NPC 好友关系好也会降价，与敌人关系好则会加价。
        最终倍率限制在合理区间，防止极端价格。
        """
        item = self.item_library.get(item_id)
        if not item:
            return 0
        base_buy, _ = self.economy_config.get_base_multipliers()
        # 基础购买倍率
        multiplier = getattr(npc, "buy_multiplier", base_buy) if npc else base_buy
        # 好感度折扣
        buy_adjust, _ = self._get_relationship_discount(npc)
        # 宗门关系带来的价格波动（友好降价、敌对加价）
        sect_buy_mult, _ = self.get_sect_price_multiplier(npc)
        # NPC 关系网修正（朋友/敌人）
        rel_buy_mult, _ = npc.get_relationship_price_adjustment(self.player, self.npc_library) if npc else (1.0, 1.0)
        # 阵营偏好修正
        camp_mult = npc.get_faction_price_multiplier(self.player.get_camp()) if npc else 1.0
        # 地点类型修正（城市/宗门/荒野物价差异）
        loc_type_buy_mult = self._get_location_type_multiplier(npc, buy=True)
        final_multiplier = multiplier * buy_adjust * sect_buy_mult * rel_buy_mult * camp_mult * loc_type_buy_mult
        # 节日期间额外折扣：仅当 NPC 配置了当前节日的特殊对话时才生效
        current_festival = self.world.get_current_festival()
        if npc and current_festival:
            has_festival_dialog = any(
                entry.get("festival_id") == current_festival
                for entry in npc.festival_dialogs
            )
            if has_festival_dialog:
                final_multiplier *= self.economy_config.get_festival_discount()
        # 动态世界事件带来的地点价格修正
        if npc:
            location_id = getattr(npc, "current_location", None) or getattr(npc, "location", None)
            mods = self.player.world_event_price_mods.get(location_id)
            if mods:
                final_multiplier *= mods.get("buy_mult", 1.0)
        # 限制购买倍率在合理区间，避免经济失衡
        limits = self.economy_config.get_price_limits()
        buy_min = limits.get("buy_min", 0.75)
        buy_max = limits.get("buy_max", 3.0)
        final_multiplier = max(buy_min, min(buy_max, final_multiplier))
        return max(1, int(item.value * final_multiplier))

    def get_sell_price(self, item, npc=None):
        """
        计算出售价格 = 物品价值 × NPC 出售倍率 × 好感度加成 × 关系网修正 × 宗门关系修正 × 地点类型修正。
        好感度越高，出售价越高；敌对宗门会压低收购价，友好宗门则提高。
        最终倍率限制在合理区间，确保玩家无法通过倒卖无限获利。
        """
        _, base_sell = self.economy_config.get_base_multipliers()
        multiplier = getattr(npc, "sell_multiplier", base_sell) if npc else base_sell
        _, sell_adjust = self._get_relationship_discount(npc)
        _, sect_sell_mult = self.get_sect_price_multiplier(npc)
        _, rel_sell_mult = npc.get_relationship_price_adjustment(self.player, self.npc_library) if npc else (1.0, 1.0)
        # 地点类型修正
        loc_type_sell_mult = self._get_location_type_multiplier(npc, buy=False)
        final_multiplier = multiplier * sell_adjust * sect_sell_mult * rel_sell_mult * loc_type_sell_mult
        # 动态世界事件带来的地点价格修正
        if npc:
            location_id = getattr(npc, "current_location", None) or getattr(npc, "location", None)
            mods = self.player.world_event_price_mods.get(location_id)
            if mods:
                final_multiplier *= mods.get("sell_mult", 1.0)
        # 限制出售倍率，让高好感 NPC 愿意提高收购价，同时仍低于最低购买价
        limits = self.economy_config.get_price_limits()
        sell_min = limits.get("sell_min", 0.2)
        sell_max = limits.get("sell_max", 0.7)
        final_multiplier = max(sell_min, min(sell_max, final_multiplier))
        return max(1, int(item.value * final_multiplier))

    def _get_location_type_multiplier(self, npc, buy=True):
        """根据 NPC 当前所在地点类型返回价格修正倍率。"""
        if not npc:
            return 1.0
        # 优先使用当前实际位置，否则使用默认归属地点
        location_id = getattr(npc, "current_location", None) or getattr(npc, "location", None)
        if not location_id:
            return 1.0
        loc = self.world.get_location(location_id)
        if not loc:
            return 1.0
        loc_type = loc.get("type", "wild")
        buy_mult, sell_mult = self.economy_config.get_location_type_modifier(loc_type)
        return buy_mult if buy else sell_mult

    def check_dynamic_npcs(self, location_id=None):
        """
        检查满足动态出现条件的 NPC，并筛选出在指定地点或玩家当前地点的 NPC。
        返回 NPC 对象列表（不重复）。
        """
        candidates = self.npc_library.get_dynamic_spawn_candidates(self.player, self.world)
        target = location_id or self.player.location_id
        result = []
        for npc in candidates:
            locations = npc.dynamic_spawn.get("locations", [])
            # 未指定具体地点则默认使用 NPC 配置 location
            if not locations:
                locations = [npc.location]
            if target in locations:
                result.append(npc)
        return result

