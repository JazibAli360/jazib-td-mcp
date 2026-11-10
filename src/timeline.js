// TL_timeline agent API (phase 4, 26 Oct 2026): td_timeline_* tools. Node half of the handlers commands timeline_*
// (td/handlers.py), which call the COMP's TimelineExt (builders/timeline_ext.py; logic builders/timeline_api_logic.py).
// Contract: docs/PROTOCOL.md "Timeline API"; build + live checks: docs/builds/timeline_phase4.md. Files only under
// output/timeline/ (exports, shows, renders). Wired into src/server.js by registerTimeline() (one line).
import fs from 'node:fs';
import path from 'node:path';
import { probeFrames } from './ae.js';

export const TL_DEFAULT = '/project1/lab/TL_timeline';
export const TL_OPS = ['add_key', 'move_key', 'delete_key', 'set_keys', 'add_lane', 'set_lane', 'delete_lane', 'move_lane',
  'add_marker', 'move_marker', 'delete_marker', 'add_clip', 'set_clip', 'move_clip', 'trim_clip', 'delete_clip', 'set'];
export const TL_ACTIONS = ['play', 'pause', 'toggle', 'stop', 'seek', 'step', 'start', 'end', 'next_marker', 'prev_marker', 'next_key', 'prev_key'];
export const TL_EXPORTS = { show: '.json', lanes_csv: '.csv', markers_json: '.json', markers_csv: '.csv' };
const SHOW_MAX = 8 * 1024 * 1024;

// A file under output/timeline/<sub>/ (relative), or an absolute path that stays under output/. ASCII only.
export function tlFile(outputDir, sub, f, ext) {
  const out = path.resolve(outputDir);
  let p = path.isAbsolute(f) ? path.resolve(f) : path.resolve(out, 'timeline', sub, f);
  if (!path.extname(p)) p += ext;
  if (path.extname(p).toLowerCase() !== ext) throw new Error(`file must end with ${ext}: ${f}`);
  if (!p.startsWith(out + path.sep)) throw new Error(`file must be under ${out}`);
  if (/[^\x20-\x7e]/.test(p)) throw new Error(`file path must be ASCII: ${p}`);
  return p;
}

const slug = (s) => String(s || 'TL_timeline').split('/').pop().replace(/[^\w.-]+/g, '_') || 'TL_timeline';

