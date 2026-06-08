from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import httpx
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .auth import expiry, hash_password, hash_token, iso_now, new_token, verify_password
from .commands import command_catalog, execute_command
from .db import connect, init_db
from .migrations import run_migrations
from .runners import augmented_path, detect_runners, hermes_status
from .acp import AcpManager
from .apprunner import AppManager
from .profile_seed import seed_hermes_home
from .settings import hermes_home_for, normalize_config, validate_slug
from .security.command_policy import classify_command
from . import fsapi
logger = logging.getLogger("hive_os.api")

from .provisioning import (
    backfill,
    enroll_all_users_as_members,
    get_team_name,
    provision_shared_project,
    provision_user_workspace,
    scaffold_project_dir,
    set_team_name,
)


class LoginRequest(BaseModel):
    username: str
    password: str = "password123"


class SharedProjectSpec(BaseModel):
    # Pattern enforced at the request layer so an invalid slug fails as 422 BEFORE
    # setup_bootstrap performs any DB writes (prevents a half-bootstrapped admin).
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$")
    name: str | None = Field(default=None, max_length=120)


class BootstrapRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)
    profile_name: str = "Default"
    profile_slug: str = "default"
    team_name: str | None = Field(default=None, max_length=80)
    shared_project: SharedProjectSpec | None = None


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)
    role: str = "member"
    profile_name: str = "Default"
    profile_slug: str = "default"


class UserUpdateRequest(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(environment_admin|member)$")
    password: str | None = Field(default=None, min_length=8)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class InviteCreateRequest(BaseModel):
    role: str = Field(default="member", pattern="^(member|admin)$")
    expires_in_hours: int = Field(default=168, ge=1, le=24 * 90)


class InviteRedeemRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)
    profile_name: str = "Default"
    profile_slug: str = "default"


class AppStartRequest(BaseModel):
    command: str = Field(min_length=1)
    port: int = 5180
    dir: str = ""


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    assignee: str | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(todo|doing|review|done)$")
    assignee: str | None = None


class CommandPolicyRequest(BaseModel):
    command: str = Field(min_length=1)
    project_slug: str
    cwd: str | None = None


