# Drop-in audit, 28 Oct 2026 (TD 2025.31550)

User rule (28 Oct): "generally all comps are like that - that i can add it to different scenes and still have it
work". A COMP is a **drop-in** when its library .tox loaded into ANY COMP of ANY project works: internal references
relative, shared systems optional, scene inputs through OP pars / inputs, copies independent.
Tool: `tools/dropin_audit.py` (offline + TD), tests `test/test_dropin_audit.py`.

## Method
- **Static (all 70 library COMPs, offline, no TD, T-262):** `python3 tools/dropin_audit.py library library
  <scratch>/expand` copies each `library/<X>/<X>.tox` into the scratchpad and runs TD's own `toeexpand` on the copy,
  then scans the text tree: `.parm` (constants, active expressions / binds; stored-but-inactive expressions apart),
  `.text` (DAT text, Python tokenized: code / embedded-in-a-string / comment), `.table` (binary length-prefixed
  cells). Skipped: annotate-box insides, zkit text-spec tables (`zk_ts*`, `zk_hs*`), display text pars, `.n`
  comments, `.cparm` labels. Every absolute path is classed against the COMP's build path (`meta.json` source):
  **self** (inside it), **shared** (effectors, AU_features, FG_fps_governor, hotkeys, CQ_cuelist, TL_timeline,
  CS_cam_sequencer, palette), **scene** (another /project1 op), **unknown**, plus **escape** (`parent(n)` /
  `op('../..')` climbing above the COMP). ~1.5 min for the library.
- **Live (b3, 31550):** every library .tox loaded into `/project1/dropin/host_<n>` (a Base COMP, not `lab`) as
  `<X>_drop`: parked on load, un-parked 600 frames later, Out TOP force-cooked 60 frames, then errors / warnings /
  Status / Out non-black read, parked, host destroyed (PX-sized ones kept parked). Device / network COMPs (audio,
  DMX, MIDI, camera, Spotify, MCP, Blender) were loaded and audited but never cooked. Pass 1: 69 COMPs, 0 crashes.
  Pass 2: the 14 effectors consumers with `/project1/effectors` renamed away (11 done; b3 bus error on item 12, the
  82nd load of the session, T-262; BL_cloud_morph / BL_splat_render / PX_pointfx not run without effectors).
- The live in-TD audit (`audit(comp)`) and the offline one agree (checked on GEN_clone and PX_pointfx).

## Findings
1. **Expressions and DAT code are already relative** in every COMP (builders use `me` / `parent()`); 1 self
   reference in DAT text in the whole library (Effectors `eff_logic`).
2. **Self references are constant OP-par / table values** that builders set from `x.path` (TD stores an OP object as
   its absolute path), 442 in all:
   - `controls/zk_cfg` row `target` (185) and `controls_window.winop` (176): written by `builders/zkit.py`
     (`('target', c.path)`, `('winop', wop.path)`); zkit's runtime resolves `op(target)` and its refresh finds the
     panel by `zk_cfg target == c.path`, so a relative target needs a zkit-side change (zkit lane).
   - Parameter Execute DAT `op` targets (`pulses`, `par_exec`, `still_pexec`, `drive_pexec`, `pexec`, `hit_pexec`,
     `hits`: 58): **in a dropped copy the copy's pulses and par callbacks watch the ORIGINAL COMP** (same project)
     or nothing (another project). Builders: `pe.par.op = c` / `c.path` / `m.path`; the FX racks already use `'..'`.
   - MX `vc_sop#.sop` + `vc_slots` table, QC `src#.top` + `sources` table, ZC `binds` table, Effectors
     `paint_step.array0chop`: per-COMP.
3. **Shared systems are optional already:** effectors consumers bind through guarded expressions (`eff_in` falls
   back to `eff_none`, `sel_expr` guards None); all 11 consumers tested cook with 0 errors with no /project1/effectors
   (BO_particles keeps its 1 warning: its AC_audio Chop default). CS `Auop` / `Tlop`, PX `Audiosrc` / `Govop` are OP
   pars. No Links page is needed for these; the path stays the default name of the system.
4. **Scene refs:** mostly OP-par defaults to other lab COMPs (BO_particles / GEN_sim / GEN_pattern `Hitchop` ->
   AC_audio, FX_glitch `Pointchop` -> FX_track, FX_scope `Pathchop`, BK_dmx_patch `Dmxcomp`, GEN_interactive
   `Faceop`, BL_splat_render `Splatfx`): fine as defaults when missing-safe (BO_particles warns). Hand fixes:
   FX_film's depth expressions read `/project1/lab/DC_depth_cam/depth` directly (should go through an OP par);
   CQ_cuelist `log` / `resolved` tables hold `/project1/show_rig` (run data); ZC `zctl_ext` names
   `/project1/show/tools/autoUI`.
