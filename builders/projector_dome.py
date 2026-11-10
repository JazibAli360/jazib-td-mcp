# projector_dome builder - upgrades /project1/lab/LK_projection_room into a projector planner + fulldome mode.
# Specs: docs/research/AT_projector_coverage.md (section 3 formulas, 6 recipe) and AW_fulldome_simulator.md
# (section 5 maths, 7 Domemode). Our own clean-room design; ideas credited in the COMP comment: asterix
# "Projector Coverage Tool" (par vocabulary only, never obtained), Theinfranet "Fulldome Simulator" (never loaded).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/projector_dome.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set, custom par values kept. Keeps the original in/out
# architecture (content_in -> ... -> out -> room_out), the Room page and its par meanings, and the stage plan.
# T-70 safe: nothing destroyed directly (_sd = safe_destroy), the COMP's controls_window is closed before a
# rebuild (zkit reopens it if it was open), the panel container is never destroyed, the pane is never moved here.
# GLSL: canvas / hud / domemaster are compute TOPs (T-46/T-47); the view / probe / dome shaders are GLSL MATs.
# No limits or warnings: the operator decides. ASCII only.

NAME = 'LK_projection_room'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
LOGIC_FILE = REPO + '/builders/projector_dome_logic.py'
ZKIT_FILE = REPO + '/builders/zkit.py'
RIG = "op('rig')"

# ------------------------------------------------------------------ shaders
CANVAS = """// canvas: projector image (content fitted to the native aspect, or a test chart) placed inside the
// padded light map (lens shift, see pd_logic.canvas). ONE compute pass. in0 = content.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uRect;   // u0 v0 u1 v1 of the image inside the map
uniform vec4 uFit;    // fit (0 fit, 1 fill, 2 stretch), native aspect w/h, test chart (0/1), 0
vec3 chart(vec2 u, float na, vec2 px)
{
\t// own test chart: grey, 16 square cells across, white border + centre cross, circle (round = aspect right),
\t// corner squares: bottom left blue, bottom right yellow, top left red, top right green
\tvec2 q = u * px;                                                  // image pixels
\tfloat cell = px.x / 16.0;
\tvec2 g = abs(fract(q / cell + 0.5) - 0.5) * cell;                  // distance to the nearest grid line (px)
\tvec3 c = vec3(0.22);
\tif (min(g.x, g.y) < 1.5) c = vec3(0.85);
\tvec2 e = min(q, px - q);
\tif (min(e.x, e.y) < 4.0) c = vec3(1.0);
\tvec2 cc = abs(q - 0.5 * px);
\tfloat arm = 0.08 * px.y;
\tif ((cc.x < 2.0 && cc.y < arm) || (cc.y < 2.0 && cc.x < arm)) c = vec3(1.0);
\tif (abs(length(q - 0.5 * px) - 0.4 * px.y) < 2.0) c = vec3(1.0);
\tfloat s = 0.1 * px.y;
\tif (q.x < s && q.y < s) c = vec3(0.1, 0.3, 1.0);
\tif (q.x > px.x - s && q.y < s) c = vec3(1.0, 0.85, 0.1);
\tif (q.x < s && q.y > px.y - s) c = vec3(1.0, 0.15, 0.1);
\tif (q.x > px.x - s && q.y > px.y - s) c = vec3(0.1, 0.9, 0.2);
\treturn c;
}
void main()
{
\tivec2 p = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (p.x >= res.x || p.y >= res.y) return;
\tvec2 cuv = (vec2(p) + 0.5) / vec2(res);
\tvec2 sz = uRect.zw - uRect.xy;
\tvec2 iu = (cuv - uRect.xy) / sz;
\tvec4 col = vec4(0.0, 0.0, 0.0, 1.0);
\tif (all(greaterThanEqual(iu, vec2(0.0))) && all(lessThanEqual(iu, vec2(1.0)))) {
\t\tvec2 ipx = vec2(res) * sz;                                    // image size in map pixels
\t\tif (uFit.z > 0.5) col = vec4(chart(iu, uFit.y, ipx), 1.0);
\t\telse {
\t\t\tvec2 ts = vec2(textureSize(sTD2DInputs[0], 0));
\t\t\tfloat ca = ts.x / max(ts.y, 1.0), na = uFit.y;
\t\t\tvec2 q = iu;
\t\t\tint fm = int(uFit.x + 0.5);
\t\t\tif (fm == 0) { if (ca > na) q.y = (iu.y - 0.5) * ca / na + 0.5; else q.x = (iu.x - 0.5) * na / ca + 0.5; }
\t\t\telse if (fm == 1) { if (ca > na) q.x = (iu.x - 0.5) * na / ca + 0.5; else q.y = (iu.y - 0.5) * ca / na + 0.5; }
\t\t\tif (all(greaterThanEqual(q, vec2(0.0))) && all(lessThanEqual(q, vec2(1.0)))) {
\t\t\t\tvec4 s = texture(sTD2DInputs[0], q);
\t\t\t\tcol = vec4(s.rgb, 1.0);
\t\t\t}
\t\t}
\t}
\tTDImageStoreOutput(0, ivec3(p, 0), TDOutputSwizzle(col));
}
"""

MAT_VERT = """// world position + world normal for the analysis shaders
out Vert { vec3 wpos; vec3 wnorm; vec3 opos; } oVert;
void main()
{
\tvec4 worldSpacePos = TDDeform(P);
\tgl_Position = TDWorldToProj(worldSpacePos);
#ifndef TD_PICKING_ACTIVE
\toVert.wpos = worldSpacePos.xyz;
\toVert.wnorm = normalize(TDDeformNorm(N));
\toVert.opos = P;
#else
\tTDWritePickingValues();
#endif
}
"""

PROBE_COMMON = """uniform vec4 uProj[12];   // 6 vec4 per projector (A, B): pos+on, R, U, F, (T resx resy lumens), (sh sv gain 0)
struct Hit { float cov; float ppm; float lux; float d; vec2 uv; };
// pinhole projector, uniform pixels in tan space; same maths as pd_logic.probe_point (tests: test_projector_dome.py)
Hit probeP(int i, vec3 W, vec3 n)
{
\tHit h = Hit(0.0, 0.0, 0.0, 0.0, vec2(-1.0));
\tvec4 pa = uProj[i * 6];
\tif (pa.w < 0.5) return h;
\tvec3 R = uProj[i * 6 + 1].xyz, U = uProj[i * 6 + 2].xyz, F = uProj[i * 6 + 3].xyz;
\tvec4 prm = uProj[i * 6 + 4], sh = uProj[i * 6 + 5];
\tvec3 v = W - pa.xyz;
\tfloat d = length(v), z = dot(v, F);
\th.d = d;
\tif (z <= 1e-4) return h;
\tfloat T = prm.x, ar = prm.y / prm.z;
\tvec2 uv = vec2(dot(v, R) / z * T + 0.5 - sh.x, dot(v, U) / z * T * ar + 0.5 - sh.y);
\th.uv = uv;
\tif (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) return h;
\tfloat cn = dot(n, -v / d);
\tif (cn <= 0.0) return h;
\tfloat cf = z / d;
\th.cov = 1.0;
\th.ppm = T * prm.y * cn / (d * cf * cf);
\th.lux = prm.w * T * T * ar * cn / (d * d * cf * cf * cf);
\treturn h;
}
"""

