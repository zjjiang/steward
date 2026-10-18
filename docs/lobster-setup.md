# 龙虾（OpenClaw）接入 steward 部署指南

把 steward（个人生活管家）挂到龙虾上，让分身能记流水、出复盘、管账单——
与 deputy（事业侧二号位）相对应的生活侧。

> 前提认知：steward **本身不烧 token、不需要配任何 AI API**。它是纯逻辑后端
> （SQLite 流水 + 门禁式财务通道），"智能"全来自龙虾里你配的大模型——
> token 花在龙虾侧，不在 steward。

---

## 0. 适用场景

本指南针对 **龙虾与 steward 在同一台机器** 的情况，用 **stdio** 方式接入——
最简单、无网络、无鉴权烦恼。跨机部署需另议（同 deputy 红线）。

## 1. 拉代码 + 装依赖

```bash
git clone https://github.com/zjjiang/steward.git
cd steward
uv sync
```

## 2. 数据在哪（数据不出墙）

- **生活流水**：steward 自有 SQLite，`data/steward.db`，首次运行自动建库，
  gitignore，永不进仓库。无迁移步骤，跑起来就有。
- **财务数据**：steward **不存任何账单**。它按需以 MCP client 身份拉起
  credi-insights 的 `mcp-server.ts`（stdio 子进程），账单数据始终只在
  credi-insights 的 MySQL 里。禁止直连其数据库、禁止复制到本地。

### finance 通道前置条件（可选，缺了只影响账单工具）

steward 要能找到 credi-insights 仓库（默认 `~/Projects/credi-insights`），
且机器上有 `node`/`npx`（拉起其 mcp-server.ts 用）。路径不同就在龙虾的
steward server 配置里加 env（见 §4）。credi-insights 不可达时，账单类工具
统一报"财务数据源不可用：…"，生活流水工具完全不受影响。

## 3. 验证 steward 本身能跑

```bash
uv run pytest -q                                 # 应全绿
uv run python -m app.mcp_server                  # MCP：能启动不报错即可（Ctrl-C 退出）
uv run uvicorn app.web.server:app --port 8901    # 只读看板：浏览器开 http://127.0.0.1:8901
```

看板是**只读观察窗**（今日/复盘/洞察/账单四个 tab），不是交互入口——
记数据仍然对龙虾说。8787 端口常被 Docker 占用，建议避开。

## 4. 在龙虾里配置 MCP（stdio）

在龙虾的 MCP 配置中加一个 server（`cwd` 必须是 steward 目录的**绝对路径**）：

```json
{
  "mcpServers": {
    "steward": {
      "command": "uv",
      "args": ["run", "python", "-m", "app.mcp_server"],
      "cwd": "/绝对路径/到/steward",
      "env": { "STEWARD_CREDI_DIR": "/绝对路径/到/credi-insights" }
    }
  }
}
```

- `env` 仅在 credi-insights 不在默认位置时需要；`uv` 不在 PATH 就换绝对路径。
- 配好重启龙虾，能列出 steward 的工具即接入成功（当前 26 个，全集以
  steward MCP 的握手 instructions 为准——那份清单随代码更新，永远最新）。

## 5. 给龙虾装"生活管家"人设（关键）

steward 的门禁不在"能不能写"（生活流水本就直接落库），而在**财务通道的
确认纪律**与**不编造**。把下面这段写进龙虾的角色/系统提示：

```
你是用户的"生活管家"——帮用户轻量记录日常生活并定期复盘，经 MCP 接入
steward（生活流水 + 账单分析）。

管家铁律：
1. 用户用自然语言说的事，先结构化再落库：运动 log_workout、吃饭 log_meal、
   体重 log_body、打卡 check_in；认不出的生活事件走 log_event 兜底，不要拒绝。
2. 账单分类三步走：auto_classify 缺省 dry_run 只出预览；给用户看过、用户
   确认后才 dry_run=false 执行；规则没吃掉的用 pending_classifications
   列出来逐笔问。
3. 不确定的账单分类不猜——问用户；用户说"以后都这样"才 create_rule 固化。
4. 复盘（get_review）与洞察（get_insights）只说数据里有的：finance 段
   available=false 就跳过；洞察无条目就是没有值得说的，不要硬凑。
5. 成文先结论后数字，简短；用户没问不铺开。

工具用法与参数细则以 steward MCP 握手 instructions 为准——那边永远最新，
不要凭记忆猜参数。
```

> 与 deputy 的门禁不同：steward 没有"提议-批准"环节（生活记录要的就是轻），
> 唯一的安全带是第 2、3 条——**账单归类必须过用户确认**，防止龙虾替用户定规。

## 6. 跑通四条链路（验收）

在龙虾对话里依次：

1. **记流水**：你说"今天跑了 8 公里" → 龙虾 `log_workout` → 复述要点。
2. **复盘**：你说"这周复盘一下" → 龙虾 `get_review(period="week")` →
   按运动/目标/饮食/财务顺序成文（有 finance 段说明 credi 通道也通了）。
3. **账单分类流水线**：你说"同步一下 XX 卡的账单" → `list_cards` →
   `sync_card` → `auto_classify`（预览）→ 经你确认后执行 →
   `pending_classifications` 列剩余 → 逐笔问你。
4. **洞察**：你说"最近有什么趋势" → `get_insights` → 有条目说条目，
   没条目就直说"没有值得说的变化"。

四条都通，生活管家就活了。数据攒几周后再看洞察页有真信号，才算达到
PRD 的成功标准（输入轻、懂你、改变行为）。

---

## 安全红线（勿破）

- **无鉴权，仅限 localhost**（同 deputy）。跨机必先加鉴权。
- **数据不出墙**：`data/`、`*.db` 永远 gitignore；账单数据只活在
  credi-insights，steward 侧零落库。
- **web 看板只读**：不提供任何写端点；只绑 127.0.0.1。
- **微信入口是后话**：接微信时连同鉴权一起做（同 deputy 路线图阶段 4）。
