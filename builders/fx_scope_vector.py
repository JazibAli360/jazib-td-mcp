# fx_scope_vector - FX_scope module 'vector': Vectrex / Asteroids / Tempest vector display (FX2 AV-31, FX0 row 58).
# Path source BY REFERENCE, no copy: Source 'chop' reads any x y [r g b] stream CHOP, default LP_laser_path's out1
# (`laser`: its optimised, resampled, corner-dwelled, blanked path); Source 'sop' turns any SOP into the same kind of
# stream with LP_laser_path's own engine (builders/laser_path_logic.py run_engine, exec'd read-only) in the
# `sop_path` Script CHOP (cooks only when the SOP or its pars change). Drawn by the shared beam engine: corner dwell
# samples -> bright vertex blobs, blank samples (rgb 0) -> beam off, overshoot ringing, frame flicker, phosphor,
# cellophane overlay bands (Vectrex / Battlezone). An effect on a parked LP_laser_path shows nothing (T-118 (1)).
# ASCII only.
import os

MODULE = 'vector'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
BE = dict(globals())
with open(os.path.join(_HERE, 'fx_scope_beam.py')) as _fh:
    exec(_fh.read(), BE)
LG = BE['LG']
P, MI = BE['P'], BE['MI']
LP_LOGIC = os.path.join(_HERE, 'laser_path_logic.py')
LP_OUT = '/project1/lab/LP_laser_path/out1'

