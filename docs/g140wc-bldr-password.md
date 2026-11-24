# Unlocking the second-stage `bldr>` password on the Tata Play Nokia G-140W-C

**Date:** 24 November 2026
**Board:** `G140WC`, EcoNet EN751221, Toshiba SPI NAND (`TC58CVG1S3H`)
**Result:** I recovered how the second-stage `bldr>` authorization works, computed the password from my unit's GPON serial, and it opened the `bldr>` command mode on the first try. The password is per unit and derived from the serial, so a value from one unit does not work on another.

This resolves the open item from [the RAM boot notes](g140wc-uart-ramboot.md): on this unit the console printed `login without authorization.` and restarted after three attempts, and a candidate value I had tried was rejected. I had worked around it through the first-stage `btrm>` monitor (uppercase `Z`), which has no password. I did not need `bldr>` for the RAM boot, but I wanted to understand the gate.

## Where the second stage lives

The 256 KiB MTD0 bootbase is the first stage; its `btrm>` monitor and the `Z` key-press gate are in it. The `Press any key` prompt and its password check belong to a **second-stage bootram** that the first stage decompresses and runs. The bootram is not in MTD0: it is an LZMA blob at the **tail of each firmware slot image**, after the kernel and root filesystem (slot A at `0x147820f`, a matching blob in slot B). It decompresses to about 206 KiB and runs at `0x81f00000`. Both slots carry the same bootram. I extracted it from my firmware backup, decompressed it, and disassembled it as big-endian MIPS in Ghidra.

The boot sequence on this unit:

```
reset 0xBFC00000 -> first stage (MTD0, btrm>, Z) -> selectImage -> "run bootram N"
   -> LZMA-decompress bootram -> 0x81F00000, jump
      -> bootram prints boardType + "Press any key in 1 secs to enter boot command mode."
         - any key, then correct password -> bldr>
         - no key within ~1 s         -> boot the slot's Linux kernel
```

## The key-press and the password gate

The `Press any key in 1 secs` countdown runs for about one second (it prints the dots) and accepts **any** key: the check reads the UART line-status "receive ready" bit at `0xBFBF0017`, not a specific byte. (The first stage's `btrm>` gate is different: it compares the received byte at `0xBFBF0003` to `Z`.)

After a key, the bootram reads a line from the console and checks it. There is no `Password:` text; it just waits for input. Wrong entries print `login without authorization.`, and the **third** failure writes the reset register (`0xBFB00040 = 0x80000000`, the same write the `reset` command makes) and reboots. There is no permanent lockout; a reboot lets you try again. A correct entry sets an "authorized" flag and drops to `bldr>`.

## How the password is derived

The password is twelve characters, computed from the unit's four-byte G984 serial number — the eight hex digits after `ALCL` on the label. In pseudocode:

```
serial_hex = lowercase hex of the 4-byte G984 serial            # 8 chars
key        = KEY32  XOR  [0x20, 0x1f, ... , 0x02, 0x01]         # 32 bytes
digest     = SHA-256( serial_hex (8 ASCII bytes) + key (32) )  # 32 bytes
b64        = standard base64(digest)                            # 44 chars
s          = b64 with every char in "oO01lI+/=" removed
if first 12 of s lack a digit / lower / upper: s[0]='J'; s[4]='s'; s[8]='2'
if len(s) < 12: pad from "sjQ51klIdOga3poSzDpIar8epo9U1o2s"      # effectively never needed
password   = s[:12]
```

Each building block is read from the bootram, not guessed:

- The hash is **SHA-256**: the init constants match the standard IV (`6a09e667 bb67ae85 3c6ef372 a54ff53a 510e527f 9b05688c 1f83d9ab 5be0cd19`), context size 104 bytes.
- The encoder is **standard base64**, alphabet `ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/` with `=` padding.
- `KEY32` (at `0x81F2B110`): `16 d1 06 d5 fe 48 cf 2a 72 5e a2 0c 26 0a 17 e4 3a 87 cb aa 67 c7 48 52 b0 1b 8a d1 d6 35 0f 79`.
- Strip set (`0x81F2DF44`): `oO01lI+/=`. Pad string (`0x81F2DF50`): `sjQ51klIdOga3poSzDpIar8epo9U1o2s`.

The four serial bytes come from the `G984Serial` entry in the RI (`ri`) partition; the getter returns the raw bytes, which the bootram then hex-encodes.

## The tool

[`tools/bldr-passwd-g140wc.py`](../tools/bldr-passwd-g140wc.py) implements the above. It is standard-library Python 3.

```sh
python3 tools/bldr-passwd-g140wc.py ALCLXXXXXXXX
```

Worked example with a placeholder serial (not my unit):

```
$ python3 tools/bldr-passwd-g140wc.py ALCL12345678
G984 serial bytes : 12345678
bldr> password    : dWhLZ6a5QiNk
```

I verified the tool against my own unit: the password it produced from my serial was accepted at the `Press any key` prompt and opened `bldr>`. Per this repository's practice I keep my serial and the resulting password in my private backup and do not record them here.

## What `bldr>` exposes

Once in, `help` lists the second-stage command set (31 entries), which matched my reverse-engineered table exactly:

```
?  help  ritool  reset  switchImage  ImageInfo  serial_disable  go
memrl  memwl  dump  jump  flash  imginfo  nandit  nandrd  nander  chkmem  innand
bdstore  bdshow  bdswitch  ddrcalswitch  drambistswitch  xmdm  miir  miiw
cpufreq  ipaddr  httpd  ddrdrv
```

These overlap the first-stage `btrm>` set and add `ImageInfo`, `ddrdrv`, and `serial_disable`. Notes:

- `serial_disable` turns off console output — avoid it over serial.
- `flash`, `nander`, `nandit`, `bdstore`, and `switchImage` change flash or boot state; same care as any bootloader write.
- `httpd` starts a small web recovery server that accepts `tcboot.bin` / `tclinux.bin`; it has its own built-in login (a known MitraStar default), separate from this serial-console password.

## Scope and confirmation

- Verified end-to-end on my Tata Play unit (`G140WC`). That test exercised the complexity fix-up branch, so that part is confirmed, not just the common path. The only branch never reached in practice is the `< 12` character padding, which does not occur for a SHA-256 base64 digest.
- The password gate only guards the key-press command mode. As recorded in [firmware slots and boot flags](g140wc-slots-and-boot-flags.md), the bootram still boots the slot's kernel on its own; it does not ask for this password during a normal boot.
- For the RAM-boot workflow I still use the first-stage `btrm>` (uppercase `Z`), which needs no password.
- I did not copy any assumption from the ACTFiber unit; this work is from the Tata Play unit's own firmware and serial.
