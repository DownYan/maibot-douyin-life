import pytest

from config import DouyinLifeConfig
from services.ledger import Ledger
from services.memory import MemoryStore
from services.tooling import ToolService


class FakeMcp:
    def __init__(self, response=None):
        self.response = response or {"ok": True, "items": []}
        self.calls = []

    async def call(self, name, args, timeout=45):
        self.calls.append((name, args, timeout))
        return self.response


def make_service(tmp_path, response=None):
    mcp = FakeMcp(response)
    service = ToolService(DouyinLifeConfig(), mcp, Ledger(tmp_path), MemoryStore(tmp_path), tmp_path)
    return service, mcp


@pytest.mark.asyncio
async def test_search_maps_keyword_and_number(tmp_path):
    service, mcp = make_service(tmp_path)
    result = await service.dispatch("dy_search", {"keyword": "猫", "num": 3})

    assert result["success"] is True
    assert mcp.calls[0][0] == "douyin_search"
    assert mcp.calls[0][1] == {"keyword": "猫", "num": 3, "order": "general"}


@pytest.mark.asyncio
async def test_need_login_is_structured_failure(tmp_path):
    service, _ = make_service(tmp_path, {"ok": False, "needLogin": True, "hint": "请登录"})
    result = await service.dispatch("dy_whoami", {})
    assert result["success"] is False
    assert result["needLogin"] is True


@pytest.mark.asyncio
async def test_config_is_read_only_and_has_no_persona_override(tmp_path):
    service, mcp = make_service(tmp_path)
    result = await service.dispatch("dy_config", {"patch": {"personaPrompt": "别的角色"}})

    assert result["success"] is True
    assert "personaPrompt" not in str(result["config"])
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_feed_uses_live_skip_setting(tmp_path):
    service, mcp = make_service(tmp_path)
    await service.dispatch("dy_feed", {"num": 4, "scrolls": 2})
    assert mcp.calls[0][1]["skip_live"] is True


@pytest.mark.asyncio
async def test_remember_writes_local_memory(tmp_path):
    service, _ = make_service(tmp_path)
    result = await service.dispatch("dy_remember", {"line": "记住这件事"})
    assert result["ok"] is True
    assert service.memory.recent() == ["记住这件事"]
