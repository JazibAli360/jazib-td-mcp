#!/usr/bin/env node
// Jazib MCP for TouchDesigner — stdio MCP server. Every tool goes through the local bridge to the /jazib_mcp COMP that
// a running TD connected (TD dials out; it opens no port). Contract: docs/PROTOCOL.md.
import { AsyncLocalStorage } from 'node:async_hooks';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { registerDebug, withSnapshots } from './debug.js'; // debug toolkit (kept apart from the sorted block: merges)
import { registerCrash } from './crash.js'; // td_crash_report (crash fingerprints; kept apart: merges)
import { registerTimeline } from './timeline.js'; // td_timeline_* (TL_timeline agent API; kept apart: merges)
import { registerLibrary } from './library.js'; // td_library_* (component library; kept apart: merges)
import { registerVat } from './vat.js'; // td_vat_load (VAT playback; lane T, kept apart: merges)
import { registerMetavido } from './metavido.js'; // td_metavido (colour+depth+pose video; lane T)
import { chanName, parseAeExport, probeFrames, readAeFile } from './ae.js';
import { opName as blOpName, planImport as blPlan, readSidecar as blSidecar, runBlenderExport } from './blender.js';
import { bridgeHealth, call as bridgeCall, ensureBridge, token, TOKEN_FILE } from './bridge.js';
import { BUNDLE, CONFIG, ROOT } from './config.js';
import { runHealth } from './health.js';
import { help as tdHelp } from './help.js';
import { journaled, readJournal } from './journal.js';
import { diffNet, looksLikeNetText, parseNet } from './netdiff.js';
import { offline as tdOffline } from './offline.js';
import { pickWindow, WINDOWS_JXA } from './windows.js';
import { BUILDS, bringHome, identityProblem, readLanes, SIDES, sideCall, TARGETS } from './scratch.js'; // side TDs: scratch T-83, b2/b3 T-120

// Every bridge call lands in logs/calls.jsonl (src/journal.js; td_log reads it); a side TD's in logs/<name>/.
const tok = () => { try { return token(); } catch { return undefined; } };
const mainCall = journaled(bridgeCall, CONFIG.logDir, tok);
const sideCalls = Object.fromEntries(Object.keys(SIDES).map((n) => [n, journaled((c, a, t) => sideCall(n, c, a, t), SIDES[n].logDir, tok)]));
// target (T-120): a tool call with target 'scratch'|'b2'|'b3' runs inside TARGET.run(name), so every bridge call it
// makes (typed tools, debug snapshots, library) goes to that side TD; no target = the main TD.
const TARGET = new AsyncLocalStorage();
const call = (cmd, args, timeoutMs) => { const t = TARGET.getStore(); return t && t !== 'main' ? sideCalls[t](cmd, args, timeoutMs) : mainCall(cmd, args, timeoutMs); };
const logDirFor = (t) => (t && t !== 'main' ? SIDES[t].logDir : CONFIG.logDir);

const server = new McpServer({ name: 'jazib-td', version: '0.1.0' });
const text = (o) => ({ content: [{ type: 'text', text: typeof o === 'string' ? o : JSON.stringify(o, null, 1) }] });
const fail = (e) => ({ isError: true, content: [{ type: 'text', text: String(e && e.message || e) }] });
const HOW_TO_CONNECT = `TouchDesigner is not connected to the bridge. Open TouchDesigner, open your project and load the /jazib_mcp COMP (see README.md: run the install line from td/install.py once). It reads the token from ${TOKEN_FILE} and dials ws://127.0.0.1:${CONFIG.bridgePort}.`;
const fromBundle = (f) => (f ? path.resolve(BUNDLE, f) : f);

// Wraps a TD tool: bridge up, TD connected (and it is the main TD), then the tool body. target (T-120) is taken off
// the args; a side target checks its own TD on every call (src/scratch.js sideCall).
const mainHandler = (name, fn) => async (args) => {
  // only TARGETABLE tools + td_exec: others (td_midi_map, td_why...) have their own `target` arg
  const routed = TARGETABLE.has(name) || name === 'td_exec';
  const { target = 'main', ...rest } = routed ? (args || {}) : {};
  const a = routed ? rest : (args || {});
  try {
    if (target === 'main') {
      await ensureBridge();
      const h = await bridgeHealth();
      if (!h?.td) return fail(HOW_TO_CONNECT);
      const why = identityProblem('main', h.tdInfo);
      if (why) return fail(why);
    }
    const out = await TARGET.run(target, () => withSnapshots(name, a, call, () => fn(a), { cfg: CONFIG, outDir: CONFIG.outputDir })); // debug.js: opt-in
    return out && out.content ? out : text(out);
  } catch (e) { return fail(e); }
};
// Tools that take target (T-120): build on a side TD with the usual tools, then td_bring_home into main.
const TARGETABLE = new Set(['td_errors', 'td_save_project', 'td_checkpoint', 'td_restore_checkpoint', 'td_library_export', 'td_list', 'td_info',
  'td_get_pars', 'td_set_pars', 'td_create', 'td_connect', 'td_delete', 'td_inspect', 'td_screenshot', 'td_layout', 'td_tox_save', 'td_tox_load', 'td_net_export', 'td_perf', 'td_health', 'td_isf',
  'td_vat_load', 'td_metavido']);
const targetArg = z.enum(TARGETS).optional().describe('main (default) = the session TD; scratch = the disposable scratch TD; b2..b5 = the build TDs (tools/scratch_td.py --name b2|b3|b4|b5)');
function tool(name, description, shape, fn) {
  server.registerTool(name, { description, inputSchema: TARGETABLE.has(name) ? { ...shape, target: targetArg } : shape }, mainHandler(name, fn));
}
// A tool that is one bridge command with the same args.
const plain = (name, cmd, description, shape, map = (a) => a, timeoutMs = 60000) => tool(name, description, shape, (a) => call(cmd, map(a), timeoutMs));

// Shared schemas
const opPath = z.string().describe('Absolute TD path, e.g. /project1/noise1');
const parValue = z.any().describe('A plain value, or {val?, expr?, bindExpr?, mode?: "CONSTANT|EXPRESSION|EXPORT|BIND", menu?}. A pulse par with true is pulsed.');
const parsShape = z.record(z.string(), parValue);
const xy = z.tuple([z.number(), z.number()]);
// td_tda: each action gets only the args its TD command takes (check none; load parent/name/accept_risk/connect; status path).
const TDA_ARGS = { check: [], load: ['parent', 'name', 'accept_risk', 'connect'], status: ['path'] };
const tdaArgs = (action, a) => Object.fromEntries((TDA_ARGS[action] || []).filter((k) => a[k] !== undefined).map((k) => [k, a[k]]));
const family = z.enum(['TOP', 'CHOP', 'SOP', 'DAT', 'COMP', 'MAT', 'POP']);

server.registerTool('td_guide', { description: 'Read first: how to drive TouchDesigner through this MCP (rules, workflow, TD gotchas). Then call td_status.', inputSchema: {} }, async () => {
  const p = path.join(ROOT, 'docs', 'USING_TD.md');
  return text(fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : 'docs/USING_TD.md is missing. Basics: call td_status first; paths are absolute TD paths (/project1/noise1); after every build call td_errors and verify wiring with td_info; save a .tox copy (td_tox_save) before big changes; td_exec runs any Python in TD and is logged.');
});

// Claude sees what the user sees (26 Oct 2026): TD's own windows via macOS screencapture, no TD round trip, so it also
// works while TD is frozen or a dialog is up. Needs Screen Recording for the terminal app (granted 26 Oct).
server.registerTool('td_window_capture', { description: 'See TouchDesigner as the user does: capture one of its windows (default the main network window; window = part of a title, e.g. "PF26 Show Panel" or a dialog title) as an image, without bringing it to the front. Lists every open TD window, so dialogs/popups show up. Works with TD frozen or disconnected.', inputSchema: { window: z.string().optional(), maxSize: z.number().int().min(200).max(3000).optional() } }, async (a) => {
  try {
    const wins = JSON.parse(execFileSync('osascript', ['-l', 'JavaScript', '-e', WINDOWS_JXA], { encoding: 'utf8', timeout: 10000 }).trim() || '[]');
    const w = pickWindow(wins, a.window);
    const list = wins.filter((x) => x.title).map((x) => ({ title: x.title, w: x.w, h: x.h }));
    if (!w) return text({ error: a.window ? `no TD window titled like ${JSON.stringify(a.window)}` : 'no TouchDesigner window on screen', windows: list });
    fs.mkdirSync(CONFIG.outputDir, { recursive: true });
    const file = path.join(CONFIG.outputDir, `window_${w.title.replace(/[^\w.-]+/g, '_').slice(0, 40)}_${new Date().toISOString().replace(/[:.]/g, '-')}.png`);
    execFileSync('screencapture', ['-x', '-o', '-l', String(w.id), file], { timeout: 15000 });
    execFileSync('sips', ['-Z', String(a.maxSize || 1600), file], { timeout: 15000, stdio: 'ignore' });
    const data = fs.readFileSync(file);
    return { content: [{ type: 'image', data: data.toString('base64'), mimeType: 'image/png' }, { type: 'text', text: JSON.stringify({ file, window: w.title, windows: list }) }] };
  } catch (e) { return fail(String(e.message || e).includes('could not create image') ? 'screencapture refused: grant Screen Recording to the terminal app (System Settings > Privacy & Security)' : e); }
});

// Offline op-type / par / docs lookup (26 Oct 2026, research AF #6): our live 2025.31550 op dump + TD's shipped param
// help and offline wiki (src/help.js). No TD round trip, so it works with TD disconnected.
server.registerTool('td_help', { description: 'Look up TouchDesigner op types offline (no TD needed; build 2025.31550 dump + TD\'s shipped help). {op:"noiseTOP"} -> family, summary, inputs/outputs and its parameters by page (name, label, style, default, menu names/labels, range, clamps); page/par filter it and add each par\'s help text; docs:true adds the offline wiki summary. {search:"blur"} -> matching op types, best first. {par:"resolutionw"} -> which op types have it. Check par names and menu values here before td_create/td_set_pars.', inputSchema: {
  op: z.string().optional().describe('op type, e.g. noiseTOP (or "Noise TOP")'), page: z.string().optional(), par: z.string().optional().describe('with op: filter its pars; alone: which ops have this par'),
  docs: z.boolean().optional().describe('with op: add the offline wiki summary'), search: z.string().optional(), family: family.optional(), limit: z.number().int().min(1).max(200).optional(),
} }, async (a) => { try { return text(tdHelp(a || {})); } catch (e) { return fail(e); } });

