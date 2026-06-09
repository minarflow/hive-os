"""Run a project's app (dev server) as a managed background process and proxy it.

Lets you preview something the agent built — e.g. `npm run dev` — live inside
Hive OS. One managed process per project; the HTTP proxy forwards to its port so
relative assets resolve and no port is exposed directly.
"""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from typing import Any

from .runners import augmented_path

IS_WINDOWS = os.name == "nt"


class AppManager:
    def __init__(self) -> None:
        self._apps: dict[str, dict[str, Any]] = {}

    async def start(self, slug: str, cwd: str, command: str, port: int) -> None:
        await self.stop(slug)
        env = os.environ.copy()
        env["PATH"] = augmented_path(env.get("PATH"))
        env["PORT"] = str(port)
        # Run the command string through the platform shell, in its own process
        # group so we can clean-kill the whole tree later.
        if IS_WINDOWS:
            shell_argv = ["cmd", "/c", command]
            extra = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        else:
            shell_argv = ["bash", "-lc", command]
            extra = {"start_new_session": True}
        proc = await asyncio.create_subprocess_exec(
            *shell_argv, cwd=cwd, env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            **extra,
        )
        self._apps[slug] = {"proc": proc, "port": port, "command": command, "started_at": time.time(), "log": []}
        asyncio.create_task(self._drain(slug, proc))

    async def _drain(self, slug: str, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            app = self._apps.get(slug)
            if app:
                app["log"].append(line.decode("utf-8", "replace").rstrip())
                del app["log"][:-200]

    async def stop(self, slug: str) -> None:
        app = self._apps.pop(slug, None)
        if not app:
            return
        proc = app["proc"]
        if proc.returncode is None:
            try:
                if IS_WINDOWS:
                    # taskkill /T ends the child tree; fall back to terminate().
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                   capture_output=True, check=False)
                else:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass

    def status(self, slug: str) -> dict[str, Any]:
        app = self._apps.get(slug)
        if not app:
            return {"running": False}
        if app["proc"].returncode is not None:  # exited on its own
            self._apps.pop(slug, None)
            return {"running": False, "command": app["command"], "log": app["log"][-40:], "exited": True}
        return {"running": True, "port": app["port"], "command": app["command"], "log": app["log"][-40:]}

    def port(self, slug: str) -> int | None:
        app = self._apps.get(slug)
        return app["port"] if app and app["proc"].returncode is None else None

    async def shutdown(self) -> None:
        for slug in list(self._apps):
            await self.stop(slug)
