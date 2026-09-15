# 10 大 Feature Master 实施计划

本计划按「依赖少 → 依赖多」「底层 → 表现」的顺序排列，每完成一个 Feature 都会跑通完整测试套件，避免一次性引入大量回归。

---

## 实施顺序与依赖

| 顺序 | Feature | 依赖系统 | 主要改动范围 | 预估工期 |
|------|---------|----------|--------------|----------|
| 1 | 转世轮回与多周目继承 | Player 存档、Engine 生命周期 | `config/reincarnation.json`、`game/reincarnation_manager.py`、Player 字段、Engine 集成、UI 弹窗 | 中 |
| 2 | 炼器附魔与装备词缀 | Item 系统、战斗系统 | `config/equipment_affixes.json`、`game/equipment_manager.py`、Item 扩展、炼器 UI | 中 |
| 3 | 天气与灵气潮汐 | World 时间、修炼/战斗计算 | `config/weather.json`、`game/weather_manager.py`、Engine tick、UI 天象面板 | 小 |
| 4 | 奇遇链分支叙事 | 事件系统、dialogue_flags | `config/encounter_chains.json`、`game/encounter_manager.py`、奇遇 UI | 中 |
| 5 | 灵兽羁绊与进化 | Beast 系统、战斗系统 | `config/beast_evolution.json`、`game/beast_manager.py`、灵兽 UI | 中 |
| 6 | 名望称号与排行榜 | 成就、事件、NPC 对话 | `config/titles.json`、`game/fame_manager.py`、Player 字段、NPC 对话接入 | 小 |
| 7 | Roguelike 秘境探险 | 战斗系统、地图系统、存档回滚 | `config/secret_realms.json`、`game/secret_realm_manager.py`、秘境 UI | 大 |
| 8 | 动态世界阵营大战 | 宗门、城池、事件、战争 | `config/factions.json`、`game/faction_war_manager.py`、战争 UI | 大 |
| 9 | 弟子培养与宗门传承 | 宗门系统、NPC、转世系统 | `game/disciple_manager.py`、宗门 UI 扩展 | 大 |
| 10 | Mod 与自定义内容 | 配置加载器、资源管理 | `mod_loader.py`、目录规范、冲突检测工具 | 大 |

---

## 每个 Feature 的标准文件结构

```
config/<feature>.json          # 配置数据
game/<feature>_manager.py      # 核心逻辑
ui/<feature>_dialog.py         # 交互界面
tests/test_<feature>_manager.py # 单元测试
tests/test_ui_<feature>.py     # UI 测试（如需要）
```

---

## 通用接入规范

1. **Player 状态**：新增字段必须在 `Player.to_dict()` 与 `from_dict()` 中序列化，并提供旧存档默认值。
2. **Engine 集成**：在 `GameEngine.__init__` 中初始化 Manager，在 `tick_monthly()` 中调用 Manager 的月度推进。
3. **配置校验**：更新 `tools/validate_configs.py`，新增对 `<feature>.json` 的校验规则。
4. **UI 入口**：在主界面或相关建筑弹窗中添加功能入口，优先复用现有弹窗组件。
5. **自动保存**：关键操作成功后调用 `engine._auto_save()`。
6. **测试覆盖**：Manager 逻辑必须 ≥ 80% 覆盖，UI 至少覆盖弹窗创建与核心交互路径。

---

## Feature 1：转世轮回与多周目继承 详细计划

### 1.1 设计目标
- 玩家死亡或飞升后可选择转世。
- 根据前世成就生成可继承项列表。
- 转世后开启新存档，保留有限继承，境界归零。

### 1.2 关键配置
- `config/reincarnation.json`：定义继承项类型、消耗业力、解锁条件。

### 1.3 关键数据字段
- `reincarnation_count`：转世次数。
- `karma`：因果业力，影响转世质量。
- `past_life_talents`：前世天赋 ID 列表。
- `inheritance_points`：本次可分配的继承点。

### 1.4 核心流程
1. 玩家死亡或飞升 → Engine 调用 `ReincarnationManager.compute_inheritance()`。
2. 弹出转世结算界面，展示可继承项与业力影响。
3. 玩家选择继承项 → 生成新 Player 初始数据。
4. 新游戏开始时读取转世数据并应用。

### 1.5 验收标准
- 死亡后可进入转世结算弹窗。
- 转世后新 Player 正确继承所选天赋/属性。
- 业力过高会触发负面转世事件。
- 旧存档无转世字段时兼容运行。

---

## 后续 Feature 概要

### Feature 2：炼器附魔与装备词缀
- 为装备增加 `enhancement_level`、`affixes`。
- 实现强化成功率、失败惩罚、重铸。
- 炼器台 UI 与战斗属性计算接入。

### Feature 3：天气与灵气潮汐
- 世界层维护天气与灵气潮汐。
- 影响修炼速度、属性伤害、事件触发。
- UI 天象面板提示当前加成。

### Feature 4：奇遇链分支叙事
- 配置化奇遇节点与分支。
- 使用 `dialogue_flags` 记录选择。
- 卷轴式文本 + 选项按钮 UI。

### Feature 5：灵兽羁绊与进化
- 扩展灵兽数据结构。
- 实现捕获、喂养、进化、战斗参战。
- 灵兽 UI 与战斗中独立行动。

### Feature 6：名望称号与排行榜
- 新增 `fame`、`title` 字段。
- 称号附带属性效果，NPC 对话中称呼称号。
- 排行榜覆盖多维度。

### Feature 7：Roguelike 秘境探险
- 随机房间生成器。
- 临时存档与失败后回滚。
- 秘境专属奖励与隐藏层。

### Feature 8：动态世界阵营大战
- 势力力量与领土控制。
- 多阶段战争事件。
- 城池建筑与 NPC 随控制势力变化。

### Feature 9：弟子培养与宗门传承
- 招收、传授、指派任务、立继承人。
- 弟子自动成长与参战。
- 与转世系统联动。

### Feature 10：Mod 与自定义内容
- Mod 目录结构。
- 配置覆盖与资源加载。
- 冲突检测与加载顺序。
