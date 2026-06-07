# Hive OS Architecture

## Goal

Build a runner-agnostic operating layer for human + AI agent teams. Hive OS provides a mobile-first PWA and backend for chat, projects, tasks, workflows, wikis, artifacts, project invites, and access control.

## Non-goals for v1

- Not a replacement for Hermes, Claude Code, Codex, or other runners.
- Not a full enterprise IAM system.
- Not a cloud SaaS by default.
- Not a native mobile app yet; Flutter/native can come after PWA validation.

## Core model

```text
User -> Agent Identity -> Runner -> Workspace/Project Context
```

- **User**: app login mapped to an OS user.
- **Agent identity**: the user's configured assistant/runner context.
- **Runner**: executable or API that performs agent work; Hermes is first.
- **Project**: private-by-default workspace with wiki/tasks/artifacts.
- **Membership**: app-level project ACL + filesystem ACL.

## Runtime/workspace split

Source code lives in a normal repo, e.g.:

```text
/path/to/hive-os
```

Runtime workspace lives outside the repo, e.g.:

```text
/srv/hive-os-demo
/srv/linc
/srv/<workspace>
```

This prevents product code from mixing with user/project data and makes OSS packaging cleaner.

## Initial laptop prototype

```text
Users:
  kuya  -> environment admin
  aris  -> member/test collaborator

Runtime:
  /srv/hive-os-demo
```

## Environment admin vs project member

Environment admin can manage OS/Hermes/server infrastructure, but is not automatically a project member in normal app policy.

Example: if `aris` creates `deltapack` and does not invite `kuya`, then:

- `aris` can see/access the project.
- `kuya` does not see/access the project in the app.
- Normal filesystem access for `kuya` should be denied unless invited.
- `kuya` can still use sudo/root for explicit break-glass maintenance, which must be logged.

## Project access enforcement

Use two layers:

1. **App ACL**: database membership controls UI/API access.
2. **OS ACL**: POSIX ACL controls filesystem access.

DB is source of truth for product membership. POSIX ACL is hard enforcement and can be rebuilt from DB.

## POSIX ACL pattern

Create private project:

```bash
mkdir -p /srv/hive-os-demo/projects/deltapack
chown aris:aris /srv/hive-os-demo/projects/deltapack
chmod 700 /srv/hive-os-demo/projects/deltapack
setfacl -m u:aris:rwx,d:u:aris:rwx /srv/hive-os-demo/projects/deltapack
```

Invite user:

```bash
setfacl -R -m u:kuya:rwx /srv/hive-os-demo/projects/deltapack
setfacl -R -m d:u:kuya:rwx /srv/hive-os-demo/projects/deltapack
```

Remove user:

```bash
setfacl -R -x u:kuya /srv/hive-os-demo/projects/deltapack
setfacl -R -x d:u:kuya /srv/hive-os-demo/projects/deltapack
```

Backups must preserve ACLs (`rsync -aAX` or `tar --acls --xattrs`) or repair ACLs from DB after restore.

## Runner abstraction

Hive OS should not hardcode Hermes as the only runtime.

Generic runner events:

```json
{ "type": "assistant_delta", "text": "..." }
{ "type": "tool_start", "tool": "terminal", "title": "npm run build" }
{ "type": "tool_output", "summary": "Build passed" }
{ "type": "approval_required", "approval_id": "..." }
{ "type": "artifact", "path": "..." }
{ "type": "final", "message": "Done" }
```

Initial runners:

- `hermes` — first-class MVP runner.
- `shell` — simple runner for smoke tests and safe command wrappers.

Future runners:

- Claude Code
- Codex
- OpenCode
- custom API runners

## Backend stack proposal

- FastAPI backend
- SQLite database
- WebSocket streaming for chat/session events
- REST endpoints for projects/tasks/wiki/artifacts/settings
- Controlled admin helper CLI (`hiveosctl`) for ACL/project operations

## Frontend stack proposal

- React + Vite PWA
- Hermes Desktop used as UX/reference, not as a direct product dependency
- Mobile-first layout
- Chat streaming with virtualized message list and compact tool cards

## MVP surfaces

- Login
- Projects
- Project create/invite/remove/archive
- Chat in project context
- Tasks
- Wiki read/edit
- Artifacts
- Workflows
- Settings
- Admin/break-glass audit

## Break-glass policy

Break-glass requires:

- explicit action
- reason text
- audit log entry
- optional temporary access grant
- no silent project browsing by environment admin
