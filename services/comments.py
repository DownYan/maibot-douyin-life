"""本人作品评论巡检；回执未知时绝不自动重发。"""

from __future__ import annotations

import random
import re
from typing import Any

from services.tooling import success_result


class CommentService:
    def __init__(self, config: Any, tools: Any, writes: Any, generation: Any, ledger: Any):
        self.config = config
        self.tools = tools
        self.writes = writes
        self.generation = generation
        self.ledger = ledger

    async def poll(self, automatic: bool = True, count: int | None = None) -> dict[str, Any]:
        if not self.config.interaction.auto_reply:
            return success_result({"replied": 0, "pending": 0, "note": "评论自动回复未开启"})
        configured = {v.strip() for v in re.split(r"[,，、\s]+", self.config.interaction.reply_video_ids) if v.strip()}
        if configured:
            videos = [{"aweme_id": value} for value in configured]
        else:
            result = await self.tools.dispatch("dy_my_posts", {"days": self.config.interaction.reply_works_days})
            if result.get("ok") is False:
                return result
            videos = result.get("items", [])
        candidates: list[dict[str, Any]] = []
        for video in videos:
            aweme_id = str(video.get("aweme_id") or video.get("id") or "")
            if not aweme_id:
                continue
            response = await self.tools.dispatch("dy_comments", {"aweme_id": aweme_id, "num": 50})
            for comment in response.get("items", []):
                cid = str(comment.get("cid") or comment.get("comment_id") or "")
                nickname = str(comment.get("user") or comment.get("nickname") or (comment.get("user_info") or {}).get("nickname") or "")
                if not cid or nickname == self.config.interaction.my_nickname:
                    continue
                if comment.get("aweme_type") == 68 or video.get("aweme_type") == 68:
                    continue
                if await self.ledger.is_processed("reply", cid) or any(r["key"] == cid for r in await self.ledger.pending("reply")):
                    continue
                if self.config.interaction.reply_once_per_user and self._already_replied(nickname):
                    continue
                candidates.append({"aweme_id": aweme_id, "cid": cid, "nickname": nickname, "text": str(comment.get("text", ""))})
        if self.config.interaction.reply_random:
            random.shuffle(candidates)
        limit = self.config.interaction.reply_per_run if count is None else max(0, min(int(count), self.config.interaction.reply_per_run))
        replied = pending = 0
        results: list[dict[str, Any]] = []
        for comment in candidates[:limit]:
            generated = await self.generation.short_reply("public", comment["text"], f"视频 ID：{comment['aweme_id']}")
            if not generated.get("success"):
                continue
            result = await self.writes.comment(comment["aweme_id"], generated["text"], comment["cid"], automatic=automatic)
            result["nickname"] = comment["nickname"]
            await self.ledger.record_result("reply", comment["cid"], result)
            if result.get("verified") is True:
                replied += 1
            elif result.get("status") in {"pending", "unknown"} or result.get("verified") is False:
                pending += 1
            results.append({"cid": comment["cid"], **result})
        return success_result({"replied": replied, "pending": pending, "items": results})

    def _already_replied(self, nickname: str) -> bool:
        if not nickname:
            return False
        return any(value.get("status") == "succeeded" and value.get("result", {}).get("nickname") == nickname for value in self.ledger._read()["records"].get("reply", {}).values())
