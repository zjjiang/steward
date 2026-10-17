"""review 模块：周期复盘的纯编排。

把周期内本地流水（workout/meal/body/commute/兜底）+ 活跃目标进度 + 预取好的
财务数据拼成结构化 sections。不做自然语言成文（龙虾职责）、不做跨周期对比
（insights 职责）。数据全部注入，零 IO，可独立单测。
"""

from datetime import date

from app.modules import body, commute, diet, fitness

KNOWN_TYPES = {"workout", "meal", "body", "commute"}


def period_bounds(period: str, ref_date: str) -> dict:
    """复盘周期起止：复用 fitness 的周期语义（周一起始周 / 自然月）。"""
    try:
        ref = date.fromisoformat(ref_date)
    except ValueError:
        raise ValueError(f"ref_date 格式应为 YYYY-MM-DD，收到 {ref_date!r}")
    start, end = fitness.current_period(period, today=ref)
    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "ref_date": ref.isoformat(),
    }


def _in_period(events: list[dict], start: str, end: str) -> list[dict]:
    return [e for e in events if start <= e["occurred_at"][:10] <= end]


def assemble_review(
    *,
    period: str,
    ref_date: str,
    workouts: list[dict],
    meals: list[dict],
    bodies: list[dict],
    commutes: list[dict],
    other_events: list[dict],
    goals: list[dict],
    finance: dict,
) -> dict:
    """拼装复盘 sections；finance 为工具层预取好的段（含降级形态）。"""
    bounds = period_bounds(period, ref_date)
    start, end = bounds["start"], bounds["end"]

    in_workouts = _in_period(workouts, start, end)
    ref = date.fromisoformat(ref_date)

    other_counts: dict[str, int] = {}
    for e in _in_period(other_events, start, end):
        other_counts[e["type"]] = other_counts.get(e["type"], 0) + 1

    return {
        "meta": bounds,
        "fitness": {
            "summary": fitness.summarize(in_workouts),
            # 目标进度按各自周期计算（周目标在月复盘里同样成立），故传全量 workouts
            "goals": [fitness.progress(g, workouts, ref_date=ref) for g in goals],
        },
        "diet": diet.summarize(_in_period(meals, start, end)),
        "body": body.summarize(_in_period(bodies, start, end)),
        "commute": commute.summarize(_in_period(commutes, start, end)),
        "other": other_counts,
        "finance": finance,
    }
