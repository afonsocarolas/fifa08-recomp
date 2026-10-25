# Find the Barcelona player (blue/garnet kit) in each screenshot, crop around him and
# put the crops side by side, labelled, in one sheet for comparing hands.
# Usage: tools\player_sheet.ps1 -Out sheet.png shot1.png shot2.png ...
param([string]$Out, [Parameter(ValueFromRemainingArguments = $true)][string[]]$Shots)
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
public static class KitFinder {
  // Bounding box of saturated blue pixels (the shirt/shorts), ignoring the top band.
  public static Rectangle Find(Bitmap bmp) {
    var d = bmp.LockBits(new Rectangle(0, 0, bmp.Width, bmp.Height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
    var px = new byte[d.Stride * d.Height];
    Marshal.Copy(d.Scan0, px, 0, px.Length);
    bmp.UnlockBits(d);
    // Column/row histograms, then take the densest window so stray blue pixels don't matter.
    int[] cols = new int[bmp.Width], rows = new int[bmp.Height];
    for (int y = bmp.Height / 3; y < bmp.Height * 15 / 16; y++)
      for (int x = 0; x < bmp.Width; x++) {
        int i = y * d.Stride + x * 4;
        int b = px[i], g = px[i + 1], r = px[i + 2];
        if (b > 70 && b > r + 25 && b > g + 45) { cols[x]++; rows[y]++; }
      }
    int cx = Densest(cols, 120), cy = Densest(rows, 160);
    return new Rectangle(cx - 160, cy - 200, 320, 360);
  }
  static int Densest(int[] h, int w) {
    int best = 0, at = 0, sum = 0;
    for (int i = 0; i < h.Length; i++) {
      sum += h[i];
      if (i >= w) sum -= h[i - w];
      if (sum > best) { best = sum; at = i - w / 2; }
    }
    return at;
  }
}
"@
$scale = 2
$tiles = @()
foreach ($s in $Shots) {
    $img = [System.Drawing.Bitmap]::FromFile((Resolve-Path $s))
    $r = [KitFinder]::Find($img)
    $r.X = [Math]::Max(0, [Math]::Min($r.X, $img.Width - $r.Width))
    $r.Y = [Math]::Max(0, [Math]::Min($r.Y, $img.Height - $r.Height))
    $tiles += , @($img, $r, [IO.Path]::GetFileNameWithoutExtension($s))
}
$tw = 320 * $scale; $th = 360 * $scale + 24
$sheet = New-Object System.Drawing.Bitmap ($tw * $tiles.Count), $th
$g = [System.Drawing.Graphics]::FromImage($sheet)
$g.Clear([System.Drawing.Color]::Black)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
$font = New-Object System.Drawing.Font "Segoe UI", 12
for ($i = 0; $i -lt $tiles.Count; $i++) {
    $img, $r, $label = $tiles[$i]
    $g.DrawImage($img, (New-Object System.Drawing.Rectangle ($i * $tw), 24, $tw, ($th - 24)), $r, [System.Drawing.GraphicsUnit]::Pixel)
    $g.DrawString($label, $font, [System.Drawing.Brushes]::White, ($i * $tw + 4), 2)
    $img.Dispose()
}
$sheet.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $sheet.Dispose()
$Out
