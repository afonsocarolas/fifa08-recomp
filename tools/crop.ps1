# Crop a region of a screenshot and scale it up (nearest neighbour), for looking at small details.
# Usage: tools\crop.ps1 -In shot.png -X 600 -Y 450 -W 500 -H 450 [-Scale 2] [-OutFile crop.png]
param([string]$In, [int]$X, [int]$Y, [int]$W, [int]$H, [int]$Scale = 2, [string]$OutFile = "")
Add-Type -AssemblyName System.Drawing
if (-not $OutFile) { $OutFile = [IO.Path]::ChangeExtension($In, $null).TrimEnd('.') + "_crop.png" }
$src = [System.Drawing.Image]::FromFile((Resolve-Path $In))
$dst = New-Object System.Drawing.Bitmap ($W * $Scale), ($H * $Scale)
$g = [System.Drawing.Graphics]::FromImage($dst)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
$g.DrawImage($src, (New-Object System.Drawing.Rectangle 0, 0, ($W * $Scale), ($H * $Scale)),
             (New-Object System.Drawing.Rectangle $X, $Y, $W, $H), [System.Drawing.GraphicsUnit]::Pixel)
$dst.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $dst.Dispose(); $src.Dispose()
$OutFile
