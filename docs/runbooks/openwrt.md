# OpenWrt on eap225 and er605

One-time migration off stock TP-Link firmware (decision 16). The access point goes first: it is cheaper and the router keeps the house online meanwhile. Stop at any step whose result differs from what is written here.

Target release: OpenWrt 25.12.6. Check [downloads.openwrt.org](https://downloads.openwrt.org/releases/) for a newer 25.12 point release on the day and update the names and checksums below.

## Before either device

- [ ] Spare ISP router ready to take the BSNL line if er605 is down for longer than planned.
- [ ] USB-to-serial adapter, 3.3 V (CP2102 or CH340), jumper wires and a soldering iron: both devices need two solder bridges before their serial console works. The only way to recover a device whose firmware does not boot.
- [ ] `openbsd-netcat` on devil (`sudo pacman -S openbsd-netcat`) for the er605 backup.
- [ ] Omada auto-upgrade stays off; no firmware upgrades on either device. er605 firmware 2.2.6 and later block the install; newer EAP firmware drops `cliclientd`.
- [ ] Images downloaded to devil and checked against the release's `sha256sums`:

| Image | sha256 |
|---|---|
| `openwrt-25.12.6-ath79-generic-tplink_eap225-v4-squashfs-factory.bin` | `de522200d9064c6cda47f67fe752e8afbfe19112b71e004e729bf0cee975d36d` |
| `openwrt-25.12.6-ramips-mt7621-tplink_er605-v2-squashfs-sysupgrade.bin` | `49bd05867b916f55e4a242b8e65b09ad28d9c519004268da1484affdf2ea5556` |

```sh
sha256sum -c --ignore-missing sha256sums
```

## A. eap225 (EAP225(US) v4.0, stock 5.1.10)

QCA9563, 128 MiB RAM, 16 MiB SPI-NOR flash. Use the **v4** image only: a v3 image can brick a v4. House Wi-Fi is down from step 1 until the `ap` role is applied; use the ISP routers' Wi-Fi meanwhile.

OpenWrt boots with a DHCP server on `192.168.1.1/24`, so from step 2 until that server is disabled the AP must not be on the home LAN: it would hand out wrong leases to every device that renews.

1. In the Omada controller, forget the EAP225. It resets to factory defaults.
2. Unplug the cable between er605 and the injector's **LAN** port at the router end and plug it into devil's `enp14s0`. Never connect devil to the injector's **PoE** port: the bundled injector is passive 24 V. Check the link is 1 Gbit/s and stable (`journalctl -k | grep enp14s0`); a flapping 10/100 Mbit/s link is a bad cable. Without DHCP the stock firmware falls back to `192.168.0.254`. Stop NetworkManager from managing the port (it would flush manual addresses when DHCP times out) and give devil addresses on both subnets for the rest of section A:
   ```sh
   sudo nmcli device set enp14s0 managed no
   sudo ip addr add 192.168.0.10/24 dev enp14s0
   sudo ip addr add 192.168.1.10/24 dev enp14s0
   ```
3. Open `http://192.168.0.254` (default login `admin`/`admin`, then set a new password) and enable SSH.
4. SSH in. Its dropbear (2018) resets the connection when offered OpenSSH 10's full host-key list, so offer only `ssh-rsa`:
   ```sh
   ssh -o HostKeyAlgorithms=ssh-rsa -o PubkeyAuthentication=no -o UserKnownHostsFile=/dev/null <user>@192.168.0.254
   ```
5. Run `cliclientd stopcs`. **If the command is missing, stop**: nothing has been changed yet; plug the AP back into the home network and re-adopt it.
6. Copy the factory image to a short name (`factory.bin`; long names have been rejected) and upload it through the web UI's firmware upgrade page. Do not power off until the AP reboots.
7. OpenWrt comes up at `192.168.1.1` with Wi-Fi off and root without a password. Install the homelab key, set the root password, disable its DHCP server and IPv6 router advertisements (odhcpd would hand the whole LAN a ULA prefix and DNS), make its LAN a DHCP client, then give the port back to NetworkManager:
   ```sh
   ssh -o UserKnownHostsFile=/dev/null root@192.168.1.1 'cat > /etc/dropbear/authorized_keys' < ~/.ssh/homelab.pub
   ssh -o UserKnownHostsFile=/dev/null root@192.168.1.1 passwd
   ssh -o UserKnownHostsFile=/dev/null root@192.168.1.1 '/etc/init.d/dnsmasq disable
     /etc/init.d/odhcpd disable
     uci set system.@system[0].hostname=eap225
     uci set network.lan.proto=dhcp
     uci -q delete network.lan.ipaddr
     uci -q delete network.lan.ip6assign
     uci -q delete network.globals.ula_prefix
     uci commit
     reboot'
   sudo ip addr del 192.168.0.10/24 dev enp14s0
   sudo ip addr del 192.168.1.10/24 dev enp14s0
   sudo nmcli device set enp14s0 managed yes
   ```
8. Plug the cable back into er605; the AP takes its reserved lease (`192.168.0.2`). Accept its new host key once (`ssh -o StrictHostKeyChecking=accept-new root@192.168.0.2 true`).
9. `ansible-playbook site.yml --limit eap225 --check --diff`, then without `--check`, then `verify.yml --limit eap225`.

Recovery if it does not boot: serial header J4 (1 TXD, 2 RXD, 3 GND, 4 VCC) needs the unpopulated resistors R225 (TXD) and R237 (RXD) bridged with solder; **never bridge R230**. 3.3 V, 115200 8n1. Hold Ctrl+B during boot for the bootloader, then:

```
setenv ipaddr 192.168.1.1
setenv serverip 192.168.1.10
tftp 0x80800000 initramfs.bin
bootelf $fileaddr
```

and flash from the initramfs's web interface (`openwrt-25.12.6-ath79-generic-tplink_eap225-v4-initramfs-kernel.bin`).

## B. er605 (ER605 v2.20, stock 2.2.5)

MT7621, 256 MiB RAM, 128 MiB NAND. The house is offline from step 1 until the `router` role is applied, so download everything first.

The official initramfs (6.4 MB) does not fit the stock kernel volume (5 MiB), so the install goes through the community image `openwrt-initramfs-compact.bin` (OpenWrt 23.05.0, 4.6 MB) from [chill1Penguin/er605v2_openwrt_install](https://github.com/chill1Penguin/er605v2_openwrt_install). It only runs long enough to install the official sysupgrade image. md5 `e06dd6da68b739b2544931a0203292db` (the repo's `md5sums` and [nicobm's guide](https://nicobm.github.io/er605-v2-openwrt/) agree).

After the install, TP-Link's emergency recovery no longer works and "Adjust UBI Layout" changes the flash layout, so the only proven way back to stock is the serial console plus the `firmware` (mtd3) backup from step 6 (see Recovery below).

Steps:

1. Download and verify everything first, then unplug all three WAN cables and keep them out until step 11. With internet access, the stock firmware refuses the locally generated debug password. Devil stays online on an ISP router's Wi-Fi.
2. In the Omada controller, forget the ER605: it resets and comes up standalone at `192.168.0.1` after 2–3 minutes. Set its admin password.
3. Web UI: System Tools → Diagnostics → Remote Assistance → enable.
4. Compute the CLI debug password offline (firmware 2.2.2 and later; the repo's `er605rootpw.html` does the same but loads its md5 library from a CDN). `<MAC>` is the label MAC in upper case with colons:
   ```sh
   echo -n "<MAC>admin<MAC>admin" | md5sum | cut -c1-16
   ```
5. SSH in, then `enable`, `debug`, and the debug password; the prompt becomes `root@ER605:/#`. Remote Assistance must be on, or port 22 is closed:
   ```sh
   ssh -o HostKeyAlgorithms=ssh-rsa -o PubkeyAuthentication=no -o UserKnownHostsFile=/dev/null admin@192.168.0.1
   ```
   `scp` does not work against this shell; files move over HTTP and netcat.
6. Back up every MTD partition. Open devil's ports for the backup (9090) and the file server (8080) through homelab: add to `ufw_rules` in `host_vars/devil.yml`
   ```yaml
   - {port: "8080", proto: tcp, from_ip: "{{ lan_cidr }}", comment: er605 install files}
   - {port: "9090", proto: tcp, from_ip: "{{ lan_cidr }}", comment: er605 backup}
   ```
   and apply with `ansible-playbook site.yml --limit devil --check --diff`, then without `--check`. In a directory served over HTTP (step 7) put `backup.sh`, adapted from the installer repo's `MTD_backup` (set `HOST` to devil's address):
   ```sh
   #!/bin/sh
   HOST=192.168.0.4
   PORT=9090
   send() { echo "$1" | busybox nc $HOST $PORT; sleep 1; }
   echo -n > /tmp/md5sums
   tail -n+2 /proc/mtd | while read; do
     DEV=$(echo ${REPLY} | cut -f1 -d:)
     NAME=$(echo ${REPLY} | cut -f2 -d\")
     FILE="${DEV}_${NAME}.backup"
     echo "Backing up ${DEV} (${NAME})"
     send "$FILE"
     dd if=/dev/${DEV}ro 2>/dev/null | busybox nc $HOST $PORT
     echo "$(dd if=/dev/${DEV}ro 2>/dev/null | md5sum | cut -f1 -d' ')  $FILE" >> /tmp/md5sums
     sleep 1
   done
   send proc_mtd.txt; cat /proc/mtd | busybox nc $HOST $PORT; sleep 1
   send ubinfo.txt; ubinfo -a 2>&1 | busybox nc $HOST $PORT; sleep 1
   send md5sums; cat /tmp/md5sums | busybox nc $HOST $PORT
   echo "BACKUP SENT"
   ```
   On devil, in `~/er605-backup`, run the receiver; then on the router `cd /tmp && curl -o backup.sh http://<devil>:8080/backup.sh && sh backup.sh` (about 5 minutes, 27 partitions):
   ```sh
   while true; do
     NAME=$(nc -d -l 9090); [ -z "$NAME" ] && continue
     echo "Receiving $NAME"; nc -d -l 9090 > "$NAME"
     [ "$NAME" = md5sums ] && break
   done
   md5sum -c md5sums
   ```
   Every partition must report OK and match its size in `proc_mtd.txt`; `mtd3_firmware.backup` is 130809856 bytes. Keep two more copies off devil (2026-11-20: old-devil and mephisto, `er605-backup-2026-11-20.tar.zst`).
7. Serve the install files from devil (`python3 -m http.server 8080 --bind <devil>` in the directory holding them) and fetch them on the router:
   ```sh
   cd /tmp
   curl -o er605v2_write_initramfs.sh http://<devil>:8080/er605v2_write_initramfs.sh
   curl -o openwrt-initramfs-compact.bin http://<devil>:8080/openwrt-initramfs-compact.bin
   md5sum openwrt-initramfs-compact.bin
   chmod +x er605v2_write_initramfs.sh
   ```
   Stop if the md5 differs from the one above.
8. `./er605v2_write_initramfs.sh openwrt-initramfs-compact.bin` must print `Found kernel ubi partitions (ubi0_7 and ubi0_14)` and `Done!`; only then `reboot`. Do not cut power while it writes. After 2–3 minutes the installer answers at `http://192.168.1.1`. If devil reaches the router through a switch its link never drops, so renew its lease by hand (`nmcli device connect enp14s0`).
9. In the installer click "Adjust UBI Layout" and wait for ADJUSTED. Its flash button runs `sysupgrade` without `-n` and fails with "Image check failed": the 25.12 image has config version 1.2, the 23.05 installer 1.1. Upload the image through the page anyway (it lands in `/tmp/firmware.bin`), then over SSH (root, no password) check it and flash without keeping settings:
   ```sh
   ssh -o UserKnownHostsFile=/dev/null root@192.168.1.1 'sha256sum /tmp/firmware.bin; sysupgrade -T -n /tmp/firmware.bin && sysupgrade -n /tmp/firmware.bin'
   ```
   Never `-F`. "Command failed: ubus call system sysupgrade … (Connection failed)" is normal as the session closes.
10. OpenWrt answers at `192.168.1.1` after about 2 minutes. Install the homelab key and set the root password (as in section A, step 7), then move the LAN to the old subnet so devices keep their leases: `uci set network.lan.ipaddr=192.168.0.1/24 && uci commit network && /etc/init.d/network restart`, and renew devil's lease. Close the ports opened in step 6: add `state: absent` to both entries, apply with `--limit devil` as before, then delete the entries.
11. Plug BSNL into the WAN port only, apply the `router` role (`site.yml --limit er605 --check --diff`, then without `--check`), then plug RailWire into WAN/LAN1 and Jio into WAN/LAN2 and run `verify.yml`. Before the role, `lan2` and `lan3` are LAN ports: an ISP box plugged in there would serve DHCP to the house.

If the router is not back the same day: BSNL into the spare ISP router; devices re-join its Wi-Fi.

Recovery and return to stock ([forum walkthrough](https://forum.openwrt.org/t/looking-for-info-and-possibility-of-future-support-of-tp-link-omada-er605-router/91868/344), partition offsets match OpenWrt's device tree):

1. Open the case and bridge the R2 and R5 pads with solder. On header J1, counting from the right: pad 1 to the adapter's RX, pad 2 to its TX, pad 3 to GND; leave pad 4 (VCC) unconnected. 3.3 V, 115200 8n1. If nothing prints, swap RX and TX.
2. Cable devil to LAN5 (`lan5`), add `192.168.0.146/24` to `enp14s0`, open UDP 69 from `lan_cidr` through `ufw_rules` as in step 6, and serve the directory holding `mtd3_firmware.backup` (renamed to `mtd3.bin`) over TFTP (`tftp-hpa`: `sudo in.tftpd -L -s <dir>`).
3. Power on; in U-Boot's boot menu choose "2. Upgrade firmware", TFTP client, U-Boot address `192.168.0.10`, server `192.168.0.146`, netmask `255.255.255.0`, file `mtd3.bin`. It loads 130809856 bytes to `0x80010000`; the automatic erase that follows has been seen to fail, so finish from the U-Boot console:
   ```
   mtdparts
   nand erase 0x00140000 0x07cc0000
   nand write 0x80010000 0x00140000 0x07cc0000
   ```
   Check that `mtdparts` shows `firmware` at offset `0x00140000`, size `0x07cc0000` before erasing. "skipping bad block" messages are expected.
4. Reboot into the stock firmware and re-flash 2.2.5 from its web UI (System Tools → Management → Firmware Upgrade).

## C. After both

Power off old-devil and remove it from `~/.ssh/config`; its Omada backup on devil (`~/omada-backup`) is no longer needed once the `router` and `ap` roles are applied.

## D. Upgrading

Firmware and packages are upgraded together with `upgrade.yml`, never with `apk upgrade`: an upgraded package is stored again on the writable overlay next to its copy in the read-only image, and eap225 has 5.8 MB of overlay. `verify.yml` reports pending updates (packages rebuilt since the release, or a newer release in the branch).

`owut` asks OpenWrt's build server (ASU, the Image Builder run by the project) for a sysupgrade image of the release with current package revisions and every installed package, so Python, mwan3, vnstat and warden's dependencies are in the image. sysupgrade keeps `/etc/config`, package conffiles and the keep lists the roles deploy (`/lib/upgrade/keep.d/homelab-*` and `warden`: usage database, warden, ISP override helper, AP's API ACL). Services the roles keep off (odhcpd on both, dnsmasq on eap225) come back enabled in a new image, so the roles also deploy `/etc/owut.d/homelab-init.sh`, which `upgrade.yml` passes to the build as its first-boot script. It goes to the build server and into a downloadable image: keep secrets out of it.

1. `site.yml` applied from `main` (the playbook refuses to start without the keep lists and first-boot script).
2. `ansible-playbook upgrade.yml --check`: reports which devices have updates. `-e upgrade_version=25.12.7` moves to another release (`owut versions` lists them); without it the installed release is rebuilt with current packages.
3. `ansible-playbook upgrade.yml`: eap225, then er605. Per device: `owut check` (stops if nothing changed or packages would be downgraded), a config backup to `~/openwrt-backups/<host>-<time>.tar.gz` on devil (contains `/etc/shadow`, the Wi-Fi key and warden's password: private, not in the repo), `owut download --init-script …` (builds for a few minutes, verifies the checksum and sysupgrade's image check), `owut install` (procd flashes and reboots; the SSH session dropping is expected), then waits for SSH and checks that `owut check` finds no changes. er605 takes the house offline for a few minutes.
4. `ansible-playbook site.yml --check --diff`, then without `--check`, then `verify.yml`. On er605 the check is not clean after an upgrade: the new image's first boot runs package defaults that put back what the templates leave out (2026-11-21: odhcpd's section and DHCPv6/RA options in `dhcp`, `dhcp_default_duid` in `network`). They are inert while odhcpd is off, and applying `site.yml` removes them; the check after that must be clean.

Never `--force` (it allows downgrades and rebuilds with nothing to change) or `--rootfs-size` (loses the config). If the server is down, wait; build with the Image Builder in a Podman container on devil only if that ever lasts. A device that does not come back: restore the backup with `sysupgrade -r` after reflashing the release image, or recover over serial as in sections A and B.
