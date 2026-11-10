# fx_analog_signalloss - FX_analog module 'signalloss' (FX0 row 51; FX1 DG-11 / DG-24; FX2 AV-07 power-off, AV-13
# weak sync, AV-14 interlace). Template: docs/builds/fx_glitch.md "Module template" (rack = builders/fx_analog.py).
# ONE compute pass (T-46/T-47, format useinput) over the picture in tape coordinates (Line axis):
#   sync loss   H: torn line segments (Tear, Tear size) re-picked at Rate, per-line jitter, H-hold drift (each line
#               slides Slant px further and wraps = diagonal bars); V: V-hold offset + roll with a blanking bar, jumps
#   no signal   card (blue / snow / black / 75 % bars) + an OSD Text TOP ("NO SIGNAL"), snow over the picture
#   interlace   weave (fields from this and the previous frame = combing on motion, Comb shift), bob (line-doubled
#               single field, twitter), blend (ghost); field rows Field pitch px tall
#   power       Power off pulse = the CRT collapse (picture squeezes to a bright line, then a dot that fades; Off hold
#               keeps it black until Power on), Power on = warm-up (grows from 55 % and brightens), Manual phase holds
#               any collapse phase (fader / MIDI / live check)
# Hit (pulse) = a sync-loss burst (tears + snow + jump) that decays over Hit decay s, at any Amount. Amount 0 with no
# burst / power transition = `out_sel` picks in1 (exact passthrough; nothing else cooks). Maths + references:
# builders/fx_analog_signal_logic.py. Doc + LIVE CHECKS: docs/builds/fx_analog_signalloss.md. ASCII only.
import os

MODULE = 'signalloss'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
_LG = dict(globals())                    # TD names (parameterexecuteDAT, ...) for the helpers that build ops
with open(os.path.join(_HERE, 'fx_analog_signal_logic.py')) as _fh:
    exec(_fh.read(), _LG)

