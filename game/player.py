from game.spiritual_root import SpiritualRootConfig
from game.item import Item


class Player:
    """玩家角色，保存修仙者的所有属性。"""

    # 存档版本号，用于旧存档迁移
    SAVE_VERSION = 1

    # 装备类型与槽位对应
    EQUIPMENT_SLOTS = ["weapon", "helmet", "armor", "accessory"]

    # 大境界突破阈值：到达这些境界后尝试突破时触发渡劫事件
    MAJOR_REALM_IDS = {"qi_refining_9", "foundation_peak", "golden_core_peak"}

    # 技能熟练度配置
    SKILL_PROFICIENCY_MAX_LEVEL = 10                # 最高等级
    SKILL_PROFICIENCY_EXP_PER_USE = 1               # 每次使用获得经验
    SKILL_PROFICIENCY_LEVEL_EXP = 3                 # 每级所需经验 = level * 该值
    SKILL_PROFICIENCY_DAMAGE_BONUS_PER_LEVEL = 0.05  # 伤害技能每级增伤 5%
    SKILL_PROFICIENCY_HEAL_BONUS_PER_LEVEL = 0.05    # 治疗技能每级增效 5%
    SKILL_PROFICIENCY_CONTROL_BONUS_PER_LEVEL = 0.03 # 控制技能每级成功率 +3%
    SKILL_PROFICIENCY_COST_REDUCE_PER_LEVEL = 0.03   # 每级减耗 3%
    SKILL_PROFICIENCY_SUPPORT_EXTRA_TURN_PER_LEVEL = 0.2 # 辅助技能每级延长 0.2 回合 buff
    SKILL_PROFICIENCY_DECAY_PER_COMBAT = 1              # 每场战斗未使用衰减 1 点经验
    # 满级特效概率与效果
    SKILL_PROFICIENCY_MAX_NO_COOLDOWN_CHANCE = 0.20 # 满级概率不进入冷却
    SKILL_PROFICIENCY_MAX_DAMAGE_DEBUFF_CHANCE = 0.25 # 满级伤害技能附加异常概率
    SKILL_PROFICIENCY_MAX_HEAL_CLEANSE_CHANCE = 0.30  # 满级治疗技能净化概率
    SKILL_PROFICIENCY_MAX_CONTROL_EXTRA_TURN = 1      # 满级控制技能额外持续回合

    # 境界功能解锁阈值（key 为境界 ID，value 为功能标识）
    FEATURE_UNLOCK_REALMS = {
        "foundation_early": "flight",       # 筑基初期：御剑飞行
        "golden_core_early": "life_treasure",  # 金丹初期：本命法宝
        "nascent_soul": "nascent_soul_revive",  # 元婴期：元婴替死
    }

    # 境界顺序表（用于旧存档兼容时判断高低境界）
    REALM_ORDER = {
        "qi_refining_1": 1, "qi_refining_2": 2, "qi_refining_3": 3,
        "qi_refining_4": 4, "qi_refining_5": 5, "qi_refining_6": 6,
        "qi_refining_7": 7, "qi_refining_8": 8, "qi_refining_9": 9,
        "foundation_early": 10, "foundation_mid": 11, "foundation_late": 12, "foundation_peak": 13,
        "golden_core_early": 14, "golden_core_mid": 15, "golden_core_late": 16, "golden_core_peak": 17,
        "nascent_soul": 18,
    }

    def __init__(self, name="无名"):
        # 基础信息
        self.name = name              # 道号
        self.save_version = self.SAVE_VERSION  # 存档版本号
        self.portrait = "assets/portraits/protagonist_default.png"  # 主角头像路径
        self.gender = "male"          # 性别：male/female，用于生成立绘等
        self.realm_id = "qi_refining_1"  # 当前境界 ID
        self.tutorial_step = 0  # 新手引导进度：已完成的引导步骤数（0 表示未开始，>= 总步数表示完成）
        # 大境界突破后的头像光效边框持续到第几个月（按世界总月份计算）
        self.portrait_glow_until_month = 0

        # 修为与寿元
        self.qi = 0                   # 当前修为
        self.age = 16                 # 当前年龄（显示用）
        self.age_months = 0           # 总月数，用于精确计算
        self.max_lifespan = 100       # 最大寿元（年）

        # 资质属性
        self.wisdom = 5               # 悟性：影响修炼速度
        self.constitution = 5         # 根骨：影响突破成功率
        self.luck = 5                 # 机缘：影响奇遇概率

        # 战斗属性
        self.base_attack = 10         # 基础攻击力
        self.base_defense = 2         # 基础防御力
        self.health = 100             # 当前健康值
        self.max_health = 100         # 最大健康值

        # 背包：里面存放 Item 对象
        self.inventory = []

        # 装备栏：键为槽位类型，值为 Item 对象或 None
        self.equipment = {
            "weapon": None,
            "helmet": None,
            "armor": None,
            "accessory": None,
        }

        # 境界解锁的特殊能力集合（如 "flight", "life_treasure", "nascent_soul_revive"）
        self.unlocked_features = set()
        # 元婴替死是否已在当前战斗中使用过（每场战斗重置）
        self.nascent_soul_revive_used = False
        # 元婴受损状态：替死后全属性下降 10%，持续若干月
        self.nascent_soul_weakened = False
        self.weakened_remaining_months = 0
        # 神识扫描目标：探索时发现的 BOSS/敌人弱点，下一场对其战斗伤害 +20%
        self.sense_scan_target = None

        # 心境 / 道心系统
        self.mental_state = 50        # 道心值 0-100，50 为平常心
        self.heart_demon = 0          # 心魔值 0-100
        self.mental_state_traits = [] # 已领悟的心境特质
        self.personality_tags = []    # 心魔劫幻境抉择塑造的性格标签（冷酷/慈悲/忠诚…）
        self.tribulation_effects = {} # 幻境抉择对后续事件概率的永久修正（key->delta）

        # 洞府系统
        self.residence = None         # 当前拥有的洞府，结构见 residence.py

        # 道侣系统
        self.companions = []          # 道侣列表，元素为 {npc_id, intimacy, is_alive, last_dual_month}

        # 心法系统
        self.learned_mind_methods = []  # 已学习心法 ID 列表
        self.equipped_mind_method = None  # 当前装备的心法 ID

        # 炼丹系统
        self.learned_recipes = []     # 已习得丹方 ID 列表

        # 演武场系统
        self.arena_streak = 0         # 当前连胜次数
        self.arena_best_streak = 0    # 最高连胜次数
        self.arena_daily_claimed = False  # 今日是否已领取演武场每日奖励
        self.arena_last_date = None   # 上次战斗/领奖日期 "year-month-day"
        self.arena_rank = 0           # 当前城池擂台排名（0 表示未上榜）
        self.arena_daily_challenges = 0  # 今日已挑战次数

        # 神通/法则系统
        self.divine_arts = []         # 已领悟神通 ID 列表
        self.enlightenment_points = 0  # 悟道点

        # 灵根觉醒/变异
        self.awakened_roots = []      # 已觉醒灵根属性
        self.mutated_roots = []       # 已变异灵根属性（如雷、冰）

        # 灵植种植系统
        self.farm_plots = []          # 洞府药园地块列表，元素为 dict 或 None

        # 灵兽养殖（与 sect_manager 的 beasts 区分，这是玩家个人驯养的灵兽）
        self.personal_beasts = []     # 元素为 {beast_id, name, growth, loyalty, type}

        # 委托悬赏
        self.active_bounties = []     # 已接取的悬赏任务列表

        # 城池动态任务
        self.city_quest_pool = []     # 当前城池可接任务列表（dict）
        self.active_city_quests = {}  # 已接取的城池任务：{quest_id: progress}

        # 成就系统
        self.achievements = []        # 已完成成就 ID 列表
        self.achievement_progress = {}  # 成就进度缓存

        # 历史年表
        self.chronicle = []           # 年表条目列表

        # 动态世界事件
        self.active_world_events = {}  # {event_id: state}
        self.world_event_history = {}  # {event_id: {"ended_month": int}}
        self.world_event_encounters = []  # 待触发的事件遭遇列表
        self.world_event_price_mods = {}  # {location_id: {"buy_mult": float, "sell_mult": float}}

        # F-04 动态世界事件深化：全局世界状态与事件链
        self.world_state = {}             # 全局状态变量（灵气/安全度/物价/阵营态度/魔气）
        self.active_event_chains = {}     # 活跃事件链 {chain_id: state}
        self.world_event_chain_history = {}  # 已结束事件链 {chain_id: {"ended_month": int}}

        # 支线任务
        self.active_side_quests = {}  # 活跃支线任务 {quest_id: state}
        self.completed_side_quests = []  # 已完成支线任务 ID 列表

        # 势力声望
        self.reputation = {}          # {rep_id: value}

        # 探索相关
        self.unlocked_secret_realms = []  # 已解锁秘境 ID 列表
        self.explored_ruins = {}      # {ruin_id: last_explored_month}
        self.unlocked_teleports = []  # 已解锁传送阵地点 ID 列表

        # Roguelike 秘境（F-03）
        self.realm_coins = 0  # 秘境币（跨周目保留，可兑换稀有物品）
        self.realm_compendium = {"cards": [], "bosses": [], "events": []}  # 秘境图鉴
        self.family = None  # 修仙家族状态（dict）；None 表示未创立家族（F-01）
        self.territory = None  # 领地建设状态（dict）；None 表示未占据领地（F-02）
        # F-06 成就分级 / 难度
        self.titles = []                  # 已获得称号列表（带属性）
        self.title_bonuses = {}           # 称号累计属性加成
        self.unlocked_hidden_events = []  # 成就解锁的隐藏事件 id
        self.difficulty = "normal"        # 当前难度 id
        self.difficulty_modifiers = {     # 难度修正系数
            "enemy_strength": 1.0, "player_combat": 1.0,
            "production_mult": 1.0, "exp_mult": 1.0, "drop_mult": 1.0,
        }
        # F-07 多周目模式
        self.game_mode = "standard"       # 当前周目模式 id
        self.allowed_paths = []           # 限制可选流派（空=不限）
        self.no_spiritual_roots = False   # 凡人挑战：无灵根
        self.hostile_factions = []        # 敌对阵营（如正道）
        self.meta_modifiers = {}          # 模式跨周目修正（exp_mult/enemy_strength）
        self.pending_start_items = []     # 开局应发放的物品 id
        # 维度④ 天道反噬（F-08）：天道注视值 0-100
        self.heaven_gaze = 0
        # 维度⑤ 寿元与轮回晚年（F-09）
        self.sit_pending = False          # 已安排坐化后事
        self.past_life_arrangements = None  # 坐化安排 {heir/leave_manual/detonate_treasure}
        self.remnant_soul = None          # 残魂状态 {host_type, host_id} 或 None
        self.is_remnant = False           # 是否以残魂 / 器灵之姿存续
        self.remnant_months = 0           # 残魂存续月数
        self.past_life_relics = []        # 前世遗物列表（本世收集，转世即清零，仅作叙事）
        self.relic_chain = []             # 前世遗物链：跨世累积的遗物 id 集合（转世保留，驱动链之加持）
        # 维度② 红尘炼心 / 入世（F-08 体验深化）
        self.red_dust_active = False          # 是否正在入世历练
        self.red_dust_bonds = []              # 红尘羁绊列表 [{type,name,intimacy}]
        self.red_dust_months = 0              # 入世历练累计月数
        self.red_dust_pending_qingjie = None  # 待了断的情劫场景 dict

        # 维度③ 百家争鸣 / 非传统修仙路线
        self.founded_sect = None             # 已立宗门 dict：{name, founded_month, disciples, qi_yun}
        self.self_created_techniques = []    # 自创功法列表 [{name, school, attribute, level}]
        self.life_path = None                # 生活流派：alchemy/artifact/array/talisman
        self.life_path_proficiency = 0       # 生活流派精进度
        self.lifepath_auto_deploy = False    # 维度③·M15：战斗中自动部署自产法宝为增益
        # 维度③·M18：丹道「灵力温养」持续修炼增益（服用丹药后若干月每月额外修为）
        self.cultivation_boost_months = 0    # 剩余生效月数
        self.cultivation_boost_amount = 0    # 每月额外修为
        # 维度③·M19：功法推演进行中的临时状态（start→逐节点参悟→大成 前的中间态）
        self.pending_deduction = None        # {name, school, attribute, nodes, idx, quality, resolved}

        self.has_won = False              # 是否已通关（解锁天道轮回模式）
        self.ending_id = None             # 达成的结局 ID（飞升/死亡时判定）
        self.main_story_step = 0          # 主线剧情进度：已完成章节数
        self.face_traits = {}             # 捏脸特征选择（路线 B：AI 提示词捏脸）
        self.face_params = {}             # 拼装捏脸参数（路线 A：{层id: 部件id, "skin": 肤色id}）
        self.treasure_maps = []       # 藏宝图列表 {map_id, location_id, hint}
        self.location_event_cooldowns = {}  # {location_id: cooldown_month}
        self.world_boss_kills = []    # 击杀过的世界 BOSS ID 列表

        # 社交关系
        self.master_id = None         # 师父 NPC ID
        self.disciples = []           # 徒弟列表 {npc_id, name, realm_id, progress}
        self.sworn_brothers = []      # 结拜兄弟 NPC ID 列表
        self.revenge_targets = []     # 复仇目标 NPC ID 列表
        self.grudges = {}             # 恩怨链：{npc_id: {"level": int, "reason": str, "start_month": int}}
        self.killed_npcs = []         # 击杀过的 NPC ID 列表

        # 图鉴与信件
        self.bestiary = {}            # {enemy_id: kill_count}
        self.item_compendium = []     # 已收录物品 ID 列表
        self.skill_compendium = []    # 已收录技能 ID 列表
        self.letters = []             # 信件列表 {from_npc, content, year, month, read}
        self.heard_rumors = []        # 已听闻传闻 ID 列表

        # 战斗统计
        self.combat_stats = {         # 累计战斗数据
            "total_battles": 0,
            "wins": 0,
            "losses": 0,
            "total_damage_dealt": 0,
            "total_damage_taken": 0,
            "highest_damage": 0,
        }

        # 论道记录
        self.debate_record = {        # {npc_id: win_count, loss_count}
            "wins": 0,
            "losses": 0,
        }

        # 转生/轮回预留
        self.reincarnation_count = 0  # 转世次数
        self.karma = 0                # 因果业力
        self.past_life_talents = []   # 前世天赋
        # 转世带来的全局加成（百分比）
        self.reincarnation_cultivation_bonus = 0.0
        self.reincarnation_breakthrough_bonus = 0.0

        # 技能：已习得的技能 ID 列表
        self.skills = []
        # 技能冷却：键为技能 ID，值为剩余冷却回合数
        self.skill_cooldowns = {}
        # 技能熟练度：键为技能 ID，值为 {"level": int, "exp": int}
        self.skill_proficiency = {}

        # 任务追踪：键为任务 ID，值为当前进度
        self.quest_progress = {}
        # 已完成任务 ID 列表
        self.completed_quests = []

        # 对话系统标志位：键为 flag 名，值为任意可序列化值
        self.dialogue_flags = {}

        # 当前所在地点
        self.location_id = "qingyun"

        # NPC 好感度：键为 NPC ID，值为好感度等级（0-10）
        self.npc_relationships = {}
        # NPC 记忆：键为 NPC ID，值为 {"choices": {}, "last_visit": {"year", "month", "day"}, "visit_count": int}
        self.npc_memory = {}

        # 灵根属性：如 ["fire"] 或 ["metal", "water", "wood"]
        # 通过 set_spiritual_roots 初始化，自动展开融合灵根并缓存 expanded_elements
        self.set_spiritual_roots(["fire"])

        # 修炼流派：fa(法修)/ti(体修)/jian(剑修)/xie(邪修)，默认法修
        self.cultivation_path = "fa"
        # 流派属性修正字典（由 set_cultivation_path 设置）
        self.path_modifiers = {}

        # 流派专属资源（不同流派使用不同字段，初始为 0）
        self.shield_qi = 0       # 法修：真气护盾
        self.rage = 0            # 体修：怒气
        self.sword_intent = 0    # 剑修：剑意层数
        self.evil_qi = 0         # 邪修：邪气值
        self.dan_fire = 0        # 丹修：丹火（炼丹火候）
        self.qi_spirit = 0       # 器修：器灵（装备共鸣）
        self.shou_soul = 0       # 御兽修：兽魂（收服的兽数量）
        self.hun_sense = 0       # 魂修：神识（神魂力量）
        self.zhen_rune = 0       # 阵修：阵纹（阵法积累）
        self.fu_seal = 0         # 符修：符箓（可囤积的消耗品）
        # 已祭炼过的武器 ID 集合（器修专属，每件武器仅可祭炼一次）
        self.refined_weapon_ids = []

        # 宗门系统字段
        self.sect_id = None              # 所属宗门 ID
        self.sect_rank = "none"          # 当前职位：outer/inner/core/elder/leader/none
        self.sect_contribution = 0       # 宗门贡献
        self.sect_loyalty = 0            # 宗门忠诚度 0-100
        self.sect_tasks_today = 0        # 今日已完成宗门任务数
        self.sect_active_task = None     # 当前进行中的宗门任务 {task_id, progress}
        self.sect_war_participation = 0  # 宗门战参与次数
        self.sect_last_reset_year = 0    # 上次重置宗门每日任务的年份

        # 城池声望系统：{city_id: reputation}
        self.city_reputation = {}
        # 城池建筑等级：{building_id: level}
        self.building_levels = {}
        # 摆摊系统
        self.stall_items = []          # 摊位商品列表
        self.stall_revenue = 0         # 待领取摆摊收入
        # 城池政策系统
        self.city_policies = {}        # {city_id: {active, mayor_until, last_campaign_month}}
        # 洞府租赁与闭关系统
        self.cave_leases = {}          # {cave_id: {remaining_months}}
        self.closed_door_remaining = 0 # 剩余闭关月数
        self.closed_door_cave_id = None
        self.sect_last_reset_month = 0   # 上次重置宗门每日任务的月份
        self.sect_wanted_by = []         # 通缉玩家的宗门 ID 列表
        self.cave_upgrade_level = 0      # 宗门洞府升级等级
        self.sect_tournament_last_month = -1  # 上次参加宗门大比的世界月份
        self.learned_inheritances = []   # 已参悟的祖师堂传承 ID 列表
        self.ancestral_hall_monthly_count = 0  # 本月已参悟祖师堂次数
        self.beasts = []                 # 玩家拥有的灵兽列表，元素为 dict
        self.sect_alliances = []         # 宗门同盟列表，元素为 {sect_id, formed_year, formed_month, duration_months}
        # 宗门设施带来的活跃效果：{facility_id: {"remaining_months": int, ...}}
        self.active_facility_effects = {}
        # 宗门仓库：玩家捐献后物品进入仓库，key 为物品 ID，value 为数量
        self.sect_warehouse = {}
        # 累计捐献价值（用于排行榜），退出宗门后清零
        self.sect_donation_total = 0
        # 上次结算捐献排行榜奖励的世界月份，避免重复发放
        self.sect_donation_last_reward_month = -1
        # 宗门秘境/禁地冷却：{realm_id: 可再次进入的世界月份（year*12+month）}
        self.sect_secret_realm_cooldowns = {}
        # 追随者列表，每项为字典（含 id/name/element/path/loyalty/status/mission_end_month 等）
        self.followers = []
        # 当前进行中的宗门外交任务：{mission_id, target_sect_id, end_month}
        self.sect_diplomatic_mission = None
        # 当前进行中的宗门悬赏任务：{bounty_id, target_enemy, target_count, progress}
        self.sect_active_bounty = None
        # 当前生效的宗门气运事件：{event_id, name, end_month, effects}
        self.active_sect_fortune = None
        # 正道 / 魔道阵营值：0-1000，决定玩家阵营倾向
        self.righteous_value = 0
        self.evil_value = 0
        # 宗门护山大阵：是否激活、当前能量值
        self.sect_formation_active = False
        self.sect_formation_energy = 0

        # 炼器附魔系统：由 Engine 注入 EquipmentManager，用于计算装备总效果
        self.equipment_manager = None

    def _get_item_total_effects(self, item):
        """获取装备的总效果（基础 + 强化 + 词缀）；无管理器时回退到基础效果。"""
        if self.equipment_manager is not None:
            return self.equipment_manager.get_total_effects(item)
        return item.effects

    @property
    def attack(self):
        """
        总攻击力 = (基础攻击力 + 装备加成 × 装备倍率) × 流派攻击修正。
        器修的 equipment_bonus_mult=2.0 会让装备提供的攻击力翻倍。
        元婴受损时额外降低 10%。
        """
        equip_mult = self.path_modifiers.get("equipment_bonus_mult", 1.0)
        total = self.base_attack
        for item in self.equipment.values():
            if item:
                # 装备加成受 equipment_bonus_mult 影响（器修 ×2.0，其他默认 ×1.0）
                # 使用总效果（基础 + 强化 + 词缀）
                total += int(self._get_item_total_effects(item).get("attack", 0) * equip_mult)
        # 应用流派攻击力修正
        mult = self.path_modifiers.get("attack_mult", 1.0)
        # 元婴受损：全属性下降 10%
        if self.nascent_soul_weakened:
            mult *= 0.9
        return int(total * mult)

    @property
    def defense(self):
        """
        总防御力 = (基础防御力 + 装备加成 × 装备倍率) × 流派防御修正。
        器修的 equipment_bonus_mult 同样作用于装备防御加成。
        元婴受损时额外降低 10%。
        """
        equip_mult = self.path_modifiers.get("equipment_bonus_mult", 1.0)
        total = self.base_defense
        for item in self.equipment.values():
            if item:
                # 使用总效果（基础 + 强化 + 词缀）
                total += int(self._get_item_total_effects(item).get("defense", 0) * equip_mult)
        # 应用流派防御力修正
        mult = self.path_modifiers.get("defense_mult", 1.0)
        # 元婴受损：全属性下降 10%
        if self.nascent_soul_weakened:
            mult *= 0.9
        return int(total * mult)

    @property
    def max_health_equipped(self):
        """装备带来的额外生命值上限（含强化与词缀加成）。"""
        total = 0
        for item in self.equipment.values():
            if item:
                total += self._get_item_total_effects(item).get("health", 0)
        return total

    @property
    def max_health_base(self):
        """
        基础生命上限（不含装备加成），受流派修正影响。
        法修 ×0.8、体修 ×1.6、剑修 ×0.9、邪修 ×1.0
        元婴受损时额外降低 10%。
        """
        mult = self.path_modifiers.get("max_health_mult", 1.0)
        # 元婴受损：全属性下降 10%
        if self.nascent_soul_weakened:
            mult *= 0.9
        return int(100 * mult)

    @property
    def max_qi_modifier(self):
        """流派对真气上限的修正倍率（影响修炼效率显示，非硬上限）。"""
        return self.path_modifiers.get("max_qi_mult", 1.0)

    @property
    def skill_damage_mult(self):
        """流派对技能伤害的修正倍率。"""
        return self.path_modifiers.get("skill_damage_mult", 1.0)

    @property
    def crit_rate_bonus(self):
        """流派提供的暴击率加成（剑修 0.25，其他 0）。"""
        return self.path_modifiers.get("crit_rate_bonus", 0.0)

    @property
    def crit_damage_mult(self):
        """流派暴击伤害倍率（剑修 2.0，其他默认 1.5）。"""
        return self.path_modifiers.get("crit_damage_mult", 1.5)

    @property
    def heal_bonus_mult(self):
        """治疗效果加成倍率（丹修 1.5，其他默认 1.0）。"""
        return self.path_modifiers.get("heal_bonus_mult", 1.0)

    @property
    def ignore_defense(self):
        """技能是否无视敌人防御（魂修 True，其他 False）。"""
        return self.path_modifiers.get("ignore_defense", False)

    @property
    def no_cooldown(self):
        """专属技能是否无冷却（符修 True，其他 False）。"""
        return self.path_modifiers.get("no_cooldown", False)

    @property
    def summon_bonus(self):
        """召唤兽属性加成倍率（御兽修 0.5 即 +50%，其他 0）。"""
        return self.path_modifiers.get("summon_bonus", 0.0)

    @property
    def control_bonus(self):
        """控制技能成功率加成（阵修 0.3 即 +30%，其他 0）。"""
        return self.path_modifiers.get("control_bonus", 0.0)

    def is_alive(self):
        """判断是否还活着。残魂 / 器灵之姿亦视为存续。"""
        if getattr(self, "is_remnant", False):
            return True
        return self.health > 0 and self.age < self.max_lifespan

    def has_feature(self, feature):
        """检查玩家是否已解锁某个境界功能。"""
        return feature in self.unlocked_features

    def unlock_feature(self, feature):
        """解锁一个境界功能，重复解锁无副作用。"""
        self.unlocked_features.add(feature)

    def check_realm_feature_unlock(self, realm_id):
        """
        根据境界 ID 检查并解锁对应功能。
        返回解锁的功能名称（中文），未解锁返回 None。
        """
        feature = self.FEATURE_UNLOCK_REALMS.get(realm_id)
        if feature and feature not in self.unlocked_features:
            self.unlocked_features.add(feature)
            feature_names = {
                "flight": "御剑飞行",
                "life_treasure": "本命法宝",
                "nascent_soul_revive": "元婴替死",
            }
            return feature_names.get(feature, feature)
        return None

    def is_major_realm(self, realm_id):
        """判断某境界是否为大境界圆满期（突破时需渡劫）。"""
        return realm_id in self.MAJOR_REALM_IDS

    def is_portrait_glow_active(self, total_months):
        """判断大境界突破后的头像光效边框是否仍在持续。"""
        return getattr(self, "portrait_glow_until_month", 0) > total_months

    def add_age_months(self, months):
        """增加月份，并同步更新年龄显示，同时推进元婴受损恢复倒计时。"""
        self.age_months += months
        # 每 12 个月换算为 1 岁
        self.age = 16 + self.age_months // 12
        # 元婴受损倒计时
        if self.nascent_soul_weakened and self.weakened_remaining_months > 0:
            self.weakened_remaining_months -= months
            if self.weakened_remaining_months <= 0:
                self.nascent_soul_weakened = False
                self.weakened_remaining_months = 0

    def add_item(self, item):
        """往背包里添加一个物品；若该物品可堆叠，则优先合并到已有堆栈。"""
        if not item:
            return
        remaining = item.count if item.stackable else 1
        if item.stackable:
            # 先尝试合并到已有未满堆栈
            for inv_item in self.inventory:
                if inv_item.id == item.id and inv_item.stackable:
                    space = inv_item.max_stack - inv_item.count
                    if space > 0:
                        add_amount = min(remaining, space)
                        inv_item.count += add_amount
                        remaining -= add_amount
                        if remaining <= 0:
                            return
        # 还有剩余则新建堆栈
        while remaining > 0:
            stack_count = min(remaining, item.max_stack) if item.stackable else 1
            new_item = Item(
                item_id=item.id,
                name=item.name,
                item_type=item.type,
                value=item.value,
                description=item.description,
                effects=dict(item.effects),
                stackable=item.stackable,
                max_stack=item.max_stack,
                count=stack_count,
            )
            self.inventory.append(new_item)
            remaining -= stack_count

    def remove_item(self, item, quantity=1):
        """从背包移除物品；可堆叠物品按 quantity 减少 count，归零时移除实例。"""
        if item not in self.inventory:
            return False
        if item.stackable and item.count > quantity:
            item.count -= quantity
            return True
        self.inventory.remove(item)
        return True

    def has_item(self, item_id):
        """判断背包中是否至少拥有一件指定物品。"""
        return any(i.id == item_id for i in self.inventory)

    def count_item(self, item_id):
        """统计背包中某物品的总数量（含堆叠 count）。"""
        return sum(i.count for i in self.inventory if i.id == item_id)

    def consume_items(self, item_id, count):
        """消耗指定数量的某物品，成功返回 True。"""
        if self.count_item(item_id) < count:
            return False
        remaining = count
        for item in list(self.inventory):
            if item.id != item_id:
                continue
            if item.stackable:
                if item.count > remaining:
                    item.count -= remaining
                    return True
                remaining -= item.count
                self.inventory.remove(item)
                if remaining <= 0:
                    return True
            else:
                self.inventory.remove(item)
                remaining -= 1
                if remaining <= 0:
                    return True
        return True

    def equip_item(self, item):
        """装备一个物品，返回被替换下来的旧装备（如果有）。"""
        slot = item.type
        # 本命法宝槽位需先解锁
        if slot == "life_treasure" and not self.has_feature("life_treasure"):
            return None
        # 只有标准槽位和已解锁的本命法宝槽位可装备
        if slot not in self.EQUIPMENT_SLOTS and slot != "life_treasure":
            return None

        # 从背包移除
        if item not in self.inventory:
            return None
        self.inventory.remove(item)

        # 卸下旧装备并放回背包
        old_item = self.equipment.get(slot)
        if old_item:
            self.inventory.append(old_item)

        # 穿上新装备
        self.equipment[slot] = item

        # 更新最大生命值上限（基础值受流派修正 + 装备加成）
        self.max_health = self.max_health_base + self.max_health_equipped
        self.health = min(self.health, self.max_health)

        return old_item

    def unequip_item(self, slot):
        """从指定槽位卸下装备。"""
        item = self.equipment.get(slot)
        if item:
            self.equipment[slot] = None
            self.inventory.append(item)
            self.max_health = self.max_health_base + self.max_health_equipped
            self.health = min(self.health, self.max_health)
            return item
        return None

    def learn_skill(self, skill_id):
        """学习一个技能，并初始化熟练度为 1 级。"""
        if skill_id not in self.skills:
            self.skills.append(skill_id)
            self.skill_cooldowns[skill_id] = 0
            self.skill_proficiency[skill_id] = {"level": 1, "exp": 0}
            return True
        return False

    def has_skill(self, skill_id):
        """是否已习得某技能。"""
        return skill_id in self.skills

    def get_skill_proficiency(self, skill_id):
        """获取技能熟练度等级，未习得返回 0。"""
        return self.skill_proficiency.get(skill_id, {}).get("level", 0)

    def gain_skill_exp(self, skill_id, amount=None):
        """增加技能经验并处理升级，返回是否升级。"""
        if skill_id not in self.skills:
            return False
        amount = amount or self.SKILL_PROFICIENCY_EXP_PER_USE
        prof = self.skill_proficiency.setdefault(skill_id, {"level": 1, "exp": 0})
        prof["exp"] += amount
        leveled_up = False
        while prof["level"] < self.SKILL_PROFICIENCY_MAX_LEVEL:
            need = prof["level"] * self.SKILL_PROFICIENCY_LEVEL_EXP
            if prof["exp"] >= need:
                prof["exp"] -= need
                prof["level"] += 1
                leveled_up = True
            else:
                break
        return leveled_up

    def get_skill_damage_multiplier(self, skill_id):
        """根据熟练度返回伤害加成倍率（仅对伤害类技能生效）。"""
        level = self.get_skill_proficiency(skill_id)
        if level <= 0:
            return 1.0
        bonus = (level - 1) * self.SKILL_PROFICIENCY_DAMAGE_BONUS_PER_LEVEL
        return 1.0 + bonus

    def get_skill_heal_multiplier(self, skill_id):
        """根据熟练度返回治疗量加成倍率（仅对治疗类技能生效）。"""
        level = self.get_skill_proficiency(skill_id)
        if level <= 0:
            return 1.0
        bonus = (level - 1) * self.SKILL_PROFICIENCY_HEAL_BONUS_PER_LEVEL
        return 1.0 + bonus

    def get_skill_control_bonus(self, skill_id):
        """根据熟练度返回控制成功率加成（仅对控制类技能生效）。"""
        level = self.get_skill_proficiency(skill_id)
        if level <= 0:
            return 0.0
        return (level - 1) * self.SKILL_PROFICIENCY_CONTROL_BONUS_PER_LEVEL

    def get_skill_qi_cost_multiplier(self, skill_id):
        """根据熟练度返回真气消耗倍率（全类型技能生效）。"""
        level = self.get_skill_proficiency(skill_id)
        if level <= 0:
            return 1.0
        reduce = (level - 1) * self.SKILL_PROFICIENCY_COST_REDUCE_PER_LEVEL
        return max(0.5, 1.0 - reduce)

    def is_skill_max_proficiency(self, skill_id):
        """判断某技能是否已达到满级熟练度。"""
        return self.get_skill_proficiency(skill_id) >= self.SKILL_PROFICIENCY_MAX_LEVEL

    def decay_skill_proficiency(self, skill_id, amount=1):
        """
        技能熟练度衰减：长期未使用则降低经验，可能掉级，但最低保持 1 级 0 经验。
        返回 (是否发生衰减, 是否掉级)，方便 UI 高亮提示。
        """
        if skill_id not in self.skills:
            return False, False
        prof = self.skill_proficiency.get(skill_id)
        if not prof:
            return False, False
        level_before = prof["level"]
        prof["exp"] -= amount
        # 经验扣到负数时尝试降级，最低 1 级
        while prof["exp"] < 0 and prof["level"] > 1:
            prof["level"] -= 1
            prof["exp"] += prof["level"] * self.SKILL_PROFICIENCY_LEVEL_EXP
        if prof["exp"] < 0:
            prof["exp"] = 0
        return True, level_before > prof["level"]

    def update_skill_cooldowns(self):
        """每回合减少技能冷却。"""
        for skill_id in list(self.skill_cooldowns.keys()):
            if self.skill_cooldowns[skill_id] > 0:
                self.skill_cooldowns[skill_id] -= 1

    def set_skill_cooldown(self, skill_id, cooldown):
        """设置技能冷却。"""
        self.skill_cooldowns[skill_id] = cooldown

    def get_skill_cooldown(self, skill_id):
        """获取技能剩余冷却。"""
        return self.skill_cooldowns.get(skill_id, 0)

    def get_npc_relationship(self, npc_id):
        """获取与某 NPC 的好感度等级（0-10）。"""
        return self.npc_relationships.get(npc_id, 0)

    def set_spiritual_roots(self, roots, purities=None):
        """
        设置灵根属性并更新修炼倍率。
        roots: 灵根属性列表，可包含普通元素或融合灵根 id，如 ["fire"] 或 ["thunder_fire"]
        purities: 可选，灵根纯度字典，如 {"fire": 1.3, "thunder_fire": 1.2}。若为 None 则默认全部 1.0。
        """
        self.spiritual_roots = list(roots)
        # 灵根数量 → 修炼倍率映射（融合灵根按 1 个计数）
        count = len(self.spiritual_roots)
        multiplier_map = {1: 1.0, 2: 1.5, 3: 2.0, 4: 2.8, 5: 4.0}
        self.cultivation_multiplier = multiplier_map.get(count, 4.0)
        # 设置纯度：未提供则默认全部 1.0
        if purities:
            self.root_purities = {e: purities.get(e, 1.0) for e in self.spiritual_roots}
        else:
            self.root_purities = {e: 1.0 for e in self.spiritual_roots}
        # 展开融合灵根，缓存每个基础/变异元素的纯度（融合灵根内所有元素共享该融合纯度）
        config = SpiritualRootConfig()
        expanded = []
        expanded_purities = {}
        for root_id in self.spiritual_roots:
            purity = self.root_purities.get(root_id, 1.0)
            for elem in config.expand_root(root_id):
                if elem not in expanded_purities:
                    expanded.append(elem)
                    expanded_purities[elem] = purity
        self.expanded_elements = expanded
        self.expanded_element_purities = expanded_purities

    def get_root_purity(self, element):
        """
        获取某属性灵根的纯度系数。
        - "none" 和 "all"（五行阵法）返回 1.0，不受纯度影响
        - 普通元素返回对应灵根纯度
        - 融合灵根展开后的元素返回所属融合灵根的纯度
        """
        if element in ("none", "all"):
            return 1.0
        return self.expanded_element_purities.get(element, self.root_purities.get(element, 1.0))

    def has_element(self, element):
        """
        判断玩家是否拥有某属性灵根（支持融合灵根展开）。
        - "none"：无属性技能，人人可用
        - "all"：五行阵法技能，需五行灵根俱全方可施展
        - 其他：需拥有对应属性灵根，或该属性被包含在融合灵根中
        """
        if element == "none":
            return True
        if element == "all":
            # 五行俱全才可施展阵法技能
            return len(self.spiritual_roots) >= 5
        return element in getattr(self, "expanded_elements", self.spiritual_roots)

    def set_cultivation_path(self, path_id, modifiers):
        """
        设置修炼流派并应用属性修正。
        path_id: 流派 ID（fa/ti/jian/xie/dan/qi/shou/hun）
        modifiers: 流派属性修正字典（来自配置文件）
        """
        self.cultivation_path = path_id
        self.path_modifiers = dict(modifiers) if modifiers else {}
        # 重置所有流派专属资源（防止旧资源残留影响新流派）
        self.shield_qi = 0
        self.rage = 0
        self.sword_intent = 0
        self.evil_qi = 0
        self.dan_fire = 0
        self.qi_spirit = 0
        self.shou_soul = 0
        self.hun_sense = 0
        self.zhen_rune = 0
        # 符修的符箓是长期囤积资源，转换流派时清零
        self.fu_seal = 0
        # 符修选择时赠送 5 张初始符箓，保证首场战斗可使用专属技能
        if path_id == "fu":
            self.fu_seal = 5
        # 重新计算最大生命值（受流派修正影响）
        self.max_health = self.max_health_base + self.max_health_equipped
        self.health = min(self.health, self.max_health)

    def get_path_resource(self):
        """
        获取当前流派的专属资源值。
        返回 (resource_key, current_value, max_value) 或 None。
        """
        mapping = {
            "fa": ("shield_qi", 100),    # 法修：真气护盾
            "ti": ("rage", 100),          # 体修：怒气
            "jian": ("sword_intent", 10), # 剑修：剑意
            "xie": ("evil_qi", 100),      # 邪修：邪气
            "dan": ("dan_fire", 100),     # 丹修：丹火
            "qi": ("qi_spirit", 50),      # 器修：器灵
            "shou": ("shou_soul", 5),     # 御兽修：兽魂
            "hun": ("hun_sense", 100),    # 魂修：神识
            "zhen": ("zhen_rune", 9),     # 阵修：阵纹
            "fu": ("fu_seal", 20),        # 符修：符箓
        }
        info = mapping.get(self.cultivation_path)
        if not info:
            return None
        key, max_val = info
        current = getattr(self, key, 0)
        return (key, current, max_val)

    def add_path_resource(self, amount):
        """
        增加当前流派专属资源（如剑修积累剑意、体修积累怒气）。
        不会超过上限。
        """
        info = self.get_path_resource()
        if not info:
            return
        key, _, max_val = info
        new_val = min(max_val, getattr(self, key, 0) + amount)
        setattr(self, key, new_val)

    def consume_path_resource(self, amount):
        """
        消耗当前流派专属资源。
        不会低于 0，成功消耗返回 True，不足返回 False。
        """
        info = self.get_path_resource()
        if not info:
            return False
        key, current, _ = info
        if current < amount:
            return False
        setattr(self, key, current - amount)
        return True

    # ==================== 阵营值 ====================

    def adjust_righteous(self, amount):
        """调整正道阵营值，限制在 0-1000 范围。"""
        self.righteous_value = max(0, min(1000, self.righteous_value + amount))

    def adjust_evil(self, amount):
        """调整魔道阵营值，限制在 0-1000 范围。"""
        self.evil_value = max(0, min(1000, self.evil_value + amount))

    def get_camp(self):
        """
        根据正道/魔道阵营值判定当前阵营。
        差距 >= 100 时取较高一方，否则为中立。
        返回 'righteous'（正道）、'evil'（魔道）、'neutral'（中立）。
        """
        diff = self.righteous_value - self.evil_value
        if diff >= 100:
            return "righteous"
        if diff <= -100:
            return "evil"
        return "neutral"

    def get_camp_name(self):
        """获取当前阵营中文名。"""
        return {"righteous": "正道", "evil": "魔道", "neutral": "中立"}.get(
            self.get_camp(), "中立"
        )

    def increase_npc_relationship(self, npc_id, amount=1):
        """
        提升与某 NPC 的好感度，上限 10。
        返回提升后的好感度值。
        """
        current = self.get_npc_relationship(npc_id)
        new_val = min(10, current + amount)
        self.npc_relationships[npc_id] = new_val
        return new_val

    def decrease_npc_relationship(self, npc_id, amount=1):
        """
        降低与某 NPC 的好感度，下限 -10。
        返回降低后的好感度值。
        """
        current = self.get_npc_relationship(npc_id)
        new_val = max(-10, current - amount)
        self.npc_relationships[npc_id] = new_val
        return new_val

    def add_grudge(self, npc_id, level=1, reason=""):
        """
        添加或加深与某 NPC 的恩怨。
        level: 恩怨等级 1-5。
        """
        current = self.grudges.get(npc_id, {"level": 0, "reason": "", "start_month": 0})
        current["level"] = min(5, current["level"] + level)
        if reason:
            current["reason"] = reason
        if not current.get("start_month"):
            current["start_month"] = getattr(self, "age_months", 0)
        self.grudges[npc_id] = current
        return current["level"]

    def remove_grudge(self, npc_id):
        """化解与某 NPC 的恩怨，返回是否成功。"""
        if npc_id in self.grudges:
            del self.grudges[npc_id]
            return True
        return False

    def has_grudge(self, npc_id):
        """判断是否与某 NPC 存在恩怨。"""
        return npc_id in self.grudges

    def get_npc_memory(self, npc_id):
        """获取与某 NPC 的记忆对象，不存在则初始化。"""
        if npc_id not in self.npc_memory:
            self.npc_memory[npc_id] = {
                "choices": {},
                "last_visit": None,
                "visit_count": 0,
            }
        return self.npc_memory[npc_id]

    def record_npc_choice(self, npc_id, choice_key, choice_value):
        """记录玩家对某 NPC 的关键选择。"""
        memory = self.get_npc_memory(npc_id)
        memory["choices"][choice_key] = choice_value

    def record_npc_visit(self, npc_id, world):
        """记录玩家访问某 NPC 的时间和次数。"""
        memory = self.get_npc_memory(npc_id)
        memory["last_visit"] = {
            "year": world.year,
            "month": world.month,
            "day": world.day,
            "hour": world.hour,
        }
        memory["visit_count"] = memory.get("visit_count", 0) + 1

    def advance_quest(self, target_type, target_id, amount=1):
        """推进任务进度。"""
        for quest_id, progress in self.quest_progress.items():
            # 这里需要外部判断任务类型是否匹配，简单处理
            pass

    def to_dict(self):
        """序列化为字典，用于存档。"""
        return {
            "name": self.name,
            "save_version": self.save_version,
            "portrait": self.portrait,
            "gender": self.gender,
            "realm_id": self.realm_id,
            "portrait_glow_until_month": self.portrait_glow_until_month,
            "tutorial_step": getattr(self, "tutorial_step", 0),
            "qi": self.qi,
            "age": self.age,
            "age_months": self.age_months,
            "max_lifespan": self.max_lifespan,
            "wisdom": self.wisdom,
            "constitution": self.constitution,
            "luck": self.luck,
            "base_attack": self.base_attack,
            "base_defense": self.base_defense,
            "health": self.health,
            "max_health": self.max_health,
            "inventory": [item.to_dict() for item in self.inventory],
            "equipment": {
                slot: (item.to_dict() if item else None)
                for slot, item in self.equipment.items()
            },
            "skills": self.skills,
            "skill_cooldowns": self.skill_cooldowns,
            "skill_proficiency": self.skill_proficiency,
            "quest_progress": self.quest_progress,
            "completed_quests": self.completed_quests,
            "dialogue_flags": self.dialogue_flags,
            "location_id": self.location_id,
            "npc_relationships": self.npc_relationships,
            "npc_memory": self.npc_memory,
            "spiritual_roots": self.spiritual_roots,
            "cultivation_multiplier": self.cultivation_multiplier,
            "root_purities": self.root_purities,
            "cultivation_path": self.cultivation_path,
            "path_modifiers": self.path_modifiers,
            "shield_qi": self.shield_qi,
            "rage": self.rage,
            "sword_intent": self.sword_intent,
            "evil_qi": self.evil_qi,
            "dan_fire": self.dan_fire,
            "qi_spirit": self.qi_spirit,
            "shou_soul": self.shou_soul,
            "hun_sense": self.hun_sense,
            "zhen_rune": self.zhen_rune,
            "fu_seal": self.fu_seal,
            "refined_weapon_ids": self.refined_weapon_ids,
            "unlocked_features": list(self.unlocked_features),
            "nascent_soul_revive_used": self.nascent_soul_revive_used,
            "nascent_soul_weakened": self.nascent_soul_weakened,
            "weakened_remaining_months": self.weakened_remaining_months,
            # 心境 / 道心系统
            "mental_state": self.mental_state,
            "heart_demon": self.heart_demon,
            "mental_state_traits": self.mental_state_traits,
            "personality_tags": self.personality_tags,
            "tribulation_effects": self.tribulation_effects,
            # 洞府系统
            "residence": self.residence,
            # 道侣系统
            "companions": self.companions,
            # 心法系统
            "learned_mind_methods": self.learned_mind_methods,
            "equipped_mind_method": self.equipped_mind_method,
            # 炼丹系统
            "learned_recipes": self.learned_recipes,
            # 演武场系统
            "arena_streak": self.arena_streak,
            "arena_best_streak": self.arena_best_streak,
            "arena_daily_claimed": self.arena_daily_claimed,
            "arena_last_date": self.arena_last_date,
            "arena_rank": self.arena_rank,
            "arena_daily_challenges": self.arena_daily_challenges,
            # 摆摊系统
            "stall_items": getattr(self, "stall_items", []),
            "stall_revenue": getattr(self, "stall_revenue", 0),
            # 神通/法则系统
            "divine_arts": self.divine_arts,
            "enlightenment_points": self.enlightenment_points,
            # 灵根觉醒/变异
            "awakened_roots": self.awakened_roots,
            "mutated_roots": self.mutated_roots,
            # 灵植系统
            "farm_plots": self.farm_plots,
            # 个人灵兽
            "personal_beasts": self.personal_beasts,
            # 委托悬赏
            "active_bounties": self.active_bounties,
            # 城池动态任务
            "city_quest_pool": self.city_quest_pool,
            "active_city_quests": self.active_city_quests,
            # 成就系统
            "achievements": self.achievements,
            "achievement_progress": self.achievement_progress,
            # 历史年表
            "chronicle": self.chronicle,
            # 动态世界事件
            "active_world_events": self.active_world_events,
            "world_event_history": self.world_event_history,
            "world_event_encounters": self.world_event_encounters,
            "world_event_price_mods": self.world_event_price_mods,
            # F-04 动态世界事件深化
            "world_state": self.world_state,
            "active_event_chains": self.active_event_chains,
            "world_event_chain_history": self.world_event_chain_history,
            # 支线任务
            "active_side_quests": self.active_side_quests,
            "completed_side_quests": self.completed_side_quests,
            # 势力声望
            "reputation": self.reputation,
            # 探索相关
            "unlocked_secret_realms": self.unlocked_secret_realms,
            "explored_ruins": self.explored_ruins,
            "unlocked_teleports": self.unlocked_teleports,
            # Roguelike 秘境
            "realm_coins": self.realm_coins,
            "realm_compendium": self.realm_compendium,
            # 修仙家族（F-01）：family 为 dict 或 None
            "family": self.family,
            # 领地建设（F-02）：territory 为 dict 或 None
            "territory": self.territory,
            # F-06 成就分级 / 难度（旧存档兼容）
            "titles": self.titles,
            "title_bonuses": self.title_bonuses,
            "unlocked_hidden_events": self.unlocked_hidden_events,
            "difficulty": self.difficulty,
            "difficulty_modifiers": self.difficulty_modifiers,
            # F-07 多周目模式（旧存档兼容）
            "game_mode": self.game_mode,
            "allowed_paths": self.allowed_paths,
            "no_spiritual_roots": self.no_spiritual_roots,
            # 维度④ 天道反噬（F-08）
            "heaven_gaze": self.heaven_gaze,
            # 维度⑤ 寿元与轮回晚年（F-09）
            "sit_pending": self.sit_pending,
            "past_life_arrangements": self.past_life_arrangements,
            "remnant_soul": self.remnant_soul,
            "is_remnant": self.is_remnant,
            "remnant_months": self.remnant_months,
            "past_life_relics": self.past_life_relics,
            "relic_chain": self.relic_chain,
            # 维度② 红尘炼心 / 入世（F-08 体验深化）
            "red_dust_active": self.red_dust_active,
            "red_dust_bonds": self.red_dust_bonds,
            "red_dust_months": self.red_dust_months,
            "red_dust_pending_qingjie": self.red_dust_pending_qingjie,
            "founded_sect": self.founded_sect,
            "self_created_techniques": self.self_created_techniques,
            "pending_deduction": self.pending_deduction,
            "life_path": self.life_path,
            "life_path_proficiency": self.life_path_proficiency,
            "lifepath_auto_deploy": self.lifepath_auto_deploy,
            # 维度③·M18 丹道持续修炼增益
            "cultivation_boost_months": self.cultivation_boost_months,
            "cultivation_boost_amount": self.cultivation_boost_amount,
            "hostile_factions": self.hostile_factions,
            "meta_modifiers": self.meta_modifiers,
            "pending_start_items": self.pending_start_items,
            "has_won": self.has_won,
            "ending_id": getattr(self, "ending_id", None),
            "main_story_step": getattr(self, "main_story_step", 0),
            "face_traits": getattr(self, "face_traits", {}),
            "face_params": getattr(self, "face_params", {}),
            "treasure_maps": self.treasure_maps,
            "location_event_cooldowns": self.location_event_cooldowns,
            "world_boss_kills": self.world_boss_kills,
            # 社交关系
            "master_id": self.master_id,
            "disciples": self.disciples,
            "sworn_brothers": self.sworn_brothers,
            "revenge_targets": self.revenge_targets,
            "grudges": self.grudges,
            "killed_npcs": self.killed_npcs,
            # 图鉴与信件
            "bestiary": self.bestiary,
            "item_compendium": self.item_compendium,
            "skill_compendium": self.skill_compendium,
            "letters": self.letters,
            "heard_rumors": self.heard_rumors,
            # 战斗统计
            "combat_stats": self.combat_stats,
            # 论道记录
            "debate_record": self.debate_record,
            # 转生/轮回
            "reincarnation_count": self.reincarnation_count,
            "karma": self.karma,
            "past_life_talents": self.past_life_talents,
            "reincarnation_cultivation_bonus": self.reincarnation_cultivation_bonus,
            "reincarnation_breakthrough_bonus": self.reincarnation_breakthrough_bonus,
            # 宗门系统
            "sect_id": self.sect_id,
            "sect_rank": self.sect_rank,
            "sect_contribution": self.sect_contribution,
            "sect_loyalty": self.sect_loyalty,
            "sect_tasks_today": self.sect_tasks_today,
            "sect_active_task": self.sect_active_task,
            # 城池声望系统
            "city_reputation": self.city_reputation,
            "building_levels": self.building_levels,
            # 城池政策系统
            "city_policies": getattr(self, "city_policies", {}),
            # 洞府租赁与闭关系统
            "cave_leases": getattr(self, "cave_leases", {}),
            "closed_door_remaining": getattr(self, "closed_door_remaining", 0),
            "closed_door_cave_id": getattr(self, "closed_door_cave_id", None),
            "sect_war_participation": self.sect_war_participation,
            "sect_last_reset_year": self.sect_last_reset_year,
            "sect_last_reset_month": self.sect_last_reset_month,
            "sect_wanted_by": self.sect_wanted_by,
            "cave_upgrade_level": self.cave_upgrade_level,
            "sect_tournament_last_month": self.sect_tournament_last_month,
            "learned_inheritances": self.learned_inheritances,
            "ancestral_hall_monthly_count": self.ancestral_hall_monthly_count,
            "beasts": self.beasts,
            "sect_alliances": self.sect_alliances,
            "active_facility_effects": self.active_facility_effects,
            "sect_warehouse": self.sect_warehouse,
            "sect_donation_total": self.sect_donation_total,
            "sect_donation_last_reward_month": self.sect_donation_last_reward_month,
            "sect_secret_realm_cooldowns": self.sect_secret_realm_cooldowns,
            "followers": self.followers,
            "sect_diplomatic_mission": self.sect_diplomatic_mission,
            "sect_active_bounty": self.sect_active_bounty,
            "active_sect_fortune": self.active_sect_fortune,
            "righteous_value": self.righteous_value,
            "evil_value": self.evil_value,
            "sect_formation_active": self.sect_formation_active,
            "sect_formation_energy": self.sect_formation_energy,
        }

    @classmethod
    def from_dict(cls, data, item_library):
        """从字典和物品库恢复玩家对象。"""
        player = cls(name=data.get("name", "无名"))
        # 存档版本与迁移：先读取旧版本号，再执行对应迁移逻辑
        player.save_version = data.get("save_version", 0)
        player._migrate_save_data(data)
        player.portrait = data.get("portrait", player.portrait)
        player.gender = data.get("gender", player.gender)
        player.realm_id = data.get("realm_id", "qi_refining_1")
        player.portrait_glow_until_month = data.get("portrait_glow_until_month", 0)
        player.tutorial_step = int(data.get("tutorial_step", 0))
        player.qi = data.get("qi", 0)
        player.age = data.get("age", 16)
        player.age_months = data.get("age_months", 0)
        player.max_lifespan = data.get("max_lifespan", 100)
        player.wisdom = data.get("wisdom", 5)
        player.constitution = data.get("constitution", 5)
        player.luck = data.get("luck", 5)
        player.base_attack = data.get("base_attack", 10)
        player.base_defense = data.get("base_defense", 2)
        player.health = data.get("health", 100)
        player.max_health = data.get("max_health", 100)
        player.location_id = data.get("location_id", "qingyun")

        # 恢复背包物品（兼容旧存档：单条记录默认 count=1）
        for item_data in data.get("inventory", []):
            item = item_library.create(item_data["id"])
            if item:
                item.count = item_data.get("count", 1)
                if "stackable" in item_data:
                    item.stackable = item_data["stackable"]
                if "max_stack" in item_data:
                    item.max_stack = item_data["max_stack"]
                player.inventory.append(item)
        player._merge_inventory_stacks()

        # 恢复装备
        for slot, item_data in data.get("equipment", {}).items():
            if item_data:
                item = item_library.create(item_data["id"])
                player.equipment[slot] = item

        # 恢复技能、冷却、任务进度、熟练度（旧存档兼容：按已学技能补 1 级）
        player.skills = data.get("skills", [])
        player.skill_cooldowns = data.get("skill_cooldowns", {})
        player.skill_proficiency = data.get("skill_proficiency", {})
        for skill_id in player.skills:
            if skill_id not in player.skill_proficiency:
                player.skill_proficiency[skill_id] = {"level": 1, "exp": 0}
        player.quest_progress = data.get("quest_progress", {})
        player.completed_quests = data.get("completed_quests", [])
        # 恢复对话标志位（旧存档兼容）
        player.dialogue_flags = data.get("dialogue_flags", {})
        # 恢复 NPC 好感度与记忆（旧存档兼容）
        player.npc_relationships = data.get("npc_relationships", {})
        player.npc_memory = data.get("npc_memory", {})
        # 恢复灵根属性（旧存档默认火灵根），通过 set_spiritual_roots 展开融合灵根
        player.set_spiritual_roots(
            data.get("spiritual_roots", ["fire"]),
            data.get("root_purities", {}),
        )
        # 恢复修炼流派（旧存档默认法修）
        player.cultivation_path = data.get("cultivation_path", "fa")
        player.path_modifiers = data.get("path_modifiers", {})
        # 恢复流派专属资源
        player.shield_qi = data.get("shield_qi", 0)
        player.rage = data.get("rage", 0)
        player.sword_intent = data.get("sword_intent", 0)
        player.evil_qi = data.get("evil_qi", 0)
        player.dan_fire = data.get("dan_fire", 0)
        player.qi_spirit = data.get("qi_spirit", 0)
        player.shou_soul = data.get("shou_soul", 0)
        player.hun_sense = data.get("hun_sense", 0)
        player.zhen_rune = data.get("zhen_rune", 0)
        player.fu_seal = data.get("fu_seal", 0)
        player.refined_weapon_ids = data.get("refined_weapon_ids", [])
        # 恢复境界解锁功能（旧存档兼容：无此字段则按当前境界重新检测）
        player.unlocked_features = set(data.get("unlocked_features", []))
        player.nascent_soul_revive_used = data.get("nascent_soul_revive_used", False)
        player.nascent_soul_weakened = data.get("nascent_soul_weakened", False)
        player.weakened_remaining_months = data.get("weakened_remaining_months", 0)
        # 心境 / 道心系统（旧存档兼容）
        player.mental_state = data.get("mental_state", 50)
        player.heart_demon = data.get("heart_demon", 0)
        player.mental_state_traits = data.get("mental_state_traits", [])
        player.personality_tags = data.get("personality_tags", [])
        player.tribulation_effects = data.get("tribulation_effects", {})
        # 洞府系统（旧存档兼容）
        player.residence = data.get("residence")
        # 道侣系统（旧存档兼容）
        player.companions = data.get("companions", [])
        # 心法系统（旧存档兼容）
        player.learned_mind_methods = data.get("learned_mind_methods", [])
        player.equipped_mind_method = data.get("equipped_mind_method")
        # 炼丹系统（旧存档兼容）
        player.learned_recipes = data.get("learned_recipes", [])
        # 演武场系统（旧存档兼容）
        player.arena_streak = data.get("arena_streak", 0)
        player.arena_best_streak = data.get("arena_best_streak", 0)
        player.arena_daily_claimed = data.get("arena_daily_claimed", False)
        player.arena_last_date = data.get("arena_last_date")
        player.arena_rank = data.get("arena_rank", 0)
        player.arena_daily_challenges = data.get("arena_daily_challenges", 0)
        # 摆摊系统（旧存档兼容）
        player.stall_items = data.get("stall_items", [])
        player.stall_revenue = data.get("stall_revenue", 0)
        # 神通/法则系统（旧存档兼容）
        player.divine_arts = data.get("divine_arts", [])
        player.enlightenment_points = data.get("enlightenment_points", 0)
        # 灵根觉醒/变异（旧存档兼容）
        player.awakened_roots = data.get("awakened_roots", [])
        player.mutated_roots = data.get("mutated_roots", [])
        # 灵植系统（旧存档兼容）
        player.farm_plots = data.get("farm_plots", [])
        # 个人灵兽（旧存档兼容）
        player.personal_beasts = data.get("personal_beasts", [])
        # 委托悬赏（旧存档兼容）
        player.active_bounties = data.get("active_bounties", [])
        # 城池动态任务（旧存档兼容）
        player.city_quest_pool = data.get("city_quest_pool", [])
        player.active_city_quests = data.get("active_city_quests", {})
        # 成就系统（旧存档兼容）
        player.achievements = data.get("achievements", [])
        player.achievement_progress = data.get("achievement_progress", {})
        # 历史年表（旧存档兼容）
        player.chronicle = data.get("chronicle", [])
        # 动态世界事件（旧存档兼容）
        player.active_world_events = data.get("active_world_events", {})
        player.world_event_history = data.get("world_event_history", {})
        player.world_event_encounters = data.get("world_event_encounters", [])
        player.world_event_price_mods = data.get("world_event_price_mods", {})
        # F-04 动态世界事件深化（旧存档兼容）
        player.world_state = data.get("world_state", {}) or {}
        player.active_event_chains = data.get("active_event_chains", {}) or {}
        player.world_event_chain_history = data.get("world_event_chain_history", {}) or {}
        # 支线任务（旧存档兼容）
        player.active_side_quests = data.get("active_side_quests", {})
        player.completed_side_quests = data.get("completed_side_quests", [])
        # 势力声望（旧存档兼容）
        player.reputation = data.get("reputation", {})
        # 探索相关（旧存档兼容）
        player.unlocked_secret_realms = data.get("unlocked_secret_realms", [])
        player.explored_ruins = data.get("explored_ruins", {})
        player.unlocked_teleports = data.get("unlocked_teleports", [])
        # Roguelike 秘境（旧存档兼容）
        player.realm_coins = data.get("realm_coins", 0)
        player.realm_compendium = data.get(
            "realm_compendium", {"cards": [], "bosses": [], "events": []}
        )
        # 修仙家族（F-01）：旧存档无此字段时为 None（未建家族），天然向后兼容
        player.family = data.get("family", None)
        # 领地建设（F-02）：旧存档无此字段时为 None（未占据领地），天然向后兼容
        player.territory = data.get("territory", None)
        # F-06 成就分级 / 难度（旧存档兼容）
        player.titles = data.get("titles", [])
        player.title_bonuses = data.get("title_bonuses", {})
        player.unlocked_hidden_events = data.get("unlocked_hidden_events", [])
        player.difficulty = data.get("difficulty", "normal")
        player.difficulty_modifiers = data.get("difficulty_modifiers", {
            "enemy_strength": 1.0, "player_combat": 1.0,
            "production_mult": 1.0, "exp_mult": 1.0, "drop_mult": 1.0,
        })
        # F-07 多周目模式（旧存档兼容）
        player.game_mode = data.get("game_mode", "standard")
        player.allowed_paths = data.get("allowed_paths", [])
        # 维度④ 天道反噬（F-08）
        player.heaven_gaze = data.get("heaven_gaze", 0)
        # 维度⑤ 寿元与轮回晚年（F-09）
        player.sit_pending = data.get("sit_pending", False)
        player.past_life_arrangements = data.get("past_life_arrangements", None)
        player.remnant_soul = data.get("remnant_soul", None)
        player.is_remnant = data.get("is_remnant", False)
        player.remnant_months = data.get("remnant_months", 0)
        player.past_life_relics = data.get("past_life_relics", [])
        player.relic_chain = data.get("relic_chain", [])
        # 维度② 红尘炼心 / 入世（F-08 体验深化，旧存档兼容）
        player.red_dust_active = data.get("red_dust_active", False)
        player.red_dust_bonds = data.get("red_dust_bonds", [])
        player.red_dust_months = data.get("red_dust_months", 0)
        player.red_dust_pending_qingjie = data.get("red_dust_pending_qingjie", None)
        player.founded_sect = data.get("founded_sect", None)
        player.self_created_techniques = data.get("self_created_techniques", [])
        player.life_path = data.get("life_path", None)
        player.life_path_proficiency = data.get("life_path_proficiency", 0)
        player.lifepath_auto_deploy = data.get("lifepath_auto_deploy", False)
        player.cultivation_boost_months = data.get("cultivation_boost_months", 0)
        player.cultivation_boost_amount = data.get("cultivation_boost_amount", 0)
        player.pending_deduction = data.get("pending_deduction", None)
        player.no_spiritual_roots = data.get("no_spiritual_roots", False)
        player.hostile_factions = data.get("hostile_factions", [])
        player.meta_modifiers = data.get("meta_modifiers", {})
        player.pending_start_items = data.get("pending_start_items", [])
        player.has_won = data.get("has_won", False)
        player.ending_id = data.get("ending_id", None)
        player.main_story_step = int(data.get("main_story_step", 0))
        ft = data.get("face_traits", {})
        player.face_traits = ft if isinstance(ft, dict) else {}
        fp = data.get("face_params", {})
        player.face_params = fp if isinstance(fp, dict) else {}
        player.treasure_maps = data.get("treasure_maps", [])
        player.location_event_cooldowns = data.get("location_event_cooldowns", {})
        player.world_boss_kills = data.get("world_boss_kills", [])
        # 社交关系（旧存档兼容）
        player.master_id = data.get("master_id")
        player.disciples = data.get("disciples", [])
        player.sworn_brothers = data.get("sworn_brothers", [])
        player.revenge_targets = data.get("revenge_targets", [])
        player.grudges = data.get("grudges", {})
        player.killed_npcs = data.get("killed_npcs", [])
        # 图鉴与信件（旧存档兼容）
        player.bestiary = data.get("bestiary", {})
        player.item_compendium = data.get("item_compendium", [])
        player.skill_compendium = data.get("skill_compendium", [])
        player.letters = data.get("letters", [])
        player.heard_rumors = data.get("heard_rumors", [])
        # 战斗统计（旧存档兼容）
        player.combat_stats = data.get("combat_stats", {
            "total_battles": 0, "wins": 0, "losses": 0,
            "total_damage_dealt": 0, "total_damage_taken": 0, "highest_damage": 0,
        })
        # 论道记录（旧存档兼容）
        player.debate_record = data.get("debate_record", {"wins": 0, "losses": 0})
        # 转生/轮回（旧存档兼容）
        player.reincarnation_count = data.get("reincarnation_count", 0)
        player.karma = data.get("karma", 0)
        player.past_life_talents = data.get("past_life_talents", [])
        player.reincarnation_cultivation_bonus = data.get(
            "reincarnation_cultivation_bonus", 0.0
        )
        player.reincarnation_breakthrough_bonus = data.get(
            "reincarnation_breakthrough_bonus", 0.0
        )
        # 宗门系统（旧存档兼容）
        player.sect_id = data.get("sect_id")
        player.sect_rank = data.get("sect_rank", "none")
        player.sect_contribution = data.get("sect_contribution", 0)
        player.sect_loyalty = data.get("sect_loyalty", 0)
        player.sect_tasks_today = data.get("sect_tasks_today", 0)
        player.sect_active_task = data.get("sect_active_task")
        # 城池声望系统（旧存档兼容）
        player.city_reputation = data.get("city_reputation", {})
        player.building_levels = data.get("building_levels", {})
        # 城池政策系统（旧存档兼容）
        player.city_policies = data.get("city_policies", {})
        # 洞府租赁与闭关系统（旧存档兼容）
        player.cave_leases = data.get("cave_leases", {})
        player.closed_door_remaining = data.get("closed_door_remaining", 0)
        player.closed_door_cave_id = data.get("closed_door_cave_id", None)
        player.sect_war_participation = data.get("sect_war_participation", 0)
        player.sect_last_reset_year = data.get("sect_last_reset_year", 0)
        player.sect_last_reset_month = data.get("sect_last_reset_month", 0)
        player.sect_wanted_by = data.get("sect_wanted_by", [])
        player.cave_upgrade_level = data.get("cave_upgrade_level", 0)
        player.sect_tournament_last_month = data.get("sect_tournament_last_month", -1)
        player.learned_inheritances = data.get("learned_inheritances", [])
        player.ancestral_hall_monthly_count = data.get("ancestral_hall_monthly_count", 0)
        player.beasts = data.get("beasts", [])
        player.sect_alliances = data.get("sect_alliances", [])
        player.active_facility_effects = data.get("active_facility_effects", {})
        # 宗门仓库与捐献排行榜（旧存档兼容）
        player.sect_warehouse = data.get("sect_warehouse", {})
        player.sect_donation_total = data.get("sect_donation_total", 0)
        player.sect_donation_last_reward_month = data.get("sect_donation_last_reward_month", -1)
        player.sect_secret_realm_cooldowns = data.get("sect_secret_realm_cooldowns", {})
        # 追随者系统（旧存档兼容）
        player.followers = data.get("followers", [])
        player.sect_diplomatic_mission = data.get("sect_diplomatic_mission", None)
        # 宗门悬赏任务（旧存档兼容）
        player.sect_active_bounty = data.get("sect_active_bounty", None)
        # 宗门气运事件（旧存档兼容）
        player.active_sect_fortune = data.get("active_sect_fortune", None)
        # 正道 / 魔道阵营值（旧存档兼容）
        player.righteous_value = data.get("righteous_value", 0)
        player.evil_value = data.get("evil_value", 0)
        # 宗门护山大阵（旧存档兼容）
        player.sect_formation_active = data.get("sect_formation_active", False)
        player.sect_formation_energy = data.get("sect_formation_energy", 0)
        # 若旧存档缺少功能字段，根据当前境界补发功能（避免老玩家丢失已解锁能力）
        current_order = player.REALM_ORDER.get(player.realm_id, 0)
        for realm_id, feature in player.FEATURE_UNLOCK_REALMS.items():
            if current_order >= player.REALM_ORDER.get(realm_id, 999):
                player.unlocked_features.add(feature)
        # 应用流派修正后重新计算最大生命值
        player.max_health = player.max_health_base + player.max_health_equipped
        player.health = min(player.health, player.max_health)

        return player

    def _migrate_save_data(self, data):
        """根据存档版本号对旧存档数据进行迁移补全。"""
        # 版本 0 -> 1：补全城池声望、建筑等级与主角头像字段
        if self.save_version < 1:
            if "city_reputation" not in data:
                data["city_reputation"] = {}
            if "building_levels" not in data:
                data["building_levels"] = {}
            if "portrait" not in data:
                data["portrait"] = self.portrait
            if "gender" not in data:
                data["gender"] = self.gender
            # 迁移完成后将版本号提升到当前版本
            self.save_version = self.SAVE_VERSION

    def _merge_inventory_stacks(self):
        """把背包中可堆叠的同类物品合并成不超过 max_stack 的堆栈，减少列表长度。"""
        merged = []
        groups = {}
        # 先分组：可堆叠按 id 分组，不可堆叠单独保留
        for item in self.inventory:
            if item.stackable:
                groups.setdefault(item.id, []).append(item)
            else:
                merged.append(item)
        for item_id, items in groups.items():
            total = sum(i.count for i in items)
            template = items[0]
            while total > 0:
                stack_count = min(total, template.max_stack)
                merged.append(Item(
                    item_id=template.id,
                    name=template.name,
                    item_type=template.type,
                    value=template.value,
                    description=template.description,
                    effects=dict(template.effects),
                    stackable=True,
                    max_stack=template.max_stack,
                    count=stack_count,
                ))
                total -= stack_count
        self.inventory = merged
