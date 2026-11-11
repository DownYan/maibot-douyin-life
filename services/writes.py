"""写操作闸门、额度、账本与平台回执。"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from config import DouyinLifeConfig
from services.ledger import Ledger
from services.memory import MemoryStore
from services.tooling import error_result, success_result


def _nicknames(value: str) -> list[str]:
    import re
    return [part.strip() for part in re.split(r"[,，、\r\n]+", value) if part.strip()]


class WriteService:
    def __init__(self, config: DouyinLifeConfig, mcp: Any, ledger: Ledger, memory: MemoryStore):
        self.config = config
        self.mcp = mcp
        self.ledger = ledger
        self.memory = memory
        self.comfy: Any = None

    def authorize(self, action: str, nickname: str = "", force: bool = False, automatic: bool = False) -> dict[str, Any]:
        if force and not automatic:
            return {"allowed": True, "reason": "manual_force"}
        interaction = self.config.interaction
        if action == "like" and interaction.auto_like:
            return {"allowed": True}
        if action == "comment":
            if interaction.auto_comment and interaction.mention_name.strip():
                return {"allowed": True}
            if interaction.auto_comment_plain:
                return {"allowed": True}
        if action == "reply" and interaction.auto_reply:
            return {"allowed": True}
        if action == "publish" and self.config.publish.auto_publish:
            return {"allowed": True}
        if action in {"chat", "sticker", "share"} and nickname in _nicknames(interaction.msg_allow_to):
            return {"allowed": True}
        return {"allowed": False, "reason": f"{action} 的安全闸门或联系人白名单未开启"}

    async def _execute(self, kind: str, key: str, target: str, args: dict[str, Any], daily: int, per_run: int, automatic: bool, force: bool, timeout: float, run_id: str = "") -> dict[str, Any]:
        run_id = run_id or (f"manual-{uuid.uuid4()}" if not automatic else "automatic")
        if not (force and not automatic):
            quota = await self.ledger.consume(kind, key, daily, per_run, run_id)
            if not quota["allowed"]:
                return {"ok": False, "success": False, "blocked": True, "error": quota["reason"]}
        result = await self.mcp.call(target, args, timeout)
        recorded = dict(result)
        recorded.setdefault("request", args)
        await self.ledger.record_result(kind, key, recorded)
        return success_result(result)

    async def like(self, aweme_id: str, undo: bool = False, force: bool = False, automatic: bool = False) -> dict[str, Any]:
        auth = self.authorize("like", force=force, automatic=automatic)
        if not auth["allowed"]:
            return {**error_result(auth["reason"]), "blocked": True}
        return await self._execute("like", aweme_id, "douyin_like", {"aweme_id": aweme_id, "undo": undo}, 10_000, 10_000, automatic, force, 90)

    async def comment(self, aweme_id: str, text: str, reply_cid: str = "", force: bool = False, automatic: bool = False, run_id: str = "") -> dict[str, Any]:
        action = "reply" if reply_cid else "comment"
        auth = self.authorize(action, force=force, automatic=automatic)
        if not auth["allowed"]:
            return {**error_result(auth["reason"]), "blocked": True, "allowed": False}
        text = " ".join(str(text).split()).strip()
        if not text:
            return error_result("评论正文是空的")
        mention = "" if reply_cid else self.config.interaction.mention_name.strip()
        if mention and f"@{mention}" not in text:
            text = f"@{mention} {text}"
        text = text[:20] if reply_cid else text[:300]
        kind = "reply" if reply_cid else ("comment" if mention else "plain_comment")
        daily = self.config.interaction.reply_per_day if reply_cid else (self.config.interaction.comment_per_day if mention else self.config.interaction.plain_comment_per_day)
        per_run = self.config.interaction.reply_per_run if reply_cid else self.config.interaction.comment_per_round
        key = reply_cid or f"{aweme_id}:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"
        result = await self._execute(kind, key, "douyin_comment", {"aweme_id": aweme_id, "text": text, "reply_cid": reply_cid, "mention": mention}, daily, per_run, automatic, force, 150, run_id=run_id)
        result["text"] = text
        return result

    async def chat_send(self, nickname: str, text: str, force: bool = False, automatic: bool = False, responding: bool = False, ledger_key: str = "") -> dict[str, Any]:
        nickname, text = nickname.strip(), text.strip()
        if responding:
            enabled = self.config.dm.dm_auto_reply or self.config.dm.dm_reply
            auth = {"allowed": enabled, "reason": "私信自动回复未开启"}
        else:
            auth = self.authorize("chat", nickname, force, automatic)
        if not auth["allowed"]:
            return {**error_result(auth["reason"]), "blocked": True}
        if not nickname or not text:
            return error_result("nickname 和 text 都要给")
        key = ledger_key or f"{nickname}:{uuid.uuid4()}"
        result = await self._execute("dm", key, "douyin_chat_send", {"nickname": nickname, "text": text}, self.config.dm.dm_reply_per_day, self.config.dm.dm_reply_per_day, automatic, force, 180)
        if result.get("verified") is True:
            self.memory.add(f"私信 · {nickname} · 我：{text[:300]}")
        return result

    async def sticker(self, nickname: str, keyword: str = "大肥鱼", pick: int = 0, flip: int = 0, force: bool = False, automatic: bool = False, ledger_key: str = "") -> dict[str, Any]:
        auth = self.authorize("sticker", nickname, force, automatic)
        if not auth["allowed"]:
            return {**error_result(auth["reason"]), "blocked": True}
        return await self._execute("sticker", ledger_key or f"{nickname}:{uuid.uuid4()}", "douyin_chat_sticker", {"nickname": nickname, "keyword": keyword, "pick": pick, "flip": max(0, min(flip, 6))}, 1000, 1000, automatic, force, 240)

    async def share(self, aweme_id: str, to: str = "", force: bool = False, automatic: bool = False) -> dict[str, Any]:
        nickname = to.strip() or self.config.interaction.share_to_nick.strip()
        auth = self.authorize("share", nickname, force, automatic)
        if not auth["allowed"]:
            return {**error_result(auth["reason"]), "blocked": True}
        return await self._execute("share", aweme_id, "douyin_share_video", {"aweme_id": aweme_id, "nickname": nickname}, self.config.interaction.share_per_day, self.config.interaction.share_per_day, automatic, force, 180)

    async def publish(self, video_path: str = "", latest: bool = False, title: str = "", tags: str = "", draft: bool | None = None, force: bool = False, automatic: bool = False) -> dict[str, Any]:
        auth = self.authorize("publish", force=force, automatic=automatic)
        if not auth["allowed"]:
            return {**error_result(auth["reason"]), "blocked": True}
        if not video_path and latest and self.comfy:
            if self.config.advanced.comfy_workflow.strip():
                generated = await self.comfy.submit_and_wait(self.config.advanced.comfy_workflow)
                if not generated.get("ok"):
                    return generated
                video_path = generated.get("video", "")
            else:
                items = self.comfy.list_recent(1).get("items", [])
                video_path = items[0]["path"] if items else ""
        if not video_path or not Path(video_path).is_file():
            return error_result("视频文件不存在；请给 video_path 或 latest=true")
        draft = self.config.publish.publish_draft if draft is None else draft
        title = title.strip() or self.config.publish.publish_title.replace("{date}", __import__("datetime").datetime.now().strftime("%Y-%m-%d"))
        tags = tags.strip() or self.config.publish.publish_tags
        stat = Path(video_path).stat()
        key = f"{Path(video_path).resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
        return await self._execute("publish", key, "douyin_publish", {"video_path": video_path, "title": title, "tags": tags, "draft": draft}, self.config.publish.publish_per_day, self.config.publish.publish_per_day, automatic, force, 300)

    async def reconcile_pending(self, limit: int = 10) -> dict[str, Any]:
        checked = verified = 0
        items = []
        for record in (await self.ledger.pending("reply"))[:max(1, min(limit, 50))]:
            request = record.get("result", {}).get("request", {})
            if not request.get("aweme_id"):
                continue
            checked += 1
            result = await self.mcp.call("douyin_check_reply", {"aweme_id": request["aweme_id"], "parent_cid": record["key"], "text": request.get("text", "")}, 90)
            if result.get("found"):
                verified += 1
                await self.ledger.record_result("reply", record["key"], {"ok": True, "verified": True, "request": request, "real_cid": result.get("cid", "")})
                items.append({"cid": record["key"], "status": "verified"})
            else:
                items.append({"cid": record["key"], "status": "not-found"})
        return success_result({"checked": checked, "verified": verified, "items": items})
