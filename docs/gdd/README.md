# 游戏设计文档（GDD）目录

本文档集用于拆解和迭代《问道长生》的整体设计，避免单文件过长，便于策划、程序、美术分模块维护。

## 文档索引

| 文档 | 说明 |
|------|------|
| [core_systems.md](./core_systems.md) | 修炼、战斗、灵根、流派等核心系统，含输入-输出-风险表 |
| [city_system.md](./city_system.md) | 城池建筑、声望、竞选、政策、城池事件设计 |
| [cave_system.md](./cave_system.md) | 洞府租赁、闭关、私人领地、设施经营设计 |
| [event_system.md](./event_system.md) | 随机事件、城池事件、宗门事件、世界事件设计 |
| [economy_balance.md](./economy_balance.md) | 经济循环、物价波动、收入来源与消耗出口 |
| [roadmap.md](./roadmap.md) | 分阶段路线图与可验收用户故事 |

## 使用规范

- 每个系统设计必须包含「输入-输出-风险」表，便于数值平衡。
- 配置字段变更时，同步更新对应文档与 `tools/validate_configs.py`。
- 新增用户故事时，在 [roadmap.md](./roadmap.md) 中标注优先级、依赖系统和验收标准。
