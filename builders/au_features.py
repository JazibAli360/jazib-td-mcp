"""au_features builder: /project1/lab/AU_features (TD 2025.31550). EssentiaTD audio features -> one clean CHOP.

Run inside TD through td_exec:
    g = dict(globals()); exec(open('<repo>/builders/au_features.py').read(), g); g['build']('/project1/lab')
build(parent_path, name, controls=True, analysis=None) is idempotent (ops reused by name). analysis=True/False sets
the Analysison toggle (loads the four EssentiaTD CHOPs by ABSOLUTE PATH the first time, T-99; off = bypass, never
unload, T-106); None keeps the COMP's value (new COMP: off).
Network: in1 (In CHOP) | file (Audio File In, Audiofile) | acaudio (Select of AC_audio/n_mono) -> src_sel -> mono
(Math avg = mono sum) -> n_in -> rhythm / loudness / tonal / spectral (CPlusPlus CHOPs, Essentia v2.0.3, realtime)
-> features (Script CHOP: names, orders, normalises; beat pulse, key index, counters; logic in au_features_logic)
-> out_features (Null) -> out1 (Out CHOP). Channels: docs/builds/au_features.md. Each plugin load stalls TD
1.3-2.3 s once (T-99): loads are staggered 30 frames apart. No functions in storage (T-67). Pure ASCII.
"""

REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
NAME = 'AU_features'
TRACK = REPO + '/media/demo/audio_tests/kick_128bpm_30s.wav'
LOGIC = "op('au_features_logic').module"
PLUG = {'rhythm': 'Rhythm', 'loudness': 'Loudness', 'tonal': 'Tonal', 'spectral': 'Spectral'}

FEATURES_CB = '''# AU_features: Essentia channels -> clean named features (one sample each). Logic: au_features_logic.
# inputs: 0 rhythm, 1 loudness, 2 tonal, 3 spectral (any may be bypassed / not loaded -> 0).
def onSetupParameters(scriptOp):
\treturn

def onPulse(par):
\treturn

def _val(ins, src, ch):
\to = ins.get(src)
\tif o is None:
\t\treturn 0.0
\tc = o.chan(ch)
\tif c is None or o.numSamples < 1:
\t\treturn 0.0
\tv = float(c[o.numSamples - 1])
\treturn v if v == v else 0.0

_BAND = {}

def _bands(scriptOp, L, c):
\t# input 4 = n_in (mono audio): bass / mid / high / band_level from the latest BAND_N samples (no Essentia needed)
\timport numpy as np
\tst = _BAND.setdefault(scriptOp.path, {'ring': np.zeros(0), 'v': None, 't': None, 'cache': {}})
\tsrc = scriptOp.inputs[4] if len(scriptOp.inputs) > 4 else None
\tif src is not None and src.numChans and src.numSamples:
\t\ta = src.numpyArray()[0]
\t\tst['ring'] = np.concatenate([st['ring'], a])[-L.BAND_N:]
\t\trate = float(src.rate)
\telse:
\t\trate = 0.0
\tfp = getattr(c.par, 'Bandfloor', None)
\tnew = L.band_levels(st['ring'], rate, float(fp.eval()) if fp is not None else L.BAND_FLOOR, L.BANDS, st['cache'])
\tnow = float(absTime.seconds)
\tdt = 0.0 if st['t'] is None else now - st['t']
\tst['t'] = now
\tprev = st['v'] or {}
\tst['v'] = dict((k, L.band_smooth(prev.get(k), new[k], dt)) for k in L.BAND_CHANNELS)
\treturn st['v']

def onCook(scriptOp):
\tL = op('au_features_logic').module
\tc = parent()
\ttry:
\t\tbands = _bands(scriptOp, L, c) if hasattr(L, 'BAND_CHANNELS') else {}
\texcept Exception:
\t\tbands = dict((k, 0.0) for k in getattr(L, 'BAND_CHANNELS', ()))
\tlive = bool(c.par.Analysison.eval())
\tnames = ('rhythm', 'loudness', 'tonal', 'spectral')
\tins = {}
\tfor i, n in enumerate(names):
\t\tif live and i < len(scriptOp.inputs):
\t\t\tsrc = scriptOp.inputs[i]
\t\t\tif not src.bypass and src.par.plugin.eval():
\t\t\t\tins[n] = src
\tvals = [(nm, _val(ins, src, ch)) for nm, src, ch in L.CHANNELS]
\td = dict(vals)
\tf = int(absTime.frame)
\tst = c.fetch('jz_feat', None, search=False) or {'beat_prev': 0.0, 'onset_prev': 0.0, 'last_beat': -999999,
\t\t'beats': 0, 'onsets': 0, 'bt': []}
\tif c.fetch('jz_feat_reset', 0, search=False):
\t\tst.update({'beats': 0, 'onsets': 0, 'last_beat': -999999, 'bt': []})
\t\tc.store('jz_feat_reset', 0)
\tnow = float(absTime.seconds)
\tbt = list(st.get('bt') or [])
\tif d['beat'] >= 0.5 and st['beat_prev'] < 0.5:
\t\tst['beats'] += 1
\t\tst['last_beat'] = f
\t\tif bt and now - bt[-1] > 3.0:
\t\t\tbt = []
\t\tbt = (bt + [round(now, 4)])[-16:]
\tst['bt'] = bt
\tlo, hi = L.bpm_range(c.par.Bpmrange.eval(), c.par.Bpmmin.eval(), c.par.Bpmmax.eval())
\tbpm = L.bpm_from_beats(bt, lo, hi) if c.par.Bpmsource.eval() == 'beats' else 0.0
\tif bpm <= 0:
\t\tbpm = d['bpm_raw']
\tif d['onset'] >= 0.5 and st['onset_prev'] < 0.5:
\t\tst['onsets'] += 1
\tst['beat_prev'], st['onset_prev'] = d['beat'], d['onset']
\tc.store('jz_feat', st)
\tfps = float(project.cookRate) or 60.0
\tkey_idx = L.key_index_from_raw(d['key_raw']) if d['key_strength'] > 0 else -1
\tderived = (('bpm', bpm), ('beat_pulse', L.pulse_decay(f - st['last_beat'], float(c.par.Beatdecay.eval()), fps)),
\t\t('loud', L.loud_norm(d['lufs'], float(c.par.Lufsfloor.eval()))),
\t\t('centroid_norm', L.centroid_norm(d['centroid'])),
\t\t('key_index', float(key_idx)),
\t\t('beat_count', float(st['beats'])), ('onset_count', float(st['onsets'])),
\t\t('live', 1.0 if ins else 0.0))
\tscriptOp.clear()
\tif scriptOp.isTimeSlice:
\t\tscriptOp.isTimeSlice = False      # n_in (input 4) is time sliced: 1 sample out needs this off (28 Oct)
\tscriptOp.numSamples = 1
\tfor nm, v in list(derived[:1]) + list(vals) + list(derived[1:]) + [(k, bands[k]) for k in bands]:
\t\tif nm == 'key_raw':
\t\t\tcontinue
\t\tscriptOp.appendChan(nm)[0] = v
\treturn
'''

