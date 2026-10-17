# Proposal: mod-finance

## Why

路线图第 4 步，也是第一个外部系统集成。财务数据（卡片/交易/分类）全部在
credi-insights 中完成记录与分类，Steward 按既定原则**不复制数据、不直连 MySQL、
不重复造分类引擎**，在其 MCP server（`mcp-server.ts`，stdio）之上封装**面向复盘
的语义工具**，让龙虾能回答"这个月花了多少/花在哪/比上月多不多/有哪些订阅在扣钱"，
并以受控白名单打通分类写操作（自动分类/单笔归类/规则管理）。

## What Changes

- **credi-insights MCP 接入**：`FinanceBackend`（懒加载 stdio 子进程客户端，
  `npx tsx mcp-server.ts`，cwd 指向 credi-insights 仓库，其自带 `dotenv/config`
  读取 `DATABASE_URL`）；上游不可用时降级为 ToolError，不影响其他模块
- **3 个语义分析工具**（聚合在纯函数中，便于 TDD）：
  - `spending_summary(month?)`：跨卡月度汇总 —— 总支出/收入、分类占比、笔数、Top 商户
  - `spending_trend(months=3)`：最近 N 个月逐月支出 + 分类对比，环比标记
  - `subscriptions(months=6)`：订阅/固定支出识别（同商户多月份、金额相近 → 月均金额）
- **2 个白名单透传工具**：`list_cards`（卡片列表）、`sync_card`（触发账单同步，
  龙虾说"同步下招行账单"时用）
- **分类写通道（受控白名单，2026-10-16 与用户确认）**：规则与分类数据**仍存
  credi-insights**（其 UI 与 AI 分类共用同一规则表，挪到 Steward 会产生双规则源、
  且 rule-parser/AI 分类引擎属上游职责），Steward 仅提供龙虾可用的通道：
  - `list_categories` / `list_rules`：只读
  - `create_rule(name, pattern, category_id)`：建分类规则（上游 pattern 语法）
  - `classify_transaction(tx_id, category_id)`：单笔手动归类
  - `auto_classify(card_id?, dry_run?)`：规则批量分类，**dry_run 缺省 true**
    （龙虾先预览、与用户确认后再执行）
  - `pending_classifications(date?)`：列出某日（缺省今天）**未分类**交易
    （tx_id/商户/金额/卡尾号/时间）——支持每日推送场景：同步后规则自动分类，
    没吃掉的由龙虾列给用户逐笔确认（确认后 classify_transaction，
    说"以后都这样"则 create_rule 固化）
- **不做**：本地保存分类规则或任何财务数据、直连 MySQL、重造规则匹配/AI 分类引擎
- `schema_version` 不变（财务不落本地库）

## Capabilities

### New Capabilities

- `finance`：财务模块 —— credi-insights 数据源接入（降级可用）、跨卡月度汇总
  （spending_summary）、趋势对比（spending_trend）、订阅识别（subscriptions）、
  卡片与同步透传（list_cards/sync_card）、受控分类写通道与每日分类确认
  （list_categories/list_rules/create_rule/classify_transaction/auto_classify/
  pending_classifications）。

### Modified Capabilities

（无 —— event-store / fitness / goals / diet / body / commute 均不变）

## Impact

- **新增代码**：`app/finance/backend.py`（MCP 客户端封装）、`app/finance/analyze.py`
  （聚合/趋势/订阅纯函数）、`app/finance/tools.py`（工具注册）、`app/mcp_server.py`
  挂载 + instructions 增补、`tests/test_finance_*.py`
- **运行依赖**：Node + credi-insights 仓库（node_modules 已装、`.env` 有
  `DATABASE_URL`）；默认路径 `~/Projects/credi-insights`，可用
  `STEWARD_CREDI_DIR` / `STEWARD_CREDI_CMD` 覆盖 —— 部署文档写清
- **不影响**：已有 12 个工具与本地库；credi-insights 无任何改动
- **后续 change**：`review`（周/月复盘，届时合并本地流水与财务月度汇总）
