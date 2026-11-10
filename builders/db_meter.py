# db_meter builder - stereo peak/RMS level meter COMP (spec docs/research/BG_rudiment_db_meter.md).
# Run inside TD (TD 2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/db_meter.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: updates <parent>/AU_db_meter in place (ops reused by name, texts/pars/wires re-set), keeps the COMP's
# custom parameter values and the controls panel (build(..., panel=True) remakes the panel sections).
# ASCII only. No Python functions in op storage (T-67).
# T-70 safe: nothing is destroyed with .destroy() directly; _sd() = safe_destroy (closes windows showing the op, moves
# panes off, defers the destroy). The controls_window is closed before any rebuild; the panel container and its
# sec_* sections are kept and refilled in place. The network pane is never moved here (td_exec does it once).
import os

NAME = 'AU_db_meter'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(HERE, 'db_meter_logic.py')


def geo(key):
    """Par expression reading one value of the 'geometry' table (single source of the layout)."""
    return "float(op('geometry')['{}', 1])".format(key)


SHADER = """// db_meter bars: one pass (T-46). Premultiplied rgba8.
uniform vec4 uLevel;   // l r lpeak rpeak (dB)
uniform vec4 uClip;    // lclip rclip floor ceil
uniform vec4 uAxis;    // a0 a1 l0 l1 (level axis, px)
uniform vec4 uCross;   // b0 bw gap vert (cross axis, px)
uniform vec4 uOpt;     // showpeak peakpx transparent -
uniform vec4 uLow;
uniform vec4 uMid;
uniform vec4 uHigh;
uniform vec4 uTrack;
uniform vec4 uBg;
uniform vec4 uPeak;
out vec4 fragColor;

vec3 grad(float db) {
    vec3 c = mix(uLow.rgb, uMid.rgb, smoothstep(-18.0, -6.0, db));
    return mix(c, uHigh.rgb, smoothstep(-6.0, 0.0, db));
}

void main() {
    vec2 res = uTDOutputInfo.res.zw;
    vec2 p = gl_FragCoord.xy;                 // pixel centres, y up
    bool vert = uCross.w > 0.5;
    float a = vert ? p.y : p.x;               // level axis, low end = 0
    float c = vert ? p.x : res.y - p.y;       // cross axis, bars first
    vec4 col = vec4(uBg.rgb, 1.0) * (1.0 - uOpt.z);
    float b0 = uCross.x, bw = uCross.y, gap = uCross.z;
    int ch = -1;
    if (c >= b0 && c < b0 + bw) ch = 0;
    else if (c >= b0 + bw + gap && c < b0 + 2.0 * bw + gap) ch = 1;
    if (ch >= 0) {
        float lvl = ch == 0 ? uLevel.x : uLevel.y;
        float pk = ch == 0 ? uLevel.z : uLevel.w;
        float clip = ch == 0 ? uClip.x : uClip.y;
        float fl = uClip.z, ce = uClip.w, a0 = uAxis.x, a1 = uAxis.y;
        float span = max(ce - fl, 1e-4);
        if (a >= a0 && a < a1) {
            float db = fl + (a - a0) / (a1 - a0) * span;
            float top = a0 + clamp((lvl - fl) / span, 0.0, 1.0) * (a1 - a0);
            float cov = clamp(top - (a - 0.5), 0.0, 1.0);
            if (lvl <= fl + 1e-4) cov = 0.0;
            col = vec4(mix(uTrack.rgb, grad(db), cov), 1.0);
            float ppos = a0 + clamp((pk - fl) / span, 0.0, 1.0) * (a1 - a0);
            if (uOpt.x > 0.5 && pk > fl + 1e-4 && abs(a - ppos) < uOpt.y * 0.5) col = vec4(uPeak.rgb, 1.0);
        } else if (a >= uAxis.z && a < uAxis.w) {
            col = vec4(clip > 0.5 ? uHigh.rgb : uTrack.rgb, 1.0);
        }
    }
    fragColor = TDOutputSwizzle(col);
}
"""