STAGES = [
    {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'au_features_logic',
                                                     'par_exec', 'features_cb', 'pull'],
     'body': 'zkit panel (Features page); pulse Opencontrols. au_features_logic = pure logic (BPM ranges, key '
             'index, LUFS/centroid normalising, beat pulse, test tracks). features_cb = the Script CHOP callback.'},
    {'title': '1 Audio in', 'role': 'input', 'ops': ['in1', 'file', 'acaudio', 'src_sel', 'mono', 'n_in'],
     'body': 'Source: Audio file (default kick_128bpm test track) | In CHOP in1 | AC_audio n_mono. mono = Math '
             'average (Essentia is mono only).'},
    {'title': '2 EssentiaTD', 'role': 'process', 'ops': ['rhythm', 'loudness', 'tonal', 'spectral'],
     'body': 'CPlusPlus CHOPs loaded by absolute path when Analysison (T-99; each load stalls TD 1.3-2.3 s once). '
             'Off = bypass, never unload (T-106). BPM range from Bpmrange (T-99: wrong metre otherwise).'},
    {'title': '3 Out features', 'role': 'output', 'ops': ['features', 'out_features', 'out1'],
     'body': 'Script CHOP: bpm beat beat_phase beat_pulse onset lufs loud rms centroid key_index chroma_c..b ... '
             '+ bass mid high band_level (FFT of n_in, input 4; no Essentia needed) (docs/builds/au_features.md). '
             'out1 = Out CHOP.'},
]


def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _close_window(c):
    w = c.op('controls_window')
    if w is not None and w.OPType == 'windowCOMP' and w.isOpen:
        w.par.winclose.pulse()
        return True
    return False


def _mk(c, cls, name):
    o = c.op(name)
    if o is not None and o.OPType != cls.__name__:
        _sd(o)
        o = None
    return o or c.create(cls, name)


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _page(c, name):
    for p in c.customPages:
        if p.name == name:
            return p
    return c.appendCustomPage(name)


