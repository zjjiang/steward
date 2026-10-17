# commute Specification

## Purpose
通勤模块：一句话上下班打卡，月底自动出通勤统计。落通用 events 表
（type="commute"）。

## Requirements

### Requirement: 通勤打卡

系统 SHALL 提供 `check_in` 工具记录一条 commute 事件：`direction` 必填且为
`in`（到岗）/ `out`（离岗）。成功后返回事件 id 及完整存档（含 type="commute"）。

#### Scenario: 到岗打卡

- **WHEN** 调用 `check_in(direction="in")`
- **THEN** commute 事件写入 events 表，occurred_at 为当前时间

#### Scenario: 非法方向拒绝

- **WHEN** 调用 `check_in(direction="home")`
- **THEN** 拒绝写入，错误信息指明 direction 只支持 in/out

### Requirement: 通勤统计查询

系统 SHALL 提供 `query_commute(date_from?, date_to?)` 返回 commute 明细
（倒序）及汇总：有打卡记录的天数、`in` / `out` 各自次数。缺省窗口最近 30 天。

#### Scenario: 月度通勤统计

- **WHEN** 查询窗口内 12 个工作日打了到岗卡、其中 10 天打了离岗卡
- **THEN** 汇总为：打卡天数 12、in=12、out=10
