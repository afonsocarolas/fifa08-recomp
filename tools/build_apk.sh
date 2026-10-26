#!/usr/bin/env bash
# Build android/out/fifa08.apk from the Android game build, without Gradle.
#
# Needs (all under third_party/android): JDK 17, the Android SDK with
# platforms;android-35 and build-tools;35.0.0, and the NDK (for libc++_shared.so).
# Libraries come from the game build (see GAME_LIBS below) and the SDK's
# out/install/android-arm64. Signs with a local debug key (android/out/debug.keystore).
#
# Usage: bash tools/build_apk.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
A="$ROOT/third_party/android"
JDK="$(ls -d "$A"/jdk-17* | head -1)"
BT="$A/sdk/build-tools/35.0.0"
ANDROID_JAR="$A/sdk/platforms/android-35/android.jar"
NDK_LIBCXX="$A/android-ndk-r28c/toolchains/llvm/prebuilt/windows-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so"
SDL_JAVA="$ROOT/third_party/rexglue-sdk/thirdparty/sdl3/android-project/app/src/main/java"
# Game build: the XenonRecomp one (android-arm64-xenon) when present, else the
# ReXGlue one; override with GAME_LIBS=<build folder>.
GAME_LIBS="${GAME_LIBS:-$ROOT/game/out/build/android-arm64-xenon}"
[ -f "$GAME_LIBS/libmain.so" ] || GAME_LIBS="$ROOT/game/out/build/android-arm64-release"
echo "game libraries: $GAME_LIBS"
SDK_LIBS="$ROOT/third_party/rexglue-sdk/out/install/android-arm64/lib"
APP="$ROOT/android"
OUT="$APP/out"

export JAVA_HOME="$(cygpath -w "$JDK")"
export PATH="$JDK/bin:$PATH"
w() { cygpath -w "$1"; }

rm -rf "$OUT/gen" "$OUT/classes" "$OUT/dex" "$OUT/res.zip" "$OUT"/*.apk
mkdir -p "$OUT/gen" "$OUT/classes" "$OUT/dex"

echo "== resources"
"$BT/aapt2.exe" compile --dir "$(w "$APP/res")" -o "$(w "$OUT/res.zip")"
"$BT/aapt2.exe" link -o "$(w "$OUT/base.apk")" -I "$(w "$ANDROID_JAR")" \
    --manifest "$(w "$APP/AndroidManifest.xml")" --java "$(w "$OUT/gen")" \
    --min-sdk-version 29 --target-sdk-version 35 "$(w "$OUT/res.zip")"

echo "== java"
find "$SDL_JAVA" "$APP/java" "$OUT/gen" -name '*.java' > "$OUT/sources.txt"
sed -i 's|^/\([a-z]\)/|\1:/|' "$OUT/sources.txt"
javac -nowarn -source 11 -target 11 -encoding UTF-8 -cp "$(w "$ANDROID_JAR")" \
    -d "$(w "$OUT/classes")" @"$(w "$OUT/sources.txt")" 2>&1 | grep -v '^warning:\|^Note:' || true

echo "== dex"
find "$OUT/classes" -name '*.class' | sed 's|^/\([a-z]\)/|\1:/|' > "$OUT/classes.txt"
cmd //c "$(w "$BT/d8.bat") --release --min-api 29 --lib $(w "$ANDROID_JAR") --output $(w "$OUT/dex") @$(w "$OUT/classes.txt")"

echo "== package"
py -I - "$(w "$OUT/base.apk")" "$(w "$OUT/unaligned.apk")" "$(w "$OUT/dex/classes.dex")" \
    "$(w "$GAME_LIBS/libmain.so")" "$(w "$GAME_LIBS/librexgpu-xenos.so")" \
    "$(w "$SDK_LIBS/librexruntime.so")" "$(w "$NDK_LIBCXX")" <<'EOF'
import shutil, sys, zipfile, os
base, out, dex, *libs = sys.argv[1:]
shutil.copyfile(base, out)
with zipfile.ZipFile(out, "a", zipfile.ZIP_DEFLATED) as z:
    z.write(dex, "classes.dex")
    for lib in libs:
        z.write(lib, "lib/arm64-v8a/" + os.path.basename(lib))
print("  ", os.path.getsize(out) // (1024 * 1024), "MB unaligned")
EOF

echo "== align + sign"
"$BT/zipalign.exe" -p -f 4 "$(w "$OUT/unaligned.apk")" "$(w "$OUT/aligned.apk")"
if [ ! -f "$OUT/debug.keystore" ]; then
    keytool -genkeypair -keystore "$(w "$OUT/debug.keystore")" -storepass android -keypass android \
        -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 \
        -dname "CN=Android Debug,O=Android,C=US" >/dev/null 2>&1
fi
cmd //c "$(w "$BT/apksigner.bat") sign --ks $(w "$OUT/debug.keystore") --ks-pass pass:android --out $(w "$OUT/fifa08.apk") $(w "$OUT/aligned.apk")"
rm -f "$OUT/unaligned.apk" "$OUT/aligned.apk"
ls -la "$OUT/fifa08.apk"
