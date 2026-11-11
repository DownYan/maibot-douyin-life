"""白名单及明确授权的陌生人私信巡检。"""

from __future__ import annotations

import re
from typing import Any

from services.tooling import success_result


def _names(value: str) -> set[str]:
    return {v.strip() for v in re.split(r"[,，、\r\n]+", value) if v.strip()}


class DirectMessageService:
    def __init__(self, config: Any, tools: Any, writes: Any, generation: Any, memory: Any, ledger: Any):
        self.config = config
        self.tools = tools
        self.writes = writes
        self.generation = generation
        self.memory = memory
        self.ledger = ledger

    async def poll(self, automatic: bool = True, strangers: bool = False) -> dict[str, Any]:
        if strangers and not self.config.dm.dm_reply:
            return success_result({"replied": 0, "pending": 0, "skipped": 0, "note": "陌生人私信回复未开启"})
        if not strangers and not self.config.dm.dm_auto_reply:
            return success_result({"replied": 0, "pending": 0, "skipped": 0, "note": "白名单私信自动回复未开启"})
        inbox = await self.tools.dispatch("dy_dm_inbox", {"limit": 50})
        if inbox.get("ok") is False:
            return inbox
        allow = _names(self.config.interaction.msg_allow_to)
        only = _names(self.config.dm.dm_reply_only_to)
        replied = pending = skipped = 0
        results: list[dict[str, Any]] = []
        for message in inbox.get("items", []):
            name = str(message.get("name") or message.get("nickname") or "").strip()
            message_id = str(message.get("messageId") or message.get("message_id") or "").strip()
            direction = str(message.get("direction", "inbound"))
            if not name or not message_id or direction not in {"inbound", "in", "received"}:
                continue
            if (strangers and not self.config.dm.dm_reply) or (not strangers and name not in allow) or (only and name not in only):
                skipped += 1
                continue
            if await self.ledger.is_processed("dm", message_id) or any(r["key"] == message_id for r in await self.ledger.pending("dm")):
                continue
            if self._contact_replies(name) >= self.config.dm.dm_reply_per_contact:
                skipped += 1
                continue
            incoming = str(message.get("text") or message.get("content") or "").strip()
            if message.get("isVideo"):
                aweme_id = str(message.get("aweme_id") or message.get("awemeId") or "").strip()
                if aweme_id:
                    watched = await self.tools.dispatch("dy_watch", {"aweme_id": aweme_id})
                    incoming += "\n视频内容：" + str(watched.get("transcript", ""))[:2000]
                else:
                    incoming += "\n[对方分享了视频，但没有可读取的视频 ID]"
            generated = await self.generation.short_reply("private", incoming, "\n".join(self.memory.recent(12)))
            if not generated.get("success"):
                results.append({"messageId": message_id, "to": name, "ok": False, "error": generated.get("error", "生成失败")})
                continue
            result = await self.writes.chat_send(name, generated["text"], automatic=automatic, responding=True, ledger_key=message_id)
            if result.get("verified") is True:
                replied += 1
                self.memory.add(f"私信 · {name} · 对方：{incoming[:300]}")
            elif result.get("status") in {"pending", "unknown"} or result.get("verified") is False:
                pending += 1
            results.append({"messageId": message_id, "to": name, **result})
        return success_result({"replied": replied, "pending": pending, "skipped": skipped, "items": results})

    def _contact_replies(self, name: str) -> int:
        today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
        records = self.ledger._read()["records"].get("dm", {})
        return sum(1 for value in records.values() if value.get("day") == today and value.get("status") in {"reserved", "pending", "unknown", "succeeded"} and value.get("result", {}).get("request", {}).get("nickname") == name)
