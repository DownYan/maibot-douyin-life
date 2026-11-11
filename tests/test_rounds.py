import pytest

from config import DouyinLifeConfig
from services.generation import GenerationService
from services.ledger import Ledger
from services.memory import MemoryStore
from services.rounds import RoundService
from services.tooling import ToolService
from services.writes import WriteService


class Personality:
    async def get_current(self): return {"personality": "自然", "reply_style": "短句"}


class LLM:
    async def generate(self, prompt, **kwargs): return {"success": True, "response": "这段挺有意思"}


class Ctx:
    personality = Personality()
    llm = LLM()
    logger = None


class FakeMcp:
    def __init__(self, items, write_result=None):
        self.items = items
        self.write_result = write_result or {"ok": True, "verified": True}
        self.calls = []

    async def call(self, name, args, timeout=45):
        self.calls.append((name, args))
        if name == "douyin_feed": return {"ok": True, "items": self.items}
        if name == "douyin_comments": return {"ok": True, "items": [{"cid": "c1", "text": "不错"}]}
        if name == "douyin_watch": return {"ok": True, "transcript": "视频正文", "frames": ["frame-1"], "silentAudio": True}
        return self.write_result


def make_round(tmp_path, items, write_result=None):
    config = DouyinLifeConfig()
    config.daily.keywords = ["猫"]
    mcp = FakeMcp(items, write_result)
    ledger = Ledger(tmp_path)
    memory = MemoryStore(tmp_path)
    tools = ToolService(config, mcp, ledger, memory, tmp_path)
    writes = WriteService(config, mcp, ledger, memory)
    service = RoundService(config, tools, writes, ledger, memory, GenerationService(Ctx()), tmp_path)
    return service, config, mcp


@pytest.mark.asyncio
async def test_round_filters_and_writes_report(tmp_path):
    items = [
        {"aweme_id": "long", "title": "猫长视频", "duration": 3700},
        {"aweme_id": "live", "title": "猫直播", "is_live": True},
        {"aweme_id": "ok", "title": "猫咪日常", "duration": 30},
    ]
    service, _, mcp = make_round(tmp_path, items)

    result = await service.run()

    assert result["ok"] is True
    assert result["picked"] == ["ok"]
    report = (tmp_path / "out" / __import__("datetime").datetime.now().strftime("%Y-%m-%d.md")).read_text(encoding="utf-8")
    assert "### ok" in report
    assert not any(call[0] == "douyin_like" for call in mcp.calls)


@pytest.mark.asyncio
async def test_round_does_only_one_primary_action(tmp_path):
    service, config, mcp = make_round(tmp_path, [{"aweme_id": "v1", "title": "猫", "duration": 20}])
    config.interaction.auto_like = True
    config.interaction.auto_comment = True
    config.interaction.mention_name = "主人"

    result = await service.run(automatic=True)
    write_names = [name for name, _ in mcp.calls if name in {"douyin_like", "douyin_comment", "douyin_share_video"}]

    assert result["picked"] == ["v1"]
    assert write_names == ["douyin_comment"]


@pytest.mark.asyncio
async def test_unknown_action_is_not_reported_as_success(tmp_path):
    service, config, _ = make_round(tmp_path, [{"aweme_id": "v1", "title": "猫", "duration": 20}], {"ok": True, "verified": False, "status": "unknown"})
    config.interaction.auto_like = True

    result = await service.run(automatic=True)

    assert result["actions"][0]["status"] == "unknown"
    assert result["actions"][0]["verified"] is False


@pytest.mark.asyncio
async def test_manual_round_still_allows_reading_when_automatic_daily_limit_is_zero(tmp_path):
    service, config, _ = make_round(tmp_path, [{"aweme_id": "v1", "title": "猫", "duration": 20}])
    config.daily.per_day = 0

    result = await service.run(automatic=False)

    assert result["ok"] is True
    assert result["picked"] == ["v1"]
