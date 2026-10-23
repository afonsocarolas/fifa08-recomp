# FIFA 08 PC

A native PC port of the Xbox 360 version of EA Sports FIFA 08, made by static
recompilation with the [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk).
Follows the approach of [fifa09-recomp](https://github.com/ChunchunQ/fifa09-recomp).

**No game files are included.** You need your own FIFA 08 Xbox 360 disc.

## Target executable

| | |
|---|---|
| Game | EA Sports FIFA 08 (Xbox 360) |
| Title ID | `4541081F` |
| Media ID | `703DA73D` |
| Version | 0.0.0.5 (disc, no title update) |
| `default.xex` SHA-256 | `414944A53B8E9B1DF0752177B05263A02773E756A8F7302F43186D1B3C58189C` |

Other regions or versions will not work with this build.

## Layout

| Folder | What |
|---|---|
| `game/assets/` | Your extracted disc files (not committed) |
| `game/` | The port project (once generated) |
| `tools/` | Helper scripts |
| `third_party/` | ReXGlue SDK and the FIFA 09 port, for reference (not committed) |

## Tools

```
py -I tools/xiso_extract.py "FIFA 08.iso" game/assets     # extract your disc image
py -I tools/xiso_extract.py "FIFA 08.iso" x --list        # list its files
py -I tools/xex_info.py game/assets/default.xex           # title ID, version, hash
```

## Requirements to build

Windows, Visual Studio 2022 with *Desktop development with C++*,
*C++ Clang Compiler for Windows* (20+) and *MSBuild support for LLVM (clang-cl)*,
plus CMake 3.25+ and Ninja.

## Launcher

`launcher/` is a small WPF app (.NET 6, runs on any newer .NET desktop runtime):
fullscreen or window, monitor, render resolution (720p / 1440p / 4K), upscaling
(off, AMD FSR, AMD CAS with sharpness) and a frame-rate limit (30 to 240, or unlimited).
Settings are saved in `launcher.json` next to it.

```
dotnet build launcher -c Release
```

It finds `fifa08.exe` and the game files either in a player package
(`bin\fifa08.exe`, `Game\default.xex` next to the launcher) or in this source tree.

FSR and CAS need the SDK built with FidelityFX:
`cmake --preset win-amd64 -DREXGLUE_ENABLE_FIDELITYFX=ON` (with `patches/sdk-fidelityfx-build.patch`).
