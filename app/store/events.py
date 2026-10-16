"""events 表的存取。薄封装，返回 dict，不做领域校验（各模块的事）。"""

import json
import sqlite3
from datetime import UTC, datetime

DEFAULT_LIST_LIMIT = 200


def _now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


def insert_event(
    conn: sqlite3.Connection,
    *,
    type: str,
    payload: dict,
    raw_text: str | None = None,
    occurred_at: str | None = None,
) -> dict:
    """写入一条事件，返回含 id 与 created_at 的完整存档。"""
    if occurred_at is None:
        occurred_at = _now_iso()
    created_at = _now_iso()
    cur = conn.execute(
        "INSERT INTO events (type, occurred_at, raw_text, payload, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (type, occurred_at, raw_text, json.dumps(payload, ensure_ascii=False), created_at),
    )
    conn.commit()
    return {
        "id": cur.lastrowid,
        "type": type,
        "occurred_at": occurred_at,
        "raw_text": raw_text,
        "payload": payload,
        "created_at": created_at,
    }


def list_events(
    conn: sqlite3.Connection,
    *,
    type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> dict:
    """按类型与日期窗口（occurred_at 的本地日期前缀）过滤，倒序返回明细。

    返回 {items, total, truncated}：total 为窗口内全部条数，
    truncated 表示 items 是否因 limit 被截断。
    """
    where, params = [], []
    if type is not None:
        where.append("type = ?")
        params.append(type)
    if date_from is not None:
        where.append("substr(occurred_at, 1, 10) >= ?")
        params.append(date_from)
    if date_to is not None:
        where.append("substr(occurred_at, 1, 10) <= ?")
        params.append(date_to)
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    (total,) = conn.execute(f"SELECT COUNT(*) FROM events {clause}", params).fetchone()
    rows = conn.execute(
        f"SELECT * FROM events {clause} ORDER BY occurred_at DESC, id DESC LIMIT ?",
        [*params, limit],
    ).fetchall()
    items = [
        {
            "id": row["id"],
            "type": row["type"],
            "occurred_at": row["occurred_at"],
            "raw_text": row["raw_text"],
            "payload": json.loads(row["payload"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"items": items, "total": total, "truncated": total > len(items)}
