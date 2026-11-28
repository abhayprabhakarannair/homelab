# Architecture

A home control platform: wake, monitor and power-manage machines from anywhere, without third-party chat apps or a public IP at home.

## Repositories

| Repo | What | Runs on | Stack |
|---|---|---|---|
| [homelab](https://github.com/abhayprabhakarannair/homelab) | Deployment and secrets for the router, the access point, mephisto and the tailnet; the only repo that knows hostnames, addresses and credentials | any PC set up as a control node | Ansible, SOPS/age, Podman Quadlets |
| [warden](https://github.com/abhayprabhakarannair/warden) | Modular host agent: state, power actions, Wake-on-LAN, ISP and LAN status | er605 (procd) | Python, paho-mqtt |
| [console](https://github.com/abhayprabhakarannair/console) | Web UI built from what devices announce | mephisto (Caddy, static) | vanilla ES modules, mqtt.js, node:test |

warden and console are generic: they read deployment values from config (env vars, `config.js`) that homelab generates. homelab deploys them from the sibling checkouts in `~/Projects/<repo>` at their committed `HEAD`, so pull `main` there before deploying.

## Hosts

| Host | What |
|---|---|
| mephisto | Oracle Cloud A1.Flex, ap-hyderabad-1, AlmaLinux 10 aarch64, 2 vCPU / 12 GB / 200 GB. Ephemeral public IP; tailnet `100.101.245.84`, `mephisto.tail6aa22b.ts.net`. Hosts the bus, the web apps and the platform Postgres. |
| devil | Home gaming PC, Windows 11 (from 2026-11-28, [runbook](runbooks/devil-windows.md)), set up by hand, not managed by homelab (decision 29). Wake target of er605's warden, which pings it for its power state (a Windows firewall rule allows ping from er605 only). Control node through WSL2 with mirrored networking. The only load on an APC Back-UPS RS 1500G-IN (USB): PowerChute Serial Shutdown powers it off at 5 min runtime and the UPS cuts its output about 2 minutes later, restoring it when mains returns, so devil boots on its own. Its only uplink is the cable to er605: joining an ISP router's Wi-Fi as well gives it an IPv6 route that bypasses failover and ISP switching (2026-11-21). |
| er605 | TP-Link ER605 v2.20, the home router. OpenWrt 25.12.6 ([runbook](runbooks/openwrt.md)), `192.168.0.1`. Runs warden (`system`, `wake`, `wan`, `clients`): the wired, always-on wake path and power state for devil, ISP status and usage, and every LAN device with its link (from eap225's read-only API login) and ISP, with per-device ISP switching. Stock flash backup on old-devil, mephisto and Google Drive. |
| eap225 | TP-Link EAP225(US) v4.0, the only access point. OpenWrt 25.12.6, `192.168.0.2` (DHCP reservation), bridged to the LAN; one SSID on both bands. |
| daredevil | ThinkPad E14 Gen 6, the dev laptop. Fedora Silverblue, set up by hand from its [runbook](runbooks/daredevil.md), not managed by homelab. A control node when set up with the same ansible-core and collections (mise): it reaches mephisto and the tailnet API from anywhere, and er605 and eap225 only from the home LAN. Tailscale SSH sets no `XDG_RUNTIME_DIR`, which the `mirror` role renders into, so a playbook started over SSH needs it set. |
| old-devil | Old laptop (NixOS, unreliable: no power-on after AC loss), `ssh old-devil -p 2442`. Its Omada controller, Home Assistant, Technitium, Syncthing and NUT client are unused; to be retired. |

## Home network

er605, eap225 and the ISPs' ONTs run on the house inverter, so the network and the wake path stay up through a power cut; devil's UPS is on the direct mains line, not the inverter.

One flat LAN, `192.168.0.0/24`, gateway er605 at `.1`, IPv4 only. DHCP and DNS from the router's dnsmasq, which forwards over HTTPS to Cloudflare and Google through two local `https-dns-proxy` instances (`doh_resolvers`, decision 24), so the ISPs neither see nor rewrite lookups, and answers `use-application-dns.net` with NXDOMAIN so Firefox keeps using the router; rebind protection stays on except for `rebind_domains` (`mephisto.iamabhay.fyi` and its subdomains, which point at tailnet addresses). Fixed addresses are DHCP reservations from SOPS (`dhcp_hosts` plus the wake targets). dnsmasq also blocks ads and trackers with the Hagezi Multi Pro list (~245k domains, the `adblock` package, decision 23), refreshed daily at 04:30 by cron; while dnsmasq restarts with a new list, LAN DNS is redirected to 1.1.1.1. Devices in `router_adblock_exempt` (none; the Jio set-top box was exempt until 2026-11-21, when it joined on trial) have their DNS redirected to 1.1.1.1 by the firewall, unfiltered; false positives go in `router_adblock_allowlist`.

Three ISPs, all behind CGNAT, used as ordered failover with mwan3 (decision 16). Each WAN is checked by pinging 1.1.1.1, 8.8.8.8 and 9.9.9.9 every second; three failed rounds mark it offline. When BSNL goes offline, mwan3 flushes connection tracking so open connections move to the backup at once; the flush is global, so backups never trigger it (a flapping RailWire would otherwise reset every connection in the house). A device can prefer another ISP (`wan_preferences` in `host_vars/er605.yml`): its traffic goes there first, with the remaining WANs as fallback in order. The Jio set-top box (`jio-stb`) prefers Jio, which its live channels need to start a session; when Jio drops it falls back to BSNL within ~4 s, and in a 45 s simulated outage (2026-11-20) a JioTV+ live channel kept playing. From the console any device with a DHCP reservation can be switched to an ISP or back to automatic (an override follows the address, so an unreserved one could pass it to the next device leasing that address; `wanpref` refuses those and `wanpref-sync` deletes them): warden's `isp` command calls the root helper `wanpref` (rpcd plugin, ubus ACL for the `warden` user only), which keeps the choice in `/tmp/wanpref`, adds a source rule to that ISP's mwan3 table and drops the device's tracked connections. `wanpref-sync` rebuilds the rules on every mwan3 event, so an override applies only while its ISP is online and a reboot returns every device to automatic. An ISP can be tracked online and still unusable (RailWire at 6–10 % loss, 2026-11-21): warden on er605 measures each online ISP's loss and median latency over the last minute from mwan3track's per-round results (quality mode, which only adds the latency files), reports them with a `degraded` flag (≥ 5 % loss or ≥ 300 ms; recovered at ≤ 2 % and ≤ 200 ms) and passes the degraded set to `wanpref degraded`, which suspends overrides to those ISPs until they recover (decision 26). A device whose override is applied, suspended or removed loses its tracked connections so it moves at once. vnstat counts usage per WAN in billing cycles starting on `router_cycle_day` (21st, Jio's), stored on flash in `/etc/vnstat`. `verify.yml` fails only if no WAN is online, traffic is not on the first online one, or warden's state lacks usage for an online WAN (vnstat only records an interface's month once it carries traffic); down WANs are reported, not failed, since an ISP can be out for days. Measured 2026-11-20: 4.3 s outage when BSNL's upstream died with the link up, ~2 s for a pulled cable, no loss when BSNL returned. A WAN is shaped with cake (sqm-scripts) by adding `sqm` rates to its `wans` entry, and `verify.yml` checks cake on both directions of every shaped WAN that is up; none is shaped, since BSNL showed no bufferbloat (decision 21).

| Router port | OpenWrt name | ISP | Link |
|---|---|---|---|
| WAN | `wan1` | BSNL | 100 Mbit/s, unlimited; primary |
| WAN/LAN1 | `lan2` | RailWire | 60 Mbit/s, unlimited, unreliable; first backup |
| WAN/LAN2 | `lan3` | Jio AirFiber | 30 Mbit/s, 1000 GB cap, drops in rain; last resort |
| LAN1, LAN2 | `lan4`, `lan5` | LAN | |

Measured on BSNL through er605 (2026-11-21, decisions 19 and 21): ~90 Mbit/s down (devil's 100 Mbit/s switch port is the limit), ~90 Mbit/s up, latency +1–4 ms under full load, 28 ms to mephisto over a direct tailnet path, 19 ms to Cloudflare; Jio 29 Mbit/s down. The figures in decisions 14 and 15 date from Omada load-balancing over RailWire.

RailWire's loss is in its access network (measured 2026-11-21, 21:50, line idle): from er605 through `lan2`, 0 % loss to its ONT (Syrotech GPON, `192.168.51.1`, optical readings on the GPON Info page), 6 % to its CGNAT gateway `100.85.128.1`, 5 % to the next hop (Airtel, its transit) and 4–10 % to 1.1.1.1 and 8.8.8.8; the port shows no CRC or frame errors. The ONT reads Rx −25.7 dBm (weak but in spec), 0 HEC errors and 0 drops, so the downstream fibre delivers clean frames: the loss is upstream on the fibre (visible only on RailWire's OLT) or congestion past it. To report to RailWire with those figures; `ping -I lan2` from er605 to the ONT, `100.85.128.1` and 1.1.1.1 side by side repeats the test.

## Data flow

```
 warden (er605) ─TLS :8443─► Funnel ─────────┐
                                            ▼
                          mephisto: Mosquitto 127.0.0.1:1883 (+ WS 127.0.0.1:9001)
                                            ▲
 browser (tailnet) ──HTTPS──► Caddy *.mephisto.iamabhay.fyi ── /mqtt ──┘
                               └─ console static files
```

- Funnel is the only public entry point, used by clients that should not depend on the tailnet (warden). Mosquitto authenticates every client.
- Caddy binds only to mephisto's tailnet address. `*.mephisto.iamabhay.fyi` is a Cloudflare DNS record pointing at that address; the wildcard certificate comes from Let's Encrypt via DNS-01. Nothing is reachable from the internet except Funnel.
- Postgres (`db.mephisto.iamabhay.fyi:5432`) listens on the tailnet address only, TLS 1.3 with a Let's Encrypt certificate from the `certs` role; each app has its own role and database. Reached by tailnet members' devices and `tag:db-client` nodes (the tailnet policy), never published. [Runbook](runbooks/postgres.md).
- Miniflux (`rss.mephisto.iamabhay.fyi`) is the first app on Postgres; mobile readers use its Google Reader or Fever API over the tailnet.
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

An empty retained payload clears `meta`/`status`/`state`. ACL (`roles/mqtt/templates/acl.j2`): each user writes its own `meta/status/state/event` and reads its own `cmd`; UI users (`console`) read `home/#` and write `home/+/cmd`. MQTT users: `er605`, `console`, `probe` (verify.yml).

The console has no device-specific code: cards come from `meta.kind` and `meta.commands`. Wake buttons appear on each machine listed in any device's `meta.wakes` (a warden with the `wake` module) and are sent as `wake <target>` through an online one. A machine's power state prefers the waker's LAN ping over the agent's own status.

## Secrets

`group_vars/all/secrets.sops.yml` (SOPS, age). Recipients: the `~/.ssh/homelab` ed25519 key (kept in 1Password) and an offline age key (1Password). Holds become passwords, the Cloudflare DNS token, the Tailscale OAuth client (`tailscale_oauth.{client_id,client_secret}`), Wi-Fi credentials, MQTT passwords, Postgres passwords (`postgres.superuser`, used only by initdb, and `postgres.apps.<app>`), wake targets (`wol.<host>.{mac,ip}`) and DHCP reservations (`dhcp_hosts.<name>.{mac,ip}`). Wake-target MAC/IP exist only here. Mosquitto password hashes are derived deterministically (`filter_plugins/mosquitto.py`) so re-runs don't churn.

## Deployment

| Target | How |
|---|---|
| tailnet | `site.yml`, role `tailnet` (on the controller): the tailnet policy is `roles/tailnet/files/policy.hujson`, uploaded through the Tailscale API (OAuth client with the `policy_file` scope) when it differs from the live one; Tailscale runs the policy's `tests` and refuses a policy that fails them. Edit the file, never the admin console. |
| mephisto | `site.yml`, roles `firewall` (tailnet zone: https and postgresql only), `podman`, `mqtt`, `funnel`, `dns`, `certs`, `postgres`, `miniflux`, `console`, `caddy`. `certs` gets a Let's Encrypt certificate (lego, DNS-01 through Cloudflare) for each entry in `certs` in `host_vars/mephisto.yml`, for services that terminate TLS themselves; `certs-renew.timer` runs lego daily (it renews with about a third of the lifetime left) and `homelab-cert-deploy` installs a renewed certificate as `server.crt`/`server.key` owned by the service's user, then sends the service SIGHUP. Caddy keeps its own certificate. `postgres` runs the official image as a Quadlet with host networking (published ports would bypass firewalld) and `listen_addresses` set to the tailnet address; `pg_hba` allows only `hostssl` + `scram-sha-256` from the tailnet for each app to its own database and the superuser only by peer over the Unix socket, which is bind-mounted to `/run/homelab-postgres` so Ansible's `community.postgresql` modules manage roles and databases from the host as root (mapped to `postgres` in `pg_ident`). Config changes to `postgresql.conf` restart it, `pg_hba`/`pg_ident` changes reload it. Apps are listed in `postgres.apps` in `group_vars/all/main.yml`. The container runs without a user namespace, so its `postgres` (UID 999) is `systemd-oom` on the host: besides root, only that account can read the key and the data (a user namespace would show host root as `nobody` on the socket and break peer login). mephisto has `psql` 16 on the host, which `verify.yml` uses as a separate client. `miniflux` runs the distroless image read-only with no capabilities on `127.0.0.1:8080` (the `rss` site), connecting to Postgres as its own role over `verify-full`. |
| er605 warden | `site.yml`, role `warden`: `python3-paho-mqtt`, a `warden` user (UID 200) allowed unprivileged ping through `net.ipv4.ping_group_range`, a procd service with `no_new_privs` |
| er605 | `site.yml`, role `router`: installs Python, mwan3, vnstat, conntrack, sqm-scripts, adblock and https-dns-proxy, templates `/etc/config/{system,network,dhcp,firewall,mwan3,vnstat,sqm,https-dns-proxy,adblock}`, the adblock allowlist and root's crontab. Files on er605 (router and warden) go through the `mirror` role: read in one `raw` call, rendered on the controller in `$XDG_RUNTIME_DIR`, written back in one, since each Python module costs ~9 s there (a converged `site.yml --check` takes ~50 s, was 8m41s). Changes apply with an automatic rollback: the router restores its previous config unless Ansible reconnects and confirms within 120 s. |
| eap225 | `site.yml`, role `ap`: templates `/etc/config/{system,network,wireless}`, keeps dnsmasq and odhcpd off. No Python on the device (it needs ~12 MB of the 6 MB free), so tasks are `raw` over SSH or run on the controller. |
| OpenWrt upgrades | `upgrade.yml` (manual): `owut` builds the release with current packages on the official build server, the device keeps its config and the roles' keep lists; eap225 first. `verify.yml` reports pending updates. [Runbook](runbooks/openwrt.md#d-upgrading). |
| console | the `console` role builds with the repo's mise Node, copies `dist/` to `/srv/console`, templates `config.js` |

`verify.yml` checks the deployed system end to end (services, bindings, auth refusal, ACL isolation, every warden host announcing, no retained topics left by removed devices, router usage per online WAN with no usage error, ISP switching as warden (unreserved addresses refused, stale overrides deleted, overrides to a degraded ISP suspended), cake on shaped WANs, live rates on the active WAN, disks per warden host, DNS upstreams only through a running DoH proxy per resolver, ad blocking (list loaded, an ad domain refused and a normal one resolved for a LAN client, exempt devices in the bypass set), OpenWrt keep lists and pending firmware updates (reported), console over HTTPS with compression and cache headers, WebSocket upgrade, certificates, the renewal timer and every `certs` certificate valid for more than 14 days, Postgres bound to the tailnet only and opened by no other firewalld zone, connections without TLS and superuser connections over the network refused, every app connecting with `verify-full` over TLS 1.3, Miniflux on localhost only with its database connections on TLS 1.3 and its health check answering through Caddy, and from the control node a verified certificate with more than 14 days left and TLS 1.2 refused). `site.yml --check` must report no changes on a converged system.

## Engineering rules

- Every repo is public; `main` is protected (PR only, CI `check` + `secrets` green, branch up to date, conversations resolved, squash merge, enforced for admins). gitleaks runs in a pre-commit hook and in CI; GitHub secret scanning and push protection are on.
- Every PR gets a Claude review (`code-review.yml`). The action skips PRs that modify that workflow file.
- `.claude/settings.json` in each repo denies Claude Code force pushes, pushes to `main`, skipping hooks, merging PRs and changing repository settings.
