#pragma once

// Debug probes called from generated code (config/debug_hooks.toml).

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <string>

#include <rex/system/kernel_state.h>
#include <rex/logging.h>
#include <rex/ppc/context.h>

#include "write_watch.h"

namespace fifa08::dbg {

inline const uint8_t* Ptr(uint32_t addr) {
  if (addr < 0x10000) return nullptr;
  return REX_KERNEL_MEMORY()->TranslateVirtual<const uint8_t*>(addr);
}

inline uint32_t U32(uint32_t addr) {
  const uint8_t* p = Ptr(addr);
  if (!p) return 0xDEADBEEF;
  return (uint32_t(p[0]) << 24) | (uint32_t(p[1]) << 16) | (uint32_t(p[2]) << 8) | p[3];
}

}  // namespace fifa08::dbg

void Dbg_PosePalette(PPCRegister& r4, PPCRegister& r5, PPCRegister& r9, PPCRegister& r11) {
  static std::atomic<int> calls = 0;
  int n = ++calls;
  if (n < 2000 || n > 2040) return;  // a few frames, well after startup
  REXKRNL_INFO("[dbg] PosePalette #{} in={:08X} out={:08X} bones={} mask={:08X}", n, r11.u32, r5.u32, r9.u32,
               r4.u32);
}

// Vector elements in guest order (the host stores them reversed).
inline float El(const PPCVRegister& v, int i) { return v.f32[3 - i]; }

inline float F32(uint32_t addr) {
  uint32_t u = fifa08::dbg::U32(addr);
  float f;
  memcpy(&f, &u, 4);
  return f;
}

// Where Dbg_BoneQuat saw the left hand's quaternion stored (guest address).
inline std::atomic<uint32_t> g_hand_quat_addr = 0;

void Dbg_Memcpy(PPCRegister& r3, PPCRegister& r4, PPCRegister& r5) {
  uint32_t a = g_hand_quat_addr.load(std::memory_order_relaxed);
  if (!a || a < r4.u32 || a >= r4.u32 + r5.u32) return;
  static std::atomic<int> logged = 0;
  if (++logged > 6) return;
  REXKRNL_INFO("[dbg] memcpy dst={:08X} src={:08X} len={} -> hand quat now at {:08X}", r3.u32, r4.u32, r5.u32,
               r3.u32 + (a - r4.u32));
  // --watch_hook=copy: catch whoever reads the copied stream.
  if (logged == 3) fifa08::watch::ArmFromHook(r3.u32 + (a - r4.u32), 8, "copy");
}

std::string Mat(uint32_t addr) {
  std::string out;
  for (uint32_t off = 0; off < 64; off += 4) out += fmt::format(" {:.6g}", F32(addr + off));
  return out;
}

// Logs, for one frame of bones: the bone's matrix B (palette r31 + slot*64), the
// reference bone's matrix P (slot from the table at obj+32 -> +12), the inverse of P
// that the loop cached at r1+592, and the result rows at r1+240 (B x inverse(P)).
void Dbg_BoneQuat(PPCVRegister& v0, PPCRegister& r1, PPCRegister& r14, PPCRegister& r25) {
  static std::atomic<int> calls = 0;
  int n = ++calls;
  // --watch_hook: catch whoever reads the left hand's packed quaternion.
  if (n > 20000 && r14.u32 == 0x41) {
    fifa08::watch::ArmFromHook(r25.u32, 8, "stream");
    g_hand_quat_addr = r25.u32;
  }
  static std::atomic<int> hand_logged = 0;
  if ((r14.u32 == 0x41 || r14.u32 == 0x60) && n > 60000 && ++hand_logged <= 12)
    REXKRNL_INFO("[dbg] EncodeHand slot {:02X} q=({:.4f},{:.4f},{:.4f},{:.4f})", r14.u32, El(v0, 0), El(v0, 1),
                 El(v0, 2), El(v0, 3));
  if (n < 20000 || n > 20000 + 3 * 137) return;
  uint32_t sp = r1.u32;
  uint32_t palette = fifa08::dbg::U32(sp + 10420);
  uint32_t table = fifa08::dbg::U32(fifa08::dbg::U32(fifa08::dbg::U32(sp + 10404) + 32) + 12);
  uint32_t ref = fifa08::dbg::U32(table + r14.u32 * 4);
  REXKRNL_INFO("[dbg] BoneQuat {} ref {} q {:.6g} {:.6g} {:.6g} {:.6g} | B{} | P{} | I{} | R{}", r14.u32, ref,
               El(v0, 0), El(v0, 1), El(v0, 2), El(v0, 3), Mat(palette + r14.u32 * 64), Mat(palette + ref * 64),
               Mat(sp + 592 + ref * 64), Mat(sp + 240));
}

