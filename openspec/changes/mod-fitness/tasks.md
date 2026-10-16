# Tasks: mod-fitness

依赖顺序：goals 存储 → fitness 模块纯函数 → MCP 工具 → 收尾。全程 TDD。

## 1. 存储层（app/store/goals.py + schema 升级）

- [ ] 1.1 schema_version 升 2 + goals 建表（幂等升级：旧库重开自动补表），测试旧库升级与新库首建
- [ ] 1.2 insert_goal / get_goal / active_goal_for / supersede（同维度替代在事务内置 superseded + superseded_by），测试替代链与 active 唯一性

## 2. fitness 模块（app/modules/fitness.py，纯函数）

- [ ] 2.1 validate_payload：sport 必填；duration_min/distance_km 至少其一且 > 0；notes 可选；逐 spec 场景写测试
- [ ] 2.2 summarize：总次数/总时长/总距离/按 sport 分组；空列表返回零值汇总
- [ ] 2.3 current_period("week"/"month")：周一起始自然周、自然月，Asia/Shanghai；测试跨周/跨月边界与月中情形
- [ ] 2.4 progress(goal, events)：三种 metric 的 current 计算 + ahead/on_track/behind 判定（阈值 1.25/0.75、时间进度 <10% 强制 on_track），逐 spec 场景写测试

## 3. MCP 工具（app/mcp_server.py 注册）

- [ ] 3.1 `log_workout`：校验失败抛 ToolError（消息含字段名），成功走 insert_event(type="workout")
- [ ] 3.2 `query_workouts`：明细 + summarize 拼装，缺省最近 30 天
- [ ] 3.3 `set_goal`：metric/period 白名单校验，同维度自动 supersede
- [ ] 3.4 `goal_progress`：active/superseded/不存在三分支
- [ ] 3.5 契约测试扩展：4 个工具经内存 client 的成功与失败路径；instructions 增补运动模块说明

## 4. 收尾验证

- [ ] 4.1 全量测试绿 + ruff 无告警
- [ ] 4.2 stdio 冒烟扩展：记录两次跑步 + 一次健身 → query_workouts 汇总核对 → 设月跑量目标 → goal_progress 判定
- [ ] 4.3 提交（本地），经用户确认后 push + PR
