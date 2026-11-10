// TD <-> After Effects helpers (26 Oct 2026; design docs/research/AK_td_aftereffects.md s3.3/s4). Pure functions
// (offline-tested) plus the ffprobe frame check for renders. Input = the JSON that the `aftereffects` MCP's
// read-only `ae_project_export_json` writes (schemaVersion 2, mcp-aftereffects v0.3.2 jsx/helpers.jsx).
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';

export const AE_MAX_BYTES = 25 * 1024 * 1024; // export files above this are refused (AK s4 #1)
export const AE_MAX_CELLS = 500000;          // baked frames x channels sent to TD in one call
const INTERP = { 6612: 'linear', 6613: 'bezier', 6614: 'hold' }; // AE KeyframeInterpolationType ints (names win)
const DIMS = { position: ['x', 'y', 'z'], anchor: ['x', 'y', 'z'], scale: ['x', 'y', 'z'], color: ['r', 'g', 'b', 'a'] };

const clean = (s) => String(s ?? '').replace(/[\t\r\n]+/g, ' ');
export const chanName = (s) => String(s ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'x';
const interpName = (name, num) => (name === 'linear' || name === 'bezier' || name === 'hold' ? name : INTERP[num] || 'linear');
const vec = (v) => (Array.isArray(v) ? v.map(Number) : [Number(v)]);
const kindOf = (v) => (v && typeof v === 'object' && !Array.isArray(v) ? v.__kind || 'object' : null);

function dimNames(matchName, n) {
  const m = String(matchName || '').toLowerCase();
  const key = m.includes('position') ? 'position' : m.includes('anchor') ? 'anchor' : m.includes('scale') ? 'scale' : m.includes('color') ? 'color' : null;
  const names = key ? DIMS[key] : [];
  return Array.from({ length: n }, (_, i) => names[i] || String(i));
}

// One AE temporal-bezier segment, exact (AK s3.3): P0=(tA,vA) P1=(tA+oA*dt, vA+sOut*oA*dt) P2=(tB-iB*dt, vB-sIn*iB*dt)
// P3=(tB,vB); x(u) is monotonic for influences in [0,1], so bisection finds u for t, then y(u). Linear side = 33.33 %
// influence at speed dv/dt (a straight line); hold = vA until tB.
export function segmentValue(t, A, B) {
  const dt = B.t - A.t;
  if (A.out === 'hold') return A.v;
  if (!(dt > 0)) return B.v;
  const slope = (B.v - A.v) / dt;
  const oA = A.out === 'bezier' && A.outEase ? A.outEase.influence / 100 : 1 / 3;
  const sA = A.out === 'bezier' && A.outEase ? A.outEase.speed : slope;
  const iB = B.in === 'bezier' && B.inEase ? B.inEase.influence / 100 : 1 / 3;
  const sB = B.in === 'bezier' && B.inEase ? B.inEase.speed : slope;
  const x1 = A.t + oA * dt, y1 = A.v + sA * oA * dt, x2 = B.t - iB * dt, y2 = B.v - sB * iB * dt;
  const bz = (p0, p1, p2, p3, u) => { const m = 1 - u; return m * m * m * p0 + 3 * m * m * u * p1 + 3 * m * u * u * p2 + u * u * u * p3; };
  let lo = 0, hi = 1;
  for (let k = 0; k < 60; k++) { const mid = (lo + hi) / 2; if (bz(A.t, x1, x2, B.t, mid) < t) lo = mid; else hi = mid; }
  return bz(A.v, y1, y2, B.v, (lo + hi) / 2);
}

// Value of a 1-D key list at time t (held before the first and after the last key).
export function evalKeys(keys, t) {
  if (!keys.length) return 0;
  if (t <= keys[0].t) return keys[0].v;
  for (let i = 0; i < keys.length - 1; i++) if (t < keys[i + 1].t) return segmentValue(t, keys[i], keys[i + 1]);
  return keys[keys.length - 1].v;
}

// AE pixels/percent -> TD units (AK s3.3 unit map). Position: Transform TOP fraction, origin centre, y up.
function toTD(matchName, dim, v, w, h) {
  const m = String(matchName || '');
  if (m === 'ADBE Opacity' || m === 'ADBE Scale') return v / 100;
  if (m === 'ADBE Position' || m === 'ADBE Position_0' || m === 'ADBE Position_1') {
    const d = m === 'ADBE Position_0' ? 'x' : m === 'ADBE Position_1' ? 'y' : dim;
    if (d === 'x') return v / w - 0.5;
    if (d === 'y') return 0.5 - v / h;
  }
  return v;
}

function* walkProps(group, trail = []) {
  if (!group) return;
  for (const p of group.properties || []) yield { p, trail };
  for (const g of group.groups || []) yield* walkProps(g, [...trail, g.name]);
}

// Parse an AE export doc into the tables the TD side builds. opts: {comp, rate, units: 'td'|'ae'}.
export function parseAeExport(doc, opts = {}) {
  if (!doc || typeof doc !== 'object' || !Array.isArray(doc.items)) throw new Error('not an ae_project_export_json file (no items[])');
  const comps = doc.items.filter((i) => i && i.type === 'CompItem');
  if (!comps.length) throw new Error('no CompItem in the export');
  const comp = opts.comp ? comps.find((c) => c.name === opts.comp || String(c.id) === String(opts.comp)) : comps[0];
  if (!comp) throw new Error(`no comp named ${JSON.stringify(opts.comp)} (comps: ${comps.map((c) => c.name).slice(0, 20).join(', ')})`);
  const units = opts.units === 'ae' ? 'ae' : 'td';
  const fps = Number(opts.rate) || Number(comp.frameRate) || 30;
  const w = Number(comp.width) || 1920, h = Number(comp.height) || 1080;
  const start = Number(comp.workAreaStart ?? comp.displayStartTime ?? 0) || 0;
  const dur = Number(comp.workAreaDuration ?? comp.duration) || 0;
  const nFrames = Math.max(1, Math.round(dur * fps));
  const warnings = [];
  const warn = (s) => { if (warnings.length < 50 && !warnings.includes(s)) warnings.push(s); };
  const keys = [['layer', 'prop', 'matchName', 'dim', 't', 'value', 'inInterp', 'outInterp', 'inSpeed', 'inInf', 'outSpeed', 'outInf']];
  const text = [['layer', 't', 'text', 'font', 'size', 'fill', 'just']];
  const markers = [['layer', 't', 'comment', 'duration']];
  const channels = []; // {name, keys}
  const used = new Set();
  const addMarkers = (layer, prop) => { for (const k of prop?.keyframes || []) markers.push([layer, k.time, clean(k.value?.comment), k.value?.duration ?? 0]); };

  addMarkers('(comp)', comp.markers);
  for (const L of comp.layers || []) {
    const lname = clean(L.name || `layer${L.index}`);
    if (L.parentIndex != null) warn(`${lname}: parented to layer ${L.parentIndex}: rebuild the parent chain in TD (values are local)`);
    if (L.stretch != null && Number(L.stretch) !== 100) warn(`${lname}: time stretch ${L.stretch} %: key times taken as comp time [U]`);
    addMarkers(lname, L.markers);
    for (const grp of [L.transformGroup, L.effectsGroup, L.textGroup]) {
      for (const { p, trail } of walkProps(grp)) {
        const pname = [...trail.slice(-1), p.name].filter(Boolean).join(' ');
        if (p.expression) warn(`${lname}.${p.name}: expression not evaluated (${clean(p.expression).slice(0, 60)}); bake it with ae_do comp.sample`);
        const kf = Array.isArray(p.keyframes) ? p.keyframes : [];
        if (!kf.length) continue;
        const k0 = kindOf(kf[0].value);
        if (k0 === 'TextDocument') {
          for (const k of kf) { const d = k.value || {}; text.push([lname, k.time, clean(d.text), clean(d.font || d.fontFamily || ''), d.fontSize ?? '', vec(d.fillColor || []).join(' '), clean(d.justification ?? '')]); }
          continue;
        }
        if (k0) { warn(`${lname}.${p.name}: ${k0} keyframes not baked`); continue; }
        const n = vec(kf[0].value).length;
        const spatial = /SPATIAL/.test(String(p.propertyValueType || '')) && n > 1;
        if (spatial) warn(`${lname}.${p.name}: spatial path baked as straight segments (export has no spatial tangents; exact: ae_do comp.sample)`);
        if (/rotat/i.test(p.matchName || p.name) && units === 'td') warn('rotation kept in AE degrees (AE clockwise; TD sign [U])');
        const dn = dimNames(p.matchName, n);
        const ease = (arr, d) => (Array.isArray(arr) && arr.length ? arr[Math.min(d, arr.length - 1)] : null);
        let noEase = false;
        const keyRow = (k, d) => {
          const inI = interpName(k.inInterpName, k.inInterp), outI = interpName(k.outInterpName, k.outInterp);
          if ((inI === 'bezier' && !k.inEase) || (outI === 'bezier' && !k.outEase)) noEase = true;
          return { inI, outI, inE: ease(k.inEase, spatial ? 0 : d), outE: ease(k.outEase, spatial ? 0 : d) };
        };
        for (let d = 0; d < n; d++) {
          for (const k of kf) {
            const r = keyRow(k, d);
            keys.push([lname, clean(pname), clean(p.matchName), dn[d], k.time, vec(k.value)[d], r.inI, r.outI, r.inE?.speed ?? '', r.inE?.influence ?? '', r.outE?.speed ?? '', r.outE?.influence ?? '']);
          }
        }
        if (noEase) warn(`${lname}.${p.name}: bezier keys without ease data treated as linear`);
        const mk = (k, v) => { const r = keyRow(k, 0); return { t: Number(k.time), v, in: r.inI === 'bezier' && !r.inE ? 'linear' : r.inI, out: r.outI === 'bezier' && !r.outE ? 'linear' : r.outI, inEase: r.inE, outEase: r.outE }; };
        const base = chanName(`${lname}_${p.name}`);
        if (spatial) { // one ease along the path: bake progress 0..len per segment, then interpolate the vector
          const segs = [];
          for (let i = 0; i < kf.length; i++) {
            const a = vec(kf[i].value), b = i + 1 < kf.length ? vec(kf[i + 1].value) : a;
            segs.push({ a, b, len: Math.hypot(...a.map((x, j) => (b[j] ?? x) - x)) });
          }
          const prog = [];
          for (let i = 0; i < kf.length - 1; i++) prog.push([mk(kf[i], 0), mk(kf[i + 1], segs[i].len)]);
          for (let d = 0; d < n; d++) {
            channels.push({ name: uniq(`${base}_${dn[d]}`, used), matchName: p.matchName, dim: dn[d], at: (t) => {
              if (kf.length === 1 || t <= kf[0].time) return vec(kf[0].value)[d];
              for (let i = 0; i < prog.length; i++) {
                if (t < kf[i + 1].time) {
                  const s = segs[i]; const u = s.len > 0 ? segmentValue(t, ...prog[i]) / s.len : 0;
                  return s.a[d] + (s.b[d] - s.a[d]) * u;
                }
              }
              return vec(kf[kf.length - 1].value)[d];
            } });
          }
        } else {
          for (let d = 0; d < n; d++) {
            const list = kf.map((k) => { const r = keyRow(k, d); const o = mk(k, vec(k.value)[d]); o.inEase = r.inE; o.outEase = r.outE; return o; });
            channels.push({ name: uniq(`${base}_${n > 1 ? dn[d] : ''}`.replace(/_$/, ''), used), matchName: p.matchName, dim: dn[d], at: (t) => evalKeys(list, t) });
          }
        }
      }
    }
  }
  const cells = nFrames * channels.length;
  if (cells > AE_MAX_CELLS) throw new Error(`bake too large: ${nFrames} frames x ${channels.length} channels = ${cells} cells (cap ${AE_MAX_CELLS}); pass comp, a lower rate, or a shorter work area`);
  const baked = [channels.map((c) => c.name)];
  for (let f = 0; f < nFrames; f++) {
    const t = start + f / fps;
    baked.push(channels.map((c) => { const v = c.at(t); return Number((units === 'td' ? toTD(c.matchName, c.dim, v, w, h) : v).toFixed(6)); }));
  }
  const meta = [['key', 'value'], ['comp', clean(comp.name)], ['width', w], ['height', h], ['fps', fps], ['start', start], ['duration', dur],
    ['frames', nFrames], ['units', units], ['source', 'ae_project_export_json v' + (doc.schemaVersion ?? '?')], ['aeVersion', clean(doc.aeVersion ?? '')]];
  return { comp: { name: comp.name, width: w, height: h, fps, start, duration: dur, frames: nFrames }, units, meta, keys, text, markers, baked, channels: channels.map((c) => c.name), warnings };
}

function uniq(name, used) {
  let n = name || 'x', i = 2;
  while (used.has(n)) n = `${name}${i++}`;
  used.add(n);
  return n;
}

export function readAeFile(file) {
  const st = fs.statSync(file);
  if (!st.isFile()) throw new Error(`not a file: ${file}`);
  if (st.size > AE_MAX_BYTES) throw new Error(`file is ${st.size} bytes (cap ${AE_MAX_BYTES})`);
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

// ---------------------------------------------------------------- ffprobe frame check (LEARNINGS T-11)
export function parseFfprobe(json) {
  const s = (JSON.parse(json).streams || [])[0];
  if (!s) return null;
  const [a, b] = String(s.r_frame_rate || '0/1').split('/').map(Number);
  return { frames: Number(s.nb_read_frames ?? s.nb_frames), codec: s.codec_name, tag: s.codec_tag_string, pix_fmt: s.pix_fmt, width: s.width, height: s.height, fps: b ? Math.round((a / b) * 1000) / 1000 : null };
}

const FFPROBE = ['/opt/homebrew/bin/ffprobe', '/usr/local/bin/ffprobe'].find((p) => fs.existsSync(p)) || 'ffprobe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// The file may have no moov atom for a few seconds after Record goes off (A s4): retry.
export async function probeFrames(file, { tries = 8, waitMs = 1000 } = {}) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      const out = execFileSync(FFPROBE, ['-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames,nb_frames,codec_name,codec_tag_string,pix_fmt,width,height,r_frame_rate', '-of', 'json', file], { encoding: 'utf8', timeout: 120000 });
      const r = parseFfprobe(out);
      if (r) return r;
    } catch (e) { last = e; }
    await sleep(waitMs);
  }
  return { error: `ffprobe could not read ${file}: ${String(last?.message || 'no video stream').slice(0, 200)}` };
}
