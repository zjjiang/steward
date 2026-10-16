"""fitness 模块纯函数测试：payload 校验、汇总、周期边界、目标进度。"""

from datetime import date

import pytest

from app.modules import fitness


class TestValidatePayload:
    def test_valid_minimal_distance(self):
        out = fitness.validate_payload({"sport": "run", "distance_km": 8})
        assert out == {"sport": "run", "distance_km": 8}

    def test_valid_duration_only(self):
        out = fitness.validate_payload({"sport": "gym", "duration_min": 60})
        assert out["duration_min"] == 60

    def test_sport_stripped(self):
        assert fitness.validate_payload({"sport": " 跑步 ", "duration_min": 30})["sport"] == "跑步"

    def test_missing_sport_rejected(self):
        with pytest.raises(ValueError, match="sport"):
            fitness.validate_payload({"distance_km": 8})

    def test_empty_sport_rejected(self):
        with pytest.raises(ValueError, match="sport"):
            fitness.validate_payload({"sport": "  ", "duration_min": 30})

    def test_no_quantitative_field_rejected(self):
        with pytest.raises(ValueError, match="duration_min"):
            fitness.validate_payload({"sport": "run"})

    def test_negative_distance_rejected(self):
        with pytest.raises(ValueError, match="distance_km"):
            fitness.validate_payload({"sport": "run", "distance_km": -3})

    def test_zero_duration_rejected(self):
        with pytest.raises(ValueError, match="duration_min"):
            fitness.validate_payload({"sport": "gym", "duration_min": 0})

    def test_notes_kept(self):
        out = fitness.validate_payload({"sport": "gym", "duration_min": 60, "notes": "练胸和肩"})
        assert out["notes"] == "练胸和肩"


class TestSummarize:
    def test_summary(self):
        items = [
            {"payload": {"sport": "run", "duration_min": 40, "distance_km": 8}},
            {"payload": {"sport": "run", "duration_min": 45, "distance_km": 9}},
            {"payload": {"sport": "gym", "duration_min": 60}},
        ]
        s = fitness.summarize(items)
        assert s["count"] == 3
        assert s["total_duration_min"] == 145
        assert s["total_distance_km"] == 17
        assert s["by_sport"]["run"] == {"count": 2, "duration_min": 85, "distance_km": 17}
        assert s["by_sport"]["gym"] == {"count": 1, "duration_min": 60, "distance_km": 0}

    def test_empty_returns_zeroed(self):
        s = fitness.summarize([])
        assert s == {
            "count": 0,
            "total_duration_min": 0,
            "total_distance_km": 0,
            "by_sport": {},
        }


class TestCurrentPeriod:
    def test_week_monday_start(self):
        # 2026-10-16 是周五
        start, end = fitness.current_period("week", today=date(2026, 10, 16))
        assert start == date(2026, 10, 12)  # 周一
        assert end == date(2026, 10, 18)    # 周日

    def test_month_natural(self):
        start, end = fitness.current_period("month", today=date(2026, 10, 16))
        assert start == date(2026, 10, 1)
        assert end == date(2026, 10, 31)

    def test_month_boundary(self):
        _start, end = fitness.current_period("month", today=date(2026, 2, 10))
        assert end == date(2026, 2, 28)  # 2026 非闰年

    def test_invalid_period_rejected(self):
        with pytest.raises(ValueError, match="period"):
            fitness.current_period("quarter", today=date(2026, 10, 16))


def _event(day_of_month: int, distance=None, duration=None) -> dict:
    payload = {"sport": "run"}
    if distance is not None:
        payload["distance_km"] = distance
    if duration is not None:
        payload["duration_min"] = duration
    return {"payload": payload, "occurred_at": f"2026-10-{day_of_month:02d}T08:00:00+08:00"}


class TestProgress:
    def goal(self, target=50, metric="distance", period="month", created="2026-10-01"):
        return {"id": 1, "kind": "workout", "metric": metric, "target": target,
                "period": period, "status": "active", "created_at": created}

    def test_mid_month_on_track(self):
        events = [_event(10, distance=15), _event(14, distance=10)]  # 16 日已跑 25
        p = fitness.progress(self.goal(), events, ref_date=date(2026, 10, 16))
        assert p["current"] == 25
        assert p["remaining"] == 25
        assert p["verdict"] == "on_track"

    def test_late_month_behind(self):
        events = [_event(5, distance=10)]
        p = fitness.progress(self.goal(), events, ref_date=date(2026, 10, 25))
        assert p["current"] == 10
        assert p["remaining"] == 40
        assert p["verdict"] == "behind"

    def test_month_start_not_misjudged(self):
        p = fitness.progress(self.goal(), [], ref_date=date(2026, 10, 2))
        assert p["verdict"] == "on_track"

    def test_ahead(self):
        events = [_event(10, distance=30), _event(12, distance=10)]
        p = fitness.progress(self.goal(), events, ref_date=date(2026, 10, 14))
        assert p["verdict"] == "ahead"

    def test_frequency_metric(self):
        goal = self.goal(target=12, metric="frequency")
        events = [_event(3), _event(6), _event(9), _event(12)]
        p = fitness.progress(goal, events, ref_date=date(2026, 10, 16))
        assert p["current"] == 4
        assert p["remaining"] == 8

    def test_duration_metric_ignores_other_days(self):
        goal = self.goal(target=600, metric="duration")
        events = [_event(5, duration=60), _event(20, duration=90)]  # 20 日在 ref(16日) 之后
        p = fitness.progress(goal, events, ref_date=date(2026, 10, 16))
        assert p["current"] == 60  # 只算周期内且已发生的

    def test_future_events_excluded_for_distance(self):
        events = [_event(1, distance=20), _event(20, distance=30)]
        p = fitness.progress(self.goal(), events, ref_date=date(2026, 10, 16))
        assert p["current"] == 20

    def test_overshoot_remaining_zero(self):
        events = [_event(5, distance=55)]
        p = fitness.progress(self.goal(target=50), events, ref_date=date(2026, 10, 10))
        assert p["remaining"] == 0
