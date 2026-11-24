# G-140W-C tools

## RAM loader (`ramboot-g140wc.py`)

I wrote `ramboot-g140wc.py` to automate the UART work for a RAM boot. It needs Python 3 and `pyserial`.

```sh
python3 tools/ramboot-g140wc.py COM9 /path/to/image.bin [run.log]
```

Close any other serial terminal before starting. The loader uses COM9 at 115200 baud, 8-N-1, with flow control off. When it asks, power-cycle the router so it can catch the early `btrm>` prompt.

The script sends `Z` while waiting for `btrm>`, applies the two volatile RAM patches, flushes the affected instruction cache, transfers the supplied image with XMODEM-CRC, checks six sample words, and jumps to the image. It does not issue NAND, erase, flash, or boot-flag commands. A reset discards the patches and returns the router to its stock firmware.

I used it with my own OpenWrt initramfs as the test image. The image and OpenWrt build files are kept outside this repository.

## `bldr>` password (`bldr-passwd-g140wc.py`)

`bldr-passwd-g140wc.py` computes a unit's second-stage `bldr>` boot-command-mode password from its GPON serial number. It is standard-library Python 3, no `pyserial` needed.

```sh
python3 tools/bldr-passwd-g140wc.py ALCLXXXXXXXX
```

Pass the eight hex digits after `ALCL` on the device label (or the full `ALCLXXXXXXXX`). The password is per unit, so it only works on the unit whose serial you give it. I recovered the derivation from the bootram and confirmed the output on my unit; see [docs/g140wc-bldr-password.md](../docs/g140wc-bldr-password.md).

