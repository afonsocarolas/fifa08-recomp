"""Read Xbox 360 guest memory from a running process (our port or Xenia).

Both map guest virtual memory at host 0x100000000, so guest address A lives at
host 0x100000000 + A.

Usage: py -I tools/guest_mem.py <process name> find-u32 <hex,hex,...>
       py -I tools/guest_mem.py <process name> dump <guest hex addr> <bytes> <out.bin>
"""
import ctypes
import ctypes.wintypes as wt
import struct
import subprocess
import sys

HOST_BASE = 0x100000000
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000

k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_uint64), ("AllocationBase", ctypes.c_uint64),
                ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_uint64),
                ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]


k32.OpenProcess.restype = wt.HANDLE
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_uint64, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]


def open_process(name):
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    pids = [int(l.split('","')[1]) for l in out.splitlines() if l.startswith('"')]
    if not pids:
        raise SystemExit(f"{name} not running")
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pids[0])
    if not h:
        raise SystemExit(f"OpenProcess failed: {ctypes.get_last_error()}")
    return h


def regions(h, lo=0x40000000, hi=0x100000000):
    """Committed guest ranges [lo, hi) as (guest_addr, size)."""
    addr = HOST_BASE + lo
    end = HOST_BASE + hi
    mbi = MBI()
    while addr < end and k32.VirtualQueryEx(h, addr, ctypes.byref(mbi), ctypes.sizeof(mbi)):
        size = mbi.RegionSize - (addr - mbi.BaseAddress)
        if mbi.State == MEM_COMMIT and mbi.Protect not in (0x01, 0x100):  # skip NOACCESS/GUARD
            yield addr - HOST_BASE, min(size, end - addr)
        addr += size


def read(h, guest, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(h, HOST_BASE + guest, buf, size, ctypes.byref(got)):
        return b""
    return buf.raw[: got.value]


def find_bytes(h, needle, lo=0x40000000, hi=0x100000000, limit=20):
    hits = []
    for base, size in regions(h, lo, hi):
        for off in range(0, size, 1 << 24):
            chunk = read(h, base + off, min(1 << 24, size - off) + len(needle))
            i = chunk.find(needle)
            while i >= 0:
                hits.append(base + off + i)
                if len(hits) >= limit:
                    return hits
                i = chunk.find(needle, i + 1)
    return hits


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    h = open_process(sys.argv[1])
    if sys.argv[2] == "find-u32":
        words = [int(x, 16) for x in sys.argv[3].split(",")]
        for a in find_bytes(h, struct.pack(f">{len(words)}I", *words)):
            print(f"{a:08X}")
    elif sys.argv[2] == "dump":
        data = read(h, int(sys.argv[3], 16), int(sys.argv[4]))
        open(sys.argv[5], "wb").write(data)
        print(f"{len(data)} bytes")