server.registerTool('td_status', { description: 'Bridge health plus TouchDesigner state (build, version, project, folder, fps, perform mode, frame, timeline). Works with TD disconnected: then it says how to connect.', inputSchema: {} }, async () => {
  try {
    await ensureBridge();
    const h = await bridgeHealth();
    const bridge = { port: CONFIG.bridgePort, pid: h?.pid, output_dir: CONFIG.outputDir };
    if (!h?.td) return text({ bridge, td_connected: false, how_to_connect: HOW_TO_CONNECT });
    return text({ bridge, td_connected: true, since: h.tdInfo?.since, hello: h.tdInfo, ...(await call('status', {}, 15000)) });
  } catch (e) { return fail(e); }
});

plain('td_list', 'list', 'List operators under a COMP: path, name, type, family, errors/warnings flags, child count. depth > 1 recurses; filter by family or type (e.g. "noiseTOP"); limit caps the count (truncated says if more exist).',
  { path: z.string().optional().describe('COMP to list (default /)'), depth: z.number().int().min(1).optional(), family: family.optional(), type: z.string().optional(), limit: z.number().int().min(1).max(10000).optional() });

plain('td_info', 'info', 'One operator in detail: type, family, inputs/outputs wiring, errors, warnings, cook times, resolution/channels/rows where they apply, and its parameters (only non-default ones unless allPars).',
  { path: opPath, allPars: z.boolean().optional() });

plain('td_get_pars', 'get_pars', 'Read parameters of an operator: value, mode (CONSTANT/EXPRESSION/EXPORT/BIND), expression, default, menu names/labels, range, read-only, custom. Filter by names or page.',
  { path: opPath, names: z.array(z.string()).optional(), page: z.string().optional() });

plain('td_set_pars', 'set_pars', 'Set parameters: {name: value} or {name: {val|expr|bindExpr|mode|menu}}. menu matches a menu name or label (warns on a miss). A pulse par with true is pulsed. Colours: "#rrggbb" or "#rrggbbaa" on an RGB(A) group name (constantTOP {color:"#00baff"} -> colorr/g/b (+ alpha); bgcolor -> bgcolorr.. + bgalpha; custom Tint -> Tintr..Tinta) or on one member sets the whole group (value/255, no sRGB step); a Str par keeps the text. Returns the names set, warnings and colors.',
  { path: opPath, pars: parsShape });

plain('td_create', 'create', 'Create an operator inside a COMP, e.g. type "noiseTOP", "glslTOP", "baseCOMP". Optional name, parameters (td_set_pars shape) and position: xy, or after (path of the op feeding it: placed to its right on the same row), else a clean new row under the COMP\'s ops (never stacked at 0,0). Returns path and xy. The COMP is then re-arranged (always-arrange; arrange:false skips, an explicit xy skips). Generator TOPs (noise, constant, ramp, circle, rectangle, text, glsl, glslmulti, render, script) are created at 1080x1920 (vertical 1080p, user rule) unless res or resolution pars say otherwise.',
  { parent: opPath, type: z.string().describe('TD op type, e.g. noiseTOP'), name: z.string().optional(), xy: xy.optional(), arrange: z.boolean().optional(), res: z.union([z.tuple([z.number().int(), z.number().int()]), z.literal(false)]).optional().describe('generator TOPs default to 1080x1920 (user rule); [w,h] overrides, false skips'), after: z.string().optional().describe('op this one follows: placed right of it'), pars: parsShape.optional() });

plain('td_housekeeping', 'housekeeping', 'Read-only housekeeping report of a COMP (default /project1; spec docs/research/U_housekeeping_workspace.md): errors/warnings, COMPs whose layout check fails, default names (noise1), duplicate op shortcuts, slowest ops and GPU memory, locked/bypassed/hidden ops, viewers off (count), orphan candidates (no outputs, no references, not display/render; tag keep to exempt), debug leftovers (probe/tmp/test names, debug tag, todo comments), missing externaltox/syncfile files, CrashAutoSave + numbered .toe files, look output resolutions, project settings. Skips the inside of clones, palette packages and /jazib_mcp. Changes nothing: orphans are for the user to decide.',
  { path: z.string().optional(), top: z.number().int().min(1).max(50).optional() }, (a) => a, 120000);

plain('td_inspect', 'inspect', 'Numeric readback of one op, read-only (answers "is it moving / not black / in range" without a screenshot). Force-cooks it (cook:false skips), reads 1 frame later. CHOP: numChans, numSamples, rate, per channel min/max/mean/last (max 32; channels = glob like "t*" or "tx ty"); full adds the first rows samples. TOP: width/height/format + per-RGBA min/max/mean over all pixels (numpyArray), sample:N adds an NxN grid of cell means (row 0 = top; full defaults to 4); numpy broken in TD (T-48) falls back to a few TOP.sample points with a note. DAT: table rows/cols + first rows rows, or text line count + first lines. SOP: numPoints/numPrims/bounds/attribute names. POP: point/prim/vert counts, bounds, attribute names (full: first P values). COMP: children by family/type. Missing APIs give notes, never errors.',
  { path: opPath, detail: z.enum(['summary', 'full']).optional(), channels: z.union([z.string(), z.array(z.string())]).optional(), rows: z.number().int().min(0).max(100).optional(), sample: z.number().int().min(0).max(16).optional(), cook: z.boolean().optional() });
// Network as text (26 Oct 2026; idea from Embody's TDXN, MIT): export a COMP as deterministic JSON lines, diff two.
const NET_EXPORT_SHAPE = {
  depth: z.number().int().min(1).max(99).optional().describe('COMP levels to enter (default 99 = all)'),
  include_defaults: z.boolean().optional().describe('every par, not only non-default ones (default false)'),
  dat_text: z.boolean().optional().describe('editable DAT text: whole when small, else hash + first lines (default true)'),
  xy: z.boolean().optional().describe('node position and color too (default false)'),
};
const netOpts = (a) => Object.fromEntries(['depth', 'include_defaults', 'dat_text', 'xy'].filter((k) => a[k] !== undefined).map((k) => [k, a[k]]));
// A file the export writes or the diff reads: relative -> under output/ (".jtdnet" added when no extension).
function netFile(f, { write = false } = {}) {
  const out = path.resolve(CONFIG.outputDir);
  let p = path.isAbsolute(f) ? path.resolve(f) : path.resolve(out, f);
  if (!path.extname(p)) p += '.jtdnet';
  if (write && p !== out && !p.startsWith(out + path.sep)) throw new Error(`file must be under ${out}`);
  return p;
}
async function liveExport(p, opts, max_chars = 4000000) {
  await ensureBridge();
  const h = await bridgeHealth();
  if (!h?.td) throw new Error(HOW_TO_CONNECT);
  return call('net_export', { path: p, ...opts, max_chars }, 120000);
}

tool('td_net_export', 'Read-only: a COMP (or one op) as compact, deterministic text (JSON lines, format jtd-net; one op per line, depth-first by name): per op type, non-default pars ("=expr", "~bind", "@export"), inputs by name + output index, COMP inputs, dock, flags, comment, tags, custom pars by page (style/value/default/range/menu), editable DAT text (whole if small, else sha1 + first lines); xy:true adds node position + color. Clones, op-shortcut packages and /jazib_mcp are listed but not entered. No timestamp: an unchanged network exports byte-identical. file (relative = under output/, .jtdnet added) saves it and returns a summary; else the text comes back (capped ~60k chars, says if truncated). Snapshot before a change, then td_net_diff.',
  { path: opPath, ...NET_EXPORT_SHAPE, file: z.string().optional().describe('save under output/ (e.g. "snapshots/look1_before")') }, async (a) => {
    const file = a.file ? netFile(a.file, { write: true }) : null;
    const r = await call('net_export', { path: a.path, ...netOpts(a), max_chars: file ? 4000000 : 60000 }, 120000);
    const meta = { ops: r.ops, total: r.total, chars: r.chars, truncated: r.truncated, ...(r.notes?.length ? { notes: r.notes } : {}) };
    if (file) {
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, r.text);
      return { file, ...meta, ...(r.truncated ? { hint: 'truncated at 4M chars: export a smaller COMP or lower depth' } : {}) };
    }
    return { content: [{ type: 'text', text: r.text }, { type: 'text', text: JSON.stringify({ ...meta, ...(r.truncated ? { hint: 'truncated: pass file to save the whole export, or lower depth' } : {}) }) }] };
  });

server.registerTool('td_net_diff', { description: 'Read-only: compare two network exports and list added / removed ops, changed pars (per name, [a, b], null = default), changed custom pars, rewired inputs and any other changed field. a and b are each export text, a saved export file (relative = under output/, from td_net_export file), or a live TD COMP path ("/project1/look1", exported now with the other side\'s options). Diffing two files works without TD. Use: td_net_export file before a change, then td_net_diff {a: that file, b: the COMP path}.',
  inputSchema: { a: z.string(), b: z.string(), ...NET_EXPORT_SHAPE, max: z.number().int().min(1).max(5000).optional().describe('cap per list (default 200)') } }, async (args) => {
  try {
    const sides = [args.a, args.b].map((s) => {
      if (looksLikeNetText(s)) return { label: 'text', text: s };
      const f = netFile(s);
      if (fs.existsSync(f) && fs.statSync(f).isFile()) return { label: f, text: fs.readFileSync(f, 'utf8') };
      if (s.startsWith('/') && !path.extname(s)) return { label: `live ${s}`, live: s };
      throw new Error(`no export file ${f} (and not a TD path or export text): ${JSON.stringify(s)}`);
    });
    const known = sides.find((x) => x.text);
    const hdr = known ? parseNet(known.text).header : {};
    const opts = { ...netOpts(hdr), ...netOpts(args) };
    for (const x of sides) if (x.live) x.text = (await liveExport(x.live, opts)).text;
    const d = diffNet(sides[0].text, sides[1].text, { max: args.max || 200 });
    return text({ a_from: sides[0].label, b_from: sides[1].label, ...d });
  } catch (e) { return fail(e); }
});

