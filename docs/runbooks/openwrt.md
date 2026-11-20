# OpenWrt on eap225 and er605

One-time migration off stock TP-Link firmware (decision 16). The access point goes first: it is cheaper and the router keeps the house online meanwhile. Stop at any step whose result differs from what is written here.

Target release: OpenWrt 25.12.6. Check [downloads.openwrt.org](https://downloads.openwrt.org/releases/) for a newer 25.12 point release on the day and update the names and checksums below.

## Before either device

- [ ] Spare ISP router ready to take the BSNL line if er605 is down for longer than planned.
- [ ] USB-to-serial adapter, 3.3 V (CP2102 or CH340). The only way to recover a device whose firmware does not boot.
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
2. Move the AP's data cable (the LAN side of its PoE injector) from the home network to devil's `enp14s0`. Without DHCP the stock firmware falls back to `192.168.0.254`. Give devil addresses on both subnets for the rest of section A:
   ```sh
   sudo ip addr add 192.168.0.10/24 dev enp14s0
   sudo ip addr add 192.168.1.10/24 dev enp14s0
   ```
3. Open `http://192.168.0.254` (default login `admin`/`admin`, then set a new password) and enable SSH.
4. SSH in with the legacy algorithms the stock firmware needs:
   ```sh
   ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa \
       -o KexAlgorithms=+diffie-hellman-group1-sha1 admin@192.168.0.254
   ```
5. Run `cliclientd stopcs`. **If the command is missing, stop**: nothing has been changed yet; plug the AP back into the home network and re-adopt it.
6. Copy the factory image to a short name (`factory.bin`; long names have been rejected) and upload it through the web UI's firmware upgrade page. Do not power off until the AP reboots.
7. OpenWrt comes up at `192.168.1.1` with Wi-Fi off. Set the root password, disable its DHCP server and make its LAN a DHCP client so it joins the home network, then remove devil's temporary addresses:
   ```sh
   ssh root@192.168.1.1 passwd
   ssh root@192.168.1.1 '/etc/init.d/dnsmasq disable
     uci set network.lan.proto=dhcp
     uci -q delete network.lan.ipaddr
     uci -q delete network.lan.netmask
     uci commit network
     reboot'
   sudo ip addr del 192.168.0.10/24 dev enp14s0
   sudo ip addr del 192.168.1.10/24 dev enp14s0
   ```
8. Plug the AP's data cable back into the home network; it takes a lease from er605 (find it in the controller's client list).
9. Open the roadmap's step 1 PR (`ap` role, inventory entry) and apply it.

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

After the install, TP-Link's emergency recovery no longer works; the way back to stock is the flash backup from step 6.

**Blocking, resolve before step 1:**

- [ ] Serial header location, pinout and voltage for the ER605 v2 (the OpenWrt device page; the console is `ttyS0` at 115200).
- [ ] The exact command that writes the `firmware` (mtd3) backup back, confirmed from a primary source for the format step 6 produces. The wrong one (`mtd write` versus `ubiformat`) can destroy the NAND's bad-block information.

Steps:

1. Unplug all three WAN cables and keep them out until step 11. With internet access, the stock firmware refuses the locally generated debug password.
2. Connect devil to LAN1. In the Omada controller, forget the ER605: it resets and comes up standalone at `192.168.0.1`. Set its admin password.
3. Web UI: System Tools → Diagnostics → Remote Assistance → enable.
4. Generate the CLI debug password with the repo's `er605rootpw.html`, opened locally (inputs: the MAC on the label, the admin username; use the field for 2.2.2–2.2.5).
5. SSH in, then `enable`, `debug`, and the debug password; the prompt becomes `root@ER605:/#`:
   ```sh
   ssh -o KexAlgorithms=+diffie-hellman-group1-sha1 -o HostKeyAlgorithms=+ssh-rsa -c aes128-ctr admin@192.168.0.1
   ```
   `scp` does not work against this shell; files move over HTTP and netcat.
6. Back up every MTD partition. Open devil's ports for the backup (9090) and the file server (8080) through homelab: add to `ufw_rules` in `host_vars/devil.yml`
   ```yaml
   - {port: "8080", proto: tcp, from_ip: "{{ lan_cidr }}", comment: er605 install files}
   - {port: "9090", proto: tcp, from_ip: "{{ lan_cidr }}", comment: er605 backup}
   ```
   and apply with `ansible-playbook site.yml --limit devil --check --diff`, then without `--check` (mephisto is unreachable while the house is offline, hence `--limit`). Note devil's address and prepare the backup directory:
   ```sh
   ip -4 addr show enp14s0
   mkdir -p ~/er605-backup && cd ~/er605-backup
   ```
   Then for each partition `N` listed in the router's `cat /proc/mtd` (save that output too): on devil `nc -l 9090 > mtdN.bin`, on the router `dd if=/dev/mtdNro | busybox nc <devil> 9090`, and compare `md5sum mtdN.bin` on devil with `dd if=/dev/mtdNro | md5sum` on the router. Every partition must match. Copy the directory to a second place off devil.
7. Serve the install files from devil (`python3 -m http.server 8080` in the directory holding them) and fetch them on the router:
   ```sh
   cd /tmp
   curl -o er605v2_write_initramfs.sh http://<devil>:8080/er605v2_write_initramfs.sh
   curl -o openwrt-initramfs-compact.bin http://<devil>:8080/openwrt-initramfs-compact.bin
   md5sum openwrt-initramfs-compact.bin
   chmod +x er605v2_write_initramfs.sh
   ```
   Stop if the md5 differs from the one above.
8. `./er605v2_write_initramfs.sh openwrt-initramfs-compact.bin`, then `reboot`. Do not cut power while it writes. After 2–3 minutes the installer answers at `http://192.168.1.1` (devil gets a `192.168.1.x` lease).
9. In the installer: "Adjust UBI Layout" if it shows NOT ADJUSTED; upload the 25.12.6 sysupgrade image; **untick "Keep settings"**; never "Force upgrade". "Image check failed" means Keep settings is still ticked.
10. After the reboot, LuCI is at `http://192.168.1.1` as `root` with an empty password: set one. Close the ports opened in step 6: add `state: absent` to both entries, apply with `--limit devil` as before, then delete the entries. Removing them without the `absent` run leaves the rules open, because the role never deletes rules it does not know about.
11. Open the roadmap's step 2 PR (`router` role) and apply it; plug the WAN cables back in (BSNL `wan1`, RailWire `lan2`, Jio `lan3`) and run `verify.yml`.

If the router is not back the same day: BSNL into the spare ISP router; devices re-join its Wi-Fi.

## C. After both

Power off old-devil and remove it from `~/.ssh/config`; its Omada backup on devil (`~/omada-backup`) is no longer needed once the `router` and `ap` roles are applied.
