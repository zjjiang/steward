# Tasks: mod-finance

先纯函数（TDD 主战场），再 backend，再工具接线，最后可选真实冒烟。全程零子进程测试。

## 1. 分析纯函数（app/finance/analyze.py）

- [x] 1.1 `merge_card_stats`：跨卡相加 total/笔数、分类合并降序、Top 5 商户 —— 逐 spec 场景写测试
- [x] 1.2 `compute_trend`：逐月升序、by_category、change_vs_prev（最早月 null）
- [x] 1.3 `detect_subscriptions`：≥3 个月 + ±20% 阈值、月均降序、金额波动/月份不足排除 —— 逐 spec 场景写测试
- [x] 1.4 `filter_pending`：未分类过滤（category=null）+ 按交易时间升序 + tx_id/商户/金额/卡尾号/时间 投影

## 2. 数据源封装（app/finance/backend.py）

- [x] 2.1 `FinanceBackend.call(tool, args)`：懒加载 fastmcp Client（StdioTransport，cwd=credi 目录），会话缓存复用
- [x] 2.2 错误转译：连接失败/上游 isError → `ToolError("财务数据源不可用：<原因>")`，fake client 注入测试
- [x] 2.3 配置解析：`STEWARD_CREDI_DIR`（默认 `~/Projects/credi-insights`）/ `STEWARD_CREDI_CMD`（JSON，默认 npx tsx）
- [x] 2.4 FastMCP lifespan 接线：服务退出时关闭 backend 会话

## 3. MCP 工具（app/finance/tools.py，注册 11 个）

- [x] 3.1 `spending_summary(month?)`：YYYY-MM 校验 → list_cards + 逐卡 get_stats → merge_card_stats
- [x] 3.2 `spending_trend(months=3)`：1..12 校验 → 逐月跨卡拉取 → compute_trend
- [x] 3.3 `subscriptions(months=6)`：1..12 校验 → 逐月 get_transactions 拼接 → detect_subscriptions
- [x] 3.4 `list_cards` / `sync_card(card_id)`：白名单透传，card_id 空值校验
- [x] 3.5 分类通道：`list_categories` / `list_rules` / `create_rule`（必填校验）/
      `classify_transaction` / `auto_classify`（dry_run 缺省 true）
- [x] 3.6 `pending_classifications(date?)`：YYYY-MM-DD 校验 → 当日 get_transactions → filter_pending
- [x] 3.7 `mcp_server.py` 挂载 + instructions 增补 finance 段（龙虾用法示例，含每日分类流水线编排说明）

## 4. 契约测试与收尾

- [x] 4.1 `tests/test_mcp_contract.py` 扩展 `TestFinance`：monkeypatch fake backend，覆盖正常路径/上游故障降级/参数校验/auto_classify 缺省预览/白名单外工具不存在
- [x] 4.2 全量测试绿 + ruff 无告警
- [x] 4.3 `scripts/smoke_finance.py`（可选真实链路：需本地 credi-insights 就绪，人工执行）——脚本已就绪，待本机跑一次
- [x] 4.4 提交（本地），经用户确认后 push + PR
