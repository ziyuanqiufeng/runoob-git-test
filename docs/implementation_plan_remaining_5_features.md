# 剩余五大系统实施方案

本文档针对《问道长生》当前尚未完成的五大系统给出可落地的分阶段实施方案：

1. 私人洞府占领与设施升级
2. 药园种植与炼丹/炼器工作台
3. 论道、双修、收徒与恩怨链
4. 宗门战争、外交与世界 BOSS
5. 渡劫飞升结局与转世继承

方案遵循项目现有的 **Manager + Dialog + Config** 三件套结构，强调配置驱动、逐模块验收、旧存档兼容。

---

## 一、总体实施顺序

| 顺序 | 系统 | 前置依赖 | 建议优先级 | 说明 |
|------|------|----------|------------|------|
| 1 | 私人洞府占领与设施升级 | ResidenceManager、FarmManager、CaveManager | P1 | 属于经营层底座，影响后续炼丹/炼器工作台 |
| 2 | 药园种植与炼丹/炼器工作台 | 洞府设施、FarmManager、Item/Recipe 配置 | P1 | 与洞府设施深度绑定 |
| 3 | 论道、双修、收徒与恩怨链 | NPC 关系、 companions、 master/disciples 字段 | P2 | 社交层核心，依赖 NPC 数据 |
| 4 | 宗门战争、外交与世界 BOSS | SectManager、WorldBossManager、DiplomaticMission | P2 | 势力与世界舞台内容 |
| 5 | 渡劫飞升结局与转世继承 | ReincarnationManager、Tribulation 战斗、结局结算 | P3 | 终局与多周目内容 |

**原则**：每个模块独立完成后跑通 `tools/validate_configs.py` + `pytest tests/`，再进入下一模块，避免一次性引入大量回归。

---

## 二、模块一：私人洞府占领与设施升级

### 2.1 现状盘点

- `game/residence.py` 已实现城中/野外洞府的购买、建筑升级、月度产出与袭击判定。
- `game/farm.py` 已绑定 `residence.buildings.herb_garden` 等级解锁地块。
- `game/cave_manager.py` 已覆盖城中洞府租赁与闭关。
- 缺失：**野外灵脉占领**、**设施升级完整链路**、**护山大阵维护与入侵战斗**、**洞府事件链**。

### 2.2 设计目标

让玩家在高境界后可在野外占据灵脉，拥有可升级、可自定义、可被攻击的永久领地，形成从「租赁洞府 → 宗门洞府 → 私人洞府」的成长线。

### 2.3 输入-输出-风险表

| 输入 | 输出 | 风险 / 代价 |
|------|------|-------------|
| 击败灵脉守卫 | 私人洞府所有权 | 占领失败损失健康与灵石 |
| 灵石 + 材料 | 设施等级提升 | 前期投入大 |
| 每月维护费 | 修炼加成、资源产出、闭关安全 | 维护不足触发入侵或设施停摆 |
| 护山大阵能量 | 降低入侵概率 | 能量耗尽后洞府暴露 |

### 2.4 数据模型扩展

#### 2.4.1 `config/residences.json` 结构

在现有字段基础上新增/明确：

```json
{
  "residences": [
    {
      "id": "wild_cloud_peak",
      "name": "云顶峰私人洞府",
      "type": "wild",
      "location_id": "cloud_peak",
      "cost": { "spirit_stone": 0, "contribution": 0 },
      "occupation": {
        "required_realm_order": 10,
        "guard_enemy_id": "cloud_peak_guardian",
        "guard_count": 1,
        "intro_text": "云顶峰灵气浓郁，但有妖兽盘踞。"
      },
      "buildings": [
        {"id": "herb_garden", "name": "灵田", "max_level": 5, "base_cost": {"spirit_stone": 500}, "cost_multiplier": 1.6, "effect_per_level": {"cultivation_speed": 0.03, "herb_id": "spirit_herb", "herb_chance": 0.15}},
        {"id": "alchemy_room", "name": "炼丹室", "max_level": 5, "base_cost": {"spirit_stone": 800}, "cost_multiplier": 1.7, "effect_per_level": {"alchemy_success": 0.05, "alchemy_quality": 0.02}},
        {"id": "smithy", "name": "炼器台", "max_level": 5, "base_cost": {"spirit_stone": 800}, "cost_multiplier": 1.7, "effect_per_level": {"smith_success": 0.05, "refine_bonus": 0.03}},
        {"id": "beast_park", "name": "灵兽园", "max_level": 3, "base_cost": {"spirit_stone": 600}, "cost_multiplier": 1.8, "effect_per_level": {"beast_growth": 0.1, "max_beasts": 1}},
        {"id": "gathering_array", "name": "聚灵阵", "max_level": 5, "base_cost": {"spirit_stone": 1000}, "cost_multiplier": 1.9, "effect_per_level": {"cultivation_speed": 0.06}},
        {"id": "defense_formation", "name": "护山大阵", "max_level": 5, "base_cost": {"spirit_stone": 1200}, "cost_multiplier": 2.0, "effect_per_level": {"raid_defense": 0.12, "max_energy": 200}}
      ]
    }
  ],
  "raid": {
    "base_chance": 0.08,
    "min_strength_bonus": 0.0,
    "max_strength_bonus": 0.4,
    "enemy_pool": ["demon_beast_wolf", "bandit_cultivator", "hostile_xie_xiu"]
  }
}
```

