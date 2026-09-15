# 《修仙模拟器》功能扩展 — 可行性评估与实现计划

> 配套文档：《修仙模拟器》功能扩展需求文档 v1.0（2025-07-11）
> 编写日期：2026-08-04 ｜ 基于代码实际状态（非项目说明书）梳理
> 目标：把 7 个扩展模块（F-01~F-07）拆解为可落地的架构方案、文件清单、接口设计与里程碑。

---

## 0. 阅读提示：本文与需求文档的基线差异

需求文档预设"在已有系统上扩展"，且要求"不改引擎核心"。经核对 `game/engine.py`、`game/`(40+ Manager)、`ui/`(47 Dialog)、`config/`(扁平 47 json)，结论如下：

- 文档列出的"扩展基线"**大体成立**——底层 Manager 大多已存在。
- 但文档有 **4 处与代码硬性冲突**（见第 1 节），其中"主题"和"引擎零侵入"是方向性问题，必须先决策。
- 文档未意识到：月度 tick 是硬编码在 `cultivate()` 循环里的直接调用，**没有订阅机制**，所以"零侵入"目前做不到，需先做引擎扩展点重构（第 3 节）。

---

## 1. 可行性总体结论

**结论：整体可行，但必须接受"3 项前置改造 + 1 项决策"作为地基，之后各模块才能按文档节奏推进。**

| 冲突 | 文档要求 | 代码现状 | 处置 |
|------|----------|----------|------|
| C1 主题 | §六「深色主题、五行配色」 | `main_window.py` QSS 是**浅色**（`#f0f2f5`/白面板） | **需决策**：改文档（保持浅色）或改代码（做深色主题）。建议本期先统一为浅色+修仙风边框，深色主题作为独立后续优化，避免在 7 模块并行期引入全量 UI 返工。 |
| C2 配置目录 | 示例用 `config/family/`、`config/territory/` 子目录 | `config/` **扁平**，47 个 json；`validate_configs.py` 按扁平加载 | 新增子目录加载器 + 扩展校验器（第 4 节）。 |
| C3 功能开关 | §七要求 `config/feature_flags.json` 开关所有功能 | 不存在 | 新建 `feature_flags.json` + 引擎启动时读取（第 5 节）。 |
| C4 引擎零侵入 | 反复强调"尽量不改动引擎层核心逻辑" | 月度 tick 硬编码于 `cultivate()`，无钩子 | 抽 `_advance_one_month()` + 月度 tick 订阅注册表（第 3 节），核心数值算法不动。 |

---

## 2. 逐模块 Gap 与复用资产（速览）

| 模块 | 代码现状 | 可复用资产 | 新工作量 |
|------|----------|------------|----------|
| F-01 家族/宗族 | ❌ 全新 | `SocialManager`(好感/关系)、`MasterDiscipleManager`(师徒)、`FollowerLibrary`(成员模板)、`ReputationManager`(声望) | 大 |
| F-02 领地建设 | ⚠️ 部分重叠 | `ResidenceManager`(占领灵脉+设施升级)、`SectManager`(护山大阵/五行阵) | 大 |
| F-03 Roguelike 秘境 | ⚠️ 改造升级 | `SecretRealmManager`(解锁/层数)、`EnemyLibrary`、`CombatDialog` | 中 |
| F-04 动态世界事件 | ⚠️ 扩展 | `WorldEventManager`、`WeatherManager`、`ChronicleManager`(年表) | 中 |
| F-05 经济深度 | ⚠️ 扩展+新增 | `AuctionHouseManager`、`StallManager`、`MarketNPCManager` | 小~中 |
| F-06 成就/难度 | ⚠️ 扩展 | `AchievementManager`、`ReincarnationManager` | 小 |
| F-07 多周目模式 | ⚠️ 扩展 | `ReincarnationManager`、`Player`(new_game 创建) | 小 |

---

## 3. 前置改造①：引擎月度 tick 扩展点（解决 C4，最关键）

### 3.1 现状（已核实 `engine.py:497-661`）
`cultivate(months)` 的 `for month_index in range(months):` 循环体内，近 20 个系统通过**直接调用**逐月推进：`residence_manager.tick_monthly()`、`social_manager.tick_grudges()`、`farm_manager.tick_monthly()`、`world_event_manager.tick()`、`world_boss_manager.tick()` 等。此外 `explore()`(游历，半年) 与 `travel()` 也会推进时间，需确认其是否走同样的 tick。

**问题**：新系统（家族结算、领地产出、经济模拟、世界状态变量）无法在不改 `cultivate()` 的情况下被按月驱动。

### 3.2 方案：订阅注册表（最小侵入）
在 `GameEngine.__init__` 中新增：
```python
self._monthly_tick_subscribers = []          # (fn, feature_flag_key)
def register_monthly_tick(self, fn, flag=None):
    self._monthly_tick_subscribers.append((fn, flag))

def _run_monthly_ticks(self):
    for fn, flag in self._monthly_tick_subscribers:
        if flag and not self.feature_flags.get(flag, True):
            continue
        fn()
```
将 `cultivate()` 循环体中**与修为计算无关**的 tick 调用（第 538-661 行）抽取为 `_advance_one_month()`，由 `cultivate/explore/travel` 各自按月调用 `_advance_one_month()`；原直接调用改为在 `__init__` 里 `register_monthly_tick(...)`。

**收益**：
- 新系统（FamilyManager、TerritoryManager、WorldStateManager、MarketManager…）只需在 `__init__` 注册自己的 `tick_monthly`，**完全不碰 `cultivate()` 的数值算法**。
- 配合 `feature_flags` 可整模块热开关。
- 满足"不改动引擎核心逻辑"——核心修炼数学（第 526-536 行）一字未动。

### 3.3 工作量
约 1 周（含抽离、回归测试确保现有系统 tick 行为不变）。**必须在 M1 之前完成。**

---

## 4. 前置改造②：配置子目录加载（解决 C2）

### 4.1 方案
- 新增 `tools/config_loader.py`：`load_config(name, subdir=None)`，优先 `config/{subdir}/{name}.json`，回退 `config/{name}.json`，保证旧扁平配置继续可用。
- 新增 `family/family_members.json`、`family/family_events.json`、`territory/territory_maps.json`、`territory/buildings.json`、`secret_realm/realm_cards.json`、`secret_realm/realm_floors.json`、`world/world_event_chains.json`、`world/weather_effects.json`、`economy/market_dynamics.json`、`economy/trade_routes.json`、`achievement/achievements_v2.json`、`difficulty/difficulty_settings.json`、`meta/new_game_modes.json`。
- 扩展 `tools/validate_configs.py`：按子目录批量校验，新增关联校验（如 `territory_maps.guardian_boss` 必须存在于 `enemies.json`；`realm_cards.apply_to` 必须是合法流派 ID）。

