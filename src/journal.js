// Call journal (26 Oct 2026): one JSON line per bridge call in logs/calls.jsonl, written by the MCP server, so
// "what failed / what did I change yesterday" survives the session (td_log reads it). Idea and redaction rules adapted
// from td-atlas by grigabyte (https://github.com/grigabyte/td-atlas, commit 7cf8f57, src/td_atlas/journal.py,
// docs/journal.md); own code. logs/exec.log (td_exec code + result) stays as it was.
import fs from 'node:fs';
import path from 'node:path';

export const MAX_BYTES = 16 * 1024 * 1024; // then calls.jsonl -> calls.1.jsonl (the one before is dropped)
const CLIP = 1000;
const CODE_CLIP = 4000;
const LINE_MAX = 32 * 1024;
// Commands whose args are kept (they change the project). Same list as MUTATING in td/handlers.py (a test checks).
export const MUTATING_CMDS = ['create', 'delete', 'rename', 'move', 'connect', 'disconnect', 'set_pars', 'dat_text',
  'custom_pars', 'tox_load', 'layout', 'exec', 'comfy_build', 'publish', 'osc_learn', 'link', 'live_audio', 'tda_load',
  'import_ae_anim', 'import_blender', 'midi_build', 'midi_learn', 'midi_map', 'midi_unmap', 'midi_bank', 'midi_load', 'midi_simulate',
  'midi_preset', 'save_hook', 'record_chop', 'shadertoy', 'osc_expose', 'layer_mixer', 'cook_active'];
// Read-only commands also worth their args (they say what was written where).
const KEEP_ARGS = new Set([...MUTATING_CMDS, 'save_project', 'tox_save', 'script_errors_recheck', 'checkpoint', 'restore_checkpoint', 'presave',
  'timeline_edit', 'timeline_load', 'timeline_transport', 'timeline_record', 'timeline_export']);

const SECRET_ASSIGN = /((?:password|passwd|secret|token|api[_-]?key|access[_-]?key|auth)\w*["']?\s*[:=(]\s*)(["'])[^"']*\2/gi;
const SECRET_SHAPES = /\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|xox[bpas]-[A-Za-z0-9-]{10,}|AKIA[A-Z0-9]{16})\b/g;

export function redact(s, token) {
  let t = String(s);
  if (token) t = t.split(token).join('[token]');
  return t.replace(SECRET_ASSIGN, '$1$2[redacted]$2').replace(SECRET_SHAPES, '[redacted]');
}
const clip = (s, n) => (s.length > n ? `${s.slice(0, n)}... (${s.length} chars)` : s);

// The op path a call is about (for the listing).
export function callPath(args = {}) {
  for (const k of ['path', 'parent', 'dst', 'src']) if (typeof args[k] === 'string') return args[k];
  if (Array.isArray(args.paths) && args.paths.length) return args.paths.length > 1 ? `${args.paths[0]} (+${args.paths.length - 1})` : args.paths[0];
  return undefined;
}

// One journal row (pure): {t, cmd, ok, ms, path?, args?, code?, error?, timeout?}.
export function journalRow({ cmd, args = {}, ok, ms, error, timeout, now = new Date(), token }) {
  const row = { t: now.toISOString(), cmd, ok: !!ok, ms: Math.round(ms * 10) / 10 };
  const p = callPath(args);
  if (p) row.path = p;
  if (KEEP_ARGS.has(cmd)) {
    const { code, text, ...rest } = args;
    if (typeof code === 'string') row.code = clip(redact(code, token), CODE_CLIP);
    if (typeof text === 'string') row.text = clip(redact(text, token), CODE_CLIP);
    if (Object.keys(rest).length) row.args = clip(redact(JSON.stringify(rest), token), CLIP);
  }
  if (!ok) row.error = clip(redact(String(error || 'error').split('\n')[0], token), 300);
  if (timeout) row.timeout = true;
  let line = JSON.stringify(row);
  if (line.length > LINE_MAX) { delete row.code; delete row.text; row.args = '(dropped: line over 32 KB)'; line = JSON.stringify(row); }
  return line;
}

