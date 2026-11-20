# homelab

Hub of a four-repo system (homelab, imp, warden, console, all in `~/Projects`). Read these before changing anything; update them in the same PR when a change affects them:

@docs/architecture.md
@docs/decisions.md
@docs/roadmap.md

## Working with the user

- Senior engineer: no AI slop. Only the files that are needed, no comments that restate the code, tests that cover the edge cases.
- Every change goes through a branch and PR. Never merge, force-push, push to `main` or change repo settings; the user merges and resolves review conversations.
- Show `ansible-playbook site.yml --check --diff` and get approval before applying to a remote host. Run `verify.yml` after applying.
- Never print, echo or ask for secrets. The user pastes tokens into `sops edit` or `gh secret set` themselves.
- Firewall changes are made through `site.yml`; anything Claude Code's sandbox blocks, give the user the exact command. The user's shell is fish.
- Explain hardware in plain terms; prefer clean builds over breadboards.

## Gotchas

- Prefix Ansible with `LANG=en_IN.UTF-8` if Python complains about the locale (Plasma's `plasma-localerc` once set a non-UTF-8 `LANG`).
- Manual `sops` needs `SOPS_AGE_SSH_PRIVATE_KEY_FILE=~/.ssh/homelab`; Ansible gets it from `ansible.cfg`.
- Quadlet service tasks always use `daemon_reload: true`; build units need `RemainAfterExit=yes` or they rebuild every run.
- Handler names must be unique across roles.
- Caddy config is validated with the real env file (a dummy Cloudflare token fails validation).
- gitleaks flags well-known sample secrets (e.g. the RFC 6455 WebSocket key); generate test values at runtime.
- The Claude review action skips PRs that change `.github/workflows/code-review.yml`.
- eap225 has no room for Python: `raw` only. `raw` is skipped in check mode unless `check_mode: false`, and its stdout has CRLF line endings (use `stdout_lines`).
- er605 runs Ansible modules with the full `python3` package (`python3-light` lacks `decimal` and `encodings.idna`) and `ansible_ssh_transfer_method: piped` (dropbear has no sftp).
- Dropbear kills an SSH session's background jobs on logout, `nohup` included: detach with `async`/`poll: 0`.
- Stock TP-Link SSH (dropbear 2018) drops OpenSSH 10's long host-key list: use `-o HostKeyAlgorithms=ssh-rsa` (no `+`).