PROBE_PIXEL = PROBE_COMMON + """uniform vec4 uSel;      // x = projector index (0 A, 1 B)
in Vert { vec3 wpos; vec3 wnorm; vec3 opos; } iVert;
layout(location = 0) out vec4 fragColor;
void main()
{
\tTDCheckDiscard();
\tvec3 n = normalize(iVert.wnorm);
\tif (!gl_FrontFacing) n = -n;
\tHit h = probeP(int(uSel.x + 0.5), iVert.wpos, n);
\t// r = px per metre (0 off-image), g = distance (occlusion map), b = mm per pixel (max = coarsest), a = covered
\tfragColor = vec4(h.ppm, h.d, h.cov > 0.5 && h.ppm > 0.0 ? 1000.0 / h.ppm : 0.0, h.cov);
}
"""

VIEW_PIXEL = PROBE_COMMON + """uniform vec4 uView;     // mode (1 coverage, 2 pixel density, 3 brightness, 4 overlap), max ppi, max nits, shadows
uniform vec4 uView2;    // shadow bias (fraction of distance), 0, 0, 0
uniform sampler2D sDepthA;
uniform sampler2D sDepthB;
in Vert { vec3 wpos; vec3 wnorm; vec3 opos; } iVert;
layout(location = 0) out vec4 fragColor;
// Turbo colormap, polynomial fit by Ruofei Du / Google (Apache-2.0), used here for the heat views
vec3 turbo(float x)
{
\tx = clamp(x, 0.0, 1.0);
\tvec4 v4 = vec4(1.0, x, x * x, x * x * x);
\tvec2 v2 = v4.zw * v4.z;
\treturn vec3(dot(v4, vec4(0.13572138, 4.61539260, -42.66032258, 132.13108234)) + dot(v2, vec2(-152.94239396, 59.28637943)),
\t            dot(v4, vec4(0.09140261, 2.19418839, 4.84296658, -14.18503333)) + dot(v2, vec2(4.27729857, 2.82956604)),
\t            dot(v4, vec4(0.10667330, 12.64194608, -60.58204836, 110.36276771)) + dot(v2, vec2(-89.90310912, 27.34824973)));
}
float shadowed(int i, Hit h)
{
\tif (uView.w < 0.5 || h.cov < 0.5) return 0.0;
\tfloat ds = (i == 0) ? texture(sDepthA, h.uv).g : texture(sDepthB, h.uv).g;
\treturn (ds > 0.0 && h.d > ds * (1.0 + uView2.x) + 0.01) ? 1.0 : 0.0;
}
void main()
{
\tTDCheckDiscard();
\tvec3 n = normalize(iVert.wnorm);
\tif (!gl_FrontFacing) n = -n;
\tfloat cnt = 0.0, ppm = 0.0, nit = 0.0, ca = 0.0, cb = 0.0;
\tfor (int i = 0; i < 2; i++) {
\t\tHit h = probeP(i, iVert.wpos, n);
\t\tif (shadowed(i, h) > 0.5) continue;
\t\tif (h.cov < 0.5) continue;
\t\tcnt += 1.0;
\t\tif (i == 0) ca = 1.0; else cb = 1.0;
\t\tppm = max(ppm, h.ppm);
\t\tnit += h.lux * uProj[i * 6 + 5].z / 3.14159265;
\t}
\tint mode = int(uView.x + 0.5);
\tvec3 col = vec3(0.08);
\tif (mode == 1) {
\t\tif (cnt > 0.5) col = ca > 0.5 && cb > 0.5 ? vec3(0.95) : (ca > 0.5 ? vec3(0.1, 0.75, 0.7) : vec3(0.85, 0.2, 0.75));
\t} else if (mode == 2) {
\t\tif (cnt > 0.5) col = turbo(1.0 - clamp(ppm / 39.37007874 / max(uView.y, 1e-6), 0.0, 1.0) * 0.9 - 0.05);
\t} else if (mode == 3) {
\t\tif (cnt > 0.5) col = turbo(clamp(nit / max(uView.z, 1e-6), 0.0, 1.0) * 0.9 + 0.05);
\t} else {
\t\tint k = int(cnt + 0.5);
\t\tcol = k == 0 ? vec3(0.08) : (k == 1 ? vec3(0.15, 0.7, 0.25) : (k == 2 ? vec3(1.0, 0.65, 0.1) : vec3(0.95, 0.15, 0.1)));
\t}
\tfloat shade = 0.65 + 0.35 * abs(dot(n, normalize(vec3(0.35, 0.8, 0.5))));
\tfragColor = TDOutputSwizzle(vec4(col * shade, 1.0));
}
"""

HUD = """// hud: audience view + legend bar + readout text (in1 = hud_text, white on transparent). ONE compute pass.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uHud;   // view mode (0 lit .. 4 overlap), show hud, 0, 0
vec3 turbo(float x)
{
\tx = clamp(x, 0.0, 1.0);
\tvec4 v4 = vec4(1.0, x, x * x, x * x * x);
\tvec2 v2 = v4.zw * v4.z;
\treturn vec3(dot(v4, vec4(0.13572138, 4.61539260, -42.66032258, 132.13108234)) + dot(v2, vec2(-152.94239396, 59.28637943)),
\t            dot(v4, vec4(0.09140261, 2.19418839, 4.84296658, -14.18503333)) + dot(v2, vec2(4.27729857, 2.82956604)),
\t            dot(v4, vec4(0.10667330, 12.64194608, -60.58204836, 110.36276771)) + dot(v2, vec2(-89.90310912, 27.34824973)));
}
void main()
{
\tivec2 p = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (p.x >= res.x || p.y >= res.y) return;
\tvec4 c = texelFetch(sTD2DInputs[0], p, 0);
\tif (uHud.y > 0.5) {
\t\tvec2 uv = (vec2(p) + 0.5) / vec2(res);
\t\tint mode = int(uHud.x + 0.5);
\t\tvec2 b0 = vec2(0.02, 0.03), b1 = vec2(0.42, 0.06);
\t\tif (all(greaterThanEqual(uv, b0)) && all(lessThanEqual(uv, b1))) {
\t\t\tfloat t = (uv.x - b0.x) / (b1.x - b0.x);
\t\t\tif (mode == 2) c.rgb = turbo(1.0 - t * 0.9 - 0.05);
\t\t\telse if (mode == 3) c.rgb = turbo(t * 0.9 + 0.05);
\t\t\telse if (mode == 4) c.rgb = t < 0.25 ? vec3(0.08) : (t < 0.5 ? vec3(0.15, 0.7, 0.25) : (t < 0.75 ? vec3(1.0, 0.65, 0.1) : vec3(0.95, 0.15, 0.1)));
\t\t\telse if (mode == 1) c.rgb = t < 0.25 ? vec3(0.08) : (t < 0.5 ? vec3(0.1, 0.75, 0.7) : (t < 0.75 ? vec3(0.85, 0.2, 0.75) : vec3(0.95)));
\t\t}
\t\tif (uv.x < 0.8 && uv.y > 0.7) {                                // text block (top left): shadow + text
\t\t\tivec2 ts = textureSize(sTD2DInputs[1], 0);
\t\t\tfloat sh = 0.0;
\t\t\tfor (int j = -2; j <= 2; j++) for (int k = -2; k <= 2; k++)
\t\t\t\tsh = max(sh, texelFetch(sTD2DInputs[1], clamp(p + ivec2(j, k), ivec2(0), ts - 1), 0).a);
\t\t\tvec4 tx = texelFetch(sTD2DInputs[1], clamp(p, ivec2(0), ts - 1), 0);
\t\t\tc.rgb = c.rgb * (1.0 - 0.7 * sh) * (1.0 - tx.a) + tx.rgb;
\t\t}
\t}
\tTDImageStoreOutput(0, ivec3(p, 0), vec4(c.rgb, 1.0));
}
"""

