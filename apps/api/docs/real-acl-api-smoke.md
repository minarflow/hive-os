# Real ACL API Smoke Test

## Goal

Verify the FastAPI project API updates both app-level DB membership and OS-level POSIX ACL through `hiveosctl`.

## Script

```text
apps/api/scripts/smoke_acl_api.py
```

Run from `apps/api`:

```bash
sudo -E /home/linuxbrew/.linuxbrew/bin/uv run python scripts/smoke_acl_api.py
```

`sudo` is required because the smoke test creates/removes `/srv/hive-os-demo-api` and `hiveosctl` mutates ownership/ACL.

## Runtime root

```text
/srv/hive-os-demo-api
```

## Result

Latest run succeeded:

```text
initialized workspace: /srv/hive-os-demo-api
created=deltapack-api path=/srv/hive-os-demo-api/projects/deltapack-api
before_invite: aris_can_read=YES kuya_can_read=NO
after_invite: kuya_can_read=YES kuya_api_visible=YES
after_remove: kuya_can_read=NO kuya_api_visible=NO
SMOKE_OK
```

Final ACL after removing `kuya`:

```text
# file: /srv/hive-os-demo-api/projects/deltapack-api
# owner: aris
# group: aris
user::rwx
user:aris:rwx
group::---
mask::rwx
other::---
default:user::rwx
default:user:aris:rwx
default:group::---
default:mask::rwx
default:other::---
```

## Verified behavior

- `aris` can create a private project through the API.
- API membership shows project only to `aris` before invite.
- OS ACL denies normal `kuya` access before invite.
- Invite through API makes project visible to `kuya` and grants filesystem access.
- Remove through API hides project from `kuya` and revokes filesystem access.

## Notes

The script runs the app in-process through FastAPI `TestClient` instead of starting a public HTTP server. This is enough to verify endpoint behavior plus real `hiveosctl` subprocess side effects.
