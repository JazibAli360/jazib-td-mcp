// Blender -> TD (26 Oct 2026; Blender 5.2.2 LTS headless, TD 2025.31550). Pure planning (offline-tested) plus the
// headless export run. The sidecar JSON comes from tools/blender_export.py (maths: tools/blender_td_logic.py): TD
// axis convention (Y-up, metres, rotate xyz) is already applied there; this file only turns it into op specs that
// td/handlers.py cmd_import_blender builds. Nothing here talks to a running Blender (that is the blender MCP's job).
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

export const SCHEMA = 'jazib-blender-td/1';
export const BLENDER_APP = '/Applications/Blender.app/Contents/MacOS/Blender';
export const SIDECAR_MAX_BYTES = 5 * 1024 * 1024;
export const MAX_CAMERAS = 32;
export const MAX_LIGHTS = 64;

export const opName = (prefix, s) => {
  const b = String(s ?? '').replace(/[^A-Za-z0-9_]+/g, '_').replace(/^_+|_+$/g, '') || 'x';
  return `${prefix}_${b}`.slice(0, 60);
};
const num = (v, d = 0) => (Number.isFinite(Number(v)) ? Number(v) : d);
const r6 = (v) => Math.round(num(v) * 1e6) / 1e6;

export function blenderPath(env = process.env) {
  return env.BLENDER_PATH || BLENDER_APP;
}

export function readSidecar(file) {
  const st = fs.statSync(file);
  if (st.size > SIDECAR_MAX_BYTES) throw new Error(`sidecar over ${SIDECAR_MAX_BYTES} bytes: ${file}`);
  const s = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (s?.schema !== SCHEMA) throw new Error(`not a ${SCHEMA} sidecar (schema ${s?.schema}): ${file}`);
  for (const k of ['cameras', 'lights', 'objects']) if (!Array.isArray(s[k])) throw new Error(`sidecar.${k} must be a list`);
  if (s.cameras.length > MAX_CAMERAS || s.lights.length > MAX_LIGHTS) throw new Error(`too many cameras/lights (max ${MAX_CAMERAS}/${MAX_LIGHTS})`);
  return s;
}

