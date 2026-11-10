# fx_glitch_checks - live checks for FX_glitch modules (lane D, 27 Oct). Run inside TD through td_exec:
#   K = dict(globals()); exec(open('<repo>/builders/fx_glitch_checks.py').read(), K)
# Rules kept: pixel reads (`read_*`, `parity`, `pass_result`) never run in the exec / run() script that changes a TOP
# or a par (T-74): `solo` / `setp` / `pass_seq` change, later execs read. pass_seq + cost schedule their own reads with
# run(delayFrames) so each read is its own script, frames after the change. No functions in op storage (T-67): only
# numbers / lists / dicts are stored. ASCII only.
import math
import os

REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
KEY = 'fxg_chk'


def _st(c):
    s = c.storage.get(KEY)
    if not isinstance(s, dict):
        s = {}
        c.storage[KEY] = s
    return s




def module_ns(module, rack=None):
    """The module file's namespace. rack 'FX_retro' (or a module listed in fx_retro.MODULES) execs it in the FX_retro
    rack namespace (pages need the logic tables), else as an FX_glitch module."""
    ns = dict(globals())
    ns['HERE'] = REPO + '/builders'
    if rack == 'FX_retro':
        exec(open(REPO + '/builders/fx_retro.py').read(), ns)
        exec(open('%s/builders/fx_retro_%s.py' % (REPO, module)).read(), ns)
        return ns
    exec(open('%s/builders/fx_glitch_%s.py' % (REPO, module)).read(), ns)
    return ns


def logic(name):
    ns = {'__name__': name}
    exec(open('%s/builders/%s.py' % (REPO, name)).read(), ns)
    return ns


def defaults(module, rack=None):
    M = module_ns(module, rack)
    return dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in M['PAGES'] for n, s, d, o in pl
                if s not in ('Pulse', 'TOP', 'CHOP', 'Str', 'DAT', 'COMP', 'RGB'))


def setp(m, vals):
    """Write pars (menus by index) as constants."""
    for k, v in vals.items():
        p = getattr(m.par, k)
        p.mode = ParMode.CONSTANT                                                 # noqa: F821
        if p.isMenu:
            p.menuIndex = int(v)
        else:
            p.val = v


def solo(c, name, pars=None, play=True):
    """Un-park the rack, Input test clip (playing), only slot `name` enabled (others 0, remembered), mix 1, Panic 0;
    the module's pars = page defaults + pars."""
    c.allowCooking = True
    t = c.op('slots')
    st = _st(c)
    if 'enabled0' not in st:
        st['enabled0'] = dict((t[i, 'name'].val, t[i, 'enabled'].val) for i in range(1, t.numRows))
    for i in range(1, t.numRows):
        n = t[i, 'name'].val
        t[i, 'enabled'] = 1 if n == name else 0
        if n == name:
            t[i, 'mix'] = 1
    c.par.Panic = False
    c.par.Input = 'test'
    c.op('test_clip').par.play = bool(play)
    row = next(i for i in range(1, t.numRows) if t[i, 'name'].val == name)
    vals = defaults(t[row, 'module'].val, c.name)
    vals.update(pars or {})
    setp(c.op(name), vals)
    return {'solo': name, 'pars': len(vals)}


def unsolo(c):
    """Slot enabled values back as they were before the first solo; clip paused; module pars untouched."""
    t = c.op('slots')
    st = _st(c)
    for n, e in (st.get('enabled0') or {}).items():
        if t.row(n) is not None:
            t[n, 'enabled'] = e
    st.pop('enabled0', None)
    c.op('test_clip').par.play = False
    return 'unsolo'


def arr(o):
    import numpy as np
    return np.asarray(o.numpyArray(), dtype=np.float64)


def read_stats(c, name):
    """img_src + module out1 basics (T-157 (3): a black paused clip passes everything)."""
    import numpy as np
    a = arr(c.op(name).op('in1'))
    b = arr(c.op(name).op('out1'))
    d = np.abs(a - b)[..., :3].max(-1)
    return {'in_mean': float(a[..., :3].mean()), 'in_std': float(a[..., :3].std()), 'out_mean': float(b[..., :3].mean()),
            'max': float(d.max()), 'changed': float((d > 1.5 / 255).mean())}


def dump(c, name, tag='chk', ops=('in1', 'out1')):
    """Save the module's in1 / out1 (and any other op names) as .npy in output/checks/fx_glitch/ (read only: run it in
    its own exec >= 2 frames after any change). The reference maths runs OUTSIDE TD (parity_files): a numpy reference
    inside a TD exec blocks the TD for minutes (scratch hang, T-181)."""
    import numpy as np
    d = REPO + '/output/checks/fx_glitch'
    os.makedirs(d, exist_ok=True)
    out = {}
    for n in ops:
        o = c.op(name).op(n)
        a = np.asarray(o.numpyArray(), dtype=np.float32)
        f = '%s/%s_%s_%s.npy' % (d, name, tag, n)
        np.save(f, a)
        out[n] = (f, a.shape)
    return out


def parity_files(logic_name, tag, name, pars, t=0.0, ref_kw=None):
    """OUTSIDE TD: compare the dumped out1 with <logic>.reference(in1, pars, t)."""
    import numpy as np
    d = REPO + '/output/checks/fx_glitch'
    a = np.load('%s/%s_%s_in1.npy' % (d, name, tag)).astype(np.float64)
    b = np.load('%s/%s_%s_out1.npy' % (d, name, tag)).astype(np.float64)
    L = logic(logic_name)
    kw = dict(ref_kw or {})
    ref = L['reference'](a, pars, t, **kw) if t is not None else L['reference'](a, pars, **kw)
    r = L['compare'](b, ref)
    r.update(in_mean=float(a[..., :3].mean()), in_std=float(a[..., :3].std()), shape=a.shape,
             changed=float((np.abs(a - b)[..., :3].max(-1) > 1.5 / 255).mean()))
    return r


