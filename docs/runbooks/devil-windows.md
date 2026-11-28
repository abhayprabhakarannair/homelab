# devil on Windows 11

Moving devil from CachyOS to Windows 11 (2026-11-28, decision 29). homelab no longer manages devil.

## What changes

| devil today | On Windows |
|---|---|
| warden (`power`, `system`, `sensors`, `ups`) | Not run. er605's warden still pings and wakes devil, so the console keeps its power state and wake button; devil's own card (sensors, disks, UPS, shutdown/reboot/suspend) goes. |
| NUT powers off at 30 % / 5 min and has the UPS cut and restore its output (decision 25) | PowerChute Serial Shutdown (section C). |
| Wake target | Unchanged in homelab; Windows needs the settings in section B. |
| Ansible control node | WSL2 on devil (section D). daredevil has been reinstalled several times; don't rely on it as the only control node. |
| ufw role, Tailscale SSH | Gone: PCs are set up by hand (decision 29), and Tailscale has no SSH server on Windows. |

## A. Install

1. BIOS: fTPM and Secure Boot on; keep Wake-on-LAN (often "Power On by PCI-E") and "Restore on AC power loss: Power On" enabled.
2. Flash the Microsoft Windows 11 ISO with Ventoy, install on the 990 PRO.
3. Leave Wi-Fi off (or disable the MediaTek MT7922 in Device Manager): joining an ISP router's Wi-Fi gives devil an IPv6 route that bypasses er605's failover.
4. Install Tailscale and log in; check devil appears in `tailscale status` from another node.

## B. Remote wake

devil's NIC is a Realtek RTL8125 (2.5GbE).

1. Install Realtek's own driver; the inbox one may lack the wake options below.
2. Fast Startup off: Control Panel → Power Options → Choose what the power buttons do → Change settings that are currently unavailable → untick **Turn on fast startup**. With it on, "shut down" is a hibernate and the NIC often isn't armed.
3. Device Manager → Network adapters → Realtek 2.5GbE → Properties:
   - Advanced: **Wake on Magic Packet** Enabled, **Shutdown Wake-On-Lan** Enabled, **Energy-Efficient Ethernet** and **Green Ethernet** Disabled.
   - Power Management: tick **Allow this device to wake the computer** and **Only allow a magic packet to wake the computer**.
4. Allow er605's ping: Windows drops inbound ICMP echo by default, and er605's warden decides devil's power state by pinging it. In an administrator PowerShell:
   ```powershell
   New-NetFirewallRule -DisplayName "Ping from er605" -Direction Inbound -Protocol ICMPv4 -IcmpType 8 -RemoteAddress 192.168.0.1 -Action Allow -Profile Any
   ```
   Check: the console shows devil online while it runs.
5. Test: shut down from the Start menu, press wake in the console. Repeat after a full power-off at the wall.

## C. UPS: PowerChute Serial Shutdown

APC's current Windows software for USB Back-UPS models (it replaces PowerChute Personal Edition). Rejected: NUT for Windows (its wiki says the installer isn't revived, the USB driver needs manual libusb setup, and no one has reported full shutdowns working on Windows).

A Back-UPS turns its output off about 2 minutes after the PC shuts down and back on when mains returns; the countdown cannot be stopped, so even if mains returns early the UPS cycles and devil boots through "Restore on AC power loss". That matches what NUT did.

1. Install PowerChute Serial Shutdown, connect the UPS over USB.
2. Shut down at 5 minutes runtime remaining. Check whether it also accepts a charge threshold (NUT used 30 %).
3. Test: pull the UPS's mains plug with devil running. Expect Windows to shut down, the UPS to cut its output, and devil to boot on its own when the plug goes back in.

## D. Control node in WSL2

1. `wsl --install` with Fedora or Arch; in `%UserProfile%\.wslconfig`:
   ```ini
   [wsl2]
   networkingMode=mirrored
   ```
   so WSL shares Windows' network: er605 and eap225 on the LAN, mephisto over Windows' Tailscale.
2. Install fish, mise, ansible-core and the collections as on daredevil ([runbook](daredevil.md)); restore `~/.ssh/homelab` from 1Password; clone the three repos into `~/Projects`.
3. Check: `ansible-playbook site.yml --check --diff` changes nothing on er605 and eap225 (mephisto changes once, in section E).

## E. Apply decision 29

The PR that made this change removes devil from the inventory, the `workstation` and `ups` roles, warden's systemd path and the `devil` MQTT user. `wol.devil` stays: er605 still wakes devil.

1. Pull `main` in all three repos.
2. While the broker still has the `devil` user, clear its retained topics, or `verify.yml` fails on them:
   ```fish
   printf '%s\n' '- hosts: mephisto' '  become: true' '  gather_facts: false' '  tasks:' \
     '    - ansible.builtin.command: podman exec mqtt mosquitto_pub -h 127.0.0.1 -p {{ mqtt.port }} -u devil -P {{ secrets.mqtt.devil }} -r -n -t {{ topic_root }}/devil/{{ item }}' \
     '      loop: [meta, status, state]' '      no_log: true' > $XDG_RUNTIME_DIR/clear-devil.yml
   ansible-playbook $XDG_RUNTIME_DIR/clear-devil.yml; and rm $XDG_RUNTIME_DIR/clear-devil.yml
   ```
3. `ansible-playbook site.yml --check --diff`: only mephisto's Mosquitto password file changes. Apply, then run `verify.yml`.
4. `sops edit group_vars/all/secrets.sops.yml`: delete `become.devil`, `mqtt.devil` and `nut`.

## Later: warden on Windows

Only if devil's card or remote power-off is missed. paho-mqtt runs unchanged; warden would need a Windows service under its own account with only the shutdown privilege, `power` through `shutdown /s`/`/r` and a suspend call, and `system` through Windows' disk and memory APIs. `sensors` (LibreHardwareMonitor) and `ups` (PowerChute has no CLI readout) would likely stay out.

## Order

A → B (test a wake) → C (plug-pull test) → D → E.
