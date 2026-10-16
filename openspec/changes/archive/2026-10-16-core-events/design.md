# Design: core-events

## Context

项目为零代码起点（仅骨架：Python 3.12 + fastmcp + 空目录）。架构决策见
`docs/架构方案.md`：Steward 是龙虾背后的纯逻辑后端，stdio MCP 接入，SQLite
本地存储。本 change 只做通用层，领域校验/汇总留给各模块 change（mod-fitness
起建立模块接入模式）。需求动机见 proposal，行为契约见 specs/。

## Goals / Non-Goals

**Goals**
- 最小可用地基：单文件 SQLite + 薄存储层 + 2 个通用 MCP 工具，结构对齐 Deputy
- 首日即带 `schema_version`，为将来迁移留钩子

**Non-Goals**
- 领域 payload 校验、类型汇总（各模块 change）
- 目标管理（mod-fitness）、Finance（mod-finance）、Review/趋势（后续）
- 自然语言解析（龙虾侧）、数据迁移框架、重复提交去重（先允许，观察后再定）

## Decisions

### D1. 存储用标准库 `sqlite3`，不引入 ORM

SQLite 唯一且足够（单机、单写者、数据量极小）。`app/store/events.py` 用薄函数
封装 SQL，返回 `dict`。备选 ORM 对此规模是纯负担。

### D2. 单表 `events` + `payload JSON`，不按类型分表

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

CREATE TABLE schema_version (version INTEGER NOT NULL);
```

备选（按模块分表）查询直观，但每加模块建表+新工具，违背通用流水抽象。
`occurred_at` 存 ISO 8601 带偏移文本（见 Risks）。

### D3. `log_event` 本层零领域校验

只校验结构：`type` 非空字符串、`occurred_at` 可解析为时间（缺省取当前）、
`payload` 是 JSON object。领域校验在各模块 change 中以"模块注册校验器"的方式
加入 `log_*` 专用工具，**不回改本层**——保证兜底通道永远畅通。

### D4. MCP 工具错误约定

参数非法 → 抛 `ToolError`，消息直接说明哪个字段非法；成功 → 返回结构化 dict。
不搞 `{success, error}` 包装层。

### D5. 服务器入口 `app/mcp_server.py`，stdio 传输

对齐 Deputy 接入方式。FastAPI/Web 界面本阶段不做（无门禁审批类 UI 需求）。

### D6. 测试策略（TDD）

- `tests/test_store_events.py`：存储层，`tmp_path` 临时库
- `tests/test_mcp_contract.py`：FastMCP 内存 client 调用 2 个工具，
  覆盖成功路径与错误消息（对齐 Deputy 的 MCP 契约测试模式）

## Risks / Trade-offs

- [payload JSON 无约束，早期数据可能残缺] → 兜底通道有意宽松；各模块上线后其专用工具承担校验；`raw_text` 永久保留，未来可修复历史数据
- [文本时间戳跨时区比较不可靠] → 单机单时区（Asia/Shanghai），写入时统一带偏移；跨时区需求出现时再评估
- [query_events 上限保护可能截断大结果] → 返回中注明 total 与是否截断，模块级汇总工具（后续）不依赖明细全量拉取

## Migration Plan

新库首建，无迁移。回滚 = 删除 `data/steward.db`（尚无真实数据）。

## Open Questions

无。
