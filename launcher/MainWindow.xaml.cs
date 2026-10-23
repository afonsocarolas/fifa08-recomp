using System;
using System.Diagnostics;
using System.Linq;
using System.IO;
using System.Windows;
using System.Windows.Controls;

namespace Fifa08Launcher;

public partial class MainWindow : Window
{
    readonly LauncherSettings settings = LauncherSettings.Load();

    public MainWindow()
    {
        InitializeComponent();
        LoadIntoControls();
        UpdateStatus();
    }

    void LoadIntoControls()
    {
        (settings.Fullscreen ? FullscreenRadio : WindowRadio).IsChecked = true;
        RemoveWindowSizesThatDoNotFit();
        SelectByContent(WindowSizeBox, settings.WindowSize);

        MonitorBox.Items.Add(new ComboBoxItem { Content = "Default", Tag = 0 });
        for (int i = 1; i <= System.Windows.Forms.Screen.AllScreens.Length; i++)
            MonitorBox.Items.Add(new ComboBoxItem { Content = $"Monitor {i}", Tag = i });
        SelectByTag(MonitorBox, settings.Monitor);

        (settings.RenderScale switch { 2 => Scale2, 3 => Scale3, _ => Scale1 }).IsChecked = true;
        (settings.Upscaling switch { "bilinear" => UpBilinear, "cas" => UpCas, _ => UpFsr }).IsChecked = true;
        SharpnessSlider.Value = settings.Sharpness;
        SelectByTag(FrameRateBox, settings.FrameRate);
    }

    void SaveFromControls()
    {
        settings.Fullscreen = FullscreenRadio.IsChecked == true;
        settings.WindowSize = (WindowSizeBox.SelectedItem as ComboBoxItem)?.Content as string ?? "1280x720";
        settings.Monitor = (MonitorBox.SelectedItem as ComboBoxItem)?.Tag as int? ?? 0;
        settings.RenderScale = Scale3.IsChecked == true ? 3 : Scale2.IsChecked == true ? 2 : 1;
        settings.Upscaling = UpBilinear.IsChecked == true ? "bilinear" : UpCas.IsChecked == true ? "cas" : "fsr";
        settings.Sharpness = (int)SharpnessSlider.Value;
        settings.FrameRate = int.Parse((FrameRateBox.SelectedItem as ComboBoxItem)?.Tag as string ?? "60");
        settings.Save();
    }

    /// <summary>
    /// The game takes the window size in logical pixels (scaled by Windows display scaling),
    /// the same units as WPF, so compare against the work area. Keep the smallest size always.
    /// </summary>
    void RemoveWindowSizesThatDoNotFit()
    {
        const double titleBar = 40;
        var area = SystemParameters.WorkArea;
        foreach (var item in WindowSizeBox.Items.OfType<ComboBoxItem>().Skip(1).ToList())
        {
            if (LauncherSettings.TryParseSize((string)item.Content, out int w, out int h) &&
                (w > area.Width || h + titleBar > area.Height))
                WindowSizeBox.Items.Remove(item);
        }
    }

    static void SelectByContent(ComboBox box, string content)
    {
        box.SelectedItem = box.Items.OfType<ComboBoxItem>().FirstOrDefault(i => (string)i.Content == content)
                           ?? box.Items[0];
    }

    static void SelectByTag(ComboBox box, int value)
    {
        box.SelectedItem = box.Items.OfType<ComboBoxItem>().FirstOrDefault(i => Convert.ToInt32(i.Tag) == value)
                           ?? box.Items[0];
    }

    void OnModeChanged(object sender, RoutedEventArgs e)
    {
        if (WindowSizeBox != null)
            WindowSizeBox.IsEnabled = WindowRadio.IsChecked == true;
    }

    void OnUpscalingChanged(object sender, RoutedEventArgs e)
    {
        if (SharpnessSlider != null)
            SharpnessSlider.IsEnabled = UpBilinear.IsChecked != true;
    }

    void OnSharpnessChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
    {
        if (SharpnessText != null)
            SharpnessText.Text = $"{(int)SharpnessSlider.Value}%";
    }

    /// <summary>Finds fifa08.exe and the game files: player package layout first, then the dev tree.</summary>
    (string? exe, string? data) FindGame()
    {
        string here = AppContext.BaseDirectory;
        string[] exeCandidates =
        {
            settings.GameExe,
            Path.Combine(here, "bin", "fifa08.exe"),
            Path.Combine(here, "fifa08.exe"),
            Path.GetFullPath(Path.Combine(here, "..", "..", "..", "..", "game", "out", "build", "win-amd64-release", "fifa08.exe")),
        };
        string[] dataCandidates =
        {
            settings.GameData,
            Path.Combine(here, "Game"),
            Path.GetFullPath(Path.Combine(here, "..", "..", "..", "..", "game", "assets")),
        };
        string? exe = exeCandidates.FirstOrDefault(p => !string.IsNullOrEmpty(p) && File.Exists(p));
        string? data = dataCandidates.FirstOrDefault(p => !string.IsNullOrEmpty(p) && File.Exists(Path.Combine(p, "default.xex")));
        return (exe, data);
    }

    void UpdateStatus()
    {
        var (exe, data) = FindGame();
        if (exe == null)
            StatusText.Text = "fifa08.exe not found next to the launcher.";
        else if (data == null)
            StatusText.Text = "Game files not found: put your FIFA 08 disc files in the Game folder (Game\\default.xex).";
        else
            StatusText.Text = $"Game files: {data}";
        PlayButton.IsEnabled = exe != null && data != null;
    }

    void OnPlay(object sender, RoutedEventArgs e)
    {
        SaveFromControls();
        var (exe, data) = FindGame();
        if (exe == null || data == null)
        {
            UpdateStatus();
            return;
        }
        var info = new ProcessStartInfo(exe) { WorkingDirectory = Path.GetDirectoryName(exe)!, UseShellExecute = false };
        foreach (var arg in settings.GameArguments(data))
            info.ArgumentList.Add(arg);
        try
        {
            Process.Start(info);
            Close();
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, ex.Message, "Could not start FIFA 08", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }
}
