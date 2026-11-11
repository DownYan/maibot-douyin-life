"""原子 JSON 账本：限额、去重和平台回执状态。"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class Ledger:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "ledger.json"
        self._lock = asyncio.Lock()

    @staticmethod
    def _day() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _read(self) -> dict[str, Any]:
        try:
            import json
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("records"), dict):
                return data
        except (OSError, ValueError):
            pass
        return {"schemaVersion": 2, "records": {}}

    def _write(self, data: dict[str, Any]) -> None:
        import json
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.path)

    @staticmethod
    def _succeeded(result: dict[str, Any], kind: str) -> bool:
        if result.get("ok") is not True:
            return False
        if kind in {"pick", "watch"}:
            return True
        return result.get("verified") is True

    async def consume(self, kind: str, key: str, daily_limit: int, per_run_limit: int, run_id: str) -> dict[str, Any]:
        async with self._lock:
            data = self._read()
            records = data["records"].setdefault(kind, {})
            previous = records.get(key, {})
            if previous.get("status") == "succeeded":
                return {"allowed": False, "reason": "duplicate"}
            if previous.get("status") in {"reserved", "pending", "unknown"}:
                return {"allowed": False, "reason": "pending"}

            today = self._day()
            active = [r for r in records.values() if r.get("day") == today and r.get("status") in {"reserved", "succeeded", "pending", "unknown"}]
            if len(active) >= daily_limit:
                return {"allowed": False, "reason": "daily_limit"}
            run_active = [r for r in active if r.get("runId") == run_id]
            if len(run_active) >= per_run_limit:
                return {"allowed": False, "reason": "per_run_limit"}

            records[key] = {"day": today, "runId": run_id, "status": "reserved", "at": datetime.now().isoformat()}
            self._write(data)
            return {"allowed": True, "reason": ""}

    async def record_result(self, kind: str, key: str, result: dict[str, Any]) -> None:
        async with self._lock:
            data = self._read()
            records = data["records"].setdefault(kind, {})
            previous = records.get(key, {"day": self._day(), "runId": "", "at": datetime.now().isoformat()})
            if self._succeeded(result, kind):
                status = "succeeded"
            elif result.get("status") in {"pending", "unknown"} or (result.get("ok") is True and result.get("verified") is False):
                status = "unknown"
            else:
                records.pop(key, None)
                self._write(data)
                return
            records[key] = {**previous, "status": status, "result": result, "updatedAt": datetime.now().isoformat()}
            self._write(data)

    async def is_processed(self, kind: str, key: str) -> bool:
        async with self._lock:
            return self._read()["records"].get(kind, {}).get(key, {}).get("status") == "succeeded"

    async def count_today(self, kind: str) -> int:
        async with self._lock:
            records = self._read()["records"].get(kind, {})
            return sum(1 for item in records.values() if item.get("day") == self._day() and item.get("status") == "succeeded")

    async def pending(self, kind: str = "") -> list[dict[str, Any]]:
        async with self._lock:
            records = self._read()["records"]
            kinds = [kind] if kind else list(records)
            return [
                {"kind": name, "key": key, **value}
                for name in kinds
                for key, value in records.get(name, {}).items()
                if value.get("status") in {"reserved", "pending", "unknown"}
            ]
