# gen_sim_ripple - GEN_sim module 'ripple' (FX7a SX-24 interactive wave-equation water; textbook Hugo Elias / lygia
# "simple ripple propagation" step, clean-room; BUILD_PLAN_27OCT lane A). A pond the size of the frame (Res x input):
# drops from Rain (drops/s, audio raises it), hits (Hit pulse or the rising edge of Hitchop / Hitchan, e.g.
# AC_audio/out_ctl kick; random place, centre or Hitu / Hitv) and Inject (the slot input's bright areas push the water:
# feed a person mask / motion edge as the slot input). Looks: refract the slot input (the pond over the video),
# palette by height, shaded. Damping per step (energy x Damp per step), wave speed, edges wrap / reflect / absorb.
# Network: in1 -> state_fb (Feedback of step) -> step (compute, npasses = Steps) -> look (+ in1) -> out_sel -> out1;
# hits + hit_chopexec (Hit -> Hitn + 1), pulses (Reset), pal (shared palette). Shaders builders/glsl/
# gen_sim_ripple_step.glsl + gen_sim_ripple_look.glsl; numpy reference gen_sim_logic.ripple_step / ripple_look;
# LIVE CHECKS docs/builds/gen_sim.md. ASCII only.
MODULE = 'ripple'

PAGES0 = [
    ('Ripple', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Res', 'Float', 0.5, {'min': 0.1, 'max': 1, 'label': 'Sim resolution (x input)'}),
        ('Steps', 'Int', 2, {'min': 0, 'max': 8, 'label': 'Steps / frame'}),
        ('Wavespeed', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Wave speed (1 = max stable)'}),
        ('Damp', 'Float', 0.995, {'min': 0.9, 'max': 1, 'label': 'Damping / step'}),
        ('Edges', 'Menu', 'reflect', {'names': ['wrap', 'reflect', 'absorb'],
                                      'labels': ['Wrap', 'Reflect (closed tank)', 'Absorb (open sea)']}),
        ('Rain', 'Float', 2.0, {'min': 0, 'max': 60, 'label': 'Rain drops / s'}),
        ('Dropamp', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Drop strength'}),
        ('Dropsize', 'Float', 6.0, {'min': 1, 'max': 80, 'label': 'Drop radius (sim px)'}),
        ('Inject', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Inject (input luma pushes)'}),
        ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Inject threshold'}),
        ('Audiochop', 'CHOP', '', {'label': 'Audio CHOP (raises rain)'}),
        ('Audiochan', 'Str', 'low', {'label': 'Audio channel'}),
        ('Audiogain', 'Float', 0.0, {'min': 0, 'max': 60, 'label': 'Audio -> extra drops / s'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (flat water)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Hits', [
        ('Hit', 'Pulse', None, {'label': 'Hit (one drop now)'}),
        ('Hitchop', 'CHOP', '/project1/lab/AC_audio/out_ctl', {'label': 'Hit CHOP (rising edge = a drop)'}),
        ('Hitchan', 'Str', 'kick', {'label': 'Hit channel'}),
        ('Hitamp', 'Float', 4.0, {'min': 0, 'max': 20, 'label': 'Hit strength'}),
        ('Hitsize', 'Float', 18.0, {'min': 1, 'max': 200, 'label': 'Hit radius (sim px)'}),
        ('Hitpos', 'Menu', 'random', {'names': ['random', 'centre', 'fixed'],
                                      'labels': ['Random', 'Centre', 'Fixed (Hitu, Hitv)']}),
        ('Hitu', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Hit u'}),
        ('Hitv', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Hit v'}),
    ]),
    ('Look', [
        ('Look', 'Menu', 'refract', {'names': ['refract', 'height', 'shaded'],
                                     'labels': ['Refract the slot input', 'Palette by height', 'Shaded palette']}),
        ('Refract', 'Float', 40.0, {'min': 0, 'max': 400, 'label': 'Refraction px'}),
        ('Bump', 'Float', 8.0, {'min': 0, 'max': 100, 'label': 'Bump (normal strength)'}),
        ('Contrast', 'Float', 0.6, {'min': 0, 'max': 10, 'label': 'Height contrast'}),
        ('Spec', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Specular'}),
        ('Shine', 'Float', 40.0, {'min': 1, 'max': 400, 'label': 'Specular sharpness'}),
        ('Lightangle', 'Float', 60.0, {'min': -180, 'max': 180, 'label': 'Light angle deg'}),
    ]),
]
PAGES = PAGES0 + [colour_page_pal('ab', 'replace', (0.0, 0.1, 0.3), (1.0, 1.0, 1.0)), palette_page('cyan_magenta'),
                  ('State', [('Resetcount', 'Int', 0, {'min': 0, 'max': 100, 'label': 'Reset count (Reset pulse +1)'}),
                             ('Hitn', 'Int', 0, {'min': 0, 'max': 1000000, 'label': 'Hits so far (Hit +1)'})])]
PANEL_PAGES = ['Ripple', 'Hits', 'Look', 'Colour', 'Palette']
RESEED = ['Seed', 'Edges']

PRESETS = full_presets(PAGES, [
    (1, 'rain on the video', {'Look': 'refract', 'Rain': 2.0}),
    (2, 'kick pond', {'Look': 'shaded', 'Rain': 0.0, 'Hitamp': 6.0, 'Hitsize': 24.0, 'Palette': 'shared',
                      'Palsource': 'cyan_magenta', 'Damp': 0.997, 'Contrast': 1.0}),
    (3, 'storm', {'Look': 'refract', 'Rain': 25.0, 'Dropamp': 0.6, 'Dropsize': 4.0, 'Refract': 60.0, 'Damp': 0.99}),
    (4, 'ink water', {'Look': 'height', 'Rain': 4.0, 'Palette': 'shared', 'Palsource': 'magenta_inv',
                      'Contrast': 1.5, 'Edges': 'wrap', 'Damp': 0.998}),
    (5, 'person wake', {'Look': 'refract', 'Rain': 0.5, 'Inject': 0.3, 'Threshold': 0.5, 'Damp': 0.99}),
])

SIMW = "max(1, int(op('in1').width * parent().par.Res.eval() + 0.5))"
SIMH = "max(1, int(op('in1').height * parent().par.Res.eval() + 0.5))"
LEVEL = ("(lambda c, n: float(c[n]) if c is not None and n and c[n] is not None else 0.0)"
         "(parent().par.Audiochop.eval(), parent().par.Audiochan.eval())")
DROPS = ("(parent().par.Rain.eval() + parent().par.Audiogain.eval() * %s) / (60.0 * max(1, parent().par.Steps.eval()))"
         % LEVEL)


def step_uniforms():
    return [('uSim', [SIMW, SIMH, PI.format('Edges'), EPOCH]),
            ('uWave', ['0.5 * parent().par.Wavespeed.eval() ** 2', P.format('Damp'), P.format('Steps'),
                       'absTime.frame']),
            ('uRain', [DROPS, P.format('Dropamp'), P.format('Dropsize'), P.format('Seed')]),
            ('uHit', [P.format('Hitn'), P.format('Hitamp'), PI.format('Hitpos'), P.format('Hitsize')]),
            ('uHitp', [P.format('Hitu'), P.format('Hitv'), P.format('Threshold'), P.format('Inject')])]


def look_uniforms():
    return [('uRl', [PI.format('Look'), P.format('Refract'), P.format('Bump'), P.format('Contrast')]),
            ('uSp', [P.format('Spec'), P.format('Shine'), 'math.radians(%s)' % P.format('Lightangle'), '0']),
            ('uPalCtl', list(PAL_CTL))] + LOOK_UNIFORMS


def shader_texts():
    return {'step': glsl_text('gen_sim_ripple_step'), 'look': pal_glsl(glsl_text('gen_sim_ripple_look'))}


def build(m, H):
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    fb = H['state'](m, 'state_fb', 'step', SIMW, SIMH)
    T = shader_texts()
    step = H['pas'](m, 'step', T['step'], [fb, in1], SIMW, SIMH, 'rgba32float', step_uniforms(),
                    npasses="max(1, parent().par.Steps.eval())")
    step.comment = 'Water: r height, g previous height, b hits applied, a epoch; npasses = Steps.'
    look = H['pas'](m, 'look', T['look'], [in1, step], IN_W, IN_H, 'useinput', look_uniforms(), filt='linear')
    look.comment = 'Refract the slot input / palette by height / shaded; specular; over the slot input.'
    pal = H['palette'](m, look)
    H['out_sel'](m, look)
    H['pulses'](m, RESEED)
    hits = H['hits'](m)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulses'] + hits},
        {'title': '2 Water', 'role': 'process', 'ops': ['state_fb_blank', 'state_fb', 'step', 'step_compute'],
         'body': 'state_fb <- step: wave equation, npasses = Steps; rain, hits (Hitn), inject.'},
        {'title': '3 Look', 'role': 'process', 'ops': ['look', 'look_compute'] + pal},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
