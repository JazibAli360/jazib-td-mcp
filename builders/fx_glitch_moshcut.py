# fx_glitch_moshcut - FX_glitch module 'moshcut' (FX1 DG-02 mosh transition A -> B).
# A = the rack chain (in1), B = a second picture (test clip or any TOP path). When the transition starts the decoded
# state S takes A's last frame; then B's motion (block match on B) drags A's texture, B's residual paints B's edges on
# it, and blocks refresh to B in an order (noise / top-down / bottom-up / radial / luma) as Progress rises; Progress 1
# = B exactly (out_sel picks B). Progress 0 = A exactly (out_sel picks in1; nothing else cooks). Drive: the Progress
# slider (MIDI/cue) or Go pulse + Duration. Engine shared with fx_glitch_mosh.py (exec'd here; its only other user).
# Template: docs/builds/fx_glitch.md; doc: docs/builds/fx_glitch.md (Module mosh / moshcut). ASCII only.
import os

MODULE = 'moshcut'
_HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
B_TEST = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/clips/tl_testsrc2_30fps_8s.mp4'
ORDERS = ['noise', 'topdown', 'bottomup', 'radial', 'luma']
CMODES = ['hard', 'soft', 'bloom']

PAGES = [
    ('Moshcut', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Progress', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Progress A -> B'}),
        ('Drive', 'Menu', 'manual', {'names': ['manual', 'go'], 'labels': ['Progress slider', 'Go pulse + Duration']}),
        ('Go', 'Pulse', None, {'label': 'Go'}),
        ('Duration', 'Float', 2.0, {'min': 0.1, 'max': 8, 'label': 'Duration s'}),
        ('Melt', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Melt (drag-only part)'}),
        ('Order', 'Menu', 'noise', {'names': ORDERS, 'labels': ['Noise blocks', 'Top down', 'Bottom up',
                                                                'Radial', 'Luma (bright first)']}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Radial centre x'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Radial centre y'}),
        ('Cutmode', 'Menu', 'hard', {'names': CMODES, 'labels': ['Hard blocks', 'Soft (fluid)', 'Bloom (latched)']}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Gain (MV x)'}),
        ('Bloomgain', 'Float', 2.0, {'min': 0, 'max': 8, 'label': 'Bloom gain'}),
        ('Minmag', 'Float', 0.5, {'min': 0, 'max': 8, 'label': 'Min motion px'}),
        ('Residual', 'Float', 0.4, {'min': 0, 'max': 1.5, 'label': 'Residual (B edges)'}),
        ('Decay', 'Float', 0.0, {'min': 0, 'max': 0.2, 'label': 'Decay (leak to B)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Estimator', [
        ('Estres', 'Menu', 'half', {'names': ['full', 'half', 'quarter'],
                                    'labels': ['Full (8 px blocks)', 'Half (16 px)', 'Quarter (32 px)']}),
        ('Range', 'Int', 8, {'min': 1, 'max': 16, 'label': 'Search +- px'}),
        ('Penalty', 'Float', 0.01, {'min': 0, 'max': 0.2, 'label': 'MV length penalty'}),
    ]),
    ('B', [
        ('Bsource', 'Menu', 'test', {'names': ['test', 'top'], 'labels': ['Test clip', 'TOP path (Btop)']}),
        ('Btop', 'Str', '', {'label': 'B TOP path'}),
        ('Gotime', 'Float', -1.0, {'min': -1, 'max': 1, 'label': 'Go time (internal)'}),
    ]),
]
PANEL_PAGES = ['Moshcut', 'Estimator']

PRESETS = [
    (1, 'drop cut', {'Amount': 1.0, 'Drive': 1, 'Duration': 1.5, 'Melt': 0.5, 'Order': 0, 'Cutmode': 0,
                     'Gain': 1.0, 'Residual': 0.4}),
    (2, 'slow melt', {'Amount': 1.0, 'Drive': 1, 'Duration': 4.0, 'Melt': 0.7, 'Order': 0, 'Cutmode': 1,
                      'Gain': 1.0, 'Residual': 0.0}),
    (3, 'radial', {'Amount': 1.0, 'Drive': 1, 'Duration': 2.0, 'Melt': 0.3, 'Order': 3, 'Cutmode': 0,
                   'Centerx': 0.5, 'Centery': 0.5, 'Residual': 0.4}),
    (4, 'bloom wipe', {'Amount': 1.0, 'Drive': 1, 'Duration': 2.5, 'Melt': 0.4, 'Order': 1, 'Cutmode': 2,
                       'Bloomgain': 2.0, 'Residual': 0.3}),
]

STAMP = """// stamp (3x1 rgba32float in place, one invocation) for moshcut.
// texel0 = (now, previous cook's now, 0, latch); texel1 = (progress, -, -, init: S = A); texel2 = (-, -, since init).
// Init = a gap > 0.25 s since the last cook (out_sel showed A, nothing cooked) or Progress leaving 0.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;   // now, progress, cut mode (0 hard 1 soft 2 bloom)
void main() {
    if (gl_GlobalInvocationID.x != 0u || gl_GlobalInvocationID.y != 0u) return;
    vec4 a = TDImageLoadOutput(0, ivec3(0, 0, 0));
    vec4 b = TDImageLoadOutput(0, ivec3(1, 0, 0));
    vec4 c = TDImageLoadOutput(0, ivec3(2, 0, 0));
    float now = uT.x;
    if (a.x == now) return;                     // a second cook in the same frame: keep
    float pn = a.x;
    bool fresh = (now - pn) > 0.25 || pn <= 0.0 || (uT.y > 0.0 && b.x <= 0.0);
    float since = fresh ? 0.0 : c.z + 1.0;
    float latch = (int(uT.z + 0.5) == 2 && since >= 2.0) ? 1.0 : 0.0;
    TDImageStoreOutput(0, ivec3(0, 0, 0), vec4(now, pn, 0.0, latch));
    TDImageStoreOutput(0, ivec3(1, 0, 0), vec4(uT.y, 0.0, 0.0, fresh ? 1.0 : 0.0));
    TDImageStoreOutput(0, ivec3(2, 0, 0), vec4(0.0, 0.0, since, 0.0));
}
"""

PULSES = """# moshcut: Go pulse -> Gotime = now (Drive go runs Progress 0 -> 1 over Duration)
def onPulse(par):
\tif par.name == 'Go':
\t\tpar.owner.par.Gotime = absTime.seconds
\treturn
"""

P = "parent().par.{}.eval()"
PE = ("(parent().par.Progress.eval() if parent().par.Drive.eval() == 'manual' else (0.0 if parent().par.Gotime.eval() "
      "< 0 else min(1.0, max(0.0, (absTime.seconds - parent().par.Gotime.eval()) / "
      "max(parent().par.Duration.eval(), 0.001)))))")


def _engine():
    ns = dict(globals())
    exec(open(os.path.join(_HERE, 'fx_glitch_mosh.py')).read(), ns)
    return ns


def build(m, H):
    E = _engine()
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    bt = mk(m, moviefileinTOP, 'b_test')
    bt.par.file = B_TEST
    expr(bt.par.play, "parent().par.Bsource.eval() == 'test'")
    bt.comment = 'B test clip (testsrc2, moving); plays only while Bsource = test.'
    bs = mk(m, selectTOP, 'b_sel')
    expr(bs.par.top, "parent().par.Btop.eval() or 'b_test'")
    bs.comment = 'B from any TOP path (Btop).'
    bw = mk(m, switchTOP, 'b_src')
    bw.inputConnectors[0].connect(bt)
    bw.inputConnectors[1].connect(bs)
    expr(bw.par.index, 'parent().par.Bsource.menuIndex')
    bf = mk(m, fitTOP, 'b_fit')
    bf.inputConnectors[0].connect(bw)
    bf.par.outputresolution = 'custom'
    expr(bf.par.resolutionw, "op('in1').width")
    expr(bf.par.resolutionh, "op('in1').height")
    bf.par.fit = 'fitoutside'
    bf.comment = 'B filled to A (in1) size, so S, A and B share one grid.'
    E['pulses'](m, H, PULSES)
    thr = "max(0.0, min(1.0, ({pe} - {melt}) / max(1.0 - {melt}, 0.001)))".format(pe=PE, melt=P.format('Melt'))
    cm = 'parent().par.Cutmode.menuIndex'
    upd, mv, eops = E['engine'](
        m, H, bf, 'in1', STAMP,
        [('uT', ['absTime.seconds', PE, cm, '0'])],
        [('uA', [P.format('Gain'), P.format('Bloomgain'), P.format('Minmag'), P.format('Residual')]),
         ('uB', [P.format('Decay'), '1 if %s == 1 else 0' % cm, '1 if %s == 1 else 0' % cm, E['SCALE']]),
         ('uC', [thr, 'parent().par.Order.menuIndex', '0', P.format('Seed')]),
         ('uD', [P.format('Centerx'), P.format('Centery'), '0', '0'])])
    sel = ("0 if {a} <= 0 or {pe} <= 0 else (2 if {pe} >= 1 and {a} >= 1 else 1)"
           .format(a=P.format('Amount'), pe=PE))
    oops = E['fx_out'](m, H, in1, upd, mv, P.format('Amount'), '0', sel, extra=[bf])
    return [
        {'title': '1 A + B', 'role': 'input', 'ops': ['in1', 'b_test', 'b_sel', 'b_src', 'b_fit', 'pulses'],
         'body': 'A = in1 (rack chain), B = test clip or Btop, fitted to A. Pulses: Go -> Gotime.'},
        {'title': '2 Engine on B', 'role': 'process', 'ops': eops,
         'body': 'S starts as A; B motion drags it; blocks refresh to B by Order as Progress passes Melt.'},
        {'title': '3 Out', 'role': 'output', 'ops': oops, 'body': 'Progress 0 = A exact, 1 = B exact (out_sel).'},
    ]
