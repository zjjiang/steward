"""MCP 契约测试：经 FastMCP 内存 client 调用 log_event / query_events。

覆盖成功路径与错误消息（对齐 Deputy 的 MCP 契约测试模式）。
"""

import pytest

from app.mcp_server import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STEWARD_DB", str(tmp_path / "contract.db"))


async def call(client, name, arguments=None):
    result = await client.call_tool(name, arguments or {})
    return result.data


class TestLogEvent:
    async def test_log_success_returns_archive(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            data = await call(
                client,
                "log_event",
                {
                    "type": "workout",
                    "payload": {"sport": "run", "distance_km": 8},
                    "raw_text": "今天跑了 8km",
                },
            )
        assert data["id"] > 0
        assert data["payload"]["distance_km"] == 8
        assert data["raw_text"] == "今天跑了 8km"
        assert data["occurred_at"]  # 缺省取当前时间

    async def test_empty_type_rejected_with_field_name(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="type"):
                await call(client, "log_event", {"type": "  ", "payload": {}})

    async def test_payload_not_object_rejected(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="payload"):
                await call(client, "log_event", {"type": "note", "payload": [1, 2]})

    async def test_bad_occurred_at_rejected_with_field_name(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="occurred_at"):
                await call(
                    client,
                    "log_event",
                    {"type": "note", "payload": {}, "occurred_at": "不是时间"},
                )


class TestQueryEvents:
    async def test_query_round_trip(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            await call(
                client,
                "log_event",
                {"type": "workout", "payload": {"sport": "run"}, "raw_text": "跑了 8km"},
            )
            data = await call(client, "query_events", {"type": "workout"})
        assert data["total"] == 1
        assert data["truncated"] is False
        assert data["items"][0]["raw_text"] == "跑了 8km"

    async def test_default_window_and_ordering(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            await call(client, "log_event", {"type": "a", "payload": {}})
            await call(client, "log_event", {"type": "b", "payload": {}})
            data = await call(client, "query_events", {})
        assert data["total"] == 2
        # 倒序：后写入的在前
        assert data["items"][0]["type"] == "b"


class TestInstructions:
    async def test_server_declares_conventions(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            instructions = client.instructions
        assert instructions and "log_event" in instructions


class TestLogWorkout:
    async def test_log_success(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            data = await call(
                client,
                "log_workout",
                {"sport": "run", "distance_km": 8, "raw_text": "今天跑了 8km"},
            )
        assert data["type"] == "workout"
        assert data["payload"]["distance_km"] == 8

    async def test_no_quantitative_field_rejected(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="duration_min"):
                await call(client, "log_workout", {"sport": "run"})

    async def test_negative_rejected(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="distance_km"):
                await call(client, "log_workout", {"sport": "run", "distance_km": -3})


class TestQueryWorkouts:
    async def test_summary_aggregation(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            await call(client, "log_workout", {"sport": "run", "distance_km": 8, "duration_min": 40})
            await call(client, "log_workout", {"sport": "run", "distance_km": 9, "duration_min": 45})
            await call(client, "log_workout", {"sport": "gym", "duration_min": 60})
            data = await call(client, "query_workouts", {})
        assert data["summary"]["count"] == 3
        assert data["summary"]["total_distance_km"] == 17
        assert data["summary"]["total_duration_min"] == 145
        assert data["summary"]["by_sport"]["run"]["count"] == 2

    async def test_excludes_other_types(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            await call(client, "log_event", {"type": "meal", "payload": {"desc": "麻辣烫"}})
            await call(client, "log_workout", {"sport": "run", "distance_km": 5})
            data = await call(client, "query_workouts", {})
        assert data["total"] == 1


class TestGoals:
    async def test_set_goal_success(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            data = await call(
                client, "set_goal", {"metric": "distance", "target": 50, "period": "month"}
            )
        assert data["status"] == "active"
        assert data["kind"] == "workout"

    async def test_same_dimension_supersedes(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            old = await call(
                client, "set_goal", {"metric": "distance", "target": 50, "period": "month"}
            )
            new = await call(
                client, "set_goal", {"metric": "distance", "target": 80, "period": "month"}
            )
        assert new["status"] == "active"
        assert new["superseded_id"] == old["id"]

    async def test_invalid_metric_rejected(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="metric"):
                await call(client, "set_goal", {"metric": "calories", "target": 100, "period": "month"})

    async def test_goal_progress_on_track(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            goal = await call(
                client, "set_goal", {"metric": "distance", "target": 50, "period": "month"}
            )
            await call(client, "log_workout", {"sport": "run", "distance_km": 25})
            data = await call(client, "goal_progress", {"goal_id": goal["id"]})
        assert data["current"] == 25
        assert data["verdict"] in ("on_track", "ahead")  # 视当天日期而定，月初强制 on_track

    async def test_goal_progress_missing(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="目标不存在"):
                await call(client, "goal_progress", {"goal_id": 999})

    async def test_goal_progress_superseded_annotated(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            old = await call(
                client, "set_goal", {"metric": "distance", "target": 50, "period": "month"}
            )
            new = await call(
                client, "set_goal", {"metric": "distance", "target": 80, "period": "month"}
            )
            data = await call(client, "goal_progress", {"goal_id": old["id"]})
        assert data["status"] == "superseded"
        assert data["superseded_by"] == new["id"]

