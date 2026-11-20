# homelab

Ansible for every machine. Re-running `site.yml` converges a host from scratch.

| Host | Role |
|---|---|
| mephisto | Oracle VM (AlmaLinux 10, aarch64). Platform: MQTT bus, Caddy for `*.mephisto.iamabhay.fyi` on the tailnet |
| devil | Workstation (CachyOS). Runs warden; wake target for imp; opens the imp OTA port to the LAN |

## Network

- `*.mephisto.iamabhay.fyi` resolves to mephisto's tailnet address; Caddy holds a wildcard certificate (DNS-01 via Cloudflare). Reachable from the tailnet only.
- The MQTT bus listens on localhost. Tailnet clients reach its WebSocket listener through Caddy; devices that cannot join the tailnet (imp) use Tailscale Funnel on `:8443`.
- Topics are `home/<client>/{meta,status,state,event,cmd}`. Each client may write its own topics and read its own `cmd`; the console reads everything and writes any `cmd`.

## Secrets

`group_vars/all/secrets.sops.yml`, encrypted with SOPS for the recipients in `.sops.yaml`: the `~/.ssh/homelab` ed25519 key and an offline age key (password manager). Either decrypts. Ansible reads it through the `community.sops` vars plugin, pointed at `~/.ssh/homelab` in `ansible.cfg`.

```sh
export SOPS_AGE_SSH_PRIVATE_KEY_FILE=~/.ssh/homelab
sops edit group_vars/all/secrets.sops.yml
sops updatekeys group_vars/all/secrets.sops.yml   # after changing recipients
```

### Unlocking on a fresh machine

Neither key is derived or generated; SOPS uses them as-is. Restore one of them, then check:

```sh
# SSH key (from the password manager)
install -m 600 /dev/stdin ~/.ssh/homelab
export SOPS_AGE_SSH_PRIVATE_KEY_FILE=~/.ssh/homelab   # for manual sops; ansible.cfg already sets it

# or the offline age key (the AGE-SECRET-KEY-1… line), at SOPS's default path
mkdir -p -m 700 ~/.config/sops/age
install -m 600 /dev/stdin ~/.config/sops/age/keys.txt

sops decrypt group_vars/all/secrets.sops.yml >/dev/null && echo unlocked
```

## Usage

```sh
ansible-playbook site.yml --check --diff
ansible-playbook site.yml
ansible-playbook verify.yml
ansible-playbook playbooks/imp.yml            # writes ../imp/site.h (wake targets from secrets.wol)
```

## Tests

```sh
pytest
ruff check . && ruff format --check .
yamllint . && ansible-lint
```

## Workflow

`main` is protected: it changes only through pull requests, with CI (`check`, `secrets`) green, the branch up to date, and every review conversation resolved. Force pushes and deletion are blocked, for admins too.

1. Branch from `main`; one concern per branch.
2. Open a PR. CI runs the tests and linters plus gitleaks over the branch history; the Claude review posts inline comments.
3. Address or explicitly dismiss every comment, then squash-merge. Branches are deleted on merge.

Local guardrails, enabled once per clone with `git config core.hooksPath .githooks`:

- `pre-commit` runs gitleaks on staged changes and refuses the commit when gitleaks is missing.
- `pre-push` refuses pushes to `main`.
- `.claude/settings.json` denies Claude Code force pushes, pushes to `main`, skipping hooks, merging PRs and changing repository settings.