#### 2.4.2 Player 字段扩展

`player.residence` 已在 Player 中预留，结构建议统一为：

```python
self.residence = {
    "id": "wild_cloud_peak",
    "buildings": {"herb_garden": 1, "alchemy_room": 0, ...},
    "energy": 500,           # 护山大阵当前能量
    "maintenance_debt": 0,   # 维护费欠费月数
    "spirit_vein_quality": 1.0  # 灵脉品质倍率
}
```

### 2.5 核心接口设计

新增 `game/private_residence_manager.py`（或扩展 `ResidenceManager`）：

```python
class PrivateResidenceManager:
    def __init__(self, player, item_library, enemy_library, world, config=None)
    def can_occupy(self, location_id) -> (bool, str)
    def occupy(self, location_id) -> (bool, str, Enemy)  # 返回守卫敌人
    def finish_occupation(self, location_id, win) -> (bool, str)
    def can_upgrade_building(self, building_id) -> (bool, str)
    def upgrade_building(self, building_id) -> (bool, str)
    def pay_maintenance(self) -> (bool, str)
    def tick_monthly(self) -> {"production": [...], "raid": dict, "logs": [...]}
    def get_cultivation_speed_bonus(self) -> float
    def get_defense_rate(self) -> float
    def consume_formation_energy(self, amount)
```

### 2.6 关键流程

1. **野外灵脉发现**：玩家在野外地点探索时，概率发现可占领灵脉（通过 `locations.json` 配置 `spirit_veins`）。
2. **占领战斗**：调用 `PrivateResidenceManager.occupy()` 生成守卫敌人，进入战斗；胜利后获得洞府所有权。
3. **设施建设**：在洞府 UI 中消耗灵石与材料升级建筑；材料需求通过 `items.json` 配置。
4. **月度结算**：`Engine.tick_monthly()` 调用 `tick_monthly()`：
   - 扣除维护费（按建筑等级总和计算）。
   - 欠费 3 个月以上设施停摆。
   - 按 `raid` 配置与护阵等级判定入侵。
   - 产出资源。
5. **入侵处理**：若触发入侵，`tick_monthly()` 返回 `raid` 信息，由 `Engine` 弹出战斗；胜利则获得材料，失败则随机降级一级建筑或扣除能量。

### 2.7 UI 入口

- 新增 `ui/private_residence_dialog.py`：洞府总览、建筑升级、维护缴费、护阵能量、入侵记录。
- 在 `map_panel.py` 的野外地点菜单中加入「占领灵脉」入口。
- 在 `main_window.py` 主界面加入「洞府」按钮。

### 2.8 配置校验

更新 `tools/validate_configs.py`，校验：

- `residences.json` 中每个 `type=wild` 的洞府必须含 `occupation` 字段。
- `buildings` 中的 `effect_per_level` 仅允许已知 key。
- `raid.enemy_pool` 中的敌人 ID 在 `enemies.json` 中存在。

### 2.9 测试要点

- 占领成功/失败的状态变化。
- 建筑升级消耗与效果累加。
- 月度维护欠费导致设施停摆。
- 入侵概率受护阵等级影响。
- 旧存档无 `residence` 字段时兼容。

---

## 三、模块二：药园种植与炼丹/炼器工作台

### 3.1 现状盘点

