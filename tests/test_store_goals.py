"""goals 存储层测试：建表升级、CRUD、同维度替代。"""

import pytest

from app.store.db import SCHEMA_VERSION, connect, init_db
from app.store.goals import active_goal_for, create_goal_superseding, get_goal


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.db")
    init_db(c)
    yield c
    c.close()


class TestSchemaUpgrade:
    def test_version_bumped(self, conn):
        (version,) = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert version == SCHEMA_VERSION == 2

    def test_goals_table_exists(self, conn):
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "goals" in tables


class TestGoalCrud:
    def test_insert_and_get(self, conn):
        goal = create_goal_superseding(
            conn, kind="workout", metric="distance", target=50, period="month"
        )
        assert goal["status"] == "active"
        fetched = get_goal(conn, goal["id"])
        assert fetched["metric"] == "distance"
        assert fetched["target"] == 50

    def test_get_missing_returns_none(self, conn):
        assert get_goal(conn, 999) is None

    def test_same_dimension_supersedes(self, conn):
        old = create_goal_superseding(conn, metric="distance", target=50, period="month")
        new = create_goal_superseding(conn, metric="distance", target=80, period="month")
        assert get_goal(conn, old["id"])["status"] == "superseded"
        assert get_goal(conn, old["id"])["superseded_by"] == new["id"]
        assert active_goal_for(conn, kind="workout", metric="distance", period="month")["id"] == new["id"]

    def test_different_dimensions_coexist(self, conn):
        a = create_goal_superseding(conn, metric="distance", target=50, period="month")
        b = create_goal_superseding(conn, metric="frequency", target=12, period="month")
        c = create_goal_superseding(conn, metric="distance", target=10, period="week")
        for g in (a, b, c):
            assert get_goal(conn, g["id"])["status"] == "active"

    def test_superseded_chain(self, conn):
        g1 = create_goal_superseding(conn, metric="duration", target=600, period="week")
        g2 = create_goal_superseding(conn, metric="duration", target=900, period="week")
        g3 = create_goal_superseding(conn, metric="duration", target=1200, period="week")
        assert get_goal(conn, g1["id"])["superseded_by"] == g2["id"]
        assert get_goal(conn, g2["id"])["superseded_by"] == g3["id"]
        assert get_goal(conn, g3["id"])["status"] == "active"
