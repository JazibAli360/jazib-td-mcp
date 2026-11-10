# U. Show-project housekeeping and a tight workspace in TouchDesigner (web research, 26 Oct 2026, target TD 2025.31550 / macOS)

Goal: how experienced TD show programmers keep a project's housekeeping in order and the editor neat, so an AI-driven (MCP) .toe
looks professional. Adds to, does not repeat, `G_network_layout.md` (placement, docking, annotate, colour roles) and
`R_show_safe_interactive.md` (perform mode, watchdog, kill switches, fallbacks, pre-show checklist).
Nothing was run in TD. Marks: **[V]** verified at source: either a fetched page, or the **offline help that ships inside our
build** (`/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/Learn/OfflineHelp/https.docs.derivative.ca/`, so
it matches 2025.31550 better than the live wiki). **[S]** secondary (blog, forum, third party, one source). **[U]** unverified
or my inference: probe live before relying on it.

## Summary

1. **The .toe is binary and cannot be diffed.** Every source agrees: externalise what can be diffed (Python/GLSL/JSON in Text
   DATs synced to files; each module as a .tox) and keep only the root wiring in the .toe. [V][S]
2. **No orphan finder exists in TD.** Derivative's own tips just say "delete unused nodes"; there is no built-in "unused ops"
   command or Python call. A report can only flag *candidates* (no outputs, nothing displayed, no reference, never cooked). [V]
3. **Cook hygiene is the real housekeeping**: `allowCooking=False` on inactive look COMPs (COMPs only), Switch not Cross,
   Probe/Performance Monitor removed when not used, unused viewers/display flags off, fixed resolution everywhere. [V][S]
4. **Backups are TD's incremental saves** (Preferences > "Increment Filename when Saving", optionally "On and Copy to Backup
   Folder", plus "Create Link Filename"). Git users turn this off and let git be the history. `CrashAutoSave*.toe` opens in
   Safe Mode (nothing cooks). [V][S]
5. **Workspace is already scriptable**: `ui.panes`, `NetworkEditor` (zoom, home, `showNetworkOverview`, `straightLinks`, backdrops),
   bookmarks and pane layouts live as COMPs under `/local/bookmarks` and `/local/layouts`; `COMP.layout()` plus built-in
   shortcuts `L` / `l` for arrange. [V]
6. **Embody/Envoy (community, Dylan Roscover) is prior art for exactly our job** (MCP + externalisation + "TDN" text network),
   but its README requires **TD 2025.33230+**, newer than our 31550. Borrow ideas, do not install. [V]
7. **Conflict with a standing user rule**: the user wants viewers ON and visible (CLAUDE.md "Visible work", 26 Oct). Generic advice
   "viewers off for speed" must only ever be a *report line* or a show-time (perform mode) step, never a silent tidy.
8. Honest gaps: Matthew Ragan's git/external-tox posts, the I&I "Managing Large Projects" body links, and all YouTube talks could
   not be read in full by the fetch tool (see Sources); claims from them are quoted only at the level the fetch returned.

---------------------------------------------------------------------------------------------------------------------

## 1. Project structure

### 1.1 Folder layout on disk
| Practice | Source / mark |
|---|---|
| Keep an **Asset folder at the same level as the .toe** so relative paths survive moving/sharing; "without a consistent folder structure, paths will break". | I&I HQ "Managing Large TouchDesigner Projects" (Crystal Jow) [S] |
| Keep the .toe in its **own project folder**; externalised .tox files in **their own subfolder** (README suggests `td-modules`, any name works). Each externalised COMP gets a folder of its own name containing a same-named tox. Avoid deep nesting ("that'll bite you", Windows path limits). | Matthew Ragan `raganmd/touchdesigner-save-external` README + blog 2018-11-28 [V] |
| TD Summit 2019 workshop repo (mir-lab, Ragan + Sandoval): top-level COMPs **Communication, Output, Tools, Data**; folders `tools/`, `sandbox/`, `environment-variables/`, `inheritance-example/`; "no delay scripts", control init and load order completely, "we NEVER reach into" an encapsulated component. | github.com/mir-lab/touchdesigner-summit-2019-large-systems [V] |
| Embody mirrors the network hierarchy on disk: externalising `base2` inside `base1` writes `<project>/base1/base2.tox`; DATs become `.py/.json/.xml/.html/.glsl`; folder is configurable. "Nothing is written to disk until you tag it." | Embody README + derivative.ca asset page [V] |
| Brendan Dawes keeps exported DAT code in a `_.code_` folder that mirrors op paths, so it is tracked but does not clutter the project folder. | brendandawes.com/blog/1279-touchdesigner-git [V] |
| `project.paths` (URL-style prefixes such as `movies://`, saved in the .toe; a machine-specific `<Project>.Settings.json` can override) is the built-in way to move media between the dev Mac and the show Mac. | Project_Class [V] |

