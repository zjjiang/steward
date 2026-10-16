"""body 模块：体重等身体指标的校验与序列汇总（纯函数）。样板见 fitness。"""


def validate_payload(payload: dict) -> dict:
    """校验 body payload，返回规范化副本；非法抛 ValueError（消息含字段名）。"""
    weight = payload.get("weight_kg")
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 < weight <= 500:
        raise ValueError("weight_kg 必须是 (0, 500] 范围内的数值")
    return {"weight_kg": weight}


def summarize(items: list[dict]) -> dict:
    """body 明细 → 汇总：时间升序序列（同日取最后一条）+ 首末差值（不足 2 条为 None）。

    不依赖传入顺序（store 返回为倒序）。
    """
    by_day: dict[str, tuple[str, float]] = {}  # day -> (occurred_at, weight)，取当日最晚
    for item in items:
        day = item["occurred_at"][:10]
        current = by_day.get(day)
        if current is None or item["occurred_at"] > current[0]:
            by_day[day] = (item["occurred_at"], item["payload"]["weight_kg"])

    series = [{"date": day, "weight_kg": weight} for day, (_, weight) in sorted(by_day.items())]
    change = None
    if len(series) >= 2:
        change = series[-1]["weight_kg"] - series[0]["weight_kg"]
    return {"series": series, "change": change}
