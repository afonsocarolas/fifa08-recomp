// Context header for XenonRecomp's output: lets xenon/ppc build against the
// ReXGlue runtime instead of XenonRecomp's own ppc_context.h.
// Pass this file as XenonRecomp's second argument; it is copied verbatim
// into ppc/ppc_context.h (after an include of ppc_config.h).

#include "fifa08_pch.h"

// Function definitions. Same shape as ReXGlue's: extern "C" bodies under
// __imp__ names, with weak aliases that hooks can replace.
#define PPC_FUNC(x) REX_FUNC(x)
#define PPC_FUNC_IMPL(x) extern "C" REX_FUNC(x)
#define PPC_EXTERN_FUNC(x) REX_EXTERN(x)
#define PPC_WEAK_FUNC(x) __attribute__((weak, noinline)) extern "C" REX_FUNC(x)
#define PPC_FUNC_PROLOGUE() REX_FUNC_PROLOGUE()

// Memory: ReXGlue's versions also handle the physical-memory host offset.
#define PPC_LOAD_U8(x) REX_LOAD_U8(x)
#define PPC_LOAD_U16(x) REX_LOAD_U16(x)
#define PPC_LOAD_U32(x) REX_LOAD_U32(x)
#define PPC_LOAD_U64(x) REX_LOAD_U64(x)
#define PPC_STORE_U8(x, y) REX_STORE_U8(x, y)
#define PPC_STORE_U16(x, y) REX_STORE_U16(x, y)
#define PPC_STORE_U32(x, y) REX_STORE_U32(x, y)
#define PPC_STORE_U64(x, y) REX_STORE_U64(x, y)
#define PPC_MM_LOAD_U8(x) REX_MM_LOAD_U8(x)
#define PPC_MM_LOAD_U16(x) REX_MM_LOAD_U16(x)
#define PPC_MM_LOAD_U32(x) REX_MM_LOAD_U32(x)
#define PPC_MM_LOAD_U64(x) REX_MM_LOAD_U64(x)
#define PPC_MM_STORE_U8(x, y) REX_MM_STORE_U8(x, y)
#define PPC_MM_STORE_U16(x, y) REX_MM_STORE_U16(x, y)
#define PPC_MM_STORE_U32(x, y) REX_MM_STORE_U32(x, y)
#define PPC_MM_STORE_U64(x, y) REX_MM_STORE_U64(x, y)

#define PPC_CALL_FUNC(x) REX_CALL_FUNC(x)
#define PPC_CALL_INDIRECT_FUNC(x) REX_CALL_INDIRECT_FUNC(x)
#define PPC_QUERY_TIMEBASE() REX_QUERY_TIMEBASE()

// Vector helpers (simde_mm_perm_epi8_, simde_mm_vctsxs, ...) live in rex::ppc.
using namespace rex::ppc;

#define PPC_RAW_ADDR(x) REX_RAW_ADDR(x)
#define PPC_CHECK_GLOBAL_LOCK() REX_CHECK_GLOBAL_LOCK()
#define PPC_ENTER_GLOBAL_LOCK() REX_ENTER_GLOBAL_LOCK()
#define PPC_LEAVE_GLOBAL_LOCK() REX_LEAVE_GLOBAL_LOCK()
