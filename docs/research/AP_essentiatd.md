# AP: EssentiaTD (Darien Brito) read for jazib-td (26 Oct 2026)

Research only. Nothing was loaded into TouchDesigner, no binary was run, nothing was installed, no pip. Tags: [PAGE] derivative.ca
asset 75075, [REPO] files in the clone, [BIN] `file`/`lipo`/`otool -L`/`nm -u` on the released binaries, UNVERIFIED = needs a probe.
Page: https://derivative.ca/community-post/asset/essentiatd/75075 (posted 23 Jul 2026; no forum thread listed on the page).
Source: https://github.com/DarienBrito/EssentiaTD, HEAD `c050b40` (16 Sep 2026), latest release **v2.0.3** (16 Sep 2026).
Local: `research_src/essentiatd_75075/repo/` (shallow clone, 7.9 MB), `dl/EssentiaTD-macOS.zip` (28 MB, v2.0.3 release asset),
`dl/x/` (the zip unzipped, five `.plugin` bundles, never opened by TD), `api_latest.json` (GitHub release metadata).
Release assets: `EssentiaTD-macOS.zip`, `EssentiaTD.pkg` (28.4 MB), `EssentiaTD-Windows.zip`, `EssentiaTD-Setup.exe`. Only the zip was downloaded.

## 1. What it is

Five **native C++ CHOP plugins** (TD C++ CHOP API, `CHOP_CPlusPlusBase.h`) that link the **Essentia** library (UPF MTG)
statically (`libessentia.a`, whole-archive, KissFFT backend, libsamplerate 0.2.2). Not Python, not a subprocess, not essentia pip.
Each plugin is one `.plugin` bundle (macOS) or `.dll` (Windows) that registers one CHOP in the OP Create dialog.
[REPO README, src/CMakeLists.txt, ci/]

| CHOP | Features (channel names in [REPO] where seen) |
|---|---|
| Essentia Spectral | MFCC (`mfcc`), mel bands (`mel`), centroid, flux, rolloff, contrast (`spectral_contrast`), HFC, complexity, optional PCA |
| Essentia Tonal | pitch (YinFFT, `pitch`, `pitch_confidence`, note name), HPCP chroma (`hpcp`), `key` + `key_strength` (key profile par), dissonance, inharmonicity |
| Essentia Rhythm | onset detection (hfc / complex / flux / melflux / degara methods), BPM, beat phase, `beat_confidence`, ticks |
| Essentia Loudness | EBU R128 loudness (momentary/short/integrated), RMS energy, zero-crossing rate |
| Essentia Spectrum | linear FFT magnitude + phase, `fftSize/2+1` bins (513 at 1024), raw data for GLSL/DSP, not a display |

Modes (all four analysers): **Realtime** (per cook, 1 sample per channel, ring buffer, latest window) and **Batch** (whole file on a
background thread, N samples = one per frame, Compute pulse or Autocompute with audio fingerprint). Mono only (sum L+R with a
Math CHOP, Average; batch reads channel 0 of a stereo input and warns). v2.0 is a breaking change: each analyser takes raw audio and
runs its own FFT (Spectrum CHOP in front now errors). Notable measured notes in the README: Tonal needs FFT 4096 at 44.1/48 kHz
(auto) and a wrong key can look confident; Rhythm realtime window 1024 default and onset F1 collapses if
`window < sampleRate/fps` (30 fps at 48 kHz = 1600 samples per cook); batch BPM resamples to 44.1 kHz.

## 2. Platforms, build, licence, audit

- **OS/arch (page + README headline):** Windows x64, macOS "Apple Silicon". **The real mac binaries are universal.** [BIN] all five
  `Contents/MacOS/*` are `Mach-O universal binary with 2 architectures: [x86_64] [arm64]` (`lipo -info`: `x86_64 arm64`); CI sets
  `MACOS_ARCHS="arm64;x86_64"` (build.yml, comment: safe because Essentia is built from source with KissFFT, no arch-specific lib).
- **TD builds:** no minimum stated anywhere ([PAGE] "TouchDesigner099" folder only, which is the macOS plugin folder name for all
  099-lineage builds incl. 2025). The plugins resolve TD symbols at load time from the host. The repo ships the SDK headers
  `CHOP_CPlusPlusBase.h` / `CPlusPlus_Common.h` and a test toe `td/EssentiaTester.1.0.161.toe` (a 1.0.161 TD-era build number is
  not a TD version). UNVERIFIED on 31550; the C++ CHOP API has been stable for years, so a load failure would be a bundle-level one.
- **Deps** [BIN] `otool -L`: only `/usr/lib/libc++.1.dylib` and `libSystem.B.dylib`. No frameworks, no Python, no ffmpeg.
- **Signature** [BIN]: ad-hoc (`flags=0x2(adhoc)`), bundle id `com.essentia-td.` (empty tail), not notarised. The pkg installs with
  no quarantine flag; the zip route triggers Gatekeeper "Open Anyway" per bundle (README). Per the host-install rule this repo does
  not gate on signatures; the real gate is "native code runs inside the TD process" (below).
