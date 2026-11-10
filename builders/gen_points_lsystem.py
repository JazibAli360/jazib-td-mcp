# gen_points_lsystem - GEN_points module 'lsystem' (FX5 G05): L-system curves and plants drawn as point dust. String
# rewriting + turtle run in Python inside the `aux` Script TOP ONLY when a rule / iteration / angle par changes (cached
# segment table, gen_points_logic.ls_*); the state pass spreads Count points evenly along the visible length (binary
# search on cumulative length), Jitter slides them along the lines each frame (Persist turns dots into lines). Growth:
# Progress (or Growspeed loop) by drawing order (pen) or by branch depth (trees grow outward). Sway bends with depth.
# Systems: Koch, snowflake, dragon, Hilbert, Gosper, Sierpinski arrowhead, plant, tree, bush (FX7 3.6, rule sets
# verified offline), or custom (Axiom + Rule1..3 strings). Shared effectors push / dissolve the dust (PXE_POINTS).
# Mirror: gen_points_logic.lsystem_* / ls_*. ASCII only.
_L = {}
exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/gen_points_logic.py').read(), _L)

MODULE = 'lsystem'
KIND = '2d'
BLURB = 'Rewriting + turtle (cached in Python) -> segment table; points spread along the visible length.'
SYSTEMS = _L['LS_NAMES']
COLORBY = ['depth', 'order', 'position', 'index']
EFFECTORS = 'points'
EPOCH = '0'

