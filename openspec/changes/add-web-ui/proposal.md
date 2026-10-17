# Proposal

## Why

Steward 目前只有一个 MCP 后端，看数据只能靠龙虾对话或直接调 MCP 工具——没有一个
"能看见" 的地方。加一层本地只读网页仪表盘，让用户（和开发过程）能直接看到今天的
运动/饮食/体重、周期复盘、趋势洞察和账单概况，感受这套数据到底长什么样。
这不改变架构原则：龙虾仍是主交互入口，UI 只是观察窗，不做任何写入操作。

## What Changes

- 新增 `app/web/` 包：FastAPI 应用，提供只读 JSON API + 单页仪表盘（静态 HTML，
  无前端构建步骤）
- API 复用现有模块逻辑（`mcp_server` 的 review/insights 编排、`finance` 的
  fetch/analyze 纯函数），不复制数据路径；财务不可用时照旧降级为
  `available: false`
- 端点：
  - `GET /` — 仪表盘页面
  - `GET /api/day?date=` — 单日流水（运动/饮食/体重/通勤 + 各自汇总）
  - `GET /api/review?period=&ref_date=` — 周期复盘（透传 get_review）
  - `GET /api/insights?ref_date=` — 趋势洞察（透传 get_insights）
  - `GET /api/finance?month=` — 月度账单概况（汇总/趋势/订阅/待分类）
- 新增依赖 `fastapi` + `uvicorn`（fastmcp 未引入 fastapi，需显式声明）
- 本地启动：`uv run uvicorn app.web.server:app`（只绑 127.0.0.1）
- **不提供任何写操作端点**——记数据走龙虾，分类确认走龙虾对话

## Capabilities

### New Capabilities

- `web-ui`：本地只读网页仪表盘——单日流水、周期复盘、趋势洞察、月度账单概况的
  HTTP 只读视图，及其只读边界（无写入端点、上游故障降级不报错）

### Modified Capabilities

（无——MCP 工具行为不变，本 change 只新增读取视图）

## Impact

- 新增：`app/web/`（server、routes、static/index.html），`tests/test_web_routes.py`
- 修改：`pyproject.toml`（+fastapi、+uvicorn）
- 复用不动：`app/mcp_server.py`、`app/modules/*`、`app/finance/*`、`app/store/*`
- 风险：web 进程与 MCP stdio server 是两个独立进程，各自读同一 SQLite（WAL 无冲突）；
  web 侧 finance 走独立的 FinanceBackend 子进程实例
