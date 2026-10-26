# Start the port fullscreen with extra flags, take screenshots at fixed times, then close it.
# Usage: tools\shot_test.ps1 -Name rov -Extra @("--render_target_path_d3d12=rov") [-Times 45,50,55] [-Out dir]
#        [-Build xenon-release]  (build folder under game\out\build)
# Screenshots: <Out>\<Name>_<seconds>s.png (whole primary screen, physical pixels).
param([string]$Name, [string[]]$Extra = @(), [int[]]$Times = @(45, 50, 55),
      [string]$Out = (Join-Path $PSScriptRoot "..\out-shots"), [string]$Build = "win-amd64-release")
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -Namespace Win32 -Name Dpi -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
[Win32.Dpi]::SetProcessDPIAware() | Out-Null
New-Item -ItemType Directory -Force $Out | Out-Null

$game = Join-Path $PSScriptRoot "..\game"
$run = Join-Path $game "out\build\$Build"
$assets = Join-Path $game "assets"
Remove-Item (Join-Path $run "run.log") -ErrorAction SilentlyContinue
$args0 = @("--game_data_root=$assets", "--gpu_plugin=xenos", "--edram_ownership_no_wrap=true", "--fullscreen",
           "--log_level=info", "--log_file=run.log") + $Extra
$p = Start-Process "$run\fifa08.exe" -WorkingDirectory $run -ArgumentList $args0 -PassThru
$t0 = Get-Date
foreach ($t in $Times) {
    while (((Get-Date) - $t0).TotalSeconds -lt $t) { Start-Sleep -Milliseconds 200 }
    if ($p.HasExited) { "game exited early (code $($p.ExitCode))"; break }
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $file = Join-Path $Out "${Name}_${t}s.png"
    $bmp.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    "saved $file"
}
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
