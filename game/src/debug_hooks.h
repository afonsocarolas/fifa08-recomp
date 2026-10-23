#pragma once

// Debug probes called from generated code (config/debug_hooks.toml).

#include <cstdint>
#include <string>

#include <rex/system/kernel_state.h>
#include <rex/logging.h>
#include <rex/ppc/context.h>

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
