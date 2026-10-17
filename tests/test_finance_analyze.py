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


# ---------- merge_card_stats：跨卡月度汇总 ----------


class TestMergeCardStats:
    def test_merge_two_cards(self):
        card_stats = [
            stats("c1", 100.0, 20.0, 5, [
                {"categoryId": "cat1", "name": "餐饮", "icon": "🍜", "amount": 60.0, "count": 2},
                {"categoryId": "uncategorized", "name": "未分类", "icon": None, "amount": 40.0, "count": 3},
            ]),
            stats("c2", 80.5, 0, 3, [
                {"categoryId": "cat1", "name": "餐饮", "icon": "🍜", "amount": 30.5, "count": 1},
                {"categoryId": "cat2", "name": "交通", "icon": "🚇", "amount": 50.0, "count": 2},
            ]),
        ]
        transactions = [
            tx("t1", "美团", "28.00", category_id="cat1"),
            tx("t2", "美团", "35.00", category_id="cat1"),
            tx("t3", "滴滴出行", "23.50", category_id="cat2"),
            tx("t4", "工资", "6000.00", type="CREDIT", category_id="cat3"),
        ]
        out = analyze.merge_card_stats(card_stats, transactions)
        assert out["total_debit"] == 180.5
        assert out["total_credit"] == 20.0
        assert out["transaction_count"] == 8
        # 分类跨卡合并、按金额降序
        assert out["by_category"][0] == {
            "category_id": "cat1", "name": "餐饮", "icon": "🍜", "amount": 90.5, "count": 3,
        }
        assert out["by_category"][1]["category_id"] == "cat2"
        assert out["by_category"][2]["category_id"] == "uncategorized"
        # Top 商户只统计支出、金额降序
        assert out["top_merchants"] == [
            {"merchant": "美团", "amount": 63.0},
            {"merchant": "滴滴出行", "amount": 23.5},
        ]

    def test_empty(self):
        out = analyze.merge_card_stats([], [])
        assert out["total_debit"] == 0
        assert out["total_credit"] == 0
        assert out["transaction_count"] == 0
        assert out["by_category"] == []
        assert out["top_merchants"] == []

    def test_top_merchants_max_five(self):
        transactions = [tx(f"t{i}", f"商户{i}", "10.00") for i in range(8)]
        out = analyze.merge_card_stats([], transactions)
        assert len(out["top_merchants"]) == 5
        assert out["top_merchants"][0]["merchant"] == "商户0"

    def test_amount_string_coerced(self):
        # 上游 get_transactions 的 amount 是字符串，必须归一为两位小数数字
        out = analyze.merge_card_stats([], [tx("t1", "美团", "28.00")])
        assert out["top_merchants"][0]["amount"] == 28.0


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