// Run tools/blender_export.py in a headless Blender: factory startup (no user add-ons, so no MCP socket) and
// --disable-autoexec (scripts inside the .blend never run). Returns the parsed JZB_EXPORT line.
export function runBlenderExport({ blend, outDir, name, format = 'usd', root, blender = blenderPath(), timeoutMs = 180000 }) {
  if (!fs.existsSync(blender)) throw new Error(`Blender not found at ${blender} (set BLENDER_PATH)`);
  if (!/\.blend$/i.test(blend) || !fs.existsSync(blend)) throw new Error(`not a .blend file: ${blend}`);
  fs.mkdirSync(outDir, { recursive: true });
  const script = path.join(root, 'tools', 'blender_export.py');
  const args = ['-b', '--factory-startup', '--disable-autoexec', blend, '--python', script, '--', '--out', outDir, '--name', name, '--format', format];
  const out = execFileSync(blender, args, { encoding: 'utf8', timeout: timeoutMs, maxBuffer: 16 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
  const line = out.split('\n').find((l) => l.startsWith('JZB_EXPORT '));
  if (!line) throw new Error(`Blender export printed no result:\n${out.slice(-2000)}`);
  return JSON.parse(line.slice('JZB_EXPORT '.length));
}

const xformPars = (x) => {
  const t = x?.t || [0, 0, 0], r = x?.r || [0, 0, 0], s = x?.s || [1, 1, 1];
  return { xord: 'srt', rord: 'xyz', tx: r6(t[0]), ty: r6(t[1]), tz: r6(t[2]), rx: r6(r[0]), ry: r6(r[1]), rz: r6(r[2]), sx: r6(s[0]), sy: r6(s[1]), sz: r6(s[2]) };
};

// Diagonal FOV of a projector image (hfov + aspect): the light cone must cover it or the corners go dark.
export function diagFov(hfov, aspect) {
  const th = Math.tan((num(hfov) * Math.PI) / 360);
  const tv = th / Math.max(num(aspect, 1), 1e-6);
  return (2 * Math.atan(Math.hypot(th, tv)) * 180) / Math.PI;
}

// sidecar -> op specs for cmd_import_blender. geo: 'usd' | 'fbx' | 'none'. dir = folder holding the sidecar.
export function planImport(side, { dir, geo = 'usd', file } = {}) {
  const warnings = [...(side.warnings || [])];
  const ops = [];
  const g = side.geometry || {};
  let geoOp = null;
  if (geo !== 'none') {
    const rel = file ? null : g[geo];
    const f = file || (rel ? path.resolve(dir, rel) : null);
    if (!f) warnings.push(`no ${geo} file in the sidecar: geometry not imported`);
    else {
      if (!fs.existsSync(f)) warnings.push(`geometry file missing: ${f}`);
      geoOp = 'geo';
      const pars = geo === 'usd' ? { file: f, cameras: false, usematerial: true } : { file: f, cameras: false, lights: false };
      ops.push({ name: 'geo', type: geo === 'usd' ? 'usdCOMP' : 'fbxCOMP', pars, pulse: ['imp'], comment: `Blender geometry (${geo}, Y-up, metres): ${path.basename(f)}` });
    }
  }
  const camNames = [];
  for (const c of side.cameras) {
    const v = c.view || {};
    const n = opName('cam', c.name);
    camNames.push(n);
    const pars = { ...xformPars(c.xform), near: r6(v.near ?? 0.1), far: r6(v.far ?? 1000), winx: r6(v.winx), winy: r6(v.winy) };
    if (v.projection === 'ortho') Object.assign(pars, { projection: 'ortho', orthowidth: r6(v.orthowidth) });
    else Object.assign(pars, { projection: 'perspective', viewanglemethod: 'horzfov', fov: r6(v.hfov) });
    ops.push({ name: n, type: 'cameraCOMP', pars, comment: `Blender camera ${c.name}: ${c.lens_mm} mm, sensor ${(c.sensor_mm || []).join('x')} ${c.sensor_fit}, shift ${(c.shift || []).join(',')} -> hfov ${v.hfov}` });
  }
  const lightNames = [];
  for (const l of side.lights) {
    const lv = l.light || {};
    const n = opName('light', l.name);
    lightNames.push(n);
    const pars = { ...xformPars(l.xform), lighttype: lv.lighttype || 'point', cr: r6(lv.color?.[0] ?? 1), cg: r6(lv.color?.[1] ?? 1), cb: r6(lv.color?.[2] ?? 1) };
    const exprs = { dimmer: `parent().par.Lightdimmer * ${r6(lv.dimmer ?? 1)}` };
    if (lv.lighttype === 'cone') Object.assign(pars, { coneangle: r6(lv.coneangle ?? 45), conedelta: r6(lv.conedelta ?? 3) });
    let comment = `Blender ${lv.kind} light ${l.name}: ${lv.energy} W -> dimmer ${lv.dimmer} (heuristic)`;
    const pj = l.projector;
    if (pj) {
      const m = opName('map', l.name);
      const [w, h] = pj.res || side.scene?.resolution || [1920, 1080];
      if (pj.texture) {
        if (!fs.existsSync(pj.texture)) warnings.push(`${l.name}: projector texture missing: ${pj.texture}`);
        ops.push({ name: m, type: 'moviefileinTOP', pars: { file: pj.texture }, comment: `Projector image for ${l.name}` });
      } else {
        ops.push({ name: m, type: 'rampTOP', pars: { outputresolution: 'custom', resolutionw: w, resolutionh: h }, comment: `Projector test image for ${l.name} (no texture given: set projector = image path in Blender)` });
      }
      const cone = Math.max(num(lv.coneangle, 0), diagFov(pj.hfov, w / h) + 2);
      Object.assign(pars, { lighttype: 'cone', coneangle: r6(cone), conedelta: r6(lv.conedelta ?? 3), projmap: m, projmaptype: 'spot', projmapmode: 'simplehorzfov', projangle: r6(pj.hfov) });
      if (pj.shift && (num(pj.shift[0]) || num(pj.shift[1]))) warnings.push(`${l.name}: projector lens shift ${pj.shift} not modelled (LK_projection_room pads the canvas for that)`);
      comment = `Projector ${l.name}: throw ${pj.throw} -> hfov ${pj.hfov} deg, map ${w}x${h}, cone ${r6(cone)} deg (covers the image diagonal)`;
    }
    ops.push({ name: n, type: 'lightCOMP', pars, exprs, comment });
  }
  const wc = side.world?.color || [0, 0, 0];
  const peak = Math.max(...wc.map((v) => num(v)), 1e-6);
  ops.push({ name: 'ambient', type: 'ambientlightCOMP', pars: { cr: r6(wc[0] / peak), cg: r6(wc[1] / peak), cb: r6(wc[2] / peak) }, exprs: { dimmer: 'parent().par.Ambient' }, comment: `Ambient from the Blender world colour ${wc.join(', ')} (strength ${side.world?.strength})` });
  const [rw, rh] = side.scene?.resolution || [1920, 1080];
  const active = side.cameras.find((c) => c.active);
  const camDefault = active ? opName('cam', active.name) : camNames[0];
  if (camNames.length) {
    ops.push({ name: 'render', type: 'renderTOP', pars: { geometry: geoOp || '', lights: [...lightNames, 'ambient'].join(' '), outputresolution: 'custom' },
      exprs: { camera: 'parent().par.Camera.eval()', resolutionw: 'parent().par.Resw', resolutionh: 'parent().par.Resh' }, comment: 'Through the chosen Blender camera (Camera par); resolution = Blender render size (Resw/Resh).' });
    ops.push({ name: 'out', type: 'nullTOP', comment: 'Output' });
  } else warnings.push('no camera in the scene: no render built');
  const wires = camNames.length ? [['render', 'out']] : [];
  const controls = [
    ...(camNames.length ? [{ name: 'Camera', style: 'Menu', menuNames: camNames, menuLabels: side.cameras.map((c) => c.name), default: camDefault }] : []),
    { name: 'Lightdimmer', label: 'Light dimmer', style: 'Float', default: 1, min: 0, max: 4, normMin: 0, normMax: 2 },
    { name: 'Ambient', style: 'Float', default: 0.15, min: 0, max: 1, normMin: 0, normMax: 1 },
    { name: 'Resw', label: 'Render width', style: 'Int', default: rw, min: 8, max: 8192, normMin: 64, normMax: 3840 },
    { name: 'Resh', label: 'Render height', style: 'Int', default: rh, min: 8, max: 8192, normMin: 64, normMax: 3840 },
  ];
  const maps = ops.filter((o) => o.name.startsWith('map_')).map((o) => o.name);
  const stages = [
    { title: 'Controls + Blender data', role: 'control', ops: ['sidecar', 'report'], body: 'Camera, light dimmer, ambient, render size on the COMP (Blender page). sidecar = the export JSON.' },
    ...(geoOp ? [{ title: 'Geometry from Blender', role: 'input', ops: [geoOp], body: 'USD/FBX COMP, Y-up metres.' }] : []),
    ...(camNames.length ? [{ title: 'Cameras', role: 'process', ops: camNames, body: 'Matched FOV, aspect and lens shift.' }] : []),
    { title: 'Lights + projectors', role: 'process', ops: [...maps, ...lightNames, 'ambient'], body: 'Projectors: Light COMP + projection map, throw = cone.' },
    ...(camNames.length ? [{ title: 'Render', role: 'output', ops: ['render', 'out'], body: 'Render TOP through the chosen camera.' }] : []),
  ];
  const report = ['Blender import report (jazib-td td_import_blender)', `source: ${side.source?.blend} (Blender ${side.source?.blender}, ${side.source?.exported})`,
    `units: ${side.units?.system} scale_length ${side.units?.scale_length} -> metres; axis ${side.axis?.point_map}`,
    `cameras ${side.cameras.length}, lights ${side.lights.length} (projectors ${maps.length}), objects ${side.objects.length}`,
    ...warnings.map((w) => `- ${w}`), '- light dimmers from watts are a heuristic (TD has no physical units); TD light attenuation off'].join('\n');
  return { ops, wires, controls, stages, report, warnings, cameras: camNames, lights: lightNames, projectors: maps, geo: geoOp };
}
