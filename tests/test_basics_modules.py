"""diet / body / commute 三模块纯函数测试，逐 spec 场景。"""

import pytest

from app.modules import body, commute, diet

# ---------- diet ----------


class TestDietValidate:
    def test_valid_full(self):
        out = diet.validate_payload({"desc": "麻辣烫", "meal": "lunch", "cost": 28})
        assert out == {"desc": "麻辣烫", "meal": "lunch", "cost": 28}

    def test_desc_only(self):
        assert diet.validate_payload({"desc": "苹果"}) == {"desc": "苹果"}

    def test_missing_desc_rejected(self):
        with pytest.raises(ValueError, match="desc"):
            diet.validate_payload({"cost": 28})

    def test_empty_desc_rejected(self):
        with pytest.raises(ValueError, match="desc"):
            diet.validate_payload({"desc": " "})

    def test_invalid_meal_rejected(self):
        with pytest.raises(ValueError, match="meal"):
            diet.validate_payload({"desc": "夜宵", "meal": "brunch"})

    def test_negative_cost_rejected(self):
        with pytest.raises(ValueError, match="cost"):
            diet.validate_payload({"desc": "咖啡", "cost": -5})

    def test_zero_cost_rejected(self):
        with pytest.raises(ValueError, match="cost"):
            diet.validate_payload({"desc": "咖啡", "cost": 0})


class TestDietSummarize:
    def test_summary(self):
        items = [
            {"payload": {"desc": "麻辣烫", "meal": "lunch", "cost": 28}},
            {"payload": {"desc": "盖浇饭", "meal": "lunch", "cost": 35}},
            {"payload": {"desc": "燕麦", "meal": "breakfast"}},
        ]
        s = diet.summarize(items)
        assert s["count"] == 3
        assert s["total_cost"] == 63
        assert s["by_meal"] == {"lunch": 2, "breakfast": 1}

    def test_empty(self):
        assert diet.summarize([]) == {"count": 0, "total_cost": 0, "by_meal": {}}


# ---------- body ----------


class TestBodyValidate:
    def test_valid_weight(self):
        assert body.validate_payload({"weight_kg": 62.5}) == {"weight_kg": 62.5}

    def test_missing_rejected(self):
        with pytest.raises(ValueError, match="weight_kg"):
            body.validate_payload({})

    def test_negative_rejected(self):
        with pytest.raises(ValueError, match="weight_kg"):
            body.validate_payload({"weight_kg": -3})

    def test_over_500_rejected(self):
        with pytest.raises(ValueError, match="weight_kg"):
            body.validate_payload({"weight_kg": 800})


class TestBodySummarize:
    def test_series_and_change(self):
        items = [
            {"occurred_at": "2026-10-10T07:00:00+08:00", "payload": {"weight_kg": 62.5}},
            {"occurred_at": "2026-10-16T07:00:00+08:00", "payload": {"weight_kg": 61.8}},
        ]
        s = body.summarize(items)
        assert s["series"] == [
            {"date": "2026-10-10", "weight_kg": 62.5},
            {"date": "2026-10-16", "weight_kg": 61.8},
        ]
        assert s["change"] == pytest.approx(-0.7)

    def test_single_record_change_null(self):
        items = [{"occurred_at": "2026-10-16T07:00:00+08:00", "payload": {"weight_kg": 62.5}}]
        s = body.summarize(items)
        assert len(s["series"]) == 1
        assert s["change"] is None

    def test_same_day_takes_last(self):
        # store 返回为倒序：晚的在前
        items = [
            {"occurred_at": "2026-10-16T22:00:00+08:00", "payload": {"weight_kg": 63.0}},
            {"occurred_at": "2026-10-16T07:00:00+08:00", "payload": {"weight_kg": 62.5}},
        ]
        s = body.summarize(items)
        assert s["series"] == [{"date": "2026-10-16", "weight_kg": 63.0}]

    def test_empty(self):
        assert body.summarize([]) == {"series": [], "change": None}


# ---------- commute ----------


class TestCommuteValidate:
    def test_valid_in(self):
        assert commute.validate_payload({"direction": "in"}) == {"direction": "in"}

    def test_invalid_direction_rejected(self):
        with pytest.raises(ValueError, match="direction"):
            commute.validate_payload({"direction": "home"})


class TestCommuteSummarize:
    def test_days_and_directions(self):
        items = [
            {"occurred_at": "2026-10-13T09:00:00+08:00", "payload": {"direction": "in"}},
            {"occurred_at": "2026-10-13T18:00:00+08:00", "payload": {"direction": "out"}},
            {"occurred_at": "2026-10-14T09:00:00+08:00", "payload": {"direction": "in"}},
        ]
        s = commute.summarize(items)
        assert s["days"] == 2
        assert s["in_count"] == 2
        assert s["out_count"] == 1

    def test_empty(self):
        assert commute.summarize([]) == {"days": 0, "in_count": 0, "out_count": 0}
