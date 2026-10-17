"""insights 信号检测纯函数测试，逐 spec 场景。"""

import pytest

from app.modules import insights


def body_ev(day, weight):
    return {"occurred_at": f"{day}T07:00:00+08:00", "payload": {"weight_kg": weight}}


# ---------- compare：环比信号与双门槛 ----------


class TestCompare:
    def test_significant_down_detected(self):
        out = insights.compare(
            "fitness", "total_distance_km", "trend", 8, 20, abs_threshold=2
        )
        assert out == {
            "area": "fitness", "kind": "trend", "metric": "total_distance_km",
            "current": 8, "previous": 20, "change": -12, "direction": "down",
        }

    def test_small_change_below_rel_threshold_rejected(self):
        # |Δ|=2km 达绝对门槛，但 10% < 25% 相对门槛
        assert insights.compare("fitness", "total_distance_km", "trend", 18, 20, abs_threshold=2) is None

    def test_small_change_below_abs_threshold_rejected(self):
        # 1km：|Δ|<2 绝对门槛
        assert insights.compare("fitness", "total_distance_km", "trend", 19, 20, abs_threshold=2) is None

    def test_no_baseline_rejected(self):
        assert insights.compare("fitness", "total_distance_km", "trend", 8, 0, abs_threshold=2) is None
        assert insights.compare("fitness", "total_distance_km", "trend", 8, None, abs_threshold=2) is None

    def test_up_direction(self):
        out = insights.compare("finance", "total_debit", "trend", 500, 100, abs_threshold=100)
        assert out["direction"] == "up"
        assert out["change"] == 400


# ---------- weight_rate：体重斜率 ----------


class TestWeightRate:
    def test_clear_decline_detected(self):
        events = [body_ev("2026-10-03", 63.0), body_ev("2026-10-17", 62.2)]
        out = insights.weight_rate(events)
        assert out["area"] == "body"
        assert out["kind"] == "trend"
        assert out["metric"] == "weight_rate_kg_week"
        assert out["change"] == pytest.approx(-0.4)
        assert out["direction"] == "down"
        assert out["current"] == 62.2
        assert out["previous"] == 63.0

    def test_multi_point_least_squares(self):
        # 不等距三点：10-01=63.0、10-08=62.8、10-15=62.6 → 斜率 -0.2/周，|rate|<0.3 不出
        events = [body_ev("2026-10-01", 63.0), body_ev("2026-10-08", 62.8), body_ev("2026-10-15", 62.6)]
        assert insights.weight_rate(events) is None

    def test_single_record_rejected(self):
        assert insights.weight_rate([body_ev("2026-10-10", 62.5)]) is None

    def test_short_window_rejected(self):
        events = [body_ev("2026-10-14", 63.0), body_ev("2026-10-16", 62.0)]  # 窗口 3 天
        assert insights.weight_rate(events) is None

    def test_same_day_takes_last(self):
        events = [
            body_ev("2026-10-03", 63.0),
            body_ev("2026-10-17", 62.0),
            body_ev("2026-10-17", 62.2),  # 同日取后写的（倒序输入下取前者也等价）
        ]
        out = insights.weight_rate(events)
        assert out["change"] == pytest.approx(-0.4)


# ---------- category_jumps：分类跳变 ----------


class TestCategoryJumps:
    def test_jump_detected_as_anomaly_up(self):
        out = insights.category_jumps({"餐饮": 900.0}, {"餐饮": 400.0})
        assert len(out) == 1
        assert out[0]["kind"] == "anomaly"
        assert out[0]["metric"] == "category:餐饮"
        assert out[0]["direction"] == "up"

    def test_down_not_reported(self):
        # 规格只报涨幅；降幅不算 anomaly
        assert insights.category_jumps({"餐饮": 100.0}, {"餐饮": 400.0}) == []

    def test_below_threshold_not_reported(self):
        assert insights.category_jumps({"餐饮": 450.0}, {"餐饮": 400.0}) == []

    def test_new_category_no_baseline(self):
        assert insights.category_jumps({"餐饮": 900.0}, {}) == []

    def test_only_jumping_categories(self):
        out = insights.category_jumps({"餐饮": 900.0, "交通": 200.0}, {"餐饮": 400.0, "交通": 190.0})
        assert [i["metric"] for i in out] == ["category:餐饮"]


# ---------- assemble_insights：汇总 ----------


class TestAssembleInsights:
    def _workout(self, day, km, minutes=30):
        return {"occurred_at": f"{day}T08:00:00+08:00",
                "payload": {"sport": "run", "distance_km": km, "duration_min": minutes}}

    def test_full_assembly(self):
        items = insights.assemble_insights(
            workouts_this=[self._workout("2026-10-13", 8)],
            workouts_prev=[self._workout("2026-10-06", 20)],
            meals_this=[], meals_prev=[],
            debit_this=900.0, debit_prev=400.0,
            cat_this={"餐饮": 900.0}, cat_prev={"餐饮": 400.0},
            bodies_window=[body_ev("2026-10-03", 63.0), body_ev("2026-10-17", 62.2)],
        )
        metrics = {(i["area"], i["metric"]) for i in items}
        assert ("fitness", "total_distance_km") in metrics
        assert ("finance", "total_debit") in metrics
        assert ("finance", "category:餐饮") in metrics
        assert ("body", "weight_rate_kg_week") in metrics

    def test_no_baseline_week_silent(self):
        items = insights.assemble_insights(
            workouts_this=[self._workout("2026-10-13", 8)],
            workouts_prev=[],
            meals_this=[], meals_prev=[],
            debit_this=0.0, debit_prev=0.0,
            cat_this={}, cat_prev={},
            bodies_window=[],
        )
        assert items == []

    def test_finance_unavailable_skipped(self):
        items = insights.assemble_insights(
            workouts_this=[self._workout("2026-10-13", 8)],
            workouts_prev=[self._workout("2026-10-06", 20)],
            meals_this=[], meals_prev=[],
            debit_this=None, debit_prev=None,  # 上游不可用
            cat_this=None, cat_prev=None,
            bodies_window=[],
        )
        assert all(i["area"] != "finance" for i in items)
        assert len(items) == 1