- `game/farm.py` 已实现播种、浇水、收获、季节枯萎逻辑。
- `ui/alchemy_dialog.py` 已有炼丹 UI。
- `game/equipment_manager.py` 已实现装备强化与词缀。
- 缺失：炼丹/炼器与洞府建筑等级挂钩、工作台批量炼制、炼丹失败与品质、炼器专属工作台。

### 3.2 设计目标

将药园、炼丹室、炼器台作为洞府设施的一部分，建筑等级直接影响种植规模、炼丹成功率/品质、炼器强化成功率。

### 3.3 输入-输出-风险表

| 输入 | 输出 | 风险 / 代价 |
|------|------|-------------|
| 种子 + 灵田 | 灵草 | 季节不对枯萎；生长周期长 |
| 材料 + 丹方 + 炼丹室等级 | 丹药 | 失败损失材料；品质影响效果 |
| 装备 + 材料 + 炼器台等级 | 强化/词缀装备 | 失败掉级或损坏 |

### 3.4 数据模型扩展

#### 3.4.1 `config/crops.json`（已存在，补充字段）

```json
{
  "id": "snow_lotus",
  "name": "雪莲",
  "seed_item_id": "snow_lotus_seed",
  "yield_item_id": "snow_lotus",
  "yield_min": 1,
  "yield_max": 2,
  "growth_months": 6,
  "seasons": ["winter"],
  "requirements": {"min_realm_order": 10},
  "water_bonus": 1  // 浇水额外 +1 生长
}
```

#### 3.4.2 `config/recipes.json`（已存在，建议补充）

```json
{
  "id": "foundation_pill_recipe",
  "name": "筑基丹方",
  "type": "alchemy",
  "materials": {"spirit_herb": 3, "demon_core_mid": 1},
  "yield_item_id": "foundation_pill",
  "yield_count": 1,
  "base_success": 0.6,
  "quality_tiers": ["普通", "上品", "极品"]
}
```

#### 3.4.3 新增 `config/smith_recipes.json`

```json
{
  "id": "enhance_weapon_iron",
  "name": "强化武器·铁",
  "type": "smith",
  "target_slot": "weapon",
  "materials": {"black_iron": 2, "spirit_stone": 100},
  "base_success": 0.75,
  "failure_penalty": "level_down"
}
```

### 3.5 核心接口设计

扩展 `game/farm.py`（已较完整，主要接入建筑等级）。

新增 `game/alchemy_manager.py`：

```python
class AlchemyManager:
    def __init__(self, player, item_library, residence_manager, config=None)
    def get_learned_recipes(self) -> list
    def can_craft(self, recipe_id, batch=1) -> (bool, str)
    def craft(self, recipe_id, batch=1) -> (bool, str, list[Item])
    def _compute_success_rate(self, recipe) -> float
    def _compute_quality(self) -> str
```

新增 `game/smithy_manager.py`：

```python
class SmithyManager:
    def __init__(self, player, item_library, equipment_manager, residence_manager, config=None)
    def can_enhance(self, item, material_id) -> (bool, str)
    def enhance(self, item, material_id) -> (bool, str)
    def can_reforge(self, item, material_id) -> (bool, str)
    def reforge(self, item, material_id) -> (bool, str)
```

### 3.6 关键流程

1. **药园种植**：
   - 地块数 = 2 + `herb_garden` 等级 × 2（已实现）。
   - 播种消耗种子；浇水本月生长 +1。
   - 成熟后收获进入背包。
2. **炼丹**：
   - 玩家在洞府 UI 选择炼丹室 → 选择已学丹方 → 输入批量。
   - 成功率 = 丹方基础成功率 + 炼丹室加成 + 丹修流派加成 + 悟道点加成。
   - 品质按成功率区间随机：普通/上品/极品，影响丹药效果倍率。
   - 失败时扣除材料，可能触发炸炉事件（健康 -10，洞府能量 -50）。
3. **炼器**：
   - 在炼器台选择装备与强化石。
   - 成功率受炼器台等级、器修流派加成影响。
   - 失败惩罚按配置：掉级、损坏、无损失。

### 3.7 UI 入口

- 在 `ui/private_residence_dialog.py` 中新增「药园」「炼丹室」「炼器台」三个标签页。
- 复用 `ui/alchemy_dialog.py` 的配方列表组件，但数据来自 `AlchemyManager`。
- 新增 `ui/smithy_dialog.py`：装备选择、材料选择、成功率预览、强化结果动画。

### 3.8 配置校验