def parity(c, name, logic_name, pars, t=0.0, extra=None):
    """Small pictures only (in-TD reference); prefer dump + parity_files."""
    import numpy as np
    L = logic(logic_name)
    a = arr(c.op(name).op('in1'))
    b = arr(c.op(name).op('out1'))
    kw = dict(extra or {})
    ref = L['reference'](a, pars, t, **kw) if t is not None else L['reference'](a, pars, **kw)
    r = L['compare'](b, ref)
    r.update(in_mean=float(a[..., :3].mean()), in_std=float(a[..., :3].std()),
             changed=float((np.abs(a - b)[..., :3].max(-1) > 1.5 / 255).mean()))
    return r


PASS_STEPS = ['amount0', 'enabled0', 'mix0', 'panic']


def _pass_set(c, name, k):
    t = c.op('slots')
    m = c.op(name)
    st = _st(c)['pass']
    if k == 0:
        st['amount'] = m.par.Amount.eval()
        m.par.Amount = 0.0
    elif k == 1:
        m.par.Amount = st['amount']
        t[name, 'enabled'] = 0
    elif k == 2:
        t[name, 'enabled'] = 1
        t[name, 'mix'] = 0
    elif k == 3:
        t[name, 'mix'] = 1
        c.par.Panic = True
    else:
        c.par.Panic = False


def _pass_read(c, name, k):
    import numpy as np
    a = arr(c.op('img_src'))
    b = arr(c.op('out1'))
    _st(c)['pass'][PASS_STEPS[k]] = float(np.abs(a - b).max())


def pass_seq(c, name, gap=6):
    """Schedule: set step k -> (gap frames) read img_src vs out1 max diff -> set k+1 ... -> restore. Clip paused first.
    Read the dict with pass_result(c) >= (4 * 2 + 1) * gap frames later."""
    c.op('test_clip').par.play = False
    _st(c)['pass'] = {}
    f = 1
    for k in range(4):
        run("K = dict(globals()); exec(open(%r).read(), K); K['_pass_set'](op(%r), %r, %d)"
            % (REPO + '/builders/fx_glitch_checks.py', c.path, name, k), delayFrames=f)        # noqa: F821
        f += gap
        run("K = dict(globals()); exec(open(%r).read(), K); K['_pass_read'](op(%r), %r, %d)"
            % (REPO + '/builders/fx_glitch_checks.py', c.path, name, k), delayFrames=f)        # noqa: F821
        f += 2
    run("K = dict(globals()); exec(open(%r).read(), K); K['_pass_set'](op(%r), %r, 4)"
        % (REPO + '/builders/fx_glitch_checks.py', c.path, name), delayFrames=f)                # noqa: F821
    return {'frames': f}


def pass_result(c):
    return dict(_st(c).get('pass', {}))


def presets(c, name, slots=None):
    """zkit Recall each module preset (twice, T-157) and read the pars back: {slot: [mismatching pars]}."""
    t = c.op('slots')
    m = c.op(name)
    M = module_ns(t[name, 'module'].val, c.name)
    rt = m.op('controls/zk_rt').module
    out = {}
    for slot, pname, vals in M['PRESETS']:
        if slots and slot not in slots:
            continue
        rt.Recall(slot)
        rt.Recall(slot)
        bad = []
        for k, v in vals.items():
            p = getattr(m.par, k)
            got = p.menuIndex if p.isMenu else p.eval()
            if isinstance(v, float) or isinstance(got, float):
                if abs(float(got) - float(v)) > 1e-4:
                    bad.append((k, got, v))
            elif int(got) != int(v):
                bad.append((k, got, v))
        out[slot] = {'name': pname, 'bad': bad[:6], 'n': len(vals)}
    return out


def cost(c, name, frames=120):
    """Per-frame pull of the module's out1 (rack soloed, clip playing): sum cpu + gpu of the module's TOPs that cooked
    in the newest cookAbsFrame (T-157 (2)), In TOPs excluded. cost_result(c) >= frames + 10 frames later."""
    _st(c)['cost'] = []
    code = ("m = op(%r).op(%r); o = m.op('out1'); o.cook(force=True); ops = [x for x in m.findChildren(depth=1) "
            "if x.family == 'TOP' and x.OPType != 'inTOP']; f = max(x.cookAbsFrame for x in ops); "
            "op(%r).storage[%r]['cost'].append(sum(x.cpuCookTime + getattr(x, 'gpuCookTime', 0) for x in ops "
            "if x.cookAbsFrame == f))") % (c.path, name, c.path, KEY)
    for k in range(frames):
        run(code, delayFrames=k + 1)                                                     # noqa: F821
    return {'frames': frames}


def cost_result(c):
    ms = sorted(_st(c).get('cost', [])[10:])
    if not ms:
        return {'ms': None}
    return {'median_ms': round(ms[len(ms) // 2], 3), 'p90_ms': round(ms[int(len(ms) * 0.9)], 3), 'n': len(ms)}


def fps(c, frames=300):
    """Real project rate: wall time over `frames` frames (absTime and frame counters), cookRate untouched."""
    import time
    _st(c)['fps0'] = (time.time(), absTime.frame)                                         # noqa: F821
    run("import time; s = op(%r).storage[%r]; t0, f0 = s['fps0']; s['fps'] = (absTime.frame - f0) / "
        "max(time.time() - t0, 1e-6)" % (c.path, KEY), delayFrames=frames)               # noqa: F821
    return {'frames': frames}


def fps_result(c):
    return {'fps': round(_st(c).get('fps', 0.0), 2), 'cookRate': project.cookRate}     # noqa: F821
