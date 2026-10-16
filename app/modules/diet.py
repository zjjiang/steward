"""diet 模块：meal 类型校验与汇总（纯函数）。样板见 fitness。"""

VALID_MEALS = ("breakfast", "lunch", "dinner", "snack")


def validate_payload(payload: dict) -> dict:
    """校验 meal payload，返回规范化副本；非法抛 ValueError（消息含字段名）。"""
    desc = payload.get("desc")
    if not isinstance(desc, str) or not desc.strip():
        raise ValueError("desc 不能为空：请说明吃了什么")

    normalized: dict = {"desc": desc.strip()}
    meal = payload.get("meal")
    if meal is not None:
        if meal not in VALID_MEALS:
            raise ValueError(f"meal 只支持 {'/'.join(VALID_MEALS)}，收到 {meal!r}")
        normalized["meal"] = meal
    cost = payload.get("cost")
    if cost is not None:
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost <= 0:
            raise ValueError("cost 必须是大于 0 的数值")
        normalized["cost"] = cost
    return normalized


def summarize(items: list[dict]) -> dict:
    """meal 明细 → 汇总：次数、花费合计、按餐次分组计数。"""
    summary = {"count": len(items), "total_cost": 0, "by_meal": {}}
    for item in items:
        payload = item["payload"]
        summary["total_cost"] += payload.get("cost") or 0
        meal = payload.get("meal")
        if meal:
            summary["by_meal"][meal] = summary["by_meal"].get(meal, 0) + 1
    return summary
