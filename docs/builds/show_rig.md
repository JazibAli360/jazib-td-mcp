# show_rig — master show rig (v1)

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60) (BP_io_router).

COMP `/project1/show_rig`, TD 2025.31550. Builder `builders/show_rig.py` (`build(layers=6, panel=True,
wire_sends=True)`, idempotent: re-runs `td_layer_mixer`'s handler, keeps par values, presets and cue rows), pure logic
`builders/show_rig_logic.py` (copied into `rig_logic`), runtime in the generated `runtime` DAT, offline tests
`test/test_show_rig.py` (13).

```python
ns = dict(globals()); exec(open('<repo>/builders/show_rig.py').read(), ns); ns['build']()
```

## What it is
- **Mixer** = `td_layer_mixer` (6 layers, 1080x1920): per layer Source / Opacity / Blend / Mute / Solo, Master,
  Masterfx. Bank = the lab looks (bank index = menu index): TP_test_pattern 0, LK_spectrum_glass 1,
  LK_projection_room 2, LK_typecore 3, BO_particles 4, BN_fluid2d 5, BN_cloth 6, BL_cloud_morph 7, BL_splat_render 8,
  LY_lyrics_feed 9, BJ_urdu_type 10, PV_previz_stage 11, DC_depth_cam 12, TL_timeline 13, AU_db_meter 14 (missing ones
  are skipped; edit `LOOKS` in the builder to change it).
- **Cook guard** (page Guard): the bank goes to the handler as Out TOP paths, so its own guard never switches a COMP;
  ours wakes what a visible layer (or live FX insert) needs. `Guardmode` owned (default: parks only what the rig woke),
  strict (parks every unshown bank COMP), off (hands off). `Protectlanes`: a COMP in `logs/active_lanes.json` is never
  parked; top-level COMPs never. Master is ignored on purpose: a master blackout keeps the shown looks warm. A tick
  re-syncs every 60 frames (T-100).
- **Master FX inserts by reference** (page FX): `fx_slot` = in1 -> palette -> trail -> strobe -> out1. Each
  `pre_<fx>` is sent to the lab FX COMP's `in1` by `/project1/lab/SR_send_<fx>` (Select TOP), `ret_<fx>` takes its
  `out1` back; `Fxpalette/Fxtrail/Fxstrobe` (needs Masterfx) switch the insert, wake the COMP and set its own source
  par (palette Source=input, trail Source=input, strobe Input=live; old value restored when off). COMP pars
  `Fx<k>comp` point at the COMPs. A live lane's FX COMP is not wired or touched.
- **Presets** (page Rig): `presets` table, row = `Preset` number, sources stored by look NAME. Preset change recalls
  (Autorecall) with `Presetfade` s / `Presetcurve`: opacities + Master fade, source/blend/mute/solo/FX switch at the
  start (a visible layer whose source changes cuts). `Store` writes the current state to row `Preset` (or appends,
  name `Storename`). Starting rows: 1 blackout, 2 test, 3 glass, 4 glass_particles, 5 fluid_cloud, 6 room_palette.
  Re-recalling the same number: pulse `Recall` (a par set to its current value fires nothing).
- **CQ_cuelist hook** (page Hooks): `Hookcq` on sets CQ's `Cuetable` to `rig_cues` (old value remembered) and wakes CQ;
  off restores and parks it if the rig woke it. Cue rows are kind `par`, target `/project1/show_rig:<Par>`: layer
  sources (numeric bank index; a menu par accepts its index), opacities (CQ fades them), `Preset` (look preset), Master.
  Demo cues: 1 Test card, 2 Glass in (2 s crossfade), 3 Particles add, 4 Preset glass_particles, 5 Blackout.
- **MIDI_mapper hook**: `Midiregister` adds 21 binds (ids `sr_*`, table `midi_binds`): CC `Midicc0`.. = L1..L6
  opacity (pickup), next CC = Master, notes `Midinote0`.. = mutes, +8 solos, +16 Masterfx, +17 Recall; bank
  `Midibank` (0 = always), channel `Midichannel`. Wakes MIDI_mapper (a parked COMP's modules do not compile);
  `Midiunregister` removes them and parks it again if the rig woke it. Every rig par is also bindable by hand
  (`td_midi_learn`).
- **Router hook**: `out1` -> `/project1/lab/SR_send_router` -> BP_io_router `in<Routerslot>`; `Hookrouter` sets the
  router's S1 kind local, O1 kind Syphon, O1 name **'jazib-td master'**, O1 source s1 and never touches `O1active`
  (stays OFF until the user's go-ahead). Off restores the router's old values.
- Controls: zkit panel `zk_controls` (66 knobs; Rig, Mixer, Layer1-6, FX, Guard, Hooks) in `controls_window`
  (Opencontrols) + the mixer's parameter panel `controls`. Status pars: Activesources, Cookingnow, Presetname,
  Rigstatus.

## Live verification (26 Oct 2026, TD 2025.31550, Rosetta; other lanes building)
- Build: `td_errors` empty, `td_layout check` ok (56 ops, 0 overlaps / back wires / intruders); checkpoint
  `output/checkpoints/show_rig/show_rig_20261026-184010.tox`; saved JazibTD_home.197.
- **Source switch cooks only that COMP:** L1 TP_test_pattern -> LK_spectrum_glass, 120 pulled frames: glass +335 child
  cooks, TP parked (owned) with 0, the other 13 bank COMPs 0.
- **Crossfade:** L1 glass 1.0 over, L2 TP 0.5 over: `l2_mix` = lerp(below, comp, 0.5), max abs error 0.0020 (= 0.5/255,
  8-bit). Unused layers 3-6: only their gate Switch cooks (pass-through), 60 pulled frames.
- **Cue GO:** Hookcq on -> CQ Cuetable = rig_cues; GO cue 1 set L1source 0 / L1 1 / L2 0; GO cue 2 (2 s linear):
  1.0 s after GO L1 0.506 + L2 0.494, end L1 0 / L2 1 (CQ log fade_start/fade_end), TP parked after the fade.
- **Preset:** Preset 4 (fade 1 s) -> glass 1.0 + BO_particles 0.8 add, BO woken. **FX:** Masterfx + Fxpalette +
  Fxstrobe -> both woken, Source=input / Input=live, ret tops 1080x1920 cooking; off -> both parked, pars back to auto.
- **MIDI:** 21 binds registered and bound; CC3 0/10/64/127/0 -> L3opacity 0 / 0.079 / 0.504 / 1 / 0; note 38 toggles
  L3mute; unregistered again, MIDI_mapper parked as before.
- **Cost / fps (2 live looks: glass + particles 65k, out1 pulled each frame):** 18 rig ops cook per frame (totalCooks
  deltas), their last cook times sum to ~1.2 ms CPU+GPU without `src4`;
  real 60.1 fps (wall clock, 300 frames), median frame 16.8 ms, 24 frames > 20 ms. BO_particles itself is the heavy
  item (its GPU time shows up in `src4`'s cook as a wait).
- Left: Preset 1 (blackout), hooks off except the router wiring, everything the rig woke parked, rig parked.

## Next
Per-layer FX sends; Take (fade a layer in, others out) and A/B bus; cue kind for named sources (needs a CQ kind or a
`L<n>sourcename` par); zkit menus for sources show the index; Syphon send test once the user says go.
