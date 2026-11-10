# gen_sim_lic - GEN_sim module 'lic': line integral convolution ink (FX5 G02): white noise combed along a vector
# field (curl noise, the input's edges or gradient, a vortex, a Field TOP such as BN_fluid2d's velocity, or an
# angle-snapped "circuit" field), with a moving Hann x cosine kernel so the ink flows (Cabral / Leedom).
# Network: in1 + clock (+ fsel = Field TOP or in1) -> field (Fieldres x input, rgba16float: half the fetch cost, error below the 8-bit filter weights) -> lic (RK2 streamlines,
# Taps per side, over the slot input) -> out_sel (Amount 0 = in1) -> out1. Stateless.
# Shaders builders/glsl/gen_sim_lic_field.glsl + gen_sim_lic.glsl; maths + numpy reference builders/gen_sim_logic.py
# (lic_curl_field, sample_bilinear, lic); LIVE CHECKS docs/builds/gen_sim.md. ASCII only.

MODULE = 'lic'
LG = logic()

PAGES = [
    ('Lic', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Source', 'Menu', 'curl', {'names': LG['LIC_SOURCES'], 'labels': ['Curl noise', 'Input edges',
                                                                          'Input gradient', 'Vortex', 'Field TOP (rg)',
                                                                          'Circuit (snapped curl)']}),
        ('Fieldtop', 'TOP', '', {'label': 'Field TOP (rg velocity)'}),
        ('Scale', 'Float', 260.0, {'min': 10, 'max': 2000, 'label': 'Noise scale px'}),
        ('Octaves', 'Int', 3, {'min': 1, 'max': 6, 'label': 'Octaves'}),
        ('Drift', 'Float', 0.15, {'min': 0, 'max': 2, 'label': 'Field drift'}),
        ('Rotate', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate deg'}),
        ('Blur', 'Float', 3.0, {'min': 1, 'max': 40, 'label': 'Input gradient px'}),
        ('Snap', 'Int', 4, {'min': 1, 'max': 16, 'label': 'Circuit directions'}),
        ('Spiral', 'Float', 20.0, {'min': -90, 'max': 90, 'label': 'Vortex spiral deg'}),
        ('Fieldres', 'Float', 0.25, {'min': 0.0625, 'max': 1, 'label': 'Field res'}),
        ('Taps', 'Int', 20, {'min': 1, 'max': 64, 'label': 'Taps / side'}),
        ('Step', 'Float', 1.0, {'min': 0.25, 'max': 6, 'label': 'Step px (<= Grain: smooth streaks)'}),
        ('Grain', 'Float', 1.5, {'min': 1, 'max': 16, 'label': 'Grain px'}),
        ('Contrast', 'Float', 3.0, {'min': 0, 'max': 10, 'label': 'Contrast'}),
        ('Bright', 'Float', 0.0, {'min': -0.5, 'max': 0.5, 'label': 'Brightness'}),
        ('Flow', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Flow ripple'}),
        ('Ripples', 'Float', 2.0, {'min': 0, 'max': 8, 'label': 'Ripples / streak'}),
        ('Flowspeed', 'Float', 0.5, {'min': -4, 'max': 4, 'label': 'Flow speed'}),
        ('Speed', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Speed (module time)'}),
        ('Colormode', 'Menu', 'value', {'names': LG['LIC_COLOURS'], 'labels': ['Value (palette)', 'Field angle',
                                                                              'Field speed', 'Input x value']}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    colour_page('ab', 'replace', (0.02, 0.02, 0.05), (0.9, 0.85, 0.75)),
]
PANEL_PAGES = ['Lic', 'Colour']

PRESETS = [
    (1, 'ink wash', {'Source': 0, 'Scale': 300.0, 'Octaves': 3, 'Taps': 32, 'Step': 1.0, 'Grain': 1.5,
                     'Contrast': 3.0, 'Flow': 0.6, 'Colormode': 0, 'Palette': 0}),
    (2, 'brushed steel', {'Source': 3, 'Spiral': 0.0, 'Taps': 32, 'Step': 2.0, 'Grain': 2.0, 'Contrast': 2.0,
                          'Flow': 0.0, 'Colormode': 0, 'Palette': 5}),
    (3, 'combed picture', {'Source': 1, 'Blur': 4.0, 'Taps': 16, 'Step': 1.0, 'Grain': 1.0, 'Contrast': 1.5,
                           'Flow': 0.4, 'Colormode': 3}),
    (4, 'circuit', {'Source': 5, 'Snap': 4, 'Scale': 200.0, 'Taps': 20, 'Step': 2.0, 'Grain': 2.0, 'Contrast': 4.0,
                    'Colormode': 1, 'Palette': 3}),
    (5, 'vortex rainbow', {'Source': 3, 'Spiral': 25.0, 'Taps': 24, 'Step': 2.0, 'Grain': 2.0, 'Contrast': 3.0,
                           'Flow': 0.8, 'Colormode': 1, 'Palette': 4}),
    (6, 'fluid ink', {'Source': 4, 'Taps': 24, 'Step': 1.0, 'Grain': 1.5, 'Contrast': 3.0, 'Flow': 0.6,
                      'Colormode': 2, 'Palette': 2}),
]

FW = "max(1, int(op('in1').width * parent().par.Fieldres.eval() + 0.5))"
FH = "max(1, int(op('in1').height * parent().par.Fieldres.eval() + 0.5))"


def uniforms():
    return {
        'field': [('uLf', [PI.format('Source'), P.format('Scale'), P.format('Octaves'), P.format('Seed')]),
                  ('uLf2', ["math.radians(%s)" % P.format('Rotate'), P.format('Blur'), P.format('Snap'),
                            "math.radians(%s)" % P.format('Spiral')]),
                  ('uLf3', [IN_W, IN_H, FW, FH]),
                  ('uLf4', [P.format('Drift'), '0', '0', '0'])],
        'lic': [('uL', [P.format('Taps'), P.format('Step'), P.format('Grain'), P.format('Seed')]),
                ('uL2', [P.format('Contrast'), P.format('Flow'), P.format('Ripples'), PI.format('Colormode')]),
                ('uL3', [P.format('Flowspeed'), P.format('Bright'), '0', '0'])] + LOOK_UNIFORMS,
    }


def shader_texts():
    return {'field': glsl_text('gen_sim_lic_field'), 'fx': glsl_text('gen_sim_lic')}


def build(m, H):
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')
    clk = H['clock'](m)
    fs = mk(m, selectTOP, 'fsel')
    expr(fs.par.top, "parent().par.Fieldtop.eval().path if parent().par.Fieldtop.eval() is not None "
                     "else me.parent().op('in1').path")
    fs.comment = 'Field TOP (Source Field TOP: rg = velocity) or the slot input when none is set.'
    field = H['pas'](m, 'field', H['glsl']('gen_sim_lic_field'), [in1, clk, fs], FW, FH, 'rgba16float', U['field'])
    field.comment = 'Vector field (unit xy, magnitude z) at Fieldres x the input size.'
    fx = H['pas'](m, 'fx', H['glsl']('gen_sim_lic'), [in1, field, clk], IN_W, IN_H, 'useinput', U['lic'],
                  filt='linear')
    fx.comment = 'LIC: RK2 streamlines both ways (Taps x Step px), noise of Grain px, Hann x cosine flow kernel.'
    H['out_sel'](m, fx)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'clock', 'clock_compute', 'fsel']},
        {'title': '2 Field', 'role': 'process', 'ops': ['field', 'field_compute']},
        {'title': '3 LIC', 'role': 'process', 'ops': ['fx', 'fx_compute']},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
