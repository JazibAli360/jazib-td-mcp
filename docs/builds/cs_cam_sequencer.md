# CS_cam_sequencer v2: a Camera COMP that eases between camera presets (how-to)

TD 2025.31550 (macOS, Rosetta). Clean-room: built from the public description and videos of Function Store's
CamSequencer only (research and sources: `docs/research/CS_camsequencer.md`); no file, code or asset of the product was
used. Builder `builders/cam_seq.py` (v2.0.0), logic `builders/cam_seq_logic.py` (tests `test/test_cam_seq.py`),
TD runtime `builders/cam_seq_rt.py`, v1 upgrade `builders/cam_seq_migrate.py`. Library: `library/CS_cam_sequencer/`.

**v2 (28 Oct 2026) replaces v1** (a Base COMP with hidden `cam_edit` / `cam_out` cameras). The user: "camsequencer
originally has a camera in comp that u can move around ... i can create and drop it in different comps with existing
3d scenes and have it to animate it". So the COMP now IS the camera, as in the original.

## 1. The workflow (the original's)

1. **Drop it in** any COMP that has a 3D scene (drag `library/CS_cam_sequencer/CS_cam_sequencer.tox` in, or
   `parent.loadTox(...)`). Nothing else is needed: no PX, no AU_features, no effectors, no `/project1/...` path.
