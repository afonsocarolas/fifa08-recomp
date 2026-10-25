package org.fifa08recomp.port;

import java.io.File;

import org.libsdl.app.SDLActivity;

/**
 * FIFA 08 (ReXGlue port) on Android.
 *
 * The game is libmain.so; SDL3 is linked into librexruntime.so, so that is
 * loaded instead of a separate libSDL3.so. Game files are read from the app's
 * external files directory:
 *   /sdcard/Android/data/org.fifa08recomp.port/files/assets/default.xex ...
 * and the log is written next to them as run.log. Extra command-line flags
 * (one per line) can be put in files/args.txt.
 */
public class Fifa08Activity extends SDLActivity {
    @Override
    protected String[] getLibraries() {
        return new String[] { "c++_shared", "rexruntime", "main" };
    }

    @Override
    protected String getMainFunction() {
        // ReXGlue's SDL entry point is a plain main().
        return "main";
    }

    @Override
    protected String[] getArguments() {
        File files = getExternalFilesDir(null);
        String dir = files != null ? files.getAbsolutePath() : getFilesDir().getAbsolutePath();
        java.util.List<String> args = new java.util.ArrayList<>(java.util.Arrays.asList(
            "--game_data_root=" + dir + "/assets",
            // Saves, shader cache and config; the desktop default ($HOME/.local)
            // is not writable for apps.
            "--user_data_root=" + dir + "/user",
            "--gpu_plugin=xenos",
            "--edram_ownership_no_wrap=true",
            "--fullscreen=true",
            "--log_level=info",
            "--log_file=" + dir + "/run.log"));
        // Extra flags for testing, one per line, from files/args.txt.
        File extra = new File(dir, "args.txt");
        if (extra.isFile()) {
            try (java.io.BufferedReader r = new java.io.BufferedReader(new java.io.FileReader(extra))) {
                for (String line; (line = r.readLine()) != null; ) {
                    line = line.trim();
                    if (!line.isEmpty() && !line.startsWith("#")) args.add(line);
                }
            } catch (java.io.IOException ignored) {
            }
        }
        return args.toArray(new String[0]);
    }
}