def _par(c, page, style, name, label, default=None, rng=None, menu=None, clamp_min=False):
    pg = _page(c, page)
    if getattr(c.par, name, None) is not None:
        return
    if style == 'Menu':
        p = pg.appendMenu(name, label=label)[0]
        p.menuNames = [m[0] for m in menu]
        p.menuLabels = [m[1] for m in menu]
    else:
        p = getattr(pg, 'append' + style)(name, label=label)[0]
    if rng is not None:
        p.normMin, p.normMax = rng
        if clamp_min:
            p.min = rng[0]
            p.clampMin = True
    if default is not None:
        p.default = default
        p.val = default


def _pars(c, L):
    F, S = 'Features', 'Setup'
    _par(c, F, 'Menu', 'Bpmrange', 'BPM range', 'wide', menu=[(n, lab) for n, lab, _a, _b in L.BPM_RANGES])
    _par(c, F, 'Float', 'Bpmmin', 'BPM min (custom)', 60.0, (30, 200), clamp_min=True)
    _par(c, F, 'Float', 'Bpmmax', 'BPM max (custom)', 180.0, (40, 240), clamp_min=True)
    _par(c, F, 'Menu', 'Bpmsource', 'BPM from', 'beats', menu=[('beats', 'Beat clock (stable, 16 beats)'),
                                                                ('essentia', 'Essentia bpm channel (raw)')])
    _par(c, F, 'Float', 'Onsetsens', 'Onset sensitivity', 0.5, (0, 1), clamp_min=True)
    _par(c, F, 'Menu', 'Onsetmethod', 'Onset method', 'complex',
         menu=[(m, m) for m in ('hfc', 'complex', 'flux', 'melflux', 'rms', 'superflux')])
    _par(c, F, 'Float', 'Beatdecay', 'Beat pulse decay s', 0.25, (0, 1), clamp_min=True)
    _par(c, F, 'Float', 'Lufsfloor', 'Loud floor LUFS', -60.0, (-90, -10))
    _par(c, F, 'Menu', 'Keymode', 'Key mode', 'windowed', menu=[('windowed', 'Windowed (follows the song)'),
                                                              ('global', 'Global (whole history)')])
    _par(c, F, 'Pulse', 'Resetcounts', 'Reset counters')
    _par(c, F, 'Float', 'Bandfloor', 'Band floor dBFS (bass / mid / high)', L.BAND_FLOOR, (-90, -10))
    _par(c, S, 'Toggle', 'Analysison', 'Analysis on (loads the Essentia plugins)', False)
    _par(c, S, 'Toggle', 'Alwayscook', 'Cook every frame (needed for BPM/onsets)', True)
    _par(c, S, 'Menu', 'Source', 'Source', 'file', menu=L.SOURCES)
    _par(c, S, 'File', 'Audiofile', 'Audio file', TRACK)
    _par(c, S, 'Str', 'Acaudiopath', 'AC_audio mono CHOP', '../AC_audio/n_mono')
    _par(c, S, 'Folder', 'Pluginfolder', 'Essentia plugin folder', L.ESSENTIA_DIR)
    _par(c, S, 'Pulse', 'Reinitplugins', 'Re-init analysers (clears key/BPM history)')


