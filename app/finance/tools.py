"""finance MCP 工具注册：5 个语义分析 + 6 个透传/分类通道。

数据全部来自 credi-insights（经 FinanceBackend），本地不落任何财务数据。
所有上游故障已由 backend 转译为"财务数据源不可用：…"的 ToolError。
"""

import calendar
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from fastmcp.exceptions import ToolError

from app.finance import analyze
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


async def fetch_transactions_range(be, start: str, end: str) -> list[dict]:
    """[start, end] 日期窗口内的交易（内部统一形状）。

    上游 v1.1.0 的 get_transactions 只按月过滤（month 参数，limit 默认 50），
    这里按窗口展开涉及月份逐月拉取（limit=500，量级见 mod-finance design），
    归一化后按日期过滤。
    """
    transactions: list[dict] = []
    for month in analyze.months_covering(start, end):
        raw = await be.call("get_transactions", {"month": month, "limit": 500})
        transactions.extend(analyze.normalize_transactions(raw))
    return [t for t in transactions if start <= t["txDate"][:10] <= end]


async def _month_transactions(be, month: str) -> list[dict]:
    start, end = _month_range(month)
    return await fetch_transactions_range(be, start, end)


def register_finance_tools(mcp) -> None:

    @mcp.tool
    async def spending_summary(month: str | None = None) -> dict:
        """跨所有信用卡的月度消费汇总：总支出/总收入/笔数/分类占比/Top 5 商户。

        Args:
            month: 月份（YYYY-MM），缺省当月
        """
        month = _validate_month(month)
        be = get_backend()
        start, end = _month_range(month)
        summary = analyze.summarize_transactions(await fetch_transactions_range(be, start, end))
        # 面向龙虾的展示形状：分类按金额降序列表
        summary["by_category"] = [
            {"name": name, "amount": amount}
            for name, amount in sorted(
                summary["by_category"].items(), key=lambda kv: kv[1], reverse=True
            )
        ]
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
    async def pending_classifications(date: str | None = None) -> dict:
        """列出某日未分类交易（每日账单同步后，把规则没吃掉的列给用户确认）。

        Args:
            date: 日期（YYYY-MM-DD），缺省今天
        """
        day = _validate_day(date)
        transactions = await fetch_transactions_range(get_backend(), day, day)
        items = analyze.filter_pending(transactions)
        return {"date": day, "count": len(items), "items": items}
