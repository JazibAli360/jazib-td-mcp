// TP_test_pattern: every pattern in ONE pixel pass (T-46 safe: no chain, no feedback).
// Mirror of builders/test_pattern_logic.py pixel(); top-left origin; exact codes (lit = Level on the Channel mask).
// in0 = labels (cabinet numbers / slice labels, Text TOP alpha), in1 = counter text.
uniform vec4 uRes;    // W H nfaces canvas
uniform vec4 uPat;    // pattern walk step linewidth
uniform vec4 uLit;    // mask r g b, level (0..1)
uniform vec4 uCab;    // cabinet w h, cell w h (comp px)
uniform vec4 uOpt;    // ramp steps, showfaces, flash now, flash width
uniform vec4 uWheel;  // on cx cy radius
uniform vec4 uClock;  // frame fps seconds counter-on
uniform vec4 uCnt;    // counter box x y w h
uniform vec4 uCnt2;   // cell size, pad, text w, text h
uniform vec4 uFaces[16];   // x y w h per face (comp px, top-left)
out vec4 fragColor;

int cellIndex(int l, float c) { return int(ceil((float(l) + 0.5) / c)) - 1; }
int cellBound(int k, float c) { return int(floor(float(k) * c + 0.5)); }
int countCells(int n, float c) { return n > 0 ? cellIndex(n - 1, c) + 1 : 0; }
bool onEdge(int lx, int ly, int aw, int ah, int lw) { return lx < lw || lx >= aw - lw || ly < lw || ly >= ah - lw; }
float pmod(float u, float c) { return u - c * floor(u / c); }

const vec3 BARS[8] = vec3[8](vec3(1,1,1), vec3(1,1,0), vec3(0,1,1), vec3(0,1,0),
                             vec3(1,0,1), vec3(1,0,0), vec3(0,0,1), vec3(0,0,0));
const float RATES[5] = float[5](24.0, 30.0, 48.0, 60.0, 120.0);

