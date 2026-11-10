"""splat_render_rt: TD runtime of /project1/lab/BL_splat_render (copied into the COMP as Text DAT `splat_rt`).

Load (decode + prepare in numpy, cached in this module's globals, never in op storage: T-67), feed the Script CHOP
(splat data) and the Script TOP (cpu draw order), drive the orbit camera, gate re-sorting, write the MAT uniforms,
publish out_info. One reader per frame (T-21). Never reads TOP pixels (T-74). Pure ASCII.
"""
from td import *  # noqa: F401,F403  (T-00f: modules do not see TD globals)
import time

_CACHE = {}      # comp.id -> state dict (arrays + sort state)


def L(comp):
    return comp.op('splat_render_logic').module


def st(comp):
    s = _CACHE.get(comp.id)
    if s is None:
        s = {'prep': None, 'fmt': '', 'order': None, 'err': None, 'load_ms': 0.0, 'sort_ms': 0.0, 'sorts': 0,
             'last_fwd': None, 'last_pos': (0.0, 0.0, 0.0), 'last_sort_frame': -1, 'orbit_off': 0.0,
             'last_t': None, 'fps': 0.0, 'reload_at': None, 'sortnow': False, 'frame': -1, 'key': None,
             'data_changed': False, 'gen': 0}
        _CACHE[comp.id] = s
    return s


def _status(comp, text):
    try:
        if comp.par.Status.eval() != text:
            comp.par.Status.val = text
    except Exception:
        pass


def _load_key(comp):
    p = comp.par
    return (p.File.eval(), p.Format.eval(), int(p.Maxsplats.eval()), int(p.Thinstep.eval()), float(p.Thinrandom.eval()),
            float(p.Opacitycull.eval()), p.Shdegree.eval(), p.Coordfix.eval(), float(p.Pointscale.eval()),
            tuple(float(x) for x in (p.Cropcenterx, p.Cropcentery, p.Cropcenterz)),
            tuple(float(x) for x in (p.Cropsizex, p.Cropsizey, p.Cropsizez)), float(p.Cropradius.eval()))


def load(comp, force=False):
    """Decode + prepare the file (synchronous; nike 270k ~0.2 s on this Mac). Then cook the data CHOP once."""
    s = st(comp)
    key = _load_key(comp)
    if not force and key == s['key'] and s['prep'] is not None:
        return s
    t0 = time.perf_counter()
    try:
        lg = L(comp)
        fmt, raw = lg.load_any(key[0], key[1])
        prep = lg.prepare(raw, fmt, coordfix=key[7], shdegree=int(key[6]), point_scale=key[8], maxsplats=key[2],
                          thinstep=key[3], thinrandom=key[4], opacitycull=key[5], crop_center=key[9],
                          crop_size=key[10], crop_radius=key[11])
        s.update(prep=prep, fmt=fmt, err=None, order=None, key=key, last_fwd=None, data_changed=True)
        s['gen'] += 1
    except Exception as e:  # noqa: BLE001  (status field shows it; T-48 numpy failures land here too)
        s.update(prep=None, err='{}: {}'.format(type(e).__name__, e), key=key)
    s['load_ms'] = (time.perf_counter() - t0) * 1000.0
    _status(comp, L(comp).status_line(s['fmt'], s['prep'], s['load_ms'], s['err']) if s['prep'] is not None
            else 'ERROR: {}'.format(s['err'])[:200])
    if s['prep'] is not None and comp.par.Autoframe.eval():
        frame_camera(comp)
    d = comp.op('splat_data')
    if d is not None:
        d.cook(force=True)
    return s


def frame_camera(comp):
    s = st(comp)
    if s['prep'] is None:
        return
    import math
    b = s['prep']['bounds']
    comp.par.Targetx, comp.par.Targety, comp.par.Targetz = b['center']
    r = max(b['radius'], 1e-3)
    comp.par.Orbitdist = round(1.15 * r / math.tan(math.radians(max(comp.par.Fov.eval(), 1.0)) * 0.5), 4)


# ---------------------------------------------------------------- op callbacks

def data_cook(scriptOp):
    """Script CHOP: one sample per splat, channels splat_render_logic.CHANNELS + SH_CHANNELS (data order)."""
    comp = scriptOp.parent()
    s = st(comp)
    scriptOp.clear()
    if s['prep'] is None:
        scriptOp.numSamples = 1
        for nm in L(comp).CHANNELS + L(comp).SH_CHANNELS:
            scriptOp.appendChan(nm)
        return
    names, M = L(comp).channel_matrix(s['prep'], None, True)
    # copyNumpyArray(M) renames every channel chan1..N (31550), so the CHOP to POP scopes matched nothing:
    # name channels first, then fill each one.
    scriptOp.numSamples = M.shape[1]
    for i, nm in enumerate(names):
        scriptOp.appendChan(nm).copyNumpyArray(M[i])


