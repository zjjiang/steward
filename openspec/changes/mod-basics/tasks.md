# Tasks: mod-basics

三个模块同构，按 diet → body → commute 顺序，全程 TDD。无 schema 变化。

## 1. 模块纯函数（app/modules/）

- [ ] 1.1 `diet.py`：validate_payload（desc 必填 / meal 4 值可选 / cost>0 可选）+ summarize（次数/花费合计/按餐次分组），逐 spec 场景写测试
- [ ] 1.2 `body.py`：validate_payload（weight_kg ∈ (0,500]）+ summarize（升序 series 含日期、同日取最后、首末差值 null 安全），逐 spec 场景写测试
- [ ] 1.3 `commute.py`：validate_payload（direction ∈ in/out）+ summarize（打卡天数按自然日去重 / in、out 计数），逐 spec 场景写测试

## 2. MCP 工具（app/mcp_server.py 注册 6 个）

- [ ] 2.1 `log_meal` / `query_meals`：校验失败抛 ToolError 含字段名；汇总拼装
- [ ] 2.2 `log_body` / `query_body`：series + change 拼装
- [ ] 2.3 `check_in` / `query_commute`：direction 白名单；天数/次数统计
- [ ] 2.4 instructions 增补三模块说明；契约测试扩展 6 个工具的成功/失败路径

## 3. 收尾验证

- [ ] 3.1 全量测试绿 + ruff 无告警
- [ ] 3.2 stdio 冒烟扩展：记午餐 + 记体重 + 上下班打卡 → 三模块查询汇总核对
- [ ] 3.3 提交（本地），经用户确认后 push + PR