### 4.2 工作量
约 0.5 周（与 §3 并行）。

---

## 5. 前置改造③：feature_flags 框架（解决 C3）

```json
// config/feature_flags.json
{
  "family_system": true,
  "territory_system": true,
  "roguelike_realm": true,
  "dynamic_world_event": true,
  "economy_deep": true,
  "achievement_tier": true,
  "difficulty_modes": true,
  "new_game_modes": true
}
```
- `GameEngine.__init__` 读取为 `self.feature_flags`(dict)，缺省 True。
- UI 入口按钮按 flag 显隐（如「家族」按钮 `if feature_flags.family_system and realm>=金丹`）。
- `Player.to_dict/from_dict` 对新增字段提供默认值，保证旧存档兼容。

---

## 6. 前置决策④：UI 主题（解决 C1）
- **建议**：本期所有新弹窗沿用现有浅色 QSS + 修仙风边框（朱砂印章按钮、卷轴标题），**不强行切换深色**。深色主题作为独立优化项排入 backlog。
- 原因：7 模块并行期改全局主题会导致 47 个旧弹窗 + 新弹窗全部回归，风险与收益不成正比。
- 若产品方坚持深色，则需在 M0 单独排 1~2 周主题重构，且不计入功能模块工期。

---

## 7. 逐模块实现计划

### F-04 动态世界事件深化（M1，优先级 P1）⭐ 建议作为第一个实做模块
- **复用**：`WorldEventManager`(已有) + `WeatherManager`(已有，含 `advance()`/`get_cultivation_speed_bonus`) + `ChronicleManager`(年表)。
- **新增文件**：
  - `game/world_state_manager.py` — 维护全局状态变量（灵气浓度/物价系数/NPC阵营态度/城池安全度），单例挂引擎。
  - `game/world_event_chain_manager.py` — 事件链阶段推进、玩家选择分支、全局效果应用。
  - `ui/world_dynamic_dialog.py`（时间线展示）、`ui/world_event_choice_dialog.py`、`ui/weather_detail_dialog.py`。
  - `config/world/world_event_chains.json`、`config/world/weather_effects.json`。
  - `tests/test_world_state_manager.py`、`tests/test_world_event_chain_manager.py`。
- **引擎接入**：`register_monthly_tick(world_state_manager.tick)`、`register_monthly_tick(world_event_chain_manager.tick)`；天气事件通过 `WorldStateManager` 修改全局系数，现有 `WeatherManager.get_cultivation_speed_bonus` 读取系数。
- **UI 入口**：主窗口顶部加「世界动态」滚动栏（复用 `LogPanel` 风格）；「见闻」分组加「天下大事」按钮。
- **风险**：事件链可能死循环/卡死——需限制链总长与分支最大深度。

### F-05 经济系统深度化（M1，P1）
- **复用**：`AuctionHouseManager`、`StallManager`、`MarketNPCManager`、`EconomyManager`(已有 `economy.json`)。
- **新增文件**：
  - `game/market_manager.py`（动态定价 = 基础价 × 供需 × 事件 × 天气；城市库存）。
  - `game/trade_route_manager.py`（商队派遣、运输结算、`bandit_chance` 劫道事件，复用 `start_combat`）。
  - `game/storage_manager.py`（多仓库容量、自动存取规则）。
  - `game/black_market_manager.py`（事件触发、违禁品交易、被抓判定 → 复用 `ReputationManager`）。
  - `ui/market_trend_dialog.py`（折线图，可用 PyQtGraph 或自绘 `QPainter`）、`ui/trade_route_dialog.py`、`ui/storage_dialog.py`。
  - `config/economy/market_dynamics.json`、`config/economy/trade_routes.json`。
  - 对应 4 个 pytest 文件。
- **引擎接入**：`register_monthly_tick(market_manager.tick)`（重算供需/库存）、`register_monthly_tick(trade_route_manager.tick)`（推进在途商队）。
- **性能**：月度结算 ≤ 2s 硬指标，动态定价 O(物品数) 可控；折线图只算近 12 月。

### F-03 Roguelike 秘境探索（M2，P1）
- **复用**：`SecretRealmManager`(升级而非重写) + `EnemyLibrary` + `CombatDialog`(增益作为额外 buff 层) + `CompendiumManager`(图鉴)。
- **新增文件**：
  - 扩展 `SecretRealmManager`：`generate_floor()` 节点图生成、`enter_realm()`/`exit_realm()`、`tick_progress()`。
  - `game/realm_card_manager.py`（卡牌抽取/叠加/效果应用，挂在 player 临时 buff）。
  - `game/realm_node_manager.py`（节点：战斗/事件/商店/Boss）。
  - `game/realm_reward_manager.py`（秘境币结算、主世界兑换）。
  - `ui/secret_realm_map_dialog.py`（节点连线图，杀戮尖塔风格）、`ui/realm_card_pick_dialog.py`(三选一)、`ui/realm_shop_dialog.py`。
  - `config/secret_realm/realm_cards.json`、`realm_floors.json`。
  - 对应 pytest 文件。
- **联动**：队伍编成复用 `PersonalBeastManager`/`MasterDiscipleManager` 的随从；增益卡与 `CultivationPathConfig` 流派挂钩。

### F-01 修仙家族/宗族系统（M3，P0）⭐ 纯新系统
- **复用**：`SocialManager`(好感/恩怨)、`MasterDiscipleManager`(师徒/招募)、`FollowerLibrary`(成员属性模板)、`ReputationManager`(家族声望)。
- **新增文件**：
  - `game/family_manager.py`（创建/解散/等级/资产）。
  - `game/family_task_manager.py`（任务分配与月度结算，注册月度 tick）。
  - `game/family_event_manager.py`（叛逃/天才觉醒/外敌入侵…，复用现有事件选择 UI 模式）。
  - `game/family_diplomacy_manager.py`（家族↔宗门结盟/对立，复用 `SectManager`）。
  - `ui/family_dialog.py`(总览)、`ui/family_member_dialog.py`、`ui/family_task_dialog.py`、`ui/family_event_dialog.py`、`ui/family_diplomacy_dialog.py`。
  - `config/family/family_members.json`、`family_events.json`、`family_buildings.json`、`family_templates.json`。
  - 对应 pytest 文件。
- **解锁**：金丹期 + 灵石/声望消耗（在 `Player`/解锁检查里加 `has_feature` 类似判定）。
- **联动转世**：死亡时若家族存在，弹「以继承人继续」选项 → 复用 `ReincarnationManager`，保留家族资产。

