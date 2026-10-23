"""Generate randomized PPC instruction tests in the rexglue test format.

Expected results come from Python reference models of the PowerPC / VMX /
VMX128 semantics. Writes one fuzz_<insn>.s per instruction into <out dir>
(normally rexglue-sdk/tests/ppc/asm, which the ppc_tests target globs).

Usage: py -I tools/fuzz_ppc.py <out dir> [cases per insn=40] [seed=1]

Inputs avoid NaN, infinities and denormals: those have their own, documented
corner cases and are not what we are hunting. Float results are exact
references; a 1-2 ulp mismatch is a rounding detail (e.g. fused vs unfused
multiply-add), anything larger is a real semantic difference.
"""
import math
import os
import random
import struct
import sys
from fractions import Fraction

# ---------------------------------------------------------------- helpers

def f32(x):
    """Round a Python float (double) to the nearest float32 value."""
    return struct.unpack(">f", struct.pack(">f", x))[0]


def f32_bits(x):
    return struct.unpack(">I", struct.pack(">f", x))[0]


def bits_f32(u):
    return struct.unpack(">f", struct.pack(">I", u & 0xFFFFFFFF))[0]


def frac_to_double(fr):
    return float(fr)  # correctly rounded


def ftz32(x):
    """VMX non-Java mode: denormal results flush to zero (keep sign)."""
    if x != 0 and abs(x) < 1.1754943508222875e-38:
        return math.copysign(0.0, x)
    return x


def s32(u):
    u &= 0xFFFFFFFF
    return u - (1 << 32) if u & 0x80000000 else u


def sat(v, lo, hi):
    return max(lo, min(hi, v))


rng = random.Random()


def rand_f32(lo_exp=-20, hi_exp=20):
    edge = [0.0, -0.0, 1.0, -1.0, 0.5, 2.0, -2.0, 3.0, 1e10, -1e10, 1e-10]
    if rng.random() < 0.15:
        return f32(rng.choice(edge))
    m = rng.uniform(1.0, 2.0)
    e = rng.randint(lo_exp, hi_exp)
    s = -1.0 if rng.random() < 0.5 else 1.0
    return f32(s * m * 2.0 ** e)


def rand_f64(lo_exp=-40, hi_exp=40):
    edge = [0.0, -0.0, 1.0, -1.0, 0.5, 1e100, -1e-100]
    if rng.random() < 0.15:
        return rng.choice(edge)
    return (-1 if rng.random() < 0.5 else 1) * rng.uniform(1.0, 2.0) * 2.0 ** rng.randint(lo_exp, hi_exp)


def rand_u32():
    edge = [0, 1, 0x7F, 0x80, 0xFF, 0x7FFF, 0x8000, 0xFFFF, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]
    if rng.random() < 0.2:
        return rng.choice(edge)
    return rng.getrandbits(32)


def vec_f(n=4, **kw):
    return [f32_bits(rand_f32(**kw)) for _ in range(n)]


def vec_u():
    return [rand_u32() for _ in range(4)]


def fmt_vec(words):
    return "[" + ", ".join(f"{w & 0xFFFFFFFF:08X}" for w in words) + "]"


def fmt_f(x):
    return "None" if x is None else x.hex()

# ------------------------------------------------------- element helpers

def to_bytes(words):
    return b"".join(struct.pack(">I", w & 0xFFFFFFFF) for w in words)


def from_bytes(b):
    return [struct.unpack_from(">I", b, i)[0] for i in range(0, 16, 4)]


def elems(words, size, signed=False):
    b = to_bytes(words)
    fmt = {1: "b", 2: "h", 4: "i"}[size] if signed else {1: "B", 2: "H", 4: "I"}[size]
    return list(struct.unpack(f">{16 // size}{fmt}", b))


def pack_elems(vals, size):
    mask = (1 << (8 * size)) - 1
    fmt = {1: "B", 2: "H", 4: "I"}[size]
    return from_bytes(struct.pack(f">{16 // size}{fmt}", *[v & mask for v in vals]))


def fop(words_a, words_b, fn, words_c=None):
    out = []
    for i in range(4):
        a, b = bits_f32(words_a[i]), bits_f32(words_b[i])
        c = bits_f32(words_c[i]) if words_c else None
        out.append(f32_bits(ftz32(fn(a, b, c))))
    return out


def fused(a, b, c, sign=1, neg=False):
    """round_f32(a*b + sign*c), optionally negated, computed exactly."""
    r = Fraction(a) * Fraction(b) + sign * Fraction(c)
    if r == 0:
        v = 0.0 if not neg else -0.0
        return v
    v = f32(frac_to_double(r))
    return -v if neg else v

# ------------------------------------------------------- test case kinds

CASES = {}


def case(name):
    def deco(fn):
        CASES[name] = fn
        return fn
    return deco


def vtest(insn, ins, out, extra_out=()):
    """ins: list of (reg, words). out: (reg, words). extra_out: [(directive line)]."""
    lines = [f"  #_ REGISTER_IN {r} {fmt_vec(w)}" for r, w in ins]
    lines.append(f"  {insn}")
    lines.append("  blr")
    lines.append(f"  #_ REGISTER_OUT {out[0]} {fmt_vec(out[1])}")
    lines += list(extra_out)
    return lines


