# fx_scope_lissajous - FX_scope module 'lissajous': analytic line figures + the audio goniometer (FX2 AV-32, FX5
# G38). Figures (logic.figure_points): lissajous (a:b, phase, drift; Lock = integer ratios, closed), harmonograph (two
# damped pendulums per axis; Pen = the pen draws live over pendulum time), spirograph (hypotrochoid R r d, closes
# after r / gcd(R, r) turns), rose (r = cos(n/d theta)), goniometer (stereo M/S: mono = vertical line, wide =
# horizontal; correlation meter, red when out of phase; test tones when no CHOP). Rainbow colours the path by
# position (Phosphor 'source' shows them). Shared beam engine: builders/fx_scope_beam.py. ASCII only.
import os

MODULE = 'lissajous'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
BE = dict(globals())
with open(os.path.join(_HERE, 'fx_scope_beam.py')) as _fh:
    exec(_fh.read(), BE)
LG = BE['LG']
P, MI = BE['P'], BE['MI']

PAGES = [
    ('Figure', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Figure', 'Menu', 'lissajous', {'names': LG['FIGURES'],
                                         'labels': ['Lissajous', 'Harmonograph', 'Spirograph', 'Rose',
                                                    'Goniometer (audio)'], 'label': 'Figure'}),
        ('Points', 'Int', 4096, {'min': 256, 'max': 16384, 'label': 'Points per frame'}),
        ('Turns', 'Float', 1.0, {'min': 0.1, 'max': 8, 'label': 'Turns (x the closing period)'}),
        ('Phase', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Phase (cycles)'}),
        ('Drift', 'Float', 0.05, {'min': -1, 'max': 1, 'label': 'Drift (cycles / s)'}),
        ('Gain', 'Float', 0.9, {'min': 0, 'max': 2, 'label': 'Size of the figure'}),
        ('Rainbow', 'Toggle', False, {'label': 'Rainbow along the path (Phosphor source)'}),
        ('Hue', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Hue shift'}),
        ('Huespeed', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Hue speed (cycles / s)'}),
    ]),
    ('Ratios', [
        ('Freqa', 'Float', 3.0, {'min': 0.25, 'max': 16, 'label': 'a (X frequency)'}),
        ('Freqb', 'Float', 2.0, {'min': 0.25, 'max': 16, 'label': 'b (Y frequency)'}),
        ('Lock', 'Toggle', True, {'label': 'Lock a, b to integers (closed figure)'}),
        ('Freqc', 'Float', 2.01, {'min': 0.25, 'max': 16, 'label': 'c (2nd X pendulum)'}),
        ('Freqd', 'Float', 3.005, {'min': 0.25, 'max': 16, 'label': 'd (2nd Y pendulum)'}),
        ('Pendmix', 'Float', 0.35, {'min': 0, 'max': 1, 'label': '2nd pendulum mix'}),
        ('Damping', 'Float', 0.02, {'min': 0, 'max': 0.5, 'label': 'Damping (1 / pendulum s)'}),
        ('Length', 'Float', 60.0, {'min': 1, 'max': 600, 'label': 'Harmonograph length (pendulum s)'}),
        ('Pen', 'Toggle', False, {'label': 'Pen draws live (with Persist)'}),
        ('Penrate', 'Float', 4.0, {'min': 0.1, 'max': 60, 'label': 'Pen rate (pendulum s per s)'}),
        ('Penspan', 'Float', 2.0, {'min': 0.05, 'max': 60, 'label': 'Pen span per frame (pendulum s)'}),
    ]),
    ('Spiro', [
        ('Ringr', 'Float', 5.0, {'min': 1, 'max': 24, 'label': 'Spirograph ring R'}),
        ('Wheelr', 'Float', 3.0, {'min': 1, 'max': 24, 'label': 'Spirograph wheel r'}),
        ('Pend', 'Float', 5.0, {'min': 0, 'max': 24, 'label': 'Spirograph pen d'}),
        ('Rosen', 'Float', 5.0, {'min': 1, 'max': 16, 'label': 'Rose n'}),
        ('Rosed', 'Float', 4.0, {'min': 1, 'max': 16, 'label': 'Rose d'}),
    ]),
    ('Audio', [
        ('Audiochop', 'CHOP', '', {'label': 'Audio CHOP (L / R; goniometer)'}),
        ('Chanx', 'Str', 'chan1', {'label': 'Left channel'}),
        ('Chany', 'Str', 'chan2', {'label': 'Right channel'}),
        ('Oversample', 'Int', 2, {'min': 1, 'max': 16, 'label': 'Oversample'}),
        ('Meter', 'Toggle', True, {'label': 'Correlation meter'}),
    ]),
] + BE['BEAM_PAGES']
PANEL_PAGES = ['Figure', 'Ratios', 'Spiro', 'Audio'] + BE['BEAM_PANEL']
MENUS = dict((n, o['names']) for _pg, pars in PAGES for n, s, _d, o in pars if s == 'Menu')


def _v(d):
    return dict((k, MENUS[k].index(v) if k in MENUS else v) for k, v in d.items())


