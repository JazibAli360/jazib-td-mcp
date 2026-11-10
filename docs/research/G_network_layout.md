# G. Clean network layout in TouchDesigner (research agent F, TD 2025.31550, 16 Oct 2026)

Trigger: the user said "learn how to place nodes cleanly and making clean flows in td - the way u have it rn isnt the way".
Cause found: `OP.create()` and `td_create` without `xy` leave **every new op at (0,0)** (probed), so ops stack on one
another; agents then moved ops to arbitrary numbers. Evidence from the home project (`/project1` children nodeX/nodeY,
probed live): `cam` (0,-1600), `geo1` (450,170), `out1` (680,200), `noise1` (175,50), `chopto1` (50,150),
`displace1` (260,200), `moviefilein1` (50,240). Default tiles are 130 wide, so `noise1` (175..305,50..140) and `chopto1`
(50..180,150..240) and `displace1` (260..390,200..290) overlap or touch, and `cam` sits 1400 units away.

Marking: **[LIVE]** = probed in 2025.31550 through td_exec (expression given). **[DOC]** = Derivative docs page.
**[COMM]** = community post / search snippet. **[UNVERIFIED]** = from memory or inference.
No screenshots were possible (no Screen Recording), so nothing about how it *looks* is verified; numbers only.

---------------------------------------------------------------------------------------------------------------------

## 1. Conventions used by TD practitioners

