# Proposal

## Why

现在的 finance 工具全是"所有卡混在一起 + 自然月"两个口径：上游 `get_transactions`
本就支持 `cardId` 可选参数但 Steward 没透传；而信用卡账单的真实周期是
**账单日 → 下个账单日**（如 5 号出账，本期 = 上月 5 日 ~ 本月 4 日），按自然月
汇总的"本月账单"与实际要还的账单对不上。需要卡级别 + 账单周期两个口径。

## What Changes

- `fetch_transactions_range` 增加可选 `card_id`，透传上游 `cardId`
- `spending_summary` / `pending_classifications` 增加可选 `card_id`（缺省行为不变）
- 新工具 `card_bill(card_id, cycle?)`：按卡的账单日算出账单周期（缺省本期），
  返回该期汇总（总支出/笔数/分类构成/明细）+ 出账日与还款日；cycle 支持
  `current` / `previous` / `YYYY-MM`（以该月账单日为期名）
- **依赖上游改动**：credi-insights `list_cards` 的 return 需加 `billingDay`、
  `dueDay` 两字段（数据库已有，仅输出遗漏）；上游未改前 `card_bill` 报
  可读错误"上游未返回账单日"
- UI 账单页：增加按卡过滤与本期/上期账单卡片
- 自然月口径的工具（trend/subscriptions/insights/review）保持不变——它们是
  生活分析口径，账单周期是还款口径，两者并存

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `finance`：新增卡级别查询要求（card_id 透传）与账单周期工具 `card_bill`
  （账单日计算周期、出账/还款日提示、上游缺字段的降级）
- `web-ui`：账单页新增按卡过滤与账单周期视图的只读展示

## Impact

- 修改：`app/finance/tools.py`（fetch 透传 + card_bill + 两工具加参）、
  `app/web/routes.py`（finance 端点加 card 参数与 bill 段）、
  `app/web/static/index.html`（按卡切换 + 本期账单卡）
- 不动：store、modules、mcp_server 编排（review/insights 仍走自然月）
- 上游：credi-insights `listCards` return 补 `billingDay`/`dueDay`（一句话修复，
  用户自行提交）
