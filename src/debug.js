// Debug toolkit (26 Oct 2026; user: "a debug controller ... analyze projects u didnt start or see whats going on and
// exactly what happening or what u did"). Node half of td/debug.py: tools td_analyze, td_analyze_file, td_why,
// td_watch, td_journal, td_debug_panel; reports under output/debug/; the opt-in per-call snapshot hook. Contract:
// docs/PROTOCOL.md "Debug toolkit". Wired into src/server.js by registerDebug() + withSnapshots() (a few lines).
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { diffNet } from './netdiff.js';

export const TOEEXPAND = process.env.JTD_TOEEXPAND || '/Applications/TouchDesigner 2.app/Contents/MacOS/toeexpand';
export const PYTHON = process.env.JTD_PYTHON || 'python3';

// ---------------------------------------------------------------- small pure helpers

export const stamp = (d = new Date()) => d.toISOString().replace(/\.\d+Z$/, 'Z').replace(/[:]/g, '-');
export const slug = (s, n = 48) => (String(s || 'root').replace(/^\/+/, '').replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '') || 'root').slice(0, n);
const clip = (s, n = 160) => { s = String(s ?? ''); return s.length > n ? `${s.slice(0, n)}...` : s; };
const first = (s) => String(s ?? '').trim().split('\n')[0];
const items = (x) => (x && Array.isArray(x.items) ? x.items : Array.isArray(x) ? x : []);
const count = (x) => (x && typeof x.count === 'number' ? x.count : items(x).length);
const base = (p) => String(p || '').split('/').pop() || '/';

// "-30m" / "-2h" / "-1d" / ISO -> epoch ms (NaN when unparsable)
export function sinceMs(since, now = Date.now()) {
  const m = /^-(\d+(?:\.\d+)?)([smhd])$/.exec(String(since || ''));
  if (m) return now - Number(m[1]) * { s: 1e3, m: 60e3, h: 3600e3, d: 86400e3 }[m[2]];
  return Date.parse(since);
}

// ---------------------------------------------------------------- reports (markdown, mermaid, dot)

export function mermaid(s, maxNodes = 60) {
  const tl = s.graph?.top_level || { nodes: [], edges: [] };
  const nodes = tl.nodes.slice(0, maxNodes);
  const id = new Map(nodes.map((n, i) => [n.p, `n${i}`]));
  const lines = ['flowchart LR'];
  for (const n of nodes) lines.push(`  ${id.get(n.p)}["${base(n.p).replace(/"/g, "'")}<br/>${n.t} (${n.ops})"]`);
  const arrow = { wire: '-->', export: '==>', bind: '-.->', expr: '-.->', ref: '-.->', script: '-.->', callbacks: '-.->', extension: '-.->', module: '-.->', watch: '-.->' };
  const agg = new Map();
  for (const [a, b, k, c] of tl.edges) {
    if (!id.has(a) || !id.has(b)) continue;
    const key = `${a}\u0000${b}\u0000${k === 'wire' || k === 'export' ? k : 'ref'}`;
    agg.set(key, (agg.get(key) || 0) + c);
  }
  for (const [key, c] of agg) {
    const [a, b, k] = key.split('\u0000');
    lines.push(`  ${id.get(a)} ${arrow[k] || '-.->'}|${k} ${c}| ${id.get(b)}`);
  }
  if (tl.nodes.length > maxNodes) lines.push(`  more["+${tl.nodes.length - maxNodes} more"]`);
  return lines.join('\n') + '\n';
}

export function dot(s, maxNodes = 200) {
  const tl = s.graph?.top_level || { nodes: [], edges: [] };
  const nodes = tl.nodes.slice(0, maxNodes);
  const known = new Set(nodes.map((n) => n.p));
  const q = (x) => JSON.stringify(String(x));
  const lines = ['digraph td {', '  rankdir=LR; node [shape=box, fontname="Helvetica"];'];
  for (const n of nodes) lines.push(`  ${q(n.p)} [label=${q(`${base(n.p)}\n${n.t} (${n.ops})`)}];`);
  for (const [a, b, k, c] of tl.edges) if (known.has(a) && known.has(b)) lines.push(`  ${q(a)} -> ${q(b)} [label=${q(`${k} ${c}`)}${k === 'wire' ? '' : ', style=dashed'}];`);
  lines.push('}');
  return lines.join('\n') + '\n';
}

function treeMd(n, depth = 0, out = []) {
  if (!n) return out;
  out.push(`${'  '.repeat(depth)}- \`${n.p}\` ${n.t || ''} (${n.ops} ops)${n.package ? ` [package: ${n.package}]` : ''}${n.more_comps ? ` (+${n.more_comps} COMPs)` : ''}`);
  for (const k of n.kids || []) treeMd(k, depth + 1, out);
  return out;
}

