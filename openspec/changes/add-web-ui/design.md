# Design

## 复用而非另起数据路径

web 层不重新实现任何业务逻辑：

- **day / review / insights**：直接调用 `app/mcp_server.py` 里的工具函数
  （`query_workouts` / `query_meals` / `query_body` / `query_commute` /
  `get_review` / `get_insights`）。它们在 fastmcp 装饰后仍是可调用的普通函数，
  校验错误抛 `ToolError`。MCP 工具与 web 视图天然同源，不会漂移。
- **finance**：`spending_summary` 等是 `register_finance_tools` 内的闭包，
  外部不可调；web 侧用 `app/finance/tools.py` 的模块级辅助
  （`fetch_transactions_range` / `_recent_months` / `_month_range`）+
  `analyze` 纯函数就地拼一个概况函数（~30 行聚合，无业务规则重复）。
  `get_backend` 由 web 模块自己 import（测试 patch 点在 `app.web.routes.get_backend`）。

## 进程与生命周期

`uv run uvicorn app.web.server:app --host 127.0.0.1`。web 进程与 MCP stdio
server 是两个独立进程：SQLite 同库并发读没有问题（web 只读）；finance 走
web 进程自己的 FinanceBackend 子进程实例，lifespan 退出时 `close_backend()`。

## 错误边界

- 参数校验失败（ToolError 来自入参校验）→ HTTP 400 + `{"detail": <可读信息>}`
- finance 上游故障（ToolError 来自 backend 转译，消息带"财务数据源不可用"前缀）
  → 不抛错，200 + `{"available": false, "error": ...}`，与 get_review 的
  finance 段降级语义一致
- review/insights 中 finance 段已在上游函数内部降级，web 不再特殊处理

## 前端

单文件 `app/web/static/index.html`：原生 JS + CSS，四个 tab（今日/复盘/洞察/账单），
手机宽度可用（龙虾生态用户以手机查看为主）。无框架、无构建步骤、无外部 CDN 依赖
（本地生活数据不出墙）。金额保留两位小数，空数据显示零值占位而非报错。

## 测试

`tests/test_web_routes.py`：fastapi `TestClient` + monkeypatch `STEWARD_DB`
指到 tmp 库（沿用 test_mcp_contract 的约定）；finance 用 fake backend patch
`app.web.routes.get_backend`（value/Exception 双形态，与 contract 测试同风格）。
MCP 侧现有测试不动。