- `recipes.json` 中所有 `materials` 与 `yield_item_id` 在 `items.json` 中存在。
- `smith_recipes.json` 中 `target_slot` 在 `Player.EQUIPMENT_SLOTS` 中。
- `crops.json` 中 `growth_months > 0`。

### 3.9 测试要点

- 建筑等级影响地块数、成功率、品质分布。
- 批量炼丹材料消耗与产出数量正确。
- 炼器失败惩罚按配置生效。
- 丹药品质效果倍率正确作用于战斗/修炼。

---

## 四、模块三：论道、双修、收徒与恩怨链

### 4.1 现状盘点

- `Player` 已预留 `companions`, `master_id`, `disciples`, `sworn_brothers`, `revenge_targets`, `killed_npcs`, `debate_record`, `npc_relationships`, `npc_memory`。
- `game/dialogue.py` 处理 NPC 对话与选择。
- 缺失：论道玩法、双修收益、师徒成长、恩怨链的复仇事件传播。

### 4.2 设计目标

构建动态 NPC 社交网络：玩家通过论道提升道心、通过双修加深道侣关系、通过收徒形成传承、通过恩怨链承担行为后果。

### 4.3 输入-输出-风险表

| 输入 | 输出 | 风险 / 代价 |
|------|------|-------------|
| 时间与 NPC 论道 | 道心、悟性、心法/神通 | 失败降低道心 |
| 与道侣共同闭关 | 双向修为加成、 intimacy 提升 | 道侣可能触发情缘危机事件 |
| 收徒并传授资源 | 徒弟成长、定期上缴 | 徒弟可能背叛或引仇上门 |
| 击杀 NPC | 掉落与任务推进 | 亲友/宗门/道侣复仇 |

### 4.4 数据模型扩展

#### 4.4.1 新增 `config/relationships.json`

```json
{
  "debate": {
    "min_realm_order": 5,
    "cooldown_months": 3,
    "base_win_rate_formula": "player_wisdom / (player_wisdom + npc_wisdom)",
    "rewards": {"mental_state": 5, "wisdom_chance": 0.3},
    "penalty": {"mental_state": -3}
  },
  "dual_cultivation": {
    "min_intimacy": 8,
    "qi_bonus_per_month": 50,
    "intimacy_gain": 1,
    "event_chance": 0.05
  },
  "disciple": {
    "max_disciples": 3,
    "growth_interval_months": 6,
    "tribute_chance": 0.4,
    "betrayal_chance_formula": "max(0, 0.1 - loyalty * 0.001)"
  },
  "grudge_chain": {
    "spread_depth": 2,
    "revenge_delay_months_min": 3,
    "revenge_delay_months_max": 24
  }
}
```

#### 4.4.2 NPC 配置扩展

在 `config/npcs.json` 中为每个 NPC 增加：

```json
{
  "id": "npc_li_yun",
  "wisdom": 12,
  "kin_ids": ["npc_li_mu"],
  "sect_id": "qingyun_sect",
  "lover_id": "npc_zi_yan",
  "master_id": "npc_old_xuan",
  "disciple_ids": ["npc_xiao_jun"],
  "sworn_brother_ids": ["npc_zhang_fei"]
}
```

### 4.5 核心接口设计

新增 `game/relationship_manager.py`：

```python
class RelationshipManager:
    def __init__(self, player, npc_library, world, config=None)

    # 论道
    def can_debate(self, npc_id) -> (bool, str)
    def debate(self, npc_id) -> (bool, str, dict)  # 返回胜负、消息、奖励

    # 双修
    def can_dual_cultivate(self, npc_id) -> (bool, str)
    def dual_cultivate(self, npc_id, months=1) -> (bool, str, dict)

    # 师徒
    def can_accept_master(self, npc_id) -> (bool, str)
    def accept_master(self, npc_id) -> (bool, str)
    def can_take_disciple(self, npc_id) -> (bool, str)
    def take_disciple(self, npc_id) -> (bool, str)
    def tick_disciples(self, year, month) -> list[str]

    # 恩怨链
    def record_kill(self, npc_id)
    def get_grudge_holders(self) -> list[dict]
    def tick_grudge_events(self, year, month) -> list[str]
    def resolve_grudge(self, npc_id, method)  # duel / gift / mediate
```

### 4.6 关键流程

