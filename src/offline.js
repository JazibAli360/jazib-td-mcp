// td_offline: read a saved .toe/.tox with TouchDesigner closed. TD's own `toeexpand` unpacks a COPY (under
// output/offline/<sha>/) into text files; the original is never touched. The file readers are adapted from td-atlas
// by grigabyte (https://github.com/grigabyte/td-atlas, commit 7cf8f57, src/td_atlas/project/formats.py: the 27-byte
// .text prologue with its length field, the .parm flags word (bit 4 = expression, bit 9 = bind), .n blocks); records
// come out in our jtd-net shape so src/netdiff.js diffs two files.
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { diffNet } from './netdiff.js';

export const TOEEXPAND = process.env.JTD_TOEEXPAND || '/Applications/TouchDesigner 2.app/Contents/MacOS/toeexpand';
const PROLOGUE = 27;
const EXPR_BIT = 0x10;
const BIND_BIT = 0x200;
const UNKNOWN_EXTRA_BIT = 0x200000;
const SMALL_TEXT = 400;
const UI_FLAGS = new Set(['picked', 'current', 'viewer', 'parlanguage', 'activeviewer', 'showdocked', 'expose']);

// ---------------------------------------------------------------- pure readers

// A DAT's text from a .text file: b"1\n*" or b"2\n*", six big-endian uint32 (the last = payload length), payload.
export function readPayload(buf) {
  if (buf.length < PROLOGUE || !(buf[0] === 0x31 || buf[0] === 0x32) || buf[1] !== 0x0a || buf[2] !== 0x2a) return null;
  return buf.subarray(PROLOGUE).toString('utf8');
}

// Table DAT cells from a .table file: after "1\n*" four uint32 (?, rows, cols, ?), then per cell uint32 tag, uint32 len, bytes.
export function readTable(buf) {
  if (buf.length < 19 || buf[1] !== 0x0a || buf[2] !== 0x2a) return null;
  const rows = buf.readUInt32BE(7); const cols = buf.readUInt32BE(11);
  const cells = [];
  let o = 19;
  while (o + 8 <= buf.length) { const len = buf.readUInt32BE(o + 4); o += 8; cells.push(buf.subarray(o, o + len).toString('utf8')); o += len; }
  if (!cols) return cells.length ? [cells] : [];
  const out = [];
  for (let i = 0; i < cells.length; i += cols) out.push(cells.slice(i, i + cols));
  return rows ? out.slice(0, rows) : out;
}

export function readNode(text) {
  const n = { family: '', type: '', inputs: [], flags: {}, tags: [] };
  let block = null;
  for (const raw of String(text).split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    if (block) {
      if (line === '}') { block = null; continue; }
      if (line === '{') continue;
      if (block === 'inputs') { const m = /^(\d+)\s+(.+)$/.exec(line); if (m) n.inputs.push([Number(m[1]), m[2].trim()]); }
      continue;
    }
    if (!n.family && /^[A-Z]+:\S+$/.test(line)) { [n.family, n.type] = line.split(':'); continue; }
    const [head, ...rest] = line.split(/\s+/);
    if (head === 'tile') n.tile = rest.slice(0, 4).map(Number);
    else if (head === 'flags') { const t = rest.filter((x) => x !== '='); for (let i = 0; i < t.length; i += 2) n.flags[t[i]] = t[i + 1] ?? ''; }
    else if (head === 'color') n.color = rest.slice(0, 3).map(Number);
    else if (head === 'comment') n.comment = unquote(line.slice(8));
    else if (head === 'tags') n.tags = rest.slice(2).map(unquote);
    else if (['inputs', 'outputs', 'docked', 'wires'].includes(head)) block = head;
    else if (head === 'end') break;
  }
  return n;
}

