# fx_time_ring - the piece the FX_glitch time modules 'timedisplace' and 'timeshuffle' share (2 real users today,
# so it exists; no-bloat rule, CLAUDE.md). Not a module (no MODULE): each of the two module files execs it.
# Chain (FX6 probe 4b: native ring, no Cache TOP, ~0.35 ms):
#   in1 -> ring (texture3dTOP, cachesize = Depth, input format, full or half res)
#       -> tmachine (timemachineTOP: ring on input 0, the module's map on input 1, blackoffset -(Depth-1) indices,
#          whiteoffset 0, depthoffset; output = in1 size) -> out_sw (Switch: Amount 0 = in1, exact) -> out1
#   stamp (1x1 rgba32float, readwrite): x now, y previous cook, z cooks since the ring restarted, w ring key.
#   map (module compute shader, rgba32float, readwrite): grey m = 1 - (offset+1)/Depth (T-122), offset clamped to z, so a
#   restarted ring (slot bypassed > 0.25 s, Depth or Quality changed) never shows stale or empty slices.
# Run inside TD only through the rack (builders/fx_glitch.py). ASCII only.

GLSL_HASH = """uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
float h(uvec4 k) { return float(pcg(k.x ^ pcg(k.y ^ pcg(k.z ^ pcg(k.w)))) >> 8) / 16777215.0; }
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
"""

STAMP_RING = """// stamp (T-111 + count): 1x1 rgba32float in place. x now, y previous cook's now, z cooks since the ring
// restarted, w ring key. Restart = gap > 0.25 s (slot bypassed / Amount 0: the ring stopped recording), time went
// back, or the key changed (Depth / Quality: TD reallocates the ring).
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;   // now key
void main() {
    vec4 s = TDImageLoadOutput(0, ivec3(0));
    bool fresh = uT.x - s.x > 0.25 || uT.x < s.x || abs(s.w - uT.y) > 0.5;
    TDImageStoreOutput(0, ivec3(0), vec4(uT.x, s.x, fresh ? 0.0 : s.z + 1.0, uT.y));
}
"""

DEPTH = 'max(2, int(parent().par.Depth.eval()))'
HALF = "(0.5 if parent().par.Quality.eval() == 'half' else 1.0)"
RING_PAR = ('Quality', 'Menu', 'full', {'names': ['full', 'half'],
                                        'labels': ['Full res ring', 'Half res ring (1/4 VRAM)']})


def map_size_exprs(scale='1.0'):
    """Python expressions for the map's width / height (also its size uniforms)."""
    return ("max(1, int(op('in1').width * %s))" % scale, "max(1, int(op('in1').height * %s))" % scale)


def build_ring(m, H, map_text, map_uniforms, map_scale='1.0', map_src=None, title='2 Time'):
    """Fill instance COMP m with the shared ring chain around the module's map shader. Returns the stage plan."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    ring = mk(m, texture3dTOP, 'ring')
    ring.inputConnectors[0].connect(in1)
    ring.par.type = 'texture3d'
    expr(ring.par.cachesize, DEPTH)
    ring.par.step = 1
    ring.par.outputresolution = 'custom'
    expr(ring.par.resolutionw, "max(1, int(op('in1').width * %s))" % HALF)
    expr(ring.par.resolutionh, "max(1, int(op('in1').height * %s))" % HALF)
    ring.par.format = 'useinput'
    ring.comment = 'Frame ring: Depth slices (VRAM = W*H*4*Depth at full, 1/4 at half). Records only while pulled.'
    st = H['compute'](m, 'stamp', STAMP_RING, [], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    H['uniforms'](st, [('uT', ['absTime.seconds',
                               "%s * 4 + (1 if parent().par.Quality.eval() == 'half' else 0)" % DEPTH, '0', '0'])])
    st.comment = 'Cook counter: z = cooks since the ring restarted; the map clamps offsets to it (no stale slices).'
    ins = [in1, map_src if map_src is not None else in1, st]
    mp = H['compute'](m, 'map', map_text, ins, fmt='rgba32float')
    mw, mh = map_size_exprs(map_scale)
    expr(mp.par.resolutionw, mw)
    expr(mp.par.resolutionh, mh)
    mp.par.outputaccess = 'readwrite'                   # Smooth reads the previous map in place
    mp.par.clearoutputs = False
    H['uniforms'](mp, map_uniforms)
    mp.comment = 'Time map (grey: 1 = now, 0 = Depth-1 cooks ago), clamped to what the ring holds.'
    tm = mk(m, timemachineTOP, 'tmachine')
    tm.inputConnectors[0].connect(ring)
    tm.inputConnectors[1].connect(mp)
    expr(tm.par.blackoffset, '-(%s - 1)' % DEPTH)
    tm.par.blackoffsetunit = 'indices'
    tm.par.whiteoffset = 0
    tm.par.whiteoffsetunit = 'indices'
    tm.par.samplemode = 'depthoffset'
    tm.par.outputresolution = 'custom'
    expr(tm.par.resolutionw, "op('in1').width")
    expr(tm.par.resolutionh, "op('in1').height")
    tm.comment = 'Per-pixel time offset: map white = now, black = Depth-1 ring slices ago (interpolated).'
    sw = mk(m, switchTOP, 'out_sw')
    sw.inputConnectors[0].connect(in1)
    sw.inputConnectors[1].connect(tm)
    expr(sw.par.index, '1 if parent().par.Amount.eval() > 0 else 0')
    sw.comment = 'Amount 0 = in1 exactly (ring not pulled; it restarts cleanly when Amount comes back).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sw)
    pre = [n for n in ('map_sel',) if m.op(n) is not None]
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1'] + pre},
        {'title': title, 'role': 'process', 'ops': ['ring', 'stamp', 'stamp_compute', 'map', 'map_compute', 'tmachine'],
         'body': 'ring (Texture 3D) + map (compute) -> Time Machine; stamp counts cooks so offsets never pass the ring.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sw', 'out1']},
    ]
