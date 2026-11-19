# One-shot RAM boot for the G-140W-C btrm> bootloader. RAM only, never flash.
#  1. waits for btrm> (power-cycle the router while this runs)
#  2. RAM patches:
#       81fbd0b4..c0  rx-ready predicate -> UART LSR bit 0 (was the 'Z' check)
#       81fbdd00      nop out the post-EOT input drain (jal 81fbdc2c), which
#                     waits for timer ticks that never advance at btrm>
#                     (timer is stopped at 81fbaa70) and so hangs forever
#  3. cache sync via trampoline at a0020000 -> 81fbb3b0(81fbd0b0, 81fbdd04)
#  4. xmdm 80020000, XMODEM-CRC transfer, EOT
#  5. verifies sample words against the file, jumps, logs boot output
# usage: python3 tools/ramboot-g140wc.py COM9 <image> [log]
import re, sys, time, serial

SOH, EOT, ACK, NAK, CAN = 0x01, 0x04, 0x06, 0x15, 0x18
ADDR = 0x80020000

port, image = sys.argv[1], sys.argv[2]
logf = open(sys.argv[3] if len(sys.argv) > 3 else image + ".all.log", "a", encoding="utf-8", errors="replace")
data = open(image, "rb").read()


def out(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    logf.write(line + "\n")
    logf.flush()


s = serial.Serial(port, 115200, timeout=0.2, xonxoff=False, rtscts=False)


def read_for(sec):
    buf, end = b"", time.time() + sec
    while time.time() < end:
        buf += s.read(4096)
    return buf


def read_until_prompt(timeout):
    buf, end = bytearray(), time.time() + timeout
    while time.time() < end:
        c = s.read(4096)
        if c:
            buf.extend(c)
            if b"btrm>" in buf[-100:]:
                break
    return bytes(buf)


def cmd(c, timeout=5):
    s.reset_input_buffer()
    s.write(c.encode() + b"\r")
    s.flush()
    r = read_until_prompt(timeout)
    if b"btrm>" not in r[-100:]:
        out(f"no prompt after {c!r}: {r[-120:]!r}")
        sys.exit(2)
    return r


def crc16(b):
    c = 0
    for x in b:
        c ^= x << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xffff if c & 0x8000 else (c << 1) & 0xffff
    return c


def memrl(addr):
    r = cmd(f"memrl {addr:08x}").decode(errors="replace")
    m = re.search(rf"{addr:08X}:\s*([0-9A-Fa-f]+)", r)
    return int(m.group(1), 16) if m else None


out(f"image {image}: {len(data)} bytes")

# 1. wait for btrm>
out("waiting up to 15 min for btrm> -- power-cycle the router now (sending 'Z')")
s.timeout = 0.02
buf, end = bytearray(), time.time() + 900
while time.time() < end:
    s.write(b"Z")
    c = s.read(4096)
    if c:
        buf.extend(c)
        if b"btrm>" in buf[-100:]:
            break
s.timeout = 0.2
out(f"console tail: {bytes(buf[-120:])!r}")
if b"btrm>" not in buf[-100:]:
    out("no btrm> prompt, stopping (nothing written)")
    sys.exit(1)
# stray Z's may have been typed at the prompt; flush them with a CR
# (runs as an unknown command) and confirm a clean prompt
read_for(1)
s.write(b"\r")
read_for(1)
cmd("")
out("clean btrm> prompt confirmed")

# 2. patches
patches = [
    (0x81fbd0c0, 0x00000000),
    (0x81fbd0bc, 0x03e00008),
    (0x81fbd0b8, 0x30420001),
    (0x81fbd0b4, 0x90420017),
    (0x81fbdd00, 0x00000000),
]
stub = [0x27bdfff0, 0xafbf000c, 0x3c0481fb, 0x3484d0b0,
        0x3c0581fb, 0x34a5dd04, 0x3c1981fb, 0x3739b3b0,
        0x0320f809, 0x00000000, 0x8fbf000c, 0x27bd0010,
        0x03e00008, 0x00000000]
for a, w in patches:
    cmd(f"memwl {a:08x} {w:08x}")
for i, w in enumerate(stub):
    cmd(f"memwl {0xa0020000 + 4 * i:08x} {w:08x}")
for a, w in patches:
    got = memrl(a)
    if got != w:
        out(f"patch readback {a:08x}: got {got} want {w:08x}; stopping")
        sys.exit(2)
r = cmd("jump a0020000", 8)
out("patches written and verified; cache sync returned to btrm>")

# 3. transfer
s.reset_input_buffer()
s.write(f"xmdm {ADDR:08x} {len(data):x}\r".encode())
end = time.time() + 30
while time.time() < end:
    if s.read(1) == b"C":
        break
else:
    out("bootloader never sent C")
    sys.exit(1)
out("bootloader ready, sending")
blocks = (len(data) + 127) // 128
t0 = time.time()
for i in range(blocks):
    chunk = data[i * 128:(i + 1) * 128].ljust(128, b"\x1a")
    n = (i + 1) & 0xff
    pkt = bytes([SOH, n, 255 - n]) + chunk + crc16(chunk).to_bytes(2, "big")
    for attempt in range(10):
        s.write(pkt)
        r, wait = b"", time.time() + 10
        while time.time() < wait:
            r = s.read(1)
            if r and r[0] in (ACK, NAK, CAN):
                break
            r = b""
        if r and r[0] == ACK:
            break
        if r and r[0] == CAN:
            out(f"cancelled at block {i + 1}")
            sys.exit(1)
        out(f"block {i + 1}: retry {attempt + 1} (reply {r!r})")
    else:
        out(f"block {i + 1}: no ACK after 10 tries")
        sys.exit(1)
    if (i + 1) % 5000 == 0 or i + 1 == blocks:
        el = time.time() - t0
        out(f"block {i + 1}/{blocks} ({100 * (i + 1) // blocks}%), {el:.0f}s, ~{el / (i + 1) * (blocks - i - 1) / 60:.1f} min left")

s.write(bytes([EOT]))
r = read_until_prompt(10)
out(f"after EOT: {r[-120:]!r}")
if b"btrm>" not in r[-100:]:
    out("prompt did not return after EOT; stopping")
    sys.exit(3)

# 4. verify
ok = True
for off in (0, 4, 0x10, 0x100000, 0x500000, (len(data) - 7) & ~3):
    want = int.from_bytes(data[off:off + 4].ljust(4, b"\x1a"), "big")
    got = memrl(ADDR + off)
    good = got == want
    ok &= good
    out(f"verify {ADDR + off:08x}: got {got if got is None else f'{got:08x}'} want {want:08x} {'OK' if good else 'BAD'}")
if not ok:
    out("RAM mismatch, not jumping")
    sys.exit(4)

# 5. boot
s.write(f"jump {ADDR:08x}\r".encode())
out("jumped; boot log follows")
end = time.time() + 240
while time.time() < end:
    b = s.read(4096)
    if b:
        t = b.decode(errors="replace")
        print(t, end="", flush=True)
        logf.write(t)
        logf.flush()
out("done, serial port released")
s.close()
