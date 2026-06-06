# Hive OS over Tailscale

Hive OS should be exposed to phones/laptops over HTTPS for PWA installability.

## Simple tailnet-only serve

After `hive-os serve` is listening on `127.0.0.1:8765`:

```bash
tailscale serve --bg https / http://127.0.0.1:8765
```

Then open the HTTPS MagicDNS URL on a device joined to the same tailnet and install the PWA from the browser.

## Notes

- Tailscale gates network reachability only. Hive OS still uses its own username/password auth and project membership checks.
- Keep Hive OS bound to `127.0.0.1` unless you intentionally place it behind a reverse proxy.
- Do not expose raw Hermes ports to the browser; the PWA should talk only to Hive OS.