DOMEMASTER = """// domemaster: square azimuthal-equidistant fisheye (zenith centre, front of the dome at the bottom, +X right)
// from flat / domemaster / equirect content or the room's fisheye render. ONE compute pass. in0 = dome_src.
// Maths = pd_logic.dome_dir / tilt_dir / window_uv / equirect_uv (tests: test_projector_dome.py).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uDome;  // format (0 flat, 1 domemaster, 2 equirect, 3 scene), fov deg, tilt deg, circle mask
uniform vec4 uWin;   // flat window: azimuth, elevation, half width, half height (deg)
uniform vec4 uTpl;   // template on, template opacity, 0, 0
void main()
{
\tivec2 p = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (p.x >= res.x || p.y >= res.y) return;
\tvec2 uv = (vec2(p) + 0.5) / vec2(res);
\tvec2 q = uv * 2.0 - 1.0;
\tfloat r = length(q);
\tint fmt = int(uDome.x + 0.5);
\tvec4 col = vec4(0.0, 0.0, 0.0, 1.0);
\tfloat halfA = radians(uDome.y) * 0.5;
\tif (fmt == 1 || fmt == 3) col = vec4(texture(sTD2DInputs[0], uv).rgb, 1.0);
\telse if (r <= 1.0) {
\t\tfloat th = r * halfA, ph = atan(q.y, q.x);
\t\tvec3 d = vec3(sin(th) * cos(ph), cos(th), sin(th) * sin(ph));
\t\tfloat a = radians(uDome.z), c = cos(a), s = sin(a);
\t\td = vec3(d.x, c * d.y + s * d.z, -s * d.y + c * d.z);
\t\tif (fmt == 0) {
\t\t\tfloat az = degrees(atan(d.x, -d.z)) - uWin.x;
\t\t\taz = mod(az + 180.0, 360.0) - 180.0;
\t\t\tfloat el = degrees(asin(clamp(d.y, -1.0, 1.0))) - uWin.y;
\t\t\tvec2 w = 0.5 + 0.5 * vec2(az / max(uWin.z, 1e-3), el / max(uWin.w, 1e-3));
\t\t\tif (all(greaterThanEqual(w, vec2(0.0))) && all(lessThanEqual(w, vec2(1.0))))
\t\t\t\tcol = vec4(texture(sTD2DInputs[0], w).rgb, 1.0);
\t\t} else {
\t\t\tfloat lon = atan(d.x, -d.z), lat = asin(clamp(d.y, -1.0, 1.0));
\t\t\tcol = vec4(texture(sTD2DInputs[0], vec2(lon / 6.28318531 + 0.5, lat / 3.14159265 + 0.5)).rgb, 1.0);
\t\t}
\t}
\tif (uTpl.x > 0.5 && r <= 1.0) {
\t\tfloat px = 2.0 / float(res.x);                                   // one pixel in q units
\t\tfloat deg = r * uDome.y * 0.5;                                    // zenith angle of this pixel
\t\tfloat ring = 0.0;
\t\tfor (int k = 1; k <= 6; k++) {
\t\t\tfloat rk = (30.0 * float(k)) / (uDome.y * 0.5);
\t\t\tif (rk <= 1.0001) ring = max(ring, 1.0 - smoothstep(0.0, 1.5 * px, abs(r - rk)));
\t\t}
\t\tfloat ang = degrees(atan(q.y, q.x));
\t\tfloat sp = abs(mod(ang + 15.0, 30.0) - 15.0) * radians(1.0) * r;  // distance to the nearest 30 deg spoke
\t\tfloat spoke = (1.0 - smoothstep(0.0, 1.5 * px, sp)) * step(0.02, r);
\t\tfloat front = (1.0 - smoothstep(0.0, 2.5 * px, abs(q.x))) * step(q.y, 0.0);   // front spoke (bottom) in red
\t\tvec3 tc = front > 0.0 ? vec3(1.0, 0.2, 0.15) : vec3(1.0);
\t\tcol.rgb = mix(col.rgb, tc, clamp(max(max(ring, spoke), front) * uTpl.y, 0.0, 1.0));
\t}
\tif (uDome.w > 0.5 && r > 1.0) col = vec4(0.0, 0.0, 0.0, 1.0);
\tTDImageStoreOutput(0, ivec3(p, 0), TDOutputSwizzle(col));
}
"""

DOME_PIXEL = """// dome preview: the domemaster mapped by direction from the dome centre (object space), seen from inside
uniform vec4 uDomeP;   // fov deg, 0, 0, 0
uniform sampler2D sMaster;
in Vert { vec3 wpos; vec3 wnorm; vec3 opos; } iVert;
layout(location = 0) out vec4 fragColor;
void main()
{
\tTDCheckDiscard();
\tvec3 d = normalize(iVert.opos);
\tfloat th = acos(clamp(d.y, -1.0, 1.0));
\tfloat halfA = radians(uDomeP.x) * 0.5;
\tvec4 c = vec4(0.03, 0.03, 0.035, 1.0);
\tif (th <= halfA) {
\t\tfloat r = th / halfA, ph = atan(d.z, d.x);
\t\tc = vec4(texture(sMaster, 0.5 + 0.5 * r * vec2(cos(ph), sin(ph))).rgb, 1.0);
\t}
\tfragColor = TDOutputSwizzle(c);
}
"""

# ------------------------------------------------------------------ callbacks
PARS_FN = """def _pars(P):
    out = {}
    for p in P.customPars:
        if p.page is None or p.page.name in ('Readouts', 'Zkit') or p.style == 'Pulse':
            continue
        out[p.name] = p.eval()
    return out
"""

RIG_CB = """# rig: one sample of derived numbers (throw ratio, FOV, light map size + image rect, viewer camera pose).
# Logic: pd_logic.rig (copy of builders/projector_dome_logic.py; tests test/test_projector_dome.py).
""" + PARS_FN + """
def onCook(scriptOp):
    L = op('pd_logic').module
    st = L.rig(_pars(parent()))
    scriptOp.clear()
    scriptOp.numSamples = 1
    for k, v in st['chans'].items():
        scriptOp.appendChan(k)[0] = float(v)
    return
"""

UNI_CB = """# proj_uniforms: vec4 array for the GLSL MATs (12 samples = 6 per projector; channels x y z w).
""" + PARS_FN + """
def onCook(scriptOp):
    L = op('pd_logic').module
    st = L.rig(_pars(parent()))
    rows = L.uniforms([st['A'], st['B']])
    scriptOp.clear()
    scriptOp.numSamples = len(rows)
    chans = [scriptOp.appendChan(n) for n in ('x', 'y', 'z', 'w')]
    for i, r in enumerate(rows):
        for c, v in zip(chans, r):
            c[i] = float(v)
    return
"""

READ_CB = """# readouts: real-world numbers from the probe renders (image centre, averages) + the pars.
""" + PARS_FN + """
def probe_dict():
    pv = op('probe_vals')
    return {c.name: float(c[0]) for c in pv.chans()} if pv is not None and pv.numSamples else {}

def onCook(scriptOp):
    L = op('pd_logic').module
    r = L.readouts(_pars(parent()), probe_dict())
    scriptOp.clear()
    scriptOp.numSamples = 1
    for k, v in r.items():
        scriptOp.appendChan(k)[0] = float(v)
    return
"""

