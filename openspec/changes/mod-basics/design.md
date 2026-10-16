# Design: mod-basics

## Context

模块样板已在 mod-fitness 确立：`app/modules/<name>.py` 提供 `validate_payload` +
`summarize` 纯函数，mcp_server.py 注册工具，数据落通用 events 表。本 change
照样板复制三个薄模块。动机见 proposal，行为契约见 specs/。

## Goals / Non-Goals

**Goals**
- 三个模块零新表、零迁移，纯函数 + 工具注册，结构严格同构于 fitness
- 每个模块的汇总口径贴合各自领域（body 是序列而非计数——样板允许这种差异）

**Non-Goals**
- 热量/营养、体重趋势判定、通勤时长（后续 insights 或用到再加）
- 多指标 body 记录（体脂等，出现需求时扩展 payload 约定即可）

## Decisions

### D1. 三个模块 = 三个同构文件，不建公共"薄模块基类"

`diet.py` / `body.py` / `commute.py` 各自实现 `validate_payload` + `summarize`。
三份小重复优于一层抽象：各模块汇总口径天然不同（diet 按餐次计数、body 是序列、
commute 按天数），强行抽象会造出参数化的泥球。等第四个模块出现共性时再提炼。

### D2. 校验规则（与 specs 一致）

- diet：`desc` 非空；`meal` ∈ 4 值可选；`cost` 可选 > 0
- body：`weight_kg` ∈ (0, 500]
- commute：`direction` ∈ {in, out}

### D3. `query_body` 的汇总形态是序列而非计数

返回 `{items, total, truncated, series: [{date, weight_kg}], change: 首末差|null}`。
series 按 occurred_at 升序、同日多条取最后一条。这是对样板的合法偏离——
各模块 summary 形态由领域决定。

### D4. `check_in` 是 `log_commute` 的领域命名

工具名用 `check_in`（用户的语言），内部即 commute 类型落库。不提供单独的
`log_commute` 别名，避免龙虾选择困难。

### D5. 测试策略（TDD）

- `tests/test_basics_modules.py`：三模块纯函数（校验/汇总），逐 spec 场景
- `tests/test_mcp_contract.py` 扩展：6 个新工具成功/失败路径
- `scripts/smoke_stdio.py` 扩展：三模块各走一条成功路径

## Risks / Trade-offs

- [同日多次打卡统计天数时按自然日去重即可，跨零点加班场景会把次日到岗算新一天] → 第一阶段接受；direction 语义由用户自己把握
- [体重同日多条] → series 取同日最后一条，明细仍全量保留可追溯

## Migration Plan

无 schema 变化，无迁移。回滚 = 删分支。

## Open Questions

无。
