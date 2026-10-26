// On a crash nobody handles, log the host call stack translated to guest
// functions (via PPCFuncMappings, so no PDB is needed). Windows only.
#pragma once

#ifndef _WIN32
namespace fifa08::crash_trace {
inline void Start() {}
}  // namespace fifa08::crash_trace
#else

#include <windows.h>

#include <algorithm>
#include <cstdint>
#include <vector>

#include <rex/logging.h>

namespace fifa08::crash_trace {

struct Entry {
  uintptr_t host;
  uint32_t guest;
};

inline std::vector<Entry>& Table() {
  static std::vector<Entry> table;
  return table;
}

// Guest function containing a host code address: the mapping with the
// nearest lower host address (the generated functions are laid out
// back to back in .text).
inline uint32_t GuestFunctionAt(uintptr_t pc, uintptr_t* offset) {
  auto& t = Table();
  auto it = std::upper_bound(t.begin(), t.end(), pc,
                             [](uintptr_t v, const Entry& e) { return v < e.host; });
  if (it == t.begin()) return 0;
  --it;
  *offset = pc - it->host;
  return it->guest;
}

inline LONG WINAPI OnUnhandled(EXCEPTION_POINTERS* info) {
  CONTEXT ctx = *info->ContextRecord;
  REXSYS_ERROR("crash_trace: exception 0x{:08X} at host 0x{:X}",
               uint32_t(info->ExceptionRecord->ExceptionCode), uintptr_t(ctx.Rip));
  for (int depth = 0; depth < 32 && ctx.Rip; ++depth) {
    uintptr_t offset = 0;
    uint32_t guest = GuestFunctionAt(ctx.Rip, &offset);
    REXSYS_ERROR("crash_trace: #{:02} host 0x{:X} -> sub_{:08X} +0x{:X}", depth,
                 uintptr_t(ctx.Rip), guest, offset);
    DWORD64 image_base = 0;
    auto* fn = RtlLookupFunctionEntry(ctx.Rip, &image_base, nullptr);
    if (!fn) {  // leaf function: return address is at [rsp]
      ctx.Rip = *reinterpret_cast<DWORD64*>(ctx.Rsp);
      ctx.Rsp += 8;
      continue;
    }
    void* handler_data = nullptr;
    DWORD64 establisher = 0;
    RtlVirtualUnwind(UNW_FLAG_NHANDLER, image_base, ctx.Rip, fn, &ctx, &handler_data,
                     &establisher, nullptr);
  }
  rex::FlushLogging();
  return EXCEPTION_CONTINUE_SEARCH;
}

inline void Start() {
  auto& t = Table();
  for (auto* m = PPCFuncMappings; m->host; ++m)
    t.push_back({reinterpret_cast<uintptr_t>(m->host), uint32_t(m->guest)});
  std::sort(t.begin(), t.end(), [](const Entry& a, const Entry& b) { return a.host < b.host; });
  SetUnhandledExceptionFilter(OnUnhandled);
}

}  // namespace fifa08::crash_trace
#endif
