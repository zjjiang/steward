# web-ui 规格（delta）

## ADDED Requirements

### Requirement: 账单页卡级别与账单周期视图

仪表盘账单页 SHALL 支持按卡过滤月度概况（`GET /api/finance?card=`），并提供
`GET /api/bills` 返回每张卡最近已出账账单期的汇总（周期起止/总额/出账日与
还款日），前端 SHALL 呈现卡切换与各卡本期账单卡片。上游不可用时照旧降级为
`available: false`，不报 5xx。

#### Scenario: 按卡过滤月度概况

- **WHEN** 请求 `GET /api/finance?month=2026-10&card=card_a`
- **THEN** summary 与 pending 仅含该卡数据

#### Scenario: 各卡本期账单

- **WHEN** 请求 `GET /api/bills`，上游有两张卡且账单日可用
- **THEN** 返回每张卡的最近已出账周期（start/end/total_debit/transaction_count/
  billing_day/due_day）；某卡上游缺账单日时该卡条目带 error 而不影响其他卡
