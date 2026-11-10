"""ac_audio_features: optional 'Features' merge for /project1/lab/AC_audio (TD 2025.31550). Adds, never changes.

Run inside TD through td_exec:
    g = dict(globals()); exec(open('<repo>/builders/ac_audio_features.py').read(), g); g['add']()
add(path) is idempotent. It adds to AC_audio:
  pars  Features (toggle, default off), Featurespath (str, default '../AU_features/out_features') on page Audio;
  ops   feat_sel (Select CHOP of Featurespath, cooks only while Features is on), feat_merge (Merge out_ctl + feat_sel),
        feat_gate (Switch: off -> out_ctl as is, on -> merged), out_ctl_feat (Null) = ctl channels + features.
AC_audio's own outputs (out_ctl, ctl_out, spec_out, its output connectors) are untouched, no Out op is added (an
extra Out op would renumber the COMP's connectors that LK_spectrum_glass uses). Read the merged channels with
op('AC_audio/out_ctl_feat')['bpm'] etc. remove(path) takes it all out again. Pure ASCII.
"""

PATH = '/project1/lab/AC_audio'
OPS = ('feat_sel', 'feat_merge', 'feat_gate', 'out_ctl_feat')


def _mk(c, cls, name):
    o = c.op(name)
    if o is not None and o.OPType != cls.__name__:
        raise RuntimeError('{} exists as {}'.format(o.path, o.OPType))
    return o or c.create(cls, name)


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def add(path=PATH):
    c = op(path)
    base = c.op('out_ctl')
    if base is None:
        raise ValueError('{} has no out_ctl'.format(path))
    pg = None
    for p in c.customPages:
        if p.name == 'Audio':
            pg = p
    pg = pg or c.appendCustomPage('Audio')
    if getattr(c.par, 'Features', None) is None:
        t = pg.appendToggle('Features', label='Merge AU_features (out_ctl_feat)')[0]
        t.default = False
        t.val = False
    if getattr(c.par, 'Featurespath', None) is None:
        s = pg.appendStr('Featurespath', label='Features CHOP')[0]
        s.default = '../AU_features/out_features'
        s.val = s.default
    sel = _mk(c, selectCHOP, 'feat_sel')
    sel.par.chop.expr = "parent().par.Featurespath.eval() if parent().par.Features else ''"
    mg = _mk(c, mergeCHOP, 'feat_merge')
    _wire(base, mg, 0)
    _wire(sel, mg, 1)
    mg.par.duplicate = 'firstname' if 'firstname' in mg.par.duplicate.menuNames else mg.par.duplicate.eval()
    gate = _mk(c, switchCHOP, 'feat_gate')
    _wire(base, gate, 0)
    _wire(mg, gate, 1)
    gate.par.index.expr = '1 if parent().par.Features else 0'
    out = _mk(c, nullCHOP, 'out_ctl_feat')
    _wire(gate, out)
    for o in (sel, mg, gate, out):
        o.viewer = True
    out.comment = 'out_ctl + AU_features channels when Features is on (else = out_ctl)'
    return {'comp': c.path, 'added': list(OPS), 'features': bool(c.par.Features.eval())}


def remove(path=PATH):
    c = op(path)
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    gone = []
    for n in OPS[::-1]:
        o = c.op(n)
        if o is not None:
            f(o)
            gone.append(n)
    for n in ('Features', 'Featurespath'):
        p = getattr(c.par, n, None)
        if p is not None:
            p.destroy()
    return gone
