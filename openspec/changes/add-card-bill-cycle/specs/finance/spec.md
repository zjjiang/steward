# finance 规格（delta）

## ADDED Requirements

### Requirement: 卡级别查询（card_id 透传）

spending_summary 与 pending_classifications SHALL 接受可选 `card_id` 参数并
透传上游 `cardId`，把结果限定到单张卡；缺省（不传）SHALL 保持现有全卡口径不变。
内部取数通道 `fetch_transactions_range` SHALL 支持同样的可选过滤。

#### Scenario: 按卡汇总

- **WHEN** 请求 spending_summary(card_id="card_a")，上游 get_transactions 收到
  `{"month": "2026-10", "limit": 500, "cardId": "card_a"}`
- **THEN** 返回的汇总只含该卡交易，且上游调用带 cardId

#### Scenario: 缺省口径不变

- **WHEN** 调用 spending_summary() 不带 card_id
- **THEN** 上游调用不带 cardId，结果为全卡汇总

### Requirement: 账单周期汇总（card_bill）

Steward SHALL 提供 `card_bill(card_id, cycle?)` 工具：按卡的账单日（billingDay）
计算账单周期（出账日 → 下个出账日前一日），返回该期汇总（总支出/总收入/笔数/
分类构成/明细）及卡的账单日与还款日。cycle 支持 `current`（最近已出账期，缺省）、
`previous`、`YYYY-MM`（以出账日所在月命名的期）。账单日超出当月天数时 SHALL
截断到当月最后一天。

#### Scenario: 本期账单

- **WHEN** 卡账单日为 5，今天是 2026-10-18，请求 card_bill(card_id="card_a")
- **THEN** 周期为 2026-09-05 ~ 2026-10-04（出账日 2026-10-05），返回该窗口内
  该卡交易的汇总与明细，响应含 billing_day 与 due_day

#### Scenario: 指定账单期

- **WHEN** 请求 card_bill(card_id="card_a", cycle="2026-08")
- **THEN** 周期取 2026-08 的出账日到 2026-09 出账日前一日

#### Scenario: 账单日超过当月天数

- **WHEN** 卡账单日为 31，出账月为 2026-02
- **THEN** 出账日截断为 2026-02-28

### Requirement: 上游缺失账单日时降级

上游 `list_cards` 未返回 `billingDay`/`dueDay` 时，card_bill SHALL 抛出可读
ToolError（提示上游需更新 list_cards），SHALL NOT 猜测账单日或按自然月兜底。

#### Scenario: 上游未返回账单日

- **WHEN** list_cards 响应的卡片不含 billingDay，请求 card_bill
- **THEN** 报 ToolError，消息含"账单日"字样与修复指引
