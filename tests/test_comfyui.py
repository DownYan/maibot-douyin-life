import os

import pytest

from config import DouyinLifeConfig
from services.comfyui import ComfyUIService


def test_list_recent_only_returns_sorted_real_mp4(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    older = output / "older.mp4"
    newer = output / "nested" / "newer.MP4"
    newer.parent.mkdir()
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    (output / "ignore.png").write_bytes(b"image")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    service = ComfyUIService(DouyinLifeConfig(), output_dir=output)

    result = service.list_recent(10)

    assert result["exists"] is True
    assert [item["name"] for item in result["items"]] == ["newer.MP4", "older.mp4"]


def test_missing_comfy_output_is_structured(tmp_path):
    service = ComfyUIService(DouyinLifeConfig(), output_dir=tmp_path / "missing")
    assert service.list_recent()["exists"] is False


@pytest.mark.asyncio
async def test_workflow_only_accepts_video_for_current_prompt(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    expected = output / "current.mp4"
    expected.write_bytes(b"video")
    (output / "other.mp4").write_bytes(b"other")
    calls = []

    async def request(method, url, payload=None, timeout=15):
        calls.append((method, url, payload))
        if url.endswith("/prompt"):
            return {"prompt_id": "prompt-current"}
        return {"prompt-current": {"status": {"completed": True}, "outputs": {"9": {"videos": [{"type": "output", "filename": "current.mp4", "subfolder": ""}]}}}}

    service = ComfyUIService(DouyinLifeConfig(), output_dir=output, request=request, poll_interval=0)
    result = await service.submit_and_wait('{"1": {"class_type": "Test"}}', timeout=1)

    assert result["ok"] is True
    assert result["video"] == str(expected)
    assert result["promptId"] == "prompt-current"
    assert calls[0][0] == "POST"


@pytest.mark.asyncio
async def test_workflow_timeout_does_not_fall_back_to_unrelated_video(tmp_path):
    async def request(method, url, payload=None, timeout=15):
        if url.endswith("/prompt"):
            return {"prompt_id": "current"}
        return {}

    service = ComfyUIService(DouyinLifeConfig(), output_dir=tmp_path, request=request, poll_interval=0)
    result = await service.submit_and_wait("{}", timeout=0.005)
    assert result["ok"] is False
    assert "超时" in result["error"]
    assert "video" not in result
