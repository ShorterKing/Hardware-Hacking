# How I reached a RAM boot on the Tata Play Nokia G-140W-C

**Date:** 19 November 2026  
**Board:** `G140WC`, EcoNet EN751221  
**Result:** I used the router's first-stage serial monitor to load my own OpenWrt build17 initramfs into RAM and boot it to the serial console. I did not write NAND, boot flags, or bootloader contents.

## The two routers

I had already worked with an ACTFiber Nokia G-140W-C of the same model. Its `bldr>` prompt was unlocked, and I used that router while developing my image. The Tata Sky / Tata Play unit had a different bootloader state. I could not enter its second-stage `bldr>` prompt: the console printed `login without authorization.` and restarted after three failed attempts. A candidate authorization value I tried was rejected.

The ordinary Linux boot gave me only a restricted `user>` shell. The serial connection itself worked; access to the second-stage command shell was gated.

## Getting a root shell and backing up stock

I logged into the web interface using the publicly documented credentials for the `AdminGPON` account and exported `config.cfg`. I used the previously published [Nokia configuration utility by Sami Alaoui Kendil](https://gist.github.com/thedroidgeek/80c379aa43b71015d71da130f85a435a) to unpack the backup, change the Telnet/SSH and `ONTUSER` settings, and rebuild it. After restoring that edited configuration, I got a root shell on the running Linux system. That gave me filesystem access but did not unlock `bldr>`.

From the root shell, I copied the MTD partitions to USB and saved a local backup. The rootfs MTD entry overlapped the active Linux image, so I did not treat it as a separate partition dump. The saved boot flags showed image0 active and valid and image1 invalid.

I tried limited erase and write operations on the inactive image1 partition. Erase returned `Invalid argument`, the generic unlock ioctl was unsupported, and a block-device write did not change the saved image. My kernel analysis found a vendor partition-protection check consistent with those failures. I did not successfully write a partition or boot flag, and I did not run the stock updater.

## Finding the earlier `btrm>` monitor

The 256 KiB MTD0 bootbase is the first-stage bootloader. Its LZMA payload begins at offset `0x10000` and is mapped around `0x81fb0000`. The later `Press any key` prompt and its authorization check belong to a second-stage bootram embedded in the stock firmware images.

When I disassembled the first stage, I found a separate, short power-up gate for uppercase `Z`. I sent `Z` while powering up and followed it with another byte, such as CR. That entered the earlier `btrm>` monitor before the second-stage authorization check. Its command list includes RAM access, `xmdm`, and `jump`. This gave me a usable RAM boot path without opening `bldr>`.

## Diagnosing the XMODEM receive failure

At `btrm>`, `xmdm 80020000 <length>` emitted `C`, asking for XMODEM-CRC packets. My first Tera Term attempts timed out. I then used Python on COM9 at 115200 baud, 8-N-1, with flow control off. The prompt responded and echoed a 120-character burst, so I knew the serial link was working. Ordinary XMODEM packets still got repeated `C` requests, NAKs, or `received len=fffffffd`.

Disassembly showed that the receive helper at `0x81fbd0b0` consumed UART data and accepted only byte `Z`. XMODEM was sending normal packet bytes, which the helper discarded. I patched the helper in RAM to check the UART RX-ready bit instead:

```text
0x81fbd0b4  lbu  v0, 0x17(v0)   # read UART status
0x81fbd0b8  andi v0, v0, 1      # test RX-ready
0x81fbd0bc  jr   ra
0x81fbd0c0  nop
```

`memwl` writes memory but does not flush the instruction cache. I wrote a trampoline at uncached address `0xa0020000` to call the bootbase cache-maintenance routine at `0x81fbb3b0`, then return to `btrm>`. After that, a normal 128-byte XMODEM-CRC test packet was ACKed twice.

## Fixing the separate EOT hang

My first full transfer attempt reached 100% on the sender, but I could not confirm the post-transfer prompt or RAM readback, so I did not jump to the image. I found a second problem: the post-EOT drain at `0x81fbdd00` waited on a timer that does not advance at `btrm>`. In the successful loader, I replaced that call with a NOP. Both patches are temporary RAM changes and disappear when the router resets.

## Loading and booting my image

I ran the one-shot loader from [`tools/ramboot-g140wc.py`](../tools/ramboot-g140wc.py) with my separately built initramfs. The loader sends `Z` while waiting for `btrm>`, applies and reads back the RAM patches, transfers the image, checks sample words, and jumps only after those checks match.

```text
Image:  openwrt-econet-en751221-nokia_g140w-c-initramfs-kernel.bin
Size:   11,102,023 bytes (0xa96747)
SHA256: 81af8b66c7df378302036e4ab5755c64087f66e03e009947f2ee12c62241d3f8
Load:   0x80020000
```

The final run sent 86,735 128-byte XMODEM-CRC blocks with zero retries. I padded the final block with `0x1a`. After EOT, the router ACKed and returned to `btrm>` with `received len=a96780`, the padded transfer size. Six sampled 32-bit words at the start, middle, and end of RAM matched the image; the first word was `0x00808025`. Then I ran `jump 80020000`.

The serial log shows the zImage decompressed, the device tree copied, and Linux 6.18.60 identifying the machine as a Nokia G-140W-C. OpenWrt reached `Please press Enter to activate this console.` That confirmed my image had booted from RAM on the Tata Play unit.

## What I did not change

- I did not unlock the second-stage `bldr>` authorization.
- I did not write NAND, change boot flags, or use the stock firmware updater.
- This is a volatile RAM boot. Power cycling returns the router to stock firmware.
- I have not verified a permanent install or a safe flash procedure for this Tata Play unit. I do not copy the ACTFiber unit's NAND or boot-flag assumptions to it.

## My records

- RAM loader: `tools/ramboot-g140wc.py`
- I keep the complete serial capture in my private research archive rather than this repository.
- I keep configuration exports, credentials, raw MTD dumps, and device identifiers in a private backup outside this repository.

