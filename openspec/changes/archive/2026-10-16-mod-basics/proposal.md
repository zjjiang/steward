# Proposal: mod-basics

## Why

mod-fitness 已确立模块接入样板。本 change 一次性交付三个薄模块——饮食（diet）、
身体（body）、通勤（commute），覆盖用户日常最高频的记录需求（需求 1 的"吃了啥/
体重"与需求 3 的"上下班打卡"）。三者结构同构、体量小，合并为一个 change。

## What Changes

- 新增 3 个模块（`app/modules/`，复制 fitness 样板），数据全部落通用 `events` 表：
  - **diet**：`meal` 类型 —— `desc` 必填；`meal`（breakfast/lunch/dinner/snack）与
    `cost`（> 0）可选。工具：`log_meal` / `query_meals`（明细 + 次数/花费合计/按餐次分组）
  - **body**：`body` 类型 —— `weight_kg` 必填，取值 (0, 500]。工具：`log_body` /
    `query_body`（时间升序体重序列 + 首末差值）
  - **commute**：`commute` 类型 —— `direction` 必填（in/out）。工具：`check_in` /
    `query_commute`（打卡天数 + in/out 次数）
- `schema_version` 不变（无新表、无迁移）
- 不做：热量/营养分析、体重趋势判定（insights）、通勤时长统计（数据够时再说）

## Capabilities

### New Capabilities

- `diet`：饮食模块 —— meal 类型校验、记录（log_meal）、查询汇总（query_meals）。
- `body`：身体模块 —— 体重等身体记录（log_body）与序列查询（query_body）。
- `commute`：通勤模块 —— 上下班打卡（check_in）与打卡统计（query_commute）。

### Modified Capabilities

（无 —— event-store / fitness / goals 均不变）

## Impact

- **新增代码**：`app/modules/diet.py` / `body.py` / `commute.py`、
  `app/mcp_server.py` 增 6 个工具、`tests/` 对应单测
- **schema**：无变化（三类型均落 events 表）
- **不影响**：已有模块行为、deputy、credi-insights
- **后续 change**：mod-finance（credi-insights 接入）
