# Proposal: life-log

## Why

Steward 第一阶段的生死线是"输入足够轻"：用户对龙虾说"今天跑了 8km"/"中午吃麻辣烫 28"/"今天 62.5kg"/"到公司了"，必须能被永久记住并随时查询统计。目前 Steward 没有任何存储与工具层，一切趋势分析、目标管理、周月复盘都无从谈起。本 change 打下地基。

核心抽象为**通用生活流水（events）**：一张表 + type 区分（workout/meal/body/commute/…），
未来任何新生活领域（expense、travel…）都是新增 type，表结构与 MCP 工具不重构。

## What Changes

- 新增 SQLite 存储层（`data/steward.db`，数据不出墙）：
  - `events` 表：`id, type, occurred_at, raw_text, payload(JSON)` —— 通用生活流水
  - `goals` 表：`id, kind, target, period, metric, status` —— 目标管理
- 新增 FastMCP server（stdio，供龙虾接入），首批 4 个工具：
  - `log_event(type, occurred_at, payload, raw_text?)` —— 记录一条生活事件；
    第一阶段约定 `workout / meal / body / commute` 四种 type 的 payload schema，
    未约定的 type 允许自由 payload（输入永不被 schema 卡死）
  - `query_events(type?, date_from?, date_to?)` —— 明细 + 按 type 汇总
    （workout：总公里/总时长/次数；body：体重序列与变化；commute：打卡天数）
  - `set_goal(kind, metric, target, period)` —— 周期型目标（月跑量 50km、每周运动 3 次）
  - `goal_progress(goal_id)` —— 当前完成 / 还差多少 / 时间进度是否正常
- **自然语言解析在龙虾侧**：Steward 保持纯逻辑后端（不配 AI、不烧 token），
  只接收龙虾解析好的结构化 payload；`raw_text` 永久保留原话。
- 第一阶段**不做**：expense 类型与 Finance 链路（credi-insights MCP 集成是独立 change）、
  自然语言解析、趋势/异常检测、Review 生成。

## Capabilities

### New Capabilities

- `life-log`：通用生活事件层 —— 事件记录（log_event）、查询与统计（query_events）、
  各 type 的 payload schema 约定。未来新生活领域在此能力上演进。
- `goals`：周期型目标管理 —— 设定（set_goal）、完成度追踪（goal_progress）。

### Modified Capabilities

（无 —— 项目尚无已有 spec）

## Impact

- **新增代码**：`app/store/`（SQLite 存取）、`app/domain.py`（type payload 校验与汇总规则）、
  `app/mcp_server.py`（FastMCP 工具）；`tests/` 对应单测
- **依赖**：fastmcp（已在 pyproject）；SQLite 标准库，无新增外部依赖
- **数据**：`data/steward.db`（已 gitignore）
- **不影响**：deputy、credi-insights 均无改动
- **后续 change**：finance-integration（credi-insights MCP 接入）、review、insights
  （见 `docs/架构方案.md` 第 5 节路线图）