export function journalFiles(dir) { return [path.join(dir, 'calls.1.jsonl'), path.join(dir, 'calls.jsonl')]; }

// Append one line; rotate first when the file would pass maxBytes. Never throws (a journal must not break a call).
export function appendJournal(dir, line, maxBytes = MAX_BYTES) {
  try {
    fs.mkdirSync(dir, { recursive: true });
    const [old, cur] = journalFiles(dir);
    let size = 0;
    try { size = fs.statSync(cur).size; } catch {}
    if (size && size + line.length + 1 > maxBytes) fs.renameSync(cur, old);
    fs.appendFileSync(cur, line + '\n');
  } catch {}
}

// Wrap a bridge call(cmd, args, timeoutMs) so every call lands in the journal.
export function journaled(call, dir, getToken = () => undefined) {
  return async (cmd, args = {}, timeoutMs) => {
    const t0 = performance.now();
    try {
      const r = await call(cmd, args, timeoutMs);
      appendJournal(dir, journalRow({ cmd, args, ok: true, ms: performance.now() - t0, token: getToken() }));
      return r;
    } catch (e) {
      appendJournal(dir, journalRow({ cmd, args, ok: false, ms: performance.now() - t0, error: e.message, timeout: e.status === 504, token: getToken() }));
      throw e;
    }
  };
}

function readRows(dir) {
  const rows = [];
  for (const f of journalFiles(dir)) {
    let txt = '';
    try { txt = fs.readFileSync(f, 'utf8'); } catch { continue; }
    for (const l of txt.split('\n')) { if (l.trim()) { try { rows.push(JSON.parse(l)); } catch {} } }
  }
  return rows;
}

// td_log: newest last. {limit=30, failures, summary, cmd, since (ISO or "-2h"/"-30m"/"-1d")}.
export function readJournal(dir, { limit = 30, failures = false, summary = false, cmd, since, now = Date.now() } = {}) {
  let rows = readRows(dir);
  if (since) {
    const m = /^-(\d+(?:\.\d+)?)([mhd])$/.exec(String(since));
    const from = m ? now - Number(m[1]) * { m: 60e3, h: 3600e3, d: 86400e3 }[m[2]] : Date.parse(since);
    if (!Number.isNaN(from)) rows = rows.filter((r) => Date.parse(r.t) >= from);
  }
  if (cmd) rows = rows.filter((r) => r.cmd === cmd);
  const fails = rows.filter((r) => !r.ok);
  if (summary) {
    const by = {};
    for (const r of rows) { const b = (by[r.cmd] ||= { calls: 0, failed: 0, ms_max: 0 }); b.calls++; if (!r.ok) b.failed++; b.ms_max = Math.max(b.ms_max, r.ms || 0); }
    const reasons = {};
    for (const r of fails) { const k = String(r.error || '').split(':')[0].slice(0, 60); reasons[k] = (reasons[k] || 0) + 1; }
    return {
      calls: rows.length, failed: fails.length, from: rows[0]?.t, to: rows.at(-1)?.t,
      by_cmd: Object.fromEntries(Object.entries(by).sort((a, b) => b[1].calls - a[1].calls)),
      reasons: Object.fromEntries(Object.entries(reasons).sort((a, b) => b[1] - a[1]).slice(0, 10)),
      slowest: [...rows].sort((a, b) => (b.ms || 0) - (a.ms || 0)).slice(0, 5).map((r) => ({ t: r.t, cmd: r.cmd, ms: r.ms, path: r.path })),
    };
  }
  const pick = failures ? fails : rows;
  const n = Math.max(1, Math.min(500, limit | 0 || 30));
  return { total: pick.length, shown: Math.min(n, pick.length), rows: pick.slice(-n) };
}
