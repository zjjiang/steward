"""FinanceBackend 测试：配置解析 + 错误转译。全部注入 fake client，零子进程。"""

import os
from types import SimpleNamespace

import pytest
from fastmcp.exceptions import ToolError

from app.finance import backend as backend_mod
from app.finance.backend import FinanceBackend, close_backend, get_backend, resolve_config

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------- 配置解析 ----------


class TestResolveConfig:
    def test_defaults(self):
        credi_dir, cmd = resolve_config({})
        assert credi_dir == os.path.expanduser("~/Projects/credi-insights")
        assert cmd == ["npx", "tsx", "mcp-server.ts"]

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("STEWARD_CREDI_DIR", "/srv/credi")
        monkeypatch.setenv("STEWARD_CREDI_CMD", '["node", "mcp-server.js"]')
        assert resolve_config() == ("/srv/credi", ["node", "mcp-server.js"])

    def test_bad_cmd_rejected(self, monkeypatch):
        monkeypatch.setenv("STEWARD_CREDI_CMD", "npx tsx")  # 不是 JSON 数组
        with pytest.raises(ValueError, match="STEWARD_CREDI_CMD"):
            resolve_config()


# ---------- call 与错误转译 ----------


def make_result(data=None, text=None, is_error=False):
    content = [] if text is None else [SimpleNamespace(text=text)]
    return SimpleNamespace(data=data, content=content, is_error=is_error)


class FakeClient:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = []

    async def call_tool(self, tool, arguments=None):
        self.calls.append((tool, arguments))
        if isinstance(self.behavior, Exception):
            raise self.behavior
        return self.behavior


def make_client(behavior):
    return FinanceBackend(client=FakeClient(behavior))


class TestCall:
    async def test_success_returns_data(self):
        backend = make_client(make_result(data={"cards": [{"id": "c1"}]}))
        out = await backend.call("list_cards")
        assert out == {"cards": [{"id": "c1"}]}

    async def test_text_json_fallback(self):
        # 上游是裸 MCP server，只返回 text content（JSON 字符串）
        backend = make_client(make_result(data=None, text='{"totalDebit": 100}'))
        assert await backend.call("get_stats", {"cardId": "c1", "period": "2026-10"}) == {
            "totalDebit": 100
        }

    async def test_upstream_tool_error_translated(self):
        backend = make_client(ToolError("Error: Rate limit: please wait 60s"))
        with pytest.raises(ToolError, match="财务数据源不可用：Error: Rate limit"):
            await backend.call("sync_card", {"cardId": "c1"})

    async def test_connection_failure_translated(self):
        backend = make_client(ConnectionError("spawn npx ENOENT"))
        with pytest.raises(ToolError, match="财务数据源不可用"):
            await backend.call("list_cards")

    async def test_is_error_result_translated(self):
        backend = make_client(make_result(text="Error: Card not found: x", is_error=True))
        with pytest.raises(ToolError, match="财务数据源不可用：Error: Card not found"):
            await backend.call("sync_card", {"cardId": "x"})


# ---------- 单例与关闭 ----------


class TestSingleton:
    async def test_get_backend_singleton(self, monkeypatch):
        monkeypatch.setattr(backend_mod, "_backend", None)
        assert get_backend() is get_backend()
        await close_backend()
        assert backend_mod._backend is None

    async def test_config_from_env(self, monkeypatch):
        monkeypatch.setattr(backend_mod, "_backend", None)
        monkeypatch.setenv("STEWARD_CREDI_DIR", "/srv/credi")
        instance = get_backend()
        assert instance.credi_dir == "/srv/credi"
        await close_backend()
