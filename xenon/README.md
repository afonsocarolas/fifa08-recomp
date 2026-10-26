# FIFA 08 with XenonRecomp

A second build of the port whose recompiled code comes from
[XenonRecomp](https://github.com/hedge-dev/XenonRecomp) instead of ReXGlue's
codegen. It still runs on the ReXGlue runtime (kernel, GPU, input). In this
build the players' wrists are not bent.

## Files

- `fifa08.toml`: XenonRecomp config (register save/restore helpers, plus
  function sizes for functions whose switch cases run past the end
  XenonRecomp would guess).
- `manual_switch_tables.toml`: two switch tables XenonAnalyse misses.
- `rex_context.h`: maps XenonRecomp's `PPC_*` macros to ReXGlue's `REX_*` ones.
  XenonRecomp copies it into `ppc/ppc_context.h`.
- `xenon_init.cpp`: the `PPCImageConfig` the runtime needs.
- `recomp.sh`: regenerates `ppc/`.
- Not committed (made from your own game): `fifa08_switch_tables.toml`
  (XenonAnalyse output) and `ppc/` (the recompiled code).

## Building

1. Clone XenonRecomp into `third_party/XenonRecomp` at commit `ddd128b` and
   apply `patches/xenonrecomp-fifa08.patch`. It adds 42 instructions FIFA 08
   uses and fixes several codegen bugs, among them the in-place `vpkd3d128`
   pack that collapsed every skeleton. Build it with clang-cl (Ninja, Release).
2. Run XenonAnalyse on `game/assets/default.xex` and save the result as
   `xenon/fifa08_switch_tables.toml`.
3. `sh xenon/recomp.sh`
4. Configure the game into a separate folder with
   `-DFIFA08_USE_XENONRECOMP=ON`, for example:
   `cmake --preset win-amd64-release -B out/build/xenon-release -DFIFA08_USE_XENONRECOMP=ON`
   (from `game/`), then build it with `ninja`.

`tools/xenon_vs_rex.py` checks the two recompilers against each other: it runs
every instruction they translate differently on random register values and
reports any instruction whose results differ.
