# Repository and Project Access Operations

## Purpose

Hive OS needs explicit enable/disable controls for repositories and projects per user/project. This keeps app users from seeing source code unless intended, and keeps AI runners from becoming a loose shell over the server.

## Concepts

### Project

A workspace created and managed by Hive OS, usually under:

```text
<workspace_root>/projects/<slug>
```

Project membership controls normal app visibility.

### Repository grant

A separate permission that exposes an existing source/code repository to a user, project, or session. The Hive OS source checkout is only accessible through this mechanism.

### Hidden source/code boundary

A repository can contain public code files and hidden/control files. Granting repository read does not automatically grant hidden files, secrets, `.git`, config, profile homes, or deployment files.

## Recommended grant schema

Future implementation should persist something like:

```sql
CREATE TABLE repository_grants (
  id INTEGER PRIMARY KEY,
  repo_slug TEXT NOT NULL,
  repo_path TEXT NOT NULL,
  scope_type TEXT NOT NULL CHECK(scope_type IN ('user','project','session')),
  scope_id TEXT NOT NULL,
  can_read INTEGER NOT NULL DEFAULT 1,
  can_edit INTEGER NOT NULL DEFAULT 0,
  can_execute_tests INTEGER NOT NULL DEFAULT 0,
  can_install_packages INTEGER NOT NULL DEFAULT 0,
  include_hidden INTEGER NOT NULL DEFAULT 0,
  denied_globs TEXT NOT NULL DEFAULT '[]',
  expires_at TEXT,
  enabled_by_user_id INTEGER NOT NULL,
  reason TEXT NOT NULL,
  disabled_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## Enable repository for a user/project

Required inputs:

- repo slug/name;
- absolute repo path;
- scope: user, project, or session;
- permission flags;
- denied globs;
- expiration;
- reason.

Validation:

1. actor is environment admin or another explicitly allowed role;
2. repo path is registered/known, not arbitrary user input;
3. path exists and is not a secrets/config directory;
4. denied globs include hidden/secrets baseline;
5. grant is audited.

## Disable repository

Disabling a grant must:

- set `disabled_at` or delete the active grant;
- cancel or prevent new runs using that grant;
- leave historical sessions intact but not able to re-read files;
- write audit event.

## Project membership operations

Current API supports create/list/detail/invite/remove/members. Rules:

- only project owner can invite/remove project collaborators;
- cannot remove owner via collaborator removal;
- list/detail only returns projects where user is member;
- OS ACL helper must update Linux permissions to match app membership;
- DB membership and OS ACL must converge; if not, fail closed.

## File permission matrix

| Operation | App member | Project owner | Environment admin | Runner |
| --- | --- | --- | --- | --- |
| List own visible projects | yes | yes | yes if member/admin endpoint | no direct UI |
| Read project files | yes if policy permits | yes if policy permits | only with project/admin grant | only through run policy |
| Edit project files | if project policy permits | if project policy permits | only with grant | only through run policy |
| Read Hive OS source | no by default | no by default | developer/admin grant | repository grant required |
| Edit Hive OS source | no by default | no by default | developer/admin grant | repository grant + edit required |
| Read `.env`/secrets | no | no | only operational vault access | no |
| Install packages | no by default | project policy maybe | admin operation | explicit run policy only |

## Admin vs app user boundary

Environment admin is an app role for Hive OS administration. It should not be treated as Linux root.

- App admin can create users and maybe register repositories.
- Linux admin controls service accounts, ACLs, system packages, backups, and secrets.
- A normal app user cannot become admin by prompt, project file, or runner command.
- Admin UI actions must require server-side role checks and audit logs.

## AnyDesk/SSH reality

If a person has AnyDesk or SSH into a powerful Linux account, they may physically browse files outside Hive OS. Hive OS docs and code should be honest about this.

Controls for that layer:

- separate Linux accounts;
- no shared root/sudo unless necessary;
- file modes and ACLs;
- encrypted backups/secrets vault;
- audit logs;
- do not store production secrets in source checkout;
- service account for Hive OS with minimal filesystem permissions.

Controls for app layer:

- do not expose files through API/UI without membership/grant;
- do not let prompt injection request files outside grant;
- do not let runner inherit broad shell/user privileges;
- deny hidden/source/secret reads by default.

## Operational runbook outline

### Add a new app user

1. Environment admin creates user.
2. User gets default profile/Hermes home.
3. User has no projects except those created/invited.
4. Audit `user.create`.

### Create project

1. Authenticated user creates project.
2. DB adds owner membership.
3. `projectctl` creates workspace and owner ACL.
4. Audit `project.create`.

### Invite user to project

1. Owner calls invite.
2. DB adds collaborator membership.
3. `projectctl invite` updates OS ACL.
4. Audit `project.invite`.

### Revoke user from project

1. Owner calls remove.
2. DB membership removed.
3. `projectctl remove` updates OS ACL.
4. New sessions/runs blocked.
5. Audit `project.remove`.

### Grant source repo access

1. Environment admin creates repository grant with reason and expiry.
2. Runner/file APIs include repo path in allowed roots only for that scope.
3. Hidden/secrets still denied unless separately and explicitly allowed.
4. Audit `repo.grant.enable`.

### Disable source repo access

1. Environment admin disables grant.
2. New file reads/edits/runs exclude repo path.
3. Active runs using grant are cancelled or prevented from further file access.
4. Audit `repo.grant.disable`.
