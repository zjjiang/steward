"""review 编排模块测试，逐 spec 场景。数据注入式，零 IO。"""

import pytest

from app.modules import review

KNOWN = {"workout", "meal", "body", "commute"}


def ev(type, occurred_at, payload):
    return {"type": type, "occurred_at": occurred_at, "payload": payload}


def workout(day, km, minutes=30, sport="run"):
    return ev("workout", f"{day}T08:00:00+08:00", {"sport": sport, "distance_km": km, "duration_min": minutes})


# ---------- period_bounds：周期边界 ----------


class TestPeriodBounds:
    def test_week_boundaries(self):
        # 2026-10-14 是周三
        assert review.period_bounds("week", "2026-10-14") == {
            "period": "week", "start": "2026-10-12", "end": "2026-10-18", "ref_date": "2026-10-14",
        }

    def test_month_boundaries(self):
        assert review.period_bounds("month", "2026-10-14") == {
            "period": "month", "start": "2026-10-01", "end": "2026-10-31", "ref_date": "2026-10-14",
        }

    def test_invalid_period_rejected(self):
        with pytest.raises(ValueError, match="period"):
            review.period_bounds("day", "2026-10-14")

    def test_invalid_date_rejected(self):
        with pytest.raises(ValueError, match="ref_date"):
            review.period_bounds("week", "10月14日")


# ---------- assemble_review：sections 拼装 ----------


def base_inputs(**overrides):
    inputs = {
        "period": "week",
        "ref_date": "2026-10-14",
        "workouts": [],
        "meals": [],
        "bodies": [],
        "commutes": [],
        "other_events": [],
        "goals": [],
        "finance": {"available": True},
    }
    inputs.update(overrides)
    return inputs


class TestAssembleReview:
    def test_meta(self):
        out = review.assemble_review(**base_inputs())
        assert out["meta"] == {
            "period": "week", "start": "2026-10-12", "end": "2026-10-18", "ref_date": "2026-10-14",
        }

    def test_local_sections(self):
        out = review.assemble_review(**base_inputs(
            workouts=[
                workout("2026-10-12", 8, 40),
                workout("2026-10-13", 9, 45),
                workout("2026-10-01", 100),  # 周期外，不计
            ],
            meals=[ev("meal", "2026-10-12T12:00:00+08:00", {"desc": "麻辣烫", "cost": 28})],
            bodies=[ev("body", "2026-10-12T07:00:00+08:00", {"weight_kg": 62.5})],
            commutes=[
                ev("commute", "2026-10-12T09:00:00+08:00", {"direction": "in"}),
                ev("commute", "2026-10-13T09:00:00+08:00", {"direction": "in"}),
            ],
            other_events=[ev("note", "2026-10-12T10:00:00+08:00", {"text": "配了颗牙"})],
        ))
        assert out["fitness"]["summary"]["count"] == 2
        assert out["fitness"]["summary"]["total_distance_km"] == 17
        assert out["diet"]["count"] == 1
        assert out["body"]["change"] is None  # 单条
        assert out["commute"]["days"] == 2
        assert out["other"] == {"note": 1}

    def test_goal_progress_included(self):
        goal = {"id": 1, "kind": "workout", "metric": "distance", "target": 50,
                "period": "month", "status": "active", "superseded_by": None,
                "created_at": "2026-10-01T00:00:00+08:00"}
        out = review.assemble_review(**base_inputs(
            period="month",
            workouts=[workout("2026-10-12", 25)],
            goals=[goal],
        ))
        assert len(out["fitness"]["goals"]) == 1
        g = out["fitness"]["goals"][0]
        assert g["metric"] == "distance"
        assert g["target"] == 50
        assert g["current"] == 25
        assert g["verdict"] in ("ahead", "on_track", "behind")

    def test_no_goals_empty_list(self):
        out = review.assemble_review(**base_inputs())
        assert out["fitness"]["goals"] == []

    def test_finance_section_passthrough(self):
        finance = {"available": True, "total_debit": 500.0, "subscriptions": []}
        out = review.assemble_review(**base_inputs(finance=finance))
        assert out["finance"] == finance

    def test_empty_period_all_zero(self):
        out = review.assemble_review(**base_inputs())
        assert out["fitness"]["summary"]["count"] == 0
        assert out["diet"] == {"count": 0, "total_cost": 0, "by_meal": {}}
        assert out["body"] == {"series": [], "change": None}
        assert out["commute"] == {"days": 0, "in_count": 0, "out_count": 0}
        assert out["other"] == {}
        assert out["finance"]["available"] is True
