import logging

import pytest

from plugin import DouyinLifePlugin


class Logger:
    def info(self, *args): pass
    def warning(self, *args): pass
    def error(self, *args): pass


class Paths:
    def __init__(self, root):
        self.data_dir = root / "data"
        self.runtime_dir = root / "runtime"


class Personality:
    async def get_current(self): return {"personality": "测试"}


class LLM:
    async def generate(self, **kwargs): return {"success": True, "response": "好"}


class Ctx:
    logger = Logger()
    personality = Personality()
    llm = LLM()

    def __init__(self, tmp_path): self.paths = Paths(tmp_path)


@pytest.mark.asyncio
async def test_lifecycle_wires_services_and_unload_closes_scheduler(tmp_path):
    plugin = DouyinLifePlugin()
    plugin._set_context(Ctx(tmp_path))
    plugin.set_plugin_config({})
    await plugin.on_load()

    assert plugin.rounds is not None
    assert plugin.direct_messages is not None
    assert plugin.comments is not None
    assert plugin.comfy is not None
    assert plugin.tools.comfy is plugin.comfy
    assert plugin.writes.comfy is plugin.comfy
    assert plugin.scheduler.tasks

    tasks = list(plugin.scheduler.tasks)
    await plugin.on_unload()
    assert all(task.done() or task.cancelled() for task in tasks)


@pytest.mark.asyncio
async def test_config_update_restarts_scheduler_without_duplicate_tasks(tmp_path):
    plugin = DouyinLifePlugin()
    plugin._set_context(Ctx(tmp_path))
    plugin.set_plugin_config({})
    await plugin.on_load()
    old_tasks = list(plugin.scheduler.tasks)

    await plugin.on_config_update("self", {}, "2")

    assert len(plugin.scheduler.tasks) == len(old_tasks)
    assert not (set(plugin.scheduler.tasks) & set(old_tasks))
    await plugin.on_unload()


@pytest.mark.asyncio
async def test_cleanup_preserves_login_ledger_and_memory(tmp_path):
    plugin = DouyinLifePlugin()
    plugin._set_context(Ctx(tmp_path))
    plugin.set_plugin_config({})
    await plugin.on_load()
    data = plugin.ctx.paths.data_dir
    protected = [data / "browser" / "Default" / "Cookies", data / "ledger.json", data / "memory" / "2026-11.md"]
    temporary = data / ".tmp" / "cache.bin"
    for path in protected + [temporary]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("keep" if path in protected else "drop", encoding="utf-8")

    result = await plugin.cleanup({})

    assert result["ok"] is True
    assert not temporary.exists()
    assert all(path.exists() for path in protected)
    await plugin.on_unload()
