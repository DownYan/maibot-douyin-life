"""插件本地事实记忆，不读取或修改人设。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


class MemoryStore:
    def __init__(self, data_dir: str | Path):
        self.directory = Path(data_dir) / "memory"

    def add(self, text: str) -> None:
        clean = str(text).strip().replace("\x00", "")[:4000]
        if not clean:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{datetime.now():%Y-%m}.md"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"- {datetime.now():%Y-%m-%d %H:%M:%S} {clean}\n")

    def recent(self, limit: int = 24) -> list[str]:
        if not self.directory.exists():
            return []
        lines: list[str] = []
        for path in sorted(self.directory.glob("*.md"))[-2:]:
            try:
                lines.extend(path.read_text(encoding="utf-8").splitlines())
            except OSError:
                continue
        facts = [re.sub(r"^- \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ", "", line) for line in lines if line.strip()]
        return facts[-limit:]
