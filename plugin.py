"""MaiBot 刷抖音插件入口与 35 个工具。"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from maibot_sdk import ConfigWidget, ConfigWidgetState, MaiBotPlugin, ON_BOT_CONFIG_RELOAD, Tool

from config import DouyinLifeConfig
from services.comfyui import ComfyUIService
from services.comments import CommentService
from services.direct_messages import DirectMessageService
from services.generation import GenerationService
from services.ledger import Ledger
from services.mcp_client import McpClient
from services.memory import MemoryStore
from services.rounds import RoundService
from services.scheduler import Scheduler
from services.tooling import ToolService, error_result, success_result
from services.writes import WriteService
from tool_schemas import TOOL_SCHEMAS


class DouyinLifePlugin(MaiBotPlugin):
    config_model = DouyinLifeConfig
    config_reload_subscriptions = {ON_BOT_CONFIG_RELOAD}
    config_widgets = [
        ConfigWidget(id="login", kind="status", label="抖音登录状态"),
        ConfigWidget(id="qr", kind="qrcode", label="生成登录二维码"),
        ConfigWidget(id="selfcheck", kind="action", label="检查运行环境"),
        ConfigWidget(id="run", kind="action", label="立即运行一轮", confirmation="只读浏览也会按当前配置执行已授权的互动，是否继续？"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.mcp: McpClient | None = None
        self.tools: ToolService | None = None
        self.writes: WriteService | None = None
        self.rounds: Any = None
        self.direct_messages: Any = None
        self.comments: Any = None
        self.scheduler: Any = None
        self.comfy: Any = None
        self._ui_tasks: set[asyncio.Task[Any]] = set()
        self._ui_results: dict[str, str] = {}

    async def on_load(self) -> None:
        data_dir = Path(self.ctx.paths.data_dir)
        runtime_dir = Path(self.ctx.paths.runtime_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        runtime_dir.mkdir(parents=True, exist_ok=True)
        self.mcp = McpClient(data_dir, runtime_dir, self.config)
        ledger = Ledger(data_dir)
        memory = MemoryStore(data_dir)
        self.tools = ToolService(self.config, self.mcp, ledger, memory, data_dir)
        self.writes = WriteService(self.config, self.mcp, ledger, memory)
        self.generation = GenerationService(self.ctx)
        self.comfy = ComfyUIService(self.config)
        self.tools.comfy = self.comfy
        self.writes.comfy = self.comfy
        self.rounds = RoundService(self.config, self.tools, self.writes, ledger, memory, self.generation, data_dir)
        self.direct_messages = DirectMessageService(self.config, self.tools, self.writes, self.generation, memory, ledger)
        self.comments = CommentService(self.config, self.tools, self.writes, self.generation, ledger)
        self.scheduler = Scheduler(self.config, self.rounds, self.direct_messages, self.comments, self.writes, self.cleanup)
        await self.scheduler.start()
        self.ctx.logger.info("MaiBot 刷抖音插件已加载；人设将读取 MaiBot 当前配置")

    async def on_unload(self) -> None:
        if self.scheduler:
            await self.scheduler.close()
        tasks = list(self._ui_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._ui_tasks.clear()
        if self.mcp:
            await self.mcp.close()

    async def on_config_update(self, scope: str, config_data: dict[str, Any], version: str) -> None:
        del config_data
        self.ctx.logger.info("刷抖音配置更新：scope=%s version=%s", scope, version)
        if scope == "self" and self.scheduler:
            await self.scheduler.restart()

    async def get_config_widget_state(self) -> dict[str, ConfigWidgetState]:
        login = self._ui_results.get("login", "尚未检查；可用 dy_whoami 查询")
        qr_text = self._ui_results.get("qr", "点击生成二维码；扫码后调用 dy_login_poll 确认")
        image = None
        if self.tools:
            path = self.tools.data_dir / "login-qr.png"
            try:
                if path.is_file() and path.stat().st_size <= 700_000:
                    image = "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
            except OSError:
                pass
        return {
            "login": ConfigWidgetState(text=login[:2000]),
            "qr": ConfigWidgetState(text=qr_text[:2000], image=image, expires_at=(datetime.now() + timedelta(seconds=180)).timestamp() if image else None),
            "selfcheck": ConfigWidgetState(text=self._ui_results.get("selfcheck", "尚未运行自检")[:2000]),
            "run": ConfigWidgetState(text=self._ui_results.get("run", "尚未手动运行")[:2000]),
        }

    async def on_config_widget_action(self, action_id: str) -> None:
        if action_id not in {"qr", "selfcheck", "run"}:
            raise ValueError(f"未实现的配置页操作：{action_id}")
        name = {"qr": "dy_login_start", "selfcheck": "dy_selfcheck", "run": "dy_run"}[action_id]

        async def execute() -> None:
            result = await self._dispatch_tool(name, {})
            self._ui_results[action_id] = str(result)[:1800]

        task = asyncio.create_task(execute())
        self._ui_tasks.add(task)
        task.add_done_callback(self._ui_tasks.discard)

    async def _dispatch_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if not self.tools or not self.writes:
            return error_result("插件尚未完成加载")
        if name in {"dy_run", "dy_dm_poll", "dy_dm_round", "dy_reply_round", "dy_cleanup"}:
            if name == "dy_run" and self.rounds:
                return await self.rounds.run("manual", automatic=False)
            if name in {"dy_dm_poll", "dy_dm_round"} and self.direct_messages:
                return await self.direct_messages.poll(automatic=False, strangers=name == "dy_dm_round")
            if name == "dy_reply_round" and self.comments:
                return await self.comments.poll(automatic=False, count=args.get("count"))
            if name == "dy_cleanup":
                return await self.cleanup(args)
            return error_result("对应任务服务尚未初始化")
        if name == "dy_like":
            return await self.writes.like(str(args.get("aweme_id", "")), bool(args.get("undo", False)), bool(args.get("force", False)))
        if name == "dy_comment":
            return await self.writes.comment(str(args.get("aweme_id", "")), str(args.get("text", "")), str(args.get("reply_cid", "")), bool(args.get("force", False)))
        if name == "dy_reply":
            return await self.writes.comment(str(args.get("aweme_id", "")), str(args.get("text", "")), str(args.get("cid", "")), bool(args.get("force", False)))
        if name == "dy_share":
            return await self.writes.share(str(args.get("aweme_id", "")), str(args.get("to", "")), bool(args.get("force", False)))
        if name == "dy_chat_send":
            return await self.writes.chat_send(str(args.get("nickname", "")), str(args.get("text", "")), bool(args.get("force", False)))
        if name == "dy_chat_sticker":
            return await self.writes.sticker(str(args.get("nickname", "")), str(args.get("keyword", "大肥鱼")), int(args.get("pick", 0)), int(args.get("flip", 0)), bool(args.get("force", False)))
        if name == "dy_reconcile_pending":
            return await self.writes.reconcile_pending(int(args.get("limit", 10)))
        if name == "dy_publish":
            draft = args.get("draft") if isinstance(args.get("draft"), bool) else None
            return await self.writes.publish(str(args.get("video_path", "")), bool(args.get("latest", False)), str(args.get("title", "")), str(args.get("tags", "")), draft, bool(args.get("force", False)))
        return await self.tools.dispatch(name, args)

    async def cleanup(self, args: dict[str, Any]) -> dict[str, Any]:
        if not self.tools:
            return error_result("插件尚未完成加载")
        root = self.tools.data_dir
        removed: list[str] = []
        errors: list[str] = []

        def drop(directory: Path, days: int, suffixes: tuple[str, ...] | None = None, keep_json: bool = False) -> None:
            if not directory.is_dir():
                return
            cutoff = datetime.now().timestamp() - days * 86400
            for path in directory.rglob("*"):
                try:
                    if not path.is_file() or (suffixes and path.suffix.lower() not in suffixes) or (keep_json and path.suffix.lower() == ".json"):
                        continue
                    if days == 0 or path.stat().st_mtime < cutoff:
                        path.unlink()
                        removed.append(str(path.relative_to(root)))
                except OSError as exc:
                    errors.append(str(exc))

        drop(root / ".tmp", 0)
        drop(root / "media", 0, keep_json=True)
        drop(root / "thumbs", max(0, min(int(args.get("thumbDays", 30)), 3650)))
        drop(root / "out", max(1, min(int(args.get("reportDays", 120)), 3650)), (".md",))
        log = root / "duty.log"
        try:
            if log.is_file() and log.stat().st_size > 2 * 1024 * 1024:
                log.write_text("\n".join(log.read_text(encoding="utf-8").splitlines()[-2000:]), encoding="utf-8")
        except OSError as exc:
            errors.append(str(exc))
        return success_result({"removed": removed, "count": len(removed), "errors": errors, "preserved": ["browser", "chrome-cdp", "ledger.json", "memory"]})


def _register_tool(name: str, schema: dict[str, Any]) -> None:
    async def handler(self: DouyinLifePlugin, _tool_name: str = name, **kwargs: Any):
        return await self._dispatch_tool(_tool_name, kwargs)

    handler.__name__ = f"handle_{name}"
    decorated = Tool(name, description=schema["description"], parameters=schema["parameters"])(handler)
    setattr(DouyinLifePlugin, f"handle_{name}", decorated)


for _name, _schema in TOOL_SCHEMAS.items():
    _register_tool(_name, _schema)


def create_plugin() -> DouyinLifePlugin:
    return DouyinLifePlugin()
