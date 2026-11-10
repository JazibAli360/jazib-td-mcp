# dmx_patch: BK_dmx_patch fixture patch sheet + stage plot + previs + aim helper (26 Oct 2026, TD 2025.31550)

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60) (BK_dmx_patch).

`/project1/lab/BK_dmx_patch`. The second COMP of `docs/research/BK_dmx_artnet_sacn.md` (sections 2.8, 3.4-3.6 and the
"Previz of fixtures" row of section 7). Clean-room, our own code. It sits next to **BK_dmx_out** (`builders/dmx_out.py`)
and only **reads** it: BK_dmx_out's `patch` / `pixels` / `profiles_json` tables and its `out3` universes CHOP
(`u<flat>` x 512). The add / check / import / pixel-map pulses stay on BK_dmx_out (Patch page); this COMP adds what
it lacks: where each fixture hangs, what it is doing (previs from the bytes on the wire), a slot ownership map, a
printable patch sheet and moving-head aiming. **No limits** (user rule): no brightness cap, no warnings.

**Status: live-verified v1 on 31550 (26 Oct, T-90).** P1-P9, P11-P14 pass with the exact numbers below; P10 by eye (2 tiles drawn, layout 5 x 4 for Mapcount 16, clash fixture at 0.10 -> Conflicts 3 = slots, not fixtures). Fixes found live: '.' in CHOP names becomes '_' (out3 reads `mh1_pan`; BK_dmx_out resolve_inputs accepts both), tube rad1/rad2 swapped, window reopened after a rebuild, stage cells 6 decimals. Cost: state 0.6 ms, render 2.4-3.5 ms CPU + 0.36 ms GPU (over the 1 ms target; aa/res is the lever). Captures: front previs live + Pattern full, address map.

## Build (live lane, ~15 min)
BK_dmx_out must exist first (it is being built live; default path `/project1/lab/BK_dmx_out`).
```python
# td_exec
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/dmx_patch.py').read(), ns)
r = ns['build']('/project1/lab')          # or build('/project1/lab', dmx_path='/project1/lab/BK_dmx_out')
r                                          # {'comp', 'dmx', 'panel', 'notes', 'layout'}: notes = pars/menu entries 31550 lacks
```
Idempotent: ops reused by name, texts/pars/wires re-set, custom par values and the `stage` table kept. T-70 safe:
closes its own `controls_window` first, nothing destroyed directly (`safe_destroy` only, for a fresh Geometry COMP's
default torus and auto-docked GLSL DATs), panel rebuilt in place by zkit, pane never moved. No TOP read methods
(T-74/T-76). One compute GLSL pass, no chains (T-46/T-47). No functions in storage (T-67). Then: `td_errors` on the
COMP (frames >= 2), `td_layout check` (ok, no intruders / unboxed / box overlaps), the checks below.

## Files
| File | What |
|---|---|
| `builders/dmx_patch.py` | builder (`build(parent_path='/project1/lab', panel=True, dmx_path=None)`) |
| `builders/dmx_patch_logic.py` | pure logic, no `td` (copied into `patch_logic`); takes BK_dmx_out's `dmx_logic` as `D` |
| `builders/dmx_patch_rt.py` | TD runtime (copied into `patch_rt`): plan, cooks, pulses, expressions |
| `builders/glsl/dmx_patch_addrmap.glsl` | the address map, one compute pass (copied into `addrmap_compute`) |
| `builders/dmx_logic.py` | BK_dmx_out's logic, read only; the builder copies it into `dmx_logic` (self-contained COMP) |
| `test/test_dmx_patch.py` | 24 offline tests: `python3 -I -m unittest discover -s test -p 'test_dmx_patch.py'` |

## In / out
- No wired inputs: data comes from `Dmxcomp` (COMP par) and, optionally, `Univchop` (any CHOP of 512-sample universe
  channels, e.g. a DMX In CHOP listening to another console; set `Chanfmt` to its channel naming).
