#pragma once

#ifndef _WIN32
// Windows-only debugging tool; no-op elsewhere (Android build).
#include <cstdint>

namespace fifa08::watch {
inline void Start() {}
inline void ArmFromHook(uint32_t, uint32_t, const char*) {}
}  // namespace fifa08::watch
#else

// Find the guest code that writes (or, with --watch_reads, reads) a range of guest memory, e.g.
//   fifa08.exe ... --watch_addr=BDB06D40 --watch_len=64 --watch_at=40 --watch_for=5
// From watch_at seconds after start, the pages holding the range are made
// PAGE_GUARD. Every write into the range records the host call stack (unwound
// through x64 unwind data and mapped back to sub_XXXXXXXX via PPCFuncMappings).
// After watch_for seconds the distinct stacks are logged as "[watch]" lines.

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <windows.h>

#include <rex/cvar.h>
#include <rex/logging.h>
#include <rex/ppc/func.h>

REXCVAR_DEFINE_STRING(watch_addr, "", "Debug", "Guest address (hex) to watch for writes");
REXCVAR_DEFINE_INT32(watch_len, 64, "Debug", "Bytes to watch from watch_addr");
REXCVAR_DEFINE_INT32(watch_at, 40, "Debug", "Seconds after start to begin watching");
REXCVAR_DEFINE_INT32(watch_for, 5, "Debug", "Seconds to watch before logging the results");
REXCVAR_DEFINE_BOOL(watch_reads, false, "Debug", "Record reads of the range instead of writes");
REXCVAR_DEFINE_BOOL(watch_both, false, "Debug", "Record reads and writes, in order (see the [watch] sequence lines)");
REXCVAR_DEFINE_STRING(watch_hook, "", "Debug", "Let the named debug hook site pick the watched address (see debug_hooks.h)");

namespace fifa08::watch {

constexpr uint64_t kGuestBase = 0x100000000ull;
constexpr int kFrames = 8;

struct Stack {
  uint64_t rip[kFrames]{};
  bool operator<(const Stack& o) const { return std::lexicographical_compare(rip, rip + kFrames, o.rip, o.rip + kFrames); }
};

struct State {
  uint8_t* lo = nullptr;  // watched host range
  uint8_t* hi = nullptr;
  uint8_t* page_lo = nullptr;
  size_t page_len = 0;
  DWORD protect = PAGE_READWRITE;
  bool armed = false;
  bool reads = false;
  bool both = false;
  std::mutex mutex;
  std::map<Stack, uint32_t> hits;  // stack -> count
  std::map<Stack, uint32_t> first_offset;
  struct Event {
    Stack stack;
    uint32_t offset;
    bool write;
    uint32_t thread;
    uint8_t bytes[16];
  };
  std::vector<Event> events;  // first writes in order, with the 16 bytes after each
  std::vector<std::pair<uintptr_t, uint32_t>> funcs;  // host fn -> guest addr, sorted
};

inline State& S() {
  static State s;
  return s;
}

inline thread_local bool t_rearm = false;
inline thread_local uint8_t* t_write = nullptr;  // in-range write being single-stepped
inline thread_local Stack t_stack;

inline void Arm() {
  DWORD old;
  VirtualProtect(S().page_lo, S().page_len, S().protect | PAGE_GUARD, &old);
}

inline Stack Unwind(const CONTEXT& fault) {
  Stack st;
  CONTEXT c = fault;
  for (int i = 0; i < kFrames && c.Rip; ++i) {
    st.rip[i] = c.Rip;
    DWORD64 image_base = 0;
    PRUNTIME_FUNCTION fn = RtlLookupFunctionEntry(c.Rip, &image_base, nullptr);
    if (!fn) {  // leaf function: return address is at [rsp]
      c.Rip = *reinterpret_cast<DWORD64*>(c.Rsp);
      c.Rsp += 8;
      continue;
    }
    void* handler_data;
    DWORD64 establisher;
    RtlVirtualUnwind(UNW_FLAG_NHANDLER, image_base, c.Rip, fn, &c, &handler_data, &establisher, nullptr);
  }
  return st;
}

inline LONG CALLBACK Handler(EXCEPTION_POINTERS* e) {
  State& s = S();
  DWORD code = e->ExceptionRecord->ExceptionCode;
  if (code == STATUS_GUARD_PAGE_VIOLATION && s.armed) {
    auto* addr = reinterpret_cast<uint8_t*>(e->ExceptionRecord->ExceptionInformation[1]);
    if (addr < s.page_lo || addr >= s.page_lo + s.page_len) return EXCEPTION_CONTINUE_SEARCH;
    bool write = e->ExceptionRecord->ExceptionInformation[0] == 1;
    if ((s.both || write != s.reads) && addr + 16 > s.lo && addr < s.hi) {
      Stack st = Unwind(*e->ContextRecord);
      std::lock_guard lock(s.mutex);
      if (s.hits[st]++ == 0) s.first_offset[st] = uint32_t(addr - s.lo);
      if (s.both && !write && s.events.size() < 400) {
        State::Event ev{st, uint32_t(addr - s.lo), false, GetCurrentThreadId(), {}};
        s.events.push_back(ev);
      }
      if (write && !s.reads) t_write = addr;
      t_stack = st;
    }
    // The guard is gone now; single-step the access, then put it back.
    t_rearm = true;
    e->ContextRecord->EFlags |= 0x100;
    return EXCEPTION_CONTINUE_EXECUTION;
  }
  if (code == STATUS_SINGLE_STEP && t_rearm) {
    t_rearm = false;
    if (t_write) {
      uint8_t* line = reinterpret_cast<uint8_t*>(reinterpret_cast<uintptr_t>(t_write) & ~uintptr_t(15));
      std::lock_guard lock(s.mutex);
      if (s.events.size() < 400) {
        State::Event ev{t_stack, uint32_t(line - s.lo), true, GetCurrentThreadId(), {}};
        memcpy(ev.bytes, line, 16);
        s.events.push_back(ev);
      }
      t_write = nullptr;
    }
    if (s.armed) Arm();
    return EXCEPTION_CONTINUE_EXECUTION;
  }
  return EXCEPTION_CONTINUE_SEARCH;
}

inline std::string Describe(uint64_t rip) {
  auto& f = S().funcs;
  auto it = std::upper_bound(f.begin(), f.end(), std::pair<uintptr_t, uint32_t>(rip, UINT32_MAX));
  uintptr_t module = reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr));
  if (it == f.begin()) return fmt::format("exe+{:X}", rip - module);
  --it;
  return fmt::format("sub_{:08X}+{:X} (exe+{:X})", it->second, rip - it->first, rip - module);
}

