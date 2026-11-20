# Decisions

Newest last. Each entry: the decision, why, and what was rejected.

1. **No chat-app control plane.** Telegram (and similar) could be blocked in India overnight; the platform must work with infrastructure we own or can replace.
2. **ESP32-S3 with the Arduino core over Rust or ESP-IDF directly.** Mature Wi-Fi, TLS MQTT and OTA; the firmware is small and not performance-bound. Logic lives in plain C++ (`imp/src`) tested on the host with sanitizers; `imp.ino` only wires hardware.
3. **imp is a separate device, not a feature of a server.** It must wake devil when every machine at home is off. A Raspberry Pi was too expensive for this.
4. **MQTT as the single bus, devices self-describe.** UIs and future clients are generic; adding a device needs no UI change.
5. **The bus lives on mephisto, reached through Tailscale.** Home is behind CGNAT and mephisto's public IP is ephemeral, so neither can be addressed directly.
6. **Funnel for the bus, Caddy on the tailnet for web.** The ESP32 cannot run Tailscale, so it needs a public TLS endpoint; Funnel provides one without opening ports on mephisto. Web apps stay tailnet-only: Tailscale acts as the access control, and no public 443 is opened.
7. **Real certificates for private hosts.** Wildcard DNS in Cloudflare pointing at the tailnet IP plus DNS-01, instead of MagicDNS names or self-signed certs. A new app is a role and a `sites` entry.
8. **Ansible + Podman Quadlets on AlmaLinux, everything declarative.** Machines get wiped; nothing may live only on a box. Rejected: Docker Compose, hand configuration, NixOS on the server.
9. **SOPS + age over ansible-vault.** Diffable encrypted YAML, two independent recipients: the homelab SSH key (in 1Password) and an offline age key. No passphrase file to lose.
10. **Four repos, one owner of deployment.** homelab holds every host-specific value and secret; the other repos are generic and publishable. Replaced the old monolithic `pc-control` (torn down 2026-11-19).
11. **Public repos with guardrails** (branch protection, gitleaks hook + CI, push protection, Claude deny rules) rather than private repos; the risk was leaked secrets, which the guardrails address.
12. **imp always sends the magic packet**, even if the target looks online: ping state lags by up to `IMP_OFFLINE_AFTER` intervals.
13. **warden runs unprivileged.** polkit grants power-off, reboot and suspend only; actions have a grace period with `cancel`; inhibitors are bypassed so a desktop app cannot block a remote command.
14. **Console in vanilla JS, no framework.** Small surface, no build-time framework churn; all device data rendered with `textContent`. On the slow home link, load time is dominated by the mqtt.js bundle, so it is versioned, deferred, compressed and cached immutably.
15. **Proposed, not decided (2026-11-20): Cloudflare in front plus an API service.** UI on Cloudflare Pages, `api.iamabhay.fyi` through Cloudflare Tunnel to a new service on mephisto (snapshot, SSE stream, commands, history, audit), Cloudflare Access for login, the bus internal-only except Funnel, the tailnet route kept as a fallback. Reason: the ISP reaches Cloudflare much better than Oracle, and the browser would no longer carry broker credentials or the MQTT library. Rejected: SSR (a live view gains nothing from it). Open questions: Cloudflare-in-front versus tailnet-only; Go (preferred) versus TypeScript/Python. See [roadmap](roadmap.md).
