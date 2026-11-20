# Architecture

A home control platform: wake, monitor and power-manage machines from anywhere, without third-party chat apps or a public IP at home.

## Repositories

| Repo | What | Runs on | Stack |
|---|---|---|---|
| [homelab](https://github.com/abhayprabhakarannair/homelab) | Deployment and secrets for every machine; the only repo that knows hostnames, addresses and credentials | devil (control node) | Ansible, SOPS/age, Podman Quadlets |
| [imp](https://github.com/abhayprabhakarannair/imp) | Wake-on-LAN and presence device | ESP32-S3 on the home LAN | Arduino core 3.3, C++17, doctest |
| [warden](https://github.com/abhayprabhakarannair/warden) | Modular host agent: state and power actions | devil (systemd) | Python, paho-mqtt |
| [console](https://github.com/abhayprabhakarannair/console) | Web UI built from what devices announce | mephisto (Caddy, static) | vanilla ES modules, mqtt.js, node:test |

imp, warden and console are generic: they read deployment values from config (`site.h`, env vars, `config.js`) that homelab generates. homelab deploys them from the sibling checkouts in `~/Projects/<repo>` at their committed `HEAD`, so pull `main` there before deploying.

## Hosts

| Host | What |
|---|---|
| mephisto | Oracle Cloud A1.Flex, ap-hyderabad-1, AlmaLinux 10 aarch64, 2 vCPU / 12 GB / 200 GB. Ephemeral public IP; tailnet `100.101.245.84`, `mephisto.tail6aa22b.ts.net`. Hosts the bus and web apps. |
| devil | Home workstation, CachyOS. Ansible control node, warden host, wake target. ufw managed by homelab. |
| imp | ESP32-S3-WROOM-1 N16R8 dev kit, `imp.local` (192.168.0.6), 2.4 GHz Wi-Fi. |
| er605 | TP-Link ER605 v2.20, the home router. Stock firmware 2.2.5 under the Omada controller until it moves to OpenWrt ([runbook](runbooks/openwrt.md)). |
| eap225 | TP-Link EAP225(US) v4.0, the only access point. Stock firmware 5.1.10 under the Omada controller until it moves to OpenWrt. |
| old-devil | Old laptop (NixOS, unreliable: no power-on after AC loss), `ssh old-devil -p 2442`. Runs the Omada controller; its Home Assistant, Technitium, Syncthing and NUT client are unused. Retired once er605 and eap225 run OpenWrt. |

## Home network

One flat LAN, `192.168.0.0/24`, gateway er605 at `.1`, DHCP from the router, public DNS resolvers. Fixed addresses are DHCP reservations; wake targets' MAC/IP live only in SOPS.

Three ISPs, all behind CGNAT, used as ordered failover (decision 16):

| Router port | OpenWrt name | ISP | Link |
|---|---|---|---|
| WAN | `wan1` | BSNL | 100 Mbit/s, unlimited; primary |
| WAN/LAN1 | `lan2` | RailWire | 60 Mbit/s, unlimited, unreliable; first backup |
| WAN/LAN2 | `lan3` | Jio AirFiber | 30 Mbit/s, 1000 GB cap, drops in rain; last resort |
| LAN1, LAN2 | `lan4`, `lan5` | LAN | |

The figures in decisions 14 and 15 (~1.7 Mbit/s, 150 ms to mephisto, 52 ms to Cloudflare) were measured while Omada load-balanced BSNL and RailWire; re-measure on BSNL after the migration.

## Data flow

```
 imp (LAN) ──TLS :8443──► Tailscale Funnel ─┐
 warden (devil) ──TLS :8443──► Funnel ──────┤
                                            ▼
                          mephisto: Mosquitto 127.0.0.1:1883 (+ WS 127.0.0.1:9001)
                                            ▲
 browser (tailnet) ──HTTPS──► Caddy *.mephisto.iamabhay.fyi ── /mqtt ──┘
                               └─ console static files
```

- Funnel is the only public entry point, used by clients that cannot join the tailnet (imp) or that should not depend on it (warden). Mosquitto authenticates every client.
- Caddy binds only to mephisto's tailnet address. `*.mephisto.iamabhay.fyi` is a Cloudflare DNS record pointing at that address; the wildcard certificate comes from Let's Encrypt via DNS-01. Nothing is reachable from the internet except Funnel.
- A new web app is a role plus an entry in `sites` in `host_vars/mephisto.yml` (static root, immutable paths, proxied paths).

## Bus contract

Topics `home/<id>/<leaf>`; `<id>` matches `^[a-z0-9_-]{1,31}$` and equals the client's MQTT username.

| Leaf | Retained | Payload |
|---|---|---|
| `meta` | yes | JSON: `kind` (required), `version`, `commands` (advertised commands), kind-specific fields (`wakes` for imp) |
| `status` | yes, also the last will | `online`, `offline`, `suspended` |
| `state` | yes | JSON object, kind-specific |
| `event` | no | JSON with `event`; retained events are ignored |
| `cmd` | no | `<command> [args…] [source]` |

An empty retained payload clears `meta`/`status`/`state`. ACL (`roles/mqtt/templates/acl.j2`): each user writes its own `meta/status/state/event` and reads its own `cmd`; UI users (`console`) read `home/#` and write `home/+/cmd`. MQTT users: `imp`, `devil`, `console`, `probe` (verify.yml).

The console has no device-specific code: cards come from `meta.kind` and `meta.commands`. Wake buttons appear on each machine listed in an imp's `meta.wakes` and are sent as `wake <target>` to that imp. A machine's power state prefers imp's LAN ping over the agent's own status.

## Secrets

`group_vars/all/secrets.sops.yml` (SOPS, age). Recipients: the `~/.ssh/homelab` ed25519 key (kept in 1Password) and an offline age key (1Password). Holds become passwords, the Cloudflare DNS token, Wi-Fi credentials, MQTT passwords, the imp OTA password and wake targets (`wol.<host>.{mac,ip}`). Wake-target MAC/IP exist only here. Mosquitto password hashes are derived deterministically (`filter_plugins/mosquitto.py`) so re-runs don't churn.

## Deployment

| Target | How |
|---|---|
| mephisto | `site.yml`, roles `firewall` (tailnet zone, https only), `podman`, `mqtt`, `funnel`, `dns`, `console`, `caddy` |
| devil | `site.yml`, roles `workstation` (ufw from `host_vars/devil.yml`), `warden` (git archive → `/opt/warden`, unprivileged user, polkit for power-off/reboot/suspend only, hardened unit) |
| imp | `playbooks/imp.yml` writes `../imp/site.h`; then `make test`, `arduino-cli compile`, `./ota-upload.sh` (OTA on 3232, callback 3233 open on devil from the LAN) |
| console | the `console` role builds with the repo's mise Node, copies `dist/` to `/srv/console`, templates `config.js` |

`verify.yml` checks the deployed system end to end (services, bindings, auth refusal, ACL isolation, every warden host announcing, console over HTTPS with compression and cache headers, WebSocket upgrade, certificates). `site.yml --check` must report no changes on a converged system.

## Engineering rules

- Every repo is public; `main` is protected (PR only, CI `check` + `secrets` green, branch up to date, conversations resolved, squash merge, enforced for admins). gitleaks runs in a pre-commit hook and in CI; GitHub secret scanning and push protection are on.
- Every PR gets a Claude review (`code-review.yml`). The action skips PRs that modify that workflow file.
- `.claude/settings.json` in each repo denies Claude Code force pushes, pushes to `main`, skipping hooks, merging PRs and changing repository settings.
