# Design: mod-finance

## 现状核对（2026-10-16 实读 credi-insights：mcp-server.ts + prisma/schema.prisma）

上游 `mcp-server.ts`（stdio，`@modelcontextprotocol/sdk`）暴露 10 个工具：

| 上游工具 | Steward 用法 |
|---|---|
| `list_cards` | 透传（select 不含 imapPassword，无泄密面） |
| `get_transactions(cardId?, startDate?, endDate?, categoryId?)` | subscriptions 数据源（**take 500，见风险 1**） |
| `get_stats(cardId, period="YYYY-MM")` | summary / trend 数据源（按卡） |
| `sync_card(cardId)` | 透传（含 60s/卡限流，上游负责） |
| `list_categories` / `list_rules` | 透传（只读） |
| `create_rule` / `update_transaction_category` / `apply_rules` | 受控封装为 create_rule / classify_transaction / auto_classify（dry_run 缺省 true），见"分类写通道" |
| `create_category` | **不暴露**（分类本体管理属 credi-insights UI） |

关键事实：

- `mcp-server.ts` 首行 `import "dotenv/config"` —— **cwd 指到其仓库即自动读取
  `.env` 的 `DATABASE_URL`**，Steward 无需注入密钥（允许 env 覆盖）。
- 无构建产物，直接 `npx tsx mcp-server.ts`（tsx 在其 devDependencies，node_modules
  已装即可）。
- `get_stats` 是**按卡**查询 → 跨卡汇总必须 `list_cards` 后逐卡合并（纯函数）。
- 上游所有错误以 `isError: true` 的文本 content 返回 → backend 需识别并转译。
- Transaction 模型（schema.prisma）：merchant / amount(**Decimal**) / txDate /
  type(DEBIT\|CREDIT) / categoryId / cardLast4 / **txStatus**（"未入账"/"已入账"）/
  source（bill=月账单 \| daily=日推送，fingerprint 去重）。
- `list_cards` 返回不含密码字段；卡片 imap 凭据只在 sync_card 内部使用。

### 实读发现的风险与对策

1. **`get_transactions` 硬上限 `take: 500`**：一次拉 6 个月可能被静默截断
   （月均 100+ 笔时必中）。→ subscriptions **逐月调用再拼接**（单月 500 笔
   足够），不依赖分页（上游无分页参数）。
2. **amount 经 JSON 序列化是字符串**：get_stats 内部已 `Number(tx.amount)`，
   但 get_transactions 返回原始对象，Prisma Decimal toJSON 为字符串。
   → analyze 层入口统一 `Number()` 归一 + `round(x, 2)`，并在测试中固化
   "amount 为字符串"的响应形状。
3. **`txStatus` "未入账"交易**：上游 get_stats **不过滤**未入账，Steward
   跟随同一口径（否则与 credi-insights 界面对不上），记为已知口径；
   结果中保留 cardLast4 便于用户对账。

## 布局

```
app/finance/
  __init__.py
  backend.py     # FinanceBackend：stdio 子进程客户端封装（懒加载/单例/错误转译）
  analyze.py     # 纯函数：merge_card_stats / compute_trend / detect_subscriptions
  tools.py       # register_finance_tools(mcp)：5 个工具的参数校验 + 编排
```

- `mcp_server.py` 已 437 行，拆出 `app/finance/tools.py` 以守住文件体量规则
  （mcp_server 底部一行 `register_finance_tools(mcp)` + instructions 增补）。
- 沿用模块样板精神，但 finance **不落本地 events 表**，故不放 `app/modules/`，
  独立 `app/finance/` 包，物理上表达"读上游、不写本地"。

## 关键设计

### 1. FinanceBackend 生命周期

```python
class FinanceBackend:
    def __init__(self, credi_dir: str, cmd: list[str]): ...
    async def call(self, tool: str, arguments: dict) -> object: ...
```

- 内部持有一个 fastmcp `Client(StdioTransport(cmd[0], cmd[1:], cwd=credi_dir))`，
  **懒加载**：首次 `call` 时进入上下文并缓存；进程退出随服务结束（FastMCP
  lifespan 中关闭）。避免每次调用冷启动子进程。
- 配置：`STEWARD_CREDI_DIR`（默认 `~/Projects/credi-insights`）、
  `STEWARD_CREDI_CMD`（JSON 数组，默认 `["npx", "tsx", "mcp-server.ts"]`）。
- 错误转译：fastmcp 的 ToolError / 连接异常 → 统一包装为
  `ToolError("财务数据源不可用：<原因>")`；上游 `isError` 文本同样转译。
  这是**面向龙虾的稳定错误契约**，不泄漏子进程栈。
- **测试注入点**：工具函数一律经 `get_backend()` 取用；测试 monkeypatch 该
  工厂返回 fake backend（返回预置上游响应 dict），全测试链路零子进程。

### 2. 数据编排（async 工具 + 同步纯函数）

