"""web 只读仪表盘路由：复用 MCP 工具函数与 finance 模块级辅助，零业务逻辑复制。

错误边界：入参校验失败（ToolError）→ 400；finance 上游故障 → 200 + available:false
（与 get_review 的 finance 段降级语义一致）。
"""

from fastapi import APIRouter, HTTPException
from fastmcp.exceptions import ToolError

from app.finance import analyze
from app.finance.backend import get_backend
from app.finance.tools import (
    _month_range,
    _recent_months,
    _today,
    _validate_day,
    _validate_month,
    build_card_bill,
    fetch_transactions_range,
)
from app.mcp_server import (
    get_insights,
    get_review,
    query_body,
    query_commute,
    query_meals,
    query_workouts,
)

router = APIRouter()

TREND_MONTHS = 6  # 账单页趋势/订阅回看月数


def _bad_request(e: ToolError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


@router.get("/api/day")
async def day(date: str | None = None):
    """单日流水：运动/饮食/体重/通勤明细 + 汇总（复用各查询工具）。"""
    try:
        day = _validate_day(date)
        workouts = query_workouts(date_from=day, date_to=day)
        meals = query_meals(date_from=day, date_to=day)
        bodies = query_body(date_from=day, date_to=day)
        commutes = query_commute(date_from=day, date_to=day)
    except ToolError as e:
        raise _bad_request(e)
    return {
        "date": day,
        "workouts": workouts,
        "meals": meals,
        "body": bodies,
        "commute": commutes,
    }


@router.get("/api/review")
async def review_view(period: str = "week", ref_date: str | None = None):
    """周期复盘：透传 MCP 工具 get_review（同一编排，finance 段已内部降级）。"""
    try:
        return await get_review(period=period, ref_date=ref_date)
    except ToolError as e:
        raise _bad_request(e)


@router.get("/api/insights")
async def insights_view(ref_date: str | None = None):
    """趋势洞察：透传 MCP 工具 get_insights。"""
    try:
        return await get_insights(ref_date=ref_date)
    except ToolError as e:
        raise _bad_request(e)


@router.get("/api/finance")
async def finance_overview(month: str | None = None, card: str | None = None):
    """月度账单概况：汇总 + 近 6 月趋势 + 订阅识别 + 当月待确认交易，可按卡过滤。"""
    try:
        month = _validate_month(month)
    except ToolError as e:
        raise _bad_request(e)
    try:
        be = get_backend()
        start, end = _month_range(month)
        transactions = await fetch_transactions_range(be, start, end, card_id=card)
        summary = analyze.summarize_transactions(transactions)
        summary = {
            **summary,
            "by_category": [
                {"name": name, "amount": amount}
                for name, amount in sorted(
                    summary["by_category"].items(), key=lambda kv: kv[1], reverse=True
                )
            ],
        }

        trend: list[dict] = []
        subs_transactions: list[dict] = []
        for m in _recent_months(TREND_MONTHS):
            m_start, m_end = _month_range(m)
            m_txs = await fetch_transactions_range(be, m_start, m_end, card_id=card)
            subs_transactions.extend(m_txs)
            m_summary = analyze.summarize_transactions(m_txs)
            trend.append(
                {
                    "month": m,
                    "total_debit": m_summary["total_debit"],
                    "by_category": m_summary["by_category"],
                }
            )

        pending = analyze.filter_pending(transactions)
        return {
            "month": month,
            "card": card,
            "available": True,
            "summary": summary,
            "trend": analyze.compute_trend(trend),
            "subscriptions": analyze.detect_subscriptions(subs_transactions),
            "pending": {"count": len(pending), "items": pending},
        }
    except ToolError as e:
        return {"available": False, "error": str(e)}


@router.get("/api/bills")
async def bills_overview(cycle: str | None = None):
    """各卡账单周期汇总（最近已出账期，缺省）：单卡失败降级为条目级 error。"""
    try:
        be = get_backend()
        cards = await be.call("list_cards")
    except ToolError as e:
        return {"available": False, "error": str(e)}
    bills = []
    for card in cards:
        card_id = card.get("id")
        try:
            bills.append(await build_card_bill(be, card_id, cycle, today=_today()))
        except ToolError as e:
            bills.append({"card": {"id": card_id, "bank": card.get("bank"),
                                   "cardLast4": card.get("cardLast4"), "alias": card.get("alias")},
                          "error": str(e)})
    return {"available": True, "bills": bills}
