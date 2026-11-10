# Build the PF26 show control framework in the open TD project (user, 16 Oct 2026: "specific controls over each
# comp", "framework only"). Run via td_exec:
#   REBUILD = False; exec(open('<repo>/tools/build_show_panel.py').read(), globals())
# Design: docs/research/H_control_panel.md. Pure ASCII (TD reads it).
#
# /project1/show
#   state     custom pars = single source of truth: Master, Blackout, Look (menu of looks/*), Fade (s), Refreshlooks
#   looks/    one COMP per look; its OWN controls are its custom pars (page "Controls"); it outputs Null TOP "out"
#             at 1080x1920. test_a / test_b are plain test looks for checking the crossfade (delete when real ones exist)
#   mixer     two slots (sel_a, sel_b) -> cross (lagged xf) -> level (Master * (1 - Blackout)) -> null_out
#             (Syphon/NDI Out attaches to null_out later); look_switch (Parameter Execute) loads the new look into the
#             idle slot and fades to it over Fade seconds. Only the looks in the two slots cook.
#   ui        control panel: Parameter COMPs for state and for the live look's own controls; ui_window opens it
#   midi_map  empty mapping table (MIDImix / MPK Mini MK3 rows added later; no rebuild)
import td

ROOT = '/project1/show'
W, H = 1080, 1920
_rebuild = globals().get('REBUILD', False)

_p1 = op('/project1')
if _p1.op('show') is not None:
    if not _rebuild:
        raise RuntimeError('/project1/show exists; set REBUILD = True to replace it')
    _p1.op('show').destroy()

show = _p1.create(baseCOMP, 'show')
show.comment = 'PF26 show control framework (tools/build_show_panel.py). Looks in looks/, controls on each look COMP.'


def mk(parent, cls, name):
    return parent.create(cls, name)


def wire(src, dst, i=0):
    dst.inputConnectors[i].connect(src.outputConnectors[0])
    assert dst.inputs[i] == src, 'wire failed {} -> {}[{}]'.format(src.path, dst.path, i)


def res(top):
    top.par.outputresolution = 'custom'
    top.par.resolutionw, top.par.resolutionh = W, H


# ---------------------------------------------------------------- state
state = mk(show, baseCOMP, 'state')
pg = state.appendCustomPage('Show')
p = pg.appendFloat('Master', label='Master')[0]
p.default = p.val = 1.0
p.normMin, p.normMax, p.clampMin, p.clampMax, p.min, p.max = 0, 1, True, True, 0, 1
pg.appendToggle('Blackout', label='Blackout')
pg.appendMenu('Look', label='Look')
p = pg.appendFloat('Fade', label='Fade (s)')[0]
p.default = p.val = 2.0
p.normMin, p.normMax, p.clampMin, p.min = 0, 10, True, 0
pg.appendPulse('Refreshlooks', label='Refresh look list')

# ---------------------------------------------------------------- looks
looks = mk(show, baseCOMP, 'looks')
looks.comment = 'One COMP per look. Controls = its custom pars (page Controls). Output = Null TOP "out", 1080x1920.'


def new_look(name, comment):
    c = mk(looks, baseCOMP, name)
    c.comment = comment
    return c, c.appendCustomPage('Controls')


# test_a: radial ramp; controls Phase, Period
a, pa = new_look('test_a', 'TEST look (delete when real looks exist): radial ramp.')
for nm, lab, dv, lo, hi in (('Phase', 'Phase', 0.0, 0, 1), ('Period', 'Period', 1.0, 0.1, 4)):
    q = pa.appendFloat(nm, label=lab)[0]
    q.default = q.val = dv
    q.normMin, q.normMax = lo, hi
r = mk(a, rampTOP, 'ramp1')
res(r)
r.par.type = 'radial'
r.par.phase.expr = "parent().par.Phase"
r.par.period.expr = "parent().par.Period"
o = mk(a, nullTOP, 'out')
wire(r, o)

# test_b: noise; controls Speed, Amp
b, pb = new_look('test_b', 'TEST look (delete when real looks exist): moving noise.')
for nm, lab, dv, lo, hi in (('Speed', 'Speed', 0.5, 0, 3), ('Amp', 'Amount', 0.6, 0, 1)):
    q = pb.appendFloat(nm, label=lab)[0]
    q.default = q.val = dv
    q.normMin, q.normMax = lo, hi
n = mk(b, noiseTOP, 'noise1')
res(n)
n.par.tz.expr = "absTime.seconds * parent().par.Speed"
n.par.amp.expr = "parent().par.Amp"
n.par.mono = False
o = mk(b, nullTOP, 'out')
wire(n, o)