1. **论道**：
   - 在 NPC 对话界面选择「论道」。
   - 判定胜率 = 玩家悟性 / (玩家悟性 + NPC 悟性) + 道心加成 - 心魔惩罚。
   - 胜利：道心 +5，概率悟性 +1，概率解锁 NPC 专属心法。
   - 失败：道心 -3，NPC 好感度 -1。
2. **双修**：
   - 仅对 intimacy ≥ 8 的道侣开放。
   - 共同闭关 1~3 个月：双方每月额外修为 +50，intimacy +1。
   - 5% 概率触发情缘事件（如被 NPC 追求者挑战、获得双修神通）。
3. **收徒**：
   - 玩家境界需高于 NPC 至少一个大境界。
   - 徒弟每 6 个月成长一次（境界随机提升），每成长一次概率上缴资源。
   - 忠诚度低于 30 时可能背叛，背叛后可能泄露玩家位置给仇敌。
4. **恩怨链**：
   - 击杀 NPC 时，读取其 `kin_ids`、`sect_id`、`lover_id`、`master_id`、`disciple_ids`、`sworn_brother_ids`。
   - 这些关联 NPC 进入潜在复仇者池，关系值下降。
   - 3~24 个月后随机触发复仇事件：遭遇战、下毒、绑架道侣等。
   - 复仇可通过战斗胜利、送礼和解、请中间人调解三种方式化解。

### 4.7 UI 入口

- 新增 `ui/relationship_dialog.py`：总览论道、双修、师徒、恩怨列表。
- 在 `ui/npc_dialog.py` 中加入「论道」「结为道侣」「拜师」「收徒」按钮（按条件显示）。
- 复仇事件触发时弹出 `ui/grudge_event_dialog.py`。

### 4.8 配置校验

- `relationships.json` 中公式字符串可被安全解析（或预编译为 lambda）。
- `npcs.json` 中所有关联 NPC ID 必须存在。
- 避免循环师徒关系（A 的师父不能是 A 的徒弟）。

### 4.9 测试要点

- 论道胜负概率符合悟性预期。
- 双修后 intimacy 与修为正确增加。
- 徒弟成长与背叛概率边界。
- 击杀 NPC 后正确生成复仇者列表。
- 复仇事件延迟与化解方式生效。

---

## 五、模块四：宗门战争、外交与世界 BOSS

### 5.1 现状盘点

- `game/sect.py` 已实现：`start_war`（简单胜负判定）、`form_alliance/break_alliance`、外交任务、悬赏榜、护山大阵、捐献排行榜。
- `game/world_boss.py` 已实现：BOSS 刷新、生成、击败记录。
- 缺失：多阶段宗门战争、战争地图/领土变化、世界 BOSS 伤害排名与协作机制、全局正魔大战事件。

### 5.2 设计目标

把宗门战争从单次随机判定扩展为可参与、可影响、有领土变化的事件；世界 BOSS 从单人挑战扩展为全服（存档内 AI 竞争）讨伐。

### 5.3 输入-输出-风险表

| 输入 | 输出 | 风险 / 代价 |
|------|------|-------------|
| 宗门贡献 + 时间 | 战争阶段推进 | 失败损失声望与健康 |
| 外交任务 | 关系变化、同盟 | 失败关系恶化 |
| 参与世界 BOSS 讨伐 | 稀有材料、声望 | 战斗失败重伤 |
| 正魔大战阵营选择 | 全局剧情走向 | 对立阵营追杀 |

### 5.4 数据模型扩展

#### 5.4.1 新增 `config/sect_wars.json`

```json
{
  "wars": [
    {
      "id": "border_conflict",
      "name": "边境冲突",
      "phases": [
        {"name": "先锋战", "type": "combat", "enemy_count": 3, "reward_contribution": 200},
        {"name": "资源争夺", "type": "collect", "target_item": "spirit_stone", "target_count": 100},
        {"name": "宗门对决", "type": "combat", "enemy_level": 10, "reward_contribution": 500}
      ],
      "victory_threshold": 2,
      "relation_shift": -30,
      "territory_reward": "spirit_vein_a"
    }
  ]
}
```

#### 5.4.2 新增 `config/world_boss_events.json`

```python
{
  "events": [
    {
      "boss_id": "ancient_dragon",
      "prelude_months": 3,
      "damage_rewards": [
        {"rank_min": 1, "rank_max": 1, "items": {"dragon_soul": 1}, "reputation": 100},
        {"rank_min": 2, "rank_max": 5, "items": {"dragon_scale": 3}, "reputation": 50}
      ]
    }
  ]
}
```

