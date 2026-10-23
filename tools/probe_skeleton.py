"""Explore a skeleton object in a running process: print its pointer fields and
the pointer fields of what they point to, looking for 137-entry bone arrays.

Usage: py -I tools/probe_skeleton.py <process> <skeleton guest hex addr>
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guest_mem import open_process, read  # noqa: E402


def is_ptr(v):
    return 0x40000000 <= v < 0x90000000 or 0xA0000000 <= v < 0x100000000


def main(proc, addr):
    h = open_process(proc)
    root = read(h, addr, 0x80)
    print(f"skeleton {addr:08X}")
    for off in range(0, len(root), 4):
        v = struct.unpack_from(">I", root, off)[0]
        if not is_ptr(v):
            continue
        sub = read(h, v, 0x60)
        words = [struct.unpack_from(">I", sub, o)[0] for o in range(0, len(sub), 4)]
        shorts = [struct.unpack_from(">H", sub, o)[0] for o in range(0, 16, 2)]
        print(f" +{off:02X} -> {v:08X}  u16[0..7]={shorts}")
        print("      " + " ".join(f"{w:08X}" for w in words[:24]))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2], 16))
