# EssentiaTD install record (26 Oct 2026)

**Update 26 Oct 18:24:** bundles now live in `helpers/installs/disabled/Essentia/` (T-81) and load **by path** in a CPlusPlus CHOP (`plugin` par) with no restart and no dialog; measured in the scratch TD: all five ~0.8 ms at 60 fps, 1.3-2.3 s stall per load, BPM correct only with a per-song Bpmmin/Bpmmax (LEARNINGS T-99). Main TD: not loaded.

Installed with the user's go-ahead (approved installs, 26 Oct). TD was left running and NOT restarted: the plugins load
only at the **next TD start**. Nothing was loaded, run or tested in TD yet. Research and audit: `docs/research/AP_essentiatd.md`.

## What was installed

- Source: EssentiaTD **v2.0.3** (released 2026-09-16), `EssentiaTD-macOS.zip`
  sha256 `3c897b9f1fa592ce52cb5ce1bb1dd50a6c80c6c26d976f2d9ea9de0422cf9e3d`, unzipped at `research_src/essentiatd_75075/dl/x/`.
  Licence AGPL-3.0-or-later (fine for use on this machine; do not redistribute it inside a tox/build).
- Route: plain `cp -R` of the five bundles (no `.pkg`, no installer script, no sudo). The folder did not exist before.
- Destination (TD's per-user plugin folder, scanned once at startup; subfolders of any name are allowed, per
  https://docs.derivative.ca/Custom_Operators, checked 26 Oct):
  `~/Library/Application Support/Derivative/TouchDesigner099/Plugins/Essentia/`
- `diff -r` source vs destination: identical. `codesign -v` passes on all five (ad-hoc). xattrs: only
  `com.apple.provenance`, no `com.apple.quarantine`, so no Gatekeeper "Open Anyway" prompt is expected.

| Bundle | Binary sha256 | Archs |
|---|---|---|
| EssentiaLoudnessCHOP.plugin | `d512ab9d7c9985258de508ce0ebc3240a1daddfd55049fbe1e2faec0e911bfac` | x86_64 arm64 |
| EssentiaRhythmCHOP.plugin | `7a50b8d2184e07dcd6811060667a994e8e2a1f18354a96f235af8a48e13b8ad9` | x86_64 arm64 |
| EssentiaSpectralCHOP.plugin | `4fe548634ad509ca02c24cb0875b81318f5b8e5e128b67d3b7434ffc56d640a0` | x86_64 arm64 |
| EssentiaSpectrumCHOP.plugin | `d22c0dd2bcc5e01a47d64a20360b65649d60d09a93cca85d9dc985e859042d68` | x86_64 arm64 |
| EssentiaTonalCHOP.plugin | `8e06fde1e19042f74d6bc02ce4a89f0f3cef7ca52abbdcb4b26c58c7f600bc19` | x86_64 arm64 |

Binary path inside each bundle: `Contents/MacOS/<BundleName without .plugin>`. TD 2025.31550 is x86_64 (Rosetta), so it
will load the x86_64 slice.

Re-check: `cd ~/Library/Application\ Support/Derivative/TouchDesigner099/Plugins/Essentia && shasum -a 256 */Contents/MacOS/*`

## Note: system-wide folder

This folder is read by **every** TD start, so after the next restart the five CHOPs are registered in every project,
including `JazibTD_home.toe` (registration only; nothing cooks until an Essentia CHOP is created). If the user wants them
out of the main project, the alternative is a project-local `Plugins/` folder next to a scratch `.toe` (also scanned,
same docs page); then move the folder there.

## Post-restart test recipe (scratch project only, a later lane, TD build 31550)

1. After the user's next TD restart (never restart TD from a lane) and the bridge reconnect: `td_errors` and
   `td_status` clean; open/create a **scratch** project (not the show toe).
2. Probe registration (read-only): in `td_exec`, try creating each op type in a scratch COMP and list its pars, e.g.
   look for the Essentia types in the OP Create dialog (Tab > CHOP: "Essentia Spectrum / Spectral / Tonal / Rhythm /
   Loudness"). Record the exact Python type names + par names in LEARNINGS (T-nn) before writing any typed tool.
   If they are missing: check TD's textport/startup log for a load error ("wrong architecture", API version) and record it.
3. Chain: Audio File In (a known 44.1 kHz track, then a 48 kHz one) -> Math CHOP (Combine Channels = Average, mono) ->
   each analyser in Realtime mode. Rhythm: window >= samples per cook (48 kHz / 60 fps = 800; README default 1024 is OK
   at 60 fps; warns if smaller). Tonal: FFT 4096.
4. Read `td_errors`, `td_perf` cook ms per CHOP and project fps (60 fps target, <= 3 ms per COMP). Compare bpm/key
   against the known tracks. Batch mode once on the same file (background thread).
5. Verdict -> LEARNINGS T-nn + `docs/research/AP_essentiatd.md` section 3; FUTURE/typed-tool ideas in AP section 5.

## Rollback

Quit TD (the user), `rm -rf ~/Library/Application\ Support/Derivative/TouchDesigner099/Plugins/Essentia`, start TD.
Nothing else was changed.
