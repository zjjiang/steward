"""fitness 模块：workout 类型校验、汇总、周期与目标进度（纯函数）。

这是生活模块的接入样板：新模块 = 本目录下一个同构文件（validate_payload +
summarize 等）+ mcp_server 注册工具。领域逻辑全部在此，保持可独立单测。
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")

# 进度判定阈值（比值 = 完成进度 / 时间进度）
AHEAD_RATIO = 1.25
BEHIND_RATIO = 0.75
# 周期时间进度低于此值时不判定（月初不误判）
MIN_PERIOD_FRACTION = 0.10


def validate_payload(payload: dict) -> dict:
    """校验 workout payload，返回规范化副本；非法抛 ValueError（消息含字段名）。"""
    sport = payload.get("sport")
    if not isinstance(sport, str) or not sport.strip():
        raise ValueError("sport 不能为空：请提供运动类型（如 run/swim/gym/cycle）")

    duration = payload.get("duration_min")
    distance = payload.get("distance_km")
    if duration is None and distance is None:
        raise ValueError("duration_min 与 distance_km 至少提供其一")
    for name, value in (("duration_min", duration), ("distance_km", distance)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"{name} 必须是大于 0 的数值")

    normalized: dict = {"sport": sport.strip()}
    if duration is not None:
        normalized["duration_min"] = duration
    if distance is not None:
        normalized["distance_km"] = distance
    if payload.get("notes"):
        normalized["notes"] = str(payload["notes"])
    return normalized


def summarize(items: list[dict]) -> dict:
    """workout 明细 → 汇总：总次数/总时长/总距离/按 sport 分组。"""
    summary = {
        "count": len(items),
        "total_duration_min": 0,
        "total_distance_km": 0,
        "by_sport": {},
    }
    for item in items:
        payload = item["payload"]
        duration = payload.get("duration_min") or 0
        distance = payload.get("distance_km") or 0
        summary["total_duration_min"] += duration
        summary["total_distance_km"] += distance
        sport = payload.get("sport", "unknown")
        group = summary["by_sport"].setdefault(
            sport, {"count": 0, "duration_min": 0, "distance_km": 0}
        )
        group["count"] += 1
        group["duration_min"] += duration
        group["distance_km"] += distance
    return summary


def current_period(period: str, today: date | None = None) -> tuple[date, date]:
    """当前周期起止（含两端）：week=周一起始自然周，month=自然月。"""
    if period not in ("week", "month"):
        raise ValueError(f"period 只支持 week/month，收到 {period!r}")
    today = today or datetime.now(TZ).date()
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    start = today.replace(day=1)
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    return start, next_month - timedelta(days=1)


def _event_in_period(event: dict, start: date, end: date) -> bool:
    day = date.fromisoformat(event["occurred_at"][:10])
    return start <= day <= end


def _metric_value(metric: str, payload: dict) -> float:
    if metric == "distance":
        return payload.get("distance_km") or 0
    if metric == "duration":
        return payload.get("duration_min") or 0
    return 0  # frequency 在 progress 中按条数计


def progress(goal: dict, events: list[dict], ref_date: date | None = None) -> dict:
    """目标进度：current 从 workout 事件实时计算，判定 ahead/on_track/behind。

    active 目标 ref_date 取今天；superseded 目标取其 created_at 所在周期。
    """
    ref = ref_date or datetime.now(TZ).date()
    start, end = current_period(goal["period"], today=ref)
    in_period = [
        e
        for e in events
        if _event_in_period(e, start, end) and date.fromisoformat(e["occurred_at"][:10]) <= ref
    ]

    if goal["metric"] == "frequency":
        current = len(in_period)
    else:
        current = sum(_metric_value(goal["metric"], e["payload"]) for e in in_period)

    target = goal["target"]
    remaining = max(target - current, 0)
    total_days = (end - start).days + 1
    elapsed_days = min(max((ref - start).days + 1, 0), total_days)
    time_fraction = elapsed_days / total_days
    done_fraction = current / target if target else 0

    if time_fraction < MIN_PERIOD_FRACTION:
        verdict = "on_track"
    else:
        ratio = done_fraction / time_fraction
        if ratio >= AHEAD_RATIO:
            verdict = "ahead"
        elif ratio < BEHIND_RATIO:
            verdict = "behind"
        else:
            verdict = "on_track"

    return {
        "goal_id": goal["id"],
        "metric": goal["metric"],
        "period": goal["period"],
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "target": target,
        "current": current,
        "remaining": remaining,
        "verdict": verdict,
    }