### F-02 领地建设与扩张（M4，P0）
- **复用**：`ResidenceManager`(占领灵脉/设施)、`SectManager`(护山大阵/五行阵)、战斗"阵地战"复用 `CombatDialog`。
- **新增文件**：
  - `game/territory_manager.py`（获取/升级：灵脉→福地→洞天，网格尺寸随等级放大）。
  - `game/territory_build_manager.py`（建筑放置/拆除/升级，N×M 网格校验）。
  - `game/territory_defense_manager.py`（阵眼五行搭配、妖兽袭扰触发，复用 `start_combat` + 建筑 buff）。
  - `game/territory_production_manager.py`（月度产出，注册月度 tick）。
  - `ui/territory_grid_widget.py`（自定义 `QWidget` 网格绘制 + 拖拽放置，非纯弹窗）。
  - `ui/territory_dialog.py`(俯视)、`ui/territory_build_dialog.py`、`ui/territory_defense_dialog.py`。
  - `config/territory/territory_maps.json`、`buildings.json`。
  - 对应 pytest 文件。
- **解锁**：元婴期（与 `ResidenceManager` 解锁条件一致）。

### F-06 成就与难度系统扩展（M5，P2）
- **复用**：`AchievementManager`(已有基础成就)。
- **新增**：
  - 扩展 `achievement_manager.py`：分级（青铜/白银/黄金/仙金）、隐藏成就、奖励发放（称号带属性、解锁隐藏事件，复用 `event_pool`）。
  - 新增 `game/difficulty_manager.py`（难度选择、全局修正系数，在 `Player` 创建时应用）。
  - `ui/difficulty_select_dialog.py`（新开局界面）、扩展 `achievement_dialog.py` 显示分级/进度。
  - `config/achievement/achievements_v2.json`、`difficulty/difficulty_settings.json`。
  - 对应 pytest 文件。
- **天道追杀模式**：地狱难度专属，每突破大境界触发 `start_combat` 派遣追杀者，复用现有战斗。

### F-07 多周目特殊模式（M5，P2）
- **复用**：`ReincarnationManager`(转世继承)、`Player`(new_game 创建)。
- **新增**：
  - 扩展 `reincarnation_manager.py` + `new_game_modes.json`：夺舍重生(元婴专属)、天道轮回(通关解锁)、凡人挑战(无灵根→仅体修/符修)、魔道独行(锁邪修、正道敌对)。
  - 在角色创建/`_reset_game` 流程接入模式选择，复用 `SpiritualRootDialog`/`CultivationPathDialog` 的条件分支。
  - 对应 pytest 文件（重点测各模式规则继承/丢失是否正确）。

---

## 8. 里程碑细化（依赖顺序）

| 阶段 | 内容 | 依赖 | 工期 | 可验收点 |
|------|------|------|------|----------|
| M0 | 前置改造：引擎 tick 钩子 + 配置子目录 + feature_flags + 主题决策 | 无 | 1.5~2 周 | 旧系统 tick 行为不变；新系统可通过 register 接入；`validate_configs` 过子目录；flag 可关任意模块 |
| M1 | F-04 动态世界事件 + F-05 经济深度 | M0 | 2~3 周 | 事件链可推进并改全局状态；动态定价/商队/仓储/黑市可用；月度结算 ≤2s |
| M2 | F-03 Roguelike 秘境 | M0 | 3~4 周 | 节点图生成、卡牌 Build、秘境币带回主世界 |
| M3 | F-01 家族系统 | M0, M1(经济) | 4~5 周 | 创建/招募/任务/事件/外交/传承全链路 |
| M4 | F-02 领地建设 | M0, M1 | 3~4 周 | 网格放置、护山大阵、袭扰战、领地升级 |
| M5 | F-06 成就/难度 + F-07 多周目 | M0 | 2 周 | 分级/隐藏成就、难度选择、4 种新模式可开局 |
| M6 | 集成测试 + 平衡调优 + Bug 修复 | 全部 | 2~3 周 | 完整通关天道难度无阻断 Bug |

**总工期**：约 17.5~23 周（与文档 16~21 周基本一致，M0 为新增必要地基）。

## 9. 实施进度（已落地）

| 阶段 | 状态 | 说明 |
|------|------|------|
| M0 | ✅ 完成 | 引擎月度 tick 订阅注册表、feature_flags、validate_configs 子目录校验、Player 显式 to_dict/from_dict 存档兼容 |
| M1 | ✅ 完成 | F-04 动态世界事件深化（WorldStateManager + 事件链）+ F-05 经济深度 |
| M2 | ✅ 完成 | F-03 Roguelike 秘境（节点图/卡牌/秘境币/兑换/队伍，5 个 JSON 配置 + 4 子弹窗） |
| M3 | ✅ 完成 | F-01 家族系统（创建/招募/任务/事件/外交/传承全链路 + 4 子弹窗），feature=territory 之外的 flag 均就绪 |
| M4 | ✅ 完成 | F-02 领地建设与扩张（territory_manager.py 四管理器 + TerritoryGridWidget + 3 弹窗；config/territory/ 子目录；元婴期 + flag 门控；22 个新增测试，全量 702 测试通过） |
| M5 | ✅ 完成 | F-06 成就/难度 + F-07 多周目（achievement.py 扩展分级/隐藏/称号 + 进度去重；difficulty_manager.py 四档难度 + 天道追杀；meta_manager.py 5 种模式含可用性与开局效应；config/achievement·difficulty·meta 子目录；难度·模式弹窗接入新游戏链；全量 731 测试通过） |
| M6 | ✅ 完成 | 集成测试 + 平衡调优 + Bug 修复（tools/balance_sim.py 离线平衡模拟 + test_integration_playthrough.py 5 用例；修复领地维护费被钳零的真实经济 bug；全量 737 测试通过，月度结算 ≤2s 零异常） |
| M7 | ✅ 完成 | 验证与交付加固（性能压测 + CI 门禁）：新增 tests/test_performance_stress.py（全难度×全模式矩阵 + 最大负载叠加，断言月度结算≤2s、零结算异常、零阻断）；新增 tools/run_checks.py 一键检查（pytest + 全模式 balance_sim 压测，自动探测 coverage 优雅降级）；新增 .github/workflows/ci.yml（PySide6+pytest+coverage，跑新模块覆盖率报告 + run_checks --quick 性能门禁）；全量 740 测试通过，峰值月度 tick ≈0.000065s |
| M8 | ✅ 完成 | **体验深化·维度① 心魔与道心**：在既有 MentalStateManager 上补齐 5 条链路——①心魔滋生（杀戮/违戒正道修魔功/重大挫折家族覆灭）②大境界突破心魔过高强制触发心魔劫幻境（3 场景×抉择永久改性格标签+后续概率）③高道心天人合一顿悟（海量修为/领悟神通）④游历名山增长道心 ⑤月度自然衰变。配置扩展 mental_state.json（precept_violations/major_setbacks/travel_dao_heart/heart_demon_tribulation/unity_enlightenment）；Player 加 personality_tags/tribulation_effects 存档兼容；engine 经 M0 插座接线（register_monthly_tick + 突破/杀戮/游历/学功/解散钩子）；新增 HeartDemonDialog + HeartDemonTribulationDialog + 心魔·道心按钮（flag 门控）；validate_configs 加 validate_mental_state；新增 23 测试（manager 16 + dialog 3 + engine 4）；全量 **763 测试通过**。 |

