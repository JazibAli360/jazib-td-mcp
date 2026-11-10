// Component library (27 Oct 2026): td_library_export / _list / _info / _load. Node half of the handlers commands
// library_* (td/library.py, loaded like td/debug.py). Files live in library/<Name>/ (tox, thumb.png, README.md,
// meta.json) + library/index.json + INDEX.md. Contract: docs/PROTOCOL.md "Component library".
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

export const THUMB_MAX = 480;

// Shrink thumb.png in place to <= THUMB_MAX px a side (macOS sips; elsewhere it stays as TD wrote it).
export function shrinkThumb(file, run = execFileSync) {
  if (!file || !fs.existsSync(file)) return { shrunk: false, why: 'no thumb' };
  try {
    run('sips', ['-Z', String(THUMB_MAX), file], { stdio: 'ignore', timeout: 20000 });
    return { shrunk: true, bytes: fs.statSync(file).size };
  } catch (e) {
    return { shrunk: false, why: String(e.message || e).slice(0, 200) };
  }
}

export function registerLibrary({ tool, call, z, ROOT }) {
  const root = path.join(ROOT, 'library');
  const name = z.string().regex(/^[A-Za-z_][A-Za-z0-9_]*$/);
  tool('td_library_export', 'Put a working COMP into the component library: library/<Name>/<Name>.tox (COMP.save) + thumb.png (its first Out TOP, force-cooked each frame for frames (30) then read 3 frames after the last cook, never in the changing script, T-74; shrunk to 480 px) + README.md (first lines of docs/builds/<name>.md, ins/outs, custom pars by page, cook ms) + meta.json (version, TD build, created, inputs/outputs, pars with values, file pars and where they point: repo / td_app / outside, sha256, size); library/index.json + INDEX.md regenerated. A parked COMP is un-parked for the thumbnail and parked again; thumb:false (or no Out TOP) = never un-parked. Refuses a COMP in logs/active_lanes.json unless force. A .tox over 5 MB goes into library/.gitignore (meta + sha stay). version default: the COMP\'s Version par, else the last export\'s, else 0.1.0.',
    { path: z.string(), name: name.optional(), version: z.string().max(40).optional(), frames: z.number().int().min(5).max(300).optional().describe('frames from un-park to the thumbnail read (default 30)'),
      force: z.boolean().optional(), thumb: z.boolean().optional().describe('false: no thumbnail and never un-park (COMPs with audio/DMX/NDI/MIDI outputs)'), doc: z.string().optional().describe('build doc name in docs/builds/ (default from the COMP name)') },
    async (a) => {
      const r = await call('library_export', { ...a, root }, 120000);
      if (r && r.thumb && r.thumb.ok && Math.max(r.thumb.width || 0, r.thumb.height || 0) > THUMB_MAX) r.thumb.resize = shrinkThumb(path.join(r.dir, 'thumb.png'));
      return r;
    });
  tool('td_library_list', 'Read-only: the component library (library/index.json data): name, version, TD build, created, source COMP, size, sha256, in git, summary, outside_files.',
    {}, () => call('library_list', { root }));
  tool('td_library_info', 'Read-only: one library entry: meta.json, README text, whether the .tox is present and its sha256 still matches, thumb path.',
    { name }, (a) => call('library_info', { ...a, root }));
  tool('td_library_load', 'Load a library COMP into parent (loadTox) as newname (default its name); it lands PARKED (allowCooking off: turn it on when you use it), viewers on, its stage plan re-applied, parent arranged. Pre-saved (a .tox load). Refuses an existing name.',
    { name, parent: z.string(), newname: name.optional(), arrange: z.boolean().optional() },
    (a) => call('library_load', { ...a, root }, 120000));
}
