# helpers/bgremoval - Apple Vision person mask, CPlusPlus TOP (x86_64 + arm64 rebuild)

Built with the user's go-ahead (approved installs, 26 Oct 2026). **Not loaded into TD yet**; how to load and test:
`docs/builds/bg_person_mask.md`. Research + audit: `docs/research/AV_macos_background_removal.md`.

## Provenance

- Upstream: https://github.com/aaronmylespereira/AppleVisionMask-TouchDesigner (Derivative asset 73414, author
  aaronmylespereira), commit `4eafaefa1e893de5e07b3668048122a863e7af7d` (2026-03-11). Licence **MIT**, `src/LICENSE` (kept).
- `src/` = upstream files copied **unmodified** from `research_src/bgremoval_73414/repo/` (sha1):
  `AppleVisionMask.h` fb77198620d3, `AppleVisionMask.mm` fe946603e18f, `TOP_CPlusPlusBase.h` 87198b1c1626,
  `CPlusPlus_Common.h` ba9301fba29d, `Info.plist` 9c596e39eec5, `LICENSE` 90d8dcd8e160, `UPSTREAM_README.md` (= README.md) 4bbc18683875.
  The unused `MyBackgroundRemover.*`, the committed arm64 `build/` and the example `.toe` were not copied.
- SDK headers: upstream's `TOP_CPlusPlusBase.h` / `CPlusPlus_Common.h` equal TD 2025.31550's own
  (`/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/CPlusPlus/CPUMemoryTOP/`) except one trailing blank
  line: same `TOPCPlusPlusAPIVersion = 12`, `OP_CommonAPIVersion = 1`. So no API mismatch is expected on 31550.

## Build

`sh helpers/bgremoval/build.sh` -> `build/AppleVisionMask.plugin` (git-ignored). clang++ (Xcode, SDK 27.0), no cmake,
`-arch x86_64 -arch arm64 -mmacosx-version-min=12.0 -bundle -fobjc-arc -O2`, upstream `Info.plist`, ad-hoc signed.
15 warnings, all `-Winvalid-offsetof` from Derivative's stock header static_asserts (harmless, same in their samples).

Verified 26 Oct (offline):
- `file` / `lipo -info`: universal, `x86_64 arm64` (upstream release was arm64 only and cannot load in x86_64 TD).
- `otool -L` (both slices): Vision, CoreVideo, Foundation, CoreFoundation, libobjc, libc++, libSystem only.
- Exports (x86_64): `_FillTOPPluginInfo`, `_CreateTOPInstance`, `_DestroyTOPInstance`.
- `codesign -dv`: `flags=0x2(adhoc)`, identifier `com.derivative.AppleVisionMask`; `codesign -v` passes.
- Binary sha256 `11ff32b431454f42827eb251bdf219f26d0e154662c2cf6c764d5a1cb26f029b` (changes per rebuild; record the new one).
