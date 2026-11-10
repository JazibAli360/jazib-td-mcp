// Offline tests for src/blender.js (Blender -> TD planning) on the fixture export test/fixtures/blender/tiny_stage.*
// (made headless by tools/blender_export.py --make-test-scene, Blender 5.2.2 LTS). Run: node --test test/blender.test.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { diagFov, opName, planImport, readSidecar, SCHEMA } from '../src/blender.js';

const FIX = new URL('./fixtures/blender/', import.meta.url).pathname;
const side = readSidecar(path.join(FIX, 'tiny_stage.json'));
const byName = (plan, n) => plan.ops.find((o) => o.name === n);

test('opName makes TD-safe names', () => {
  assert.equal(opName('cam', 'Cam.FOH 01'), 'cam_Cam_FOH_01');
  assert.equal(opName('light', '...'), 'light_x');
});

test('readSidecar refuses other JSON', () => {
  const f = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'jtd-bl-')), 'x.json');
  fs.writeFileSync(f, JSON.stringify({ schema: 'other', cameras: [], lights: [], objects: [] }));
  assert.throws(() => readSidecar(f), /not a jazib-blender-td/);
  assert.equal(side.schema, SCHEMA);
});

test('plan: USD geo, matched camera, projector light, ambient, render, controls, stages', () => {
  const p = planImport(side, { dir: FIX });
  assert.deepEqual(p.ops.map((o) => `${o.name}:${o.type}`), ['geo:usdCOMP', 'cam_Cam_FOH:cameraCOMP', 'map_PROJ_A:rampTOP',
    'light_PROJ_A:lightCOMP', 'ambient:ambientlightCOMP', 'render:renderTOP', 'out:nullTOP']);
  const g = byName(p, 'geo');
  assert.equal(g.pars.file, path.join(FIX, 'tiny_stage.usdc'));
  assert.deepEqual(g.pulse, ['imp']);
  const c = byName(p, 'cam_Cam_FOH').pars;
  assert.deepEqual([c.tx, c.ty, c.tz, c.rord, c.viewanglemethod, c.winx], [0, 3, 12, 'xyz', 'horzfov', 0.1]);
  assert.ok(Math.abs(c.fov - 54.432223) < 1e-5);
  const l = byName(p, 'light_PROJ_A');
  assert.equal(l.pars.projmap, 'map_PROJ_A');
  assert.equal(l.pars.projmapmode, 'simplehorzfov');
  assert.ok(Math.abs(l.pars.projangle - 36.8699) < 1e-3);
  assert.ok(l.pars.coneangle >= diagFov(36.8699, 16 / 9) + 2 - 1e-6);
  assert.equal(l.exprs.dimmer, 'parent().par.Lightdimmer * 0.8');
  assert.deepEqual(byName(p, 'map_PROJ_A').pars, { outputresolution: 'custom', resolutionw: 1920, resolutionh: 1080 });
  const r = byName(p, 'render');
  assert.equal(r.pars.lights, 'light_PROJ_A ambient');
  assert.equal(r.pars.geometry, 'geo');
  assert.deepEqual(p.wires, [['render', 'out']]);
  const cam = p.controls.find((x) => x.name === 'Camera');
  assert.deepEqual([cam.menuNames, cam.default], [['cam_Cam_FOH'], 'cam_Cam_FOH']);
  assert.deepEqual(p.controls.map((x) => x.name), ['Camera', 'Lightdimmer', 'Ambient', 'Resw', 'Resh']);
  assert.deepEqual(p.controls.slice(3).map((x) => x.default), [1920, 1080]);
  const staged = p.stages.flatMap((s) => s.ops);
  for (const o of p.ops) assert.ok(staged.includes(o.name), o.name);
  assert.match(p.report, /cameras 1, lights 1 \(projectors 1\)/);
});

test('plan: fbx / none / texture / shift warnings', () => {
  const fbx = planImport(side, { dir: FIX, geo: 'fbx' });
  assert.equal(byName(fbx, 'geo').type, 'fbxCOMP');
  assert.equal(byName(fbx, 'geo').pars.lights, false);
  const none = planImport(side, { dir: FIX, geo: 'none' });
  assert.equal(byName(none, 'geo'), undefined);
  assert.equal(byName(none, 'render').pars.geometry, '');
  const s2 = structuredClone(side);
  s2.lights[0].projector.texture = '/nope/img.png';
  s2.lights[0].projector.shift = [0.1, 0];
  const t = planImport(s2, { dir: FIX });
  assert.equal(byName(t, 'map_PROJ_A').type, 'moviefileinTOP');
  assert.ok(t.warnings.some((w) => /texture missing/.test(w)));
  assert.ok(t.warnings.some((w) => /lens shift/.test(w)));
  const s3 = structuredClone(side);
  s3.cameras = [];
  const nc = planImport(s3, { dir: FIX });
  assert.equal(byName(nc, 'render'), undefined);
  assert.ok(nc.warnings.some((w) => /no camera/.test(w)));
});
