"""存储层测试：建库、事件写入读回、过滤查询。"""


import pytest

from app.store.db import connect, init_db
from app.store.events import insert_event, list_events


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


class TestInitDb:
    def test_creates_tables(self, conn):
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"events", "schema_version"} <= tables

    def test_schema_version_written(self, conn):
        from app.store.db import SCHEMA_VERSION

        (version,) = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert version == SCHEMA_VERSION

    def test_reinit_idempotent(self, conn):
        insert_event(conn, type="note", payload={"a": 1})
        init_db(conn)  # 不应清数据、不应报错
        (count,) = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        assert count == 1


class TestInsertEvent:
    def test_round_trip(self, conn):
        saved = insert_event(
            conn,
            type="workout",
            payload={"sport": "run", "distance_km": 8},
            raw_text="今天跑了 8km",
            occurred_at="2026-10-16T08:30:00+08:00",
        )
        assert saved["id"] > 0
        assert saved["type"] == "workout"
        assert saved["payload"] == {"sport": "run", "distance_km": 8}
        assert saved["raw_text"] == "今天跑了 8km"
        assert saved["occurred_at"] == "2026-10-16T08:30:00+08:00"
        assert saved["created_at"]  # 服务器写入

    def test_raw_text_stored_verbatim(self, conn):
        text = "今天跑了 8km，配速 5'30\"，感觉不错 🏃"
        insert_event(conn, type="workout", payload={}, raw_text=text)
        row = list_events(conn, type="workout")["items"][0]
        assert row["raw_text"] == text

    def test_raw_text_optional(self, conn):
        saved = insert_event(conn, type="note", payload={"x": 1})
        assert saved["raw_text"] is None

    def test_payload_must_survive_as_json(self, conn):
        insert_event(conn, type="t", payload={"嵌套": {"列表": [1, 2]}})
        row = list_events(conn, type="t")["items"][0]
        assert row["payload"] == {"嵌套": {"列表": [1, 2]}}

    def test_unknown_type_allowed(self, conn):
        saved = insert_event(conn, type="expense", payload={"cost": 86})
        assert saved["type"] == "expense"


class TestListEvents:
    @pytest.fixture
    def seeded(self, conn):
        insert_event(conn, type="workout", payload={}, occurred_at="2026-10-01T08:00:00+08:00")
        insert_event(conn, type="workout", payload={}, occurred_at="2026-10-15T09:00:00+08:00")
        insert_event(conn, type="meal", payload={}, occurred_at="2026-10-10T12:00:00+08:00")
        insert_event(conn, type="body", payload={}, occurred_at="2026-09-20T07:00:00+08:00")

    def test_filter_by_type(self, conn, seeded):
        result = list_events(conn, type="workout")
        assert result["total"] == 2
        assert all(e["type"] == "workout" for e in result["items"])

    def test_filter_by_window(self, conn, seeded):
        result = list_events(conn, date_from="2026-10-01", date_to="2026-10-31")
        assert result["total"] == 3  # 9月20日的 body 不在内

    def test_type_and_window_combined(self, conn, seeded):
        result = list_events(conn, type="workout", date_from="2026-10-10", date_to="2026-10-31")
        assert result["total"] == 1
        assert result["items"][0]["occurred_at"].startswith("2026-10-15")

    def test_ordered_desc(self, conn, seeded):
        items = list_events(conn)["items"]
        times = [e["occurred_at"] for e in items]
        assert times == sorted(times, reverse=True)

    def test_limit_and_truncated(self, conn, seeded):
        result = list_events(conn, limit=2)
        assert len(result["items"]) == 2
        assert result["total"] == 4
        assert result["truncated"] is True

    def test_no_truncation_when_under_limit(self, conn, seeded):
        result = list_events(conn, limit=10)
        assert result["truncated"] is False

    def test_empty_result(self, conn):
        result = list_events(conn, type="nothing")
        assert result == {"items": [], "total": 0, "truncated": False}