def ftest(insn, ins, out):
    lines = [f"  #_ REGISTER_IN {r} {fmt_f(v)}" for r, v in ins]
    lines.append(f"  {insn}")
    lines.append("  blr")
    lines.append(f"  #_ REGISTER_OUT {out[0]} {fmt_f(out[1])}")
    return lines


# --- scalar float (single precision results)
def scalar_single(name, fn, nin=2):
    @case(name)
    def gen():
        a, b, c = rand_f32(), rand_f32(), rand_f32()
        regs = [("f2", a), ("f3", b), ("f4", c)][:nin]
        args = ", ".join(r for r, _ in regs)
        return ftest(f"{name} f1, {args}", regs, ("f1", fn(a, b, c)))


scalar_single("fadds", lambda a, b, c: f32(a + b))
scalar_single("fsubs", lambda a, b, c: f32(a - b))
scalar_single("fmuls", lambda a, b, c: f32(a * b))
scalar_single("fdivs", lambda a, b, c: f32(a / b) if b != 0 else None)
scalar_single("fmsubs", lambda a, b, c: fused(a, b, c, -1), 3)
scalar_single("fnmsubs", lambda a, b, c: fused(a, b, c, -1, neg=True), 3)


@case("fsqrts")
def _():
    a = abs(rand_f32())
    return ftest("fsqrts f1, f2", [("f2", a)], ("f1", f32(math.sqrt(a))))


@case("frsp")
def _():
    a = rand_f64(-100, 100)
    return ftest("frsp f1, f2", [("f2", a)], ("f1", f32(a)))


@case("fneg")
def _():
    a = rand_f64()
    return ftest("fneg f1, f2", [("f2", a)], ("f1", -a))


def scalar_double(name, fn, nin=2):
    @case(name)
    def gen():
        a, b, c = rand_f64(), rand_f64(), rand_f64()
        regs = [("f2", a), ("f3", b), ("f4", c)][:nin]
        args = ", ".join(r for r, _ in regs)
        return ftest(f"{name} f1, {args}", regs, ("f1", fn(a, b, c)))


scalar_double("fsub", lambda a, b, c: a - b)
scalar_double("fdiv", lambda a, b, c: a / b if b != 0 else None)
scalar_double("fmsub", lambda a, b, c: frac_to_double(Fraction(a) * Fraction(b) - Fraction(c)), 3)
scalar_double("fnmsub", lambda a, b, c: -frac_to_double(Fraction(a) * Fraction(b) - Fraction(c)), 3)


@case("fcfid")
def _():
    n = rng.choice([0, 1, 7, 12345, rng.getrandbits(40), rng.getrandbits(62)])
    src = struct.unpack(">d", struct.pack(">q", n))[0]
    return ftest("fcfid f1, f2", [("f2", src)], ("f1", float(n)))


# --- vector float
@case("vmulfp128")
def _():
    a, b = vec_f(), vec_f()
    return vtest("vmulfp128 v6, v3, v4", [("v3", a), ("v4", b)], ("v6", fop(a, b, lambda x, y, z: f32(x * y))))


@case("vmaddfp128")
def _():
    a, b, d = vec_f(), vec_f(), vec_f()
    return vtest("vmaddfp128 v6, v3, v4, v6", [("v3", a), ("v4", b), ("v6", d)],
                 ("v6", fop(a, b, lambda x, y, z: fused(x, y, z), d)))


@case("vmaddcfp128")
def _():
    a, b, d = vec_f(), vec_f(), vec_f()
    # vD = vA * vD + vB
    return vtest("vmaddcfp128 v6, v3, v6, v4", [("v3", a), ("v4", b), ("v6", d)],
                 ("v6", fop(a, d, lambda x, y, z: fused(x, y, z), b)))


@case("vnmsubfp128")
def _():
    a, b, d = vec_f(), vec_f(), vec_f()
    return vtest("vnmsubfp128 v6, v3, v4, v6", [("v3", a), ("v4", b), ("v6", d)],
                 ("v6", fop(a, b, lambda x, y, z: fused(x, y, z, -1, neg=True), d)))


@case("vnmsubfp")
def _():
    a, c, b = vec_f(), vec_f(), vec_f()
    return vtest("vnmsubfp v6, v3, v4, v5", [("v3", a), ("v4", c), ("v5", b)],
                 ("v6", fop(a, c, lambda x, y, z: fused(x, y, z, -1, neg=True), b)))


@case("vcsxwfp128")
def _():
    a = vec_u()
    imm = rng.randint(0, 15)  # binutils encodes this field as signed (-16..15)
    res = [f32_bits(ftz32(f32(s32(w) / 2.0 ** imm))) for w in a]
    return vtest(f"vcsxwfp128 v6, v3, {imm}", [("v3", a)], ("v6", res))


@case("vcfux")
def _():
    a = vec_u()
    imm = rng.randint(0, 31)
    res = [f32_bits(ftz32(f32((w & 0xFFFFFFFF) / 2.0 ** imm))) for w in a]
    return vtest(f"vcfux v6, v3, {imm}", [("v3", a)], ("v6", res))