- `out1` TOP: previs render (`Resw` x `Resh`, default 1080x1920, rgba16float).
- `out2` TOP: address map (`Mapw` x `Maph`, default 1024x768): one 32x16-slot tile per sent universe, slot = owner
  colour x live value; conflicts solid red; first slot of each fixture has a white left edge; `Highlight` outlines.
- `out3` CHOP: aim helper, `<fixture>.pan` / `<fixture>.tilt` 0..1 while `Aimon` (wire it, merged with anything else,
  into BK_dmx_out `in2`; its compose splits them into 16-bit coarse/fine).

## Parameters (zkit panel shows all pages, pulse `Opencontrols`)
| Page | Pars |
|---|---|
| Source | Dmxcomp, Univchop, Chanfmt (`u{u}`), Autosync, Syncpatch, Prune, Checkpatch; read: Fixtures, Pixelsshown, Conflicts, Statems |
| Stage | Arrange (line / arc / grid / ring), Arrangeset (name pattern), Spanx, Height, Depth, Curve, Cols, Rowgap, Hang, Applyarrange; pixel wall Wallx/y/z/w/h; Pixmax |
| View | View (front / top / side / persp), Fit, Centerx/y/z, Viewsize, Orbit, Elev, Fov, Beams, Beamlen, Beamangle, Beamgain, Bodysize, Pixsize, Pixgain, Mingrey, Grid, Highlight, Resw, Resh |
| Aim | Aimon, Aimset, Targetx/y/z, Targetchop (tx ty tz), Calfixture, Calpan, Caltilt, Calibrate; read: Aimmissed |
| Sheet | Mapmode, Mapfirst, Mapcount, Mapcell, Mapw, Maph, Sheetname, Sheetdir (default `<repo>/output/dmx`), Exportsheet |
| Controls | Resetdefaults |

## Data
- `stage` (Table DAT, of record): `name x y z rx ry rz group pan_zero tilt_off pan_dir tilt_dir`. Metres, degrees,
  y up, audience +z. Rotation x first then y then z (same as `dmx_logic._rot`); hanging = rx 180. A fixture without
  pan/tilt shines along its mount axis (+y local, so hanging = down). Calibration columns feed `dmx_logic.aim`
  (pan01 = pan_zero + pan_dir * pan / range; tilt01 = 0.5 + (tilt_dir * theta + tilt_off) / range).
- Sync (`Syncpatch`, or automatic on every BK_dmx_out table change with `Autosync`): fixtures already in `stage` keep
  position + calibration; new ones are arranged and appended (a line continues to the right); fixtures no longer
  patched stay as "stale" until `Prune`.
- `sheet` (generated): `name profile mode chans univ wire net subnet universe addr end dmx node group x y z`, address
  order; `Exportsheet` writes `<Sheetdir>/<Sheetname>.csv` + `.md` (per-universe tables + issues).
- `report` (Text DAT): Sync / Arrange / Check / Calibrate / Export results.

