#!/bin/sh
# Builds helpers/bgremoval/build/AppleVisionMask.plugin (universal x86_64 + arm64) from the unmodified upstream source
# in src/ and ad-hoc signs it. TD 2025.31550 runs x86_64 under Rosetta, so the x86_64 slice is the one it loads; the
# upstream release is arm64-only and cannot load there (docs/research/AV_macos_background_removal.md section 4).
#   sh helpers/bgremoval/build.sh            (from anywhere)
# Needs Xcode command-line tools (clang++, macOS SDK). No cmake, no network; writes only under build/.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/build/AppleVisionMask.plugin"
rm -rf "$OUT"
mkdir -p "$OUT/Contents/MacOS"
clang++ -std=c++17 -fobjc-arc -O2 -arch x86_64 -arch arm64 -mmacosx-version-min=12.0 -bundle \
  -I "$HERE/src" -o "$OUT/Contents/MacOS/AppleVisionMask" "$HERE/src/AppleVisionMask.mm" \
  -framework Vision -framework CoreVideo -framework Foundation -framework CoreFoundation
cp "$HERE/src/Info.plist" "$OUT/Contents/Info.plist"
codesign -s - -f "$OUT"
codesign -v "$OUT"
file "$OUT/Contents/MacOS/AppleVisionMask"
lipo -info "$OUT/Contents/MacOS/AppleVisionMask"
otool -L "$OUT/Contents/MacOS/AppleVisionMask"
shasum -a 256 "$OUT/Contents/MacOS/AppleVisionMask"
