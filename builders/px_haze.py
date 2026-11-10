# px_haze - standalone builder for the W1-D haze + bloom passes (doc docs/builds/px_haze.md). Run inside TD (td_exec
# with this file's text, then build('/project1/lab', 'FX_haze')): a COMP that puts volumetric haze, light shafts and
# two-scale tinted bloom over ANY TOP (+ optional depth), lit by TD Light COMPs placed in 3D. PX wave 2 wires the
# same shaders into PX itself (haze before grade; bloom replaces px_glow); this COMP is the harness and the
# "use it on anything" version. Pure logic + references: px_haze_logic.py; palette: palette_map_logic.py (W1-B).
#
# in1 (scene RGBA premultiplied) -> haze_src (Resolution half / quarter) -> haze (compute, px_haze.glsl; in 0 = haze_src,
#   in 1 = in2 depth) -> comp (compute full res, px_haze_comp.glsl; in 0 = in1, in 1 = haze) -> glow_q (1/4 mipmap)
#   + glow_e (1/8 mipmap) -> bloom (compute 1/4, px_bloom.glsl) -> glow_add (Composite add over comp) -> out1.
# Rows: Script CHOPs haze_rows (uH, per frame: lights + camera move), light_rows (uHL), pal_chop (uPal, on palette
# edits); time + frame from TOP expressions (uHt). GLSL TOPs: <= 2 wired inputs each (T-84 / T-88). ASCII only.
import os

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else ''
DEFAULT_DIR = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'

LIGHT_TYPE_MAP = {'point': 'point', 'cone': 'spot', 'spot': 'spot', 'distant': 'directional',
                  'directional': 'directional', 'area': 'area', 'arealight': 'area'}   # TD lighttype -> ours (LIVE CHECK)


