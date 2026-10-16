# body Specification

## Purpose
身体模块：记录体重等身体指标（第一阶段仅体重），提供序列查询。落通用
events 表（type="body"），未来体脂等指标在此模块扩展。

## Requirements

### Requirement: 记录身体指标

系统 SHALL 提供 `log_body` 工具记录一条 body 事件：`weight_kg` 必填，
取值 (0, 500]。成功后返回事件 id 及完整存档（含 type="body"）。

#### Scenario: 记录体重

- **WHEN** 调用 `log_body(weight_kg=62.5, raw_text="今天 62.5kg")`
- **THEN** body 事件写入 events 表，返回事件 id，原话保留

#### Scenario: 非法体重拒绝

- **WHEN** 调用 `log_body(weight_kg=-3)` 或 `log_body(weight_kg=800)`
- **THEN** 拒绝写入，错误信息指明 weight_kg 取值范围为 (0, 500]

### Requirement: 体重序列查询

系统 SHALL 提供 `query_body(date_from?, date_to?)` 返回 body 明细及汇总：
按时间升序的体重序列（含日期），以及首末差值。窗口内不足 2 条时差值为 null。
缺省窗口最近 30 天。

#### Scenario: 体重序列与差值

- **WHEN** 查询窗口内记录过 62.5kg 和 61.8kg
- **THEN** 返回升序序列 [62.5, 61.8] 及差值 -0.7

#### Scenario: 单条记录

- **WHEN** 查询窗口内只有 1 条体重记录
- **THEN** 返回序列与该条明细，差值为 null
