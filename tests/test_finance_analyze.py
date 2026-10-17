"""finance 分析纯函数测试，逐 spec 场景。

上游响应形状说明（对齐 credi-insights 实测）：
- get_stats：camelCase，categoryBreakdown 内 amount 已是数字
- get_transactions：Prisma 原始对象，amount 为**字符串**（Decimal 序列化），
  未分类交易 categoryId 与 category 均为 null
"""

from app.finance import analyze

# ---------- 固定上游响应形状 ----------


def tx(
    id,
    merchant,
    amount,
    date="2026-10-05T00:00:00.000Z",
    time=None,
    type="DEBIT",
    card="0094",
    category_id=None,
):
    return {
        "id": id,
        "txDate": date,
        "txTime": time,
        "merchant": merchant,
        "amount": amount,  # 字符串，同上游
        "type": type,
        "cardLast4": card,
        "categoryId": category_id,
        "category": {"name": "餐饮", "icon": "🍜"} if category_id else None,
    }


def stats(card_id, debit, credit, count, breakdown):
    return {
        "period": "2026-10",
        "cardId": card_id,
        "totalDebit": debit,
        "totalCredit": credit,
        "netSpending": debit - credit,
        "transactionCount": count,
        "categoryBreakdown": breakdown,
    }


# ---------- compute_trend：趋势与环比 ----------


class TestComputeTrend:
    def test_sorted_asc_with_change(self):
        monthly = [
            {"month": "2026-09", "total_debit": 100.0, "by_category": {"餐饮": 100.0}},
            {"month": "2026-08", "total_debit": 80.0, "by_category": {"餐饮": 80.0}},
            {"month": "2026-10", "total_debit": 150.0, "by_category": {"餐饮": 150.0}},
        ]
        out = analyze.compute_trend(monthly)
        assert [m["month"] for m in out] == ["2026-08", "2026-09", "2026-10"]
        assert out[0]["change_vs_prev"] is None
        assert out[1]["change_vs_prev"] == 20.0
        assert out[2]["change_vs_prev"] == 50.0
        assert out[2]["by_category"] == {"餐饮": 150.0}

    def test_single_month_change_none(self):
        out = analyze.compute_trend([{"month": "2026-10", "total_debit": 50.0, "by_category": {}}])
        assert out[0]["change_vs_prev"] is None


# ---------- detect_subscriptions：订阅识别 ----------


class TestDetectSubscriptions:
    def test_typical_subscription_detected(self):
        txs = [
            tx(f"t{i}", "爱奇艺", "25.00", date=f"2026-{m:02d}-10T00:00:00.000Z")
            for i, m in enumerate([7, 8, 9, 10])
        ]
        out = analyze.detect_subscriptions(txs)
        assert len(out) == 1
        sub = out[0]
        assert sub["merchant"] == "爱奇艺"
        assert sub["monthly_avg"] == 25.0
        assert sub["months_count"] == 4
        assert sub["last_amount"] == 25.0
        assert sub["last_date"] == "2026-10-10"

    def test_volatile_amounts_rejected(self):
        txs = [
            tx("t1", "某商户", "10.00", date="2026-08-01"),
            tx("t2", "某商户", "200.00", date="2026-09-01"),
            tx("t3", "某商户", "15.00", date="2026-10-01"),
        ]
        assert analyze.detect_subscriptions(txs) == []

    def test_too_few_months_rejected(self):
        txs = [
            tx("t1", "某商户", "25.00", date="2026-09-01"),
            tx("t2", "某商户", "25.00", date="2026-10-01"),
        ]
        assert analyze.detect_subscriptions(txs) == []

    def test_sorted_by_monthly_avg_desc(self):
        txs = [tx("a1", "低价", "10.00", date="2026-08-01"),
               tx("a2", "低价", "10.00", date="2026-09-01"),
               tx("a3", "低价", "10.00", date="2026-10-01"),
               tx("b1", "高价", "30.00", date="2026-08-02"),
               tx("b2", "高价", "30.00", date="2026-09-02"),
               tx("b3", "高价", "30.00", date="2026-10-02")]
        out = analyze.detect_subscriptions(txs)
        assert [s["merchant"] for s in out] == ["高价", "低价"]

    def test_credit_and_uncategorized_ignored(self):
        # 收入与已分类交易不参与订阅识别？——已分类也应识别（订阅通常有固定分类）。
        # 收入（CREDIT）不识别。
        txs = [tx("t1", "工资", "6000.00", type="CREDIT", date=f"2026-{m:02d}-10")
               for m in (8, 9, 10)]
        assert analyze.detect_subscriptions(txs) == []

    def test_within_tolerance_detected(self):
        # ±20% 以内的波动仍识别：25 / 26 / 25（偏差 4%）
        txs = [tx("t1", "视频会员", "25.00", date="2026-08-01"),
               tx("t2", "视频会员", "26.00", date="2026-09-01"),
               tx("t3", "视频会员", "25.00", date="2026-10-01")]
        out = analyze.detect_subscriptions(txs)
        assert len(out) == 1
        assert out[0]["monthly_avg"] == 25.33  # round(76/3, 2)


# ---------- filter_pending：每日待确认清单 ----------


