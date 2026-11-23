# daredevil

The dev laptop: ThinkPad E14 Gen 6 (21M4), Ryzen 7 7735U, 57 Wh battery. Fedora Silverblue 45 with GNOME, set up by hand and deliberately not managed by Ansible; this runbook rebuilds it. Goals, in order: battery, stability, few updates, current tools only where chosen (mise, Flatpak, the Toolbox).

Rejected for this laptop (2026-11-22): CachyOS (rolling, built for devil's gaming), Debian 13 (its netinst found no network on this hardware), Ubuntu (snaps), Bluefin (more than needed).

## A. Install

1. BIOS (F1): supervisor password set, Secure Boot on. Update firmware first if `fwupdmgr get-updates` offers any (BIOS 1.18 on 2026-11-22).
2. Install Silverblue from the official ISO: automatic partitioning (btrfs), **Encrypt my data** on.
3. `rpm-ostree upgrade`, reboot.
4. `sudo ostree admin pin 0`: keeps the first known-good deployment in the boot menu.

## B. Layered packages

Keep this list short: every update re-applies it, and a third-party package that lags Fedora blocks the update until it catches up (most likely `mesa-va-drivers-freeworld`, which must match Fedora's Mesa). Nothing in the base image is removed or overridden.

```fish
rpm-ostree install \
  https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-(rpm -E %fedora).noarch.rpm \
  https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-(rpm -E %fedora).noarch.rpm
systemctl reboot
# make the release packages follow Fedora upgrades
rpm-ostree update --uninstall rpmfusion-free-release --uninstall rpmfusion-nonfree-release \
  --install rpmfusion-free-release --install rpmfusion-nonfree-release
sudo curl -fsSLo /etc/yum.repos.d/brave-browser.repo https://brave-browser-rpm-release.s3.brave.com/brave-browser.repo
sudo curl -fsSLo /etc/yum.repos.d/tailscale.repo https://pkgs.tailscale.com/stable/fedora/tailscale.repo
rpm-ostree install libavcodec-freeworld mesa-va-drivers-freeworld gstreamer1-plugins-bad-freeworld \
  fish brave-origin tailscale
systemctl reboot
```

| Package | Why on the host |
|---|---|
| `mesa-va-drivers-freeworld` | AMD hardware decoding of H.264/HEVC (Fedora ships Mesa without it); Brave uses it |
| `libavcodec-freeworld`, `gstreamer1-plugins-bad-freeworld` | Full codecs for Firefox and GNOME's own apps, beside Fedora's reduced ones |
| `fish` | The login shell |
| `brave-origin` | The browser; not on Flathub |
| `tailscale` | System daemon |

Check decoding in Brave: `brave://gpu` shows **Video Decode: Hardware accelerated**.

## C. System settings

- **Disk unlock by TPM**, bound to the Secure Boot state (PCR 7), passphrase kept as a fallback:
  ```fish
  rpm-ostree kargs --append-if-missing=rd.luks.options=tpm2-device=auto
  sudo systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /dev/nvme0n1p3
  sudo systemd-cryptenroll --recovery-key /dev/nvme0n1p3   # key into 1Password
  ```
  After a BIOS update or a Secure Boot change the TPM refuses once: unlock with the passphrase, then `sudo systemd-cryptenroll --wipe-slot=tpm2 --tpm2-device=auto --tpm2-pcrs=7 /dev/nvme0n1p3`.
- **Fingerprint** for sudo, polkit, the lock and login screens: `sudo authselect enable-feature with-fingerprint`, then `sudo fprintd-enroll -f right-index-finger $USER`. Type the password at the first login after boot, so the keyring unlocks.
- **Shell:** `sudo usermod -s /usr/bin/fish $USER`.
- **Network:** the home Wi-Fi connection uses the card's permanent MAC, so er605 gives it the `daredevil` reservation in `dhcp_hosts`; every other network keeps the per-network random MAC:
  `sudo nmcli connection modify <home-ssid> 802-11-wireless.cloned-mac-address permanent`.
- **Firewall:** `sudo firewall-cmd --set-default-zone=public` and `sudo firewall-cmd --permanent --zone=public --remove-service=ssh` (Fedora's own zone opens ports 1025–65535). sshd stays disabled; a remote shell is Tailscale SSH, like devil.
- **Tailscale:** `sudo systemctl enable --now tailscaled`, then `sudo tailscale up --ssh --hostname daredevil`; turn off key expiry in the admin console. Remove an old `daredevil` from the admin console first, or the new one becomes `daredevil-1`.
- **Updates:** `AutomaticUpdatePolicy=stage` in `/etc/rpm-ostreed.conf`, `rpm-ostree reload`, `systemctl enable --now rpm-ostreed-automatic.timer`; a daily `flatpak-update.timer` (`flatpak update --noninteractive --assumeyes`); GNOME Software's own downloads off (`gsettings set org.gnome.software download-updates false`).
- **Background work:** `ModemManager` disabled (no modem), `cups.service` disabled with `cups.socket` enabled (starts on demand), file indexing limited to `&DOCUMENTS &DOWNLOAD &MUSIC &PICTURES &VIDEOS` (`org.freedesktop.Tracker3.Miner.Files index-recursive-directories`).

Power needs no tuning: `tuned-ppd` switches to `balanced-battery` when unplugged (Power Saver in the menu goes further; no TLP or auto-cpufreq, which fight it), and the firmware stops charging at 90 %.

## D. Apps

- Flathub unfiltered: `sudo flatpak remote-modify --no-filter --enable flathub`; VLC from it (`org.videolan.VLC`).
- Fedora's Flatpaks removed: Media Writer, Contacts, Calendar, Maps, Weather, Clocks, Connections, Decibels, Characters, Fonts. Firefox stays as a second browser.
- Brave Origin is the default for `http`, `https` and HTML (`xdg-settings set default-web-browser brave-origin.desktop`, plus `gio mime` for each type).

## E. Dev environment

- **SSH keys** `github`, `homelab`, `mephisto`, `whatbox` (from 1Password or devil), mode 600, with `~/.ssh/config` as on devil (`github.com`, `whatbox`, `mephisto`, `Host *` → homelab). The keys have no passphrase, so no agent is needed; GNOME runs one if that changes.
- **git:** name and email, `init.defaultBranch main`, commits and tags signed with `~/.ssh/github.pub` (`gpg.format ssh`, `gpg.ssh.allowedSignersFile ~/.config/git/allowed_signers` holding the email and that key). The key is registered on GitHub as a signing key. devil uses the same settings.
- **mise** (`curl https://mise.run | sh`, into `~/.local/bin`), global tools in `~/.config/mise/config.toml`: `gh`, `ripgrep`, `jq`, `sops`, `age`, `uv`, `gitleaks`, `github:1player/host-spawn`, and CI's pinned versions: `ruff 0.17.5`, `shellcheck 0.11.0`, `yamllint 1.38.0`, `pipx:pytest 9.2.0` (`uvx_args = "--with jinja2 --with pyyaml"`), `pipx:ansible-core 2.22.0` (`--with netaddr`), `pipx:ansible-lint 26.11.0` (`--with ansible-core==2.22.0 --with netaddr`). Languages are per project (`mise use node@24` in a repo).
- **fish** (`~/.config/fish/`): `config.fish` sets `XDG_RUNTIME_DIR` when missing (Tailscale SSH sessions lack it; Toolbox and the `mirror` role need it), adds `~/.local/bin`, inside the Toolbox points `CONTAINER_HOST` at the host's Podman socket and aliases `host` to `host-spawn`, and activates mise (shims when non-interactive). The prompt (`functions/fish_prompt.fish`) is the cyan path with ` => `, prefixed `⬢ ` inside the Toolbox; `functions/code.fish` runs VS Code in the Toolbox from a host terminal. `SOPS_AGE_SSH_PRIVATE_KEY_FILE` is a universal variable pointing at `~/.ssh/homelab`.
- **Repos:** homelab, warden and console cloned in `~/Projects`, `mise trust` in each, and `git config core.hooksPath .githooks` in each (clones do not carry it: without it gitleaks and the push-to-main guard do not run).
- **Ansible:** `ansible-galaxy collection install -r requirements.yml` in homelab. daredevil is a control node (decision 28): mephisto and the tailnet from anywhere, devil over Tailscale SSH (run `ssh devil` once to pass the check), er605 and eap225 only from the home LAN; away, run with `--limit '!routers:!access_points'`. Seed `known_hosts` for `devil.tail6aa22b.ts.net`, `192.168.0.1` and `192.168.0.2` from devil's, never by accepting new keys (on other networks `192.168.0.1` is someone else's router).
- **Claude Code:** the native installer (`curl -fsSL https://claude.ai/install.sh | bash`), `~/.claude/CLAUDE.md` and `settings.json` from devil. Its per-project memory is keyed by path, and the home here is `/var/home/abhay`.

### Toolbox

`toolbox create` (the box matches the host's release), then inside it `sudo dnf install gcc gcc-c++ make pkgconf-pkg-config openssl-devel zlib-devel fish podman-remote` and `sudo ln -sf /usr/bin/podman-remote /usr/local/bin/podman`; on the host `systemctl --user enable --now podman.socket`. Its home is the host's; only `/usr` differs, so `toolbox rm -f fedora-toolbox-45` and a fresh `toolbox create` lose nothing but packages.

`toolbox run` passes its stdin to the command: in scripts give it `</dev/null`, or it swallows the rest of the script.

### VS Code

Microsoft's RPM inside the Toolbox, not layered: its window shows on the desktop and its terminal and extensions see the box's tools. In the box, import `https://packages.microsoft.com/keys/microsoft.asc`, add the `code` repo (`baseurl=https://packages.microsoft.com/yumrepos/vscode`, `gpgcheck=1`) and `sudo dnf install code`. On the host:

- `~/.local/share/applications/code-toolbox.desktop`: `Exec=toolbox run --container fedora-toolbox-45 code %F`, `StartupWMClass=Code`, icon copied from the box's `/usr/share/pixmaps/vscode.png`.
- `code-toolbox-url-handler.desktop` (`--open-url %U`, `MimeType=x-scheme-handler/vscode;`), set as the `vscode://` default for sign-in callbacks.
- `~/.config/Code/User/settings.json`: `"telemetry.telemetryLevel": "off"`, `"dev.containers.dockerPath": "podman"`.

Update it with `sudo dnf upgrade` in the box; no reboot.

Installing from the Marketplace fails with `Signature verification failed with 'UnknownError'` (Microsoft's `vsce-sign` helper exits without verifying; also reported on Arch and Manjaro). Signature checks stay on: install the extension from the `.vsix` VS Code would download (the `Microsoft.VisualStudio.Services.VSIXPackage` URL from `code --install-extension <id> --log trace`) with `code --install-extension <file>.vsix`, or use **Install Anyway** in the error dialog for a publisher you trust.

### Game dev

- Godot (GDScript, `org.godotengine.Godot`) and Blender (`org.blender.Blender`) from Flathub. Flathub's .NET Godot lags far behind, so C# would need the official build and the .NET SDK through mise instead.
- Godot may talk to the host's Flatpak service (`flatpak override --user --talk-name=org.freedesktop.Flatpak org.godotengine.Godot`; it already sees the whole filesystem), so it can start:
  - `~/.local/bin/godot-blender` (`flatpak-spawn --host flatpak run --command=blender org.blender.Blender "$@"`): Godot's Blender path, so `.blend` files import directly.
  - `~/.local/bin/godot-code` (`flatpak-spawn --host toolbox run --container fedora-toolbox-45 code "$@"`): the external editor, exec flags `{project} --goto {file}:{line}:{col}`, off until **Use External Editor** is ticked.
  These live in `~/.var/app/org.godotengine.Godot/config/godot/editor_settings-4.7.tres`.
- `~/.local/bin/godot` runs the Flatpak from the host or the Toolbox; VS Code's `godot-tools` (GDScript language server and debugger over localhost) uses it through `godotTools.editorPath.godot4`.
- Git LFS through mise (`git lfs install --skip-repo`) for models, textures and audio in game repos.
- Blender: **Emulate Numpad** and **Emulate 3 Button Mouse** on (no numpad, touchpad). Cycles cannot use the Radeon 680M, so it renders on the CPU; EEVEE and the viewport run on the GPU.

## F. Checks

| Check | Expected (2026-11-23) |
|---|---|
| Idle on battery, screen at 15 % | ~4 W (`/sys/class/power_supply/BAT0/power_now`) |
| Light work | ~5 W; 7–10 h per charge |
| Overnight sleep (`s2idle`) | 0.6 %/h; `/sys/power/suspend_stats/last_hw_sleep` close to the time asleep |
| Hardware decoding | `brave://gpu`: Video Decode hardware accelerated |
| Ansible from here | `site.yml --check --diff` gives the same recap as from devil |
| Repos | each repo's CI commands pass locally; a commit with a token is refused by gitleaks |

Wake-on-Wi-Fi is not set up: it would keep the radio powered through every sleep.
