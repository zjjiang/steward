# Tasks

## 1. 依赖

- [x] 1.1 `uv add fastapi uvicorn`，`uv sync` 通过

## 2. web 包（TDD）

- [x] 2.1 RED：`tests/test_web_routes.py` — 首页 200 且为 HTML；day 空库零值；
      day 非法日期 400；review 参数透传与非法 period 400；insights 200；
      finance 可用/降级两态（fake backend）
- [x] 2.2 GREEN：`app/web/__init__.py`、`app/web/routes.py`（五个只读端点 +
      ToolError→400 翻译）、`app/web/server.py`（app 工厂 + lifespan 关 backend）
- [x] 2.3 前端：`app/web/static/index.html` 四 tab 单页（今日/复盘/洞察/账单），
      手机宽度可用，本地数据缺失显示零值
- [x] 2.4 Refactor：消除 routes 内重复，全绿

## 3. 验证

- [x] 3.1 `uv run pytest -q` 全绿（含既有 176 个测试）
- [x] 3.2 `uv run ruff check .` 干净
- [x] 3.3 本地起 `uvicorn app.web.server:app` 冒烟：`/`、`/api/day`、
      `/api/review`、`/api/insights`、`/api/finance` 实测返回
- [x] 3.4 `openspec validate add-web-ui --strict` 通过

## 4. 收尾

- [x] 4.1 提交分支（不 push——等用户确认后 push + 出 PR）
