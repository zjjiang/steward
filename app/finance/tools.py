"""finance MCP 工具注册：5 个语义分析 + 6 个透传/分类通道。

数据全部来自 credi-insights（经 FinanceBackend），本地不落任何财务数据。
所有上游故障已由 backend 转译为"财务数据源不可用：…"的 ToolError。
"""

import calendar
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastmcp.exceptions import ToolError

from app.finance import analyze, billing
from app.finance.backend import get_backend

TZ = ZoneInfo("Asia/Shanghai")
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_month(month: str | None) -> str:
    if month is None or not month.strip():
        return datetime.now(TZ).strftime("%Y-%m")
    month = month.strip()
    if not _MONTH_RE.match(month):
        raise ToolError(f"month 格式应为 YYYY-MM（例：2026-10），收到 {month!r}")
    return month


def _validate_day(date: str | None) -> str:
    if date is None or not date.strip():
        return datetime.now(TZ).strftime("%Y-%m-%d")
    day = date.strip()
    if not _DAY_RE.match(day):
        raise ToolError(f"date 格式应为 YYYY-MM-DD（例：2026-10-16），收到 {day!r}")
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        raise ToolError(f"date 不是合法日期：{day!r}")
    return day


def _validate_months(months: int) -> int:
    if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= 12:
        raise ToolError(f"months 必须是 1..12 的整数，收到 {months!r}")
    return months


def _require(**fields) -> None:
    for name, value in fields.items():
        if value is None or not str(value).strip():
            raise ToolError(f"{name} 不能为空")


def _month_range(month: str) -> tuple[str, str]:
    year, mon = int(month[:4]), int(month[5:7])
    last_day = calendar.monthrange(year, mon)[1]
    return f"{month}-01", f"{month}-{last_day:02d}"


def _recent_months(n: int) -> list[str]:
    """含当月的最近 n 个自然月，升序。"""
    now = datetime.now(TZ)
    out = []
    for i in range(n):
        total = now.year * 12 + now.month - 1 - i
        out.append(f"{total // 12:04d}-{total % 12 + 1:02d}")
    return sorted(out)


def _today() -> date:
    return datetime.now(TZ).date()


async def fetch_transactions_range(
    be, start: str, end: str, card_id: str | None = None
) -> list[dict]:
    """[start, end] 日期窗口内的交易（内部统一形状），可选限定单卡。

    上游 v1.1.0 的 get_transactions 只按月过滤（month 参数，limit 默认 50），
    这里按窗口展开涉及月份逐月拉取（limit=500，量级见 mod-finance design），
    归一化后按日期过滤；card_id 非空时透传上游 cardId。
    """
    transactions: list[dict] = []
    for month in analyze.months_covering(start, end):
        arguments: dict = {"month": month, "limit": 500}
        if card_id:
            arguments["cardId"] = card_id
        raw = await be.call("get_transactions", arguments)
        transactions.extend(analyze.normalize_transactions(raw))
    return [t for t in transactions if start <= t["txDate"][:10] <= end]


async def _month_transactions(be, month: str) -> list[dict]:
    start, end = _month_range(month)
    return await fetch_transactions_range(be, start, end)


def _sorted_categories(by_category: dict) -> list[dict]:
    """面向展示的形状：分类按金额降序列表。"""
    return [
        {"name": name, "amount": amount}
        for name, amount in sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
    ]


async def build_card_bill(be, card_id: str, cycle: str | None = None, today: date | None = None) -> dict:
    """单卡账单周期汇总（模块级 build_card_bill，MCP 工具与 web 共用）。

    按卡的 billingDay 算出账单期窗口，取该期该卡交易做汇总与明细投影。
    上游未返回 billingDay 时抛可读 ToolError，不按自然月兜底。
    """
    cards = await be.call("list_cards")
    card = next((c for c in cards if c.get("id") == card_id), None)
    if card is None:
        raise ToolError(f"卡片不存在：{card_id}")
    billing_day = card.get("billingDay")
    if billing_day is None:
        raise ToolError(
            "上游未返回账单日（billingDay）——需要更新 credi-insights 的 "
            "list_cards 输出（return 加 billingDay/dueDay）"
        )
    try:
        bounds = billing.cycle_bounds(billing_day, cycle or "current", today or _today())
    except ValueError as e:
        raise ToolError(str(e))

    transactions = await fetch_transactions_range(
        be, bounds["start"], bounds["end"], card_id=card_id
    )
    summary = analyze.summarize_transactions(transactions)
    items = [
        {
            "date": t.get("txDate", "")[:10],
            "merchant": t.get("merchant", ""),
            "amount": analyze._num(t.get("amount", 0)),
            "category": (t.get("category") or {}).get("name") or "未分类",
        }
        for t in transactions
    ]
    return {
        "card": {
            "id": card.get("id"),
            "bank": card.get("bank"),
            "cardLast4": card.get("cardLast4"),
            "alias": card.get("alias"),
        },
        "billing_day": billing_day,
        "due_day": card.get("dueDay"),
        "cycle": bounds["cycle"],
        "statement_date": bounds["statement_date"],
        "start": bounds["start"],
        "end": bounds["end"],
        "total_debit": summary["total_debit"],
        "total_credit": summary["total_credit"],
        "transaction_count": summary["transaction_count"],
        "by_category": _sorted_categories(summary["by_category"]),
        "items": items,
    }


