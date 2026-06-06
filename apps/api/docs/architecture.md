# Hive OS Architecture and Trust Boundaries

## Product context

Hive OS is a Team Mode, app-level multi-user Hermes PWA hosted on a Linux server. Users interact through the web app. The app queues runs for an AI runner, currently Hermes-first, and stores sessions, messages, project membership, and audit data.

## Actors

| Actor | Meaning | Allowed by default |
| --- | --- | --- |
| Environment admin | Manages the Hive OS server and app users | User/profile/project administration, server operations if separately granted |
| Project owner | Owns one Hive OS project | Invite/remove members, run sessions in that project |
| Project collaborator | Member of one project | Read/write only inside granted project policy |
| App user | Any authenticated web user | Only their own visible sessions/projects |
| Runner process | Hermes/Claude Code/Codex/etc. subprocess launched by Hive OS | Only what app policy and runner sandbox grant |
| Physical operator | Person with AnyDesk/SSH/filesystem access | Out of app-policy scope; controlled by Linux accounts, sudo, ACLs, audits |

## Non-negotiable boundaries

1. App authorization is checked before every project/session/message/run operation.
2. Runner access is a subset of app authorization, not broader than it.
3. Source code repositories are hidden from normal app users unless explicitly enabled for that user/project.
4. Hidden files (`.git`, `.env`, `.ssh`, profile stores, token files, config dirs) are denied by default.
5. Admin endpoints do not imply runner access to admin-only files.
6. The UI must not expose paths, source, logs, or tool outputs that bypass membership checks.

## Filesystem model

Recommended layout:

```text
/hive-os/
  app/                  # Hive OS source/deploy checkout, not app-user visible
  workspace/
    projects/           # user/project workspaces governed by Hive OS policy
    scratch/            # no-project temporary runs
  profiles/             # per-user/per-profile Hermes homes
  var/
    hive-os.db          # app database
    logs/               # service logs, admin-only
```

Current prototype paths are config-driven by `workspace_root`, `hermes_profiles_root`, `database_path`, and `projectctl_path`.

## App layer vs OS layer

Hive OS must enforce both:

- App layer: tokens, roles, project memberships, session visibility, per-run policy.
- OS layer: Unix users/groups/ACLs, service account permissions, file modes, optional containers/sandboxes.

If these disagree, use the more restrictive result. Example: a user is a project member in DB but Linux ACL denies project path; the run must fail closed.

## Source/code boundary

Hive OS source code is not automatically a project. Treat source checkout as admin/developer material. To let a user or runner inspect source, create an explicit repository grant:

- repo id/name;
- absolute path;
- allowed users/projects;
- allowed operations: read, edit, execute tests, install packages;
- allowed file globs;
- expiration or manual revoke path;
- audit log reason.

## Runner launch boundary

A run must be created from an authorized session. The worker must resolve:

1. authenticated user;
2. selected profile/Hermes home owned by that user;
3. project membership;
4. effective file policy;
5. runner binary allowlist;
6. command/tool policy;
7. environment variable allowlist;
8. timeout and cancellation policy.

The runner must not infer authorization from the prompt text.

## Known prototype gaps to keep visible

The current API prototype is intentionally not production-hard yet. Future developers must treat these as open security requirements:

- local username/password auth must be replaced or hardened before production;
- runner currently executes Hermes directly and needs a policy gate around file/tools;
- source repository access needs explicit enable/disable storage and enforcement;
- hidden-file deny rules need implementation and tests;
- prompt injection defenses need implementation in runner adapters and tool mediation;
- service deployment needs OS-level confinement.