- **Licence:** AGPL-3.0-or-later (repo `LICENSE`, page). Essentia itself is AGPL-3.0 [general knowledge]; vendored headers + patches
  in `ci/essentia-patches/`. Licences are not a blocker for research; if we ever *distribute* a build or tox that bundles the plugin,
  AGPL source obligations apply. Using the plugin on the user's own machine is fine. Do not copy its source into jazib-td.
- **Audit** [REPO grep + BIN]: no `system/popen/exec/fork/curl/http/socket` in `src/*.cpp` or `src/Shared`; `nm -u` on the Rhythm binary shows
  only `__throw_system_error` among network/process-looking imports. No Python, no eval, no file writes other than reading the input
  CHOP. Batch mode runs a worker **thread inside TD** (no subprocess). Essentia's own logger is disabled at init. `installer/macos/build-pkg.sh`
  is plain `pkgbuild` (`require-scripts="false"`, no postinstall script, `enable_currentUserHome`). Residual risk: unsigned native code in
  the TD process (a bug can crash TD; TD does not sandbox plugins), and we have not read all of the C++ line by line (`UNVERIFIED`).
  The `.toe` files in `td/` were not opened.

## 3. Mac/Rosetta feasibility verdict

**Live (26 Oct, 31550, scratch TD, T-99):** loads by path at runtime; Rhythm 0.19 ms, all five 0.8 ms; 128/100 BPM test tracks exact after ~10 s; a real song reads 1.5x unless the BPM range is narrowed (then 88 vs 88.15). Go, with loads before doors and a per-song range.