class ProjectCreateRequest(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$")
    name: str = Field(min_length=1, max_length=120)
    visibility: str = Field(default="private", pattern="^(private|shared)$")

    @property
    def stripped_name(self) -> str:
        return self.name.strip()

    def model_post_init(self, __context: object) -> None:
        stripped = self.name.strip()
        if not stripped:
            raise ValueError("name must not be empty or whitespace-only")
        object.__setattr__(self, "name", stripped)


class MemberRequest(BaseModel):
    username: str = Field(min_length=1)


class CommandRequest(BaseModel):
    command: str = Field(min_length=1)
    project_slug: str | None = None
    runner_id: str | None = None


class ProfileCreateRequest(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$")
    name: str
    default_model: str | None = None


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    default_model: str | None = None
    is_default: bool | None = None


class SessionCreateRequest(BaseModel):
    title: str | None = None
    project_slug: str | None = None
    profile_id: int | None = None
    runner_id: str = "hermes"
    visibility: str = Field(default="private", pattern="^(private|project)$")


class SessionUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class MessageCreateRequest(BaseModel):
    role: str = Field(pattern="^(user|system|assistant)$")
    content: str = Field(min_length=1)


class RunCreateRequest(BaseModel):
    message: str = Field(min_length=1)
    profile_id: int | None = None
    model: str | None = None


class ChatSendRequest(BaseModel):
    session_id: int | None = None
    message: str = Field(min_length=1)
    project_slug: str | None = None
    profile_id: int | None = None
    runner_id: str = "hermes"
    model: str | None = None


class FileWriteRequest(BaseModel):
    content: str


class FsPathRequest(BaseModel):
    path: str = Field(min_length=1)


class FsRenameRequest(BaseModel):
    from_: str = Field(min_length=1, alias="from")
    to: str = Field(min_length=1)

    model_config = {"populate_by_name": True}


class EventHub:
    """In-process pub/sub so event streams wake the instant a new event is
    written, instead of polling. Durability still goes through the DB; this only
    removes the polling latency. notify() is safe to call from any thread."""

    def __init__(self) -> None:
        self._waiters: dict[int, set[asyncio.Event]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, session_id: int) -> asyncio.Event:
        ev = asyncio.Event()
        self._waiters.setdefault(session_id, set()).add(ev)
        return ev

    def unsubscribe(self, session_id: int, ev: asyncio.Event) -> None:
        bucket = self._waiters.get(session_id)
        if bucket:
            bucket.discard(ev)
            if not bucket:
                self._waiters.pop(session_id, None)

    def _wake(self, session_id: int) -> None:
        for ev in self._waiters.get(session_id, ()):  # set is a snapshot view; ok for set()
            ev.set()

    def notify(self, session_id: int) -> None:
        loop = self._loop
        if loop is None:
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._wake(session_id)            # already on the loop thread
        else:
            loop.call_soon_threadsafe(self._wake, session_id)  # from a worker/threadpool thread


class RunWorker:
    def __init__(self, app: FastAPI):
        self.app = app
        self.task: asyncio.Task | None = None
        self.processes: dict[int, asyncio.subprocess.Process] = {}
        self.active_runs: dict[int, tuple] = {}
        self.stop_event = asyncio.Event()

    def start(self) -> None:
        self.task = asyncio.create_task(self.loop())

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        for proc in list(self.processes.values()):
            if proc.returncode is None:
                proc.terminate()

    async def loop(self) -> None:
        cfg = self.app.state.config
        poll = max(0.05, int(cfg.get("run_worker_poll_interval_ms", 250)) / 1000)
        stale_seconds = int(cfg.get("run_stale_seconds") or 60)
        reap_every = max(5.0, stale_seconds / 2)
        last_reap = 0.0
        while not self.stop_event.is_set():
            try:
                now = time.monotonic()
                if now - last_reap >= reap_every:
                    last_reap = now
                    self.reap_stale_runs(stale_seconds)
                run = self.claim_run()
                if run:
                    await self.execute_run(run)
                else:
                    await asyncio.sleep(poll)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"run worker error: {exc}", flush=True)
                await asyncio.sleep(poll)

    def claim_run(self) -> dict[str, Any] | None:
        db = self.app.state.worker_db
        with self.app.state.db_lock:
            # Per-session serialization: never start a run for a session that
            # already has one in flight, so two agents can't talk over each
            # other on the same chat/task (avoids the "empty reply" collision).
            row = db.execute(
                """
                SELECT * FROM runs WHERE status = 'queued'
                  AND session_id NOT IN (SELECT session_id FROM runs WHERE status = 'running')
                ORDER BY id LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            db.execute(
                "UPDATE runs SET status = 'running', started_at = CURRENT_TIMESTAMP, heartbeat_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'queued'",
                (row["id"],),
            )
            self.add_event(row["id"], row["session_id"], row["project_id"], "run.started", {"runner": row["runner_id"]})
            return dict(db.execute("SELECT * FROM runs WHERE id = ?", (row["id"],)).fetchone())

    def _reconstruct_text(self, run_id: int) -> str:
        """Rebuild the agent's message from streamed deltas already in the DB —
        so output is never lost even if a run is interrupted before its final save."""
        db = self.app.state.worker_db
        rows = db.execute(
            "SELECT payload FROM events WHERE run_id = ? AND type = 'message.delta' ORDER BY seq",
            (run_id,),
        ).fetchall()
        parts = []
        for r in rows:
            try:
                parts.append(json.loads(r["payload"]).get("text", ""))
            except Exception:
                pass
        return "".join(parts).strip()

    def _fail_interrupted(self, run_id: int, session_id: int, project_id: int | None, reason: str) -> None:
        """Terminally close a run that lost its in-memory state (shutdown / crash /
        stale heartbeat). Salvages any streamed output as a saved message."""
        db = self.app.state.worker_db
        with self.app.state.db_lock:
            cur = db.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not cur or cur["status"] != "running":
                return  # already finalized by someone else
            salvaged = self._reconstruct_text(run_id)
            if salvaged:
                db.execute("INSERT INTO messages(session_id, role, content) VALUES (?, 'assistant', ?)", (session_id, salvaged))
            self.add_event(run_id, session_id, project_id, "run.failed", {"error": reason})
            db.execute(
                "UPDATE runs SET status = 'failed', error = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'running'",
                (reason, run_id),
            )

    def reap_stale_runs(self, stale_seconds: int) -> None:
        """Mark runs whose worker stopped checking in (crash without a clean
        restart, wedged event loop) as failed — the watchdog for hangs."""
        db = self.app.state.worker_db
        with self.app.state.db_lock:
            stale = db.execute(
                f"SELECT id, session_id, project_id FROM runs WHERE status = 'running' "
                f"AND (heartbeat_at IS NULL OR heartbeat_at < datetime('now', '-{int(stale_seconds)} seconds'))"
            ).fetchall()
            rows = [dict(r) for r in stale]
        for r in rows:
            self._fail_interrupted(r["id"], r["session_id"], r["project_id"], "Run stalled (no heartbeat)")

    async def _heartbeat(self, run_id: int, interval: float) -> None:
        db = self.app.state.worker_db
        try:
            while True:
                await asyncio.sleep(interval)
                with self.app.state.db_lock:
                    db.execute("UPDATE runs SET heartbeat_at = CURRENT_TIMESTAMP WHERE id = ?", (run_id,))
        except asyncio.CancelledError:
            raise

    def add_event(self, run_id: int, session_id: int, project_id: int | None, event_type: str, payload: dict[str, Any]) -> None:
        db = self.app.state.worker_db
        seq_row = db.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM events WHERE run_id = ?", (run_id,)).fetchone()
        seq = int(seq_row["next_seq"])
        db.execute(
            "INSERT INTO events(run_id, session_id, project_id, seq, type, payload) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, session_id, project_id, seq, event_type, json.dumps(payload)),
        )
        self.app.state.hub.notify(session_id)  # wake live streams immediately

    async def execute_run(self, run: dict[str, Any]) -> None:
        db = self.app.state.worker_db
        cfg = self.app.state.config
        run_id = int(run["id"])
        session_id = int(run["session_id"])
        project_id = run["project_id"]
        hermes_home = run["hermes_home"] or ""
        cwd = str(Path(cfg["workspace_root"]) / "scratch")
        if project_id:
            row = db.execute("SELECT path FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row and row["path"]:
                cwd = row["path"]
        Path(cwd).mkdir(parents=True, exist_ok=True)

        chunks: list[str] = []
        hb_task: asyncio.Task | None = None

        def on_update(u: dict[str, Any]) -> None:
            kind = u.get("sessionUpdate")
            if kind == "agent_message_chunk":
                text = (u.get("content") or {}).get("text", "")
                if text:
                    chunks.append(text)
                    with self.app.state.db_lock:
                        self.add_event(run_id, session_id, project_id, "message.delta", {"text": text})
            elif kind == "agent_thought_chunk":
                text = (u.get("content") or {}).get("text", "")
                if text:
                    with self.app.state.db_lock:
                        self.add_event(run_id, session_id, project_id, "reasoning.delta", {"text": text})
            elif kind == "tool_call":
                with self.app.state.db_lock:
                    self.add_event(run_id, session_id, project_id, "tool.start", {"id": u.get("toolCallId"), "title": u.get("title") or u.get("kind") or "tool"})
            elif kind == "tool_call_update" and u.get("status") in ("completed", "failed"):
                with self.app.state.db_lock:
                    self.add_event(run_id, session_id, project_id, "tool.complete", {"id": u.get("toolCallId"), "status": u.get("status")})

        try:
            proc = await self.app.state.acp_manager.get(hermes_home, cwd)
            srow = db.execute("SELECT acp_session_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
            acp_sid = srow["acp_session_id"] if srow else None
            if acp_sid:
                try:
                    await proc.load_session(acp_sid, cwd)
                except Exception:
                    acp_sid = None  # stale/unknown session -> start fresh
            if not acp_sid:
                acp_sid = await proc.new_session(cwd)
                with self.app.state.db_lock:
                    db.execute("UPDATE sessions SET acp_session_id = ? WHERE id = ?", (acp_sid, session_id))
            self.active_runs[run_id] = (proc, acp_sid)
            hb_task = asyncio.create_task(self._heartbeat(run_id, float(cfg.get("run_heartbeat_seconds") or 10)))
            timeout = int(cfg.get("run_timeout_seconds") or 600)
            stop_reason = await proc.prompt(acp_sid, run["prompt"], on_update, timeout=timeout)

            status_row = db.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
            if status_row and status_row["status"] == "cancelled":
                return
            answer = "".join(chunks).strip() or "Hermes produced no output."
            with self.app.state.db_lock:
                cur = db.execute("INSERT INTO messages(session_id, role, content) VALUES (?, 'assistant', ?)", (session_id, answer))
                db.execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))
                self.add_event(run_id, session_id, project_id, "message.complete", {"message_id": cur.lastrowid, "text": answer})
                self.add_event(run_id, session_id, project_id, "run.completed", {"stop_reason": stop_reason})
                db.execute("UPDATE runs SET status = 'completed', finished_at = CURRENT_TIMESTAMP WHERE id = ?", (run_id,))
                trow = db.execute("SELECT task_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
                if trow and trow["task_id"]:
                    db.execute("UPDATE tasks SET status = 'review', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status != 'done'", (trow["task_id"],))
        except asyncio.CancelledError:
            # Graceful shutdown: close the run cleanly (salvaging streamed text)
            # instead of leaving it orphaned in 'running'.
            self._fail_interrupted(run_id, session_id, project_id, "Interrupted by server shutdown")
            raise
        except asyncio.TimeoutError:
            # Abort the agent's turn so it stops working in the background and the
            # next message isn't "queued for the next turn" against a busy session.
            # session/cancel is best-effort and a turn wedged inside a blocking
            # tool call can't process it, so also recycle (kill) the cached agent
            # process — otherwise the wedged session is reused and every later
            # message in this project returns "Queued for the next turn".
            entry = self.active_runs.get(run_id)
            if entry:
                try: entry[0].cancel(entry[1])
                except Exception: pass
            try:
                await self.app.state.acp_manager.recycle(hermes_home, cwd)
            except Exception:
                logging.getLogger("hive_os.worker").exception("failed to recycle agent process after timeout")
            with self.app.state.db_lock:
                salvaged = self._reconstruct_text(run_id)
                if salvaged:
                    db.execute("INSERT INTO messages(session_id, role, content) VALUES (?, 'assistant', ?)", (session_id, salvaged))
                self.add_event(run_id, session_id, project_id, "run.failed", {"error": "Hermes runner timed out"})
                db.execute("UPDATE runs SET status = 'failed', error = 'Hermes runner timed out', finished_at = CURRENT_TIMESTAMP WHERE id = ?", (run_id,))
        except Exception as exc:
            detail = str(exc)[-2000:]
            with self.app.state.db_lock:
                cur = db.execute("INSERT INTO messages(session_id, role, content) VALUES (?, 'error', ?)", (session_id, f"Run failed: {detail}"))
                self.add_event(run_id, session_id, project_id, "message.complete", {"message_id": cur.lastrowid, "text": f"Run failed: {detail}"})
                self.add_event(run_id, session_id, project_id, "run.failed", {"error": detail})
                db.execute("UPDATE runs SET status = 'failed', error = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?", (detail, run_id))
        finally:
            if hb_task:
                hb_task.cancel()
                with suppress(asyncio.CancelledError):
                    await hb_task
            self.active_runs.pop(run_id, None)

    def cancel(self, run_id: int) -> None:
        entry = self.active_runs.get(run_id)
        if entry:
            proc, sid = entry
            proc.cancel(sid)


def tailscale_base_url() -> str | None:
    """Best-effort detection of this host's Tailscale MagicDNS HTTPS URL."""
    try:
        out = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=4)
        if out.returncode != 0:
            return None
        name = (json.loads(out.stdout).get("Self") or {}).get("DNSName", "").rstrip(".")
        return f"https://{name}" if name else None
    except Exception:
        return None


def create_app(config: dict[str, Any] | None = None) -> FastAPI:
    cfg = normalize_config(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.hub.bind_loop(asyncio.get_running_loop())
        if cfg.get("auto_provision", True):
            try:
                backfill(app.state.db, cfg)
            except Exception:
                logging.getLogger("hive_os.provisioning").exception("startup backfill failed")
        worker = app.state.worker
        # Reclaim runs orphaned by a previous shutdown: a run left in 'running'
        # had in-memory ACP state that's now gone, so it can never complete.
        # Mark it failed (and emit a terminal event) instead of leaving it stuck.
        try:
            with app.state.db_lock:
                orphaned = [dict(r) for r in app.state.worker_db.execute(
                    "SELECT id, session_id, project_id FROM runs WHERE status = 'running'"
                ).fetchall()]
            for r in orphaned:
                worker._fail_interrupted(r["id"], r["session_id"], r["project_id"], "Interrupted by server restart")
        except Exception:
            logging.getLogger("hive_os.worker").exception("orphaned run cleanup failed")
        if cfg.get("start_worker", True):
            worker.start()
        yield
        await worker.stop()
        await app.state.acp_manager.shutdown()
        await app.state.app_manager.shutdown()

    app = FastAPI(title="Hive OS API", version="0.2.0", lifespan=lifespan)
    app.state.config = cfg
    app.state.db = connect(cfg["database_path"])
    app.state.db_lock = __import__("threading").RLock()
    init_db(app.state.db, cfg.get("seed_users") or [], lambda username, slug: hermes_home_for(cfg, username, slug), source_hermes_home=cfg.get("source_hermes_home"))
    run_migrations(app.state.db, cfg.get("database_path"))  # versioned migrations (backs up before applying)
    app.state.worker_db = connect(cfg["database_path"])  # dedicated connection for the async run worker
    app.state.worker = RunWorker(app)
    app.state.acp_manager = AcpManager()
    app.state.app_manager = AppManager()
    app.state.login_attempts = {}  # ip -> [monotonic timestamps] for login throttling
    app.state.hub = EventHub()

    web_dist_path = cfg.get("web_dist_path")
    if web_dist_path and Path(web_dist_path).exists():
        dist = Path(web_dist_path)
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")
        icons = dist / "icons"
        if icons.exists():
            app.mount("/icons", StaticFiles(directory=str(icons)), name="icons")

        @app.get("/manifest.webmanifest", include_in_schema=False)
        def web_manifest():
            return FileResponse(dist / "manifest.webmanifest")

        @app.get("/sw.js", include_in_schema=False)
        def service_worker():
            return FileResponse(dist / "sw.js")

        @app.get("/", include_in_schema=False)
        def web_index():
            return FileResponse(dist / "index.html")

    def db():
        return app.state.db

    def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
        token_hash = hash_token(authorization.removeprefix("Bearer ").strip())
        with app.state.db_lock:
            row = db().execute(
                """
                SELECT u.* FROM auth_sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.revoked_at IS NULL AND (s.expires_at IS NULL OR s.expires_at > CURRENT_TIMESTAMP)
                """,
                (token_hash,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
        return dict(row)

    def admin_user(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user["role"] != "environment_admin":
            raise HTTPException(status_code=403, detail="environment admin required")
        return user

    def public_user(user: dict[str, Any]) -> dict[str, Any]:
        return {"id": user["id"], "username": user["username"], "role": user["role"], "os_user": user["os_user"]}

    def get_user(username: str) -> dict[str, Any]:
        row = db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        return dict(row)

    def create_token(user_id: int) -> str:
        token = new_token()
        db().execute(
            "INSERT INTO auth_sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (hash_token(token), user_id, expiry(int(cfg.get("auth_token_ttl_hours") or 0))),
        )
        return token

    def create_profile_for(user: dict[str, Any], slug: str, name: str, default_model: str | None = None, is_default: bool = False) -> dict[str, Any]:
        slug = validate_slug(slug)
        home = hermes_home_for(cfg, user["username"], slug)
        home.mkdir(parents=True, exist_ok=True)
        seed_hermes_home(Path(cfg["source_hermes_home"]), home)
        if is_default:
            db().execute("UPDATE profiles SET is_default = 0 WHERE user_id = ?", (user["id"],))
        cur = db().execute(
            "INSERT INTO profiles(user_id, slug, name, hermes_home, default_model, is_default) VALUES (?, ?, ?, ?, ?, ?)",
            (user["id"], slug, name, str(home), default_model, 1 if is_default else 0),
        )
        return dict(db().execute("SELECT * FROM profiles WHERE id = ?", (cur.lastrowid,)).fetchone())

    def ensure_default_profile(user: dict[str, Any]) -> dict[str, Any]:
        row = db().execute("SELECT * FROM profiles WHERE user_id = ? AND is_default = 1 ORDER BY id LIMIT 1", (user["id"],)).fetchone()
        if row:
            return dict(row)
        row = db().execute("SELECT * FROM profiles WHERE user_id = ? ORDER BY id LIMIT 1", (user["id"],)).fetchone()
        if row:
            db().execute("UPDATE profiles SET is_default = 1 WHERE id = ?", (row["id"],))
            return dict(row)
        return create_profile_for(user, "default", "Default", is_default=True)

    def profile_for_user(profile_id: int | None, user: dict[str, Any]) -> dict[str, Any]:
        if profile_id is None:
            return ensure_default_profile(user)
        row = db().execute("SELECT * FROM profiles WHERE id = ? AND user_id = ?", (profile_id, user["id"])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="profile not found")
        return dict(row)

    def visible_project(slug: str, user: dict[str, Any]) -> dict[str, Any]:
        row = db().execute(
            """
            SELECT p.*, u.username AS owner, pm.role
            FROM projects p
            JOIN users u ON u.id = p.owner_user_id
            JOIN project_members pm ON pm.project_id = p.id
            WHERE p.slug = ? AND pm.user_id = ? AND p.archived_at IS NULL
            """,
            (slug, user["id"]),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="project not found")
        return dict(row)

    def require_owner(slug: str, user: dict[str, Any]) -> dict[str, Any]:
        project = visible_project(slug, user)
        if project["role"] != "owner":
            raise HTTPException(status_code=403, detail="project owner required")
        return project

    def session_for_user(session_id: int, user: dict[str, Any]) -> dict[str, Any]:
        row = db().execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="session not found")
        session = dict(row)
        if session["owner_user_id"] == user["id"]:
            if session["project_id"]:
                member = db().execute("SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?", (session["project_id"], user["id"])).fetchone()
                if not member:
                    raise HTTPException(status_code=404, detail="session not found")
            return session
        if session["visibility"] == "project" and session["project_id"]:
            member = db().execute("SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?", (session["project_id"], user["id"])).fetchone()
            if member:
                return session
        raise HTTPException(status_code=404, detail="session not found")

    def run_projectctl(*args: str) -> None:
        # Single-user $HOME deployments don't manage OS ownership/ACLs: the dir is
        # scaffolded by scaffold_project_dir and access is enforced at the app layer
        # (DB membership). Only the privileged /srv multi-user install opts in.
        if not cfg.get("manage_os_acl"):
            return
        base_command = cfg.get("projectctl_command") or [str(cfg["projectctl_path"])]
        command = [*base_command, "--root", str(cfg["workspace_root"]), *args]
        try:
            subprocess.run(command, check=True, text=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip()
            raise HTTPException(status_code=500, detail=detail) from exc

    def project_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {"slug": row["slug"], "name": row["name"], "path": row["path"], "owner": row.get("owner"), "role": row.get("role"), "visibility": row.get("visibility", "private")}

    def profile_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {"id": row["id"], "slug": row["slug"], "name": row["name"], "default_model": row["default_model"], "is_default": bool(row["is_default"]), "hermes_home": row["hermes_home"]}

    def session_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {"id": row["id"], "title": row["title"], "runner_id": row["runner_id"], "profile_id": row["profile_id"], "profile_slug": row.get("profile_slug"), "profile_name": row.get("profile_name"), "project_slug": row.get("project_slug"), "project_name": row.get("project_name"), "visibility": row["visibility"], "updated_at": row["updated_at"], "task_id": row.get("task_id"), "task_title": row.get("task_title")}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/setup/status")
    def setup_status() -> dict[str, Any]:
        count = db().execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        return {
            "bootstrap_required": count == 0,
            "mode": "team",
            "team_name": get_team_name(db(), cfg),
            "hermes_profiles_root": cfg["hermes_profiles_root"],
        }

    @app.post("/api/setup/bootstrap", status_code=201)
    def setup_bootstrap(payload: BootstrapRequest) -> dict[str, Any]:
        if db().execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]:
            raise HTTPException(status_code=409, detail="bootstrap already completed")
        username = validate_slug(payload.username)
        cur = db().execute(
            "INSERT INTO users(username, os_user, role, password_hash, password_set_at) VALUES (?, ?, 'environment_admin', ?, ?)",
            (username, username, hash_password(payload.password), iso_now()),
        )
        user = dict(db().execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())
        profile = create_profile_for(user, payload.profile_slug, payload.profile_name, is_default=True)
        team_name = payload.team_name or cfg.get("default_team_name") or "Team"
        set_team_name(db(), team_name)
        # Provision the shared project FIRST so that if the admin's username equals the
        # shared slug, their private workspace correctly falls back to <username>-home.
        shared = None
        warning = None
        if payload.shared_project:
            shared_name = payload.shared_project.name or team_name
            try:
                shared = provision_shared_project(
                    db(), cfg, validate_slug(payload.shared_project.slug), shared_name, user
                )
            except Exception as exc:
                logger.exception("setup_bootstrap: provision_shared_project failed")
                try:
                    db().execute(
                        "INSERT INTO audit_log(actor_user_id, action, target_type, target_id, metadata) "
                        "VALUES (?, 'workspace.provision.error', 'project', ?, ?)",
                        (user["id"], payload.shared_project.slug, f'{{"error": "{exc}"}}'),
                    )
                except Exception:
                    pass
                warning = f"shared project could not be created: {exc}"
        provision_user_workspace(db(), cfg, user)
        token = create_token(user["id"])
        return {
            "token": token,
            "user": public_user(user),
            "profile": profile_payload(profile),
            "team_name": team_name,
            "shared_project": project_payload(shared) if shared else None,
            "warning": warning,
        }

    @app.post("/auth/login")
    def login(payload: LoginRequest, request: Request):
        # Simple in-memory brute-force throttle: cap failed attempts per client IP
        # within a rolling window before locking out for the rest of it.
        limit = int(cfg.get("login_max_attempts") or 10)
        window = float(cfg.get("login_window_seconds") or 300)
        ip = (request.client.host if request.client else "?") or "?"
        now = time.monotonic()
        attempts = app.state.login_attempts
        recent = [t for t in attempts.get(ip, []) if now - t < window]
        if len(recent) >= limit:
            attempts[ip] = recent
            raise HTTPException(status_code=429, detail="too many login attempts — try again later")
        try:
            user = get_user(payload.username)
            ok = verify_password(payload.password, user.get("password_hash"))
        except HTTPException:
            ok = False
        if not ok:
            recent.append(now)
            attempts[ip] = recent
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")
        attempts.pop(ip, None)  # reset on success
        token = create_token(user["id"])
        return {"token": token, "user": public_user(user)}

    @app.post("/auth/logout")
    def logout(user: dict[str, Any] = Depends(current_user), authorization: str | None = Header(default=None)):
        if authorization:
            db().execute("UPDATE auth_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE token_hash = ?", (hash_token(authorization.removeprefix("Bearer ").strip()),))
        return {"ok": True}

    @app.get("/api/me")
    def me(user: dict[str, Any] = Depends(current_user)):
        return public_user(user)

    @app.post("/api/me/password")
    def change_password(payload: PasswordChangeRequest, user: dict[str, Any] = Depends(current_user)):
        if not verify_password(payload.current_password, user.get("password_hash")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="current password is incorrect")
        db().execute(
            "UPDATE users SET password_hash = ?, password_set_at = ? WHERE id = ?",
            (hash_password(payload.new_password), iso_now(), user["id"]),
        )
        db().execute("UPDATE auth_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user["id"],))
        db().execute(
            "INSERT INTO audit_log(actor_user_id, action, target_type, target_id) VALUES (?, 'user.password.change', 'user', ?)",
            (user["id"], user["username"]),
        )
        return {"ok": True, "message": "password changed; please log in again"}

    @app.post("/api/policy/command/check")
    def command_policy_check(payload: CommandPolicyRequest, user: dict[str, Any] = Depends(current_user)):
        project = visible_project(payload.project_slug, user)
        cwd = Path(payload.cwd) if payload.cwd else Path(project["path"])
        decision = classify_command(payload.command, cwd, Path(project["path"]))
        db().execute(
            "INSERT INTO audit_log(actor_user_id, action, target_type, target_id, metadata) VALUES (?, 'policy.command.check', 'project', ?, ?)",
            (user["id"], payload.project_slug, json.dumps({"command": payload.command, "allowed": decision.allowed, "category": decision.category, "reason": decision.reason})),
        )
        return {"allowed": decision.allowed, "category": decision.category, "reason": decision.reason, "argv": decision.argv}

    @app.get("/api/audit")
    def list_audit(limit: int = 300, user: dict[str, Any] = Depends(admin_user)):
        rows = db().execute(
            "SELECT a.id, a.action, a.target_type, a.target_id, a.metadata, a.created_at, u.username AS actor "
            "FROM audit_log a LEFT JOIN users u ON u.id = a.actor_user_id ORDER BY a.id DESC LIMIT ?",
            (max(1, min(limit, 1000)),),
        ).fetchall()
        return {"entries": [dict(r) for r in rows]}

    @app.get("/api/users")
    def list_users(user: dict[str, Any] = Depends(admin_user)):
        rows = db().execute("SELECT id, username, os_user, role, created_at FROM users ORDER BY username").fetchall()
        return {"users": [dict(row) for row in rows]}

    @app.post("/api/users", status_code=201)
    def create_user(payload: UserCreateRequest, user: dict[str, Any] = Depends(admin_user)):
        username = validate_slug(payload.username)
        try:
            cur = db().execute(
                "INSERT INTO users(username, os_user, role, password_hash, password_set_at) VALUES (?, ?, ?, ?, ?)",
                (username, username, payload.role, hash_password(payload.password), iso_now()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="username already exists") from None
        created = dict(db().execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())
        profile = create_profile_for(created, payload.profile_slug, payload.profile_name, is_default=True)
        provision_user_workspace(db(), cfg, created)
        return {"user": public_user(created), "profile": profile_payload(profile)}

    def _admin_count(exclude_id: int | None = None) -> int:
        q = "SELECT COUNT(*) AS c FROM users WHERE role = 'environment_admin'"
        params: tuple = ()
        if exclude_id is not None:
            q += " AND id != ?"; params = (exclude_id,)
        return db().execute(q, params).fetchone()["c"]

    def _purge_project(project: dict[str, Any]) -> None:
        """Delete a project's on-disk dir (jailed to workspace root) + its DB row."""
        path = project.get("path")
        root = str(Path(cfg["workspace_root"]).resolve())
        if path:
            try:
                rp = Path(path).resolve()
                if str(rp).startswith(root + os.sep) and rp.exists():
                    __import__("shutil").rmtree(rp)
            except Exception:
                logging.getLogger("hive_os.projects").exception("project dir removal failed for %s", project.get("slug"))
        db().execute("DELETE FROM projects WHERE id = ?", (project["id"],))

    @app.patch("/api/users/{user_id}")
    def update_user(user_id: int, payload: UserUpdateRequest, user: dict[str, Any] = Depends(admin_user)):
        target = db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="user not found")
        target = dict(target)
        if payload.role and payload.role != target["role"]:
            # Don't let the last admin demote themselves into a lockout.
            if target["role"] == "environment_admin" and payload.role != "environment_admin" and _admin_count(exclude_id=user_id) == 0:
                raise HTTPException(status_code=400, detail="cannot demote the last environment admin")
            db().execute("UPDATE users SET role = ? WHERE id = ?", (payload.role, user_id))
            db().execute("INSERT INTO audit_log(actor_user_id, action, target_type, target_id) VALUES (?, 'user.role', 'user', ?)", (user["id"], str(user_id)))
        if payload.password:
            db().execute("UPDATE users SET password_hash = ?, password_set_at = ? WHERE id = ?", (hash_password(payload.password), iso_now(), user_id))
            db().execute("UPDATE auth_sessions SET revoked_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))  # force re-login
            db().execute("INSERT INTO audit_log(actor_user_id, action, target_type, target_id) VALUES (?, 'user.password_reset', 'user', ?)", (user["id"], str(user_id)))
        return {"user": public_user(dict(db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()))}

    @app.delete("/api/users/{user_id}")
    def delete_user(user_id: int, user: dict[str, Any] = Depends(admin_user)):
        target = db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="user not found")
        if user_id == user["id"]:
            raise HTTPException(status_code=400, detail="cannot delete yourself")
        if dict(target)["role"] == "environment_admin" and _admin_count(exclude_id=user_id) == 0:
            raise HTTPException(status_code=400, detail="cannot delete the last environment admin")
        shared_owned = db().execute("SELECT COUNT(*) AS c FROM projects WHERE owner_user_id = ? AND visibility = 'shared'", (user_id,)).fetchone()["c"]
        if shared_owned:
            raise HTTPException(status_code=409, detail="user owns shared project(s) — transfer or delete those first")
        # Remove the user's private projects (personal workspace etc.) so the
        # non-cascading owner_user_id FK doesn't block the delete.
        for prow in db().execute("SELECT * FROM projects WHERE owner_user_id = ?", (user_id,)).fetchall():
            _purge_project(dict(prow))
        # Null out non-cascading references so the delete (and history) stays intact.
        db().execute("UPDATE tasks SET created_by = NULL WHERE created_by = ?", (user_id,))
        db().execute("UPDATE invites SET created_by = NULL WHERE created_by = ?", (user_id,))
        db().execute("UPDATE invites SET used_by = NULL WHERE used_by = ?", (user_id,))
        db().execute("UPDATE audit_log SET actor_user_id = NULL WHERE actor_user_id = ?", (user_id,))
        db().execute("INSERT INTO audit_log(actor_user_id, action, target_type, target_id) VALUES (?, 'user.delete', 'user', ?)", (user["id"], str(user_id)))
        db().execute("DELETE FROM users WHERE id = ?", (user_id,))  # cascades sessions, profiles, members, runs
        return {"ok": True, "id": user_id}

    # ── Invite links (admin generates, user self-registers) ──────────
    def _valid_invite(code: str) -> dict[str, Any]:
        row = db().execute("SELECT * FROM invites WHERE code = ?", (code,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="invalid invite code")
        inv = dict(row)
        if inv["used_at"]:
            raise HTTPException(status_code=410, detail="invite already used")
        if inv["expires_at"] and inv["expires_at"] < iso_now():
            raise HTTPException(status_code=410, detail="invite expired")
        return inv

    @app.post("/api/invites", status_code=201)
    def create_invite(payload: InviteCreateRequest, user: dict[str, Any] = Depends(admin_user)):
        code = new_token()[:14]
        expires = expiry(payload.expires_in_hours)
        db().execute(
            "INSERT INTO invites(code, role, created_by, expires_at) VALUES (?, ?, ?, ?)",
            (code, payload.role, user["id"], expires),
        )
        base = cfg.get("public_base_url") or tailscale_base_url()
        link = f"{base.rstrip('/')}/?invite={code}" if base else None
        return {"code": code, "role": payload.role, "expires_at": expires, "link": link}

    @app.get("/api/invites")
    def list_invites(user: dict[str, Any] = Depends(admin_user)):
        rows = db().execute(
            "SELECT i.code, i.role, i.expires_at, i.used_at, u.username AS used_by "
            "FROM invites i LEFT JOIN users u ON u.id = i.used_by ORDER BY i.created_at DESC"
        ).fetchall()
        return {"invites": [dict(r) for r in rows]}

    @app.delete("/api/invites/{code}")
    def revoke_invite(code: str, user: dict[str, Any] = Depends(admin_user)):
        db().execute("DELETE FROM invites WHERE code = ? AND used_at IS NULL", (code,))
        return {"ok": True, "code": code}

    @app.get("/api/invites/{code}")
    def preview_invite(code: str):
        inv = _valid_invite(code)
        return {"valid": True, "role": inv["role"]}

    @app.post("/api/invites/{code}/redeem", status_code=201)
    def redeem_invite(code: str, payload: InviteRedeemRequest):
        inv = _valid_invite(code)
        username = validate_slug(payload.username)
        user_role = "environment_admin" if inv["role"] == "admin" else "member"
        try:
            cur = db().execute(
                "INSERT INTO users(username, os_user, role, password_hash, password_set_at) VALUES (?, ?, ?, ?, ?)",
                (username, username, user_role, hash_password(payload.password), iso_now()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="username already exists") from None
        created = dict(db().execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())
        profile = create_profile_for(created, payload.profile_slug, payload.profile_name, is_default=True)
        db().execute("UPDATE invites SET used_at = ?, used_by = ? WHERE code = ?", (iso_now(), created["id"], code))
        db().execute("INSERT INTO audit_log(actor_user_id, action, target_type, target_id) VALUES (?, 'invite.redeem', 'user', ?)", (created["id"], username))
        try:
            provision_user_workspace(db(), cfg, created)
        except Exception:
            logging.getLogger("hive_os.provisioning").exception("invite redeem provisioning failed")
        token = create_token(created["id"])
        return {"token": token, "user": public_user(created), "profile": profile_payload(profile)}

    # ── Tasks (kanban + a dedicated agent thread per task) ───────────
    def task_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {"id": row["id"], "project_slug": row.get("project_slug"), "session_id": row["session_id"], "title": row["title"], "description": row["description"], "status": row["status"], "assignee": row["assignee"], "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def _task_for_user(task_id: int, user: dict[str, Any]) -> dict[str, Any]:
        row = db().execute("SELECT t.*, p.slug AS project_slug FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.id = ?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="task not found")
        visible_project(row["project_slug"], user)  # ACL: must be a project member
        return dict(row)

    def _task_audit(user: dict[str, Any], action: str, task_id: int) -> None:
        db().execute("INSERT INTO audit_log(actor_user_id, action, target_type, target_id) VALUES (?, ?, 'task', ?)", (user["id"], action, str(task_id)))

    @app.get("/api/projects/{slug}/tasks")
    def list_tasks(slug: str, user: dict[str, Any] = Depends(current_user)):
        project = visible_project(slug, user)
        rows = db().execute("SELECT t.*, ? AS project_slug FROM tasks t WHERE t.project_id = ? ORDER BY t.updated_at DESC, t.id DESC", (slug, project["id"])).fetchall()
        return {"tasks": [task_payload(dict(r)) for r in rows]}

    @app.post("/api/projects/{slug}/tasks", status_code=201)
    def create_task(slug: str, payload: TaskCreateRequest, user: dict[str, Any] = Depends(current_user)):
        project = visible_project(slug, user)
        profile = profile_for_user(None, user)
        title = payload.title.strip()
        cur = db().execute(
            "INSERT INTO tasks(project_id, title, description, assignee, created_by) VALUES (?, ?, ?, ?, ?)",
            (project["id"], title, payload.description or "", payload.assignee, user["id"]),
        )
        task_id = int(cur.lastrowid)
        scur = db().execute(
            "INSERT INTO sessions(title, project_id, owner_user_id, profile_id, runner_id, visibility, task_id) VALUES (?, ?, ?, ?, 'hermes', 'project', ?)",
            (title[:80], project["id"], user["id"], profile["id"], task_id),
        )
        db().execute("UPDATE tasks SET session_id = ? WHERE id = ?", (scur.lastrowid, task_id))
        _task_audit(user, "task.create", task_id)
        row = db().execute("SELECT t.*, ? AS project_slug FROM tasks t WHERE t.id = ?", (slug, task_id)).fetchone()
        return task_payload(dict(row))

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: int, user: dict[str, Any] = Depends(current_user)):
        return task_payload(_task_for_user(task_id, user))

    @app.patch("/api/tasks/{task_id}")
    def update_task(task_id: int, payload: TaskUpdateRequest, user: dict[str, Any] = Depends(current_user)):
        _task_for_user(task_id, user)
        fields: list[str] = []
        vals: list[Any] = []
        if payload.title is not None and payload.title.strip():
            fields.append("title = ?"); vals.append(payload.title.strip())
        if payload.description is not None:
            fields.append("description = ?"); vals.append(payload.description)
        if payload.status is not None:
            fields.append("status = ?"); vals.append(payload.status)
        if payload.assignee is not None:
            fields.append("assignee = ?"); vals.append(payload.assignee or None)
        if fields:
            fields.append("updated_at = CURRENT_TIMESTAMP")
            db().execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", (*vals, task_id))
            _task_audit(user, "task.update", task_id)
        row = db().execute("SELECT t.*, p.slug AS project_slug FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.id = ?", (task_id,)).fetchone()
        return task_payload(dict(row))

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: int, user: dict[str, Any] = Depends(current_user)):
        task = _task_for_user(task_id, user)
        db().execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if task["session_id"]:
            db().execute("DELETE FROM sessions WHERE id = ?", (task["session_id"],))
        _task_audit(user, "task.delete", task_id)
        return {"ok": True, "id": task_id}

    @app.get("/api/profiles")
    def list_profiles(user: dict[str, Any] = Depends(current_user)):
        ensure_default_profile(user)
        rows = db().execute("SELECT * FROM profiles WHERE user_id = ? ORDER BY is_default DESC, name", (user["id"],)).fetchall()
        return {"profiles": [profile_payload(dict(row)) for row in rows]}

    @app.post("/api/profiles", status_code=201)
    def create_profile(payload: ProfileCreateRequest, user: dict[str, Any] = Depends(current_user)):
        try:
            profile = create_profile_for(user, payload.slug, payload.name, payload.default_model)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="profile slug already exists") from None
        return profile_payload(profile)

    @app.patch("/api/profiles/{profile_id}")
    def update_profile(profile_id: int, payload: ProfileUpdateRequest, user: dict[str, Any] = Depends(current_user)):
        profile_for_user(profile_id, user)
        if payload.is_default:
            db().execute("UPDATE profiles SET is_default = 0 WHERE user_id = ?", (user["id"],))
            db().execute("UPDATE profiles SET is_default = 1 WHERE id = ?", (profile_id,))
        if payload.name is not None:
            db().execute("UPDATE profiles SET name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (payload.name, profile_id))
        if payload.default_model is not None:
            db().execute("UPDATE profiles SET default_model = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (payload.default_model, profile_id))
        return profile_payload(dict(db().execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()))

    @app.delete("/api/profiles/{profile_id}")
    def delete_profile(profile_id: int, user: dict[str, Any] = Depends(current_user)):
        profile = profile_for_user(profile_id, user)
        count = db().execute("SELECT COUNT(*) AS c FROM profiles WHERE user_id = ?", (user["id"],)).fetchone()["c"]
        if count <= 1 or profile["is_default"]:
            raise HTTPException(status_code=400, detail="cannot delete last or default profile")
        db().execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        return {"ok": True}

    @app.get("/api/runners/detect")
    def runners_detect(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        runners = detect_runners()
        for runner in runners:
            if runner["id"] != "hermes":
                runner["runnable"] = False
                runner["detectionOnly"] = True
                runner["notes"] = "Future adapter; Hive OS Team Mode is Hermes-first."
        return {
            "user": user["username"],
            "runners": runners,
            "hermes": hermes_status(source_home=cfg.get("source_hermes_home"), binary=cfg.get("hermes_bin"), path_env=None),
        }

    @app.get("/api/commands/catalog")
    def commands_catalog(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        return {"user": user["username"], **command_catalog()}

    @app.post("/api/commands/execute")
    def commands_execute(payload: CommandRequest, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if payload.project_slug:
            visible_project(payload.project_slug, user)
        return execute_command(payload.command, user=user, project_slug=payload.project_slug, runner_id="hermes")

    @app.get("/api/projects")
    def list_projects(user: dict[str, Any] = Depends(current_user)):
        rows = db().execute(
            """
            SELECT p.slug, p.name, p.path, p.visibility, u.username AS owner, pm.role
            FROM projects p
            JOIN users u ON u.id = p.owner_user_id
            JOIN project_members pm ON pm.project_id = p.id
            WHERE pm.user_id = ? AND p.archived_at IS NULL
            ORDER BY p.created_at DESC, p.id DESC
            """,
            (user["id"],),
        ).fetchall()
        return {"projects": [project_payload(dict(row)) for row in rows]}

    @app.post("/api/projects", status_code=201)
    def create_project(payload: ProjectCreateRequest, user: dict[str, Any] = Depends(current_user)):
        if db().execute("SELECT id FROM projects WHERE slug = ?", (payload.slug,)).fetchone():
            raise HTTPException(status_code=409, detail="project slug already exists")
        path = str(Path(cfg["workspace_root"]) / "projects" / payload.slug)
        run_projectctl("create-project", payload.slug, "--owner", user["os_user"])
        scaffold_project_dir(cfg, payload.slug)
        cur = db().execute(
            "INSERT INTO projects(slug, name, path, owner_user_id, visibility) VALUES (?, ?, ?, ?, ?)",
            (payload.slug, payload.name, path, user["id"], payload.visibility),
        )
        project_id = cur.lastrowid
        db().execute("INSERT INTO project_members(project_id, user_id, role) VALUES (?, ?, 'owner')", (project_id, user["id"]))
        if payload.visibility == "shared":
            enroll_all_users_as_members(db(), project_id, user["id"])
        db().execute("INSERT INTO audit_log(actor_user_id, action, target_type, target_id) VALUES (?, 'project.create', 'project', ?)", (user["id"], payload.slug))
        row = dict(db().execute("SELECT p.*, ? AS owner, 'owner' AS role FROM projects p WHERE p.id = ?", (user["username"], project_id)).fetchone())
        return project_payload(row)

    @app.get("/api/projects/{slug}")
    def get_project(slug: str, user: dict[str, Any] = Depends(current_user)):
        return project_payload(visible_project(slug, user))

    @app.post("/api/projects/{slug}/invite")
    def invite_user(slug: str, payload: MemberRequest, user: dict[str, Any] = Depends(current_user)):
        project = require_owner(slug, user)
        target = get_user(payload.username)
        db().execute("INSERT OR REPLACE INTO project_members(project_id, user_id, role) VALUES (?, ?, 'collaborator')", (project["id"], target["id"]))
        db().execute("INSERT INTO audit_log(actor_user_id, action, target_type, target_id) VALUES (?, 'project.invite', 'project', ?)", (user["id"], slug))
        run_projectctl("invite", slug, target["os_user"])
        return {"ok": True, "slug": slug, "username": target["username"], "role": "collaborator"}

    @app.post("/api/projects/{slug}/remove")
    def remove_user(slug: str, payload: MemberRequest, user: dict[str, Any] = Depends(current_user)):
        project = require_owner(slug, user)
        target = get_user(payload.username)
        if target["id"] == project["owner_user_id"]:
            raise HTTPException(status_code=400, detail="cannot remove project owner")
        db().execute("DELETE FROM project_members WHERE project_id = ? AND user_id = ?", (project["id"], target["id"]))
        db().execute("INSERT INTO audit_log(actor_user_id, action, target_type, target_id) VALUES (?, 'project.remove', 'project', ?)", (user["id"], slug))
        run_projectctl("remove", slug, target["os_user"])
        return {"ok": True, "slug": slug, "username": target["username"]}

    @app.delete("/api/projects/{slug}")
    def delete_project(slug: str, user: dict[str, Any] = Depends(current_user)):
        project = visible_project(slug, user)
        if project["role"] != "owner" and user["role"] != "environment_admin":
            raise HTTPException(status_code=403, detail="project owner or environment admin required")
        db().execute("INSERT INTO audit_log(actor_user_id, action, target_type, target_id) VALUES (?, 'project.delete', 'project', ?)", (user["id"], slug))
        _purge_project(project)  # rm dir (jailed) + DB row; cascades members/tasks, nulls session/run links
        return {"ok": True, "slug": slug}

    @app.get("/api/projects/{slug}/members")
    def list_members(slug: str, user: dict[str, Any] = Depends(current_user)):
        project = visible_project(slug, user)
        rows = db().execute(
            """
            SELECT u.username, u.os_user, pm.role
            FROM project_members pm JOIN users u ON u.id = pm.user_id
            WHERE pm.project_id = ? ORDER BY pm.role DESC, u.username
            """,
            (project["id"],),
        ).fetchall()
        return {"members": [dict(row) for row in rows]}

    @app.get("/api/projects/{slug}/invitable")
    def invitable_users(slug: str, user: dict[str, Any] = Depends(current_user)):
        """Users the owner can still invite (registered, not already members).

        Owner-only, so a project owner can populate an invite picker without the
        admin-only /api/users endpoint.
        """
        project = require_owner(slug, user)
        rows = db().execute(
            "SELECT username FROM users "
            "WHERE id NOT IN (SELECT user_id FROM project_members WHERE project_id = ?) "
            "ORDER BY username",
            (project["id"],),
        ).fetchall()
        return {"users": [row["username"] for row in rows]}

    def _project_root(slug: str, user: dict[str, Any]) -> Path:
        project = visible_project(slug, user)
        return Path(project["path"])

    def _audit_fs(user: dict[str, Any], action: str, slug: str, path: str) -> None:
        db().execute(
            "INSERT INTO audit_log(actor_user_id, action, target_type, target_id, metadata) VALUES (?, ?, 'project', ?, ?)",
            (user["id"], action, slug, json.dumps({"path": path})),
        )

    @app.get("/api/projects/{slug}/tree")
    def project_tree(slug: str, path: str = "", user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            return {"path": path, "entries": fsapi.list_tree(root, path)}
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/projects/{slug}/file")
    def project_read_file(slug: str, path: str, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            return {"path": path, "content": fsapi.read_file(root, path)}
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/projects/{slug}/file")
    def project_write_file(slug: str, path: str, payload: FileWriteRequest, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            fsapi.write_file(root, path, payload.content)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_fs(user, "file.write", slug, path)
        return {"ok": True, "path": path}

    @app.post("/api/projects/{slug}/upload")
    async def project_upload(slug: str, file: UploadFile = File(...), user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        name = Path(file.filename or "file").name or "file"
        try:
            target = fsapi.resolve_in_project(root, f"uploads/{name}")
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():  # de-dupe: name.ext -> name-1.ext
            stem, suffix, i = target.stem, target.suffix, 1
            while target.exists():
                target = target.parent / f"{stem}-{i}{suffix}"; i += 1
        target.write_bytes(await file.read())
        rel = f"uploads/{target.name}"
        _audit_fs(user, "file.upload", slug, rel)
        return {"path": rel, "name": target.name}

    # ── Run & preview a project app (managed dev server + proxy) ──────
    @app.post("/api/projects/{slug}/app/start")
    async def app_start(slug: str, payload: AppStartRequest, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        cwd = root
        if payload.dir:
            try:
                cwd = fsapi.resolve_in_project(root, payload.dir)
            except fsapi.FsError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if not cwd.is_dir():
                raise HTTPException(status_code=400, detail="folder not found")
        await app.state.app_manager.start(slug, str(cwd), payload.command, int(payload.port or 5180))
        _audit_fs(user, "app.start", slug, f"{payload.dir or '.'}: {payload.command}")
        return {"ok": True}

    @app.post("/api/projects/{slug}/app/stop")
    async def app_stop(slug: str, user: dict[str, Any] = Depends(current_user)):
        _project_root(slug, user)
        await app.state.app_manager.stop(slug)
        return {"ok": True}

    @app.get("/api/projects/{slug}/app/status")
    def app_status(slug: str, user: dict[str, Any] = Depends(current_user)):
        _project_root(slug, user)
        return app.state.app_manager.status(slug)

    _HOP = {"connection", "keep-alive", "transfer-encoding", "content-encoding", "content-length", "host"}

    @app.api_route("/api/appview/{token}/{slug}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def app_view(token: str, slug: str, path: str, request: Request):
        # Proxy to the project's running app. Token in path so the iframe + its
        # relative assets authenticate (same pattern as file preview).
        user = user_from_token_query(token)
        _project_root(slug, user)  # access check
        port = app.state.app_manager.port(slug)
        if not port:
            raise HTTPException(status_code=503, detail="app not running")
        url = f"http://127.0.0.1:{port}/{path}"
        fwd = {k: v for k, v in request.headers.items() if k.lower() not in _HOP}
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                up = await client.request(request.method, url, params=request.query_params, content=await request.body(), headers=fwd)
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="app not reachable yet") from None
        out = {k: v for k, v in up.headers.items() if k.lower() not in _HOP}
        return Response(content=up.content, status_code=up.status_code, headers=out, media_type=up.headers.get("content-type"))

    @app.post("/api/projects/{slug}/fs/mkdir")
    def project_mkdir(slug: str, payload: FsPathRequest, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            fsapi.mkdir(root, payload.path)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_fs(user, "fs.mkdir", slug, payload.path)
        return {"ok": True, "path": payload.path}

    @app.post("/api/projects/{slug}/fs/rename")
    def project_rename(slug: str, payload: FsRenameRequest, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            fsapi.rename(root, payload.from_, payload.to)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_fs(user, "fs.rename", slug, f"{payload.from_} -> {payload.to}")
        return {"ok": True}

    @app.delete("/api/projects/{slug}/fs")
    def project_delete(slug: str, path: str, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            fsapi.delete(root, path)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_fs(user, "fs.delete", slug, path)
        return {"ok": True, "path": path}

    @app.get("/api/projects/{slug}/raw")
    def project_raw(slug: str, path: str, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        try:
            target = fsapi.resolve_in_project(root, path)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not target.is_file():
            raise HTTPException(status_code=404, detail="not a file")
        return FileResponse(str(target), filename=target.name)

    @app.get("/api/preview/{token}/{slug}/{file_path:path}")
    def project_preview(token: str, slug: str, file_path: str):
        # Serve a project file inline for live preview (e.g. rendering a built
        # site in an <iframe>). The token sits in the path — not a header — so the
        # iframe AND its relative asset requests (styles.css, script.js) all carry
        # it (same exposure as the SSE ?token= stream). Path-jailed to the project.
        user = user_from_token_query(token)
        root = _project_root(slug, user)
        try:
            target = fsapi.resolve_in_project(root, file_path)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not target.is_file():
            raise HTTPException(status_code=404, detail="not a file")
        return FileResponse(str(target))  # inline (no attachment) so HTML/CSS/JS render

    @app.get("/api/projects/{slug}/wiki/all")
    def project_wiki_all(slug: str, user: dict[str, Any] = Depends(current_user)):
        root = _project_root(slug, user)
        return {"notes": fsapi.walk_files(root, "wiki")}

    # ── Personal per-user wiki (workspace_root/users/<username>/wiki) ──
    def _wiki_root(user: dict[str, Any]) -> Path:
        root = Path(cfg["workspace_root"]) / "users" / validate_slug(user["username"]) / "wiki"
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
            (root / "index.md").write_text(f"# {user['username']}'s wiki\n\nYour personal notes.\n", encoding="utf-8")
        return root

    def _audit_wiki(user: dict[str, Any], action: str, path: str) -> None:
        db().execute(
            "INSERT INTO audit_log(actor_user_id, action, target_type, target_id, metadata) VALUES (?, ?, 'wiki', ?, ?)",
            (user["id"], action, user["username"], json.dumps({"path": path})),
        )

    @app.get("/api/wiki/all")
    def wiki_all(user: dict[str, Any] = Depends(current_user)):
        return {"notes": fsapi.walk_files(_wiki_root(user))}

    @app.get("/api/wiki/tree")
    def wiki_tree(path: str = "", user: dict[str, Any] = Depends(current_user)):
        try:
            return {"path": path, "entries": fsapi.list_tree(_wiki_root(user), path)}
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/wiki/file")
    def wiki_read_file(path: str, user: dict[str, Any] = Depends(current_user)):
        try:
            return {"path": path, "content": fsapi.read_file(_wiki_root(user), path)}
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/wiki/file")
    def wiki_write_file(path: str, payload: FileWriteRequest, user: dict[str, Any] = Depends(current_user)):
        try:
            fsapi.write_file(_wiki_root(user), path, payload.content)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_wiki(user, "wiki.write", path)
        return {"ok": True, "path": path}

    @app.post("/api/wiki/fs/mkdir")
    def wiki_mkdir(payload: FsPathRequest, user: dict[str, Any] = Depends(current_user)):
        try:
            fsapi.mkdir(_wiki_root(user), payload.path)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_wiki(user, "wiki.mkdir", payload.path)
        return {"ok": True, "path": payload.path}

    @app.post("/api/wiki/fs/rename")
    def wiki_rename(payload: FsRenameRequest, user: dict[str, Any] = Depends(current_user)):
        try:
            fsapi.rename(_wiki_root(user), payload.from_, payload.to)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_wiki(user, "wiki.rename", f"{payload.from_} -> {payload.to}")
        return {"ok": True}

    @app.delete("/api/wiki/fs")
    def wiki_delete(path: str, user: dict[str, Any] = Depends(current_user)):
        try:
            fsapi.delete(_wiki_root(user), path)
        except fsapi.FsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _audit_wiki(user, "wiki.delete", path)
        return {"ok": True, "path": path}

    @app.get("/api/sessions")
    def list_sessions(user: dict[str, Any] = Depends(current_user)):
        rows = db().execute(
            """
            SELECT s.*, p.slug AS project_slug, p.name AS project_name, pr.slug AS profile_slug, pr.name AS profile_name, t.title AS task_title
            FROM sessions s
            LEFT JOIN projects p ON p.id = s.project_id
            LEFT JOIN profiles pr ON pr.id = s.profile_id
            LEFT JOIN tasks t ON t.id = s.task_id
            WHERE s.owner_user_id = ?
            ORDER BY s.updated_at DESC, s.id DESC
            """,
            (user["id"],),
        ).fetchall()
        return {"sessions": [session_payload(dict(row)) for row in rows]}

    @app.get("/api/search")
    def search(q: str = "", user: dict[str, Any] = Depends(current_user)):
        term = q.strip()
        if len(term) < 2:
            return {"projects": [], "chats": [], "tasks": [], "messages": []}
        like = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        uid = user["id"]
        projects = [dict(r) for r in db().execute(
            "SELECT p.slug, p.name FROM projects p JOIN project_members pm ON pm.project_id = p.id "
            "WHERE pm.user_id = ? AND (p.name LIKE ? ESCAPE '\\' OR p.slug LIKE ? ESCAPE '\\') ORDER BY p.name LIMIT 10",
            (uid, like, like)).fetchall()]
        chats = [dict(r) for r in db().execute(
            "SELECT id, title, task_id FROM sessions WHERE owner_user_id = ? AND title LIKE ? ESCAPE '\\' "
            "ORDER BY updated_at DESC LIMIT 10", (uid, like)).fetchall()]
        tasks = [dict(r) for r in db().execute(
            "SELECT t.id, t.title, t.status, p.slug AS project_slug FROM tasks t JOIN projects p ON p.id = t.project_id "
            "JOIN project_members pm ON pm.project_id = p.id WHERE pm.user_id = ? "
            "AND (t.title LIKE ? ESCAPE '\\' OR t.description LIKE ? ESCAPE '\\') ORDER BY t.updated_at DESC LIMIT 10",
            (uid, like, like)).fetchall()]
        msgs = [dict(r) for r in db().execute(
            "SELECT m.session_id, m.role, substr(m.content, 1, 160) AS snippet, s.title AS session_title, s.task_id "
            "FROM messages m JOIN sessions s ON s.id = m.session_id WHERE s.owner_user_id = ? "
            "AND m.content LIKE ? ESCAPE '\\' ORDER BY m.id DESC LIMIT 15", (uid, like)).fetchall()]
        return {"projects": projects, "chats": chats, "tasks": tasks, "messages": msgs}

    @app.post("/api/sessions", status_code=201)
    def create_session(payload: SessionCreateRequest, user: dict[str, Any] = Depends(current_user)):
        profile = profile_for_user(payload.profile_id, user)
        project_id = None
        if payload.project_slug:
            project = visible_project(payload.project_slug, user)
            project_id = project["id"]
        title = (payload.title or "New session").strip() or "New session"
        cur = db().execute(
            "INSERT INTO sessions(title, project_id, owner_user_id, profile_id, runner_id, visibility) VALUES (?, ?, ?, ?, 'hermes', ?)",
            (title, project_id, user["id"], profile["id"], payload.visibility),
        )
        row = db().execute(
            """
            SELECT s.*, p.slug AS project_slug, p.name AS project_name, pr.slug AS profile_slug, pr.name AS profile_name, t.title AS task_title
            FROM sessions s LEFT JOIN projects p ON p.id=s.project_id LEFT JOIN profiles pr ON pr.id=s.profile_id LEFT JOIN tasks t ON t.id=s.task_id WHERE s.id=?
            """,
            (cur.lastrowid,),
        ).fetchone()
        return session_payload(dict(row))

    @app.patch("/api/sessions/{session_id}")
    def update_session(session_id: int, payload: SessionUpdateRequest, user: dict[str, Any] = Depends(current_user)):
        session = session_for_user(session_id, user)
        if session["owner_user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="only the session owner can rename it")
        title = payload.title.strip() or session["title"]
        db().execute("UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (title, session_id))
        row = db().execute(
            """
            SELECT s.*, p.slug AS project_slug, p.name AS project_name, pr.slug AS profile_slug, pr.name AS profile_name, t.title AS task_title
            FROM sessions s LEFT JOIN projects p ON p.id=s.project_id LEFT JOIN profiles pr ON pr.id=s.profile_id LEFT JOIN tasks t ON t.id=s.task_id WHERE s.id=?
            """,
            (session_id,),
        ).fetchone()
        return session_payload(dict(row))

    @app.delete("/api/sessions/{session_id}")
    def delete_session(session_id: int, user: dict[str, Any] = Depends(current_user)):
        session = session_for_user(session_id, user)
        if session["owner_user_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="only the session owner can delete it")
        db().execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return {"ok": True, "id": session_id}

    @app.get("/api/sessions/{session_id}/messages")
    def list_messages(session_id: int, user: dict[str, Any] = Depends(current_user)):
        session_for_user(session_id, user)
        rows = db().execute("SELECT id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)).fetchall()
        return {"messages": [dict(row) for row in rows]}

    @app.post("/api/sessions/{session_id}/messages")
    def create_message(session_id: int, payload: MessageCreateRequest, user: dict[str, Any] = Depends(current_user)):
        session_for_user(session_id, user)
        cur = db().execute("INSERT INTO messages(session_id, role, content) VALUES (?, ?, ?)", (session_id, payload.role, payload.content))
        db().execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))
        return {"id": cur.lastrowid, "role": payload.role, "content": payload.content}

    @app.post("/api/sessions/{session_id}/runs", status_code=202)
    def create_run(session_id: int, payload: RunCreateRequest, user: dict[str, Any] = Depends(current_user)):
        session = session_for_user(session_id, user)
        profile = profile_for_user(payload.profile_id or session.get("profile_id"), user)
        db().execute("INSERT INTO messages(session_id, role, content) VALUES (?, 'user', ?)", (session_id, payload.message))
        cur = db().execute(
            """
            INSERT INTO runs(session_id, project_id, user_id, profile_id, runner_id, status, prompt, model, hermes_home)
            VALUES (?, ?, ?, ?, 'hermes', 'queued', ?, ?, ?)
            """,
            (session_id, session["project_id"], user["id"], profile["id"], payload.message, payload.model or profile["default_model"], profile["hermes_home"]),
        )
        run_id = int(cur.lastrowid)
        app.state.worker.add_event(run_id, session_id, session["project_id"], "run.queued", {"runner": "hermes"})
        db().execute("UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))
        if session.get("task_id"):
            db().execute("UPDATE tasks SET status = 'doing', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status != 'done'", (session["task_id"],))
        return {"run_id": run_id, "session_id": session_id, "status": "queued"}

    @app.post("/api/chat/send", status_code=202)
    def chat_send(payload: ChatSendRequest, user: dict[str, Any] = Depends(current_user)):
        if payload.runner_id != "hermes":
            raise HTTPException(status_code=400, detail="Hive OS Team Mode is Hermes-first; other adapters are not wired yet")
        if payload.session_id is None:
            created = create_session(SessionCreateRequest(title=payload.message[:60] or "New session", project_slug=payload.project_slug, profile_id=payload.profile_id), user)
            session_id = created["id"]
        else:
            session_id = payload.session_id
        return create_run(session_id, RunCreateRequest(message=payload.message, profile_id=payload.profile_id, model=payload.model), user)

    def event_payload(row: sqlite3.Row) -> dict[str, Any]:
        event = dict(row)
        event["payload"] = json.loads(event["payload"] or "{}")
        return event

    @app.get("/api/sessions/{session_id}/events")
    def list_events(session_id: int, after_seq: int = 0, user: dict[str, Any] = Depends(current_user)):
        session_for_user(session_id, user)
        rows = db().execute("SELECT * FROM events WHERE session_id = ? AND seq > ? ORDER BY id ASC", (session_id, after_seq)).fetchall()
        return {"events": [event_payload(row) for row in rows]}

    def user_from_token_query(token: str) -> dict[str, Any]:
        with app.state.db_lock:
            row = db().execute(
                "SELECT u.* FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.revoked_at IS NULL AND (s.expires_at IS NULL OR s.expires_at > CURRENT_TIMESTAMP)",
                (hash_token(token),),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
        return dict(row)

    @app.get("/api/sessions/{session_id}/events/stream")
    async def stream_events(request: Request, session_id: int, after_seq: int = 0, token: str = ""):
        user = user_from_token_query(token)
        session_for_user(session_id, user)

        async def gen():
            hub = app.state.hub
            ev = hub.subscribe(session_id)
            last_id = 0
            try:
                while not await request.is_disconnected():
                    ev.clear()  # clear before reading so a notify during the read isn't lost
                    rows = db().execute("SELECT * FROM events WHERE session_id = ? AND id > ? ORDER BY id ASC", (session_id, last_id)).fetchall()
                    for row in rows:
                        if row["seq"] <= after_seq:
                            last_id = max(last_id, row["id"])
                            continue
                        last_id = row["id"]
                        yield f"id: {row['id']}\nevent: {row['type']}\ndata: {json.dumps(event_payload(row))}\n\n"
                    try:
                        await asyncio.wait_for(ev.wait(), timeout=15)  # instant wake on new event; 15s = keepalive fallback
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                hub.unsubscribe(session_id, ev)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.websocket("/api/ws/sessions/{session_id}")
    async def ws_events(websocket: WebSocket, session_id: int, token: str):
        user = None
        token_hash = hash_token(token)
        with app.state.db_lock:
            row = db().execute("SELECT u.* FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.revoked_at IS NULL", (token_hash,)).fetchone()
        if row:
            user = dict(row)
        if not user:
            await websocket.close(code=4401)
            return
        session_for_user(session_id, user)
        await websocket.accept()
        hub = app.state.hub
        ev = hub.subscribe(session_id)
        last_id = 0
        try:
            while True:
                ev.clear()
                rows = db().execute("SELECT * FROM events WHERE session_id=? AND id>? ORDER BY id ASC", (session_id, last_id)).fetchall()
                for row in rows:
                    last_id = row["id"]
                    await websocket.send_json(event_payload(row))
                try:
                    await asyncio.wait_for(ev.wait(), timeout=15)
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            return
        finally:
            hub.unsubscribe(session_id, ev)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: int, user: dict[str, Any] = Depends(current_user)):
        row = db().execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="run not found")
        session_for_user(row["session_id"], user)
        return dict(row)

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: int, user: dict[str, Any] = Depends(current_user)):
        row = db().execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="run not found")
        session_for_user(row["session_id"], user)
        db().execute("UPDATE runs SET status = 'cancelled', finished_at = CURRENT_TIMESTAMP WHERE id = ? AND status IN ('queued','running')", (run_id,))
        app.state.worker.add_event(run_id, row["session_id"], row["project_id"], "run.cancelled", {})
        app.state.worker.cancel(run_id)
        return {"ok": True, "run_id": run_id, "status": "cancelled"}

    return app


def _config_from_env() -> dict[str, Any]:
    """Config for the ASGI entrypoint (`uvicorn hive_os_api.main:app`), from env.

    Mirrors scripts/serve.py so running either way behaves the same and never
    falls back to the /srv demo defaults.
    """
    workspace_root = Path(os.environ.get("HIVEOS_WORKSPACE_ROOT", str(Path.home() / ".local/share/hive-os")))
    return {
        "database_path": os.environ.get("HIVEOS_DB_PATH", str(workspace_root / "hive-os.db")),
        "workspace_root": str(workspace_root),
        "hermes_profiles_root": os.environ.get("HIVEOS_HERMES_PROFILES_ROOT", str(workspace_root / "hermes-profiles")),
        "web_dist_path": os.environ.get("HIVEOS_WEB_DIST") or None,
        "public_base_url": os.environ.get("HIVEOS_PUBLIC_BASE_URL") or None,
        "projectctl_command": os.environ.get("HIVEOS_PROJECTCTL_COMMAND", "").split() or None,
    }


# Lazily build the ASGI app only when `app` is actually accessed (e.g. by
# uvicorn), so importing this module (tests, serve.py) has no side effects and
# never opens the /srv demo database.
def __getattr__(name: str):
    if name == "app":
        return create_app(_config_from_env())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