PRESETS = [
    (1, 'knot 3:2', _v({'Figure': 'lissajous', 'Freqa': 3.0, 'Freqb': 2.0, 'Drift': 0.05, 'Phosphor': 'p1',
                        'Persist': 0.1, 'Glow': 0.6, 'Gratstyle': 'scope', 'Background': 'screen'})),
    (2, 'harmonograph pen', _v({'Figure': 'harmonograph', 'Pen': 1, 'Penrate': 4.0, 'Penspan': 0.5,
                                'Damping': 0.015, 'Phosphor': 'p7', 'Persist': 2.5, 'Afterglow': 0.9, 'Glow': 0.7,
                                'Gratstyle': 'none', 'Background': 'black', 'Points': 2048})),
    (3, 'spirograph rainbow', _v({'Figure': 'spirograph', 'Ringr': 7.0, 'Wheelr': 4.0, 'Pend': 6.0,
                                  'Rainbow': 1, 'Huespeed': 0.05, 'Phosphor': 'source', 'Persist': 0.05,
                                  'Glow': 0.8, 'Gratstyle': 'none', 'Background': 'black', 'Points': 8192})),
    (4, 'rose 5/4', _v({'Figure': 'rose', 'Rosen': 5.0, 'Rosed': 4.0, 'Drift': 0.02, 'Phosphor': 'p4',
                        'Persist': 0.1, 'Glow': 0.6, 'Gratstyle': 'polar', 'Background': 'add'})),
    (5, 'goniometer', _v({'Figure': 'goniometer', 'Rotate': 0.0, 'Phosphor': 'p31', 'Persist': 0.12, 'Glow': 0.4,
                          'Gratstyle': 'polar', 'Graticule': 0.35, 'Background': 'screen', 'Meter': 1})),
]

# theta range (rad) of the closed spirograph / rose figures; tests compare them with logic.spiro_period / rose_period
SPIRO_LAMBDA = ("(lambda R, r, t: (2 * math.pi * int(round(r)) / math.gcd(int(round(R)), int(round(r))) * t) "
                "if (abs(R - round(R)) < 1e-9 and abs(r - round(r)) < 1e-9 and int(round(r)) > 0) "
                "else 2 * math.pi * max(r, 1e-6) * t)")
ROSE_LAMBDA = ("(lambda n, d, t: (math.pi * max(int(round(d)), 1) if (int(round(n)) * max(int(round(d)), 1)) % 2 == 1 "
               "else 2 * math.pi * max(int(round(d)), 1)) * t)")
WINDOW_LAMBDA = ("(lambda pen, rate, span, L, now: (lambda tau: (max(0.0, tau - span), tau - max(0.0, tau - span)))"
                 "((now * rate) % L) if pen else (0.0, L))")
GONIO = "%s == 4" % MI.format('Figure')
SOURCE_EXPR = "(%s.path if %s is not None else 'src_none')" % (P.format('Audiochop'), P.format('Audiochop'))


def _win(k):
    return WINDOW_LAMBDA + "(%s, %s, %s, max(%s, 1e-3), absTime.seconds)[%d]" % (
        P.format('Pen'), P.format('Penrate'), P.format('Penspan'), P.format('Length'), k)


def src_uniforms():
    ab = lambda n: "(float(round(%s)) if %s else %s)" % (P.format(n), P.format('Lock'), P.format(n))
    theta = "[0.0, 0.0, %s, %s, 0.0][%s]" % (
        SPIRO_LAMBDA + "(%s, %s, %s)" % (P.format('Ringr'), P.format('Wheelr'), P.format('Turns')),
        ROSE_LAMBDA + "(%s, %s, %s)" % (P.format('Rosen'), P.format('Rosed'), P.format('Turns')), MI.format('Figure'))
    return [
        ('uL0', [MI.format('Figure'), P.format('Points'), P.format('Turns'),
                 '(%s * absTime.seconds) %% 1.0' % P.format('Drift')]),
        ('uL1', [ab('Freqa'), ab('Freqb'), P.format('Phase'), P.format('Damping')]),
        ('uL2', [P.format('Freqc'), P.format('Freqd'), P.format('Pendmix'), _win(0)]),
        ('uL3', [P.format('Ringr'), P.format('Wheelr'), P.format('Pend'), _win(1)]),
        ('uL4', ['1 if %s else 0' % P.format('Rainbow'),
                 '(%s + %s * absTime.seconds) %% 1.0' % (P.format('Hue'), P.format('Huespeed')), P.format('Gain'), theta]),
        ('uL5', ['%s / max(%s, 1.0)' % (P.format('Rosen'), P.format('Rosed')), '0', '0', '0']),
        # goniometer audio: the CHOP when set, else a 440 Hz test pair 30 deg apart (a tilted ellipse)
        ('uS0', ['1 if %s is not None else 0' % P.format('Audiochop'), '440.0 / 48000.0', '440.0 / 48000.0', '0.7']),
        ('uS1', ['(440.0 * absTime.frame / project.cookRate) % 1.0',
                 '(440.0 * absTime.frame / project.cookRate + 30.0 / 360.0) % 1.0', 'round(48000.0 / project.cookRate)',
                 P.format('Oversample')]),
    ]


def look_over():
    return {'uO': ['0', '0', '1 if (%s and %s) else 0' % (P.format('Meter'), GONIO),
                   '(%s) if (%s and %s) else 0.0' % (LG['CORR_EXPR'], P.format('Meter'), GONIO)]}


def shader_texts():
    t = BE['engine_texts']()
    t['path'] = BE['path_text']('src_lissajous', rgb=False, audio=True)
    return t


def build(m, H):
    names = [(k, P.format(par), P.format(par)) for k, par in (('x', 'Chanx'), ('y', 'Chany'))]
    miss = BE['chan_chops'](m, H, names, SOURCE_EXPR)
    stages, m2 = BE['build_engine'](m, H, 'src_lissajous', False, True, src_uniforms(), look_over(),
                                    chop_ops=['src_none', 'sel_x', 'sel_y', 'src_xy'])
    m.store('fx_scope_missing', ' '.join(miss + m2))
    return stages