| M9 | ✅ 完成 | **体验深化·维度④ 天道反噬与生态平衡 + 维度⑤ 寿元与轮回晚年**：均为低风险加法式。④ `HeavenRetributionManager`——灵脉枯竭（领地 spirit_stone 抽取超品阶承载力→枯竭累积→满值产出归零+地脉怨气攻城）、天道注视（战力/财富暴涨监测→无妄之灾/杀人夺宝/坊市拒交易，散财/行善/隐世消除），与 difficulty_manager「天道追杀」严格划界；⑤ `LifespanManager`——坐化安排后事（继承人/留功法/引爆法宝→转世转化为前世遗产）、残魂夺舍/器灵化身（高阶神魂依附法宝/灵兽、月度重塑肉身）、前世遗迹回响（探索概率触发）。Player 加 heaven_gaze/sit_pending/past_life_arrangements/remnant_soul/is_remnant/remnant_months/past_life_relics 并存档兼容（is_remnant 纳入 is_alive）；config 加 heaven_retribution.json / lifespan.json 及 feature_flags 两开关；engine 经 M0 插座接线（register_monthly_tick + explore 游历危害/回响 + _check_death 坐化转化）；新增 heaven_retribution_dialog + lifespan_dialog + 两按钮；validate_configs 加 validate_heaven_retribution/validate_lifespan；新增 27 测试；全量 **790 测试通过**。 |
| M10 | ✅ 完成 | **体验深化·维度② 红尘炼心 / 入世**：以「入世历练」开关 + 红尘羁绊（情缘/知己/挚友/红颜/恩怨五类，各对道心/心魔有不同牵引）+ 月度随机事件 + 情劫抉择（3 场景×2 抉择永久改变道心/心魔）+ 归隐出尘沉淀心境，淬炼既有的 MentalStateManager 道心/心魔属性（单一真相源、边界钳制 0-100）。`RedDustManager` 纯加法式接入，未入世时 tick 为 no-op；状态持久化 player.red_dust_active/red_dust_bonds/red_dust_months/red_dust_pending_qingjie 并存档兼容；config/red_dust.json + feature_flags.red_dust 开关；engine 经 M0 插座接线（register_monthly_tick(_tick_red_dust, flag=red_dust) + enter/exit/experience/apply_qingjie_choice 动作）；新增 red_dust_dialog + 「红尘炼心」按钮（flag 门控、无境界门槛）；validate_configs 加 validate_red_dust（于 update_all 第 12 项）；新增 21 测试（manager 16 + engine/dialog 5）；全量 **811 测试通过**。 |
| M11 | ✅ 完成 | **体验深化·维度③ 百家争鸣 / 非传统修仙路线**：最小可玩版，三支柱纯加法式接入 M0 月度插座 + feature_flags.hundred_schools。①立派传道·气运反哺（金丹期+灵石开宗→弟子/气运累积→月度灵石反哺，并用 pending_stones 小数累积器避免低气运期被 int 截断丢光→可耗气运「道韵灌顶」增益道心）②自创功法（金丹期+灵石推演→明心见性→月度道心微涨）③生活流派御劫（择丹/器/阵/符精进→达阈值后按概率化解大境界突破的心魔劫，与维度① heart_demon 协同）。`HundredSchoolsManager` 状态持久化 player.founded_sect/self_created_techniques/life_path/life_path_proficiency 并存档兼容；config/hundred_schools.json + feature_flags 加 hundred_schools；engine 经 M0 插座接线（register_monthly_tick(_tick_hundred_schools, flag=hundred_schools)→发放灵石物品，+found_sect/create_technique/choose_life_path/spend_qi_yun_for_enlightenment 动作，心魔劫触发处接 should_mitigate_heart_demon_tribulation）；新增 hundred_schools_dialog + 「百家争鸣」按钮（flag 门控、无境界门槛）；validate_configs 加 validate_hundred_schools（于 validate_all 第 13 项，含 sect/technique/life_path 校验，qi_yun_per_new_disciple 等比率字段按数值校验）；新增 18 测试（manager 9 + engine/dialog 9）；全量 **829 测试通过**，无回归。 |
| M12 | ✅ 完成 | **维度③ 真正"生效"（自创功法接入技能体系 + 生活流派产出真实物品）：** 把 M11 的两条"偏装饰"效果落地为真实玩法。①自创功法→真实可施展 Skill：config 加 `skill_templates`(8 流派战斗参数) + `attribute_element`(属性→五行 metal/wood/water/fire/earth)；`create_technique` 生成稳定 `skill_id="self_tech_N"`；engine 在成功后 `Skill(**kwargs)` 注册进 `skill_library.skills[id]` 并 `player.learn_skill(id)`；**关键修复读档丢失**——引擎 `__init__` 末尾 `_register_self_created_skills()` 幂等地把已存 `self_created_techniques` 重注册为 Skill（因 skill_library 由 skills.json 重建、自创 Skill 不持久化）；`build_skill_kwargs` 由 manager 提供映射。②生活流派产出真实物品：config `life_path.produce` 按流派映射 item_id/every_months/min_proficiency；manager `tick_monthly` 按 `age_months%every==0` 产出物品 id 经 `rewards.produced_items`；engine `_tick_hundred_schools` 经 `item_library.create`+`player.add_item` 发放（丹道→qi_pill、器修→spirit_wood_sword、符箓→新增 talisman_paper、阵法→新增 array_disk，二者为 consumable 类型新物品）；UI 弹窗标注"✓已可施展"与产出物名。`validate_hundred_schools` 增 skill_templates/attribute_element/produce 校验；新增 7 测试（manager 4 + engine 3：含读档重注册、tick 产出）；全量 **836 测试通过**，无回归，配置校验全绿。 |

