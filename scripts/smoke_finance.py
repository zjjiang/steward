"""finance 真实链路冒烟：经 stdio 连 credi-insights（需其 node_modules 与 .env 就绪）。

前置：~/Projects/credi-insights 已 uv… 即 npm install && prisma generate，.env 含 DATABASE_URL。
用法：uv run python scripts/smoke_finance.py
（只读操作：不触发 sync_card，不改任何数据。）
"""

import asyncio
import os

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main() -> None:
    transport = StdioTransport("uv", ["run", "python", "-m", "app.mcp_server"], env={**os.environ})
    async with Client(transport) as client:
        cards = (await client.call_tool("list_cards", {})).data["cards"]
        print(f"list_cards → {len(cards)} 张卡：")
        for c in cards:
            print(f"  - {c.get('bank')} *{c.get('cardLast4')} {c.get('alias') or ''}")

        summary = (await client.call_tool("spending_summary", {})).data
        print(
            f"spending_summary({summary['month']}) → 支出 {summary['total_debit']} / "
            f"收入 {summary['total_credit']} / {summary['transaction_count']} 笔"
        )
        for cat in summary["by_category"][:5]:
            print(f"  - {cat['name']}: {cat['amount']} ({cat['count']} 笔)")

        pending = (await client.call_tool("pending_classifications", {})).data
        print(f"pending_classifications({pending['date']}) → {pending['count']} 笔待分类")
        for item in pending["items"][:5]:
            print(f"  - {item['merchant']} ¥{item['amount']} 卡{item['cardLast4']}")

        subs = (await client.call_tool("subscriptions", {})).data["subscriptions"]
        print(f"subscriptions → {len(subs)} 个疑似订阅")
        for s in subs[:5]:
            print(f"  - {s['merchant']} ¥{s['monthly_avg']}/月 × {s['months_count']} 个月")

    print("finance smoke passed ✅")


if __name__ == "__main__":
    asyncio.run(main())
