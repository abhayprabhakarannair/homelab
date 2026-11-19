# homelab

Ansible for every machine. Re-running `site.yml` converges a host from scratch.

| Host | Role |
|---|---|
| mephisto | Oracle VM (AlmaLinux 10, aarch64). Platform: MQTT bus, Caddy for `*.mephisto.iamabhay.fyi` on the tailnet |
| devil | Workstation (CachyOS). Runs warden |

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

## Usage

```sh
ansible-playbook site.yml --check --diff
ansible-playbook site.yml
ansible-playbook verify.yml
```

## Tests

```sh
pytest
ruff check . && ruff format --check .
yamllint . && ansible-lint
```
