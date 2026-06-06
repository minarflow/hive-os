# ACL Smoke Test Notes

## Goal

Verify Hive OS private-by-default project access using POSIX ACL with laptop prototype users:

- `kuya` — environment admin
- `aris` — member/test collaborator

Runtime root:

```text
/srv/hive-os-demo
```

## Helper

Created:

```text
infra/scripts/hiveosctl
```

Supported commands:

```bash
hiveosctl init-workspace /srv/hive-os-demo --owner kuya
hiveosctl --root /srv/hive-os-demo create-project deltapack --owner aris
hiveosctl --root /srv/hive-os-demo invite deltapack kuya
hiveosctl --root /srv/hive-os-demo remove deltapack kuya
hiveosctl --root /srv/hive-os-demo members deltapack
```

The helper validates:

- workspace root must be under `/srv`
- project slug is lowercase/hyphen-safe
- OS users must exist
- project paths cannot escape root
- script must run as root/sudo for ownership + ACL mutation

## Local verification completed

```bash
chmod +x infra/scripts/hiveosctl
python3 -m py_compile infra/scripts/hiveosctl
./infra/scripts/hiveosctl --help
```

Result: script compiles and help renders.

## Smoke test result

Executed successfully from the Hermes tool session after sudo authorization.

Observed result:

```text
initialized workspace: /srv/hive-os-demo
created project: /srv/hive-os-demo/projects/deltapack owner=aris

-- access before invite --
aris_can_read=YES
kuya_can_read=NO

-- invite kuya --
invited kuya to /srv/hive-os-demo/projects/deltapack
kuya_can_read_after_invite=YES

-- remove kuya --
removed kuya from /srv/hive-os-demo/projects/deltapack
kuya_can_read_after_remove=NO

-- aris write --
aris_write=YES
```

Important bug found and fixed: the first implementation recursively set a default ACL on the workspace root, causing new projects to inherit `kuya:rwx`. The fix avoids default ACLs on the workspace root and grants only execute-only traversal on `/srv/hive-os-demo` and `/srv/hive-os-demo/projects`.

## Commands

From repo root:

```bash
cd /home/kuya/projects/hive-os

sudo ./infra/scripts/hiveosctl init-workspace /srv/hive-os-demo --owner kuya
sudo ./infra/scripts/hiveosctl --root /srv/hive-os-demo create-project deltapack --owner aris

# Before invite: aris yes, kuya no
sudo -u aris test -r /srv/hive-os-demo/projects/deltapack && echo aris_can_read=YES || echo aris_can_read=NO
sudo -u kuya test -r /srv/hive-os-demo/projects/deltapack && echo kuya_can_read=YES || echo kuya_can_read=NO

# Invite kuya
sudo ./infra/scripts/hiveosctl --root /srv/hive-os-demo invite deltapack kuya
sudo -u kuya test -r /srv/hive-os-demo/projects/deltapack && echo kuya_can_read_after_invite=YES || echo kuya_can_read_after_invite=NO

# Remove kuya
sudo ./infra/scripts/hiveosctl --root /srv/hive-os-demo remove deltapack kuya
sudo -u kuya test -r /srv/hive-os-demo/projects/deltapack && echo kuya_can_read_after_remove=YES || echo kuya_can_read_after_remove=NO

# Show ACL
sudo ./infra/scripts/hiveosctl --root /srv/hive-os-demo members deltapack
```

Expected:

```text
aris_can_read=YES
kuya_can_read=NO
kuya_can_read_after_invite=YES
kuya_can_read_after_remove=NO
```

## Future backend integration

The PWA backend should not execute arbitrary sudo commands. It should call a limited, validated helper like `hiveosctl` through a sudoers rule scoped to specific commands/paths.