PAGES = [
    ('Sync', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Htear', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Tear (H sync loss)'}),
        ('Tearsize', 'Float', 80.0, {'min': 0, 'max': 400, 'label': 'Tear size px'}),
        ('Hslant', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'H-hold drift px/line'}),
        ('Hjitter', 'Float', 0.0, {'min': 0, 'max': 20, 'label': 'Line jitter px'}),
        ('Vroll', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'V-hold roll /s'}),
        ('Vpos', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'V-hold offset'}),
        ('Vbar', 'Float', 0.08, {'min': 0, 'max': 0.5, 'label': 'Blanking bar'}),
        ('Vjump', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'V jumps'}),
        ('Rate', 'Float', 12.0, {'min': 0, 'max': 60, 'label': 'Rate Hz (tears / jitter / jumps)'}),
        ('Hit', 'Pulse', None, {'label': 'Hit (sync-loss burst)'}),
        ('Hitdecay', 'Float', 0.6, {'min': 0.05, 'max': 4, 'label': 'Hit decay s'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 99, 'label': 'Seed'}),
    ]),
    ('Nosignal', [
        ('Nosignal', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'No signal (card mix)'}),
        ('Card', 'Menu', 'blue', {'names': _LG['SL_CARDS'], 'labels': ['Blue screen', 'Snow', 'Black',
                                                                      'Colour bars 75 %']}),
        ('Snow', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Snow over the picture'}),
        ('Osd', 'Toggle', True, {'label': 'OSD text on the card'}),
    ]),
    ('Interlace', [
        ('Interlace', 'Menu', 'off', {'names': _LG['SL_INTERLACE'], 'labels': ['Off', 'Weave (combing)',
                                                                              'Bob (twitter)', 'Blend (ghost)']}),
        ('Fieldpitch', 'Int', 2, {'min': 1, 'max': 16, 'label': 'Field line px'}),
        ('Combshift', 'Float', 0.0, {'min': -40, 'max': 40, 'label': 'Comb shift px'}),
    ]),
    ('Power', [
        ('Poweroff', 'Pulse', None, {'label': 'Power off (collapse)'}),
        ('Poweron', 'Pulse', None, {'label': 'Power on (warm-up)'}),
        ('Powerdur', 'Float', 0.45, {'min': 0.05, 'max': 3, 'label': 'Collapse s'}),
        ('Warmup', 'Float', 1.2, {'min': 0, 'max': 5, 'label': 'Warm-up s'}),
        ('Offhold', 'Toggle', True, {'label': 'Off hold (black until Power on)'}),
        ('Powerphase', 'Float', -1.0, {'min': -1, 'max': 1, 'label': 'Manual phase (-1 = pulses)'}),
        ('Glow', 'Float', 1.5, {'min': 0, 'max': 4, 'label': 'Line / dot glow'}),
    ]),
    ('Setup', [
        _LG['AXIS_PAR'],
        ('Cardr', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Card colour R'}),
        ('Cardg', 'Float', 0.12, {'min': 0, 'max': 1, 'label': 'Card colour G'}),
        ('Cardb', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Card colour B'}),
        ('Osdtext', 'Str', 'NO SIGNAL', {'label': 'OSD text'}),
    ]),
    ('State', [
        ('Hittime', 'Float', -1000.0, {'min': -1, 'max': 1, 'label': 'Last Hit (absTime s)'}),
        ('Offtime', 'Float', -1000.0, {'min': -1, 'max': 1, 'label': 'Last Power off (absTime s)'}),
        ('Ontime', 'Float', -1000.0, {'min': -1, 'max': 1, 'label': 'Last Power on (absTime s)'}),
    ]),
]
PANEL_PAGES = ['Sync', 'Nosignal', 'Interlace', 'Power']

# Menus as index (Card 0 blue / 1 snow / 2 black / 3 bars; Interlace 0 off / 1 weave / 2 bob / 3 blend), toggles 0/1.
_Z = {'Amount': 1.0, 'Htear': 0.0, 'Tearsize': 80.0, 'Hslant': 0.0, 'Hjitter': 0.0, 'Vroll': 0.0, 'Vpos': 0.0,
      'Vbar': 0.08, 'Vjump': 0.0, 'Rate': 12.0, 'Nosignal': 0.0, 'Card': 0, 'Snow': 0.0, 'Osd': 1, 'Interlace': 0,
      'Fieldpitch': 2, 'Combshift': 0.0, 'Powerphase': -1.0}
PRESETS = [
    (1, 'v-hold', dict(_Z, Vroll=0.4, Vbar=0.08)),
    (2, 'h-hold', dict(_Z, Hslant=0.35, Hjitter=2.0)),
    (3, 'weak sync', dict(_Z, Htear=0.35, Tearsize=60.0, Hjitter=3.0, Vjump=0.15, Snow=0.2, Rate=10.0)),
    (4, 'no signal', dict(_Z, Nosignal=1.0, Card=0, Osd=1)),
    (5, 'dead air', dict(_Z, Nosignal=1.0, Card=1, Osd=0)),
    (6, 'interlaced', dict(_Z, Interlace=1, Fieldpitch=2, Combshift=6.0)),
    (7, 'bars', dict(_Z, Nosignal=1.0, Card=3, Osd=0)),
]

FX = """// FX_analog signalloss (compute, T-47, output = input size, format useinput). in0 picture, in1 previous frame
// (weave / blend) or the picture, in2 stamp (x now, y previous cook: gap > 0.25 s = stale), in3 OSD text (or 1x1 blank).
// Pixel units in tape coordinates (s along the line, l = line from the bottom): fx_analog_signal_logic.collapse /
// vroll_line / slant_src / power_state mirror this.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, tear, tear size px, slant px/line
uniform vec4 uB;   // jitter px, roll /s, V offset, blanking bar
uniform vec4 uC;   // V jumps, rate Hz, seed, t
uniform vec4 uD;   // no signal, card, snow, osd
uniform vec4 uE;   // interlace mode, field pitch px, comb shift px, line axis
uniform vec4 uF;   // now, power-off time, power-on time, manual phase
uniform vec4 uG;   // collapse s, warm-up s, off hold, glow
uniform vec4 uH;   // seconds since Hit, hit decay s, frame, -
uniform vec4 uK;   // card colour
""" + _LG['GLSL_LIB'] + """
const vec3 BARS[7] = vec3[7](vec3(0.75, 0.75, 0.75), vec3(0.75, 0.75, 0.0), vec3(0.0, 0.75, 0.75), vec3(0.0, 0.75, 0.0),
                             vec3(0.75, 0.0, 0.75), vec3(0.75, 0.0, 0.0), vec3(0.0, 0.0, 0.75));
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    float A = uA.x;
    float env = uH.x >= 0.0 ? exp(-uH.x / max(uH.y, 1e-3)) : 0.0;                // Hit burst
    if (env < 0.01) env = 0.0;
    int mode = 0;                                                               // power_state
    float k = 0.0;
    if (uF.w >= 0.0) { if (uF.w < 1.0) { mode = 1; k = uF.w; } else { mode = 2; k = 1.0; } }
    else if (uF.y > uF.z) {
        float pp = (uF.x - uF.y) / max(uG.x, 1e-3);
        if (pp < 1.0) { mode = 1; k = max(pp, 0.0); } else if (uG.z > 0.5) { mode = 2; k = 1.0; }
    }
    else if (uF.z > -999.0 && uF.x - uF.z < uG.y) { mode = 3; k = max(0.0, (uF.x - uF.z) / max(uG.y, 1e-3)); }
    if (A <= 0.0 && env <= 0.0 && mode == 0) { TDImageStoreOutput(0, ivec3(p, 0), c0); return; }   // exact
    if (mode == 2) { TDImageStoreOutput(0, ivec3(p, 0), vec4(0.0, 0.0, 0.0, c0.a)); return; }      // TV off
    bool ay = uE.w > 0.5;
    ivec2 T = tdims(isz, ay);
    vec2 Tf = vec2(T);
    ivec2 tp = to_tape(p, isz, ay);
    float sx = 1.0, sy = 1.0, gain = 1.0, white = 0.0;                          // collapse / warmup
    if (mode == 1) {
        float ly = min(1.0, 4.0 / Tf.y);
        float dx = min(1.0, 8.0 / Tf.x);
        if (k < 0.5) { float e = ease(k / 0.5); sy = 1.0 + (ly - 1.0) * e; gain = 1.0 + (uG.w - 1.0) * e; white = e; }
        else if (k < 0.8) { float e = ease((k - 0.5) / 0.3); sy = ly; sx = 1.0 + (dx - 1.0) * e; gain = uG.w; white = 1.0; }
        else { sy = ly; sx = dx; gain = uG.w * (1.0 - (k - 0.8) / 0.2); white = 1.0; }
    } else if (mode == 3) {
        float sc = 0.55 + 0.45 * ease(k); sx = sc; sy = sc; gain = k * k;
    }
    vec2 d = vec2(tp) + 0.5 - 0.5 * Tf;                                          // px from the centre
    if (abs(d.x) > 0.5 * sx * Tf.x || abs(d.y) > 0.5 * sy * Tf.y) {
        TDImageStoreOutput(0, ivec3(p, 0), vec4(0.0, 0.0, 0.0, c0.a)); return;
    }
    vec2 q = 0.5 * Tf + d / vec2(sx, sy);                                        // picture position, px
    uint sdI = uint(max(uC.z, 0.0) + 0.5);
    uint sd = pcg(sdI + 0x51u);
    int ti = int(floor(uC.w * max(uC.y, 0.0)));                                  // Rate tick
    float roll = uB.z * A + uB.y * A * uC.w;                                     // V-hold (picture heights)
    if (hh(ivec2(ti, 1), sd + 9u) < uC.x * A) roll += (hh(ivec2(ti, 2), sd + 9u) - 0.5) * 0.2;
    roll += env * 0.1;
    float per = Tf.y * (1.0 + max(uB.w, 0.0));
    float yv = mod(q.y + roll * Tf.y, per);
    vec3 col = vec3(0.02);                                                        // blanking bar
    if (yv < Tf.y) {
        int ls = int(floor(yv));
        float off = uA.w * A * float(ls);                                        // H-hold drift (wraps)
        float tearP = clamp(uA.y * A + env, 0.0, 1.0);
        int b = int(floor(yv / Tf.y * 12.0 + hh(ivec2(ti, 4), sd)));
        if (hh(ivec2(b, ti), sd + 3u) < tearP) off += (hh(ivec2(b, ti), sd + 5u) * 2.0 - 1.0) * uA.z * max(A, env);
        off += uB.x * A * (hh(ivec2(ls, ti), sd + 7u) * 2.0 - 1.0);              // line jitter
        float ss = mod(q.x - off, Tf.x);
        ivec2 src = ivec2(clamp(int(floor(ss)), 0, T.x - 1), clamp(ls, 0, T.y - 1));
        vec4 a = texelFetch(sTD2DInputs[0], to_pix(src, isz, ay), 0);
        col = a.rgb;
        int im = int(uE.x + 0.5);
        if (im > 0 && A > 0.0) {
            vec4 ck = texelFetch(sTD2DInputs[2], ivec2(0), 0);
            bool fresh = ck.x - ck.y > 0.25;
            int fp = max(1, int(uE.y + 0.5));
            int field = (src.y / fp) & 1;
            int cur = int(mod(uH.z, 2.0));
            if (im == 1 && field != cur && !fresh) {                                // weave
                ivec2 s2 = ivec2(clamp(src.x - int(floor(uE.z * A + 0.5)), 0, T.x - 1), src.y);
                col = texelFetch(sTD2DInputs[1], to_pix(s2, isz, ay), 0).rgb;
            } else if (im == 2 && field != cur) {                                   // bob: the paired row of field cur
                int ry = clamp(((src.y / fp) ^ 1) * fp + (src.y % fp), 0, T.y - 1);
                col = texelFetch(sTD2DInputs[0], to_pix(ivec2(src.x, ry), isz, ay), 0).rgb;
            } else if (im == 3 && !fresh) {                                         // blend
                col = 0.5 * (a.rgb + texelFetch(sTD2DInputs[1], to_pix(src, isz, ay), 0).rgb);
            }
        }
    }
    int fr = int(mod(uH.z, 8192.0));
    float sn = hh(ivec2(tp.x / 2, tp.y + fr * 1931), sd + 13u);
    sn = mix(sn, hh(ivec2(tp.x / 9, tp.y + fr * 1931), sd + 17u), 0.4);          // horizontal streaks
    sn = min(sn * sn * 1.2, 1.0);
    int cm = int(uD.y + 0.5);
    vec3 card = cm == 0 ? uK.rgb : (cm == 1 ? vec3(sn) : (cm == 2 ? vec3(0.0)
                : BARS[clamp(int(floor(q.x / Tf.x * 7.0)), 0, 6)]));
    if (uD.w > 0.5) card = mix(card, vec3(1.0), texture(sTD2DInputs[3], (vec2(p) + 0.5) / vec2(isz)).a);
    col = mix(col, card, clamp(uD.x * A, 0.0, 1.0));
    col = mix(col, vec3(sn), clamp(uD.z * A + env * 0.5, 0.0, 1.0));
    col = mix(col, vec3(1.0), white * 0.85) * gain;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(max(col, vec3(0.0)), c0.a));
}
"""

SHADERS = {'fx': FX, 'stamp': _LG['STAMP']}

P = _LG['P']
UNIFORMS = {
    'fx': [('uA', [P.format('Amount'), P.format('Htear'), P.format('Tearsize'), P.format('Hslant')]),
           ('uB', [P.format('Hjitter'), P.format('Vroll'), P.format('Vpos'), P.format('Vbar')]),
           ('uC', [P.format('Vjump'), P.format('Rate'), P.format('Seed'), 'absTime.seconds']),
           ('uD', [P.format('Nosignal'), 'parent().par.Card.menuIndex', P.format('Snow'),
                   '1 if %s else 0' % P.format('Osd')]),
           ('uE', ['parent().par.Interlace.menuIndex', P.format('Fieldpitch'), P.format('Combshift'),
                   'parent().par.Lineaxis.menuIndex']),
           ('uF', ['absTime.seconds', P.format('Offtime'), P.format('Ontime'), P.format('Powerphase')]),
           ('uG', [P.format('Powerdur'), P.format('Warmup'), '1 if %s else 0' % P.format('Offhold'), P.format('Glow')]),
           ('uH', ['absTime.seconds - %s' % P.format('Hittime'), P.format('Hitdecay'), 'absTime.frame', '0']),
           ('uK', [P.format('Cardr'), P.format('Cardg'), P.format('Cardb'), '1'])],
}


def build(m, H):
    """Fill instance COMP m: in1 (+ cprev / prev_src, stamp, osd / osd_src) -> fx -> out_sel -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    _LG['pulse_exec'](m, H, {'Hit': ('Hittime', ''), 'Poweroff': ('Offtime', ''), 'Poweron': ('Ontime', '')})
    cp = mk(m, cacheTOP, 'cprev')
    cp.inputConnectors[0].connect(in1)
    cp.par.cachesize = 2
    cp.par.outputindex = -1
    cp.comment = 'Previous picture (Interlace weave / blend only; pulled only while prev_src selects it).'
    pv = mk(m, switchTOP, 'prev_src')
    pv.inputConnectors[0].connect(in1)
    pv.inputConnectors[1].connect(cp)
    expr(pv.par.index, "1 if parent().par.Interlace.eval() in ('weave', 'blend') else 0")
    st = _LG['stamp'](m, H)
    bl = mk(m, constantTOP, 'osd_blank')
    bl.par.outputresolution = 'custom'
    bl.par.resolutionw, bl.par.resolutionh = 1, 1
    bl.par.colorr = bl.par.colorg = bl.par.colorb = bl.par.alpha = 0
    bl.comment = '1x1 transparent: the OSD input while the OSD is off.'
    tx = mk(m, textTOP, 'osd')
    missing = _LG['setp'](tx, H, outputresolution='custom', resolutionw="=op('in1').width",
                          resolutionh="=op('in1').height", text='=parent().par.Osdtext.eval()', alignx='center',
                          aligny='center', fontsizex="=op('in1').height * 0.045", bgalpha=0)
    tx.comment = 'OSD text on the no-signal card (white on transparent). Missing pars on this build: %s' % (
        ' '.join(missing) or 'none')
    os_ = mk(m, switchTOP, 'osd_src')
    os_.inputConnectors[0].connect(bl)
    os_.inputConnectors[1].connect(tx)
    expr(os_.par.index, '1 if %s and %s > 0 else 0' % (P.format('Osd'), P.format('Nosignal')))
    fx = H['compute'](m, 'fx', FX, [in1, pv, st, os_])
    H['uniforms'](fx, UNIFORMS['fx'])
    fx.comment = 'Sync loss, V-hold, no-signal card, snow, interlace, power collapse / warm-up; one pass.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, _LG['signalloss_active_expr']())
    sel.comment = 'Amount 0, no Hit burst, power normal = in1 exact (fx not pulled).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulses', 'cprev', 'prev_src'],
         'body': 'Pulses Hit / Power off / Power on -> State times. cprev only for weave / blend.'},
        {'title': '2 Signal loss', 'role': 'process', 'ops': ['stamp', 'stamp_compute', 'osd_blank', 'osd', 'osd_src',
                                                              'fx', 'fx_compute'],
         'body': 'One compute pass: sync, V-hold, card + OSD, snow, interlace, power.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
