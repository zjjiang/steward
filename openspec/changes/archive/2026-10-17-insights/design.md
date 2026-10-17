# Design: insights

## 定位

问的时候能答 + 龙虾在对话里主动带一句。**纯函数信号检测**，不出文案、
不推送。条目宁缺毋滥：所有信号都有双门槛（相对 + 绝对），不过门槛不出。

## 布局

```
app/modules/insights.py   # 全部纯函数：compare/weight_rate/category_jumps + assemble
app/mcp_server.py         # + get_insights 工具（拉数据 → 纯函数 → items）
```

不加新 store / finance 代码——全部复用 list_events / summarize_transactions /
detect_subscriptions 既有产出。

## 信号与阈值（模块常量）

| 信号 | 周期 | 相对门槛 | 绝对门槛 | metric |
|---|---|---|---|---|
| fitness 次数 | 周环比 | ≥25% | ≥1 次 | workout_count |
| fitness 距离 | 周环比 | ≥25% | ≥2 km | total_distance_km |
| fitness 时长 | 周环比 | ≥25% | ≥20 min | total_duration_min |
| diet 次数/花费 | 周环比 | ≥25% | ≥1 次 / ≥100 元 | meal_count / meal_total_cost |
| finance 总支出 | 月环比 | ≥25% | ≥100 元 | total_debit |
| finance 分类 | 月环比 | ≥50% | ≥100 元 | category:<名>（kind=anomaly） |
| body 斜率 | 近 14 天 | — | ≥0.3 kg/周 | weight_rate_kg_week |

上一周期无数据 → 不出环比条目（无基线不算趋势）。

## 关键设计

### 1. 周期计算

复用 `fitness.current_period`：ref 所在周与前一周、所在月与前一月。
前一周期直接 `current_period(period, today=start - 1day)`。

### 2. compare 纯函数

```python
def compare(metric, area, current, previous, *, abs_threshold, rel_threshold=0.25) -> dict | None
```
- previous 为 None/0 → 返回 None（无基线）
- change = current - previous；direction 按 change 符号
- 不满足双门槛 → None；满足 → 条目 dict

weight_rate：对 14 天窗口内的 (date, weight) 做最小二乘斜率（样本可能不等距，
不能拿首末差除固定天数失真），×7 得 kg/周。复用 body.summarize 的升序
同日取最后口径。窗口 <4 天或 <2 条 → None。

category_jumps：本期 by_category（summarize_transactions 产出）vs 上期，
逐分类过双门槛（50%/100 元），出 anomaly 条目。

### 3. 财务拉取与降级

工具层：本月 + 上月各拉一次 get_transactions → summarize_transactions；
整体 try/except ToolError → finance 条目整体跳过，不报错。
（本期无数据但上游可用 → 空汇总，与"上月无数据"同样无基线处理。）

### 4. 汇总

`assemble_insights(workouts_this, workouts_prev, ..., finance_this, finance_prev, bodies, ref_date) -> list[dict]`
——数据注入式，契约测试与单测零子进程、零 monkeypatch 之外的依赖。

## 测试策略（TDD）

| 层 | 文件 | 覆盖 |
|---|---|---|
| compare / weight_rate / category_jumps | `tests/test_insights_module.py` | 逐 spec 场景 + 阈值边界 |
| MCP 契约 | `test_mcp_contract.py` +`TestInsights` | 正常路径 / 非法日期 / 降级 / 空数据 |
| stdio 冒烟 | `smoke_stdio.py` +1 步 | 结构核对 |

## 取舍记录

- **不做周度 finance 环比**：上游账单口径按月最稳（月账单 + 日推送），
  周度财务噪音大；月环比足够"主动指出"。
- **斜率用最小二乘而非首末差**：体重记录不等距（有时一天两条有时三天不记），
  首末差除以自然日会失真；线性拟合几行代码且可测。
- **不做"连续 N 周"类多窗口检测**：等真实用起来发现缺什么再加（PRD 克制原则）。