HUD_CB = """# hud_lines: the HUD text (Text TOP hud_text reads this DAT).
""" + PARS_FN + """
def onCook(scriptOp):
    L = op('pd_logic').module
    P = _pars(parent())
    pv = op('probe_vals')
    probe = {c.name: float(c[0]) for c in pv.chans()} if pv is not None and pv.numSamples else {}
    scriptOp.clear()
    scriptOp.write(L.hud_text(P, L.readouts(P, probe)))
    return
"""

FRUSTUM_CB = """# frustum lines of projector A (and B when on), length = throw distance at the image centre (else 6 m).
def onCook(scriptOp):
    C = parent(2)
    L = C.op('pd_logic').module
    P = {}
    for p in C.customPars:
        if p.page is None or p.page.name in ('Readouts', 'Zkit') or p.style == 'Pulse':
            continue
        P[p.name] = p.eval()
    st = L.rig(P)
    pv = C.op('probe_vals')
    pr = {c.name: float(c[0]) for c in pv.chans()} if pv is not None and pv.numSamples else {}
    scriptOp.clear()
    segs = L.frustum_segments(st['A'], pr.get('a_d', 0.0) or 6.0)
    if st['B']['on']:
        segs += L.frustum_segments(st['B'], pr.get('b_d', 0.0) or 6.0)
    for a, b in segs:
        poly = scriptOp.appendPoly(2, closed=False, addPoints=True)
        poly[0].point.P = a
        poly[1].point.P = b
    return
"""

PROBE_CB = """# probe_vals: numbers from the probe renders (1x1 TOP downloads). On 31550 a pulled Render TOP re-renders every
# frame (even a static scene), so reading the probes every cook made the readouts / HUD / frustum chain cook every
# frame. Here the TOPs are read only when the rig, the pars or the stage geometry change (key); otherwise the stored
# numbers are returned without touching the TOPs, so the dependency drops and the chain goes idle.
""" + PARS_FN + """
# Cache in module globals, not op storage: fetch() of the op's own storage plus store() in the same cook made a
# 'Cook dependency loop' (probe_vals -> probe_vals) on 31550 (26 Oct). The cache resets when this DAT's text changes.
_S = {}

def _px(name):
    t = op(name)
    if t is None or t.width < 1:
        return None
    a = t.numpyArray(delayed=False)
    return None if a is None or not a.size else a.reshape(-1, a.shape[-1])[0]

def _key():
    so = op('stage/out')
    rg = op('rig')
    return repr((sorted(_pars(parent()).items()), [round(float(ch[0]), 6) for ch in rg.chans()] if rg else [],
                 (so.numPoints, so.totalCooks) if so is not None else None))

def onCook(scriptOp):
    k = _key()
    v = _S.get('pv')
    if v is None or _S.get('pv_key', '') != k:
        v = {'a_ppm': 0.0, 'a_d': 0.0, 'a_avgppm': 0.0, 'a_avgcov': 0.0, 'a_maxmm': 0.0, 'b_ppm': 0.0, 'b_d': 0.0}
        c = _px('pa_c')
        if c is not None:
            v['a_ppm'], v['a_d'] = float(c[0]), float(c[1])
        s = _px('pa_avg')
        if s is not None:
            v['a_avgppm'], v['a_avgcov'] = float(s[0]), float(s[3])
        m = _px('pa_max')
        if m is not None:
            v['a_maxmm'] = float(m[2])
        if parent().par.Projbon.eval():
            b = _px('pb_c')
            if b is not None:
                v['b_ppm'], v['b_d'] = float(b[0]), float(b[1])
        _S['pv'] = v
        _S['pv_key'] = k
    scriptOp.clear()
    scriptOp.numSamples = 1
    for name, x in v.items():
        scriptOp.appendChan(name)[0] = x
    return

def onSetupParameters(scriptOp):
    return

def onPulse(par):
    return
"""

PAR_EXEC = """# par_exec: a resolution preset writes Resx / Resy; editing them by hand switches the preset to Custom.
def onValueChange(par, prev):
    P = parent()
    L = op('pd_logic').module
    if par.name == 'Respreset':
        if par.eval() != 'custom':
            w, h = L.RES_SIZE[par.eval()]
            P.par.Resx = w
            P.par.Resy = h
    elif par.name in ('Resx', 'Resy'):
        pre = P.par.Respreset.eval()
        if pre != 'custom' and L.RES_SIZE.get(pre) != (int(P.par.Resx.eval()), int(P.par.Resy.eval())):
            P.par.Respreset = 'custom'
    return
"""


def _logic():
    ns = {}
    exec(open(LOGIC_FILE, encoding='utf-8').read(), ns)
    return ns


def _menu(m):
    return {'names': [k for k, _ in m], 'labels': [l for _, l in m]}