// Checks sub_826118E8's output against C = A x B computed here: the three texels
// at r3 must be the columns 0..2 of C (as rows). Logs a summary every 20000 calls
// and the first few mismatches with their inputs.
void Dbg_BoneTexel(PPCRegister& r3, PPCRegister& r4, PPCRegister& r5) {
  static std::atomic<int> calls = 0, bad = 0;
  static std::atomic<float> worst = 0;
  int n = ++calls;
  float a[16], b[16], out[12];
  for (int i = 0; i < 16; ++i) {
    a[i] = F32(r4.u32 + i * 4);
    b[i] = F32(r5.u32 + i * 4);
  }
  for (int i = 0; i < 12; ++i) out[i] = F32(r3.u32 + i * 4);
  a[15] = 1;  // the code adds B's translation row as is: A is affine
  float err = 0;
  for (int col = 0; col < 3; ++col)
    for (int row = 0; row < 4; ++row) {
      double c = 0;
      for (int k = 0; k < 4; ++k) c += double(a[row * 4 + k]) * b[k * 4 + col];
      float d = float(std::abs(c - out[col * 4 + row]) / std::max(1.0, std::abs(c)));
      err = std::max(err, d);
    }
  if (err > worst) worst = err;
  if (err > 1e-3f && ++bad <= 5) {
    std::string sa, sb, so;
    for (int i = 0; i < 16; ++i) sa += fmt::format(" {:.5g}", a[i]), sb += fmt::format(" {:.5g}", b[i]);
    for (int i = 0; i < 12; ++i) so += fmt::format(" {:.5g}", out[i]);
    REXKRNL_INFO("[dbg] BoneTexel MISMATCH err={:.4g} dst={:08X} A={:08X} B={:08X} | A{} | B{} | out{}", err,
                 r3.u32, r4.u32, r5.u32, sa, sb, so);
  }
  // Texture entries that differ from Xenia: row 11, slots 3..10 (x = 192 + 3 * slot).
  uint32_t off = r3.u32 - 0xF88C0000;
  static std::atomic<int> logged_rows = 0;
  if (off / 4096 == 11 && (off % 4096) / 16 >= 192 + 9 && (off % 4096) / 16 <= 192 + 30 && ++logged_rows <= 24)
    REXKRNL_INFO("[dbg] BoneTexelAddr slot {} dst={:08X} A={:08X} B={:08X} | A{} | B{}",
                 ((off % 4096) / 16 - 192) / 3, r3.u32, r4.u32, r5.u32, Mat(r4.u32), Mat(r5.u32));
  if (n % 20000 == 0) REXKRNL_INFO("[dbg] BoneTexel {} calls, {} mismatches, worst rel err {:.3g}", n, bad.load(), worst.load());
}

void Dbg_SkinArray(PPCRegister& r3, PPCRegister& r11, PPCRegister& r30, PPCRegister& r31, PPCRegister& r29) {
  static std::atomic<int> calls = 0;
  int n = ++calls;
  if (n > 40 && n % 500) return;
  REXKRNL_INFO("[dbg] SkinArray #{} array={:08X} fn={:08X} bind={:08X} count={} row={} col={}", n, r3.u32, r11.u32,
               r30.u32, fifa08::dbg::U32(r30.u32), r31.u32, r29.u32);
}

// Rebuilds the rotation rows from the decoder's quaternion and compares them with
// what the recompiled shuffles produced. Logs the first mismatches and a summary.
void Dbg_DecodeQuat(PPCVRegister& v0, PPCVRegister& v11, PPCVRegister& v12, PPCVRegister& v10, PPCVRegister& v4,
                    PPCVRegister& v3, PPCVRegister& v2, PPCRegister& r8, PPCRegister& r1) {
  static std::atomic<int> calls = 0, bad = 0, logged = 0;
  int n = ++calls;
  static std::atomic<int> sp_logged = 0;
  if (++sp_logged <= 4) {
    std::string c;
    for (uint32_t off = 152; off < 176; off += 4) c += fmt::format(" {:08X}", fifa08::dbg::U32(r1.u32 + off));
    REXKRNL_INFO("[dbg] DecodeQuat r1={:08X} (r1 & 15 = {}) words at r1+152..175:{}", r1.u32, r1.u32 & 15, c);
  }
  static std::atomic<int> hand_logged = 0;
  if ((r8.u32 == 115 || r8.u32 == 119) && n > 200000 && ++hand_logged <= 12)
    REXKRNL_INFO("[dbg] DecodeHand bone {} q=({:.4f},{:.4f},{:.4f},{:.4f})", r8.u32, El(v0, 0), El(v0, 1), El(v0, 2),
                 El(v0, 3));
  float x = El(v0, 0), y = El(v0, 1), z = El(v0, 2), w = El(v0, 3);
  // Standard unit-quaternion rotation matrix (row-vector convention).
  float r[3][3] = {{1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w)},
                   {2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w)},
                   {2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)}};
  const PPCVRegister* rows[3] = {&v11, &v12, &v10};
  const PPCVRegister* scales[3] = {&v4, &v3, &v2};
  float err = 0, errT = 0;
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) {
      float sc = El(*scales[i], 0);
      float got = El(*rows[i], j) / (std::abs(sc) > 1e-6f ? sc : 1.0f);
      err = std::max(err, std::abs(got - r[i][j]));
      errT = std::max(errT, std::abs(got - r[j][i]));
    }
  float e = std::min(err, errT);
  if (e > 2e-3f) ++bad;
  if ((e > 2e-3f && logged < 6) || n <= 3) {
    ++logged;
    REXKRNL_INFO("[dbg] DecodeQuat #{} err={:.4f} errT={:.4f} q=({:.4f},{:.4f},{:.4f},{:.4f}) scale=({:.3f},{:.3f},{:.3f}) "
                 "rows=({:.4f},{:.4f},{:.4f}|{:.4f},{:.4f},{:.4f}|{:.4f},{:.4f},{:.4f})",
                 n, err, errT, x, y, z, w, El(v4, 0), El(v3, 0), El(v2, 0), El(v11, 0), El(v11, 1), El(v11, 2),
                 El(v12, 0), El(v12, 1), El(v12, 2), El(v10, 0), El(v10, 1), El(v10, 2));
  }
  if (n % 50000 == 0) REXKRNL_INFO("[dbg] DecodeQuat {} calls, {} mismatches", n, bad.load());
}

