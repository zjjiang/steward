# insights Specification

## Purpose
TBD - created by archiving change insights. Update Purpose after archive.

## Requirements

### Requirement: 洞察条目结构与工具签名

`get_insights(ref_date?)` SHALL 返回 `{items: [...]}`；每条洞察为
`{area, kind, metric, current, previous, change, direction}`，area ∈
fitness/diet/body/finance，kind ∈ trend/anomaly，direction ∈ up/down/flat；
`ref_date` 缺省今天（YYYY-MM-DD，Asia/Shanghai），非法格式抛含 "ref_date"
的 ToolError。

#### Scenario: 返回结构完整

- **GIVEN** 近两周有运动数据且满足阈值
- **WHEN** 调用 `get_insights`
- **THEN** items 中 fitness 条目含 area/kind/metric/current/previous/change/direction 全字段

#### Scenario: 非法日期拒绝

- **WHEN** `ref_date="下周"` 或 "2026-13-01"
- **THEN** 抛出含 "ref_date" 的 ToolError

### Requirement: 环比趋势信号与阈值门槛

fitness（次数/总距离/总时长）与 diet（次数/花费）SHALL 按周环比计算；
finance（总支出）按月环比。仅当变化同时满足**相对阈值与绝对阈值**
（模块常量）时出条目：次数 |Δ|≥1 且 |Δ%|≥25%；距离 |Δ|≥2km；
时长 |Δ|≥20min；花费/支出 |Δ|≥100 元（相对阈值 25%）。不足门槛不出条目。

#### Scenario: 跑量显著下降被指出

- **GIVEN** 本周跑 8km、上周跑 20km
- **WHEN** 调用 `get_insights`
- **THEN** 含 fitness 条目 metric=total_distance_km，direction=down，
  current=8，previous=20

#### Scenario: 小幅波动不出条目

- **GIVEN** 本周 18km、上周 20km（|Δ|=2km 但 |Δ%|=10% < 25%）
- **WHEN** 调用 `get_insights`
- **THEN** 不含 total_distance_km 条目

#### Scenario: 上一周期无数据

- **GIVEN** 上周无任何运动
- **WHEN** 本周有运动
- **THEN** 不出环比条目（无基线，不构成"趋势"）

### Requirement: 财务分类跳变

月度复盘中若某支出分类较上月**涨幅 ≥50% 且差额 ≥100 元**，SHALL 出
kind=anomaly 的 finance 条目（metric=category:<名>）。上游不可用时 SHALL
跳过全部 finance 条目，fitness/diet/body 条目照常返回。

#### Scenario: 餐饮支出跳变

- **GIVEN** 本月餐饮 900 元、上月 400 元（+125%，差额 500 元）
- **WHEN** 调用 `get_insights`
- **THEN** 含条目 kind=anomaly、metric="category:餐饮"、direction=up

#### Scenario: 上游不可用降级

- **GIVEN** credi-insights 不可用
- **WHEN** 调用 `get_insights`
- **THEN** 无 finance 条目且不报错，本地 area 条目完整

### Requirement: 体重趋势斜率

body SHALL 报告近 14 天体重斜率：|斜率| ≥0.3 kg/周时出条目
（kind=trend、metric=weight_rate_kg_week、change=斜率、direction 按斜率符号）。
记录不足（<2 条或窗口 <4 天）不出条目。

#### Scenario: 明显下降趋势

- **GIVEN** 近 14 天体重从 63.0 降到 62.2（约 -0.4kg/周）
- **WHEN** 调用 `get_insights`
- **THEN** 含 body 条目 direction=down，change 约 -0.4

#### Scenario: 记录不足不出条目

- **GIVEN** 仅 1 条体重记录
- **WHEN** 调用 `get_insights`
- **THEN** 无 body 条目

### Requirement: 无数据静默

无任何满足门槛的信号时 SHALL 返回空 items 列表，不报错、不产出占位条目。

#### Scenario: 全新用户空数据

- **WHEN** 本地无事件且上游无交易
- **THEN** `{"items": []}`，调用成功
