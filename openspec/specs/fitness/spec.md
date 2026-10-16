# fitness Specification

## Purpose
运动模块：把用户描述的运动（跑/走/游泳/健身/骑行/徒步/球类）记录为 workout
事件并提供查询汇总。本能力同时是所有生活模块的接入样板：校验器 + 汇总器 +
专用工具，数据落通用 events 表。

## Requirements

### Requirement: 记录运动

系统 SHALL 提供 `log_workout` 工具记录一条 workout 事件：`sport` 必填
（自由文本）；`duration_min` 与 `distance_km` 至少提供其一且必须 > 0；
`notes` 可选。成功后返回事件 id 及完整存档（含 type="workout"）。

#### Scenario: 记录跑步

- **WHEN** 调用 `log_workout(sport="run", distance_km=8, raw_text="今天跑了 8km")`
- **THEN** workout 事件写入通用 events 表，返回事件 id，原话保留

#### Scenario: 缺少量化字段拒绝

- **WHEN** 调用 `log_workout(sport="run")`（无 duration_min 与 distance_km）
- **THEN** 拒绝写入，错误信息说明时长与距离至少提供其一

#### Scenario: 非法数值拒绝

- **WHEN** 调用 `log_workout(sport="run", distance_km=-3)`
- **THEN** 拒绝写入，错误信息指明 distance_km 必须大于 0

### Requirement: 运动查询与汇总

系统 SHALL 提供 `query_workouts(date_from?, date_to?)` 返回 workout 明细
（复用通用查询的过滤与上限语义）及汇总：总次数、总时长（分钟）、总距离
（公里）、按 `sport` 分组小计。缺省窗口为最近 30 天。

#### Scenario: 月度运动汇总

- **WHEN** 调用 `query_workouts(date_from="2026-10-01", date_to="2026-10-31")`，
  期间有 3 次跑步共 24km、1 次健身 60 分钟
- **THEN** 返回 4 条明细；汇总为：次数 4、总距离 24、总时长 60+跑步时长、
  分组小计 run=3 次 24km / gym=1 次

#### Scenario: 空窗口

- **WHEN** 查询窗口内无 workout 记录
- **THEN** 返回明细为空，汇总各计数为 0，不报错