For our repo: `projects/<Show>.toe`, `projects/<Show>/modules/<Look>.tox` (or `td-modules/`), `projects/<Show>/code/` for synced
text, `media/` outside git. This is a proposal built from the above; no source prescribes these exact names [U].

### 1.2 Externalised .tox per module
- Common page pars [V, Base_COMP wiki]: `externaltox` (path, "sources the component's contents upon start of a .toe"),
  `enableexternaltox` (default **on**; loads at start), `enableexternaltoxpulse` (re-load now), `reloadcustom` / `reloadbuiltin`
  (take the top-level par *values* from the file on reload), `savebackup` ("Save Backup of External": a copy is stored in the
  .toe and used if the file is missing).
- **Build 2023.10k changed this** [V, Derivative post]: "Re-Init Network" pulse and "Reload .tox on Start" are gone; `Enable
  External .tox` replaces them. New *Relative File Path Behavior* can resolve paths **relative to the .tox, not the .toe**
  (portable modules); only active while Enable External .tox is on; dropping a .tox into a network turns the toggle **off**
  (embeds). `OP.fileFolder` / `filePath` give the saved location. Old advice mentioning "Reload .tox on Start" is stale for us.
- Ragan: with everything externalised "we never save our toe file again, only the toxes"; re-save the .toe only when adding a
  component to the root or changing project-level settings (perform window). Turn **Save Backup of External off** to keep the repo
  clean (git replaces numbered backups). Keep modules "independent islands": talk through custom pars and In/Out/Select ops. [V]
- Save API [V, offline help]: `COMP.save(path)`, `COMP.saveExternalTox(recurse=False, password=None)` -> count saved,
  `project.save(path, saveExternalToxs=False)`, and callbacks `project.externalToxModifiedInProject` / `...OnDisk`.
