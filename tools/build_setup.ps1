# Builds the PC setup exe (out\setup\FIFA08-Recomp-Setup-<version>.exe): the
# launcher (self-contained, no .NET install needed), the XenonRecomp game build
# and the Visual C++ runtime. No game files go in. Needs Inno Setup 6.
#   powershell -File tools\build_setup.ps1 [-GameBuild xenon-release] [-Version 0.1.0]
param(
    [string]$GameBuild = "xenon-release",
    [string]$Version = "0.1.0"
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$stage = Join-Path $root "out\setup\stage"
$game = Join-Path $root "game\out\build\$GameBuild"

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found (winget install JRSoftware.InnoSetup)" }
if (-not (Test-Path "$game\fifa08.exe")) { throw "No game build at $game; build it first" }

$vs = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\18\BuildTools"
$crt = Get-ChildItem "$vs\VC\Redist\MSVC\*\x64\Microsoft.VC*.CRT" | Sort-Object FullName | Select-Object -Last 1
if (-not $crt) { throw "Visual C++ runtime DLLs not found under $vs\VC\Redist" }

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory "$stage\launcher", "$stage\bin" | Out-Null

dotnet publish "$root\launcher\Fifa08Launcher.csproj" -c Release -r win-x64 --self-contained true `
    -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:EnableCompressionInSingleFile=true `
    -p:Version=$Version -o "$stage\launcher"
if ($LASTEXITCODE) { throw "dotnet publish failed" }
Remove-Item "$stage\launcher\*.pdb", "$stage\launcher\launcher.json" -ErrorAction SilentlyContinue

Copy-Item "$game\fifa08.exe", "$game\*.dll" "$stage\bin"
Copy-Item "$($crt.FullName)\*.dll" "$stage\bin"

& $iscc "/DStage=$stage" "/DAppVersion=$Version" "$root\installer\fifa08.iss"
if ($LASTEXITCODE) { throw "Inno Setup failed" }
Get-Item "$root\out\setup\FIFA08-Recomp-Setup-$Version.exe"
