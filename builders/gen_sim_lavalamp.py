# gen_sim_lavalamp - GEN_sim module 'lavalamp' (FX7a SX-25 Rayleigh-Taylor / oil mixing; clean-room from the lygia
# description, no lygia code: Prosperity licence; BUILD_PLAN_27OCT lane A). Heavy fluid on top of light fluid falls in
# fingers and rises in plumes (one step = semi-Lagrangian advection + one warm-started Jacobi pressure iteration +
# Boussinesq buoyancy); Heat turns the bottom zone light and the top zone heavy (Heatnoise splits it into plumes), so
# it convects forever like a lava lamp; Relax pulls toward the slot input (a logo or picture melts and re-forms);
# Conserve keeps the total density = the seeded total (Analyze TOP mean -> 1x1 mass book -> every texel shifted).
# Looks: wax (crisp blobs: smoothstep at Edge +- Soft, palette), glossy wax (+ gradient highlight), bath (raw density).
# Network: in1 -> state_fb -> step (npasses = Steps; + in1 + mass_fb) -> avg (Analyze, mean) -> mass (1x1) -> mass_fb;
# look (in1 + step + mass) -> out_sel -> out1; pulses (Reset, reseed), pal (shared palette). Shaders builders/glsl/
# gen_sim_lava_step.glsl, gen_sim_lava_mass.glsl, gen_sim_lava_look.glsl; numpy reference gen_sim_logic lava_step /
# lava_mass; LIVE CHECKS docs/builds/gen_sim.md. ASCII only.
MODULE = 'lavalamp'