| M13 | ✅ 完成 | **五维度端到端平衡回归（E2E regression）**：把 M8~M12 的五维度（心魔道心/红尘炼心/百家争鸣/天道反噬/寿元轮回）纳入 M6 平衡模拟与 M7 门禁，确保跨系统零崩溃、存档可 round-trip。`tools/balance_sim.py` 新增 `setup_dimension_systems`（演练心魔劫/红尘/百家/天道动作）、`exercise_lifespan_events`（残魂化身化身后仍 is_alive）、`save_load_roundtrip`（DIM_FIELDS 字段 to_dict→from_dict→to_dict 一致）；`run_checks.py` 的 `NEW_MODULES` 扩入 mental_state/red_dust_manager/hundred_schools_manager/heaven_retribution_manager/lifespan_manager；新增 `tests/test_e2e_playthrough.py`（4 用例：全维度动作闭环、存档 round-trip、残魂化身 is_alive、维度状态记录）。**关键修复**：`setup_playthrough`/`run_playthrough` 是无头共享 harness（被 integration/performance 测试直接调用），M13 初版无条件改动玩家终态（额外突破/残魂化身/境界抬升）致 4 失败；改为加 `exercise_dimensions=False` 形参门控维度演练/残魂/round-trip，仅 E2E 测试与 run_checks 传 True，对集成/性能测试零侵入。全量 **840 测试通过**，无回归，配置校验全绿。 |
| M14 | ✅ 完成 | **维度③ 生活流派产出物「可用化」（produce→consume 闭环）**：M12 让生活流派（丹/器/符/阵）月度产出真实物品，但 M12 新增的两种 consumable（自绘符箓 talisman_paper、布设阵盘 array_disk）当时**无 effects**，在 `engine.use_item` 中被判「无法直接使用」而沦为死物。本里程碑：① `config/items.json` 为二者补齐 effects——符箓为镇心符（道心+4 / 心魔-3 / 气血+20，与维度①②联动）、阵盘为聚灵阵（修为+80 / 悟性+2），并同步更新描述标注「可于背包服用」；② `engine.use_item` 常规效果段新增 `mental_state`(钳制0-100) 与 `heart_demon`(钳制0-100) 两种效果键，并把消耗判定由仅 `pill` 改为 `pill`/`consumable`，使带效果的消耗品使用后正确退包——**顺带修复**了 detox_pill/info_scroll 等既有 consumable 因不退包而可无限复用的问题；③ 新增 `tests/test_lifepath_items_usable.py`（6 用例：符箓道心/心魔/气血生效+退包、道心钳制上限、心魔钳制下限、阵盘修为/悟性生效+退包、灵木剑可装备、补气丹可服用）。纯加法式零侵入，`use_item` 行为对既有 pill 不变（仅新增键 + 修复 consumable 退包）。全量 **846 测试通过**，无回归，配置校验全绿。 |
| M15 | ✅ 完成 | **维度③ 生活流派产物「进入战斗循环」（produce→consume→战斗增益闭环）：** 此前符箓/阵盘只是背包即时属性物品，未真正影响战斗。本里程碑复用引擎原生战斗 buff 体系（`player_attack_up`/`enemy_attack_down`/`player_shield`，已由伤害计算消费、`start_combat` 每场重置），把生活法宝做成"战斗中临时增益"。① `config/hundred_schools.json` 的 `life_path.produce` 给 talisman(符箓/镇心符) 与 array(阵盘/聚灵阵) 加 `battle_buff`——符箓=敌方攻-15%持续3回合+护盾30，阵盘=己方攻+20%持续3回合（alamy/artifact 不改，其产物为即时属性/武器）；② `engine.deploy_battle_consumable(item_id)` 校验 flag/持有/消耗1个/施加战斗 buff+notify，无货或非部署物安全失败；`_auto_deploy_lifepath_consumables()` 在 `start_combat` 经 `is_feature_enabled("hundred_schools")` 门控自动调用；③ `choose_life_path` 选符箓/阵法时把 `player.lifepath_auto_deploy` 设为 True（旧档/其他流派默认 False，对既有战斗数值基线零影响）；④ `game/player.py` 加 `lifepath_auto_deploy` 并在 to_dict/from_dict 存档兼容；⑤ `tools/validate_configs.py` 的 `validate_hundred_schools` 增 `battle_buff` 合法键校验；⑥ 新增 `tests/test_lifepath_battle_buff.py`（7 用例：符箓削敌攻+护盾+退包、阵盘攻加成、无货失败、非部署物失败、战斗开始自动部署、未选流派不部署、下场战斗重置）。纯加法式零侵入，buff 随 `_tick_buffs` 衰减、下场重置。全量 **853 测试通过**，无回归，配置校验全绿。 |
| M16 | ✅ 完成 | **维度③ 生活法宝「战斗部署」玩家自主权（修正 M15 设计瑕疵）：** M15 让符箓/阵法流派在战斗开始**无脑自动消耗**法宝，玩家既不能手动部署、也无法关闭——违背"玩家自主"。本里程碑把控制权交还玩家（纯加法、零侵入引擎核心）：① `engine.get_deployable_battle_consumables()` 返回玩家持有且 `life_path.produce` 带 `battle_buff` 的物品清单（item_id/name/count/desc），供战斗内手动部署 UI 与发现提示（flag 门控、无货返回空）；② `ui/hundred_schools_dialog.py` 在符箓/阵法流派下新增 `QCheckBox`「战斗自动部署法宝」绑定 `player.lifepath_auto_deploy`，玩家可随时关闭（默认仍随 `choose_life_path` 开启，保持无缝体验，但变为可逆而非强制）；③ `ui/combat_dialog.py` 操作栏加「部署法宝」按钮，连 `_on_deploy_treasure`（取持有最多的可部署法宝调用 `deploy_battle_consumable` 并刷新日志/buff 状态栏），`_refresh_status` 按 `get_deployable_battle_consumables` 动态启用/禁用该按钮；④ 新增 `tests/test_lifepath_battle_buff.py` 2 用例（`test_get_deployable_lists_held_battle_consumables`、`test_toggle_off_auto_deploy_prevents_auto_consume`，共 9 用例）。全量 **855 测试通过**，无回归，配置校验全绿；两个 dialog 已直接 import 校验无语法/加载错误。 |
| M17 | ✅ 完成 | **维度③ 数值平衡审计与校准（M6「平衡调优」的补全）：** 新增 `tools/balance_audit.py` 离线审计工具，复用 `balance_sim.build_engine` 对维度③三支柱做受控模拟并量化输出——①立派传道：气运约 37 月封顶、稳态灵石反哺 30/月（判定合理，不改）；②自创功法：满 5 门约 33 月道心满 100（偏快但属"明心见性"设计奖励，审计报告标注观察、暂不改）；③生活流派产出：符箓每2月/阵盘每4月/丹道每3月/器修每6月各 1 件；④战斗增益：符箓（敌攻-15%+护盾30）/阵盘（己攻+20%）有战斗增益而丹道/器修无。**关键校准**：自动部署默认改为关（`choose_life_path` 不再默认 `lifepath_auto_deploy=True`），消除"选符箓/阵法即默认白嫖战斗增益"的流派战斗强度不对称；玩家可在百家争鸣面板主动勾选或战斗中手动部署（M16 自主权保留；UI checkbox 经 `setChecked(player.lifepath_auto_deploy)` 已自然跟随默认不勾）。更新 `tests/test_lifepath_battle_buff.py` 测试 5/7 反映新默认。全量 **855 测试通过**（仅改默认行为 + 审计工具，未增 pytest 计数），配置校验全绿。 |
| M18 | ✅ 完成 | **维度③ 丹道「灵力温养」持续修炼增益（补偿丹道相对符箓/阵法的战斗增益弱势）：** M17 审计指出符箓/阵法有战斗增益而丹道（补气丹仅即时+50修为，相对突破数千需求效用极低）、器修（永久武器）无战斗增益，造成流派价值不对称。本里程碑让丹道成为"长期成长"路线——补气丹服用后引发「灵力温养」：此后 3 个月内每月额外 +40 修为（与丹道 life_path 每 3 月产 1 丹的节奏契合，形成可持续成长引擎）。纯加法、零侵入引擎核心：① `config/items.json` 的 `qi_pill.effects` 加 `cultivation_boost:{amount:40,months:3}` 并改描述；② `game/player.py` 加 `cultivation_boost_months`/`cultivation_boost_amount` 并在 `to_dict`/`from_dict` 存档兼容（旧档默认 0）；③ `engine.use_item` 常规效果段读取 `cultivation_boost` 设置玩家增益；④ `engine.cultivate` 月度循环内每月经该增益加修为并递减月数；⑤ `tools/validate_configs.py` 新增 `validate_item_effects`（第 14 项）校验 `cultivation_boost.amount/months` 为正整数；⑥ 新增 `tests/test_lifepath_dan_cultivation_buff.py`（4 用例：即时+持续设置、月度附加到期递减、存档 round-trip、非丹道物品不触发）。全量 **859 测试通过**（855+4），无回归，配置校验全绿。 |

