"""Print parent->child angles along the arm, hand and finger chains of bone palettes.

Usage: py -I tools/hand_chain.py <process> <palette hex addr>[,<addr>...]

For skinning matrices (current pose x inverse bind pose) a bone that is not
animated relative to its parent has the same matrix as the parent: angle 0.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from find_bone_palettes import angle  # noqa: E402
from guest_mem import open_process, read  # noqa: E402

# (label, chain of bone indices) from the FIFA 08 player skeleton
CHAINS = {
    "L arm":    [0x3C, 0x3D, 0x3E, 0x3F, 0x40, 0x41],
    "L index":  [0x41, 0x42, 0x43, 0x44, 0x45],
    "L thumb":  [0x41, 0x56, 0x57, 0x58],
    "R arm":    [0x5B, 0x5C, 0x5D, 0x5E, 0x5F, 0x60],
    "R index":  [0x60, 0x61, 0x62, 0x63, 0x64],
    "R thumb":  [0x60, 0x75, 0x76, 0x77],
    "L leg":    [0x79, 0x7A, 0x7B],
}


def main(proc, addrs):
    h = open_process(proc)
    for a in addrs:
        data = read(h, a, 137 * 64)
        m = [struct.unpack_from(">16f", data, i * 64) for i in range(137)]
        print(f"palette {a:08X}")
        for label, chain in CHAINS.items():
            steps = "  ".join(f"{angle(m[p], m[c]):5.1f}" for p, c in zip(chain, chain[1:]))
            print(f"  {label:8s} {steps}")


if __name__ == "__main__":
    main(sys.argv[1], [int(x, 16) for x in sys.argv[2].split(",")])
