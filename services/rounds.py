"""推荐流巡检：挑选、理解、单次互动与本地日报。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from services.tooling import error_result, success_result


class RoundService:
    def __init__(self, config: Any, tools: Any, writes: Any, ledger: Any, memory: Any, generation: Any, data_dir: str | Path):
        self.config = config
        self.tools = tools
        self.writes = writes
        self.ledger = ledger
        self.memory = memory
        self.generation = generation
        self.data_dir = Path(data_dir)
        self._lock = asyncio.Lock()

    async def run(self, why: str = "manual", automatic: bool = False) -> dict[str, Any]:
        if self._lock.locked():
            return error_result("上一轮仍在运行，请稍后再试")
        async with self._lock:
            return await self._run_once(why=why, automatic=automatic)

    async def _run_once(self, why: str = "manual", automatic: bool = False) -> dict[str, Any]:
        run_id = f"round-{uuid.uuid4()}"
        daily_limit = self.config.daily.per_day if automatic else max(1, self.config.daily.per_day)
        remaining = daily_limit - await self.ledger.count_today("pick")
        if remaining <= 0:
            return success_result({"why": why, "picked": [], "actions": [], "note": "今日挑选额度已用完"})
        count = min(self.config.daily.pick_per_round, remaining)
        feed = await self.tools.dispatch("dy_feed", {"num": max(count * 3, 10), "scrolls": 6})
        if feed.get("ok") is False:
            return feed
        picked: list[dict[str, Any]] = []
        for item in feed.get("items", []):
            aweme_id = str(item.get("aweme_id") or item.get("id") or "").strip()
            if not aweme_id or not self._eligible(item):
                continue
            if await self.ledger.is_processed("pick", aweme_id) or any(r["key"] == aweme_id for r in await self.ledger.pending("pick")):
                continue
            if self.config.daily.keywords and not any(k.lower() in str(item.get("title", "")).lower() for k in self.config.daily.keywords if k.strip()):
                continue
            quota = await self.ledger.consume("pick", aweme_id, daily_limit, count, run_id)
            if not quota["allowed"]:
                continue
            await self.ledger.record_result("pick", aweme_id, {"ok": True, "verified": True, "title": item.get("title", "")})
            picked.append(item)
            if len(picked) >= count:
                break

        actions: list[dict[str, Any]] = []
        report_items: list[dict[str, Any]] = []
        for item in picked:
            aweme_id = str(item.get("aweme_id") or item.get("id"))
            watched: dict[str, Any] = {}
            if self.config.watch.watch_before_act or self.config.daily.report_level == "full":
                watched = await self.tools.dispatch("dy_watch", {"aweme_id": aweme_id})
            context = str(watched.get("transcript", ""))[:2000]
            report_items.append({**item, "transcript": context, "watchOk": watched.get("ok") is True})
            action = await self._act(item, watched, automatic, run_id)
            if action:
                actions.append(action)
                if action.get("verified") is True and self.config.daily.memory:
                    self.memory.add(f"刷视频 · {item.get('title', aweme_id)} · {action.get('kind')}：已确认")
        report = self._write_report(why, report_items, actions) if picked else None
        return success_result({"why": why, "picked": [str(v.get("aweme_id") or v.get("id")) for v in picked], "actions": actions, "report": str(report) if report else None, "count": len(picked)})

    def _eligible(self, item: dict[str, Any]) -> bool:
        if self.config.interaction.skip_live and (item.get("is_live") or item.get("isLive") or item.get("type") == "live"):
            return False
        try:
            duration = float(item.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0
        minutes = duration / 60000 if duration > 10000 else duration / 60
        return minutes <= self.config.watch.skip_over_min

    async def _act(self, item: dict[str, Any], watched: dict[str, Any], automatic: bool, run_id: str) -> dict[str, Any] | None:
        interaction = self.config.interaction
        aweme_id = str(item.get("aweme_id") or item.get("id"))
        incoming = f"标题：{item.get('title', '')}\n视频转写：{watched.get('transcript', '')}"
        # 每条视频至多一种主要互动，避免重复打扰。
        if interaction.auto_comment or interaction.auto_comment_plain:
            generated = await self.generation.short_reply("public", incoming, "\n".join(self.memory.recent(6)))
            if generated.get("success"):
                result = await self.writes.comment(aweme_id, generated["text"], automatic=automatic, run_id=run_id)
                return {"kind": "comment", "aweme_id": aweme_id, **result}
        if interaction.share_to_nick.strip():
            result = await self.writes.share(aweme_id, automatic=automatic)
            action = {"kind": "share", "aweme_id": aweme_id, **result}
            if result.get("verified") is True and interaction.share_with_note:
                note = interaction.share_note.strip()
                if not note:
                    note = (await self.generation.share_note({**item, **watched})).get("text", "")
                if note:
                    action["note"] = await self.writes.chat_send(interaction.share_to_nick, note, automatic=automatic)
            return action
        if interaction.auto_like:
            return {"kind": "like", "aweme_id": aweme_id, **await self.writes.like(aweme_id, automatic=automatic)}
        return None

    def _write_report(self, why: str, items: list[dict[str, Any]], actions: list[dict[str, Any]]) -> Path | None:
        if self.config.daily.report_level == "off":
            return None
        directory = self.data_dir / "out"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{datetime.now():%Y-%m-%d}.md"
        lines = [f"\n## {datetime.now():%H:%M:%S} · {why}"]
        for item in items:
            aweme_id = item.get("aweme_id") or item.get("id")
            lines.extend([f"\n### {aweme_id}", f"- 标题：{item.get('title', '')}", f"- 链接：https://www.douyin.com/video/{aweme_id}"])
            if self.config.daily.report_level == "full":
                lines.append(f"- 内容：{str(item.get('transcript', ''))[:1200] or '未获得转写'}")
        for action in actions:
            lines.append(f"- 互动：{action.get('kind')} / {action.get('aweme_id')} / {action.get('status', '已确认' if action.get('verified') is True else '失败')}")
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        return path
