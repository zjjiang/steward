# Design: life-log

## Context

项目为零代码起点（仅骨架：Python 3.12 + fastmcp 依赖 + 空目录）。架构决策见
`docs/架构方案.md`：Steward 是龙虾背后的纯逻辑后端（不配 AI），stdio MCP 接入，
SQLite 本地存储，数据不出墙。需求动机见 proposal，行为契约见 specs/。

## Goals / Non-Goals

**Goals**
- 单文件 SQLite 库 + 薄存储层 + FastMCP 工具，结构对齐 Deputy（纯逻辑、易测试）
- type 的校验与汇总是本 change 唯一的"领域逻辑"，集中一处、可独立单测

**Non-Goals**
- 不做自然语言解析（龙虾侧职责）
- 不做趋势/异常检测、Review 生成（后续 change）
- 不做数据迁移框架（首版 schema，见 Risks）
- 不做重复提交去重（用户手滑记两次，先允许，观察后再定）

## Decisions

### D1. 存储用标准库 `sqlite3`，不引入 ORM

SQLite 是唯一且长期足够的存储（单机、单写者、数据量极小）。ORM（SQLAlchemy 等）
对此规模是纯负担。`app/store/` 内用薄函数封装 SQL，返回 `dict`，不建实体类层级。

### D2. 事件表用 `type + payload JSON`，不按类型分表

```sql
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,   -- ISO 8601 含时区偏移
  raw_text TEXT,
  payload TEXT NOT NULL,        -- JSON object
  created_at TEXT NOT NULL
);
CREATE INDEX idx_events_type_time ON events(type, occurred_at);
```

- 备选方案（按类型分表）查询直观，但每加一个生活领域就要建表 + 新工具，
  违背"通用生活流水"的核心抽象。JSON1 函数（`json_extract`）足以做查询。
- `occurred_at` 存 ISO 8601 带偏移文本：SQLite 无原生时区类型，文本可读、可比较
  （同偏移前提下），跨时区问题到出现时再解（当前单机单时区）。

### D3. 校验与汇总集中在 `app/domain.py`

每个已知 type 一个 payload 校验函数 + 一个汇总函数，用简单的 `dataclass`
Schema 描述（字段名、类型、可选性、约束），不做 JSON Schema 库（依赖最小化）。
未知 type：只要求 payload 是 JSON object，其余放行。

### D4. 目标进度实时计算，不存进度快照

`goal_progress` 每次从 events 现算（周期内 SUM/COUNT）。数据量下这是零成本，
且永远自洽。进度判断（ahead/on_track/behind）算法在 `app/domain.py`，阈值为
1.25 / 0.75，时间进度 <10% 时强制 on_track（见 goals spec）。

### D5. 目标表与生效规则

```sql
CREATE TABLE goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  metric TEXT NOT NULL,        -- distance | frequency | duration
  target REAL NOT NULL,
  period TEXT NOT NULL,        -- week | month
  status TEXT NOT NULL DEFAULT 'active',  -- active | superseded
  created_at TEXT NOT NULL
);
CREATE INDEX idx_goals_kind_metric_period ON goals(kind, metric, period, status);
```

- set_goal 同 `(kind, metric, period)` 已有 active 时：事务内将旧目标置
  `superseded`，插入新目标。
- 周期边界（自然周一起始的自然周 / 自然月）在 `app/domain.py` 按本地时间计算。

### D6. MCP 工具错误约定

参数校验失败 → 抛 `ToolError`，消息直接说明哪个字段非法（龙虾能读给用户听）；
成功 → 返回结构化 dict（自动序列化为 JSON）。不搞 `{success, error}` 包装层——
MCP 工具级错误语义已足够，少一层约定少一层误用。

### D7. 服务器入口：`app/mcp_server.py`，stdio 传输

对齐 Deputy 的接入方式。工具 instructions 内写明 type/payload 约定，
让龙虾侧不读代码也能正确构造参数。FastAPI/Web 界面本阶段**不做**
（Deputy 有看板是因为它有门禁审批 UI 需求；Steward 暂无此需求）。

### D8. 测试策略（TDD）

- `tests/test_store.py`：存储层，用 `tmp_path` 建临时库
- `tests/test_domain.py`：payload 校验、汇总、周期边界、进度算法（纯函数，重点覆盖）
- `tests/test_mcp_contract.py`：经 FastMCP client 内存调用 4 个工具，验证
  成功路径与错误消息（对齐 Deputy 的 MCP 契约测试模式）

## Risks / Trade-offs

- [payload JSON 无外键约束，脏数据只能靠校验层拦截] → 校验集中在 domain 层并全量单测；未知 type 自由记录是**有意取舍**（输入不被 schema 卡死优先）
- [首版 schema 无版本号，将来改表结构没有迁移机制] → 建表语句从第一天起带 `schema_version` 单行表（成本几乎为零），为后续迁移留钩子
- [文本时间戳跨时区比较不可靠] → 当前单机单时区（Asia/Shanghai），`occurred_at` 统一由服务器写入时带偏移；跨时区需求出现时再评估（届时可能改存 UTC）
- [龙虾侧解析质量决定数据质量] → MCP instructions 与 specs 中的 payload 约定保持一致；`raw_text` 永久保留，未来可用真解析修复历史数据

## Migration Plan

新库首建，无迁移。回滚 = 删除 `data/steward.db`（尚无真实数据）。

## Open Questions

无。
