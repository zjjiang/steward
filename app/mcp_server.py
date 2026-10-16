"""Steward MCP server（stdio）——龙虾背后的生活管家。

通用生活流水工具（兜底通道，零领域校验）+ 各生活模块的专用工具。
当前模块：fitness（运动 + 目标）。新模块在 app/modules/ 下实现并在本文件注册。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from app.modules import body, commute, diet, fitness
from app.store.db import connect, init_db
from app.store.events import DEFAULT_LIST_LIMIT, insert_event, list_events
from app.store.goals import VALID_METRICS, VALID_PERIODS, create_goal_superseding, get_goal

TZ = ZoneInfo("Asia/Shanghai")

INSTRUCTIONS = """Steward —— 个人生活管家。

你（龙虾）负责把用户的自然语言解析成结构化数据，再调用这里的工具落库。
优先用各模块的专用工具；不认识的类型走通用兜底，不要拒绝用户。

【fitness 模块】
- log_workout：记录运动。sport 必填（run/swim/gym/cycle/hike/ball 等，跟随用户用词）；
  duration_min（分钟）与 distance_km（公里）至少其一；notes 可选。
- query_workouts：运动明细 + 汇总（次数/总时长/总距离/按 sport 分组）。
- set_goal：设定周期型运动目标。metric: distance(公里)/frequency(次数)/duration(分钟)；
  period: week/month；target 为数值。例："这个月目标跑 50km" →
  set_goal(metric="distance", target=50, period="month")。
- goal_progress：目标完成度（target/current/remaining + ahead/on_track/behind）。

【diet 模块】
- log_meal：记录饮食。desc 必填（吃了什么）；meal 可选（breakfast/lunch/dinner/snack）；
  cost 可选（元）。例："中午吃的麻辣烫，28 块" → log_meal(desc="麻辣烫", meal="lunch", cost=28)。
- query_meals：饮食明细 + 汇总（次数/花费合计/按餐次分组）。

【body 模块】
- log_body：记录体重。weight_kg 必填。例："今天 62.5kg" → log_body(weight_kg=62.5)。
- query_body：体重序列（升序）+ 首末差值。

【commute 模块】
- check_in：上下班打卡。direction: in（到岗）/ out（离岗）。
- query_commute：打卡统计（天数 / in、out 次数）。

【通用兜底】
- log_event：记录任意类型生活事件。type 为事件类型；payload 必须是 JSON object；
  raw_text 传用户原话，会永久保留。
- query_events：按 type 与日期窗口查询事件明细（倒序），不做汇总统计。
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


# ---------- fitness 模块 ----------


def _module_conn(conn):
    return conn


@mcp.tool
def log_workout(
    sport: str,
    duration_min: float | None = None,
    distance_km: float | None = None,
    notes: str | None = None,
    occurred_at: str | None = None,
    raw_text: str | None = None,
) -> dict:
    """记录一次运动。

    Args:
        sport: 运动类型（run/swim/gym/cycle/hike/ball 等，跟随用户用词）
        duration_min: 运动时长（分钟），与 distance_km 至少其一
        distance_km: 距离（公里），与 duration_min 至少其一
        notes: 备注（如"练胸和肩"）
        occurred_at: 发生时间（ISO 8601），缺省取当前时间
        raw_text: 用户原话，永久保留
    """
    payload: dict = {"sport": sport}
    if duration_min is not None:
        payload["duration_min"] = duration_min
    if distance_km is not None:
        payload["distance_km"] = distance_km
    if notes is not None:
        payload["notes"] = notes
    try:
        payload = fitness.validate_payload(payload)
    except ValueError as e:
        raise ToolError(str(e))
    occurred = _normalize_occurred_at(occurred_at)
    conn = get_conn()
    try:
        return insert_event(
            conn, type="workout", payload=payload, raw_text=raw_text, occurred_at=occurred
        )
    finally:
        conn.close()