plain('td_layout', 'layout', 'Clean network layout of a COMP (docs/research/G_network_layout.md). mode flow: arrange left-to-right by wire depth, main chain (input 0) on one row, side inputs below, separate streams as bands (CHOP, DAT, TOP/SOP/POP/MAT, COMP), docked DATs under their op; colors:true tints roles (input blue, control amber, output green, feedback red). mode check: report overlaps, right-to-left wires, ops piled at 0,0 (changes nothing). mode annotate: a titled network box around ops (names in the COMP; default all). mode stages (human-readable, user rule): flow, then one titled coloured box per stage with a short note (stages [{ops, title, body, role}]), spaced so boxes never overlap. The plan is stored on the COMP: every later re-flow (any build) re-applies it and places new ops itself (wired -> its neighbour\'s stage, unwired panels/windows/scripts -> Controls, else Other); check then fails on an op inside a box it is not in, an op in no box, or boxes on each other. mode unstage: drop the plan + its boxes, plain flow. create/connect/disconnect/delete/tox_load already re-flow the COMP they touch (always-arrange, user rule); call flow after td_exec builds, check to verify.',
  { path: opPath, mode: z.enum(['flow', 'check', 'annotate', 'stages', 'unstage']).optional(), ops: z.array(z.string()).optional(), title: z.string().optional(), colors: z.boolean().optional(), xy: xy.optional(),
    stages: z.array(z.object({ ops: z.array(z.string()).min(1), title: z.string(), body: z.string().optional(), role: z.enum(['input', 'process', 'control', 'output', 'feedback', 'note']).optional(), after: z.array(z.string()).optional().describe('titles of stages this one depends on without a wire (parameter references)') })).optional(),
    arrange: z.enum(['mixed', 'rows', 'columns']).optional().describe('stages: mixed (default) = feeding stages to the left, parallel stages stacked, inside a stage wire depth left->right and branches top->bottom; rows = one row per stage; columns = side by side') });

plain('td_focus', 'focus', 'Show the user an operator (they watch TD live): the network editor pane (the one they are in, else the first) goes to its parent COMP, the op is made current and selected (other selections there cleared; select:false leaves selection alone) and homed; zoom:true zooms to it, a number sets the pane zoom. flash:true (opt-in, default off: it tints the user\'s node) tints it yellow for ~0.5 s, then puts its colour back. UI only, no undo step. Notes say what was not possible (no network pane).',
  { path: opPath, select: z.boolean().optional(), zoom: z.union([z.boolean(), z.number().positive()]).optional(), flash: z.boolean().optional() });

plain('td_selection', 'selection', 'What the user is pointing at right now: network pane and its COMP, selected ops (capped list + count), current op, the op under the mouse (rollover) and this = the op "this node" means (current/selected, never the rollover; null if several are selected and none is current: ask). Read-only.', {});

plain('td_delete','delete', 'Delete operators by path. Returns deleted and missing paths; re-arranges the parent COMPs.', { paths: z.array(z.string()).min(1), arrange: z.boolean().optional() });

plain('td_rename', 'rename', 'Rename an operator. Returns its new path.', { path: opPath, name: z.string() });

plain('td_move', 'move', 'Move an operator in the network editor to xy (node units).', { path: opPath, xy });

plain('td_connect', 'connect', 'Wire src output outIndex into dst input inIndex, then check it took (fails if not). An inIndex beyond the connector count fails naming the count; a GLSL TOP takes more than 3 inputs through its tops par.',
  { src: opPath, dst: opPath, outIndex: z.number().int().min(0).optional(), inIndex: z.number().int().min(0).optional(), arrange: z.boolean().optional() });

plain('td_disconnect', 'disconnect', 'Remove the wire into dst input inIndex. Returns dst inputs after; re-arranges the COMP.', { dst: opPath, inIndex: z.number().int().min(0), arrange: z.boolean().optional() });

plain('td_dat_text', 'dat_text', 'Read a DAT\'s text (no text given) or set/append it. Set returns the new length.',
  { path: opPath, text: z.string().optional(), append: z.boolean().optional() });

plain('td_errors', 'errors', 'Force-cook the operators under path (cook:false skips that; unviewed ops never cook otherwise), wait some frames, then list operators with errors or warnings (recursive by default). TD reports GLSL compile errors as warnings; the compile log is included. Script errors (callback/extension/Script-op exceptions) come as "Script: ...". Call after every build.',
  { path: z.string().optional(), frames: z.number().int().min(0).max(600).optional(), recurse: z.boolean().optional(), cook: z.boolean().optional() });

tool('td_screenshot', 'Save a TOP\'s current image as PNG under output/ and return it as an image (plus path, size). Use any TOP path; for another op type, point it at a TOP that shows it.', { path: opPath }, async (a) => {
  fs.mkdirSync(CONFIG.outputDir, { recursive: true });
  const name = a.path.replace(/^\/+/, '').replace(/[^\w.-]+/g, '_') || 'root';
  const file = path.join(CONFIG.outputDir, `${name}_${new Date().toISOString().replace(/[:.]/g, '-')}.png`);
  const r = await call('screenshot', { path: a.path, file }, 30000);
  const data = fs.readFileSync(r.file || file);
  return { content: [{ type: 'image', data: data.toString('base64'), mimeType: 'image/png' }, { type: 'text', text: JSON.stringify({ file: r.file || file, width: r.width, height: r.height, bytes: data.length }) }] };
});

plain('td_custom_pars', 'custom_pars', 'Add custom parameters on a page of a COMP. Names: one capital then lowercase/digits (checked first). style Float|Int|Toggle|Pulse|Menu|Str|RGB|XY|File. Existing names are skipped. mirror (instead of pars): copy the built-in pars of an op INSIDE the COMP onto it and bind them (inner.bindExpr = parent(n).par.<Custom>, so the COMP drives its insides): {src: "./blur1" or a path inside, pars?: globs ["size*"], pages?: ["Blur"] (default every page but Common), prefix?, replace_expr?: replace inner expressions with the binding}. Tuplets stay together (tx ty -> one XY), menus/ranges/defaults copied, current values kept, pulses relayed by a mirror_pulse Parameter Execute DAT; read-only pars skipped. Reply: mirrored [{name, style, bound}], skipped [{par, why}].',
  { path: opPath, page: z.string(), mirror: z.object({ src: z.string(), pars: z.array(z.string()).optional(), pages: z.array(z.string()).optional(), prefix: z.string().optional(), replace_expr: z.boolean().optional() }).optional(),
    pars: z.array(z.object({
    name: z.string(), label: z.string().optional(), style: z.enum(['Float', 'Int', 'Toggle', 'Pulse', 'Menu', 'Str', 'RGB', 'XY', 'File']),
    size: z.number().int().optional(), default: z.any().optional(), min: z.number().optional(), max: z.number().optional(),
    normMin: z.number().optional(), normMax: z.number().optional(), clampMin: z.boolean().optional(), clampMax: z.boolean().optional(),
    menuNames: z.array(z.string()).optional(), menuLabels: z.array(z.string()).optional(),
  })).min(1).optional() });

plain('td_tox_save', 'tox_save', `Save a COMP as a .tox. A relative file resolves against the bundle root (${BUNDLE}). stamp (default true) first sets an About page on the COMP: Version (kept; version sets it, bump major|minor|patch counts it up; 0.1.0 the first time), Touchbuild (this TD build), Saved (local time), so the .tox says which build made it. stamp:false saves as is.`,
  { path: opPath, file: z.string(), stamp: z.boolean().optional(), version: z.string().optional(), bump: z.enum(['major', 'minor', 'patch']).optional() }, (a) => ({ ...a, file: fromBundle(a.file) }));

plain('td_tox_load', 'tox_load', `Load a .tox into a parent COMP (optional name). A relative file resolves against the bundle root (${BUNDLE}). Returns the new COMP's path.`,
  { parent: opPath, file: z.string(), name: z.string().optional(), arrange: z.boolean().optional() }, (a) => ({ ...a, file: fromBundle(a.file) }));

plain('td_save_project', 'save_project', `Save the .toe: in place, or to file (relative resolves against ${BUNDLE}).`,
  { file: z.string().optional() }, (a) => ({ ...a, file: fromBundle(a.file) }));

plain('td_perf', 'perf', 'Slowest-cooking operators under path (cook, CPU and GPU times), slowest first.', { path: z.string().optional(), top: z.number().int().min(1).max(1000).optional() });

