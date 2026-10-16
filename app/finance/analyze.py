"""finance 分析纯函数：跨卡汇总、趋势对比、订阅识别、待确认清单。

只吃上游响应形状的 dict/list（get_stats / get_transactions），不碰网络与数据库。
注意：上游 get_transactions 的 amount 经 JSON 序列化是字符串（Prisma Decimal），
所有金额入口统一经 _num 归一。
"""

MIN_SUBSCRIPTION_MONTHS = 3
SUBSCRIPTION_TOLERANCE = 0.20
TOP_MERCHANTS_LIMIT = 5
UNCATEGORIZED_ID = "uncategorized"


def _num(value) -> float:
    """金额归一：字符串/数字 → 两位小数 float。"""
    return round(float(value), 2)


def _month_of(tx_date: str) -> str:
    return tx_date[:7]


def _date_of(tx_date: str) -> str:
    return tx_date[:10]


def merge_card_stats(card_stats: list[dict], transactions: list[dict]) -> dict:
    """跨卡合并 get_stats 结果；Top 商户取自全月 get_transactions（仅支出）。"""
    total_debit = _num(sum(s.get("totalDebit", 0) for s in card_stats))
    total_credit = _num(sum(s.get("totalCredit", 0) for s in card_stats))
    transaction_count = sum(s.get("transactionCount", 0) for s in card_stats)

    by_category: dict[str, dict] = {}
    for s in card_stats:
        for entry in s.get("categoryBreakdown", []):
            cid = entry.get("categoryId") or UNCATEGORIZED_ID
            bucket = by_category.setdefault(
                cid,
                {
                    "category_id": cid,
                    "name": entry.get("name", "未分类"),
                    "icon": entry.get("icon"),
                    "amount": 0.0,
                    "count": 0,
                },
            )
            bucket["amount"] = _num(bucket["amount"] + entry.get("amount", 0))
            bucket["count"] += entry.get("count", 0)
    categories = sorted(by_category.values(), key=lambda c: c["amount"], reverse=True)

    merchants: dict[str, float] = {}
    for t in transactions:
        if t.get("type") != "DEBIT":
            continue
        name = t.get("merchant", "")
        merchants[name] = _num(merchants.get(name, 0.0) + _num(t.get("amount", 0)))
    top_merchants = [
        {"merchant": name, "amount": amount}
        for name, amount in sorted(merchants.items(), key=lambda kv: kv[1], reverse=True)
    ][:TOP_MERCHANTS_LIMIT]

    return {
        "total_debit": total_debit,
        "total_credit": total_credit,
        "transaction_count": transaction_count,
        "by_category": categories,
        "top_merchants": top_merchants,
    }


def compute_trend(monthly: list[dict]) -> list[dict]:
    """月度列表按月升序排列，附相邻月环比（最早一月为 null）。"""
    ordered = sorted(monthly, key=lambda m: m["month"])
    result = []
    prev_debit = None
    for m in ordered:
        total = _num(m["total_debit"])
        change = None if prev_debit is None else _num(total - prev_debit)
        result.append(
            {
                "month": m["month"],
                "total_debit": total,
                "by_category": m["by_category"],
                "change_vs_prev": change,
            }
        )
        prev_debit = total
    return result


def detect_subscriptions(
    transactions: list[dict],
    min_months: int = MIN_SUBSCRIPTION_MONTHS,
    tolerance: float = SUBSCRIPTION_TOLERANCE,
) -> list[dict]:
    """识别订阅/固定支出：同商户 ≥min_months 个不同月份，且各月金额偏差 ≤tolerance。"""
    debit_by_merchant: dict[str, list[dict]] = {}
    for t in transactions:
        if t.get("type") != "DEBIT":
            continue
        debit_by_merchant.setdefault(t.get("merchant", ""), []).append(t)

    subscriptions = []
    for merchant, txs in debit_by_merchant.items():
        by_month: dict[str, float] = {}
        for t in txs:
            month = _month_of(t["txDate"])
            by_month[month] = _num(by_month.get(month, 0.0) + _num(t.get("amount", 0)))
        if len(by_month) < min_months:
            continue
        amounts = list(by_month.values())
        avg = _num(sum(amounts) / len(amounts))
        if avg <= 0:
            continue
        if any(abs(a - avg) > avg * tolerance for a in amounts):
            continue
        last = max(txs, key=lambda t: t["txDate"])
        subscriptions.append(
            {
                "merchant": merchant,
                "monthly_avg": avg,
                "months_count": len(by_month),
                "last_amount": _num(last.get("amount", 0)),
                "last_date": _date_of(last["txDate"]),
            }
        )
    return sorted(subscriptions, key=lambda s: s["monthly_avg"], reverse=True)


def filter_pending(transactions: list[dict]) -> list[dict]:
    """未分类交易投影（tx_id/merchant/amount/cardLast4/txTime），按交易时间升序。"""
    pending = [t for t in transactions if t.get("categoryId") is None]
    # 同日无 txTime（月账单来源）排在有时间的之后
    pending.sort(key=lambda t: (t.get("txDate") or "", t.get("txTime") is None, t.get("txTime") or ""))
    return [
        {
            "tx_id": t.get("id"),
            "merchant": t.get("merchant", ""),
            "amount": _num(t.get("amount", 0)),
            "cardLast4": t.get("cardLast4"),
            "txTime": t.get("txTime"),
        }
        for t in pending
    ]
