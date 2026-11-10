# blender_export - run INSIDE Blender (headless) to hand a scene to TouchDesigner (26 Oct 2026, Blender 5.2 LTS).
#
#   Blender -b scene.blend --python tools/blender_export.py -- --out DIR [--name NAME] [--format usd|fbx|both|none]
#   Blender -b --factory-startup --python tools/blender_export.py -- --make-test-scene --save-blend X.blend --out DIR
#
# Writes into DIR: <name>.usdc (geometry, Y-up, metres; cameras/lights left out: TD builds its own from the sidecar)
# and/or <name>.fbx, plus <name>.json = the sidecar td_import_blender reads: cameras (focal, sensor, fit, shift,
# clip -> TD hfov / winx / winy / near / far), lights (type, colour, watts -> dimmer, cone, blend, projector custom
# props), object transforms in TD's axis convention (Y-up, metres, rotate xyz), units, render size, fps, world colour.
# Maths: tools/blender_td_logic.py (pure, tested). Reads the scene, writes only DIR (and --save-blend). No network.
# ASCII only.
import argparse
import datetime
import json
import math
import os
import sys

import bpy  # noqa: E402  (Blender only)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_td_logic as L  # noqa: E402


def _args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(prog='blender_export')
    ap.add_argument('--out', required=True)
    ap.add_argument('--name')
    ap.add_argument('--format', default='usd', choices=('usd', 'fbx', 'both', 'none'))
    ap.add_argument('--make-test-scene', action='store_true')
    ap.add_argument('--save-blend')
    return ap.parse_args(argv)


def _aim(obj, target):
    from mathutils import Vector
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler('XYZ')


