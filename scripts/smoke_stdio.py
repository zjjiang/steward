"""stdio 冒烟：以子进程方式启动 MCP server，走"记录 → 查询 → 原话追溯"全链路。

用法：uv run python scripts/smoke_stdio.py
"""

import asyncio
import os
import tempfile
import uuid

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="steward-smoke-")
    env = {**os.environ, "STEWARD_DB": os.path.join(tmp, "smoke.db")}
    transport = StdioTransport("uv", ["run", "python", "-m", "app.mcp_server"], env=env)

    marker = f"冒烟测试 {uuid.uuid4().hex[:8]}"
    async with Client(transport) as client:
        server_info = client.server_info
        print(f"server: {server_info.name} {server_info.version}")

        logged = await client.call_tool(
            "log_event",
            {
                "type": "workout",
                "payload": {"sport": "run", "distance_km": 8},
                "raw_text": marker,
            },
        )
        event_id = logged.data["id"]
        print(f"log_event → id={event_id}")

        queried = await client.call_tool("query_events", {"type": "workout"})
        assert queried.data["total"] == 1, "应有 1 条 workout"
        assert queried.data["items"][0]["raw_text"] == marker, "原话应原样保留"
        print("query_events → total=1, 原话追溯 OK")

    print("smoke passed ✅")


if __name__ == "__main__":
    asyncio.run(main())