### 5.5 核心接口设计

新增 `game/sect_war_manager.py`：

```python
class SectWarManager:
    def __init__(self, player, sect_manager, world, config=None)
    def get_available_wars(self) -> list
    def can_start_war(self, war_id, target_sect_id) -> (bool, str)
    def start_war(self, war_id, target_sect_id) -> (bool, str)
    def get_current_phase(self) -> dict
    def resolve_phase(self, player_action, **kwargs) -> (bool, str)
    def finish_war(self, victory) -> (bool, str)
    def tick_war(self, year, month) -> list[str]
```

扩展 `game/world_boss.py`：

```python
class WorldBossManager:
    # 新增
    def record_damage(self, boss_id, damage)
    def get_ranking(self, boss_id) -> list[dict]  # 玩家 + AI 竞争者
    def compute_rewards(self, boss_id) -> dict
    def trigger_world_event(self, boss_id) -> str
```

### 5.6 关键流程

1. **宗门战争**：
   - 玩家在宗门大殿选择「发动宗门战」，选择目标宗门与战争类型。
   - 战争分为 3 个阶段，每阶段持续 1~3 个月。
   - 阶段类型包括：战斗（连续击败敌方弟子）、收集（上缴资源）、防守（抵御入侵）。
   - 玩家可选择参与或派遣追随者代打。
   - 达成胜利阈值后获胜：夺取灵脉/领土，提升宗门声望；失败则关系恶化、健康受损。
2. **外交**：
   - 在现有外交任务基础上，新增「联姻」「结盟」「宣战」「停战」四种外交行动。
   - 外交结果写入 `player.sect_alliances` 与全局关系表。
3. **世界 BOSS**：
   - BOSS 刷新前 3 个月全地图公告。
   - 玩家可前往 BOSS 地点挑战，每次挑战造成伤害。
   - 存档内模拟其他修士（AI）也在讨伐，最终按伤害排名发奖。
   - 首杀触发全服事件，解锁特殊商店或剧情。
4. **正魔大战**：
   - 当正道/魔道阵营值差距达到阈值时，触发全局事件。
   - 玩家选择阵营，参与系列战争阶段。
   - 大战结果影响所有城池政策、NPC 态度、可加入宗门。

### 5.7 UI 入口

- 新增 `ui/sect_war_dialog.py`：战争列表、阶段进度、派遣追随者。
- 新增 `ui/diplomacy_dialog.py`：关系地图、外交行动。
- 扩展 `ui/world_boss_dialog.py`：伤害排名、AI 竞争者、奖励预览。
- 正魔大战触发时全屏事件弹窗 `ui/faction_war_dialog.py`。

### 5.8 配置校验

- `sect_wars.json` 中 `phases` 类型只能是 `combat`/`collect`/`defense`。
- `world_boss_events.json` 中 `boss_id` 在 `world_bosses.json` 中存在。
- 确保外交行动不会导致同盟宗门之间宣战。

### 5.9 测试要点

- 战争阶段推进与胜利判定。
- 领土/灵脉奖励正确写入宗门配置。
- 世界 BOSS 伤害排名计算与 AI 竞争者模拟。
- 正魔大战触发条件与全局状态变化。

---

## 六、模块五：渡劫飞升结局与转世继承

### 6.1 现状盘点

- `Player.MAJOR_REALM_IDS` 已定义大境界突破阈值（练气 9、筑基圆满、金丹圆满）。
- `game/reincarnation_manager.py` 已实现转世点数计算、继承选项、新 Player 生成。
- `game/save_manager.py` 与 `Player.to_dict/from_dict` 已支持存档。
- 缺失：渡劫战斗/心魔玩法、飞升结局、死亡后转世流程接入、更多继承项。

### 6.2 设计目标

为每个大境界突破加入渡劫挑战，为游戏终局提供「飞升成仙」或「转世重修」两种结局，并打通多周目继承。

### 6.3 输入-输出-风险表

| 输入 | 输出 | 风险 / 代价 |
|------|------|-------------|
| 修为达到圆满 | 渡劫事件 | 失败重伤/境界跌落/死亡 |
| 渡劫道具/阵法 | 成功率提升 | 资源消耗 |
| 死亡/飞升 | 转世结算 | 新一世从零开始，仅保留有限继承 |

### 6.4 数据模型扩展

#### 6.4.1 新增 `config/tribulations.json`