def make_test_scene():
    """Tiny stage: a 8 x 4 x 1 m deck box, a FOH camera (35 mm, shift x 0.1), a projector spot (40 deg, throw 1.5)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.render.fps = 60
    me = bpy.data.meshes.new('stage_deck')
    h = (4.0, 2.0, 0.5)
    vs = [(sx * h[0], sy * h[1], sz * h[2] + 0.5) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(vs, [], fs)
    me.update()
    deck = bpy.data.objects.new('Stage_Deck', me)
    sc.collection.objects.link(deck)
    cam_d = bpy.data.cameras.new('Cam_FOH')
    cam_d.lens, cam_d.sensor_width, cam_d.sensor_fit = 35.0, 36.0, 'AUTO'
    cam_d.shift_x, cam_d.clip_start, cam_d.clip_end = 0.1, 0.1, 200.0
    cam = bpy.data.objects.new('Cam_FOH', cam_d)
    sc.collection.objects.link(cam)
    cam.location = (0.0, -12.0, 3.0)
    _aim(cam, (0.0, 0.0, 1.0))
    sc.camera = cam
    ld = bpy.data.lights.new('PROJ_A', 'SPOT')
    ld.energy, ld.spot_size, ld.spot_blend, ld.color = 800.0, math.radians(40.0), 0.15, (1.0, 0.95, 0.9)
    pj = bpy.data.objects.new('PROJ_A', ld)
    sc.collection.objects.link(pj)
    pj.location = (0.0, -8.0, 4.0)
    _aim(pj, (0.0, 0.0, 1.0))
    pj['projector'] = True
    pj['projector_throw'] = 1.5
    pj['projector_res'] = '1920x1080'
    w = bpy.data.worlds.new('World')
    w.color = (0.05, 0.05, 0.08)
    sc.world = w
    bpy.context.view_layer.update()


def _props(obj):
    out = {}
    for src in (obj, obj.data):
        if src is None:
            continue
        for k in src.keys():
            if k.startswith('projector'):
                v = src[k]
                out[k] = list(v) if hasattr(v, '__len__') and not isinstance(v, str) else v
    return out


def _world():
    w = bpy.context.scene.world
    if w is None:
        return {'color': [0.0, 0.0, 0.0], 'strength': 0.0}
    col, strength = list(w.color)[:3], 1.0
    nt = getattr(w, 'node_tree', None)
    if nt is not None:
        for n in nt.nodes:
            if n.type == 'BACKGROUND':
                col = list(n.inputs['Color'].default_value)[:3]
                strength = float(n.inputs['Strength'].default_value)
                break
    return {'color': [round(c, 4) for c in col], 'strength': round(strength, 4)}


def collect(unit):
    sc = bpy.context.scene
    r = sc.render
    res = (r.resolution_x * r.resolution_percentage // 100, r.resolution_y * r.resolution_percentage // 100)
    data = {'objects': [], 'cameras': [], 'lights': [], 'warnings': []}
    for o in sc.objects:
        mw = [list(row) for row in o.matrix_world]
        base = {'name': o.name, 'parent': o.parent.name if o.parent else None, 'blender_matrix_world': mw,
                'visible': not o.hide_render}
        if o.type == 'CAMERA':
            c = o.data
            v = L.camera_view(c.lens, c.sensor_width, c.sensor_height, c.sensor_fit, res[0], res[1],
                              r.pixel_aspect_x, r.pixel_aspect_y, c.shift_x, c.shift_y, c.type == 'ORTHO',
                              c.ortho_scale, c.clip_start, c.clip_end, unit)
            if c.type == 'PANO':
                data['warnings'].append('{}: panoramic camera exported as perspective'.format(o.name))
            base.update({'xform': L.decompose(L.mat4_to_td(mw, 'camera'), unit), 'lens_mm': round(c.lens, 4),
                         'sensor_mm': [round(c.sensor_width, 4), round(c.sensor_height, 4)],
                         'sensor_fit': c.sensor_fit, 'shift': [round(c.shift_x, 5), round(c.shift_y, 5)],
                         'view': v, 'active': sc.camera is o})
            data['cameras'].append(base)
        elif o.type == 'LIGHT':
            ld = o.data
            lv = L.light_values(ld.type, ld.color, ld.energy, getattr(ld, 'spot_size', None),
                                getattr(ld, 'spot_blend', 0.0))
            if ld.type == 'AREA':
                data['warnings'].append('{}: area light approximated as a wide cone'.format(o.name))
            props = _props(o)
            pj = L.projector_values(props, lv.get('coneangle', 45.0)) if props else None
            if pj and ld.type != 'SPOT':
                data['warnings'].append('{}: projector props on a {} light; TD builds it as a cone'.format(o.name, ld.type))
            if pj and pj['texture'] and not os.path.isabs(pj['texture']):
                pj['texture'] = os.path.normpath(bpy.path.abspath(pj['texture']))
            if pj and pj['texture'] and not os.path.exists(pj['texture']):
                data['warnings'].append('{}: projector texture missing: {}'.format(o.name, pj['texture']))
            base.update({'xform': L.decompose(L.mat4_to_td(mw, 'light'), unit), 'light': lv, 'projector': pj})
            data['lights'].append(base)
        elif o.type in ('MESH', 'EMPTY', 'CURVE', 'FONT', 'SURFACE', 'META'):
            base.update({'type': o.type, 'xform': L.decompose(L.mat4_to_td(mw, 'object'), unit),
                         'dims_m': [round(d * unit, 5) for d in (o.dimensions.x, o.dimensions.z, o.dimensions.y)]})
            data['objects'].append(base)
        else:
            data['warnings'].append('{}: {} not exported'.format(o.name, o.type))
    return res, data


def export(out, name, fmt):
    sc = bpy.context.scene
    us = sc.unit_settings
    unit = L.unit_scale(us.scale_length, us.system)
    os.makedirs(out, exist_ok=True)
    res, data = collect(unit)
    geo = {'usd': None, 'fbx': None, 'up': 'Y', 'forward': '-Z', 'metres_per_unit': 1.0}
    if fmt in ('usd', 'both'):
        f = os.path.join(out, name + '.usdc')
        bpy.ops.wm.usd_export(filepath=f, export_cameras=False, export_lights=False, export_animation=False,
                              export_materials=True, convert_orientation=True,
                              export_global_forward_selection='NEGATIVE_Z', export_global_up_selection='Y',
                              convert_scene_units='METERS', root_prim_path='/root')
        geo['usd'] = os.path.basename(f)
    if fmt in ('fbx', 'both'):
        f = os.path.join(out, name + '.fbx')
        bpy.ops.export_scene.fbx(filepath=f, object_types={'MESH', 'EMPTY', 'OTHER'}, axis_forward='-Z',
                                 axis_up='Y', apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                                 bake_anim=False, use_custom_props=True)
        geo['fbx'] = os.path.basename(f)
    side = {
        'schema': L.SCHEMA,
        'source': {'blend': bpy.data.filepath or None, 'blender': bpy.app.version_string,
                   'exported': datetime.datetime.now().isoformat(timespec='seconds')},
        'units': {'system': us.system, 'length_unit': us.length_unit, 'scale_length': us.scale_length,
                  'metres_per_blender_unit': unit, 'td': 'metres'},
        'axis': {'blender': 'Z up, front view along +Y', 'td': 'Y up', 'point_map': 'td = (x, z, -y)',
                 'rotate_order': 'xyz', 'xform_order': 'srt'},
        'scene': {'name': sc.name, 'resolution': list(res), 'pixel_aspect': [sc.render.pixel_aspect_x,
                  sc.render.pixel_aspect_y], 'fps': sc.render.fps / sc.render.fps_base,
                  'frame_range': [sc.frame_start, sc.frame_end],
                  'active_camera': sc.camera.name if sc.camera else None},
        'geometry': geo, 'world': _world(),
        'objects': data['objects'], 'cameras': data['cameras'], 'lights': data['lights'],
        'warnings': data['warnings'],
    }
    p = os.path.join(out, name + '.json')
    with open(p, 'w', encoding='utf-8') as fh:
        json.dump(side, fh, indent=1, sort_keys=True)
    return p, side


def main():
    a = _args()
    if a.make_test_scene:
        make_test_scene()
        if a.save_blend:
            bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save_blend), compress=True)
    name = a.name or (os.path.splitext(os.path.basename(bpy.data.filepath))[0] if bpy.data.filepath else 'scene')
    p, side = export(os.path.abspath(a.out), name, a.format)
    print('JZB_EXPORT ' + json.dumps({'sidecar': p, 'usd': side['geometry']['usd'], 'fbx': side['geometry']['fbx'],
                                      'cameras': len(side['cameras']), 'lights': len(side['lights']),
                                      'objects': len(side['objects']), 'warnings': side['warnings']}))


if __name__ == '__main__':
    main()