class TestFilterPending:
    def test_filter_and_project(self):
        txs = [
            tx("t1", "已分类", "28.00", time="12:30:00", category_id="cat1"),
            tx("t2", "滴滴出行", "23.50", time="08:10:00"),
            tx("t3", "美团", "28.00", time="19:05:00"),
        ]
        out = analyze.filter_pending(txs)
        assert [i["tx_id"] for i in out] == ["t2", "t3"]  # 按时间升序
        assert out[0] == {
            "tx_id": "t2",
            "merchant": "滴滴出行",
            "amount": 23.5,
            "cardLast4": "0094",
            "txTime": "08:10:00",
        }

    def test_sorted_by_time_asc(self):
        txs = [
            tx("t1", "晚的", "10.00", time="22:00:00"),
            tx("t2", "早的", "10.00", time="07:00:00"),
        ]
        assert [i["tx_id"] for i in analyze.filter_pending(txs)] == ["t2", "t1"]

    def test_no_time_sorts_last(self):
        # 月账单来源无 txTime，排在有时间的之后（同日）
        txs = [
            tx("t1", "无时间", "10.00", time=None),
            tx("t2", "有时间", "10.00", time="07:00:00"),
        ]
        assert [i["tx_id"] for i in analyze.filter_pending(txs)] == ["t2", "t1"]

    def test_all_classified_returns_empty(self):
        txs = [tx("t1", "已分类", "28.00", category_id="cat1")]
        assert analyze.filter_pending(txs) == []

    def test_v110_categorized_not_pending(self):
        # 上游 v1.1.0 不回 categoryId：分类与否看 category 名（"未分类"已被归一化为 None）
        txs = [
            {"id": "t1", "txDate": "2026-10-05", "merchant": "美团", "amount": 35.5,
             "type": "DEBIT", "categoryId": None, "category": {"name": "餐饮"}},
            {"id": "t2", "txDate": "2026-10-06", "merchant": "地铁", "amount": 4.0,
             "type": "DEBIT", "categoryId": None, "category": None},
        ]
        out = analyze.filter_pending(txs)
        assert [i["tx_id"] for i in out] == ["t2"]


# ---------- summarize_transactions：任意窗口交易汇总 ----------


class TestSummarizeTransactions:
    def test_totals_and_categories(self):
        txs = [
            tx("t1", "美团", "28.00", category_id="cat1"),
            tx("t2", "滴滴出行", "23.50", category_id="cat2"),
            tx("t3", "美团", "12.00", category_id="cat1"),
            tx("t4", "某小店", "9.90"),
            tx("t5", "工资", "6000.00", type="CREDIT", category_id="cat3"),
        ]
        out = analyze.summarize_transactions(txs)
        assert out["total_debit"] == 73.4
        assert out["total_credit"] == 6000.0
        assert out["transaction_count"] == 5
        # 夹具 tx() 的分类名固定为"餐饮"（cat1/cat2 同名合并）、无分类计"未分类"
        assert out["by_category"] == {"餐饮": 63.5, "未分类": 9.9}
        assert out["top_merchants"][0] == {"merchant": "美团", "amount": 40.0}

    def test_empty(self):
        out = analyze.summarize_transactions([])
        assert out == {
            "total_debit": 0,
            "total_credit": 0,
            "transaction_count": 0,
            "by_category": {},
            "top_merchants": [],
        }


# ---------- normalize_transactions：上游 v1.1.0 适配 ----------


class TestNormalizeTransactions:
    def test_new_shape_mapped(self):
        # 新上游：date(YYYY-MM-DD)/amount 数字/category 名字符串，无 txTime/cardLast4
        raw = [{"id": "t1", "date": "2026-10-05", "merchant": "美团", "amount": 28,
                "type": "DEBIT", "category": "餐饮"}]
        out = analyze.normalize_transactions(raw)
        assert out[0]["txDate"] == "2026-10-05"
        assert out[0]["amount"] == 28
        assert out[0]["category"] == {"name": "餐饮"}
        assert out[0]["categoryId"] is None
        assert out[0]["txTime"] is None
        assert out[0]["cardLast4"] is None

    def test_uncategorized_becomes_none(self):
        out = analyze.normalize_transactions([{"id": "t1", "date": "2026-10-05",
                                               "merchant": "x", "amount": 1,
                                               "type": "DEBIT", "category": "未分类"}])
        assert out[0]["category"] is None  # filter_pending 的未分类判据

    def test_old_shape_passthrough(self):
        # 兼容旧形状（测试夹具/潜在回滚）
        raw = [{"id": "t1", "txDate": "2026-10-05T00:00:00.000Z", "merchant": "美团",
                "amount": "28.00", "type": "DEBIT", "categoryId": "cat1",
                "category": {"name": "餐饮"}}]
        out = analyze.normalize_transactions(raw)
        assert out[0]["txDate"] == "2026-10-05T00:00:00.000Z"
        assert out[0]["category"] == {"name": "餐饮"}

    def test_normalized_flows_through_pure_functions(self):
        # 归一化后的新形状能直接进订阅识别/待确认/汇总
        txs = analyze.normalize_transactions([
            {"id": f"t{i}", "date": f"2026-{m:02d}-10", "merchant": "爱奇艺",
             "amount": 25, "type": "DEBIT", "category": "娱乐"}
            for i, m in enumerate([7, 8, 9, 10])
        ])
        subs = analyze.detect_subscriptions(txs)
        assert len(subs) == 1 and subs[0]["monthly_avg"] == 25.0


# ---------- months_covering：窗口覆盖月份 ----------


class TestMonthsCovering:
    def test_single_month(self):
        assert analyze.months_covering("2026-10-05", "2026-10-31") == ["2026-10"]

    def test_cross_month(self):
        assert analyze.months_covering("2026-09-28", "2026-10-04") == ["2026-09", "2026-10"]
