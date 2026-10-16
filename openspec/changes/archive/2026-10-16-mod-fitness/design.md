# Design: mod-fitness

## Context

core-events 已交付：`events` 表（store 层 `insert_event`/`list_events`）、
FastMCP server（stdio）、schema_version=1。本 change 是第一个生活模块，
除了功能本身，还要**确立模块接入模式**——diet/body/commute 将复制此模式。
需求动机见 proposal，行为契约见 specs/。

## Goals / Non-Goals

**Goals**
- 模块代码边界清晰：领域逻辑（校验/汇总/进度）与 MCP 工具分离，纯函数可独立单测
- 复用 event-store，events 表零改动

**Non-Goals**
- 趋势/异常检测、配速等衍生统计（后续 insights / 用到再加）
- 目标的通用化抽象（先只做 workout 目标，出现第二个目标领域时再提升）

## Decisions

### D1. 模块代码放 `app/modules/fitness.py`，模块 = 三个纯函数

```python
validate_payload(payload: dict) -> dict        # 校验并补默认，非法抛 ValueError
summarize(items: list[dict]) -> dict           # 明细 → 汇总（次数/时长/距离/分组）
```

加工具注册（在 mcp_server.py 中 import 模块并声明 4 个工具）。
备选（校验逻辑散在工具函数里）不可测、且 diet/body/commute 无样板可抄。
**这就是模块接入模式**：新模块 = 新 `app/modules/<name>.py` 实现同名函数 +
mcp_server.py 注册工具。

### D2. `log_workout` 落库仍走 `insert_event(type="workout")`

模块不另建表。校验通过后调 store 层，raw_text 语义与通用层一致。

### D3. `goals` 表 + schema_version 升 2

```sql
CREATE TABLE goals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL DEFAULT 'workout',
  metric TEXT NOT NULL,        -- distance | frequency | duration
  target REAL NOT NULL,
  period TEXT NOT NULL,        -- week | month
  status TEXT NOT NULL DEFAULT 'active',   -- active | superseded
  superseded_by INTEGER REFERENCES goals(id),
  created_at TEXT NOT NULL
);
CREATE INDEX idx_goals_lookup ON goals(kind, metric, period, status);
```

`app/store/goals.py`：`insert_goal` / `get_goal` / `active_goal_for` /
`supersede`（同维度旧目标置 superseded + 记 superseded_by，事务内完成）。

### D4. 周期与进度算法在 `app/modules/fitness.py`（纯函数）

- 周期边界：`current_period(period)` 返回 (起, 止)，week = 周一起始的自然周，
  month = 自然月，按 Asia/Shanghai 本地时间
- 进度：`progress(goal, events)` → current（SUM/COUNT 按 metric）+
  判定（比值 ≥1.25 ahead / <0.75 behind / 其余 on_track；时间进度 <10% 强制
  on_track）

### D5. `goal_progress` 对 superseded 目标返回存档进度

superseded 目标查询其原生效周期内的数据（周期起止按 created_at 所在周期
推算并存于返回中）；若已有接任目标，附 `superseded_by=<新目标 id>`。

### D6. 测试策略（TDD）

- `tests/test_fitness_module.py`：payload 校验、汇总、周期边界、进度算法（纯函数，重点）
- `tests/test_store_goals.py`：goals 存取与 supersede 事务
- `tests/test_mcp_contract.py` 扩展：4 个新工具的成功/失败路径（沿用内存 client 模式）

## Risks / Trade-offs

- [sport 自由文本导致分组统计口径漂移（run/跑步/running 各算一组）] → 第一阶段接受；汇总按原文分组，口径统一留给后续（如sport别名归一），raw_text 与 payload 均保留原值可回溯
- [进度判定阈值 1.25/0.75 可能不合手感] → 阈值集中在模块顶部常量，观察后可调，不影响 spec 语义
- [goals 表引用 events 数据计算，跨表无约束] → events 只增不删（现无删除路径），进度计算天然一致；将来若支持删除需重算进度（现阶段无此需求）

## Migration Plan

`init_db` 增加 goals 建表语句 + schema_version 升 2（旧库幂等升级：表不存在则建，
version 行更新）。无数据迁移。回滚 = 删库（尚无真实数据）。

## Open Questions

无。
