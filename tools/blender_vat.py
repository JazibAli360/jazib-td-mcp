# blender_vat - run INSIDE Blender (headless) to bake a vertex animation texture (VAT) for td_vat_load
# (27 Oct 2026, Blender 5.2.2 LTS, FX7c card 26, lane T).
#
#   Blender -b --factory-startup --disable-autoexec X.blend --python tools/blender_vat.py -- --out DIR
#           [--name NAME] [--objects A,B] [--start S] [--end E] [--step K] [--no-normals] [--max-width W]
#   Blender -b --factory-startup --python tools/blender_vat.py -- --make-demo cloth|wave --save-blend X.blend --out DIR
#
# Steps every frame start..end (sims such as cloth / soft body / rigid-body-with-fixed-topology are simulated in
# order), takes each object's EVALUATED mesh (modifiers, shape keys, armatures, sims) in world space, converts it to
# TD space (Y-up, metres) and writes into DIR: <name>_pos.exr (+ <name>_nrm.exr), <name>.obj (rest mesh = first
# frame, vt w = point index) and <name>.json (sidecar). Layout + formats: tools/vat_logic.py. Objects default to
# every visible mesh object. Point counts must stay the same every frame (fluids / remeshers that change topology
# are refused). Reads the scene, writes only DIR (and --save-blend). No network. Prints one line
# `JZB_VAT {json}` for the caller. ASCII only.
import argparse
import datetime
import json
import os
import sys

import bpy  # noqa: E402  (Blender only)
import numpy as np  # noqa: E402  (bundled with Blender)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vat_logic as V  # noqa: E402


def _args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(prog='blender_vat')
    ap.add_argument('--out', required=True)
    ap.add_argument('--name')
    ap.add_argument('--objects', help='comma-separated object names (default: every visible mesh object)')
    ap.add_argument('--start', type=int)
    ap.add_argument('--end', type=int)
    ap.add_argument('--step', type=int, default=1)
    ap.add_argument('--no-normals', action='store_true')
    ap.add_argument('--max-width', type=int, default=V.MAX_W)
    ap.add_argument('--make-demo', choices=('cloth', 'wave'))
    ap.add_argument('--save-blend')
    return ap.parse_args(argv)


# ------------------------------------------------------------------ demo scenes (made by script, no assets)
def _grid_object(name, n, size, z):
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=n, y_segments=n, size=size * 0.5, calc_uvs=True)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, 0.0, z))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def make_demo(kind):
    """cloth: a 48 x 48 cloth sheet drops onto a sphere on a floor (3 s at 30 fps). wave: a 64 x 64 grid with an animated
    Wave modifier (keyframed deform, no sim, 2 s loop at 30 fps)."""
    import bmesh
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    sc.render.fps = 30
    if kind == 'cloth':
        sc.frame_start, sc.frame_end = 1, 90
        cl = _grid_object('Cloth', 48, 2.4, 1.6)
        cl.rotation_euler = (0.0, 0.0, 0.3)
        mod = cl.modifiers.new('Cloth', 'CLOTH')
        mod.settings.quality = 6
        mod.settings.mass = 0.25
        mod.collision_settings.use_self_collision = False
        mod.collision_settings.distance_min = 0.01
        mod.point_cache.frame_start, mod.point_cache.frame_end = 1, 90
        me = bpy.data.meshes.new('Ball')
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.55, calc_uvs=True)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0.0, 0.0, 0.6))
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        ball = bpy.data.objects.new('Ball', me)
        sc.collection.objects.link(ball)
        ball.modifiers.new('Collision', 'COLLISION')
        ball.collision.thickness_outer = 0.02
        fl = _grid_object('Floor', 1, 6.0, 0.0)
        fl.modifiers.new('Collision', 'COLLISION')
    else:
        sc.frame_start, sc.frame_end = 1, 60
        gr = _grid_object('Wave', 64, 3.0, 0.0)
        w = gr.modifiers.new('Wave', 'WAVE')
        w.height, w.width, w.narrowness, w.speed = 0.25, 0.9, 1.2, 0.05  # ripples move with the scene frame
    bpy.context.view_layer.update()


# ------------------------------------------------------------------ bake
def _objects(names):
    sc = bpy.context.scene
    if names:
        obs = []
        for n in names:
            ob = bpy.data.objects.get(n)
            if ob is None or ob.type != 'MESH':
                raise SystemExit('VAT: no mesh object named {!r}'.format(n))
            obs.append(ob)
        return obs
    obs = [ob for ob in sc.objects if ob.type == 'MESH' and not ob.hide_render and ob.visible_get()]
    if not obs:
        raise SystemExit('VAT: no visible mesh objects')
    return sorted(obs, key=lambda o: o.name)


def _mesh_arrays(ob, dg, want_normals):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh(preserve_all_data_layers=False, depsgraph=dg)
    try:
        n = len(me.vertices)
        co = np.empty(n * 3, dtype=np.float64)
        me.vertices.foreach_get('co', co)
        co = co.reshape(n, 3)
        mw = np.array(ev.matrix_world, dtype=np.float64)
        wco = co @ mw[:3, :3].T + mw[:3, 3]
        nrm = None
        if want_normals:
            nn = np.empty(n * 3, dtype=np.float64)
            src = getattr(me, 'vertex_normals', None)
            if src is not None and len(src) == n:
                src.foreach_get('vector', nn)
            else:
                me.vertices.foreach_get('normal', nn)
            nn = nn.reshape(n, 3) @ np.linalg.inv(mw[:3, :3])  # inverse-transpose
            ln = np.linalg.norm(nn, axis=1, keepdims=True)
            nrm = nn / np.maximum(ln, 1e-12)
        return wco, nrm, me
    except Exception:
        ev.to_mesh_clear()
        raise


