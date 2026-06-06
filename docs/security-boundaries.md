# Security boundaries and access model

Hive OS has two different security layers. Do not confuse them.

## 1. Server/admin boundary

Anyone with physical access, AnyDesk, SSH, sudo, or filesystem access to the server can potentially inspect source code, runtime data, DB files, Hermes homes, and project files.

This is outside app-level isolation.

Examples:

```text
Linux Mint server admin
OS user: Linc Development
AnyDesk/SSH operator
sudo/root
```

These people are server operators. They can see more than Hive OS app users.

## 2. Hive OS app boundary

Hive OS app users should only see what the API authorizes:

- their own profiles
- their own private sessions
- projects where they are members
- project-visible sessions for projects where they are members
- artifacts/events/messages allowed by the project/session policy

App users should not see source code, install scripts, server config, other users' Hermes homes, or private projects through the app unless explicitly authorized.

## Current Team Mode boundary

Current agreed mode:

```text
No OS-level user isolation.
One Linux OS user/service runs Hive OS and runners.
Hive OS enforces app-level authorization.
Each Hive app user/profile gets separate HERMES_HOME.
```

This is suitable for trusted internal team use.

It is **not** suitable for untrusted external tenants unless secure mode is implemented.

## Command/install policy

Normal app users may create/edit/run project files and install project-local dependencies inside repos they can access.

Allowed examples inside project root:

```text
npm install express
uv add requests
python -m venv .venv
pip install -r requirements.txt --target .venv
go get ...
cargo add ...
```

Blocked examples:

```text
sudo apt install ...
npm install -g ...
pip install --user ...
pip install --break-system-packages ...
curl ... | bash
```

The current API exposes `/api/policy/command/check` to classify and audit these decisions. Runner/tool execution should consult this policy before running install-like commands.

## Source code visibility

Normal Hive OS app users should not have any app UI/API route that browses the Hive OS source repository.

Allowed:

- environment admin intentionally opens source via SSH/AnyDesk/local shell
- developer/agent running in admin/developer mode checks repo docs/code

Not allowed by default:

- app user asks Hermes: "read Hive OS source code"
- app user browses `/opt/hive-os` through project file UI
- app user edits install scripts through a project workspace route

## Project file visibility

Project file APIs must be rooted in the project path from the database. Client input must be relative and normalized.

Never allow:

```text
../../..
absolute paths
symlink escape without validation
client-supplied project root
```

## Hermes profile visibility

Hermes homes are runtime state, not project files.

Normal users can own profiles but should not browse raw profile directories through generic file UI unless a future explicit profile-admin feature is built.

Never expose:

- tokens
- provider credentials
- auth files
- raw `.env`
- cookies/session stores

## Environment admin

Environment admins can manage users/projects/config in Hive OS. But even admin UI should avoid dumping secrets by default.

Admin-only features should require:

- auth
- role check
- clear UI wording
- audit log
- no raw secret display

## Secure mode future

For untrusted users, add OS-level isolation:

```text
Linux user per Hive user
sudoers/systemd-run wrapper
POSIX ACL project enforcement
runner sandboxing
resource limits
```

Until that exists, document deployments as trusted-team only.
