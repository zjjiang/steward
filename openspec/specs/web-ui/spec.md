# web-ui Specification

## Purpose
TBD - created by archiving change add-web-ui. Update Purpose after archive.

## Requirements

### Requirement: 本地只读仪表盘

Steward SHALL 提供一个本地网页仪表盘（FastAPI 应用，默认只绑定 127.0.0.1），
以只读方式展示生活数据；系统 SHALL NOT 提供任何经由仪表盘写入数据（记事件、
改目标、分类交易等）的端点。

#### Scenario: 打开首页得到仪表盘页面

- **WHEN** 用户在浏览器打开 `GET /`
- **THEN** 返回单页 HTML 仪表盘（含单日流水、周期复盘、趋势洞察、月度账单概况的视图），
  页面经只读 JSON API 取数，无前端构建步骤

### Requirement: 单日流水视图

仪表盘 SHALL 提供 `GET /api/day?date=YYYY-MM-DD`（缺省当天），返回该日的
运动/饮食/体重/通勤明细与各自汇总，数据形状与对应 MCP 查询工具一致。

#### Scenario: 查询有数据的日期

- **WHEN** 当日已记录一次运动和一顿饮食，请求 `GET /api/day`
- **THEN** 响应含 workouts 与 meals 的明细及汇总（次数/时长/距离、次数/花费）

#### Scenario: 日期参数非法

- **WHEN** 请求 `GET /api/day?date=2026/10/17`
- **THEN** 返回 400 与可读的错误信息

### Requirement: 周期复盘与洞察视图

仪表盘 SHALL 提供 `GET /api/review`（period=week|month，缺省 week）与
`GET /api/insights`，其响应 SHALL 与对应 MCP 工具 `get_review` / `get_insights`
完全一致（同一编排逻辑，不另起数据路径）。

#### Scenario: 复盘参数透传

- **WHEN** 请求 `GET /api/review?period=month&ref_date=2026-10-31`
- **THEN** 响应等价于 MCP 工具 `get_review(period="month", ref_date="2026-10-31")` 的返回

#### Scenario: 复盘参数非法

- **WHEN** 请求 `GET /api/review?period=year`
- **THEN** 返回 400 与可读的错误信息

### Requirement: 月度账单概况视图

仪表盘 SHALL 提供 `GET /api/finance?month=YYYY-MM`（缺省当月），一次返回该月
消费汇总、近 6 个月支出趋势、订阅识别与当月待确认（未分类）交易。

#### Scenario: 上游财务不可用时降级

- **WHEN** credi-insights 不可达，请求 `GET /api/finance`
- **THEN** 返回 200 且 `{"available": false, "error": <原因>}`，不返回 5xx

#### Scenario: 上游可用时返回概况

- **WHEN** credi-insights 可达且有当月交易，请求 `GET /api/finance`
- **THEN** 响应含 summary（total_debit/by_category/top_merchants）、
  trend（近 6 个月）、subscriptions 与 pending（未分类交易清单）

### Requirement: 本地数据缺失时正常呈现

本地 SQLite 无当日/当期数据时，对应视图 SHALL 正常返回空汇总（count 为 0），
SHALL NOT 因无数据返回错误。

#### Scenario: 空库查询单日

- **WHEN** 空库上请求 `GET /api/day`
- **THEN** 返回 200，各模块明细为空列表且汇总为零值