function unquote(s) { s = String(s).trim(); return s.length >= 2 && s[0] === '"' && s.at(-1) === '"' ? unescape_(s.slice(1, -1)) : s; }
function unescape_(s) { return s.replace(/\\(["\\nt'])/g, (_, c) => ({ n: '\n', t: '\t' }[c] || c)); }
// One field (quoted or bare) and the rest.
function takeField(s) {
  s = s.replace(/^\s+/, '');
  if (s[0] !== '"') { const i = s.indexOf(' '); return i < 0 ? [s, ''] : [s.slice(0, i), s.slice(i + 1)]; }
  for (let i = 1; i < s.length; i++) {
    if (s[i] === '\\') { i++; continue; }
    if (s[i] === '"') return [unescape_(s.slice(1, i)), s.slice(i + 1)];
  }
  return [unescape_(s.slice(1)), ''];
}
function splitValues(rest, count) {
  const out = [];
  for (let i = 0; i < count - 1; i++) { const [h, r] = takeField(rest); out.push(h); rest = r; }
  const tail = rest.trim();
  out.push(tail.startsWith('"') ? takeField(tail)[0] : tail);
  return out;
}

// .parm: "name <flags> <constant> [<expr>] [<bind>]" between "?" lines. -> {name: {flags, value, expr?, bind?, raw?}}
export function readParms(text) {
  const out = {};
  for (const raw of String(text).split('\n')) {
    const line = raw.trim();
    const m = /^(\S+)\s+(-?\d+)\s*(.*)$/.exec(line);
    if (!line || line === '?' || !m) continue;
    const flags = Number(m[2]); const rest = m[3];
    if (flags & UNKNOWN_EXTRA_BIT) { const [v, r] = takeField(rest); out[m[1]] = { flags, value: v, raw: r.trim() || undefined }; continue; }
    const halves = (flags & EXPR_BIT ? 1 : 0) + (flags & BIND_BIT ? 1 : 0);
    if (!halves) { out[m[1]] = { flags, value: unquote(rest) }; continue; }
    const v = splitValues(rest, halves + 1);
    const p = { flags, value: v[0] };
    let i = 1;
    if (flags & EXPR_BIT) p.expr = v[i++];
    if (flags & BIND_BIT) p.bind = v[i];
    out[m[1]] = p;
  }
  return out;
}

// Our jtd-net par code from a file par: '~bind', '=expr', else the constant (a leading = ~ @ doubled).
export function parCode(p) {
  if (p.flags & BIND_BIT && p.bind) return `~${p.bind}`;
  if (p.flags & EXPR_BIT) return `=${p.expr ?? ''}`;
  const v = p.value;
  return typeof v === 'string' && /^[=~@]/.test(v) ? v[0] + v : v;
}

// .cparm: first line "pages <n> names...", then definitions (layout not measured: we keep names only).
export function readCustomParms(text) {
  const out = { pages: [], names: [] };
  for (const raw of String(text).split('\n')) {
    const line = raw.trim();
    if (!line || line === '?') continue;
    const m = /^pages\s+\d+\s+(.*)$/.exec(line);
    if (m && !out.pages.length) { let r = m[1]; while (r.trim()) { const [h, t] = takeField(r); out.pages.push(h); r = t; } continue; }
    const d = /^\d+\s+([A-Z][a-z0-9]*)\s/.exec(line);
    if (d) out.names.push(d[1]);
  }
  return out;
}

function textFields(text) {
  if (text.length <= SMALL_TEXT) return { text };
  const lines = text.split(/\r?\n/);
  return { text_len: text.length, text_lines: lines.length, text_sha1: crypto.createHash('sha1').update(text).digest('hex').slice(0, 16), text_head: lines.slice(0, 6).map((l) => l.slice(0, 160)) };
}

// ---------------------------------------------------------------- expanded tree -> records

// Walk the .dir: one record per .n file, depth-first by name. path '/a/b' for file a/b.n.
export function readExpanded(dir, { root = '/', depth = 99, xy = false, datText = true } = {}) {
  const recs = [];
  const want = root.replace(/\/+$/, '') || '';
  const rootDepth = want ? want.split('/').length - 1 : 0;
  const walk = (rel) => {
    const abs = path.join(dir, rel);
    let names;
    try { names = fs.readdirSync(abs).sort(); } catch { return; }
    for (const f of names.filter((x) => x.endsWith('.n'))) {
      const base = f.slice(0, -2);
      const opRel = rel ? `${rel}/${base}` : base;
      const opPath = `/${opRel}`;
      const level = opPath.split('/').length - 1 - rootDepth;
      const inside = !want || opPath === want || opPath.startsWith(`${want}/`);
      if (!want || opPath === want || want.startsWith(`${opPath}/`) || inside) {
        if (inside && level <= depth) recs.push(record(dir, opRel, opPath, want, { xy, datText }));
        if ((inside && level < depth) || (!inside && want.startsWith(`${opPath}/`))) walk(opRel);
      }
    }
  };
  walk('');
  return recs;
}

function rel(p, want) {
  if (!want) return p;
  if (p === want) return '.';
  return p.startsWith(`${want}/`) ? p.slice(want.length + 1) : p;
}

function record(dir, opRel, opPath, want, { xy, datText }) {
  const read = (ext) => { try { return fs.readFileSync(path.join(dir, opRel + ext)); } catch { return null; } };
  const node = readNode(read('.n')?.toString('utf8') || '');
  const r = { p: rel(opPath, want), t: node.type && node.family ? `${node.type}${node.family}` : '' };
  if (node.inputs.length) {
    const ins = [];
    for (const [i, src] of node.inputs) ins[i] = [src, 0];
    for (let i = 0; i < ins.length; i++) if (ins[i] === undefined) ins[i] = null;
    r.in = ins;
  }
  const flags = Object.entries(node.flags).filter(([k, v]) => !UI_FLAGS.has(k) && (v === 'on' || v === '1')).map(([k]) => k).sort();
  if (flags.length) r.flags = flags;
  if (node.comment) r.comment = node.comment;
  if (node.tags.length) r.tags = [...node.tags].sort();
  const parm = read('.parm');
  if (parm) {
    const pars = {};
    for (const [k, v] of Object.entries(readParms(parm.toString('utf8')))) pars[k] = parCode(v);
    if (Object.keys(pars).length) r.pars = pars;
  }
  const cparm = read('.cparm');
  if (cparm) { const c = readCustomParms(cparm.toString('utf8')); r.cpages = c.pages; if (c.names.length) r.cnames = c.names; }
  if (datText) {
    const t = read('.text');
    const txt = t && readPayload(t);
    if (txt !== null && txt !== undefined) Object.assign(r, textFields(txt));
    const tb = read('.table');
    const rows = tb && readTable(tb);
    if (rows) { r.table = [rows.length, rows[0]?.length || 0]; if (rows.length <= 10) r.rows = rows.map((row) => row.map((c) => c.slice(0, 80))); }
  }
  if (xy && node.tile) r.xy = node.tile.slice(0, 2);
  if (node.tile) Object.defineProperty(r, '_tile', { value: node.tile.slice(0, 2), enumerable: false });
  return r;
}

export function readBuild(dir) {
  const out = {};
  try { for (const l of fs.readFileSync(path.join(dir, '.build'), 'utf8').split('\n')) { const [k, ...v] = l.trim().split(' '); if (k) out[k] = v.join(' '); } } catch {}
  return out;
}

const sortKeys = (v) => (Array.isArray(v) ? v.map(sortKeys) : v && typeof v === 'object' ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortKeys(v[k])])) : v);
const KEY_ORDER = ['p', 't', 'in', 'flags', 'comment', 'tags', 'pars', 'cpages', 'cnames', 'text', 'text_len', 'text_lines', 'text_sha1', 'text_head', 'table', 'rows', 'xy'];
const line = (r) => JSON.stringify(Object.fromEntries([...KEY_ORDER.filter((k) => k in r), ...Object.keys(r).filter((k) => !KEY_ORDER.includes(k)).sort()].map((k) => [k, sortKeys(r[k])])));

// jtd-net text (format of td_net_export, source "file") so diffNet compares two files.
export function netText(recs, { file, root, build, depth, xy }) {
  const hdr = { format: 'jtd-net', v: 1, root, type: recs[0]?.p === '.' ? recs[0].t : '', build: build.build || '', depth, include_defaults: false, dat_text: true, xy: !!xy, source: 'file', file: path.basename(file) };
  return [JSON.stringify(hdr), ...recs.map(line), JSON.stringify({ end: true, ops: recs.length, total: recs.length, truncated: false })].join('\n') + '\n';
}

// grep the DAT text of the records' files. pattern: regex source (case-insensitive unless it has an uppercase char).
export function grepExpanded(dir, recs, pattern, { limit = 50, want = '' } = {}) {
  const re = new RegExp(pattern, /[A-Z]/.test(pattern) ? '' : 'i');
  const hits = []; let total = 0; let files = 0;
  for (const r of recs) {
    const opRel = (r.p === '.' ? want : want ? `${want}/${r.p}` : `/${r.p}`).replace(/^\//, '');
    let buf;
    try { buf = fs.readFileSync(path.join(dir, `${opRel}.text`)); } catch { continue; }
    const txt = readPayload(buf);
    if (txt == null) continue;
    files++;
    txt.split(/\r?\n/).forEach((l, i) => { if (re.test(l)) { total++; if (hits.length < limit) hits.push({ p: r.p, line: i + 1, text: l.trim().slice(0, 200) }); } });
  }
  return { pattern, dats: files, matches: total, hits, ...(total > hits.length ? { truncated: true } : {}) };
}

// Tree listing (compact): one line per op "path type [<- in1, in2] (n pars)".
export function treeLines(recs, limit = 200) {
  const lines = recs.slice(0, limit).map((r) => {
    let s = `${r.p} ${r.t}`;
    if (r.in) s += ` <- ${r.in.map((x) => (x ? x[0] : '-')).join(', ')}`;
    if (r.pars) s += ` (${Object.keys(r.pars).length} pars)`;
    if (r.flags) s += ` [${r.flags.join(',')}]`;
    if (r.text !== undefined) s += ` "${r.text.split('\n')[0].slice(0, 60)}"`;
    else if (r.text_head) s += ` "${(r.text_head[0] || '').slice(0, 60)}" (${r.text_lines} lines)`;
    return s;
  });
  return { lines, total: recs.length, ...(recs.length > limit ? { truncated: true } : {}) };
}

// Ops present in both whose node position changed (kept apart from real changes).
export function moves(a, b) {
  const pos = new Map(a.map((r) => [r.p, r._tile]));
  const out = [];
  for (const r of b) { const p = pos.get(r.p); if (p && r._tile && (p[0] !== r._tile[0] || p[1] !== r._tile[1])) out.push(r.p); }
  return out;
}

// ---------------------------------------------------------------- expanding a copy (side effects)

export function resolveProjectFile(f, base) {
  const p = path.isAbsolute(f) ? f : path.resolve(base, f);
  if (!/\.(toe|tox)$/i.test(p)) throw new Error(`not a .toe/.tox file: ${p}`);
  if (!fs.existsSync(p) || !fs.statSync(p).isFile()) throw new Error(`no such file: ${p}`);
  return p;
}

// Copy file into cacheRoot/<sha16>/src.<ext> and toeexpand there (once per content). Returns {dir, sha, cached}.
export function expandCopy(file, cacheRoot, toeexpand = TOEEXPAND) {
  if (!fs.existsSync(toeexpand)) throw new Error(`toeexpand not found at ${toeexpand} (ships with TouchDesigner; set JTD_TOEEXPAND)`);
  const buf = fs.readFileSync(file);
  const sha = crypto.createHash('sha1').update(buf).digest('hex').slice(0, 16);
  const ext = path.extname(file).toLowerCase();
  const work = path.join(cacheRoot, sha);
  const name = `src${ext}`;
  const dir = path.join(work, `${name}.dir`);
  if (fs.existsSync(dir)) return { dir, sha, cached: true };
  fs.mkdirSync(work, { recursive: true });
  fs.writeFileSync(path.join(work, name), buf);
  try { execFileSync(toeexpand, [name], { cwd: work, timeout: 120000, stdio: 'pipe' }); } catch (e) { if (!fs.existsSync(dir)) throw new Error(`toeexpand failed on the copy: ${String(e.stderr || e.message).trim().slice(0, 300)}`); }
  if (!fs.existsSync(dir)) throw new Error('toeexpand wrote no .dir');
  return { dir, sha, cached: false }; // toeexpand exits 1 even on success (2025.31550): the .dir decides
}

// The td_offline tool body. a: {file, mode, path, depth, query, other, limit, xy}.
export function offline(a, { base, cacheRoot, toeexpand = TOEEXPAND }) {
  const mode = a.mode || (a.query ? 'grep' : a.other ? 'diff' : 'tree');
  const file = resolveProjectFile(a.file, base);
  const want = (a.path || '').replace(/\/+$/, '');
  if (want && !want.startsWith('/')) throw new Error('path must be an absolute TD path, e.g. /project1');
  const depth = a.depth ?? 99;
  const load = (f) => {
    const x = expandCopy(f, cacheRoot, toeexpand);
    const recs = readExpanded(x.dir, { root: want || '/', depth, xy: !!a.xy });
    return { ...x, recs, build: readBuild(x.dir) };
  };
  const A = load(file);
  const head = { file, build: A.build.build, cache: A.dir, ...(want ? { path: want } : {}) };
  if (want && !A.recs.length) throw new Error(`no operator ${want} in ${path.basename(file)} (try mode tree without path)`);
  if (mode === 'tree') {
    const fam = {};
    for (const r of A.recs) { const f = (r.t.match(/(TOP|CHOP|SOP|DAT|COMP|MAT|POP)$/) || ['?'])[0]; fam[f] = (fam[f] || 0) + 1; }
    return { ...head, ops: A.recs.length, by_family: fam, ...treeLines(A.recs, a.limit || 200) };
  }
  if (mode === 'text') {
    const t = netText(A.recs, { file, root: want || '/', build: A.build, depth, xy: a.xy });
    const max = 60000;
    return { ...head, ops: A.recs.length, chars: t.length, text: t.length > max ? t.slice(0, t.lastIndexOf('\n', max) + 1) : t, ...(t.length > max ? { truncated: true, hint: 'narrow with path or depth' } : {}) };
  }
  if (mode === 'grep') {
    if (!a.query) throw new Error('grep needs query (a regex)');
    return { ...head, ...grepExpanded(A.dir, A.recs, a.query, { limit: a.limit || 50, want }) };
  }
  if (mode === 'diff') {
    if (!a.other) throw new Error('diff needs other (a second .toe/.tox)');
    const B = load(resolveProjectFile(a.other, base));
    const opt = { root: want || '/', depth, xy: false };
    const d = diffNet(netText(A.recs, { file, build: A.build, ...opt }), netText(B.recs, { file: a.other, build: B.build, ...opt }), { max: a.limit || 200 });
    const moved = moves(A.recs, B.recs);
    return { ...head, other: a.other, ...d, moved: moved.slice(0, a.limit || 200), moved_count: moved.length };
  }
  throw new Error(`mode must be tree, text, grep or diff (got ${mode})`);
}