## Network (stages)
Controls (zkit + window, `settings`, `status_tick`) | 1 Source (`univ_in` Select CHOP, `src_watch` DAT Execute on
BK_dmx_out's tables, `dmx_pars` Parameter Execute on its Colororder/Univfilter/Firstuniv, code DATs) | 2 Stage plot +
sheet | 3 Decode (`state` Script CHOP per fixture: tx ty tz s cr cg cb + rx ry rz sr sl br bg bb; `pix_pos` static;
`pix_col` per DMX cook) | 4 Previs (`fix_geo` spheres, `beam_geo` additive tube cones, `pix_geo` boxes, `floor_geo`
wireframe grid, `cam`, `render` -> `out1`) | 5 Address map (`owner` static Script CHOP -> `owner_tex`, `live_tex` of
`univ_in` -> `addrmap` compute -> `out2`) | 6 Aim (`aim` Script CHOP, per frame while Aimon -> `out3`).

## Live verification (31550; numbers precomputed offline with the same logic)
Test rig on BK_dmx_out (its Patch page): Profile `generic_mh_16bit_16ch`, Count 4, Fixname `mh`, Addfixture; Profile
`generic_rgb_3ch`, Count 2, Fixname `par`, Addfixture; Pixlayout strip, Pixw 50, Genpixels. Then build BK_dmx_patch.

| Id | Check | Pass |
|---|---|---|
| P1 | build returns, `td_errors` clean (frames >= 2), `td_layout check` ok, `notes` empty or only harmless misses | as stated |
| P2 | sync: `stage` has 6 rows; mh1..mh4 x = -6, -3.6, -1.2, 1.2; par1 3.6, par2 6.0; y 6, z 0, rx 180 | exact |
| P3 | `sheet`: mh1 0.001-16, mh2 0.017-32, mh3 0.033-48, mh4 0.049-64, par1 0.065-67, par2 0.068-70; Fixtures 6, Pixelsshown 50, Conflicts 0 | exact |
| P4 | `owner` CHOP: channels `o0 o1`; o0 slots 61-64 = 4, 65-67 = 5, 68-70 = 6; o1 slots 1-150 = 7 (pixels) | exact |
| P5 | Aimon, target (0, 0, 4): out3 mh1.pan 0.6043 tilt 0.6861, mh2 0.5778 / 0.6551, mh3 0.5309 / 0.6290, mh4 0.4691 / 0.6290; Aimmissed 0 | +-0.0001 |
| P6 | Round trip: Merge out3 + a Constant CHOP (`mh1.dimmer`..`mh4.dimmer` = 1, `mh1.white`..`mh4.white` = 1) into BK_dmx_out in2 (Pattern live). BK_dmx_out mh1 slots 1-16 = 154 177 175 161 0 255 255 255 0 0 0 255 0 0 0 0 | exact |
| P7 | Then decode in td_exec (CHOP read, no TOP read): `m = op('/project1/lab/BK_dmx_patch/patch_rt').module; s = m.L().decode(m.S['dec'], m.get_flat(op('/project1/lab/BK_dmx_patch/univ_in')))`; angle between `s['dir'][k]` and target - pos | < 0.05 deg for mh1..4 (offline: 0.0025 / 0.0007 / 0.0017 / 0.0017); beam rx/ry mh1 129.76 / 56.31, mh3 145.16 / 16.70, mh4 145.16 / -16.70 |
| P8 | Previs (td_window_capture / screenshot of out1, front view): 4 white beams converging on a floor point at x 0, two par bodies grey (dark), 50 pixel dots across the wall at y 3; then BK_dmx_out Pattern `full` -> every body lit, beams on all 6 | by eye + `td_inspect out1` mean rises |
| P9 | Views: front cam tz 43.96, top ty 46.96 rx -90 (upstage at the top), side tx 43.96 ry 90, persp (10.33, 10.52, 17.89) rx -20 ry 30; `Fit` (front) -> centre (0, 4.5, -0.5), Viewsize 13.8 | exact (cam pars read back) |
| P10 | Address map: 2 tiles drawn (Mapcount 16 -> layout 5 x 7 tiles), mh tiles hue-coloured with white starts, a forced overlap (add a par at 0.1 by hand) -> red slots + Conflicts 1; `Highlight mh2` -> yellow outline | by eye + Conflicts |
| P11 | Calibrate: Calfixture mh1, target (0,0,4), Calpan 0.52, Caltilt 0.61 -> report `pan_zero 0.415722, tilt_off -20.5378 deg`, `stage` row updated, P5 numbers for mh1 then match (0.52, 0.61) | +-1e-6 |
| P12 | Exportsheet -> `output/dmx/dmx_patch.csv` (header + 6 rows) and `.md` (one "Universe 0" table, "70 / 512 slots"); Checkpatch -> `patch + stage ok` | exact |
| P13 | Autosync: add one `generic_rgbw_4ch` on BK_dmx_out -> `stage` 7 rows, report `added 1`, sheet + owner follow without a rebuild | as stated |
| P14 | Rebuild with the controls window open: window closed + reopened, `stage` and par values kept, no crash (T-70) | as stated |

## Performance (60 fps rule; measure with the other lab COMPs parked, window open, T-72/T-73 real fps)
- Targets: `Statems` (state + pix_col Python) <= 0.5 ms on the 6-fixture rig, <= 2 ms on the stress rig; `render`
  <= 1 ms GPU at 1080x1920 aa4; `addrmap` <= 0.2 ms; `owner` / `pix_pos` 0 cooks per frame when idle (static);
  whole COMP <= 3 ms; project stays at 60 fps (cookRate untouched, T-64).
- Offline numbers (CPython native, not Rosetta): decode + instances + 50 pixels ~0.4 ms per frame including channel
  writes (fake-TD smoke); stress rig (64 movers + 28,900 px over 172 universes, Pixmax 4096 -> 3,613 dots, stride 8)
  decode + instances + pixel colours 0.2 ms before channel writes.
- Stress check live: BK_dmx_out Genpixels grid 170 x 170 -> Pixelsshown 3613, fps 60, Statems recorded.
- When nobody looks at out1/out2/out3 nothing here cooks (all chains are pulled by their Out ops); viewers on by rule.

## LIVE CHECK (facts only TD can settle)
- DAT Execute `dat` par: does an expression returning several space-separated DAT paths (another COMP's tables)
  watch them all? (The 31550 dump names the par `dat`; BK_dmx_out's builder sets `watch.par.dats`, which is not in the
  dump: worth a look in that lane.)
- Parameter Execute `op` par from an expression (`parent().par.Dmxcomp.eval()`) fires on that COMP's pars.
- Script CHOP channel names with a dot (`mh1.pan`) are kept as is (BK_dmx_out's in2 convention depends on it too).
- `OP.totalCooks` on the Select CHOP increments per cook (get_flat's per-frame cache key).
- Tube SOP: which end is `rad1`? The narrow end (0.02) must sit at the fixture (y 0 after ty 0.5); swap rad1/rad2 if
  the cones open toward the fixture.
- Instancing rotation: instance rx/ry with the default orders turns the +y cone like `Ry @ Rx` (P7/P8: hanging par
  beams point down, mh beams converge on the target). If they mirror, the instance rotate order differs from the
  COMP's xyz: fix in `dirs_to_euler`, not by hand.
- Instance colour on a Constant MAT (`instancecolormode` replace) colours each instance; additive blend
  (`srcblend`/`destblend` one, depth writing off) for the beams; `wireframeMAT` defaults draw grid lines.
- Geometry COMP with 0 instances: the `render` expressions switch it off (no stray un-instanced shape).
- CHOP to TOP rows: first channel = row 0 (bottom). The address map assumes row = universe index like BK_dmx_out's
  monitor; if tiles come out reversed, both shaders need the same flip.
- Camera `projection` menu names `ortho` / `perspective` (laser_path uses `ortho`).
- Exportsheet writes files from a pulse callback (plain Python file IO inside TD's main thread; small files).

## Not done / open
- No labels in the previs (Text TOP per label would break T-76's rule); names live in the sheet and the Highlight par.
- Beams are geometry, not light: no haze, gobos, zoom or shutter/strobe decoding (shutter channel ignored, read open).
- Colour model: additive emitters (R G B W A UV lime warm/cold white) + CMY filters on white; colour wheels show
  white. 16-bit colour channels decode at 16 bit.
- `Univchop` with a foreign channel order: the previs decodes by name (works), the address map still assumes the
  BK_dmx_out out3 row order.
- GDTF geometry, 3D models of fixtures, truss geometry, PV_previz_stage hookup (a later step: feed `state` into its
  beam rig) - FUTURE.