def _pages():
    import px_haze_logic as H
    import palette_map_logic as P
    d = H.HAZE_DEFAULTS
    b = H.BLOOM_DEFAULTS
    hz = P.colsrc_pars('Haze', 'source', d['colour'])
    bl = P.colsrc_pars('Bloom', 'solid', (1.0, 1.0, 1.0))
    return [
        ('Haze', [
            ('Hazeamount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = passthrough)'}),
            ('Hazeres', 'Menu', 'quarter', {'names': ['half', 'quarter'], 'labels': ['Half res (~4x cost)', 'Quarter res']}),
            ('Density', 'Float', d['density'], {'min': 0, 'max': 1}),
            ('Floor', 'Float', d['floor'], {'min': -5, 'max': 5, 'label': 'Floor height (y)'}),
            ('Falloff', 'Float', d['falloff'], {'min': 0, 'max': 4, 'label': 'Height falloff'}),
            ('Noise', 'Float', d['noise'], {'min': 0, 'max': 1, 'label': 'Patchiness (fbm)'}),
            ('Noisescale', 'Float', d['noisescale'], {'min': 0.01, 'max': 4}),
            ('Wind', 'XYZ', d['wind'], {'min': -2, 'max': 2, 'label': 'Drift (units/s)'}),
            ('Noisepersample', 'Toggle', False, {'label': 'Noise per sample (detail, slower)'}),
            ('Extinction', 'Float', d['extinction'], {'min': 0, 'max': 1, 'label': 'Extinction (dims the scene)'}),
            ('Ambient', 'Float', d['ambient'], {'min': 0, 'max': 4, 'label': 'Ambient haze'}),
        ] + hz + [
            ('Hazetint', 'RGB', d['tint'], {'label': 'Lit fog tint'}),
            ('Gain', 'Float', d['gain'], {'min': 0, 'max': 20, 'label': 'Lit fog gain'}),
            ('Anisotropy', 'Float', d['g'], {'min': -0.9, 'max': 0.9, 'label': 'Forward scatter (g)'}),
            ('Steps', 'Int', d['steps'], {'min': 1, 'max': 32}),
            ('Softradius', 'Float', d['softradius'], {'min': 0.001, 'max': 1, 'label': 'Light size'}),
            ('Jitter', 'Toggle', False, {}),
            ('Depthmode', 'Menu', 'none', {'names': list(H.DEPTH_MODES),
                                           'labels': ['No depth (alpha)', 'View z', 'NDC 0..1', 'Ray distance']}),
            ('Depthscale', 'Float', 1.0, {'min': 0, 'max': 100}),
            ('Objdist', 'Float', d['objdist'], {'min': 0, 'max': 100, 'label': 'Object distance (no depth)'}),
            ('Maxdist', 'Float', d['maxdist'], {'min': 1, 'max': 500, 'label': 'Max distance (sky)'}),
        ]),
        ('Shafts', [
            ('Shafts', 'Float', d['shafts'], {'min': 0, 'max': 4, 'label': 'Shafts (0 = off)'}),
            ('Decay', 'Float', d['decay'], {'min': 0.5, 'max': 1}),
            ('Length', 'Float', d['length'], {'min': 0, 'max': 1}),
            ('Taps', 'Int', d['taps'], {'min': 1, 'max': 64}),
            ('Threshold', 'Float', d['threshold'], {'min': 0, 'max': 4, 'label': 'Bright pixels emit (0 = off)'}),
            ('Disc', 'Float', d['disc'], {'min': 0.001, 'max': 0.5, 'label': 'Source disc'}),
            ('Occlusion', 'Float', d['occlusion'], {'min': 0, 'max': 1}),
            ('Shaftlod', 'Float', d['shaftlod'], {'min': 0, 'max': 4, 'label': 'Shaft mip (perf)'}),
        ]),
        ('Lights', [
            ('Lights', 'Str', '', {'label': 'Light COMPs (paths / patterns)'}),
            ('Camera', 'Str', '', {'label': 'Camera COMP (empty = manual)'}),
            ('Campos', 'XYZ', (0.0, 1.0, 8.0), {'min': -50, 'max': 50}),
            ('Camtarget', 'XYZ', (0.0, 1.0, 0.0), {'min': -50, 'max': 50}),
            ('Fov', 'Float', 45.0, {'min': 5, 'max': 150, 'label': 'Horizontal FOV'}),
            ('Near', 'Float', 0.1, {'min': 0.001, 'max': 10}),
            ('Far', 'Float', 1000.0, {'min': 10, 'max': 10000}),
        ]),
        ('Bloom', [
            ('Bloom', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Bloom (0 = off)'}),
            ('Bloomthr', 'Float', b['threshold'], {'min': 0, 'max': 8}),
            ('Bloomknee', 'Float', b['knee'], {'min': 0, 'max': 2}),
            ('Bloomwide', 'Float', b['wide'], {'min': 0, 'max': 4}),
            ('Bloomtight', 'Float', 0.6, {'min': 0, 'max': 4}),
            ('Bloomclamp', 'Float', b['clamp'], {'min': 0, 'max': 20, 'label': 'Firefly clamp (0 = off)'}),
        ] + bl + [
            ('Bloomsat', 'Float', b['saturation'], {'min': 0, 'max': 2}),
            ('Ring', 'Float', b['ring'], {'min': 0, 'max': 4, 'label': 'Ring halo'}),
            ('Ringradius', 'Float', b['ringradius'], {'min': 0.01, 'max': 0.5}),
            ('Ringwidth', 'Float', b['ringwidth'], {'min': 0, 'max': 1}),
            ('Ringchroma', 'Float', b['ringchroma'], {'min': 0, 'max': 0.5}),
        ]),
        ('Palette', [
            ('Palsource', 'Menu', 'neon_trio', {'names': [m[0] for m in P.PAL_SOURCES],
                                                'labels': [m[1] for m in P.PAL_SOURCES]}),
            ('Palstops', 'Str', '', {'label': 'Custom stops (hex hex ...)'}),
            ('Palmode', 'Menu', 'gradient', {'names': [m[0] for m in P.PAL_MODES], 'labels': [m[1] for m in P.PAL_MODES]}),
            ('Palinterp', 'Menu', 'oklab', {'names': [m[0] for m in P.PAL_INTERP],
                                            'labels': [m[1] for m in P.PAL_INTERP]}),
            ('Palshift', 'Float', 0.0, {'min': 0, 'max': 1}),
        ]),
    ]


