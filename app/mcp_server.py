"""Steward MCP server（stdio）——龙虾背后的生活管家。

本层只提供通用生活流水工具（兜底通道，零领域校验）；
各生活模块（fitness/diet/body/commute）的专用工具在后续 change 中加入。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from app.store.db import connect, init_db
from app.store.events import DEFAULT_LIST_LIMIT, insert_event, list_events

TZ = ZoneInfo("Asia/Shanghai")

INSTRUCTIONS = """Steward —— 个人生活管家（通用生活流水层）。

你（龙虾）负责把用户的自然语言解析成结构化数据，再调用这里的工具落库：
- log_event：记录一条生活事件。type 为事件类型（如 workout/meal/body/commute，
  或任意自定义类型）；payload 必须是 JSON object，字段由该类型的约定决定；
  raw_text 传用户原话，会永久保留。
- query_events：按 type 与日期窗口查询事件明细（倒序），不做汇总统计。

本层是通用兜底：不认识的 type 也允许记录，不要因为类型不熟悉而拒绝用户。
各生活模块的专用工具（log_workout/query_workouts 等）由后续版本提供。
"""


def _normalize_occurred_at(value: str | None) -> str:
    """校验并规范化时间：缺省取当前；naive 视为本地时区。返回 ISO 字符串。"""
    if value is None or not value.strip():
        return datetime.now(TZ).isoformat(timespec="seconds")
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        raise ToolError("occurred_at 不是合法时间（例：2026-10-16T08:30:00 或 2026-10-16）")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.isoformat(timespec="seconds")


def _validate_log_args(type: str, payload: object) -> None:
    if not isinstance(type, str) or not type.strip():
        raise ToolError("type 不能为空：请提供事件类型（如 workout/meal/body/commute）")
    if not isinstance(payload, dict):
        raise ToolError("payload 必须是 JSON object（键值对），不能是数组或标量")


def get_conn():
    conn = connect()
    init_db(conn)
    return conn


mcp = FastMCP("steward", instructions=INSTRUCTIONS)


@mcp.tool
def log_event(
    type: str,
    payload: dict,
    occurred_at: str | None = None,
    raw_text: str | None = None,
) -> dict:
    """记录一条生活事件。

    Args:
        type: 事件类型（workout/meal/body/commute/…任意自定义）
        payload: 结构化数据，JSON object
        occurred_at: 事件发生时间（ISO 8601），缺省取当前时间
        raw_text: 用户原话，永久保留
    """
    _validate_log_args(type, payload)
    occurred = _normalize_occurred_at(occurred_at)
    conn = get_conn()
    try:
        return insert_event(
            conn,
            type=type.strip(),
            payload=payload,
            raw_text=raw_text,
            occurred_at=occurred,
        )
    finally:
        conn.close()


@mcp.tool
def query_events(
    type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> dict:
    """查询生活事件明细（按时间倒序），返回 {items, total, truncated}。

    Args:
        type: 按类型过滤（缺省不过滤）
        date_from: 起始日期（含，YYYY-MM-DD）
        date_to: 结束日期（含，YYYY-MM-DD）
        limit: 返回条数上限
    """
    conn = get_conn()
    try:
        return list_events(
            conn, type=type, date_from=date_from, date_to=date_to, limit=limit
        )
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
