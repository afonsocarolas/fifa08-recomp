# FIFA 08 (X360): player hands bent back at the wrist; correct in Xenia, same data in memory

## Summary

In a ReXGlue recompilation of **EA Sports FIFA 08 (Xbox 360)**, every player's hands are held
bent sharply upward at the wrist (open palm, thumb up), in idle and while moving. Arms, legs,
body and all other animation look right. The same disc in **Xenia Canary** shows relaxed,
correctly posed hands.

I've ruled out graphics, loaded data and the per-instruction semantics I could test (details
below). That leaves something in the recompiled CPU code that only shows up when the animation
code runs, so I'm hoping someone who knows the recompiler's internals can recognise the pattern.

## Environment

| | |
|---|---|
| ReXGlue SDK | `v0.10.0` (`f5337cd`), built from source |
| Compiler | Clang 22.1.3 (VS Build Tools 2026), CMake 4.3.1, Ninja |
| OS / GPU | Windows 11 (10.0.26200), NVIDIA RTX 5050 Laptop, D3D12 (`--gpu_plugin=xenos`) |
| Game | EA Sports FIFA 08, Xbox 360, title ID `4541081F`, media ID `703DA73D`, version 0.0.0.5 (disc, no title update) |
| `default.xex` SHA-256 | `414944A53B8E9B1DF0752177B05263A02773E756A8F7302F43186D1B3C58189C` |
| Reference | Xenia Canary `02d2cb5` (official release build) |

SDK patches applied on top of v0.10.0 (none touch codegen except the last):

- `src/kernel/CMakeLists.txt`: enable `xboxkrnl_usbcam.cpp` (game imports `XUsbcamGetState`/`SetConfig`)
- Resolve fixes from the FIFA 09 port: execute resolves while a visibility query kills pixels,
  and `edram_ownership_no_wrap` (without these, UI text is missing)
- FidelityFX build fixes (UTF-16 `.rc`, install config) and a guest-frame RenderDoc capture hook
- Upstream `6319e23` (vpkuwus/vpkuhus vD aliasing). FIFA 08 uses these 9 times; no change to the bug

Codegen: 445 files. Overrides add 8 tail-call targets plus 115 indirect-call/vtable targets
(found by scanning data sections for code pointers and cross-checking against `.pdata`).
The game boots, menus work and full matches play.

## Steps to reproduce

1. Recompile `default.xex` above with SDK v0.10.0 (plus the patches above), D3D12 Xenos backend.
2. Start the game and leave it on the title screen / Practice Arena (Ronaldinho on the ball).
3. Watch the hands, or start any match.

**Expected (Xenia):** hands relaxed, fingers slightly curled, wrists in line with the forearm.
**Actual (ReXGlue):** hands bent up about 60–90° at the wrist, palm open, thumb up, most of the time.
Screenshots of both are attached.

## What I checked

### 1. Not graphics

RenderDoc guest-frame captures show that FIFA 08 **skins characters on the CPU**. The vertex
shaders with dynamically indexed constants (`CB2[256], dynamicIndexed`) make only one relative
read (`CB2[r + 4]`), not a bone palette, and vertices are fetched from raw shared memory. The GPU
draws already-deformed geometry, so the pose is wrong before it reaches the GPU.

### 2. Loaded data and setup are identical to Xenia

Both Xenia and our runtime map guest memory at host `0x100000000`, and FIFA 08's heap layout
turned out to be **identical** in both, so I could read the same guest addresses from both
processes while they ran:

- **2 MB around the skeleton/rig objects (`0xBC600000–0xBC7FFFFF`) is byte-identical** to Xenia
  in the Practice Arena: rig assets, rig hierarchy (`AnimRig`, `BodyRig`, `LArmRig`, …) and setup data.
- The rig channel table built by `sub_82715170` (channel name → bone index) is identical in every
  build (3 player models). 8 names have no match (`*ArmRoll`, `*ForeArmRoll`, `*UpLegRoll`,
  `*KneeEffectorAux`), but the 137-bone skeleton genuinely uses `*Twist`/`*Twist1` names instead.
  `LHandRig`/`RHandRig` are found (`sub_82957E80` returns non-zero) and `LeftHand`/`RightHand`
  resolve to bones `0x41`/`0x60`.

### 3. Live bone matrices differ only in the arm/wrist joints

