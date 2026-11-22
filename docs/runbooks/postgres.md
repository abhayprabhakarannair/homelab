# Postgres

The platform database on mephisto (decision 27): `db.mephisto.iamabhay.fyi:5432`, tailnet only, TLS 1.3, one role and database per app.

## Connecting

| Field | Value |
|---|---|
| Host | `db.mephisto.iamabhay.fyi` |
| Port | `5432` |
| Database, user | the app's name |
| Password | `secrets.postgres.apps.<app>` |
| SSL mode | `verify-full` |

```
postgres://<app>:<password>@db.mephisto.iamabhay.fyi:5432/<app>?sslmode=verify-full
```

The certificate is from Let's Encrypt, so clients verify it against the system store: libpq 16+ (psql) needs `sslrootcert=system`, Go drivers use the system store with no `sslrootcert`. Passwords go into URLs as they are, so generate them with `openssl rand -hex 32` (no characters to escape).

The client's machine must be a tailnet member's device or tagged `tag:db-client` (`roles/tailnet/files/policy.hujson`); from anywhere else the name resolves to a `100.x` address that does not answer.

From devil, with `~/.pg_service.conf`:

```ini
[miniflux]
host=db.mephisto.iamabhay.fyi
dbname=miniflux
user=miniflux
sslmode=verify-full
sslrootcert=system
```

then `psql service=miniflux`. The superuser has no network access: `ssh mephisto` and `sudo podman exec -it postgres psql -U postgres`.

## Adding an app

1. Add it to `postgres.apps` in `group_vars/all/main.yml` with a `conn_limit` above the app's pool size.
2. `sops edit group_vars/all/secrets.sops.yml`: `postgres.apps.<app>: <openssl rand -hex 32>`.
3. `ansible-playbook site.yml --check --diff`, then apply: the role, its database (owned by the role, `PUBLIC` revoked) and its `pg_hba` line. `verify.yml` connects as every app.

Changing a password: edit it in SOPS, apply, restart the app.

## A backend outside the tailnet

It joins the tailnet as a tagged node and uses the same connection string. Create an auth key in the admin console (Settings → Keys): reusable, ephemeral, tag `tag:db-client`. Then:

- VM or VPS: install Tailscale and `tailscale up --auth-key=<key>`.
- Docker: a `tailscale/tailscale` sidecar with `TS_AUTHKEY`, the app sharing its network namespace.
- Go: `tsnet` in the app itself.
- GitHub Actions (migrations): `tailscale/github-action` with the key as a secret.

A tagged node reaches only `mephisto:5432`. A serverless platform that cannot run Tailscale gets its own managed database or an API in front; Postgres is never published.

## Certificate renewal failed

`certs-renew.timer` runs daily; lego renews with about a third of the lifetime left (~30 days), so there are weeks to react. `verify.yml` fails at 14 days.

```sh
systemctl list-timers certs-renew.timer
journalctl -u certs-renew.service -n 50
systemctl start certs-renew.service   # retry
```

- Cloudflare errors: the token (`secrets.cloudflare_api_token`, shared with Caddy) needs Zone → DNS → Edit on the zone.
- `rateLimited`: Let's Encrypt allows 5 identical certificates a week; wait, do not loop retries.
- The certificate renewed but Postgres serves the old one: `homelab-cert-deploy` sends SIGHUP only when `postgres.service` is active; `sudo podman kill --signal HUP postgres`. A key the container cannot read (SELinux) shows as `could not load private key file` in `journalctl -u postgres`; compare `ls -Z /etc/homelab/postgres/tls` with the directory.

Postgres keeps serving the old certificate until it expires, so a failure is not an outage until then.

## Public exposure

Postgres binds only to the tailnet address and only the firewalld `tailnet` zone allows it; `verify.yml` checks both. In the Oracle console (Networking → Virtual cloud networks → mephisto's VCN → Security Lists, and any Network Security Group on the instance's VNIC) there must be no ingress rule for TCP 5432 and none for all protocols from `0.0.0.0/0`.

## Restore test

No backup job exists yet (target undecided). Whatever it becomes, test a restore like this:

```sh
sudo podman exec postgres pg_dump -U postgres -Fc miniflux > /tmp/miniflux.dump
sudo podman exec -i postgres createdb -U postgres restore_test
sudo podman exec -i postgres pg_restore -U postgres -d restore_test --no-owner < /tmp/miniflux.dump
sudo podman exec postgres psql -U postgres -d restore_test -c 'select count(*) from entries'   # compare with miniflux
sudo podman exec postgres dropdb -U postgres restore_test
rm /tmp/miniflux.dump
```