```json
{
  "tribulations": [
    {
      "id": "foundation_tribulation",
      "name": "筑基雷劫",
      "trigger_realm_id": "foundation_peak",
      "target_realm_id": "golden_core_early",
      "stages": [
        {"type": "thunder", "waves": 3, "base_damage": 50},
        {"type": "heart_demon", "enemy_id": "heart_demon_foundation"},
        {"type": "thunder", "waves": 5, "base_damage": 80}
      ],
      "success_bonus_items": ["golden_core_pill"],
      "failure_results": ["health_loss", "realm_down"]
    },
    {
      "id": "ascension_tribulation",
      "name": "飞升大劫",
      "trigger_realm_id": "nascent_soul",
      "target_realm_id": "ascended",
      "stages": [
        {"type": "thunder", "waves": 9, "base_damage": 200},
        {"type": "heart_demon", "enemy_id": "heart_demon_ascension"},
        {"type": "divine_trial", "enemy_id": "heavenly_general"}
      ],
      "success_ending": "ascension",
      "failure_results": ["death_or_reincarnation"]
    }
  ]
}
```

#### 6.4.2 新增 `config/endings.json`

```json
{
  "endings": [
    {
      "id": "ascension",
      "name": "飞升成仙",
      "condition": {"type": "tribulation_success", "tribulation_id": "ascension_tribulation"},
      "description": "你破开天门，羽化登仙。",
      "unlocks": ["new_game_plus", "celestial_shop"]
    },
    {
      "id": "demon_lord",
      "name": "魔道巨擘",
      "condition": {"type": "camp", "evil_value": 900},
      "description": "你以杀入道，成为魔道至尊。"
    }
  ]
}
```

#### 6.4.3 扩展 `config/reincarnation.json`

新增更多继承项：

```json
{
  "inheritance_options": [
    {"id": "retain_memory", "name": "保留记忆", "cost": 15, "category": "talent", "effects": {"unlock_dialogue_flags": true}},
    {"id": "carry_equipment", "name": "携带本命法宝", "cost": 20, "category": "item", "effects": {"carry_life_treasure": true}},
    {"id": "sect_favor", "name": "宗门好感", "cost": 10, "category": "relationship", "effects": {"relationship_npc_count": 2, "intimacy_bonus": 3}}
  ]
}
```

### 6.5 核心接口设计

新增 `game/tribulation_manager.py`：

```python
class TribulationManager:
    def __init__(self, player, item_library, enemy_library, world, config=None)
    def get_pending_tribulation(self) -> dict
    def can_attempt_tribulation(self, tribulation_id) -> (bool, str)
    def start_tribulation(self, tribulation_id) -> (bool, str, list)
    def resolve_thunder_wave(self, stage_index, wave_index, formation_active) -> dict
    def resolve_heart_demon(self, stage_index) -> (bool, str)
    def finish_tribulation(self, success) -> (bool, str, str)
    def use_tribulation_item(self, item_id) -> (bool, str)
```

扩展 `game/reincarnation_manager.py`：

```python
class ReincarnationManager:
    # 新增
    def on_player_death(self) -> dict  # 返回转世结算数据
    def on_player_ascension(self) -> dict
    def save_legacy(self, new_player) -> bool  # 写入 legacy 存档
```

### 6.6 关键流程

1. **渡劫触发**：
   - 玩家尝试突破大境界时，若 `realm_id in MAJOR_REALM_IDS`，Engine 调用 `TribulationManager.get_pending_tribulation()`。
   - 弹出渡劫准备界面：可选择使用避雷符、护劫丹、激活护山大阵等提升成功率。
2. **渡劫阶段**：
   - 雷劫：连续多波范围伤害，玩家可消耗真气/护盾硬抗，每波伤害受护阵、丹药、境界影响。
   - 心魔：进入特殊战斗，敌人是玩家心魔（复制玩家属性 + 心魔加成）。
   - 天劫试炼（仅飞升）：与高难度敌人「天将」战斗。
3. **渡劫结果**：
   - 成功：突破到下一境界，获得奖励；飞升则触发结局。
   - 失败：轻伤（健康 -30）、重伤（健康 -60 + 虚弱数月）、境界跌落、死亡。
4. **转世流程**：
   - 死亡或飞升后弹出「转世结算」：展示境界分、名望分、业力等级、可选继承项。
   - 玩家选择后生成新 Player，可选择「重新开始」或「开启新周目」。
   - 新周目保留：转世次数、业力、前世天赋、继承属性/物品/关系。
