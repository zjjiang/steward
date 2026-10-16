# Steward · 个人生活管家

> 我的个人生活管家。与 [Deputy](https://github.com/zjjiang/deputy)（事业助手）相对应，
> Steward 负责我的**个人生活**。

架构：龙虾（OpenClaw）负责听懂自然语言，Steward 负责记住和算清。
模块划分、财务接入、路线图见 [docs/架构方案.md](docs/架构方案.md)，
产品需求见 [docs/PRD-第一阶段.md](docs/PRD-第一阶段.md)。

## 跑起来

```bash
uv sync                                        # 装依赖
uv run pytest -q                               # 测试
uv run python -m app.mcp_server                # 启动 MCP server（stdio）
uv run python scripts/smoke_stdio.py           # stdio 全链路冒烟
```

数据库默认落在 `data/steward.db`（已 gitignore，数据不出墙），
可用 `STEWARD_DB` 环境变量覆盖路径。

## 龙虾（OpenClaw）接入

stdio 方式接入（与 deputy 同构，龙虾与 steward 同机）：

```json
{
  "mcpServers": {
    "steward": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/steward", "python", "-m", "app.mcp_server"]
    }
  }
}
```

当前工具（core-events）：`log_event`（通用事件记录）· `query_events`（明细查询）。
生活模块工具（log_workout / log_meal / …）按路线图逐个模块交付。