def order_cook(scriptOp):
    """Script TOP (32-bit float mono, 4096 wide): draw order for the cpu sort mode (identity otherwise)."""
    import numpy as np
    comp = scriptOp.parent()
    s = st(comp)
    n = s['prep']['count'] if s['prep'] is not None else 1
    order = s['order'] if s['order'] is not None and s['order'].size == n else np.arange(n)
    h = max(1, (n + 4095) // 4096)
    buf = np.zeros((h, 4096, 4), np.float32)
    buf.reshape(-1, 4)[:n, 0] = order.astype(np.float32)
    scriptOp.copyNumpyArray(buf)


def info_cook(scriptOp):
    comp = scriptOp.parent()
    s = st(comp)
    scriptOp.clear()
    scriptOp.numSamples = 1
    n = s['prep']['count'] if s['prep'] is not None else 0
    vals = {'splats': n, 'drawn': int(round(n * (1.0 - min(max(comp.par.Dissolve.eval(), 0.0), 1.0)))),
            'sort_ms': s['sort_ms'], 'fps_cook': s['fps'], 'ok': 1 if s['prep'] is not None else 0,
            'sorts': s['sorts'], 'load_ms': s['load_ms']}
    for k, v in vals.items():
        scriptOp.appendChan(k)[0] = v


# ---------------------------------------------------------------- per frame

def render_cam(comp):
    if comp.par.Cammode.eval() == 'external':
        c = comp.par.Camcomp.eval()
        if c is not None and getattr(c, 'isCOMP', False):
            return c
    return comp.op('cam')


def _set(par, v):
    if par.eval() != v:
        par.val = v


def _audio_values(comp):
    a = comp.par.Audiochop.eval()
    out = {}
    if a is None or not getattr(a, 'isCHOP', False):
        return out
    for ch in a.chans():
        out[ch.name] = float(ch.eval())
    return out


def _audio_rows(comp):
    t = comp.op('audiomap')
    rows = []
    if t is None:
        return rows
    for r in range(1, t.numRows):
        try:
            rows.append((t[r, 0].val, t[r, 1].val, float(t[r, 2].val)))
        except Exception:
            pass
    return rows


def frame(comp):
    """Execute DAT onFrameStart. Cheap when nothing changes (no array work)."""
    if not comp.allowCooking:
        return
    s = st(comp)
    f = absTime.frame
    if s['frame'] == f:                       # T-21: once per frame
        return
    s['frame'] = f
    now = time.perf_counter()
    dt = 0.0 if s['last_t'] is None else now - s['last_t']
    s['last_t'] = now
    if dt > 0:
        s['fps'] = 1.0 / dt if s['fps'] == 0 else 0.9 * s['fps'] + 0.1 / dt
    if s['reload_at'] is not None and f >= s['reload_at']:
        s['reload_at'] = None
        load(comp)
    if s['prep'] is None:
        if s['key'] is None:
            load(comp)
        return
    lg = L(comp)
    p = comp.par
    beat = lg.beat_env(absTime.seconds, p.Bpm.eval())
    mods = lg.audio_mods(_audio_rows(comp), _audio_values(comp)) if p.Audiochop.eval() is not None else {}

    # orbit camera (internal)
    if p.Cammode.eval() == 'orbit':
        rate = lg.orbit_rate_deg_s(p.Autorbit.eval(), p.Orbitsync.eval(), p.Bpm.eval(), p.Beatsperrev.eval(),
                                   mods.get('orbit', 0.0))
        s['orbit_off'] = (s['orbit_off'] + rate * min(dt, 0.25)) % 360.0
        c = lg.orbit_camera(p.Orbitaz.eval() + s['orbit_off'], p.Orbitel.eval(), p.Orbitdist.eval(),
                            (p.Targetx.eval(), p.Targety.eval(), p.Targetz.eval()))
        cam = comp.op('cam')
        for nm, v in (('tx', c['pos'][0]), ('ty', c['pos'][1]), ('tz', c['pos'][2]), ('rx', c['rx']), ('ry', c['ry'])):
            _set(getattr(cam.par, nm), round(float(v), 6))

    # sort gate
    rc = render_cam(comp)
    m = rc.worldTransform
    pos = (m[0, 3], m[1, 3], m[2, 3])
    fwd = (-m[0, 2], -m[1, 2], -m[2, 2])
    mode = p.Sortmode.eval()
    radius = s['prep']['bounds']['radius']
    if lg.need_sort(mode, f, s['last_sort_frame'], int(p.Sorteveryn.eval()), fwd, s['last_fwd'], pos,
                    s['last_pos'], float(p.Sortmovedeg.eval()), radius, pulse=s['sortnow'],
                    data_changed=s['data_changed']):
        _sort(comp, s, mode, m, pos, fwd)
    _uniforms(comp, s, lg, beat, mods, rc, pos, fwd, radius)
    if f % 10 == 0:
        i = comp.op('info')
        if i is not None:
            i.cook(force=True)


def _sort(comp, s, mode, m, pos, fwd):
    t0 = time.perf_counter()
    s['sortnow'] = False
    s['data_changed'] = False
    s['last_fwd'], s['last_pos'], s['last_sort_frame'] = fwd, pos, absTime.frame
    s['sorts'] += 1
    if mode == 'cpu':
        s['order'] = L(comp).back_to_front(s['prep']['P'], pos, fwd)
        comp.op('order_tex').cook(force=True)
        s['sort_ms'] = (time.perf_counter() - t0) * 1000.0
    elif mode in ('sortpop', 'frozen'):
        sc = comp.op('sort_cam')
        sc.setTransform(m)
        srt = comp.op('sort')
        s['sort_ms'] = float(getattr(srt, 'gpuCookTime', 0.0) or 0.0) + float(getattr(srt, 'cpuCookTime', 0.0) or 0.0)
    else:
        s['sort_ms'] = 0.0


def _uniforms(comp, s, lg, beat, mods, rc, pos, fwd, radius):
    p = comp.par
    mat = comp.op('splatmat')
    sc, og, ex, na = lg.uniform_mods(p.Scalemult.eval(), p.Opacitygain.eval(), p.Explode.eval(), p.Noiseamp.eval(),
                                     p.Beatpulse.eval(), beat, mods)
    import math
    tx, ty, tz = p.Targetx.eval(), p.Targety.eval(), p.Targetz.eval()
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(pos, (tx, ty, tz))))
    rs = getattr(p, 'Renderscale', None)  # the render size (Renderscale), not Resolution: splat px footprints
    rw, rh = lg.render_size(p.Resolution1.eval(), p.Resolution2.eval(), rs.eval() if rs is not None else 'full')
    vals = {
        'vec0valuex': float(rw), 'vec0valuey': float(rh),
        'vec0valuez': 1.0 if p.Sortmode.eval() == 'cpu' else 0.0, 'vec0valuew': float(s['prep']['count']),
        'vec1valuex': sc, 'vec1valuey': og, 'vec1valuez': p.Alphathreshold.eval(), 'vec1valuew': p.Lowpass.eval(),
        'vec2valuex': p.Pointmix.eval(), 'vec2valuey': p.Pointsize.eval(), 'vec2valuez': p.Brightness.eval(),
        'vec2valuew': p.Gamma.eval(),
        'vec3valuex': p.Dissolve.eval(), 'vec3valuey': p.Dissolveseed.eval(), 'vec3valuez': na,
        'vec3valuew': p.Noisefreq.eval(),
        'vec4valuex': absTime.seconds * p.Noisespeed.eval() % 1000.0, 'vec4valuey': ex, 'vec4valuez': p.Reveal.eval(),
        'vec4valuew': 1.0 if p.Srgbtolinear.eval() else 0.0,
        'vec5valuex': tx, 'vec5valuey': ty, 'vec5valuez': tz, 'vec5valuew': float(int(p.Shdegree.eval())),
        'vec6valuex': max(dist - radius * 1.1, 0.0), 'vec6valuey': dist + radius * 1.1,
    }
    for k, v in vals.items():
        par = getattr(mat.par, k)
        v = round(float(v), 6)
        if par.eval() != v:
            par.val = v