PAGES = [
    ('Vector', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Source', 'Menu', 'chop', {'names': ['chop', 'sop'],
                                    'labels': ['Path CHOP (default LP_laser_path out1)', 'SOP (LP engine logic)'],
                                    'label': 'Source'}),
        ('Pathchop', 'CHOP', LP_OUT, {'label': 'Path CHOP (x y r g b stream)'}),
        ('Chanx', 'Str', 'x', {'label': 'X channel'}),
        ('Chany', 'Str', 'y', {'label': 'Y channel'}),
        ('Colour', 'Menu', 'stream', {'names': ['stream', 'white'],
                                      'labels': ['From the stream (r g b; 0 = blank)', 'White (no blanking)'],
                                      'label': 'Colour'}),
        ('Chanr', 'Str', 'r', {'label': 'R channel'}),
        ('Chang', 'Str', 'g', {'label': 'G channel'}),
        ('Chanb', 'Str', 'b', {'label': 'B channel'}),
        ('Blank', 'Float', 0.02, {'min': 0, 'max': 0.5, 'label': 'Blank below (max channel)'}),
        ('Gainx', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Gain X'}),
        ('Gainy', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Gain Y'}),
    ]),
    ('Sop', [
        ('Pathsop', 'Str', '', {'label': 'SOP path (Source sop)'}),
        ('Pps', 'Float', 30000.0, {'min': 1000, 'max': 100000, 'label': 'Points per second (dwell timing)'}),
        ('Step', 'Float', 0.02, {'min': 0.002, 'max': 0.2, 'label': 'Beam step (units, constant speed)'}),
        ('Vertexhold', 'Float', 0.15, {'min': 0, 'max': 2, 'label': 'Vertex dwell (ms)'}),
    ]),
    ('Monitor', [
        ('Overshoot', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Overshoot (corner ringing)'}),
        ('Flicker', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Flicker depth'}),
        ('Flickerhz', 'Float', 30.0, {'min': 1, 'max': 60, 'label': 'Flicker Hz (square, frame-locked)'}),
        ('Overlay', 'Toggle', False, {'label': 'Cellophane overlay'}),
        ('Split', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Overlay split (panel height)'}),
        ('Topr', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Top colour R'}),
        ('Topg', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Top colour G'}),
        ('Topb', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Top colour B'}),
        ('Bottomr', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Bottom colour R'}),
        ('Bottomg', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Bottom colour G'}),
        ('Bottomb', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Bottom colour B'}),
    ]),
] + BE['BEAM_PAGES']
PANEL_PAGES = ['Vector', 'Sop', 'Monitor'] + BE['BEAM_PANEL']
MENUS = dict((n, o['names']) for _pg, pars in PAGES for n, s, _d, o in pars if s == 'Menu')


def _v(d):
    return dict((k, MENUS[k].index(v) if k in MENUS else v) for k, v in d.items())


PRESETS = [
    (1, 'Vectrex', _v({'Phosphor': 'p4', 'Persist': 0.04, 'Flash': 0.6, 'Glow': 0.9, 'Beamwidth': 1.4,
                       'Background': 'screen', 'Gratstyle': 'none', 'Overlay': 0, 'Flicker': 0.1, 'Colour': 'white'})),
    (2, 'Asteroids', _v({'Phosphor': 'p4', 'Persist': 0.02, 'Flash': 0.4, 'Glow': 0.5, 'Beamwidth': 1.2,
                         'Background': 'black', 'Gratstyle': 'none', 'Flicker': 0.15, 'Colour': 'white'})),
    (3, 'Battlezone overlay', _v({'Phosphor': 'p4', 'Persist': 0.05, 'Glow': 0.7, 'Background': 'black',
                                  'Gratstyle': 'none', 'Overlay': 1, 'Split': 0.82, 'Colour': 'white'})),
    (4, 'Tempest colour', _v({'Phosphor': 'source', 'Persist': 0.05, 'Flash': 0.5, 'Glow': 1.0, 'Beamwidth': 1.6,
                              'Background': 'black', 'Gratstyle': 'none', 'Colour': 'stream'})),
    (5, 'scope trace', _v({'Phosphor': 'p1', 'Persist': 0.3, 'Overshoot': 0.3, 'Glow': 0.6, 'Gratstyle': 'scope',
                           'Graticule': 0.3, 'Background': 'screen', 'Colour': 'stream'})),
]

SOURCE_EXPR = ("('sop_path' if %s == 1 else (%s.path if %s is not None else 'src_none'))"
               % (MI.format('Source'), P.format('Pathchop'), P.format('Pathchop')))


def _chan(par, sop_name, colour=False):
    """Channel a Select picks: the sop_path names on Source sop; colour channels fall back to X when Colour white
    (any channel that exists; the shader ignores it)."""
    pick = P.format(par)
    if colour:
        pick = '(%s if %s == 0 else %s)' % (P.format(par), MI.format('Colour'), P.format('Chanx'))
    return "('%s' if %s == 1 else %s)" % (sop_name, MI.format('Source'), pick)


def src_uniforms():
    flick = "1.0 - %s * (int(absTime.seconds * %s * 2.0) %% 2)" % (P.format('Flicker'), P.format('Flickerhz'))
    return [
        ('uV0', [P.format('Gainx'), P.format('Gainy'), '1 if %s == 0 else 0' % MI.format('Colour'), P.format('Blank')]),
        ('uV1', [P.format('Overshoot'), flick, '0', '0']),
    ]


def look_over():
    return {'uO': ['1 if %s else 0' % P.format('Overlay'), P.format('Split'), '0', '0'],
            'uO1': [P.format('Topr'), P.format('Topg'), P.format('Topb'), '0'],
            'uO2': [P.format('Bottomr'), P.format('Bottomg'), P.format('Bottomb'), '0']}


SOP_CB = """# sop_path (FX_scope vector, Source sop): SOP prims -> x y r g b stream through LP_laser_path's own engine
# (laser_path_logic.run_engine, read-only exec of %(lp)r): constant-speed resample (Step), vertex dwell (Vertexhold
# ms at Pps), blanked travel between shapes (rgb 0), nearest-neighbour order. No absTime read: cooks only when the
# SOP or a par changes (T-85 (4)).
_L = {}

def _rows(sop):
\trows, sid = [], 0
\tfor pr in sop.prims:
\t\tvs = [v.point for v in pr]
\t\tif not vs:
\t\t\tcontinue
\t\tfor v in vs:
\t\t\ttry:
\t\t\t\tcd = v.Cd
\t\t\t\tc3 = (float(cd[0]), float(cd[1]), float(cd[2]))
\t\t\texcept Exception:
\t\t\t\tc3 = (1.0, 1.0, 1.0)
\t\t\trows.append((float(v.P[0]), float(v.P[1]), c3[0], c3[1], c3[2], sid, -1.0))
\t\tcl = getattr(pr, 'closed', None)
\t\tclosed = bool(cl() if callable(cl) else (cl if cl is not None else True))
\t\tif closed and len(vs) > 2:
\t\t\trows.append(rows[-len(vs)])
\t\tsid += 1
\treturn rows

def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tscriptOp.clear()
\tm = scriptOp.parent()
\tsop = op(m.par.Pathsop.eval()) if m.par.Pathsop.eval() else None
\tif sop is None:
\t\treturn
\tif not _L:
\t\texec(open(%(lp)r).read(), _L)
\trows = _rows(sop)
\tif not rows:
\t\treturn
\th = float(m.par.Vertexhold.eval())
\tp = _L['params'](pps=float(m.par.Pps.eval()), stepsize=max(float(m.par.Step.eval()), 1e-4), minhold=h, maxhold=h,
\t\torder='nearest')
\tout = _L['run_engine'](rows, p)
\tscriptOp.numSamples = len(out['x'])
\tfor nm in ('x', 'y', 'r', 'g', 'b'):
\t\tscriptOp.appendChan(nm).vals = [float(v) for v in out[nm]]
\treturn
"""


def shader_texts():
    t = BE['engine_texts']()
    t['path'] = BE['path_text']('src_vector', rgb=True, audio=False)
    return t


def _sop_path(m, H):
    mk = H['mk']
    cb = mk(m, textDAT, 'sop_path_cb')                           # noqa: F821 (TD global)
    txt = SOP_CB % {'lp': LP_LOGIC}
    if cb.text != txt:
        cb.text = txt
    sc = mk(m, scriptCHOP, 'sop_path')                           # noqa: F821
    stray = m.op('sop_path_callbacks')                           # a new Script CHOP makes its own DAT (T-109 (4))
    if stray is not None:
        H['sd'](stray)
    sc.par.callbacks = cb.name
    sc.comment = 'Source sop: SOP -> laser-style stream (LP engine logic). Cooks on SOP / par change only.'
    return sc


def build(m, H):
    _sop_path(m, H)
    names = [(k, _chan(par, k, k in 'rgb'), P.format(par))
             for k, par in (('x', 'Chanx'), ('y', 'Chany'), ('r', 'Chanr'), ('g', 'Chang'), ('b', 'Chanb'))]
    miss = BE['chan_chops'](m, H, names, SOURCE_EXPR)
    stages, m2 = BE['build_engine'](
        m, H, 'src_vector', True, False, src_uniforms(), look_over(),
        chop_ops=['sop_path_cb', 'sop_path', 'src_none', 'sel_x', 'sel_y', 'sel_r', 'sel_g', 'sel_b', 'src_xy',
                  'src_rgb'])
    m.store('fx_scope_missing', ' '.join(miss + m2))
    return stages