export function registerTimeline({ tool, call, z, CONFIG }) {
  const comp = z.string().optional().describe(`TL_timeline COMP (default ${TL_DEFAULT})`);
  const time = z.union([z.number(), z.string()]).describe('seconds, or "90f" frames, "8b" beats, "2bar", "3.2.1" bar.beat.16th, "00:00:04:15" SMPTE, "01:04.5", "@Marker", "@Marker+2b"');
  const pick = (a, keys) => Object.fromEntries(keys.filter((k) => a[k] !== undefined).map((k) => [k, a[k]]));

  tool('td_timeline_state', `Read-only: TL_timeline transport (t, frame, play, rate, loop, in/out, length, fps, bpm, timecode, bar.beat, current marker, wraps), lane values now, lane_status (which bound pars are driven / missing), clips on screen, a running take. at = up to 64 times -> lane values there (pure maths, no seek). Time forms: ${time.description}.`,
    { comp, at: z.array(time).max(64).optional() },
    (a) => call('timeline_state', pick(a, ['comp', 'at'])));

  tool('td_timeline_show', 'Read-only: the whole show as data ("tl-show" v1 JSON): settings (length, fps, bpm, beatsperbar, in/out, loop, rate, snap..., clip page), lanes [{name, op, par, min, max, enabled, keys: [[t, v, interp]]}], markers [[t, name]], clips [{id, track, start, dur, src, in, speed, fade, proxy, enabled}] (null = no clips track). parts narrows it. Edit it with td_timeline_edit (ops) or td_timeline_load (a whole document).',
    { comp, parts: z.array(z.enum(['settings', 'lanes', 'markers', 'clips'])).optional() },
    (a) => call('timeline_show', pick(a, ['comp', 'parts'])));

  tool('td_timeline_edit', `Edit the show by data: a list of ops applied in order, validated, ATOMIC by default (one bad op = nothing written; each result says ok/error), written back only to the tables/pars that changed, one undo step. dry:true = report only. Ops: add_key {lane, t, v, interp?: hold|linear|ease|bezier, snap?} | move_key {lane, at|index, t?|by?, v?, interp?} | delete_key {lane, at|index} | set_keys {lane, keys: [[t, v, interp?]]} | add_lane {name, target: "op.par" (op relative to the COMP or absolute) | op+par, min?, max?, enabled?, keys?} | set_lane {name, target?, min?, max?, enabled?, rename?, keys?} | delete_lane {name} | move_lane {name, to} | add_marker {t, name} | move_marker {name|at, t?|by?, rename?} | delete_marker {name|at} | add_clip {id?, src, start, dur|end, track?, in?, speed?, fade?, proxy?, enabled?} | set_clip {id, ...fields, end?, rename?} | move_clip {id, start?|by?, track?} | trim_clip {id, edge: in|out, t} | delete_clip {id} | set {bpm?, length?, fps?, beatsperbar?, inpoint?, outpoint?, loop?, rate?, snap?, snapdiv?, snapunit?, tcmode?, clockmode?, program?, maxplayers?, sourcemode?, blendmode?, premult?, fit?, preroll?}. Times: ${time.description}; at finds a key/marker within tol (0.001 s).`,
    { comp, ops: z.array(z.object({ op: z.enum(TL_OPS) }).passthrough()).min(1).max(2000), atomic: z.boolean().optional(), dry: z.boolean().optional() },
    (a) => call('timeline_edit', pick(a, ['comp', 'ops', 'atomic', 'dry'])));

  tool('td_timeline_transport', 'TL_timeline transport (its own clock, never the project timeline): action play | pause | toggle | stop (pause + to in point) | seek {t | frame} | step {n frames, negative = back} | start | end | next_marker | prev_marker | next_key | prev_key {lane? (default the selected lane)}; and/or rate (-4..4), loop, inpoint, outpoint. Replies with td_timeline_state plus what was set.',
    { comp, action: z.enum(TL_ACTIONS).optional(), t: time.optional(), frame: z.number().optional(), n: z.number().int().optional(), lane: z.string().optional(),
      rate: z.number().min(-4).max(4).optional(), loop: z.boolean().optional(), inpoint: time.optional(), outpoint: time.optional() },
    (a) => call('timeline_transport', pick(a, ['comp', 'action', 't', 'frame', 'n', 'lane', 'rate', 'loop', 'inpoint', 'outpoint'])));

  tool('td_timeline_export', 'Write the show to a file under output/timeline/exports/ (relative file; default <comp>_<what>): what show (tl-show JSON, reload it with td_timeline_load) | lanes_csv (frame,time,<lane>... one row per frame of start..end at fps; defaults 0..length at the timeline fps; lanes = names) | markers_json ({t, name, frame, smpte, bars}) | markers_csv.',
    { comp, what: z.enum(Object.keys(TL_EXPORTS)).optional(), file: z.string().optional(), start: time.optional(), end: time.optional(),
      fps: z.number().positive().max(240).optional(), lanes: z.array(z.string()).optional() },
    (a) => {
      const what = a.what || 'show';
      const file = tlFile(CONFIG.outputDir, 'exports', a.file || `${slug(a.comp)}_${what}`, TL_EXPORTS[what]);
      fs.mkdirSync(path.dirname(file), { recursive: true });
      return call('timeline_export', { ...pick(a, ['comp', 'start', 'end', 'fps', 'lanes']), what, file });
    });

  tool('td_timeline_load', 'Load a show document (tl-show JSON: settings / lanes / markers / clips, as td_timeline_show gives it) into TL_timeline: show = the object, or file = a .json (relative = output/timeline/shows/ or exports/). mode replace (default: the parts present replace the COMP\'s, missing parts stay) | merge (same-named lanes / clip ids / marker names replaced, new ones added). Validated first (a bad document changes nothing); one undo step; dry:true = report only.',
    { comp, show: z.record(z.string(), z.any()).optional(), file: z.string().optional(), mode: z.enum(['replace', 'merge']).optional(), dry: z.boolean().optional() },
    (a) => {
      if (!!a.show === !!a.file) throw new Error('give show or file (one of them)');
      let show = a.show;
      if (a.file) {
        let f = tlFile(CONFIG.outputDir, 'shows', a.file, '.json');
        if (!fs.existsSync(f) && !path.isAbsolute(a.file)) f = tlFile(CONFIG.outputDir, 'exports', a.file, '.json');
        if (fs.statSync(f).size > SHOW_MAX) throw new Error(`${f} is over ${SHOW_MAX} bytes`);
        show = JSON.parse(fs.readFileSync(f, 'utf8'));
      }
      return call('timeline_load', { ...pick(a, ['comp', 'mode', 'dry']), show });
    });

  tool('td_timeline_record', 'Stepped take of TL_timeline to a .mov under output/timeline/renders/: the transport is parked (paused at start, In/Out = the take, Loop off, Rate 1), the shared offline recorder (fresh Movie File Out + pump, realTime off for the take, never cookRate) records source (default the COMP\'s program TOP) while the timeline clock steps 1/cookRate per TD frame from the frame Record goes on; afterwards the transport is put back. start/end default the In/Out points; fps default the timeline Fps; codec prores422hq (default) | prores4444 (alpha) | hapq. Reply adds ffprobe and frames_ok.',
    { comp, file: z.string().describe('relative = under output/timeline/renders/ (.mov added)'), start: time.optional(), end: time.optional(),
      fps: z.number().positive().max(240).optional(), source: z.string().optional().describe('TOP inside the COMP (default program)'),
      codec: z.enum(['prores422hq', 'prores4444', 'hapq']).optional() },
    async (a) => {
      const file = tlFile(CONFIG.outputDir, 'renders', a.file, '.mov');
      fs.mkdirSync(path.dirname(file), { recursive: true });
      const r = await call('timeline_record', { ...pick(a, ['comp', 'start', 'end', 'fps', 'source', 'codec']), file }, 600000);
      const probe = await probeFrames(file);
      return { ...r, ffprobe: probe, frames_ok: probe.frames === r?.frames_asked };
    });
}
