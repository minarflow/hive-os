# Hive OS API

FastAPI backend prototype for Hive OS.

## Current MVP

- Local username login (`POST /auth/login`)
- Current user (`GET /api/me`)
- Project create/list/detail
- Project invite/remove
- Project members
- SQLite tables: `users`, `projects`, `project_members`, `audit_log`
- Calls validated `hiveosctl` helper for project ACL operations

## Test

```bash
uv run pytest -q
```

## Run dev server

```bash
uv run uvicorn hive_os_api.main:app --host 127.0.0.1 --port 8765
```

## Documentation

Start with [`docs/README.md`](docs/README.md) for the repository documentation map. Security-sensitive work must follow:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/security/security-model.md`](docs/security/security-model.md)
- [`docs/security/runner-policy.md`](docs/security/runner-policy.md)
- [`docs/security/prompt-injection.md`](docs/security/prompt-injection.md)
- [`docs/operations/repository-access.md`](docs/operations/repository-access.md)
- [`docs/development/setup.md`](docs/development/setup.md)
- [`docs/development/package-policy.md`](docs/development/package-policy.md)

## Notes

This is a prototype. Real auth should replace local username login before production. Project content visibility must always be enforced by app membership plus OS ACL. App users and prompt-injected runner content must not see source code, hidden files, secrets, or unrelated projects unless an explicit app-level policy grant allows it.
