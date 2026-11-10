"""px_looks: Ruben-Fro-like starting looks for /project1/lab/PX_pointfx, stored as PX presets (Presets page).
Runs INSIDE TD via td_exec:
    ns = dict(globals()); exec(open('<repo>/builders/px_looks.py').read(), ns); ns['apply'](op('/project1/lab/PX_pointfx'), 'dissolving_scan')
    ns['store_all'](c)        # applies each look in turn over frames and stores it as a preset (run() chain)
A look = core pars + module stack (with values, effector links, drives) + animated effector objects. Scans: the two
public sample splats in research_src/BL_gaussian_splats_pointclouds/samples (nike.splat, hornedlizard.spz; see their
READMEs for source/licence). Animated effectors use expressions (absTime), so they keep moving after a recall; a preset
stores their current transform only. Look references: docs/research/BR_rubenfro_pointcloud_fx.md (L1-L7). ASCII.
"""
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
SAMPLES = REPO + '/research_src/BL_gaussian_splats_pointclouds/samples/'
NIKE = SAMPLES + 'nike.splat'
LIZARD = SAMPLES + 'hornedlizard.spz'

# night teal / orange grade (L1), shallow DOF (L3), haze; every look starts from this and overrides
NIGHT = {'Tonemap': 'aces', 'Exposure': 0.2, 'Saturation': 1.15, 'Contrast': 1.1, 'Tealorange': 0.55, 'Split': 0.35,
         'Balance': 0.35, 'Haze': 0.06, 'Hazecolr': 0.03, 'Hazecolg': 0.09, 'Hazecolb': 0.12, 'Vignette': 0.35,
         'Grain': 0.025, 'Bloom': 0.7, 'Bloomthr': 0.9, 'Trails': False, 'Chromatic': 0.002,
         'Sprite': 'soft', 'Softness': 0.7, 'Blend': 'add', 'Alpha': 0.85, 'Hdr': 1.0, 'Bright': 1.0, 'Size': 0.006,
         'Attenuation': 1.0, 'Minpx': 0.8, 'Maxpx': 48.0, 'Aperture': 5.0, 'Maxcoc': 24.0, 'Minenergy': 0.05,
         'Bokehbright': 1.4, 'Fog': 0.15, 'Edgegain': 3.0, 'Edgecolr': 1.0, 'Edgecolg': 0.45, 'Edgecolb': 0.12,
         'Disfade': 1.0, 'Dissize': 0.5, 'Disrecover': 0.0, 'Spring': 4.0, 'Damping': 1.5, 'Drag': 0.2, 'Maxspeed': 0.0,
         'Heatdecay': 0.5, 'Speed': 1.0, 'Play': True, 'Quality': 'std', 'Bmode': 'off', 'Morph': 0.0, 'Orbit': 0.0,
         'Camheight': 0.0, 'Fov': 45.0, 'Tempo': 'manual', 'Bpm': 120.0, 'Lfo1rate': 0.07, 'Lfo2rate': 0.5,
         'Aspin': 0.0, 'Arot': 0.0, 'Ascale': 1.0, 'Aoffsetx': 0.0, 'Aoffsety': 0.0, 'Aoffsetz': 0.0, 'Aup': 'y',
         'Acolmode': 'position', 'Stagger': 0.6, 'Staggermode': 'random', 'Arc': 0.4, 'Ease': 'smooth'}

# far sky shell of the lizard splat (8 % of its points at r ~ 200): hidden by two modules (mask by radius + alpha)
CROP = [('mask_attr', {'by': 'radius', 'lo': -1.0, 'hi': 3.2, 'soft': 0.6, 'out': 'm2', 'op': 'set'}, ''),
        ('colour_adjust', {'alphamul': 0.0, 'maskin': 'm2', 'invert': True}, '')]

