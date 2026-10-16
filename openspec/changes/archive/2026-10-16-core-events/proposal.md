# Proposal: core-events

## Why

Steward 第一阶段的生死线是"输入足够轻"：用户对龙虾说的任何生活琐事必须能被
永久记住并随时查询。本 change 建立通用生活流水地基——一张 events 表 +
通用记录/查询工具，是所有模块（fitness/diet/body/commute）与未来一切
生活领域的公共底座（模块划分见 `docs/架构方案.md` 第 2 节）。

## What Changes

- 新增 SQLite 存储层（`data/steward.db`，数据不出墙）：
  - `events` 表：`id, type, occurred_at, raw_text, payload(JSON)` —— 通用生活流水
  - `schema_version` 表：首日即带版本号，为将来迁移留钩子
- 新增 FastMCP server（stdio，供龙虾接入），首批 2 个通用工具：
  - `log_event(type, occurred_at?, payload, raw_text?)` —— 记录一条生活事件；
    **不校验业务字段**（领域校验由各模块 change 引入），只要求 payload 是
    JSON object、occurred_at 是合法时间
  - `query_events(type?, date_from?, date_to?)` —— 明细查询，缺省最近 30 天，
    条数上限保护；无类型汇总（各模块提供自己的汇总工具）
- **自然语言解析在龙虾侧**：Steward 保持纯逻辑后端（不配 AI、不烧 token）；
  `raw_text` 永久保留原话。
- 第一阶段**不做**：任何领域类型校验与汇总（fitness/diet/body/commute 在各自
  模块 change 中做）、目标管理（属 mod-finance 之前的 mod-fitness）、
  Finance 链路、趋势检测、Review。

## Capabilities

### New Capabilities

- `event-store`：通用生活事件层 —— 事件记录（log_event）、明细查询
  （query_events）、原文保留、未知类型自由记录。领域模块在此层上演进，
  表结构与通用工具不因新模块重构。

### Modified Capabilities

（无 —— 项目尚无已有 spec）

## Impact

- **新增代码**：`app/store/`（SQLite 存取）、`app/mcp_server.py`（FastMCP 工具）、
  `tests/` 对应单测；`app/domain.py` 本 change 不创建（首个模块 change 引入）
- **依赖**：fastmcp（已在 pyproject）；SQLite 标准库，无新增外部依赖
- **数据**：`data/steward.db`（已 gitignore）
- **不影响**：deputy、credi-insights 均无改动
- **后续 change**：mod-fitness → mod-basics → mod-finance → review → insights
  （见 `docs/架构方案.md` 第 6 节路线图）
