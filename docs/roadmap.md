# Roadmap

## Status (2026-11-20)

All four repos are on `main` with CI green; `verify.yml` passes 20/20 and `site.yml --check` reports no changes. imp runs firmware 0.1.0 (flashed over OTA).

## Next: API service (decision 15)

1. API service on mephisto (tailnet only at first); console switches from MQTT to it.
2. Cloudflare Tunnel and Access for `api.iamabhay.fyi`; console on Cloudflare Pages; tailnet route kept as fallback.
3. History and charts (SQLite), per-user permissions, audit log.
4. PWA, then a mobile app on the same API.

## Backlog

- Backups: restic to the Hetzner storage box.
- UPS: NUT on devil, then a warden `ups` module.
- Omada controller off old-devil (backup in `~/omada-backup` on old-devil).
- imp: power-button wiring through an optocoupler (waiting for the 3D-printed case, ViperWolf "ESP32-S3 case [with extra room]"); BLE presence auto-wake; USB HID.
- SSO for tailnet apps (tsidp).
- More apps on mephisto as roles: Nextcloud, Paperless, IT-Tools, Plane.
