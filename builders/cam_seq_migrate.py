"""cs_migrate: upgrade a v1 CS_cam_sequencer (Base COMP with cam_edit / cam_out + a `shots` table) IN PLACE to the
v2 Camera COMP (builders/cam_seq.py), keeping the same path, so references to the COMP keep working. TD 2025.31550.

Staged and UI-safe (T-249 / T-252 / T-254): each step is ONE exec, run from outside, a few seconds apart, polling
the reply (and `cs_migrate_status`) before the next:

    ns = dict(globals()); exec(open('<repo>/builders/cam_seq_migrate.py').read(), ns)
    ns['cs_migrate']('/project1/lab/CS_cam_sequencer', 'prepare')   # read old shots / pars / refs, close windows,
                                                                    # panes off, viewer off, park, rename -> *_v1
    ns['cs_migrate'](path, 'build')     # new Camera COMP at the same path (parked), presets from the old shots
    ns['cs_migrate'](path, 'unpark')    # >= 10 s later: cook it
    ns['cs_migrate'](path, 'repoint')   # >= 60 frames later: Camcomp / camera pars that named .../cam_out -> the COMP
    ns['cs_migrate'](path, 'finish')    # optional, later: destroy the parked *_v1 (deferred, nothing shown)

Scans are scoped (T-255): only the old COMP's own children and the ops of its parent (depth 1) are read, by
p.val / p.expr strings, never p.eval(). The plan travels in the parent's storage key 'cs_migrate' (plain data).
"""
import json

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
CARRY = {                                     # v1 par -> v2 par (values copied when both exist)
    'Ease': 'Easing', 'Override': 'Override', 'Splineinterp': 'Splineinterp', 'Splinetension': 'Splinetension',
    'Active': 'Bind', 'Playmode': 'Playmode', 'Loopmode': 'Loopmode', 'Select': 'Select', 'Lag': 'Lag',
    'Clockmode': 'Clockmode', 'Bpm': 'Bpm', 'Seek': 'Seek', 'Beatsperbar': 'Beatsperbar', 'Quant': 'Quant',
    'Defaulthold': 'Defaulthold', 'Tdur': 'Tdur', 'Minhold': 'Minhold', 'Maxhold': 'Maxhold', 'Seed': 'Seed',
    'Gotoblend': 'Gotoblend', 'Gototime': 'Gototime', 'Gotoease': 'Gotoease', 'Shakeprofile': 'Shakeprofile',
    'Shakeamount': 'Shakeamount', 'Shakepos': 'Shakepos', 'Shakerot': 'Shakerot', 'Shakespeed': 'Shakespeed',
    'Shakeseed': 'Shakeseed', 'Shakebeat': 'Shakebeat', 'Shakeperlens': 'Shakeperlens', 'Lookdamp': 'Lookdamp',
    'Frame': 'Frame', 'Frameradius': 'Frameradius', 'Framepad': 'Framepad', 'Roll': 'Roll', 'Fovoffset': 'Fovoffset',
    'Resx': 'Resx', 'Resy': 'Resy', 'Targetop': 'Targetop',
}
REF_PARS = ('Camcomp', 'camera', 'Camera', 'Camop')
FACTORY = ['corner1', 'corner2', 'corner3', 'corner4']    # v1's default 'Four corners' set


def _ns(name):
    ns = dict(globals())
    exec(open('%s/%s' % (HERE, name)).read(), ns)
    return ns


def _plan(pp):
    s = pp.fetch('cs_migrate', None, search=False)
    return dict(s) if isinstance(s, dict) else {}


def _save_plan(pp, plan):
    pp.store('cs_migrate', plan)


def _par_text(p):
    try:
        return p.expr if p.mode == ParMode.EXPRESSION else str(p.val)
    except Exception:
        return ''


def find_refs(pp, path):
    """(op path, par name, mode, text) of pars in the parent's ops (depth 1, children of COMPs not entered) that name
    <path>/cam_out or <path>. Read as strings only (T-255)."""
    out = []
    keys = (path + '/cam_out', path)
    for o in pp.children:
        if o.path == path or o.path.startswith(path + '/'):
            continue
        for n in REF_PARS:
            p = getattr(o.par, n, None)
            if p is None:
                continue
            t = _par_text(p)
            if any(k in t for k in keys) or t.endswith('/cam_out'):
                out.append((o.path, n, 'expr' if p.mode == ParMode.EXPRESSION else 'const', t))
    return out


def _ui_off(c):
    """Windows closed, panes off c, viewer off, not current / selected (T-249 / T-251 / T-252)."""
    for w in c.findChildren(type=windowCOMP):
        try:
            if w.isOpen:
                w.par.winclose.pulse()
        except Exception:
            pass
    for pn in ui.panes:
        try:
            ow = pn.owner
            if ow is not None and (ow.path == c.path or ow.path.startswith(c.path + '/')):
                pn.owner = c.parent()
        except Exception:
            pass
    c.viewer = False
    c.current = False
    c.selected = False


