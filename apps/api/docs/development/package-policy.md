# Package Installation Policy

## Goal

Dependencies are part of the security boundary. Hive OS launches AI runners and handles multi-user project data, so new packages must be intentional, minimal, and auditable.

## Approved package manager

Use `uv` for Python dependencies.

```bash
cd /home/kuya/storage/projects/hive-os/apps/api
uv add <package>
uv add --dev <package>
```

Do not edit `uv.lock` manually.

## Dependency decision checklist

Before adding a package, answer:

1. What exact feature needs this dependency?
2. Can the standard library or existing dependency do it safely?
3. Is the package maintained and commonly used?
4. Does it execute subprocesses, parse untrusted input, open network sockets, or read files?
5. Does it add transitive dependencies that affect auth, crypto, file IO, or runner execution?
6. Is the license acceptable for the project?
7. Is it needed at runtime or only in dev/test?

## Runtime dependency rules

Runtime dependencies require extra caution if they touch:

- authentication or session handling;
- cryptography/password hashing;
- subprocess execution;
- filesystem traversal;
- archive extraction;
- YAML/TOML/JSON parsing of untrusted content;
- HTTP clients/servers;
- AI/LLM prompt/tool mediation;
- sandboxing or container control.

For these, include tests showing safe failure behavior.

## Dev dependency rules

Dev dependencies may be broader but must not require global installation. Prefer `uv add --dev` and `uv run`.

## System packages

System packages are installed by an environment admin, not by app users or prompt-triggered runners.

Document any required system package with:

- package name;
- why it is needed;
- install command for the target distro;
- whether it is needed by app server, runner, tests, or optional tooling;
- security implications.

## AI runner package installs

App users and prompts must not install packages into the Hive OS server environment by default.

Allowed patterns:

- project-local virtualenv/container only;
- explicit project policy enables installation;
- install command is audited;
- no write access to Hive OS source env or global site-packages;
- no secrets passed to installer unless explicitly configured by admin.

Disallowed patterns:

- prompt says `pip install` and runner executes globally;
- npm/pip/uv install in source checkout without repository grant;
- installing from arbitrary URLs without admin/project-owner approval;
- package scripts running with server admin privileges.

## Lockfile policy

Commit `pyproject.toml` and `uv.lock` together when dependencies change.

## Documentation update trigger

Update this file when:

- package manager changes;
- install permissions change;
- runner package install behavior changes;
- production deployment introduces new system dependencies.
