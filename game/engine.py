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
from game.engine_combat_flow_mixin import CombatFlowMixin
from game.engine_city_life_mixin import CityLifeMixin
from game.engine_item_alchemy_mixin import ItemAlchemyMixin
from game.engine_cave_home_mixin import CaveHomeMixin
from game.engine_social_beast_mixin import SocialBeastMixin
from game.engine_quest_dialogue_mixin import QuestDialogueMixin

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


class GameEngine(EventMixin, EndingMixin, MainStoryMixin, CombatMixin, MentorMixin, SectMixin, CombatFlowMixin, CityLifeMixin, ItemAlchemyMixin, CaveHomeMixin, SocialBeastMixin, QuestDialogueMixin):
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
            self.player, self.item_library, world=self.world
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
            # 修为奖励已在 SideQuestManager.complete 中发放（内部已乘境界系数），这里同步缩放仅通知
            qi_reward = int(rewards.get("qi", 0) * self._realm_qi_scale())
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
            actual_gain = int(actual_gain * self._realm_qi_scale())
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

    def _realm_qi_scale(self):
        """境界成长系数：静态 qi 奖励/惩罚随境界放大（与 cultivate 收入同斜率）。

        背景：修为收入乘 (1 + order * 0.8) 后，固定值的事件/丹药/任务 qi 奖励
        在高境界会贬值到无感；统一乘本系数保持其相对意义（正负向同比例）。
        """
        realm = self.world.get_realm(self.player.realm_id)
        order = realm["order"] if realm else 1
        return 1 + order * 0.8

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


    def save_game(self, save_manager=None):
        """调用存档管理器保存游戏。"""
        sm = save_manager or self.save_manager
        if sm:
            sm.save(self.player, self.world)
            self.notify("游戏已保存。")

    # ==================== 通用 ====================

    def _check_death(self):
        """检查玩家是否寿元耗尽或健康归零。"""
        if self.player.health <= 0 or self.player.age >= self.player.max_lifespan:
            # 维度⑤：若已安排坐化后事，则在身死时转化为前世遗产
            if getattr(self.player, "sit_pending", False) and self.is_feature_enabled(
                "lifespan_reincarnation"
            ):
                for line in self.lifespan_manager.on_death():
                    self.notify(f"[magenta]{line}")
            if self.player.health <= 0:
                self.chronicle_manager.record(
                    f"{self.player.age} 岁时重伤陨落", category="death"
                )
                self.notify("你身受重伤，道消身殒。")
            else:
                self.chronicle_manager.record(
                    f"{self.player.age} 岁时寿元耗尽", category="death"
                )
                self.notify("你寿元耗尽，化为一抔黄土。")
            # 判定死亡结局（红尘归隐 / 凡尘谢幕）
            self._trigger_ending("death")

    # ==================== 宗门系统 ====================

    def start_world_boss_combat(self, boss_id):
        """
        开启世界 BOSS 战斗。
        生成 BOSS 敌人并标记 pending_world_boss_id，战斗结束后据此发放奖励。
        """
        boss_cfg = self.world_boss_manager.config.get(boss_id)
        if not boss_cfg:
            self.notify("世界 BOSS 配置异常，无法进入战斗。")
            return False

        # 校验玩家境界是否满足挑战要求
        player_order = self.player.REALM_ORDER.get(self.player.realm_id, 0)
        min_order = boss_cfg.get("min_realm_order", 1)
        if player_order < min_order:
            self.notify("你的境界尚不足以挑战该世界 BOSS。")
            return False

        enemy = self.world_boss_manager.create_enemy(boss_id)
        if not enemy:
            self.notify("世界 BOSS 敌人数据异常，无法进入战斗。")
            return False

        self.pending_world_boss_id = boss_id
        self.notify(f"【世界 BOSS】你遭遇了 {boss_cfg['name']}！")
        self.start_combat(enemy)
        return True

    def finish_world_boss_combat(self, result):
        """世界 BOSS 战斗结束后结算奖励与击败状态。"""
        boss_id = getattr(self, "pending_world_boss_id", None)
        if not boss_id:
            return

        boss_cfg = self.world_boss_manager.config.get(boss_id)
        boss_name = boss_cfg["name"] if boss_cfg else "世界 BOSS"

        if result == "win":
            # 发放击败奖励
            reward_msgs, gained_names = self.world_boss_manager.grant_defeat_rewards(
                self.player, self.item_library, boss_id
            )
            self.world_boss_manager.defeat(boss_id)
            self.chronicle_manager.record(
                f"击败世界 BOSS【{boss_name}】", category="combat"
            )

            msg = f"【世界 BOSS】你成功击败【{boss_name}】！"
            if reward_msgs:
                msg += " " + "，".join(reward_msgs)
            if gained_names:
                msg += " 获得：" + "、".join(gained_names)
            self.notify(msg)
        else:
            self.notify(f"【世界 BOSS】你未能击败【{boss_name}】，它仍在世间游荡。")

        self.pending_world_boss_id = None
        self._auto_save()
        self.update_view()
