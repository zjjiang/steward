# diet Specification

## Purpose
饮食模块：记录一日三餐与加餐（可带花费），提供查询汇总。落通用 events 表
（type="meal"），复制 fitness 模块样板。

## Requirements

### Requirement: 记录饮食

系统 SHALL 提供 `log_meal` 工具记录一条 meal 事件：`desc` 必填（吃了什么）；
`meal` 可选，取值 breakfast/lunch/dinner/snack；`cost` 可选且必须 > 0。
成功后返回事件 id 及完整存档（含 type="meal"）。

#### Scenario: 记录一顿午餐

- **WHEN** 调用 `log_meal(desc="麻辣烫", meal="lunch", cost=28, raw_text="中午吃的麻辣烫，28 块")`
- **THEN** meal 事件写入 events 表，返回事件 id，原话保留

#### Scenario: 缺少描述拒绝

- **WHEN** 调用 `log_meal(cost=28)`（无 desc）
- **THEN** 拒绝写入，错误信息指明缺少 desc

#### Scenario: 非法 cost 拒绝

- **WHEN** 调用 `log_meal(desc="咖啡", cost=-5)`
- **THEN** 拒绝写入，错误信息指明 cost 必须大于 0

#### Scenario: 非法餐次拒绝

- **WHEN** 调用 `log_meal(desc="夜宵", meal="brunch")`
- **THEN** 拒绝写入，错误信息列出支持的 meal 取值

### Requirement: 饮食查询与汇总

系统 SHALL 提供 `query_meals(date_from?, date_to?)` 返回 meal 明细（倒序）
及汇总：次数、有 cost 记录的花费合计、按餐次分组计数。缺省窗口最近 30 天。

#### Scenario: 月度饮食汇总

- **WHEN** 查询窗口内有 2 次午餐（cost 28、35）和 1 次无花费早餐
- **THEN** 汇总为：次数 3、花费合计 63、分组 lunch=2 / breakfast=1
