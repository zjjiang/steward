"""web 只读仪表盘路由测试：TestClient 直打 HTTP 端点。

数据约定与 MCP 契约测试一致（STEWARD_DB 指向 tmp 库）；finance 用 fake
backend，patch 点为 app.web.routes.get_backend 与 app.mcp_server.get_backend。
"""

import pytest
from fastmcp.exceptions import ToolError

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("STEWARD_DB", str(tmp_path / "web.db"))


@pytest.fixture
def client(isolated_db):
    from app.web.server import app

    return TestClientWithNoLifespan(app)


class TestClientWithNoLifespan:
    """不触发 lifespan 的 TestClient（真实 backend 子进程不在测试里拉起）。"""

    def __init__(self, app):
        from fastapi.testclient import TestClient

        self._tc = TestClient(app)

    def get(self, path):
        return self._tc.get(path)


@pytest.fixture
def no_finance(monkeypatch):
    """review/insights 的 finance 段降级：上游不可用。"""

    def _raise():
        raise ToolError("财务数据源不可用：连接超时")

    monkeypatch.setattr("app.mcp_server.get_backend", _raise)


def seed(conn, type_, payload, occurred_at):
    from app.store.events import insert_event

    return insert_event(conn, type=type_, payload=payload, occurred_at=occurred_at)


@pytest.fixture
def seeded_db(isolated_db):
    from app.store.db import connect, init_db

    conn = connect()
    init_db(conn)
    seed(
        conn,
        "workout",
        {"sport": "run", "distance_km": 8, "duration_min": 40},
        "2026-10-17T08:00:00+08:00",
    )
    seed(conn, "meal", {"desc": "麻辣烫", "meal": "lunch", "cost": 28}, "2026-10-17T12:00:00+08:00")
    seed(conn, "workout", {"sport": "gym"}, "2026-10-16T19:00:00+08:00")
    yield conn
    conn.close()


# ---------- 首页 ----------


class TestHome:
    def test_home_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "仪表盘" in resp.text


# ---------- 单日流水 ----------


class TestDay:
    def test_empty_db_returns_zeroes(self, client):
        resp = client.get("/api/day?date=2026-10-17")
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == "2026-10-17"
        for key in ("workouts", "meals", "body", "commute"):
            assert data[key]["items"] == []
        assert data["workouts"]["summary"]["count"] == 0

    def test_day_with_events(self, seeded_db, client):
        resp = client.get("/api/day?date=2026-10-17")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["workouts"]["items"]) == 1
        assert data["workouts"]["summary"]["count"] == 1
        assert data["workouts"]["summary"]["total_distance_km"] == 8
        assert data["meals"]["summary"]["count"] == 1
        assert data["meals"]["summary"]["total_cost"] == 28
        # 其他日期的 workout 不串
        assert data["body"]["items"] == []

    def test_bad_date_rejected(self, client):
        resp = client.get("/api/day?date=2026/10/17")
        assert resp.status_code == 400
        assert "date" in resp.json()["detail"]


# ---------- 周期复盘 / 洞察 ----------


class TestReview:
    def test_month_passthrough(self, seeded_db, client, no_finance):
        resp = client.get("/api/review?period=month&ref_date=2026-10-31")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["period"] == "month"
        assert data["meta"]["start"] == "2026-10-01"
        assert data["meta"]["end"] == "2026-10-31"
        assert data["finance"]["available"] is False

    def test_default_period_is_week(self, isolated_db, client, no_finance):
        resp = client.get("/api/review")
        assert resp.status_code == 200
        assert resp.json()["meta"]["period"] == "week"

    def test_bad_period_rejected(self, client):
        resp = client.get("/api/review?period=year")
        assert resp.status_code == 400
        assert "period" in resp.json()["detail"]


class TestInsights:
    def test_insights_ok(self, seeded_db, client, no_finance):
        resp = client.get("/api/insights?ref_date=2026-10-17")
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_bad_ref_date_rejected(self, client):
        resp = client.get("/api/insights?ref_date=不是日期")
        assert resp.status_code == 400
        assert "ref_date" in resp.json()["detail"]


# ---------- 月度账单概况 ----------


def _tx(day, merchant, amount, category=None):
    return {
        "id": f"tx-{day}-{merchant}",
        "date": day,
        "merchant": merchant,
        "amount": amount,
        "type": "DEBIT",
        "category": category or "未分类",
    }