// returns colour (already at level); lit amount uses the channel mask
vec3 pattern(int pat, int lx, int ly, int aw, int ah) {
    vec3 lit = uLit.rgb * uLit.w;
    float cw = uCab.x, ch = uCab.y, cellw = uCab.z, cellh = uCab.w;
    int walk = int(uPat.y + 0.5), stp = int(uPat.z + 0.5), lw = int(uPat.w + 0.5);
    if (pat == 2) return lit;                                             // solid
    if (pat == 0) {                                                       // cabinets
        int kx = cellIndex(lx, cw), ky = cellIndex(ly, ch);
        int x0 = cellBound(kx, cw), x1 = min(cellBound(kx + 1, cw), aw);
        int y0 = cellBound(ky, ch), y1 = min(cellBound(ky + 1, ch), ah);
        int fx = lx - x0, fy = ly - y0;
        return (fx < lw || fx >= (x1 - x0) - lw || fy < lw || fy >= (y1 - y0) - lw) ? lit : vec3(0.0);
    }
    if (pat == 1) {                                                       // slices: outline + diagonals
        if (onEdge(lx, ly, aw, ah, lw)) return lit;
        float w = float(aw), h = float(ah), px = float(lx) + 0.5, py = float(ly) + 0.5;
        float n = sqrt(w * w + h * h);
        float d1 = abs(px * h - py * w) / n, d2 = abs((w - px) * h - py * w) / n;
        return (d1 < float(lw) * 0.5 || d2 < float(lw) * 0.5) ? lit : vec3(0.0);
    }
    if (pat == 3) return BARS[min(7, (lx * 8) / aw)] * uLit.w;            // bars
    if (pat == 4) {                                                       // ramp, exact codes
        int steps = int(uOpt.x + 0.5);
        float t = (aw >= ah) ? float(lx) / float(aw) : float(ly) / float(ah);
        int k = min(steps - 1, int(floor(t * float(steps))));
        float code = floor(float(k) * (uLit.w * 255.0) / float(steps - 1) + 0.5);
        return uLit.rgb * code / 255.0;
    }
    if (pat == 9) {                                                       // gradient (16-bit float)
        float t = (aw >= ah) ? float(lx) / float(max(1, aw - 1)) : float(ly) / float(max(1, ah - 1));
        return lit * t;
    }
    if (pat == 5) return ((cellIndex(lx, cellw) + cellIndex(ly, cellh)) % 2 == 0) ? lit : vec3(0.0);   // checker
    if (pat == 6) {                                                       // crosshatch from the centre + edge
        if (onEdge(lx, ly, aw, ah, lw)) return lit;
        float mx = pmod(float(lx - aw / 2), cellw), my = pmod(float(ly - ah / 2), cellh);
        return (mx < float(lw) || my < float(lw)) ? lit : vec3(0.0);
    }
    if (pat == 8) {                                                       // circles
        if (onEdge(lx, ly, aw, ah, lw)) return lit;
        float dx = float(lx) + 0.5 - float(aw) * 0.5, dy = float(ly) + 0.5 - float(ah) * 0.5;
        float d = sqrt(dx * dx + dy * dy);
        float R = float(min(aw, ah)) * 0.5 - float(lw) * 0.5;
        if (abs(d - R) < float(lw) * 0.5) return lit;
        return (pmod(d, cellw) < float(lw)) ? lit : vec3(0.0);
    }
    if (pat == 10) {                                                      // pixel check
        if (ly < ah / 2) return ((lx + ly) % 2 == 0) ? lit : vec3(0.0);
        if (lx < aw / 2) return (lx % lw == 0) ? lit : vec3(0.0);
        return (ly % lw == 0) ? lit : vec3(0.0);
    }
    if (pat == 7) {                                                       // walk
        int span;
        if (walk == 0) span = (aw + lw - 1) / lw;
        else if (walk == 1) span = (ah + lw - 1) / lw;
        else if (walk == 2) span = (aw + ah + lw - 1) / lw;
        else if (walk == 3) span = ((int(ceil(cw)) + lw - 1) / lw) * ((int(ceil(ch)) + lw - 1) / lw);
        else span = countCells(aw, cw) * countCells(ah, ch);
        int k = stp % max(1, span);
        if (walk == 0) return (lx / lw == k) ? lit : vec3(0.0);
        if (walk == 1) return (ly / lw == k) ? lit : vec3(0.0);
        if (walk == 2) return ((lx + ly) / lw == k) ? lit : vec3(0.0);
        int kx = cellIndex(lx, cw), ky = cellIndex(ly, ch);
        if (walk == 3) {
            int nx = (int(ceil(cw)) + lw - 1) / lw;
            int fx = lx - cellBound(kx, cw), fy = ly - cellBound(ky, ch);
            int dx = (k % nx) * lw, dy = (k / nx) * lw;
            return (fx >= dx && fx < dx + lw && fy >= dy && fy < dy + lw) ? lit : vec3(0.0);
        }
        int ncx = countCells(aw, cw);
        return (kx == k % ncx && ky == k / ncx) ? lit : vec3(0.0);
    }
    return vec3(0.0);
}