# expressions for animated effectors (name -> {par: expr}); kinds created if missing
PATHS = {
    'N1': ('null', {'tx': '0.75 * math.sin(absTime.seconds * 0.9)', 'ty': '0.45 * math.cos(absTime.seconds * 0.7)', 'tz': '0.15'}),
    'N2': ('null', {'tx': '0.85 * math.cos(absTime.seconds * 0.5 + 2.0)', 'ty': '0.4 * math.sin(absTime.seconds * 1.1 + 1.0)', 'tz': '0.1'}),
    'N3': ('null', {'tx': '0.55 * math.sin(absTime.seconds * 1.3 + 4.0)', 'ty': '0.5 * math.sin(absTime.seconds * 0.6)', 'tz': '-0.1'}),
    'W1': ('sphere', {'tx': '0.7 * math.sin(absTime.seconds * 0.35)', 'ty': '0.05', 'tz': '0.45 * math.cos(absTime.seconds * 0.27)',
                      'sx': '0.5', 'sy': '0.9', 'sz': '0.5'}),
}

LOOKS = {
    # L6 + L1: the scan frays into drifting particles along a warped front that sweeps back and forth (LFO 1)
    'dissolving_scan': dict(
        core={'Amode': 'file', 'Afile': NIKE, 'Aoffsetx': -0.14, 'Aoffsety': 1.76, 'Aoffsetz': 1.09, 'Ascale': 1.0,
              'Arot': 0.0, 'Camdist': 4.6, 'Camheight': 0.0, 'Orbit': 2.0, 'Focus': 4.6, 'Lfo1rate': 0.06,
              'Tealorange': 0.3, 'Split': 0.2, 'Aperture': 3.0,
              'Size': 0.0055, 'Alpha': 0.8, 'Edgegain': 5.0, 'Disrecover': 0.6, 'Disfade': 0.5, 'Dissize': 0.8, 'Drag': 1.2},
        stack=[('dissolve_gradient', {'axis': 'x', 'range': 3.2, 'soft': 0.22, 'warp': 0.7, 'warpscale': 3.0,
                                      'release': 0.08, 'curl': 0.9, 'up': 0.7, 'drive': 'progress:lfo1*0.5+0.25'}, ''),
               ('curl', {'strength': 0.25, 'scale': 2.0, 'speed': 0.2}, ''),
               ('colour_ramp', {'attr': 'dissolve', 'lo': 0.0, 'hi': 1.0, 'col0r': 1.0, 'col0g': 1.0, 'col0b': 1.0,
                                'col1r': 1.0, 'col1g': 0.6, 'col1b': 0.2, 'col2r': 1.0, 'col2g': 0.25, 'col2b': 0.05,
                                'col3r': 0.3, 'col3g': 0.05, 'col3b': 0.02, 'blend': 'multiply', 'emission': 3.0}, ''),
               ('velocity_streak', {'gain': 3.0, 'maxlen': 40.0, 'colourspeed': 0.8}, '')],
        anim=[]),
    # L5 proximity: three hands (Nulls N1-N3) push holes through a volumetric cloud; hit points glow and streak
    'hand_push_cloud': dict(
        core={'Amode': 'gen', 'Agen': 'ball', 'Agenp': 1.15, 'Acolmode': 'solid', 'Acolourr': 0.3, 'Acolourg': 0.62,
              'Acolourb': 0.85, 'Camdist': 3.6, 'Focus': 3.4, 'Aperture': 6.0, 'Size': 0.0045, 'Alpha': 0.9,
              'Tealorange': 0.35, 'Split': 0.15, 'Spring': 2.5, 'Damping': 1.2, 'Exposure': 0.7, 'Bright': 1.4},
        stack=[('curl', {'mode': 'displace', 'distance': 0.18, 'scale': 1.6, 'speed': 0.15}, ''),
               ('prox_push', {'mode': 'force', 'strength': 12.0, 'radius': 0.38, 'shape': 'gaussian', 'falloff': 1.0,
                              'dir': 'centre', 'publish': 'm0'}, 'N1 N2 N3'),
               ('prox_colour', {'mode': 'ramp', 'colourr': 1.0, 'colourg': 0.55, 'colourb': 0.15, 'colour2r': 1.0,
                                'colour2g': 0.95, 'colour2b': 0.85, 'emission': 6.0, 'radius': 0.45, 'shape': 'smooth',
                                'flicker': 0.3}, 'N1 N2 N3'),
               ('velocity_streak', {'gain': 4.0, 'maxlen': 60.0, 'colourspeed': 1.5}, '')],
        anim=['N1', 'N2', 'N3']),
    # L4 fire walker: a visible sphere effector (W1) walks through the scanned garden and ignites it; embers rise,
    # consumed points float away and the scan heals slowly behind it
    'ember_splat': dict(
        core={'Amode': 'file', 'Afile': LIZARD, 'Ascale': 0.55, 'Camdist': 2.4, 'Camheight': 0.75, 'Fov': 50.0,
              'Focus': 2.4, 'Aperture': 7.0, 'Size': 0.005, 'Disrecover': 0.12, 'Heatdecay': 0.35, 'Trails': True,
              'Trailkeep': 0.75, 'Bloom': 1.1, 'Bloomthr': 0.8, 'Tealorange': 0.45, 'Exposure': 0.0, 'Saturation': 1.35},
        stack=CROP + [('prox_burn', {'radius': 0.35, 'falloff': 1.0, 'shape': 'smooth', 'noiseedge': 0.8, 'noisefreq': 4.0,
                                     'rise': 3.0, 'flamefreq': 5.0, 'flamespeed': 1.5, 'lift': 1.1, 'embers': 1.2,
                                     'consume': 2.6, 'heatscale': 1.0, 'emission': 3.5}, 'W1'),
                      ('wind', {'buoyancy': 0.6, 'gust': 0.6, 'gustfreq': 0.8, 'windx': 0.12}, ''),
                      ('velocity_streak', {'gain': 1.5, 'maxlen': 24.0, 'colourspeed': 0.6}, '')],
        anim=['W1']),
    # morph between two scans (A shoe -> B lizard garden): staggered, arcing through curl; Morph is the knob
    'scan_morph': dict(
        core={'Amode': 'file', 'Afile': NIKE, 'Aoffsetx': -0.14, 'Aoffsety': 1.76, 'Aoffsetz': 1.09, 'Ascale': 1.0,
              'Bmode': 'file', 'Bfile': LIZARD, 'Bscale': 0.55, 'Morph': 0.5, 'Stagger': 1.4, 'Staggermode': 'height',
              'Arc': 1.6, 'Ease': 'cubic', 'Camdist': 3.0, 'Camheight': 0.4, 'Focus': 3.0, 'Orbit': 5.0,
              'Size': 0.005, 'Tealorange': 0.1, 'Split': 0.0, 'Saturation': 1.3, 'Exposure': 0.5, 'Edgegain': 0.0},
        stack=CROP + [('colour_ramp', {'attr': 'height', 'lo': -0.6, 'hi': 0.9, 'col0r': 0.05, 'col0g': 0.35, 'col0b': 0.45,
                                       'col1r': 0.6, 'col1g': 0.8, 'col1b': 0.85, 'col2r': 1.0, 'col2g': 0.7, 'col2b': 0.35,
                                       'col3r': 1.0, 'col3g': 0.35, 'col3b': 0.1, 'blend': 'replace', 'emission': 0.8}, ''),
                      ('jitter', {'amp': 0.004, 'rate': 24.0, 'mode': 'smooth'}, '')],
        anim=[]),
    # L7 lattice collapse: the scan snaps to its sampling grid near the walker, stretched streaks, red monochrome
    'lattice_collapse': dict(
        core={'Amode': 'file', 'Afile': NIKE, 'Aoffsetx': -0.14, 'Aoffsety': 1.76, 'Aoffsetz': 1.09, 'Ascale': 1.1,
              'Camdist': 2.8, 'Camheight': 0.2, 'Focus': 2.8, 'Size': 0.005, 'Tealorange': 0.0, 'Split': 0.0,
              'Saturation': 1.4, 'Bloom': 1.0},
        stack=[('prox_stretch', {'radius': 0.9, 'falloff': 1.5, 'stretch': 14.0, 'thin': 0.7, 'snap': 1.0, 'cell': 0.06,
                                 'tintr': 1.0, 'tintg': 0.08, 'tintb': 0.04, 'tintamt': 1.0, 'noiseedge': 0.5}, 'N1 N2'),
               ('glitch', {'block': 0.25, 'prob': 0.12, 'offset': 0.12, 'hold': 0.18, 'quantize': 0.6, 'qcells': 6.0}, ''),
               ('colour_adjust', {'saturation': 0.25, 'tintr': 1.0, 'tintg': 0.25, 'tintb': 0.2, 'tintamt': 0.8,
                                  'exposure': 0.3}, '')],
        anim=['N1', 'N2']),
}


