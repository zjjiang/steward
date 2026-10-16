# Tasks: life-log

实现顺序按依赖排列：schema → 存储层 → 领域逻辑 → MCP 工具 → 契约测试 → 验证。
全程 TDD：每层先写失败测试（RED）再实现（GREEN）。

## 1. 存储层（app/store/）

- [ ] 1.1 建库脚本与 schema（events / goals / schema_version 三表 + 索引），测试：新库建表成功、schema_version 写入
- [ ] 1.2 events 增查函数（insert_event / list_events(type, date_from, date_to)），测试：写入读回一致、按类型与时间窗口过滤、上限保护
- [ ] 1.3 goals 增查函数（insert_goal / get_goal / supersede_goal / list_active_goal），测试：同维度替代后旧目标状态为 superseded

## 2. 领域逻辑（app/domain.py，纯函数）

- [ ] 2.1 payload 校验器：workout / meal / body / commute 四类型 + 未知类型放行，逐 spec 场景写测试（缺字段、非法数值、未知 type 自由 JSON）
- [ ] 2.2 周期边界函数：week（周一起始）/ month（自然月），测试：月中设定当月生效、跨月/跨周边界
- [ ] 2.3 汇总函数：workout（次数/时长/距离/按 sport 分组）、body（升序序列+首末差）、commute（打卡天数+in/out 次数）、meal（次数+花费合计）、未知 type 仅明细
- [ ] 2.4 目标进度算法：current（distance/frequency/duration 三种算法）+ ahead/on_track/behind 判定（阈值 1.25/0.75、时间进度 <10% 强制 on_track），逐 spec 场景写测试

## 3. MCP 工具（app/mcp_server.py）

- [ ] 3.1 `log_event`：参数透传 store+domain，校验失败抛 ToolError（错误消息含非法字段名），测试经 FastMCP 内存 client 调用
- [ ] 3.2 `query_events`：明细 + 按 type 汇总拼装，缺省窗口最近 30 天，测试覆盖 workout/body 两种汇总
- [ ] 3.3 `set_goal`：同维度自动 supersede，返回新目标 id 与生效周期，测试重复设定场景
- [ ] 3.4 `goal_progress`：返回 target/current/remaining/周期起止/进度判断，测试 on_track、behind、不存在、superseded 四场景
- [ ] 3.5 服务器 instructions 写明四类型 payload 约定（与 specs 措辞一致），供龙虾侧免读代码正确构造参数

## 4. 收尾验证

- [ ] 4.1 全量测试绿（uv run pytest -q）+ ruff 无告警
- [ ] 4.2 stdio 冒烟：本机起 server，用 FastMCP client stdio 方式完成"记录跑步 → 查询汇总 → 设目标 → 查进度"全链路
- [ ] 4.3 更新 README 运行说明（启动命令、龙虾接入配置示例），提交 PR
