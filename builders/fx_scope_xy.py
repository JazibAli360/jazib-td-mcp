# fx_scope_xy - FX_scope module 'xy': audio XY oscilloscope (FX2 AV-30, FX5 G19, FX0 row 25). Stereo audio (any
# CHOP, e.g. an Audio Device In / Audio File In you point it at; default = built-in test tones) as X / Y, Catmull-Rom
# oversampled, drawn by the shared beam engine (builders/fx_scope_beam.py): beam dwell (slow beam = bright, energy
# per frame conserved), phosphor persistence + flash, glow, graticule. Template: docs/builds/fx_glitch.md "Module
# template"; rack = builders/fx_scope.py. Audio rule: this module only READS a CHOP; it never opens a device or plays
# sound. ASCII only.
import os

MODULE = 'xy'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
BE = dict(globals())
with open(os.path.join(_HERE, 'fx_scope_beam.py')) as _fh:
    exec(_fh.read(), BE)
LG = BE['LG']
P, MI = BE['P'], BE['MI']

PAGES = [
    ('XY', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Source', 'Menu', 'test', {'names': ['test', 'chop'], 'labels': ['Test tones', 'Audio CHOP'],
                                    'label': 'Source'}),
        ('Audiochop', 'CHOP', '', {'label': 'Audio CHOP (L / R)'}),
        ('Chanx', 'Str', 'chan1', {'label': 'X channel'}),
        ('Chany', 'Str', 'chan2', {'label': 'Y channel'}),
        ('Gainx', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Gain X'}),
        ('Gainy', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Gain Y'}),
        ('Swap', 'Toggle', False, {'label': 'Swap X / Y'}),
        ('Oversample', 'Int', 4, {'min': 1, 'max': 16, 'label': 'Oversample (Catmull-Rom points per sample)'}),
    ]),
    ('Test', [
        ('Testfreq', 'Float', 110.0, {'min': 20, 'max': 2000, 'label': 'Test X Hz'}),
        ('Testratio', 'Float', 1.5, {'min': 0.25, 'max': 8, 'label': 'Test Y / X ratio'}),
        ('Testphase', 'Float', 90.0, {'min': 0, 'max': 360, 'label': 'Test Y phase (deg)'}),
        ('Testamp', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Test amplitude'}),
        ('Testrate', 'Float', 48000.0, {'min': 8000, 'max': 192000, 'label': 'Test sample rate'}),
    ]),
] + BE['BEAM_PAGES']
PANEL_PAGES = ['XY', 'Test'] + BE['BEAM_PANEL']
MENUS = dict((n, o['names']) for _pg, pars in PAGES for n, s, _d, o in pars if s == 'Menu')


def _v(d):
    return dict((k, MENUS[k].index(v) if k in MENUS else v) for k, v in d.items())


PRESETS = [
    (1, 'green scope', _v({'Phosphor': 'p1', 'Persist': 0.08, 'Flash': 0.5, 'Glow': 0.6, 'Graticule': 0.3,
                           'Gratstyle': 'scope', 'Background': 'screen', 'Beamwidth': 1.5, 'Exposure': 1.0})),
    (2, 'oscilloscope music', _v({'Phosphor': 'p31', 'Persist': 0.25, 'Flash': 0.8, 'Glow': 1.0, 'Graticule': 0.0,
                                  'Gratstyle': 'none', 'Background': 'black', 'Beamwidth': 1.2, 'Exposure': 1.5,
                                  'Oversample': 8})),
    (3, 'radar P7', _v({'Phosphor': 'p7', 'Persist': 1.5, 'Afterglow': 0.8, 'Flash': 1.2, 'Glow': 0.8,
                        'Gratstyle': 'polar', 'Graticule': 0.35, 'Background': 'screen'})),
    (4, 'white vector', _v({'Phosphor': 'p4', 'Persist': 0.03, 'Flash': 0.3, 'Glow': 0.7, 'Gratstyle': 'none',
                            'Background': 'add', 'Beamwidth': 2.0})),
    (5, 'amber over picture', _v({'Phosphor': 'p3', 'Persist': 0.15, 'Glow': 0.5, 'Gratstyle': 'cross',
                                  'Graticule': 0.2, 'Background': 'dim', 'Bgdim': 0.5, 'Size': 0.7})),
]


def src_uniforms():
    """uS0 / uS1 (fx_scope_audio.glsl) + uX. Test tones: n = round(rate / cookRate) samples per frame, start phases
    from absTime.frame (logic.test_tone_uniforms), so the tone runs on across frames."""
    f, r, ph = P.format('Testfreq'), P.format('Testratio'), P.format('Testphase')
    rate = 'max(1.0, %s)' % P.format('Testrate')
    return [
        ('uS0', ['1 if (%s == 1 and %s is not None) else 0' % (MI.format('Source'), P.format('Audiochop')),
                 '%s / %s' % (f, rate), '%s * %s / %s' % (f, r, rate), P.format('Testamp')]),
        ('uS1', ['(%s * absTime.frame / project.cookRate) %% 1.0' % f,
                 '(%s * %s * absTime.frame / project.cookRate + %s / 360.0) %% 1.0' % (f, r, ph),
                 'round(%s / project.cookRate)' % rate, P.format('Oversample')]),
        ('uX', [P.format('Gainx'), P.format('Gainy'), '1 if %s else 0' % P.format('Swap'), '0']),
    ]


SOURCE_EXPR = ("(%s.path if (%s == 1 and %s is not None) else 'src_none')"
               % (P.format('Audiochop'), MI.format('Source'), P.format('Audiochop')))


def shader_texts():
    t = BE['engine_texts']()
    t['path'] = BE['path_text']('src_xy', rgb=False, audio=True)
    return t


def build(m, H):
    names = [(k, P.format(par), P.format(par)) for k, par in (('x', 'Chanx'), ('y', 'Chany'))]
    miss = BE['chan_chops'](m, H, names, SOURCE_EXPR)
    stages, m2 = BE['build_engine'](m, H, 'src_xy', False, True, src_uniforms(),
                                    chop_ops=['src_none', 'sel_x', 'sel_y', 'src_xy'])
    m.store('fx_scope_missing', ' '.join(miss + m2))          # plain str (T-67); empty = every par name found
    return stages
