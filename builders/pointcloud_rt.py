"""pointcloud_rt: TD runtime of /project1/lab/BL_cloud_morph (copied into the COMP as the Text DAT `pc_rt`).

Loads both clouds (numpy, pointcloud_logic), caches them in this module's globals (never op storage, T-67), feeds the
Script CHOP `cloud_data` (one sample per point), runs the per-frame morph clock (Script CHOP `engine`), writes the
constant MAT uniforms for live depth-TOP sides, and publishes `info`. Loads are debounced and run from the Execute DAT
`frame_exec` (never inside another op's cook). Never reads TOP pixels (T-74): a depth TOP's width/height only. ASCII.
"""
from td import *  # noqa: F401,F403  (T-00f: modules do not see TD globals)
import time

_CACHE = {}      # comp.id -> state
LOAD_PARS = ('Sourcea', 'Filea', 'Gena', 'Depthfilea', 'Colourfilea', 'Deptha', 'Colora', 'Upa', 'Scalea', 'Offseta',
             'Sourceb', 'Fileb', 'Genb', 'Depthfileb', 'Colourfileb', 'Depthb', 'Colorb', 'Upb', 'Scaleb', 'Offsetb',
             'Count', 'Match', 'Slices', 'Seed', 'Staggermode', 'Resample', 'Outlier', 'Fit', 'Depthkind', 'Dfov',
             'Znear', 'Zfar', 'Depthlo', 'Depthhi', 'Depthauto', 'Depthstep')
PULSES = ('Reload', 'Frame', 'Reset')
RESET_LOOK = {'Morph': 0.0, 'Stagger': 0.0, 'Arc': 0.0, 'Noiseamp': 0.0, 'Dof': 0.0, 'Streak': 0.0, 'Tintamount': 0.0,
              'Brightness': 1.0, 'Opacity': 1.0, 'Size': 2.0, 'Sizebydepth': 0.0, 'Autorbit': 0.0}


def L(comp):
    return comp.op('pointcloud_logic').module


def st(comp):
    s = _CACHE.get(comp.id)
    if s is None:
        s = {'a': None, 'b': None, 'pair': None, 'err': None, 'load_ms': 0.0, 'reload_at': None, 'gen': 0,
             'eng': None, 'key': None}
        _CACHE[comp.id] = s
    return s


def _status(comp, text):
    try:
        if comp.par.Status.eval() != text:
            comp.par.Status.val = text
    except Exception:
        pass


def _xyz(comp, name):
    return tuple(float(getattr(comp.par, name + ax).eval()) for ax in 'xyz')


def _aspect(top):
    try:
        if top is not None and top.width > 0 and top.height > 0:      # metadata only, no pixel readback (T-74)
            return float(top.width) / float(top.height)
    except Exception:
        pass
    return 16.0 / 9.0


def _side_spec(comp, k):
    p = comp.par
    g = lambda n: getattr(p, n + k).eval()  # noqa: E731
    dtop = g('Depth')
    ctop = g('Color')
    return {'source': g('Source'), 'file': g('File'), 'gen': g('Gen'), 'depthfile': g('Depthfile'),
            'colourfile': g('Colourfile'), 'up': g('Up'), 'outlier': float(p.Outlier.eval()), 'fit': bool(p.Fit.eval()),
            'scale': float(g('Scale')), 'offset': _xyz(comp, 'Offset' + k), 'kind': p.Depthkind.eval(),
            'fov': float(p.Dfov.eval()), 'znear': float(p.Znear.eval()), 'zfar': float(p.Zfar.eval()),
            'lo': float(p.Depthlo.eval()), 'hi': float(p.Depthhi.eval()), 'depthauto': bool(p.Depthauto.eval()),
            'step': int(p.Depthstep.eval()), 'aspect': _aspect(dtop), 'has_colour_top': ctop is not None,
            'seed': int(p.Seed.eval()) + (0 if k == 'a' else 101)}


def schedule_reload(comp, frames=6):
    st(comp)['reload_at'] = absTime.frame + frames


def load(comp):
    """Synchronous load + match (banana 49k + sphere: ~0.1 s offline arm64; measure under Rosetta). Then cook the data
    CHOP once and write the depth-TOP uniforms."""
    s = st(comp)
    t0 = time.perf_counter()
    p = comp.par
    try:
        lg = L(comp)
        a, b, pair = lg.load_pair(_side_spec(comp, 'a'), _side_spec(comp, 'b'), int(p.Count.eval()), p.Match.eval(),
                                  int(p.Slices.eval()), int(p.Seed.eval()), p.Staggermode.eval(), p.Resample.eval())
        s.update(a=a, b=b, pair=pair, err=None)
        s['gen'] += 1
    except Exception as e:  # noqa: BLE001  (Status shows it; T-48 numpy failures land here too)
        s.update(err='{}: {}'.format(type(e).__name__, e))
    s['load_ms'] = (time.perf_counter() - t0) * 1000.0
    if s['pair'] is not None and s['err'] is None:
        _status(comp, L(comp).status_line(s['pair'], s['a'], s['b'], s['load_ms']))
        write_tex_uniforms(comp)
    else:
        _status(comp, 'ERROR: {}'.format(s['err'])[:200])
    for nm in ('cloud_data', 'info'):
        o = comp.op(nm)
        if o is not None:
            o.cook(force=True)
    return s