void main() {
    int W = int(uRes.x + 0.5), H = int(uRes.y + 0.5), nf = int(uRes.z + 0.5);
    int ix = int(gl_FragCoord.x), iy = H - 1 - int(gl_FragCoord.y);
    int pat = int(uPat.x + 0.5);
    int lw = int(uPat.w + 0.5);
    bool canvas = uRes.w > 0.5;
    if (pat == 1 && nf > 0) canvas = false;
    vec4 area = vec4(-1.0);
    int fi = -1;
    for (int i = 0; i < 16; i++) {
        if (i >= nf) break;
        vec4 f = uFaces[i];
        if (ix >= int(f.x) && ix < int(f.x + f.z) && iy >= int(f.y) && iy < int(f.y + f.w)) { fi = i; break; }
    }
    if (canvas) area = vec4(0.0, 0.0, float(W), float(H));
    else if (fi >= 0) area = uFaces[fi];
    vec3 col = vec3(0.0);
    float alpha = 0.0;
    if (area.z > 0.0) {
        int ax = int(area.x), ay = int(area.y), aw = int(area.z), ah = int(area.w);
        col = pattern(pat, ix - ax, iy - ay, aw, ah);
        alpha = 1.0;
        if (uOpt.y > 0.5 && fi >= 0) {                                    // Showfaces: outline XOR
            vec4 f = uFaces[fi];
            if (onEdge(ix - int(f.x), iy - int(f.y), int(f.z), int(f.w), lw)) {
                bool on = any(greaterThan(col, vec3(0.0)));
                col = on ? vec3(0.0) : uLit.rgb * uLit.w;
            }
        }
        if (pat <= 1) {                                                   // labels (the only soft pixels)
            float a = texelFetch(sTD2DInputs[0], ivec2(gl_FragCoord.xy), 0).a;
            col = mix(col, uLit.rgb * uLit.w, a);
        }
    }
    // flash bar: a full-height cabinet-wide white column at the right edge on flash frames
    if (uOpt.z > 0.5 && ix >= W - int(uOpt.w)) { col = vec3(uLit.w); alpha = 1.0; }
    // sync wheel: rings 24 30 48 60 120 Hz (project seconds) inner -> outer, outermost = project frame mod fps
    if (uWheel.x > 0.5) {
        float dx = float(ix) + 0.5 - uWheel.y, dy = float(iy) + 0.5 - uWheel.z;
        float d = sqrt(dx * dx + dy * dy), R = uWheel.w, r0 = R * 0.3;
        if (d < R) {
            col = vec3(0.0); alpha = 1.0;
            if (d < 3.0) col = vec3(1.0);
            if (d >= r0) {
                float bw = (R - r0) / 6.0;
                int band = min(5, int((d - r0) / bw));
                float inb = d - r0 - float(band) * bw;
                if (inb > 2.0 && inb < bw - 2.0) {
                    float fr = atan(dx, -dy) / 6.28318530718;
                    fr = fr - floor(fr);
                    int N, litseg;
                    if (band < 5) { N = int(RATES[band]); litseg = int(floor(uClock.z * RATES[band] + 1e-4)) % N; }
                    else { N = max(1, int(uClock.y + 0.5)); litseg = int(uClock.x + 0.5) % N; }
                    int seg = min(N - 1, int(floor(fr * float(N))));
                    col = (seg == litseg) ? vec3(1.0) : vec3(0.12);
                }
            }
        }
    }
    // frame counter: text line + start, 24 frame bits (MSB first), end cells
    if (uClock.w > 0.5) {
        int bx = ix - int(uCnt.x), by = iy - int(uCnt.y);
        if (bx >= 0 && by >= 0 && bx < int(uCnt.z) && by < int(uCnt.w)) {
            col = vec3(0.0); alpha = 1.0;
            int cs = int(uCnt2.x), pad = int(uCnt2.y), tw = int(uCnt2.z), th = int(uCnt2.w);
            int tx = bx - pad, ty = by - pad;
            if (tx >= 0 && ty >= 0 && tx < tw && ty < th)
                col = vec3(texelFetch(sTD2DInputs[1], ivec2(tx, th - 1 - ty), 0).a);
            int sy = by - (pad * 2 + th), sx = bx - pad;
            if (sy >= 0 && sy < cs && sx >= 0 && sx < 26 * cs) {
                int cell = sx / cs;
                bool inner = (sx % cs) < cs - 1 && sy < cs - 1;
                int frame = int(uClock.x + 0.5);
                bool on = (cell == 0 || cell == 25) ? true : (((frame >> (24 - cell)) & 1) == 1);
                col = (on && inner) ? vec3(1.0) : vec3(0.0);
            }
        }
    }
    fragColor = TDOutputSwizzle(vec4(col * alpha, alpha));
}