PAGES0 = [
    ('Lava', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Res', 'Float', 0.4, {'min': 0.1, 'max': 1, 'label': 'Sim resolution (x input)'}),
        ('Steps', 'Int', 2, {'min': 0, 'max': 8, 'label': 'Steps / frame'}),
        ('Buoyancy', 'Float', 0.03, {'min': 0, 'max': 0.5, 'label': 'Buoyancy'}),
        ('Viscosity', 'Float', 0.002, {'min': 0, 'max': 0.2, 'label': 'Viscosity (velocity loss / step)'}),
        ('Heat', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Heat (0 = pure mixing)'}),
        ('Heatzone', 'Float', 0.06, {'min': 0.005, 'max': 0.4, 'label': 'Heater / cooler zone (x height)'}),
        ('Heatnoise', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Heater noise (plumes)'}),
        ('Seedmode', 'Menu', 'layers', {'names': ['layers', 'blobs', 'input'],
                                        'labels': ['Layers (heavy on top)', 'Heavy blobs', 'Slot input luma']}),
        ('Fill', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Heavy fraction (layers)'}),
        ('Conserve', 'Toggle', True, {'label': 'Conserve total density'}),
        ('Relax', 'Float', 0.0, {'min': 0, 'max': 0.2, 'label': 'Relax toward the slot input'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (re-seed)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Look', [
        ('Look', 'Menu', 'wax', {'names': ['wax', 'glossy', 'bath'],
                                 'labels': ['Wax (crisp blobs)', 'Glossy wax', 'Bath (raw density)']}),
        ('Edge', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Blob edge (density)'}),
        ('Soft', 'Float', 0.08, {'min': 0.001, 'max': 0.5, 'label': 'Edge softness'}),
        ('Glow', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Speed glow (palette shift)'}),
        ('Gloss', 'Float', 0.35, {'min': 0, 'max': 2, 'label': 'Gloss (glossy look)'}),
        ('Lightangle', 'Float', 60.0, {'min': -180, 'max': 180, 'label': 'Light angle deg'}),
    ]),
]
PAGES = PAGES0 + [colour_page_pal('shared', 'replace', (0.05, 0.0, 0.1), (1.0, 0.5, 0.1)), palette_page('fire'),
                  STATE_PAGE]
PANEL_PAGES = ['Lava', 'Look', 'Colour', 'Palette']
RESEED = ['Seedmode', 'Seed', 'Fill']

PRESETS = full_presets(PAGES, [
    (1, 'lava lamp', {'Seedmode': 'blobs', 'Heat': 0.05, 'Look': 'glossy', 'Palsource': 'fire'}),
    (2, 'rt fingers', {'Seedmode': 'layers', 'Heat': 0.0, 'Buoyancy': 0.05, 'Look': 'bath', 'Palsource': 'magenta_inv'}),
    (3, 'neon lamp', {'Seedmode': 'blobs', 'Heat': 0.08, 'Look': 'glossy', 'Palsource': 'cyan_magenta',
                      'Glow': 0.4, 'Palcycle': 0.05}),
    (4, 'logo melt', {'Seedmode': 'input', 'Heat': 0.0, 'Relax': 0.004, 'Buoyancy': 0.02, 'Look': 'wax',
                      'Palsource': 'px_ramp'}),
    (5, 'oil bath', {'Seedmode': 'layers', 'Heat': 0.03, 'Look': 'bath', 'Palette': 'rainbow', 'Viscosity': 0.0}),
])

SIMW = "max(1, int(op('in1').width * parent().par.Res.eval() + 0.5))"
SIMH = "max(1, int(op('in1').height * parent().par.Res.eval() + 0.5))"


def step_uniforms():
    return [('uSim', [SIMW, SIMH, PI.format('Seedmode'), EPOCH]),
            ('uFl', [P.format('Buoyancy'), P.format('Viscosity'), P.format('Heat'), P.format('Heatzone')]),
            ('uSd', [P.format('Fill'), P.format('Seed'), P.format('Relax'), "1 if parent().par.Conserve.eval() else 0"]),
            ('uRun', [P.format('Steps'), 'absTime.frame', P.format('Heatnoise'), 'absTime.seconds'])]


def mass_uniforms():
    return [('uM', [EPOCH, '0', '0', '0'])]


def look_uniforms():
    return [('uLl', [PI.format('Look'), P.format('Edge'), P.format('Soft'), P.format('Glow')]),
            ('uLs', [P.format('Gloss'), 'math.radians(%s)' % P.format('Lightangle'), '0', '0']),
            ('uPalCtl', list(PAL_CTL))] + LOOK_UNIFORMS


def shader_texts():
    return {'step': glsl_text('gen_sim_lava_step'), 'mass': glsl_text('gen_sim_lava_mass'),
            'look': pal_glsl(glsl_text('gen_sim_lava_look'))}


def build(m, H):
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    T = shader_texts()
    fb = H['state'](m, 'state_fb', 'step', SIMW, SIMH)
    mfb = H['state'](m, 'mass_fb', 'mass', '1', '1')
    step = H['pas'](m, 'step', T['step'], [fb, in1, mfb], SIMW, SIMH, 'rgba32float', step_uniforms(),
                    npasses="max(1, parent().par.Steps.eval())", filt='linear')
    step.comment = 'Fluid: xy velocity, z density, w pressure; npasses = Steps; seeds when mass_fb has not seen the epoch.'
    avg = mk(m, analyzeTOP, 'avg')
    avg.inputConnectors[0].connect(step)
    avg.par.op = 'average'
    avg.par.analyzechannel = 'independent'
    avg.par.scope = 'image'
    avg.par.format = 'rgba32float'
    avg.comment = 'Per-channel mean of the state (z = mean density) for the mass book.'
    mass = H['pas'](m, 'mass', T['mass'], [avg, mfb], '1', '1', 'rgba32float', mass_uniforms())
    mass.comment = 'Mass book: x target (seeded) mean, y current mean, a epoch.'
    look = H['pas'](m, 'look', T['look'], [in1, step, mass], IN_W, IN_H, 'useinput', look_uniforms(), filt='linear')
    look.comment = 'Wax / glossy wax / bath; palette; over the slot input. (mass wired so the book cooks every frame.)'
    pal = H['palette'](m, look)
    H['out_sel'](m, look)
    H['pulses'](m, RESEED)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulses']},
        {'title': '2 Fluid', 'role': 'process', 'ops': ['state_fb_blank', 'state_fb', 'step', 'step_compute'],
         'body': 'state_fb <- step: advect, 1 Jacobi pressure, buoyancy, heat, relax, conserve.'},
        {'title': '3 Mass', 'role': 'process', 'ops': ['avg', 'mass', 'mass_compute', 'mass_fb_blank', 'mass_fb'],
         'body': 'avg (mean) -> mass (target, mean, epoch) -> mass_fb -> next frame\'s step.'},
        {'title': '4 Look', 'role': 'process', 'ops': ['look', 'look_compute'] + pal},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
