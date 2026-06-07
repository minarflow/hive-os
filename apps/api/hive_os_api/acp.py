"""Agent Client Protocol (ACP) integration for the Hermes runner.

Hive OS drives Hermes through ACP (the same standard editors like Zed/VS Code
use): a persistent `hermes acp` subprocess per profile, JSON-RPC 2.0 over stdio
(newline-delimited). This gives native session continuity (load/resume), token
streaming, and tool events — without coupling to any vendor-specific gateway.

One AcpProcess per HERMES_HOME hosts many ACP sessions (one per Hive OS chat).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

from .runners import augmented_path

logger = logging.getLogger("hive_os.acp")

UpdateHandler = Callable[[dict[str, Any]], None]
READ_LIMIT = 16 * 1024 * 1024


def config_sig(hermes_home: str) -> tuple:
    """Signature of the profile's tool config (MCP + skills). When it changes the
    cached agent process is recycled so newly added MCP/skills load on the next run."""
    if not hermes_home:
        return ()
    base = Path(hermes_home)
    sig = []
    for rel in ("config.yaml", "skills", ".skills_prompt_snapshot.json"):
        try:
            sig.append(round((base / rel).stat().st_mtime, 3))
        except OSError:
            sig.append(0.0)
    return tuple(sig)


class AcpError(Exception):
    pass


class AcpProcess:
    def __init__(self, hermes_home: str, cwd: str):
        self.hermes_home = hermes_home
        self.cwd = cwd
        self.proc: asyncio.subprocess.Process | None = None
        self._next_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._handlers: dict[str, UpdateHandler] = {}   # sessionId -> update handler
        self._reader: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._started = False
        self.config_sig: tuple = ()

    async def start(self) -> None:
        if self._started:
            return
        env = os.environ.copy()
        env["HERMES_HOME"] = self.hermes_home or ""
        env["PATH"] = augmented_path(env.get("PATH"))
        if self.hermes_home:
            os.makedirs(self.hermes_home, exist_ok=True)
        os.makedirs(self.cwd, exist_ok=True)
        self.proc = await asyncio.create_subprocess_exec(
            "hermes", "acp", "--accept-hooks",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env, cwd=self.cwd, limit=READ_LIMIT,
        )
        self._reader = asyncio.create_task(self._read_loop())
        await self._request("initialize", {"protocolVersion": 1, "clientCapabilities": {}})
        self.config_sig = config_sig(self.hermes_home)
        self._started = True

    async def _read_loop(self) -> None:
        assert self.proc and self.proc.stdout
        while True:
            try:
                line = await self.proc.stdout.readline()
            except (asyncio.LimitOverrunError, ValueError):
                continue  # skip oversized frame
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._dispatch(msg)
        # process exited: fail any pending requests
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(AcpError("hermes acp process exited"))
        self._pending.clear()
        self._started = False

    def _dispatch(self, msg: dict[str, Any]) -> None:
        if "id" in msg and ("result" in msg or "error" in msg):
            fut = self._pending.pop(msg["id"], None)
            if fut and not fut.done():
                if "error" in msg:
                    fut.set_exception(AcpError(str(msg["error"])))
                else:
                    fut.set_result(msg["result"])
            return
        method = msg.get("method")
        if not method:
            return
        if method == "session/update":
            params = msg.get("params", {})
            handler = self._handlers.get(params.get("sessionId"))
            if handler:
                try:
                    handler(params.get("update", {}))
                except Exception:
                    logger.exception("acp update handler failed")
            return
        # agent -> client request (needs a response by id)
        if "id" in msg:
            self._respond_to_agent(msg)

    def _respond_to_agent(self, msg: dict[str, Any]) -> None:
        method = msg.get("method", "")
        params = msg.get("params", {})
        result: dict[str, Any]
        if method == "session/request_permission":
            options = params.get("options", [])
            allow = next((o for o in options if o.get("kind") in ("allow_always", "allow_once")), None)
            if allow:
                result = {"outcome": {"outcome": "selected", "optionId": allow["optionId"]}}
            else:
                result = {"outcome": {"outcome": "cancelled"}}
        else:
            # Unsupported agent->client request (e.g. fs/* we didn't advertise).
            self._send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "unsupported"}})
            return
        self._send({"jsonrpc": "2.0", "id": msg["id"], "result": result})

    def _send(self, obj: dict[str, Any]) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write((json.dumps(obj) + "\n").encode())

    async def _request(self, method: str, params: dict[str, Any]) -> Any:
        self._next_id += 1
        mid = self._next_id
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[mid] = fut
        self._send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        if self.proc and self.proc.stdin:
            await self.proc.stdin.drain()
        return await fut

    async def new_session(self, cwd: str) -> str:
        res = await self._request("session/new", {"cwd": cwd, "mcpServers": []})
        return res["sessionId"]

    async def load_session(self, session_id: str, cwd: str) -> None:
        await self._request("session/load", {"sessionId": session_id, "cwd": cwd, "mcpServers": []})

    async def prompt(self, session_id: str, text: str, on_update: UpdateHandler, timeout: float = 600) -> str:
        self._handlers[session_id] = on_update
        try:
            res = await asyncio.wait_for(
                self._request("session/prompt", {"sessionId": session_id, "prompt": [{"type": "text", "text": text}]}),
                timeout=timeout,
            )
            return res.get("stopReason", "end_turn")
        finally:
            self._handlers.pop(session_id, None)

    def cancel(self, session_id: str) -> None:
        try:
            self._send({"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": session_id}})
        except Exception:
            pass

    async def stop(self) -> None:
        if self._reader:
            self._reader.cancel()
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
        self._started = False


class AcpManager:
    """Owns one AcpProcess per (HERMES_HOME, cwd), started on demand.

    Keyed by cwd because Hermes writes files relative to the agent process's
    working directory — so each project needs its own process rooted there.
    """

    def __init__(self) -> None:
        self._procs: dict[tuple[str, str], AcpProcess] = {}
        self._lock = asyncio.Lock()

    async def get(self, hermes_home: str, cwd: str) -> AcpProcess:
        key = (hermes_home, cwd)
        async with self._lock:
            proc = self._procs.get(key)
            if proc and proc._started:
                # Recycle if MCP/skill config changed since this process started,
                # so newly added tools load on the next run (no manual restart).
                if proc.config_sig == config_sig(hermes_home):
                    return proc
                logger.info("acp: tool config changed, recycling process for %s", hermes_home)
                await proc.stop()
                self._procs.pop(key, None)
            proc = AcpProcess(hermes_home, cwd)
            await proc.start()
            self._procs[key] = proc
            return proc

    async def shutdown(self) -> None:
        for proc in list(self._procs.values()):
            await proc.stop()
        self._procs.clear()
