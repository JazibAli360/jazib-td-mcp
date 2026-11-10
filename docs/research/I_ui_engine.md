# I. "UI Engine" (VvirDev): what it is and whether it fits our show panel (research agent I, 16 Oct 2026)

Task: the user asked "check out this ui engine for making controllable uis"
(https://derivative.ca/community-post/asset/ui-engine-modular-ui-tool-touchdesigner/75309). Compared against our
framework in `docs/SHOW_PANEL.md` (`/project1/show`: `state`, `looks/<name>` with own custom pars, `mixer`, `ui` Parameter
COMPs, `midi_map`) and `H_control_panel.md`. Research only: nothing downloaded or installed, no `td_*` call, no TD touched.

Evidence tags: **[SRC]** = read from the primary source on 16 Oct 2026 (URL given). **[DESC]** = the author's description,
not checked against the tool itself (the tool was not downloaded). **[UNV]** = unverified / not stated anywhere I could read.

## 0. Short answer

1. It is **not a control-panel generator**. It is a **library of pre-made, themed UI elements** (HUD / data-visualisation /
   parameter-exposure widgets) that you **click to copy into your own network**; each copy is then an independent COMP you
   "wire up, resize, or customize" by hand [SRC Notion docs]. Nothing in the docs says it reads a COMP's custom parameters
   and builds controls for them, or that elements bind to parameters automatically.
2. Free for personal **and commercial** use, but **no redistribution** of the `.tox` (or any modified version, or inside a pack
   or template) [SRC Notion docs, "LISCENSE"]. Built with **TD 2025.33070** (newer than our 31550); OS support **not stated**.
3. **Recommendation: skip** for the show panel (reasons §5). Our "own controls per look" rule is already met by the Parameter
   COMP on the live look, and by the shipped `autoUI.tox` if a nicer auto-built panel is wanted (H §3.1). Re-look only if the user
   wants decorative HUD / meter widgets for a monitor page; that needs the user's download OK and an `AUDIT.md` entry.

## 1. What it is and how it works

Sources: the Derivative asset page [SRC https://derivative.ca/community-post/asset/ui-engine-modular-ui-tool-touchdesigner/75309,
page text read with WebFetch; "updated_time" meta 2026-09-14]; the Patreon post [SRC public post JSON,
`https://www.patreon.com/api/posts/168513276`, the same data the post page serves; the web page itself returned 403 to a
plain fetch]; the Notion documentation [SRC https://app.notion.com/p/UI-Engine-Documentation-3d013083fd5c80948a96e7e39c09e056,
a JavaScript page that WebFetch cannot read; I read its public blocks through Notion's own public page endpoint
(`loadCachedPageChunkV2` + `syncRecordValues`), so the text below is the page's real content, except one 4-row table
(see "Not retrievable")].

- **Author:** "VvirDev" on Derivative; Patreon campaign "VirDev"; docs sign off "Built by Malena Goya (VirDev)". Visual artist and
  PhD researcher. Links: Patreon https://www.patreon.com/VvirDev , YouTube https://www.youtube.com/@VvirDev ,
  Instagram https://www.instagram.com/vvirdev/ . No GitHub repo, no Gumroad, no forum thread [SRC asset page].
- **Dates:** Patreon post created 3 Sep 2026, published 3 Sep 2026, last edited 10 Sep 2026; Derivative asset page dated 7 Sep 2026
  [SRC]. So it is **6 weeks old**, v1.0, with 0 comments on both Derivative (135 reads) and Patreon. No public issue tracker
  exists, so **known bugs: none published; the only warning is performance/crashes with several modules open** (below).
- **Pitch (author's words):** "a modular, click-based UI system for exposing parameters and visualizing data inside your TD
  projects"; built to stop "fighting the same battles with resolutions and aspect ratios" [SRC asset page + Patreon post].
- **Workflow [SRC Notion]:** drop the UI Engine `.tox` into the project -> open its Viewer in **Panel mode** (parameters alone do
  nothing) -> a list of titles, each a module (a themed pack of elements) -> click a title and the module appears in the network
  to the right of UI Engine -> click an element and a **fresh independent copy** is placed in the workspace (below the module);
  "each click gives you a fresh copy". The pulled copy is "fully editable, and ready for you to wire up, resize, or customize".
- **Modules:** 5 native + 3 external (the external ones are separate `.tox` files attached to the Patreon post; installed with an
  **Install Module** button which opens a file browser) [SRC Patreon post + Notion]. **The contents of the 5 native and 3
  external modules (which widgets: sliders? buttons? meters? graphs?) are not described in any text I could read** [UNV]. The
  author's cover image (1920x1200 JPG on Patreon) was not inspected.
- **How a UI is defined:** no JSON / template / custom-par schema. Each module is "a container with the same internal structure:
  a set of elements inside a pre-wired, clickable layout"; to author your own: duplicate a module, replace the child elements,
  "keep the naming and structure consistent (the UI Engine expects certain hooks for clicking and copying)", save as `.tox`
  [SRC Notion, "Creating custom modules"]. So a UI is **assembled by hand from copied elements**, in the network editor.
- **Layout and resolution:** one `Proj Resolution` parameter on the main COMP; every element reads it **once, when copied**, and
  sizes itself; later changes need the per-element **Match Project Resolution** (or **Reset Resolution**) button [SRC Notion].
  Not stated: whether it supports portrait (our looks are 1080x1920 but the operator panel resolution is separate and free).
- **Theming:** a "Custom Look" window on the main parameters for colours, fonts and styling [SRC Notion]. Presets of the
  theme: not mentioned.
- **Workspace tools:** buttons for Install Module, delete modules, close some or all created elements/modules, **Normalize
  Nodes** (resizes nodes in the Network Editor), Reset Modules, **Clear All** ("intentionally broad") [SRC Notion; the docs
  table that describes each button did not come back, [UNV] on exact semantics].
- **Binding to parameters:** **not documented.** The only statement is that elements are independent copies to wire up yourself
  [SRC]. Whether an element exposes `Value0`/CHOP output, or has a "bind to this OP par" field, is [UNV].
- **Presets, MIDI, OSC, perform-mode/window usage, touch/tablet support:** **none of these is mentioned** in the page, the post or
  the docs [SRC: absence in all three]. Treat as not provided until the tool itself is inspected.
- **Performance:** the author's own warning: all modules are **bypassed when not in use**, but modules opened together all
  run in the background; use **no more than 2 open at once**, take what you need, then close/delete the module "to avoid
  potential crashes" [SRC Patreon post + Notion]. No numbers given. It is a workspace-building tool: the pulled-out elements
  are what remain in a finished project, and their per-frame cost is [UNV].
- **Network / phoning home:** nothing in the docs mentions network access, accounts or licence keys; the Install Module flow
  uses a local file browser [SRC Notion]. That is absence of evidence only: **[UNV]** until the `.tox` is expanded (e.g.
  `toeexpand` on a copy, search for `urllib`/`requests`/`webclient`/`tcp` etc.), exactly the audit we would do.

## 2. Author, licence, version, platform

| Item | Finding |
|---|---|
| Licence (exact terms) | "UI Engine is free to use in both personal and commercial projects. You're welcome to build with it, ship with it, and make money with it." Forbidden: (1) "Redistribute, share, or sell the UI Engine .tox file itself, or any modified version of it, as a standalone product"; (2) "Include UI Engine, in whole or in part, as part of a paid asset pack, template, or toolkit that you distribute." "A mention or credit ... is always appreciated." [SRC Notion, "LISCENSE" (sic)]. It is a **custom proprietary licence, not an open-source one** (no SPDX identifier, no source repo). |
| Price | The Patreon post is `is_paid: false`, `min_cents_pledged_to_view: null`, but `current_user_can_view: false` for an anonymous reader, so **the download is behind a Patreon login (and possibly a tier)**. Patreon tiers shown: Free $0, "Basic Toolkit" $4/month ("Access to all my .tox files"), "Full Projects" $8/month [SRC Patreon campaign JSON]. **Which tier unlocks this post's files is not stated** [UNV]. Attached files (names and sizes are public): `UI_Engine files.zip` (344,357 bytes) and `UI_Engine_HowToUse_Example_VvDv.toe` (205,140 bytes). The asset page itself lists no price [SRC]. |
| Version / TD build | "Version 1.0 developed with TD 2025.33070 in 2026" [SRC Notion]. Our target 31550 is **older** (build numbering: 33070 > 31550), same major 2025. A `.tox` made in a newer build can load in an older one only if it uses nothing newer; **[UNV]**, and the H rule applies: TDXMorph at 33230 was already judged a risk. |
| OS | Not stated anywhere [UNV]. `.tox`-only tool, so macOS is likely but not claimed. Our TD runs x86_64 under Rosetta. |
| Last update | Post edited 10 Sep 2026 [SRC]. No changelog. |
| Open issues | No public tracker; 0 comments. The author asks for feedback on Instagram/email [SRC]. |
| Support risk | Single hobbyist-scale author; show is 24 Oct 2026 (8 days away). |

**Licence and our repo.** We would keep the `.tox` in `jazib-td-mcp/` for pinning/audit. A private local copy for the user's own
shows is covered ("free ... commercial"). But anything that ships the tool or a modified copy to others (a published bundle,
a shared repo, a template) is covered by the redistribution clause. If `jazib-td-mcp/` is ever published, the `.tox` must be
excluded (keep it git-ignored, record the SHA-256 and the source URL in `AUDIT.md` instead). Also our own panel `.tox`
must not embed UI Engine elements if that `.tox` were ever shared.

## 3. Fit with our framework (`SHOW_PANEL.md`)

| Question | Answer |
|---|---|
| Replace `ui` (Parameter COMPs `global_ctrl` + `look_ctrl`)? | **No.** UI Engine has no documented link from a COMP's parameters to elements. The Parameter COMP already shows any COMP's custom pars live, with zero wiring (verified in SHOW_PANEL: `look_ctrl` follows the live look). |
| Sit on top of it? | **Only as decoration:** e.g. copy a styled slider/meter element out and bind it by hand to `op.SHOW.par.Master`. That is the same hand-binding H §3.1 already designs with plain Slider/Button COMPs, plus a dependency, so no gain for controls. Possibly useful for read-only display (level meters, a flash-limiter lamp, a state readout) **if** the native modules contain such widgets [UNV]. |
| Auto-build per-look panels from each look COMP's custom pars ("specific controls over each comp")? | **Not provided.** Elements are copied one click at a time by a human in the Viewer; there is no scripted API documented (the click hooks exist inside modules, but they are internal and undocumented). A scripted build (td_exec looping over `look.customPars`) would need reverse-engineering the elements first. The shipped `Palette/UI/Basic Widgets/Tools/autoUI.tox` does exactly this loop with `bindExpr` (expanded and quoted in H §3.1 [X]); that is the better-proven route, and the Parameter COMP is the zero-code route already live. |
| MIDI mapping later? | Not a feature of UI Engine. Our `midi_map` table + router writes the same `state` / look pars the panel shows, independent of which widgets draw them (H §3.7). Adopting UI Engine changes nothing there. |
| Perform mode / Window COMP / touch? | Not covered by its docs. Our `ui_window` Window COMP + Perform mode path is independent. One conflict to note: the tool is built around the Viewer in **Panel mode inside the network editor** (build-time interaction), not a runtime panel generator. |
| 1080x1920 / portrait operator panel? | Resolution is a single `Proj Resolution` value; aspect handling beyond that [UNV]. |
| Extra cost | A second widget system next to Parameter COMPs and (planned) plain Slider/Button COMPs; elements are extra COMPs per control (cost [UNV]; H measured nothing for Basic Widgets either, only quoted a 2021 forum report of ~15 fps with widget fields). |

## 4. What adopting it would require (if the user ever wants it)

Per our rules (`AUDIT.md`: audited, pinned, free licence, nothing phones home; user's OK before any download):
1. User's go-ahead to download; user logs in to Patreon himself (post is gated; which tier unknown, free-tier follow may suffice).
   The agent must not use his credentials.
2. Download `UI_Engine files.zip` into its own empty directory outside the repo; record SHA-256, size, date, source URL.
3. Audit on a copy: `toeexpand` the `.tox`; grep for network / file-write / `os`/`subprocess`/`eval`/`exec`/`webclient`/`tcp`/`osc`
   use; read the extension code; check the licence statement is present in the file; check every embedded font/asset licence.
4. Decide on the redistribution clause: keep the `.tox` git-ignored; `AUDIT.md` row with hash, licence text quoted, build 33070.
5. Load test in a scratch project (`/project1/_research_probe`), `td_errors`, check it loads on **2025.31550 / macOS Rosetta**,
   note which native modules contain sliders / buttons / meters, and whether elements expose a value we can `bindExpr` to.
6. Only then decide on use; never put it on the show path unless a bench shows binding both ways and acceptable `td_perf` cost.

## 5. Recommendation: **skip** for the show panel (revisit only for decorative/read-out widgets)

Reasons, each a fact above:
1. **Wrong tool for the stated need.** The need is controls per look driven by custom pars; UI Engine is a copy-out element
   library with hand wiring and no documented parameter binding [SRC Notion]. It would add work, not remove it.
2. **We already have the need covered with shipped, proven parts:** Parameter COMPs (live, verified in SHOW_PANEL) and
   `autoUI.tox` (bind recipe expanded and read in H §3.1).
3. **Build mismatch.** Made on 2025.33070; our final build is 31550 and the host rule is "no upgrade". H already rejected
   TDXMorph for the same reason.
4. **Opaque and unproven.** Closed-source, gated download, 6 weeks old, 0 comments, no changelog or tracker, undocumented
   contents of the modules, undocumented MIDI/presets/perform support, and the author's own crash warning when several
   modules are open. The show is 24 Oct; the bind/MIDI/Window steps in H §5 are the real risks to spend time on.
5. **Licence friction.** Usable commercially but not redistributable; adds a "keep out of any shared bundle" constraint.

Possible value (low priority, only on the user's request): a nicer-looking, themed read-out page (meters, state display,
flash lamp) for the operator monitor, if the native modules turn out to include such widgets. Check that after step 5 above.

Alternatives noticed in the search (not read in depth, **[DESC]/[UNV]**, none downloaded):
- **UberGui V4**, Lucas Morgan (lucasm), Derivative asset page dated 4 Feb 2021: "a layer of abstraction directly on top of Custom
  Parameters", WebRender TOP UI on a separate thread, CSS-variable styling [SRC https://derivative.ca/community-post/asset/ubergui-v4-lightweight-multi-threaded-webrender-ui-module-custom-parameters];
  GitHub https://github.com/EnviralDesign/UberGui (licence and build not checked; my GitHub API query returned no data).
  This is the closest to "auto-UI from custom parameters", but it is from 2021 and web-based.
- **VIBE-Controller**: HTML Canvas UI inside TD, values arrive via Web Server DAT as CHOP channels; free tier unidirectional,
  Pro (paid) has bidirectional + presets + auto layout + themes [DESC from a search snippet; https://derivative.ca/community-post/asset/vibe-controller-touchdesigner-build-any-ui-claude-code/74272 , page not read].
- **Widgets** (forum.derivative.ca/t/widgets-modular-drop-in-widget-library-to-build-uis/998013): drag-and-drop widget library
  with presets [DESC from a search snippet, not read].
- **Built in:** `Palette/UI/Basic Widgets` + `autoUI.tox` (H §1.1).
H's recommendation (build our own from plain COMPs + borrow autoUI's bind recipe) stands unchanged by this finding.

## 6. Not retrievable / limits of this research

- The Patreon web page (403) and the gated files: I could not see the post's attachments, so module contents and the example
  `.toe` are unseen. Only the public post JSON (title, teaser text, file names and sizes, tier list) was read.
- The Notion "Managing your workspace" table (4 rows; button names and meanings) did not return.
- The YouTube channel page returned no video list; no video demonstrating UI Engine was found. The Derivative page links the
  author's YouTube channel only; the author says tutorials are "coming soon".
- Nothing was run: no performance, macOS, 31550-compatibility or phone-home claim is verified.

## 7. Open questions for the lead

1. Is the goal only the **operator control panel** (then skip, as above), or also a prettier read-out/monitor page where UI Engine
   elements could help? If the latter, say so and I'd ask the user for a download OK (Patreon login is his).
2. If the user wants an **auto-built per-look panel** beyond Parameter COMPs: try the shipped `autoUI.tox` first (no download),
   and read UberGui's repo/licence (GitHub, no download needed to read) before considering anything gated.
3. Is `jazib-td-mcp/` ever published or shared? That decides whether the no-redistribution clause matters.
4. Does the operator panel need to be portrait/tablet? UI Engine's docs say nothing; the Window COMP + Perform mode path in H §5 step 10 is the plan.
