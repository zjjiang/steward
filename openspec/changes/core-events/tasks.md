# Tasks: core-events

实现顺序按依赖排列，全程 TDD：每层先写失败测试（RED）再实现（GREEN）。

## 1. 存储层（app/store/）

- [x] 1.1 建库脚本与 schema（events / schema_version + 索引），测试：新库建表成功、schema_version 写入、重复初始化幂等
- [x] 1.2 insert_event：写入并返回含 id 的完整存档 dict，测试字段round-trip、缺省 occurred_at 取当前
- [x] 1.3 list_events(type?, date_from?, date_to?, limit)：按类型与时间窗口过滤、倒序、上限保护，测试各过滤组合与截断标注

## 2. MCP 工具（app/mcp_server.py）

- [x] 2.1 `log_event`：结构校验（type 非空 / payload 是 object / occurred_at 可解析），失败抛 ToolError 且消息含字段名，测试经 FastMCP 内存 client 调用成功与失败路径
- [x] 2.2 `query_events`：参数透传 store，缺省最近 30 天，返回明细 + total + truncated 标注，测试缺省窗口与过滤
- [x] 2.3 服务器 instructions：说明本层为通用兜底、各模块专用工具后续提供、payload 需为 JSON object

## 3. 收尾验证

- [x] 3.1 全量测试绿（uv run pytest -q）+ ruff 无告警
- [x] 3.2 stdio 冒烟：起 server，用 FastMCP client stdio 完成"记录 → 查询 → 原话追溯"全链路
- [ ] 3.3 更新 README 运行说明（启动命令、龙虾接入配置示例），提交 PR