def _pages(Lg):
    F = lambda lo, hi, label: {'min': lo, 'max': hi, 'label': label}
    return [
        ('Projector', [
            ('Lensinput', 'Menu', 'ratio', dict(_menu(Lg['LENSINPUT']), label='Lens input')),
            ('Throwratio', 'Float', 1.2564, F(0.3, 3.0, 'Throw ratio (distance / width)')),
            ('Respreset', 'Menu', 'hd', dict(_menu(Lg['RES_PRESETS']), label='Native resolution')),
            ('Resx', 'Int', 1920, F(320, 8192, 'Native width px')),
            ('Resy', 'Int', 1080, F(200, 4320, 'Native height px')),
            ('Lumens', 'Float', 6000.0, F(500, 40000, 'Lumens (ANSI)')),
            ('Fnum', 'Float', 2.0, F(1.0, 4.0, 'F-number (info)')),
            ('Shifth', 'Float', 0.0, F(-100, 100, 'Lens shift H % of width')),
            ('Shiftv', 'Float', 0.0, F(-100, 100, 'Lens shift V % of height')),
            ('Gain', 'Float', 1.0, F(0.3, 3.0, 'Screen gain')),
            ('Fitcontent', 'Menu', 'fit', dict(_menu(Lg['FITMODES']), label='Content fit')),
            ('Testchart', 'Toggle', False, {'label': 'Test chart'}),
            ('Mapres', 'Int', 1024, F(128, 4096, 'Light map width px')),
            ('Showfrustum', 'Toggle', True, {'label': 'Show frustum'}),
            ('Unit', 'Menu', 'm', dict(_menu(Lg['UNITS']), label='Units')),
        ]),
        ('Projb', [
            ('Projbon', 'Toggle', False, {'label': 'Projector B on'}),
            ('Projbx', 'Float', 2.7, F(-10, 10, 'B x')),
            ('Projby', 'Float', 2.24, F(0, 8, 'B y')),
            ('Projbz', 'Float', 6.58, F(-10, 15, 'B z')),
            ('Projbtilt', 'Float', -10.75, F(-90, 90, 'B tilt')),
            ('Projbpan', 'Float', -8.0, F(-180, 180, 'B pan')),
            ('Projbthrow', 'Float', 1.2564, F(0.3, 3.0, 'B throw ratio')),
            ('Projbshifth', 'Float', 0.0, F(-100, 100, 'B lens shift H %')),
            ('Projbshiftv', 'Float', 0.0, F(-100, 100, 'B lens shift V %')),
            ('Projblumens', 'Float', 6000.0, F(500, 40000, 'B lumens')),
        ]),
        ('View', [
            ('Viewmode', 'Menu', 'lit', dict(_menu(Lg['VIEWMODES']), label='View mode')),
            ('Maxppi', 'Float', 40.0, F(1, 200, 'Legend max ppi')),
            ('Maxnits', 'Float', 500.0, F(10, 5000, 'Legend max nits')),
            ('Heatshadows', 'Toggle', True, {'label': 'Occlusion in heat views'}),
            ('Shadowres', 'Int', 384, F(64, 2048, 'Probe width px')),
            ('Shadowbias', 'Float', 0.02, F(0, 0.2, 'Occlusion bias')),
            ('Showhud', 'Toggle', True, {'label': 'Show readouts'}),
        ]),
        ('Camera', [
            ('Campreset', 'Menu', 'orbit', dict(_menu(Lg['CAMPRESETS']), label='Camera preset')),
            ('Camproj', 'Menu', 'persp', dict(_menu(Lg['CAMPROJ']), label='Projection')),
            ('Orthowidth', 'Float', 12.0, F(1, 50, 'Ortho width')),
            ('Lookx', 'Float', 0.0, F(-10, 10, 'Look at x')),
            ('Lookz', 'Float', 0.0, F(-10, 10, 'Look at z')),
            ('Eyeheight', 'Float', 1.7, F(0, 5, 'Audience eye height')),
            ('Camshiftx', 'Float', 0.0, F(-100, 100, 'Camera shift x %')),
            ('Camshifty', 'Float', 0.0, F(-100, 100, 'Camera shift y %')),
        ]),
        ('Dome', [
            ('Domemode', 'Menu', 'off', dict(_menu(Lg['DOMEMODES']), label='Dome mode')),
            ('Inputformat', 'Menu', 'flat', dict(_menu(Lg['INPUTFORMATS']), label='Input format')),
            ('Domefov', 'Float', 180.0, F(90, 250, 'Dome fov')),
            ('Dometilt', 'Float', 0.0, F(-45, 45, 'Dome tilt')),
            ('Domeradius', 'Float', 6.0, F(1, 30, 'Dome radius m')),
            ('Seatx', 'Float', 0.0, F(-10, 10, 'Seat x')),
            ('Seatz', 'Float', 0.0, F(-10, 10, 'Seat z')),
            ('Domeeye', 'Float', 0.0, F(-2, 5, 'Eye above spring line')),
            ('Domeyaw', 'Float', 0.0, F(-180, 180, 'Look yaw')),
            ('Domepitch', 'Float', 45.0, F(-30, 90, 'Look pitch')),
            ('Domecamfov', 'Float', 100.0, F(30, 170, 'View fov')),
            ('Domeres', 'Int', 2048, F(256, 8192, 'Domemaster px')),
            ('Winaz', 'Float', 0.0, F(-180, 180, 'Window azimuth')),
            ('Winel', 'Float', 25.0, F(-30, 90, 'Window elevation')),
            ('Winhw', 'Float', 60.0, F(1, 180, 'Window half width')),
            ('Winhh', 'Float', 34.0, F(1, 90, 'Window half height')),
            ('Template', 'Toggle', True, {'label': 'Angle rings'}),
            ('Templateopacity', 'Float', 0.5, F(0, 1, 'Rings opacity')),
            ('Domemask', 'Toggle', True, {'label': 'Circle mask'}),
            ('Scenex', 'Float', 0.0, F(-10, 10, 'Room fisheye x')),
            ('Sceney', 'Float', 1.6, F(0, 8, 'Room fisheye y')),
            ('Scenez', 'Float', 0.0, F(-10, 10, 'Room fisheye z')),
        ]),
    ]


READOUTS = [('Throwdist', 'throwdist', 'Throw distance m (image centre)'), ('Imgw', 'imgw', 'Image width m'),
            ('Imgh', 'imgh', 'Image height m'), ('Imgdiag', 'imgdiag', 'Image diagonal m'),
            ('Hfov', 'hfov', 'H FOV deg'), ('Vfov', 'vfov', 'V FOV deg'), ('Pxpm', 'pxpm', 'Px per metre (centre)'),
            ('Ppi', 'ppi', 'Ppi (centre)'), ('Mmpx', 'mmpx', 'mm per px (centre)'), ('Lux', 'lux', 'Lux (centre)'),
            ('Nits', 'nits', 'Nits (centre)'), ('Fl', 'fl', 'Foot-lamberts (centre)'),
            ('Avgppi', 'avgppi', 'Ppi average on surfaces'), ('Minppi', 'minppi', 'Ppi minimum'),
            ('Coverage', 'coverage', 'Image on surfaces (0-1)'), ('Bthrowdist', 'b_throwdist', 'B throw distance m'),
            ('Bppi', 'b_ppi', 'B ppi (centre)'), ('Bnits', 'b_nits', 'B nits (centre)')]

PANEL_PAGES = ['Room', 'Projector', 'Projb', 'View', 'Camera', 'Dome']


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']   # slider range only: no clamps (no limits)
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
            p.default = default
            p.val = default
    page = next((pg for pg in c.customPages if pg.name == 'Readouts'), None) or c.appendCustomPage('Readouts')
    for name, ch, label in READOUTS:
        p = getattr(c.par, name, None)
        if p is None:
            p = page.appendFloat(name, label=label)[0]
        p.expr = "me.op('readouts')['%s'] if me.op('readouts') is not None and me.op('readouts')['%s'] is not None else 0" % (ch, ch)
        p.mode = ParMode.EXPRESSION
        p.readOnly = True
    # the legacy cone angle stays on the Room page with its old meaning; say when it is used
    c.par.Throw.label = 'Cone angle (Lens input = angle)'


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


def _wire(a, b, i=0):
    b.inputConnectors[i].connect(a)


def _text(c, name, txt, dock=None, comment=None):
    t = _mk(c, textDAT, name)
    t.text = txt
    if dock is not None:
        t.dock = dock
    if comment:
        t.comment = comment
    return t


def _script(c, cls, name, cb_text, comment):
    s = _mk(c, cls, name)
    cbn = name + '_callbacks'
    cb = _text(c, cbn, cb_text, dock=s)
    s.par.callbacks = cbn
    s.comment = comment
    return s


def _vecs(g, U):
    g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), len(U))
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), str(e))


def _compute_top(c, name, dat_name, code, w_expr, h_expr, fmt, comment):
    g = _mk(c, glslTOP, name)
    g.par.mode = 'compute'
    _text(c, dat_name, code, dock=g)
    g.par.computedat = dat_name
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w_expr)
    _expr(g.par.resolutionh, h_expr)
    g.par.format = fmt
    g.par.autodispatchsize = True
    g.comment = comment
    for dn in ('_info', '_pixel', '_compute'):            # GLSL TOP docks its own DATs; ours is the compute DAT
        d = c.op(name + dn)
        if d is not None and d.name != dat_name:
            _sd(d)
    return g


def _glsl_mat(c, name, vdat, pdat, comment):
    m = _mk(c, glslMAT, name)
    m.par.vdat = vdat
    m.par.pdat = pdat
    m.comment = comment
    for dn in ('_vertex', '_pixel', '_info'):
        d = c.op(name + dn)
        if d is not None and d.name not in (vdat, pdat):
            _sd(d)
    return m


