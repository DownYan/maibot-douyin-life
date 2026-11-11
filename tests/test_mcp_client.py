import asyncio
import json

import pytest

from config import DouyinLifeConfig
from services.mcp_client import McpClient


class FakeTransport:
    def __init__(self, hang=False, response=None):
        self.hang = hang
        self.response = response
        self.closed = False

    async def request(self, method, params, timeout):
        if self.hang:
            await asyncio.sleep(1)
        return self.response or {"content": [{"type": "text", "text": json.dumps({"ok": True, "echo": params})}]}

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_call_returns_structured_timeout():
    client = McpClient(transport=FakeTransport(hang=True))
    result = await client.call("douyin_feed", {}, timeout=0.01)
    assert result["ok"] is False
    assert "超时" in result["error"]


@pytest.mark.asyncio
async def test_call_unwraps_mcp_json_and_close_is_idempotent():
    transport = FakeTransport()
    client = McpClient(transport=transport)
    result = await client.call("douyin_search", {"keyword": "猫"})

    assert result["ok"] is True
    assert result["echo"]["arguments"]["keyword"] == "猫"
    await client.close()
    await client.close()
    assert transport.closed is True


@pytest.mark.asyncio
async def test_non_object_payload_is_an_error():
    response = {"content": [{"type": "text", "text": "not-json"}]}
    result = await McpClient(transport=FakeTransport(response=response)).call("douyin_feed", {})
    assert result["ok"] is False
    assert "返回" in result["error"]


@pytest.mark.asyncio
async def test_need_login_is_preserved():
    response = {"content": [{"type": "text", "text": json.dumps({"ok": False, "needLogin": True})}]}
    result = await McpClient(transport=FakeTransport(response=response)).call("douyin_search", {})
    assert result["needLogin"] is True
    assert result["ok"] is False


def test_kernel_write_gate_is_delegated_to_verified_host_service(tmp_path):
    client = McpClient(tmp_path / "data", tmp_path / "runtime", DouyinLifeConfig())
    env = client._build_transport().env
    assert env["MAIBOT_DOUYIN_HOME"] == str(tmp_path / "data")
    assert env["DOUYIN_ALLOW_WRITES"] == "1"
