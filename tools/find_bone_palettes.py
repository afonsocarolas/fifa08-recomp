"""Find bone matrix palettes in a running process and measure the wrist angles.

Looks for runs of >= N consecutive 4x4 big-endian float matrices whose 4th column
is (0, 0, 0, 1) (row-major, translation in row 3), then for each run prints the
angle between the forearm and hand bone orientations.

Usage: py -I tools/find_bone_palettes.py <process> [N=137]
"""
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guest_mem import open_process, read, regions  # noqa: E402

LAYOUTS = {
    # row-major, translation in row 3: 4th column is (0, 0, 0, 1)
    "rows": rb".{12}\x00\x00\x00\x00.{12}\x00\x00\x00\x00.{12}\x00\x00\x00\x00.{12}\x3f\x80\x00\x00",
    # column-major, translation in column 3: 4th row is (0, 0, 0, 1)
    "cols": rb".{48}\x00{12}\x3f\x80\x00\x00",
}
MAT = LAYOUTS[os.environ.get("PALETTE_LAYOUT", "rows")]
L_FOREARM, L_HAND, R_FOREARM, R_HAND = 0x3E, 0x41, 0x5D, 0x60
L_INDEX1, R_INDEX1 = 0x43, 0x62


def rows(m):
    if os.environ.get("PALETTE_LAYOUT") == "cols":  # rotation is the upper-left 3x3, transposed
        return [[m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]]]
    return [m[0:3], m[4:7], m[8:11]]


def angle(a, b):
    """Rotation angle (degrees) between two 3x3 orientations given as rows."""
    ra, rb = rows(a), rows(b)
    # trace of ra * rb^T
    tr = sum(ra[i][k] * rb[i][k] for i in range(3) for k in range(3))
    c = max(-1.0, min(1.0, (tr - 1) / 2))
    return math.degrees(math.acos(c))


def unit(m):
    return all(abs(math.sqrt(sum(x * x for x in r)) - 1) < 0.05 for r in rows(m))


def main(proc, n):
    h = open_process(proc)
    rx = re.compile(b"(?:" + MAT + b"){%d,}" % n, re.S)
    found = 0
    # Virtual heaps plus the first physical mirror (0xA0000000..0xBFFFFFFF);
    # the 0xC0/0xE0 mirrors repeat the same memory.
    for base, size in regions(h, 0x40000000, 0xC0000000):
        step = 1 << 24
        for off in range(0, size, step):
            chunk = read(h, base + off, min(step + 64 * n, size - off))
            for m in rx.finditer(chunk):
                start = m.start()
                if start % 16:
                    continue
                count = (m.end() - start) // 64
                if count <= R_INDEX1:
                    continue  # too short to hold the hand bones
                mats = [struct.unpack_from(">16f", chunk, start + i * 64) for i in range(count)]
                if not all(unit(x) for x in mats[:n]):
                    continue
                addr = base + off + start
                found += 1
                print(f"{addr:08X} x{count}  wrist L {angle(mats[L_FOREARM], mats[L_HAND]):6.1f}  "
                      f"R {angle(mats[R_FOREARM], mats[R_HAND]):6.1f}   "
                      f"finger L {angle(mats[L_HAND], mats[L_INDEX1]):6.1f}  R {angle(mats[R_HAND], mats[R_INDEX1]):6.1f}")
    print(f"{found} palettes")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 137)
