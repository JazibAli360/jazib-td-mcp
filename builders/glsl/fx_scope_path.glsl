// FX_scope path pass (compute, T-47). The module's source (scopeCount / scopePoint) -> up to CAP points in
// beam-buffer px. Out 1024 x 17 rgba32float: texel j (row j / 1024) = (x px, y px, weight of segment j -> j+1
// (0 = blank or last), packed rgb); row 16: texel c < 64 = bbox of chunk c's lit segments (minx miny maxx maxy;
// empty = +1e30 / -1e30), texel 1023 = (np, 0, 0, 0). One workgroup = one chunk of 256 points.
layout (local_size_x = 256, local_size_y = 1) in;
uniform vec4 uG;   // beam w, beam h, px per unit x, px per unit y
uniform vec4 uR;   // cos(rotate), sin(rotate), noise px, absTime.frame
//@LIB
//@BUF
//@AUDIO
//@SOURCE
shared vec4 sB[256];
vec2 placed(int j, int np, out vec3 col, out float w) {
    vec2 p = scopePoint(j, np, col, w);
    p = vec2(p.x * uR.x - p.y * uR.y, p.x * uR.y + p.y * uR.x);
    vec2 q = vec2(0.5 * uG.x + p.x * uG.z, 0.5 * uG.y + p.y * uG.w);
    if (uR.z > 0.0) {
        uint h = uint(j) * 747796405u + uint(uR.w) * 2891336453u;
        q += uR.z * 2.0 * (vec2(hash01(h), hash01(h ^ 0x9e3779b9u)) - 0.5);
    }
    return q;
}
void main() {
    ivec2 g = ivec2(gl_GlobalInvocationID.xy);
    if (g.y >= CAPROW) return;                     // the bbox row's own workgroups (whole groups: uniform)
    int j = g.y * ROWW + g.x;
    int np = min(scopeCount(), CAP);
    vec4 o = vec4(0.0);
    vec4 bb = vec4(1e30, 1e30, -1e30, -1e30);
    if (j < np) {
        vec3 c;
        float w;
        vec2 a = placed(j, np, c, w);
        if (j + 1 < np && w > 0.0) {
            vec3 c1;
            float w1;
            vec2 b = placed(j + 1, np, c1, w1);
            bb = vec4(min(a, b), max(a, b));
        } else {
            w = 0.0;
        }
        o = vec4(a, w, packRGB(c));
    }
    TDImageStoreOutput(0, ivec3(g, 0), o);
    uint lid = gl_LocalInvocationIndex;
    sB[lid] = bb;
    barrier();
    for (uint s = 128u; s > 0u; s >>= 1) {
        if (lid < s) {
            vec4 q = sB[lid + s];
            sB[lid] = vec4(min(sB[lid].xy, q.xy), max(sB[lid].zw, q.zw));
        }
        barrier();
    }
    if (lid == 0u) {
        int c = j / CH;
        TDImageStoreOutput(0, ivec3(c, CAPROW, 0), sB[0]);
        if (c == 0) TDImageStoreOutput(0, ivec3(ROWW - 1, CAPROW, 0), vec4(float(np), 0.0, 0.0, 0.0));
    }
}