GEOMETRY_CB = """# geometry: the meter layout in px (one table, read by the bars shader and the labels).
def onCook(scriptOp):
    L = op('meter_logic').module
    P = parent()
    g = L.geometry(P.par.Resw.eval(), P.par.Resh.eval(), P.par.Orient.eval(), P.par.Gap.eval(),
                   P.par.Scalew.eval(), P.par.Showscale.eval())
    scriptOp.clear()
    scriptOp.appendRow(['key', 'value'])
    for k in sorted(g):
        scriptOp.appendRow([k, repr(float(g[k]))])
    return
"""

LABELS_CB = """# label_table: one row per scale label: dB, text, pos (px on the level axis, same mapping as the bars), px.
def onCook(scriptOp):
    L = op('meter_logic').module
    P = parent()
    fl, ce = P.par.Floor.eval(), P.par.Ceil.eval()
    g = L.geometry(P.par.Resw.eval(), P.par.Resh.eval(), P.par.Orient.eval(), P.par.Gap.eval(),
                   P.par.Scalew.eval(), P.par.Showscale.eval())
    px = L.auto_font_px(g, P.par.Fontsize.eval())
    scriptOp.clear()
    scriptOp.appendRow(['db', 'text', 'pos', 'px'])
    for d in L.label_rows(fl, ce, P.par.Step.eval()):
        scriptOp.appendRow([repr(float(d)), L.label_text(d), repr(L.axis_pos(d, g, fl, ce)), repr(px)])
    return
"""

SCALE_CB = """# labels: the scale strip (ticks + numbers), premultiplied rgba8, transparent elsewhere.
# Cooks only when the label table or a look parameter changes (not every frame).
import numpy as np
import cv2

def onCook(scriptOp):
    L = op('meter_logic').module
    P = parent()
    W, H = int(P.par.Resw.eval()), int(P.par.Resh.eval())
    g = L.geometry(W, H, P.par.Orient.eval(), P.par.Gap.eval(), P.par.Scalew.eval(), P.par.Showscale.eval())
    t = op('label_table')
    img = np.zeros((H, W), np.uint8)          # top-down canvas for cv2
    vert = g['vert'] > 0.5
    if P.par.Showscale.eval() and t.numRows > 1:
        font = cv2.FONT_HERSHEY_SIMPLEX
        px = float(t[1, 'px'])
        scale = px / 22.0
        th = max(1, int(round(px / 11.0)))
        strip = g['s1'] - g['s0']
        tick = max(2, int(round(0.14 * strip)))
        pad = max(2, int(round(px * 0.35)))
        s0 = int(round(g['s0']))
        for r in range(1, t.numRows):
            pos = float(t[r, 'pos'])
            txt = t[r, 'text'].val
            (tw, tht), base = cv2.getTextSize(txt, font, scale, th)
            m = th + 3
            tmp = np.zeros((tht + base + 2 * m, tw + 2 * m), np.uint8)
            cv2.putText(tmp, txt, (m, tht + m), font, scale, 255, th, cv2.LINE_AA)
            ys, xs = np.nonzero(tmp)
            if not len(ys):
                continue
            ink = tmp[ys.min():ys.max() + 1, xs.min():xs.max() + 1]   # the drawn glyphs only
            ih, iw = ink.shape
            n = min(int(pos), int(g['L']) - 1)                           # pixel holding the coordinate
            if vert:
                img[H - 1 - n, s0:s0 + tick] = 255
                top, left = int(round(H - pos - ih / 2.0)), s0 + tick + pad   # ink centre on the bar row
            else:
                img[s0:s0 + tick, n] = 255
                top, left = s0 + tick + pad, int(round(pos - iw / 2.0))
            top = max(0, min(H - ih, top))      # never cut a label at the picture edge
            left = max(0, min(W - iw, left))
            y1, x1 = min(H, top + ih), min(W, left + iw)
            img[top:y1, left:x1] = np.maximum(img[top:y1, left:x1], ink[:y1 - top, :x1 - left])
    a = img.astype(np.float32) / 255.0
    col = (P.par.Labelcolr.eval(), P.par.Labelcolg.eval(), P.par.Labelcolb.eval())
    rgba = np.zeros((H, W, 4), np.uint8)
    for i in range(3):
        rgba[..., i] = np.clip(col[i] * a * 255.0 + 0.5, 0, 255).astype(np.uint8)
    rgba[..., 3] = img
    scriptOp.copyNumpyArray(np.ascontiguousarray(rgba[::-1]))   # TD row 0 = bottom (T-58)
    return
"""

