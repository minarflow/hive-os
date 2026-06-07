# Backup & recovery

Hive OS stores everything in a single SQLite database (plus project files on
disk). `scripts/backup` makes a **consistent online snapshot** using SQLite's
backup API (safe to run while the server is up, WAL and all), compacts it, and
rotates old copies.

## Manual backup

```bash
HIVEOS_DB_PATH=~/.local/share/hive-os/hive-os.db bash scripts/backup
```

Environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `HIVEOS_DB_PATH` | `~/.local/share/hive-os/hive-os.db` | live database |
| `HIVEOS_BACKUP_DIR` | `<db dir>/backups` | where snapshots are written |
| `HIVEOS_BACKUP_KEEP` | `14` | how many snapshots to retain |

Each run writes `hive-os-YYYYMMDD-HHMMSS.db` and prunes anything beyond the
newest `HIVEOS_BACKUP_KEEP`.

> Also back up the project files directory (under your workspace root) if your
> agents write artifacts you care about — those live on disk, not in the DB.

## Scheduled backup (cron)

Daily at 03:00:

```cron
0 3 * * *  HIVEOS_DB_PATH=$HOME/.local/share/hive-os/hive-os.db /path/to/hive-os/scripts/backup >> $HOME/.local/share/hive-os/backup.log 2>&1
```

## Scheduled backup (systemd timer)

`~/.config/systemd/user/hive-os-backup.service`:

```ini
[Unit]
Description=Hive OS database backup

[Service]
Type=oneshot
Environment=HIVEOS_DB_PATH=%h/.local/share/hive-os/hive-os.db
ExecStart=/path/to/hive-os/scripts/backup
```

`~/.config/systemd/user/hive-os-backup.timer`:

```ini
[Unit]
Description=Daily Hive OS backup

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable it:

```bash
systemctl --user daemon-reload
systemctl --user enable --now hive-os-backup.timer
```

## Restore

Stop the server, then copy a snapshot over the live database:

```bash
cp ~/.local/share/hive-os/backups/hive-os-YYYYMMDD-HHMMSS.db \
   ~/.local/share/hive-os/hive-os.db
```

Verify before starting back up:

```bash
sqlite3 ~/.local/share/hive-os/hive-os.db "PRAGMA integrity_check;"
```