| M19 | ✅ 完成 | **维度③ 自创功法「功法推演」养成式小游戏（capstone 子系统）：** 自创功法从"一次性填参注册成 Skill"升级为「推演→逐节点参悟→大成」的养成过程，深度化维度③核心玩法。设计要点：新增 `config/hundred_schools.json` 的 `self_created_technique.deduction` 块（节点类型 参悟/炼炁/凝元/御器，各含 stat/quality/success/desc；品质阶 凡/灵/仙/道 各含 min_quality+mult）；每参悟一节点累积「品质」（成功全额/滞涩半额），品质达阶位阈值决定功法品质，大成时按阶乘算最终 Skill 的 base_damage/realm_multiplier/weapon_multiplier/heal/heal_realm_multiplier。`game/hundred_schools_manager`：`create_technique` 重构为内部 `_make_technique_dict`；新增 `start_deduction`/`resolve_deduction_node(force_success)`/`commit_deduction`/`get_deduction_status`/`_tier_for_quality`；`build_skill_kwargs` 按 `tech.quality` 乘算并标注品阶（旧功法 quality=0 不受影响）。`game/player` 加 `pending_deduction` 并 to_dict/from_dict 兼容。`game/engine` 加 `start/resolve/commit_technique_deduction` 三委托，commit 经 `_register_one_self_created_skill` 注册 Skill（与 create_technique 一致）。`ui/hundred_schools_dialog` 加「功法推演（养成式）」按钮（开推演→逐节点随机参悟→大成）。`tools/validate_configs.py` 增 deduction 块校验。新增 `tests/test_technique_deduction.py`（8 用例）。**重要纠正**：M18 行曾称"器修无战斗增益"——实测 `player.attack` 器修有 `equipment_bonus_mult=2.0`（装备加成翻倍）+ 既有 `refined_weapon_ids` 祭炼（+5 基础攻击/武器）机制，器修已是强永久装备路线，故 M17 审计所虑的"器修补偿"经复核判定为多虑，M19 未做器修补偿（避免过度强化）。全量 **867 测试通过**（859+8），无回归，配置校验全绿。 |

| M20 | ✅ 完成 | **维度① 道境被动深化（把平面 5 档心境等级升级为「道境」身份化被动）：** 既有 `mental_state_levels` 仅提供速度/突破/心魔衰减的数值加成，缺乏可感知的"道境"身份。本里程碑给顶部两阶补 `passive` 字段，让高道心获得身份化被动——①**无漏之境**（道心≥80）：心魔事件免疫 + 天人合一月几率 ×1.5；②**护道之境**（道心≥60）：突破失败不再折损道心 + 游历名山道心增长 ×1.5。纯加法、零侵入引擎核心：`config/mental_state.json` 顶部两阶加 `passive`（name/desc + 类型化键）；`game/mental_state.py` 新增 `get_passive()` 并在 `check_heart_demon_events`/`maybe_unity_enlightenment`/`on_breakthrough`/`on_travel` 四个既有方法内消费被动、新增 `get_dao_realm_status()` 供 UI；`tools/validate_configs.py` 的 `validate_mental_state` 增第 7 节校验 `mental_state_levels` 结构与 `passive` 合法键/类型；`ui/heart_demon_dialog.py` 增「道境」区块展示当前道境名、被动名+描述、距下一阶所需道心；未改 Player 字段（无存档兼容负担，被动由配置派生）。新增 `tests/test_dao_realm_passives.py`（13 用例：四类被动 + 道境状态查询）。全量 **880 测试通过**（867+13），无回归，配置校验全绿。 |

