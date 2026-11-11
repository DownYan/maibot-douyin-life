import asyncio

import pytest

from services.rounds import RoundService


@pytest.mark.asyncio
async def test_round_reentry_is_rejected():
    service = object.__new__(RoundService)
    service._lock = asyncio.Lock()
    service._run_once = lambda **kwargs: asyncio.sleep(0.05)

    first = asyncio.create_task(service.run())
    await asyncio.sleep(0)
    second = await service.run()
    await first

    assert second["ok"] is False
    assert "运行" in second["error"]
