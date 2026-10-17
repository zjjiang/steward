"""goals 表的存取：周期型目标，同维度至多一个 active。"""

import sqlite3
from datetime import UTC, datetime

VALID_METRICS = ("distance", "frequency", "duration")
VALID_PERIODS = ("week", "month")


def _now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def _row_to_goal(row: sqlite3.Row) -> dict:
    return dict(row)


def create_goal_superseding(
    conn: sqlite3.Connection,
    *,
    kind: str = "workout",
    metric: str,
    target: float,
    period: str,
) -> dict:
    """创建目标；同 (kind, metric, period) 的 active 目标在事务内被替代。"""
    conn.execute("BEGIN")
    try:
        row = conn.execute(
            "SELECT id FROM goals WHERE kind=? AND metric=? AND period=? AND status='active'",
            (kind, metric, period),
        ).fetchone()
        old_id = row[0] if row else None
        cur = conn.execute(
            "INSERT INTO goals (kind, metric, target, period, status, created_at) "
            "VALUES (?, ?, ?, ?, 'active', ?)",
            (kind, metric, target, period, _now_iso()),
        )
        new_id = cur.lastrowid
        if old_id is not None:
            conn.execute(
                "UPDATE goals SET status='superseded', superseded_by=? WHERE id=?",
                (new_id, old_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    goal = get_goal(conn, new_id)  # type: ignore[assignment]
    goal["superseded_id"] = old_id  # 替代发生时告知调用方被替代的目标 id，无替代为 None
    return goal


def get_goal(conn: sqlite3.Connection, goal_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
    return _row_to_goal(row) if row else None


def active_goal_for(
    conn: sqlite3.Connection, *, kind: str, metric: str, period: str
) -> dict | None:
    row = conn.execute(
        "SELECT * FROM goals WHERE kind=? AND metric=? AND period=? AND status='active'",
        (kind, metric, period),
    ).fetchone()
    return _row_to_goal(row) if row else None


def list_active_goals(conn: sqlite3.Connection) -> list[dict]:
    """全部 status=active 的目标（复盘遍历用）。"""
    rows = conn.execute("SELECT * FROM goals WHERE status='active' ORDER BY id").fetchall()
    return [_row_to_goal(r) for r in rows]
