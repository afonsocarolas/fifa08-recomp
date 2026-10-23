# Repeat: run the game, register the address of any "Call to invalid or unregistered
# function" crash in fifa08_overrides.toml, regenerate, rebuild. Stops when a run
# survives -Seconds, crashes some other way, or after -MaxRounds.
# Usage: tools\chase_indirect.ps1 [-Seconds 45] [-MaxRounds 25]
param([int]$Seconds = 45, [int]$MaxRounds = 25)
$root = Split-Path $PSScriptRoot
$game = Join-Path $root "game"
$rexglue = Join-Path $root "third_party\rexglue-sdk\out\install\win-amd64\bin\rexglue.exe"
$vsenv = Join-Path $PSScriptRoot "vsenv.cmd"
$overrides = Join-Path $game "fifa08_overrides.toml"
$log = Join-Path $game "out\build\win-amd64-release\run.log"
Set-Location $game

for ($round = 1; $round -le $MaxRounds; $round++) {
    $result = & (Join-Path $game "run.ps1") -Seconds $Seconds
    $fatal = Select-String -Path $log -Pattern 'unregistered function at guest address\s+0x([0-9A-Fa-f]{8})' |
        Select-Object -First 1
    if (-not $fatal) {
        "round ${round}: $result, no unregistered-function crash"
        Get-Content $log | Select-String 'critical|FATAL' | Select-Object -First 5
        break
    }
    $addr = "0x" + $fatal.Matches[0].Groups[1].Value.ToUpper()
    if (Select-String -Path $overrides -SimpleMatch "$addr =" -Quiet) {
        "round ${round}: $addr is already registered but still unresolved; stopping"
        break
    }
    "round ${round}: crash at $addr, registering it"
    Add-Content -Path $overrides -Value "$addr = { name = `"sub_$($addr.Substring(2))`" }"
    & $rexglue --log-file (Join-Path $root "out-codegen.log") codegen fifa08_manifest.toml *> (Join-Path $root "out-codegen-stdout.log")
    if ($LASTEXITCODE -ne 0) { "codegen failed, see out-codegen-stdout.log"; break }
    cmd /c "`"$vsenv`" cmake --build --preset win-amd64-release" *> (Join-Path $root "out-game-build.log")
    if ($LASTEXITCODE -ne 0) { "build failed, see out-game-build.log"; break }
}
