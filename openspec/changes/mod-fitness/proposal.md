# Proposal: mod-fitness

## Why

运动是 PRD 第一阶段的核心方向之一（场景一/二/三：运动记录、运动目标、运动趋势）。
core-events 已提供通用流水地基，本 change 是**第一个生活模块**：交付 workout
类型的校验与汇总 + 周期型运动目标，并确立后续所有模块（diet/body/commute）
的接入模式——这是它的第二重意义。

## What Changes

- 新增 fitness 模块（`app/modules/fitness.py`），建立模块接入模式：
  每个模块 = payload 校验器 + 汇总器 + 专用 MCP 工具，数据仍落通用 `events` 表
- workout 类型 payload 校验：`sport` 必填（自由文本）；`duration_min` 与
  `distance_km` 至少其一，数值 > 0；`notes` 可选
- 新增 4 个 MCP 工具：
  - `log_workout(sport, duration_min?, distance_km?, notes?, occurred_at?, raw_text?)` —— 记录运动
  - `query_workouts(date_from?, date_to?)` —— 明细 + 汇总（总次数/总时长/总距离/按 sport 分组）
  - `set_goal(metric, target, period)` —— 周期型目标（distance/frequency/duration × week/month）
  - `goal_progress(goal_id)` —— 完成度、剩余量、ahead/on_track/behind 判断（从 events 实时计算）
- 新增 `goals` 表：`(kind, metric, target, period, status)`，
  同 `(kind, metric, period)` 至多一个 active，重复设定自动 supersede
- 不做：趋势/异常检测（insights change）、其他运动衍生统计（配速等，用到再加）

## Capabilities

### New Capabilities

- `fitness`：运动模块 —— workout 类型校验、记录（log_workout）、查询汇总
  （query_workouts）。
- `goals`：周期型目标管理 —— 设定（set_goal）、完成度追踪（goal_progress），
  进度基于 fitness 流水实时计算。

### Modified Capabilities

（无 —— event-store 不变，本 change 只消费它）

## Impact

- **新增代码**：`app/modules/fitness.py`（校验+汇总，确立模块模式）、
  `app/store/goals.py`、`app/mcp_server.py` 增 4 个工具、`tests/` 对应单测
- **schema**：新增 `goals` 表（events 表不动）；`schema_version` 升到 2
- **不影响**：event-store 行为、deputy、credi-insights
- **后续 change**：mod-basics（diet/body/commute 复制本模块模式）
