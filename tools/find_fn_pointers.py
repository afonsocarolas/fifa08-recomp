"""Find function pointers (vtables, callback tables) the codegen has not registered.

Decrypts and decompresses default.xex (retail key, basic compression), scans
everything outside the code section for big-endian words that point into code,
keeps those that land where a function can start, and drops the ones the
generated function table already has.

Usage: py -I tools/find_fn_pointers.py <default.xex> <generated/default/<name>_init.cpp>
           [--known 0xADDR,...] [--out new.toml]

AES runs through .NET (PowerShell), so no Python crypto package is needed.
"""
import argparse
import os
import re
import struct
import subprocess
import tempfile

RETAIL_KEY = bytes.fromhex("20B185A59D28FDC340583FBB0896BF91")
KEY_FILE_FORMAT = 0x000003FF
KEY_IMAGE_BASE = 0x00010201

BLR = 0x4E800020
BCTR = 0x4E800420


def aes_cbc_decrypt(key, data):
    """AES-128-CBC, zero IV, no padding, via .NET."""
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, "in.bin"), os.path.join(tmp, "out.bin")
        open(src, "wb").write(data)
        ps = (
            "$a=[Security.Cryptography.Aes]::Create();$a.Mode='CBC';$a.Padding='None';"
            f"$a.Key=[Convert]::FromHexString('{key.hex()}');$a.IV=[byte[]]::new(16);"
            f"$d=$a.CreateDecryptor();$b=[IO.File]::ReadAllBytes('{src}');"
            f"[IO.File]::WriteAllBytes('{dst}',$d.TransformFinalBlock($b,0,$b.Length))"
        )
        # FromHexString needs .NET 5+, so use pwsh when present, else build bytes by hand.
        shell = "pwsh" if subprocess.run(["where", "pwsh"], capture_output=True).returncode == 0 else None
        if shell is None:
            ps = ps.replace(f"[Convert]::FromHexString('{key.hex()}')",
                            "[byte[]](" + ",".join(str(b) for b in key) + ")")
            shell = "powershell"
        subprocess.run([shell, "-NoProfile", "-Command", ps], check=True)
        return open(dst, "rb").read()


def load_image(path):
    xex = open(path, "rb").read()
    if xex[:4] != b"XEX2":
        raise SystemExit("not an XEX2 file")
    _, header_size, _, sec_off, count = struct.unpack_from(">IIIII", xex, 4)
    headers = dict(struct.unpack_from(">II", xex, 24 + i * 8) for i in range(count))

    base = headers[KEY_IMAGE_BASE]
    ffi = headers[KEY_FILE_FORMAT]
    info_size, encryption, compression = struct.unpack_from(">IHH", xex, ffi)
    if compression != 1:
        raise SystemExit(f"compression type {compression} not supported (only basic)")

    payload = xex[header_size:]
    if encryption == 1:
        session_key = aes_cbc_decrypt(RETAIL_KEY, xex[sec_off + 0x150: sec_off + 0x160])
        payload = aes_cbc_decrypt(session_key, payload[: len(payload) // 16 * 16])

    image = bytearray()
    pos = 0
    for i in range((info_size - 8) // 8):
        data_size, zero_size = struct.unpack_from(">II", xex, ffi + 8 + i * 8)
        image += payload[pos: pos + data_size]
        image += bytes(zero_size)
        pos += data_size
    if image[:2] != b"MZ":
        raise SystemExit("decrypted image has no PE header; wrong key or format")
    return base, bytes(image)


def pe_sections(image):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    nsec = struct.unpack_from("<H", image, pe + 6)[0]
    opt_size = struct.unpack_from("<H", image, pe + 20)[0]
    sec = pe + 24 + opt_size
    out = []
    for i in range(nsec):
        name, vsize, va, rawsize, raw = struct.unpack_from("<8sIIII", image, sec + i * 40)
        flags = struct.unpack_from("<I", image, sec + i * 40 + 36)[0]
        out.append((name.rstrip(b"\0").decode(), va, max(vsize, rawsize), flags))
    return out


def registered(init_cpp):
    text = open(init_cpp, encoding="utf-8", errors="replace").read()
    return {int(m, 16) for m in re.findall(r"\{\s*0x([0-9A-Fa-f]{8}),\s*\w+\s*\}", text)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xex")
    ap.add_argument("init_cpp")
    ap.add_argument("--known", default="", help="comma-separated addresses that must be found")
    ap.add_argument("--out", help="write new [functions] entries to this TOML file")
    args = ap.parse_args()

    base, image = load_image(args.xex)
    sections = pe_sections(image)
    code = [(base + va, base + va + size) for name, va, size, flags in sections if flags & 0x20]
    print("sections:", ", ".join(f"{n} {base + va:08X}+{s:X}" for n, va, s, _ in sections))

    def in_code(a):
        return any(lo <= a < hi for lo, hi in code)

    def word(a):
        return struct.unpack_from(">I", image, a - base)[0]

    def can_start_function(a):
        if a & 3 or not in_code(a) or word(a) == 0:
            return False
        prev = word(a - 4)
        is_b = (prev >> 26) == 18 and (prev & 3) == 0
        return prev in (BLR, BCTR, 0) or is_b

    known_funcs = registered(args.init_cpp)
    targets, refs = set(), {}
    for name, va, size, flags in sections:
        if flags & 0x20:
            continue  # pointers inside code are jump tables / literals, skip
        for off in range(va, min(va + size, len(image)) - 3, 4):
            v = struct.unpack_from(">I", image, off)[0]
            if can_start_function(v):
                targets.add(v)
                refs.setdefault(v, base + off)
    found = targets - known_funcs

    # .pdata: (begin, packed) per function; length in words is bits 8..29 of packed.
    pdata = [(n, base + va, size) for n, va, size, _ in sections if n == ".pdata"]
    pdata_ranges = []
    for _, lo, size in pdata:
        for off in range(lo - base, lo - base + size - 7, 8):
            begin, packed = struct.unpack_from(">II", image, off)
            if begin:
                pdata_ranges.append((begin, begin + ((packed >> 8) & 0x3FFFFF) * 4))
    pdata_ranges.sort()
    pdata_starts = {lo for lo, _ in pdata_ranges}

    def inside_pdata_function(a):
        import bisect
        i = bisect.bisect_right(pdata_ranges, (a, 0xFFFFFFFF)) - 1
        return i >= 0 and pdata_ranges[i][0] < a < pdata_ranges[i][1]

    rejected = {a for a in found if inside_pdata_function(a)}
    found -= rejected

    print(f"{len(known_funcs)} functions registered, {len(targets)} pointer targets, "
          f"{len(found) + len(rejected)} of them unregistered")
    print(f".pdata: {len(pdata_ranges)} functions; dropped {len(rejected)} candidates inside one; "
          f"{len(found & pdata_starts)} of the {len(found)} kept are .pdata function starts")
    if args.known:
        # Addresses found by crashes: the scan alone (ignoring registration) should see them.
        want = [int(x, 16) for x in args.known.split(",") if x]
        hit = [a for a in want if a in targets]
        print(f"known crash addresses the scan finds: {len(hit)}/{len(want)}")
        for a in want:
            if a not in hit:
                print(f"  missed {a:08X} (prev word {word(a - 4):08X})")
    if args.out:
        with open(args.out, "w") as f:
            f.write("# Function pointer targets found in data sections by tools/find_fn_pointers.py\n")
            for a in sorted(found):
                f.write(f'0x{a:08X} = {{ name = "sub_{a:08X}" }}  # referenced at 0x{refs[a]:08X}\n')
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
