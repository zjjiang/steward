"""账单周期纯函数测试：cycle_bounds 的窗口计算与边界截断。"""

from datetime import date

import pytest

from app.finance.billing import cycle_bounds


class TestExplicitCycle:
    def test_statement_day_5_cycle_2026_10(self):
        # 出账日 2026-10-05，窗口 10-05 ~ 11-04
        out = cycle_bounds(5, "2026-10", today=date(2026, 10, 18))
        assert out == {
            "cycle": "2026-10",
            "statement_date": "2026-10-05",
            "start": "2026-10-05",
            "end": "2026-11-04",
        }

    def test_statement_day_1_cycle_is_calendar_month(self):
        out = cycle_bounds(1, "2026-10", today=date(2026, 10, 18))
        assert (out["start"], out["end"]) == ("2026-10-01", "2026-10-31")

    def test_billing_day_31_clamped_in_february(self):
        # 31 日卡在 2 月出账日截断为 2/28（2026 非闰年）
        out = cycle_bounds(31, "2026-02", today=date(2026, 10, 18))
        assert out["statement_date"] == "2026-02-28"
        assert out["start"] == "2026-02-28"
        assert out["end"] == "2026-03-30"  # 下月出账 3/31 前一日


class TestCurrentAndPrevious:
    def test_current_after_statement_day(self):
        # 今天 10-18 ≥ 出账日 5 号 → 本月那期已出账
        out = cycle_bounds(5, "current", today=date(2026, 10, 18))
        assert out["cycle"] == "2026-10"
        assert out["statement_date"] == "2026-10-05"
        assert (out["start"], out["end"]) == ("2026-10-05", "2026-11-04")

    def test_current_before_statement_day(self):
        # 今天 10-03 < 出账日 5 号 → 最近已出账的是上月那期
        out = cycle_bounds(5, "current", today=date(2026, 10, 3))
        assert out["cycle"] == "2026-09"
        assert out["statement_date"] == "2026-09-05"
        assert (out["start"], out["end"]) == ("2026-09-05", "2026-10-04")

    def test_current_on_statement_day(self):
        # 今天恰为出账日 → 本期已出账
        out = cycle_bounds(5, "current", today=date(2026, 10, 5))
        assert out["cycle"] == "2026-10"

    def test_previous_of_current(self):
        out = cycle_bounds(5, "previous", today=date(2026, 10, 18))
        assert out["cycle"] == "2026-09"
        assert (out["start"], out["end"]) == ("2026-09-05", "2026-10-04")

    def test_current_year_rollover(self):
        # 1 月出账前，current 是去年 12 月那期
        out = cycle_bounds(10, "current", today=date(2026, 1, 5))
        assert out["cycle"] == "2025-12"
        assert out["statement_date"] == "2025-12-10"


class TestValidation:
    def test_bad_billing_day_rejected(self):
        with pytest.raises(ValueError, match="billing_day"):
            cycle_bounds(0, "current", today=date(2026, 10, 18))
        with pytest.raises(ValueError, match="billing_day"):
            cycle_bounds(32, "current", today=date(2026, 10, 18))

    def test_bad_cycle_rejected(self):
        with pytest.raises(ValueError, match="cycle"):
            cycle_bounds(5, "2026-13", today=date(2026, 10, 18))
        with pytest.raises(ValueError, match="cycle"):
            cycle_bounds(5, "junk", today=date(2026, 10, 18))
