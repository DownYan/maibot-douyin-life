import json

import pytest

from services.ledger import Ledger


@pytest.mark.asyncio
async def test_unknown_does_not_consume_success_or_allow_automatic_resend(tmp_path):
    ledger = Ledger(tmp_path)
    first = await ledger.consume("dm", "u1:m1", 5, 1, "r1")
    assert first["allowed"] is True

    await ledger.record_result("dm", "u1:m1", {"ok": True, "verified": False, "status": "unknown"})

    assert await ledger.is_processed("dm", "u1:m1") is False
    assert await ledger.count_today("dm") == 0
    retry = await ledger.consume("dm", "u1:m1", 5, 1, "r2")
    assert retry["allowed"] is False
    assert retry["reason"] == "pending"


@pytest.mark.asyncio
async def test_verified_result_counts_and_deduplicates(tmp_path):
    ledger = Ledger(tmp_path)
    await ledger.consume("like", "video-1", 5, 1, "r1")
    await ledger.record_result("like", "video-1", {"ok": True, "verified": True})

    assert await ledger.count_today("like") == 1
    assert await ledger.is_processed("like", "video-1") is True
    assert (await ledger.consume("like", "video-1", 5, 1, "r2"))["allowed"] is False
    assert json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))["schemaVersion"] == 2


@pytest.mark.asyncio
async def test_daily_and_per_run_limits(tmp_path):
    ledger = Ledger(tmp_path)
    assert (await ledger.consume("comment", "v1", 1, 1, "r1"))["allowed"]
    assert (await ledger.consume("comment", "v2", 2, 1, "r1"))["reason"] == "per_run_limit"
    assert (await ledger.consume("comment", "v2", 1, 2, "r2"))["reason"] == "daily_limit"
