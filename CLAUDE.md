# steward · 个人生活管家

> Steward —— 我的**个人生活管家**，与 Deputy（事业助手）相对应。
> 第一阶段只做 **Finance + Fitness**，Review（周/月复盘）是核心场景。
> 产品需求见 `docs/PRD-第一阶段.md` —— 判断任何功能取舍前先读它。

## 已定架构（2026-10-16 确认）

```
龙虾（OpenClaw）—— 脑子在龙虾侧，Steward 不配 AI、不烧 token
   ├── MCP stdio → deputy      事业助手
   └── MCP stdio → steward     生活管家（本项目）
                       └── MCP → credi-insights   财务数据源
```

- **交互**：Steward 是 OpenClaw（龙虾）背后的纯逻辑后端，同 Deputy 模式。
  龙虾经 MCP stdio 接入；用户微信自然语言输入（"今天跑了 8 公里"），Steward 负责结构化。
- **技术栈**：Python 3.12+ / FastAPI + SQLite（`data/steward.db`，.gitignore）+ FastMCP，包管理用 `uv`。
- **Finance 数据**：Steward 作为 MCP client 挂载 credi-insights 的 `mcp-server.ts`（stdio），
  在其数据之上封装分析工具。**禁止直连其 MySQL，禁止复制数据到本地。**
- **Fitness 数据**：Steward 自有 SQLite 库。

## 开发流程（强制，三条铁律）

与 Deputy 一致，任何非平凡改动必须：

1. **OpenSpec 先行** — `/opsx:propose` 立提案（proposal → specs → design → tasks），
   用户审阅通过前**不动手写代码**。零风险改动（错字/格式）除外。
2. **TDD** — Red → Green → Refactor，先写失败测试再实现。测试跑 `uv run pytest -q`。
3. **PR 合入，push 先问** — **任何 git push 之前必须先找用户确认**（docs 改动也不例外），
   不直推 main。流程：`git switch -c feat/<简述>` → 提交 → **用户确认** → push →
   `gh pr create` → 测试绿 + 用户审阅后合并。一个 OpenSpec change 对应一个分支/PR。

## 命令

```bash
uv sync                     # 装依赖
uv run pytest -q            # 测试
uv run ruff check .         # lint
```

## 范围纪律（第一阶段）

只做 Finance + Fitness。不做：Travel、Family、情感、医疗健康、复杂资产管理、
投资分析、大量生活分类。想扩展时先回到 PRD 第 6 节确认，走 OpenSpec 提案。

## 成功标准

输入是否够轻、是否越来越懂用户的基线、是否真的改变行为 —— 不看功能数量。