| # | Convention | Source / status |
|---|---|---|
| 1 | Signal flows **left to right**; inputs on the left of a tile, outputs on the right; lay work out in that direction, not top to bottom. | [COMM] Interactive & Immersive HQ tutorials as summarised by search (https://interactiveimmersive.io/touchdesigner-signal-flow/ - page body was truncated on fetch, so the wording is the search summary, not a quote); also UAL lab guide "data flows left to right" via https://lab.arts.ac.uk/books/touchdesigner/page/intro-to-touchdesigner/revisions/3492 (snippet only). |
| 2 | Keep a network small: "never really more than 10-20 operators in a network, because if it starts to go beyond that, we take a step back" - split into Base COMPs. | [COMM] nVoid / Interactive & Immersive HQ book, search snippet only (https://interactiveimmersivehq.github.io/touchdesigner-book/book/en/introductiontotouchdesigner.pdf; PDF unreadable by fetch). |
| 3 | Collapse a section into a Base COMP to keep the parent readable; bind custom pars so values travel up/down the hierarchy. | [COMM] I&I HQ "Managing large TouchDesigner projects" (https://interactiveimmersive.io/blog/deployment/managing-large-touchdesigner-projects/; search snippet only). API: `COMP.collapseSelected()` returns the new Base COMP [DOC https://docs.derivative.ca/COMP_Class, LIVE signature]. |
| 4 | **Null at the end of a stream and before any reference/export**: other networks point at the Null, so the chain behind it can be rebuilt without breaking links. Example pattern Sphere POP -> Null -> Geometry COMP. | [COMM] satoruhiga touchdesigner skill ("Use Null as intermediary before any reference connection"; https://skills.cat/skills/satoruhiga/claude-touchdesigner/touchdesigner). Also Null CHOP export endpoint in the forum thread below. |
| 5 | In/Out ops are the module boundary of a Base/Container: In TOP/CHOP/SOP/DAT makes an inlet, Out makes an outlet. | [COMM] Matthew Ragan cheat sheet via search (https://matthewragan.com/teaching-resources/touchdesigner/touchdesigner-common-operations-cheat-sheet/). |
| 6 | Naming: `<type>_<function>` for mid-stream ops (`select_XY`, `math_normalize`, `lag_soften`); drop the type prefix for end-of-stream Nulls other parts reference (`END`, `POS`); rename channels whenever meaning changes. Consistency matters more than which scheme. | [COMM] forum thread (https://forum.derivative.ca/t/best-practices-for-channel-and-operator-names/168632), fetched and read. |
| 7 | Prefer relative paths / parent shortcuts for references so collapsing nodes does not break them. | [COMM] forum thread https://forum.derivative.ca/t/custom-base-component/169743 (search snippet); satoruhiga skill ("Use relative paths for references to nearby operators"). |
| 8 | Group and document with **Annotate COMP**: three modes Comment (Shift-C, text only), Network Box (Shift-B, groups/moves/labels nodes), Annotate (Shift-A or Alt-drag, adds OP viewer). With **Enclose Operators** on, moving the annotation moves the nodes inside it, including other annotations; hold Alt to move it alone. Layer Zone (belowgrid / betweengridnodes / abovenodes) and Depth Layer order stacking. | [DOC] https://docs.derivative.ca/Annotate_COMP (fetched). Pars confirmed [LIVE], section 2. |
| 9 | Network editor: grid snap is a preference (Off / Coarse / Fine; snaps Lower Left Corner or Node Center); right-click Layout commands arrange nodes; `o` toggles a network overview; list mode Shift+T. | [DOC] https://docs.derivative.ca/Preferences and https://docs.derivative.ca/Network_Editor (fetched). |
| 10 | MCP-style tooling elsewhere: chain helpers place ops left to right with **200 px spacing**, and "verify layout before creating to avoid overlapping operators"; another suggests multiples of 200. | [COMM] satoruhiga skill; glama listings for `td_layout` / `arrange_network` (search snippets). Third-party, not Derivative guidance. |

Not found despite searching (be honest about it): any Derivative-authored style guide for **colour coding**, for Null naming,
or for node spacing numbers. The I&I HQ articles "Managing Large TouchDesigner Projects", "Own your TouchDesigner networks"
and the Signal Flow tutorial returned only their titles through the fetch tool (page text truncated), so their detailed
advice is **not** quoted here. Colour roles in section 4 are therefore **our proposal**, not an industry standard.
Matthew Ragan / elekktronaut / Function Store layout posts did not surface in search; nothing is attributed to them
beyond the cheat-sheet link above.

---------------------------------------------------------------------------------------------------------------------

## 2. The Python layout API in TD 2025.31550 (all probed live in `/project1/_probe_layout`, deleted afterwards)

### Units, sizes, axes
- `nodeX/nodeY` = lower-left corner of the tile; `nodeCenterX/Y` = centre; **Y grows upward** (bottom edge = nodeY).
  [DOC OP_Class https://docs.derivative.ca/OP_Class: "measured from its left edge / bottom edge"]. [LIVE] noise TOP at
  (0,0): `nodeCenterX,nodeCenterY = 65,45`, so centre = x + w/2, y + h/2.
- **Default tile sizes [LIVE]** (`o.nodeWidth, o.nodeHeight` right after `create`): TOP, CHOP, DAT, SOP, MAT, POP-class
  tested (noise, null, glsl, level, lfo, math, text, table, in/out/select, render, constantMAT, boxSOP, info,
  parameter, opexecute) = **130 x 90**. COMPs (base, container, geometry, camera) = **160 x 130**.
  annotateCOMP = **382 x 288** created at (-300,100).
- `resetNodeSize()` restores default size [LIVE doc string]. Setting `nodeWidth/nodeHeight` works (annotate 720x260 held).
- A node's size is not changed by turning its viewer on (`n.viewer=True` left 130x90) [LIVE]. The preference "Resize
  TOP nodes to TOP viewer aspect" (`network.fittoptotile`=1) exists [LIVE `ui.preferences.defaults`], so a TOP *may* be
  resized when the user drags it; do not rely on the 130x90 for TOPs that already have a user-set size - **read
  `nodeWidth/Height` per op, never hard-code**.
- New ops from script appear at (0,0) [LIVE: 8 mixed ops, all `(0,0)`].

### Built-in `COMP.layout()` [LIVE + DOC COMP_Class]
`comp.layout(ops=None, horizontal=None, vertical=None, gridRows=0)`.
Tested on 8 ops (noise/level/null/out TOP chain, lfo/math/null CHOP chain, text DAT):
- It is **alphabetical by op name, not topological.** `horizontal=True` produced x = -350 level1, -125 lfo1, 100 math1,
  325 noise1, 550 null1, 775 null2, 1000 out1, 1225 text1 (all y=75): **wired neighbours end up far apart, wires
  cross.** Do not use it to "clean up" a network that has wires.
- Its pitch is the native grid: **225 horizontal** (130 wide + 95 gap), **200 vertical** (90 tall + 110 gap);
  `gridRows=3` mixes both. `layout()` with no args made a 2-row block (x about -341/-114/112/339, y +-78: pitch ~227 x 156).
- Useful only to park unconnected ops (e.g. a DAT pile) or as the "TD native pitch" reference.

### Docking [LIVE]
- `op.dock = other` / `op.dock = None`; `other.docked` is a list; `other.showDocked` hides/shows docked ops.
- A GLSL TOP creates its own docked DATs on creation: `glsl1_pixel`, `glsl1_compute`, `glsl1_info` with **nodeX/nodeY
  (0,-120), (160,-120), (320,-120)** - i.e. directly under the parent, pitch 160 = 130 + 30, drop 120 = 90 + 30.
  (Reading order in `.docked`: compute, pixel, info.)
- When I moved the parent from (1000,-1000) to (1500,-1500) to (-500,300) the docked ops' `nodeX/nodeY` **did not
  change** (still 0,-120). `nodeCenterX/Y` of the docked op followed `nodeX` normally. Inference [UNVERIFIED visually]:
  docked ops store an **offset relative to their parent**, and the editor draws them there. A freshly docked extra DAT
  keeps whatever xy it had (I set `d.dock=g` on a DAT at (0,0): it stayed (0,0) = on top of the parent's offset origin),
  so the MCP must set the offset itself after docking.

### Annotate COMP [LIVE pars; DOC behaviour]
`parent.create(annotateCOMP, 't_annotateCOMP')` works but the requested name was **ignored on that call** (the op came
out as `annotate1`; a second create with 'note_a' was never name-checked) - so read `.name` back and `rename` after creating an annotate. Pars (page: names): **Text**: `Titletext`, `Titleheight`(30), `Titlealign`
(left/center/right), `Bodytext`, `Bodyfontsize`(10), `Bodylimitwidth`, `Bodymaxwidth`(1000). **Settings**: `Mode`
(menu `comment` / `networkbox` / `annotate`, labels Comment / Network Box / Annotate), `Smartquote`, `Bodywordwrap`,
`Backcolorr/g/b` (0.45 default) + `Backcoloralpha`, `Opacity`. **Annotate**: `enable`, `encloseops`(True), `utility`,
`layerzone` (belowgrid / betweengridnodes / abovenodes), `layer`, `order`, `includeinorder`. **OP Viewer**:
`Opviewerdisplay`, `Opviewer`, size/zoom/offset. Size/position = the node's own `nodeX/nodeY/nodeWidth/nodeHeight`
(set `a.nodeX,a.nodeY,a.nodeWidth,a.nodeHeight = -30,-60,720,260` held). It owns an internal child `annotation`.
Its extension class `AnnotateExt` has `EncloseOPs` (a **bool property**, not a method), `OnCreate`, `TitleText`,
`BodyText`, `Color`. Whether "enclosed" is geometric (ops whose tile lies inside the rectangle) is what the doc implies
("other operators in the Annotate's area will move with it"); I could not test dragging (no UI), so **moving an annotate
via Python `nodeX` probably does NOT drag the enclosed ops - UNVERIFIED**; move the ops yourself.

### Other flags [LIVE]
`op.color` = RGB 3-tuple (set (0.2,0.5,0.8) read back as float32 approximations 0.2000000, 0.5, 0.8000000); default
node colour (0.67,0.67,0.67) for most ops, annotate default back (0.45,0.45,0.45). `op.comment` str; `op.tags` list
(settable); `op.viewer` bool (set True/False worked); `op.expose` bool (hides node from view, default True);
`op.selected` bool; `comp.selectedChildren` list; `comp.collapseSelected()`.

### View / pane [LIVE attribute list; DOC for signatures]
`ui.panes[i]` of type `PaneType.NETWORKEDITOR` has: `home(zoom=True, op=None)`, `homeSelected(zoom=True)`,
`fitWidth(width)` (width in node units), `x`,`y`,`zoom`,`owner` (the COMP shown), `placeOPs(listOfOPs, inputIndex,
outputIndex, delOP, undoName)` (needs the mouse: "Use the mouse to place the specified operators"), `straightLinks`
(False), `showDataLinks`, `showNetworkOverview`. Setting `pane.owner` changes what the user sees, so the MCP should
not do it silently. `COMP.resetNetworkView(recurse)` re-homes on entering [DOC COMP_Class]. In this session the only
pane was owned by `/project1/_research_probe` (another agent's), which shows that a pane can sit in a COMP the user is
not looking at; a typed `td_layout` should therefore return the numbers and optionally call `pane.home(op=...)` only if
`pane.owner` is the target COMP.

### Preferences that change what "grid" means [LIVE `ui.preferences.defaults`]
`network.gridshow`=1, `network.gridbrightness`=0.5, `network.gridsnapdiv`=1, `network.gridsnapstyle`=0 (menu mapping
Off/Coarse/Fine and Lower-left/Centre is [DOC Preferences]; which integer is which is **unverified**). Snap only affects
mouse drags, not `nodeX`. Not set by us.

---------------------------------------------------------------------------------------------------------------------

## 3. LAYOUT SPEC for the MCP (proposal - the lead decides)

### 3.1 Grid and spacing (all numbers are node-editor units; derived from the live default tile sizes)
| Quantity | Value | Why |
|---|---|---|
| Tile (read per op, don't hard-code) | TOP/CHOP/DAT/SOP/MAT/POP 130x90; COMP 160x130 | [LIVE] |
| Horizontal gap between tiles | **95** (so column pitch = 225 for a 130 tile) | matches TD's own `layout()` pitch, [LIVE] |
| Vertical gap between rows of one stream | **60** (row pitch 150 for a 90 tile; 190 for a COMP row) | TD's vertical layout uses 110; 60 keeps names legible and leaves room for 2 wires |
| Gap between streams (bands) inside a COMP | **120** extra above the row pitch (band pitch 270 = 90+60+120) | separates families visually |
| Origin of a fresh COMP | (0,0) = lower-left of the first tile of the first stream; streams stack **downward** (y decreases) | y is up; reading top to bottom = control first |
| Snap | positions are multiples of **5** (225, 150, 270 all are) | stable diffs, matches layout() output |
| Annotate padding | 40 left/right/bottom, 30 + `Titleheight`(30) top | clears names and the title bar |
| Docked op offset (relative) | n-th docked op at **(160*n, -120)** for 130x90 parent (general: n*(w+30), -(h+30)) | [LIVE] GLSL TOP default |

### 3.2 Placing one new op (`td_create` with no `xy`, or `xy="auto"`)
1. If it has an **input** to wire: `x = src.nodeX + src.nodeWidth + 95`, `y = src.nodeY`. If that rectangle collides with
   any non-docked op, step `y -= (h + 60)` until free (branches stack below the spine, never above).
2. If it is a **source** (no input; noise, constant, movie in, lfo): column 0 of a new row: `x = left edge of the
   COMP's occupied box`, `y = bottom of occupied box - 270` (a new band under everything), or in the band of its
   family (see 3.4).
3. **Docked** ops (callback DATs, GLSL pixel/compute/info DAT): `op.dock = parent`, then set the offset above. Never
   leave a docked op at its create default (0,0).
4. Return the final `xy` and the overlap check result (see 3.6) from the tool.
5. `createOp(... wire_from=...)` should wire first, place second, so that "to the right of its input" is a fact.

### 3.3 Auto-arrange an existing COMP (`td_layout {path, mode:"flow"}`) - prototype tested live
Algorithm (full code in section 5, run on a scrambled 12-op network in the probe: **5 overlaps -> 0**, all wired ops in
increasing-x order):
1. Collect children that are not docked and not annotates. Edges = `op.inputs`. (Cross-op parameter references and
   exports are not wires; optionally parse `op('...')` in par expressions to draw the same dependency - phase 2.)
2. **Column = wire depth**: longest path from any source; back edges (feedback loops wired into earlier ops) ignored via DFS.
3. **Stream** = weakly connected component. **Row inside a stream**: the spine (path through input[0]) keeps row 0;
   extra branches and extra inputs take the next free row at their depth, ordered by input index to reduce crossings
   (the prototype tie-breaks alphabetically - improve with input-index order and "path to Out" as spine).
4. **Band order** (top to bottom): CHOP control streams, DAT/table/text streams, then TOP/SOP/POP/MAT streams, COMP
   last. Rationale: control sits above what it drives (item 1.7 reference/export draws from above), output reads at the bottom.
5. x per column = running sum of (max tile width in column + 95). y per row = y0 - row*(maxH+60); streams separated by 120.
6. Write `nodeX/nodeY` last (T-00b: compute everything, then mutate); leave docked ops and annotates alone; then
   rebuild annotations (3.5). Return `{moved, overlaps_before, overlaps_after, crossings_estimate}`.
7. Do **not** call built-in `comp.layout()` for this (alphabetical, wire-blind, section 2).
8. Do not auto-arrange a COMP the user has hand-laid unless asked; a tag `#hand` on the COMP (or `layout=false`) skips it.

### 3.4 Roles, colours and names (our proposal; no industry standard found)
Colour via `op.color` (RGB 0-1). Colour only a few roles so the palette means something; leave the rest default grey.
| Role | Colour (r,g,b) | Naming | Examples |
|---|---|---|---|
| input / source | (0.25, 0.55, 0.85) blue | `in_<what>` or the op type name for plain generators | `in_cam`, `in_movie` |
| process | default grey (0.67) - don't recolour | `<type>_<function>` (forum convention 6) | `blur_soft`, `comp_mix` |
| control / data | (0.90, 0.65, 0.20) amber | `ctl_<what>`, end Null `null_<what>` | `ctl_lfo`, `null_speed` |
| output / reference point | (0.30, 0.75, 0.40) green | `out_<what>` (Null) then `out1` (Out) | `out_main`, `out1` |
| feedback / loop | (0.80, 0.35, 0.35) red | `fb_<what>` | `fb_trail` |
| script / DAT code | (0.60, 0.50, 0.75) violet | `<op>_pixel` style stays for GLSL docked DATs | `ext_main` |
Rules: lower-case, `[a-z0-9_]`, begin with a letter; no spaces; role prefix first so sort order groups the stream;
custom-par names are separate (T-00e). One Null with a stable name at every stream end; other COMPs reference the Null,
never the op behind it. Add a `comment` (one line) on any Null that other COMPs read ("read by /project1/render1").

### 3.5 Annotations
- One **Network Box** (`Mode='networkbox'`) per stream/module, titled with the role, e.g. `INPUT cam`, `CONTROL lfo`, `FX glow`,
  `OUT`. Use `Mode='comment'` for single-line notes. Use `annotate` mode only when an OP viewer preview helps.
- Rect = bounding box of its ops + padding (3.1). Set `nodeX,nodeY,nodeWidth,nodeHeight` explicitly; `Titletext`, `Titleheight=30`,
  `Backcolor*` = the role colour at low brightness (e.g. 0.18 of the role colour + alpha 1) so text stays readable;
  `layerzone='belowgrid'` (default) so it never covers tiles.
- Only when a COMP holds >= 2 streams or >= 8 ops. A 4-op chain gets none.
- Annotates are created last and excluded from arrange; the tool deletes and recreates its own (tag `#auto`) on re-arrange.

### 3.6 Hard checks the tool should return every time
`overlaps == 0` (rectangle test with real `nodeWidth/Height`), every wired input at smaller x than its consumer
(feedback excepted), no op at (0,0) unless it is the only one, spread of the COMP < 6000 wide (a sanity guard against
the `cam (0,-1600)` kind of outlier), docked offsets set.

### 3.7 Structure rules (beyond coordinates)
- >= 15-20 ops in one COMP -> split into a Base COMP per module (convention 2). Module boundary = `in*`/`out*` ops
  (convention 5), module name = role (`fx_glow`, `ctl_audio`).
- **Control COMP separate from render COMPs**: `ctl` holds CHOPs/custom pars and exposes Null CHOPs; render COMPs read
  them by relative path/bind (convention 3) - never wires across COMP boundaries.
- Wire vs reference: wire = image/signal that flows (TOP->TOP, CHOP->CHOP). Parameter control from another op = reference
  (`op('ctl/null_speed')['speed']`) or CHOP export to the par, not a wire. Cross-COMP image links: a **Select TOP** (or
  In/Out) at the consumer, not a long wire. Never run a wire backwards; a feedback loop goes through the Feedback TOP's
  target par (no backward wire) when possible.
- Wire crossing avoidance: spine on row 0; merges (Composite/Over) take the second input from the row below; sources of
  control sit in the band above; never route a wire past an unrelated op in the same row (the row step in 3.3 prevents it).

---------------------------------------------------------------------------------------------------------------------

## 4. ASCII diagrams (x grows right, y up in TD; tiles drawn 1 char = 20 units wide)

### 4.1 Camera -> effect -> null -> out (one spine, annotated)
```
 +-- INPUT cam ---------+  +-- FX ---------------------+  +-- OUT ---------------+
 | [in_cam]---->[blur_soft]---->[level_grade]---->[null_main]---->[out1]          |
 +-----------------------+  +---------------------------+  +----------------------+
 x:    0           225             450              675          900
 y: all 0   (pitch 225, tiles 130x90; one Network Box per module is optional here, 4 ops = none)
```

### 4.2 CHOP control row above, driving TOP parameters (references, not wires)
```
 CONTROL   [ctl_lfo]-->[math_scale]-->[null_speed]     (amber, y = 0)
                                          :                       (dotted = par reference / export,
                                          :                        never a wire; no crossing)
 IMAGE     [noise_base]-->[level_drive]-->[null_main]-->[out1]   (y = -270, spine row 0)
                           ^ par `brightness` = op('null_speed')['speed']
```
Band order top to bottom: CONTROL (CHOP) then IMAGE (TOP). Column spacing is shared so reference lines stay short.

### 4.3 GLSL with feedback loop and docked DATs
```
 [noise_seed]--+                              +-->[null_glow]-->[out1]
               v                              |
               +-->[glsl_trail]--------->[null_trail]        glsl_trail docked DATs (relative offsets):
 [fb_trail]----^   (input 1)  |  ^                             (0,-120) pixel   (160,-120) info   (320,-120) compute
   ^                          |  |
   |  Feedback TOP: `top` par = null_trail   (no backward wire)
   +-- target set by parameter, drawn as a dotted reference
 row 0 : noise_seed -> glsl_trail -> null_trail -> null_glow -> out1      (x = 0,225,450,675,900)
 row 1 : fb_trail                                                   (x = 0, y = -150: feeds glsl input 1)
```

---------------------------------------------------------------------------------------------------------------------

## 5. Prototype used for the live test (ASCII, ran inside TD; also at the scratchpad path below)

Tested result [LIVE]: 12-op scrambled network (noise+circle -> composite -> blur -> {null, edge->null}, null -> out; lfo ->
math -> null CHOP; text DAT): overlaps before = 5, **after = 0**; columns 0/225/450/675/900; CHOP band, then DAT band,
then TOP band (y = -90, -300, -510/-660). Known weakness: the spine tie-break is alphabetical (blur's two children
`edge1`/`null_out` took row 0 / row 1 in name order), so implement "spine = path to Out / input[0]" in the real tool.
Scratchpad copy: `/private/tmp/claude-501/-Users-vyro-Documents-StageLab-PrismFest/884be6b4-f6c3-4881-b616-b05ae1e8baed/scratchpad/arrange.py`.

```python
# arrange(comp): left-to-right columns by wire depth, rows by stream; docked ops left alone.
GAP_X, GAP_Y, BAND_GAP = 95, 60, 120
FAM_ORDER = {'CHOP': 0, 'DAT': 1, 'TOP': 2, 'SOP': 2, 'POP': 2, 'MAT': 2, 'COMP': 3}   # band order, top to bottom
def arrange(comp, x0=0, y0=0):
    ops = [o for o in comp.children if o.dock is None and o.OPType != 'annotateCOMP']
    S = set(ops)
    ins = {o: [i for i in o.inputs if i in S] for o in ops}
    outs = {o: [] for o in ops}
    for o in ops:
        for i in ins[o]: outs[i].append(o)
    # depth = longest path from a source, ignoring back edges (feedback)
    depth, state = {}, {}
    def dfs(o):
        if o in depth: return depth[o]
        if state.get(o) == 1: return -1          # back edge, ignore
        state[o] = 1
        d = 0
        for i in ins[o]:
            di = dfs(i)
            if di >= 0: d = max(d, di + 1)
        state[o] = 2; depth[o] = d
        return d
    for o in ops: dfs(o)
    # streams = weakly connected components
    seen, comps = set(), []
    for o in sorted(ops, key=lambda o: (depth[o], o.name)):
        if o in seen: continue
        stack, grp = [o], []
        while stack:
            a = stack.pop()
            if a in seen: continue
            seen.add(a); grp.append(a); stack += ins[a] + outs[a]
        comps.append(grp)
    # order streams: by family band of the sink, then name
    def fam(g):
        sink = max(g, key=lambda o: depth[o]); return (FAM_ORDER.get(sink.family, 9), sink.name)
    comps.sort(key=fam)
    y = y0
    pos = {}
    for g in comps:
        # rows inside a stream: first-output inherits row, extra branches take new rows
        row = {}; used = {}
        nrows = 0
        for o in sorted(g, key=lambda o: (depth[o], o.name)):
            ps = [row[i] for i in ins[o] if i in row]
            r = min(ps) if ps else None
            if r is None or (depth[o], r) in used:
                r = 0
                while (depth[o], r) in used: r += 1
            row[o] = r; used[(depth[o], r)] = 1; nrows = max(nrows, r + 1)
        cw = {}
        for o in g: cw[depth[o]] = max(cw.get(depth[o], 0), o.nodeWidth)
        colx, x = {}, x0
        for d in sorted(cw): colx[d] = x; x += cw[d] + GAP_X
        rh = max(o.nodeHeight for o in g)
        for o in g:
            pos[o] = (colx[depth[o]], y - row[o] * (rh + GAP_Y) - rh)
        y -= nrows * (rh + GAP_Y) + BAND_GAP - GAP_Y
    for o, (px, py) in pos.items(): o.nodeX, o.nodeY = px, py
    return {o.name: pos[o] for o in pos}
def overlaps(comp):
    ops = [o for o in comp.children if o.dock is None]
    n = 0
    for i, a in enumerate(ops):
        for b in ops[i+1:]:
            if a.nodeX < b.nodeX + b.nodeWidth and b.nodeX < a.nodeX + a.nodeWidth and a.nodeY < b.nodeY + b.nodeHeight and b.nodeY < a.nodeY + a.nodeHeight: n += 1
    return n
```

---------------------------------------------------------------------------------------------------------------------

## 6. What I did and cleaned up
- Created `/project1/_probe_layout` (and its children), probed, **deleted it** (`/project1` children afterwards: cam, geo1, out1,
  noise1, chopto1, displace1, moviefilein1, `_research_probe`). Did not save the project, did not touch `/jazib_mcp`,
  `cam`, or anything else. Note: the `cb_*` COMPs that were present when I started (`cb_small`, `cb_result`, ...,
  `cb_probe_page_host`) were gone by my last listing; I did not delete them (other work in the same project).
- Fetch tool could not read the I&I HQ articles' bodies (truncated) or the 6 MB nVoid PDF; their claims are search-snippet
  level only and marked [COMM].

## Open questions for the lead
1. Should `td_create` with no `xy` auto-place by 3.2 (my recommendation), or require `xy` and error otherwise? Either removes the (0,0) pile-up.
2. Add a typed `td_layout` (modes: `flow`, `check`, `annotate`) to `handlers.py` using section 5? `check` alone (overlap/order guards,
   section 3.6) is cheap and could run after every build as part of the T-00b verify step.
3. Adopt the colour/naming roles (3.4)? They are a proposal; no standard exists. Does the user want colours at all?
4. Docked offsets are inferred to be parent-relative from numbers only; the user can confirm by eye (move a GLSL TOP, see whether the three
   DATs follow). Same for "does moving an annotate via `nodeX` carry enclosed ops" (I expect no).
5. Which input connector sits on top in the editor (input 0 top or bottom) - needed to order merge rows without crossings; needs one
   look at a Composite TOP in the real editor (no screenshots available to me).
6. Should layout be forced on existing hand-laid COMPs (e.g. `/project1` outliers)? I'd offer `check` first and `flow` only on request.
