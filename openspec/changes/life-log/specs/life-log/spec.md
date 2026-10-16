# Spec Delta: life-log

## Purpose

通用生活事件层：把用户自然语言描述的生活事件（运动、饮食、身体、通勤……）
持久化为一本可查询、可汇总的流水。任何未来生活领域都以新 type 在此层上演进，
表结构与查询接口不因新领域重构。

## ADDED Requirements

### Requirement: 记录生活事件

系统 SHALL 提供 `log_event` 工具记录一条生活事件，持久化以下字段：
`type`、`occurred_at`、`payload`（结构化数据）、`raw_text`（用户原话，可选）。
记录成功后 SHALL 返回事件 id 及完整存档内容。`occurred_at` 缺省时 SHALL 取当前时间。

#### Scenario: 记录一次跑步

- **WHEN** 调用 `log_event(type="workout", payload={"sport":"run","distance_km":8}, raw_text="今天跑了 8km")`
- **THEN** 事件写入流水，返回事件 id；`raw_text` 原样保留为"今天跑了 8km"

#### Scenario: 记录上下班打卡

- **WHEN** 调用 `log_event(type="commute", payload={"direction":"in"})`，未传 `occurred_at`
- **THEN** 事件写入流水，`occurred_at` 为当前时间

### Requirement: 已知类型的 payload 校验

对已知 type（`workout` / `meal` / `body` / `commute`），系统 MUST 校验 payload
符合该类型约定，校验失败时 SHALL 拒绝写入并返回明确指出非法字段的错误信息：

- `workout`：`sport` 必填（自由文本，如 run/swim/gym/cycle/hike/ball）；
  `duration_min` 与 `distance_km` 至少提供其一；数值必须 > 0；`notes` 可选
- `meal`：`desc` 必填；`meal`（breakfast/lunch/dinner/snack）与 `cost` 可选，`cost` > 0
- `body`：`weight_kg` 必填，取值 (0, 500]
- `commute`：`direction` 必填且为 `in` / `out`

#### Scenario: 校验失败拒绝写入

- **WHEN** 调用 `log_event(type="workout", payload={"distance_km":8})`（缺 `sport`）
- **THEN** 拒绝写入，错误信息指明缺少 `sport` 字段

#### Scenario: 数值非法拒绝写入

- **WHEN** 调用 `log_event(type="body", payload={"weight_kg":-3})`
- **THEN** 拒绝写入，错误信息指明 `weight_kg` 非法

### Requirement: 未知类型允许自由记录

对未知 type，系统 SHALL 允许写入（payload 为任意 JSON object），
保证输入不被第一阶段 schema 卡死。查询与汇总对未知 type 只返回明细，不做汇总。

#### Scenario: 未来类型直接记录

- **WHEN** 调用 `log_event(type="expense", payload={"desc":"打车","cost":86})`
- **THEN** 事件成功写入流水

### Requirement: 查询与按类型汇总

系统 SHALL 提供 `query_events(type?, date_from?, date_to?)` 返回事件明细，
并对已知 type 附带汇总统计；日期缺省窗口为最近 30 天，返回条数有上限保护：

- `workout`：总次数、总时长（分钟）、总距离（公里）、按 `sport` 分组小计
- `body`：按时间升序的体重序列、首末差值
- `commute`：有打卡记录的天数、`in` / `out` 各自次数
- `meal`：次数、有 `cost` 记录的花费合计
- 未知 type：仅明细

#### Scenario: 月度运动汇总

- **WHEN** 调用 `query_events(type="workout", date_from="2026-10-01", date_to="2026-10-31")`，
  期间有 3 次跑步共 24km、1 次健身 60 分钟
- **THEN** 返回 4 条明细，汇总为：次数 4、总时长 60+跑步时长、总距离 24、
  分组小计 run=3 次共 24km / gym=1 次

#### Scenario: 体重序列

- **WHEN** 调用 `query_events(type="body")`，期间记录过 62.5kg 和 61.8kg
- **THEN** 返回升序体重序列及差值 -0.7kg

### Requirement: 原文永久保留

`raw_text` SHALL 原样存储、永不改写；缺省时允许为空（龙虾直接传结构化数据时）。

#### Scenario: 原话可追溯

- **WHEN** 以 `raw_text="今天跑了 8km"` 记录后查询该事件
- **THEN** 返回的明细中原样包含"今天跑了 8km"
