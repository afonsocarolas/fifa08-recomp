@echo off
rem Build and run the XenonRecomp-vs-ReXGlue instruction test.
rem Usage: tools\xenon_vs_rex.cmd <generated.cpp> <out.exe>
rem (generate the .cpp first with: py -I tools\xenon_vs_rex.py <generated.cpp>)
call "%~dp0vsenv.cmd" clang++ -O2 -std=gnu++23 -msse4.1 -D_DLL -D_MT -Xclang --dependent-lib=msvcrt ^
  -DNOMINMAX -DWIN32_LEAN_AND_MEAN ^
  -isystem "%~dp0..\third_party\rexglue-sdk\out\install\win-amd64\include" ^
  "%~1" -o "%~2" || exit /b 1
"%~2"
