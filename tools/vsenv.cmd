@echo off
rem Run a command inside the Visual Studio x64 build environment with Clang first on PATH.
rem Usage: tools\vsenv.cmd <command> [args...]
setlocal
set "VS=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools"
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set "PATH=%VS%\VC\Tools\Llvm\x64\bin;%VS%\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;%VS%\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%"
%*