def write_tex_uniforms(comp):
    """Constant uniforms (depth-TOP sides) straight into the MAT's vec pars (no per-frame expressions)."""
    s = st(comp)
    mat = comp.op('pcmat')
    if mat is None or s['a'] is None:
        return
    ta, tb = s['a']['tex'], s['b']['tex']
    vals = {'uTexA': ta['tex'], 'uTexB': tb['tex'], 'uFitA': ta['fit'], 'uOffA': ta['off'], 'uFitB': tb['fit'],
            'uOffB': tb['off'], 'uKind': (ta['kind'], tb['kind'], ta['hascol'], tb['hascol']),
            'uLoHi': (ta['lohi'][0], ta['lohi'][1], tb['lohi'][0], tb['lohi'][1])}
    for i in range(int(mat.seq.vec.numBlocks)):
        nm = getattr(mat.par, 'vec{}name'.format(i)).eval()
        if nm in vals:
            for ax, v in zip('xyzw', vals[nm]):
                par = getattr(mat.par, 'vec{}value{}'.format(i, ax))
                if par.mode != ParMode.CONSTANT:
                    par.mode = ParMode.CONSTANT
                if par.eval() != float(v):
                    par.val = float(v)


def frame_camera(comp):
    s = st(comp)
    if s['pair'] is None:
        return
    import math
    ba, bb = s['pair']['bounds_a'], s['pair']['bounds_b']
    lo = [min(ba['min'][i], bb['min'][i]) for i in range(3)]
    hi = [max(ba['max'][i], bb['max'][i]) for i in range(3)]
    c = [(lo[i] + hi[i]) * 0.5 for i in range(3)]
    r = 0.5 * math.sqrt(sum((hi[i] - lo[i]) ** 2 for i in range(3)))
    comp.par.Targetx, comp.par.Targety, comp.par.Targetz = c
    comp.par.Orbitdist = round(L(comp).frame_distance(r, comp.par.Fov.eval()), 4)


# ---------------------------------------------------------------- op callbacks

def data_cook(scriptOp):
    """Script CHOP: one sample per point, channels pointcloud_logic.CHANNELS (matched A/B order)."""
    comp = scriptOp.parent()
    s = st(comp)
    lg = L(comp)
    scriptOp.clear()
    if s['pair'] is None:
        scriptOp.numSamples = 1
        for nm in lg.CHANNELS:
            scriptOp.appendChan(nm)
        return
    M = s['pair']['M']
    scriptOp.numSamples = M.shape[1]
    for i, nm in enumerate(lg.CHANNELS):      # T-81: per-channel copy keeps names (2D copy renames chan1..)
        scriptOp.appendChan(nm).copyNumpyArray(M[i])


def info_cook(scriptOp):
    comp = scriptOp.parent()
    s = st(comp)
    scriptOp.clear()
    scriptOp.numSamples = 1
    pr = s['pair']
    vals = {'points': pr['n'] if pr else 0, 'count_a': s['a']['n'] if s['a'] else 0,
            'count_b': s['b']['n'] if s['b'] else 0, 'travel': pr['cost'] if pr else 0.0, 'load_ms': s['load_ms'],
            'ok': 1 if (pr is not None and s['err'] is None) else 0, 'gen': s['gen']}
    for k, v in vals.items():
        scriptOp.appendChan(k)[0] = v


def _level(comp):
    ch = comp.par.Audiochop.eval()
    if ch is None or not getattr(ch, 'isCHOP', False):
        return 0.0
    c = ch[comp.par.Audiochan.eval()] if comp.par.Audiochan.eval() else (ch[0] if ch.numChans else None)
    if c is None:
        return 0.0
    v = c.vals
    return float(max(v)) if len(v) else 0.0


def engine_cook(scriptOp):
    """Per frame (the Script CHOP's Frame par = absTime.frame keeps it cooking): morph clock + orbit camera."""
    comp = scriptOp.parent()
    s = st(comp)
    p = comp.par
    q = {'mode': p.Morphmode.eval(), 'morph': float(p.Morph.eval()), 'tempo': p.Tempo.eval(), 'bpm': float(p.Bpm.eval()),
         'project_bpm': float(op('/local/time').par.tempo.eval()), 'beatsperswap': float(p.Beatsperswap.eval()),
         'morphbeats': float(p.Morphbeats.eval()), 'rate': float(p.Rate.eval()), 'audiogain': float(p.Audiogain.eval()),
         'attack': float(p.Attack.eval()), 'release': float(p.Release.eval()), 'autorbit': float(p.Autorbit.eval()),
         'orbitaz': float(p.Orbitaz.eval()), 'orbitel': float(p.Orbitel.eval()), 'orbitdist': float(p.Orbitdist.eval()),
         'target': _xyz(comp, 'Target')}
    s['eng'], o = L(comp).engine_step(s['eng'], absTime.seconds, q, _level(comp))
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for nm in L(comp).ENGINE_CHANNELS:
        scriptOp.appendChan(nm)[0] = float(o[nm])


def frame(comp):
    """Execute DAT onFrameStart: run a pending (debounced) reload outside any cook."""
    s = st(comp)
    if s['pair'] is None and s['err'] is None and s['reload_at'] is None:
        # empty cache = fresh module (DAT recompiled after build, or project reopened): load once (live, 26 Oct)
        s['reload_at'] = absTime.frame + 1
    if s['reload_at'] is not None and absTime.frame >= s['reload_at']:
        s['reload_at'] = None
        load(comp)


def on_value(comp, par):
    if par.name in LOAD_PARS or par.tupletName in LOAD_PARS:
        schedule_reload(comp)


def on_pulse(comp, par):
    n = par.name
    if n == 'Reload':
        schedule_reload(comp, 1)
    elif n == 'Frame':
        frame_camera(comp)
    elif n == 'Reset':
        for k, v in RESET_LOOK.items():
            if getattr(comp.par, k, None) is not None:
                setattr(comp.par, k, v)
        st(comp)['eng'] = None
