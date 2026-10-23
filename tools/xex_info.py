"""Print the identifying fields of an Xbox 360 XEX2 executable.

Usage: py -I tools/xex_info.py game/assets/default.xex
"""
import hashlib
import struct
import sys

KEY_ENTRY_POINT = 0x00010100
KEY_IMAGE_BASE = 0x00010201
KEY_ORIGINAL_PE_NAME = 0x000183FF
KEY_FILE_FORMAT = 0x000003FF
KEY_EXECUTION_INFO = 0x00040006

COMPRESSION = {0: "none", 1: "basic", 2: "normal (LZX)", 3: "delta"}
ENCRYPTION = {0: "none", 1: "normal"}


def version_str(v):
    return f"{v >> 28}.{(v >> 24) & 0xF}.{(v >> 8) & 0xFFFF}.{v & 0xFF}"


def main(path):
    data = open(path, "rb").read()
    if data[:4] != b"XEX2":
        raise SystemExit("Not an XEX2 file")
    flags, pe_offset, _, sec_offset, count = struct.unpack_from(">IIIII", data, 4)
    headers = {}
    for i in range(count):
        key, value = struct.unpack_from(">II", data, 24 + i * 8)
        headers[key] = value

    print(f"file           {path}")
    print(f"size           {len(data)} bytes")
    print(f"sha256         {hashlib.sha256(data).hexdigest().upper()}")
    print(f"module flags   0x{flags:08X}")

    if KEY_EXECUTION_INFO in headers:
        off = headers[KEY_EXECUTION_INFO]
        media, ver, base_ver, title, plat, exe_type, disc, discs, save = struct.unpack_from(
            ">IIIIBBBBI", data, off)
        print(f"title id       {title:08X}")
        print(f"media id       {media:08X}")
        print(f"version        {version_str(ver)}  (base {version_str(base_ver)})")
        print(f"disc           {disc} of {discs}")
    if KEY_ORIGINAL_PE_NAME in headers:
        off = headers[KEY_ORIGINAL_PE_NAME]
        size = struct.unpack_from(">I", data, off)[0]
        print(f"original name  {data[off + 4: off + size].split(b'\0')[0].decode('ascii', 'replace')}")
    if KEY_IMAGE_BASE in headers:
        print(f"image base     0x{headers[KEY_IMAGE_BASE]:08X}")
    if KEY_ENTRY_POINT in headers:
        print(f"entry point    0x{headers[KEY_ENTRY_POINT]:08X}")
    if KEY_FILE_FORMAT in headers:
        enc, comp = struct.unpack_from(">HH", data, headers[KEY_FILE_FORMAT] + 4)
        print(f"encryption     {ENCRYPTION.get(enc, enc)}")
        print(f"compression    {COMPRESSION.get(comp, comp)}")

    sec_image_size = struct.unpack_from(">I", data, sec_offset + 4)[0]
    print(f"image size     0x{sec_image_size:X} ({sec_image_size / 2**20:.1f} MiB in memory)")
    print(f"pe data at     0x{pe_offset:X}, {count} optional headers")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