- Gotcha for an MCP: externalised tox + `td_tox_save` on a parent prompts in the GUI (nested externalisation asks "parent too, or
  only this COMP") [V, Ragan blog]; script with `saveExternalTox` instead. Replicants/clones cannot be externalised by Embody [V].

### 1.3 Version control (git)
- .toe = binary, "impossible to diff, merge, or review". Practitioners track: externalised .tox (also binary, but small and per
  module), `.py/.glsl/.json` text, and not the media ("you don't put assets in your repo"; Git LFS for big files). [V][S]
- `toeexpand` ships in `Contents/MacOS/` (this repo's PLATFORM.md; LEARNINGS T-32) and the wiki says it expands a .toe into "ASCII
  readable files" with `toecollapse` as the inverse [V]. **No source found that uses toeexpand for git in practice**; the wiki page
  has no syntax, and Ragan/Dawes/Embody all externalise instead. Treat toeexpand as an inspection tool, not a workflow. [U for git]
- **Newest idea (Mar 2026, Dylan Roscover, "The Great Inversion")**: text is the source of truth, the .toe a disposable runtime
  container; a JSON/YAML network text format ("TDN"/"TDXN") stores only non-default pars so diffs are meaningful. He also says
  Derivative is building native MCP/text/externalisation support (author's claim) [S]. Embody needs **2025.33230+** [V]; our
  31550 is older, so check before adopting any of it.
- Minimum for us today [proposal]: `git init` in `projects/`, commit .toe + modules + text; `.gitignore` the `Backup/`, `*.dmp`,
  `CrashAutoSave*`, media. Our own LEARNINGS T-06 already notes the `.1` increment copies.

### 1.4 Naming
- Containers/Bases "named so they clearly state what they do" [S, I&I]. Ops: `<type>_<function>` mid-stream, bare names for
  end Nulls others reference (forum 168632, already in G section 1 row 6). Custom-par names must start with a capital and
  should stay under ~10-12 characters; the wiki is inconsistent on underscores. [V, Custom_Parameters]
- Extension classes: capitalised, `Ext` suffix (`LookExt`); promote only what outside ops need, keep internals lowercase. [V]
- Global OP Shortcut names must be unique across the project (error on duplicates); generate sequence names with
  `'Player'+str(me.digits)`. [V]

### 1.5 Where Python lives
- Extensions [V, Extensions wiki]: Extension Object `ExampleExt(me)`; prefer `ext.Name` access (searches up the hierarchy);
  enable **Init Extensions on Start** when something must run at load; write extensions so they can **re-init at any time**;
  clean up in `onDestroyTD`, not `__del__`; `StorageManager` for hidden/persistent values, **custom parameters for anything the
  user touches**; check `extensionsReady` in par expressions.
- Text DAT <-> file [V, Text_DAT wiki]: `file`, **`syncfile`** (two-way live sync; created if missing; if the file is deleted the DAT
  keeps its text), `loadonstart`, `write` ("Write on Toe Save"), `loadonstartpulse`, `writepulse`. Medium post "Improving Python
  Development for TouchDesigner" (tekt) advises most code in external .py linked this way (page returned 403; search summary only [S]).
- Sizes: avoid per-frame scripts, precompute, profile with `time.perf_counter()`; heavy extension functions are the costly part. [V]
- Global access: `op.Shortcut` (Global OP Shortcut, COMPs only) for cross-network access; parent shortcuts (`parent.Name`) for
  hierarchy; bind (`BIND` mode, `Par.bindExpr`) custom pars so values travel up and down. [V]
- `project1` vs root: nothing found that sets a convention; the default `/project1` is just the first Base. The Summit repo and
  Embody place their own tools COMP at `/` or `/project1` ("drop it into the root"). [S][U]

### 1.6 Config tables and storage vs custom pars
- Config in a Table DAT (or JSON/Text DAT synced to a file) read by one config extension; Summit README prefers **environment
  variables** over a stand-alone .json for per-machine differences (multi-GPU affinity). [V]
- Rule of thumb from the extension wiki: *user-facing value -> custom parameter; hidden value that must survive saves and
  re-init -> StorageManager / `store()`*. `OP.storage` is "persistent dictionary saved with the operator". [V]
- sceneChanger (Palette) house rules worth copying for looks [V]: every scene is a COMP with parent shortcut `Scene`, tag
  `TDScene`, a settings page, an `out1` TOP; **all scenes the same resolution** ("a cleanly running show should have a strict
  resolution... dynamic resolution causes new memory allocations which lead to frame drops"); bind all resolution pars to one
  top-level custom par; non-playing scenes do not cook.

---------------------------------------------------------------------------------------------------------------------

## 2. Housekeeping ops

### 2.1 Unused / orphaned ops and errors
- **No built-in orphan tool**: searches for one returned nothing; I&I's own tip list says only "Delete unused nodes" [S].
  Derivative's "Optimize" page: use the Performance Monitor to find "nodes that are unnecessarily cooking". [V]
- Candidate heuristics (my design, [U] until tested): op has no `outputs`, is not display/viewer-bound (`COMP.isCOMP` and nothing
  references it), `totalCooks == 0` or `cookFrame` stale, not an Out/Null with an export, not tagged `keep`. Reference detection is
  the weak spot: `OP.dependenciesTo(op)` [V exists] finds cook-dependency paths, and `findChildren(parExpr='*name*')` /
  `text='*name*'` [V] find textual references in par expressions and DATs. Exports and `op('/x')` calls inside callbacks need `text=`.
- Errors: `OP.errors(recurse)`, `warnings(recurse)`, `scriptErrors(recurse)` [V]; Errors Dialog (click error -> jumps to op) [V];
  Preference "Show Startup Errors" (nothing / warnings / all) [V]. Our `td_errors` already wraps these (Open question 1).
- OP Find DAT (`opfind`) [V]: filters `namefilter`, `typefilter`, `tagsfilter`, depth limits; output columns incl. tags, cook
  times, CPU/GPU time and memory, depth. No error or flag filter documented.

### 2.2 Cook control for inactive looks
- Cooking flag (`allowCooking`): "Only COMPs can disable this flag" [V]. Flags do not themselves cause cooks [V]. TD is pull-based;
  a node still cooks if anything pulls it (open viewer, export, MIDI/time/key dependencies). [S forum 114244, 2019]
- Scene switching pattern (evan_jones, forum 2019): one Base COMP per scene, a top-level Switch driven by a table, and "nodes
  don't cook if they aren't being used" [S]. Palette sceneChanger does this for you [V].
- **Switch vs Cross**: Cross cooks both inputs; Switch cooks only the selected input. Jack DiLaura (I&I) [S]. **Conflict** on
  Switch TOP with blend on: one forum reply says it cooks all inputs, another says current + next [S/U]. Measure with
  `cookedThisFrame`/`totalCooks` in our build before trusting either.
- Lock flag: freezes output, stored in the file; I&I: "Don't lock nodes unnecessarily - it increases file size" [S]; wiki Flag
  page confirms data is saved in the file [V] but not the size claim.
- `bypass` on a COMP bypasses everything inside [V]; it is the reversible alternative to delete (a third-party MCP also
  offers "bypass instead of delete") [S].

### 2.3 Viewers, display flags, memory
- Turning off node viewers in the editor "can dramatically improve performance" for big DATs/CHOPs but "won't help in Perform
  mode"; **Perform mode renders only one Window COMP** and is the real fix for live. Jack DiLaura, I&I; Perform Mode wiki. [V][S]
- Preferences [V]: "Node Viewer On by Default", "Turn on Node Viewers when Entering Network", "Viewers Active On Click Select",
  "Cache Node Viewers". Flags: `viewer`, `activeViewer`, `expose` (hides node from the network). Application shortcuts `a`
  (activate viewers) and `alt+a` (always) exist [V].
- Probe (Palette > Tools, toggled with ctrl/cmd+P): CPU circles, GPU diamonds, CPU/GPU memory, child counts. It costs ~3.5 ms
  itself in I&I's example, so **remove or switch it off when not measuring**. [V][S]
- Memory: Optimize page: use Probe for memory; Audio Play loads whole files into RAM (use Audio File In). Movie File In
  `prereadframes` is the documented memory control; no documented `unload` for movies in this build's help. [V] A global
  rule from sceneChanger: strict, constant TOP resolutions avoid reallocations. [V]
- Python: `OP.cpuMemory`, `gpuMemory`, `cpuCookTime`, `gpuCookTime`, `totalCooks`, `cookedThisFrame`; `cookTime` is **deprecated**. [V]
- Textport/log hygiene: Preference "Console Mode" (Default / Native on Windows only / Disabled), `app.logExtensionCompiles`
  (extra compile messages, resets to False each start). No documented textport-clear call [V for what exists, U otherwise].
- Tools with a cost, per I&I: Hog CHOP (CPU stress test) and tiny-resolution test (32x32 Render TOP) to find CPU vs GPU bottleneck; do
  not leave them in a show file. [S]

### 2.4 Saves, incremental backups, crash files
- Preferences > General [V]: **Increment Filename when Saving** (number suffix on Save, not Save As); **On and Copy to Backup
  Folder** puts numbered copies in a `Backup` folder next to the project; **Create Link Filename when Saving** keeps an
  un-numbered file equal to the latest save; "Prompt to Save on Exit" honours the increment setting. Startup File Mode / Custom
  Startup File. Pref file on macOS: `~/Library/Application Support/Derivative/TouchDesigner/pref.txt`.
- Known pitfall [S, forum]: with increment on, reopening can load `name.1.toe`, so edits "disappear"; fix: Save As the base
  name and keep the link filename. Same as our LEARNINGS T-06 (reported `file` has `.1`).
- Crash [V]: a crash writes `CrashAutoSave.<name>.toe`; opening it (or **any file renamed to start with `CrashAutoSave`**) is
  **Safe Mode**: nothing cooks, so you can delete the last op and save as a numbered file. Env vars `TOUCH_QUICK_CRASH` (no
  autosave/dump) and `TOUCH_DISABLE_CRASH_HANDLERS` exist; `.dmp` files help Derivative, not recovery. I&I "Recovering from a
  crash": "save often" is the real safeguard. Locations: project folder, or Desktop for unsaved projects [S]; our macOS evidence:
  Desktop (td-port LEARNINGS).
- Housekeeping policy [proposal]: one saved milestone per structural batch, never `td_save_project` mid-experiment on the show file;
  prune `CrashAutoSave*` and old `.N.toe` after the show is frozen; keep the final `.toe` + `.tox` set in git.

### 2.5 Pre-show clean (additions to R section 4)
R already has the show-day checklist. New housekeeping items (proposal built from the above):
- [ ] `td_errors` empty on every COMP, including `warnings(recurse=True)`.
- [ ] Probe/Hog/test ops deleted; no stray `test_*`, `_probe_*` COMPs; no `CrashAutoSave*` or `.N.toe` left beside the show file.
- [ ] Every inactive look has `allowCooking=False` (or is gated by the scene switcher); no viewer-driven cook of hidden looks.
- [ ] All looks at the same resolution; one top-level resolution par bound down.
- [ ] External .tox all loaded from disk (`enableexternaltox` on), `project.externalToxModified*` quiet, git tree clean, tag the commit.
- [ ] Perform window set (`project.performWindowPath`, `performOnStart`), saved in Perform mode state; bookmarks/layouts irrelevant there.

---------------------------------------------------------------------------------------------------------------------

## 3. Workspace / UI neatness

| Thing | Fact | Mark |
|---|---|---|
| Arrange | Application shortcuts: `L` = `network.layout` (selection), `l` = `network.layout.all`; unbound by default: `network.layout.all.pack`, `network.align.area.keepsize`, `network.align.area.resize`, `network.cascade.area.keepsize`, `network.reset.tile.sizes`, `network.normalize.tile.sizes`, `network.snap.grid.selection`, `network.snap.grid.all`. These are labels in the build's shortcut table; the wiki page was last edited Apr 2022, so confirm in `/local/shortcuts`. | [V, Application_Shortcuts] |
| View | `h` home, `H` home selected, `f` frame (unity zoom), `F` frame selected, `o` network overview, `s` link style (straight/curved), `x` data links, `t` list mode, `n` toggle op names, `e` expose, `D` hide, `E` expose all, `c` colour palette, `p` parameters, `G` add annotation group, `g` open groups, `tab` add operator, `ctrl+F` find, `alt+S` search, `alt+B` bookmarks. | [V] |
| Overrides | Custom shortcuts: `app.preferencesFolder/TouchShortcuts.txt` (3 columns: label, key, command); per-file override by locking the DAT `/local/shortcuts`. | [V] |
| Grid / snap | Preferences > Network: Show Network Editor Grid, Grid Brightness, **Snap to Grid** (Off/Coarse/Fine), **Snap to** (Lower Left Corner / Node Center), **Fixed-size Operator Names**. | [V] |
| Node size | `network.reset.tile.sizes` / `normalize.tile.sizes` exist; pref "Resize TOP nodes to TOP viewer aspect" already in G. | [V] |
| Pane layouts | **Layout Strip** under the menu bar: 5 defaults (single, quad, vertical, horizontal, tri); "add layout" saves every pane's *type and network path* as a custom layout; stored in the .toe as COMPs in **`/local/layouts`**; right-click renames/deletes. Python for layouts is not documented. | [V] |
| Bookmarks | Pane bar bookmark icon; stored as COMPs in **`/local/bookmarks`**; Bookmarks Dialog `alt+B`. Python access not documented (children of that COMP are the likely route). | [V] doc / [U] script |
| Panes (API) | `ui.panes` (index, name, iterate, `.current`, `createFloating(type, name, maxWidth, ...)`), `Pane.owner`, `.type`, `.maximize`, `.ratio`, `changeType()`, `splitLeft/Right/Top/Bottom()`, `tearAway()`, `floatingCopy()`, `close()`. | [V] |
| NetworkEditor (API) | `x`, `y`, `zoom`, `home(zoom, op)`, `homeSelected`, `fitWidth/fitHeight`, `placeOPs`, `showList`, `showNetworkOverview`, `showParameters`, `showDataLinks`, `straightLinks`, `showBackdropTOPs/CHOPs/Geometry`, `showColorPalette`. | [V] |
| Perform vs editor | `ui.performMode = True`, `F1`/`Esc`; only the chosen Window COMP renders; editor not open. Privacy on => cannot return to Designer. | [V] |
| Undo | `ui.undo.startBlock(name)` / `endBlock()` groups scripted edits into one undo step; `ui.undo.undoStack` lists them. Good for one-click revert of a tidy pass. | [V] |

### 3.1 Colour, comments, tags, hiding
- Colour roles and annotate boxes: see G section 3.4-3.5. New: `OP.color` (RGB 3-tuple), `OP.comment` (shown on hover), and
  `findChildren(comment='*todo*')` finds todos. [V]
- **Tags**: free-form strings set in the Parameter dialog (top) or `op.tags = {...}` / `.add()` (it is a set); searchable with
  `findChildren(tags=['*seq*'], allTags=True)` and OP Find DAT `tagsfilter`. Palette sceneChanger uses `TDScene`; Embody uses a tag to
  mark ops for externalisation. Proposed tags: `look`, `module`, `keep` (never delete), `debug` (remove before show), `ext`. [V][U names]
- **Hide internals**: `expose=False` hides a node from view in a network (reversible; `E` re-exposes all) [V]. Real privacy
  (`COMP.isPrivate`, `isPrivacyActive`, `project.addPrivacy`) requires a **Pro licence** and blocks returning to Designer; do **not**
  use it for tidy [V].
- Custom parameter pages [V, Custom_Parameters / Page / Par]: `appendCustomPage(name)`, `sortCustomPages('Definition','Controls')`,
  `Page.sort()`, `Page.pars`, `Par.order`, `Par.label`, `Par.help` ("shown when you hold Alt and roll over the parameter"),
  `Par.startSection` (separator above), `Par.readOnly`, `Par.default`. Order and attributes propagate to clones unless
  `styleCloneImmune`. Practice [S, I&I]: put the frequently adjusted pars on one custom page of the COMP and use **Bind** so
  upper and lower levels follow.
- Keep the root clean: few top-level COMPs (Summit repo: four), each a named, coloured, annotated module; collapse stray ops with
  `COMP.collapseSelected()` [V]. "Never more than 10-20 operators in a network" is quoted in G row 2 [S].

---------------------------------------------------------------------------------------------------------------------

## 4. TD Python API for a housekeeping report / tidy pass

All rows are from the offline help of our build unless stated. **D** = documented, **G** = my guess about a use or a missing piece.

| Need | Call | Mark |
|---|---|---|
| Walk a network | `comp.findChildren(depth=, maxDepth=, type=, name=, path=, text=, comment=, tags=[], allTags=, parValue=, parExpr=, parName=, onlyNonDefaults=, includeUtility=)` | D |
| Identify | `op.path`, `op.type`, `op.opType`, `op.family`, `op.isCOMP`, `op.isBase`, `op.id` (changes on reopen), `op.valid`, `op.digits` | D |
| Cost | `cpuCookTime`, `gpuCookTime`, `totalCooks`, `cookFrame`, `cookAbsFrame`, `cookedThisFrame`, `cpuMemory`, `gpuMemory`, `cook(force, recurse)`; `cookTime` deprecated | D |
| Errors | `errors(recurse)`, `warnings(recurse)`, `scriptErrors(recurse)` | D |
| Flags | `bypass`, `lock`, `viewer`, `activeViewer`, `expose`, `cloneImmune`, `selected`, `current`, `allowCooking` (COMP only) | D |
| Metadata | `tags` (set), `comment`, `color`, `nodeX/Y`, `nodeWidth/Height`, `dock`, `docked`, `inputs`, `outputs`, `parent(n)` | D |
| Reference graph | `op.dependenciesTo(other)` (cook dependency paths); par expressions via `findChildren(parExpr=)`; callbacks via `text=` | D, usefulness G |
| Orphan / unused | no API; combine `outputs==[]`, `totalCooks`, no references, no `keep` tag | G |
| Files | `op.fileFolder`, `op.filePath`, COMP `par.externaltox`, `par.enableexternaltox`, `saveExternalTox(recurse)`, `project.save(path, saveExternalToxs)`, `project.folder/name`, `project.paths` | D |
| Extensions | `comp.extensions`, `extensionsReady`, par `reinitextensions` (pulse; token **G**) | D / G |
| Custom pars | `customPages`, `appendCustomPage`, `sortCustomPages`, `Page.pars/name/index`, `Par.help/label/order/startSection/isCustom/isDefault/mode/bindExpr` | D |
| Layout | `comp.layout(ops, horizontal, vertical, gridRows)` (alphabetical, not topological: see G section 2), `collapseSelected()` | D |
| UI | `ui.panes`, `Pane`, `ui.panes.current.owner`, `NetworkEditor.*` (above), `ui.preferences` (probed in G), `ui.performMode`, `ui.undo.startBlock/endBlock`, `ui.rolloverOp` | D |
| App/project | `app.build`, `app.launchTime`, `app.power`, `app.preferencesFolder`, `app.configFolder`; `project.cookRate`, `realTime`, `cacheParameters`, `performWindowPath`, `performOnStart`, `stack()`, `pythonStack()` | D |
| Perf timeline | Perform CHOP / Info CHOP / Performance Monitor dialog (frame-trigger threshold); no Python API for the Probe | D (tools) |
| Bookmarks, saved layouts | children of `/local/bookmarks`, `/local/layouts` | G (storage is D) |
| Delete safely | `op.destroy()` (raises if already destroyed); no recycle bin; undo only inside `ui.undo` blocks | D |

`td_exec` already covers all of these; a typed `td_housekeeping` tool would just batch them.

---------------------------------------------------------------------------------------------------------------------

## Proposed housekeeping spec for the MCP (proposal; the lead decides)

### A. `td_housekeeping {path, mode:"report"}` returns, per COMP and in total (read-only, always safe)
1. **Errors**: `errors/warnings/scriptErrors` recursive; count and paths. Must be zero for ok.
2. **Layout health**: reuse `td_layout check` (overlaps, wrong-way flow, stacked at 0,0).
3. **Names**: default names left over (`noise1`, `null1`), non-unique Global OP Shortcuts, custom-par names not starting uppercase.
4. **Cook hygiene**: COMPs tagged `look` with `allowCooking=True` but not selected; ops with the highest `cpuCookTime`/`gpuCookTime`
   and `cpuMemory/gpuMemory`; ops that cook every frame with no consumer; Cross TOPs; Probe/Hog/Info test ops present.
5. **Flags**: count of `lock`ed ops (file size), `bypass`ed ops, `expose=False` ops, viewers on (informational only; see C).
6. **Orphan candidates**: no outputs + no references + not display + no `keep` tag; list only, with the evidence per op.
7. **Debug leftovers**: ops tagged `debug`, names matching `test*|_probe*|tmp*`, comments with `todo`.
8. **Files**: `externaltox` path exists, `enableexternaltox` on, modified-on-disk/in-project, absolute vs relative paths, text DATs with
   `syncfile` pointing to missing files, `project.folder` contents (`CrashAutoSave*`, `.N.toe` count and ages, `Backup/` size).
9. **Custom pars**: pages with one par, pars with empty `help`, unsorted pages (alphabetical vs intended), `readOnly` mismatches.
10. **Workspace**: panes (types and owners), whether `/local/layouts` and `/local/bookmarks` are empty, `showNetworkOverview`/`straightLinks`
    state; reported as info, never as errors.
11. **Resolution consistency** across looks (sceneChanger rule) and Global Resolution Multiplier = 1.
12. **Project**: `cookRate`, `realTime`, `performWindowPath`, `performOnStart`, build number, `app.launchTime`.

### B. `mode:"tidy"` may safely change (all inside one `ui.undo` block, one structural batch per call, `td_errors` before and after)
- Node positions and sizes through the existing flow layout; annotation boxes created/refreshed; `OP.color` by role (G section 3.4).
- Rename **only** default-named ops whose role is obvious, and **only** by `td_rename` (check live that references follow; [U]); never rename ops that
  have a Global OP Shortcut, are externalised, or are referenced by text in DATs/callbacks.
- Sort custom parameter pages/pars and fill missing `help` text from a supplied table; set `startSection` separators.
- Add tags (`module`, `look`, `debug`, `keep`) and `comment`s; save a bookmark and a pane layout for the show view.
- `allowCooking=False` on inactive look COMPs **only if** the look switcher is known and the COMP is not on the live path; log what
  was changed and offer one call to restore.
- Set Application preferences that are purely cosmetic (grid, straight links) only on request.
- Save through the user's chosen path (Increment Filename on); never delete older numbered saves.

### C. Must never change (without the user's explicit go-ahead)
- **Viewers and the visible-network rule**: do not turn node viewers off or close the network pane (user rule 26 Oct). Viewers-off is a
  report line and a pre-show step only.
- Do not delete, destroy, bypass, lock or unlock ops on the strength of a heuristic; orphans are *listed*, the user decides.
- Do not touch Global OP Shortcut names, extension code, Text DAT contents, external tox paths, or `enableexternaltox`.
- Do not enable privacy (Pro licence; blocks Designer mode), do not `expose=False` nodes the user can't find again, do not `project.save()`
  on a file in perform mode, do not rename the show `.toe`, do not delete `CrashAutoSave*` or `.N.toe` while a show is live.
- Do not change resolution, cook rate, Global Resolution Multiplier, device or MIDI mappings, or anything on the live Syphon/NDI path.
- Do not install Embody/Envoy or anything newer than 31550 supports; do not git commit as part of tidy.

### D. Gaps to close before writing the tool
Probe live: (1) Switch TOP blend cook behaviour; (2) whether `project.save()` honours Increment Filename; (3) children of
`/local/bookmarks` and `/local/layouts` (add/remove from Python); (4) actual default key table in `/local/shortcuts`; (5) whether
`OP.dependenciesTo` is cheap enough to run over 100+ ops.

---------------------------------------------------------------------------------------------------------------------

## Sources (fetched 26 Oct 2026; "offline help" = files inside our `TouchDesigner 2.app`)

Derivative wiki/docs [V]: docs.derivative.ca pages Base_COMP, COMP_Class, OP_Class, Project_Class, UI_Class, NetworkEditor_Class,
Panes_Class, Pane_Class, App_Class, Page_Class, Par_Class, Flag, Perform_Mode, Extensions, Text_DAT, Custom_Parameters, OP_Find_DAT,
Global_OP_Shortcut, Preferences, Network_Editor, Bookmark, Layout (Layout Strip), Safe_Mode, Variables, Undo_Class, Errors_Dialog,
Optimize, Movie_File_In_TOP, Toeexpand, Palette:sceneChanger, Palette:probe, Application_Shortcuts (offline copy last edited 7 Apr 2022).
Derivative community: "A word about External Files, 2023.10k builds" https://derivative.ca/community-post/word-about-external-files-202310k-builds/68166 ;
Embody asset page https://derivative.ca/community-post/asset/embody-automate-externalization/70497 ;
Dylan Roscover, "The Great Inversion", 22 Mar 2026, https://derivative.ca/community-post/great-inversion/74207 ;
"GitHub & External Toxes" (Ragan/Sandoval, mir.works, 7 Oct 2019; intro only) https://derivative.ca/community-post/tutorial/github-external-toxes/61020 ;
Elburz post "TouchDesigner optimization strategies", 19 Dec 2024 (intro only; body is the I&I article below).
Interactive & Immersive HQ [S]: "Managing Large TouchDesigner Projects" (Crystal Jow) https://interactiveimmersive.io/blog/deployment/managing-large-touchdesigner-projects/ ;
"TouchDesigner Optimization Strategies" (Jack DiLaura) https://interactiveimmersive.io/blog/touchdesigner-resources/touchdesigner-optimization-strategies/ ;
"Recovering from a crash / autosave" https://interactiveimmersive.io/blog/touchdesigner-lessons/recovering-from-a-crash-touchdesigner-autosave/ ;
"Python tags in TouchDesigner" (search summary only).
Ragan / mir-lab: https://github.com/raganmd/touchdesigner-save-external ; https://matthewragan.com/2018/11/28/touchdesigner-save-external/ ;
https://matthewragan.com/2017/12/03/touchdesigner-working-styles-git/ ; https://github.com/mir-lab/touchdesigner-summit-2019-large-systems (TD Summit 2019 "Modular Architectures & Large Systems").
Others: Embody README https://github.com/dylanroscover/Embody ; Brendan Dawes https://brendandawes.com/blog/1279-touchdesigner-git ;
forum "Organizing a file with different scenes" https://forum.derivative.ca/t/organizing-a-file-with-different-scenes/114244 (Nov 2019).
Not readable: matthewragan.com 2017 "Git and TouchDesigner" and external-tox posts (empty response), I&I HQ body links, Medium
(tekt) 403, all YouTube/Summit recordings (no transcript access). The "Ctrl+?" arrange shortcuts were taken from the shortcut table, not a talk.

## Open questions (for the lead / user)
1. Should `td_housekeeping` be one typed tool (report + tidy) or fold into `td_layout check` / `td_errors`?
2. Tag vocabulary (`look`, `module`, `keep`, `debug`, `ext`): accept, or use only comments?
3. Do you want git around `projects/` now (externalised modules + text) and Increment Filename switched off for the show .toe?
4. Should looks become tox files (`enableexternaltox`) before the show, accepting the GUI-prompt gotcha for nested saves?
5. Is a final "freeze" step wanted (errors zero, test ops removed, cooking off for inactive looks, one tagged save)?
6. Embody/Envoy needs 2025.33230+: stay on 31550 (7.23.2-style "final" rule) and only borrow the ideas?
