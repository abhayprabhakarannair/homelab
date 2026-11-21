# Architecture

A home control platform: wake, monitor and power-manage machines from anywhere, without third-party chat apps or a public IP at home.

## Repositories

| Repo | What | Runs on | Stack |
|---|---|---|---|
| [homelab](https://github.com/abhayprabhakarannair/homelab) | Deployment and secrets for every machine; the only repo that knows hostnames, addresses and credentials | devil (control node) | Ansible, SOPS/age, Podman Quadlets |
| [warden](https://github.com/abhayprabhakarannair/warden) | Modular host agent: state, power actions, Wake-on-LAN, ISP and LAN status | devil (systemd), er605 (procd) | Python, paho-mqtt |
| [console](https://github.com/abhayprabhakarannair/console) | Web UI built from what devices announce | mephisto (Caddy, static) | vanilla ES modules, mqtt.js, node:test |

warden and console are generic: they read deployment values from config (env vars, `config.js`) that homelab generates. homelab deploys them from the sibling checkouts in `~/Projects/<repo>` at their committed `HEAD`, so pull `main` there before deploying.

## Hosts

| Host | What |
|---|---|
| mephisto | Oracle Cloud A1.Flex, ap-hyderabad-1, AlmaLinux 10 aarch64, 2 vCPU / 12 GB / 200 GB. Ephemeral public IP; tailnet `100.101.245.84`, `mephisto.tail6aa22b.ts.net`. Hosts the bus and web apps. |
| devil | Home workstation, CachyOS. Ansible control node, warden host, wake target. ufw managed by homelab. Its only uplink is the cable to er605: joining an ISP router's Wi-Fi as well gives it an IPv6 route that bypasses failover and ISP switching (2026-11-21). |
| er605 | TP-Link ER605 v2.20, the home router. OpenWrt 25.12.6 ([runbook](runbooks/openwrt.md)), `192.168.0.1`. Runs warden (`system`, `wake`, `wan`, `clients`): the wired, always-on wake path and power state for devil, ISP status and usage, and every LAN device with its link (from eap225's read-only API login) and ISP, with per-device ISP switching. Stock flash backup on devil (`~/er605-backup`), old-devil and mephisto. |
| eap225 | TP-Link EAP225(US) v4.0, the only access point. OpenWrt 25.12.6, `192.168.0.2` (DHCP reservation), bridged to the LAN; one SSID on both bands. |
| old-devil | Old laptop (NixOS, unreliable: no power-on after AC loss), `ssh old-devil -p 2442`. Its Omada controller, Home Assistant, Technitium, Syncthing and NUT client are unused; to be retired. |

## Home network

One flat LAN, `192.168.0.0/24`, gateway er605 at `.1`, IPv4 only. DHCP and DNS from the router's dnsmasq, which forwards to 1.1.1.1 and 8.8.8.8; rebind protection stays on except for `rebind_domains` (`mephisto.iamabhay.fyi` and its subdomains, which point at tailnet addresses). Fixed addresses are DHCP reservations from SOPS (`dhcp_hosts` plus the wake targets).

Three ISPs, all behind CGNAT, used as ordered failover with mwan3 (decision 16). Each WAN is checked by pinging 1.1.1.1, 8.8.8.8 and 9.9.9.9 every second; three failed rounds mark it offline. When BSNL goes offline, mwan3 flushes connection tracking so open connections move to the backup at once; the flush is global, so backups never trigger it (a flapping RailWire would otherwise reset every connection in the house). A device can prefer another ISP (`wan_preferences` in `host_vars/er605.yml`): its traffic goes there first, with the remaining WANs as fallback in order. The Jio set-top box (`jio-stb`) prefers Jio, which its live channels need to start a session; when Jio drops it falls back to BSNL within ~4 s, and in a 45 s simulated outage (2026-11-20) a JioTV+ live channel kept playing. From the console any device can be switched to an ISP or back to automatic: warden's `isp` command calls the root helper `wanpref` (rpcd plugin, ubus ACL for the `warden` user only), which keeps the choice in `/tmp/wanpref`, adds a source rule to that ISP's mwan3 table and drops the device's tracked connections. `wanpref-sync` rebuilds the rules on every mwan3 event, so an override applies only while its ISP is online and a reboot returns every device to automatic. vnstat counts usage per WAN in billing cycles starting on `router_cycle_day` (21st, Jio's), stored on flash in `/etc/vnstat`. `verify.yml` fails only if no WAN is online, traffic is not on the first online one, or warden's state lacks usage for an online WAN (vnstat only records an interface's month once it carries traffic); down WANs are reported, not failed, since an ISP can be out for days. Measured 2026-11-20: 4.3 s outage when BSNL's upstream died with the link up, ~2 s for a pulled cable, no loss when BSNL returned.

| Router port | OpenWrt name | ISP | Link |
|---|---|---|---|
| WAN | `wan1` | BSNL | 100 Mbit/s, unlimited; primary |
| WAN/LAN1 | `lan2` | RailWire | 60 Mbit/s, unlimited, unreliable; first backup |
| WAN/LAN2 | `lan3` | Jio AirFiber | 30 Mbit/s, 1000 GB cap, drops in rain; last resort |
| LAN1, LAN2 | `lan4`, `lan5` | LAN | |

Measured on BSNL through er605 (2026-11-21, decision 19): ~90 Mbit/s down (devil's 100 Mbit/s switch port is the limit), ~60 Mbit/s up, 28 ms to mephisto over a direct tailnet path, 19 ms to Cloudflare; Jio 29 Mbit/s down. The figures in decisions 14 and 15 date from Omada load-balancing over RailWire.

## Data flow

```
 warden (devil, er605) ─TLS :8443─► Funnel ─┐
                                            ▼
                          mephisto: Mosquitto 127.0.0.1:1883 (+ WS 127.0.0.1:9001)
                                            ▲
 browser (tailnet) ──HTTPS──► Caddy *.mephisto.iamabhay.fyi ── /mqtt ──┘
                               └─ console static files
```

- Funnel is the only public entry point, used by clients that should not depend on the tailnet (warden). Mosquitto authenticates every client.
- Caddy binds only to mephisto's tailnet address. `*.mephisto.iamabhay.fyi` is a Cloudflare DNS record pointing at that address; the wildcard certificate comes from Let's Encrypt via DNS-01. Nothing is reachable from the internet except Funnel.
- A new web app is a role plus an entry in `sites` in `host_vars/mephisto.yml` (static root, immutable paths, proxied paths).

## Bus contract

Topics `home/<id>/<leaf>`; `<id>` matches `^[a-z0-9_-]{1,31}$` and equals the client's MQTT username.

| Leaf | Retained | Payload |
|---|---|---|
| `meta` | yes | JSON: `kind` (required), `version`, `commands` (advertised commands), kind-specific fields (`wakes` for a warden with the `wake` module) |
| `status` | yes, also the last will | `online`, `offline`, `suspended` |
| `state` | yes | JSON object, kind-specific |
| `event` | no | JSON with `event`; retained events are ignored |
| `cmd` | no | `<command> [args…] [source]` |

An empty retained payload clears `meta`/`status`/`state`. ACL (`roles/mqtt/templates/acl.j2`): each user writes its own `meta/status/state/event` and reads its own `cmd`; UI users (`console`) read `home/#` and write `home/+/cmd`. MQTT users: `devil`, `er605`, `console`, `probe` (verify.yml).

The console has no device-specific code: cards come from `meta.kind` and `meta.commands`. Wake buttons appear on each machine listed in any device's `meta.wakes` (a warden with the `wake` module) and are sent as `wake <target>` through an online one. A machine's power state prefers the waker's LAN ping over the agent's own status.

## Secrets

`group_vars/all/secrets.sops.yml` (SOPS, age). Recipients: the `~/.ssh/homelab` ed25519 key (kept in 1Password) and an offline age key (1Password). Holds become passwords, the Cloudflare DNS token, Wi-Fi credentials, MQTT passwords, wake targets (`wol.<host>.{mac,ip}`) and DHCP reservations (`dhcp_hosts.<name>.{mac,ip}`). Wake-target MAC/IP exist only here. Mosquitto password hashes are derived deterministically (`filter_plugins/mosquitto.py`) so re-runs don't churn.

## Deployment

| Target | How |
|---|---|
| mephisto | `site.yml`, roles `firewall` (tailnet zone, https only), `podman`, `mqtt`, `funnel`, `dns`, `console`, `caddy` |
| devil | `site.yml`, roles `workstation` (ufw from `host_vars/devil.yml`), `warden` (git archive → `/opt/warden`, unprivileged user, polkit for power-off/reboot/suspend only, hardened unit) |
| er605 warden | `site.yml`, role `warden` with `warden_init: procd`: `python3-paho-mqtt`, a `warden` user (UID 200) allowed unprivileged ping through `net.ipv4.ping_group_range`, a procd service with `no_new_privs` |
| er605 | `site.yml`, role `router`: installs Python and mwan3, templates `/etc/config/{system,network,dhcp,firewall,mwan3,vnstat}`. Files on er605 (router and warden) go through the `mirror` role: read in one `raw` call, rendered on the controller in `$XDG_RUNTIME_DIR`, written back in one, since each Python module costs ~9 s there (a converged `site.yml --check` takes ~50 s, was 8m41s). Changes apply with an automatic rollback: the router restores its previous config unless Ansible reconnects and confirms within 120 s. |
| eap225 | `site.yml`, role `ap`: templates `/etc/config/{system,network,wireless}`, keeps dnsmasq and odhcpd off. No Python on the device (it needs ~12 MB of the 6 MB free), so tasks are `raw` over SSH or run on the controller. |
| console | the `console` role builds with the repo's mise Node, copies `dist/` to `/srv/console`, templates `config.js` |

`verify.yml` checks the deployed system end to end (services, bindings, auth refusal, ACL isolation, every warden host announcing, no retained topics left by removed devices, router usage per online WAN, console over HTTPS with compression and cache headers, WebSocket upgrade, certificates). `site.yml --check` must report no changes on a converged system.

## Engineering rules

- Every repo is public; `main` is protected (PR only, CI `check` + `secrets` green, branch up to date, conversations resolved, squash merge, enforced for admins). gitleaks runs in a pre-commit hook and in CI; GitHub secret scanning and push protection are on.
- Every PR gets a Claude review (`code-review.yml`). The action skips PRs that modify that workflow file.
- `.claude/settings.json` in each repo denies Claude Code force pushes, pushes to `main`, skipping hooks, merging PRs and changing repository settings.