class TestFinance:
    @pytest.fixture
    def fake_backend(self, monkeypatch):
        class FakeFinanceBackend:
            async def call(self, tool, arguments=None):
                if tool == "get_transactions":
                    if arguments.get("month") == "2026-10":
                        return [
                            _tx("2026-10-05", "美团", 35.5, "餐饮"),
                            _tx("2026-10-12", "地铁", 4.0),
                        ]
                    return []
                raise AssertionError(f"未预期的工具调用 {tool}")

        backend = FakeFinanceBackend()
        monkeypatch.setattr("app.web.routes.get_backend", lambda: backend)
        return backend

    def test_unavailable_degrades_to_200(self, isolated_db, client, monkeypatch):
        def _raise():
            raise ToolError("财务数据源不可用：spawn 失败")

        monkeypatch.setattr("app.web.routes.get_backend", _raise)
        resp = client.get("/api/finance?month=2026-10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert "财务数据源不可用" in data["error"]

    def test_overview_with_data(self, isolated_db, client, fake_backend):
        resp = client.get("/api/finance?month=2026-10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["month"] == "2026-10"
        assert data["summary"]["total_debit"] == 39.5
        assert data["summary"]["by_category"][0] == {"name": "餐饮", "amount": 35.5}
        assert len(data["trend"]) == 6
        assert data["trend"][-1]["month"] == "2026-10"
        assert data["trend"][-1]["total_debit"] == 39.5
        assert data["subscriptions"] == []
        pending = data["pending"]
        assert pending["count"] == 1
        assert pending["items"][0]["merchant"] == "地铁"

    def test_bad_month_rejected(self, isolated_db, client):
        resp = client.get("/api/finance?month=2026-13")
        assert resp.status_code == 400
        assert "month" in resp.json()["detail"]


# ---------- 卡级别与账单周期（add-card-bill-cycle） ----------


class TestFinanceCardScoped:
    @pytest.fixture
    def fake_backend(self, monkeypatch):
        class FakeFinanceBackend:
            async def call(self, tool, arguments=None):
                if tool == "list_cards":
                    return [
                        {"id": "card_a", "bank": "CMB", "cardLast4": "0094", "alias": "主卡",
                         "isActive": True, "billingDay": 5, "dueDay": 23},
                        {"id": "card_b", "bank": "SPDB", "cardLast4": "7788", "alias": None,
                         "isActive": True, "billingDay": 15, "dueDay": 3},
                    ]
                if tool == "get_transactions":
                    assert arguments.get("cardId"), "web 层按卡查询必须带 cardId"
                    if arguments["month"] == "2026-10" and arguments["cardId"] == "card_a":
                        return [_tx("2026-10-06", "美团", 28.0, "餐饮")]
                    return []
                raise AssertionError(f"未预期的工具调用 {tool}")

        backend = FakeFinanceBackend()
        monkeypatch.setattr("app.web.routes.get_backend", lambda: backend)
        monkeypatch.setattr("app.web.routes._today", lambda: __import__("datetime").date(2026, 10, 18))
        return backend

    def test_finance_by_card(self, isolated_db, client, fake_backend):
        resp = client.get("/api/finance?month=2026-10&card=card_a")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["summary"]["total_debit"] == 28.0

    def test_bills_per_card(self, isolated_db, client, fake_backend):
        resp = client.get("/api/bills")
        assert resp.status_code == 200
        bills = resp.json()["bills"]
        assert len(bills) == 2
        by_card = {b["card"]["id"]: b for b in bills}
        a = by_card["card_a"]
        assert a["cycle"] == "2026-10"  # 今天 10-18 ≥ 出账日 10-05
        assert (a["start"], a["end"]) == ("2026-10-05", "2026-11-04")
        assert a["total_debit"] == 28.0
        assert a["due_day"] == 23
        assert "error" not in a

    def test_bill_single_card_failure_degrades(self, isolated_db, client, monkeypatch):
        # card_b 缺 billingDay：该卡条目带 error，不影响 card_a
        class PartialBackend:
            async def call(self, tool, arguments=None):
                if tool == "list_cards":
                    return [
                        {"id": "card_a", "bank": "CMB", "cardLast4": "0094", "alias": "主卡",
                         "isActive": True, "billingDay": 5, "dueDay": 23},
                        {"id": "card_b", "bank": "SPDB", "cardLast4": "7788", "alias": None,
                         "isActive": True, "dueDay": 3},
                    ]
                if tool == "get_transactions":
                    if arguments["month"] == "2026-10" and arguments["cardId"] == "card_a":
                        return [_tx("2026-10-06", "美团", 28.0, "餐饮")]
                    return []
                raise AssertionError(f"未预期的工具调用 {tool}")

        monkeypatch.setattr("app.web.routes.get_backend", lambda: PartialBackend())
        monkeypatch.setattr(
            "app.web.routes._today", lambda: __import__("datetime").date(2026, 10, 18)
        )
        resp = client.get("/api/bills")
        assert resp.status_code == 200
        bills = resp.json()["bills"]
        assert len(bills) == 2
        ok = [b for b in bills if "error" not in b]
        bad = [b for b in bills if "error" in b]
        assert len(ok) == 1 and ok[0]["card"]["id"] == "card_a"
        assert len(bad) == 1 and "账单日" in bad[0]["error"]


class FakeBackendBase:
    async def call(self, tool, arguments=None):
        raise NotImplementedError
