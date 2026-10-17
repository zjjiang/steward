# finance Specification

## Purpose
TBD - created by archiving change mod-finance. Update Purpose after archive.

## Requirements

### Requirement: 数据源接入与降级

Steward SHALL 通过 stdio 子进程挂载 credi-insights 的 MCP server（`mcp-server.ts`）
作为唯一财务数据源；Steward **分析只读，写操作仅限分类通道白名单；
不复制数据、不直连 MySQL**。

#### Scenario: 正常调用上游工具

- **WHEN** Steward 的财务工具被调用
- **THEN** 经 `FinanceBackend` 调用 credi-insights 的对应 MCP 工具并返回结果
- **AND** 本地 SQLite 不写入任何财务数据

#### Scenario: 上游不可用时优雅降级

- **WHEN** credi-insights 子进程启动失败、连接超时或调用报错
- **THEN** 工具抛出 ToolError，消息为中文并以"财务数据源不可用"开头、附原因
- **AND** Steward 服务本身不崩溃，非财务工具不受影响

#### Scenario: 数据源位置可配置

- **WHEN** 未设置 `STEWARD_CREDI_DIR` / `STEWARD_CREDI_CMD`
- **THEN** 默认在 `~/Projects/credi-insights` 下执行 `npx tsx mcp-server.ts`
- **AND** 设置后以环境变量指定的目录/命令启动

### Requirement: 跨卡月度汇总（spending_summary）

`spending_summary(month)` SHALL 返回某自然月（缺省当月，格式 YYYY-MM）跨所有卡片的
消费汇总：总支出（DEBIT 合计）、总收入（CREDIT 合计）、交易笔数、
按分类的支出占比（含"未分类"）、支出 Top 5 商户。

#### Scenario: 多卡月度汇总合并

- **GIVEN** 两张卡在某月各有交易与分类
- **WHEN** 调用 `spending_summary` 传入该月
- **THEN** 返回跨卡合并的 total_debit / total_credit / transaction_count
- **AND** 分类金额为两卡同分类之和，按金额降序
- **AND** top_merchants 为支出金额降序前 5 的商户及金额

#### Scenario: 月份格式校验

- **WHEN** month 不是 `YYYY-MM` 格式（如 "十月" 或 "2026-13"）
- **THEN** 抛出 ToolError，消息含 "month" 与正确格式示例

#### Scenario: 无数据月份

- **WHEN** 查询月份无任何交易
- **THEN** 返回 total_debit=0、transaction_count=0、空分类与空商户列表，不报错

### Requirement: 消费趋势对比（spending_trend）

`spending_trend(months)` SHALL 返回最近 N 个自然月（含当月，缺省 3，上限 12）的
逐月总支出、按分类支出，及相邻月份的环比变化。

#### Scenario: 逐月趋势与环比

- **GIVEN** 近三个月的跨卡交易数据
- **WHEN** 调用 `spending_trend`（缺省 months=3）
- **THEN** 返回按月升序的列表，每月含 month / total_debit / by_category
- **AND** 每月附 change_vs_prev（本月 − 上月；最早一月为 null）

#### Scenario: 月数校验

- **WHEN** months 不在 1..12 范围
- **THEN** 抛出 ToolError，消息含 "months" 与合法范围

### Requirement: 订阅与固定支出识别（subscriptions）

`subscriptions(months)` SHALL 分析最近 N 个月（缺省 6，上限 12）的交易，识别
订阅/固定支出：同一商户在 ≥3 个不同月份出现，且各月金额相对月均偏差 ≤20%。

#### Scenario: 典型订阅被识别

- **GIVEN** 商户 "爱奇艺" 连续 4 个月每月一笔 25 元交易
- **WHEN** 调用 `subscriptions`
- **THEN** 结果包含该商户，含月均金额 25、出现月份数 4、最近一笔金额

#### Scenario: 金额波动过大不识别

