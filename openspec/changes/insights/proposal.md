# Proposal: insights

## Why

路线图第 6 步（第一阶段收官）。PRD 对 insights 的定位是克制的：
**"问的时候能答 + Review 里主动指出"**，不做主动推送打扰。本 change 交付
一个 `get_insights(ref_date?)` 工具：从既有流水与财务数据里算出**跨周期
趋势与异常**的结构化条目（面积/类型/指标/现值/前值/变化），成文归龙虾。

## What Changes

- 新工具 `get_insights(ref_date?)`：返回 `{items: [...]}`，每条
  `{area, kind, metric, current, previous, change, direction}`，全部有阈值门槛，
  **不够显著不出条目**（宁可少说，不说噪音）：
  - **fitness 周环比**：次数 / 总距离 / 总时长，本周 vs 上周
  - **diet 周环比**：次数 / 花费合计
  - **finance 月环比**：总支出 + 分类跳变（某分类较上月涨幅 ≥50% 且差额 ≥100 元）
  - **body 体重趋势**：近 14 天斜率（kg/周），|斜率| ≥0.3 才报
- 阈值全部为模块常量；财务段失败降级（fitness/diet/body 条目照常）
- **不做**：主动推送/定时通知、自然语言文案、预测（均超出 PRD 第一阶段）

## Capabilities

### New Capabilities

- `insights`：趋势与异常发现 —— get_insights 工具，环比阈值门槛、
  分类跳变、体重斜率、财务降级。

### Modified Capabilities

（无 —— 只读既有模块函数与 finance 数据，不改任何行为）

## Impact

- **新增代码**：`app/modules/insights.py`（纯函数）、`app/mcp_server.py`
  注册 1 个工具 + instructions 增补、`tests/` 对应单测
- **schema**：无变化（纯读）
- **不影响**：既有 24 个工具行为
- **第一阶段至此功能闭环**；后续扩展（主动推送、预测）先回 PRD 第 6 节
