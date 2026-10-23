# Launch a program under RenderDoc and press F12 (capture key) at given times.
# Usage: tools\rdoc_capture.ps1 -Exe <path> -Args @(...) -WorkDir <dir> -Out <dir\prefix> -At 46,50,54 [-Quit 60]
param([string]$Exe, [string[]]$Args = @(), [string]$WorkDir, [string]$Out, [int[]]$At = @(50), [int]$Quit = 0)
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class RdKeys {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
"@
$rdoc = Join-Path (Split-Path $PSScriptRoot) "third_party\renderdoc\app\RenderDoc_1.46_64\renderdoccmd.exe"
$quoted = $Args | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }
$p = Start-Process $rdoc -ArgumentList (@("capture", "-d", "`"$WorkDir`"", "-c", "`"$Out`"", "`"$Exe`"") + $quoted) -PassThru
$name = [IO.Path]::GetFileNameWithoutExtension($Exe)
$t0 = Get-Date
foreach ($t in $At) {
    while (((Get-Date) - $t0).TotalSeconds -lt $t) { Start-Sleep -Milliseconds 200 }
    $game = Get-Process $name -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
    if (-not $game) { "no $name window at ${t}s"; continue }
    [RdKeys]::SetForegroundWindow($game.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 300
    [RdKeys]::keybd_event(0x7B, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 80
    [RdKeys]::keybd_event(0x7B, 0, 2, [UIntPtr]::Zero)
    "F12 at ${t}s"
}
if ($Quit -gt 0) {
    while (((Get-Date) - $t0).TotalSeconds -lt $Quit) { Start-Sleep -Milliseconds 200 }
    Get-Process $name -ErrorAction SilentlyContinue | Stop-Process -Force
}