- **GIVEN** 同商户各月金额分别为 10 / 200 / 15 元（偏差远超 20%）
- **WHEN** 调用 `subscriptions`
- **THEN** 该商户不在结果中

#### Scenario: 出现月份不足不识别

- **GIVEN** 商户仅出现在 2 个不同月份、金额固定
- **WHEN** 调用 `subscriptions`
- **THEN** 该商户不在结果中（阈值 3 个月）

#### Scenario: 结果按月均金额降序

- **WHEN** 多个商户满足订阅条件
- **THEN** 返回列表按月均金额从大到小排序

### Requirement: 卡片与同步透传

Steward SHALL 透传两个管理面工具：`list_cards`（卡片列表）与
`sync_card(card_id)`（触发上游 IMAP 账单同步）。

#### Scenario: 列出卡片

- **WHEN** 调用 `list_cards`
- **THEN** 原样返回上游卡片列表（bank/cardLast4/alias/billingDay/dueDay/isActive，
  不含 IMAP 凭据）

#### Scenario: 触发账单同步

- **WHEN** 调用 `sync_card(card_id="…")`
- **THEN** 透传至上游 `sync_card` 并返回同步计数（newCount/skippedCount）
- **AND** card_id 为空时抛出含 "card_id" 的 ToolError

### Requirement: 分类规则与归类通道

分类规则与分类数据 SHALL 继续存储于 credi-insights（其 UI 与 AI 分类共用同一
规则表）；Steward 不本地保存规则、不重造规则匹配/AI 分类引擎，仅提供受控
写通道，且白名单硬编码、不做任意工具名透传。

#### Scenario: 查看分类与规则

- **WHEN** 调用 `list_categories` / `list_rules`
- **THEN** 原样返回上游的分类列表 / 规则列表（含所属分类名）

#### Scenario: 创建分类规则

- **WHEN** 调用 `create_rule(name="美团→餐饮", pattern="merchant contains 美团",
  category_id="…")`
- **THEN** 透传至上游 create_rule 并返回新规则（含所属分类）
- **AND** name/pattern/category_id 缺失时抛出含对应字段名的 ToolError

#### Scenario: 单笔手动归类

- **WHEN** 调用 `classify_transaction(tx_id="…", category_id="…")`
- **THEN** 透传至上游 update_transaction_category 并返回更新后的交易（含分类名）

#### Scenario: 自动分类先预览后执行

- **WHEN** 调用 `auto_classify(card_id?, dry_run?)` 且未传 dry_run
- **THEN** 以 dry_run=true 调用上游 apply_rules，返回匹配预览（matchedCount +
  matches），不改动任何数据
- **WHEN** 显式传 dry_run=false
- **THEN** 上游执行归类并返回实际匹配结果

### Requirement: 每日分类与待确认清单（pending_classifications）

`pending_classifications(date)` SHALL 列出某自然日（缺省当天，YYYY-MM-DD）中
**未分类**（category 为空）的交易，供每日推送后的"规则自动分类 → 剩余找用户
确认"流水线使用。

#### Scenario: 列出当日未分类交易

- **GIVEN** 当日有 3 笔交易，其中 1 笔已分类、2 笔未分类
- **WHEN** 调用 `pending_classifications()`
- **THEN** 仅返回 2 笔未分类交易，各含 tx_id / merchant / amount / cardLast4 / txTime
- **AND** 按交易时间升序排列

#### Scenario: 全部已分类时返回空

- **WHEN** 查询日期的所有交易均已分类
- **THEN** 返回空列表与 count=0，不报错

#### Scenario: 日期格式校验

- **WHEN** date 不是 YYYY-MM-DD 格式
- **THEN** 抛出含 "date" 与正确格式示例的 ToolError

#### Scenario: 任意透传不暴露

- **WHEN** 查看 Steward 暴露的工具列表
- **THEN** 不存在 create_category 与任意名称的通用透传工具（新增透传须改代码过评审）
