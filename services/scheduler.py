"""可取消、可重启的轻量后台调度。"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, time
from typing import Any


class Scheduler:
    def __init__(self, config: Any, rounds: Any = None, direct_messages: Any = None, comments: Any = None, writes: Any = None, cleanup: Any = None):
        self.config = config
        self.rounds = rounds
        self.direct_messages = direct_messages
        self.comments = comments
        self.writes = writes
        self.cleanup = cleanup
        self.tasks: set[asyncio.Task[Any]] = set()
        self._closed = False

    async def start(self) -> None:
        self._closed = False
        if self.tasks:
            return
        self._spawn(self._round_loop())
        self._spawn(self._dm_loop())
        self._spawn(self._comment_loop())
        self._spawn(self._streak_loop())
        if self.config.advanced.auto_clean:
            self._spawn(self._cleanup_loop())

    def _spawn(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def close(self) -> None:
        self._closed = True
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()

    async def restart(self) -> None:
        await self.close()
        await self.start()

    async def _round_loop(self) -> None:
        while True:
            if self.config.daily.peak_valley and self.rounds and self._in_window(datetime.now().time()):
                await self.rounds.run("scheduled", automatic=True)
                await asyncio.sleep(random.uniform(45, 75) * 60)
            else:
                await asyncio.sleep(60)

    async def _dm_loop(self) -> None:
        while True:
            if self.direct_messages and (self.config.dm.dm_auto_reply or self.config.dm.dm_reply):
                if self.config.dm.dm_auto_reply:
                    await self.direct_messages.poll(automatic=True, strangers=False)
                if self.config.dm.dm_reply:
                    await self.direct_messages.poll(automatic=True, strangers=True)
            await asyncio.sleep(self.config.dm.dm_auto_interval_sec * random.uniform(0.8, 1.2))

    async def _comment_loop(self) -> None:
        while True:
            if self.comments and self.config.interaction.auto_reply:
                await self.comments.poll(automatic=True)
            await asyncio.sleep(self.config.interaction.reply_interval_min * 60 * random.uniform(0.8, 1.2))

    async def streak_once(self) -> dict[str, Any] | None:
        nickname = self.config.interaction.streak_nick.strip()
        if not self.writes or not nickname or not self.config.interaction.streak_per_day:
            return None
        key = f"streak:{datetime.now():%Y-%m-%d}:{nickname}"
        return await self.writes.sticker(nickname, self.config.sticker.streak_sticker, automatic=True, ledger_key=key)

    async def _streak_loop(self) -> None:
        while True:
            await self.streak_once()
            await asyncio.sleep(3600 * random.uniform(0.8, 1.2))

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(3600)
            if self.cleanup:
                result = self.cleanup({})
                if hasattr(result, "__await__"):
                    await result

    def _in_window(self, current: time) -> bool:
        noon = time(12, 0) <= current < time(14, 0)
        night = current >= time(0, 30) and current < time(8, 30)
        return (self.config.daily.noon and noon) or (self.config.daily.night and night)