# ------------------------------------------------------------------------------------------- runtime (in the COMP)
# Text DAT 'haze_rt' (module): Script CHOP callbacks. Reads pars, Light COMPs and the camera; no absTime read except
# through the Frame par expression on haze_rows (the clock, cooks once per frame, T-143 (1)).
RT = r'''# haze_rt: rows for FX_haze (px_haze_logic + palette_map_logic in sibling Text DATs)
import math

def _H():
    return op('px_haze_logic').module

def _P():
    return op('palette_map_logic').module

def _rgb(c, n):
    return (float(getattr(c.par, n + 'r')), float(getattr(c.par, n + 'g')), float(getattr(c.par, n + 'b')))

def _xyz(c, n):
    return (float(getattr(c.par, n + 'x')), float(getattr(c.par, n + 'y')), float(getattr(c.par, n + 'z')))

LTYPE = %r

def lights(c):
    out = []
    for o in c.ops(*str(c.par.Lights.eval()).split()) if str(c.par.Lights.eval()).strip() else []:
        if not hasattr(o.par, 'dimmer'):
            continue
        m = o.worldTransform
        rows = [[m[r, k] for k in range(4)] for r in range(4)]
        sx = math.sqrt(rows[0][0] ** 2 + rows[1][0] ** 2 + rows[2][0] ** 2)
        sy = math.sqrt(rows[0][1] ** 2 + rows[1][1] ** 2 + rows[2][1] ** 2)
        lt = str(getattr(o.par, 'lighttype', 'point').eval()) if hasattr(o.par, 'lighttype') else 'point'
        att = bool(o.par.attenuated.eval()) if hasattr(o.par, 'attenuated') else False
        rng = float(o.par.attenuationend.eval()) if (att and hasattr(o.par, 'attenuationend')) else 0.0
        out.append({'type': LTYPE.get(lt, 'point'), 'pos': (rows[0][3], rows[1][3], rows[2][3]),
                    'dir': (-rows[0][2], -rows[1][2], -rows[2][2]),
                    'colour': (float(o.par.cr), float(o.par.cg), float(o.par.cb)), 'intensity': float(o.par.dimmer),
                    'range': rng, 'cone': float(getattr(o.par, 'coneangle', 40.0)),
                    'delta': float(getattr(o.par, 'conedelta', 10.0)), 'size': (sx, sy), 'shaft': 1.0})
        # (no enabled flag: a Light COMP's render flag reads False on 31550 even when it lights a Render TOP; dimmer 0
        # switches a light off)
    return out

def camera(c, w, h):
    H = _H()
    asp = float(w) / max(float(h), 1.0)
    cam = op(str(c.par.Camera.eval())) if str(c.par.Camera.eval()).strip() else None
    if cam is not None and hasattr(cam, 'worldTransform'):
        m = cam.worldTransform
        rows = [[m[r, k] for k in range(4)] for r in range(4)]
        return H.camera_from_world(rows, float(cam.par.fov), asp, 'x', float(cam.par.near), float(cam.par.far))
    fy = math.degrees(2.0 * math.atan(math.tan(math.radians(float(c.par.Fov)) * 0.5) / asp))
    return H.camera_lookat(_xyz(c, 'Campos'), _xyz(c, 'Camtarget'), fy, asp, near=float(c.par.Near),
                           far=float(c.par.Far))

def params(c):
    p = c.par
    return {'colour': _rgb(c, 'Hazecol'), 'density': float(p.Density), 'floor': float(p.Floor),
            'falloff': float(p.Falloff), 'noise': float(p.Noise), 'noisescale': float(p.Noisescale),
            'wind': _xyz(c, 'Wind'), 'extinction': float(p.Extinction), 'tint': _rgb(c, 'Hazetint'),
            'gain': float(p.Gain), 'g': float(p.Anisotropy), 'ambient': float(p.Ambient), 'steps': int(p.Steps),
            'shafts': float(p.Shafts), 'decay': float(p.Decay), 'length': float(p.Length), 'taps': int(p.Taps),
            'threshold': float(p.Threshold), 'disc': float(p.Disc), 'occlusion': float(p.Occlusion),
            'depthmode': str(p.Depthmode), 'depthscale': float(p.Depthscale), 'objdist': float(p.Objdist),
            'maxdist': float(p.Maxdist), 'softradius': float(p.Softradius), 'jitter': 1.0 if p.Jitter else 0.0,
            'noisemode': 'sample' if p.Noisepersample else 'light', 'shaftlod': float(p.Shaftlod)}

def _write(scriptOp, rows):
    import numpy as np
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    a = np.asarray(rows, dtype=np.float32).reshape(-1, 4)
    scriptOp.numSamples = a.shape[0]
    for k, n in enumerate('xyzw'):
        scriptOp.appendChan(n).copyNumpyArray(np.array(a[:, k], dtype=np.float32, copy=True))

def _stops(c):
    P = _P()
    src = str(c.par.Palsource)
    spec = {'source': src}
    if src == 'custom':
        spec['stops'] = ['#' + t.lstrip('#') for t in str(c.par.Palstops).split()] or ['#ffffff']
    return P.palette_stops(spec)

def pal_count(c):
    return min(len(_stops(c)), 16)

def cook(scriptOp, key):
    c = scriptOp.parent()
    H = _H()
    if key == 'pal':
        P = _P()
        P.cook_chop(scriptOp, P.pal_rows(_stops(c)))
        return
    ls = lights(c)
    lrows, n = H.light_rows(ls)
    if key == 'l':
        _write(scriptOp, lrows)
        return
    cam = camera(c, 1.0, 1.0)      # aspect 1: rows carry tan(fovx/2); the shader uses its own output aspect (no TOP
                                   # size read here, so the rows stay event-driven, live b5)
    _write(scriptOp, H.haze_rows(params(c), cam, n))
''' % (LIGHT_TYPE_MAP,)

