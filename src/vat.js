// td_vat_load (27 Oct 2026, lane T, FX7c card 26): vertex animation textures baked in Blender play in TD at 60 fps.
// Bake: tools/blender_vat.py in a headless Blender 5.2.2 (factory startup, autoexec off) -> output/vat/<name>/
// <name>.json (schema jazib-vat/1) + <name>_pos.exr (+ _nrm.exr) + <name>.obj; layout: tools/vat_logic.py.
// TD half: td/vat.py (handlers command vat_load). Contract: docs/PROTOCOL.md "vat_load".
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { blenderPath } from './blender.js';

export const VAT_SCHEMA = 'jazib-vat/1';
export const VAT_SIDECAR_MAX = 4 * 1024 * 1024;

// Same rules as tools/vat_logic.check_sidecar and td/vat.py check_sidecar.
export function checkVatSidecar(s) {
  const bad = [];
  if (!s || typeof s !== 'object') return ['sidecar must be a JSON object'];
  if (s.schema !== VAT_SCHEMA) bad.push(`schema is ${JSON.stringify(s.schema)}, want ${VAT_SCHEMA} (bake with tools/blender_vat.py)`);
  for (const k of ['frames', 'points', 'width', 'rows_per_frame', 'height']) if (!Number.isInteger(s[k]) || s[k] < 1) bad.push(`${k} must be a positive int`);
  if (!bad.length) {
    if (s.width * s.rows_per_frame < s.points) bad.push('width x rows_per_frame < points');
    if (s.height !== s.frames * s.rows_per_frame) bad.push('height != frames x rows_per_frame');
  }
  for (const k of ['mesh', 'pos']) if (!s.files?.[k]) bad.push(`files.${k} missing`);
  return bad;
}

// sidecar file -> { side, mesh_file, pos_file, nrm_file } (files resolved beside the sidecar, must exist).
export function readVat(file) {
  const st = fs.statSync(file);
  if (st.size > VAT_SIDECAR_MAX) throw new Error(`sidecar over ${VAT_SIDECAR_MAX} bytes: ${file}`);
  const side = JSON.parse(fs.readFileSync(file, 'utf8'));
  const bad = checkVatSidecar(side);
  if (bad.length) throw new Error(`bad VAT sidecar ${file}: ${bad.join('; ')}`);
  const dir = path.dirname(file);
  const at = (f) => (f ? path.resolve(dir, f) : null);
  const out = { side, mesh_file: at(side.files.mesh), pos_file: at(side.files.pos), nrm_file: at(side.files.nrm) };
  for (const k of ['mesh_file', 'pos_file', 'nrm_file']) if (out[k] && !fs.existsSync(out[k])) throw new Error(`${k} missing: ${out[k]}`);
  return out;
}

// Headless bake. demo 'cloth' | 'wave' makes its own scene (and saves it beside the bake). Returns the JZB_VAT line.
export function runVatBake({ blend, demo, outDir, name, objects, start, end, step, normals = true, root, blender = blenderPath(), timeoutMs = 300000 }) {
  if (!fs.existsSync(blender)) throw new Error(`Blender not found at ${blender} (set BLENDER_PATH)`);
  const script = path.join(root, 'tools', 'blender_vat.py');
  fs.mkdirSync(outDir, { recursive: true });
  const args = ['-b', '--factory-startup', '--disable-autoexec'];
  if (blend) {
    if (!/\.blend$/i.test(blend) || !fs.existsSync(blend)) throw new Error(`not a .blend file: ${blend}`);
    args.push(blend);
  }
  args.push('--python', script, '--', '--out', outDir, '--name', name);
  if (demo) args.push('--make-demo', demo, '--save-blend', path.join(outDir, `${name}.blend`));
  if (objects?.length) args.push('--objects', objects.join(','));
  if (start !== undefined) args.push('--start', String(start));
  if (end !== undefined) args.push('--end', String(end));
  if (step !== undefined) args.push('--step', String(step));
  if (normals === false) args.push('--no-normals');
  const out = execFileSync(blender, args, { encoding: 'utf8', timeout: timeoutMs, maxBuffer: 32 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] });
  const line = out.split('\n').find((l) => l.startsWith('JZB_VAT '));
  if (!line) throw new Error(`Blender VAT bake printed no result:\n${out.slice(-2000)}`);
  return JSON.parse(line.slice('JZB_VAT '.length));
}

