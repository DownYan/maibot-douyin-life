"""读取 MaiBot 当前人设；插件不维护或修改独立人设。"""

from __future__ import annotations

from typing import Any


_FIELDS = (
    ("personality", "性格"),
    ("behavior_style", "行为风格"),
    ("reply_style", "回复风格"),
    ("multiple_reply_style", "多段回复风格"),
)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return ""


class PersonaService:
    def __init__(self, ctx: Any):
        self.ctx = ctx

    async def prompt(self, scene: str = "default") -> str:
        """每次生成前重新读取，避免人设切换后使用旧文本。"""
        try:
            current = await self.ctx.personality.get_current()
        except Exception as exc:
            logger = getattr(self.ctx, "logger", None)
            if logger:
                logger.warning("读取 MaiBot 当前人设失败，将使用中性表达：%s", exc)
            return ""
        if not isinstance(current, dict):
            return ""

        parts = []
        for key, label in _FIELDS:
            value = _text(current.get(key))
            if value:
                parts.append(f"{label}：\n{value}")
        if scene == "private":
            value = _text(current.get("private_chat_prompts"))
            if value:
                parts.append(f"私聊表达：\n{value}")
        elif scene == "group":
            value = _text(current.get("group_chat_prompt"))
            if value:
                parts.append(f"群聊表达：\n{value}")
        return "\n\n".join(parts)[:12000]