| M21 | ✅ 完成 | **维度② 红尘羁绊共鸣（Resonance）+ 温养（Warmth）养成回路：** 维度②此前羁绊只是"数值牵引道心/心魔"，缺乏随亲密度成长的养成弧光（五维中最薄）。本里程碑把羁绊升级为可养成的「共鸣」资产——亲密度达阈值解锁身份化共鸣被动，月度稳定滋养道心/抑制心魔，并以灵石温养主动升温。纯加法、零侵入引擎核心、未改 Player 字段（无旧档兼容负担）：① `config/red_dust.json` 新增 `bond_resonance`（情缘/知己/挚友/红颜/恩怨五类各 2 档、按 min_intimacy 40/80 升序，每档含 name/monthly_mental/monthly_heart/desc）+ `warmth`（cost_item=spirit_stone, cost_count=5, intimacy_gain=8）；② `game/red_dust_manager.py` 新增 `get_resonance`/`get_warmth`/`_resonance_for`/`get_resonances`/`_apply_resonance_tick`（独立方法便于确定性测试）/`warm_bond`（消耗灵石升温、不足失败、钳制 intimacy_max），`tick_monthly` 末尾调用 `_apply_resonance_tick`；③ `game/engine.py` 维度② 动作区新增 `red_dust_warm(bond_type)` 委托；④ `tools/validate_configs.py` 的 `validate_red_dust` 增第 8 节校验 `bond_resonance`（键为 bond_types 子集、按 min 升序唯一、字段合法、跳过 `_comment`）与 `warmth`；⑤ `ui/red_dust_dialog.py` 每条羁绊展示共鸣档（当前共鸣名+描述，或距下一共鸣所需亲密度）并加「温养」按钮（连 `engine.red_dust_warm`）；⑥ 新增 `tests/test_red_dust_resonance.py`（18 用例：共鸣阈值解锁、月度消费含正/负 heart、温养消耗/上限/不足/未入世/无此羁绊、状态暴露、配置校验合法/非法升序/缺字段、引擎委托接线）。全量 **898 测试通过**（880+18），无回归，配置校验全绿；`red_dust_dialog` import 校验通过。 |

| M22 | ✅ 完成 | **维度④ 天道反噬事件池（Retribution Events）扩充：** 维度④此前注视高时仅产生"无妄之灾/杀人夺宝/拒交易"三类概率日志，缺乏有叙事、有多样后果的事件池。本里程碑新增配置驱动的反噬事件池，让高注视外出游历时按等级概率触发其一，后果多样化且可感知。纯加法、零侵入引擎核心、未改 Player 字段（无旧档兼容负担）：① `config/heaven_retribution.json` 三档 gaze level 各加 `retribution_event_chance`（low 0.10/mid 0.20/high 0.35）+ 顶层新增 `retribution_events` 数组（6 事件：雷劫轻谴/灵宝蒙尘/心魔低语/追夺天降/道心崩裂/大劫加身，各含 id/name/desc/min_gaze/weight/effects{qi_loss|stone_loss|mental_delta|heart_delta|spawn_enemy}）；② `game/heaven_retribution_manager.py` 的 `Config` 加 `get_retribution_events`，新增 `get_event_chance_for_level`、`roll_retribution_event(engine,rng)`（按 min_gaze 阈值筛选+weight 加权抽取+应用四类效果并钳制 0-100+spawn_enemy 召来追夺者开战）、`_apply_retribution_event`，并在既有 `roll_travel_hazard` 末尾调用；`get_status` 暴露 `eligible_events`（含 id/name/desc）与 `event_chance`；③ `tools/validate_configs.py` 的 `validate_heaven_retribution` 增第 3 节校验 `retribution_events`（id 唯一/name·desc 字符串/min_gaze 整数/weight 正数/effects 合法键与类型）与 levels.retribution_event_chance∈[0,1]；④ `ui/heaven_retribution_dialog.py` 增「天道反噬事件（外出时可能降临）」区块展示当前注视下可被触发的事件名+描述与触发概率；⑤ 新增 `tests/test_heaven_retribution_events.py`（13 用例：配置加载/min_gaze 分级筛选/阈值门跳过/四类效果应用与钳制/召战/roll_travel_hazard 集成/配置合法与非法校验）。全量 **911 测试通过**（898+13），无回归，配置校验全绿；`heaven_retribution_dialog` import 校验通过。 |

| M23 | ✅ 完成 | **维度⑤ 寿元轮回·残魂化身形态分化（Resonance Forms）：** 维度⑤残魂此前只有"依附法宝/灵兽"两类载体，缺乏按神魂资质分化的"形态"。本里程碑在化为残魂时按玩家道心/心魔/依附载体自动解锁不同形态（道魂/剑魂/妖灵/无相），每种带月度被动（道心滋养/心魔抑制/重塑加速），与 M20 道境被动、M21 羁绊共鸣同一范式。纯加法、零侵入核心判定（host_types 不变）、未改 Player 顶级字段（form 作为 `remnant_soul` dict 的可选键，整存整取天然向后兼容，无旧档兼容负担）：① `config/lifespan.json` 的 `remnant_soul` 块新增 `default_form="formless"` 与 `forms` 数组（dao_soul 道心≥80&心魔≤20、sword_soul require_host=treasure&道心≥40、beast_soul require_host=spirit_beast&道心≥40、formless 兜底；每 form 含 id/name/desc/min_mental_state/max_heart_demon/require_host/monthly_passive{mental_delta,heart_delta,reshape_bonus}）；② `game/lifespan_manager.py` 的 `Config` 加 `get_forms`/`get_default_form`，管理器加 `_get_form`/`_select_form`（取满足条件中 min_mental_state 最高者，无则 default）/`_apply_form_passive`/`_form_status`，`become_remnant_soul` 写入 `remnant_soul["form"]` 并更新通知文案，`tick_remnant_soul` 月度应用 passive 且重塑几率叠加 `reshape_bonus`，`get_status` 暴露 `remnant_form`；③ `tools/validate_configs.py` 的 `validate_lifespan` 第 2 节增 forms 校验（id 唯一/name·desc 字符串/min_mental_state·max_heart_demon 整数/require_host 合法值/monthly_passive 合法键与类型/default_form 指向存在 id）；④ `ui/lifespan_dialog.py` 残魂区块展示当前形态名+描述+月度被动（道心/心魔/重塑几率）；⑤ 新增 `tests/test_lifespan_remnant_forms.py`（13 用例：形态选择优先级/require_host 限制/default 回退/月度 passive 应用/重塑加成/状态暴露/旧档 form 缺省兼容/配置合法与非法校验）。全量 **924 测试通过**（911+13），无回归，配置校验全绿；`lifespan_dialog` import 校验通过。**至此五维度深化闭环完成**（①道境被动②羁绊共鸣③百家争鸣三支柱④反噬事件池⑤残魂形态分化）。 |