def register_finance_tools(mcp) -> None:

    @mcp.tool
    async def spending_summary(month: str | None = None, card_id: str | None = None) -> dict:
        """跨所有信用卡的月度消费汇总：总支出/总收入/笔数/分类占比/Top 5 商户。

        Args:
            month: 月份（YYYY-MM），缺省当月
            card_id: 可选，仅统计某张卡（list_cards 返回的 id）
        """
        month = _validate_month(month)
        be = get_backend()
        start, end = _month_range(month)
        summary = analyze.summarize_transactions(
            await fetch_transactions_range(be, start, end, card_id=card_id)
        )
        # 面向龙虾的展示形状：分类按金额降序列表
        summary["by_category"] = _sorted_categories(summary["by_category"])
        return {"month": month, **summary}

    @mcp.tool
    async def spending_trend(months: int = 3) -> dict:
        """最近 N 个月（含当月）的逐月总支出、分类构成与环比变化。

        Args:
            months: 月数（1..12），缺省 3
        """
        months = _validate_months(months)
        be = get_backend()
        monthly = []
        for m in _recent_months(months):
            start, end = _month_range(m)
            summary = analyze.summarize_transactions(
                await fetch_transactions_range(be, start, end)
            )
            monthly.append(
                {
                    "month": m,
                    "total_debit": summary["total_debit"],
                    "by_category": summary["by_category"],
                }
            )
        return {"months": months, "items": analyze.compute_trend(monthly)}

    @mcp.tool
    async def subscriptions(months: int = 6) -> dict:
        """识别订阅/固定支出：同商户 ≥3 个月出现且金额波动 ≤20%，返回月均金额。

        Args:
            months: 回看月数（1..12），缺省 6
        """
        months = _validate_months(months)
        be = get_backend()
        transactions = []
        for m in _recent_months(months):
            transactions.extend(await _month_transactions(be, m))
        return {"months": months, "subscriptions": analyze.detect_subscriptions(transactions)}

    @mcp.tool
    async def list_cards() -> dict:
        """列出所有信用卡（银行/尾号/别名/账单日/还款日/启用状态）。"""
        return {"cards": await get_backend().call("list_cards")}

    @mcp.tool
    async def sync_card(card_id: str) -> dict:
        """同步指定卡的账单（拉取上游邮件入库），返回新增/跳过笔数。

        Args:
            card_id: list_cards 返回的卡片 id
        """
        _require(card_id=card_id)
        return await get_backend().call("sync_card", {"cardId": card_id})

    @mcp.tool
    async def list_categories() -> dict:
        """列出所有交易分类（名称/图标/颜色）。"""
        return {"categories": await get_backend().call("list_categories")}

    @mcp.tool
    async def list_rules() -> dict:
        """列出所有分类规则（含所属分类）。"""
        return {"rules": await get_backend().call("list_rules")}

    @mcp.tool
    async def create_rule(name: str, pattern: str, category_id: str) -> dict:
        """创建分类规则（命中后自动归类，如"以后美团都算餐饮"）。

        Args:
            name: 规则名
            pattern: 匹配语法同上游，例：merchant contains 美团
            category_id: list_categories 返回的分类 id
        """
        _require(name=name, pattern=pattern, category_id=category_id)
        return await get_backend().call(
            "create_rule", {"name": name, "pattern": pattern, "categoryId": category_id}
        )

    @mcp.tool
    async def classify_transaction(tx_id: str, category_id: str) -> dict:
        """给某一笔交易归类（用户单笔确认后调用）。

        Args:
            tx_id: 交易 id（见 pending_classifications）
            category_id: 分类 id
        """
        _require(tx_id=tx_id, category_id=category_id)
        return await get_backend().call(
            "update_transaction_category", {"txId": tx_id, "categoryId": category_id}
        )

    @mcp.tool
    async def auto_classify(card_id: str | None = None, dry_run: bool = True) -> dict:
        """按规则批量给未分类交易归类。缺省只预览（dry_run），与用户确认后再执行。

        Args:
            card_id: 可选，仅处理某张卡
            dry_run: true=只返回匹配预览（缺省）；false=实际执行归类
        """
        arguments: dict = {"dryRun": bool(dry_run)}
        if card_id and card_id.strip():
            arguments["cardId"] = card_id.strip()
        return await get_backend().call("apply_rules", arguments)

    @mcp.tool
    async def pending_classifications(date: str | None = None, card_id: str | None = None) -> dict:
        """列出某日未分类交易（每日账单同步后，把规则没吃掉的列给用户确认）。

        Args:
            date: 日期（YYYY-MM-DD），缺省今天
            card_id: 可选，仅看某张卡
        """
        day = _validate_day(date)
        transactions = await fetch_transactions_range(get_backend(), day, day, card_id=card_id)
        items = analyze.filter_pending(transactions)
        return {"date": day, "count": len(items), "items": items}

    @mcp.tool
    async def card_bill(card_id: str, cycle: str | None = None) -> dict:
        """单卡账单周期汇总：按账单日算周期（出账日→下个出账日前一日），
        返回该期总支出/分类构成/明细与出账日、还款日。还款口径，与自然月工具并存。

        Args:
            card_id: list_cards 返回的卡片 id
            cycle: current（最近已出账期，缺省）/ previous / YYYY-MM（出账月）
        """
        _require(card_id=card_id)
        return await build_card_bill(get_backend(), card_id.strip(), cycle)