def build(parent_path='/project1/lab', name=NAME, controls=True, analysis=None):
    pc = op(parent_path)
    c = pc.op(name) or pc.create(baseCOMP, name)
    c.allowCooking = True
    was_open = _close_window(c)
    lg = _mk(c, textDAT, 'au_features_logic')
    lg.text = open(REPO + '/builders/au_features_logic.py').read()
    L = lg.module
    _pars(c, L)
    if analysis is not None:
        c.par.Analysison = bool(analysis)
    c.comment = 'au_features: EssentiaTD BPM/beat/onset/loudness/key/chroma/centroid -> clean CHOP (out1)'

    # 1 Audio in
    inp = _mk(c, inCHOP, 'in1')
    f = _mk(c, audiofileinCHOP, 'file')
    f.par.file.expr = 'parent().par.Audiofile'
    f.par.play = True
    ac = _mk(c, selectCHOP, 'acaudio')
    ac.par.chop.expr = 'parent().par.Acaudiopath'
    sw = _mk(c, switchCHOP, 'src_sel')
    _wire(f, sw, 0)
    _wire(inp, sw, 1)
    _wire(ac, sw, 2)
    sw.par.index.expr = "{}.menu_index({}.SOURCES, parent().par.Source.eval())".format(LOGIC, LOGIC)
    mono = _mk(c, mathCHOP, 'mono')
    _wire(sw, mono)
    mono.par.chopop = 'avg'
    nin = _mk(c, nullCHOP, 'n_in')
    _wire(mono, nin)

    # 2 EssentiaTD
    for nm in PLUG:
        o = _mk(c, cplusplusCHOP, nm)
        _wire(nin, o)

    # 3 Out
    cb = _mk(c, textDAT, 'features_cb')
    cb.text = FEATURES_CB
    fe = _mk(c, scriptCHOP, 'features')
    fe.par.callbacks = cb.name
    auto = c.op('features_callbacks')   # TD makes a default callbacks DAT with a new Script CHOP: not used
    if auto is not None and auto is not cb:
        _sd(auto)
    for i, nm in enumerate(PLUG):
        _wire(c.op(nm), fe, i)
    _wire(nin, fe, 4)                    # 28 Oct: bass / mid / high / band_level from the audio itself (numpy FFT)
    of = _mk(c, nullCHOP, 'out_features')
    _wire(fe, of)
    o1 = _mk(c, outCHOP, 'out1')
    _wire(of, o1)
    # the analysers must see every timeslice: a viewer-only pull ran them at ~18 cooks/s (2400+ samples per cook >
    # the 1024/2048 windows) and BPM read 83.7 for a 128 track. Pull out_features every frame while Alwayscook.
    pull = _mk(c, executeDAT, 'pull')
    pull.text = ("# au_features: cook the analysis chain every frame (Alwayscook) so no audio timeslice is skipped\n"
                 "def onFrameStart(frame):\n\tc = parent()\n\tif c.par.Alwayscook.eval() and c.par.Analysison.eval():\n"
                 "\t\top('out_features').cook()\n\treturn\n")
    pull.par.framestart = True
    pull.par.active = False
    pull.par.active = True     # T-97: toggle after writing the text so frame callbacks fire

    pe = _mk(c, parameterexecuteDAT, 'par_exec')
    pe.text = ("# au_features: Analysison -> load/bypass the plugins; Resetcounts / Reinitplugins pulses\n"
               "def onPulse(par):\n\tc = parent()\n\tif par.name == 'Resetcounts':\n\t\tc.store('jz_feat_reset', 1)\n"
               "\telif par.name == 'Reinitplugins':\n\t\tfor n in ('rhythm', 'loudness', 'tonal', 'spectral'):\n"
               "\t\t\to = c.op(n)\n\t\t\tif o is not None and o.par.plugin.eval():\n\t\t\t\to.par.reinitpulse.pulse()\n"
               "\treturn\n\ndef onValueChange(par, prev):\n\tif par.name == 'Analysison':\n"
               "\t\tg = dict(globals()); exec(open('" + REPO + "/builders/au_features.py').read(), g)\n"
               "\t\tg['set_analysis'](parent(), par.eval())\n\treturn\n")
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Analysison Resetcounts Reinitplugins'
    pe.par.onpulse = True
    pe.par.valuechange = True
    pe.par.active = True

    set_analysis(c, c.par.Analysison.eval())

    ui = 'skipped'
    if controls:
        ns = dict(globals())
        exec(open(REPO + '/builders/zkit.py').read(), ns)
        ui = ns['build_controls'](c.path, pages=['Features'], d=56, cols=6, open_window=was_open)

    c.par.opviewer.expr = "me.op('out_features')"
    c.viewer = True
    for o in c.children:
        if o.family == 'CHOP':
            o.viewer = True
    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, STAGES, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    return {'comp': c.path, 'ops': len(c.children), 'analysis': bool(c.par.Analysison.eval()), 'ui': str(ui)[:200],
            'layout': str(lay)[:300]}


