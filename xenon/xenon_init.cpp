// Image info for the XenonRecomp build (FIFA08_USE_XENONRECOMP): the same as
// ReXGlue's generated fifa08_init.cpp, but pointing at the function table in
// xenon/ppc/ppc_func_mapping.cpp.

#include "ppc/ppc_context.h"

static_assert(PPC_CODE_BASE == REX_CODE_BASE && PPC_CODE_SIZE == REX_CODE_SIZE &&
              PPC_IMAGE_BASE == REX_IMAGE_BASE && PPC_IMAGE_SIZE == REX_IMAGE_SIZE,
              "XenonRecomp and ReXGlue disagree about the image layout");

const rex::PPCImageInfo PPCImageConfig = {
    .code_base = REX_CODE_BASE,
    .code_size = REX_CODE_SIZE,
    .image_base = REX_IMAGE_BASE,
    .image_size = REX_IMAGE_SIZE,
    .func_mappings = PPCFuncMappings,
    .rexcrt_heap = REXCRT_HEAP,

    // Matches xenon/fifa08.toml: no optimizations.
    .codegen_flags = {
        .skip_lr = false,
        .ctr_as_local = false,
        .xer_as_local = false,
        .reserved_as_local = false,
        .skip_msr = false,
        .cr_as_local = false,
        .non_argument_as_local = false,
        .non_volatile_as_local = false,
    },
};