def _topology(me, offset):
    polys, uvs = [], []
    uvl = me.uv_layers.active
    loops = np.empty(len(me.loops), dtype=np.int64)
    me.loops.foreach_get('vertex_index', loops)
    if uvl is not None:
        luv = np.empty(len(me.loops) * 2, dtype=np.float64)
        uvl.data.foreach_get('uv', luv)
        luv = luv.reshape(-1, 2)
    for p in me.polygons:
        s, k = p.loop_start, p.loop_total
        polys.append([int(v) + offset for v in loops[s:s + k]])
        uvs.append([tuple(luv[j]) for j in range(s, s + k)] if uvl is not None else [(0.0, 0.0)] * k)
    return polys, uvs


def bake(a):
    sc = bpy.context.scene
    unit = sc.unit_settings.scale_length if sc.unit_settings.system != 'NONE' else 1.0
    start = sc.frame_start if a.start is None else a.start
    end = sc.frame_end if a.end is None else a.end
    step = max(1, int(a.step))
    if end < start:
        raise SystemExit('VAT: end < start')
    frames = list(range(start, end + 1, step))
    obs = _objects([s for s in (a.objects or '').split(',') if s.strip()])
    name = a.name or os.path.splitext(os.path.basename(bpy.data.filepath or 'vat'))[0] or 'vat'
    want_n = not a.no_normals
    pos, nrm, counts = [], [], None
    polys, uvs, objects = [], [], []
    # sims compute in order: walk every scene frame from the sim start up to `end`, keep the baked ones
    walk_from = min(start, sc.frame_start)
    keep = set(frames)
    for fr in range(walk_from, end + 1):
        sc.frame_set(fr)
        if fr not in keep:
            continue
        dg = bpy.context.evaluated_depsgraph_get()
        fp, fn, cnt, off = [], [], [], 0
        for ob in obs:
            wco, wn, me = _mesh_arrays(ob, dg, want_n)
            try:
                if fr == frames[0]:
                    pl, uv = _topology(me, off)
                    polys += pl
                    uvs += uv
                    objects.append({'name': ob.name, 'points': len(wco), 'first': off})
            finally:
                ob.evaluated_get(dg).to_mesh_clear()
            cnt.append(len(wco))
            off += len(wco)
            fp.append(V.to_td_np(wco, unit))
            if want_n:
                fn.append(V.to_td_np(wn, 1.0))
        if counts is None:
            counts = cnt
        elif cnt != counts:
            raise SystemExit('VAT: point count changed at frame {} ({} -> {}): topology must stay fixed '
                             '(fluids / remesh are not VAT-soft)'.format(fr, counts, cnt))
        pos.append(np.concatenate(fp))
        if want_n:
            nrm.append(np.concatenate(fn))
    pos = np.stack(pos)
    npts = pos.shape[1]
    lay = V.layout(npts, len(frames), a.max_width)
    os.makedirs(a.out, exist_ok=True)
    files = {'mesh': name + '.obj', 'pos': name + '_pos.exr', 'nrm': (name + '_nrm.exr') if want_n else None}
    V.write_exr(os.path.join(a.out, files['pos']), V.pack(pos, lay['width'], lay['rows_per_frame'], 1.0))
    if want_n:
        V.write_exr(os.path.join(a.out, files['nrm']), V.pack(np.stack(nrm), lay['width'], lay['rows_per_frame'], 0.0))
    hdr = 'jazib-td-mcp VAT rest mesh ({}); vt w = VAT point index'.format(name)
    with open(os.path.join(a.out, files['mesh']), 'w', encoding='ascii') as f:
        f.write(V.obj_text(pos[0], polys, uvs, hdr))
    src = {'blend': bpy.data.filepath or None, 'blender': bpy.app.version_string,
           'made': datetime.datetime.now().isoformat(timespec='seconds'), 'unit_scale': unit}
    side = V.sidecar(name, len(frames), npts, lay, sc.render.fps / max(sc.render.fps_base, 1e-9), start, end, step,
                     files, V.bounds(pos), V.bounds(pos[:1]), objects, src)
    bad = V.check_sidecar(side)
    if bad:
        raise SystemExit('VAT: sidecar check failed: {}'.format(bad))
    jp = os.path.abspath(os.path.join(a.out, name + '.json'))
    with open(jp, 'w', encoding='ascii') as f:
        f.write(V.dumps(side))
    return {'sidecar': jp, 'name': name, 'frames': len(frames), 'points': npts, 'width': lay['width'],
            'rows_per_frame': lay['rows_per_frame'], 'height': lay['height'], 'objects': [o['name'] for o in objects],
            'polys': len(polys), 'fps': side['fps']}


def main():
    a = _args()
    if a.make_demo:
        make_demo(a.make_demo)
        if a.save_blend:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save_blend), check_existing=False)
        if not a.name:
            a.name = 'vat_demo_' + a.make_demo
    r = bake(a)
    print('JZB_VAT ' + json.dumps(r))


main()