| M24 | ✅ 完成 | **战斗前可部署法宝预览确认弹窗（完善 M15/M16 战斗部署 UX）：** 维度③生活法宝战斗部署虽已有「部署法宝」按钮（M16），但原逻辑只会部署"持有最多的一类"且**无预览**，玩家看不到各法宝的增益描述、也无法多选。本里程碑新增独立模态弹窗 `ui/deploy_treasure_dialog.py` 的 `DeployPreviewDialog`，开战前/战斗中列出所有可部署法宝（名称/持有数/增益描述）并逐项勾选+「确认部署/暂不部署」，确认后逐件消耗施加临时增益。纯 UI 层加法、零侵入引擎与配置（复用 `engine.get_deployable_battle_consumables` 与 `deploy_battle_consumable` 既有接口）：① 弹窗含静态 `deploy_chosen(engine, ids)`（逐件部署、仅返成功项、跳过不可部署）与 `run(engine, parent)`（弹窗并部署）；② `ui/combat_dialog.py` 的「部署法宝」按钮 `_on_deploy_treasure` 改为打开该弹窗（替代原 max-count 单件部署），确认后写日志+刷新 buff 状态栏；③ `ui/main_window.py` 的 `_open_combat` 在构造 CombatDialog **之前**、以 `hundred_schools 开启 且 未开 lifepath_auto_deploy 且 有可部署法宝` 为门控地自动弹出预览——实现真正的"战斗前预览确认"，且因 `start_combat` 已先执行、buff 容器已初始化、门控避免与自动部署重复，时序安全（测试 `test_ui_portrait` 构造 CombatDialog 不调用 exec，不受影响）。新增 `tests/test_deploy_treasure_dialog.py`（8 用例：勾选框构造/默认全勾/取消剔除/空列表/逐件部署消耗与跳过/exec=Accepted 真实部署/exec=Rejected 不部署/combat 按钮接线）。全量 **932 测试通过**（924+8），无回归，配置校验全绿；三个 dialog 模块 import 校验通过。 |

| M25 | ✅ 完成 | **多周目/轮回·前世遗物链（跨世累积纵向成长）：** 此前前世遗物（past_life_relics）仅是惰性叙事、转世即清零，与"跨世累积"的轮回主题脱节。本里程碑新增持久 `player.relic_chain`（跨世保留的遗物 id 集合）+ 配置驱动 `relic_chains`（两条链：三遗归元、遗泽功藏，各含 links/per_link/set 加成键），把"收集遗物"升级为纵向成长投资：每收集到一条链的一个 link，下次转世即获 per_link 永久加成（属性/修炼速度/突破），集齐全部 link 额外获 set 加成。`game/lifespan_manager`：`_record_relic` 把遗物同时记入本世列表与持久链（去重+首入链提示），坐化留功法与探索回响均经其入链；新增纯函数 `compute_relic_chain_bonus`（多链聚合、便于测试与转世复用）+ `get_relic_chain_status`（UI 进度）；`get_status` 暴露 `relic_chains_status`。`game/reincarnation_manager`：`apply_inheritance` 计算并携带 `relic_chain`/`relic_chain_bonuses`，`create_new_player` 跨世保留 relic_chain 并应用链加成（属性加法 / 叠加既有 reincarnation_cultivation_bonus·reincarnation_breakthrough_bonus）。`game/engine.apply_reincarnation` 摘要新增 `relic_chain_bonuses`；`game/player` 加 `relic_chain` 并 to_dict/from_dict 存档兼容（旧档默认 []）。`tools/validate_configs.validate_lifespan` 增第 4 节校验遗物链（id 唯一/links 合法指向已知遗物 id/加成键与类型）。UI：`lifespan_dialog` 增「前世遗物链」进度区（每环/圆满加成、集齐标记），`reincarnation_dialog`「前世因果」区展示转世链加成摘要。新增 14 测试（纯函数加成/去重入链/坐化·探索记链/链进度状态/转世应用与携带/配置合法与非法）；全量 **946 测试通过**（932+14），无回归，配置校验全绿；四个改动模块 import 校验通过。 |

**下一步**：五维度体验深化闭环已完整（M20–M23），战斗部署 UX 经 M24 补完"预览确认"，轮回纵向成长经 M25 补完"前世遗物链"。余下候选：①E2E 维度压测接入 CI（run_checks 已开启 balance_sim）；②balance_audit 接入 CI 或加 smoke 测试（丹道持续增益上线后重跑看长期成长曲线）；③生活流派产出价值再审计；④转世天赋树真正"树状化"（既有 inheritance_options 为扁平成本选点，可加 tier/requires 前置分层）；⑤其余战斗 UX 打磨（法宝部署后回合内可视化倒计时、多件同法宝叠加提示）。

---

## 9. 风险与应对（结合代码实际）

| 风险 | 应对（代码层） |
|------|----------------|
| 引擎耦合 | M0 抽 `_advance_one_month()` + 订阅注册表，新系统只 register 不碰核心；系统间经 `notify`/事件总线通信。 |
| 数值平衡崩坏 | 所有数值进 JSON；新增 `tools/balance_sim.py` 离线模拟月度结算；先做纸面验证。 |
| JSON 配置膨胀 | 按 §4 子目录分模块；`validate_configs.py` 加关联校验（外键一致性）。 |
| 性能瓶颈 | 月度 tick 已为单线程循环；动态定价/供需 O(物品数) 可控；折线图仅近 12 月；非关键计算（如趋势图）延迟到打开弹窗时算。 |
| 旧存档兼容 | 所有新字段在 `Player.to_dict/from_dict` 给默认值；M0 加「存档迁移」自检。 |
| 主题冲突(C1) | 见 §6，本期保持浅色，深色入 backlog。 |

---

## 10. 验收标准落地映射（文档 §七）

| 文档验收项 | 落地方式 |
|------------|----------|
| 所有功能经 `feature_flags.json` 开关 | §5 框架 + 每模块注册时带 flag |
| 新增 Manager 全部通过 pytest（≥80%） | 每模块配套 tests/，CI 跑 `pytest tests/` |
| 旧存档可加载 | §9「旧存档兼容」+ M6 回归 |
| 通关天道难度无阻断 Bug | M5 难度 + M6 集成测试 |
| 月度结算 ≤2s | M1 性能基线 + `tools/balance_sim.py` 计时 |

---

## 11. 建议的下一步执行顺序
1. **先落 M0**（前置改造）——它是所有模块的"插座"，不做则后续无法零侵入接入。
2. **M1 从 F-04 入手**（动态世界事件）：复用度最高、风险最低、能最快验证"订阅注册表 + 新 Manager + 新弹窗 + 配置子目录"这一整套新范式是否跑通。
3. 范式跑通后，F-05/F-03 依葫芦画瓢；F-01/F-02 体量最大，放在范式稳定后。