inline void Setup() {
  static std::once_flag once;
  std::call_once(once, [] {
    State& s = S();
    for (PPCFuncMapping* m = PPCFuncMappings; m->host; ++m)
      s.funcs.emplace_back(reinterpret_cast<uintptr_t>(m->host), uint32_t(m->guest));
    std::sort(s.funcs.begin(), s.funcs.end());
    s.reads = REXCVAR_GET(watch_reads);
    s.both = REXCVAR_GET(watch_both);
    AddVectoredExceptionHandler(1, Handler);
  });
}

inline void Report() {
  State& s = S();
  std::lock_guard lock(s.mutex);
  REXKRNL_INFO("[watch] {} distinct {} stacks", s.hits.size(), s.reads ? "reader" : "writer");
  for (auto& [st, n] : s.hits) {
    REXKRNL_INFO("[watch] {} hits, first at +{}:", n, s.first_offset[st]);
    for (uint64_t rip : st.rip)
      if (rip) REXKRNL_INFO("[watch]     {}", Describe(rip));
  }
  // Values as big-endian floats, tagged with the writing function and its caller.
  for (auto& ev : s.events) {
    float f[4];
    for (int i = 0; i < 4; ++i) {
      uint32_t u = _byteswap_ulong(*reinterpret_cast<uint32_t*>(ev.bytes + i * 4));
      memcpy(&f[i], &u, 4);
    }
    if (!ev.write) {
      REXKRNL_INFO("[watch] +{:<3} READ  t{:<6} {} <- {}", ev.offset, ev.thread, Describe(ev.stack.rip[0]),
                   Describe(ev.stack.rip[1]));
      continue;
    }
    REXKRNL_INFO("[watch] +{:<3} WRITE t{:<6} {:>10.5f} {:>10.5f} {:>10.5f} {:>10.5f}  {} <- {}", ev.offset, ev.thread,
                 f[0], f[1], f[2], f[3], Describe(ev.stack.rip[0]), Describe(ev.stack.rip[1]));
  }
}

// Watch [guest, guest + len) now, for watch_for seconds, then log the results.
inline void ArmRange(uint32_t guest, uint32_t len) {
  Setup();
  State& s = S();
  s.lo = reinterpret_cast<uint8_t*>(kGuestBase + guest);
  s.hi = s.lo + len;
  s.page_lo = reinterpret_cast<uint8_t*>(reinterpret_cast<uintptr_t>(s.lo) & ~uintptr_t(0xFFF));
  s.page_len = ((reinterpret_cast<uintptr_t>(s.hi) + 0xFFF) & ~uintptr_t(0xFFF)) - reinterpret_cast<uintptr_t>(s.page_lo);
  MEMORY_BASIC_INFORMATION mbi{};
  VirtualQuery(s.page_lo, &mbi, sizeof(mbi));
  s.protect = mbi.Protect & ~PAGE_GUARD;
  REXKRNL_INFO("[watch] watching {:08X}..{:08X} (protect {:X})", guest, guest + len, s.protect);
  s.armed = true;
  Arm();
  int dur = REXCVAR_GET(watch_for);
  std::thread([dur] {
    State& s = S();
    std::this_thread::sleep_for(std::chrono::seconds(dur));
    s.armed = false;
    DWORD old;
    VirtualProtect(s.page_lo, s.page_len, s.protect, &old);
    Report();
  }).detach();
}

// From a debug hook: watch an address the hook just computed, if --watch_hook
// names this site (once per run).
inline void ArmFromHook(uint32_t guest, uint32_t len, const char* site) {
  static std::atomic<bool> used = false;
  if (REXCVAR_GET(watch_hook) != site || used.exchange(true)) return;
  ArmRange(guest, len);
}

inline void Start() {
  std::string a = REXCVAR_GET(watch_addr);
  if (a.empty()) return;
  uint32_t guest = uint32_t(std::strtoul(a.c_str(), nullptr, 16));
  Setup();
  int at = REXCVAR_GET(watch_at), len = REXCVAR_GET(watch_len);
  std::thread([guest, at, len] {
    std::this_thread::sleep_for(std::chrono::seconds(at));
    ArmRange(guest, uint32_t(len));
  }).detach();
}

}  // namespace fifa08::watch

#endif  // _WIN32
