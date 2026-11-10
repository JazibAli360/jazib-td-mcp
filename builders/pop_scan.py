# pop_scan - shared single-workgroup exclusive prefix scan for lane H (2 users today: pop_linegrowth insert,
# pop_branching alloc; doc docs/builds/pop_lane_h.md). GLSL text + numpy mirrors. The pass that includes SCAN_GLSL
# must run as ONE workgroup of SCAN_T threads (GLSL TOP compute, autodispatchsize off, dispatch 1 x 1 x 1) and call
# scan_excl from uniform control flow (every thread, same number of times). Shared memory: SCAN_T uints = 4 KB
# (Metal threadgroup limit 32 KB; FX6 probes 1a-1c proved shared + barrier() up to local_size 1024 on 31550).
# ASCII only.
import numpy as np

SCAN_T = 1024

SCAN_GLSL = """
#define SCAN_T 1024
shared uint sScan[SCAN_T];
// Hillis-Steele inclusive scan in shared memory, returned as exclusive; total = sum over the workgroup.
// Mirror: pop_scan.hillis_steele_excl. Call from uniform control flow only (barriers inside).
uint scan_excl(uint v, uint tid, out uint total)
{
    sScan[tid] = v;
    barrier();
    for (uint off = 1u; off < SCAN_T; off <<= 1u) {
        uint add = tid >= off ? sScan[tid - off] : 0u;
        barrier();
        sScan[tid] += add;
        barrier();
    }
    total = sScan[SCAN_T - 1u];
    uint incl = sScan[tid];
    barrier();
    return incl - v;
}
"""


def exclusive_scan(v):
    v = np.asarray(v, dtype=np.int64)
    out = np.zeros_like(v)
    if v.size > 1:
        out[1:] = np.cumsum(v)[:-1]
    return out, int(v.sum())


def hillis_steele_excl(v):
    """Step-by-step simulation of SCAN_GLSL (same off loop, same read-then-barrier-then-add order)."""
    s = np.zeros(SCAN_T, dtype=np.int64)
    v = np.asarray(v, dtype=np.int64)
    s[:v.size] = v
    vv = s.copy()
    off = 1
    while off < SCAN_T:
        add = np.zeros_like(s)
        add[off:] = s[:-off]
        s = s + add
        off <<= 1
    return (s - vv)[:v.size], int(s[-1])
