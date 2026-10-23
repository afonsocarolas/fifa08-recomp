"""Search the decrypted default.xex image for strings and the code that loads their address.

Usage: py -I tools/xex_strings.py <default.xex> <generated/default dir> <regex>

Prints each matching ASCII string with its guest address, then the generated
functions whose `lis`/`addi` pair builds that address.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from find_fn_pointers import load_image  # noqa: E402


def main(xex, gen_dir, pattern):
    base, image = load_image(xex)
    rx = re.compile(pattern.encode(), re.I)
    hits = []
    for m in re.finditer(rb"[\x20-\x7e]{4,}", image):
        if rx.search(m.group()):
            hits.append((base + m.start(), m.group().decode()))
    for addr, text in hits[:80]:
        print(f"{addr:08X}  {text}")
    print(f"{len(hits)} strings")

    # lis rX,HI / addi rY,rX,LO  ->  HI<<16 + signed LO
    want = {a for a, _ in hits}
    lis_re = re.compile(r"// lis (r\d+),(-?\d+)")
    addi_re = re.compile(r"// addi (r\d+),(r\d+),(-?\d+)")
    func_re = re.compile(r"DEFINE_REX_FUNC\((\w+)\)")
    refs = {}
    for name in sorted(os.listdir(gen_dir)):
        if not name.endswith(".cpp"):
            continue
        func, his = None, {}
        for line in open(os.path.join(gen_dir, name), encoding="utf-8", errors="replace"):
            if (m := func_re.search(line)):
                func, his = m.group(1), {}
            elif (m := lis_re.search(line)):
                his[m.group(1)] = (int(m.group(2)) & 0xFFFF) << 16
            elif (m := addi_re.search(line)) and m.group(2) in his:
                addr = (his[m.group(2)] + int(m.group(3))) & 0xFFFFFFFF
                if addr in want:
                    refs.setdefault(addr, set()).add(func)
    for addr, text in hits:
        if addr in refs:
            print(f"{addr:08X} {text!r:40s} used by {', '.join(sorted(refs[addr]))}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