# plugin par -> expression, or an int = menu INDEX (bound once the plugin's pars exist, i.e. after its first cook).
# Menus whose names are digits ('512', '1024', ...) must be set by index: the expression "'2048'" evaluated to
# 4096 on 31550 (the digit string is read as an index and clamped to the last entry).
BINDS = {
    'rhythm': (('Mode', "'realtime'"), ('Rtwindowsize', 2),   # 2048: a dropped frame gives 1600 samples; 1024 lost them (BPM 113-119 on 120)
               ('Bpmmin', "op('au_features_logic').module.bpm_range(parent().par.Bpmrange.eval(), "
                          "parent().par.Bpmmin, parent().par.Bpmmax)[0]"),
               ('Bpmmax', "op('au_features_logic').module.bpm_range(parent().par.Bpmrange.eval(), "
                          "parent().par.Bpmmin, parent().par.Bpmmax)[1]"),
               ('Onsetsensitivity', 'parent().par.Onsetsens'), ('Onsetmethod', 'parent().par.Onsetmethod.eval()')),
    'loudness': (('Mode', "'realtime'"),),
    'tonal': (('Mode', "'realtime'"), ('Keymode', 'parent().par.Keymode.eval()'), ('Enablepitchnote', 'False')),
    'spectral': (('Mode', "'realtime'"), ('Enablemfcc', 'False'), ('Enablemel', 'False'), ('Enablehfc', 'False'),
                 ('Enablecomplexity', 'False'), ('Enablecentroid', 'True'), ('Enableflux', 'True'),
                 ('Enablerolloff', 'True')),
}

LOAD_CODE = '''o = op(args[0])
left = args[1]
if o is not None and o.par.plugin.eval():
\tif getattr(o.par, 'Mode', None) is None:
\t\to.cook()
\tif getattr(o.par, 'Mode', None) is None:
\t\tif left > 0:
\t\t\trun(args[2], args[0], left - 1, args[2], args[3], delayFrames=1)
\telse:
\t\tfor pn, e in args[3]:
\t\t\tp = getattr(o.par, pn, None)
\t\t\tif p is None:
\t\t\t\tcontinue
\t\t\tif isinstance(e, int):
\t\t\t\tif p.expr:
\t\t\t\t\tp.expr = ''
\t\t\t\tp.menuIndex = e
\t\t\telif p.expr != e:
\t\t\t\tp.expr = e
'''

SET_PLUGIN = '''o = op(args[0])
if o is not None and o.par.plugin.eval() != args[1]:
\to.par.plugin = args[1]
o.bypass = False
run(args[2], args[0], 90, args[2], args[3], delayFrames=1)
'''


def set_analysis(c, on):
    """On: load each Essentia CHOP by absolute path (once; staggered 30 frames, each load stalls ~1.3-2.3 s, T-99),
    then bind its pars when they appear. Off: bypass only; never unload a C++ plugin (T-106)."""
    folder = str(c.par.Pluginfolder.eval() or '').rstrip('/') + '/'
    out = {}
    for k, nm in enumerate(PLUG):
        o = c.op(nm)
        if o is None:
            continue
        if on:
            path = folder + 'Essentia{}CHOP.plugin'.format(PLUG[nm])
            if o.par.plugin.eval() == path:
                o.bypass = False
                run(LOAD_CODE, o.path, 90, LOAD_CODE, BINDS[nm], delayFrames=1)
                out[nm] = 'on'
            else:
                run(SET_PLUGIN, o.path, path, LOAD_CODE, BINDS[nm], delayFrames=1 + 30 * k)
                out[nm] = 'loading in {} frames'.format(1 + 30 * k)
        else:
            o.bypass = True
            out[nm] = 'bypassed'
    return out


def bands_upgrade(parent_path='/project1/lab', name=NAME):
    """28 Oct (PX beat sync) on an existing AU_features, no rebuild: au_features_logic + features_cb text, the
    Bandfloor par (Features page), n_in -> features input 4. Adds the channels bass / mid / high / band_level to
    out_features; every other channel, par value and wire is kept; no plugin is (re)loaded and Analysison is not
    touched. Idempotent: a second run returns changed = []. Parked COMPs stay parked."""
    c = op(parent_path).op(name)
    if c is None:
        return {'changed': [], 'error': 'no %s/%s' % (parent_path, name)}
    changed = []
    lg = c.op('au_features_logic')
    txt = open(REPO + '/builders/au_features_logic.py').read()
    if lg.text != txt:
        lg.text = txt
        changed.append('au_features_logic')
    cb = c.op('features_cb')
    if cb.text != FEATURES_CB:
        cb.text = FEATURES_CB
        changed.append('features_cb')
    if getattr(c.par, 'Bandfloor', None) is None:
        _pars(c, lg.module)
        changed.append('Bandfloor')
    fe, nin = c.op('features'), c.op('n_in')
    if not (len(fe.inputs) > 4 and fe.inputs[4] is nin):
        _wire(nin, fe, 4)
        changed.append('n_in -> features 4')
    return {'changed': changed, 'allowCooking': c.allowCooking,
            'chans': c.op('out_features').numChans if c.allowCooking else None}
