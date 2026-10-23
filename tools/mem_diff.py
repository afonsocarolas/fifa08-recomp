"""Diff a guest memory range between two dumps (same guest addresses).

Usage:
  py -I tools/guest_mem.py fifa08.exe dump BC600000 2097152 port.bin
  py -I tools/guest_mem.py xenia_canary.exe dump BC600000 2097152 xenia.bin
  py -I tools/mem_diff.py port.bin xenia.bin BC600000 [--floats]

Prints differing 16-byte lines. With --floats, only lines where both sides hold
plausible floats (|x| < 1e6, not tiny denormal-like) that differ by more than 1%.
"""
import math
import struct
import sys


def plausible(v):
    return math.isfinite(v) and (v == 0 or 1e-6 < abs(v) < 1e6)


def main(a_path, b_path, base, floats):
    a, b = open(a_path, "rb").read(), open(b_path, "rb").read()
    n = min(len(a), len(b))
    shown = 0
    for off in range(0, n - 15, 16):
        la, lb = a[off:off + 16], b[off:off + 16]
        if la == lb:
            continue
        if floats:
            fa, fb = struct.unpack(">4f", la), struct.unpack(">4f", lb)
            if not all(plausible(x) for x in fa + fb):
                continue
            if all(abs(x - y) <= 0.01 * max(abs(x), abs(y), 1e-3) for x, y in zip(fa, fb)):
                continue
            print(f"{base + off:08X}  port {' '.join(f'{x:10.4f}' for x in fa)}   xenia {' '.join(f'{x:10.4f}' for x in fb)}")
        else:
            print(f"{base + off:08X}  {la.hex(' ', 4)}  |  {lb.hex(' ', 4)}")
        shown += 1
        if shown >= 400:
            print("...")
            break
    print(f"{sum(1 for o in range(0, n - 15, 16) if a[o:o+16] != b[o:o+16])} differing lines of {n // 16}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3], 16), "--floats" in sys.argv)
