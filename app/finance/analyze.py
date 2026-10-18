"""finance 分析纯函数：跨卡汇总、趋势对比、订阅识别、待确认清单。

只吃上游响应形状的 dict/list（get_stats / get_transactions），不碰网络与数据库。
注意：上游 get_transactions 的 amount 经 JSON 序列化是字符串（Prisma Decimal），
所有金额入口统一经 _num 归一。
"""

from datetime import date

MIN_SUBSCRIPTION_MONTHS = 3
SUBSCRIPTION_TOLERANCE = 0.20
TOP_MERCHANTS_LIMIT = 5


def _num(value) -> float:
    """金额归一：字符串/数字 → 两位小数 float。"""
    return round(float(value), 2)


def _month_of(tx_date: str) -> str:
    return tx_date[:7]


def _date_of(tx_date: str) -> str:
    return tx_date[:10]


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
    """未分类交易投影（tx_id/merchant/amount/cardLast4/txTime），按交易时间升序。

    上游 v1.1.0 不回 categoryId，未分类以 category 缺失/None 表达，两种形状都认。
    """
    pending = [
        t for t in transactions
        if t.get("categoryId") is None and t.get("category") is None
    ]
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


def summarize_transactions(transactions: list[dict]) -> dict:
    """任意时间窗口的交易汇总（get_transactions 响应 → totals/分类/Top 商户）。

    与 merge_card_stats 的区别：不依赖上游按月的 get_stats，周/月同一代码路径。
    分类按 category.name 归组，无分类计"未分类"。
    """
    total_debit = 0.0
    total_credit = 0.0
    by_category: dict[str, float] = {}
    merchants: dict[str, float] = {}
    for t in transactions:
        amount = _num(t.get("amount", 0))
        if t.get("type") == "DEBIT":
            total_debit = _num(total_debit + amount)
            category = (t.get("category") or {}).get("name") or "未分类"
            by_category[category] = _num(by_category.get(category, 0.0) + amount)
            merchant = t.get("merchant", "")
            merchants[merchant] = _num(merchants.get(merchant, 0.0) + amount)
        else:
            total_credit = _num(total_credit + amount)
            # 退款冲抵消费（还款类 CREDIT 不是退款，只计入 total_credit）
            if "还款" not in (t.get("merchant") or ""):
                total_debit = _num(total_debit - amount)
    top_merchants = [
        {"merchant": name, "amount": amount}
        for name, amount in sorted(merchants.items(), key=lambda kv: kv[1], reverse=True)
    ][:TOP_MERCHANTS_LIMIT]
    return {
        "total_debit": total_debit,
        "total_credit": total_credit,
        "transaction_count": len(transactions),
        "by_category": by_category,
        "top_merchants": top_merchants,
    }


def normalize_transactions(transactions: list[dict] | None) -> list[dict]:
    """上游交易 → 内部统一形状（txDate/category{name}/categoryId/cardLast4/txTime）。

    credi-insights v1.1.0 起 get_transactions 返回 date（YYYY-MM-DD）、amount 数字、
    category 名字符串；本函数同时兼容旧形状（txDate/category 对象），下游纯函数
    只认统一形状。
    """
    normalized: list[dict] = []
    for t in transactions or []:
        category = t.get("category")
        if isinstance(category, str):
            category = None if category == "未分类" else {"name": category}
        normalized.append(
            {
                "id": t.get("id"),
                "txDate": t.get("txDate") or t.get("date") or "",
                "txTime": t.get("txTime"),
                "merchant": t.get("merchant", ""),
                "amount": t.get("amount", 0),
                "type": t.get("type", "DEBIT"),
                "cardLast4": t.get("cardLast4"),
                "categoryId": t.get("categoryId"),
                "category": category,
            }
        )
    return normalized


def months_covering(start: str, end: str) -> list[str]:
    """[start, end] 日期窗口覆盖的 YYYY-MM 列表（升序，通常 1-2 个）。"""
    first = date.fromisoformat(start[:10])
    last = date.fromisoformat(end[:10])
    months = []
    y, m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months
