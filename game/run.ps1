# Start the FIFA 08 port from the build folder, with logging to run.log.
# Usage: .\run.ps1 [-Fullscreen] [-Seconds N] [-Extra @("--flag=value")]
#   -Seconds N  stop the game after N seconds (for test runs)
param([switch]$Fullscreen, [int]$Seconds = 0, [string[]]$Extra = @())
$run = Join-Path $PSScriptRoot "out\build\win-amd64-release"
$assets = Join-Path $PSScriptRoot "assets"
Remove-Item (Join-Path $run "run.log") -ErrorAction SilentlyContinue
$screen = if ($Fullscreen) { @("--fullscreen") } else { @("--no-fullscreen", "--window_width=1280", "--window_height=720") }
$args0 = @("--game_data_root=$assets", "--gpu_plugin=xenos", "--edram_ownership_no_wrap=true") + $screen + @("--log_level=info", "--log_file=run.log")
$p = Start-Process "$run\fifa08.exe" -WorkingDirectory $run -ArgumentList ($args0 + $Extra) -PassThru
if ($Seconds -gt 0) {
    if (-not $p.WaitForExit($Seconds * 1000)) { Stop-Process -Id $p.Id -Force; "stopped after $Seconds s" }
    else { "exited with code $($p.ExitCode)" }
}