CB = """# {name}: rows '{key}' (haze_rt.cook)
def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tscriptOp.parent().op('haze_rt').module.cook(scriptOp, '{key}')
"""

PP = 'parent().par.'


def _read(path):
    with open(path) as fh:
        return fh.read()


def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _mk(c, cls, name, viewer=True):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = viewer
    return o


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _text(c, name, text, dock=None):
    d = _mk(c, textDAT, name, viewer=False)
    if d.text != text:
        d.text = text
    if dock is not None:
        d.dock = dock
    return d


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            probe = name + ('x' if style == 'XYZ' else ('r' if style == 'RGB' else ''))
            if getattr(c.par, probe, None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
                p.default = default
                p.val = default
            elif style in ('Float', 'Int'):
                p = (page.appendFloat if style == 'Float' else page.appendInt)(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
                p.default = default
                p.val = default
            elif style in ('Toggle', 'Str'):
                p = (page.appendToggle if style == 'Toggle' else page.appendStr)(name, label=label)[0]
                p.default = default
                p.val = default
            elif style in ('XYZ', 'RGB'):
                ps = page.appendRGB(name, label=label) if style == 'RGB' else page.appendXYZ(name, label=label)
                for p, v in zip(ps, default):
                    p.default = v
                    p.val = v


def _compute(c, name, dat, code, w_expr, h_expr, comment):
    g = _mk(c, glslTOP, name)
    g.par.mode = 'compute'
    _text(c, dat, code, dock=g)
    g.par.computedat = dat
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w_expr)
    _expr(g.par.resolutionh, h_expr)
    g.par.format = 'rgba16float'
    g.par.autodispatchsize = True
    g.par.inputfiltertype = 'linear'
    g.comment = comment
    for dn in ('_info', '_pixel', '_compute'):
        d = c.op(name + dn)
        if d is not None and d.name != dat:
            _sd(d)
    return g


def _vec(g, k, name, vals):
    """Vectors block k = name, values: numbers or expression strings."""
    g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), k + 1)
    getattr(g.par, 'vec%dname' % k).val = name
    for comp, v in zip('xyzw', vals):
        p = getattr(g.par, 'vec%dvalue%s' % (k, comp))
        if isinstance(v, str):
            _expr(p, v)
        else:
            p.val = float(v)


