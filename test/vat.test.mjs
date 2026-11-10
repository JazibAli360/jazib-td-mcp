// Offline tests for src/vat.js (td_vat_load Node half): sidecar checks + file resolution. Run: node --test test/vat.test.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { checkVatSidecar, readVat, VAT_SCHEMA } from '../src/vat.js';

const good = () => ({ schema: VAT_SCHEMA, name: 'x', frames: 4, points: 10, width: 10, rows_per_frame: 1, height: 4, fps: 30, files: { mesh: 'x.obj', pos: 'x_pos.exr', nrm: null } });

test('checkVatSidecar: same rules as tools/vat_logic.check_sidecar', () => {
  assert.deepEqual(checkVatSidecar(good()), []);
  assert.ok(checkVatSidecar({ ...good(), schema: 'jazib-blender-td/1' })[0].includes('schema'));
  assert.ok(checkVatSidecar({ ...good(), height: 5 }).some((b) => b.includes('height')));
  assert.ok(checkVatSidecar({ ...good(), width: 3 }).some((b) => b.includes('width')));
  assert.ok(checkVatSidecar({ ...good(), files: { pos: 'p' } }).some((b) => b.includes('files.mesh')));
  assert.ok(checkVatSidecar(null).length);
});

test('readVat: files resolved beside the sidecar; a missing file is an error', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'vat-'));
  const side = path.join(dir, 'x.json');
  fs.writeFileSync(side, JSON.stringify(good()));
  assert.throws(() => readVat(side), /mesh_file missing/);
  fs.writeFileSync(path.join(dir, 'x.obj'), 'v 0 0 0\n');
  fs.writeFileSync(path.join(dir, 'x_pos.exr'), 'x');
  const v = readVat(side);
  assert.equal(v.mesh_file, path.join(dir, 'x.obj'));
  assert.equal(v.nrm_file, null);
  assert.equal(v.side.frames, 4);
  fs.writeFileSync(side, JSON.stringify({ ...good(), frames: 0 }));
  assert.throws(() => readVat(side), /bad VAT sidecar/);
});

// src/metavido.js (td_metavido Node half; lane T keeps both tool halves' Node tests here)
import { MV_DEMO, resolveClip } from '../src/metavido.js';

test('resolveClip: relative = repo root, default demo, video extensions only', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mv-'));
  fs.writeFileSync(path.join(dir, 'a.mp4'), 'x');
  assert.equal(resolveClip('a.mp4', dir), path.join(dir, 'a.mp4'));
  assert.throws(() => resolveClip('a.png', dir), /not a video/);
  assert.throws(() => resolveClip(undefined, dir), new RegExp(MV_DEMO.replace(/[.]/g, '\\.')));
  assert.throws(() => resolveClip('b.mov', dir), /not found/);
});