void Dbg_DecodeInputs(PPCVRegister& v12, PPCVRegister& v0, PPCVRegister& v5, PPCVRegister& v6, PPCRegister& r8,
                      PPCRegister& r1) {
  static std::atomic<int> logged = 0, calls = 0;
  int n = ++calls;
  // WORKAROUND(wrists): Xenia's hand offset for render bone 115 has the opposite
  // X sign; flip it in both blend inputs (guest element 0 = host f32[3]).
  if (r8.u32 == 115 || r8.u32 == 119) {
    v12.f32[3] = -v12.f32[3];
    v0.f32[3] = -v0.f32[3];
  }
  if (r8.u32 != 115 || n < 200000 || ++logged > 6) return;
  std::string raw;
  for (uint32_t off = 80; off < 112; off += 2) {
    const uint8_t* p = fifa08::dbg::Ptr(r1.u32 + off);
    raw += fmt::format(" {:02X}{:02X}", p[0], p[1]);
  }
  REXKRNL_INFO("[dbg] DecodeInputs bone 115 q1=({:.4f},{:.4f},{:.4f},{:.4f}) q0=({:.4f},{:.4f},{:.4f},{:.4f}) "
               "w5=({:.3f},{:.3f}) w6=({:.3f},{:.3f}) staged halves r1+80:{}",
               El(v12, 0), El(v12, 1), El(v12, 2), El(v12, 3), El(v0, 0), El(v0, 1), El(v0, 2), El(v0, 3), El(v5, 0),
               El(v5, 3), El(v6, 0), El(v6, 3), raw);
}

void Dbg_RigTable(PPCRegister& r26, PPCRegister& r28) {
  static int calls = 0;
  if (++calls > 4) return;
  uint32_t t = r28.u32;
  std::string line;
  int missing = 0;
  for (uint32_t off = 0; off <= 336; off += 4) {
    uint32_t v = fifa08::dbg::U32(t + off);
    if (v == 0xFFFF || v == 0xFFFFFFFF) ++missing;
    line += fmt::format("{}:{:X} ", off, v);
  }
  REXKRNL_INFO("[dbg] RigTable #{} src={:08X} table={:08X} missing={} LHandRig={:08X} RHandRig={:08X}",
               calls, r26.u32, t, missing, fifa08::dbg::U32(t + 332), fifa08::dbg::U32(t + 336));
  REXKRNL_INFO("[dbg]   {}", line);

  // The skeleton's channel names, as sub_82715170 searches them:
  // r26 -> +40 -> +32 = name list: u16 count at +4, char* array at +12.
  if (calls == 1) {
    uint32_t list = fifa08::dbg::U32(fifa08::dbg::U32(r26.u32 + 40) + 32);
    const uint8_t* cp = fifa08::dbg::Ptr(list + 4);
    uint32_t count = cp ? (uint32_t(cp[0]) << 8 | cp[1]) : 0;
    uint32_t names = fifa08::dbg::U32(list + 12);
    std::string all;
    for (uint32_t i = 0; i < count; ++i) {
      const char* s = reinterpret_cast<const char*>(fifa08::dbg::Ptr(fifa08::dbg::U32(names + i * 4)));
      all += fmt::format("{:X}={} ", i, s ? std::string(s, strnlen(s, 64)) : "?");
    }
    REXKRNL_INFO("[dbg] skeleton channels ({}): {}", count, all);
  }
}