LOOK_NAMES = [c.name for c in looks.children if c.isCOMP]
state.par.Look.menuNames = LOOK_NAMES
state.par.Look.menuLabels = LOOK_NAMES
state.par.Look = LOOK_NAMES[0]

# ---------------------------------------------------------------- mixer
mixer = mk(show, baseCOMP, 'mixer')
sel_a = mk(mixer, selectTOP, 'sel_a')
sel_b = mk(mixer, selectTOP, 'sel_b')
sel_a.par.top = ROOT + '/looks/' + LOOK_NAMES[0] + '/out'
sel_b.par.top = ROOT + '/looks/' + LOOK_NAMES[0] + '/out'
xf_t = mk(mixer, constantCHOP, 'xf_target')
xf_t.par.const0name = 'xf'
xf_t.par.const0value = 0
xf = mk(mixer, lagCHOP, 'xf_lag')
xf.par.lagunit = 'seconds'
xf.par.lag1.expr = "op('{}/state').par.Fade".format(ROOT)
xf.par.lag2.expr = "op('{}/state').par.Fade".format(ROOT)
wire(xf_t, xf)
xf_out = mk(mixer, nullCHOP, 'xf_out')
wire(xf, xf_out)
cross = mk(mixer, crossTOP, 'cross')
wire(sel_a, cross, 0)
wire(sel_b, cross, 1)
cross.par.cross.expr = "op('xf_out')['xf']"
lvl = mk(mixer, levelTOP, 'master')
wire(cross, lvl)
lvl.par.brightness1.expr = "op('{0}/state').par.Master * (1 - op('{0}/state').par.Blackout)".format(ROOT)
out = mk(mixer, nullTOP, 'null_out')
wire(lvl, out)
mixer.comment = 'A/B slots -> cross (xf lagged by Fade) -> master level -> null_out (Syphon/NDI Out goes after null_out).'

sw = mk(mixer, parameterexecuteDAT, 'look_switch')
sw.par.op = ROOT + '/state'
sw.par.pars = 'Look Refreshlooks'
sw.par.valuechange = True
sw.par.onpulse = True
sw.text = r'''# Look change: load the new look into the idle slot, fade to it over state.Fade (xf_lag). Refreshlooks rebuilds the menu.
ROOT = '/project1/show'


def _refresh():
    st = op(ROOT + '/state')
    names = [c.name for c in op(ROOT + '/looks').children if c.isCOMP]
    st.par.Look.menuNames = names
    st.par.Look.menuLabels = names


def onValueChange(par, prev):
    if par.name != 'Look':
        return
    path = ROOT + '/looks/' + str(par.eval()) + '/out'
    if op(path) is None:
        return
    tgt = op('xf_target')
    showing_b = tgt.par.const0value.eval() >= 0.5
    live = op('sel_b' if showing_b else 'sel_a')
    if str(live.par.top.eval()) == path:
        return
    if showing_b:
        op('sel_a').par.top = path
        tgt.par.const0value = 0
    else:
        op('sel_b').par.top = path
        tgt.par.const0value = 1
    return


def onPulse(par):
    if par.name == 'Refreshlooks':
        _refresh()
    return
'''
sw.dock = xf_t

# ---------------------------------------------------------------- ui
ui = mk(show, containerCOMP, 'ui')
ui.par.w, ui.par.h = 900, 1000
g = mk(ui, parameterCOMP, 'global_ctrl')
g.par.op = ROOT + '/state'
g.par.builtin = False
g.par.custom = True
g.par.x, g.par.y, g.par.w, g.par.h = 0, 700, 900, 300
lc = mk(ui, parameterCOMP, 'look_ctrl')
lc.par.op.expr = "'{0}/looks/' + op('{0}/state').par.Look.eval()".format(ROOT)
lc.par.builtin = False
lc.par.custom = True
lc.par.x, lc.par.y, lc.par.w, lc.par.h = 0, 0, 900, 690
ui.comment = 'Control panel: global_ctrl = state pars, look_ctrl = the live look COMP own controls. Open via ui_window.'
win = mk(show, windowCOMP, 'ui_window')
win.par.winop = ui.path

# ---------------------------------------------------------------- midi map (filled later)
mm = mk(show, tableDAT, 'midi_map')
mm.clear()
mm.appendRow(['device', 'msg', 'number', 'channel', 'target', 'par', 'min', 'max', 'pickup'])
mm.comment = 'MIDI mapping rows (MIDImix / MPK Mini MK3) go here later; no rebuild needed.'

BUILD_RESULT = {'show': show.path, 'looks': LOOK_NAMES, 'out': out.path}
