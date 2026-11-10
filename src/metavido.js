// td_metavido (27 Oct 2026, lane T, FX7c card 27): Metavido clips (Keijiro Takahashi's iPhone LiDAR video subformat:
// colour + hue-encoded depth + human stencil + a burnt-in camera-pose barcode in one 1920x1080 frame) -> TD colour /
// depth / world-points TOPs, a pose CHOP and the recording camera. TD half: td/metavido.py; reference decoder:
// tools/metavido_logic.py. Contract: docs/PROTOCOL.md "metavido".
import fs from 'node:fs';
import path from 'node:path';

export const MV_DEMO = 'media/demo/metavido/TaiwanStreet1-H264.mp4';
export const MV_EXT = /\.(mp4|mov|m4v|webm|mkv)$/i;

// file -> absolute path (relative = the repo root jazib-td-mcp/; default the demo clip). Throws when missing or not a video.
export function resolveClip(file, root) {
  const f = path.isAbsolute(file || '') ? file : path.resolve(root, file || MV_DEMO);
  if (!MV_EXT.test(f)) throw new Error(`not a video file (.mp4/.mov/.m4v/.webm/.mkv): ${f}`);
  if (!fs.existsSync(f)) throw new Error(`Metavido clip not found: ${f}${file ? '' : ' (demo clip: see media/demo/metavido/SOURCES.md)'}`);
  return f;
}

export function registerMetavido({ tool, call, z, ROOT }) {
  tool('td_metavido', 'Metavido decoder (Keijiro Takahashi\'s volumetric video subformat: iPhone LiDAR recordings with colour, hue-encoded depth, human stencil and the camera pose burnt in as a barcode, 1920x1080). file = the clip (relative = the repo root jazib-td-mcp/; default the demo media/demo/metavido/TaiwanStreet1-H264.mp4, Unlicense). Builds (or updates) COMP mv_<stem> under parent: Movie File In (passthrough), GLSL TOPs meta_decode (12 floats from the barcode), pose (TD pose), colour -> out1 (960x1080; Stencil = premultiplied alpha from the human stencil), depth -> out2 (960x540 32F metres), points -> out3 (960x540 32F TD world xyz per depth texel, w = 1 when inside near..far: feed instancing / pointcloud / PX), pose_out CHOP (tx ty tz rx ry rz [rotate order zxy] fov hfov near far shiftx shifty valid hash; one frame late: nextframe download) and cam = the recording camera. Pars: Play, Speed, Scrub + Index, Stencil, Margin. Unity -> TD by mirroring Z.',
    { file: z.string().optional(), parent: z.string().optional().describe('default /project1'),
      name: z.string().regex(/^[A-Za-z_][A-Za-z0-9_]*$/).optional(), frames: z.number().int().min(1).max(120).optional(),
      dry: z.boolean().optional() },
    async (a) => {
      const file = resolveClip(a.file, ROOT);
      if (a.dry) return { dry: true, file };
      const send = { file, parent: a.parent || '/project1' };
      for (const k of ['name', 'frames']) if (a[k] !== undefined) send[k] = a[k];
      return { ...(await call('metavido', send, 120000)), file };
    });
}
