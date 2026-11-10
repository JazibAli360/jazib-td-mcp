// BK_dmx_patch address map: ONE compute pass (T-46/T-47 safe), no chain.
// In0 = owner texture: x = slot 0..511, y = universe row (BK_dmx_out out3 channel order), r = owner id
//       (0 free, 1..nfix fixtures, > nfix pixel groups, -1 two owners = conflict).
// In1 = live values: same layout, r = slot value 0..255 (CHOP to TOP of the universes CHOP).
// Tiles of 32 x 16 slots per universe (same tiling as BK_dmx_out's monitor), universe 0 top left.
// uMon: x tiles per row, y px per slot, z first row, w rows shown.
// uOpt: x mode (0 owner x value, 1 owner, 2 value heat), y width, z height, w selected owner id (0 = none).
// uInfo: x fixture count (owner ids above it are pixel groups).
uniform vec4 uMon;
uniform vec4 uOpt;
uniform vec4 uInfo;
layout (local_size_x = 8, local_size_y = 8) in;

vec3 hsv(float h, float s, float v) {
    vec3 k = clamp(abs(fract(h + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    return v * mix(vec3(1.0), k, s);
}
vec3 heat(float v) { return vec3(clamp(v * 3.0, 0.0, 1.0), clamp(v * 3.0 - 1.0, 0.0, 1.0), clamp(v * 3.0 - 2.0, 0.0, 1.0)); }

float ownerAt(ivec2 isz, int slot, int row) {
    if (slot < 0 || slot >= isz.x || row < 0 || row >= isz.y) return 0.0;
    return texelFetch(sTD2DInputs[0], ivec2(slot, row), 0).r;
}

void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    int W = int(uOpt.y), H = int(uOpt.z);
    if (p.x >= W || p.y >= H) return;
    int cell = max(1, int(uMon.y));
    int tx = max(1, int(uMon.x));
    ivec2 tile = ivec2(32, 16) * cell + ivec2(4);              // 4 px gutter between universes
    ivec2 q = ivec2(p.x, H - 1 - p.y);                          // top-left origin
    ivec2 t = q / tile;
    ivec2 l = q - t * tile;
    int u = t.y * tx + t.x;
    vec4 c = vec4(0.04, 0.04, 0.05, 1.0);
    ivec2 osz = textureSize(sTD2DInputs[0], 0);
    ivec2 vsz = textureSize(sTD2DInputs[1], 0);
    if (t.x < tx && u < int(uMon.w) && l.x < 32 * cell && l.y < 16 * cell) {
        int row = int(uMon.z) + u;
        ivec2 ce = l / cell;
        int slot = ce.y * 32 + ce.x;
        ivec2 lc = l - ce * cell;                               // pixel inside the slot cell
        if (row < osz.y && slot < osz.x) {
            float o = ownerAt(osz, slot, row);
            float v = (row < vsz.y && slot < vsz.x) ? texelFetch(sTD2DInputs[1], ivec2(slot, row), 0).r / 255.0 : 0.0;
            int mode = int(uOpt.x + 0.5);
            if (o < -0.5) {
                c.rgb = vec3(0.95, 0.08, 0.08);                 // conflict: always solid red
            } else if (o < 0.5) {
                c.rgb = mode == 2 ? heat(v) * 0.5 + vec3(0.06) : vec3(0.08, 0.08, 0.09);   // free slot
            } else {
                bool pix = o > uInfo.x + 0.5;
                vec3 hue = hsv(fract(o * 0.6180339), pix ? 0.25 : 0.6, 1.0);
                if (mode == 0)      c.rgb = hue * (0.22 + 0.78 * v);
                else if (mode == 1) c.rgb = hue * 0.8;
                else                c.rgb = heat(v);
                bool start = ownerAt(osz, slot - 1, row) != o;  // first slot of a fixture: bright left edge
                if (start && lc.x == 0 && cell > 2) c.rgb = vec3(1.0);
                if (uOpt.w > 0.5 && abs(o - uOpt.w) < 0.5 && (lc.y == 0 || lc.y == cell - 1)) c.rgb = vec3(1.0, 1.0, 0.2);
            }
        } else {
            c.rgb = vec3(0.10, 0.02, 0.02);                     // no data for this row
        }
    }
    TDImageStoreOutput(0, ivec3(p, 0), c);
}
