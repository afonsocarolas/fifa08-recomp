@echo off
rem Double-click launcher: runs run.ps1 without changing the system's script policy.
rem Pass the same options as run.ps1, e.g. run.cmd -Fullscreen
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
