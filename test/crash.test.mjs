// Offline tests for src/crash.js (td_crash_report): fixture .ips + exec.log + faulthandler log, no TD, no bridge.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { crashArgs, crashReport } from '../src/crash.js';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);
const FIX = path.join(ROOT, 'test', 'fixtures', 'crash');
const opts = { root: ROOT, logDir: FIX, diag: FIX };

test('crash: args (ips name, absolute path, refuses non-.ips)', () => {
  const a = crashArgs({ ips: 'TouchDesigner-2026-10-26-150020.ips', window_s: 30 }, opts);
  assert.equal(a[a.indexOf('--ips') + 1], path.join(FIX, 'TouchDesigner-2026-10-26-150020.ips'));
  assert.equal(a[a.indexOf('--window') + 1], '30');
  assert.equal(a[a.indexOf('--patterns') + 1], path.join(ROOT, 'logs', 'crash_patterns.json'));
  assert.equal(crashArgs({ ips: '/x/y.ips' }, opts).at(-1), '/x/y.ips');
  assert.ok(!crashArgs({}, opts).includes('--ips'));
  assert.throws(() => crashArgs({ ips: '../../etc/passwd' }, opts), /\.ips/);
});

test('crash: known pattern T-74 from stack + in-flight code + faulthandler stack', () => {
  const r = crashReport({ ips: 'TouchDesigner-2026-10-26-150020.ips' }, opts);
  assert.equal(r.crash.exception.signal, 'SIGSEGV');
  assert.deepEqual(r.crash.top.slice(0, 3), ['libGX', 'libC_TOP', 'Python']);
  assert.deepEqual(r.known.both, ['T-74-readback-after-change']);
  assert.equal(r.exec.in_flight.length, 2);
  assert.equal(r.exec.in_flight[0].agent, 'lane1');
  assert.equal(r.faulthandler.crashed, true);
  assert.equal(r.faulthandler.exec_frames[0].line, 3);
  assert.equal(r.proposal, null);
});

test('crash: unknown crash -> proposal (not added); newest .ips by default', () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'jtd-crash-'));
  try {
    for (const [n, t] of [['TouchDesigner-2026-10-26-131216.ips', 1000], ['TouchDesigner-2026-10-27-090000.ips', 2000]]) {
      fs.copyFileSync(path.join(FIX, n), path.join(d, n)); fs.utimesSync(path.join(d, n), t, t);
    }
    const before = fs.readFileSync(path.join(ROOT, 'logs', 'crash_patterns.json'), 'utf8');
    const r = crashReport({}, { root: ROOT, logDir: d, diag: d });
    assert.equal(r.crash.file, 'TouchDesigner-2026-10-27-090000.ips');
    assert.match(r.verdict, /unknown crash/);
    assert.equal(r.proposal.status, 'proposed');
    assert.deepEqual(r.proposal.stack.top, ['libC_SOP', 'libOP', 'Python']);
    assert.ok(r.notes.some((n) => /no faulthandler log/.test(n)));
    assert.equal(fs.readFileSync(path.join(ROOT, 'logs', 'crash_patterns.json'), 'utf8'), before, 'never auto-added');
  } finally { fs.rmSync(d, { recursive: true, force: true }); }
});

test('crash: python failure surfaces as an error', () => {
  assert.throws(() => crashReport({}, { ...opts, python: '/nonexistent/python3' }), /crashdb\.py failed/);
});
