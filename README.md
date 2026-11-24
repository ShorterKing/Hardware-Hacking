# Hardware Hacking

I use this repository to document my hardware investigations: getting access to devices I own, understanding their firmware and boot paths, and recording what I verified on the hardware.

## Current case: Tata Play Nokia G-140W-C

I investigated a Tata Sky / Tata Play Nokia G-140W-C whose normal serial boot did not give me a usable bootloader prompt. I used the web configuration to get a root shell, backed up and inspected the stock firmware, found the earlier `btrm>` monitor, and patched its UART receive path in RAM. That let me load and boot my own OpenWrt initramfs from RAM without writing NAND.

I had already worked with an ACTFiber G-140W-C of the same model, where `bldr>` was accessible. The Tata Play router had a different bootloader state and different flash contents. I keep those device-specific details separate.

On 24 November 2026 I also recovered the Tata Play unit's second-stage `bldr>` password. It is derived from the unit's GPON serial number, so it is different on every unit. I reverse-engineered the derivation from the bootram, computed my unit's password, and confirmed it opens the `bldr>` command mode.

This repository is about the hardware access and bootloader work that made the RAM boot possible, and, since 24 November 2026, a permanent OpenWrt install on this unit. My OpenWrt target development and build artifacts live elsewhere; they are not part of this project.

## Contents

- [`docs/g140wc-uart-ramboot.md`](docs/g140wc-uart-ramboot.md) — how I obtained root, found `btrm>`, diagnosed XMODEM, patched the receive and EOT paths, and booted my image.
- [`docs/g140wc-slots-and-boot-flags.md`](docs/g140wc-slots-and-boot-flags.md) — the two firmware slots, the boot flags, why repeated RAM boots made the bootloader switch to the other slot, and the permanent OpenWrt install that the locked second stage boots (24 November 2026).
- [`docs/g140wc-bldr-password.md`](docs/g140wc-bldr-password.md) — how the second-stage `bldr>` password works, the serial-derived derivation I recovered from the bootram, and confirmation that the computed password opens the command mode (24 November 2026).
- [`tools/ramboot-g140wc.py`](tools/ramboot-g140wc.py) — the RAM-only serial loader I used for the completed run.
- [`tools/bldr-passwd-g140wc.py`](tools/bldr-passwd-g140wc.py) — computes a unit's `bldr>` password from its GPON serial.
- `LICENSE` — repository license.

The loader writes temporary code and the supplied image to RAM, verifies image words, and jumps to the image. It does not issue NAND flash or boot-flag commands. A power cycle discards the patches and the router boots stock firmware again. Repeated RAM boots can still make it boot the other stock slot, because the bootloader counts each power-on as a failed boot; see [firmware slots and boot flags](docs/g140wc-slots-and-boot-flags.md).

## Private device data

I keep configuration exports, shadow files, credentials, serial and subscriber identifiers, raw MTD dumps, and run logs in a private backup outside this repository. `.gitignore` excludes these common artifacts. The engineering notes omit their values.

