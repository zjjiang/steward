# Tasks: review

先两处小地基（纯函数），再编排函数，最后工具接线。全程 TDD，零子进程测试。

## 1. 地基

- [ ] 1.1 `finance/analyze.py` 增 `summarize_transactions(transactions)`：任意窗口
      总支出/收入/笔数/按分类（含未分类）/Top 商户，与 merge_card_stats 共享金额归一 —— 逐场景测试
- [ ] 1.2 `store/goals.py` 增 `list_active_goals(conn)`：全部 status=active，含 superseded 不计 —— 测试

## 2. 编排函数（app/modules/review.py）

- [ ] 2.1 `period_bounds(period, ref_date)`：复用 fitness.current_period，week/month 边界 —— 逐 spec 场景测试
- [ ] 2.2 `assemble_review(...)`：注入本地 events + 财务数据，拼 meta/fitness（含 goals 判定）/
      diet/body/commute/other sections —— 逐 spec 场景测试
- [ ] 2.3 财务 section 形态：月度含 subscriptions、周度不含；available:false 降级形态

## 3. MCP 工具

- [ ] 3.1 `get_review(period, ref_date?)`：参数校验（period 白名单 / YYYY-MM-DD）→
      list_events + list_active_goals + 财务拉取（try/except ToolError 降级）→ assemble_review
- [ ] 3.2 instructions 增补 review 段（龙虾用法：复盘数据 → 成文）

## 4. 契约测试与收尾

- [ ] 4.1 `tests/test_mcp_contract.py` 追加 `TestReview`：正常周复盘 / 非法参数 / 财务降级 /
      空周期
- [ ] 4.2 全量测试绿 + ruff 无告警
- [ ] 4.3 stdio 冒烟扩展：get_review 月度复盘一步（含财务 fake 不适用——冒烟里仅验结构）
- [ ] 4.4 提交（本地），经用户确认后 push + PR
