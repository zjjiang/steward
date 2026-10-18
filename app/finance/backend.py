"""FinanceBackend：credi-insights MCP server（stdio 子进程）客户端封装。

- 懒加载：首次 call 才启动子进程并进入会话，进程级复用
- 错误转译：连接失败 / 上游报错统一为 ToolError("财务数据源不可用：<原因>")
- 配置：STEWARD_CREDI_DIR（默认 ~/Projects/credi-insights）、
  STEWARD_CREDI_CMD（JSON 数组，默认 ["npx", "tsx", "mcp-server.ts"]）
"""

import json
import os

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError

DEFAULT_CREDI_DIR = "~/Projects/credi-insights"
DEFAULT_CREDI_CMD = ["npx", "tsx", "mcp-server.ts"]
UNAVAILABLE_PREFIX = "财务数据源不可用"


def resolve_config(env: dict | None = None) -> tuple[str, list[str]]:
    """解析数据源配置，返回 (credi_dir, cmd)。"""
    env = os.environ if env is None else env
    credi_dir = env.get("STEWARD_CREDI_DIR", DEFAULT_CREDI_DIR)
    raw_cmd = env.get("STEWARD_CREDI_CMD", json.dumps(DEFAULT_CREDI_CMD))
    try:
        cmd = json.loads(raw_cmd)
    except json.JSONDecodeError as e:
        raise ValueError(f"STEWARD_CREDI_CMD 必须是 JSON 数组：{e}") from e
    if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
        raise ValueError('STEWARD_CREDI_CMD 必须是字符串数组，如 ["npx", "tsx", "mcp-server.ts"]')
    return os.path.expanduser(credi_dir), cmd


class FinanceBackend:
    """单个上游工具调用的最小封装；client 参数为测试注入点。"""

    def __init__(self, credi_dir: str | None = None, cmd: list[str] | None = None, client=None):
        default_dir, default_cmd = resolve_config()
        self.credi_dir = credi_dir or default_dir
        self.cmd = cmd or default_cmd
        self._injected = client
        self._client = client
        self._entered = False

    async def _get_client(self):
        if self._client is None:
            # FastMCP StdioTransport 不传 env 时子进程只拿到精简环境，会丢 DATABASE_URL；
            # 这里显式继承当前环境并从 credi-insights/.env 兜底注入 DATABASE_URL（子进程连 MySQL 需要）。
            env = dict(os.environ)
            dotenv = os.path.join(self.credi_dir, ".env")
            if "DATABASE_URL" not in env and os.path.exists(dotenv):
                with open(dotenv, encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("DATABASE_URL="):
                            env["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            transport = StdioTransport(self.cmd[0], self.cmd[1:], cwd=self.credi_dir, env=env)
            self._client = Client(transport)
        if not self._entered and self._injected is None:
            # 注入的 client（测试）视为已就绪，不做上下文管理
            await self._client.__aenter__()
            self._entered = True
        return self._client

    async def call(self, tool: str, arguments: dict | None = None):
        """调用上游工具，返回解析后的数据。失败转译为统一中文 ToolError。"""
        try:
            client = await self._get_client()
            result = await client.call_tool(tool, arguments or {})
        except ToolError as e:
            raise self._translate(e) from e
        except Exception as e:
            raise self._translate(e) from e
        if getattr(result, "is_error", False):
            text = self._text_of(result) or "上游返回错误"
            raise self._translate(Exception(text))
        data = getattr(result, "data", None)
        if data is None:
            text = self._text_of(result)
            if text:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = text
        return data

    @staticmethod
    def _translate(err: Exception) -> ToolError:
        msg = str(err)
        if not msg.startswith(UNAVAILABLE_PREFIX):
            msg = f"{UNAVAILABLE_PREFIX}：{msg}"
        return ToolError(msg)

    @staticmethod
    def _text_of(result) -> str | None:
        for block in getattr(result, "content", None) or []:
            text = getattr(block, "text", None)
            if text:
                return text
        return None

    async def aclose(self):
        if self._entered and self._client is not None:
            await self._client.__aexit__(None, None, None)
        self._entered = False
        self._client = self._injected


_backend: FinanceBackend | None = None


def get_backend() -> FinanceBackend:
    global _backend
    if _backend is None:
        _backend = FinanceBackend()
    return _backend


async def close_backend():
    global _backend
    if _backend is not None:
        await _backend.aclose()
        _backend = None
