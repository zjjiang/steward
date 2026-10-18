"""账单周期计算（纯函数）。

信用卡账单期 = 出账日 → 下个出账日前一日。出账日按卡配置的 billingDay，
超出当月天数时截断到当月最后一天（31 日卡在 2 月按 2/28 出账）。
期名（cycle）= 出账日所在月，如 2026-10 期即 2026-10-05 出账的那期。
"""

import calendar
from datetime import date, timedelta

_CURRENT = "current"
_PREVIOUS = "previous"


def _statement_date(year: int, month: int, billing_day: int) -> date:
    """该月出账日：billing_day 超出当月天数则截断。"""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(billing_day, last))


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    total = year * 12 + month - 1 + offset
    return total // 12, total % 12 + 1


def cycle_bounds(billing_day: int, cycle: str, today: date) -> dict:
    """按账单日计算周期。cycle: current / previous / YYYY-MM。

    返回 {cycle, statement_date, start, end}（ISO 日期字符串）。
    """
    if not isinstance(billing_day, int) or isinstance(billing_day, bool) or not 1 <= billing_day <= 31:
        raise ValueError(f"billing_day 应为 1-31，收到 {billing_day!r}")

    if cycle in (_CURRENT, _PREVIOUS):
        # 最近一个已到的出账日：今天 ≥ 本月出账日 → 本月，否则上月
        stmt_this = _statement_date(today.year, today.month, billing_day)
        prev_y, prev_m = _shift_month(today.year, today.month, -1)
        if today >= stmt_this:
            anchor = (today.year, today.month)
        else:
            anchor = (prev_y, prev_m)
        if cycle == _PREVIOUS:
            anchor = _shift_month(anchor[0], anchor[1], -1)
        stmt_y, stmt_m = anchor
        stmt_next_y, stmt_next_m = _shift_month(stmt_y, stmt_m, 1)
    else:
        try:
            stmt_y, stmt_m = int(cycle[:4]), int(cycle[5:7])
            date(stmt_y, stmt_m, 1)
            if len(cycle) != 7 or cycle[4] != "-" or f"{stmt_m:02d}" != cycle[5:7]:
                raise ValueError
        except (ValueError, IndexError):
            raise ValueError(f"cycle 应为 current/previous/YYYY-MM，收到 {cycle!r}")
        stmt_next_y, stmt_next_m = _shift_month(stmt_y, stmt_m, 1)

    statement = _statement_date(stmt_y, stmt_m, billing_day)
    end = _statement_date(stmt_next_y, stmt_next_m, billing_day) - timedelta(days=1)
    return {
        "cycle": f"{stmt_y:04d}-{stmt_m:02d}",
        "statement_date": statement.isoformat(),
        "start": statement.isoformat(),
        "end": end.isoformat(),
    }
