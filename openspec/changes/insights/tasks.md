# Tasks: insights

纯函数信号检测先行，工具接线收尾。全程 TDD，零子进程测试。

## 1. 信号纯函数（app/modules/insights.py）

- [ ] 1.1 阈值常量 + `compare(metric, area, current, previous, *, abs_threshold, rel_threshold=0.25)`：
      无基线/双门槛不过 → None，过 → 条目 dict —— 逐 spec 场景测试
- [ ] 1.2 `weight_rate(bodies_window)`：最小二乘斜率 ×7（kg/周），<2 条或窗口 <4 天 → None —— 测试
- [ ] 1.3 `category_jumps(this_by_cat, prev_by_cat)`：≥50% 且 ≥100 元 → anomaly 条目 —— 测试
- [ ] 1.4 `assemble_insights(...)`：拼 fitness/diet 周环比 + finance 月环比/分类 + body 斜率，注入式 —— 测试

## 2. MCP 工具

- [ ] 2.1 `get_insights(ref_date?)`：ref 校验 → 本/上周期 events 拉取 → 本/上月财务
      （try/except ToolError 降级）→ assemble_insights
- [ ] 2.2 instructions 增补 insights 段（龙虾：问趋势时用、复盘时可带一句）

## 3. 契约测试与收尾

- [ ] 3.1 `test_mcp_contract.py` +`TestInsights`：正常路径 / 非法日期 / 财务降级 / 空数据
- [ ] 3.2 全量测试绿 + ruff 无告警
- [ ] 3.3 stdio 冒烟 +get_insights 步骤（结构核对）
- [ ] 3.4 提交（本地），经用户确认后 push + PR
