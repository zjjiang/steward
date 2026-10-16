# Spec Delta: event-store

## Purpose

通用生活事件层：把龙虾转述的生活事件持久化为一本可查询的流水。
本能力只提供通用记录与明细查询，不含任何领域校验与汇总——那是各模块
（fitness/diet/body/commute/…）的事。任何未来生活领域以新 type 落在此层，
表结构与通用工具不重构。

## ADDED Requirements

### Requirement: 记录生活事件

系统 SHALL 提供 `log_event` 工具记录一条生活事件，持久化 `type`、`occurred_at`、
`payload`、`raw_text`（可选），成功后返回事件 id 及完整存档内容。
`occurred_at` 缺省时 SHALL 取当前时间。本层不做领域字段校验：
`type` 为任意非空字符串，`payload` 为任意 JSON object。

#### Scenario: 记录任意类型事件

- **WHEN** 调用 `log_event(type="expense", payload={"desc":"打车","cost":86}, raw_text="打车 86 块")`
- **THEN** 事件写入流水，返回事件 id；`raw_text` 原样保留

#### Scenario: 缺省时间取当前

- **WHEN** 调用 `log_event(type="note", payload={"text":"换了新牙刷"})`，未传 `occurred_at`
- **THEN** 事件写入流水，`occurred_at` 为当前时间

#### Scenario: 非法输入拒绝

- **WHEN** 调用 `log_event(type="", payload={"a":1})` 或 `payload` 不是 JSON object
- **THEN** 拒绝写入，错误信息指明非法的字段及原因

### Requirement: 明细查询

系统 SHALL 提供 `query_events(type?, date_from?, date_to?)` 返回事件明细
（按 `occurred_at` 倒序），缺省窗口为最近 30 天，返回条数有上限保护。
本层不提供类型汇总统计——各模块在自己的查询工具中实现。

#### Scenario: 按类型与时间窗口过滤

- **WHEN** 调用 `query_events(type="workout", date_from="2026-10-01", date_to="2026-10-31")`
- **THEN** 仅返回该窗口内的 workout 明细，按时间倒序

#### Scenario: 缺省窗口

- **WHEN** 调用 `query_events()` 不带任何筛选
- **THEN** 返回最近 30 天内的全部事件明细，按时间倒序

### Requirement: 原文永久保留

`raw_text` SHALL 原样存储、永不改写；缺省时允许为空。

#### Scenario: 原话可追溯

- **WHEN** 以 `raw_text="今天跑了 8km"` 记录后查询该事件
- **THEN** 返回的明细中原样包含"今天跑了 8km"
