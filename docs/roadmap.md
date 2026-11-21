# Roadmap

## Status (2026-11-21)

All four repos are on `main` with CI green; `verify.yml` passes on every host and `site.yml --check` reports no changes. imp runs firmware 0.1.0 (flashed over OTA). er605 and eap225 run OpenWrt under the `router` and `ap` roles; er605 also runs warden 0.3.2 (wake path, ISP status and usage, devices with link and ISP, per-device ISP switching, decisions 17 and 18). The link was re-measured on BSNL (decision 19).

## Next

1. Retire old-devil and the Omada controller (the last step of decision 16).
2. imp: a wake sent to a machine that is already up reports `up` after ~1 s; port warden's fix (record whether the target was online when the wake was sent).
3. Replace the 10/100 switch behind er605 with a TL-SG1008P (gigabit, 802.3af/at PoE on ports 1–4, so eap225 can drop its injector); devil's port is capped at 100 Mbit/s until then.
4. Decide decision 15 with decision 19's numbers.

## Then: API service (decision 15, if adopted)

1. API service on mephisto (tailnet only at first); console switches from MQTT to it.
2. Cloudflare Tunnel and Access for `api.iamabhay.fyi`; console on Cloudflare Pages; tailnet route kept as fallback.
3. History and charts (SQLite), per-user permissions, audit log.
4. PWA, then a mobile app on the same API.

## Backlog

- Backups: restic to the Hetzner storage box.
- UPS: NUT on devil, then a warden `ups` module.
- imp: power-button wiring through an optocoupler (waiting for the 3D-printed case, ViperWolf "ESP32-S3 case [with extra room]"); BLE presence auto-wake; USB HID.
- SSO for tailnet apps (tsidp).
- More apps on mephisto as roles: Nextcloud, Paperless, IT-Tools, Plane.