function table(rows, cols) {
  if (!rows.length) return '_none_\n';
  const esc = (v) => String(v ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ');
  return [`| ${cols.map((c) => c[0]).join(' | ')} |`, `|${cols.map(() => '---').join('|')}|`, ...rows.map((r) => `| ${cols.map((c) => esc(typeof c[1] === 'function' ? c[1](r) : r[c[1]])).join(' | ')} |`)].join('\n') + '\n';
}

export function renderMarkdown(s, { title } = {}) {
  const h = s.health || {};
  const py = s.python || {};
  const L = [];
  const more = (x) => (count(x) > items(x).length ? `\n_${count(x) - items(x).length} more not listed (raise max_items)._\n` : '');
  L.push(`# ${title || `TD analysis: ${s.project || s.file || ''} ${s.root}`}`, '');
  L.push(`Source: ${s.source}${s.file ? ` (${s.file})` : ''} | build ${s.build || '?'} | root \`${s.root}\` | ops read ${s.ops}${s.total_ops !== undefined ? ` of ${s.total_ops}` : ''}${s.next_offset ? ` (next page: offset ${s.next_offset})` : ''} | ${s.ms} ms${s.frames ? ` over ${s.frames} frames` : ''}`, '');
  if (s.notes?.length) L.push(...s.notes.map((n) => `> ${n}`), '');
  L.push('## Summary', '');
  L.push(table([
    ['errors / warnings / script errors', `${count(h.errors)} / ${count(h.warnings)} / ${count(h.script_errors)}`],
    ['missing files', s.files?.missing ?? 0],
    ['devices + ports', count(s.devices)],
    ['Python: exec DATs (active) / callbacks / script ops / extensions', `${py.where?.exec_dats ?? 0} (${py.where?.exec_dats_active ?? 0}) / ${py.where?.callback_dats ?? 0} / ${py.where?.script_ops ?? 0} / ${py.where?.extensions ?? 0}`],
    ['expressions / binds / exports', `${count(s.expressions)} / ${count(s.binds)} / ${count(s.exports)}`],
    ['unresolved references', count(s.unresolved_refs)],
    ['dead-branch candidates', count(h.dead_branches)],
    ['cook-always / bypassed / locked / parked', `${count(h.cook_always)} / ${count(h.bypassed)} / ${count(h.locked)} / ${count(h.parked)}`],
    ['viewers on (cook while visible)', h.viewers_on ?? 0],
  ].map(([k, v]) => ({ k, v })), [['what', 'k'], ['', 'v']]));
  L.push('## Inventory', '', table(Object.entries(s.inventory?.by_family || {}).map(([f, n]) => ({ f, n })), [['family', 'f'], ['ops', 'n']]));
  L.push('Top types: ' + Object.entries(s.inventory?.by_type || {}).slice(0, 20).map(([t, n]) => `${t} ${n}`).join(', '), '');
  L.push('### COMP tree', '', ...treeMd(s.inventory?.comp_tree), '');
  if (s.inventory?.packages?.length) {
    const by = new Map();
    for (const x of s.inventory.packages) { const k = by.get(x.kind) || { kind: x.kind, comps: 0, kids: 0, example: x.p }; k.comps++; k.kids += x.kids || 0; by.set(x.kind, k); }
    L.push('### Packages (listed, not entered; include ["packages"] enters them)', '', table([...by.values()].sort((a, b) => b.comps - a.comps), [['kind', 'kind'], ['COMPs', 'comps'], ['children', 'kids'], ['example', 'example']]));
  }
  L.push('## Top-level flow', '', `Children of \`${s.graph?.top_level?.root || s.root}\`. Edges by kind: ${Object.entries(s.graph?.edges_by_kind || {}).map(([k, n]) => `${k} ${n}`).join(', ') || 'none'} (total ${s.graph?.edges_total ?? 0})`, '', '```mermaid', mermaid(s).trimEnd(), '```', '');
  L.push('## Where Python runs', '');
  if (py.where?.frame_callbacks?.length) L.push(`Every-frame callbacks: ${py.where.frame_callbacks.map((p) => `\`${p}\``).join(', ')}`, '');
  L.push('### Execute DATs', '', table(items(py.exec_dats), [['DAT', 'p'], ['type', 't'], ['active', 'active'], ['triggers', (r) => (r.triggers || []).join(' ')], ['watches', 'watches']]), more(py.exec_dats));
  L.push('### Callback DATs', '', table(items(py.callbacks), [['host', 'host'], ['host type', 'host_t'], ['callbacks DAT', 'dat'], ['found', 'found']]), more(py.callbacks));
  L.push('### Extensions', '', table(items(s.extensions), [['COMP', 'p'], ['par', 'par'], ['class', 'class'], ['DAT', 'dat'], ['object', 'object']]));
  if (items(py.script_ops).length) L.push('### Script ops', '', table(items(py.script_ops), [['op', 'p'], ['type', 't']]));
  if (items(py.modules).length) L.push('### Modules used (mod.X)', '', table(items(py.modules), [['module', 'name'], ['used by', (r) => r.used_by.join(', ')]]));
  if (s.runs?.available) L.push(`Delayed run() scripts pending: ${s.runs.count}`, '', table(s.runs.items || [], [['source', 'source'], ['frames', 'frames'], ['ms', 'ms']]));
  L.push('## Devices and ports', '', table(items(s.devices), [['op', 'p'], ['kind', 'kind'], ['active', 'active'], ['settings', (r) => Object.entries(r.settings || {}).map(([k, v]) => `${k}=${v}`).join(' ')]]));
  L.push('## External files', '', table(items(s.files), [['op', 'p'], ['par', 'par'], ['path', 'path'], ['exists', (r) => (r.exists === false ? '**MISSING**' : r.exists ? 'yes' : r.write ? '(written)' : r.url ? '(url)' : r.dynamic ? '(expression)' : '?')]]), more(s.files));
  L.push('## Cook health', '');
  L.push('### Errors', '', table(items(h.errors), [['op', 'p'], ['type', 't'], ['message', 'msg']]), more(h.errors));
  L.push('### Script errors', '', table(items(h.script_errors), [['op', 'p'], ['type', 't'], ['message', 'msg']]));
  L.push('### Warnings', '', table(items(h.warnings), [['op', 'p'], ['type', 't'], ['message', 'msg']]), more(h.warnings));
  L.push('### Heaviest (last cook)', '', table(h.heavy || [], [['op', 'p'], ['type', 't'], ['cpu ms', 'cpu_ms'], ['gpu ms', 'gpu_ms'], ['cooks', 'cooks'], ['stale', (r) => (r.stale ? `yes (${r.frames_since_cook} frames ago)` : '')]]));
  if (h.gpu_memory_mb?.length) L.push('### GPU memory', '', table(h.gpu_memory_mb, [['op', 'p'], ['MB', 'mb']]));
  L.push('### Cook-always pars', '', table(items(h.cook_always), [['op', 'p'], ['type', 't'], ['par', 'par']]));
  L.push('### Dead-branch candidates (no wire out, nothing refers to them, no display/render/export flag)', '', items(h.dead_branches).map((p) => `- \`${p}\``).join('\n') || '_none_', more(h.dead_branches), '');
  for (const [k, label] of [['bypassed', 'Bypassed'], ['locked', 'Locked'], ['parked', 'Parked (allowCooking off)'], ['exporting', 'CHOPs exporting']]) if (count(h[k])) L.push(`${label}: ${items(h[k]).map((p) => `\`${p}\``).join(', ')}`, '');
  L.push('## References', '');
  L.push('### Unresolved (dynamic or broken)', '', table(items(s.unresolved_refs), [['op', 'p'], ['par', 'par'], ['ref', 'ref'], ['tried', 'tried']]), more(s.unresolved_refs));
  L.push('### Binds', '', table(items(s.binds), [['op', 'p'], ['par', 'par'], ['bind', 'expr'], ['to', (r) => r.refs.join(', ')]]), more(s.binds));
  L.push('### Exports', '', table(items(s.exports), [['op', 'p'], ['par', 'par'], ['from', 'from']]), more(s.exports));
  L.push('### Expressions (first ones)', '', table(items(s.expressions).slice(0, 80), [['op', 'p'], ['par', 'par'], ['expr', 'expr'], ['refs', (r) => r.refs.join(', ')]]));
  L.push('### DAT text references', '', table(items(s.dat_refs).slice(0, 80), [['DAT', 'p'], ['refers to', (r) => r.refs.join(', ')]]));
  return L.join('\n') + '\n';
}

// Writes <name>_<stamp>.json / .md / .mmd / .dot under dir; returns their paths.
export function writeReport(s, dir, name, { now = new Date() } = {}) {
  fs.mkdirSync(dir, { recursive: true });
  const b = path.join(dir, `${slug(name)}_${stamp(now)}`);
  const files = { json: `${b}.json`, md: `${b}.md`, mermaid: `${b}.mmd`, dot: `${b}.dot` };
  fs.writeFileSync(files.json, JSON.stringify(s, null, 1));
  fs.writeFileSync(files.md, renderMarkdown(s));
  fs.writeFileSync(files.mermaid, mermaid(s));
  fs.writeFileSync(files.dot, dot(s));
  return files;
}

// The reply: counts + the first few of each list (the whole thing is in the files).
export function compactAnalysis(s, files, n = 8) {
  const h = s.health || {};
  const top = (x) => items(x).slice(0, n);
  return {
    source: s.source, root: s.root, project: s.project, file: s.file, build: s.build, ops: s.ops, total_ops: s.total_ops,
    ...(s.next_offset ? { next_offset: s.next_offset } : {}), ms: s.ms, frames: s.frames,
    inventory: { by_family: s.inventory?.by_family, types: s.inventory?.types, packages: (s.inventory?.packages || []).length },
    edges_by_kind: s.graph?.edges_by_kind,
    top_level: (s.graph?.top_level?.nodes || []).slice(0, 20).map((x) => `${x.p} ${x.t} (${x.ops})`),
    python: s.python?.where,
    devices: top(s.devices).map((d) => `${d.p} ${d.kind} active=${d.active} ${Object.entries(d.settings || {}).map(([k, v]) => `${k}=${v}`).join(' ')}`),
    files: { count: count(s.files), missing: s.files?.missing ?? 0, missing_list: items(s.files).filter((f) => f.exists === false).slice(0, n).map((f) => `${f.p}.${f.par}: ${f.path}`) },
    health: {
      errors: count(h.errors), warnings: count(h.warnings), script_errors: count(h.script_errors),
      first_errors: [...top(h.errors), ...top(h.script_errors)].slice(0, n).map((e) => `${e.p}: ${first(e.msg)}`),
      heavy: (h.heavy || []).slice(0, 5).map((x) => `${x.p} cpu ${x.cpu_ms} gpu ${x.gpu_ms}${x.stale ? ' (stale)' : ''}`),
      dead_branches: count(h.dead_branches), cook_always: count(h.cook_always), viewers_on: h.viewers_on, parked: count(h.parked),
    },
    refs: { expressions: count(s.expressions), binds: count(s.binds), exports: count(s.exports), unresolved: count(s.unresolved_refs), dat_refs: count(s.dat_refs), extensions: count(s.extensions) },
    ...(s.notes?.length ? { notes: s.notes } : {}),
    files_written: files,
  };
}

// ---------------------------------------------------------------- td_analyze_file: toeexpand a copy, parse in Python

export function resolveToe(f, bundle) {
  const p = path.isAbsolute(f) ? f : path.resolve(bundle, f);
  if (!/\.(toe|tox)$/i.test(p)) throw new Error(`not a .toe/.tox file: ${p}`);
  if (!fs.existsSync(p) || !fs.statSync(p).isFile()) throw new Error(`no such file: ${p}`);
  return p;
}

// Copy the file to cacheRoot/<sha16>/src.<ext> and toeexpand the COPY there (once per content). The original is
// never opened by TD's tools. toeexpand exits 1 even on success on 2025.31550: the .dir decides.
export function expandCopy(file, cacheRoot, toeexpand = TOEEXPAND) {
  const buf = fs.readFileSync(file);
  const sha = crypto.createHash('sha1').update(buf).digest('hex').slice(0, 16);
  const ext = path.extname(file).toLowerCase();
  const work = path.join(cacheRoot, sha);
  const dir = path.join(work, `src${ext}.dir`);
  if (fs.existsSync(dir)) return { dir, sha, cached: true };
  if (!fs.existsSync(toeexpand)) throw new Error(`toeexpand not found at ${toeexpand} (ships with TouchDesigner; set JTD_TOEEXPAND)`);
  fs.mkdirSync(work, { recursive: true });
  fs.writeFileSync(path.join(work, `src${ext}`), buf);
  try { execFileSync(toeexpand, [`src${ext}`], { cwd: work, timeout: 180000, stdio: 'pipe' }); } catch (e) { if (!fs.existsSync(dir)) throw new Error(`toeexpand failed on the copy: ${String(e.stderr || e.message).trim().slice(0, 300)}`); }
  if (!fs.existsSync(dir)) throw new Error('toeexpand wrote no .dir');
  return { dir, sha, cached: false };
}

export function analyzeExpanded(dir, a, { root: repo, python = PYTHON, file, folder }) {
  const args = ['-I', path.join(repo, 'td', 'debug.py'), 'analyze-expanded', dir, '--root', a.path || '/', '--depth', String(a.depth ?? 99),
    '--ops-dir', path.join(repo, 'docs', 'research', 'ops'), '--top', String(a.top ?? 10), '--max-items', String(a.max_items ?? 200)];
  if (a.packages) args.push('--packages');
  if (folder) args.push('--folder', folder);
  if (file) args.push('--file', file);
  let out;
  try { out = execFileSync(python, args, { encoding: 'utf8', maxBuffer: 512 * 1024 * 1024, timeout: 300000, stdio: ['ignore', 'pipe', 'pipe'] }); } catch (e) { throw new Error(`td/debug.py failed: ${String(e.stderr || e.message).trim().split('\n').slice(-3).join(' ').slice(0, 400)}`); }
  return JSON.parse(out);
}

// ---------------------------------------------------------------- td_why: tree -> indented text

export function whyLines(tree, out = [], depth = 0, max = 400) {
  if (!tree || out.length >= max) return out;
  const tag = [tree.missing ? 'MISSING' : '', tree.seen ? '(seen above)' : '', tree.more ? '(depth limit)' : ''].filter(Boolean).join(' ');
  out.push(`${'  '.repeat(depth)}${depth ? '<- ' : ''}${tree.p ?? '?'}${tree.par ? `.par.${tree.par}` : ''}${tree.t ? ` [${tree.t}]` : ''}${depth ? `  via ${tree.via}` : ''}${tag ? ` ${tag}` : ''}`);
  for (const k of tree.up || []) whyLines(k, out, depth + 1, max);
  return out;
}

// ---------------------------------------------------------------- watch: compact reply

export function compactWatch(r, file) {
  const tl = r.timeline || [];
  const step = Math.max(1, Math.ceil(tl.length / 40));
  const { timeline, par_changes_all, ...rest } = r;
  return { ...rest, fps_timeline: tl.filter((_, i) => i % step === 0).map((x) => [x.t, x.fps ?? null]), file };
}

// ---------------------------------------------------------------- journal (logs/exec.log + logs/calls.jsonl + snapshots)

function readJsonl(f) {
  let t = '';
  try { t = fs.readFileSync(f, 'utf8'); } catch { return []; }
  const rows = [];
  for (const l of t.split('\n')) { if (l.trim()) { try { rows.push(JSON.parse(l)); } catch { /* torn line */ } } }
  return rows;
}

const OPPATH_RE = /\bop\(\s*['"](\/[^'"]+)['"]/g;
export function codePaths(code) { return [...new Set([...String(code || '').matchAll(OPPATH_RE)].map((m) => m[1]))]; }
function commonPrefix(paths) {
  if (!paths.length) return null;
  const split = paths.map((p) => p.split('/').filter(Boolean));
  const outp = [];
  for (let i = 0; ; i++) { const s = split[0][i]; if (s === undefined || split.some((x) => x[i] !== s)) break; outp.push(s); }
  return outp.length ? `/${outp.join('/')}` : null;
}

// exec.log rows -> events (start/end paired by pid + code, oldest first). Reply text is the server's 500-char clip.
export function execEvents(rows) {
  const open = [];
  const ev = [];
  for (const r of rows) {
    if (r.phase === 'start') { const e = { t: r.time, tool: 'td_exec', cmd: 'exec', ok: null, code: r.code, pid: r.pid, agent: r.agent, src: 'exec.log' }; open.push(e); ev.push(e); continue; }
    if (r.phase !== 'end') continue;
    let i = open.length - 1;
    while (i >= 0 && !(open[i].code === r.code && (open[i].pid ?? null) === (r.pid ?? null))) i--;
    const e = i >= 0 ? open.splice(i, 1)[0] : (ev.push({ t: r.time, tool: 'td_exec', cmd: 'exec', code: r.code, pid: r.pid, agent: r.agent, src: 'exec.log' }), ev.at(-1));
    e.ok = !!r.ok; e.end = r.time; e.ms = Date.parse(r.time) - Date.parse(e.t);
    if (r.error) e.error = first(r.error);
    const res = String(r.result || '');
    const no = /"new_ops":(\d+)/.exec(res); if (no) e.new_ops = Number(no[1]);
    const pane = /"pane":"([^"]+)"/.exec(res); if (pane) e.pane = pane[1];
    const lay = [...res.matchAll(/"comp":"([^"]+)"/g)].map((m) => m[1]); if (lay.length) e.layout = [...new Set(lay)];
    if (/"notes":\[/.test(res)) e.notes = true;
  }
  for (const e of ev) {
    if (e.ok === null) e.error = 'no reply logged (timeout, crash, or still running)';
    e.what = clip(first(e.code), 140);
    e.comps = [...new Set([...codePaths(e.code), ...(e.pane ? [e.pane] : [])])].slice(0, 6);
    delete e.code;
  }
  return ev;
}

export function callEvents(rows) {
  return rows.map((r) => ({ t: r.t, tool: `td_${r.cmd}`, cmd: r.cmd, ok: !!r.ok, ms: r.ms, path: r.path, what: clip(first(r.code || r.text || r.args || ''), 140), ...(r.error ? { error: r.error } : {}), ...(r.timeout ? { timeout: true } : {}), ...(r.pid ? { pid: r.pid } : {}), ...(r.agent ? { agent: r.agent } : {}), src: 'calls.jsonl', comps: r.path ? [r.path] : [] }));
}

export function mergeEvents(execEv, callEv, snaps = []) {
  // calls.jsonl also has exec calls: keep the exec.log one (it has the code + reply details) when both exist
  const execT = execEv.map((e) => Date.parse(e.t));
  const calls = callEv.filter((c) => c.cmd !== 'exec' || !execT.some((t) => Math.abs(t - Date.parse(c.t)) < 5000));
  const all = [...execEv, ...calls].sort((a, b) => Date.parse(a.t) - Date.parse(b.t));
  for (const s of snaps) {
    const ts = Date.parse(s.t);
    let best = null; let bd = Infinity;
    for (const e of all) {
      if (e.tool !== s.tool) continue;
      if (s.pid && e.pid && s.pid !== e.pid) continue;
      const d = Math.abs(Date.parse(e.t) - ts);
      if (d < bd && d < 120000) { bd = d; best = e; }
    }
    if (best) best.snapshot = s.id; else all.push({ t: s.t, tool: s.tool, ok: s.ok, what: `(snapshot only) ${s.comp}`, comps: [s.comp], snapshot: s.id, pid: s.pid, src: 'snapshots' });
  }
  return all.sort((a, b) => Date.parse(a.t) - Date.parse(b.t));
}

export function filterEvents(ev, { since, until, agent, comp, tool, failures, now = Date.now() } = {}) {
  let out = ev;
  if (since) { const f = sinceMs(since, now); if (!Number.isNaN(f)) out = out.filter((e) => Date.parse(e.t) >= f); }
  if (until) { const u = sinceMs(until, now); if (!Number.isNaN(u)) out = out.filter((e) => Date.parse(e.t) <= u); }
  if (agent) out = out.filter((e) => String(e.agent ?? '') === String(agent) || String(e.pid ?? '') === String(agent));
  if (comp) { const c = String(comp).replace(/\/+$/, ''); out = out.filter((e) => [...(e.comps || []), e.path, ...(e.layout || [])].filter(Boolean).some((p) => p === c || p.startsWith(`${c}/`) || c.startsWith(`${p}/`)) || String(e.what || '').includes(c)); }
  if (tool) out = out.filter((e) => String(e.tool).includes(tool));
  if (failures) out = out.filter((e) => e.ok === false || e.ok === null);
  return out;
}

export function journalLine(e) {
  const t = String(e.t || '').replace('T', ' ').replace(/\.\d+Z$/, 'Z');
  const ok = e.ok === true ? 'ok' : e.ok === false ? 'FAIL' : '??';
  const extra = [e.ms !== undefined && !Number.isNaN(e.ms) ? `${Math.round(e.ms)}ms` : '', e.new_ops ? `+${e.new_ops} ops` : '', e.pane ? `pane ${e.pane}` : '', e.snapshot ? `snap ${e.snapshot}` : '', e.agent ? `agent ${e.agent}` : e.pid ? `pid ${e.pid}` : ''].filter(Boolean).join(' ');
  return `${t} ${e.tool} ${ok}${extra ? ` (${extra})` : ''}${e.path ? ` ${e.path}` : ''}: ${e.what || ''}${e.error ? `  !! ${clip(e.error, 160)}` : ''}`;
}

export function readJournalEvents(logDir, snapDir) {
  const ex = execEvents(readJsonl(path.join(logDir, 'exec.log')));
  const calls = callEvents([...readJsonl(path.join(logDir, 'calls.1.jsonl')), ...readJsonl(path.join(logDir, 'calls.jsonl'))]);
  const snaps = snapDir ? readJsonl(path.join(snapDir, 'index.jsonl')) : [];
  return mergeEvents(ex, calls, snaps);
}

// ---------------------------------------------------------------- per-call snapshot hook (opt-in)

const parentOf = (p) => (typeof p === 'string' && p.startsWith('/') ? p.replace(/\/[^/]+\/?$/, '') || '/' : null);
// tool -> the op/COMP a call changes (net_export of it before and after).
export const SNAP_TARGET = {
  td_create: (a) => a.parent,
  td_delete: (a) => parentOf(a.paths?.[0]),
  td_rename: (a) => parentOf(a.path),
  td_set_pars: (a) => a.path,
  td_custom_pars: (a) => a.path,
  td_connect: (a) => a.dst,
  td_disconnect: (a) => a.dst,
  td_dat_text: (a) => (a.text !== undefined ? a.path : null),
  td_tox_load: (a) => a.parent,
  td_exec: (a) => { const ps = codePaths(a.code); return ps.length === 1 ? ps[0] : commonPrefix(ps); },
  td_debug_panel: (a) => a.path || '/project1/debug',
  td_midi_build: (a) => a.path || '/project1/jazib_midi',
  td_comfy_build: (a) => `${a.parent || '/project1'}/${a.name || 'comfy'}`,
  td_publish: (a) => (a.source ? `${a.parent || '/project1'}/publish_${a.name}` : null),
  td_import_ae_anim: (a) => a.parent || '/project1',
  td_import_blender: (a) => a.parent || '/project1',
};

export function snapshotSettings(cfg, outDir) {
  const dir = path.join(outDir, 'debug', 'snapshots');
  const on = cfg.debugSnapshots === true || process.env.JTD_DEBUG_SNAPSHOTS === '1' || fs.existsSync(path.join(dir, '.on'));
  return { on, dir, maxBytes: Math.round((Number(cfg.debugSnapshotsMaxMB) || 200) * 1048576), depth: Number(cfg.debugSnapshotsDepth) || 2 };
}

// Oldest snapshot files go first once the folder is over maxBytes (index.jsonl and .on stay).
export function pruneSnapshots(dir, maxBytes) {
  let files;
  try { files = fs.readdirSync(dir).filter((f) => f.endsWith('.gz')).map((f) => ({ f, ...fs.statSync(path.join(dir, f)) })); } catch { return 0; }
  files.sort((a, b) => a.mtimeMs - b.mtimeMs || a.f.localeCompare(b.f));
  let total = files.reduce((s, x) => s + x.size, 0);
  let removed = 0;
  while (total > maxBytes && files.length) { const x = files.shift(); try { fs.unlinkSync(path.join(dir, x.f)); total -= x.size; removed++; } catch { /* gone */ } }
  return removed;
}

async function exportFor(call, p, depth) {
  try {
    const r = await call('net_export', { path: p, depth, max_chars: 1500000 }, 60000);
    return r && typeof r.text === 'string' ? r : null;
  } catch { return null; }
}

// Wraps one tool call: when snapshots are on and the tool changes a known op/COMP, its network text is saved
// (gzip) before and after, plus an index row. Never fails the call.
export async function withSnapshots(name, args, call, run, { cfg, outDir, now = () => new Date() } = {}) {
  const target = SNAP_TARGET[name];
  if (!target || !cfg || !outDir) return run();
  const st = snapshotSettings(cfg, outDir);
  if (!st.on) return run();
  let comp = null;
  try { comp = target(args); } catch { comp = null; }
  if (!comp || !String(comp).startsWith('/')) return run();
  const t = now();
  const before = await exportFor(call, comp, st.depth);
  let ok = true;
  try { return await run(); } catch (e) { ok = false; throw e; } finally {
    try {
      const after = await exportFor(call, comp, st.depth);
      fs.mkdirSync(st.dir, { recursive: true });
      const id = `${stamp(t)}_${process.pid}_${name.replace(/^td_/, '')}_${slug(comp, 40)}`;
      const save = (r, k) => { if (!r) return null; const f = `${id}.${k}.jtdnet.gz`; fs.writeFileSync(path.join(st.dir, f), zlib.gzipSync(r.text)); return f; };
      const row = { t: t.toISOString(), id, pid: process.pid, ...(process.env.JTD_AGENT ? { agent: process.env.JTD_AGENT } : {}), tool: name, comp, ok, before: save(before, 'before'), after: save(after, 'after'), ops_before: before?.ops, ops_after: after?.ops, truncated: !!(before?.truncated || after?.truncated) };
      fs.appendFileSync(path.join(st.dir, 'index.jsonl'), JSON.stringify(row) + '\n');
      pruneSnapshots(st.dir, st.maxBytes);
    } catch { /* a snapshot must never break the call */ }
  }
}

export function snapshotDiff(dir, id, max = 200) {
  const rows = readJsonl(path.join(dir, 'index.jsonl'));
  const row = rows.find((r) => r.id === id) || rows.find((r) => r.id?.startsWith(id));
  if (!row) throw new Error(`no snapshot ${id} in ${dir}`);
  const read = (f) => (f && fs.existsSync(path.join(dir, f)) ? zlib.gunzipSync(fs.readFileSync(path.join(dir, f))).toString('utf8') : null);
  const a = read(row.before); const b = read(row.after);
  if (!a || !b) return { snapshot: row, error: 'before or after export missing (pruned, or the op did not exist on one side)', before_exists: !!a, after_exists: !!b };
  return { snapshot: row, ...diffNet(a, b, { max }) };
}

// ---------------------------------------------------------------- tools

export function registerDebug({ server, tool, call, text, fail, z, CONFIG, ROOT, BUNDLE }) {
  const outDir = path.join(CONFIG.outputDir, 'debug');
  const snapDir = path.join(outDir, 'snapshots');
  const opPath = z.string().describe('Absolute TD path, e.g. /project1/look1');

  tool('td_analyze', 'Read-only X-ray of ANY open project or COMP (also ones Claude did not build). Inventory (counts by family/type, COMP tree with sizes, packages listed not entered), signal flow (wires + OP-reference pars + CHOP exports + expressions/binds parsed for op()/parent()/shortcut/par/channel refs + op(...) strings in DAT text + extensions), where Python runs (Execute / Parameter / Panel / CHOP / DAT / OP Execute DATs with their triggers and watched op, callbacks DATs, Script ops, extensions, pending run() scripts), external files with a missing-file check, devices + ports (OSC, Web, TCP/UDP, WebSocket, NDI/Syphon, DMX/Art-Net/sACN, MIDI, Serial, video/audio devices), cook health (errors, warnings, script errors, cook-always pars, viewers on, bypass/lock/parked, dead-branch candidates, heaviest by last cook time, GPU memory). Big projects are read in frame-sized chunks (budget_ms per frame; TD keeps running) and paged (limit/offset). Writes output/debug/<project>_<stamp>.md + .json + .mmd (Mermaid) + .dot of the top-level flow; replies with counts and the first items.',
    { path: z.string().optional().describe('COMP to analyze (default /)'), depth: z.number().int().min(1).max(99).optional(),
      include: z.array(z.enum(['packages', 'mcp'])).optional().describe('packages: enter clones / op-shortcut / palette COMPs; mcp: include /jazib_mcp'),
      limit: z.number().int().min(1).max(50000).optional().describe('ops read in detail per page (default 5000)'), offset: z.number().int().min(0).optional(),
      top: z.number().int().min(1).max(100).optional(), max_items: z.number().int().min(10).max(2000).optional(), budget_ms: z.number().min(1).max(50).optional().describe('work per frame (default 8 ms)') },
    async (a) => {
      const r = await call('analyze', a, 600000);
      const files = writeReport(r, outDir, `${String(r.project || 'td').replace(/\.toe$/, '')}_${slug(r.root, 30)}`);
      return compactAnalysis(r, files);
    });

  server.registerTool('td_analyze_file', { description: `The td_analyze report for a .toe/.tox that is NOT open (TD not needed): TD's own toeexpand unpacks a COPY under output/debug/expand/<sha>/ (the original is never touched, nothing in it runs); td/debug.py (python3 -I, read-only) parses the .n/.parm/.text files. Same sections as td_analyze minus runtime facts (cook times, errors, CHOP export sources); par defaults are not saved in the file, so an untouched device's active state shows as unknown. Relative file = under ${BUNDLE}. Writes output/debug/<file>_<stamp>.md/.json/.mmd/.dot.`,
    inputSchema: { toe: z.string(), path: z.string().optional().describe('COMP inside the file (default /)'), depth: z.number().int().min(1).max(99).optional(), packages: z.boolean().optional(), top: z.number().int().min(1).max(100).optional(), max_items: z.number().int().min(10).max(2000).optional() } }, async (a) => {
    try {
      const file = resolveToe(a.toe, BUNDLE);
      const x = expandCopy(file, path.join(outDir, 'expand'));
      const s = analyzeExpanded(x.dir, a, { root: ROOT, file, folder: path.dirname(file) });
      s.expanded = x.dir;
      const files = writeReport(s, outDir, `${path.basename(file).replace(/\.(toe|tox)$/i, '')}_${slug(s.root, 30)}`);
      return text(compactAnalysis(s, files));
    } catch (e) { return fail(e); }
  });

  tool('td_why', 'Read-only dependency trace: what drives this op (or one par). Tree of wired inputs, expressions / binds (op(), parent(), shortcuts, .par.X, [\'chan\']), CHOP exports into its pars, OP-reference pars (Select TOP top, callbacks...), recursively to depth (max_nodes cap, cycles marked); plus DAT scripts in scope whose text writes it (".par.X =", .val/.expr/.pulse, or for an op: .text=/connect/destroy...) or mentions it, and Execute DATs watching it. Answers "why does this value change / where does this come from".',
    { path: opPath, par: z.string().optional(), depth: z.number().int().min(1).max(12).optional(), max_nodes: z.number().int().min(5).max(1000).optional(), scope: z.string().optional().describe('where to search DAT text (default /)'), scan_dats: z.boolean().optional() },
    async (a) => { const r = await call('why', a, 120000); return { ...r, text: whyLines(r.tree).join('\n') }; });

  tool('td_watch', 'Live recorder (read-only): for seconds (max 120) at sample_hz under path: per-op cook-count deltas and estimated cook ms (cooks x last cook time), par value changes (custom, non-constant and non-default pars, max_pars), errors / warnings / script errors appearing and clearing (rotating scan), fps timeline (TD frames vs wall clock) against the cook rate. Setup and samples are bounded per frame. Full result: output/debug/watch_<stamp>.json; reply = summary + a 40-point fps timeline.',
    { path: z.string().optional(), seconds: z.number().min(0.5).max(120).optional(), sample_hz: z.number().min(0.5).max(30).optional(), max_ops: z.number().int().min(1).max(20000).optional(), max_pars: z.number().int().min(0).max(5000).optional(), top: z.number().int().min(1).max(100).optional() },
    async (a) => {
      const r = await call('watch', a, Math.round((a.seconds ?? 5) * 3000) + 120000);
      fs.mkdirSync(outDir, { recursive: true });
      const file = path.join(outDir, `watch_${slug(a.path || '/', 30)}_${stamp()}.json`);
      fs.writeFileSync(file, JSON.stringify(r, null, 1));
      return compactWatch(r, file);
    });

  server.registerTool('td_journal', { description: 'Read-only, TD not needed: what the MCP did, as a timeline. Reads logs/exec.log (every td_exec: code, reply, new ops, pane, layout) and, when present, logs/calls.jsonl (call journal of every tool) tolerantly, newest last: time, tool, ok/FAIL/?? (no reply = timeout or crash), duration, what (code first line / args), ops created, agent (MCP server pid, or JTD_AGENT; logged from 26 Oct). Filters: since ("-30m", "-2h", ISO), until, agent, comp (prefix), tool, failures. Snapshots (off by default): snapshots:true turns on the per-call hook for every MCP server (flag file; config.json debugSnapshots also works): before/after td_net_export of the op/COMP a mutating call touches, gzip under output/debug/snapshots/ (size-capped, oldest pruned); events then carry a snapshot id; diff:<id> returns that call\'s network diff (td_net_diff format).',
    inputSchema: { since: z.string().optional(), until: z.string().optional(), agent: z.string().optional(), comp: z.string().optional(), tool: z.string().optional(), failures: z.boolean().optional(), limit: z.number().int().min(1).max(1000).optional(),
      diff: z.string().optional().describe('snapshot id (or prefix): before/after network diff'), snapshots: z.boolean().optional().describe('turn the per-call snapshot hook on/off for all MCP servers') } }, async (a) => {
    try {
      if (a.snapshots !== undefined) {
        fs.mkdirSync(snapDir, { recursive: true });
        const flag = path.join(snapDir, '.on');
        if (a.snapshots) fs.writeFileSync(flag, `${new Date().toISOString()}\n`); else fs.rmSync(flag, { force: true });
      }
      if (a.diff) return text(snapshotDiff(snapDir, a.diff, 200));
      const ev = filterEvents(readJournalEvents(CONFIG.logDir, snapDir), a);
      const n = a.limit || 50;
      const shown = ev.slice(-n);
      const by = {};
      for (const e of ev) { const b = (by[e.tool] ||= { calls: 0, failed: 0 }); b.calls++; if (e.ok !== true) b.failed++; }
      const st = snapshotSettings(CONFIG, CONFIG.outputDir);
      return text({ total: ev.length, shown: shown.length, from: ev[0]?.t, to: ev.at(-1)?.t, by_tool: by, snapshots: { on: st.on, dir: st.dir }, text: shown.map(journalLine).join('\n'), events: shown });
    } catch (e) { return fail(e); }
  });

  tool('td_debug_panel', 'Build (or refresh in place) a self-contained debug panel Container COMP (default /project1/debug) that works without the MCP: live fps graph (Perform CHOP -> 10 s trail in an OP Viewer), top-10 cook ops (2 Hz, a small slice of ops read per frame), current errors / script errors / warnings, recent MCP actions (tail of logs/exec.log + calls.jsonl), click a row = the network editor jumps to the op. Pars on page Debug: Active, Scope, Refreshhz, Slice, Logdir. T-70 safe rebuild (window closed first, panel refilled in place, safe_destroy); arranged in stage boxes. style "zkit" calls builders/zkit.py style_debug_panel(comp) when that exists (hook).',
    { path: z.string().optional(), scope: z.string().optional().describe('COMP to watch (default /project1)'), open_window: z.boolean().optional(), style: z.enum(['plain', 'zkit']).optional(), slice_ops: z.number().int().min(5).max(2000).optional() },
    (a) => call('debug_panel_build', a, 60000));
}