- `spending_summary`：`list_cards` → 并发逐卡 `get_stats(card, month)` →
  `analyze.merge_card_stats()`（跨卡相加、分类降序、Top 商户取自
  `get_transactions` 全月数据）。开销可控：卡数量是个位数。
- `spending_trend`：对 months 中每个月重复 summary 的跨卡拉取（按月缓存于
  单次调用内即可，不做跨调用缓存——单机低频，简单优先）。
- `subscriptions`：一次 `get_transactions(start=months 前, end=今天)` →
  `analyze.detect_subscriptions()`。阈值（≥3 个月、±20%）定义为模块常量。
- 金额统一 `round(x, 2)`，浮点相加后归一，避免 0.30000000000000004 入结果。

### 3. 分类写通道与边界（2026-10-16 与用户确认）

诉求：龙虾要能"触发自动分类 / 给某笔归类 / 管理分类规则"。

**规则仍存 credi-insights，不挪 Steward**，理由：

- credi-insights 的 UI 与 AI 分类（`ai-classify.ts`）读的是它库里的同一张
  rules 表 —— 挪存储即产生双规则源，两边的分类行为会分叉；
- pattern 语法（`merchant contains 美团`）的解析引擎 `rule-parser.ts` 在上游，
  挪存储不挪引擎无意义，挪引擎即重造分类（踩"不重复造分类"红线）。

Steward 提供的是**通道**，白名单硬编码于 `tools.py`：

| Steward 工具 | 上游工具 | 安全设计 |
|---|---|---|
| `list_categories` / `list_rules` | 同名 | 只读 |
| `create_rule(name, pattern, category_id)` | create_rule | pattern 沿用上游语法 |
| `classify_transaction(tx_id, category_id)` | update_transaction_category | 单笔、显式 |
| `auto_classify(card_id?, dry_run?)` | apply_rules | **dry_run 缺省 true**：龙虾先拿预览，与用户确认后以 dry_run=false 执行 |
| `pending_classifications(date?)` | get_transactions + 客户端过滤 category=null | 见下"每日分类流水线" |

`create_category` 不暴露（分类本体增删属 credi-insights UI 职责，龙虾暂无此诉求）。
铁律表述从"只读不写"细化为"**分析只读 + 分类写走受控白名单**"；
"不直连 MySQL、不复制数据、不重造规则匹配/AI 分类引擎"三条不变。
不做任意工具名透传，新增白名单须改代码过评审。

### 3.1 每日分类流水线（龙虾侧编排，Steward 供工具）

用户每日收到信用卡推送邮件（龙虾设置的推送），落地后的分类节奏：

```
sync_card(card_id)                    # 同步当日推送 → 上游入库
auto_classify()                       # dry_run=true 预览 → 执行（规则能吃的自动吃掉）
pending_classifications(date?)        # 规则没命中的未分类交易，列给龙虾
  → 龙虾逐笔问用户："滴滴出行 23.5 元，归交通？"
  → 用户确认 → classify_transaction(tx_id, category_id)
  → 用户说"以后都这样" → create_rule 固化，下次 auto_classify 直接命中
```

实现要点：上游 `apply_rules` 只返回**命中**项，不返回未命中清单 →
`pending_classifications` 用 `get_transactions(start=date, end=date)` 拉全天后
**客户端过滤 category=null**（响应里未分类交易的 category 字段为 null），
纯函数 `filter_pending` 承接、升序输出。单日交易量远小于 take:500，无截断风险。
"不确定的找用户确认"这一步由龙虾（脑子）承担——Steward 只负责把待确认清单
给得干净、把归类动作给得顺手。

### 4. 测试策略（TDD）

| 层 | 文件 | 依赖 |
|---|---|---|
| 纯函数 | `tests/test_finance_analyze.py` | 无（预置上游响应形状的 dict） |
| backend | `tests/test_finance_backend.py` | fake client 注入，验证错误转译/配置解析 |
| MCP 契约 | `tests/test_mcp_contract.py` 扩展 `TestFinance` | monkeypatch `get_backend` |
| 真实链路 | `scripts/smoke_finance.py`（**可选**，不进常规测试） | 本地 credi-insights 就绪时人工跑 |

- 契约测试注入的 fake backend 按工具名返回预置数据，覆盖：正常汇总、
  上游报错 → 中文 ToolError、month/months 参数校验、订阅识别路径。

## 取舍记录

- **不用 FastMCP proxy/mount**：`as_proxy` 对上游全量工具透传（含 5 个写工具），
  违反只读边界且前缀工具名对龙虾不友好；白名单式封装更贴合"语义化复盘工具"定位。
- **不做跨调用缓存**：单机单人低频查询，本地 MySQL 秒回，缓存引入失效复杂度，
  收益趋零（insights change 若需要再议）。
- **不落本地库**：维持"不复制数据"铁律；review change 需要合并视图时，
  在调用时聚合而非复制存储。