BALLISTICS_CB = """# ballistics: bar fall, peak hold and clip lamp per frame (logic in meter_logic).
# State lives in this module (plain dict), not in op storage: store() inside its own cook = cook loop.
STATE = {'st': None, 'reset': False}

def reset():
    STATE['reset'] = True

def onSetupParameters(scriptOp):
    # Clock par (absTime.frame): makes this CHOP cook every frame, so hold/fall run on steady input too.
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def onCook(scriptOp):
    L = op('meter_logic').module
    P = parent()
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    i = scriptOp.inputs[0] if scriptOp.inputs else None
    fl = P.par.Floor.eval()
    raw_l = i['l'][0] if (i is not None and i['l'] is not None) else fl
    raw_r = i['r'][0] if (i is not None and i['r'] is not None) else fl
    p = {'floor': fl, 'ceil': P.par.Ceil.eval(), 'attack': P.par.Attack.eval(), 'release': P.par.Release.eval(),
         'hold': P.par.Hold.eval(), 'clipdb': P.par.Clipdb.eval()}
    st = None if STATE['reset'] else STATE['st']
    STATE['reset'] = False
    st, o = L.meter_step(st, raw_l, raw_r, absTime.seconds, p)
    STATE['st'] = st
    scriptOp.clear()
    scriptOp.numSamples = 1
    for n in ('l', 'r', 'lpeak', 'rpeak', 'lclip', 'rclip'):
        scriptOp.appendChan(n)[0] = float(o[n])
    return
"""

PEXEC = """# Opencontrols -> this COMP's controls window; Holdreset -> clear peak hold + clip lamps.
def onPulse(par):
    if par.name == 'Opencontrols':
        parent().op('controls_window').par.winopen.pulse()
    elif par.name == 'Holdreset':
        parent().op('ballistics_callbacks').module.reset()
        parent().op('ballistics').cook(force=True)
    return
"""

DBEXPR = "20 * math.log10(max(abs(me.inputVal), 1e-6))"

P_EXPR = "parent().par.{}.eval()"

