# Roadmap

## Status (2026-11-21)

All three repos are on `main` with CI green; `verify.yml` passes on every host and `site.yml --check` reports no changes. imp is retired and its repo archived (decision 20). er605 and eap225 run OpenWrt under the `router` and `ap` roles; er605 also runs warden 0.3.4 (wake path, ISP status and usage, devices with link and ISP, ISP switching for reserved devices, decisions 17 and 18). The link was re-measured on BSNL (decision 19); it shows no bufferbloat, so no WAN is shaped (decision 21). Both devices were upgraded with `upgrade.yml` (decision 22) to 25.12.6 with current packages. er605 blocks ads and trackers for the LAN through dnsmasq, the Jio set-top box included on trial (decision 23). Its upstream DNS goes over HTTPS (decision 24).

## Next

1. Retire old-devil and the Omada controller (the last step of decision 16).
2. Replace the 10/100 switch behind er605 with a TP-Link LS108GP (unmanaged gigabit, 802.3af/at PoE+ on all 8 ports, 62 W budget), so eap225 (802.3af, ≤ 12.6 W) can drop its passive 24 V injector; keep Extend mode off (it drops ports 1–2 to 10 Mbit/s). devil's port is capped at 100 Mbit/s until then.
3. Decide decision 15 with decision 19's numbers.

## Then: API service (decision 15, if adopted)

1. API service on mephisto (tailnet only at first); console switches from MQTT to it.
2. Cloudflare Tunnel and Access for `api.iamabhay.fyi`; console on Cloudflare Pages; tailnet route kept as fallback.
3. History and charts (SQLite), per-user permissions, audit log.
4. PWA, then a mobile app on the same API.

## Backlog

- Backups: restic to the Hetzner storage box.
- UPS: NUT on devil, then a warden `ups` module.
- A power-button device (imp hardware, optocoupler) if ever needed.
- SSO for tailnet apps (tsidp).
- More apps on mephisto as roles: Nextcloud, Paperless, IT-Tools, Plane.