@case("vrfiz")
def _():
    a = vec_f(lo_exp=-3, hi_exp=25)
    return vtest("vrfiz v6, v3", [("v3", a)], ("v6", [f32_bits(math.copysign(float(math.trunc(bits_f32(w))), bits_f32(w))) for w in a]))


@case("vrfim")
def _():
    a = vec_f(lo_exp=-3, hi_exp=25)
    return vtest("vrfim v6, v3", [("v3", a)], ("v6", [f32_bits(math.copysign(float(math.floor(bits_f32(w))), bits_f32(w)) if bits_f32(w) >= 0 or math.floor(bits_f32(w)) != 0 else -0.0) for w in a]))


def vcmp_float(name, pred, dot):
    @case(name + ("." if dot else ""))
    def gen():
        a, b = vec_f(lo_exp=-2, hi_exp=2), vec_f(lo_exp=-2, hi_exp=2)
        for i in range(4):  # make some lanes equal
            if rng.random() < 0.3:
                b[i] = a[i]
        res = [0xFFFFFFFF if pred(bits_f32(x), bits_f32(y)) else 0 for x, y in zip(a, b)]
        extra = []
        if dot:
            cr6 = (8 if all(res) else 0) | (2 if not any(res) else 0)
            extra = [f"  #_ REGISTER_OUT cr 0x{cr6 << 4:08X}"]
        ins = [("v3", a), ("v4", b)]
        lines = vtest(f"{name}{'.' if dot else ''} v6, v3, v4", ins, ("v6", res), extra)
        if dot:
            lines.insert(0, "  #_ REGISTER_IN cr 0x00000000")
        return lines


for nm, p in (("vcmpgtfp", lambda x, y: x > y), ("vcmpgefp", lambda x, y: x >= y), ("vcmpeqfp", lambda x, y: x == y)):
    vcmp_float(nm, p, False)
    vcmp_float(nm, p, True)

# --- vector integer
def vint(name, size, fn, signed=False):
    @case(name)
    def gen():
        a, b = vec_u(), vec_u()
        ea, eb = elems(a, size, signed), elems(b, size, signed)
        res = pack_elems([fn(x, y) for x, y in zip(ea, eb)], size)
        return vtest(f"{name} v6, v3, v4", [("v3", a), ("v4", b)], ("v6", res))


@case("vsraw")
def _():
    a, b = vec_u(), vec_u()
    res = [(s32(x) >> (y & 31)) & 0xFFFFFFFF for x, y in zip(a, b)]
    return vtest("vsraw v6, v3, v4", [("v3", a), ("v4", b)], ("v6", res))


vint("vsrw", 4, lambda x, y: x >> (y & 31))
vint("vsrb", 1, lambda x, y: x >> (y & 7))
vint("vsububm", 1, lambda x, y: x - y)
vint("vaddubm", 1, lambda x, y: x + y)
vint("vadduwm", 4, lambda x, y: x + y)
vint("vaddubs", 1, lambda x, y: sat(x + y, 0, 255))
vint("vaddsbs", 1, lambda x, y: sat(x + y, -128, 127), signed=True)
vint("vaddsws", 4, lambda x, y: sat(x + y, -2**31, 2**31 - 1), signed=True)
vint("vsubsws", 4, lambda x, y: sat(x - y, -2**31, 2**31 - 1), signed=True)
vint("vnor", 4, lambda x, y: ~(x | y))
vint("vavgub", 1, lambda x, y: (x + y + 1) >> 1)
vint("vcmpequb", 1, lambda x, y: -1 if x == y else 0)
vint("vcmpequh", 2, lambda x, y: -1 if x == y else 0)
vint("vcmpequw", 4, lambda x, y: -1 if x == y else 0)
vint("vcmpgtub", 1, lambda x, y: -1 if x > y else 0)
vint("vcmpgtuh", 2, lambda x, y: -1 if x > y else 0)
vint("vcmpgtsh", 2, lambda x, y: -1 if x > y else 0, signed=True)
vint("vcmpgtsw", 4, lambda x, y: -1 if x > y else 0, signed=True)


def main(out_dir, n, seed):
    rng.seed(seed)
    os.makedirs(out_dir, exist_ok=True)
    total = 0
    for name, gen in CASES.items():
        stem = name.replace(".", "_dot")
        body = []
        made = 0
        while made < n:
            try:
                lines = gen()
            except (OverflowError, TypeError, ZeroDivisionError, ValueError):
                continue  # result not representable (float32 overflow) or undefined
            if any("None" in l for l in lines):
                continue  # reference undefined (e.g. divide by zero)
            body.append(f"test_fuzz_{stem}_{made}:")
            body += lines
            body.append("")
            made += 1
        open(os.path.join(out_dir, f"fuzz_{stem}.s"), "w", newline="\n").write("\n".join(body) + "\n")
        total += made
    print(f"{len(CASES)} instructions, {total} cases")


if __name__ == "__main__":
    out = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    main(out, n, seed)