def _mat_uniforms(m, samplers=(), vecs=()):
    m.seq.array.numBlocks = max(int(m.seq.array.numBlocks), 1)
    m.par.array0name = 'uProj'
    m.par.array0type = 'vec4'
    m.par.array0chop = 'proj_uniforms'
    m.par.array0arraytype = 'uniformarray'
    if samplers:
        m.seq.sampler.numBlocks = max(int(m.seq.sampler.numBlocks), len(samplers))
        for k, (sn, top) in enumerate(samplers):
            getattr(m.par, 'sampler{}name'.format(k)).val = sn
            getattr(m.par, 'sampler{}top'.format(k)).val = top
            getattr(m.par, 'sampler{}extendu'.format(k)).val = 'zero'
            getattr(m.par, 'sampler{}extendv'.format(k)).val = 'zero'
            getattr(m.par, 'sampler{}filter'.format(k)).val = 'nearest'
    if vecs:
        _vecs(m, vecs)


def build(parent_path='/project1/lab', panel=True):
    Lg = _logic()
    pc = op(parent_path)
    c = pc.op(NAME)
    if c is None:
        raise ValueError('LK_projection_room not found under ' + parent_path)
    c.allowCooking = True                       # never parked while being built (user rule)
    was_open = _close_window(c)
    _pars(c, _pages(Lg))
    pp = 'parent().par.'
    for old in ('pa_min', 'pa_ctr', 'pa_stats', 'pa_low', 'pb_ctr', 'pa_ctr_callbacks'):                     # ops of earlier builder versions
        _sd(c.op(old))

    lg = _text(c, 'pd_logic', open(LOGIC_FILE, encoding='utf-8').read(),
               comment='Pure logic (copy of builders/projector_dome_logic.py; tests test/test_projector_dome.py).')
    rig = _script(c, scriptCHOP, 'rig', RIG_CB,
                  'rig: throw ratio, FOVs, light map size + image rect (lens shift), viewer camera pose.')
    uni = _script(c, scriptCHOP, 'proj_uniforms', UNI_CB, 'vec4 array uProj[12] for the GLSL MATs (A, B).')

    # 1 Input: content -> projector images (fit to native aspect + lens shift padding)
    cin = c.op('content_in')
    can_a = _compute_top(c, 'canvas_a', 'canvas_compute', CANVAS, RIG + "['pa_mapw']", RIG + "['pa_maph']",
                         'rgba8fixed', 'Projector A image: content fitted to the native aspect (or test chart), '
                         'placed off-centre in the light map for lens shift.')
    _wire(cin, can_a, 0)
    _vecs(can_a, [('uRect', [RIG + "['pa_u0']", RIG + "['pa_v0']", RIG + "['pa_u1']", RIG + "['pa_v1']"]),
                  ('uFit', ["op('pd_logic').module.menu_index(op('pd_logic').module.FITMODES, parent().par.Fitcontent.eval())",
                            RIG + "['resx'] / " + RIG + "['resy']", "1 if parent().par.Testchart else 0", '0'])])
    can_b = _mk(c, glslTOP, 'canvas_b')
    can_b.par.mode = 'compute'
    can_b.par.computedat = 'canvas_compute'
    can_b.par.outputresolution = 'custom'
    _expr(can_b.par.resolutionw, RIG + "['pb_mapw']")
    _expr(can_b.par.resolutionh, RIG + "['pb_maph']")
    can_b.par.format = 'rgba8fixed'
    can_b.par.autodispatchsize = True
    can_b.comment = 'Projector B image (same content and native resolution, its own lens shift).'
    for dn in ('_info', '_pixel', '_compute'):
        d = c.op('canvas_b' + dn)
        if d is not None:
            _sd(d)
    _wire(cin, can_b, 0)
    _vecs(can_b, [('uRect', [RIG + "['pb_u0']", RIG + "['pb_v0']", RIG + "['pb_u1']", RIG + "['pb_v1']"]),
                  ('uFit', ["op('pd_logic').module.menu_index(op('pd_logic').module.FITMODES, parent().par.Fitcontent.eval())",
                            RIG + "['resx'] / " + RIG + "['resy']", "1 if parent().par.Testchart else 0", '0'])])

    # 3 Projectors: lights (lit view, shadows) + matching cameras (probe renders, through-projector view)
    pa = c.op('projector')
    pa.par.projmap = 'canvas_a'
    _expr(pa.par.projangle, RIG + "['pa_projangle']")
    pa.par.projmapmode = 'simplehorzfov'
    pa.par.shadowcasters = 'stage'
    pb = _mk(c, lightCOMP, 'projector_b')
    for k, n in (('tx', 'Projbx'), ('ty', 'Projby'), ('tz', 'Projbz'), ('rx', 'Projbtilt'), ('ry', 'Projbpan')):
        _expr(getattr(pb.par, k), pp + n)
    _expr(pb.par.dimmer, pp + 'Brightness')
    pb.par.projmap = 'canvas_b'
    pb.par.projmapmode = 'simplehorzfov'
    _expr(pb.par.projangle, RIG + "['pb_projangle']")
    _expr(pb.par.shadowtype, "'hard2d' if parent().par.Shadows else 'off'")
    pb.par.shadowcasters = 'stage'
    pb.comment = 'Projector B light (Projb page; on when Projbon).'
    for nm, src, fovc in (('proj_cam', ('Projx', 'Projy', 'Projz', 'Projtilt', 'Projpan', 'Shifth', 'Shiftv'), 'pa_hfov'),
                          ('proj_cam_b', ('Projbx', 'Projby', 'Projbz', 'Projbtilt', 'Projbpan', 'Projbshifth',
                                          'Projbshiftv'), 'pb_hfov')):
        cm = _mk(c, cameraCOMP, nm)
        for k, n in zip(('tx', 'ty', 'tz', 'rx', 'ry'), src[:5]):
            _expr(getattr(cm.par, k), pp + n)
        cm.par.viewanglemethod = 'horzfov'
        _expr(cm.par.fov, RIG + "['%s']" % fovc)
        _expr(cm.par.winx, pp + src[5] + ' / 100.0')
        _expr(cm.par.winy, pp + src[6] + ' / 100.0')
        cm.par.near = 0.05
        cm.par.far = 500
        cm.comment = 'Camera = the projector lens (off-axis via winx/winy = lens shift; probed live, see docs).'

    fmat = _mk(c, constantMAT, 'frustum_mat')
    fmat.par.colorr, fmat.par.colorg, fmat.par.colorb = 1.0, 0.85, 0.2
    fr = _mk(c, geometryCOMP, 'frustum')
    for ch in list(fr.children):
        if ch.name not in ('lines', 'lines_callbacks'):
            _sd(ch)
    ls = fr.op('lines') or fr.create(scriptSOP, 'lines')
    lcb = fr.op('lines_callbacks') or fr.create(textDAT, 'lines_callbacks')
    lcb.text = FRUSTUM_CB
    lcb.dock = ls
    ls.par.callbacks = 'lines_callbacks'
    ls.render = True
    ls.display = True
    fr.par.material = 'frustum_mat'
    fr.comment = 'Projector frustum lines (Showfrustum), to the throw distance at the image centre.'

    # 5 Analysis: probe renders from each projector + view material
    pm_v = _text(c, 'pd_mat_vertex', MAT_VERT, comment='Vertex shader shared by probe_mat_*, view_mat, dome_mat.')
    pm_p = _text(c, 'probe_pixel', PROBE_PIXEL, comment='Probe: px/m, distance, min search, covered (32F).')
    vw_p = _text(c, 'view_pixel', VIEW_PIXEL, comment='Heat views: coverage / pixel density / brightness / overlap.')
    for nm, idx in (('probe_mat_a', 0), ('probe_mat_b', 1)):
        m = _glsl_mat(c, nm, 'pd_mat_vertex', 'probe_pixel', 'Probe material for projector ' + 'AB'[idx] + '.')
        _mat_uniforms(m, vecs=[('uSel', [idx, 0, 0, 0])])
    probes = []
    for nm, cam, mat, on in (('probe_a', 'proj_cam', 'probe_mat_a', None), ('probe_b', 'proj_cam_b', 'probe_mat_b', 'pb_on')):
        r = _mk(c, renderTOP, nm)
        r.par.camera = cam
        r.par.geometry = 'stage'
        r.par.lights = ''
        r.par.overridemat = mat
        r.par.outputresolution = 'custom'
        _expr(r.par.resolutionw, RIG + "['probe_w']")
        _expr(r.par.resolutionh, RIG + "['probe_h']")
        r.par.format = 'rgba32float'
        r.par.antialias = 'aa1'
        r.par.bgcolorr = r.par.bgcolorg = r.par.bgcolorb = r.par.bgcolora = 0
        r.par.cullface = 'neither'
        r.comment = ('Render from projector %s: r px/m, g distance (occlusion map), b mm/px, a covered.'
                     % ('A' if nm == 'probe_a' else 'B'))
        probes.append(r)
    vm = _glsl_mat(c, 'view_mat', 'pd_mat_vertex', 'view_pixel', 'Heat view material (render overridemat).')
    _mat_uniforms(vm, samplers=[('sDepthA', 'probe_a'), ('sDepthB', 'probe_b')],
                  vecs=[('uView', ["op('pd_logic').module.menu_index(op('pd_logic').module.VIEWMODES, parent().par.Viewmode.eval())",
                                   pp + 'Maxppi', pp + 'Maxnits', "1 if parent().par.Heatshadows else 0"]),
                        ('uView2', [pp + 'Shadowbias', 0, 0, 0])])
    an_avg = _mk(c, analyzeTOP, 'pa_avg')
    _wire(probes[0], an_avg)
    an_avg.par.op = 'average'
    an_avg.par.analyzechannel = 'independent'
    an_min = _mk(c, analyzeTOP, 'pa_max')
    _wire(probes[0], an_min)
    an_min.par.op = 'maximum'
    an_min.par.analyzechannel = 'independent'
    for nm, src in (('pa_c', 'probe_a'), ('pb_c', 'probe_b')):
        cr = _mk(c, cropTOP, nm)
        _wire(c.op(src), cr)
        for k in ('cropleftunit', 'croprightunit', 'cropbottomunit', 'croptopunit'):
            getattr(cr.par, k).val = 'fraction'
        _expr(cr.par.cropleft, "0.5 - 0.5 / max(me.inputs[0].width, 1)")
        _expr(cr.par.cropright, "0.5 + 0.5 / max(me.inputs[0].width, 1)")
        _expr(cr.par.cropbottom, "0.5 - 0.5 / max(me.inputs[0].height, 1)")
        _expr(cr.par.croptop, "0.5 + 0.5 / max(me.inputs[0].height, 1)")
        cr.comment = 'Image-centre pixel of ' + src + ' (1x1).'
    pv = _script(c, scriptCHOP, 'probe_vals', PROBE_CB,
                 'Probe numbers (1x1 TOP downloads; cooks only when a probe re-renders, not every frame).')
    rd = _script(c, scriptCHOP, 'readouts', READ_CB, 'Readouts (read-only pars on the Readouts page + HUD).')
    hl = _script(c, scriptDAT, 'hud_lines', HUD_CB, 'HUD text lines.')

    # 6 Audience view -> output
    vc = c.op('viewer')
    for k in ('tx', 'ty', 'tz', 'rx', 'ry', 'fov', 'winx', 'winy'):
        _expr(getattr(vc.par, k), RIG + "['cam_%s']" % k)
    vc.par.viewanglemethod = 'horzfov'
    _expr(vc.par.projection, "'ortho' if " + RIG + "['cam_ortho'] > 0.5 else 'perspective'")
    _expr(vc.par.orthowidth, RIG + "['cam_orthow']")
    rn = c.op('render')
    _expr(rn.par.geometry, "'stage frustum' if parent().par.Showfrustum else 'stage'")
    _expr(rn.par.lights, "'projector ambient projector_b' if parent().par.Projbon else 'projector ambient'")
    _expr(rn.par.overridemat, "'' if parent().par.Viewmode.eval() == 'lit' else 'view_mat'")
    ht = _mk(c, textTOP, 'hud_text')
    ht.par.dat = 'hud_lines'
    ht.par.outputresolution = 'custom'
    _expr(ht.par.resolutionw, "op('render').width")
    _expr(ht.par.resolutionh, "op('render').height")
    ht.par.alignx = 'left'
    ht.par.aligny = 'top'
    ht.par.positionunit = 'fraction'
    ht.par.positionx = -0.48
    ht.par.positiony = 0.47
    ht.par.fontsizex = 22
    ht.par.bgalpha = 0
    ht.par.fontcolorr = ht.par.fontcolorg = ht.par.fontcolorb = 1
    hud = _compute_top(c, 'hud', 'hud_compute', HUD, "op('render').width", "op('render').height", 'rgba8fixed',
                       'Audience view + legend bar + readouts (Showhud).')
    _wire(rn, hud, 0)
    _wire(ht, hud, 1)
    _vecs(hud, [('uHud', ["op('pd_logic').module.menu_index(op('pd_logic').module.VIEWMODES, parent().par.Viewmode.eval())",
                          "1 if parent().par.Showhud else 0", 0, 0])])

    # 7 Dome
    dsc = _mk(c, cameraCOMP, 'dome_scene_cam')
    _expr(dsc.par.tx, pp + 'Scenex')
    _expr(dsc.par.ty, pp + 'Sceney')
    _expr(dsc.par.tz, pp + 'Scenez')
    _expr(dsc.par.rx, '90 - ' + pp + 'Dometilt')
    dsc.par.near = 0.05
    dsc.comment = 'Room fisheye camera: looks up (zenith), front (-Z) at the bottom of the fisheye.'
    dsr = _mk(c, renderTOP, 'dome_scene')
    dsr.par.camera = 'dome_scene_cam'
    _expr(dsr.par.geometry, "'stage'")
    _expr(dsr.par.lights, "'projector ambient projector_b' if parent().par.Projbon else 'projector ambient'")
    dsr.par.rendermode = 'fisheye180'
    dsr.par.outputresolution = 'custom'
    _expr(dsr.par.resolutionw, pp + 'Domeres')
    _expr(dsr.par.resolutionh, pp + 'Domeres')
    dsr.par.antialias = 'aa2'
    dsr.comment = 'Input format = The room: fisheye180 render of the lit room from Scenex/y/z.'
    dsw = _mk(c, switchTOP, 'dome_src')
    _wire(cin, dsw, 0)
    _wire(dsr, dsw, 1)
    _expr(dsw.par.index, "1 if parent().par.Inputformat.eval() == 'scene' else 0")
    dsw.comment = 'Only the selected source cooks (content, or the room fisheye render).'
    dm = _compute_top(c, 'dome_master', 'dome_compute', DOMEMASTER, pp + 'Domeres', pp + 'Domeres', 'rgba8fixed',
                      'Square domemaster (azimuthal equidistant, front at the bottom), rings template, circle mask.')
    _wire(dsw, dm, 0)
    _vecs(dm, [('uDome', ["op('pd_logic').module.menu_index(op('pd_logic').module.INPUTFORMATS, parent().par.Inputformat.eval())",
                          pp + 'Domefov', pp + 'Dometilt', "1 if parent().par.Domemask else 0"]),
               ('uWin', [pp + 'Winaz', pp + 'Winel', pp + 'Winhw', pp + 'Winhh']),
               ('uTpl', ["1 if parent().par.Template else 0", pp + 'Templateopacity', 0, 0])])
    dpx = _text(c, 'dome_pixel', DOME_PIXEL, comment='Dome preview: domemaster by direction from the dome centre.')
    dmat = _glsl_mat(c, 'dome_mat', 'pd_mat_vertex', 'dome_pixel', 'Dome preview material.')
    dmat.seq.sampler.numBlocks = max(int(dmat.seq.sampler.numBlocks), 1)
    dmat.par.sampler0name = 'sMaster'
    dmat.par.sampler0top = 'dome_master'
    _vecs(dmat, [('uDomeP', [pp + 'Domefov', 0, 0, 0])])
    dg = _mk(c, geometryCOMP, 'dome_geo')
    for ch in list(dg.children):
        if ch.name != 'sphere':
            _sd(ch)
    sp = dg.op('sphere') or dg.create(sphereSOP, 'sphere')
    sp.par.type = 'mesh'
    sp.par.rows = 64
    sp.par.cols = 96
    for k in ('radx', 'rady', 'radz'):
        _expr(getattr(sp.par, k), 'parent(2).par.Domeradius')
    sp.render = True
    sp.display = True
    dg.par.material = 'dome_mat'            # a COMP's OP pars resolve beside it (stage.material = mat)
    _expr(dg.par.rx, '-' + pp + 'Dometilt')
    dg.comment = 'Dome: sphere of Domeradius, tilted forward by Dometilt; dome_mat shows the part within Domefov.'
    dcam = _mk(c, cameraCOMP, 'dome_cam')
    for k, n in (('tx', 'Seatx'), ('ty', 'Domeeye'), ('tz', 'Seatz'), ('rx', 'Domepitch'), ('ry', 'Domeyaw'),
                 ('fov', 'Domecamfov')):
        _expr(getattr(dcam.par, k), pp + n)
    dcam.par.near = 0.05
    dcam.comment = 'Spectator inside the dome (seat x/z, eye height, look yaw/pitch).'
    dr = _mk(c, renderTOP, 'dome_render')
    dr.par.camera = 'dome_cam'
    dr.par.geometry = 'dome_geo'
    dr.par.lights = ''
    dr.par.cullface = 'neither'
    dr.par.outputresolution = 'custom'
    _expr(dr.par.resolutionw, "op('render').width")
    _expr(dr.par.resolutionh, "op('render').height")
    dr.par.antialias = 'aa4'
    dr.comment = 'Dome preview render (Domemode = Preview).'

    osw = _mk(c, switchTOP, 'out_switch')
    _wire(hud, osw, 0)
    _wire(dr, osw, 1)
    _wire(dm, osw, 2)
    _expr(osw.par.index, "op('pd_logic').module.menu_index(op('pd_logic').module.DOMEMODES, parent().par.Domemode.eval())")
    osw.comment = 'Domemode: off = room view, preview = inside the dome, domemaster = the square master.'
    outn = c.op('out')
    _wire(osw, outn, 0)
    dmo = _mk(c, outTOP, 'domemaster_out')
    _wire(dm, dmo, 0)
    dmo.comment = 'out 2 (TOP): the square domemaster, output only.'

    pe = _mk(c, parameterexecuteDAT, 'par_exec')
    pe.text = PAR_EXEC
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Respreset Resx Resy'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = True
    pe.par.active = True

    c.comment = ('LK_projection_room: projector planner + fulldome preview. in 1 TOP = content; out 1 = room view '
                 '(or dome preview / domemaster per Domemode), out 2 = domemaster. Real-world projector pars '
                 '(throw ratio, native res, lumens, lens shift, gain), heat views (coverage, pixel density, '
                 'brightness, overlap), camera presets incl. through-projector, Domemode. Readouts page = numbers. '
                 'Ideas: asterix Projector Coverage Tool (par names), Theinfranet Fulldome Simulator (dome preview); '
                 'our own code. Pulse Opencontrols.')
    for o in c.children:
        if o.family in ('TOP', 'CHOP') and not o.viewer:
            o.viewer = True
    # T-74: no force-cook of readouts / hud_lines here: they pull probe_vals, whose numpyArray() of the probe TOPs
    # would run in the same script that (re)made those TOPs. They cook on their own next frames.
    for o in (rig, uni):
        o.cook(force=True)

    info = 'skipped'
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=PANEL_PAGES, d=52, cols=10, open_window=was_open)

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'controls_open', 'par_exec'],
         'body': 'zkit panel + window (pulse Opencontrols). par_exec: resolution preset <-> Resx/Resy.'},
        {'title': '1  Input: content', 'role': 'input', 'ops': ['content_in', 'canvas_a', 'canvas_compute', 'canvas_b'],
         'body': 'in 1 (TOP) -> fitted to the native aspect (or Test chart), placed in the light map for lens shift '
                 '(compute pass each).'},
        {'title': '2  The room', 'ops': ['stage', 'mat'], 'body': 'stage = 3D set; mat = white Phong'},
        {'title': '3  Rig maths', 'role': 'control',
         'ops': ['pd_logic', 'rig', 'rig_callbacks', 'proj_uniforms', 'proj_uniforms_callbacks'],
         'body': 'pd_logic = builders/projector_dome_logic.py. rig: throw ratio, FOV, map size, camera pose. '
                 'proj_uniforms: vec4 array for the shaders.'},
        {'title': '4  Projectors + light', 'ops': ['projector', 'projector_b', 'ambient', 'proj_cam', 'proj_cam_b',
                                                   'frustum', 'frustum_mat'],
         'body': 'Light COMPs (projangle = padded hFOV, map = canvas), lens cameras (winx/winy = shift), frustum lines.'},
        {'title': '5  Analysis', 'ops': ['pd_mat_vertex', 'probe_pixel', 'probe_mat_a', 'probe_mat_b', 'probe_a',
                                         'probe_b', 'pa_avg', 'pa_max', 'pa_c', 'pb_c', 'probe_vals',
                                         'probe_vals_callbacks', 'readouts', 'readouts_callbacks', 'hud_lines',
                                         'hud_lines_callbacks', 'view_pixel', 'view_mat'],
         'body': 'Probe renders from each lens (px/m, distance, covered) -> readouts + occlusion maps; '
                 'view_mat = heat views (one GLSL MAT pass).'},
        {'title': '6  Audience view -> output', 'role': 'output',
         'ops': ['viewer', 'render', 'hud_text', 'hud', 'hud_compute', 'out_switch', 'out', 'room_out',
                 'domemaster_out'],
         'body': 'viewer camera (presets) -> render (overridemat in heat views) -> hud -> Domemode switch -> '
                 'out 1; out 2 = domemaster. Output only.'},
        {'title': '7  Dome', 'ops': ['dome_scene_cam', 'dome_scene', 'dome_src', 'dome_master', 'dome_compute',
                                     'dome_pixel', 'dome_mat', 'dome_geo', 'dome_cam', 'dome_render'],
         'body': 'content (flat / domemaster / equirect) or the room fisheye -> domemaster (compute) -> dome '
                 'sphere seen from a seat (Domemode).'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    return {'comp': c.path, 'ops': len(c.children), 'panel': str(info)[:300], 'layout': str(lay)[:400]}
