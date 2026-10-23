"""Extract an Xbox 360 disc image (XDVDFS / XGD) to a folder.

Usage: py -I tools/xiso_extract.py <image.iso> <out_dir> [--list]

Handles both full disc dumps (game partition at a fixed offset) and
game-partition-only images. Read-only on the image.
"""
import os
import struct
import sys

SECTOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
# Game partition offsets: game-only image, XGD1, XGD2, XGD3
PARTITION_OFFSETS = (0, 0x18300000, 0xFD90000, 0x2080000)
ATTR_DIRECTORY = 0x10


def find_partition(f):
    for base in PARTITION_OFFSETS:
        f.seek(base + 32 * SECTOR)
        if f.read(len(MAGIC)) == MAGIC:
            return base
    raise SystemExit("No XDVDFS volume descriptor found; not an Xbox disc image?")


def read_dir(f, base, sector, size):
    """Return [(name, start_sector, file_size, is_dir)] for one directory table."""
    f.seek(base + sector * SECTOR)
    table = f.read(size)
    entries, seen = [], set()

    def walk(off):
        if off in seen or off + 14 > len(table):
            return
        seen.add(off)
        left, right, start, fsize, attr, nlen = struct.unpack_from("<HHIIBB", table, off)
        if left == 0xFFFF and right == 0xFFFF and start == 0xFFFFFFFF:
            return  # padding
        name = table[off + 14: off + 14 + nlen].decode("ascii", "replace")
        entries.append((name, start, fsize, bool(attr & ATTR_DIRECTORY)))
        if left:
            walk(left * 4)
        if right:
            walk(right * 4)

    if size:
        walk(0)
    return entries


def safe_join(root, rel):
    path = os.path.normpath(os.path.join(root, rel))
    if os.path.commonpath([os.path.abspath(root), os.path.abspath(path)]) != os.path.abspath(root):
        raise SystemExit(f"Refusing path outside output folder: {rel}")
    return path


def extract(image, out_dir, list_only=False):
    with open(image, "rb") as f:
        base = find_partition(f)
        f.seek(base + 32 * SECTOR + len(MAGIC))
        root_sector, root_size = struct.unpack("<II", f.read(8))
        print(f"partition offset 0x{base:X}, root dir sector {root_sector}, size {root_size}")

        total_files = total_bytes = 0
        stack = [("", root_sector, root_size)]
        while stack:
            rel_dir, sector, size = stack.pop()
            for name, start, fsize, is_dir in read_dir(f, base, sector, size):
                rel = os.path.join(rel_dir, name)
                if is_dir:
                    stack.append((rel, start, fsize))
                    if not list_only:
                        os.makedirs(safe_join(out_dir, rel), exist_ok=True)
                    continue
                total_files += 1
                total_bytes += fsize
                if list_only:
                    print(f"{fsize:>12}  {rel}")
                    continue
                dest = safe_join(out_dir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                f.seek(base + start * SECTOR)
                remaining = fsize
                with open(dest, "wb") as out:
                    while remaining:
                        chunk = f.read(min(remaining, 1 << 22))
                        if not chunk:
                            raise SystemExit(f"Image truncated while reading {rel}")
                        out.write(chunk)
                        remaining -= len(chunk)
        print(f"{total_files} files, {total_bytes / 2**30:.2f} GiB")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--list"]
    if len(args) != 2:
        raise SystemExit(__doc__)
    extract(args[0], args[1], list_only="--list" in sys.argv)