// TD + ComfyUI (26 Oct 2026, research AL 4.2): a comfy COMP in TD whose client threads talk to a loopback ComfyUI
// (Comfy Desktop, default 127.0.0.1:8188). Nothing here waits on ComfyUI: send returns a job id, result/status poll.
const COMFY_OUT = () => path.join(CONFIG.outputDir, 'comfy');
const comfyComp = z.string().describe('the comfy COMP, e.g. /project1/comfy (td_comfy_build makes it)');
const comfyWorkflow = (w) => (typeof w === 'string' && !/^\s*[{/]/.test(w) ? fromBundle(w) : w);
plain('td_comfy_build', 'comfy_build', 'Build (or refresh in place) a tidy ComfyUI bridge COMP: client Text DAT (td/comfy_client.py: stdlib threads + urllib, never blocks TD), workflow Text DAT, status + jobs Table DATs, Execute DAT pump, result Movie File In TOP -> out Null TOP; viewers on, arranged; custom par Url. url must be loopback (127.0.0.1/localhost/::1). Probes ComfyUI once (td_comfy_status reads it).',
  { parent: z.string().optional().describe('default /project1'), name: z.string().optional().describe('default comfy'), url: z.string().optional().describe('default http://127.0.0.1:8188') });
plain('td_comfy_status', 'comfy_status', 'Read-only: is ComfyUI reachable from the comfy COMP (version, device, VRAM, queue) plus the last jobs. A thread probes GET /system_stats + /queue (2 s timeout); with ComfyUI closed it says reachable:false cleanly.',
  { comp: comfyComp, frames: z.number().int().min(1).max(300).optional().describe('frames to wait for the probe (default 20)') });
tool('td_comfy_send', 'Queue a ComfyUI job from TD, returns at once with job (= prompt_id). workflow: API-format JSON (object or text), a .json file (relative = bundle root) or a DAT path; default the COMP\'s workflow DAT. UI-format exports are refused (use "Save (API Format)"). inputs {"6.text": "...", "3.seed": 42} set node inputs (node + input must exist; links are never overwritten). image_from: a TOP saved as PNG and uploaded (multipart) to ComfyUI input/jazib_td; it goes to the input whose value is "$image", else the first LoadImage. REFUSES graphs with partner/API (credit-spending) nodes unless confirm_spend:true, which needs the user\'s go-ahead for this job. Results land in output/comfy/ and load into <comp>/out.',
  { comp: comfyComp, workflow: z.union([z.string(), z.record(z.string(), z.any())]).optional(), inputs: z.record(z.string(), z.any()).optional(),
    image_from: z.string().optional().describe('TOP path to send as the input image'), confirm_spend: z.boolean().optional().describe('only with the user\'s explicit go-ahead: allow partner/API nodes that spend credits'),
    timeout_s: z.number().int().min(5).max(3600).optional(), load: z.boolean().optional().describe('load the first image into <comp>/result when done (default true)') },
  (a) => call('comfy_send', { ...a, workflow: comfyWorkflow(a.workflow), out_dir: COMFY_OUT() }, 60000));
plain('td_comfy_result', 'comfy_result', 'A job\'s state (starting/checking/uploading/queued/running/done/error/refused/timeout/cancelled), its files under output/comfy/ and, when done, loads the first image into <comp>/result (-> <comp>/out). job defaults to the latest; a prompt_id this COMP did not send (e.g. from the comfyui MCP) is fetched from /history + /view in a thread.',
  { comp: comfyComp, job: z.string().optional(), load: z.boolean().optional(), timeout_s: z.number().int().min(5).max(3600).optional() }, (a) => ({ ...a, out_dir: COMFY_OUT() }));
plain('td_comfy_cancel', 'comfy_cancel', 'Cancel a ComfyUI job (default the latest running one): POST /queue delete + /interrupt from a thread.', { comp: comfyComp, job: z.string().optional() });
plain('td_comfy_free', 'comfy_free', 'Ask ComfyUI to unload models and free memory (POST /free) from a thread; frees the shared GPU for TD after a run. td_comfy_status shows the outcome.', { comp: comfyComp });

function execLog(row, dir = CONFIG.logDir) {
  fs.mkdirSync(dir, { recursive: true });
  fs.appendFileSync(path.join(dir, 'exec.log'), JSON.stringify({ time: new Date().toISOString(), pid: process.pid, ...(process.env.JTD_AGENT ? { agent: process.env.JTD_AGENT } : {}), ...row }) + '\n');
}
const short = (v) => { const s = typeof v === 'string' ? v : JSON.stringify(v); return s && s.length > 500 ? s.slice(0, 500) + '…' : s; };

// target 'scratch' (T-83) / 'b2' / 'b3' (T-120): a side TD (tools/scratch_td.py), logged to logs/<name>/ so the
// watchdog's exec.log signals (T-77, T-78) only ever describe the main TD.
const execBody = (a, viaCall, target = 'main') => async () => {
  const dir = logDirFor(target);
  execLog({ phase: 'start', code: a.code, ...(target !== 'main' ? { target } : {}) }, dir);
  try {
    const r = await viaCall('exec', { code: a.code, frames: a.frames || 0, ...(a.dialogs ? { dialogs: a.dialogs } : {}) }, a.timeout_ms || 60000);
    execLog({ phase: 'end', code: a.code, ok: true, result: short(r) }, dir);
    return r;
  } catch (e) { execLog({ phase: 'end', code: a.code, ok: false, error: short(e.message) }, dir); throw e; }
};
server.registerTool('td_exec', { description: 'Run any Python in TD (full access) with the TD globals (op, me, parent, project, app, td...). The last line\'s expression value comes back as result; stdout/stderr too. frames > 0 runs it that many frames later. Ops it creates get their viewers on, their COMP re-flowed and the network pane sent there (reply visible; the user watches live). Every call is logged to logs/exec.log (a side target: logs/<target>/exec.log). Prefer the typed tools when one fits. Modal dialogs never open from it (they would block TD and the reply): ui.messageBox returns 0 (first button), ui.chooseFile / ui.chooseFolder return None, each noted in reply.dialogs; dialogs {messageBox: index, chooseFile: path, chooseFolder: path} picks the answers. Only the exec namespace\'s ui is guarded (DAT modules/extensions it calls see the real one). target "scratch" runs it on the disposable scratch TD instead (T-83: start it with python3 tools/scratch_td.py start; its own bridge port ' + SIDES.scratch.port + ', logged to logs/scratch/exec.log; the crash guard becomes a note there): use it for code matching a known crash pattern (TOP reads after a change, cookRate/realTime, destroy under windows, complex-script fonts, window COMPs); on the main TD such code gets a note pointing here. target "b2" / "b3": a build TD (python3 tools/scratch_td.py start --name b2; ports 9337 / 9338; keeps + autosaves its project, crash guard on): build there, then td_bring_home into the main TD.',
  inputSchema: { code: z.string(), frames: z.number().int().min(0).max(600).optional(), timeout_ms: z.number().int().min(1000).max(600000).optional(),
    dialogs: z.object({ messageBox: z.number().int().min(0).optional(), chooseFile: z.string().nullable().optional(), chooseFolder: z.string().nullable().optional() }).optional(),
    target: targetArg } }, async (args) => {
  const a = args || {};
  return mainHandler('td_exec', (b) => execBody(b, call, a.target || 'main')())(a);
});

// Bring home (T-120, user 26 Oct: "save files and than bring comps in the main td file so everythings viewable in
// there"): COMP built in a build TD -> output/transfer/<name>.tox -> the main TD, checked, parked, both saved.
server.registerTool('td_bring_home', { description: 'Copy a COMP built in a build TD (b2/b3) into the MAIN TD so everything ends in the main .toe. In the build TD: COMP.save -> output/transfer/<name>.tox (safe_tox) + op count, then its project is saved. In the main TD (pre-saved: exec): a COMP of that name under parent is checkpointed (output/checkpoints/) then closed + safe_destroy (T-70) and its xy/colour/wires reused; the .tox loads under parent with the same name (a new one: the parent is arranged); 3 frames later errors are read, the stage plan re-applied, the COMP parked (park:false keeps it cooking), the main project saved. Refuses a COMP registered by another lane in logs/active_lanes.json (force only for your own). Reply: transfer file, main path, checkpoint of the old one, check {ops_equal, errors, warnings}, saves.',
  inputSchema: { comp: z.string().describe('COMP path in the build TD, e.g. /project1/lab/MyComp'), from: z.enum(BUILDS), parent: z.string().optional().describe('main-TD parent (default /project1/lab)'),
    park: z.boolean().optional().describe('default true (park idle COMPs)'), force: z.boolean().optional(),
    lane: z.string().optional().describe('your lane label as registered in logs/active_lanes.json: lets a lane bring home its own registered COMP (T-138)') } }, async (a) => {
  try {
    await ensureBridge();
    const h = await bridgeHealth();
    if (!h?.td) return fail(HOW_TO_CONNECT);
    const why = identityProblem('main', h.tdInfo);
    if (why) return fail(why);
    const side = sideCalls[a.from];
    return text(await bringHome(a, {
      sideExec: (code, frames) => execBody({ code, frames }, side, a.from)(), side,
      mainExec: (code, frames) => execBody({ code, frames, timeout_ms: 240000 }, mainCall, 'main')(), main: mainCall, // T-126: a big .tox load stalls main > 60 s
      lanes: () => readLanes(CONFIG.logDir), outDir: CONFIG.outputDir,
    }));
  } catch (e) { return fail(e); }
});

// TD -> Resolume Arena (26 Oct 2026; docs/research/AI_td_resolume.md "Proposed upgrades"). Built inactive: starting a
// Syphon/NDI sender or an OSC listener is the user's go-ahead. Never writes Arena's files.
const res2 = z.tuple([z.number().int().min(16).max(16384), z.number().int().min(16).max(16384)]);
plain('td_publish', 'publish', 'Send a TOP to Resolume Arena (or any Syphon/NDI app). Builds a tidy COMP publish_<name> under parent (default /project1): Select (source) -> Fit (only if res) -> alpha step (only if needed: Level premultiply, or one GLSL pass to un-premultiply / drop alpha) -> Null out -> Syphon Spout Out and/or NDI Out (skip frames, 8-bit, includealpha unless alpha none) + Info CHOP; viewers on, arranged. INACTIVE unless active:true (a sender = the user\'s go-ahead). alpha default premultiplied (bundle rule; source_alpha default premultiplied = TD\'s normal composite, so no step). Returns the exact sender name(s) to pick in Arena (Syphon: sender, default TD_<name>; NDI: "HOST (sender)") and the resolume-723 tools to use next. On an existing publish_<name>: {name, active} flips its senders (other args must match, else td_delete it first).',
  { name: z.string().regex(/^[A-Za-z][A-Za-z0-9_]{0,39}$/), source: opPath.optional().describe('TOP to send (required to build)'), transport: z.enum(['syphon', 'ndi', 'both']).optional(),
    alpha: z.enum(['premultiplied', 'straight', 'none']).optional(), source_alpha: z.enum(['premultiplied', 'straight']).optional().describe('what the source holds (TD composites: premultiplied)'),
    res: res2.optional().describe('[w,h]: Fit TOP (fit best) to this size; omitted = the source size'), active: z.boolean().optional().describe('default false (inactive)'),
    parent: opPath.optional(), sender: z.string().optional().describe('sender name in Arena (default TD_<name>)') });

plain('td_publish_status', 'publish_status', 'Read-only: every Syphon/NDI Out TOP in the project (td_publish COMPs first, name filters to publish_<name>): sender name, active, width/height, input, cook time; NDI fps/includealpha/skip-frames/8-bit and Info CHOP skipped_frames/last_send_time; project cookRate; warns on duplicate sender names.',
  { name: z.string().optional() });

// osc_addresses_<arena build>.json under output/ (same sanitising as td/handlers.py osc_export_name).
const oscExportName = (b) => `osc_addresses_${(String(b || 'arena').replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^[._]+|[._]+$/g, '') || 'arena').slice(0, 60)}.json`;
tool('td_osc_learn', 'Learn the OSC addresses a Resolume Arena build really sends (the old repo\'s `learn`, in TD). action build (default): COMP osc_learn_<port> under parent (default /project1) with an OSC In DAT (INACTIVE), callbacks, a learned table (address, count, first/last seen, last args) and a keep-cooking Execute DAT. start (opens a UDP port = the user\'s go-ahead; the user turns on Arena Preferences > OSC Output to 127.0.0.1:<port>): listens; with seconds it stops and exports after that long and replies then. stop: stop + export; export: write only. File: output/osc_addresses_<arena_build>.json. Port 7001 trade-off: Arena has ONE OSC Output target; while TD listens there resolume-723 osc_query/osc_subscribe go quiet (osc_send still works).',
  { action: z.enum(['build', 'start', 'stop', 'export']).optional(), port: z.number().int().min(1).max(65535).optional().describe('default 7001 (Arena OSC Output target in prefs)'),
    seconds: z.number().min(1).max(600).optional(), parent: opPath.optional(), arena_build: z.string().optional().describe('for the file name, e.g. 7.23.2.51094'), clear: z.boolean().optional().describe('start: empty the table first') },
  (a) => {
    const exporting = ['stop', 'export'].includes(a.action) || (a.action === 'start' && a.seconds);
    let file;
    if (exporting) { fs.mkdirSync(CONFIG.outputDir, { recursive: true }); file = path.join(CONFIG.outputDir, oscExportName(a.arena_build)); }
    return call('osc_learn', { ...a, ...(file ? { file } : {}) }, a.seconds ? a.seconds * 2000 + 30000 : 60000);
  });
// TD + Ableton Live (26 Oct 2026, docs/research/AJ_td_ableton.md section 4). Live itself is driven by the separate
// ableton-live MCP; these build the TD side. Pairs: docs/USING_TD.md "TD + Ableton".
plain('td_link', 'link', 'Ableton Link tempo/phase in TD (no Live install). Builds a COMP parent/name (arranged, viewers on): Ableton Link CHOP link1 -> select -> rename -> Null out with channels beat, bar, bar_ramp, tempo, peers; Info CHOP info on link1 (ableton_is_playing, ableton_tempo, clock diff). Link stays off unless enable:true; called again on an existing td_link COMP it only switches enable. Returns out values + numpeers/linked/synced. Live side: ableton-live set_ableton_link(true), set_tempo, start_playback.',
  { parent: z.string().optional().describe('default /project1'), name: z.string().optional().describe('default link'), enable: z.boolean().optional().describe('join the Link session (default false)') });

plain('td_link_status', 'link_status', 'Read-only: current out channels (beat, bar, bar_ramp, tempo, peers), Link status (numpeers, linked, waiting, synced) and Info channels of a td_link COMP, plus a hint when off or no peers.',
  { path: z.string().optional().describe('default /project1/link') });

tool('td_tda', 'TDAbleton (Derivative palette, ships in TD) health and loader. check (read-only): palette present + version, Live\'s Remote Scripts/TouchDesigner installed? (User Library from Live\'s Library.cfg, read only), AbletonMCP present, go/no-go list. load: loads the palette tdAbletonPackage.tox into parent as name with Connect off (connect:true turns it on), Listen Only on, address 127.0.0.1, popups suppressed; never presses Install/Update/Start, never touches Library.cfg. Needs accept_risk:true because the Live-side script binds 0.0.0.0:58888 and accepts remote Python (/shell/runCode): the user\'s go-ahead only. status (read-only): connected, pars, track names, duplicate names.',
  { action: z.enum(['check', 'load', 'status']), parent: z.string().optional(), name: z.string().optional(), path: z.string().optional().describe('status: package or master COMP'),
    accept_risk: z.boolean().optional(), connect: z.boolean().optional() },
  ({ action, ...a }) => call('tda_' + action, tdaArgs(action, a)));

plain('td_live_audio', 'live_audio', 'Switch the audio source of the AC_audio analysis COMP (default /project1/lab/AC_audio: src -> trim -> mono -> n_mono). file: Audio File In src (optional new file), device off. device: adds a Switch CHOP src_sel (src | src_device) before trim and an Audio Device In CHOP src_device, left inactive (analysis stays on the file) unless activate:true (mic permission prompt = the user\'s go-ahead); device picks a menu entry by name/label. Reports the device list and any loopback device / HAL driver (BlackHole etc., read-only). Live side: route Live\'s output to the loopback device (Live Settings, GUI); meters without a device: ableton-live get_master_meters.',
  { mode: z.enum(['file', 'device']), file: z.string().optional(), device: z.string().optional(), activate: z.boolean().optional(), path: z.string().optional() });
// TD + After Effects (26 Oct 2026; docs/research/AK_td_aftereffects.md). Pairs with the read-only `aftereffects` MCP:
// ae_project_export_json -> td_import_ae_anim; td_export_ae_data / td_render_for_ae -> files AE imports (write mode =
// the user's go-ahead). TD writes only under output/ae_out/; nothing here touches AE's mailbox or project files.
const AE_OUT = () => path.join(path.resolve(CONFIG.outputDir), 'ae_out');
function aeOutFile(f, ext) {
  const out = path.resolve(CONFIG.outputDir);
  let p = path.isAbsolute(f) ? path.resolve(f) : path.resolve(AE_OUT(), f);
  if (!path.extname(p)) p += ext;
  if (path.extname(p).toLowerCase() !== ext) throw new Error(`file must end with ${ext}: ${f}`);
  if (!p.startsWith(out + path.sep)) throw new Error(`file must be under ${out}`);
  if (/[^\x20-\x7e]/.test(p)) throw new Error(`file path must be ASCII: ${p}`);
  return p;
}
async function needTD() {
  await ensureBridge();
  const h = await bridgeHealth();
  if (!h?.td) throw new Error(HOW_TO_CONNECT);
}

server.registerTool('td_import_ae_anim', { description: 'After Effects animation -> TD. file = the JSON the aftereffects MCP wrote with ae_project_export_json (absolute, or relative to output/). Parsed here (exact AE temporal bezier from speed/influence, hold/linear keys, one sample per comp frame at the comp fps or rate) into one COMP under parent: meta / keys (long form, AE units) / text (Source Text keys) / markers Table DATs, baked table -> DAT to CHOP -> Null CHOP out (channels <layer>_<prop>_<dim>), report DAT of warnings (expressions not evaluated, spatial paths as straight segments, parenting). units td (default: position -> Transform TOP fraction, origin centre, y up; scale/opacity /100) or ae (raw). dry:true parses only (no TD needed). No Animation COMP yet (unprobed).',
  inputSchema: { file: z.string(), parent: z.string().optional().describe('default /project1'), name: z.string().optional().describe('default ae_<comp>'), comp: z.string().optional().describe('comp name or id (default the first comp)'),
    units: z.enum(['td', 'ae']).optional(), rate: z.number().positive().max(240).optional().describe('bake rate (default the comp fps)'), dry: z.boolean().optional() } }, async (a) => {
  try {
    const f = path.isAbsolute(a.file) ? a.file : path.resolve(CONFIG.outputDir, a.file);
    if (!/\.json$/i.test(f)) throw new Error(`file must be a .json export: ${f}`);
    const r = parseAeExport(readAeFile(f), { comp: a.comp, rate: a.rate, units: a.units });
    const summary = { file: f, comp: r.comp, units: r.units, channels: r.channels.length, channel_names: r.channels.slice(0, 20), keys: r.keys.length - 1, text: r.text.length - 1, markers: r.markers.length - 1, warnings: r.warnings };
    if (a.dry) return text({ dry: true, ...summary });
    await needTD();
    const name = a.name || ('ae_' + chanName(r.comp.name)).slice(0, 60);
    if (!r.channels.length) r.baked = [['none'], ...r.baked.slice(1).map(() => [0])];
    const td = await call('import_ae_anim', { parent: a.parent || '/project1', name, meta: r.meta, keys: r.keys, text: r.text, markers: r.markers, baked: r.baked, warnings: r.warnings }, 120000);
    return text({ ...td, comp: r.comp, units: r.units, warnings: r.warnings });
  } catch (e) { return fail(e); }
});

// Blender -> TD (26 Oct 2026; Blender 5.2.2 LTS; docs/research/BC_blender_td_scripts.md s6). tools/blender_export.py
// runs in a headless Blender (factory startup, autoexec off) and writes <name>.usdc/.fbx + <name>.json under
// output/blender/<name>/; the TD side builds one self-contained COMP. Writes nothing in Blender files.
server.registerTool('td_import_blender', { description: 'Blender scene -> one TD COMP. blend: a .blend (exported headless first: tools/blender_export.py, factory startup, scripts in the file never run) -> output/blender/<name>/<name>.usdc + .json sidecar; or usd/fbx: an existing export with its sidecar (default: same name .json). Builds under parent: geo (USD COMP, or FBX COMP; Y-up metres, import pulsed), one Camera COMP per Blender camera (horz FOV from lens + sensor fit + render aspect, lens shift -> winx/winy, clip -> near/far, ortho width), one Light COMP per light (point/cone/distant, colour, watts -> dimmer heuristic, cone + blend), projectors = lights with the Blender custom prop projector (image path or true = test ramp; projector_throw, projector_res, projector_shift): projection map TOP, simplehorzfov projangle = horizontal FOV from the throw, cone covers the image diagonal; ambient from the world colour; render TOP through the chosen camera -> out; sidecar + report DATs; controls on the Blender page (Camera, Light dimmer, Ambient, Render width/height); stage plan stored. dry:true plans only (no TD needed). First live run on the scratch TD (USD COMP import is unprobed).',
  inputSchema: { blend: z.string().optional(), usd: z.string().optional(), fbx: z.string().optional(), sidecar: z.string().optional(),
    parent: z.string().optional().describe('default /project1'), name: z.string().optional().describe('default bl_<scene file name>'),
    geo: z.enum(['usd', 'fbx', 'none']).optional().describe('default usd (fbx when only fbx is given)'), dry: z.boolean().optional() } }, async (a) => {
  try {
    const abs = (f) => (f ? (path.isAbsolute(f) ? f : path.resolve(CONFIG.outputDir, f)) : undefined);
    let sidecar = abs(a.sidecar), geo = a.geo || (a.fbx && !a.usd ? 'fbx' : 'usd'), file = abs(a.usd || a.fbx), exported = null;
    if (a.blend) {
      const blend = abs(a.blend);
      const base = blOpName('bl', path.basename(blend, path.extname(blend))).slice(3);
      const outDir = path.join(path.resolve(CONFIG.outputDir), 'blender', base);
      exported = runBlenderExport({ blend, outDir, name: base, format: geo === 'none' ? 'none' : geo, root: ROOT });
      sidecar = exported.sidecar;
      file = undefined;
    } else if (!sidecar) {
      if (!file) throw new Error('give blend, or usd/fbx (+ sidecar), or sidecar');
      sidecar = file.replace(/\.(usdc?|usda|usdz|fbx)$/i, '.json');
    }
    const side = blSidecar(sidecar);
    const plan = blPlan(side, { dir: path.dirname(sidecar), geo, file });
    const name = a.name || blOpName('bl', path.basename(sidecar, '.json'));
    const summary = { sidecar, exported, name, geo: plan.geo, cameras: plan.cameras, lights: plan.lights, projectors: plan.projectors, warnings: plan.warnings };
    if (a.dry) return text({ dry: true, ...summary, ops: plan.ops.map((o) => `${o.name}:${o.type}`) });
    await needTD();
    const td = await call('import_blender', { parent: a.parent || '/project1', name, ops: plan.ops, wires: plan.wires, controls: plan.controls,
      stages: plan.stages, sidecar: JSON.stringify(side, null, 1), report: plan.report }, 120000);
    return text({ ...td, ...summary });
  } catch (e) { return fail(e); }
});

tool('td_export_ae_data', 'Read-only in TD: write a CHOP\'s channels to an After Effects data-footage file under output/ae_out/ (json: {source, fps, frames, frame[], channels{name: []}}; csv: frame + one column per channel). frames: sample the CHOP\'s current values on each of the next N TD frames (live curves such as audio analysis; frame column = absTime.frame, gaps noted); without it: the CHOP\'s own samples. AE side (write mode, user\'s go-ahead): project.import_file + an expression reading footage(...).sourceData / dataValue.',
  { chop: opPath, file: z.string().describe('relative = under output/ae_out/'), format: z.enum(['json', 'csv']).optional(), frames: z.number().int().min(1).max(18000).optional() }, async (a) => {
    const format = a.format || 'json';
    const file = aeOutFile(a.file, '.' + format);
    return call('export_ae_data', { chop: a.chop, file, format, ...(a.frames ? { frames: a.frames } : {}) }, a.frames ? 60000 + a.frames * 1000 : 60000);
  });

tool('td_render_for_ae', 'Offline render of a TOP to a .mov under output/ae_out/ for After Effects (shared recorder offline_render, LEARNINGS T-11/T-29/T-30): fresh Movie File Out + pump, realTime off for the take and restored, one movie frame per TD frame, temp ops removed after. alpha premultiplied (default) = ProRes 4444 with alpha (12-bit yuva), none = ProRes 422 HQ; straight not built yet. Reply includes the ffprobe frame count (frames_ok = file frames == frames). AE side: footage.interpret alphaMode premultiplied, conform to fps.',
  { source: opPath, file: z.string().describe('relative = under output/ae_out/ (.mov added)'), frames: z.number().int().min(1).max(18000), fps: z.number().positive().max(240).optional(), alpha: z.enum(['premultiplied', 'none', 'straight']).optional() }, async (a) => {
    const file = aeOutFile(a.file, '.mov');
    const r = await call('render_for_ae', { source: a.source, file, frames: a.frames, fps: a.fps || 30, alpha: a.alpha || 'premultiplied' }, Math.min(600000, 90000 + a.frames * 2500));
    const probe = await probeFrames(file);
    return { ...r, ffprobe: probe, frames_ok: probe.frames === a.frames };
  });

// MIDI mapping (26 Oct 2026; own clean-room design, docs/research/AR_tdmap_midi.md section 6): a self-contained
// jazib_midi COMP in TD (td/midi_core.py value logic + td/midi_runtime.py TD I/O) that works without the MCP.
const midiComp = z.string().optional().describe('the jazib_midi COMP (default /project1/jazib_midi)');
const midiKind = z.enum(['cc', 'cc14', 'note', 'noteoff', 'pitchbend', 'aftertouch', 'program']);
const midiMapping = z.object({
  id: z.string().optional().describe('existing id = update (fields merged); none = new mapping'), bank: z.number().int().min(0).optional().describe('0 = always live; default the active bank'),
  label: z.string().optional(), kind: z.enum(['cc', 'cc14', 'note', 'pitchbend', 'aftertouch', 'program']).optional(), channel: z.number().int().min(0).max(16).optional().describe('1..16, 0 = any'),
  number: z.number().int().min(-1).max(127).optional().describe('CC / note number (cc14: MSB 0..31)'), target: z.string().optional().describe('absolute op path'), par: z.string().optional(),
  min: z.number().optional(), max: z.number().optional().describe('default the par\'s normMin/normMax'), default: z.number().optional(),
  curve: z.string().optional().describe('linear ease_in ease_out ease_in_out log exp smoothstep steps:N'), invert: z.boolean().optional(),
  mode: z.enum(['absolute', 'relative_2c', 'relative_bin', 'relative_sign', 'toggle', 'momentary', 'trigger']).optional(),
  takeover: z.enum(['none', 'pickup', 'scale']).optional(), smooth: z.number().min(0).max(10).optional().describe('seconds'), clamp: z.boolean().optional(),
  feedback: z.boolean().optional().describe('send the value back (LED rings, motor faders)'), step: z.number().positive().optional().describe('relative: norm per tick'),
});
const midiEvent = z.object({ kind: midiKind.optional(), channel: z.number().int().min(1).max(16).optional(), number: z.number().int().min(-1).max(127).optional(), value: z.number().int().min(-8192).max(16383).optional(), value2: z.number().int().min(0).max(127).optional() });
// midi_save / midi_load: relative files land under the TD project folder (bare name -> midi_maps/<name>); save never leaves it.
const midiFile = z.string().regex(/\.json$/i).describe('relative to the TD project folder ("show.json" -> midi_maps/show.json)');

plain('td_midi_build', 'midi_build', 'Build (or refresh in place, mappings kept) a self-contained MIDI mapping COMP (default /project1/jazib_midi) that keeps working in the saved .toe without the MCP: midi_core + runtime Text DATs (code from td/), bindings / config / events tables, MIDI In DAT (device = Device par = the MIDI Device Mapper id) -> callbacks -> engine, MIDI Out CHOP for LED feedback, Frame Start tick (smoothing, learn window, 10 Hz poll for soft takeover + feedback), Parameter Execute, a scrolling List COMP editor + editor_window. Custom page MIDI: Enable, Device, Activebank, Learn (hover a par, move a control), Feedback, Sendfeedback, Openeditor, Refreshdevices. Arranged in stage boxes. device picks a Device Mapper entry by id/name.',
  { path: midiComp, device: z.string().optional() });
plain('td_midi_status', 'midi_status', 'Read-only: MIDI devices from TD\'s /local/midi/device table (MIDI Device Mapper), the MIDI In DAT state, Enable/Feedback/Device, active bank and banks, mapping counts (live in bank, unbound slots, broken targets), learn state, last 5 messages, last feedback sent, last engine error.',
  { path: midiComp });
tool('td_midi_learn', 'MIDI learn. action start (default): target+par = bind that par to the next control moved; no target = hover mode (the par under the mouse, ui.rolloverPar, while the control moves); id = re-learn the message of that mapping. The engine collects ~0.5 s of messages and classifies them (knob/fader absolute, relative encoder 2c/bin/sign, button -> toggle / momentary / trigger by par style, 14-bit pair, pitch bend); min/max default to the par\'s normMin/normMax; other fields (curve, takeover, smooth, feedback, bank...) apply to the new mapping. One binding per par and bank: re-learn replaces it. wait_s (<= 120) replies when learned (or stops at the deadline); else it returns at once: then status. stop / finish (classify now) / status.',
  { path: midiComp, action: z.enum(['start', 'stop', 'finish', 'status']).optional(), target: z.string().optional(), par: z.string().optional(), id: z.string().optional(),
    mode: z.enum(['par', 'hover', 'slot']).optional(), wait_s: z.number().min(0).max(120).optional(),
    min: z.number().optional(), max: z.number().optional(), curve: z.string().optional(), takeover: z.enum(['none', 'pickup', 'scale']).optional(), smooth: z.number().min(0).max(10).optional(),
    feedback: z.boolean().optional(), bank: z.number().int().min(0).optional(), label: z.string().optional(), invert: z.boolean().optional(), clamp: z.boolean().optional(), step: z.number().positive().optional() },
  (a) => call('midi_learn', a, a.wait_s ? a.wait_s * 1000 + 30000 : 60000));
plain('td_midi_map', 'midi_map', 'Add a MIDI mapping explicitly, or update one (mapping.id known: only the given fields change). Validated by the engine (kinds, modes, curves, ranges); min/max default to the target par\'s normMin/normMax; channel 0 = any; bank 0 = always live. Unbound slot = no target. Returns the stored mapping.',
  { path: midiComp, mapping: midiMapping });
plain('td_midi_unmap', 'midi_unmap', 'Remove MIDI mappings by ids, or every mapping of target (+ par).', { path: midiComp, ids: z.array(z.string()).optional(), target: z.string().optional(), par: z.string().optional() });
plain('td_midi_list', 'midi_list', 'Read-only: all MIDI mappings (or one bank) with a short msg ("cc ch1 #7") and bound (target par found).', { path: midiComp, bank: z.number().int().min(0).optional() });
plain('td_midi_bank', 'midi_bank', 'Switch the active MIDI bank (>= 1; bank 0 mappings are always live): soft takeover resets, feedback re-sent. No bank: report active bank, banks and the live mapping ids.', { path: midiComp, bank: z.number().int().min(1).optional() });
plain('td_midi_save', 'midi_save', 'Save all MIDI mappings + active bank as JSON (format midi_core v1) under the TD project folder (bare name -> midi_maps/). Read-only in TD.', { path: midiComp, file: midiFile });
plain('td_midi_load', 'midi_load', 'Load MIDI mappings from a JSON file (relative = TD project folder; validated before anything changes); merge:true keeps mappings with other ids. Takeover state resets.', { path: midiComp, file: z.string().regex(/\.json$/i), merge: z.boolean().optional() });
plain('td_midi_monitor', 'midi_monitor', 'Read-only: the last n MIDI messages the engine saw (time, src midi/sim, kind, channel, number, raw, mapping ids written, note: learn / waiting for pickup / exported / disabled), the last feedback messages sent and the last engine error.', { path: midiComp, n: z.number().int().min(1).max(100).optional() });
plain('td_midi_simulate', 'midi_simulate', 'Test without hardware: inject MIDI as raw bytes into the same runtime entry the MIDI In DAT callback uses (learn, banks, takeover, curves, smoothing, feedback all apply). One message (kind, channel, number, value; pitchbend value 0..16383; cc14 = MSB+LSB pair) or events: [...] for a burst. frames > 0 replies that many frames later (smoothing / learn window ran). Returns the writes and the values after.',
  { path: midiComp, kind: midiKind.optional(), channel: z.number().int().min(1).max(16).optional(), number: z.number().int().min(-1).max(127).optional(), value: z.number().int().min(-8192).max(16383).optional(), value2: z.number().int().min(0).max(127).optional(),
    events: z.array(midiEvent).min(1).max(512).optional(), frames: z.number().int().min(0).max(600).optional() });
plain('td_midi_preset', 'midi_preset', 'Controller templates: no name = list them; name = add its controls as UNBOUND mapping slots (bank default = active) to bind later with td_midi_map {mapping:{id, target, par}} or the editor. Templates are marked verified or not: an unverified one is an assumption, re-learn on the real controller.', { path: midiComp, name: z.string().optional(), bank: z.number().int().min(0).optional() });
// td-atlas port (26 Oct 2026; grigabyte/td-atlas, commit 7cf8f57): health, trace, save hook, call journal, offline .toe.
tool('td_health', 'Read-mostly check for what TouchDesigner stays QUIET about (td_errors lists only what TD flags). Samples the COMP twice interval s apart (default 1, max 10) and reports findings by severity: ops that change but nothing pulls (not running), never-cooked, output ops switched off (Movie File Out, Audio/NDI/Syphon out...), GLSL compile failures, script/callback tracebacks, slow cooks (stale cook times told apart), fps below target / window throttled / timeline paused, bypassed gain ops (bypass passes the image through), feedback loops, Level TOPs making negative floats into an Add, absTime / unseeded random reads (non-reproducible renders), file pars naming missing files, CHOPs with NaN, licence resolution clamps, warnings. It asks quiet ops to cook() once (as a viewer would; no force, outputs never). recheck:true also clears each kept traceback and reads it 0.2 s later to tell live from stale (stale ones stay cleared). Run after building anything; then td_errors for messages.',
  { path: z.string().optional().describe('COMP to check (default /project1)'), interval: z.number().min(0).max(60).optional(), recheck: z.boolean().optional() },
  (a) => runHealth(call, { path: a.path || '/project1', interval: a.interval ?? 1, recheck: !!a.recheck }));

plain('td_trace', 'trace', 'Read-only "why is this TOP black?": walks up the TOP\'s wired inputs (breadth-first, depth default 8, max 40 nodes), reads each TOP\'s min/mean/max per RGBA (numpyArray at <= 256 px a side, no forced cook; reading an out-of-date image cooks it once) and marks where the signal was lost: "dropped here" (goes black while an input had something, or an Add fed negative values), "negative values start here", "alpha goes to 0 here", "NaN/Inf start here", with reasons from the node (bypass, lock, opacity 0, blacklevel, empty input, error). look_at lists the marks; "?" = an input could not be read. Wires only (Select/Render TOP references are not followed).',
  { path: opPath, depth: z.number().int().min(0).max(20).optional() });

plain('td_save_hook', 'save_hook', 'Network text on every save (default OFF): on:true installs an Execute DAT /jazib_mcp/save_hook (Project Post-Save) that writes <project>.<root>.jtdnet (td_net_export format) beside the .toe after each save, so the project gets a git-diffable history; the save number (X.3.toe) is dropped so one project keeps one text. path = COMP exported (default /project1, at most 2000 ops). Atomic write; a file already there that is not a jtd-net text is never overwritten. on:false removes the DAT; no on: status. write_now:true writes once now (test it without saving).',
  { on: z.boolean().optional(), path: z.string().optional(), write_now: z.boolean().optional() });

server.registerTool('td_log', { description: 'Your own trail (works with TD disconnected): every bridge call this MCP made, from logs/calls.jsonl (kept across sessions, 16 MB then rotated): time, cmd, ok, ms, op path, and for calls that change the project their args (pars set, code head of td_exec, DAT text clipped; secrets redacted). failures:true = only refusals; summary:true = calls/failures per command, top error reasons, 5 slowest; cmd filters ("set_pars"); since = ISO time or "-2h"/"-30m"/"-1d". Read it before retrying something that failed, or to see what was changed.',
  inputSchema: { limit: z.number().int().min(1).max(500).optional(), failures: z.boolean().optional(), summary: z.boolean().optional(), cmd: z.string().optional(), since: z.string().optional() } },
async (a) => { try { return text(readJournal(CONFIG.logDir, a || {})); } catch (e) { return fail(e); } });

server.registerTool('td_offline', { description: `Read a saved .toe/.tox WITHOUT TouchDesigner (TD's own toeexpand on a copy under output/offline/; the original is never touched; relative file = under ${BUNDLE}). mode tree (default): ops as "path type <- inputs (n pars) [flags] first DAT line", counts by family; path narrows to a COMP (e.g. /project1), depth limits levels. mode text: the network as jtd-net JSON lines (pars as saved strings, "=expr", "~bind"; DAT text whole or hash + head; custom par pages/names). mode grep (or just query): regex over the Python/GLSL/text inside DATs -> {p, line, text}. mode diff (or just other): compare with a second file: added/removed/changed ops, rewired, par and DAT text changes; ops only moved are listed apart. Format reverse-engineered (td-atlas): custom par values/definitions are partial.`,
  inputSchema: { file: z.string(), mode: z.enum(['tree', 'text', 'grep', 'diff']).optional(), path: z.string().optional(), depth: z.number().int().min(0).max(99).optional(), query: z.string().optional(), other: z.string().optional(), limit: z.number().int().min(1).max(2000).optional(), xy: z.boolean().optional() } },
async (a) => { try { return text(tdOffline(a || {}, { base: BUNDLE, cacheRoot: path.join(CONFIG.outputDir, 'offline') })); } catch (e) { return fail(e); } });

// MCP upgrades 27 Oct 2026 (research AM / AN / AY / AU): record CHOP, Shadertoy, OSC expose, layer mixer, cook guard.
// Recordings: relative .csv -> output/recordings/ (never outside output/).
function recFile(f) {
  const out = path.resolve(CONFIG.outputDir);
  let p = path.isAbsolute(f) ? path.resolve(f) : path.resolve(out, 'recordings', f);
  if (!path.extname(p)) p += '.csv';
  if (path.extname(p).toLowerCase() !== '.csv') throw new Error(`file must end with .csv: ${f}`);
  if (!p.startsWith(out + path.sep)) throw new Error(`file must be under ${out}`);
  return p;
}
tool('td_record_chop', 'Record a CHOP: its current values once per TD frame for frames N (or seconds x cookRate) into a Table DAT (frame, time, one column per channel; default <chop parent>/<chop>_rec, or table = name / absolute path; append:true adds rows) and optionally a .csv under output/recordings/. channels = globs ("tx ty" or ["kick*"]). Freezes audio features / OSC / LFO tracks for a repeatable bake. Replies when done (frame gaps from dropped frames are noted).',
  { chop: opPath, seconds: z.number().positive().max(600).optional(), frames: z.number().int().min(1).max(18000).optional(), table: z.string().optional(),
    file: z.string().optional().describe('relative = under output/recordings/ (.csv added)'), channels: z.union([z.string(), z.array(z.string())]).optional(), append: z.boolean().optional() },
  (a) => {
    if ((a.seconds === undefined) === (a.frames === undefined)) throw new Error('give seconds or frames (one of them)');
    const args = { ...a, ...(a.file ? { file: recFile(a.file) } : {}) };
    const ms = Math.min(600000, 30000 + (a.seconds ? a.seconds * 2000 : a.frames * 70));
    return call('record_chop', args, ms);
  });

const ST_MAX = 512 * 1024;
tool('td_shadertoy', 'Shadertoy -> TD: paste the Image tab (mainImage) as code, or file (.glsl/.frag/.fs/.txt, relative = bundle root). Builds (or updates in place) a self-contained COMP under parent: source DAT (code + licence note), shader DAT (TD wrapper: iResolution, iTime, iTimeDelta, iFrame, iFrameRate, iMouse, iDate, iSampleRate, iChannel0..3 = sTD2DInputs, iChannelResolution, iChannelTime; #line 1 so compile errors give your line numbers), GLSL TOP (pixel; compute:true = compute shader, the T-47 tear-free path), iChannel Select TOPs on custom Channel0..3 pars (black when empty), clock (Play, Speed, Reset), Out TOP out1, own controls (Opencontrols). Resolution default 1080x1920. Replies after a few frames with compile ok/errors/log and warnings (cubemaps, sound, #version). Not supported: multi-buffer (Buffer A-D), Common tab (paste it above mainImage), keyboard/cubemap/sound inputs. Shadertoy shaders default to CC BY-NC-SA 3.0: pass licence/author/url, they stay on the COMP.',
  { code: z.string().optional(), file: z.string().optional(), parent: z.string().optional().describe('default /project1'), name: z.string().regex(/^[A-Za-z_][A-Za-z0-9_]*$/).optional().describe('default shadertoy'),
    compute: z.boolean().optional(), res: z.tuple([z.number().int().min(16).max(8192), z.number().int().min(16).max(8192)]).optional(),
    channels: z.array(z.string()).max(4).optional().describe('TOP paths for iChannel0..3'), licence: z.string().optional(), author: z.string().optional(), url: z.string().optional(),
    frames: z.number().int().min(1).max(120).optional().describe('frames to wait before reading the compile log (default 3)') },
  (a) => {
    if (!!a.code === !!a.file) throw new Error('give code or file (one of them)');
    let code = a.code;
    if (a.file) {
      const f = fromBundle(a.file);
      if (!/\.(glsl|frag|fs|txt)$/i.test(f)) throw new Error(`file must be .glsl/.frag/.fs/.txt: ${f}`);
      if (fs.statSync(f).size > ST_MAX) throw new Error(`file is over ${ST_MAX} bytes`);
      code = fs.readFileSync(f, 'utf8');
    }
    const { file, ...rest } = a; // eslint-disable-line no-unused-vars
    return call('shadertoy', { ...rest, code }, 60000 + (a.frames || 3) * 1000);
  });

// td_isf (FX0 phase 3 E / G-ISF): ISF .fs (+ .vs) -> GLSL TOP COMP; the parser + translator live in td/isf.py.
tool('td_isf', 'ISF (Interactive Shader Format, VDMX / Vidvox) -> TD: file = an ISF .fs (relative = bundle root; the sibling .vs with the same name is used when there, or vs_file), or code (+ vs). Builds (or updates in place) a self-contained COMP under parent (default name isf_<file stem>): source DATs, shader DAT (one GLSL 4.60 pixel shader shared by every pass: ISF built-ins IMG_PIXEL / IMG_NORM_PIXEL / IMG_THIS_PIXEL / IMG_THIS_NORM_PIXEL / IMG_SIZE, isf_FragNormCoord, RENDERSIZE, TIME, TIMEDELTA, FRAMEINDEX, DATE, PASSINDEX; the .vs folded in and run per pixel; #line so the log gives your line numbers), one GLSL TOP per PASS (WIDTH/HEIGHT expressions, FLOAT), Feedback TOPs for PERSISTENT targets, INPUTS as custom pars with ranges/defaults on page ISF (float, bool, event = pulse, long = menu or int, point2D = XY, color = RGBA), image inputs as TOP pars on page Images (the first falls back to the COMP in1), audio / audioFFT as CHOP pars (CHOP -> TOP), IMPORTED images (Movie File In, paths relative to the .fs), clock (Play, Speed, Reset clears buffers), Out TOP out1, zkit knob panel (panel:"plain" = Parameter COMP panel). <= 3 wired GLSL inputs, the rest via tops (T-88). Resolution default 1080x1920. images = {isf input name: TOP/CHOP path}. Replies after a few frames with compile ok/errors/log, the par map and warnings. Not supported: gl_Position displacement in the .vs, cube maps, several outputs. Vidvox ISF-Files are MIT; pass licence/author/url for others.',
  { file: z.string().optional(), vs_file: z.string().optional(), code: z.string().optional(), vs: z.string().optional(),
    parent: z.string().optional().describe('default /project1'), name: z.string().regex(/^[A-Za-z_][A-Za-z0-9_]*$/).optional().describe('default isf_<file stem>'),
    res: z.tuple([z.number().int().min(16).max(8192), z.number().int().min(16).max(8192)]).optional(),
    panel: z.enum(['zkit', 'plain']).optional(), images: z.record(z.string(), z.string()).optional(),
    licence: z.string().optional(), author: z.string().optional(), url: z.string().optional(),
    frames: z.number().int().min(1).max(120).optional().describe('frames to wait before reading the compile log (default 3)') },
  (a) => {
    if (!!a.code === !!a.file) throw new Error('give code or file (one of them)');
    const read = (f, exts) => {
      if (!new RegExp(`\\.(${exts})$`, 'i').test(f)) throw new Error(`file must be .${exts.split('|').join('/.')}: ${f}`);
      if (fs.statSync(f).size > ST_MAX) throw new Error(`file is over ${ST_MAX} bytes`);
      return fs.readFileSync(f, 'utf8');
    };
    const { file, vs_file: vsFile, ...rest } = a;
    const args = { ...rest };
    if (file) {
      const f = fromBundle(file);
      args.code = read(f, 'fs|frag|glsl|txt');
      args.source_name = path.basename(f);
      args.base_dir = path.dirname(f);
      const vf = vsFile ? fromBundle(vsFile) : f.replace(/\.[^./]+$/, '.vs');
      if (vsFile || (a.vs === undefined && fs.existsSync(vf))) { args.vs = read(vf, 'vs|vert|glsl|txt'); args.vs_file = vf; }
    } else if (vsFile) throw new Error('vs_file goes with file (with code, pass vs)');
    const { vs_file: _vf, ...send } = args; // eslint-disable-line no-unused-vars
    return call('isf', send, 60000 + (a.frames || 3) * 1000);
  });

plain('td_osc_expose', 'osc_expose', 'Publish a COMP\'s custom pars as an OSC address tree from a self-contained sibling COMP <comp>_osc (or name/parent): map table (one row per par group = the allow-list), runtime DAT, OSC Out DAT (send, change-only, max rate_hz), OSC In DAT (receive: writes ONLY mapped pars, values coerced to the par style; no eval, no command route), optional OSCQuery JSON (oscquery DAT always; Web Server DAT when oscquery:true, answers loopback clients only unless loopback_only:false) and own controls (Opencontrols, Sendall, Rebuildmap). layout plain: /<prefix>/<Par> (prefix default the COMP name; tuplets = one message, N args); osct: OSCToolset/UE5 /OSCT/R/<TYPE>/<prefix>_<Par> out, /OSCT/S/... in (port 9999 / in 9998 by default; plain 9000 / 9001). Host defaults 127.0.0.1. Send, receive and the server stay OFF unless active / receive / oscquery are true (each = network traffic: the user\'s go-ahead).',
  { comp: opPath, name: z.string().regex(/^[A-Za-z_][A-Za-z0-9_]*$/).optional(), parent: z.string().optional(), host: z.string().optional(), port: z.number().int().min(1).max(65535).optional(),
    active: z.boolean().optional(), receive: z.boolean().optional(), in_host: z.string().optional(), in_port: z.number().int().min(1).max(65535).optional(),
    rate_hz: z.number().min(0.1).max(240).optional(), layout: z.enum(['plain', 'osct']).optional(), prefix: z.string().optional(),
    pages: z.array(z.string()).optional(), pars: z.array(z.string()).optional().describe('par globs'),
    oscquery: z.boolean().optional(), oscquery_port: z.number().int().min(1).max(65535).optional(), loopback_only: z.boolean().optional() });

const MIX_BLENDS = ['over', 'add', 'screen', 'multiply', 'subtract', 'difference', 'maximum', 'minimum', 'overlay', 'softlight', 'hardlight', 'under', 'inside', 'outside', 'atop', 'average'];
plain('td_layer_mixer', 'layer_mixer', 'Build (or update in place) an N-layer mixer COMP (VJ style, research AU): a shared source bank (sources = TOP or COMP paths; a COMP gives its Out TOP), per layer custom page Layer<n>: L<n>source (menu), L<n>opacity, L<n>blend (Composite operand), L<n>mute, L<n>solo; Mixer page: Master, Masterfx (fx_slot COMP: put a master effect between its in1 and out1), Resw/Resh (default 1080x1920), Fit, Cookguard. Layer n = mix(below, composite(source, below), opacity x mute/solo), skipped by a Switch at 0 (no cook). Cookguard: COMP sources no visible layer shows get allowCooking off. Out TOP out1 = the mix only; own controls (Opencontrols). Fewer layers on a rebuild remove the extra ones.',
  { parent: z.string().optional(), name: z.string().regex(/^[A-Za-z_][A-Za-z0-9_]*$/).optional(), layers: z.number().int().min(1).max(16).optional(),
    sources: z.array(z.string()).max(64).optional(), blend: z.enum(MIX_BLENDS).optional(),
    res: z.tuple([z.number().int().min(16).max(8192), z.number().int().min(16).max(8192)]).optional(), fit: z.enum(['fill', 'fithorz', 'fitvert', 'fitbest', 'fitoutside', 'nativeres']).optional(),
    cook_guard: z.boolean().optional() });

plain('td_cook_active', 'cook_active', 'Cooking guard (research AU): allowCooking on for the active COMPs, off for the other candidates, so only what is shown costs GPU/CPU. Candidates: paths (COMPs) or the child COMPs of parent matching pattern (default *). active = names or paths among them (an unknown one is an error; empty = all off). Never touches the MCP COMP or its ancestors. One undo step.',
  { active: z.array(z.string()).optional(), paths: z.array(z.string()).optional(), parent: z.string().optional(), pattern: z.string().optional() });

// Debug toolkit (26 Oct 2026): td_analyze, td_analyze_file, td_why, td_watch, td_journal, td_debug_panel (src/debug.js).
registerDebug({ server, tool, call, text, fail, z, CONFIG, ROOT, BUNDLE });
// td_crash_report (26 Oct 2026; src/crash.js + td/crashdb.py): works with TD dead.
registerCrash({ server, text, fail, z, CONFIG, ROOT });
// TL_timeline agent API (phase 4; src/timeline.js -> handlers timeline_* -> the COMP's TimelineExt).
registerTimeline({ tool, call, z, CONFIG });
// Component library (27 Oct 2026; src/library.js -> handlers library_* -> td/library.py): library/<Name>/.
registerLibrary({ tool, call, z, ROOT });
// VAT playback + Metavido decoder (27 Oct 2026, lane T; src/vat.js -> td/vat.py, src/metavido.js -> td/metavido.py).
registerVat({ tool, call, z, CONFIG, ROOT });
registerMetavido({ tool, call, z, CONFIG, ROOT, BUNDLE });

// Lose nothing (26 Oct 2026, after crashes T-64/T-70/T-74/T-76; td/safety.py): pre-risk save + per-COMP .tox checkpoints.
const CKPT_ROOT = () => { const t = TARGET.getStore(); return path.join(CONFIG.outputDir, t && t !== 'main' ? `checkpoints_${t}` : 'checkpoints'); }; // a side TD's own folder
plain('td_checkpoint', 'checkpoint', 'Checkpoint one COMP as a .tox after its build verifies: output/checkpoints/<comp>/<comp>_<stamp>.tox + .json (parent, xy, wires, allowCooking, stage plan, build), newest keep (5) kept. verify (default true) force-cooks the COMP and checks errors frames (2) later; errors -> nothing saved ({saved:false, errors}) unless force. The COMP stays as it is (no About stamp, never switched to externaltox). list:true lists its checkpoints (and pre_restore copies) without saving. Call it after td_errors is clean at the end of every builder step.',
  { path: opPath, verify: z.boolean().optional(), frames: z.number().int().min(2).max(120).optional(), keep: z.number().int().min(1).max(50).optional(),
    note: z.string().max(300).optional(), force: z.boolean().optional(), list: z.boolean().optional() },
  ({ list, ...a }) => ({ ...a, ...(list ? { list_only: true } : {}), root: CKPT_ROOT() }), 120000);
plain('td_restore_checkpoint', 'restore_checkpoint', 'Reload a COMP from its checkpoint (after a crash lost it, or a rebuild broke it), T-70-safe: the current COMP is first saved to <dir>/pre_restore/ (lose nothing; the project is pre-saved too), the .tox loads into the same parent with cooking off, the old COMP goes through safe_destroy (windows closed, panes moved, destroy deferred), the new one takes the name, xy, colour, wires (COMP inputs/outputs) and allowCooking, its stage plan is re-applied, windows that were open reopen frames (10) later; reply lists errors under it. which: "latest" (default), "previous", an index (0 = latest) or a stamp prefix ("20261026-1612"). Works when the COMP is missing (placed from the checkpoint record). One undo step.',
  { path: opPath, which: z.union([z.string(), z.number().int().min(0)]).optional(), frames: z.number().int().min(1).max(120).optional(), reopen: z.boolean().optional() },
  (a) => ({ ...a, root: CKPT_ROOT() }), 120000);
plain('td_presave', 'presave', 'Pre-risk save settings (on by default): before a risky call (td_exec / td_create of an op type this project never had, a .tox or C++ plugin load, font pars, a builder build, a destroy of COMPs, a module reload, a checkpoint restore, the typed builders) the project is saved in place first, at most once per min_s (60) s counting every save, skipped while realTime is off, in perform mode or before the first save. Replies of those calls carry pre_save {reasons, saved|skipped, ms}. "# no-presave" in exec code opts out. on / min_s set it; check {cmd, args} says what a call would do (nothing saved). Reply: on, min_s, count, skipped, last_file, last_save_s_ago, seen_types.',
  { on: z.boolean().optional(), min_s: z.number().min(10).max(3600).optional(), check: z.object({ cmd: z.string(), args: z.record(z.string(), z.any()).optional() }).optional() });

plain('td_autosave', 'autosave', 'Read or set the in-TD autosave (T-71/T-77): minutes (0 = off, default 5), keep (newest autosaves kept beside the .toe; older ones go to output/backups/autosave/), now=true saves at once. No args = read only. Agents normally leave it alone (tools/td_recover.py sets 5 min after a relaunch).',
  { minutes: z.number().min(0).optional(), keep: z.number().int().min(1).optional(), now: z.boolean().optional() });

plain('td_reload', 'reload','Re-read td/handlers.py from disk into the TD handlers DAT (after editing it; no reinstall). Pending requests are dropped.', {});

await ensureBridge().catch(() => {});
await server.connect(new StdioServerTransport());
