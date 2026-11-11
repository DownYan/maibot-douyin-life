import pytest

from config import DouyinLifeConfig
from services.ledger import Ledger
from services.memory import MemoryStore
from services.writes import WriteService


class FakeMcp:
    def __init__(self, response=None):
        self.response = response or {"ok": True, "verified": True}
        self.calls = []

    async def call(self, name, args, timeout=45):
        self.calls.append((name, args))
        return self.response


def make_service(tmp_path, response=None):
    config = DouyinLifeConfig()
    mcp = FakeMcp(response)
    return WriteService(config, mcp, Ledger(tmp_path), MemoryStore(tmp_path)), config, mcp


def test_automatic_force_cannot_bypass_gate(tmp_path):
    service, _, _ = make_service(tmp_path)
    result = service.authorize("like", force=True, automatic=True)
    assert result["allowed"] is False


@pytest.mark.asyncio
async def test_like_gate_and_verified_ledger(tmp_path):
    service, config, mcp = make_service(tmp_path)
    blocked = await service.like("v1")
    assert blocked["blocked"] is True
    assert mcp.calls == []

    config.interaction.auto_like = True
    result = await service.like("v1", automatic=True)
    assert result["ok"] is True
    assert await service.ledger.count_today("like") == 1


@pytest.mark.asyncio
async def test_mention_comment_requires_switch_and_nickname(tmp_path):
    service, config, mcp = make_service(tmp_path)
    config.interaction.auto_comment = True
    result = await service.comment("v1", "好看", automatic=True)
    assert result["allowed"] is False if "allowed" in result else result["blocked"]
    assert mcp.calls == []

    config.interaction.mention_name = "主人"
    result = await service.comment("v1", "好看", automatic=True)
    assert mcp.calls[0][1]["mention"] == "主人"
    assert "@主人" in result["text"]


@pytest.mark.asyncio
async def test_direct_message_requires_exact_allowlist(tmp_path):
    service, config, mcp = make_service(tmp_path)
    config.interaction.msg_allow_to = "小明,小红"
    assert (await service.chat_send("小明", "你好"))["ok"] is True
    assert (await service.chat_send("小明2", "你好"))["blocked"] is True
    assert len(mcp.calls) == 1


@pytest.mark.asyncio
async def test_unknown_result_is_not_counted_or_resent(tmp_path):
    service, config, _ = make_service(tmp_path, {"ok": True, "verified": False, "status": "unknown"})
    config.interaction.auto_like = True
    first = await service.like("v1", automatic=True)
    second = await service.like("v1", automatic=True)

    assert first["status"] == "unknown"
    assert second["blocked"] is True
    assert await service.ledger.count_today("like") == 0


@pytest.mark.asyncio
async def test_publish_defaults_to_draft(tmp_path):
    service, config, mcp = make_service(tmp_path)
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")
    config.publish.auto_publish = True

    await service.publish(video_path=str(video), automatic=True)

    assert mcp.calls[0][0] == "douyin_publish"
    assert mcp.calls[0][1]["draft"] is True


@pytest.mark.asyncio
async def test_reply_to_stranger_uses_dm_reply_gate_not_proactive_allowlist(tmp_path):
    service, config, mcp = make_service(tmp_path)
    config.dm.dm_reply = True

    result = await service.chat_send("陌生人", "你好", automatic=True, responding=True, ledger_key="message-1")

    assert result["ok"] is True
    assert mcp.calls[0][1]["nickname"] == "陌生人"