5. **Unknown:** `op('/jazib_mcp/handlers')` fallbacks (PX px_rt, TL TimelineExt / tl_record, CS cs_rt, Effectors
   eff_rt) exist only in a TD with this MCP installed; BX_blender_scene `/root/Stage_Deck/stage_deck` (a Blender
   object path, not an op); the rest are doc examples.
6. **Does it work when dropped (69 COMPs + Effectors):** 48 render (Out non-black, 0 errors), 15 device / network COMPs load clean (not cooked), 4 cook clean with a black Out, 2 have errors. To check by hand: LK_spectrum_glass (`glass`
   value expression: `float(None)`), TL_timeline (5 errors inside its zkit annotate boxes: `annotateCOMP has no
   attribute 'Editing'`; the drop also kept the name `TL_timeline`), out black after 60 frames: BJ_urdu_type,
   BN_fluid2d, FX_track, POP_meshwarp (likely need an input / interaction; not yet confirmed).

## Fixes (done 28 Oct, b3 31550; commits febc785 .. 08ced81)
- **Builders now emit relative references** (`test/test_dropin_builders.py` scans every builder):
  - Parameter Execute targets `'..'` in 19 builders (`x.par.op = c.path` stored an absolute path: a dropped copy's
    pulses / callbacks watched the ORIGINAL). Assigning an OP object (`= c`) stores `..` and was already fine.
  - zkit: `zk_cfg` target = `..` per panel level, `controls_window.winop` = the panel's name; `zk_rt.host()` and
    `refresh_panel` resolve both forms (old absolute panels keep working); a copy whose target still names the
    original is found by its Zkit-page owner (`_zk_owner`).
  - MX vertex cache `vc_sop#.sop` + `vc_slots` relative to the COMP (a scene geo outside stays absolute).
  - FX_film dof: `Depthop` COMP par (empty: the lab DC_depth_cam when present, else the focus plane).
  - `/jazib_mcp/handlers` fallbacks (PX px_rt, effectors eff_rt, TL tl_record) degrade without the MCP (plain destroy;
    Record says it needs the MCP).
  - Stored stamps from another session: BJ_urdu_type re-anchors a future `jz_t0`; POP_collide / CV_person_mask /
    FX_motion_trail ignore a stored frame later than now (they reset every frame in a copy).
  - POP_meshwarp shows the stored webcam clip while in1 is not wired; BN_fluid2d has a Status (idle: what to wire).
- **`tools/dropin_audit.py`** (TD side; loaded with `ns = dict(globals()); exec(open(<repo>/tools/dropin_audit.py)
  .read(), ns)`):
  - `dropin_fix(comp, dry, report)`: self OP pars -> relative (each checked with the par's OWN eval: Window winop
    resolves from the parent network = a bare name, Parameter Execute `..` = its parent; T-263), self expressions /
    DAT text -> `me.parent(k)` forms, In CHOP channel reads guarded (LK_spectrum_glass `float(None)`), stale-frame
    guard, frozen demo clip (play off + Input test) back to play + auto, blank annotate clone repaired (TL), zk_cfg
    target once the panel runtime is new, MX vc_slots. Open Window COMPs are skipped (close first, T-70).
  - `dropin_main(comp, dry)`: `dropin_fix(report=False)` + per-COMP extras, each guarded: urdu_rt / BN_fluid2d texts
    only when they are exactly the pre-drop-in sha1; POP_meshwarp `demo_upgrade`; FX_film `depthop_upgrade`.
  - `audit(comp)`, `profile_audit(comp, budget_s)`; offline `python3 tools/dropin_audit.py library ...`.
- **Proofs on b3 (fresh parked library loads, one step per exec):** GEN_points (25 OP pars, 0 errors, renders; a
  zkit refresh of a module panel -> target `..`, host = the copy), LK_spectrum_glass (0 errors, renders), TL_timeline
  (50 errors -> 0), BJ_urdu_type (renders), FX_track (renders), POP_meshwarp (fresh build + in-place upgrade render
  the clip), BN_fluid2d (Status idle -> running with BPM Internal), MX_prox_material (vertex cache reads relative
  names), FX_film (Depthop -> its depth TOP); in place: PX_pointfx (2 winops, presets sha1 unchanged, second run 0
  changes) and 13 more lab COMPs (no revert, no error). Frame cost of `dropin_fix(report=False)`: 12 ms - 1.6 s
  (GEN_pattern); the re-audit is 0.3 - 3 s (GEN_points), so it runs in its own exec.