PAGES = [
    ('Meter', [
        ('Mode', 'Menu', 'peak', {'names': ['peak', 'rms'], 'labels': ['Peak', 'RMS']}),
        ('Floor', 'Float', -60.0, {'min': -120, 'max': -6, 'label': 'Floor dB'}),
        ('Ceil', 'Float', 3.0, {'min': -20, 'max': 24, 'label': 'Ceil dB'}),
        ('Step', 'Float', 6.0, {'min': 1, 'max': 24, 'label': 'Label step dB'}),
        ('Gain', 'Float', 0.0, {'min': -40, 'max': 40, 'label': 'Gain dB'}),
        ('Attack', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Attack s'}),
        ('Release', 'Float', 24.0, {'min': 0, 'max': 120, 'label': 'Release dB/s'}),
        ('Hold', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Peak/clip hold s'}),
        ('Clipdb', 'Float', 0.0, {'min': -20, 'max': 12, 'label': 'Clip at dB'}),
        ('Holdreset', 'Pulse', None, {'label': 'Reset hold'}),
    ]),
    ('Input', [
        ('Source', 'Menu', 'input', {'names': ['input', 'test'], 'labels': ['In CHOP', 'Test tone']}),
        ('Channels', 'Menu', 'auto', {'names': ['auto', 'mono', 'stereo'], 'labels': ['Auto', 'Mono', 'Stereo']}),
        ('Testamp', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Test amplitude'}),
        ('Testfreq', 'Float', 440.0, {'min': 20, 'max': 8000, 'label': 'Test Hz'}),
        ('Testchan', 'Menu', 'both', {'names': ['both', 'left', 'right'], 'labels': ['Both', 'Left', 'Right']}),
    ]),
    ('Look', [
        ('Resw', 'Int', 256, {'min': 16, 'max': 4096, 'label': 'Width'}),
        ('Resh', 'Int', 1024, {'min': 16, 'max': 4096, 'label': 'Height'}),
        ('Orient', 'Menu', 'vertical', {'names': ['vertical', 'horizontal'], 'labels': ['Vertical', 'Horizontal']}),
        ('Gap', 'Float', 4.0, {'min': 0, 'max': 64, 'label': 'Bar gap px'}),
        ('Scalew', 'Float', 0.4, {'min': 0, 'max': 0.9, 'label': 'Scale strip'}),
        ('Showscale', 'Toggle', True, {'label': 'Scale'}),
        ('Showpeak', 'Toggle', True, {'label': 'Peak hold line'}),
        ('Peakpx', 'Float', 2.0, {'min': 1, 'max': 16, 'label': 'Peak line px'}),
        ('Fontsize', 'Float', 0.0, {'min': 0, 'max': 96, 'label': 'Font px (0 auto)'}),
        ('Transparent', 'Toggle', False, {'label': 'Transparent bg'}),
    ]),
    ('Colours', [
        ('Gradlow', 'RGB', (0.10, 0.62, 0.22), {'label': 'Low'}),
        ('Gradmid', 'RGB', (0.90, 0.78, 0.12), {'label': 'Mid (-6 dB)'}),
        ('Gradhigh', 'RGB', (0.95, 0.18, 0.12), {'label': 'High (0 dB) / clip'}),
        ('Track', 'RGB', (0.16, 0.16, 0.17), {'label': 'Track'}),
        ('Bg', 'RGB', (0.0, 0.0, 0.0), {'label': 'Background'}),
        ('Peakcol', 'RGB', (0.92, 0.92, 0.92), {'label': 'Peak line'}),
        ('Labelcol', 'RGB', (0.80, 0.80, 0.80), {'label': 'Labels'}),
    ]),
    ('Controls', [
        ('Opencontrols', 'Pulse', None, {'label': 'Open controls'}),
    ]),
]

PANEL_PAGES = ['Meter', 'Input', 'Look']   # colours stay on their own page (autoUI RGB bug, T-68)


def _pars(c):
    """Create the custom pages/pars once; keep existing values."""
    for page_name, pars in PAGES:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None or (style == 'RGB' and getattr(c.par, name + 'r', None) is not None):
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
                p.default = default
                p.val = default
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
                p.default = default
                p.val = default
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
                p.clampMin = True
                p.min = o['min']
                p.default = default
                p.val = default
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style == 'RGB':
                for p, v in zip(page.appendRGB(name, label=label), default):
                    p.default = v
                    p.val = v


def _sd(o):
    """T-70: destroy through safe_destroy (td_exec namespace, else the MCP handlers module)."""
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _close_window(c):
    """Close this COMP's own controls window before touching anything it shows (T-70)."""
    w = c.op('controls_window')
    if w is not None and w.OPType == 'windowCOMP' and w.isOpen:
        w.par.winclose.pulse()
        return True
    return False


def _mk(c, cls, name):
    """Reuse the op if it exists with that type, else create it: a rebuild updates in place instead of destroying
    the whole network (a mass destroy under the live network pane was followed by a TD UI-thread crash)."""
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = True
    return o


def _tidy(c):
    """Drop leftovers of earlier probes/tests (names starting with '_')."""
    for ch in list(c.children):
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _zkit_refresh(comp):
    """The COMP carries a zkit panel (builders/zkit.py, rolled out 26 Oct): refresh it in place (T-70 safe) instead
    of making autoUI widgets. None when there is no kit panel."""
    p_ = comp.op('controls')
    if p_ is None or p_.op('zk_rt') is None:
        return None
    ns_ = dict(globals())
    exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/zkit.py').read(), ns_)
    return ns_['build_controls'](comp.path)


def _panel(c, rebuild=False):
    """Own controls panel (autoUI, clone links cut) + window opened by Opencontrols.
    An existing panel is kept unless rebuild=True (then only its sections are made again)."""
    zk = _zkit_refresh(c)
    if zk is not None:
        return [('zkit', zk['rebuild'])]
    au = op('/project1/show/tools/autoUI')
    panel = c.op('controls')
    if panel is not None and not rebuild and panel.op('sec_meter') is not None:
        made = [('kept', len(panel.children))]
        total = int(panel.par.h.eval())
    else:
        _close_window(c)
        made, total = _panel_build(c, au, panel)
        panel = c.op('controls')
    win = _mk(c, windowCOMP, 'controls_window')
    win.par.winop = panel
    win.par.title = c.name + ' controls'
    win.par.size = 'automatic'
    win.par.winw, win.par.winh = 400, total + 28
    pe = _mk(c, parameterexecuteDAT, 'controls_open')
    pe.text = PEXEC
    pe.par.op = c
    pe.par.pars = 'Opencontrols Holdreset'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = False
    pe.par.onpulse = True
    return made


def _panel_build(c, au, panel):
    if panel is None:
        panel = _mk(c, containerCOMP, 'controls')
    want = ['sec_' + pg.lower() for pg in PANEL_PAGES]
    for s_ in list(panel.children):          # only strays go; the sections themselves are refilled in place
        if s_.valid and s_.name not in want:
            _sd(s_)
    panel.par.w = 380
    panel.par.align = 'verttb'
    panel.par.bgcolorr, panel.par.bgcolorg, panel.par.bgcolorb, panel.par.bgalpha = 0.12, 0.12, 0.13, 1
    panel.comment = 'db_meter controls (autoUI widgets bound to the COMP pars; clone links cut). Open: Opencontrols.'
    keep = {p.name: (p.mode, p.expr, p.eval()) for p in au.customPars if p.name in ('Pagetabs', 'Pagescope', 'Header')}
    total, made = 0, []
    try:
        for k, pg in enumerate(PANEL_PAGES):
            sec = _mk(panel, containerCOMP, 'sec_' + pg.lower())
            for w_ in list(sec.children):    # window is closed (T-70): clear the old widgets, keep the section
                _sd(w_)
            sec.par.w = 380
            sec.par.hmode = 'fill'
            sec.par.align = 'verttb'
            sec.par.alignorder = k
            sec.par.bgcolorr, sec.par.bgcolorg, sec.par.bgcolorb, sec.par.bgalpha = 0.12, 0.12, 0.13, 1
            au.par.Pagetabs = False
            au.par.Header = True
            au.par.Pagescope = pg
            au.ext.AutoUIExt.GenerateUI(customComp=c, ui=sec, shortcutDialog=False)
            h = 0
            for w in sec.children:
                if w.OPType == 'widgetCOMP' or w.isPanel:
                    w.par.hmode = 'fill'
                    if getattr(w.par, 'clone', None) is not None:
                        w.par.clone.expr = ''
                        w.par.clone.mode = ParMode.CONSTANT
                        w.par.clone = ''
                    if getattr(w.par, 'enablecloning', None) is not None:
                        w.par.enablecloning = False
                    h += int(w.par.h.eval())
            hd = sec.op('header')
            if hd is not None and getattr(hd.par, 'Headerlabel', None) is not None:
                hd.par.Headerlabel = pg.upper()
            sec.par.h = h + 4
            total += h + 4
            made.append((pg, len(sec.children)))
    finally:
        for n, (m, e, v) in keep.items():
            p = getattr(au.par, n)
            if m == ParMode.EXPRESSION:
                p.expr = e
            else:
                p.val = v
    panel.par.h = total
    return made, total


def build(parent_path='/project1/lab', panel=False):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.comment = 'db_meter: stereo peak/RMS meter, dB scale, peak hold, clip lamps. In: in1 (audio CHOP). Out: out1 TOP, out2 CHOP.'
    _close_window(c)                         # T-70: never rebuild under an open window
    _pars(c)
    _tidy(c)

    # 5 Geometry (logic first: everything reads it)
    logic = _mk(c, textDAT, 'meter_logic')
    logic.text = open(LOGIC_FILE).read()
    logic.comment = 'Pure logic (copy of builders/db_meter_logic.py; tests in test/test_db_meter.py).'

    # 1 Input
    in1 = _mk(c, inCHOP, 'in1')
    tone = _mk(c, audiooscillatorCHOP, 'testtone')
    tone.par.wavetype = 'sin'
    _expr(tone.par.frequency, P_EXPR.format('Testfreq'))
    _expr(tone.par.amp, P_EXPR.format('Testamp'))
    tone.par.octave = 0
    sil = _mk(c, constantCHOP, 'silence')
    sil.par.name0 = 'chan1'
    sil.par.value0 = 0
    src = _mk(c, switchCHOP, 'src')
    for k, o_ in enumerate((in1, tone, sil)):
        src.inputConnectors[k].connect(o_)
    _expr(src.par.index, "1 if parent().par.Source.eval() == 'test' else (0 if op('in1').numChans else 2)")
    sel_l = _mk(c, selectCHOP, 'sel_l')
    sel_r = _mk(c, selectCHOP, 'sel_r')
    for s_ in (sel_l, sel_r):
        s_.inputConnectors[0].connect(src)
    el = "(op('src')[0].name if op('src').numChans else '')"
    er = ("(op('src')[1].name if (op('src').numChans > 1 and parent().par.Channels.eval() != 'mono') "
          "else (op('src')[0].name if op('src').numChans else ''))")
    _expr(sel_l.par.channames, el)
    _expr(sel_l.par.renamefrom, el)
    sel_l.par.renameto = 'l'
    _expr(sel_r.par.channames, er)
    _expr(sel_r.par.renamefrom, er)
    sel_r.par.renameto = 'r'
    gain_l = _mk(c, mathCHOP, 'gain_l')
    gain_r = _mk(c, mathCHOP, 'gain_r')
    gain_l.inputConnectors[0].connect(sel_l)
    gain_r.inputConnectors[0].connect(sel_r)
    g = "10 ** (parent().par.Gain.eval() / 20.0)"
    _expr(gain_l.par.gain, g + " * (0 if (parent().par.Source.eval() == 'test' and parent().par.Testchan.eval() == 'right') else 1)")
    _expr(gain_r.par.gain, g + " * (0 if (parent().par.Source.eval() == 'test' and parent().par.Testchan.eval() == 'left') else 1)"
          " * (0 if (parent().par.Channels.eval() == 'stereo' and op('src').numChans < 2) else 1)")
    lr = _mk(c, mergeCHOP, 'lr')
    lr.inputConnectors[0].connect(gain_l)
    lr.inputConnectors[1].connect(gain_r)

    # 2 Level (one value per frame from the frame's audio block)
    rect = _mk(c, mathCHOP, 'rectify')
    rect.par.postop = 'pos'
    rect.inputConnectors[0].connect(lr)
    pk = _mk(c, analyzeCHOP, 'peak')
    pk.par.function = 'maximum'
    pk.inputConnectors[0].connect(rect)
    rms = _mk(c, analyzeCHOP, 'rms')
    rms.par.function = 'rmspower'
    rms.inputConnectors[0].connect(lr)
    lvl = _mk(c, switchCHOP, 'level')
    lvl.inputConnectors[0].connect(pk)
    lvl.inputConnectors[1].connect(rms)
    _expr(lvl.par.index, "parent().par.Mode.menuIndex")

    # 3 dB
    todb = _mk(c, expressionCHOP, 'todb')
    todb.inputConnectors[0].connect(lvl)
    todb.par.expr0expr.expr = DBEXPR
    todb.par.expr0expr.mode = ParMode.EXPRESSION

    # 4 Ballistics
    bal = _mk(c, scriptCHOP, 'ballistics')
    bal.inputConnectors[0].connect(todb)
    bal.par.callbacks.eval().text = BALLISTICS_CB
    bal.par.setuppars.pulse()
    levels = _mk(c, nullCHOP, 'levels')
    levels.inputConnectors[0].connect(bal)
    out2 = _mk(c, outCHOP, 'out2')
    out2.inputConnectors[0].connect(levels)

    # 5 Geometry tables
    gt = _mk(c, scriptDAT, 'geometry')
    gt.par.callbacks.eval().text = GEOMETRY_CB
    lt = _mk(c, scriptDAT, 'label_table')
    lt.par.callbacks.eval().text = LABELS_CB

    # 6 Bars
    bars = _mk(c, glslTOP, 'bars')
    bars.par.pixeldat.eval().text = SHADER
    bars.par.outputresolution = 'custom'
    _expr(bars.par.resolutionw, P_EXPR.format('Resw'))
    _expr(bars.par.resolutionh, P_EXPR.format('Resh'))
    bars.par.format = 'rgba8fixed'
    bars.seq.vec.numBlocks = 11
    U = [
        ('uLevel', ["op('levels')['l'][0]", "op('levels')['r'][0]", "op('levels')['lpeak'][0]", "op('levels')['rpeak'][0]"]),
        ('uClip', ["op('levels')['lclip'][0]", "op('levels')['rclip'][0]", P_EXPR.format('Floor'), P_EXPR.format('Ceil')]),
        ('uAxis', [geo('a0'), geo('a1'), geo('l0'), geo('l1')]),
        ('uCross', [geo('b0'), geo('bw'), geo('gap'), geo('vert')]),
        ('uOpt', ["float(parent().par.Showpeak.eval())", P_EXPR.format('Peakpx'), "float(parent().par.Transparent.eval())", '0']),
    ]
    for nm in ('Gradlow', 'Gradmid', 'Gradhigh', 'Track', 'Bg', 'Peakcol'):
        un = {'Gradlow': 'uLow', 'Gradmid': 'uMid', 'Gradhigh': 'uHigh', 'Track': 'uTrack', 'Bg': 'uBg', 'Peakcol': 'uPeak'}[nm]
        U.append((un, [P_EXPR.format(nm + 'r'), P_EXPR.format(nm + 'g'), P_EXPR.format(nm + 'b'), '1']))
    for k, (un, ex) in enumerate(U):
        getattr(bars.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(bars.par, 'vec{}value{}'.format(k, comp)), e)

    # 7 Scale labels
    lab = _mk(c, scriptTOP, 'labels')
    lab.par.callbacks.eval().text = SCALE_CB

    # 8 Compose
    comp = _mk(c, overTOP, 'compose')
    comp.inputConnectors[0].connect(lab)
    comp.inputConnectors[1].connect(bars)
    out1 = _mk(c, outTOP, 'out1')
    out1.inputConnectors[0].connect(comp)

    made = _panel(c, rebuild=panel)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'controls_open'],
         'body': 'Own panel (autoUI: Meter, Input, Look pages) + window. Pulse Opencontrols on the COMP to open it.'},
        {'title': '1 Input', 'role': 'input', 'ops': ['in1', 'testtone', 'silence', 'src', 'sel_l', 'sel_r', 'gain_l', 'gain_r', 'lr'],
         'body': 'Source: In CHOP or test tone (never to a speaker). 1 channel = both bars. Gain dB trim.'},
        {'title': '2 Level', 'role': 'process', 'ops': ['rectify', 'peak', 'rms', 'level'],
         'body': "One value per frame from the frame's audio block: max |x| (peak) or RMS. Mode picks."},
        {'title': '3 dB', 'role': 'process', 'ops': ['todb'], 'body': '20 log10(level), 1e-6 floor.'},
        {'title': '4 Ballistics', 'role': 'output', 'ops': ['ballistics', 'levels', 'out2'],
         'body': 'Attack/Release on the bar, peak hold (Hold s then Release dB/s), clip lamps. out2 = l r lpeak rpeak lclip rclip.'},
        {'title': '5 Geometry', 'role': 'process', 'ops': ['meter_logic', 'geometry', 'label_table'],
         'body': 'One layout for bars and labels (meter_logic), so labels line up at any size.'},
        {'title': '6 Bars', 'role': 'process', 'ops': ['bars'], 'body': 'Single-pass GLSL: gradient fill, track, peak line, clip lamp.'},
        {'title': '7 Scale labels', 'role': 'process', 'ops': ['labels'], 'body': 'Script TOP (cv2): ticks + numbers from label_table. Cooks on change only.'},
        {'title': '8 Compose', 'role': 'output', 'ops': ['compose', 'out1'], 'body': 'Labels over bars. out1 = premultiplied rgba8 meter picture.'},
    ]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    return {'comp': c.path, 'panel': made, 'layout': str(lay)[:400]}
