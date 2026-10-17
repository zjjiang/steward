# Proposal: review

## Why

路线图第 5 步，PRD 的核心场景："每周/每月复盘"——把本地生活流水（运动/饮食/
身体/通勤/兜底）+ 运动目标 + credi-insights 财务数据**一次性拼装成结构化
复盘数据**，成文（鼓励、建议、异常指出）由龙虾完成，Steward 只给干净的料。

## What Changes

- 新工具 `get_review(period, ref_date?)`：
  - `period`: week（周一始）/ month（自然月）；`ref_date` 缺省今天（Asia/Shanghai）
  - 返回 sections：
    - `meta`：period / start / end / ref_date
    - `fitness`：运动汇总（次数/时长/距离/按类型）+ 全部活跃目标的进度判定
    - `diet`：次数/花费/按餐次
    - `body`：周期内体重序列 + 首末差值
    - `commute`：打卡天数 / in、out 次数
    - `finance`：窗口内跨卡支出汇总（分类占比 / Top 商户）；月度复盘附订阅识别
    - `other`：兜底事件按 type 计数
- 财务新增纯函数 `summarize_transactions(transactions)`：任意时间窗口的
  交易汇总（不依赖上游按月的 get_stats，周/月同一代码路径）
- goals store 新增 `list_active_goals(conn)`（复盘要遍历全部活跃目标）
- **降级**：credi-insights 不可用时 finance section 返回 `available: false` +
  原因，其余 section 照常——复盘不能因为财务挂了而整体失败
- **不做**：成文总结/建议（龙虾职责）、跨周期对比解读（insights change）、
  主动推送

## Capabilities

### New Capabilities

- `review`：周期复盘 —— get_review 工具，周期语义（周一起始周/自然月）、
  各 section 拼装、财务降级、空周期全零不报错。

### Modified Capabilities

（无 —— 各既有模块与 finance 分析函数只被复用，不被修改；goals store 增一个
查询函数属实现细节）

## Impact

- **新增代码**：`app/modules/review.py`（编排）、`app/finance/analyze.py` 增
  `summarize_transactions`、`app/store/goals.py` 增 `list_active_goals`、
  `app/mcp_server.py` 注册 1 个工具 + instructions 增补、`tests/` 对应单测
- **schema**：无变化（纯读）
- **不影响**：既有 23 个工具行为
- **后续 change**：`insights`（趋势与异常主动发现，在 review 数据之上）