@mcp.tool
def query_workouts(
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> dict:
    """查询运动明细与汇总（次数/总时长/总距离/按 sport 分组），按时间倒序。

    Args:
        date_from: 起始日期（含，YYYY-MM-DD），缺省最近 30 天
        date_to: 结束日期（含，YYYY-MM-DD）
        limit: 明细条数上限
    """
    conn = get_conn()
    try:
        result = list_events(
            conn, type="workout", date_from=date_from, date_to=date_to, limit=limit
        )
    finally:
        conn.close()
    result["summary"] = fitness.summarize(result["items"])
    return result


@mcp.tool
def set_goal(metric: str, target: float, period: str) -> dict:
    """设定周期型运动目标（同维度重复设定会自动替代旧目标）。

    Args:
        metric: distance（公里）/ frequency（次数）/ duration（分钟）
        target: 目标数值（> 0），如月跑量 50 → 50
        period: week / month
    """
    if metric not in VALID_METRICS:
        raise ToolError(f"metric 只支持 {'/'.join(VALID_METRICS)}，收到 {metric!r}")
    if period not in VALID_PERIODS:
        raise ToolError(f"period 只支持 {'/'.join(VALID_PERIODS)}，收到 {period!r}")
    if isinstance(target, bool) or not isinstance(target, (int, float)) or target <= 0:
        raise ToolError("target 必须是大于 0 的数值")
    conn = get_conn()
    try:
        return create_goal_superseding(conn, metric=metric, target=target, period=period)
    finally:
        conn.close()


@mcp.tool
def goal_progress(goal_id: int) -> dict:
    """查询目标进度：target/current/remaining、周期起止、ahead/on_track/behind 判定。

    Args:
        goal_id: set_goal 返回的目标 id
    """
    conn = get_conn()
    try:
        goal = get_goal(conn, goal_id)
        if goal is None:
            raise ToolError("目标不存在")
        if goal["status"] == "superseded":
            ref_date = _date_of(goal["created_at"])
            result = fitness.progress(goal, _workouts(conn), ref_date=ref_date)
            successor = get_goal(conn, goal["superseded_by"]) if goal["superseded_by"] else None
            result["status"] = "superseded"
            result["superseded_by"] = goal["superseded_by"]
            result["successor_active"] = bool(successor and successor["status"] == "active")
            return result
        return fitness.progress(goal, _workouts(conn))
    finally:
        conn.close()


def _date_of(iso_text: str):
    return datetime.fromisoformat(iso_text).date()


def _workouts(conn) -> list[dict]:
    # 目标周期最长一个月，全部拉回内存交给纯函数计算
    return list_events(conn, type="workout", limit=10000)["items"]


# ---------- diet 模块 ----------


@mcp.tool
def log_meal(
    desc: str,
    meal: str | None = None,
    cost: float | None = None,
    occurred_at: str | None = None,
    raw_text: str | None = None,
) -> dict:
    """记录一顿饮食。

    Args:
        desc: 吃了什么
        meal: 餐次（breakfast/lunch/dinner/snack），可选
        cost: 花费（元，> 0），可选
        occurred_at: 发生时间（ISO 8601），缺省取当前时间
        raw_text: 用户原话，永久保留
    """
    payload: dict = {"desc": desc}
    if meal is not None:
        payload["meal"] = meal
    if cost is not None:
        payload["cost"] = cost
    try:
        payload = diet.validate_payload(payload)
    except ValueError as e:
        raise ToolError(str(e))
    occurred = _normalize_occurred_at(occurred_at)
    conn = get_conn()
    try:
        return insert_event(
            conn, type="meal", payload=payload, raw_text=raw_text, occurred_at=occurred
        )
    finally:
        conn.close()


@mcp.tool
def query_meals(
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> dict:
    """查询饮食明细与汇总（次数/花费合计/按餐次分组），按时间倒序。

    Args:
        date_from: 起始日期（含，YYYY-MM-DD），缺省最近 30 天
        date_to: 结束日期（含，YYYY-MM-DD）
        limit: 明细条数上限
    """
    conn = get_conn()
    try:
        result = list_events(
            conn, type="meal", date_from=date_from, date_to=date_to, limit=limit
        )
    finally:
        conn.close()
    result["summary"] = diet.summarize(result["items"])
    return result


# ---------- body 模块 ----------


@mcp.tool
def log_body(
    weight_kg: float,
    occurred_at: str | None = None,
    raw_text: str | None = None,
) -> dict:
    """记录体重。

    Args:
        weight_kg: 体重（公斤），(0, 500]
        occurred_at: 发生时间（ISO 8601），缺省取当前时间
        raw_text: 用户原话，永久保留
    """
    try:
        payload = body.validate_payload({"weight_kg": weight_kg})
    except ValueError as e:
        raise ToolError(str(e))
    occurred = _normalize_occurred_at(occurred_at)
    conn = get_conn()
    try:
        return insert_event(
            conn, type="body", payload=payload, raw_text=raw_text, occurred_at=occurred
        )
    finally:
        conn.close()


@mcp.tool
def query_body(
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> dict:
    """查询体重序列（时间升序，同日取最后）与首末差值。

    Args:
        date_from: 起始日期（含，YYYY-MM-DD），缺省最近 30 天
        date_to: 结束日期（含，YYYY-MM-DD）
        limit: 明细条数上限
    """
    conn = get_conn()
    try:
        result = list_events(
            conn, type="body", date_from=date_from, date_to=date_to, limit=limit
        )
    finally:
        conn.close()
    result["summary"] = body.summarize(result["items"])
    return result


# ---------- commute 模块 ----------


@mcp.tool
def check_in(
    direction: str,
    occurred_at: str | None = None,
    raw_text: str | None = None,
) -> dict:
    """上下班打卡。

    Args:
        direction: in（到岗）/ out（离岗）
        occurred_at: 打卡时间（ISO 8601），缺省取当前时间
        raw_text: 用户原话，永久保留
    """
    try:
        payload = commute.validate_payload({"direction": direction})
    except ValueError as e:
        raise ToolError(str(e))
    occurred = _normalize_occurred_at(occurred_at)
    conn = get_conn()
    try:
        return insert_event(
            conn, type="commute", payload=payload, raw_text=raw_text, occurred_at=occurred
        )
    finally:
        conn.close()


@mcp.tool
def query_commute(
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> dict:
    """查询打卡明细与统计（打卡天数 / in、out 次数），按时间倒序。

    Args:
        date_from: 起始日期（含，YYYY-MM-DD），缺省最近 30 天
        date_to: 结束日期（含，YYYY-MM-DD）
        limit: 明细条数上限
    """
    conn = get_conn()
    try:
        result = list_events(
            conn, type="commute", date_from=date_from, date_to=date_to, limit=limit
        )
    finally:
        conn.close()
    result["summary"] = commute.summarize(result["items"])
    return result


if __name__ == "__main__":
    mcp.run()
