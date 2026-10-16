"""MCP 契约测试：经 FastMCP 内存 client 调用 log_event / query_events。

覆盖成功路径与错误消息（对齐 Deputy 的 MCP 契约测试模式）。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

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


class TestDiet:
    async def test_log_and_query(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            await call(
                client,
                "log_meal",
                {"desc": "麻辣烫", "meal": "lunch", "cost": 28, "raw_text": "中午吃的麻辣烫，28 块"},
            )
            await call(client, "log_meal", {"desc": "燕麦", "meal": "breakfast"})
            data = await call(client, "query_meals", {})
        assert data["summary"]["count"] == 2
        assert data["summary"]["total_cost"] == 28
        assert data["summary"]["by_meal"] == {"lunch": 1, "breakfast": 1}
        # 倒序：燕麦（后记）在前，麻辣烫（先记、带原话）在后
        assert data["items"][1]["raw_text"] == "中午吃的麻辣烫，28 块"

    async def test_missing_desc_rejected(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="desc"):
                await call(client, "log_meal", {"cost": 28})

    async def test_invalid_meal_rejected(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="meal"):
                await call(client, "log_meal", {"desc": "夜宵", "meal": "brunch"})


class TestBody:
    async def test_log_and_query_series(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            await call(
                client,
                "log_body",
                {"weight_kg": 62.5, "occurred_at": "2026-10-10T07:00:00", "raw_text": "今天 62.5kg"},
            )
            await call(client, "log_body", {"weight_kg": 61.8, "occurred_at": "2026-10-16T07:00:00"})
            data = await call(client, "query_body", {})
        assert data["total"] == 2
        assert data["summary"]["series"][-1] == {"date": "2026-10-16", "weight_kg": 61.8}
        assert data["summary"]["change"] == pytest.approx(-0.7)
        assert data["items"][1]["raw_text"] == "今天 62.5kg"

    async def test_invalid_weight_rejected(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="weight_kg"):
                await call(client, "log_body", {"weight_kg": 800})


class TestCommute:
    async def test_check_in_and_query(self, isolated_db):
        from fastmcp import Client

        async with Client(mcp) as client:
            await call(client, "check_in", {"direction": "in"})
            await call(client, "check_in", {"direction": "out"})
            data = await call(client, "query_commute", {})
        assert data["summary"]["days"] == 1
        assert data["summary"]["in_count"] == 1
        assert data["summary"]["out_count"] == 1

    async def test_invalid_direction_rejected(self, isolated_db):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="direction"):
                await call(client, "check_in", {"direction": "home"})


# ---------- finance 模块（fake backend 注入，零子进程） ----------


def _recent_months(n):
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    out = []
    for i in range(n):
        total = now.year * 12 + now.month - 1 - i
        out.append(f"{total // 12:04d}-{total % 12 + 1:02d}")
    return sorted(out)


def _fin_tx(id, merchant, amount, date, time=None, type="DEBIT", card="0094", category_id=None):
    return {
        "id": id, "txDate": date, "txTime": time, "merchant": merchant,
        "amount": amount, "type": type, "cardLast4": card,
        "categoryId": category_id,
        "category": {"name": "餐饮", "icon": "🍜"} if category_id else None,
    }


def _fin_stats(card_id, debit, count=1):
    return {
        "period": "", "cardId": card_id, "totalDebit": debit, "totalCredit": 0,
        "netSpending": debit, "transactionCount": count, "categoryBreakdown": [],
    }


class FakeFinanceBackend:
    def __init__(self):
        self.responses = {}
        self.calls = []

    async def call(self, tool, arguments=None):
        self.calls.append((tool, arguments))
        response = self.responses.get(tool)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return response(arguments or {})
        return response


@pytest.fixture
def finance_backend(monkeypatch):
    fake = FakeFinanceBackend()
    monkeypatch.setattr("app.finance.tools.get_backend", lambda: fake)
    return fake


class TestFinanceSummary:
    async def test_cross_card_merge(self, isolated_db, finance_backend):
        finance_backend.responses = {
            "list_cards": [{"id": "c1", "bank": "CMB"}, {"id": "c2", "bank": "SPDB"}],
            "get_stats": lambda a: _fin_stats(a["cardId"], 100 if a["cardId"] == "c1" else 80.5),
            "get_transactions": [
                _fin_tx("t1", "美团", "28.00", "2026-10-05T00:00:00.000Z"),
                _fin_tx("t2", "滴滴出行", "23.50", "2026-10-06T00:00:00.000Z"),
            ],
        }
        from fastmcp import Client

        async with Client(mcp) as client:
            data = await call(client, "spending_summary", {"month": "2026-10"})
        assert data["month"] == "2026-10"
        assert data["total_debit"] == 180.5
        assert data["transaction_count"] == 2
        assert data["top_merchants"][0] == {"merchant": "美团", "amount": 28.0}

    async def test_bad_month_rejected(self, isolated_db, finance_backend):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="month"):
                await call(client, "spending_summary", {"month": "十月"})
            with pytest.raises(ToolError, match="month"):
                await call(client, "spending_summary", {"month": "2026-13"})

    async def test_upstream_down_translated(self, isolated_db, finance_backend):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        # 真实链路中 backend 已把上游故障转译为本消息（见 test_finance_backend.py）
        finance_backend.responses = {
            "list_cards": ToolError("财务数据源不可用：Error: connection refused"),
        }
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="财务数据源不可用"):
                await call(client, "spending_summary", {})


class TestFinanceTrend:
    async def test_two_months_with_change(self, isolated_db, finance_backend):
        months = _recent_months(2)
        debit_map = {months[0]: 80.0, months[1]: 120.0}
        finance_backend.responses = {
            "list_cards": [{"id": "c1"}],
            "get_stats": lambda a: _fin_stats("c1", debit_map[a["period"]]),
            "get_transactions": [],
        }
        from fastmcp import Client

        async with Client(mcp) as client:
            data = await call(client, "spending_trend", {"months": 2})
        items = data["items"]
        assert [m["month"] for m in items] == months
        assert items[0]["total_debit"] == 80.0 and items[0]["change_vs_prev"] is None
        assert items[1]["total_debit"] == 120.0 and items[1]["change_vs_prev"] == 40.0

    async def test_bad_months_rejected(self, isolated_db, finance_backend):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="months"):
                await call(client, "spending_trend", {"months": 0})
            with pytest.raises(ToolError, match="months"):
                await call(client, "subscriptions", {"months": 13})


class TestFinanceSubscriptions:
    async def test_subscription_detected(self, isolated_db, finance_backend):
        months = _recent_months(3)
        by_start = {
            f"{m}-01": [_fin_tx(f"t{i}", "爱奇艺", "25.00", f"{m}-10T00:00:00.000Z")]
            for i, m in enumerate(months)
        }
        finance_backend.responses = {"get_transactions": lambda a: by_start[a["startDate"]]}
        from fastmcp import Client

        async with Client(mcp) as client:
            data = await call(client, "subscriptions", {"months": 3})
        subs = data["subscriptions"]
        assert len(subs) == 1
        assert subs[0]["merchant"] == "爱奇艺"
        assert subs[0]["monthly_avg"] == 25.0
        assert subs[0]["months_count"] == 3


class TestFinanceClassification:
    async def test_auto_classify_defaults_to_dry_run(self, isolated_db, finance_backend):
        finance_backend.responses = {"apply_rules": {"dryRun": True, "matchedCount": 0, "matches": []}}
        from fastmcp import Client

        async with Client(mcp) as client:
            await call(client, "auto_classify", {})
        assert finance_backend.calls[-1] == ("apply_rules", {"dryRun": True})

    async def test_auto_classify_execute(self, isolated_db, finance_backend):
        finance_backend.responses = {"apply_rules": {"dryRun": False, "matchedCount": 2, "matches": []}}
        from fastmcp import Client

        async with Client(mcp) as client:
            await call(client, "auto_classify", {"card_id": "c1", "dry_run": False})
        assert finance_backend.calls[-1] == ("apply_rules", {"cardId": "c1", "dryRun": False})

    async def test_pending_classifications(self, isolated_db, finance_backend):
        finance_backend.responses = {
            "get_transactions": [
                _fin_tx("t1", "已分类", "28.00", "2026-10-16T00:00:00.000Z", "12:30:00", category_id="cat1"),
                _fin_tx("t2", "滴滴出行", "23.50", "2026-10-16T00:00:00.000Z", "08:10:00"),
                _fin_tx("t3", "美团", "28.00", "2026-10-16T00:00:00.000Z", "19:05:00"),
            ],
        }
        from fastmcp import Client

        async with Client(mcp) as client:
            data = await call(client, "pending_classifications", {"date": "2026-10-16"})
        assert data["date"] == "2026-10-16"
        assert data["count"] == 2
        assert [i["tx_id"] for i in data["items"]] == ["t2", "t3"]
        assert finance_backend.calls[-1] == (
            "get_transactions", {"startDate": "2026-10-16", "endDate": "2026-10-16"},
        )

    async def test_pending_bad_date_rejected(self, isolated_db, finance_backend):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="date"):
                await call(client, "pending_classifications", {"date": "10月16日"})

    async def test_create_rule_passthrough(self, isolated_db, finance_backend):
        finance_backend.responses = {"create_rule": {"id": "r1", "name": "美团→餐饮"}}
        from fastmcp import Client

        async with Client(mcp) as client:
            data = await call(
                client, "create_rule",
                {"name": "美团→餐饮", "pattern": "merchant contains 美团", "category_id": "cat1"},
            )
        assert data["id"] == "r1"
        assert finance_backend.calls[-1] == (
            "create_rule", {"name": "美团→餐饮", "pattern": "merchant contains 美团", "categoryId": "cat1"},
        )

    async def test_create_rule_missing_fields(self, isolated_db, finance_backend):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="pattern"):
                await call(client, "create_rule", {"name": "x", "category_id": "cat1"})

    async def test_classify_transaction_passthrough(self, isolated_db, finance_backend):
        finance_backend.responses = {
            "update_transaction_category": {"id": "t1", "categoryId": "cat1"},
        }
        from fastmcp import Client

        async with Client(mcp) as client:
            await call(client, "classify_transaction", {"tx_id": "t1", "category_id": "cat1"})
        assert finance_backend.calls[-1] == (
            "update_transaction_category", {"txId": "t1", "categoryId": "cat1"},
        )

    async def test_sync_card_empty_rejected(self, isolated_db, finance_backend):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="card_id"):
                await call(client, "sync_card", {"card_id": " "})

    async def test_whitelist_no_create_category(self, isolated_db, finance_backend):
        from fastmcp import Client

        async with Client(mcp) as client:
            names = {t.name for t in await client.list_tools()}
        assert "create_category" not in names
        assert {
            "spending_summary", "spending_trend", "subscriptions", "list_cards",
            "sync_card", "list_categories", "list_rules", "create_rule",
            "classify_transaction", "auto_classify", "pending_classifications",
        } <= names

