"""Sample FIFA 08's per-bone pose buffer from a running process and compare runs.

The pose buffer (input of sub_829510E8, at the same guest address in our port and
in Xenia) holds 48 bytes per bone: scale +0, translation +16, rotation quaternion
+32 (x, y, z, w; big-endian floats).

Usage:
  py -I tools/pose_sample.py sample <process> <out.bin> [addr=BDB00980] [bones=137] [count=100] [interval=0.2]
  py -I tools/pose_sample.py compare <port.bin> <xenia.bin> [bones=137]
  py -I tools/pose_sample.py region <process> <out.bin> <addr> <bytes> [count=100] [interval=0.2]
  py -I tools/pose_sample.py chains <port.bin> <xenia.bin> <region addr> <palette addr>

compare prints, per bone, the angle between the two runs' average rotations and
each run's average rotation size, largest difference first.
region samples raw bytes; chains reads a 137 x 4x4 matrix palette (row-major,
big-endian) out of two region samples and compares the average parent->child
angles along the arm and hand chains.
"""
import math
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guest_mem import open_process, read  # noqa: E402

STRIDE = 48

# Bone names for the 137-bone skeleton (from the rig channel log); only the ones
# near the arms are needed to read the output.
NAMES = {0x3B: "LeftShoulder", 0x3C: "LeftArm", 0x3D: "LeftArmTwist", 0x3E: "LeftForeArm",
         0x3F: "LeftForeArmTwist", 0x40: "LeftForeArmTwist1", 0x41: "LeftHand",
         0x5A: "RightShoulder", 0x5B: "RightArm", 0x5C: "RightArmTwist", 0x5D: "RightForeArm",
         0x5E: "RightForeArmTwist", 0x5F: "RightForeArmTwist1", 0x60: "RightHand"}


def sample(proc, out, addr=0xBDB00980, bones=137, count=100, interval=0.2):
    h = open_process(proc)
    size = bones * STRIDE
    with open(out, "wb") as f:
        got = 0
        while got < count:
            data = read(h, addr, size)
            if len(data) == size:
                f.write(data)
                got += 1
            time.sleep(interval)
    print(f"{got} samples of {bones} bones -> {out}")


def quats(path, bones):
    data = open(path, "rb").read()
    size = bones * STRIDE
    frames = []
    for off in range(0, len(data) - size + 1, size):
        frame = []
        for b in range(bones):
            q = struct.unpack_from(">4f", data, off + b * STRIDE + 32)
            frame.append(q)
        frames.append(frame)
    return frames


def mean_quat(qs):
    ref = qs[0]
    acc = [0.0] * 4
    for q in qs:
        s = 1.0 if sum(a * b for a, b in zip(q, ref)) >= 0 else -1.0
        for i in range(4):
            acc[i] += s * q[i]
    n = math.sqrt(sum(a * a for a in acc)) or 1.0
    return [a / n for a in acc]


def angle(q):
    return math.degrees(2 * math.acos(min(1.0, abs(q[3]))))


def between(a, b):
    d = abs(sum(x * y for x, y in zip(a, b)))
    return math.degrees(2 * math.acos(min(1.0, d)))


def compare(a_path, b_path, bones=137):
    a, b = quats(a_path, bones), quats(b_path, bones)
    rows = []
    for i in range(bones):
        qa = mean_quat([f[i] for f in a])
        qb = mean_quat([f[i] for f in b])
        bad = sum(1 for f in a + b if abs(math.sqrt(sum(x * x for x in f[i])) - 1) > 0.01)
        rows.append((between(qa, qb), i, angle(qa), angle(qb), qa, qb, bad))
    rows.sort(reverse=True)
    print(f"{len(a)} vs {len(b)} samples")
    print(" diff  bone                     |avg rot| port / xenia   avg quat port              avg quat xenia")
    for d, i, ra, rb, qa, qb, bad in rows[:30]:
        name = NAMES.get(i, "")
        fa = " ".join(f"{x:6.3f}" for x in qa)
        fb = " ".join(f"{x:6.3f}" for x in qb)
        flag = f"  ({bad} non-unit)" if bad else ""
        print(f"{d:5.1f}  {i:02X} {name:20} {ra:6.1f} / {rb:6.1f}   {fa}   {fb}{flag}")


def region(proc, out, addr, size, count=100, interval=0.2):
    h = open_process(proc)
    with open(out, "wb") as f:
        got = 0
        while got < count:
            data = read(h, addr, size)
            if len(data) == size:
                f.write(struct.pack("<II", addr, size) + data)
                got += 1
            time.sleep(interval)
    print(f"{got} samples of {size} bytes at {addr:08X} -> {out}")


def region_frames(path):
    data = open(path, "rb").read()
    frames, off = [], 0
    while off + 8 <= len(data):
        addr, size = struct.unpack_from("<II", data, off)
        frames.append((addr, data[off + 8:off + 8 + size]))
        off += 8 + size
    return frames


def rot_angle(a, b):
    """Angle between the 3x3 rotations (rows) of two row-major 4x4 matrices."""
    ra = [a[0:3], a[4:7], a[8:11]]
    rb = [b[0:3], b[4:7], b[8:11]]
    norm = lambda r: [x / (math.sqrt(sum(y * y for y in r)) or 1) for x in r]
    ra, rb = [norm(r) for r in ra], [norm(r) for r in rb]
    tr = sum(ra[i][k] * rb[i][k] for i in range(3) for k in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1) / 2))))


CHAINS = {
    "L arm": [0x3B, 0x3C, 0x3D, 0x3E, 0x3F, 0x40, 0x41, 0x43, 0x44],
    "R arm": [0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F, 0x60, 0x62, 0x63],
}


def chains(a_path, b_path, palette):
    result = {}
    for label, path in (("port", a_path), ("xenia", b_path)):
        sums = {}
        frames = region_frames(path)
        for base, data in frames:
            off = palette - base
            mats = [struct.unpack_from(">16f", data, off + i * 64) for i in range(137)]
            for chain in CHAINS.values():
                for p, c in zip(chain, chain[1:]):
                    sums.setdefault((p, c), []).append(rot_angle(mats[p], mats[c]))
        result[label] = {k: (sum(v) / len(v), min(v), max(v)) for k, v in sums.items()}
    print(f"palette {palette:08X}: average (min..max) angle between bone and next bone in chain")
    for chain in CHAINS.values():
        for p, c in zip(chain, chain[1:]):
            a, b = result["port"][(p, c)], result["xenia"][(p, c)]
            mark = "  <--" if abs(a[0] - b[0]) > 5 else ""
            print(f"  {NAMES.get(p, hex(p)):>18} -> {NAMES.get(c, hex(c)):18} "
                  f"port {a[0]:6.1f} ({a[1]:5.1f}..{a[2]:5.1f})   xenia {b[0]:6.1f} ({b[1]:5.1f}..{b[2]:5.1f}){mark}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "sample":
        args = sys.argv[2:]
        sample(args[0], args[1],
               int(args[2], 16) if len(args) > 2 else 0xBDB00980,
               int(args[3]) if len(args) > 3 else 137,
               int(args[4]) if len(args) > 4 else 100,
               float(args[5]) if len(args) > 5 else 0.2)
    elif cmd == "region":
        a = sys.argv[2:]
        region(a[0], a[1], int(a[2], 16), int(a[3]), int(a[4]) if len(a) > 4 else 100,
               float(a[5]) if len(a) > 5 else 0.2)
    elif cmd == "chains":
        chains(sys.argv[2], sys.argv[3], int(sys.argv[5], 16))
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 137)
