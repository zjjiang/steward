# Spec Delta: goals

## Purpose

周期型目标管理：让用户用一句话（"这个月目标跑 50km"）设定目标，
之后随时能查到当前完成、还差多少、进度是否正常。目标数据基于生活流水
（life-log）实时计算，不单独维护进度。

## ADDED Requirements

### Requirement: 设定周期型目标

系统 SHALL 提供 `set_goal(kind, metric, target, period)` 设定周期型目标：

- 第一阶段 `kind` 限定 `workout`；`metric` ∈ `distance`（距离）/ `frequency`（次数）/
  `duration`（总时长）；`period` ∈ `week` / `month`；`target` > 0
- 目标自下一个周期起点生效（月中设定月目标，则当月即生效）
- 同一 `(kind, metric, period)` 组合 SHALL 至多有一个进行中目标；
  重复设定时旧目标自动标记为 `superseded`，新目标生效

#### Scenario: 设定月跑量目标

- **WHEN** 调用 `set_goal(kind="workout", metric="distance", target=50, period="month")`
- **THEN** 目标创建，状态 `active`，生效周期为当前自然月

#### Scenario: 同维度重复设定

- **WHEN** 月跑量目标进行中，再次 `set_goal(kind="workout", metric="distance", target=80, period="month")`
- **THEN** 旧目标标记 `superseded`，新目标（80km）为唯一 `active` 状态

### Requirement: 目标进度查询

系统 SHALL 提供 `goal_progress(goal_id)` 返回：`target`、`current`、`remaining`、
所在周期起止、进度判断（`ahead` / `on_track` / `behind`）。`current` SHALL 基于
流水数据实时计算：

- `distance`：周期内 workout 的 `distance_km` 合计
- `frequency`：周期内 workout 次数
- `duration`：周期内 workout 的 `duration_min` 合计

进度判断按时间进度与完成进度之比：比值 ≥ 1.25 为 `ahead`，< 0.75 为 `behind`，
其余为 `on_track`；周期刚起步（时间进度 < 10%）时 SHALL 返回 `on_track` 避免误判。

#### Scenario: 月中查询跑量进度

- **WHEN** 10 月目标 50km，10 月 16 日已跑 25km（时间进度约 48%，完成进度 50%）
- **THEN** 返回 current=25、remaining=25、进度判断 `on_track`

#### Scenario: 明显落后

- **WHEN** 10 月目标 50km，10 月 25 日仅跑 10km（时间进度约 77%，完成进度 20%，比值约 0.26）
- **THEN** 返回 remaining=40、进度判断 `behind`

#### Scenario: 月初不误判

- **WHEN** 10 月 2 日查询月跑量目标，已跑 0km
- **THEN** 进度判断返回 `on_track`（时间进度 < 10%）

### Requirement: 目标不存在或已失效

`goal_progress` 指向不存在的 goal_id 时 SHALL 返回明确错误；
指向 `superseded` 目标时 SHALL 正常返回其存档进度并注明该目标已被替代。

#### Scenario: 查询不存在的目标

- **WHEN** 调用 `goal_progress(goal_id=999)` 且无此目标
- **THEN** 返回明确错误"目标不存在"

#### Scenario: 查询已被替代的目标

- **WHEN** 查询一个 `superseded` 状态的目标
- **THEN** 返回其生效周期内的进度，并注明 `superseded_by=<现行目标 id>`