def cs_migrate(path, step='prepare', keep_old=True):
    pp = op(path.rsplit('/', 1)[0])
    name = path.rsplit('/', 1)[1]
    plan = _plan(pp)
    cur = pp.op(name)

    if step == 'prepare':
        if cur is None:
            return {'ok': False, 'error': 'no op at %s' % path}
        if cur.OPType == 'cameraCOMP':
            return {'ok': True, 'note': 'already a v2 Camera COMP', 'next': None}
        shots = cur.op('shots')
        rows = [[x.val for x in shots.row(r)] for r in range(shots.numRows)] if shots is not None else []
        names = [r[0] for r in rows[1:]]
        cam_out = cur.op('cam_out')
        pars = {}
        for a, b in CARRY.items():
            p = getattr(cur.par, a, None)
            if p is not None:
                pars[b] = {'mode': 'expr' if p.mode == ParMode.EXPRESSION else 'const',
                           'expr': p.expr if p.mode == ParMode.EXPRESSION else '',
                           'val': p.val if isinstance(p.val, (int, float, str, bool)) else str(p.val)}
        plan = {'path': path, 'rows': rows, 'factory_only': names == FACTORY, 'pars': pars,
                'rord': cam_out.par.rord.val if cam_out is not None else 'xyz',
                'refs': find_refs(pp, path), 'was_cooking': bool(cur.allowCooking), 'old': name + '_v1'}
        _ui_off(cur)
        cur.allowCooking = False
        cur.name = plan['old']
        _save_plan(pp, plan)
        return {'ok': True, 'shots': len(names), 'shot_names': names[:12], 'factory_only': plan['factory_only'],
                'refs': plan['refs'], 'renamed_to': pp.op(plan['old']).path, 'next': 'build'}

    if not plan:
        return {'ok': False, 'error': 'no migration plan in %s storage: run step prepare first' % pp.path}

    if step == 'build':
        if cur is not None and cur.OPType != 'cameraCOMP':
            return {'ok': False, 'error': '%s exists and is a %s' % (path, cur.OPType)}
        res = _ns('cam_seq.py')['build'](pp.path, name, layout=True)
        c = pp.op(name)
        c.allowCooking = False
        Lg = _ns('cam_seq_logic.py')
        Rg = _ns('cam_rig_logic.py')
        import types
        rig = types.ModuleType('cam_rig_logic')
        rig.__dict__.update(Rg)
        Lg['bind_rig'](rig)
        p = plan['pars'].get('Easing', {})
        ease_default = p.get('val', 'inOutSine') if p.get('mode') == 'const' else 'inOutSine'
        cam, look = Lg['from_old_shots'](plan['rows'], plan.get('rord', 'xyz'), ease_default)
        for tname, pre, cols in (('cam_presets', cam, Lg['CAM_PARS']), ('lookat_presets', look, Lg['LOOK_PARS'])):
            t = c.op(tname)
            t.clear()
            t.appendRows(Lg['preset_rows'](pre, cols))
        for b, d in plan['pars'].items():
            q = getattr(c.par, b, None)
            if q is None or q.readOnly:
                continue
            try:
                if d['mode'] == 'expr' and d['expr']:
                    q.expr = d['expr']
                    q.mode = ParMode.EXPRESSION
                elif b in ('Playmode', 'Loopmode', 'Clockmode', 'Easing', 'Gotoblend', 'Gotoease', 'Shakeprofile'):
                    if d['val'] in q.menuNames:
                        q.val = d['val']
                else:
                    q.val = d['val']
            except Exception:
                pass
        if cam:                                         # start on the shot the old Select showed
            v = cam[min(int(float(plan['pars'].get('Select', {}).get('val', 0) or 0)), len(cam) - 1)]['v']
            for n, x in zip(Lg['CAM_PARS'], v):
                getattr(c.par, n).val = x
        c.par.Select.normMax = max(len(cam), 1)
        plan['built'] = True
        _save_plan(pp, plan)
        return {'ok': True, 'comp': c.path, 'type': c.OPType, 'presets': len(cam), 'parked': not c.allowCooking,
                'build': res, 'next': 'unpark (>= 10 s later)'}

    if cur is None or cur.OPType != 'cameraCOMP':
        return {'ok': False, 'error': 'no v2 Camera COMP at %s: run step build' % path}

    if step == 'unpark':
        cur.allowCooking = True
        return {'ok': True, 'cooking': True, 'next': 'repoint (>= 60 frames later)'}

    if step == 'repoint':
        done = []
        for opath, pname, mode, text in plan.get('refs', []):
            o = op(opath)
            p = getattr(o.par, pname, None) if o is not None else None
            if p is None:
                continue
            old = plan['old']
            new_text = text.replace(path + '/cam_out', path).replace('/' + old + '/cam_out', '/' + name)
            now = _par_text(p)                          # TD may have followed the rename to *_v1/cam_out
            now_fixed = now.replace(pp.path + '/' + old + '/cam_out', path).replace(path + '/cam_out', path)
            target = new_text if now == text else now_fixed
            if mode == 'expr':
                p.expr = target
            else:
                p.val = target
            done.append((opath, pname, now, target))
        errs = [o.path for o in cur.findChildren() if o.errors()]
        plan['repointed'] = done
        _save_plan(pp, plan)
        return {'ok': True, 'repointed': done, 'errors': errs, 'presets': cur.par.Length.eval(),
                'next': 'finish (optional; keep_old leaves %s parked)' % plan['old']}

    if step == 'finish':
        old = pp.op(plan['old'])
        if old is None:
            pp.unstore('cs_migrate')
            return {'ok': True, 'note': 'nothing to remove'}
        if keep_old:
            return {'ok': True, 'kept': old.path, 'note': 'pass keep_old=False to destroy it (deferred, UI off)'}
        _ui_off(old)
        f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
        r = f(old)
        pp.unstore('cs_migrate')
        return {'ok': True, 'destroyed': plan['old'], 'safe_destroy': str(r)[:120]}

    return {'ok': False, 'error': 'unknown step %r' % step}


def cs_migrate_status(path):
    pp = op(path.rsplit('/', 1)[0])
    plan = _plan(pp)
    c = op(path)
    return {'plan': {k: v for k, v in plan.items() if k != 'rows'}, 'rows': len(plan.get('rows', [])) - 1 if plan else 0,
            'comp': c.path if c else None, 'type': c.OPType if c else None,
            'cooking': bool(c.allowCooking) if c else None, 'json': json.dumps(bool(plan))}
