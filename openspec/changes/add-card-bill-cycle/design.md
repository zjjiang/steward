# Design

## 账单周期是纯函数

`app/finance/billing.py`：`cycle_bounds(billing_day, cycle, today) -> dict`。
规则：出账日 = min(billing_day, 当月天数)；`YYYY-MM` 期的窗口 = 该月出账日 ~
下月出账日前一日；`current` = 最近一个已到的出账日开始的期（今天 ≥ 本月出账日
→ 本月那期，否则上月那期）；`previous` 再退一期。返回
`{cycle, statement_date, start, end}`。零 IO，独立单测覆盖 31 日卡遇 2 月、
今天在出账日前等边界。

## 单一实现，两层薄壳

账单汇总逻辑放 `app/finance/tools.py` 模块级 `card_bill(be, card_id, cycle,
today=None)`（取 list_cards → 校验 billingDay → cycle_bounds → 带 cardId 拉窗口
交易 → summarize+明细投影）。MCP 工具 `card_bill` 与 web `/api/bills`、
`/api/finance` 都调它，不再出现闭包外不可达的问题。MCP 抛 ToolError；
web 的 `/api/bills` 逐卡 try/except，一卡失败不影响其他卡（条目带 error）。

## cardId 透传

`fetch_transactions_range(be, start, end, card_id=None)`：card_id 非空时上游
arguments 加 `"cardId"`。spending_summary / pending_classifications 加同名可选
参数直通。缺省不带 → 上游行为与现在完全一致。

## 口径并存

自然月口径（trend/订阅/insights/review）不动；card_bill 是还款口径。
UI 账单页顶部加"本期账单"卡片区（/api/bills），卡下拉切换后 /api/finance
带 card 参数刷新。卡清单从 /api/bills 的返回取（它已含卡标识与别名）。

## 测试

- `tests/test_finance_billing.py`：cycle_bounds 纯函数（截断/current/previous/
  指定期/出账日前后边界）
- `tests/test_mcp_contract.py` TestFinance 追加：card_id 透传断言（fake 检查
  arguments）、card_bill 三种 cycle、上游缺 billingDay 的 ToolError
- `tests/test_web_routes.py`：/api/finance?card=、/api/bills 两态（含单卡失败降级）