**Feasible, yes.** Our TD 2025.31550 runs as x86_64 under Rosetta, and the plugin binaries carry an x86_64 slice, so TD loads that
slice (a TD arm64 build would load the arm64 slice). The page and README's "Apple Silicon" wording understates the real binary; the
x86_64 slice is shipped because CI builds `arm64;x86_64`. Remaining UNVERIFIED items, all settled only by a gated live test:
(1) 31550 accepts the bundles (SDK ABI, "Open Anyway" prompt if a zip install is used); (2) Rhythm realtime onset quality at the show's
cook rate and sample rate (the README's own warning); (3) the licence tier: custom C++ operators require a TD licence that allows
plug-ins (UNVERIFIED which tiers; ask before the test); (4) the plugin folder is read once at TD start, so TD must be restarted
and the MCP bridge re-opened after install.

## 4. What our native-CHOP AC_audio can adopt without EssentiaTD

AC_audio today: Audio Device In / file -> lowpass band, level, kick trigger, 256-bin spectrum TOP. Natively in 31550 (no plugin):

| Essentia feature | Native route | Quality vs Essentia |
|---|---|---|
| RMS / level | Analyze CHOP (RMS) or Math + Lag | same |
| Band energies (sub/low/mid/high) | Audio Filter CHOPs (lowpass/bandpass) -> Analyze RMS -> Lag; or Audio Spectrum CHOP -> Select ranges -> Analyze | good; this is what AC_audio does |
| Spectrum | Audio Spectrum CHOP (perceptual, log) or Math/Resample of FFT; keep the 256-bin TOP | native is the better display (the README says so) |
| Spectral centroid | Audio Spectrum CHOP x frequency index (Script/Math/Expression CHOP: sum(i*mag)/sum(mag)) | same maths, a few CHOPs |
| Spectral flux | Audio Spectrum, Delay by one cook, Subtract, positive-part (Math range), Analyze Sum | same maths; first-frame bug in Essentia is a hint to zero frame 0 |
| Rolloff | cumulative Sum of spectrum (Limit CHOP / Accumulate via Math) -> first index over 0.85*total (Script CHOP or CHOP Execute Python) | easy in a 20-line Script CHOP |
| Zero-crossing rate | Math sign -> Delay -> Subtract -> abs -> Analyze avg | same |
| Onset | flux (or HFC = sum(i*mag^2)) -> Trigger/Threshold with adaptive threshold (Lag of mean * k) + hold | simple version good for kicks/snares; Essentia's multifeature is better for noisy mixes |
| Kick trigger | already in AC_audio | fine |
| BPM / beat phase | tap-tempo from onset Trigger CHOP + Count/Timer; or Ableton Link (td_link, AJ) or the Resolume clock; Rhythm CHOP is the only real auto-BPM here | native BPM from onset history = Script CHOP with inter-onset histogram (doable, ~40 lines, weaker on tempo changes) |
| Mel bands / MFCC | mel filterbank = a matrix multiply of the Audio Spectrum vector by a precomputed table (Script CHOP + numpy is NOT assumed in TD: TD's python has numpy, check `import numpy` first); DCT for MFCC the same | doable; MFCC is rarely needed for visuals |
| Chroma (HPCP) / key / pitch | fold FFT bins by pitch class (12 bins) in a Script CHOP; key = correlate with Krumhansl profiles; pitch = peak pick or autocorrelation | rough; Essentia's HPCP/YinFFT/key are clearly better. This is where the plugin earns its place |
| Loudness LUFS | K-weighting biquads (Audio Filter CHOP x2) -> mean-square over 400 ms -> 10*log10 | doable; not gated by the plugin |

Recommendation: keep AC_audio native for the show (bands, level, kick, spectrum; zero native code risk). Add cheap native
extras on demand: centroid, flux, onset, ZCR, rolloff. Adopt the plugin only if the user wants BPM auto-detect, key/chroma-driven
colour, or MFCC/timbre analysis; that is a live-rig question (see section 7).

## 5. Ideas for jazib-td (not built, nothing registered)

- `td_audio_features {path, features:[centroid,flux,rolloff,zcr,onset]}`: builds the native chains above inside AC_audio as optional
  extra outputs behind a `features` custom page (default off, no cook cost when off). Idea only.
- `td_essentia_probe` (read-only): after the user installs the plugin, list op types containing "Essentia" in the OP Create list and
  return their parameter names, so the typed tool can be written from evidence rather than from the README. Idea only.
- When the plugin is present, `td_live_audio` could add an `analysis:"essentia"` option that wires a Math (average) -> four analysers
  next to AC_audio and exposes bpm / key / onset on the COMP's custom page. Gate: plugin probe true.
- Lessons to copy into any native version: mono-sum first; `startIndex=0`-style fixed output (avoid ever-growing sample ranges in Merge);
  window >= samples per cook; do not trust key_strength as a quality signal; silence holds the last tempo at confidence 0.

## 6. Install recipe (GATED: needs the user's explicit OK, then TD closed)

Do not run any of this without the go-ahead. It writes only under the user's Library, no sudo. Prefer the **zip, manual copy** over the
pkg: we already hold the verified zip, no installer script runs, and it keeps the install to one reversible folder.

1. User OK + user closes TD (and the MCP bridge) saving the project; note the project path.
2. Copy the five bundles from `research_src/essentiatd_75075/dl/x/*.plugin` to
   `~/Library/Application Support/Derivative/TouchDesigner099/Plugins/Essentia/` (create the folder; `cp -R`). If the folder
   exists, stop and ask.
3. If Gatekeeper blocks a bundle on first load: System Settings > Privacy & Security > Open Anyway (GUI only, user does it), or the user
   decides on `xattr -dr com.apple.quarantine` for that folder. The zip we downloaded via curl carries no quarantine attribute (check
   with `xattr` first); this is the user's call, not a gate on provenance.
4. User starts TD; the Tab menu should list "Essentia Spectrum / Spectral / Tonal / Rhythm / Loudness".
5. Test in a **scratch project, not the show toe**: Audio File In (a 44.1 kHz file; also a 48 kHz one) -> Math (Combine Channels =
   Average) -> each analyser, Realtime. Read `td_errors` and `td_perf` before and after. Expect Rhythm to warn if the window is
   smaller than samples per cook. Compare bpm/key against known tracks. Record the verdict as a LEARNINGS T-nn.
6. Rollback: quit TD, delete `.../Plugins/Essentia/`. Nothing else changes.
7. Only then the live check on the mic/BlackHole path (mic permission, user OK) and the cook-time budget on the show rig.

## 7. FUTURE.md-style gating notes

| Feature | Needs build | Status | Where | How to test when available |
|---|---|---|---|---|
| EssentiaTD CHOPs (BPM, onset, key, HPCP, MFCC, loudness) in AC_audio | 31550 (universal x86_64 slice exists; unverified load) | idea only, install needs the user's OK | docs/research/AP_essentiatd.md 6 | scratch project, recipe 6 steps 1-5 |
| `td_essentia_probe` (list Essentia op types + pars) | 31550 + plugin installed | idea only | AP 5 | after install: op list contains "Essentia" |
| Native extras (centroid/flux/rolloff/ZCR/onset) in AC_audio behind a `features` page | any | idea only | AP 4-5 | td_perf shows no cook cost when off |
| Mic/loopback realtime Rhythm quality at show cook rate | 31550, mic permission | unverified | AP 3 | live rig check with the user present |

Open questions for the user: (1) is auto BPM / key detection wanted for PF26 (the Resolume clock or Ableton Link may already give
tempo)? (2) OK to install the plugin folder into `~/Library/Application Support/Derivative/TouchDesigner099/Plugins/` for a scratch test?
(3) does the user's TD licence tier allow third-party C++ operators (UNVERIFIED)?