2. **Set your Render TOP's Camera** to it (`CS_cam_sequencer`, the COMP itself).
3. **Activate its viewer and navigate** (tumble / pan / dolly in the camera's viewer) to a first position. You can
   also type values on the Xform / View pages: the presets are the camera's own pars.
4. **Seq > Init**: clears the presets and saves the current position as preset 0.
5. Navigate elsewhere (change FOV too if you like), **Append**. Repeat (x3 or more).
6. Optional: **Xform > Look At = a Null** in your scene, move the Null, Append. The Null's transform is
   sequenced too (its own preset table, row k goes with camera preset k).
7. **Drive Select**: by hand (the slider; integer = preset, fraction = the blend into the next one) or with an
   expression such as `absTime.seconds * 0.25`, or a CHOP. It animates.

Edit later: set Select to the preset (e.g. 2), re-pose, **Replace**; **Insert** puts a new preset before the selected
one; **Remove** deletes the selected one. "Selected" = the preset nearest to Select.

## 2. Pages, page by page

The par dialog shows the stock Camera pages (Xform / Pre-Xform / View / Settings / Render / Extensions / Common) and
the custom pages **Seq | Presets | About** (the original's), then ours **Play | Clock | Shake | Look | Output**.

| Page | Pars (label) | Behaviour |
|---|---|---|
| **Seq** | Append, Replace, Insert, Remove, Init (pulses) | capture the camera's `tx ty tz rx ry rz sx sy sz px py pz fov` (+ the Look At op's `tx..pz`) into the tables; EASE = the current Easing |
| | Ease Override (`Override`) | on: Easing is used for every segment; off: the curve stored with a preset eases INTO it, the wrap segment N-1 -> 0 included (preset 0's curve) |
| | Easing (`Easing`) | linear, smoothstep, smootherstep, the 30 easings.net curves (in / out / in-out x Sine Quad Cubic Quart Quint Expo Circ Back Elastic Bounce), custom (Play > Custom ease CHOP) |
| | Spline Interpolation (`Splineinterp`) | a centripetal Catmull-Rom through the presets (closed when Loopmode = loop): no kink at the presets. Without Override the time along the curve is linear (one continuous move); with Override the Easing shapes each segment. Like the original's, it can swing wide on some paths: pick what looks best |
| | Select | the fader: integer part = preset, fraction = the blend; wraps (Loopmode loop) |
| | Length | read-only count of presets |
| | Bind | on: the sequencer owns the camera's pars (and the Look At op's); off: nothing is written, edit freely, then Append / Replace and re-bind (section 3) |
| **Presets** | Open Cam Presets, Open Lookat Presets | a pop-up table editor (`#`, `EASE`, a column per par): click a cell to edit it; buttons Row - / Row + (pick a row), Up, Down, Add current, Dup, Delete, Sort # (type `1.5` in `#` to move a row between 1 and 2), Close. Moves act on the shown table only (the two tables are separate, as the original's) |
| **About** | About, Version, Docs, Status | help text, `2.0.0`, this doc, the last action ("append -> preset 3 of 4 (+ Look At target)") |
| Play (ours) | Playmode manual / sequence / beat / random, Loopmode loop / ping-pong / once, Quantise cuts, Hold, Transition (beats), Transition cut / ease / arc, Random min / max hold, Seed, Next / Previous / Random / Cut to selected, **Go to preset** (any to any) + Go, Go-to blend / time / ease, Spline amount, Shortest rotation, Select lag, Custom ease CHOP, Reset | sequence = auto-advance every Hold beats (quantised), eased INTO each preset over Transition beats; beat = hard cuts on the grid; random = seeded, never the same twice; Go to preset blends from the CURRENT view straight to the target (never sweeps the presets in between, the forum complaint F1); in manual mode Next / Prev / Random are such jumps |
| Clock (ours) | Clockmode internal / AU_features / TL_timeline / In CHOP `beats` / manual (Seek), Bpm, Beats per bar, AU_features COMP, TL_timeline COMP | the hook COMP pars are EMPTY by default; an empty or missing hook falls back to the internal clock (`absTime.seconds * Bpm / 60`) |
| Shake (ours) | profile off / breath / handheld / walk / vehicle / quake, amount, position / rotation scale, speed, seed, beat kick, scale by FOV | applied after the blend (never fed into the next preset); with a Look At op the aim noise moves the look point (TD's Look At owns the aim) |
| Look (ours) | Targetmode Look At presets / global target op / global effector, Global target op, Effectors COMP (optional), effector name, Look damping, Frame (pull back so the radius fits the NARROWER frame angle), radius, padding, Roll offset, FOV offset | a global target drives the Look At op when one is set, else the camera's rx / ry / rz are aimed at it |
| Output (ours) | Frame width / height (aspect for Frame; 1080 x 1920 default), Out CHOP channels (read-only list), Open controls | `out1` CHOP: `cs_tx..cs_fov`, `cs_la_tx..cs_la_pz`, `cs_select cs_preset cs_progress cs_blend cs_cut cs_goto cs_beats cs_bar cs_shake cs_dist cs_haslook cs_ver` (float32). Open controls = the optional zkit panel: built on demand only where this repo's `builders/zkit.py` and `/jazib_mcp` exist, else a Status note; never required |

Optional CHOP drives on `in1`: `select`, `preset` (go to on change), `next` / `prev` / `random` / `kick` (rising
edge), `beats` (Clockmode In CHOP).

## 3. How Bind works (the choice, and why)

**Write on change.** The Script CHOP `solve` computes one camera state per cook. When it differs from the last one,
the counter channel `cs_ver` steps and the CHOP Execute `cs_bind` writes the new values into the camera's own
**constant** pars (and the Look At op's), only those that changed, from the module's float64 copy (not the float32
CHOP, T-247).

- Nothing is written while the output stands still, so **with Bind on you can still tumble the viewer** between
  Select moves, then Append / Replace capture it (exactly the original's authoring loop; the task's drop-in workflow
  needs no Bind toggling).
- Whenever the sequencer moves (Select scrubbed or expression-driven, a playmode, a go-to, shake, a moving target),
  it overwrites the pars every frame: **Bind on owns the pars**. Turning Bind on also turns expressions / exports on
  those pars into constants and writes the current state at once.
- **Bind off**: no writes at all; the camera and the Null are yours. Then Append / Replace, and Bind on again.
- Not chosen: expressions / exports on the camera's pars (the viewer cannot tumble a par that has an expression, and a
  Null outside the COMP would carry a path into the sequencer that breaks on rename / copy).
- Caveat: a hand edit of a par that the next state does not change (e.g. rx while only tx moves) stays until Bind is
  toggled or that par moves.

## 4. Drop-in, copies, cost (what was proven live, b2, 28 Oct 2026)

- **Fresh drop**: a container `/project1/dropin` with only a Geometry COMP (torus, floor, ball), a Phong MAT, a Light
  and a Render TOP (540 x 960), plus a Null `target`. The library tox (`c.save`) was loaded parked, un-parked 10 s
  later: 0 errors. Render TOP Camera = `CS_cam_sequencer`; Init + 3 Appends; Look At = `target`; Append; Replace of
  preset 3 with the Null moved. Select 0 / 0.5 / 1 / 2 / 3 / 3.5 / 4 / 4.5 by hand: the camera pars and the Null
  matched the maths and the renders change shot by shot with the Null near frame centre
  (8-frame contact sheet in the build report); `Select = absTime.seconds * 0.4`: the camera and the Null move every
  frame (118 cooks in 119 frames), real b2 rate 60.0 fps.
- **Seq**: Init / Append / Insert (before the selected) / Replace / Remove on both tables at the same row; the Look
  At table is padded with the Null's values the first time a Look At op appears.
- **Easing**: Select 1.5 = the exact midpoint; 2.5 eased by preset 3's `outBounce`; 3.5 (the wrap) by preset 0's
  `inOutSine`; Override + linear and Spline sweeps (81 forced cooks each) = the offline logic to 0.0; spline turn at
  the presets ~11 deg per 1/20 step (the curve's bend) vs 90 deg for the straight line.
- **Bind**: off -> Select 2 did not move the camera and a hand edit held; on -> the camera and Null jumped to preset 2.
- **Pop-up**: opened on the cam table; real `click()`s on Row + / Down / Up / Sort # / Add current / Delete / Close,
  and a cell edit reached the camera.
- **Beat mode** (internal clock, Quant 1, Hold 2): cuts at whole beats every 2 beats, presets in order. AU_features
  was not on b2 (the optional AU test was skipped; the AU clock path is the v1 one, unchanged).
- **Copies**: `parent.copy()` -> its own tables, own runtime state (separate module, id key), every op reference
  resolves inside the copy; `relative_check()` finds no absolute path inside the COMP.
- **Cost** (in-frame medians over 120 frames, b2 alone): idle = **0 cooks** (Tick off); playing: `solve` 0.22-0.24
  ms, `cs_bind` 0.09-0.11 ms, rename 0.06 ms, about **0.36-0.40 ms** CPU, 0 GPU. Over the ~0.3 ms target: a trivial
  one-channel Script CHOP alone costs ~0.05 ms here and the Python body ~45 us warm (Rosetta in-frame factor, T-247).

## 5. Upgrading the v1 COMP in main (same path)

`builders/cam_seq_migrate.py` `cs_migrate(path, step)`: one exec per step, a few seconds apart, polling the reply
(`cs_migrate_status(path)` reads the plan):

| Step | What it does |
|---|---|
| `prepare` | reads the v1 `shots` rows, the pars worth carrying (Ease -> Easing, Active -> Bind, Select, playmode, shake ...), the rotate order, and the refs in the PARENT's ops (`Camcomp`, `camera` ...; strings only, no eval, T-255); closes its windows, panes off, viewer off, not current; parks it; renames it `<name>_v1` |
| `build` | builds the v2 Camera COMP at the same path (parked); shots -> presets: position + target + roll -> the camera's tx..rz for its rotate order (it aims right with no Look At op), fov; the target -> the Look At preset |
| `unpark` | >= 10 s later |
| `repoint` | >= 60 frames later: every recorded ref that named `.../cam_out` now names the COMP (TD did NOT follow the rename on b2) |
| `finish` | optional: `keep_old=False` destroys the parked `_v1` (deferred `safe_destroy`) |

Proved on b2: the old library tox (v1) with 3 fake user shots, a PX-like `Camcomp` and a Render TOP on
`.../cam_out` -> 3 cam + 3 Look At presets (eases carried, the blank one = the old Ease), aim error 0.007 deg at the
old target, both refs on the COMP, 0 errors, then `finish` destroyed `_v1` with b2 still alive. Main (offline read
of `JazibTD_home.1366.toe`): its `shots` held only the factory `corner1..corner4`, and neither PX `Camcomp` was set.

## 6. Limits and notes

- The camera viewer's tumble cannot be driven from Python, so the live proofs set the same pars the viewer writes.
- With Xform > Look At set, TD still applies the camera's rx / ry / rz as a twist about the aim (probed: the view
  axis stays on the Null, X / Y turn). Zero rx / ry after tumbling if a preset rolls oddly; rz = roll.
- Rotations interpolate raw, as the original's pars (350 -> 10 sweeps through 180); Play > Shortest rotation fixes that.
- Arc transitions need Look At values (else straight).
- Clean-room: names on Seq / Presets are the visible labels of the original (generic words); the maths is ours
  (easings.net closed forms, Barry-Goldman centripetal Catmull-Rom, cam_rig_logic's Director / noise).