5. **结局解锁**：
   - 飞升、魔道至尊、正道领袖、逍遥散人等多种结局写入 `player.achievements` 与历史年表。

### 6.7 UI 入口

- 新增 `ui/tribulation_dialog.py`：渡劫准备、阶段展示、雷劫动画、心魔战斗入口。
- 新增 `ui/ending_dialog.py`：结局 CG + 文字 + 解锁内容。
- 新增 `ui/reincarnation_dialog.py`：转世结算、继承项选择。
- 在主菜单新增「新周目」入口。

### 6.8 配置校验

- `tribulations.json` 中 `trigger_realm_id` 与 `target_realm_id` 在 `realms.json` 中存在。
- `endings.json` 中条件类型必须是已知类型。
- `reincarnation.json` 中继承项 cost 非负，category 合法。

### 6.9 测试要点

- 渡劫触发条件与阶段解析。
- 雷劫伤害受道具/护阵影响。
- 心魔敌人属性正确复制玩家。
- 转世后新 Player 正确应用继承。
- 旧存档无 tribulation/ending 字段时兼容。

---

## 七、跨模块集成清单

| 集成点 | 涉及模块 | 处理方式 |
|--------|----------|----------|
| 洞府修炼加成汇总 | 洞府、宗门、设施、心境 | `Engine._compute_cultivation_bonus()` 中新增 `private_residence_bonus` |
| 炼丹/炼器成功率 | 洞府建筑、流派、悟道 | `AlchemyManager._compute_success_rate()` 读取 `ResidenceManager.get_building_effect` |
| NPC 日程与交互 | 论道、双修、任务 | `NPCScheduleManager` 维护 NPC 当前位置，决定可交互选项 |
| 宗门战争与外交 | 宗门、城池、世界事件 | 战争结果写入 `World` 全局状态，影响城池政策 |
| 渡劫与转世 | 存档、结局、新周目 | `SaveManager` 增加 legacy 存档槽，主菜单读取 |
| 历史年表 | 所有模块 | 所有重大事件调用 `Engine.add_chronicle_entry()` |

---

## 八、建议的实施里程碑

### 里程碑 1：洞府经营闭环（2~3 周）

- 完成私人洞府占领、建筑升级、月度维护、入侵战斗。
- 完成药园种植与洞府建筑等级联动。
- 输出：`tests/test_private_residence_manager.py`、`tests/test_farm_integration.py`。

### 里程碑 2：生活技能工作台（2 周）

- 完成炼丹室工作台（成功率、品质、批量）。
- 完成炼器台工作台（强化、重铸、失败惩罚）。
- 输出：`tests/test_alchemy_manager.py`、`tests/test_smithy_manager.py`。

### 里程碑 3：社交网络（2~3 周）

- 完成论道、双修、收徒、恩怨链。
- 输出：`tests/test_relationship_manager.py`。

### 里程碑 4：势力与世界舞台（3 周）

- 完成多阶段宗门战争、外交关系图、世界 BOSS 排名。
- 输出：`tests/test_sect_war_manager.py`、`tests/test_world_boss_ranking.py`。

### 里程碑 5：终局与多周目（2 周）

- 完成渡劫战斗、结局结算、转世继承。
- 输出：`tests/test_tribulation_manager.py`、`tests/test_reincarnation_integration.py`。

---

## 九、验收标准

1. 每个模块完成后 `pytest tests/` 全绿。
2. `tools/validate_configs.py` 对新增配置无报错。
3. 新玩家能在 10 分钟内理解洞府、炼丹、论道等新增核心循环。
4. 旧存档打开后无异常，缺失字段自动补默认值。
5. 关键数值调整可通过修改 JSON 实现，无需改代码。

---

## 十、风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 五个模块同时改动导致 Engine 过于臃肿 | 高 | 每个模块独立 Manager，Engine 仅做组合调用 |
| NPC 关系数据膨胀 | 中 | 关联 ID 仅保存直接一层，复仇链动态计算 |
| 渡劫/转世破坏现有存档 | 高 | 严格旧存档兼容，新增字段全部提供默认值 |
| 世界 BOSS AI 竞争者模拟不真实 | 中 | 使用确定性随机 + 玩家境界加权模拟 |
| UI 弹窗过多 | 中 | 合并相关功能到同一 Dialog 的标签页 |