Per-frame 137×4×4 bone matrix palettes are at the same addresses in both processes
(`0xBDB03A80`, `0xBDB05D00`, `0xBDB0DD00`, …). Parent→child angles along the finger chains match
Xenia exactly (for example index 25.0°/12.0°/16.7°, thumb 79.2°/10.9°). The differences are in the
shoulder and forearm-twist→hand steps, for example `ForeArmTwist1→Hand` in `0xBDB05D00`:
ours 9.3°/3.0° (L/R), Xenia 20.1°/15.7°. I can't capture both at the same game frame, so this is
indicative, not conclusive.

### 4. Instruction semantics

- All 1458 existing `ppc_tests` pass.
- I fuzzed **48 instructions FIFA 08 uses that have no test file** (1920 random cases with
  Python reference models; NaN/Inf/denormals excluded). These were scalar
  `fadds/fsubs/fmuls/fdivs/fsqrts/frsp/fmsubs/fnmsubs/fsub/fdiv/fmsub/fnmsub/fneg/fcfid`, VMX/VMX128
  float `vmulfp128/vmaddfp128/vmaddcfp128/vnmsubfp(128)/vcsxwfp128/vcfux/vrfiz/vrfim`,
  `vcmp{gt,ge,eq}fp(.)` including CR6, and integer
  `vsraw/vsrw/vsrb/vsububm/vaddubm/vadduwm/vaddubs/vaddsbs/vaddsws/vsubsws/vnor/vavgub/vcmpequ{b,h,w}/vcmpgt{ub,uh,sh,sw}`.
  **44/48 match exactly.**
- The 4 that don't are **`vmaddfp128`, `vmaddcfp128`, `vnmsubfp`, `vnmsubfp128`**: 1–2 ulp (10 ulp
  in one cancellation case), because codegen emits `mul_ps` then `add_ps`, while my reference (and
  Xenia's JIT on FMA hardware) is fused. Switching `build_vmaddfp`/`build_vnmsubfp` to
  `simde_mm_fmadd_ps`/`simde_mm_fnmadd_ps` with `-mfma` makes all fuzz cases pass (10,653 sites in
  FIFA 08) **but does not fix the wrists**. It also makes the existing `instr_vmaddfp.s` test_1
  fail: it expects the unfused `0x4013D70A` for 1.1×1.1+1.1, where fused gives `0x4013D70B`. Do you
  know whether that expectation comes from hardware?
- Also tried, no effect on the wrists: keeping MXCSR rounding at round-to-nearest while in VMX
  flush mode (currently a guest `mtfsf` rounding change also applies to VMX ops; FIFA 08 has 5
  `mtfsf`, all in CRT-style FP-control routines).
- Reviewed and look correct: `vupkhsh/vupklsh/vcfsx/vupkd3d128` (all modes), VMX128 multiply-add
  operand order, `vmsum3fp128/vmsum4fp128` (same `dpps` approach as Xenia).
- FIFA 08 doesn't use `fctiw` (non-z); `vcsxwfp128` immediates used are only 0, 1 and 11.

## What would help

- Any known codegen issue in this area: animation/IK math, `lvlx`/`lvrx` at unusual alignments,
  `vperm`/`vpermwi128`/`vrlimi128` with aliased registers, `vsldoi`, CR6-based branches after
  vector compares, or anything that only goes wrong in combination.
- A way to trace one guest function's register/memory state per call, so I can compare
  `RHandRig` evaluation against Xenia directly.

The hooks and tools used here (guest memory reader, palette finder, fuzzer generator in the SDK
test format, RenderDoc guest-frame capture) are available if they're useful. No game files or
generated code are included.

## Other things I ran into (Windows)

- `git clone --recursive` without symlink support leaves symlink placeholders as text files
  (for example `thirdparty/libmspack/cabextract/mspack/lzxd.c` contains `../../libmspack/mspack/lzxd.c`),
  which breaks the build. Copying the targets over fixes it.
- With `REXGLUE_BUILD_TESTS=ON`, `unit_tests` fails: `rex/hash.h: 'xxhash.h' file not found`.
- The `ppc_tests` generation step runs `rexglue.exe` from the build tree, which fails with
  `0xC0000135` (missing `TracyClient.dll`) unless the install `bin/` is on `PATH`.
- binutils accepts only −16…15 for the `vcsxwfp128` immediate (signed), while Xenia treats it as
  unsigned 0…31, which may be worth a look in the decoder.