def _array(g, k, name, chop):
    g.seq.array.numBlocks = max(int(g.seq.array.numBlocks), k + 1)
    getattr(g.par, 'array%dname' % k).val = name
    getattr(g.par, 'array%dtype' % k).val = 'vec4'
    getattr(g.par, 'array%dchop' % k).val = chop
    getattr(g.par, 'array%darraytype' % k).val = 'uniformarray'


def _script(c, name, key, comment):
    s = _mk(c, scriptCHOP, name)
    _text(c, name + '_callbacks', CB.format(name=name, key=key), dock=s)
    s.par.callbacks = name + '_callbacks'
    s.comment = comment
    return s


def _cs(prefix):
    """cs vec4 expressions for pxColSrc from the colsrc_pars of <prefix> (menu index, palpos, palspread, keep)."""
    return [PP + prefix + 'colsrc.menuIndex', PP + prefix + 'palpos', PP + prefix + 'palspread', PP + prefix + 'keep']


def build(parent_path='/project1/lab', name='FX_haze', src_dir=None):
    """Create or update the COMP (idempotent). Returns it."""
    d = src_dir or (HERE if HERE and os.path.isdir(os.path.join(HERE, 'glsl')) else DEFAULT_DIR)
    import sys
    if d not in sys.path:
        sys.path.insert(0, d)
    import importlib
    import px_haze_logic as H
    import palette_map_logic
    importlib.reload(H)
    importlib.reload(palette_map_logic)
    parent_ = op(parent_path)
    c = parent_.op(name) or parent_.create(baseCOMP, name)
    c.allowCooking = True
    _pars(c, _pages())
    _text(c, 'px_haze_logic', _read(os.path.join(d, 'px_haze_logic.py')))
    _text(c, 'palette_map_logic', _read(os.path.join(d, 'palette_map_logic.py')))
    _text(c, 'haze_rt', RT)
    i1 = _mk(c, inTOP, 'in1')
    i2 = _mk(c, inTOP, 'in2')
    i2.comment = 'Depth (r). Unwired = 0: Depthmode none uses scene alpha instead.'
    # Event-driven (live b5, 31550): the par / worldTransform reads inside the cooks are dependencies, so the rows
    # recook only when a par, a light or the camera changes (a per-frame clock cost 0.65 + 0.25 ms CPU every frame)
    hr = _script(c, 'haze_rows', 'h', 'uH rows: haze pars + camera (+ light count); recooks on change.')
    lr = _script(c, 'light_rows', 'l', 'uHL rows: Light COMPs (5 rows each); recooks when a light changes.')
    pc = _script(c, 'pal_chop', 'pal', 'uPal: 16 stops r g b pos (W1-B), recooks on palette edits.')
    hs = _mk(c, resolutionTOP, 'haze_src')
    _wire(i1, hs)
    hs.par.outputresolution = 'custom'
    div = "(2 if parent().par.Hazeres == 'half' else 4)"
    _expr(hs.par.resolutionw, "max(1, op('in1').width // %s)" % div)
    _expr(hs.par.resolutionh, "max(1, op('in1').height // %s)" % div)
    hs.par.filtertype = 'mipmap'
    hs.par.format = 'rgba16float'
    hz = _compute(c, 'haze', 'haze_compute', H.shader_text('px_haze.glsl'), "op('haze_src').width",
                  "op('haze_src').height", 'Haze: depth fog + lit fog (lights) + shafts, half res.')
    hz.par.inputfiltertype = 'mipmap'    # shaft taps read a coarser mip (Shaftlod)
    _wire(hs, hz, 0)
    _wire(i2, hz, 1)
    _array(hz, 0, 'uH', 'haze_rows')
    _array(hz, 1, 'uHL', 'light_rows')
    _array(hz, 2, 'uPal', 'pal_chop')
    _vec(hz, 0, 'uHt', ['absTime.seconds', 'absTime.frame % 65536', 0, 0])
    _vec(hz, 1, 'uHazeCs', _cs('Haze'))
    # count = stops in the palette (pal_chop always has 16 samples; the count is the real stop number)
    pal_ctl = ["op('haze_rt').module.pal_count(parent())", PP + 'Palshift', PP + 'Palmode.menuIndex',
               PP + 'Palinterp.menuIndex']
    _vec(hz, 2, 'uPalCtl', pal_ctl)
    cp = _compute(c, 'comp', 'comp_compute', H.shader_text('px_haze_comp.glsl'), "op('in1').width",
                  "op('in1').height", 'Haze over the scene (Amount 0 = exact passthrough).')
    _wire(i1, cp, 0)
    _wire(hz, cp, 1)
    _vec(cp, 0, 'uHc', [PP + 'Hazeamount', 1, 0, 0])
    gq = _mk(c, resolutionTOP, 'glow_q')
    _wire(cp, gq)
    gq.par.outputresolution = 'quarter'
    gq.par.filtertype = 'mipmap'
    gq.par.format = 'rgba16float'
    ge = _mk(c, resolutionTOP, 'glow_e')
    _wire(cp, ge)
    ge.par.outputresolution = 'eighth'
    ge.par.filtertype = 'mipmap'
    ge.par.format = 'rgba16float'
    bl = _compute(c, 'bloom', 'bloom_compute', H.shader_text('px_bloom.glsl'), "op('glow_q').width",
                  "op('glow_q').height", 'Bloom v2: wide (1/8) + tight (1/4), ring halo, palette tint.')
    _wire(ge, bl, 0)
    _wire(gq, bl, 1)
    _vec(bl, 0, 'uB', [PP + 'Bloomthr', PP + 'Bloom', 1.5, PP + 'Bloomknee'])
    _vec(bl, 1, 'uB2', [PP + 'Bloomwide', PP + 'Bloomtight', 1.0, PP + 'Bloomclamp'])
    _vec(bl, 2, 'uBt', [PP + 'Bloomcolr', PP + 'Bloomcolg', PP + 'Bloomcolb', PP + 'Bloomsat'])
    _vec(bl, 3, 'uBr', [PP + 'Ring', PP + 'Ringradius', PP + 'Ringwidth', PP + 'Ringchroma'])
    _vec(bl, 4, 'uGlowCs', _cs('Bloom'))
    _vec(bl, 5, 'uPalCtl', pal_ctl)
    _array(bl, 0, 'uPal', 'pal_chop')
    ad = _mk(c, compositeTOP, 'glow_add')
    _wire(cp, ad, 0)
    _wire(bl, ad, 1)
    ad.par.operand = 'add'
    ad.par.prefit = 'fill'                # bloom (1/4 res) stretched over the picture
    ad.par.outputresolution = 'custom'    # live 31550: 'useinput' gave the BLOOM's 1/4 size (135 x 240), not in1's
    _expr(ad.par.resolutionw, "op('comp').width")
    _expr(ad.par.resolutionh, "op('comp').height")
    ad.par.format = 'rgba16float'
    sw = _mk(c, switchTOP, 'sw_bloom')
    _wire(cp, sw, 0)
    _wire(ad, sw, 1)
    _expr(sw.par.index, '1 if %sBloom > 0 else 0' % PP)
    o1 = _mk(c, outTOP, 'out1')
    _wire(sw, o1)
    return c
