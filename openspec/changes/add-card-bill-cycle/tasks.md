# Tasks

## 1. 账单周期纯函数（TDD）

- [x] 1.1 RED：`tests/test_finance_billing.py` — 指定期窗口、current（今天在
      出账日前/后两态）、previous、31 日卡遇 2 月截断、非法 billing_day/cycle
- [x] 1.2 GREEN：`app/finance/billing.py` 的 `cycle_bounds`

## 2. 卡级别透传 + card_bill 工具（TDD）

- [x] 2.1 RED：contract 测试 — fetch 带 cardId、缺省不带；spending_summary/
      pending_classifications 的 card_id；card_bill 三种 cycle 与缺账单日 ToolError
- [x] 2.2 GREEN：fetch_transactions_range 加 card_id；两个工具加参；
      `app/finance/tools.py` 模块级 `card_bill` + MCP 工具注册

## 3. web 层（TDD）

- [x] 3.1 RED：/api/finance?card= 透传；/api/bills 全卡两态 + 单卡失败降级
- [x] 3.2 GREEN：routes 加参数与端点；前端账单页卡切换 + 本期账单卡片区

## 4. 验证与收尾

- [x] 4.1 `uv run pytest -q` 全绿、`uv run ruff check .` 干净
- [x] 4.2 `openspec validate add-card-bill-cycle --strict` 通过
- [x] 4.3 真实链路冒烟（list_cards / card_bill）——上游补 billingDay 前应报可读错误
- [x] 4.4 提交分支（push 前等确认）
