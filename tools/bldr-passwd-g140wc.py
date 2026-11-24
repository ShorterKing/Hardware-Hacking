#!/usr/bin/env python3
"""
Compute the G-140W-C second-stage (`bldr>`) boot-command-mode password.

The password is per unit: it is derived from the unit's 4-byte G984 GPON serial
number (the eight hex digits after `ALCL` on the device label). I recovered the
algorithm from the second-stage bootram with Ghidra and confirmed the output
opens `bldr>` on my unit. See docs/g140wc-bldr-password.md.

Standard library only (Python 3).

    python3 bldr-passwd-g140wc.py ALCLXXXXXXXX
    python3 bldr-passwd-g140wc.py XXXXXXXX        # the 8 hex digits alone
"""
import sys
import hashlib
import base64

# 32-byte constant from the bootram (at 0x81F2B110), XORed with 0x20..0x01.
KEY32 = bytes([0x16, 0xd1, 0x06, 0xd5, 0xfe, 0x48, 0xcf, 0x2a,
               0x72, 0x5e, 0xa2, 0x0c, 0x26, 0x0a, 0x17, 0xe4,
               0x3a, 0x87, 0xcb, 0xaa, 0x67, 0xc7, 0x48, 0x52,
               0xb0, 0x1b, 0x8a, 0xd1, 0xd6, 0x35, 0x0f, 0x79])
STRIP = set("oO01lI+/=")                       # removed from the base64
PAD = "sjQ51klIdOga3poSzDpIar8epo9U1o2s"        # used only if result < 12 chars


def bldr_password(serial4: bytes) -> str:
    """serial4 = the 4 raw bytes of the G984 serial (e.g. bytes.fromhex('12345678'))."""
    if len(serial4) != 4:
        raise ValueError("G984 serial must be 4 bytes")
    serial_hex = serial4.hex()                                  # 8 lowercase hex chars
    key = bytes(b ^ c for b, c in zip(KEY32, range(0x20, 0x00, -1)))
    digest = hashlib.sha256(serial_hex.encode() + key).digest() # SHA-256, 32 bytes
    s = "".join(c for c in base64.b64encode(digest).decode() if c not in STRIP)
    # Complexity fix-up: if the first 12 chars lack a digit / lower / upper,
    # the bootram forces positions 0, 4, 8.
    first12 = s[:12]
    if not (any(c.isdigit() for c in first12)
            and any(c.islower() for c in first12)
            and any(c.isupper() for c in first12)):
        s = list(s)
        for i, ch in ((0, "J"), (4, "s"), (8, "2")):
            if i < len(s):
                s[i] = ch
        s = "".join(s)
    if len(s) < 12:                                             # effectively never happens
        s += PAD[:12 - len(s)]
    return s[:12]


def parse_serial(arg: str) -> bytes:
    a = arg.strip()
    if len(a) == 12 and a[:4].isalpha():        # ALCLXXXXXXXX -> XXXXXXXX
        a = a[4:]
    a = a.replace("0x", "").replace(":", "").replace(" ", "")
    if len(a) == 8:
        return bytes.fromhex(a)
    raise ValueError("give the 8 hex digits, or a 12-char GPON SN like ALCLXXXXXXXX")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip())
        return 1
    serial4 = parse_serial(sys.argv[1])
    print("G984 serial bytes :", serial4.hex())
    print("bldr> password    :", bldr_password(serial4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