# ---------------------------------------------------------------- par exec

LOAD_PARS = ('File', 'Format', 'Maxsplats', 'Thinstep', 'Thinrandom', 'Opacitycull', 'Shdegree', 'Coordfix',
             'Pointscale', 'Cropcenterx', 'Cropcentery', 'Cropcenterz', 'Cropsizex', 'Cropsizey', 'Cropsizez',
             'Cropradius')
RESET_PAGES = ('Camera', 'Splat', 'Sort', 'Look')


def _slot(o, kind, name):
    """Index of the vec block named `name`, else the first free one, else appended (other adapters' blocks kept)."""
    seq = getattr(o.seq, kind)
    for k in range(int(seq.numBlocks)):
        if getattr(o.par, '%s%dname' % (kind, k)).eval() == name:
            return k
    for k in range(int(seq.numBlocks)):
        p = getattr(o.par, '%s%dname' % (kind, k))
        if not p.eval() and not p.expr:
            return k
    seq.numBlocks = int(seq.numBlocks) + 1
    return int(seq.numBlocks) - 1


def _geo_uniform(m, on, P='parent().par.'):
    """uGeo vec block on the splat MAT only while Geoon (off: the block's name is cleared, so the MAT has no
    unused uniform and other adapters may reuse the slot; found again by name when on)."""
    if not on:
        k = next((i for i in range(int(m.seq.vec.numBlocks)) if getattr(m.par, 'vec%dname' % i).eval() == 'uGeo'),
                 None)
        if k is not None:
            getattr(m.par, 'vec%dname' % k).val = ''
            for ax in 'xyzw':
                q = getattr(m.par, 'vec%dvalue%s' % (k, ax))
                q.expr = ''
                q.mode = ParMode.CONSTANT
                q.val = 0.0
        return None
    k = _slot(m, 'vec', 'uGeo')
    getattr(m.par, 'vec%dname' % k).val = 'uGeo'
    lm = "parent().op('splat_render_logic').module.menu_index(parent().op('splat_render_logic').module.LIGHTMODES, " \
         "%sGeolightmode.eval())" % P
    for ax, e in zip('xyzw', (P + 'Georelight', P + 'Geoambient', lm, P + 'Geodepthbias')):
        q = getattr(m.par, 'vec%dvalue%s' % (k, ax))
        q.expr = e
        q.mode = ParMode.EXPRESSION
    return k


