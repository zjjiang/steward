# review Specification

## Purpose
TBD - created by archiving change review. Update Purpose after archive.

## Requirements

### Requirement: 周期语义与参数校验

`get_review(period, ref_date?)` SHALL 支持 week（周一为始）与 month（自然月）
两种周期，时区固定 Asia/Shanghai；`ref_date` 缺省今天，周期边界由 ref_date
所在周期决定，返回 `meta`（period/start/end/ref_date，ISO 日期）。

#### Scenario: 周复盘边界

- **WHEN** 调用 `get_review(period="week", ref_date="2026-10-14")`（周三）
- **THEN** meta.start 为该周周一 "2026-10-12"，meta.end 为周日 "2026-10-18"

#### Scenario: 月复盘边界

- **WHEN** 调用 `get_review(period="month", ref_date="2026-10-14")`
- **THEN** meta.start 为 "2026-10-01"，meta.end 为 "2026-10-31"

#### Scenario: 非法参数拒绝

- **WHEN** period 不是 week/month，或 ref_date 不是合法 YYYY-MM-DD
- **THEN** 抛出 ToolError，消息含 "period" 或 "ref_date"

### Requirement: 本地生活 sections

复盘 SHALL 聚合本地 events 表中周期内数据：fitness（次数/总时长/总距离/按
sport 分组 + 全部活跃目标的 target/current/verdict）、diet（次数/花费/按餐次）、
body（周期内体重升序序列 + 首末差值）、commute（打卡天数/in、out 次数）、
other（除 workout/meal/body/commute 外各 type 的事件计数）。

#### Scenario: 各 section 汇总正确

- **GIVEN** 周期内有 2 次跑步（合计 17km/85min）、1 条体重、2 天通勤打卡、
  1 条兜底事件 type="note"
- **WHEN** 调用 `get_review`
- **THEN** fitness.summary.count=2 且 total_distance_km=17
- **AND** diet/body/commute section 与各自模块汇总口径一致
- **AND** other 为 {"note": 1}

#### Scenario: 活跃目标进度判定

- **GIVEN** 存在活跃目标 distance 50km/month，周期内已跑 25km
- **WHEN** 调用 `get_review`
- **THEN** fitness.goals 含该目标：metric/target/current(25)/verdict

#### Scenario: 无活跃目标

- **WHEN** 无任何活跃运动目标
- **THEN** fitness.goals 为空列表，不报错

### Requirement: 财务 section 与降级

月度复盘 SHALL 包含 finance section：周期内跨卡支出汇总（总支出/笔数/分类
占比/Top 商户）与订阅识别；周度复盘只含窗口汇总。credi-insights 不可用时
SHALL 返回 `available: false` 与原因，其余 section 不受影响。

#### Scenario: 月度财务汇总与订阅

- **GIVEN** 复盘月内有跨卡交易与满足阈值的订阅商户
- **WHEN** 调用 `get_review(period="month")`
- **THEN** finance.available=true，含 total_debit/transaction_count/by_category/
  top_merchants 与 subscriptions 列表

#### Scenario: 周度财务仅窗口汇总

- **WHEN** 调用 `get_review(period="week")`
- **THEN** finance 含周期窗口的 total_debit/transaction_count/by_category，
  不含 subscriptions

#### Scenario: 财务降级不影响整体

- **GIVEN** credi-insights 子进程不可用
- **WHEN** 调用 `get_review`
- **THEN** finance.available=false 且 error 含"财务数据源不可用"
- **AND** fitness/diet/body/commute/other sections 数据完整返回

### Requirement: 空周期全零

周期内无任何数据时 SHALL 返回各 section 的零值/空列表，不报错。

#### Scenario: 全新周期

- **WHEN** 周期内无本地事件且上游无交易
- **THEN** 各 section 计数为 0、列表为空，finance.available=true，返回成功
