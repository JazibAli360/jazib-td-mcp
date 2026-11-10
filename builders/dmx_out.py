# dmx_out builder - BK_dmx_out: Art-Net / sACN output with a pixel map, fixture patch, test patterns and a monitor.
# Spec: docs/research/BK_dmx_artnet_sacn.md section 3 (clean-room, our own code). No limits: no brightness cap,
# no strobe limiter, no broadcast / rate warnings (values are bytes only because DMX slots are bytes).
# Harmless by default: Active off, Targetip 127.0.0.1 (a fresh COMP sends nothing anywhere).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/dmx_out.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set; custom par values and the tables (patch, pixels,
# profiles_json) kept; zkit panel refreshed in place. T-70 safe: nothing destroyed directly (_sd = safe_destroy),
# controls_window closed before a rebuild (zkit reopens it), panel container never destroyed, network pane not moved.
# T-74: no TOP pixel readback (pixels come back through a TOP to CHOP), no force-cook + read in one script.
# No Python functions in op storage (T-67). ASCII only.
import os

NAME = 'BK_dmx_out'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(HERE, 'dmx_logic.py')
RT_FILE = os.path.join(HERE, 'dmx_rt.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
DEMO_MOVIE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4'

PIXSAMPLE_GLSL = """// BK pixsample: one compute pass (T-46/T-47). In0 = content, In1 = uv map (rg = u,v per pixel slot).
// Out = sampled colour per pixel (same W x H as the uv map). uP: x interp (0 nearest, 1 bilinear), y npix, z w, w h.
uniform vec4 uP;
layout (local_size_x = 8, local_size_y = 8) in;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= int(uP.z) || p.y >= int(uP.w)) return;
    vec4 c = vec4(0.0);
    ivec2 msz = textureSize(sTD2DInputs[1], 0);
    ivec2 csz = textureSize(sTD2DInputs[0], 0);
    if (p.x < msz.x && p.y < msz.y && p.y * int(uP.z) + p.x < int(uP.y)) {
        vec2 uv = clamp(texelFetch(sTD2DInputs[1], p, 0).rg, 0.0, 1.0);
        if (uP.x < 0.5) {
            ivec2 q = clamp(ivec2(floor(uv * vec2(csz))), ivec2(0), csz - ivec2(1));
            c = texelFetch(sTD2DInputs[0], q, 0);
        } else {
            c = texture(sTD2DInputs[0], uv);
        }
    }
    TDImageStoreOutput(0, ivec3(p, 0), c);
}
"""

MONITOR_GLSL = """// BK monitor: one compute pass (T-46/T-47). In0 = universe values (x = slot 0..511, y = universe row, 0..255).
// uMon: x tiles per row, y px per slot, z first row, w rows shown. uOpt: x mode (0 heat, 1 grey, 2 nonzero), y w, z h.
uniform vec4 uMon;
uniform vec4 uOpt;
layout (local_size_x = 8, local_size_y = 8) in;
vec3 heat(float v) { return vec3(clamp(v * 3.0, 0.0, 1.0), clamp(v * 3.0 - 1.0, 0.0, 1.0), clamp(v * 3.0 - 2.0, 0.0, 1.0)); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    int W = int(uOpt.y), H = int(uOpt.z);
    if (p.x >= W || p.y >= H) return;
    int cell = max(1, int(uMon.y));
    int tx = max(1, int(uMon.x));
    ivec2 tile = ivec2(32, 16) * cell + ivec2(4);
    ivec2 q = ivec2(p.x, H - 1 - p.y);                       // top-left origin: universe 0 top left
    ivec2 t = q / tile;
    ivec2 l = q - t * tile;
    int u = t.y * tx + t.x;
    vec4 c = vec4(0.04, 0.04, 0.05, 1.0);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (t.x < tx && u < int(uMon.w) && l.x < 32 * cell && l.y < 16 * cell) {
        int row = int(uMon.z) + u;
        ivec2 ce = l / cell;
        int slot = ce.y * 32 + ce.x;
        if (row < isz.y && slot < isz.x) {
            float v = texelFetch(sTD2DInputs[0], ivec2(slot, row), 0).r / 255.0;
            c.rgb = uOpt.x < 0.5 ? heat(v) : (uOpt.x < 1.5 ? vec3(v) : (v > 0.0 ? vec3(1.0) : vec3(0.08)));
        } else {
            c.rgb = vec3(0.10, 0.02, 0.02);                    // tile with no data (not sent / not patched)
        }
    }
    TDImageStoreOutput(0, ivec3(p, 0), c);
}
"""

COMPOSE_CB = """# compose: one 512-sample channel per sent universe (u<flat>), via dmx_rt.cook_compose.
def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def onCook(scriptOp):
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    op('dmx_rt').module.cook_compose(scriptOp)
    return
"""

STATS_CB = COMPOSE_CB.replace('compose: one 512-sample channel per sent universe (u<flat>), via dmx_rt.cook_compose.',
                              'stats: packets_s universes slots_used frame compose_ms loopdiff seq (dmx_rt.cook_stats).'
                              ).replace('cook_compose', 'cook_stats')

UVMAP_CB = """# uvmap: pixel map -> float texture (r = u, g = v), one texel per pixel; dmx_rt writes it (no readback).
def onSetupParameters(scriptOp):
    return

def onCook(scriptOp):
    op('dmx_rt').module.cook_uvmap(scriptOp)
    return
"""

PLAN_WATCH = """# plan_watch: patch / pixels / profiles_json changed -> new plan + routing table.
def onTableChange(dat):
    op('dmx_rt').module.on_table_change()
    return
"""

SETTINGS = """# settings: plan pars -> replan; helper pulses -> dmx_rt.on_pulse.
def onValueChange(par, prev):
    op('dmx_rt').module.on_value(par)
    return

def onPulse(par):
    op('dmx_rt').module.on_pulse(par)
    return
"""

PACER = """# pacer: the Rate gate. 31550's DMX Out sends once per cook while active, and its own `rate` overshoots
# (measured: rate 10 -> 13.7 packets/s, 20 -> 34/s, 30+ -> every frame). So dmxout.rate sits at 1000 and this opens
# dmxout.active only on frames where int(absTime.seconds * Rate) ticks (time based: survives dropped frames).
# Measured with it: Rate 10/20/30/40/60 -> 10.0/19.9/30.0/40.0/59.7 packets/s per universe (10 s, loopback sniffer).
S = {'last': -1}

def onFrameStart(frame):
    c = parent()
    d = op('dmxout')
    on = bool(c.par.Active.eval()) and not c.par.Bypass.eval()
    tick = int(absTime.seconds * max(0.001, c.par.Rate.eval()))
    go = on and tick != S['last']
    if go:
        S['last'] = tick
    if d.par.active.eval() != go:
        d.par.active = go
    return
"""

STATUS_TICK = """# status_tick: read-only status pars every 30 frames (never inside a cook).
def onFrameEnd(frame):
    if frame % 30 == 0:
        op('dmx_rt').module.status()
        op('stats').cook(force=True)     # stats has no consumer unless out2 is wired: keep loopdiff/packets fresh
    return
"""


def _logic():
    ns = {}
    exec(open(LOGIC_FILE).read(), ns)
    return ns


def _pages(Lg):
    M = 'Menu'
    return [
        ('Output', [
            ('Active', 'Toggle', False, {'label': 'Active (send)'}),
            ('Protocol', M, 'artnet', {'names': Lg['PROTOCOLS'], 'labels': ['Art-Net', 'sACN (E1.31)']}),
            ('Targetmode', M, 'unicast', {'names': Lg['TARGETMODES'], 'labels': ['Unicast', 'Broadcast',
                                                                                 'Multicast (sACN)'],
                                          'label': 'Target'}),
            ('Targetip', 'Str', '127.0.0.1', {'label': 'Target IP'}),
            ('Localip', 'Str', '', {'label': 'Local IP (blank = OS)'}),
            ('Rate', 'Float', 40.0, {'min': 1, 'max': 60, 'label': 'Rate Hz'}),
            ('Firstuniv', 'Int', 0, {'min': 0, 'max': 64, 'label': 'First universe'}),
            ('Priority', 'Int', 100, {'min': 0, 'max': 200, 'label': 'sACN priority'}),
            ('Sourcename', 'Str', 'BK_dmx_out', {'label': 'Source name'}),
            ('Sendsync', 'Toggle', False, {'label': 'Send ArtSync'}),
            ('Syncms', 'Int', 20, {'min': 0, 'max': 100, 'label': 'Sync timeout ms'}),
            ('Netport', 'Int', 0, {'min': 0, 'max': 65535, 'label': 'Port (0 = default)'}),
            ('Loopback', 'Toggle', False, {'label': 'Loopback check'}),
            ('Sender', M, 'tddmx', {'names': Lg['SENDERS'], 'labels': ['TD DMX Out', 'Python (v2)']}),
            ('Universes', 'Int', 0, {'min': 0, 'max': 200, 'label': 'Universes (read)', 'ro': True}),
            ('Slotsused', 'Int', 0, {'min': 0, 'max': 100000, 'label': 'Slots used (read)', 'ro': True}),
            ('Packetsrate', 'Float', 0.0, {'min': 0, 'max': 10000, 'label': 'Packets/s (read)', 'ro': True}),
            ('Mapok', 'Toggle', True, {'label': 'Map ok (read)', 'ro': True}),
        ]),
        ('Mapping', [
            ('Pixelsrc', 'TOP', '', {'label': 'Pixel source (blank = in1)'}),
            ('Popsrc', 'POP', '', {'label': 'Pixel source POP (point i Color -> pixel i; set = wins over the TOP)'}),
            ('Pixelblur', 'Float', 0.0, {'min': 0, 'max': 32, 'label': 'Blur px'}),
            ('Colororder', M, 'rgb', {'names': Lg['ORDERS'], 'labels': [o.upper() for o in Lg['ORDERS']],
                                      'label': 'Colour order'}),
            ('Whitemode', M, 'none', {'names': Lg['WHITEMODES'], 'labels': ['None', 'Extract min', 'Zero W'],
                                      'label': 'White'}),
            ('Gamma', 'Float', 1.0, {'min': 0.2, 'max': 4, 'label': 'Gamma'}),
            ('Pixperuniv', 'Int', 170, {'min': 1, 'max': 512, 'label': 'Pixels / universe'}),
            ('Spanuniv', 'Toggle', False, {'label': 'Span universes'}),
            ('Pixelscale', 'Float', 255.0, {'min': 0, 'max': 255, 'label': 'Full scale'}),
            ('Interp', M, 'nearest', {'names': Lg['INTERPS'], 'labels': ['Nearest', 'Bilinear']}),
        ]),
        ('Master', [
            ('Master', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Master'}),
            ('Blackout', 'Toggle', False, {'label': 'Blackout'}),
            ('Blackoutmode', M, 'intensity', {'names': Lg['BLACKOUTMODES'], 'labels': ['Intensity + colour', 'All'],
                                              'label': 'Blackout acts on'}),
            ('Freeze', 'Toggle', False, {'label': 'Freeze'}),
            ('Masterfrom', M, 'manual', {'names': Lg['MASTERFROM'], 'labels': ['Manual', 'BPM', 'Audio (in3)',
                                                                                'BPM x audio'],
                                         'label': 'Master from'}),
            ('Bpm', 'Float', 120.0, {'min': 20, 'max': 300, 'label': 'BPM'}),
            ('Beatshape', M, 'pulse', {'names': Lg['BEATSHAPES'], 'labels': ['Pulse', 'Saw', 'Sine', 'Square'],
                                       'label': 'Beat shape'}),
            ('Beatdepth', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Beat depth'}),
            ('Audioamt', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Audio amount'}),
            ('Tapbpm', 'Pulse', None, {'label': 'Tap BPM'}),
        ]),
        ('Test', [
            ('Pattern', M, 'live', {'names': Lg['PATTERNS'], 'labels': ['Live', 'Zero', 'Full', 'Ramp', 'Channel id',
                                                                        'Chase', 'RGB cycle', 'Walk pixel',
                                                                        'Fixture id', 'Strobe']}),
            ('Patternmix', M, 'replace', {'names': Lg['PATTERNMIX'], 'labels': ['Replace', 'Add', 'Max'],
                                          'label': 'Pattern mix'}),
            ('Level', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Level'}),
            ('Speed', 'Float', 1.0, {'min': 0, 'max': 30, 'label': 'Speed (Hz / beats)'}),
            ('Solofixture', 'Str', '', {'label': 'Solo fixture (pattern)'}),
            ('Solochan', 'Int', 0, {'min': 0, 'max': 512, 'label': 'Solo slot (0 = off)'}),
            ('Univfilter', 'Str', '', {'label': 'Universe filter (e.g. 0-3 7)'}),
        ]),
        ('Monitor', [
            ('Monfirst', 'Int', 0, {'min': 0, 'max': 200, 'label': 'First row'}),
            ('Moncount', 'Int', 16, {'min': 1, 'max': 200, 'label': 'Rows shown'}),
            ('Moncell', 'Int', 6, {'min': 1, 'max': 16, 'label': 'Px per slot'}),
            ('Monmode', M, 'heat', {'names': Lg['MONMODES'], 'labels': ['Heat', 'Grey', 'Non-zero'], 'label': 'Mode'}),
            ('Monw', 'Int', 1024, {'min': 64, 'max': 4096, 'label': 'Monitor width'}),
            ('Monh', 'Int', 768, {'min': 64, 'max': 4096, 'label': 'Monitor height'}),
        ]),
        ('Patch', [
            ('Profile', M, 'generic_rgb_3ch', {'names': [p['id'] for p in Lg['builtin_profiles']()],
                                               'labels': [p['name'] for p in Lg['builtin_profiles']()]}),
            ('Mode', 'Str', '', {'label': 'Mode (blank = first)'}),
            ('Count', 'Int', 1, {'min': 1, 'max': 200, 'label': 'Count'}),
            ('Fixname', 'Str', 'fx', {'label': 'Name'}),
            ('Univ', 'Int', 0, {'min': 0, 'max': 200, 'label': 'Universe'}),
            ('Addr', 'Int', 1, {'min': 1, 'max': 512, 'label': 'Address'}),
            ('Autonext', 'Toggle', True, {'label': 'Next free'}),
            ('Quantize', M, 'fixture', {'names': Lg['QUANTIZE'], 'labels': ['Off', 'Per fixture']}),
            ('Gap', 'Int', 0, {'min': 0, 'max': 64, 'label': 'Gap slots'}),
            ('Addfixture', 'Pulse', None, {'label': 'Add fixture(s)'}),
            ('Checkpatch', 'Pulse', None, {'label': 'Check patch'}),
            ('Pixlayout', M, 'strip', {'names': Lg['PIXLAYOUTS'], 'labels': ['Strip', 'Grid', 'Ring'],
                                       'label': 'Pixel layout'}),
            ('Pixw', 'Int', 50, {'min': 1, 'max': 1000, 'label': 'Pixels W / count'}),
            ('Pixh', 'Int', 1, {'min': 1, 'max': 1000, 'label': 'Pixels H'}),
            ('Serpentine', 'Toggle', True, {'label': 'Serpentine'}),
            ('Genpixels', 'Pulse', None, {'label': 'Make pixel map'}),
            ('Importfile', 'File', '', {'label': 'Import (OFL .json / .csv)'}),
            ('Importpulse', 'Pulse', None, {'label': 'Import'}),
            ('Clearpatch', 'Pulse', None, {'label': 'Clear patch'}),
        ]),
        ('Controls', [
            ('Bypass', 'Toggle', False, {'label': 'Bypass (send nothing)'}),
            ('Resetdefaults', 'Pulse', None, {'label': 'Reset defaults'}),
        ]),
    ]


PANEL_PAGES = ['Output', 'Master', 'Test', 'Mapping', 'Monitor', 'Patch', 'Controls']


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None:
                if o.get('ro'):
                    getattr(c.par, name).readOnly = True
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']      # slider range only: no clamps (no limits)
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
            elif style == 'TOP':
                p = page.appendTOP(name, label=label)[0]
            elif style == 'POP':   # TC-38 POP -> DMX (27 Oct, lane T): appendPOP on 31550, appendOP as a fallback
                p = (getattr(page, 'appendPOP', None) or page.appendOP)(name, label=label)[0]
            elif style == 'File':
                p = page.appendFile(name, label=label)[0]
            else:
                continue
            p.default = default
            p.val = default
            if o.get('ro'):
                p.readOnly = True


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
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = True
    return o


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


NOTES = []


def _try(o, name, value=None, expr=None, menu_like=None):
    """Set a par that the docs name but our 31550 dump never listed (DMX ops): record misses instead of failing."""
    p = getattr(o.par, name, None)
    if p is None:
        NOTES.append('%s.%s: no such par' % (o.name, name))
        return None
    try:
        if menu_like is not None:
            names = list(p.menuNames)
            hit = next((m for m in names if any(k in m.lower() for k in menu_like)), None)
            if hit is None:
                NOTES.append('%s.%s: no menu entry like %s in %s' % (o.name, name, menu_like, names))
                return None
            p.val = hit
            return hit
        if expr is not None:
            _expr(p, expr)
        else:
            p.val = value
    except Exception as e:
        NOTES.append('%s.%s: %s' % (o.name, name, e))
    return p


def _table(c, name, cols):
    t = _mk(c, tableDAT, name)
    if t.numRows == 0 or not any(x.val for r in t.rows() for x in r):   # new (blank) table: header only
        t.clear()
        t.appendRow(cols)
    return t


def _drop_auto_docked(o, keep):
    for dk in list(o.docked):
        if dk.valid and dk.name != keep and dk.name.startswith(o.name + '_'):
            _sd(dk)


def _glsl_compute(c, name, dat_name, code):
    g = _mk(c, glslTOP, name)
    d = c.op(dat_name)
    if d is None:
        d = _mk(c, textDAT, dat_name)
    d.text = code
    g.par.mode = 'compute'
    g.par.computedat = d
    for dk in list(g.docked):                # a new GLSL TOP docks its own pixel/compute/info DATs: ours is dat_name
        if dk.valid and dk.name != dat_name and dk.name.endswith(('_pixel', '_compute', '_vertex')):
            _sd(dk)
    d.dock = g
    g.par.outputresolution = 'custom'
    g.par.inputextenduv = 'zero'
    g.seq.vec.numBlocks = max(2, g.seq.vec.numBlocks)
    return g


def build(parent_path='/project1/lab', panel=True):
    del NOTES[:]
    Lg = _logic()
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('BK_dmx_out: Art-Net / sACN out. In: in1 TOP (pixel content), in2 CHOP (<fixture>.<attr> 0..1, '
                 '*_deg degrees), in3 CHOP (audio level). Out: out1 monitor TOP, out2 stats CHOP, out3 universes CHOP '
                 '(u<flat> x 512). Patch / pixels / profiles tables inside. Active off + 127.0.0.1 by default. No '
                 'limits. Pulse Opencontrols.')
    _close_window(c)
    _pars(c, _pages(Lg))
    c.par.Sender.enable = False              # python sender = v2 (FUTURE.md)
    for ch in list(c.children):
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)

    # 1 Inputs + tables
    in1 = _mk(c, inTOP, 'in1')
    in2 = _mk(c, inCHOP, 'in2')
    in3 = _mk(c, inCHOP, 'in3')
    lg = _mk(c, textDAT, 'dmx_logic')
    lg.text = open(LOGIC_FILE).read()
    lg.comment = 'Pure logic = builders/dmx_logic.py (tests: test/test_dmx.py).'
    rt = _mk(c, textDAT, 'dmx_rt')
    rt.text = open(RT_FILE).read()
    rt.comment = 'TD runtime = builders/dmx_rt.py (compose, stats, uvmap, tables, pulses).'
    patch = _table(c, 'patch', Lg['PATCH_COLS'])
    patch.comment = 'Fixtures: name profile mode univ addr count gapslots node kind (univ = flat, addr 1-based).'
    pixels = _table(c, 'pixels', Lg['PIXEL_COLS'])
    pixels.comment = 'Pixel map: id u v univ addr group (u,v 0..1 over the content). Make with Genpixels / Import.'
    prof = _mk(c, textDAT, 'profiles_json')
    if not prof.text.strip():
        prof.text = '[]'
    prof.comment = 'User profiles (jzfix JSON list; OFL imports land here). Built-ins come from dmx_logic.'
    rep = _mk(c, textDAT, 'patch_report')
    rep.comment = 'Check patch / add / import results (reports only, never blocks sending).'
    watch = _mk(c, datexecuteDAT, 'plan_watch')
    watch.text = PLAN_WATCH
    watch.par.dats = 'patch pixels profiles_json'
    watch.par.tablechange = True
    for k in ('rowchange', 'colchange', 'cellchange', 'sizechange'):
        if getattr(watch.par, k, None) is not None:
            setattr(watch.par, k, False)
    sett = _mk(c, parameterexecuteDAT, 'settings')
    sett.text = SETTINGS
    sett.par.op = c
    sett.par.pars = ' '.join(('Colororder', 'Univfilter', 'Protocol', 'Targetmode', 'Targetip', 'Loopback',
                              'Firstuniv', 'Addfixture', 'Checkpatch', 'Importpulse', 'Clearpatch', 'Genpixels',
                              'Tapbpm', 'Resetdefaults', 'Pixelblur'))
    sett.par.custom = True
    sett.par.builtin = False
    sett.par.valuechange = True
    sett.par.onpulse = True
    tick = _mk(c, executeDAT, 'status_tick')
    tick.text = STATUS_TICK
    tick.par.frameend = True
    tick.par.active = True

    # 2 Pixel sample
    demo = _mk(c, moviefileinTOP, 'demo_movie')
    demo.par.file = DEMO_MOVIE
    demo.comment = 'Demo content (webcam_ref_5s.mp4): set Pixelsrc to this op for tests. Cooks only when used.'
    src = _mk(c, selectTOP, 'pixsrc')
    _expr(src.par.top, "parent().par.Pixelsrc.eval() or op('in1')")
    blur = _mk(c, blurTOP, 'pixblur')
    blur.inputConnectors[0].connect(src)
    _expr(blur.par.size, "max(1, parent().par.Pixelblur.eval())")
    blur.bypass = c.par.Pixelblur.eval() <= 0    # bypass is an op flag, not a par: dmx_rt.on_value keeps it in step
    blur.comment = ('Bypassed on purpose while Pixelblur = 0 (default: no blur, no cook); dmx_rt.on_value '
                    'un-bypasses it when Pixelblur > 0. td_health lists it as "bypassed": expected.')
    uv = _mk(c, scriptTOP, 'uvmap')
    ucb = uv.par.callbacks.eval()
    if ucb is None or ucb.name != 'uvmap_callbacks':
        ucb = c.op('uvmap_callbacks') or _mk(c, textDAT, 'uvmap_callbacks')
        uv.par.callbacks = ucb
    ucb.text = UVMAP_CB
    _try(uv, 'format', 'rgba32float')
    ps = _glsl_compute(c, 'pixsample', 'pixsample_compute', PIXSAMPLE_GLSL)
    ps.par.format = 'rgba32float'
    ps.inputConnectors[0].connect(blur)
    ps.inputConnectors[1].connect(uv)
    _expr(ps.par.resolutionw, "op('dmx_rt').module.pix_wh()[0]")
    _expr(ps.par.resolutionh, "op('dmx_rt').module.pix_wh()[1]")
    ps.par.vec0name = 'uP'
    for comp_, e in zip('xyzw', ["parent().par.Interp.menuIndex", "op('dmx_rt').module.plan()['npix']",
                                 "op('dmx_rt').module.pix_wh()[0]", "op('dmx_rt').module.pix_wh()[1]"]):
        _expr(getattr(ps.par, 'vec0value' + comp_), e)
    pchop = _mk(c, toptoCHOP, 'pixchop')
    pchop.par.top = ps
    _try(pchop, 'downloadtype', 'nextframe')
    _try(pchop, 'crop', 'full')
    _try(pchop, 'rgbaunit', 'u1')
    _try(pchop, 'outputcolorspace', menu_like=('passthrough',))
    pchop.comment = 'Sampled pixel colours to the CPU (CHOP, one frame late): no Python TOP readback (T-74).'
    # POP source (TC-38, 27 Oct, lane T): point i's Color (RGBA 0..1) -> pixel i. POP to CHOP gives 4 channels x
    # npoints samples, the same layout pixchop_to_pixels reads for a 1-row texture; pixin picks it while Popsrc is set.
    pop2c = _mk(c, poptoCHOP, 'popchop')
    _expr(pop2c.par.pop, "parent().par.Popsrc.eval()")
    _try(pop2c, 'extract', 'points')
    _try(pop2c, 'attribscope', 'Color')
    _try(pop2c, 'downloadtype', 'nextframe')
    pop2c.comment = 'Popsrc points: Color per point (one frame late, nextframe), point order = pixel order.'
    pixin = _mk(c, switchCHOP, 'pixin')
    pixin.inputConnectors[0].connect(pchop)
    pixin.inputConnectors[1].connect(pop2c)
    _expr(pixin.par.index, "1 if parent().par.Popsrc.eval() else 0")
    pixin.comment = 'Pixel colours: 0 = sampled TOP (pixchop), 1 = Popsrc POP (popchop).'

    # 3 Master source (audio level from in3)
    alvl = _mk(c, analyzeCHOP, 'audio_level')
    alvl.inputConnectors[0].connect(in3)
    alvl.par.function = 'rmspower'
    alag = _mk(c, lagCHOP, 'audio_lag')
    alag.inputConnectors[0].connect(alvl)
    alag.par.lag1, alag.par.lag2 = 0.02, 0.15
    alag.comment = 'in3 RMS level, lagged (Masterfrom audio / bpm-x-audio).'

    # 4 Compose
    comp = _mk(c, scriptCHOP, 'compose')
    comp.inputConnectors[0].connect(in2)
    comp.inputConnectors[1].connect(pixin)
    comp.inputConnectors[2].connect(alag)
    cb = comp.par.callbacks.eval()
    if cb is None or cb.name != 'compose_callbacks':
        cb = c.op('compose_callbacks') or _mk(c, textDAT, 'compose_callbacks')
        comp.par.callbacks = cb
    cb.text = COMPOSE_CB
    comp.par.setuppars.pulse()
    if getattr(comp.par, 'Frame', None) is not None:
        # compose on the pacer's Rate clock (same tick that opens dmxout.active, so each send carries fresh data);
        # with static content this skips composes between ticks; moving pixel content still cooks compose every
        # frame (its input changes), measured 50 cooks/s at 170 univ (T-82). dmxout cost fell 55 -> 18 ms/s.
        _expr(comp.par.Frame, 'int(absTime.seconds * max(0.001, parent().par.Rate.eval()))')
    univ = _mk(c, nullCHOP, 'universes')
    univ.inputConnectors[0].connect(comp)

    # 5 Send
    routing = _table(c, 'routing', Lg['ROUTING_COLS'])
    routing.comment = 'Generated from the plan (one row per sent universe, in channel order). Do not edit.'
    dout = _mk(c, dmxoutCHOP, 'dmxout')
    dout.inputConnectors[0].connect(univ)
    routing.dock = dout
    pacer = _mk(c, executeDAT, 'pacer')      # drives dmxout.active (Active, Bypass, Rate), see PACER
    pacer.text = PACER
    pacer.par.framestart = True
    pacer.par.active = True
    pacer.comment = 'Rate gate: opens dmxout.active on frames where the Rate clock ticks (exact Rate, <= fps).'
    if getattr(dout.par, 'active', None) is not None:
        dout.par.active.mode = ParMode.CONSTANT
        dout.par.active = False
    art = sac = None
    if getattr(dout.par, 'interface', None) is not None:
        nm = list(dout.par.interface.menuNames)
        art = next((m for m in nm if 'art' in m.lower()), None)
        sac = next((m for m in nm if 'sacn' in m.lower() or 'e131' in m.lower() or 'acn' in m.lower()), None)
        if art and sac:
            _try(dout, 'interface', expr="%r if parent().par.Protocol.eval() == 'artnet' else %r" % (art, sac))
        else:
            NOTES.append('dmxout.interface menu: %s' % nm)
    _try(dout, 'format', menu_like=('perchan', 'per chan', 'channel'))
    _try(dout, 'rate', 1000)                 # pacing comes from `pacer` (TD's own rate gate overshoots on 31550)
    _try(dout, 'routingtable', routing)
    _try(dout, 'netaddress', expr="'127.0.0.1' if parent().par.Loopback.eval() else ('255.255.255.255' if "
                                  "parent().par.Targetmode.eval() == 'broadcast' else parent().par.Targetip.eval())")
    _try(dout, 'localaddress', expr="parent().par.Localip.eval()")
    _try(dout, 'multicast', expr="parent().par.Targetmode.eval() == 'multicast'")
    _try(dout, 'priority', expr="parent().par.Priority.eval()")
    if getattr(dout.par, 'sourcename', None) is not None:
        _try(dout, 'sourcename', expr="parent().par.Sourcename.eval()")
    else:
        _try(dout, 'source', expr="parent().par.Sourcename.eval()")
    _try(dout, 'sendartsync', expr="parent().par.Sendsync.eval()")
    _try(dout, 'artsynctimeout', expr="parent().par.Syncms.eval()")
    _try(dout, 'customport', expr="parent().par.Netport.eval() > 0")
    _try(dout, 'netport', expr="parent().par.Netport.eval() if parent().par.Netport.eval() > 0 else "
                               "(6454 if parent().par.Protocol.eval() == 'artnet' else 5568)")
    _drop_auto_docked(dout, 'routing')       # 31550 docks its own default `dmxout_routingtable` at create
    for k, i in (('net', 0), ('subnet', 1), ('universe', 2)):
        _try(dout, k, expr="op('dmx_logic').module.port_address(parent().par.Firstuniv.eval())[%d]" % i)

    # 6 Loopback check
    filt = _table(c, 'loop_filter', ['net', 'subnet', 'universe'])
    din = _mk(c, dmxinCHOP, 'dmxin')
    filt.dock = din
    _try(din, 'active', expr="parent().par.Loopback.eval() and parent().par.Protocol.eval() == 'artnet'")
    if art and sac and getattr(din.par, 'interface', None) is not None:
        _try(din, 'interface', expr="%r if parent().par.Protocol.eval() == 'artnet' else %r" % (art, sac))
    _try(din, 'format', menu_like=('perchan', 'latest'))
    _try(din, 'multicast', False)
    _try(din, 'filterdat', filt)
    _drop_auto_docked(din, 'loop_filter')    # and `dmxin_filterdat` on the DMX In
    din.comment = ('Loopback check (Art-Net only): listens on the standard port while Loopback is on (Netport 0). '
                   'sACN: 31550 DMX In gets nothing on unicast loopback (T-82), stats.loopdiff = -2; '
                   'check sACN with tools/dmx_sniff.py.')

    # 7 Monitor
    u2t = _mk(c, choptoTOP, 'u2top')
    u2t.par.chop = univ
    u2t.par.dataformat = 'r'
    _try(u2t, 'format', 'r32float')
    mon = _glsl_compute(c, 'mon', 'mon_compute', MONITOR_GLSL)
    mon.par.format = 'rgba8fixed'
    mon.inputConnectors[0].connect(u2t)
    _expr(mon.par.resolutionw, "parent().par.Monw.eval()")
    _expr(mon.par.resolutionh, "parent().par.Monh.eval()")
    tiles = "op('dmx_logic').module.monitor_layout(parent().par.Monw.eval(), parent().par.Monh.eval(), " \
            "parent().par.Moncell.eval(), parent().par.Moncount.eval())"
    mon.par.vec0name, mon.par.vec1name = 'uMon', 'uOpt'
    for comp_, e in zip('xyzw', [tiles + '[0]', "parent().par.Moncell.eval()", "parent().par.Monfirst.eval()",
                                 tiles + '[2]']):
        _expr(getattr(mon.par, 'vec0value' + comp_), e)
    for comp_, e in zip('xyzw', ["parent().par.Monmode.menuIndex", "parent().par.Monw.eval()",
                                 "parent().par.Monh.eval()", '0']):
        _expr(getattr(mon.par, 'vec1value' + comp_), e)
    out1 = _mk(c, outTOP, 'out1')
    out1.inputConnectors[0].connect(mon)

    # 8 Stats / outputs
    st = _mk(c, scriptCHOP, 'stats')
    scb = st.par.callbacks.eval()
    if scb is None or scb.name != 'stats_callbacks':
        scb = c.op('stats_callbacks') or _mk(c, textDAT, 'stats_callbacks')
        st.par.callbacks = scb
    scb.text = STATS_CB
    st.par.setuppars.pulse()
    st.inputConnectors[0].connect(univ)      # a wire so the stage reads L-to-R (stats reads dmx_rt state)
    out2 = _mk(c, outCHOP, 'out2')
    out2.inputConnectors[0].connect(st)
    out3 = _mk(c, outCHOP, 'out3')
    out3.inputConnectors[0].connect(univ)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    rt.module.replan(write=True)
    rt.module.refresh_profile_menu()

    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=PANEL_PAGES, d=52, cols=8)

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'settings', 'status_tick'],
         'body': 'zkit panel + window (pulse Opencontrols). settings = plan pars + patch pulses; status_tick = '
                 'read-only status pars every 30 frames.'},
        {'title': '1 Inputs + tables', 'role': 'input',
         'ops': ['in1', 'in2', 'in3', 'patch', 'pixels', 'profiles_json', 'patch_report', 'plan_watch', 'dmx_logic',
                 'dmx_rt'],
         'body': 'in1 content TOP, in2 fixture values (<fixture>.<attr>), in3 audio level. Tables = the patch of '
                 'record; plan_watch rebuilds the plan when they change.'},
        {'title': '2 Pixel sample', 'role': 'process',
         'ops': ['demo_movie', 'pixsrc', 'pixblur', 'uvmap', 'uvmap_callbacks', 'pixsample', 'pixsample_compute',
                 'pixchop', 'popchop', 'pixin'],
         'body': 'Content (Pixelsrc or in1) -> blur -> ONE compute pass samples each pixel at its (u,v) -> TOP to '
                 'CHOP (no Python readback). Or Popsrc: POP to CHOP of Color, point i = pixel i; pixin picks.'},
        {'title': '3 Master source', 'role': 'process', 'ops': ['audio_level', 'audio_lag'],
         'body': 'in3 RMS + lag; BPM shape is computed in compose (Masterfrom).'},
        {'title': '4 Compose', 'role': 'process', 'ops': ['compose', 'compose_callbacks', 'universes'],
         'body': 'Script CHOP: fixtures -> pixels -> pattern -> master/blackout -> solo; one 512-sample channel per '
                 'sent universe (u<flat>).'},
        {'title': '5 Send', 'role': 'output', 'ops': ['pacer', 'dmxout', 'routing'],
         'body': 'DMX Out CHOP, Packet Per Channel, generated routing table (per-universe unicast). pacer opens '
                 'dmxout.active on Rate ticks (exact Rate). Active off by default.'},
        {'title': '6 Loopback check', 'role': 'process', 'ops': ['dmxin', 'loop_filter'],
         'body': 'DMX In on the standard port while Loopback is on; stats.loopdiff = max |sent - received|.'},
        {'title': '7 Monitor', 'role': 'output', 'ops': ['u2top', 'mon', 'mon_compute', 'out1'],
         'body': 'Universes -> float texture -> ONE compute pass draws 32x16-slot tiles (heat / grey / non-zero).'},
        {'title': '8 Stats / outputs', 'role': 'output', 'ops': ['stats', 'stats_callbacks', 'out2', 'out3'],
         'body': 'out2 stats (packets_s universes slots_used frame compose_ms loopdiff seq), out3 universes.'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    return {'comp': c.path, 'panel': info, 'notes': list(NOTES), 'layout': str(lay)[:400]}