def geo_sync(comp, dat='splat_glsl', adapter='splat_geo_adapter', mat='splatmat', logic='splat_render_logic'):
    """W1-E (docs/builds/px_geo.md): the geo adapter block in front of the splat shader (Geoon) or out of it (off =
    the exact old text), and the MAT's uGeo block added / cleared to match. Returns a warning ('' = fine)."""
    lg = comp.op(logic).module
    sg, ad, m = comp.op(dat), comp.op(adapter), comp.op(mat)
    on = bool(comp.par.Geoon.eval())
    if not on:
        _geo_uniform(m, False)
    t = lg.geo_patch(sg.text, ad.text, on)
    if sg.text != t:
        sg.text = t
    if on:
        _geo_uniform(m, True)
    w = lg.geo_warning(on, comp.par.Sortmode.eval())
    if w:
        _status(comp, w)
    return w


def geo_lights(comp, root='/project1/effectors'):
    """geo_render's `lights`: Geolights resolved (#tag -> Light COMPs under `root`, W1-A kind light) + geo_key
    (Geokey) + geo_env_light (Geoenv)."""
    cands = []
    eff = op(root)
    if eff is not None:
        for o in eff.findChildren(type=lightCOMP, maxDepth=2):
            cands.append((o.path, list(o.tags)))
    s = L(comp).resolve_lights(comp.par.Geolights.eval(), cands).split()
    if comp.par.Geokey.eval() and comp.op('geo_key') is not None:
        s.append(comp.op('geo_key').path)
    if comp.par.Geoenv.eval() and comp.op('geo_env_light') is not None:
        s.append(comp.op('geo_env_light').path)
    return ' '.join(s)


def on_value(comp, par):
    s = st(comp)
    if par.name in L(comp).GEO_PARS:
        geo_sync(comp)
        return
    if par.name in LOAD_PARS:
        s['reload_at'] = absTime.frame + 2       # debounce: knob drags reload once they settle
    elif par.name == 'Sortmode':
        s['sortnow'] = True


def on_pulse(comp, par):
    s = st(comp)
    if par.name == 'Reload':
        s['key'] = None
        load(comp, force=True)
    elif par.name == 'Sortnow':
        s['sortnow'] = True
    elif par.name == 'Frame':
        frame_camera(comp)
    elif par.name == 'Reset':
        for pg in comp.customPages:
            if pg.name in RESET_PAGES:
                for pp in pg.pars:
                    if not pp.isPulse and not pp.readOnly and pp.mode == ParMode.CONSTANT:
                        pp.val = pp.default
        s['orbit_off'] = 0.0
        frame_camera(comp)