def _lg(c):
    return c.op('px_logic').module


def _rt(c):
    return c.op('px_rt').module


def animate(c, names):
    rt = _rt(c)
    have = [r['name'] for r in rt.eff_table(c)]
    for nm in names:
        kind, ex = PATHS[nm]
        if nm not in have:
            rt.add_effector(c, kind, nm, {})
        o = c.op('effectors/' + nm)
        for k, e in ex.items():
            p = getattr(o.par, k)
            p.expr = e
            p.mode = ParMode.EXPRESSION


def apply(c, name):
    """Core pars (NIGHT + the look's), stack (one recompile), module values, animated effectors, sim reset."""
    lk = LOOKS[name]
    Lg = _lg(c)
    rt = _rt(c)
    c.allowCooking = True
    animate(c, lk['anim'])
    core = dict(NIGHT)
    core.update(lk['core'])
    reload_needed = False
    for k, v in core.items():
        p = getattr(c.par, k, None)
        if p is None:
            continue
        if p.mode != ParMode.CONSTANT:
            p.mode = ParMode.CONSTANT
        if p.eval() != v:
            p.val = v
            reload_needed = reload_needed or k in ('Afile', 'Bfile', 'Amode', 'Bmode', 'Aup', 'Bup', 'Quality')
    st = []
    vals = {}
    for t, v, effs in lk['stack']:
        st, uid = Lg.add_module(st, t)
        for k, x in Lg.instance_defaults(st[-1]).items():        # defaults first: no values left over from a last look
            if isinstance(x, (tuple, list)):
                for s, xx in zip('xyz' if Lg.param(t, k)['kind'] == 'xyz' else 'rgb', x):
                    vals[Lg.par_name(uid, k + s)] = xx
            else:
                vals[Lg.par_name(uid, k)] = x
        for k, x in v.items():
            vals[Lg.par_name(uid, k)] = x
        vals[Lg.par_name(uid, 'effectors')] = effs
        vals.setdefault(Lg.par_name(uid, 'drive'), '')
    rt.sync_pages(c, st, vals)
    rt.write_stack(c, st)
    rt.sync_pages(c, st, vals)
    if reload_needed:
        rt.load(c)
    rt.S(c)['reset'] = 2
    c.par.Presetname = name
    return {'look': name, 'stack': [(i['uid'], i['type']) for i in st]}


def hold(c, uid, **vals):
    """Capture helper: clear the drive of module uid and set fixed values (e.g. progress=0.45) for a still."""
    setattr(c.par, 'M%ddrive' % uid, '')
    for k, v in vals.items():
        setattr(c.par, 'M%d%s' % (uid, k), v)


def store(c, name):
    _rt(c).store(c, name)
    return name
