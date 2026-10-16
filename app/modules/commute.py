"""commute 模块：上下班打卡的校验与统计（纯函数）。样板见 fitness。"""

VALID_DIRECTIONS = ("in", "out")


def validate_payload(payload: dict) -> dict:
    """校验 commute payload，返回规范化副本；非法抛 ValueError（消息含字段名）。"""
    direction = payload.get("direction")
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"direction 只支持 {'/'.join(VALID_DIRECTIONS)}，收到 {direction!r}")
    return {"direction": direction}


def summarize(items: list[dict]) -> dict:
    """commute 明细 → 汇总：打卡天数（按自然日去重）、in/out 各自次数。"""
    days: set[str] = set()
    in_count = 0
    out_count = 0
    for item in items:
        days.add(item["occurred_at"][:10])
        if item["payload"]["direction"] == "in":
            in_count += 1
        else:
            out_count += 1
    return {"days": len(days), "in_count": in_count, "out_count": out_count}
