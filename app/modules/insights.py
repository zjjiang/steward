"""insights 模块：跨周期趋势与异常的信号检测（纯函数）。

宁缺毋滥：所有信号都有双门槛（相对 + 绝对），不过门槛不出条目；
上一周期无数据视为无基线，同样不出。条目只含结构化字段，成文归龙虾。
"""

from datetime import date

REL_THRESHOLD = 0.25  # 通用相对门槛
CAT_REL_THRESHOLD = 0.50  # 分类跳变相对门槛
CAT_ABS_THRESHOLD = 100.0  # 分类跳变绝对门槛（元）
DEBIT_ABS_THRESHOLD = 100.0  # 总支出绝对门槛（元）
COST_ABS_THRESHOLD = 100.0  # 饮食花费绝对门槛（元）
WEIGHT_WINDOW_DAYS = 14
WEIGHT_MIN_SPAN_DAYS = 4
WEIGHT_RATE_THRESHOLD = 0.3  # kg/周


def compare(
    area: str,
    metric: str,
    kind: str,
    current: float,
    previous: float | None,
    *,
    abs_threshold: float,
    rel_threshold: float = REL_THRESHOLD,
) -> dict | None:
    """环比信号：无基线或双门槛不过 → None；过 → 结构化条目。"""
    if previous is None or previous == 0:
        return None
    change = current - previous
    if abs(change) < abs_threshold:
        return None
    if abs(change) / abs(previous) < rel_threshold:
        return None
    return {
        "area": area,
        "kind": kind,
        "metric": metric,
        "current": round(current, 2),
        "previous": round(previous, 2),
        "change": round(change, 2),
        "direction": "up" if change > 0 else "down",
    }


def weight_rate(events: list[dict]) -> dict | None:
    """近窗口体重斜率（kg/周）：最小二乘，同日取最后；样本不足/平缓 → None。"""
    per_day: dict[str, float] = {}
    for e in events:  # 无论输入顺序，同日以后写入的为准
        per_day[e["occurred_at"][:10]] = e["payload"]["weight_kg"]
    if len(per_day) < 2:
        return None
    days = sorted(per_day)
    span = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days
    if span < WEIGHT_MIN_SPAN_DAYS:
        return None
    xs = [date.fromisoformat(d).toordinal() for d in days]
    ys = [per_day[d] for d in days]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var = sum((x - mean_x) ** 2 for x in xs)
    if var == 0:
        return None
    rate = round(cov / var * 7, 2)  # 日斜率 → kg/周
    if abs(rate) < WEIGHT_RATE_THRESHOLD:
        return None
    return {
        "area": "body",
        "kind": "trend",
        "metric": "weight_rate_kg_week",
        "current": ys[-1],
        "previous": ys[0],
        "change": rate,
        "direction": "down" if rate < 0 else "up",
    }


def category_jumps(this_by_cat: dict | None, prev_by_cat: dict | None) -> list[dict]:
    """月度分类跳变：涨幅 ≥50% 且差额 ≥100 元出 anomaly；降幅不报。"""
    if not this_by_cat or not prev_by_cat:
        return []
    items = []
    for cat, current in this_by_cat.items():
        item = compare(
            "finance",
            f"category:{cat}",
            "anomaly",
            current,
            prev_by_cat.get(cat),
            abs_threshold=CAT_ABS_THRESHOLD,
            rel_threshold=CAT_REL_THRESHOLD,
        )
        if item and item["direction"] == "up":
            items.append(item)
    return items


def assemble_insights(
    *,
    workouts_this: list[dict],
    workouts_prev: list[dict],
    meals_this: list[dict],
    meals_prev: list[dict],
    debit_this: float | None,
    debit_prev: float | None,
    cat_this: dict | None,
    cat_prev: dict | None,
    bodies_window: list[dict],
) -> list[dict]:
    """拼装全部信号；finance 入参为 None 表示上游不可用，整体跳过。"""
    from app.modules import diet as diet_mod
    from app.modules import fitness as fitness_mod

    items: list[dict] = []

    fit_this = fitness_mod.summarize(workouts_this)
    fit_prev = fitness_mod.summarize(workouts_prev)
    prev_count = fit_prev["count"] or None
    prev_distance = fit_prev["total_distance_km"] or None
    prev_duration = fit_prev["total_duration_min"] or None
    for metric, current, prev, abs_th in (
        ("workout_count", fit_this["count"], prev_count, 1),
        ("total_distance_km", fit_this["total_distance_km"], prev_distance, 2),
        ("total_duration_min", fit_this["total_duration_min"], prev_duration, 20),
    ):
        item = compare("fitness", metric, "trend", current, prev, abs_threshold=abs_th)
        if item:
            items.append(item)

    meal_this = diet_mod.summarize(meals_this)
    meal_prev = diet_mod.summarize(meals_prev)
    for metric, current, prev, abs_th in (
        ("meal_count", meal_this["count"], meal_prev["count"] or None, 1),
        ("meal_total_cost", meal_this["total_cost"], meal_prev["total_cost"] or None, COST_ABS_THRESHOLD),
    ):
        item = compare("diet", metric, "trend", current, prev, abs_threshold=abs_th)
        if item:
            items.append(item)

    if debit_this is not None:
        item = compare(
            "finance", "total_debit", "trend", debit_this, debit_prev,
            abs_threshold=DEBIT_ABS_THRESHOLD,
        )
        if item:
            items.append(item)
        items.extend(category_jumps(cat_this, cat_prev))

    body_item = weight_rate(bodies_window)
    if body_item:
        items.append(body_item)

    return items