- **Hand / other lanes, not changed:** QC_mcp_checks tables (an MCP-only tool), ZC_control_surface `binds` (the
  user's bind targets; demo rows point at its own test ops), CQ_cuelist `log` / `resolved` (run data),
  BO_particles / GEN_sim / GEN_pattern `Hitchop` defaults to `/project1/lab/AC_audio/out_ctl` (an OP-par default:
  BO_particles warns when AC_audio is missing), the Effectors COMP itself (the shared system at its contract path).

## Main recipe (coordinator runs it; one exec per line, a few seconds apart, `# jtd:nofollow`, pane on /project1)
Save main first. Close the controls windows of the COMP (open windows are skipped and reported). Never a
project-wide scan (T-255): every call is scoped to one COMP.
```
# load (every exec):  ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/tools/dropin_audit.py').read(), ns)
1 dry : ns['dropin_main'](op('/project1/lab/<X>'), dry=True)
2 real: ns['dropin_main'](op('/project1/lab/<X>'), dry=False)
3 check (later exec): a = ns['audit'](op('/project1/lab/<X>')); a['summary'], [(r['op'], r['kind'], r['par'], r['path']) for r in a['refs'] if r['cls'] == 'self']
```
Expected after step 2: `self` lists only `controls/zk_cfg` rows (and QC / ZC tables) until the zkit refresh; after
the refresh (new zk_rt + target `..` + relative winop): no self refs. A second step 2 returns no changes.
COMPs (from an offline audit of a copy of main .1394; CS_cam_sequencer v2 is already clean, CS_cam_sequencer_v1
skipped): AU_features BJ_urdu_type BK_dmx_patch BL_cloud_morph BL_splat_render BN_cloth BN_fluid2d BO_particles
BP_io_router CQ_cuelist CV_person_mask DC_depth_cam FG_fps_governor FT_face_track FX_analog FX_destroy FX_film FX_glass
FX_glitch FX_motion_trail FX_palette_map FX_retro FX_scope FX_strobe FX_stylise FX_synth FX_track FX_trans GEN_clone
GEN_interactive GEN_pattern GEN_points GEN_sdf GEN_sim GN_physarum GN_reaction_diffusion LK_projection_room
LK_spectrum_glass LP_laser_path LY_lyrics_feed MX_prox_material POP_branching POP_caustics POP_collide POP_crack3d
POP_fillbody POP_linegrowth POP_meshwarp POP_rd3d POP_terrain POP_tree POP_tubes PX_lines PX_pointfx PX_pointfx1
QC_mcp_checks TP_test_pattern ZC_control_surface ZK_controls_kit (zkit refresh only: AC_audio AU_db_meter LK_typecore
PV_previz_stage TL_timeline). PX_pointfx1 note: its `PX_lines/controls_window` opens the ORIGINAL PX_pointfx's PX_lines
panel today; step 2 points it at its own. PX_pointfx / PX_pointfx1 also: rerun `px.presetsrc_upgrade` (staged) for
px_rt's no-MCP fallback (`changed: [px_rt]`, presets kept). Then the zkit refresh across all panels, then step 3
again, then re-export the library from main for every COMP step 2 changed.

## Table (static refs = code context only, builtin excluded)
| COMP | works when dropped? | self refs | shared | scene | unknown | fix |
|---|---|---|---|---|---|---|
| AC_audio | loads clean (device / network: not cooked) | 1 (zk_cfg table) | 0 | 0 | 0 | Z: zk_cfg target (zkit lane) |
| AU_db_meter | loads clean (device / network: not cooked) | 1 (zk_cfg table) | 0 | 0 | 0 | Z: zk_cfg target (zkit lane) |
| AU_features | loads clean (device / network: not cooked) | 3 (par_exec op, controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| BJ_urdu_type | cooks clean, out black | 3 (par_exec op, controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| BK_dmx_out | loads clean (device / network: not cooked) | 0 | 0 | 0 | 0 | none |
| BK_dmx_patch | loads clean (device / network: not cooked) | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| BL_cloud_morph | yes; without effectors: not run (T-262) | 3 (par_exec op, controls_window winop, zk_cfg table) | 8 (eff_in chops x2, pcmat vec15valuex, ...) | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| BL_splat_render | yes; without effectors: not run (T-262) | 3 (par_exec op, controls_window winop, zk_cfg table) | 9 (eff_in chops x2, splat_rt dat, ...) | 1 (. Splatfx) | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane); S: scene default in an OP par (ok if missing-safe) |
| BN_cloth | yes; without effectors: yes | 2 (controls_window winop, zk_cfg table) | 3 (eff_in chops x2, eff_colliders_callbacks dat) | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| BN_fluid2d | cooks clean, out black; without effectors: clean, black | 2 (controls_window winop, zk_cfg table) | 14 (eff_in chops x2, eff_dye vec0valuex, ...) | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| BO_particles | yes; without effectors: yes | 2 (controls_window winop, zk_cfg table) | 8 (eff_in chops x2, state vec0valuex, ...) | 4 (zk_presets table x2, . Chop, ...) | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane); S: scene path in expr / text / table (hand) |
| BP_io_router | loads clean (device / network: not cooked) | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| BX_blender_scene | loads clean (device / network: not cooked) | 0 | 0 | 0 | 1 (/root/Stage_Deck/stage_deck) | U: hand |
| CQ_cuelist | yes (no TOP out) | 2 (controls_window winop, zk_cfg table) | 0 | 9 (resolved table x5, log table x4) | 1 (/cq/ping) | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane); S: scene path in expr / text / table (hand); U: hand |
| CS_cam_sequencer | yes; without effectors: clean | 0 | 1 (menu_logic dat) | 0 | 1 (/jazib_mcp/handlers) | U: hand |
| CV_person_mask | loads clean (device / network: not cooked) | 3 (par_exec op, controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| DC_depth_cam | loads clean (device / network: not cooked) | 3 (par_exec op, controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| Effectors | loads clean (device / network: not cooked) | 4 (eff_logic dat, controls_window winop, zk_cfg table, ...) | 0 | 0 | 1 (/jazib_mcp/handlers) | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane); A: expr / text (dropin_fix); U: hand; E: check parent(n) |
| FG_fps_governor | yes (no TOP out) | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FT_face_track | loads clean (device / network: not cooked) | 2 (par_exec op, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_analog | yes | 14 (controls_window winop x6, zk_cfg table x6, pulses op x2) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_destroy | yes; without effectors: yes | 12 (controls_window winop x6, zk_cfg table x6) | 8 (eff_in chops x2, eff_mask vec0valuex, ...) | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_film | yes | 28 (controls_window winop x14, zk_cfg table x14) | 0 | 3 (af vec3valuex, coc vec2valuex, ...) | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane); S: scene path in expr / text / table (hand) |
| FX_glass | yes | 10 (controls_window winop x5, zk_cfg table x5) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_glitch | yes | 34 (controls_window winop x16, zk_cfg table x16, pulses op x2) | 0 | 1 (misc# Pointchop) | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane); S: scene default in an OP par (ok if missing-safe) |
| FX_haze | yes | 0 | 0 | 0 | 0 | none |
| FX_motion_trail | yes | 3 (par_exec op, controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_palette_map | yes | 3 (par_exec op, controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_retro | yes | 24 (controls_window winop x12, zk_cfg table x12) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_scope | yes | 11 (controls_window winop x5, zk_cfg table x5, pulses op) | 0 | 0 | 1 (/Figure) | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane); U: hand |
| FX_strobe | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_stylise | yes | 16 (controls_window winop x8, zk_cfg table x8) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_synth | yes | 14 (controls_window winop x7, zk_cfg table x7) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_track | cooks clean, out black | 6 (controls_window winop x3, zk_cfg table x3) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| FX_trans | yes | 4 (pexec op, controls_window winop, pulses op, ...) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| GEN_clone | yes; without effectors: yes | 2 (controls_window winop, zk_cfg table) | 8 (eff_in chops x2, clones vec20valuex, ...) | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| GEN_interactive | yes; without effectors: yes | 22 (pulses op x7, controls_window winop x7, zk_cfg table x7, ...) | 2 (pts_callbacks dat x2) | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| GEN_pattern | yes | 36 (controls_window winop x17, zk_cfg table x17, drive_pexec op, ...) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| GEN_points | yes; without effectors: yes | 37 (pulses op x12, controls_window winop x12, zk_cfg table x12, ...) | 56 (eff_in chops x14, state vec9valuex x4, ...) | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| GEN_sdf | yes | 31 (still_pexec op x10, controls_window winop x10, zk_cfg table x10, ...) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| GEN_sim | yes | 23 (controls_window winop x8, zk_cfg table x8, pulses op x5, ...) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| GN_physarum | yes; without effectors: yes | 2 (controls_window winop, zk_cfg table) | 3 (engine_callbacks dat x3) | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| GN_reaction_diffusion | yes; without effectors: yes | 2 (controls_window winop, zk_cfg table) | 3 (engine_callbacks dat x3) | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| LK_projection_room | yes | 2 (par_exec op, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| LK_spectrum_glass | NO: 1 op error(s) | 1 (zk_cfg table) | 0 | 0 | 0 | Z: zk_cfg target (zkit lane) |
| LK_typecore | yes | 1 (zk_cfg table) | 0 | 0 | 0 | Z: zk_cfg target (zkit lane) |
| LP_laser_path | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| LY_lyrics_feed | loads clean (device / network: not cooked) | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| MIDI_mapper | loads clean (device / network: not cooked) | 0 | 0 | 0 | 0 | none |
| MX_prox_material | yes; without effectors: yes | 11 (vc_slots table x6, vc_sop# sop x3, controls_window winop, ...) | 26 (eff_in chops x2, mx_mat_torus vec1valuex, ...) | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane); T: table of paths (hand) |
| POP_branching | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| POP_caustics | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| POP_collide | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| POP_crack3d | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| POP_fillbody | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| POP_linegrowth | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| POP_meshwarp | cooks clean, out black | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| POP_rd3d | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| POP_terrain | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| POP_tree | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| POP_tubes | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| PV_previz_stage | yes | 1 (zk_cfg table) | 0 | 0 | 0 | Z: zk_cfg target (zkit lane) |
| PX_lines | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| PX_pointfx | yes; without effectors: not run (T-262) | 4 (controls_window winop x2, zk_cfg table x2) | 12 (px_rt dat x8, eff_in chops x2, ...) | 0 | 2 (/geo/, /jazib_mcp/handlers) | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane); U: hand |
| QC_mcp_checks | loads clean (device / network: not cooked) | 6 (sources table x4, src# top x2) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); T: table of paths (hand) |
| TL_timeline | NO: 5 op error(s) | 1 (zk_cfg table) | 0 | 1 (tl_api_logic dat) | 3 (/jazib_mcp/handlers) | Z: zk_cfg target (zkit lane); S: scene path in expr / text / table (hand); U: hand |
| TP_test_pattern | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |
| ZC_control_surface | loads clean (device / network: not cooked) | 7 (binds table x6, zk_cfg table) | 0 | 1 (zctl_ext dat) | 1 (/path/op) | Z: zk_cfg target (zkit lane); T: table of paths (hand); S: scene path in expr / text / table (hand); U: hand |
| ZK_controls_kit | yes | 2 (controls_window winop, zk_cfg table) | 0 | 0 | 0 | A: OP pars -> relative (dropin_fix + builders); Z: zk_cfg target (zkit lane) |

## 29 Oct, lane A (effectors / PX / BL_splat_render): independence round
Details: `docs/builds/effectors.md` "Published rows (#pub)", `docs/builds/px.md` "29 Oct: drop-in round", T-266.
Main recipe (coordinator; save main first; one exec per line, >= 3 s apart, `# jtd:nofollow`, pane on /project1;
`E` = `ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/effectors.py').read(), ns)`,
`P` = the same with `builders/px.py`, `B` = with `builders/splat_render.py`):
1. `E; ns['pub_upgrade']()` -> 2. (later) `E; ns['pub_result']()`: state done, errors 0, changed lists the texts,
   eff_rows_pub, `pub px_hot_px_pointfx1 ...` (+ `track` if present), grid passes, the consumer COMPs; run 1 + 2 again:
   `changed: []`.
3. `op('/project1/lab/PX_pointfx').allowCooking = True` (it is parked) -> 4. `P; ns['indep_upgrade']('/project1/lab',
   name='PX_pointfx')` -> 5. (>= 3 s) `P; ns['indep_result']('/project1/lab', name='PX_pointfx')`: done, presets_kept
   True, errors 0, changed px_logic px_rt eff_in:chops (+ hot row); 4 + 5 again: `changed: []`; then park it again.
6. Same 4 + 5 (twice) for `PX_pointfx1` (already cooking; leave it cooking). Its hot row ends enabled only if its stack
   has heat_spread / a light module (bounce); else `enabled 0`.
7. `B; ns['indep_upgrade']('/project1/lab/BL_splat_render')` twice (second `changed: []`).
8. Check: `op('/project1/effectors').par.Status` ends with "N published"; the grey lines into PX_pointfx1 are gone
   (a consumer's `eff_in.dependenciesTo(op('/project1/effectors/px_hot_px_pointfx1'))` == [] while it cooks).
9. Save; re-export library: Effectors, PX_pointfx, BL_splat_render, and the consumers pub_upgrade listed.
