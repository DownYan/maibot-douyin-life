"""只读、登录和配置工具的参数映射。"""

from __future__ import annotations

import asyncio
import os
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from config import DouyinLifeConfig
from services.ledger import Ledger
from services.memory import MemoryStore


def success_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"ok": False, "success": False, "error": "工具返回不是对象"}
    output = dict(result)
    output.setdefault("ok", True)
    output["success"] = output["ok"] is not False
    return output


def error_result(error: str, hint: str = "") -> dict[str, Any]:
    result = {"ok": False, "success": False, "error": str(error)}
    if hint:
        result["hint"] = hint
    return result


class ToolService:
    DIRECT = {
        "dy_whoami": ("douyin_check_credential", 60, ()),
        "dy_login_start": ("douyin_login_qr", 90, ()),
        "dy_login_poll": ("douyin_login_poll", 90, ()),
        "dy_hot": ("douyin_hot", 90, ("limit",)),
        "dy_hot_videos": ("douyin_hot_videos", 120, ("sentence_id", "word", "num")),
        "dy_video": ("douyin_video", 90, ("aweme_id",)),
        "dy_comments": ("douyin_comments", 120, ("aweme_id", "num")),
        "dy_my_posts": ("douyin_my_posts", 90, ("days",)),
        "dy_thumb": ("douyin_thumb", 90, ("aweme_id",)),
        "dy_dm_inbox": ("douyin_inbox", 120, ("limit", "nickname")),
        "dy_selfcheck": ("douyin_selfcheck", 120, ()),
    }

    def __init__(self, config: DouyinLifeConfig, mcp: Any, ledger: Ledger, memory: MemoryStore, data_dir: str | Path):
        self.config = config
        self.mcp = mcp
        self.ledger = ledger
        self.memory = memory
        self.data_dir = Path(data_dir)
        self.comfy: Any = None

    async def dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "dy_status":
                return success_result(await self.status())
            if name == "dy_config":
                return success_result({"config": self.config.model_dump(), "home": str(self.data_dir), "note": "请在 MaiBot WebUI 修改配置；工具不提供绕过校验的写配置入口"})
            if name == "dy_remember":
                line = str(args.get("line", "")).strip()
                if not line:
                    return error_result("line 是空的")
                self.memory.add(line)
                return success_result({"line": line, "lines": len(self.memory.recent(1000))})
            if name == "dy_my_videos":
                return success_result(await self.my_videos())
            if name == "dy_comfy_list":
                if not self.comfy:
                    return error_result("ComfyUI 服务尚未初始化")
                return success_result(self.comfy.list_recent(int(args.get("limit", 0)) or self.config.advanced.comfy_list_limit))
            if name == "dy_search":
                return success_result(await self.mcp.call("douyin_search", {
                    "keyword": str(args.get("keyword", "")),
                    "num": _clamp(args.get("num"), 10, 1, 50),
                    "order": str(args.get("order", "general")),
                }, 120))
            if name == "dy_feed":
                return success_result(await self.mcp.call("douyin_feed", {
                    "num": _clamp(args.get("num"), 10, 1, 50),
                    "scrolls": _clamp(args.get("scrolls"), 6, 1, 30),
                    "skip_live": self.config.interaction.skip_live,
                }, 240))
            if name == "dy_watch":
                return success_result(await self.mcp.call("douyin_watch", {
                    "aweme_id": str(args.get("aweme_id", "")),
                    "seconds": _clamp(args.get("seconds"), self.config.watch.watch_seconds, 15, 600),
                    "frames": _clamp(args.get("frames"), self.config.watch.watch_frames, 3, 48),
                }, 900))
            if name == "dy_login_sms":
                phone = "".join(ch for ch in str(args.get("phone", "")) if ch.isdigit())
                if len(phone) != 11:
                    return error_result("手机号要给 11 位数字")
                return success_result(await self.mcp.call("douyin_login_sms", {"phone": phone}, 90))
            if name == "dy_login_sms_submit":
                code = "".join(ch for ch in str(args.get("code", "")) if ch.isdigit())
                if not 4 <= len(code) <= 6:
                    return error_result("验证码要是 4–6 位数字")
                return success_result(await self.mcp.call("douyin_login_sms_submit", {"code": code}, 120))
            if name == "dy_chrome_open":
                return success_result(await self.chrome_open(_clamp(args.get("port"), self.config.advanced.cdp_port, 1024, 65535)))
            if name in self.DIRECT:
                target, timeout, allowed = self.DIRECT[name]
                payload = {key: args[key] for key in allowed if key in args}
                return success_result(await self.mcp.call(target, payload, timeout))
            return error_result(f"未知工具：{name}")
        except Exception as exc:
            return error_result(str(exc))

    async def status(self) -> dict[str, Any]:
        return {
            "today": datetime.now().strftime("%Y-%m-%d"),
            "home": str(self.data_dir),
            "perDay": self.config.daily.per_day,
            "pickedToday": await self.ledger.count_today("pick"),
            "gates": {
                "autoLike": self.config.interaction.auto_like,
                "autoComment": self.config.interaction.auto_comment,
                "autoPublish": self.config.publish.auto_publish,
                "autoReply": self.config.interaction.auto_reply,
            },
            "reportLevel": self.config.daily.report_level,
            "personaSource": "MaiBot personality.get_current",
        }

    async def my_videos(self) -> dict[str, Any]:
        pending = await self.ledger.pending("publish")
        records = self.ledger._read()["records"].get("publish", {})
        items = [
            {"key": key, **value.get("result", {}), "at": value.get("updatedAt", value.get("at", ""))}
            for key, value in records.items()
            if value.get("status") == "succeeded"
        ]
        return {"count": len(items), "items": items, "pending": len(pending)}

    async def chrome_open(self, port: int) -> dict[str, Any]:
        url = f"http://127.0.0.1:{port}"
        try:
            urllib.request.urlopen(url + "/json/version", timeout=1).close()
            self.config.advanced.cdp_url = url
            return {"already": True, "cdpUrl": url}
        except Exception:
            pass
        chrome = self.config.advanced.chrome_path or _find_chrome()
        if not chrome:
            return error_result("没找到 Chrome，请在高级设置填写 chrome_path")
        profile = self.data_dir / "chrome-cdp"
        profile.mkdir(parents=True, exist_ok=True)
        flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0
        subprocess.Popen([
            chrome, f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check", "https://www.douyin.com/",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        for _ in range(20):
            try:
                urllib.request.urlopen(url + "/json/version", timeout=1).close()
                self.config.advanced.cdp_url = url
                return {"started": True, "cdpUrl": url, "note": "如需重启后继续使用 CDP，请在 MaiBot 高级设置保存该地址"}
            except Exception:
                await asyncio.sleep(0.5)
        return error_result("20 秒内 CDP 端口未就绪")


def _clamp(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _find_chrome() -> str:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe"),
    ]
    return next((path for path in candidates if path and Path(path).is_file()), "")
