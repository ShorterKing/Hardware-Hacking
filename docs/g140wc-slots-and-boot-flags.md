# Firmware slots, boot flags and a permanent OpenWrt install on the Tata Play Nokia G-140W-C

**Date:** 24 November 2026  
**Board:** `G140WC`, EcoNet EN751221, Toshiba SPI NAND (`TC58CVG1S3H`)  
**Result:** Slot B holds a complete stock image, and it boots. My repeated RAM boots had made the bootloader switch to it by itself. With slot B as a fallback, I installed OpenWrt to slot A, and the unit's own locked second stage boots it.

## Checking the flash against my backup

I RAM-booted OpenWrt as described in [the RAM boot notes](g140wc-uart-ramboot.md) and hashed the partitions from Linux. My device tree for this board has no `econet,enable-remap`, so reading can't make the bad-block layer remap (write) a block. The first-stage bootloader (MTD0) and both firmware slots matched my 15 November backup byte for byte.

## Two complete firmware slots

| Slot | Flash offset | Size | Header | Firmware |
|---|---|---|---|---|
| A (`tclinux`) | `0x0080000` | 34 MiB | `2RDH`, checksum matches | `3FE47150BBBL02` |
| B (`tclinux_slave`) | `0x2280000` | 34 MiB | `2RDH`, checksum matches | `3FE47150CGCB42` |

The checksum is the JAMCRC stored in the header, over the image from offset `0x100` to its total length. Slot B isn't empty: it holds an older complete stock image. Both slots carry the same second-stage bootram.

## The boot flags

The `flag` partition and its copy `flagback` start with six big-endian 32-bit words. The second stage prints the first five at boot:

| Word | Name |
|---|---|
| 0 | `commit` |
| 1 | `next_active` (0 = slot A, 1 = slot B) |
| 2 | `image0_is_valid` |
| 3 | `image1_is_valid` |
| 4 | `boot_fail_num` |
| 5 | not printed |

| | `next_active` | `image0_is_valid` | `image1_is_valid` | `boot_fail_num` |
|---|---|---|---|---|
| 15 November backup | 0 | 1 | 0 | 0 |
| 24 November, before my test | 1 | 0 | 1 | 1 |

## Why the bootloader switched slots

The bootloader counts every power-on as a failed boot. The stock firmware resets the count once it has started. My RAM boots stop at `btrm>`, so the stock firmware never ran between them. After about nine power-ons, the bootloader marked slot A invalid and switched to slot B.

So the RAM boot doesn't write the flash itself, but repeated RAM boots still change the flags, and the next normal boot then uses the other slot.

## Slot B boots

I let the router boot normally with these flags and only logged the serial console, without sending anything. The second stage printed the flags, selected slot B at `0x2280000` and loaded its kernel:

```
*********run bootram 1********
...
next_active = 1
image0_is_valid = 0
image1_is_valid = 1
boot_fail_num = 2
#######select1  0x2280000
#######kernel_size 2769913
```

The stock firmware from slot B (kernel built in 2020) came up and reported slot B as active and committed.

## A misleading size warning

At every power-on, the first stage prints:

```
tclinux partition size = 0x1000000, real size = 0x147820f
tclinux partition size < its real size
tclinux_slave partition size = 0x1000000, real size = 0x2ab0ac6d
tclinux_slave partition size < its real size
```

This check assumes 16 MiB slots. For slot A the size is right and the warning is harmless. For slot B it reads the header at `0x1080000`, inside slot A, so the size it prints is garbage. I confirmed that against my backup: the header words at that offset give exactly `0x2ab0ac6d`. The boot itself uses the right address, as the log above shows.

## Installing OpenWrt to slot A

With slot B proven, I installed my OpenWrt build to slot A. I RAM-booted my production image, which, unlike my RAM-test image, carries the install scripts, checked the upgrade with `sysupgrade -T`, and ran `sysupgrade -n` with my image. The upgrade:

- copied the second-stage bootram from the stock image into the new slot A image, unchanged;
- read the Wi-Fi calibration from the stock configuration partition, which my device tree keeps read-only;
- set the flags to boot slot A, with both slots valid;
- wrote the kernel and the root filesystem to slot A. MTD0, slot B and the configuration are read-only in my device tree.

After the reboot, the bootloader ran slot A's bootram, which is this unit's own stock bootram, and it booted OpenWrt:

```
*********run bootram 0********
...
next_active = 0
image0_is_valid = 1
image1_is_valid = 1
#######select0  0x80000
#######kernel_size 4063232
```

So on this unit the login prompt only guards the key-press command mode, and the bootram boots my kernel without complaint. OpenWrt now runs from flash with both radios calibrated. It resets the failed-boot count at every boot, so the bootloader stays on slot A, and slot B keeps the stock firmware as a fallback.

At the end of the upgrade, just before the reboot, the console showed a firmware-loading warning from the 5 GHz Wi-Fi driver. Creating the calibration volume woke the Wi-Fi drivers after the upgrade had already removed their firmware files. It's harmless: the next boot, from flash, loaded both radios' firmware.

## What I changed

In the slot and flag test, nothing: the bootloader changed the flags by itself, and the stock firmware updated them when it booted from slot B. The install then wrote slot A and the boot flags, as described above. I didn't touch MTD0 or slot B, and the first-stage `btrm>` RAM boot stays available as a way back.
