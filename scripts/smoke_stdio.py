"""stdio 冒烟：以子进程方式启动 MCP server，走"记录 → 查询 → 原话追溯"全链路。

用法：uv run python scripts/smoke_stdio.py
"""

import asyncio
import os
import tempfile
import uuid

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="steward-smoke-")
    env = {**os.environ, "STEWARD_DB": os.path.join(tmp, "smoke.db")}
    transport = StdioTransport("uv", ["run", "python", "-m", "app.mcp_server"], env=env)

    marker = f"冒烟测试 {uuid.uuid4().hex[:8]}"
    async with Client(transport) as client:
        server_info = client.server_info
        print(f"server: {server_info.name} {server_info.version}")

        logged = await client.call_tool(
            "log_event",
            {
                "type": "workout",
                "payload": {"sport": "run", "distance_km": 8},
                "raw_text": marker,
            },
        )
        event_id = logged.data["id"]
        print(f"log_event → id={event_id}")

        queried = await client.call_tool("query_events", {"type": "workout"})
        assert queried.data["total"] == 1, "应有 1 条 workout"
        assert queried.data["items"][0]["raw_text"] == marker, "原话应原样保留"
        print("query_events → total=1, 原话追溯 OK")

        # fitness 模块：记录 → 汇总 → 目标 → 进度
        await client.call_tool(
            "log_workout", {"sport": "run", "distance_km": 9, "duration_min": 45}
        )
        await client.call_tool("log_workout", {"sport": "gym", "duration_min": 60})
        summary = (await client.call_tool("query_workouts", {})).data["summary"]
        assert summary["count"] == 3, "应有 3 次运动"
        assert summary["total_distance_km"] == 17, "总距离应为 17km"
        print(f"query_workouts → count=3, distance=17km, by_sport={list(summary['by_sport'])}")

        goal = (
            await client.call_tool(
                "set_goal", {"metric": "distance", "target": 50, "period": "month"}
            )
        ).data
        progress = (await client.call_tool("goal_progress", {"goal_id": goal["id"]})).data
        assert progress["current"] == 17, "目标进度应为 17km"
        assert progress["verdict"] in ("ahead", "on_track", "behind")
        print(
            f"goal_progress → current={progress['current']}/50, "
            f"remaining={progress['remaining']}, verdict={progress['verdict']}"
        )

        # diet / body / commute 三模块
        await client.call_tool("log_meal", {"desc": "麻辣烫", "meal": "lunch", "cost": 28})
        meal_summary = (await client.call_tool("query_meals", {})).data["summary"]
        assert meal_summary["count"] == 1 and meal_summary["total_cost"] == 28
        print(f"query_meals → count={meal_summary['count']}, cost={meal_summary['total_cost']}")

        await client.call_tool("log_body", {"weight_kg": 62.5})
        body_summary = (await client.call_tool("query_body", {})).data["summary"]
        assert body_summary["series"][-1]["weight_kg"] == 62.5 and body_summary["change"] is None
        print(f"query_body → series={body_summary['series']}, change={body_summary['change']}")

        await client.call_tool("check_in", {"direction": "in"})
        await client.call_tool("check_in", {"direction": "out"})
        commute_summary = (await client.call_tool("query_commute", {})).data["summary"]
        assert commute_summary["days"] == 1 and commute_summary["in_count"] == 1
        print(f"query_commute → {commute_summary}")

        # review：月度复盘结构核对（财务段来自上游，冒烟只验结构不验数值）
        review_data = (
            await client.call_tool("get_review", {"period": "month", "ref_date": "2026-10-16"})
        ).data
        assert review_data["meta"]["start"] == "2026-10-01"
        assert review_data["fitness"]["summary"]["count"] >= 3
        assert "diet" in review_data and "finance" in review_data and "other" in review_data
        print(
            f"get_review → {review_data['meta']['period']} "
            f"{review_data['meta']['start']}..{review_data['meta']['end']}, "
            f"fitness={review_data['fitness']['summary']['count']} 次, "
            f"finance.available={review_data['finance']['available']}"
        )

        # insights：结构核对（有数据周才可能有条目，冒烟里只验调用与形状）
        insights_data = (await client.call_tool("get_insights", {"ref_date": "2026-10-16"})).data
        assert isinstance(insights_data["items"], list)
        for item in insights_data["items"]:
            assert {"area", "kind", "metric", "current", "previous", "change", "direction"} <= set(item)
        print(f"get_insights → {len(insights_data['items'])} 条: "
              f"{[i['metric'] for i in insights_data['items']]}")

    print("smoke passed ✅")


if __name__ == "__main__":
    asyncio.run(main())
