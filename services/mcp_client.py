"""受控 MCP stdio 客户端，连接保留的抖音浏览器内核。"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


class StdioTransport:
    def __init__(self, command: list[str], env: dict[str, str], cwd: Path):
        self.command = command
        self.env = env
        self.cwd = cwd
        self.process: asyncio.subprocess.Process | None = None
        self.reader_task: asyncio.Task | None = None
        self.pending: dict[int, asyncio.Future] = {}
        self.next_id = 0
        self.write_lock = asyncio.Lock()

    async def start(self) -> None:
        if self.process and self.process.returncode is None:
            return
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.cwd),
            env=self.env,
        )
        self.reader_task = asyncio.create_task(self._read_loop())
        await self.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "maibot-douyin-life", "version": "1.0.0"},
        }, 30)
        await self._notify("notifications/initialized", {})

    async def _notify(self, method: str, params: dict) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params})

    async def _send(self, payload: dict) -> None:
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP 进程未启动")
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        async with self.write_lock:
            self.process.stdin.write(data)
            await self.process.stdin.drain()

    async def _read_loop(self) -> None:
        try:
            while self.process and self.process.stdout:
                line = await self.process.stdout.readline()
                if not line:
                    break
                message = json.loads(line.decode("utf-8"))
                request_id = message.get("id")
                future = self.pending.pop(request_id, None)
                if future and not future.done():
                    if "error" in message:
                        future.set_exception(RuntimeError(str(message["error"])))
                    else:
                        future.set_result(message.get("result", {}))
        except Exception as exc:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(exc)
            self.pending.clear()

    async def request(self, method: str, params: dict, timeout: float) -> dict:
        await self.start() if method != "initialize" else None
        self.next_id += 1
        request_id = self.next_id
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        await self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        return await asyncio.wait_for(future, timeout)

    async def close(self) -> None:
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self.reader_task = None
        process, self.process = self.process, None
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()


class McpClient:
    def __init__(self, data_dir: str | Path = "", runtime_dir: str | Path = "", config: Any = None, transport: Any = None):
        self.data_dir = Path(data_dir) if data_dir else Path.cwd()
        self.runtime_dir = Path(runtime_dir) if runtime_dir else self.data_dir / "tmp"
        self.config = config
        self.transport = transport
        self._started = transport is not None

    def _build_transport(self) -> StdioTransport:
        plugin_dir = Path(__file__).resolve().parents[1]
        script = plugin_dir / "vendor" / "douyin-mcp" / "mcp_server.py"
        advanced = getattr(self.config, "advanced", None)
        python_path = getattr(advanced, "python_path", "python") or "python"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update({
            "PYTHONUTF8": "1",
            "MAIBOT_DOUYIN_HOME": str(self.data_dir),
            "DSH_DOUYIN_HOME": str(self.data_dir),
            # 内核只执行经 WriteService 授权、限额和回执记录的调用。
            "DOUYIN_ALLOW_WRITES": "1",
            "DOUYIN_VIDEO_LAB": str(plugin_dir / "video-understanding-lab"),
            "TEMP": str(self.runtime_dir),
            "TMP": str(self.runtime_dir),
            "TMPDIR": str(self.runtime_dir),
        })
        cdp_url = getattr(advanced, "cdp_url", "")
        chrome_path = getattr(advanced, "chrome_path", "")
        if cdp_url:
            env["DOUYIN_CDP_URL"] = cdp_url
        if chrome_path:
            env["DOUYIN_CHROME_PATH"] = chrome_path
        return StdioTransport([python_path, str(script)], env, self.data_dir)

    async def start(self) -> None:
        if self._started:
            return
        self.transport = self._build_transport()
        await self.transport.start()
        self._started = True

    async def call(self, name: str, args: dict[str, Any], timeout: float = 45) -> dict[str, Any]:
        try:
            await self.start()
            response = await asyncio.wait_for(
                self.transport.request("tools/call", {"name": name, "arguments": args}, timeout),
                timeout,
            )
            if response.get("isError"):
                return {"ok": False, "error": str(response.get("content") or "MCP 工具错误")}
            content = response.get("content", [])
            if isinstance(content, list) and content and isinstance(content[0], dict):
                text = content[0].get("text", "")
                try:
                    result = json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    return {"ok": False, "error": "MCP 返回内容不是有效的 JSON 对象"}
                if isinstance(result, dict):
                    return result
            if isinstance(response.get("structuredContent"), dict):
                return response["structuredContent"]
            return {"ok": False, "error": "MCP 返回内容不是有效的 JSON 对象"}
        except asyncio.TimeoutError:
            return {"ok": False, "error": f"调用 {name} 超时（{timeout:g} 秒）"}
        except Exception as exc:
            return {"ok": False, "error": f"调用 {name} 失败：{exc}"}

    async def close(self) -> None:
        if self.transport:
            await self.transport.close()
        self._started = False
