# Hive OS Security Model

## Security objective

Hive OS must let multiple app users work with Hermes safely on one Linux server. It must prevent accidental or prompt-driven access to projects, source code, hidden files, secrets, and admin functions outside the user's grant.

## Threat model summary

In scope:

- normal app users trying to access other users' projects;
- prompt injection inside project files, chat messages, tool output, web pages, or logs;
- runner attempting to read/edit files outside policy;
- app endpoint missing authorization checks;
- hidden file/source leakage through UI, logs, or runner output;
- package install abuse by prompt or user;
- confused-deputy behavior where admin-created resources let non-admins access admin files.

Out of scope for app policy but still operationally important:

- people with root/sudo;
- people with direct AnyDesk/SSH filesystem access;
- kernel compromise;
- malicious server admin.

Important: out of scope does not mean ignored. Physical/operator access must be managed by Linux accounts, ACLs, sudo policy, and audit logs. App users still get least privilege in Hive OS.

## Roles

### environment_admin

Can manage Hive OS app users and operational settings. This role does not automatically mean every runner run can access every file.

### member

Can use the app and work in projects where they are a member.

### project owner

Project membership role. Can invite/remove collaborators for that project. Cannot grant access to Hive OS source or secrets unless also permitted by environment policy.

### collaborator

Can use the project according to project file/run policy.

## Authorization rules

- Return 401 for missing/invalid auth.
- Return 403 when user is authenticated but role is insufficient.
- Return 404 for resources outside project/session visibility to avoid enumeration.
- Check session ownership or project visibility before messages, events, runs, and cancellation.
- Check project membership before project detail, members, invite/remove, sessions, commands, and runs.
- Never trust `project_slug`, `session_id`, `profile_id`, `runner_id`, `path`, or `cwd` from the client without resolving to server-side policy.

## File classes

| Class | Examples | Default app-user access | Default runner access |
| --- | --- | --- | --- |
| Project content | `/workspace/projects/<slug>/...` | Members only | Members only, policy-filtered |
| User/profile data | `/profiles/<user>/<profile>/...` | Owner only | Owner's selected profile only |
| Hive OS source | `/hive-os/app`, repository checkout | Admin/developer only | Denied unless repo grant exists |
| Hidden source metadata | `.git`, `.github`, `.claude`, `.venv` | Denied by default | Denied by default |
| Secrets | `.env`, `.ssh`, tokens, key files, config vaults | Denied | Denied |
| Logs/database | `var/logs`, `hive-os.db` | Admin-only | Denied unless diagnostic grant |
| System paths | `/etc`, `/home/*`, `/var`, `/tmp` outside run dir | Denied by app policy | Denied unless explicit sandbox grants |

## Hidden file deny baseline

Deny by default:

```text
**/.git/**
**/.hg/**
**/.svn/**
**/.env
**/.env.*
**/.ssh/**
**/.gnupg/**
**/.aws/**
**/.config/**
**/.claude/**
**/.hermes/**
**/.venv/**
**/node_modules/**
**/__pycache__/**
**/*.pem
**/*.key
**/*token*
**/*secret*
```

Allow exceptions only through explicit policy and audit reason.

## API output rules

- Do not return absolute filesystem paths to users unless needed and authorized.
- Do not stream runner stderr/stdout to users until the run/session authorization is checked.
- Redact secrets from logs and API errors.
- Do not leak whether a hidden path exists; return denied/not found consistently.

## Audit events

Audit at minimum:

- bootstrap;
- user create/delete/role change;
- project create/archive/invite/remove;
- repository grants enable/disable;
- runner started/completed/failed/cancelled;
- file read/edit denied for policy reasons;
- package install requests and results;
- admin override use.

## Test requirements

Every security-sensitive change should include tests for:

- allowed user succeeds;
- non-member gets 404/403;
- non-admin cannot call admin endpoint;
- runner cannot access unrelated project;
- runner cannot read hidden/secret/source path by prompt injection;
- disabled repository grant blocks access again.
