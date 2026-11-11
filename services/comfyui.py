"""ComfyUI HTTP 桥：只接受本次工作流明确产出的 MP4。"""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from services.tooling import error_result, success_result


class ComfyUIService:
    def __init__(self, config: Any, output_dir: str | Path | None = None, request: Callable[..., Awaitable[Any]] | None = None, poll_interval: float = 2.0):
        self.config = config
        self.output_dir = Path(output_dir) if output_dir is not None else Path(config.advanced.comfy_output_dir or "")
        self.request = request or self._request
        self.poll_interval = poll_interval

    def list_recent(self, limit: int | None = None) -> dict[str, Any]:
        root = self.output_dir
        found: list[dict[str, Any]] = []
        if str(root) and root.is_dir():
            for directory, subdirs, files in os.walk(root):
                current = Path(directory)
                try:
                    depth = len(current.relative_to(root).parts)
                except ValueError:
                    continue
                if depth >= 6:
                    subdirs[:] = []
                for filename in files:
                    path = current / filename
                    if path.suffix.lower() != ".mp4" or not path.is_file():
                        continue
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    found.append({"path": str(path), "name": filename, "size": stat.st_size, "mtime": stat.st_mtime * 1000, "mtimeText": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()})
                    if len(found) > 20000:
                        break
        found.sort(key=lambda item: item["mtime"], reverse=True)
        count = max(1, min(int(limit or self.config.advanced.comfy_list_limit), 200))
        return {"dir": str(root), "exists": root.is_dir(), "total": len(found), "items": found[:count]}

    async def submit_and_wait(self, workflow: str, timeout: float | None = None) -> dict[str, Any]:
        try:
            raw = str(workflow).strip()
            if not raw:
                return error_result("未配置 ComfyUI 工作流")
            source = "inline"
            if not raw.startswith(("{", "[")) and Path(raw).is_file():
                source = raw
                raw = Path(raw).read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return error_result("ComfyUI 工作流必须是 JSON 对象")
            prompt = parsed.get("prompt") if isinstance(parsed.get("prompt"), dict) else parsed
            submitted = await self.request("POST", self._url("/prompt"), {"prompt": prompt, "client_id": "maibot-douyin-life"}, 20)
            prompt_id = str(submitted.get("prompt_id") or submitted.get("id") or "") if isinstance(submitted, dict) else ""
            if not prompt_id:
                return error_result("ComfyUI 没有返回 prompt_id")
            deadline = time.monotonic() + (self.config.advanced.comfy_wait_seconds if timeout is None else timeout)
            while time.monotonic() < deadline:
                try:
                    history = await self.request("GET", self._url("/history/" + urllib.parse.quote(prompt_id, safe="")), timeout=15)
                except Exception:
                    history = {}
                entry = history.get(prompt_id) if isinstance(history, dict) else None
                if isinstance(entry, dict):
                    status = entry.get("status") or {}
                    messages = status.get("messages") or []
                    if status.get("status_str") == "error" or any(isinstance(m, list) and m and m[0] == "error" for m in messages):
                        return error_result("ComfyUI 执行出错", str(status)[:300])
                    if status.get("completed") is True or status.get("status_str") == "success":
                        video = self._completed_video(entry)
                        if isinstance(video, dict):
                            return video
                        return success_result({"promptId": prompt_id, "source": source, "video": str(video)})
                if self.poll_interval:
                    await asyncio.sleep(self.poll_interval)
            return error_result(f"等待 ComfyUI 出片超时（prompt_id={prompt_id}）")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            return error_result(f"ComfyUI 工作流无效：{exc}")
        except Exception as exc:
            return error_result(f"ComfyUI 请求失败：{exc}")

    def _completed_video(self, entry: dict[str, Any]) -> Path | dict[str, Any]:
        root = self.output_dir.resolve()
        paths: list[Path] = []
        for output in (entry.get("outputs") or {}).values():
            for media in [*(output.get("videos") or []), *(output.get("gifs") or [])]:
                filename = str(media.get("filename") or "")
                if media.get("type") != "output" or not filename.lower().endswith(".mp4"):
                    continue
                path = (root / str(media.get("subfolder") or "") / filename).resolve()
                if not path.is_relative_to(root):
                    return error_result("ComfyUI 输出路径越界")
                if path.is_file():
                    paths.append(path)
        if len(paths) != 1:
            return error_result(f"当前工作流有 {len(paths)} 个有效 MP4 输出，请显式指定 video_path")
        return paths[0]

    def _url(self, path: str) -> str:
        base = self.config.advanced.comfy_url.rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise ValueError("ComfyUI 地址必须使用 HTTP(S)")
        return base + path

    @staticmethod
    async def _request(method: str, url: str, payload: Any = None, timeout: float = 15) -> Any:
        def run() -> Any:
            body = json.dumps(payload).encode("utf-8") if payload is not None else None
            request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8")
            return json.loads(text) if text else {}

        return await asyncio.to_thread(run)
