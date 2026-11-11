import asyncio

import pytest

from config import DouyinLifeConfig
from services.direct_messages import DirectMessageService
from services.comments import CommentService
from services.generation import GenerationService
from services.ledger import Ledger
from services.memory import MemoryStore
from services.scheduler import Scheduler
from services.tooling import ToolService
from services.writes import WriteService


class Personality:
    async def get_current(self): return {"personality": "温和", "private_chat_prompts": "像朋友"}


class LLM:
    async def generate(self, prompt, **kwargs): return {"success": True, "response": "晚安呀"}


class Ctx:
    personality = Personality()
    llm = LLM()
    logger = None


class FakeMcp:
    def __init__(self, inbox=None, comments=None, send_result=None):
        self.inbox = inbox or []
        self.comments = comments or []
        self.send_result = send_result or {"ok": True, "verified": True}
        self.calls = []

    async def call(self, name, args, timeout=45):
        self.calls.append((name, args))
        if name == "douyin_inbox": return {"ok": True, "items": self.inbox}
        if name == "douyin_my_posts": return {"ok": True, "items": [{"aweme_id": "own-video"}]}
        if name == "douyin_comments": return {"ok": True, "items": self.comments}
        return self.send_result


def make_dm(tmp_path, inbox, send_result=None):
    config = DouyinLifeConfig()
    config.interaction.msg_allow_to = "小明"
    mcp = FakeMcp(inbox=inbox, send_result=send_result)
    ledger = Ledger(tmp_path)
    memory = MemoryStore(tmp_path)
    tools = ToolService(config, mcp, ledger, memory, tmp_path)
    writes = WriteService(config, mcp, ledger, memory)
    return DirectMessageService(config, tools, writes, GenerationService(Ctx()), memory, ledger), mcp


@pytest.mark.asyncio
async def test_dm_replies_only_to_allowlist_and_deduplicates(tmp_path):
    service, mcp = make_dm(tmp_path, [
        {"name": "小明", "messageId": "m1", "direction": "inbound", "text": "晚安"},
        {"name": "别人", "messageId": "m2", "direction": "inbound", "text": "你好"},
    ])
    first = await service.poll()
    second = await service.poll()

    assert first["replied"] == 1
    assert second["replied"] == 0
    assert len([c for c in mcp.calls if c[0] == "douyin_chat_send"]) == 1


@pytest.mark.asyncio
async def test_video_card_without_id_never_calls_watch(tmp_path):
    service, mcp = make_dm(tmp_path, [{"name": "小明", "messageId": "m1", "direction": "inbound", "isVideo": True, "text": "[视频卡片]"}])
    await service.poll()
    assert not any(call[0] == "douyin_watch" for call in mcp.calls)


@pytest.mark.asyncio
async def test_unknown_dm_is_not_counted_as_replied(tmp_path):
    service, _ = make_dm(tmp_path, [{"name": "小明", "messageId": "m1", "direction": "inbound", "text": "在吗"}], {"ok": True, "verified": False, "status": "unknown"})
    result = await service.poll()
    assert result["replied"] == 0
    assert result["pending"] == 1


@pytest.mark.asyncio
async def test_comments_skip_self_and_note(tmp_path):
    config = DouyinLifeConfig()
    config.interaction.auto_reply = True
    config.interaction.my_nickname = "麦麦"
    mcp = FakeMcp(comments=[
        {"cid": "self", "user": "麦麦", "text": "自己的"},
        {"cid": "note", "user": "别人", "text": "图文", "aweme_type": 68},
    ])
    ledger = Ledger(tmp_path)
    memory = MemoryStore(tmp_path)
    tools = ToolService(config, mcp, ledger, memory, tmp_path)
    writes = WriteService(config, mcp, ledger, memory)
    service = CommentService(config, tools, writes, GenerationService(Ctx()), ledger)

    result = await service.poll()
    assert result["replied"] == 0
    assert not any(call[0] == "douyin_comment" for call in mcp.calls)


@pytest.mark.asyncio
async def test_scheduler_close_cancels_tasks():
    scheduler = Scheduler(DouyinLifeConfig())
    await scheduler.start()
    tasks = list(scheduler.tasks)
    await scheduler.close()
    assert tasks
    assert all(task.cancelled() or task.done() for task in tasks)
    await scheduler.close()


@pytest.mark.asyncio
async def test_streak_uses_stable_daily_ledger_key(tmp_path):
    config = DouyinLifeConfig()
    config.interaction.msg_allow_to = "小明"
    config.interaction.streak_nick = "小明"
    mcp = FakeMcp()
    ledger = Ledger(tmp_path)
    writes = WriteService(config, mcp, ledger, MemoryStore(tmp_path))
    scheduler = Scheduler(config, writes=writes)

    await scheduler.streak_once()
    await scheduler.streak_once()

    assert len([call for call in mcp.calls if call[0] == "douyin_chat_sticker"]) == 1
    assert await ledger.count_today("sticker") == 1