export function registerVat({ tool, call, z, CONFIG, ROOT }) {
  const opn = z.string().regex(/^[A-Za-z_][A-Za-z0-9_]*$/);
  tool('td_vat_load', 'Vertex animation texture (VAT) -> a TD COMP that plays a Blender bake (cloth, soft body, shape keys, armature, keyframed deforms; any sim with fixed topology) on its mesh at 60 fps, whatever the sim cost. Source: json = a jazib-vat/1 sidecar (relative = output/), or blend = a .blend baked first in a headless Blender 5.2.2 (tools/blender_vat.py: factory startup, autoexec off; every visible mesh or objects; start/end/step; normals) into output/vat/<name>/, or demo = cloth | wave (a scripted demo scene, baked the same way). Files: <name>_pos.exr (32F, one column per point, one row band per frame, absolute TD-space positions), <name>_nrm.exr, <name>.obj (rest mesh, uv w = point index), <name>.json. TD COMP (default vat_<name>): pos/nrm Movie File In (32F, passthrough), clock (Play x Speed x bake fps), GLSL MAT on the rest mesh (texelFetch by point index, lerp between frames, baked or flat normals, own key+fill light, Map TOP via the mesh uv), frame_pos GLSL TOP (this frame\'s positions per point, 32F) -> out2, orbit camera + Render TOP -> out1 (default 1080x1920). Pars: VAT page Play, Speed, Loop (loop/once/pingpong), Interp, Scrub + Frame (drive from audio/timeline), Reset; Look; Camera. Houdini VAT files are not read (Blender only). dry:true bakes/reads and plans only (no TD).',
    { json: z.string().optional(), blend: z.string().optional(), demo: z.enum(['cloth', 'wave']).optional(),
      objects: z.array(z.string()).max(256).optional(), start: z.number().int().optional(), end: z.number().int().optional(), step: z.number().int().min(1).max(100).optional(),
      normals: z.boolean().optional().describe('bake normals (default true; false = flat shading)'),
      bake_name: opn.optional().describe('output/vat/<bake_name>/ (default from the .blend / vat_demo_<demo>)'),
      parent: z.string().optional().describe('default /project1'), name: opn.optional().describe('default vat_<bake name>'),
      res: z.tuple([z.number().int().min(16).max(8192), z.number().int().min(16).max(8192)]).optional(),
      panel: z.enum(['zkit', 'plain']).optional(), frames: z.number().int().min(1).max(120).optional(), dry: z.boolean().optional() },
    async (a) => {
      const srcs = [a.json, a.blend, a.demo].filter(Boolean).length;
      if (srcs !== 1) throw new Error('give exactly one of json, blend, demo');
      const abs = (f) => (path.isAbsolute(f) ? f : path.resolve(CONFIG.outputDir, f));
      let sidecar, baked = null;
      if (a.json) sidecar = abs(a.json);
      else {
        const base = a.bake_name || (a.demo ? `vat_demo_${a.demo}` : path.basename(a.blend, path.extname(a.blend)).replace(/[^A-Za-z0-9_]+/g, '_'));
        const outDir = path.join(path.resolve(CONFIG.outputDir), 'vat', base);
        baked = runVatBake({ blend: a.blend ? abs(a.blend) : undefined, demo: a.demo, outDir, name: base, objects: a.objects, start: a.start, end: a.end, step: a.step, normals: a.normals, root: ROOT });
        sidecar = baked.sidecar;
      }
      const v = readVat(sidecar);
      const summary = { sidecar, baked, frames: v.side.frames, points: v.side.points, fps: v.side.fps, texture: [v.side.width, v.side.height], files: { mesh: v.mesh_file, pos: v.pos_file, nrm: v.nrm_file } };
      if (a.dry) return { dry: true, ...summary };
      const send = { sidecar: v.side, sidecar_file: sidecar, mesh_file: v.mesh_file, pos_file: v.pos_file, nrm_file: v.nrm_file, parent: a.parent || '/project1' };
      for (const k of ['name', 'res', 'panel', 'frames']) if (a[k] !== undefined) send[k] = a[k];
      const td = await call('vat_load', send, 120000);
      return { ...td, ...summary };
    });
}
