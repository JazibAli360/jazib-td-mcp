#!/bin/sh
# Builds helpers/vision_bridge/build/jzb_vision_bridge (arm64 only, see README "Why arm64 only") and ad-hoc signs it.
#   sh helpers/vision_bridge/build.sh            (from anywhere)
# Copied from td-port/camera_bridge/build.sh (sha1 b8ff73b62c9a), renamed for this copy. Needs Xcode command-line
# tools (clang++, macOS SDK). No network; nothing outside this folder is read or written.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$HERE/build"
clang++ -std=c++17 -fobjc-arc -O2 -Wall -Wextra -Werror -arch arm64 -mmacosx-version-min=14.0 \
  -o "$HERE/build/jzb_vision_bridge" "$HERE/src/jzb_vision_bridge.mm" \
  -framework CoreML -framework Vision -framework CoreVideo -framework ImageIO -framework CoreGraphics \
  -framework UniformTypeIdentifiers -framework Foundation
codesign -s - -f "$HERE/build/jzb_vision_bridge" 2>/dev/null || true
file "$HERE/build/jzb_vision_bridge"
shasum -a 1 "$HERE/build/jzb_vision_bridge"