PAGES = [('Lsystem', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('System', 'Menu', 'plant', {'names': SYSTEMS, 'labels': ['Koch curve', 'Koch snowflake', 'Dragon', 'Hilbert',
                                                             'Gosper', 'Sierpinski arrowhead', 'Fractal plant',
                                                             'Tree', 'Bush', 'Custom (Axiom + rules)']}),
    ('Iterations', 'Int', 0, {'min': 0, 'max': 12, 'label': 'Iterations (0 = system default)'}),
    ('Angle', 'Float', 0.0, {'min': 0, 'max': 180, 'label': 'Turn angle deg (0 = system default)'}),
    ('Heading', 'Float', -1.0, {'min': -1, 'max': 360, 'label': 'Start heading deg (-1 = default)'}),
    ('Lengthdecay', 'Float', 1.0, {'min': 0.3, 'max': 1, 'label': 'Length x per bracket depth'}),
    ('Turnjitter', 'Float', 0.0, {'min': 0, 'max': 30, 'label': 'Turn jitter deg (natural plants)'}),
    ('Lseed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Jitter seed'}),
    ('Axiom', 'Str', 'F', {'label': 'Custom axiom'}),
    ('Rule1', 'Str', 'F=F[+F]F[-F]F', {'label': 'Custom rule 1 (X=...)'}),
    ('Rule2', 'Str', '', {'label': 'Custom rule 2'}),
    ('Rule3', 'Str', '', {'label': 'Custom rule 3'}),
    ('Drawsyms', 'Str', 'F', {'label': 'Custom draw symbols'}),
    ('Progress', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Growth progress'}),
    ('Growspeed', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Grow loop per s (0 = Progress)'}),
    ('Growmode', 'Menu', 'path', {'names': ['path', 'depth'], 'labels': ['Drawing order (pen)', 'Branch depth']}),
    ('Jitter', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Slide dots along lines per frame'}),
    ('Sway', 'Float', 0.0, {'min': 0, 'max': 0.5, 'label': 'Sway (x depth^2)'}),
    ('Swayspeed', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Sway speed'}),
    ('Worldsize', 'Float', 1.0, {'min': 0.1, 'max': 4, 'label': 'Size'}),
    ('Colorby', 'Menu', 'depth', {'names': COLORBY, 'labels': ['Branch depth', 'Drawing order', 'Position', 'Index']}),
])]
DEFAULTS = {'Count': 65536, 'Persist': 0.8, 'Tonemap': 0, 'Palette': 5, 'Exposure': 1.0}
PANEL_PAGES = ['Lsystem', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'plant grow', {'System': 6, 'Growmode': 1, 'Growspeed': 0.08, 'Sway': 0.06, 'Palette': 5, 'Count': 65536,
                       'Turnjitter': 4.0}),
    (2, 'dragon pen', {'System': 2, 'Growmode': 0, 'Growspeed': 0.05, 'Colorby': 1, 'Palette': 6, 'Count': 65536,
                       'Persist': 0.9}),
    (3, 'hilbert', {'System': 3, 'Colorby': 1, 'Palette': 2, 'Count': 65536, 'Persist': 0.85}),
    (4, 'snowflake fold', {'System': 1, 'Colorby': 2, 'Palette': 4, 'Fold': 3, 'Rotspeed': 6.0, 'Count': 65536}),
    (5, 'bush sway', {'System': 8, 'Growmode': 1, 'Sway': 0.12, 'Swayspeed': 0.5, 'Palette': 3, 'Count': 65536,
                      'Turnjitter': 6.0}),
]
UNIFORMS = [('uM0', ['{Progress}', '{Growmode#}', '{Jitter}', '{Sway}']),
            ('uM1', ['{Swayspeed}', '{Colorby#}', '{Worldsize}', '{Growspeed}'])]

AUX_SCRIPT = """# GEN_points lsystem segment table (builders/gen_points_lsystem.py; maths gen_points_logic.ls_*).
# Cooks only when the pars read below change (TD tracks them): expansion + turtle in Python, then one upload.
_LS = {}

def onSetupParameters(scriptOp):
	return

def onCook(scriptOp):
	import numpy as np
	if not _LS:
		exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/gen_points_logic.py').read(), _LS)
	m = scriptOp.parent()
	sysname = m.par.System.eval()
	ax, ru, an, it, dr, hd = _LS['ls_resolve'](sysname, m.par.Axiom.eval(), [m.par.Rule1.eval(), m.par.Rule2.eval(),
	                                           m.par.Rule3.eval()], m.par.Angle.eval(), m.par.Iterations.eval(),
	                                           m.par.Drawsyms.eval(), m.par.Heading.eval())
	S, D, used = _LS['ls_segments'](ax, ru, an, it, dr, hd, m.par.Lengthdecay.eval(), m.par.Turnjitter.eval(),
	                                m.par.Lseed.eval())
	scriptOp.copyNumpyArray(np.ascontiguousarray(_LS['ls_table'](S, D, used)))
	return
"""

STEP = """
vec4 ls_eval(int i) {
    vec4 h0 = texelFetch(GP_AUX, ivec2(0, 0), 0);
    vec4 h1 = texelFetch(GP_AUX, ivec2(1, 0), 0);
    int n = int(h0.x + 0.5);
    if (n < 1) return vec4(0.0);
    float total = h1.x, maxd = h1.y;
    float grow = uM1.w;
    float prog = grow <= 0.0 ? clamp(uM0.x, 0.0, 1.0) : min(fract(T * grow) * 1.2, 1.0);
    int mode = int(uM0.y + 0.5);
    float u01 = (float(i) + fract(rnd(i, 41u) + uM0.z * float(FR) * 0.618034)) / float(max(NPTS, 1));
    float Ls = u01 * total * (mode == 0 ? prog : 1.0);
    int lo = 0, hi = n - 1;
    for (int k = 0; k < 20; k++) {                       // largest j with cum[j] <= Ls
        if (lo >= hi) break;
        int mid = (lo + hi + 1) / 2;
        int q = 3 + 2 * mid;
        if (texelFetch(GP_AUX, ivec2(q % 1024, q / 1024), 0).z <= Ls) lo = mid; else hi = mid - 1;
    }
    int q0 = 2 + 2 * lo, q1 = 3 + 2 * lo;
    vec4 seg = texelFetch(GP_AUX, ivec2(q0 % 1024, q0 / 1024), 0);
    vec4 inf = texelFetch(GP_AUX, ivec2(q1 % 1024, q1 / 1024), 0);
    float t = clamp((Ls - inf.z) / max(inf.w, 1e-9), 0.0, 1.0);
    float vis = prog <= 0.0 ? 0.0 : 1.0;
    if (mode == 1 && t > clamp(prog * (maxd + 1.0) - inf.x, 0.0, 1.0)) vis = 0.0;
    vec2 p = mix(seg.xy, seg.zw, t);
    float dn = inf.x / max(maxd, 1.0);
    if (uM0.w != 0.0) p.x += uM0.w * h0.w * dn * dn * (pxNoise(vec3(T * uM1.x, inf.x * 0.37, 0.0), SEED) - 0.5) * 2.0;
    float sc = min(ASP, 1.0) * 0.95 * uM1.z / max(h0.w, 1e-6);
    vec3 P = vec3((p - h0.yz) * sc, 0.0);
#ifdef PXE_POINTS
    PXEFx fx = pxePointFx(P, float(i));
    P += fx.off;
    vis *= fx.alpha;
#endif
    int cb = int(uM1.y + 0.5);
    float k = cb == 0 ? dn : (cb == 1 ? inf.y : (cb == 2 ? u01 : rnd(i, 5u)));
    return vec4(P, packKA(k, vis));
}
vec4 pt_seed(int i) { return ls_eval(i); }
vec4 pt_step(int i, vec4 s, float dt) { if (dt <= 0.0) return s; return ls_eval(i); }
"""

PLACE = """
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    P = s.xyz;
    float a = unpackA(s.w);
    C = vec4(ptpal(unpackK(s.w)), a);
    return a > 0.0;
}
"""
