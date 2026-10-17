# Design: review

## 定位

复盘 = **纯编排**：Steward 把周期内数据拼成结构化 sections，龙虾负责成文
（鼓励/建议/异常解读）。Steward 不产出自然语言，不做跨周期对比（insights）。

## 布局

```
app/modules/review.py      # assemble_review(...)：纯编排函数（数据注入，可测）
app/finance/analyze.py     # + summarize_transactions(transactions)：任意窗口交易汇总
app/store/goals.py         # + list_active_goals(conn)
app/mcp_server.py          # + get_review 工具（参数校验 → 拉数据 → 编排）
```

- 编排函数放 `app/modules/review.py` 与既有模块并列；它**不 import finance
  backend**——财务数据由工具层拉好后注入，模块保持纯函数、测试零子进程。

## 关键设计

### 1. 周期边界

复用 `fitness.current_period(period, today)`（周一起始周 / 自然月，
Asia/Shanghai）——同一段语义不写第二份。返回 (start, end) 两个 `date`，
事件过滤走 `list_events(date_from=date.isoformat(), date_to=…)` 的既有
日期前缀比较。

### 2. 财务窗口汇总：新纯函数 summarize_transactions

上游 `get_stats` 只支持按自然月，周复盘无法直接用。新增
`summarize_transactions(transactions)`：直接从 get_transactions 响应算
total_debit / total_credit / transaction_count / by_category（按
category.name，无则"未分类"）/ top_merchants，与 merge_card_stats 共享
金额归一与投影逻辑。周/月复盘走同一代码路径；月度不再调 get_stats
（口径自洽，代价是绕过上游既有统计——两端口径本就一致，均来自同一张表）。

单月单次 get_transactions 仍在 take:500 内（mod-finance 已核实量级）；
周窗口更小。

### 3. 目标进度

`list_active_goals(conn)` 返回全部 status=active 的 goals；逐个调用
`fitness.progress(goal, workouts)`（ref_date=复盘 ref_date），输出
metric/target/current/verdict/period。无目标 → 空列表。

### 4. 财务降级

工具层对 finance 段的拉取整体 try/except ToolError：
成功 → `{"available": True, ...}`；失败 →
`{"available": False, "error": "<转译后的中文原因>"}`。其余 section 照常。
订阅识别仅在 month 周期附（复用 subscriptions 工具的数据路径：逐月拉取），
week 周期省略——一周窗口内的"固定支出"无意义。

### 5. other 兜底 section

已知类型 {workout, meal, body, commute} 之外按 type 计数，让"配牙 800 块"
这类零散记录在复盘里可见，为未来升格模块提供数据感知。

## 测试策略（TDD）

| 层 | 文件 | 说明 |
|---|---|---|
| summarize_transactions | `tests/test_finance_analyze.py` 追加 | 空列表/字符串金额/未分类 |
| list_active_goals | `tests/test_store_goals.py` 追加 | 空库/多目标/含 superseded |
| assemble_review | `tests/test_review_module.py` 新建 | 逐 spec 场景：边界/汇总/降级/空周期 |
| MCP 契约 | `tests/test_mcp_contract.py` 追加 `TestReview` | fake backend，参数校验 + 降级路径 |

## 取舍记录

- **不做跨周期对比/文案**：insights 与龙虾的职责，复盘数据结构先稳定。
- **月度财务不再调 get_stats**：同一代码路径覆盖周/月，减少一个上游依赖点；
  上游 stats 若日后增强（如排除未入账）再评估切回。
- **不加 review 快照表**：复盘随时可从流水重算（core 事件层设计初衷），
  无状态、无迁移。
