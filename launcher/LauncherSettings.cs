using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace Fifa08Launcher;

/// <summary>Everything the launcher remembers, saved as launcher.json next to the launcher.</summary>
public sealed class LauncherSettings
{
    public bool Fullscreen { get; set; } = true;
    public string WindowSize { get; set; } = "1280x720";
    public int Monitor { get; set; } = 0;              // 0 = default

    public int RenderScale { get; set; } = 1;          // 1 = 720p (original), 2 = 1440p, 3 = 4K
    public string Upscaling { get; set; } = "fsr";     // bilinear, fsr, cas
    public int Sharpness { get; set; } = 80;           // 0..100

    public int FrameRate { get; set; } = 60;           // 0 = unlimited

    public string GameExe { get; set; } = "";          // empty = auto-detect
    public string GameData { get; set; } = "";

    static string FilePath => Path.Combine(AppContext.BaseDirectory, "launcher.json");
    static readonly JsonSerializerOptions Json = new() { WriteIndented = true };

    public static LauncherSettings Load()
    {
        try
        {
            if (File.Exists(FilePath))
                return JsonSerializer.Deserialize<LauncherSettings>(File.ReadAllText(FilePath)) ?? new();
        }
        catch (Exception) { /* broken file: start from defaults */ }
        return new();
    }

    public void Save() => File.WriteAllText(FilePath, JsonSerializer.Serialize(this, Json));

    /// <summary>Command-line flags for fifa08.exe.</summary>
    public List<string> GameArguments(string gameData)
    {
        var args = new List<string>
        {
            $"--game_data_root={gameData}",
            "--gpu_plugin=xenos",
            "--edram_ownership_no_wrap=true",
            Fullscreen ? "--fullscreen" : "--no-fullscreen",
            $"--resolution_scale={Math.Clamp(RenderScale, 1, 3)}",
            $"--present_effect={Upscaling}",
            "--log_level=info",
            "--log_file=run.log",
        };
        if (!Fullscreen && TryParseSize(WindowSize, out int w, out int h))
        {
            args.Add($"--window_width={w}");
            args.Add($"--window_height={h}");
        }
        if (Monitor > 0)
            args.Add($"--monitor={Monitor}");

        double s = Math.Clamp(Sharpness, 0, 100) / 100.0;
        if (Upscaling == "fsr")
            args.Add(FormattableString.Invariant($"--present_fsr_sharpness_reduction={2.0 * (1.0 - s):0.00}"));
        else if (Upscaling == "cas")
            args.Add(FormattableString.Invariant($"--present_cas_additional_sharpness={s:0.00}"));

        if (FrameRate <= 0)
        {
            args.Add("--no-vsync");
        }
        else
        {
            args.Add("--vsync");
            args.Add($"--video_mode_refresh_rate={Math.Clamp(FrameRate, 24, 240)}");
        }
        return args;
    }

    public static bool TryParseSize(string text, out int w, out int h)
    {
        w = h = 0;
        var parts = text.Split('x');
        return parts.Length == 2 && int.TryParse(parts[0], out w) && int.TryParse(parts[1], out h);
    }
}
