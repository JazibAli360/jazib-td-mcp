# gen_sdf_logic - numpy mirror of the GEN_sdf shaders (builders/gen_sdf.py shared ray core + composite,
# gen_sdf_<module>.py). Vectorised over sample pixels, float32 like the GPU. `expect_rm(module, U, xs, ys, W, H, ref)`
# = the rgba the module's `rm` pass writes at rm texels (xs, ys) (TD: y up), from the uniform values read live
# (U = {name: (x, y, z, w)}); `compare()` scores live vs mirror; `compose_px()` = the fx composite at one output pixel.
# Uniform specs are evaluated with gen_pattern_logic.uniforms (same mini-language). Runs in TD (numpy) and offline.
# ASCII only.
import math
import os
import numpy as np

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
if not os.path.isdir(HERE):                                     # offline copies of the repo
    HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else HERE
_GPL = {}
exec(open(os.path.join(HERE, 'gen_pattern_logic.py')).read(), _GPL)
uniforms = _GPL['uniforms']
sample_points = _GPL['sample_points']
CAPS = {'MAXSTEPS': 512, 'MAXSHADOW': 64, 'MAXAO': 8, 'MAXIT': 32, 'MAXIT2D': 8192}
F = np.float32
TAU = F(6.283185307)
U32 = 0xffffffff


def f(x):
    return np.asarray(x, dtype=F)


# ------------------------------------------------------------------ vector helpers ((N, 3) arrays)
def length(v):
    return np.sqrt(np.sum(v * v, axis=-1))


def dot(a, b):
    return np.sum(a * b, axis=-1)


def normalize(v):
    return v / length(v)[..., None]


def v3(x, y, z):
    return np.stack([f(x), f(y), f(z)], axis=-1)


def fract(x):
    return x - np.floor(x)


def gmod(x, y):
    return x - y * np.floor(x / y)


def mix(a, b, t):
    return a + (b - a) * t


def clamp(x, a, b):
    return np.minimum(np.maximum(x, a), b)


def smin(a, b, k):
    k = max(float(k), 1e-5)
    h = np.maximum(F(k) - np.abs(a - b), F(0)) / F(k)
    return np.minimum(a, b) - h * h * F(k) * F(0.25)


def sdBox(p, b):
    q = np.abs(p) - f(b)
    return length(np.maximum(q, F(0))) + np.minimum(np.max(q, axis=-1), F(0))


def rot2(x, y, a):
    c, s = np.cos(a), np.sin(a)
    return c * x - s * y, s * x + c * y


def lb32(x):
    M = np.uint64(U32)
    x = np.asarray(x, dtype=np.uint64) & M
    x ^= x >> np.uint64(16)
    x = (x * np.uint64(0x7feb352d)) & M
    x ^= x >> np.uint64(15)
    x = (x * np.uint64(0x846ca68b)) & M
    x ^= x >> np.uint64(16)
    return x


def h2(cx, cy, s):
    M = np.uint64(U32)
    cx = (np.asarray(cx, dtype=np.int64) & U32).astype(np.uint64)
    cy = (np.asarray(cy, dtype=np.int64) & U32).astype(np.uint64)
    s = np.uint64((int(s) * 2654435761) & U32)
    v = ((cx * np.uint64(1597334677)) & M) ^ lb32(cy ^ s)
    return (lb32(v).astype(np.float64) / 4294967296.0).astype(F)


# palettes (= GLSL_COMMON PA..PD)
PA = [(0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.4, 0.6, 0.8), (0.6, 0.45, 0.2), (0.5, 0.5, 0.5), (0.8, 0.5, 0.4)]
PB = [(0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (0.4, 0.4, 0.2), (0.4, 0.35, 0.2), (0.5, 0.5, 0.5), (0.2, 0.4, 0.2)]
PC = [(1.0, 1.0, 1.0), (1.0, 0.7, 0.4), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0), (2.0, 1.0, 0.0), (2.0, 1.0, 1.0)]
PD = [(0.0, 0.33, 0.67), (0.0, 0.15, 0.2), (0.0, 0.05, 0.1), (0.0, 0.05, 0.15), (0.5, 0.2, 0.25), (0.0, 0.25, 0.25)]


class Ctx(object):
    """GLSL globals T STEP AGE ENV LEVEL SEED RES + the uniforms as float32 vectors."""

    def __init__(self, U, W, H):
        self.U = dict((k, f(v)) for k, v in U.items())
        d, b = self.U['uDrv'], self.U['uBeat']
        self.T, self.STEP, self.AGE = d[0], d[1], d[2]
        self.ENV = F(b[0] * np.exp(-d[2] / max(b[1], F(1e-3))))
        self.LEVEL = F(b[2] * d[3])
        self.SEED = int(int(b[3]) & U32)
        self.RES = (F(W), F(H))

    def __getitem__(self, k):
        return self.U[k]


def pal(C, k):
    """palk(): k (N,) -> rgb (N, 3)."""
    up = C['uPal']
    kk = k * up[1] + up[2] + up[3] * C.T
    i = int(up[0] + 0.5)
    if i <= 0:
        t = 1.0 - np.abs(fract(kk * F(0.5)) * F(2) - F(1))
        return mix(C['uCa'][:3][None, :], C['uCb'][:3][None, :], t[:, None])
    if i == 1:
        return np.repeat(C['uCa'][:3][None, :], len(kk), axis=0)
    j = min(i - 2, 5)
    a, b, c, d = f(PA[j]), f(PB[j]), f(PC[j]), f(PD[j])
    return a + b * np.cos(TAU * (c[None, :] * kk[:, None] + d[None, :]))


# ------------------------------------------------------------------ module SDFs (mirror the module GLSL)
class Scene(object):
    def __init__(self, C):
        self.C = C
        m0, m1, m2, m3 = C['uM0'], C['uM1'], C['uM2'], C['uM3']
        T, ENV, LEVEL = C.T, C.ENV, C.LEVEL
        self.PUL = F(1.0) + LEVEL + ENV
        self.MORPH = float(np.clip(m0[2] + m0[3] * (F(0.5) - F(0.5) * np.cos(TAU * m1[0] * T)) + m1[1] * ENV, 0, 1))
        fi = np.arange(16, dtype=F)
        self.BC = F(1.2) * np.stack([np.sin(T * F(0.7) * (F(1) + F(0.13) * fi) + fi * F(1.7)),
                                     np.cos(T * F(0.53) * (F(1) + F(0.11) * fi) + fi * F(2.3)),
                                     np.sin(T * F(0.61) * (F(1) + F(0.07) * fi) + fi * F(0.9))], axis=-1)
        self.BR = F(0.35) * (F(0.6) + F(0.4) * fract(fi * F(0.618034))) * (F(1) + F(0.5) * LEVEL + F(0.3) * ENV)
        fi6 = np.arange(6, dtype=F)
        a1 = T * (F(0.4) + F(0.15) * fi6) + fi6
        a2 = T * (F(0.3) + F(0.1) * fi6) + F(0.5) * fi6
        self.RC = np.stack([np.cos(a1), np.sin(a1), np.cos(a2), np.sin(a2)], axis=-1)

    def tunnel(self, p):
        m = np.maximum(np.abs(p[:, 0]), np.abs(p[:, 1]))
        qz = gmod(p[:, 2] + F(0.5), F(1.0)) - F(0.5)
        return np.minimum(F(1.2) - m, np.maximum(np.abs(qz) - F(0.5) * self.C['uM1'][3] * self.PUL, F(0.95) - m))

    def gyroid(self, p):
        q = F(2) * p
        g = dot(np.sin(q), np.cos(q[:, [2, 0, 1]]))
        return np.maximum((np.abs(g) - self.C['uM1'][3] * self.PUL) * F(0.25),
                          F(0.8) - np.sqrt(p[:, 0] ** 2 + p[:, 1] ** 2))

    def sponge(self, p):
        d = sdBox(p, (1.0, 1.0, 1.0))
        s = F(1)
        n = int(self.C['uM2'][0] + 0.5)
        for _i in range(min(n, 8)):
            a = gmod(p * s, F(2)) - F(1)
            s = s * F(3)
            r = np.abs(F(1) - F(3) * np.abs(a))
            mx = lambda i, j: np.maximum(r[:, i], r[:, j])
            c = (np.minimum(mx(0, 1), np.minimum(mx(1, 2), mx(2, 0))) - F(1)) / s
            d = np.maximum(d, c)
        return d

    def apollo(self, p):
        sc = np.ones(len(p), dtype=F)
        orb = np.full(len(p), 1e10, dtype=F)
        n = int(self.C['uM2'][0] + 0.5) + 4
        for _i in range(min(n, 12)):
            p = F(-1) + F(2) * fract(F(0.5) * p + F(0.5))
            r2 = np.maximum(dot(p, p), F(1e-6))
            orb = np.minimum(orb, r2)
            k = self.C['uM3'][2] / r2
            p = p * k[:, None]
            sc = sc * k
        return F(0.25) * np.abs(p[:, 1]) / sc, orb

    def blobs(self, p):
        d = np.full(len(p), 1e10, dtype=F)
        n = int(self.C['uM2'][2] + 0.5)
        for i in range(min(n, 16)):
            d = smin(d, length(p - self.BC[i][None, :]) - self.BR[i], self.C['uM2'][1])
        return d

    def lattice(self, p):
        q = p - np.floor(p + F(0.5))
        l2 = lambda i, j: np.sqrt(q[:, i] ** 2 + q[:, j] ** 2)
        return np.minimum(np.minimum(l2(1, 2), l2(0, 2)), l2(0, 1)) - F(0.5) * self.C['uM1'][3] * self.PUL

    def city(self, p):
        C = self.C
        idx = np.floor(p[:, 0] + F(0.5))
        idz = np.floor(p[:, 2] + F(0.5))
        qx, qz = p[:, 0] - idx, p[:, 2] - idz
        ix, iz = idx.astype(np.int64), idz.astype(np.int64)
        h = (F(0.3) + F(1.5) * h2(ix, iz, C.SEED) + F(0.8) * C.ENV * h2(ix, iz, C.SEED + 7)) * (F(1) + F(0.5) * C.LEVEL)
        b = _sdbox_h(qx, p[:, 1] + F(1) - h, qz, h)
        return np.minimum(p[:, 1] + F(1), np.minimum(b, F(0.55) - np.maximum(np.abs(qx), np.abs(qz))))

    def rings(self, p):
        d = np.full(len(p), 1e10, dtype=F)
        n = min(max(int(self.C['uM2'][0] + 0.5), 1), 6)
        th = F(0.5) * self.C['uM1'][3] * self.PUL
        for i in range(n):
            r = self.RC[i]
            x, y, z = p[:, 0], p[:, 1], p[:, 2]
            y, z = r[0] * y - r[1] * z, r[1] * y + r[0] * z
            x, y = r[2] * x - r[3] * y, r[3] * x + r[2] * y
            R = F(1.5) - F(0.22) * F(i)
            a = np.sqrt(x * x + z * z) - R
            d = np.minimum(d, np.sqrt(a * a + y * y) - th)
        return d

    def stairs(self, p):
        C = self.C
        T = C.T
        DA, DH, RH, NS = TAU / F(12), F(0.2), F(1.6), F(24)
        y0 = F(0.5) * NS * DH
        ka = np.arctan2(p[:, 2], p[:, 0]) / DA
        kc = ka + F(12) * np.floor(((p[:, 1] + y0) / DH - ka) / F(12) + F(0.5))
        d = np.full(len(p), 1e10, dtype=F)
        for j in range(3):
            k = np.floor(kc + F(0.5)) + F(j - 1)
            ok = (k >= 0) & (k <= NS - 1)
            th = k * DA
            q = p - np.stack([RH * np.cos(th), k * DH - y0 + F(0.05) * np.sin(T * F(1.3) + k), RH * np.sin(th)], -1)
            x, z = rot2(q[:, 0], q[:, 2], -th)
            x, y = rot2(x, q[:, 1], F(0.08) * np.sin(T * F(0.9) + F(0.7) * k))
            b = sdBox(np.stack([x, y, z], -1).astype(F), (0.38, float(F(0.4) * C['uM1'][3] * self.PUL), 0.24)) - F(0.02)
            d = np.where(ok, np.minimum(d, b), d)
        thd = NS * DA
        q = p - f([RH * np.cos(thd), NS * DH - y0 + F(0.55), RH * np.sin(thd)])
        x, z = rot2(q[:, 0], q[:, 2], -thd)
        q = np.stack([x, q[:, 1], z], -1).astype(F)
        door = np.maximum(sdBox(q, (0.08, 0.78, 0.5)), -sdBox(q, (0.3, 0.64, 0.36)))
        door = np.minimum(door, sdBox(q, (0.012, 0.64, 0.36)))
        cl = p[:, 1] + y0 + F(0.7) + F(0.25) * np.sin(p[:, 0] * F(1.1) + T * F(0.15)) * np.sin(p[:, 2] * F(0.9) - T * F(0.1))
        return np.minimum(np.minimum(d, door), cl)

    def scene(self, sid, p):
        if sid == 3:
            return self.apollo(p)[0]
        return [self.tunnel, self.gyroid, self.sponge, None, self.blobs, self.lattice, self.city, self.rings,
                self.stairs][min(sid, 8)](p)

    def scenek(self, sid, p):
        C = self.C
        if sid == 0:
            return F(0.1) * p[:, 2] + F(0.2) * np.maximum(np.abs(p[:, 0]), np.abs(p[:, 1]))
        if sid == 1:
            return F(0.1) * (p[:, 0] + p[:, 1] + p[:, 2])
        if sid == 2:
            return F(0.3) * length(p)
        if sid == 3:
            return F(0.5) * np.sqrt(self.apollo(p)[1])
        if sid == 4:
            return F(0.25) * p[:, 1] + F(0.15) * length(p)
        if sid == 5:
            return F(0.05) * (np.floor(p[:, 0] + F(0.5)) + np.floor(p[:, 1] + F(0.5)) + np.floor(p[:, 2] + F(0.5)))
        if sid == 6:
            ix = np.floor(p[:, 0] + F(0.5)).astype(np.int64)
            iz = np.floor(p[:, 2] + F(0.5)).astype(np.int64)
            return h2(ix, iz, C.SEED + 3) + F(0.1) * p[:, 1]
        if sid == 7:
            return F(0.2) * length(p)
        return np.where(p[:, 1] > F(2.6), F(1.0), F(0.15) + F(0.15) * clamp((p[:, 1] + F(2.4)) / F(4.8), F(0), F(1))).astype(F)

    def domain(self, p):
        C = self.C
        m1, m2, m3 = C['uM1'], C['uM2'], C['uM3']
        p = p / m1[2]
        if m3[1] > 0:
            p = p - m3[1] * np.floor(p / m3[1] + F(0.5))
        if m2[3] != 0:
            x, z = rot2(p[:, 0], p[:, 2], m2[3] * p[:, 1])
            p = np.stack([x, p[:, 1], z], axis=-1)
        if m3[0] >= 2:
            sec = TAU / F(math.floor(m3[0] + 0.5))
            a = np.abs(gmod(np.arctan2(p[:, 2], p[:, 0]) + F(0.5) * sec, sec) - F(0.5) * sec)
            r = np.sqrt(p[:, 0] ** 2 + p[:, 2] ** 2)
            p = np.stack([r * np.cos(a), p[:, 1], r * np.sin(a)], axis=-1)
        return p.astype(F)

    def _two(self, fn, p):
        q = self.domain(p)
        A, B = int(self.C['uM0'][0] + 0.5), int(self.C['uM0'][1] + 0.5)
        d = fn(A, q) if self.MORPH < 1.0 else np.zeros(len(p), dtype=F)
        if self.MORPH > 0.0:
            d = mix(d, fn(B, q), F(self.MORPH))
        return d

    def map(self, p):
        return self._two(self.scene, p) * self.C['uM1'][2]

    def mapk(self, p):
        return self._two(self.scenek, p)


def _sdbox_h(x, y, z, h):
    """sdBox(vec3(x, y, z), vec3(0.35, h, 0.35)) with a per-point half height h."""
    q = np.stack([np.abs(x) - F(0.35), np.abs(y) - h, np.abs(z) - F(0.35)], axis=-1)
    return length(np.maximum(q, F(0))) + np.minimum(np.max(q, axis=-1), F(0))


class Fractal(object):
    def __init__(self, C):
        self.C = C
        m0, m1, m2, m3, m4 = C['uM0'], C['uM1'], C['uM2'], C['uM3'], C['uM4']
        T = C.T
        self.POW = F(m0[2] + m0[3] * np.sin(m1[0] * T) + m1[1] * C.ENV + C.LEVEL)
        w = m3[1] * T
        self.JC = f([m2[0] + m1[3] * np.cos(w), m2[1] + m1[3] * np.sin(w), m2[2] + m1[3] * F(0.5) * np.sin(F(0.7) * w), m2[3]])
        ka = m4[2] + m4[3] * T
        self.KR = (F(np.cos(ka)), F(np.sin(ka)))

    def bulb(self, p):
        C, P = self.C, self.POW
        jm = C['uM3'][0]
        z = p.copy()
        c = mix(p, self.JC[None, :3], jm)
        dr = np.ones(len(p), dtype=F)
        r = np.zeros(len(p), dtype=F)
        trap = np.full(len(p), 1e10, dtype=F)
        live = np.ones(len(p), dtype=bool)
        n = int(C['uM0'][1] + 0.5)
        pn = np.floor(P + F(0.5))
        ip = bool(abs(P - pn) < F(1e-4) and pn >= F(2))
        ni = int(pn)
        for _i in range(min(n, CAPS['MAXIT'])):
            rr = length(z)
            r = np.where(live, rr, r)
            live = live & (rr <= C['uM1'][2])
            if not live.any():
                break
            L = live
            rl, zl = r[L], z[L]
            ri = F(1) / np.maximum(rl, F(1e-9))
            if ip:                                            # whole power: complex powers (GLSL de_bulb)
                rho = np.sqrt(zl[:, 0] * zl[:, 0] + zl[:, 1] * zl[:, 1])
                ux, uy = zl[:, 2] * ri, rho * ri
                ok = rho > F(1e-9)
                rs = np.where(ok, rho, F(1))
                vx, vy = np.where(ok, zl[:, 0] / rs, F(1)), np.where(ok, zl[:, 1] / rs, F(0))
                unx, uny = np.ones_like(ux), np.zeros_like(ux)
                vnx, vny = np.ones_like(ux), np.zeros_like(ux)
                rn, rb, ex = np.ones_like(ux), rl.copy(), ni
                for _k in range(5):
                    if ex & 1:
                        unx, uny = unx * ux - uny * uy, unx * uy + uny * ux
                        vnx, vny = vnx * vx - vny * vy, vnx * vy + vny * vx
                        rn = rn * rb
                    ex >>= 1
                    if ex == 0:
                        break
                    ux, uy = ux * ux - uy * uy, F(2) * ux * uy
                    vx, vy = vx * vx - vy * vy, F(2) * vx * vy
                    rb = rb * rb
                rpw = rn
                z[L] = rn[:, None] * np.stack([uny * vnx, uny * vny, unx], axis=-1) + c[L]
            else:
                th = np.arccos(clamp(zl[:, 2] * ri, F(-1), F(1))) * P
                ph = np.arctan2(zl[:, 1], zl[:, 0]) * P
                rpw = np.power(rl, P)
                z[L] = rpw[:, None] * np.stack([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)], axis=-1) + c[L]
            dr[L] = rpw * ri * P * dr[L] + (F(1) - jm)
            trap[L] = np.minimum(trap[L], dot(z[L], z[L]))
        return F(0.5) * np.log(np.maximum(r, F(1e-9))) * r / np.maximum(dr, F(1e-9)), trap

    def box(self, p):
        C = self.C
        m3, m4 = C['uM3'], C['uM4']
        jm, S, fl = m3[0], m3[2], m3[3]
        mr2, fr2 = max(m4[0] * m4[0], F(1e-6)), m4[1] * m4[1]
        z = p.copy()
        c = mix(p, self.JC[None, :3], jm)
        dr = np.ones(len(p), dtype=F)
        trap = np.full(len(p), 1e10, dtype=F)
        n = int(C['uM0'][1] + 0.5)
        for _i in range(min(n, CAPS['MAXIT'])):
            z = clamp(z, -fl, fl) * F(2) - z
            r2 = dot(z, z)
            k = np.where(r2 < mr2, fr2 / mr2, np.where(r2 < fr2, fr2 / np.maximum(r2, F(1e-30)), F(1))).astype(F)
            z = z * k[:, None]
            dr = dr * k
            z = z * S + c
            dr = dr * abs(S) + (F(1) - jm)
            trap = np.minimum(trap, r2)
        return length(z) / np.abs(dr), trap

    def quat(self, p):
        C = self.C
        z = np.concatenate([p, np.zeros((len(p), 1), dtype=F)], axis=-1)
        md2 = np.ones(len(p), dtype=F)
        mz2 = dot(z, z)
        trap = np.full(len(p), 1e10, dtype=F)
        live = np.ones(len(p), dtype=bool)
        n = int(C['uM0'][1] + 0.5)
        for _i in range(min(n, CAPS['MAXIT'])):
            if not live.any():
                break
            L = live
            zl = z[L]
            md2[L] = md2[L] * F(4) * mz2[L]
            zn = np.concatenate([(zl[:, 0] * zl[:, 0] - dot(zl[:, 1:], zl[:, 1:]))[:, None], F(2) * zl[:, :1] * zl[:, 1:]],
                                axis=-1) + self.JC[None, :]
            z[L] = zn
            mz2[L] = dot(zn, zn)
            trap[L] = np.minimum(trap[L], mz2[L])
            live = live & ~(mz2 > F(256))
        return F(0.25) * np.sqrt(mz2 / np.maximum(md2, F(1e-20))) * np.log(np.maximum(mz2, F(1e-20))), trap

    def kifs(self, p):
        C = self.C
        S, o = C['uM5'][0], C['uM5'][1]
        kc, ks = self.KR
        sc = F(1)
        trap = np.full(len(p), 1e10, dtype=F)
        n = int(C['uM0'][1] + 0.5)
        p = p.copy()
        for _i in range(min(n, CAPS['MAXIT'])):
            p = np.abs(p)
            for i, j in ((0, 1), (0, 2), (1, 2)):
                sw = p[:, i] < p[:, j]
                a, b = p[sw, i].copy(), p[sw, j].copy()
                p[sw, i], p[sw, j] = b, a
            x, y = kc * p[:, 0] - ks * p[:, 1], ks * p[:, 0] + kc * p[:, 1]
            p = np.stack([x, y, p[:, 2]], axis=-1)
            p = p * S - o * (S - F(1))
            p[:, 2] = np.where(p[:, 2] < F(-0.5) * o * (S - F(1)), p[:, 2] + o * (S - F(1)), p[:, 2])
            sc = sc * S
            trap = np.minimum(trap, dot(p, p))
        return sdBox(p, (1.0, 1.0, 1.0)) / sc, trap

    def de(self, p):
        ty = int(self.C['uM0'][0] + 0.5)
        return [self.bulb, self.box, self.quat, self.kifs][min(ty, 3)](p.astype(F))

    def map(self, p):
        return self.de(p)[0]

    def mapk(self, p):
        return np.sqrt(np.maximum(self.de(p)[1], F(0)))


MAPS = {'scene': Scene, 'fractal': Fractal}


# ------------------------------------------------------------------ shared ray core (GLSL_RAY)
def fwd_dir(yaw, pitch):
    return f([np.cos(pitch) * np.sin(yaw), np.sin(pitch), np.cos(pitch) * np.cos(yaw)])


def camera(C, P):
    """P (N, 2) pixel centres -> ro (N, 3), rd (N, 3), fk."""
    cam, cam2, cam3, cam4 = C['uCam'], C['uCam2'], C['uCam3'], C['uCam4']
    W, H = C.RES
    uvx = (P[:, 0] - F(0.5) * W) / H
    uvy = (P[:, 1] - F(0.5) * H) / H
    path = int(cam[0] + 0.5)
    T = C.T
    yaw = cam[2] + cam2[0] * T + cam3[0] * C.STEP
    pitch = cam[3]
    dist = cam[1] * (F(1) - cam3[1] * C.ENV) * (F(1) - cam3[2] * C.LEVEL)
    ta = cam4[:3]
    if path == 1:
        fw = fwd_dir(yaw - cam2[0] * T, pitch)
        s = cam2[1] * T
        ro = ta + fw * s + cam4[3] * f([np.sin(F(0.7) * s), F(0.6) * np.sin(F(0.53) * s), 0.0])
        look = ro + fw + cam4[3] * F(0.3) * f([np.cos(F(0.7) * s), 0.0, 0.0])
    else:
        if path == 2:
            pitch = pitch + cam4[3] * F(0.6) * np.sin(F(0.37) * T)
            dist = dist * (F(1) + F(0.3) * cam4[3] * np.sin(F(0.23) * T))
        ro = ta + dist * fwd_dir(yaw, pitch)
        look = ta
    ww = f(look - ro)
    ww = ww / np.sqrt(np.sum(ww * ww))
    roll = cam2[3] + cam3[3] * T
    up = f([np.sin(roll), np.cos(roll), 0.0])
    uu = np.cross(ww, up).astype(F)
    lu = np.sqrt(np.sum(uu * uu))
    uu = f([1.0, 0.0, 0.0]) if lu < 1e-4 else uu / lu
    vv = np.cross(uu, ww).astype(F)
    fk = F(0.5) / np.tan(F(0.5) * cam2[2])
    rd = normalize(uvx[:, None] * uu[None, :] + uvy[:, None] * vv[None, :] + fk * ww[None, :]).astype(F)
    return np.repeat(f(ro)[None, :], len(P), axis=0), rd, F(fk)


class Ray(object):
    def __init__(self, module, U, W, H):
        self.C = Ctx(U, W, H)
        self.M = MAPS[module](self.C)
        sa = self.C['uObj'][0] + self.C['uObj'][1] * self.C.T
        self.SPIN = (F(np.cos(sa)), F(np.sin(sa)))

    def _spin(self, p):
        c, s = self.SPIN
        return np.stack([c * p[:, 0] + s * p[:, 2], p[:, 1], -s * p[:, 0] + c * p[:, 2]], axis=-1).astype(F)

    def sdf(self, p):
        return self.M.map(self._spin(p)).astype(F)

    def sdfk(self, p):
        return self.M.mapk(self._spin(p)).astype(F)

    def normal(self, p, h):
        k = [(1, -1, -1), (-1, -1, 1), (-1, 1, -1), (1, 1, 1)]
        acc = np.zeros_like(p)
        for kk in k:
            kv = f(kk)
            acc += kv[None, :] * self.sdf(p + kv[None, :] * h[:, None])[:, None]
        return normalize(acc)

    def shadow(self, ro, rd, k, ns):
        res = np.ones(len(ro), dtype=F)
        t = np.full(len(ro), 0.02, dtype=F)
        live = np.ones(len(ro), dtype=bool)
        for _i in range(min(ns, CAPS['MAXSHADOW'])):
            if not live.any():
                break
            L = live
            h = self.sdf(ro[L] + rd[L] * t[L][:, None])
            res[L] = np.minimum(res[L], k * h / t[L])
            t[L] = t[L] + clamp(h, F(0.02), F(0.4))
            live = live & ~((res < F(0.001)) | (t > F(12)))
        return clamp(res, F(0), F(1))

    def ambocc(self, p, n, na, s):
        if na <= 0:
            return np.ones(len(p), dtype=F)
        occ = np.zeros(len(p), dtype=F)
        sca = F(1)
        for i in range(min(na, CAPS['MAXAO'])):
            h = F(0.01) + F(0.12) * F(i) / F(max(na - 1, 1))
            occ = occ + (h - self.sdf(p + h * n)) * sca
            sca = sca * F(0.95)
        return clamp(F(1) - s * occ, F(0), F(1))

    def shade(self, m, base, n, rd, Lv, sh, oc):
        C = self.C
        lt, ltc, mat = C['uLt'], C['uLtc'], C['uMat']
        lc = ltc[:3] * ltc[3]
        dif = np.maximum(dot(n, Lv[None, :]), F(0)) * sh
        amb = lt[2] * oc
        fre = np.power(clamp(F(1) + dot(n, rd), F(0), F(1)), F(3))
        hv = normalize(Lv[None, :] - rd)
        spe = np.power(np.maximum(dot(n, hv), F(0)), lt[3]) * sh
        if m == 0:
            return base * (lc[None, :] * dif[:, None] + amb[:, None])
        if m == 1:
            return base * (lc[None, :] * dif[:, None] + amb[:, None]) + lc[None, :] * (spe * (F(0.25) + F(0.75) * fre))[:, None]
        if m == 2:
            r = rd - F(2) * dot(n, rd)[:, None] * n
            sky = mix(C['uFog'][None, :3], ltc[None, :3], (F(0.5) + F(0.5) * r[:, 1])[:, None]) * F(0.6) + \
                ltc[None, :3] * np.power(np.maximum(dot(r, Lv[None, :]), F(0)), F(24))[:, None]
            return base * sky * (F(0.35) + F(0.65) * oc)[:, None] + lc[None, :] * spe[:, None]
        if m == 3:
            return base * (F(0.2) * dif + F(0.2) * amb)[:, None] + base * (fre * mat[2] * F(2))[:, None] + base * mat[3]
        c = base * (lc[None, :] * (np.floor(dif * F(3) + F(0.5)) / F(3))[:, None] + amb[:, None])
        out = dot(n, -rd) < mat[2] * F(0.5)
        return np.where(out[:, None], c * F(0.08), c)

    def render(self, xs, ys):
        C = self.C
        P = np.stack([f(xs) + F(0.5), f(ys) + F(0.5)], axis=-1)
        ro, rd, fk = camera(C, P)
        pa = F(1) / (C.RES[1] * fk)
        q, q2, glw = C['uQ'], C['uQ2'], C['uGlow']
        N = int(q[0] + 0.5)
        n = len(P)
        t = np.zeros(n, dtype=F)
        tp = np.zeros(n, dtype=F)
        rp = np.zeros(n, dtype=F)
        om0 = F(max(C['uObj'][2], F(1)))
        om = np.full(n, om0, dtype=F)
        gl = np.zeros(n, dtype=F)
        st = np.zeros(n, dtype=F)
        e = np.zeros(n, dtype=F)
        hit = np.zeros(n, dtype=bool)
        live = np.ones(n, dtype=bool)
        for _i in range(min(N, CAPS['MAXSTEPS'])):          # over-relaxed sphere tracing (GLSL_RAY main)
            if not live.any():
                break
            L = np.nonzero(live)[0]
            d = self.sdf(ro[L] + rd[L] * t[L][:, None])
            r = d * q[3]
            fail = (om[L] > F(1)) & (r + rp[L] < t[L] - tp[L])
            Fi = L[fail]
            t[Fi] = tp[Fi] + rp[Fi]
            om[Fi] = F(1)
            st[Fi] += F(1)
            G = L[~fail]
            dg, rg = d[~fail], r[~fail]
            gl[G] += np.exp(-np.maximum(dg, F(0)) * glw[1]) * om[G]
            e[G] = q[1] * pa * np.maximum(t[G], F(0.05))
            h = dg < e[G]
            hit[G[h]] = True
            live[G[h]] = False
            M_ = G[~h]
            tp[M_] = t[M_]
            rp[M_] = rg[~h]
            t[M_] = t[M_] + rg[~h] * om[M_]
            om[M_] = om0
            st[M_] += F(1)
            live[M_[t[M_] > q[2]]] = False
        view = int(C['uMat'][1] + 0.5)
        pos = ro + rd * t[:, None]
        out = np.zeros((n, 4), dtype=F)
        if view == 1:
            out[:, 0], out[:, 1], out[:, 2] = t, hit.astype(F), st
            if hit.any():
                out[hit, 3] = self.sdfk(pos[hit])
            return out
        col = np.zeros((n, 3), dtype=F)
        a = np.zeros(n, dtype=F)
        if hit.any():
            I = np.nonzero(hit)[0]
            hh = np.maximum(e[I], F(1e-4))
            nr = self.normal(pos[I], hh)
            if view == 2:
                out[I, :3] = nr * F(0.5) + F(0.5)
                out[I, 3] = 1.0
            else:
                lt = C['uLt']
                Lv = fwd_dir(lt[0], lt[1])
                ns = int(q2[0] + 0.5)
                sh = self.shadow(pos[I] + nr * (hh * F(2))[:, None], np.repeat(Lv[None, :], len(I), axis=0), q2[1], ns) \
                    if ns > 0 else np.ones(len(I), dtype=F)
                oc = self.ambocc(pos[I], nr, int(q2[2] + 0.5), q2[3])
                base = pal(C, self.sdfk(pos[I]))
                c = self.shade(int(C['uMat'][0] + 0.5), base, nr, rd[I], Lv, sh, oc)
                a[I] = np.exp(-C['uFog'][3] * t[I])
                col[I] = c * a[I][:, None]
        if view == 2:
            return out
        if view == 3:
            col = pal(C, st / F(max(N, 1)))
            a[:] = 1.0
        g = glw[0] * (F(1) + glw[2] * C.ENV) * gl / F(64)
        col = col + pal(C, np.full(n, glw[3], dtype=F)) * g[:, None]
        a = clamp(a + g, F(0), F(1))
        out[:, :3], out[:, 3] = col, a
        return out


# ------------------------------------------------------------------ fractal2d (flat)
def _cmul(ax, ay, bx, by):
    return ax * bx - ay * by, ax * by + ay * bx


def flat2d(U, xs, ys, W, H, ref=None):
    with np.errstate(all='ignore'):
        return _flat2d(U, xs, ys, W, H, ref)


def _flat2d(U, xs, ys, W, H, ref=None):
    C = Ctx(U, W, H)
    m0, m1, m2, m3, m4, m5 = (C['uM%d' % i] for i in range(6))
    ty, IT, cm = int(m0[0] + 0.5), int(m0[1] + 0.5), int(m0[2] + 0.5)
    T = C.T
    pw = F(m3[0] + m5[3] * np.sin(m3[1] * T))
    sc = F(np.exp2(m1[2] - (m1[3] * T + m3[2] * C.ENV + C.LEVEL)))
    px, py = f(xs) + F(0.5), f(ys) + F(0.5)
    ux, uy = rot2((px - F(0.5) * C.RES[0]) / C.RES[1], (py - F(0.5) * C.RES[1]) / C.RES[1], m3[3] + m4[0] * T)
    ux, uy = (ux * sc).astype(F), (uy * sc).astype(F)
    wj = m2[3] * T
    jx, jy = F(m2[0] + m2[2] * np.cos(wj)), F(m2[1] + m2[2] * np.sin(wj))
    n = len(ux)
    dadd = F(0) if ty == 1 else F(1)
    derx = np.full(n, 1.0 if ty == 1 else 0.0, dtype=F)
    dery = np.zeros(n, dtype=F)
    trap = np.full(n, 1e10, dtype=F)
    r2 = np.zeros(n, dtype=F)
    it = np.zeros(n, dtype=np.int64)
    esc = np.zeros(n, dtype=bool)
    live = np.ones(n, dtype=bool)
    B2 = m5[2]

    def trapd(zx, zy):
        if cm == 2:
            return np.abs(zy - m4[2])
        if cm == 3:
            return np.abs(np.sqrt((zx - m4[1]) ** 2 + (zy - m4[2]) ** 2) - m4[3])
        return np.sqrt((zx - m4[1]) ** 2 + (zy - m4[2]) ** 2)

    if m5[1] > 0.5 and ty <= 1:
        R = np.asarray(ref, dtype=F).reshape(-1, 4) if ref is not None else np.zeros((2, 4), dtype=F)
        RL = max(len(R) - 1, 1)
        Z0x, Z0y, Z0lx, Z0ly = R[0, 0], R[0, 1], R[0, 2], R[0, 3]
        dzx = ux.copy() if ty == 1 else np.zeros(n, dtype=F)
        dzy = uy.copy() if ty == 1 else np.zeros(n, dtype=F)
        dcx = np.zeros(n, dtype=F) if ty == 1 else ux
        dcy = np.zeros(n, dtype=F) if ty == 1 else uy
        m = np.zeros(n, dtype=np.int64)
        zx, zy = Z0x + (Z0lx + dzx), Z0y + (Z0ly + dzy)
        for i in range(min(IT, CAPS['MAXIT2D'])):
            L = np.nonzero(live)[0]
            if not len(L):
                break
            Zx, Zy = R[m[L], 0], R[m[L], 1]
            a, b = _cmul(zx[L], zy[L], derx[L], dery[L])
            derx[L], dery[L] = F(2) * a + dadd, F(2) * b
            a, b = _cmul(F(2) * Zx + dzx[L], F(2) * Zy + dzy[L], dzx[L], dzy[L])
            dzx[L], dzy[L] = a + dcx[L], b + dcy[L]
            m[L] += 1
            Rm = R[m[L]]
            zx[L], zy[L] = Rm[:, 0] + (Rm[:, 2] + dzx[L]), Rm[:, 1] + (Rm[:, 3] + dzy[L])
            r2[L] = zx[L] * zx[L] + zy[L] * zy[L]
            trap[L] = np.minimum(trap[L], trapd(zx[L], zy[L]))
            it[L] = i + 1
            e_ = r2[L] > B2
            esc[L[e_]] = True
            live[L[e_]] = False
            K = L[~e_]
            rb = (r2[K] < dzx[K] * dzx[K] + dzy[K] * dzy[K]) | (m[K] >= RL - 1)
            Kb = K[rb]
            Rb = R[m[Kb]]
            dzx[Kb] = (Rb[:, 0] - Z0x) + (Rb[:, 2] - Z0lx + dzx[Kb])
            dzy[Kb] = (Rb[:, 1] - Z0y) + (Rb[:, 3] - Z0ly + dzy[Kb])
            m[Kb] = 0
    else:
        if ty == 1:
            zx, zy = m1[0] + ux, m1[1] + uy
            cx, cy = np.full(n, jx, dtype=F), np.full(n, jy, dtype=F)
        else:
            zx, zy = np.zeros(n, dtype=F), np.zeros(n, dtype=F)
            cx, cy = (m1[0] + ux).astype(F), (m1[1] + uy).astype(F)
        zx, zy = zx.astype(F), zy.astype(F)
        cyc = C['uM6'][0] > 0.5
        zsx, zsy = zx.copy(), zy.copy()
        pk = np.full(n, 8, dtype=np.int64)
        pc = np.zeros(n, dtype=np.int64)
        for i in range(min(IT, CAPS['MAXIT2D'])):
            L = np.nonzero(live)[0]
            if not len(L):
                break
            x, y = zx[L], zy[L]
            if ty == 4:
                r = np.sqrt(x * x + y * y)
                small = r < F(1e-20)
                a = np.arctan2(y, x)
                rr = np.maximum(r, F(1e-30))
                rp = np.power(rr, pw)
                zpx, zpy = rp * np.cos(pw * a), rp * np.sin(pw * a)               # z^pw
                ux, uy = _cmul(zpx, zpy, x, -y)                                    # z^(pw-1) = z^pw conj(z) / r^2
                r2_ = np.maximum(rr * rr, F(1e-30))
                tx, ty_ = _cmul(ux / r2_, uy / r2_, derx[L], dery[L])
                ndx, ndy = pw * tx + dadd, pw * ty_
                nzx, nzy = zpx + cx[L], zpy + cy[L]
                derx[L] = np.where(small, dadd, ndx)
                dery[L] = np.where(small, F(0), ndy)
                zx[L] = np.where(small, cx[L], nzx)
                zy[L] = np.where(small, cy[L], nzy)
            else:
                a, b = _cmul(x, y, derx[L], dery[L])
                derx[L], dery[L] = F(2) * a + dadd, F(2) * b
                if ty == 2:
                    x, y = np.abs(x), np.abs(y)
                if ty == 3:
                    y = -y
                a, b = _cmul(x, y, x, y)
                zx[L], zy[L] = a + cx[L], b + cy[L]
            r2[L] = zx[L] * zx[L] + zy[L] * zy[L]
            trap[L] = np.minimum(trap[L], trapd(zx[L], zy[L]))
            it[L] = i + 1
            e_ = r2[L] > B2
            esc[L[e_]] = True
            live[L[e_]] = False
            if cyc:
                K = L[~e_]
                ddx, ddy = zx[K] - zsx[K], zy[K] - zsy[K]
                stop = ddx * ddx + ddy * ddy < F(1e-12)
                live[K[stop]] = False
                K = K[~stop]
                pc[K] += 1
                sv = K[pc[K] == pk[K]]
                zsx[sv], zsy[sv] = zx[sv], zy[sv]
                pc[sv] = 0
                pk[sv] *= 2
    lp = F(np.log(max(float(pw), 1.0001))) if ty == 4 else F(np.log(2.0))
    with np.errstate(all='ignore'):
        mu = np.where(esc, it.astype(F) + F(1) - np.log(np.maximum(F(0.5) * np.log(r2), F(1e-9))) / lp, F(-1))
        dl = np.maximum(np.sqrt(derx * derx + dery * dery), F(1e-30))
        dep = np.where(esc, F(0.5) * np.sqrt(r2) * np.log(r2) / dl / (sc / C.RES[1]), F(-1))
    out = np.zeros((n, 4), dtype=F)
    if int(C['uMat'][1] + 0.5) == 1:
        out[:, 0], out[:, 1], out[:, 2], out[:, 3] = mu, esc.astype(F), trap, dep
        return out
    inner = m0[3] > 0.5
    ks = F(0.3) * np.log2(F(1) + np.maximum(mu, F(0)))
    if cm == 0:
        k = np.where(esc, ks, trap)
        v = np.where(esc | inner, F(1), F(0))
    elif cm == 4:
        k = np.where(esc, ks, trap)
        with np.errstate(all='ignore'):
            v = np.where(esc, np.exp(-dep / max(m5[0], F(1e-3))), F(1) if inner else F(0))
    else:
        k = trap
        v = np.where(esc | inner, F(1), F(0))
    out[:, :3] = pal(C, k.astype(F)) * v[:, None]
    out[:, 3] = v
    return out


# ------------------------------------------------------------------ aurora (gen_sdf_aurora.py GLSL, line by line)
def _tw(x):
    return np.abs(fract(x) - F(0.5)) * F(2)


def aurora_curtain(qx, qy, w, U):
    m1 = U['uM1']
    a = np.zeros_like(qx)
    amp = F(0.5)
    w = F(w)
    for _o in range(4):
        gx, gy = _tw(qy * F(0.43) + w), _tw(qx * F(0.31) - F(0.7) * w)
        qx, qy = qx + (gx - F(0.5)) * m1[1], qy + (gy - F(0.5)) * m1[1]
        a = a + amp * _tw(qx + F(0.35) * _tw(qy * F(0.23)))
        qx, qy = (F(0.8) * qx - F(0.6) * qy) * F(1.7), (F(0.6) * qx + F(0.8) * qy) * F(1.7)
        amp = amp * F(0.5)
        w = w * F(1.3)
    return np.power(clamp(a / F(0.9375), F(0), F(1)), m1[2]).astype(F)


def aurora_dir(C, xs, ys):
    m2, m3 = C['uM2'], C['uM3']
    px, py = f(xs) + F(0.5), f(ys) + F(0.5)
    ux, uy = (px - F(0.5) * C.RES[0]) / C.RES[1], (py - F(0.5) * C.RES[1]) / C.RES[1]
    yaw, pitch = F(m3[0] + m3[1] * C.T), m2[3]
    ww = f([np.cos(pitch) * np.sin(yaw), np.sin(pitch), np.cos(pitch) * np.cos(yaw)])
    uu = np.cross(ww, f([0.0, 1.0, 0.0]))
    uu = (uu / np.sqrt(np.sum(uu * uu))).astype(F)
    vv = np.cross(uu, ww).astype(F)
    fk = F(0.5) / np.tan(F(0.5) * m3[2])
    rd = ux[:, None] * uu[None, :] + uy[:, None] * vv[None, :] + fk * ww[None, :]
    return normalize(rd.astype(F))


def aurora_sky(C, rd):
    m0, m1, m2, m3, m4, m5 = (C['uM%d' % i] for i in range(6))
    n = rd.shape[0]
    acc = np.zeros((n, 3), dtype=F)
    nsum = np.zeros(n, dtype=F)
    up = rd[:, 1] > 0
    N = int(m0[0] + 0.5)
    inv = F(1.0 / max(N - 1, 1))
    dx, dz = m2[1] * C.T, m2[2] * C.T
    w = m2[0] * C.T
    ry = np.where(up, rd[:, 1], F(1)).astype(F)
    for i in range(min(N, 64)):
        k = F(i) * inv
        t = np.minimum((m0[1] + F(i) * m0[2]) / ry, F(60))
        nn = aurora_curtain(rd[:, 0] * t * m1[0] + dx, rd[:, 2] * t * m1[0] + dz, w, C)
        nsum = nsum + nn
        acc = acc + pal(C, np.full(n, k, dtype=F)) * (nn * np.exp(-m0[3] * F(4) * k - F(0.035) * t))[:, None]
    g = m1[3] * (F(1) + m5[1] * C.ENV + m5[2] * C.LEVEL) / F(max(N, 1)) * F(6)
    acc = acc * (g * clamp(rd[:, 1] * m3[3], F(0), F(1)))[:, None]
    nsum = nsum / F(max(N, 1))
    if m4[0] > 0:
        s = rd * m4[1]
        c = np.floor(s).astype(np.int64)
        h = h2(c[:, 0], c[:, 1] ^ (c[:, 2] * 7919), C.SEED)
        h1 = h2(c[:, 1], c[:, 2] ^ (c[:, 0] * 7919), (C.SEED + 1) & U32)
        h3 = h2(c[:, 2], c[:, 0] ^ (c[:, 1] * 7919), (C.SEED + 2) & U32)
        sp = c.astype(F) + F(0.5) + (np.stack([h1, h3, h / max(m4[0], F(1e-6))], -1) - F(0.5)) * F(0.5)
        d = length(s - sp)
        tw2 = F(0.65) + F(0.35) * np.sin(m4[2] * C.T + h1 * TAU)
        add = np.maximum(F(0), F(1) - d * F(2.5)) * tw2 * clamp(rd[:, 1] * F(20), F(0), F(1))
        acc = acc + np.where((h < m4[0])[:, None], add[:, None], F(0))
    acc = np.where(up[:, None], acc, F(0))
    nsum = np.where(up, nsum, F(0))
    return acc.astype(F), nsum.astype(F)


def aurora_rm(U, xs, ys, W, H):
    C = Ctx(U, W, H)
    m4, m5 = C['uM4'], C['uM5']
    rd = aurora_dir(C, xs, ys)
    col, ns = aurora_sky(C, rd)
    below = rd[:, 1] < 0
    if below.any() and m4[3] > 0:
        rb = rd[below]
        rp = m5[0] * np.sin(rb[:, 0] * F(140) / np.maximum(-rb[:, 1], F(0.05)) + C.T * F(1.7)) * \
            np.sin(rb[:, 2] * F(90) + C.T * F(1.3))
        r2 = normalize(np.stack([rb[:, 0] + rp, -rb[:, 1], rb[:, 2]], -1).astype(F))
        cb, nb = aurora_sky(C, r2)
        col[below] = cb * (m4[3] * (F(0.6) + F(0.4) * clamp(F(1) + rb[:, 1] * F(4), F(0), F(1))))[:, None]
        ns[below] = nb
    if int(C['uMat'][1] + 0.5) == 1:
        return np.stack([ns, rd[:, 1], col[:, 1], np.ones_like(ns)], -1)
    a = clamp(np.max(col, axis=-1), F(0), F(1))
    return np.concatenate([col, a[:, None]], -1)


# ------------------------------------------------------------------ sky (gen_sdf_sky.py GLSL, line by line)
SKY_RP, SKY_RA = F(6371.0), F(6471.0)
SKY_KR = f([5.5e-3, 13.0e-3, 22.4e-3])


def sky_rsi(r0, rd, sr):
    a = np.sum(rd * rd, -1)
    b = F(2) * np.sum(rd * r0, -1)
    c = np.sum(r0 * r0, -1) - F(sr) * F(sr)
    d = b * b - F(4) * a * c
    q = np.sqrt(np.maximum(d, F(0)))
    x = np.where(d < 0, F(1e5), (-b - q) / (F(2) * a))
    y = np.where(d < 0, F(-1e5), (-b + q) / (F(2) * a))
    return x.astype(F), y.astype(F)


def sky_rm(U, xs, ys, W, H):
    C = Ctx(U, W, H)
    m0, m1, m2, m3, m4 = (C['uM%d' % i] for i in range(5))
    n = len(xs)
    px, py = f(xs) + F(0.5), f(ys) + F(0.5)
    ux, uy = (px - F(0.5) * C.RES[0]) / C.RES[1], (py - F(0.5) * C.RES[1]) / C.RES[1]
    yaw, pitch = m3[3], m3[2]
    ww = f([np.cos(pitch) * np.sin(yaw), np.sin(pitch), np.cos(pitch) * np.cos(yaw)])
    uu = np.cross(ww, f([0.0, 1.0, 0.0]))
    uu = (uu / np.sqrt(np.sum(uu * uu))).astype(F)
    vv = np.cross(uu, ww).astype(F)
    rd = normalize((ux[:, None] * uu + uy[:, None] * vv + (F(0.5) / np.tan(F(0.5) * m4[0])) * ww).astype(F))
    el = m0[3]
    if m0[0] < 0.5:
        el = F(np.sin(TAU * (m0[1] + m0[2] * C.T - F(0.25))) * F(1.5707963))
    az = m1[0]
    ps = f([np.cos(el) * np.sin(az), np.sin(el), np.cos(el) * np.cos(az)])
    r0 = np.tile(f([0.0, SKY_RP + m2[3], 0.0]), (n, 1))
    kR, kM, g = SKY_KR * m2[0], F(21e-3) * m2[1], m2[2]
    shR, shM = F(8.0), F(1.2)
    p0, p1 = sky_rsi(r0, rd, SKY_RA)
    p0 = np.maximum(p0, F(0))
    pg, _ = sky_rsi(r0, rd, SKY_RP)
    p1 = np.where(pg > 0, np.minimum(p1, pg), p1)
    NI, NJ = int(m3[0] + 0.5), int(m3[1] + 0.5)
    iss = (p1 - p0) / F(NI)
    it = p0.copy()
    tR, tM = np.zeros((n, 3), F), np.zeros((n, 3), F)
    odR, odM = np.zeros(n, F), np.zeros(n, F)
    mu = np.sum(rd * ps, -1)
    mumu, gg = mu * mu, g * g
    pR = F(3.0 / (16.0 * math.pi)) * (F(1) + mumu)
    pM = F(3.0 / (8.0 * math.pi)) * ((F(1) - gg) * (mumu + F(1))) / (np.power(F(1) + gg - F(2) * mu * g, F(1.5)) * (F(2) + gg))
    psn = np.tile(ps, (n, 1))
    for _i in range(min(NI, 32)):
        ip = r0 + rd * (it + iss * F(0.5))[:, None]
        ih = length(ip) - SKY_RP
        sR, sM = np.exp(-ih / shR) * iss, np.exp(-ih / shM) * iss
        odR, odM = odR + sR, odM + sM
        jss = sky_rsi(ip, psn, SKY_RA)[1] / F(NJ)
        jt, jR, jM = np.zeros(n, F), np.zeros(n, F), np.zeros(n, F)
        for _j in range(min(NJ, 16)):
            jp = ip + psn * (jt + jss * F(0.5))[:, None]
            jh = length(jp) - SKY_RP
            jR, jM = jR + np.exp(-jh / shR) * jss, jM + np.exp(-jh / shM) * jss
            jt = jt + jss
        at = np.exp(-(kM * (odM + jM)[:, None] + kR[None, :] * (odR + jR)[:, None]))
        tR, tM = tR + sR[:, None] * at, tM + sM[:, None] * at
        it = it + iss
    c = m1[1] * (pR[:, None] * kR[None, :] * tR + (pM * kM)[:, None] * tM)
    c = np.where((p0 > p1)[:, None], F(0), c).astype(F)
    hitg = (pg > 0) & (pg < F(1e4))
    if m1[2] > 0:
        od = sky_rsi(r0[:1], ps[None, :], SKY_RA)[1][0]
        sun = m1[1] * F(0.25) * np.exp(-(SKY_KR * m2[0] * F(np.exp(-m2[3] / F(8.0))) +
                                         F(21e-3) * m2[1] * F(np.exp(-m2[3] / F(1.2)))) * od * F(0.1))
        disk = (~hitg) & (np.sum(rd * ps, -1) > np.cos(m1[2]))
        c = c + np.where(disk[:, None], sun[None, :], F(0))
    c = np.where(hitg[:, None], c * F(0.35), c).astype(F)
    if int(C['uMat'][1] + 0.5) == 1:
        return np.concatenate([c, np.where(hitg, F(1), F(0))[:, None]], -1)
    col = F(1) - np.exp(-m1[3] * c)
    a = np.where(hitg, clamp(np.max(col, -1), F(0), F(1)), F(1))
    return np.concatenate([col, a[:, None]], -1).astype(F)


# ------------------------------------------------------------------ planet (gen_sdf_planet.py GLSL, line by line)
def _psph(ro, rd, c, r):
    o = ro - c
    b = np.sum(o * rd, -1)
    q = np.sum(o * o, -1) - F(r) * F(r)
    h = b * b - q
    hs = np.sqrt(np.maximum(h, F(0)))
    t = -b - hs
    t = np.where(t < 0, -b + hs, t)
    return np.where(h < 0, F(-1), t).astype(F)


def _smooth(e0, e1, x):
    t = clamp((x - F(e0)) / F(e1 - e0), F(0), F(1))
    return t * t * (F(3) - F(2) * t)


def _pring(U, r):
    m2, m3 = U['uM2'], U['uM3']
    u = (r - m2[3]) / max(m3[0] - m2[3], F(1e-4))
    d = F(0.55) + F(0.25) * np.sin(u * m3[1] * F(3.1)) + F(0.2) * np.sin(u * m3[1] * F(7.7) + F(1.3))
    d = d * _smooth(0.0, 0.04, u) * _smooth(1.0, 0.92, u)
    d = d * (F(1) - F(0.85) * _smooth(0.012, 0.0, np.abs(u - F(0.62))))
    out = clamp(d, F(0), F(1)) * m2[2]
    return np.where((m2[2] <= 0) | (r < m2[3]) | (r > m3[0]), F(0), out).astype(F)


def _ptilt(U, v):
    a = U['uM0'][1]
    c, s = np.cos(a), np.sin(a)
    return np.stack([c * v[..., 0] + s * v[..., 1], -s * v[..., 0] + c * v[..., 1], v[..., 2]], -1).astype(F)


def planet_rm(U, xs, ys, W, H):
    C = Ctx(U, W, H)
    m0, m1, m2, m3, m4, m5, m6, m7 = (C['uM%d' % i] for i in range(8))
    n = len(xs)
    px, py = f(xs) + F(0.5), f(ys) + F(0.5)
    ux, uy = (px - F(0.5) * C.RES[0]) / C.RES[1], (py - F(0.5) * C.RES[1]) / C.RES[1]
    yaw, pitch = F(m6[0] + m6[2] * C.T), m6[1]
    dist = m5[3] * (F(1) - m7[0] * C.ENV)
    ro1 = (dist * f([np.cos(pitch) * np.sin(yaw), np.sin(pitch), np.cos(pitch) * np.cos(yaw)])).astype(F)
    ww = normalize(-ro1[None, :])[0]
    uu = np.cross(ww, f([0.0, 1.0, 0.0]))
    uu = (uu / np.sqrt(np.sum(uu * uu))).astype(F)
    vv = np.cross(uu, ww).astype(F)
    rd = normalize((ux[:, None] * uu + uy[:, None] * vv + (F(0.5) / np.tan(F(0.5) * m6[3])) * ww).astype(F))
    L = f([np.cos(m4[3]) * np.sin(m4[2]), np.sin(m4[3]), np.cos(m4[3]) * np.cos(m4[2])])
    ro = np.tile(ro1, (n, 1))
    pro, prd, pL = _ptilt(C, ro), _ptilt(C, rd), _ptilt(C, L[None, :])[0]
    k = F(1) / (F(1) - m0[0])
    so = pro * f([1.0, k, 1.0])
    sd = prd * f([1.0, k, 1.0])
    sl = length(sd)
    tp = _psph(so, sd / sl[:, None], f([0, 0, 0]), 1.0)
    tp = np.where(tp > 0, tp / sl, F(-1)).astype(F)
    tr = np.where(np.abs(prd[:, 1]) > 1e-6, -pro[:, 1] / np.where(np.abs(prd[:, 1]) > 1e-6, prd[:, 1], F(1)), F(-1)).astype(F)
    rp = pro + prd * tr[:, None]
    dr = np.where(tr > 0, _pring(C, np.sqrt(rp[:, 0] ** 2 + rp[:, 2] ** 2)), F(0)).astype(F)
    col = np.zeros((n, 3), F)
    a = np.zeros(n, F)
    tbest = np.full(n, F(1e9))
    hp = tp > 0
    if hp.any():
        p = pro + prd * tp[:, None]
        nn = normalize(np.stack([p[:, 0], p[:, 1] * k * k, p[:, 2]], -1).astype(F))
        lat = np.arcsin(clamp(p[:, 1] * k, F(-1), F(1)))
        lon = np.arctan2(p[:, 2], p[:, 0]) + m0[2] * C.T + m1[2] * np.sin(lat * m0[3] * F(0.5)) * C.T
        tt = m1[1] * C.T
        b = lat * m0[3] + m1[0] * (F(0.6) * np.sin(F(3) * lon + F(5) * lat + tt) * np.sin(F(7) * lat - F(2) * lon - F(0.7) * tt)
                                   + F(0.4) * np.sin(F(11) * lat + F(4) * lon + F(1.3) * tt))
        base = pal(C, (F(0.5) + F(0.5) * np.sin(b)).astype(F))
        if m1[3] > 0:
            dl = lon - m2[1] - m0[2] * C.T
            dl = np.arctan2(np.sin(dl), np.cos(dl))
            d = np.sqrt((dl * np.cos(lat) * F(0.6)) ** 2 + (lat - m2[0]) ** 2) / m1[3]
            st = _smooth(1.0, 0.5, d)
            storm = pal(C, np.full(n, F(0.95))) * (F(0.85) + F(0.15) * np.sin(d * F(14) - C.T * F(2)))[:, None]
            base = mix(base, storm, (st * F(0.85))[:, None])
        dif = _smooth(-0.08, 0.35, np.sum(nn * pL, -1))
        trs = np.where(abs(pL[1]) > 1e-6, -p[:, 1] / (pL[1] if abs(pL[1]) > 1e-6 else F(1)), F(-1))
        q = p + pL[None, :] * trs[:, None]
        sh = F(1) - F(0.8) * _pring(C, np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2)) / max(m2[2], F(1e-4))
        dif = np.where(trs > 0, dif * sh, dif)
        fre = np.power(clamp(F(1) + np.sum(nn * prd, -1), F(0), F(1)), F(3))
        cp = base * (dif + m5[0])[:, None] + C['uCa'][:3][None, :] * (fre * m5[1] * (F(0.3) + F(0.7) * dif))[:, None]
        col = np.where(hp[:, None], cp, col)
        a = np.where(hp, F(1), a)
        tbest = np.where(hp, tp, tbest)
    rg = (dr > 0) & (tr < tbest)
    if rg.any():
        rs = rp * f([1.0, k, 1.0])
        ldir = normalize((pL * f([1.0, k, 1.0]))[None, :])[0]
        shp = np.where(_psph(rs, np.tile(ldir, (n, 1)), f([0, 0, 0]), 1.0) > 0, F(0.08), F(1))
        rr = np.sqrt(rp[:, 0] ** 2 + rp[:, 2] ** 2)
        rc = pal(C, (F(0.2) + F(0.25) * (rr - m2[3])).astype(F)) * ((F(0.25) + F(0.75) * abs(pL[1])) * shp)[:, None] + m5[0]
        col = np.where(rg[:, None], mix(col, rc, dr[:, None]), col)
        a = np.where(rg, a + dr * (F(1) - a), a)
        tbest = np.where(rg, np.minimum(tbest, tr), tbest)
    nm = int(m3[2] + 0.5)
    for i in range(min(nm, 3)):
        ang = m4[1] * C.T / F(1 + i) + F(i) * F(2.1)
        orb = m4[0] * F(1.0 + 0.45 * i)
        mc = f([orb * np.cos(ang), orb * F(0.06) * np.sin(ang * F(1.7) + F(i)), orb * np.sin(ang)])
        rr_ = m3[3] * F(1.0 - 0.25 * i)
        tm = _psph(pro, prd, mc, rr_)
        hm = (tm > 0) & (tm < tbest)
        nrm = normalize((pro + prd * tm[:, None] - mc).astype(F))
        cm = f([0.75, 0.72, 0.68])[None, :] * (np.maximum(np.sum(nrm * pL, -1), F(0)) + m5[0])[:, None]
        col = np.where(hm[:, None], cm, col)
        a = np.where(hm, F(1), a)
        tbest = np.where(hm, tm, tbest)
    if m5[2] > 0:
        s = rd * F(260)
        c = np.floor(s).astype(np.int64)
        h = h2(c[:, 0], c[:, 1] ^ (c[:, 2] * 7919), C.SEED)
        h1 = h2(c[:, 1], c[:, 2] ^ (c[:, 0] * 7919), (C.SEED + 1) & U32)
        h3 = h2(c[:, 2], c[:, 0] ^ (c[:, 1] * 7919), (C.SEED + 2) & U32)
        sp = c.astype(F) + F(0.5) + (np.stack([h1, h3, h / max(m5[2], F(1e-6))], -1) - F(0.5)) * F(0.5)
        sv = np.maximum(F(0), F(1) - length(s - sp) * F(2.5)) * (F(1) - a)
        ok = (a < 1) & (h < m5[2])
        col = np.where(ok[:, None], col + sv[:, None], col)
        a = np.where(ok, a + sv, a)
    if int(C['uMat'][1] + 0.5) == 1:
        return np.stack([tp, tr, dr, a], -1).astype(F)
    return np.concatenate([col, a[:, None]], -1).astype(F)


# ------------------------------------------------------------------ shared camera of the tail flat modules
def flat_cam(C, xs, ys, yaw, pitch, fov):
    """ww / uu / vv camera (yaw, pitch, vertical fov) like aurora_dir: rd (N, 3) for rm texels (xs, ys)."""
    px, py = f(xs) + F(0.5), f(ys) + F(0.5)
    ux, uy = (px - F(0.5) * C.RES[0]) / C.RES[1], (py - F(0.5) * C.RES[1]) / C.RES[1]
    yaw, pitch = F(yaw), F(pitch)
    ww = f([np.cos(pitch) * np.sin(yaw), np.sin(pitch), np.cos(pitch) * np.cos(yaw)])
    uu = np.cross(ww, f([0.0, 1.0, 0.0]))
    uu = (uu / np.sqrt(np.sum(uu * uu))).astype(F)
    vv = np.cross(uu, ww).astype(F)
    fk = F(0.5) / np.tan(F(0.5) * F(fov))
    return normalize((ux[:, None] * uu[None, :] + uy[:, None] * vv[None, :] + fk * ww[None, :]).astype(F))


def _dir(yaw, pitch):
    return f([np.cos(pitch) * np.sin(yaw), np.sin(pitch), np.cos(pitch) * np.cos(yaw)])


def _reflect(i, n):
    return (i - F(2) * np.sum(n * i, -1)[:, None] * n).astype(F)


# ------------------------------------------------------------------ ocean (gen_sdf_ocean.py GLSL, line by line)
def ocean_h(C, x, z, n, gain):
    m0, m1 = C['uM0'], C['uM1']
    qx, qz = (x * m0[3]).astype(F), (z * m0[3]).astype(F)
    amp, h, ch, tt = m0[2], np.zeros_like(qx), m1[0], F(C.T * m1[1])
    for _i in range(min(int(n), 8)):
        s1 = np.sin(qx + tt + m1[2] * np.sin(F(0.7) * qz + F(1.3)))
        s2 = np.sin(F(0.5) * qx + F(0.866) * qz - F(0.7) * tt + F(0.8))
        h = h + amp * (F(0.6) * np.exp(ch * (s1 - F(1))) + F(0.4) * np.exp(ch * (s2 - F(1))))
        qx, qz = (F(0.8) * qx - F(0.6) * qz) * F(1.9), (F(0.6) * qx + F(0.8) * qz) * F(1.9)
        amp = F(amp * F(0.42))
        ch = F(ch + (F(1) - ch) * F(0.2))
        tt = F(tt * F(1.38))
    return (h * gain).astype(F)


def ocean_sky(C, rd, L):
    m4, m7, m8 = C['uM4'], C['uM7'], C['uM8']
    y = np.maximum(rd[:, 1], F(0))
    c = mix(m8[None, :3], m4[None, :3], (F(1) - np.exp(F(-4) * y))[:, None])
    s = np.maximum(np.sum(rd * L[None, :], -1), F(0))
    return (c + m7[None, :3] * (m4[3] * (F(0.2) * np.power(s, F(32)) + F(3) * np.power(s, F(3000))))[:, None]).astype(F)


def ocean_rm(U, xs, ys, W, H):
    C = Ctx(U, W, H)
    m0, m1, m2, m3, m4, m5, m6, m7, m8 = (C['uM%d' % i] for i in range(9))
    gain = F(F(1) + m6[2] * C.ENV + m6[3] * C.LEVEL)
    rd = flat_cam(C, xs, ys, m2[3] + m3[0] * C.T, m2[2], m3[1])
    n = rd.shape[0]
    ro = (f([np.sin(m2[3]), 0.0, np.cos(m2[3])]) * F(m2[1] * C.T) + f([0.0, m2[0], 0.0])).astype(F)
    L = _dir(m5[0], m5[1])
    ng, nd, N = int(m0[0] + 0.5), int(m0[1] + 0.5), int(m1[3] + 0.5)
    far = m3[2]
    px = ro[None, :] + rd * far
    hx = px[:, 1] - ocean_h(C, px[:, 0], px[:, 2], ng, gain)
    hm0 = F(ro[1] - ocean_h(C, f([ro[0]]), f([ro[2]]), ng, gain)[0])
    hit = hx < 0
    t = np.where(hit, F(0), far).astype(F)
    if hm0 > 0:
        tm, tx = np.zeros(n, F), np.full(n, far, F)
        hm = np.full(n, hm0, F)
        for _i in range(min(N, 64)):
            tc = (tm + (tx - tm) * (hm / (hm - hx))).astype(F)
            p = ro[None, :] + rd * tc[:, None]
            hc = p[:, 1] - ocean_h(C, p[:, 0], p[:, 2], ng, gain)
            below = hc < 0
            tx, hx = np.where(below, tc, tx), np.where(below, hc, hx)
            tm, hm = np.where(below, tm, tc), np.where(below, hm, hc)
            t = np.where(hit, tc, t)
    col = ocean_sky(C, rd, L)
    hh = np.zeros(n, F)
    if hit.any():
        p = ro[None, :] + rd * t[:, None]
        e = np.maximum(F(0.01), F(0.002) * t)
        hh = ocean_h(C, p[:, 0], p[:, 2], nd, gain)
        nn = normalize(np.stack([hh - ocean_h(C, p[:, 0] + e, p[:, 2], nd, gain), e,
                                 hh - ocean_h(C, p[:, 0], p[:, 2] + e, nd, gain)], -1).astype(F))
        fre = np.power(F(1) - clamp(-np.sum(nn * rd, -1), F(0), F(1)), m6[1]) * F(0.85)
        rf = _reflect(rd, nn)
        rf[:, 1] = np.abs(rf[:, 1])
        refl = ocean_sky(C, rf, L)
        dif = clamp(np.sum(nn * L[None, :], -1) * F(0.4) + F(0.6), F(0), F(1))
        hn = hh / max(m0[2] * F(1.72) * gain, F(1e-4))
        refr = C['uCa'][None, :3] + C['uCb'][None, :3] * (dif * dif * F(0.12) + hn * m6[0] * F(0.3))[:, None]
        c = mix(refr, refl, fre[:, None])
        c = c + m7[None, :3] * (m4[3] * np.power(np.maximum(np.sum(rf * L[None, :], -1), F(0)), m5[2]))[:, None]
        fs = clamp((hn - m7[3]) / max(F(1) - m7[3], F(1e-3)), F(0), F(1))
        foam = f([0.9, 0.95, 1.0])[None, :]
        c = mix(c, foam * (F(0.5) + F(0.5) * dif)[:, None], (fs * fs * (F(3) - F(2) * fs) * min(m5[3], F(1)))[:, None])
        c = c + foam * (fs * max(m5[3] - F(1), F(0)))[:, None]
        c = mix(c, m8[None, :3], (F(1) - np.exp(-m3[3] * t))[:, None])
        col = np.where(hit[:, None], c, col)
        hh = np.where(hit, hh, F(0))
    if int(C['uMat'][1] + 0.5) == 1:
        return np.stack([t, np.where(hit, F(1), F(0)), hh, np.ones(n, F)], -1).astype(F)
    return np.concatenate([col, np.ones((n, 1), F)], -1).astype(F)


# ------------------------------------------------------------------ cloud (gen_sdf_cloud.py GLSL, line by line)
def cn_hash(C, ix, iy, iz):
    M = np.uint64(U32)
    a = (np.asarray(ix, np.int64) & U32).astype(np.uint64) * np.uint64(73856093) & M
    b = (np.asarray(iy, np.int64) & U32).astype(np.uint64) * np.uint64(19349663) & M
    c = (np.asarray(iz, np.int64) & U32).astype(np.uint64) * np.uint64(83492791) & M
    s = np.uint64((C.SEED * 2654435761) & U32)
    return (lb32(a ^ b ^ c ^ s).astype(np.float64) / 4294967296.0).astype(F)


def cn_noise(C, p):
    fl = np.floor(p)
    fr = (p - fl).astype(F)
    i = fl.astype(np.int64)
    u = (fr * fr * (F(3) - F(2) * fr)).astype(F)
    h = lambda dx, dy, dz: cn_hash(C, i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz)
    a = mix(h(0, 0, 0), h(1, 0, 0), u[:, 0])
    b = mix(h(0, 1, 0), h(1, 1, 0), u[:, 0])
    c = mix(h(0, 0, 1), h(1, 0, 1), u[:, 0])
    d = mix(h(0, 1, 1), h(1, 1, 1), u[:, 0])
    return mix(mix(a, b, u[:, 1]), mix(c, d, u[:, 1]), u[:, 2]).astype(F)


def cl_dens(C, p, n):
    m0, m1, m3, m4 = C['uM0'], C['uM1'], C['uM3'], C['uM4']
    hf = ((p[:, 1] - m1[0]) / max(m1[1] - m1[0], F(1e-3))).astype(F)
    q = (p * m0[3] + f([m4[0], m3[3], m4[1]]) * C.T).astype(F)
    s, a, w = np.zeros(len(p), F), F(0.5), F(0)
    for _o in range(min(int(n), 6)):
        s = s + a * cn_noise(C, q)
        w = F(w + a)
        q = (q * F(2.03) + f([17.1, 31.7, 7.3])).astype(F)
        a = F(a * F(0.5))
    prof = clamp(hf * F(5), F(0), F(1)) * clamp((F(1) - hf) * F(2), F(0), F(1))
    d = np.maximum(s / w * prof - (F(1) - m1[2]), F(0)) * m1[3]
    return np.where((hf <= 0) | (hf >= 1), F(0), d).astype(F)


def cl_sky(C, rd, L):
    m6, m7, m9 = C['uM6'], C['uM7'], C['uM9']
    y = np.maximum(rd[:, 1], F(0))
    c = mix(m9[None, :3], m6[None, :3], (F(1) - np.exp(F(-3) * y))[:, None])
    s = np.maximum(np.sum(rd * L[None, :], -1), F(0))
    return (c + m7[None, :3] * (m6[3] * (F(0.12) * np.power(s, F(16)) + F(2) * np.power(s, F(3000))))[:, None]).astype(F)


def cloud_rm(U, xs, ys, W, H):
    C = Ctx(U, W, H)
    m0, m1, m2, m3, m4, m5, m6, m7, m8, m9 = (C['uM%d' % i] for i in range(10))
    rd = flat_cam(C, xs, ys, m5[1] + m5[2] * C.T, m5[0], m5[3])
    n = rd.shape[0]
    ro = (f([np.sin(m5[1]), 0.0, np.cos(m5[1])]) * F(m4[3] * C.T) + f([0.0, m4[2], 0.0])).astype(F)
    L = _dir(m8[0], m8[1])
    sky = cl_sky(C, rd, L)
    ry = rd[:, 1]
    big = np.abs(ry) > F(1e-4)
    rys = np.where(big, ry, F(1))
    ta, tb = (m1[0] - ro[1]) / rys, (m1[1] - ro[1]) / rys
    t0 = np.where(big, np.maximum(np.minimum(ta, tb), F(0)), F(0)).astype(F)
    inside = (ro[1] > m1[0]) & (ro[1] < m1[1])
    t1 = np.where(big, np.maximum(ta, tb), m3[0] if inside else F(-1)).astype(F)
    t1 = np.minimum(t1, m3[0])
    tr, dsum = np.ones(n, F), np.zeros(n, F)
    col = np.zeros((n, 3), F)
    act = t1 > t0
    N, no, nl = int(m0[0] + 0.5), int(m0[1] + 0.5), int(m0[2] + 0.5)
    dt = ((t1 - t0) / F(N)).astype(F)
    t = (t0 + dt * m3[2] * h2(np.asarray(xs), np.asarray(ys), C.SEED)).astype(F)
    mu = np.sum(rd * L[None, :], -1)
    g = m2[2]
    hg = (F(1) - g * g) / np.power(np.maximum(F(1) + g * g - F(2) * g * mu, F(1e-4)), F(1.5))
    ph = F(0.4) + F(0.08) * hg
    sun = F(m6[3] * (F(1) + m7[3] * C.ENV + m8[2] * C.LEVEL))
    for _i in range(min(N, 64)):
        if not act.any():
            break
        p = (ro[None, :] + rd * t[:, None]).astype(F)
        d = cl_dens(C, p, no)
        on = act & (d > 0)
        if on.any():
            dl = cl_dens(C, (p + L[None, :] * m2[1]).astype(F), nl)
            lum = np.exp(-dl * m2[0] * m2[1])
            hf = (p[:, 1] - m1[0]) / max(m1[1] - m1[0], F(1e-3))
            S = m7[None, :3] * (lum * ph * sun)[:, None] + m6[None, :3] * (m2[3] * (F(0.4) + F(0.6) * hf))[:, None]
            S = mix(m9[None, :3], S, np.exp(-m3[1] * t)[:, None])
            a = F(1) - np.exp(-d * dt)
            col = np.where(on[:, None], col + (tr * a)[:, None] * S, col).astype(F)
            tr = np.where(on, tr * (F(1) - a), tr).astype(F)
            dsum = np.where(on, dsum + d * dt, dsum).astype(F)
            act = act & ~(on & (tr < F(0.01)))
        t = np.where(act, t + dt, t).astype(F)
    if int(C['uMat'][1] + 0.5) == 1:
        return np.stack([t0, np.where(t1 > t0, F(1), F(0)), tr, dsum], -1).astype(F)
    return np.concatenate([col + tr[:, None] * sky, np.ones((n, 1), F)], -1).astype(F)


# ------------------------------------------------------------------ blackhole (gen_sdf_blackhole.py GLSL, line by line)
def bh_disk(C, q, vdir, gain):
    m0, m1, m2 = C['uM0'], C['uM1'], C['uM2']
    rq = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2).astype(F)
    k = ((rq - m1[0]) / max(m1[1] - m1[0], F(1e-3))).astype(F)
    fin, fout = clamp(k * F(8), F(0), F(1)), clamp((F(1) - k) * F(3), F(0), F(1))
    kk, a0, ph = np.power(m1[0] / rq, F(1.5)), np.arctan2(q[:, 2], q[:, 0]).astype(F), F(m2[0] * C.T * F(0.25))
    w1, w2 = fract(ph), fract(F(ph + F(0.5)))
    x1 = F(1) - abs(F(2) * w1 - F(1))
    bb = lambda aa: F(0.55) + F(0.45) * np.sin(rq * m2[1] + m2[2] * np.sin(F(3) * aa + F(1.7) * rq)) * np.sin(F(5) * aa + F(2) * rq)
    band = (bb((a0 + (w1 - F(0.5)) * F(4) * kk).astype(F)) * x1 + bb((a0 + (w2 - F(0.5)) * F(4) * kk).astype(F)) * (F(1) - x1)).astype(F)
    op = (m1[2] * fin * fout * clamp(band + F(0.2), F(0), F(1))).astype(F)
    vd = normalize(np.stack([-q[:, 2], np.zeros_like(rq), q[:, 0]], -1).astype(F))
    beta = np.sqrt(F(0.5) * m0[3] / rq)
    boost = np.maximum(F(1) + m2[3] * beta * (-np.sum(vd * vdir, -1)), F(0.05))
    e = pal(C, k) * (gain * band * (m1[0] * m1[0]) / (rq * rq) * boost * boost * boost)[:, None]
    return e.astype(F), op


def blackhole_rm(U, xs, ys, W, H):
    C = Ctx(U, W, H)
    m0, m1, m2, m3, m4, m5 = (C['uM%d' % i] for i in range(6))
    yaw, pitch = F(m3[2] + m3[3] * C.T), m3[1]
    ro = (m3[0] * _dir(yaw, pitch)).astype(F)
    ww = normalize(-ro[None, :])[0]
    uu = np.cross(ww, f([0.0, 1.0, 0.0]))
    uu = (uu / np.sqrt(np.sum(uu * uu))).astype(F)
    vv = np.cross(uu, ww).astype(F)
    px, py = f(xs) + F(0.5), f(ys) + F(0.5)
    ux, uy = (px - F(0.5) * C.RES[0]) / C.RES[1], (py - F(0.5) * C.RES[1]) / C.RES[1]
    v = normalize((ux[:, None] * uu + uy[:, None] * vv + (F(0.5) / np.tan(F(0.5) * m4[0])) * ww).astype(F))
    n = v.shape[0]
    p = np.tile(ro, (n, 1)).astype(F)
    hv = np.cross(p, v).astype(F)
    hh = np.sum(hv * hv, -1).astype(F)
    rs, far = m0[3], F(m3[0] * F(1.5) + m1[1])
    gain = F(m1[3] * (F(1) + m5[1] * C.ENV + m5[2] * C.LEVEL))
    col = np.zeros((n, 3), F)
    al, glow, rmin = np.zeros(n, F), np.zeros(n, F), np.full(n, F(1e9))
    cap = np.zeros(n, bool)
    act = np.ones(n, bool)
    N = int(m0[0] + 0.5)
    for _i in range(min(N, 256)):
        if not act.any():
            break
        r2 = np.sum(p * p, -1)
        r = np.sqrt(r2)
        rmin = np.where(act, np.minimum(rmin, r), rmin)
        dt = (m0[1] * np.maximum(r, F(0.2))).astype(F)
        vn = (v + ((F(-1.5) * m0[2] * rs * hh / (r2 * r2 * r)) * dt)[:, None] * p).astype(F)
        pn = (p + vn * dt[:, None]).astype(F)
        cross = act & (p[:, 1] * pn[:, 1] < 0)
        if cross.any():
            fq = np.where(cross, p[:, 1] / np.where(cross, p[:, 1] - pn[:, 1], F(1)), F(0)).astype(F)
            q = (p + (pn - p) * fq[:, None]).astype(F)
            rq = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2)
            ind = cross & (rq > m1[0]) & (rq < m1[1])
            if ind.any():
                e, op = bh_disk(C, q[ind], normalize(vn[ind]), gain)
                ci = np.where(ind)[0]
                col[ci] = col[ci] + ((F(1) - al[ci]) * op)[:, None] * e
                al[ci] = al[ci] + (F(1) - al[ci]) * op
        glow = np.where(act, glow + np.exp(-np.abs(r - F(1.5) * rs) * F(6) / rs) * dt, glow).astype(F)
        v = np.where(act[:, None], vn, v)
        p = np.where(act[:, None], pn, p)
        capn = act & (length(p) < rs)
        cap = cap | capn
        act = act & ~capn & ~(r > far) & ~(al > F(0.99))
    d = normalize(v)
    bg = np.zeros((n, 3), F)
    if m4[2] > 0:
        s_ = (d * m4[3]).astype(F)
        c = np.floor(s_).astype(np.int64)
        h = h2(c[:, 0], c[:, 1] ^ (c[:, 2] * 7919), C.SEED)
        h1 = h2(c[:, 1], c[:, 2] ^ (c[:, 0] * 7919), (C.SEED + 1) & U32)
        h3 = h2(c[:, 2], c[:, 0] ^ (c[:, 1] * 7919), (C.SEED + 2) & U32)
        sp = c.astype(F) + F(0.5) + (np.stack([h1, h3, h / max(m4[2], F(1e-6))], -1) - F(0.5)) * F(0.5)
        sv = np.maximum(F(0), F(1) - length(s_ - sp) * F(2.5)) * (F(0.4) + F(0.6) * h1)
        bg = np.where((h < m4[2])[:, None], sv[:, None] * f([1.0, 1.0, 1.0])[None, :], bg)
    col = np.where(cap[:, None], col, col + (F(1) - al)[:, None] * bg)
    col = col + pal(C, np.full(n, F(0.15))) * (m5[0] * glow * F(0.15) * (F(1) - al))[:, None]
    if int(C['uMat'][1] + 0.5) == 1:
        return np.stack([rmin, np.where(cap, F(1), F(0)), al, glow], -1).astype(F)
    col = F(1) - np.exp(-m4[1] * col)
    return np.concatenate([col, np.ones((n, 1), F)], -1).astype(F)


# ------------------------------------------------------------------ terrain (gen_sdf_terrain.py GLSL, line by line)
def th_hash(C, ix, iy):
    M = np.uint64(U32)
    a = (np.asarray(ix, np.int64) & U32).astype(np.uint64) * np.uint64(73856093) & M
    b = (np.asarray(iy, np.int64) & U32).astype(np.uint64) * np.uint64(19349663) & M
    s = np.uint64((C.SEED * 2654435761) & U32)
    return (lb32(a ^ b ^ s).astype(np.float64) * (2.0 / 4294967296.0) - 1.0).astype(F)


def th_noised(C, x, y):
    flx, fly = np.floor(x), np.floor(y)
    fx, fy = (x - flx).astype(F), (y - fly).astype(F)
    ix, iy = flx.astype(np.int64), fly.astype(np.int64)
    ux, uy = fx * fx * (F(3) - F(2) * fx), fy * fy * (F(3) - F(2) * fy)
    dux, duy = F(6) * fx * (F(1) - fx), F(6) * fy * (F(1) - fy)
    a, b = th_hash(C, ix, iy), th_hash(C, ix + 1, iy)
    c, d = th_hash(C, ix, iy + 1), th_hash(C, ix + 1, iy + 1)
    k1, k2, k4 = b - a, c - a, a - b - c + d
    return (a + k1 * ux + k2 * uy + k4 * ux * uy).astype(F), (dux * (k1 + k4 * uy)).astype(F), (duy * (k2 + k4 * ux)).astype(F)


def terrain_h(C, x, z, n, TH):
    m1 = C['uM1']
    px, pz = (x * m1[1]).astype(F), (z * m1[1]).astype(F)
    dx, dz = np.zeros_like(px), np.zeros_like(px)
    a, b = np.zeros_like(px), F(1)
    for _i in range(min(int(n), 12)):
        v, gx, gz = th_noised(C, px, pz)
        dx, dz = dx + gx, dz + gz
        a = a + b * v / (F(1) + m1[3] * (dx * dx + dz * dz))
        b = F(b * F(0.5))
        px, pz = (F(0.8) * px - F(0.6) * pz) * F(2), (F(0.6) * px + F(0.8) * pz) * F(2)
    return (a * TH).astype(F)


def terrain_sky(C, rd, L):
    m4, m5, m7 = C['uM4'], C['uM5'], C['uM7']
    y = np.maximum(rd[:, 1], F(0))
    c = mix(m7[None, :3], m4[None, :3], (F(1) - np.exp(F(-3) * y))[:, None])
    s = np.maximum(np.sum(rd * L[None, :], -1), F(0))
    return (c + m5[None, :3] * (m4[3] * (F(0.15) * np.power(s, F(12)) + F(2) * np.power(s, F(3000))))[:, None]).astype(F)


def terrain_rm(U, xs, ys, W, H):
    C = Ctx(U, W, H)
    m0, m1, m2, m3, m4, m5, m6, m7 = (C['uM%d' % i] for i in range(8))
    TH = F(m1[2] * (F(1) + m7[3] * C.LEVEL))
    rd = flat_cam(C, xs, ys, m3[1] + m3[2] * C.T, m3[0], m3[3])
    n = rd.shape[0]
    ro = (f([np.sin(m3[1]), 0.0, np.cos(m3[1])]) * F(m2[2] * C.T)).astype(F)
    ro[1] = terrain_h(C, f([ro[0]]), f([ro[2]]), 3, TH)[0] + m2[1]
    L = _dir(m6[0], m6[1])
    ng, nd, N = int(m0[0] + 0.5), int(m0[1] + 0.5), int(m0[2] + 0.5)
    far = m1[0]
    t = np.full(n, F(0.5))
    hit = np.zeros(n, bool)
    act = np.ones(n, bool)
    for _i in range(min(N, 256)):
        if not act.any():
            break
        p = (ro[None, :] + rd * t[:, None]).astype(F)
        d = p[:, 1] - terrain_h(C, p[:, 0], p[:, 2], ng, TH)
        h_ = act & (d < F(0.002) * t)
        hit = hit | h_
        act = act & ~h_
        t = np.where(act, t + m0[3] * d, t).astype(F)
        act = act & ~(t > far)
    col = terrain_sky(C, rd, L)
    hh = np.zeros(n, F)
    if hit.any():
        hi = np.where(hit)[0]
        rh, th_ = rd[hi], t[hi]
        p = (ro[None, :] + rh * th_[:, None]).astype(F)
        e = np.maximum(F(0.005), F(0.002) * th_)
        hv = terrain_h(C, p[:, 0], p[:, 2], nd, TH)
        nn = normalize(np.stack([hv - terrain_h(C, p[:, 0] + e, p[:, 2], nd, TH), e,
                                 hv - terrain_h(C, p[:, 0], p[:, 2] + e, nd, TH)], -1).astype(F))
        rock = clamp((F(0.85) - nn[:, 1]) * F(5), F(0), F(1))
        base = mix(C['uCb'][None, :3], C['uCa'][None, :3], rock[:, None])
        sn = clamp((hv / max(TH, F(1e-3)) - m2[0]) * F(6), F(0), F(1)) * clamp((nn[:, 1] - F(0.6)) * F(5), F(0), F(1))
        base = mix(base, f([0.92, 0.94, 0.98])[None, :], sn[:, None])
        sh = np.ones(len(hi), F)
        ns = int(m6[2] + 0.5)
        if ns > 0:
            st = np.full(len(hi), F(0.3))
            on = np.ones(len(hi), bool)
            for _j in range(min(ns, 32)):
                if not on.any():
                    break
                sp = (p + L[None, :] * st[:, None]).astype(F)
                dh = sp[:, 1] - terrain_h(C, sp[:, 0], sp[:, 2], ng, TH)
                sh = np.where(on, np.minimum(sh, F(8) * dh / st), sh).astype(F)
                st = np.where(on, st + clamp(dh, F(0.1), F(2)), st).astype(F)
                on = on & ~(sh < F(0.001))
            sh = clamp(sh, F(0), F(1))
        dif = np.maximum(np.sum(nn * L[None, :], -1), F(0)) * sh
        sun = F(m4[3] * (F(1) + m6[3] * C.ENV))
        c = base * (m5[None, :3] * (dif * sun)[:, None] + m4[None, :3] * (m5[3] * (F(0.5) + F(0.5) * nn[:, 1]))[:, None])
        fd = normalize(np.stack([rh[:, 0], np.full(len(hi), F(0.02)), rh[:, 2]], -1).astype(F))
        fc = terrain_sky(C, fd, L)
        col[hi] = mix(c, fc, (F(1) - np.exp(-m2[3] * th_))[:, None])
        hh[hi] = hv
    if int(C['uMat'][1] + 0.5) == 1:
        return np.stack([t, np.where(hit, F(1), F(0)), hh, np.ones(n, F)], -1).astype(F)
    return np.concatenate([col, np.ones((n, 1), F)], -1).astype(F)


# ------------------------------------------------------------------ entry points
FLAT_TAIL = {}            # module -> mirror function (filled below the tail modules)


def expect_rm(module, U, xs, ys, W, H, ref=None):
    """rm rgba at rm texels (xs, ys) (lists of ints, TD y up) for an rm of W x H. Returns a list of [r, g, b, a]."""
    if module in FLAT_TAIL:
        with np.errstate(all='ignore'):
            out = FLAT_TAIL[module](U, xs, ys, W, H)
    elif module == 'aurora':
        with np.errstate(all='ignore'):
            out = aurora_rm(U, xs, ys, W, H)
    elif module == 'sky':
        with np.errstate(all='ignore'):
            out = sky_rm(U, xs, ys, W, H)
    elif module == 'planet':
        with np.errstate(all='ignore'):
            out = planet_rm(U, xs, ys, W, H)
    elif module == 'fractal2d':
        out = flat2d(U, xs, ys, W, H, ref)
    else:
        out = Ray(module, U, W, H).render(xs, ys)
    return out.astype(np.float64).tolist()


def ref_orbit_ns():
    ns = {}
    exec(open(os.path.join(HERE, 'gen_sdf_fractal2d.py')).read(), ns)
    rns = {}
    exec(ns['REF_PY'], rns)
    return rns


def compare(module, U, got, exp_, tol_t=0.02, tol_c=4.0 / 255.0):
    """Live rm values vs mirror. Data view: ray = relative t error on pixels both call hits + hit agreement;
    flat = escape agreement + |mu| diff. Else colour: max channel diff (clamped 0..1)."""
    g, e = np.asarray(got, dtype=np.float64), np.asarray(exp_, dtype=np.float64)
    view = int(U['uMat'][1] + 0.5)
    n = len(g)
    if module in FLAT_TAIL and view == 1:                  # tail flat modules: data = (t, hit, x, y) like a ray
        agree = g[:, 1] == e[:, 1]
        both = agree & (e[:, 1] > 0.5)
        rel = np.abs(g[both, 0] - e[both, 0]) / np.maximum(np.abs(e[both, 0]), 1e-3)
        d23 = np.max(np.abs(g[both][:, 2:] - e[both][:, 2:]), axis=1) if both.any() else np.zeros(1)
        return {'view': 'data', 'hit_agree': round(float(agree.mean()), 4), 'hits': int(both.sum()),
                't_within': round(float((rel <= tol_t).mean()) if both.any() else 1.0, 4),
                't_rel_median': round(float(np.median(rel)) if both.any() else 0.0, 6),
                'zw_within': round(float((d23 <= 0.02).mean()), 4)}
    if module in ('aurora', 'sky', 'planet'):             # every view compared as values (aurora data = nsum, rd.y, g, 1)
        d = np.max(np.abs(g - e), axis=1)
        return {'view': 'data' if view == 1 else 'colour', 'within_tol': round(float((d <= tol_c).mean()), 4),
                'median': round(float(np.median(d)), 5), 'p90': round(float(np.sort(d)[int(0.9 * (n - 1))]), 4),
                'max': round(float(d.max()), 4)}
    if view == 1 and module != 'fractal2d':
        agree = g[:, 1] == e[:, 1]
        both = agree & (e[:, 1] > 0.5)
        rel = np.abs(g[both, 0] - e[both, 0]) / np.maximum(e[both, 0], 1e-3)
        return {'view': 'data', 'hit_agree': round(float(agree.mean()), 4), 'hits': int(both.sum()),
                't_within': round(float((rel <= tol_t).mean()) if both.any() else 1.0, 4),
                't_rel_median': round(float(np.median(rel)) if both.any() else 0.0, 6)}
    if view == 1:
        agree = g[:, 1] == e[:, 1]
        both = agree & (e[:, 1] > 0.5)
        dmu = np.abs(g[both, 0] - e[both, 0])
        return {'view': 'data', 'esc_agree': round(float(agree.mean()), 4), 'escaped': int(both.sum()),
                'mu_within_0.5': round(float((dmu <= 0.5).mean()) if both.any() else 1.0, 4),
                'mu_median': round(float(np.median(dmu)) if both.any() else 0.0, 5)}
    d = np.max(np.abs(np.clip(g, 0, 1) - np.clip(e, 0, 1)), axis=1)
    return {'view': 'colour', 'within_tol': round(float((d <= tol_c).mean()), 4), 'median': round(float(np.median(d)), 5),
            'p90': round(float(np.sort(d)[int(0.9 * (n - 1))]), 4), 'max': round(float(d.max()), 4)}


def compose(U, s, c):
    """fx composite for one pixel: s = bilinear rm sample (premultiplied rgba), c = input rgba."""
    am, bg = U['uAmt'], U['uBg']
    if am[0] <= 0.0:
        return list(c)
    mode = int(am[1] + 0.5)
    if mode == 0:
        o = [s[j] + bg[j] * (1.0 - s[3]) for j in range(3)] + [1.0]
    elif mode == 1:
        o = [s[j] + c[j] * (1.0 - s[3]) for j in range(3)] + [s[3] + c[3] * (1.0 - s[3])]
    elif mode == 2:
        o = [c[j] + s[j] for j in range(3)] + [c[3]]
    elif mode == 3:
        o = [1.0 - (1.0 - c[j]) * (1.0 - s[j]) for j in range(3)] + [c[3]]
    elif mode == 4:
        o = [c[j] * (s[j] + (1.0 - s[3])) for j in range(3)] + [c[3]]
    elif mode == 5:
        o = [abs(c[j] - s[j]) for j in range(3)] + [c[3]]
    else:
        o = list(s)
    return [min(max(c[j] + (o[j] - c[j]) * am[0], 0.0), 1.0) for j in range(4)]


def bilinear(img, u, v):
    """GL texture() with clamp-to-edge on img (numpy H x W x 4, row 0 = TD y 0)."""
    H, W = img.shape[0], img.shape[1]
    x, y = u * W - 0.5, v * H - 0.5
    x0, y0 = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - x0, y - y0
    px = lambda i, j: img[min(max(j, 0), H - 1)][min(max(i, 0), W - 1)]
    a, b, c, d = px(x0, y0), px(x0 + 1, y0), px(x0, y0 + 1), px(x0 + 1, y0 + 1)
    return [(float(a[k]) * (1 - fx) + float(b[k]) * fx) * (1 - fy) + (float(c[k]) * (1 - fx) + float(d[k]) * fx) * fy
            for k in range(4)]


def compose_px(U, rm, src, x, y, W, H):
    s = bilinear(rm, (x + 0.5) / W, (y + 0.5) / H)
    return compose(U, s, [float(v) for v in src[y][x]])


def render_img(module, U, W, H, ref=None):
    """Offline picture (H x W x 4 rgba, row 0 = bottom) of the rm pass composited 'replace' over its bg (tests,
    preview PNGs)."""
    ys, xs = np.mgrid[0:H, 0:W]
    o = np.asarray(expect_rm(module, U, xs.ravel().tolist(), ys.ravel().tolist(), W, H, ref), dtype=np.float64)
    o = o.reshape(H, W, 4)
    bg = np.asarray(U.get('uFog', U.get('uBg', (0, 0, 0, 0)))[:3]) if module != 'fractal2d' else np.zeros(3)
    rgb = o[:, :, :3] + bg[None, None, :] * (1.0 - o[:, :, 3:4])
    return np.clip(np.concatenate([rgb, np.ones((H, W, 1))], axis=-1), 0, 1)


def out_stats(module, U, Uf, Wo, Ho, Wr, Hr, ref=None, n=1000, seed=7, src=(0.0, 0.0, 0.0, 1.0)):
    """Expected gen_sdf.stats() of out1 (Wo x Ho) when rm is Wr x Hr: mirror rm at the texels the 1000 sample points
    bilinear-read, composite over a constant input `src` (rack Input black = (0, 0, 0, 1)). U = rm uniforms, Uf = fx
    uniforms. Returns {mean_rgb, lit} like gen_pattern_logic.stats."""
    pts = sample_points(Wo, Ho, n, seed)
    need = {}
    taps = []
    for x, y in pts:
        fx_, fy_ = (x + 0.5) / Wo * Wr - 0.5, (y + 0.5) / Ho * Hr - 0.5
        x0, y0 = int(math.floor(fx_)), int(math.floor(fy_))
        tx, ty = fx_ - x0, fy_ - y0
        cs = []
        for i, j, w in ((x0, y0, (1 - tx) * (1 - ty)), (x0 + 1, y0, tx * (1 - ty)), (x0, y0 + 1, (1 - tx) * ty),
                        (x0 + 1, y0 + 1, tx * ty)):
            k = (min(max(i, 0), Wr - 1), min(max(j, 0), Hr - 1))
            need[k] = None
            cs.append((k, w))
        taps.append(cs)
    keys = list(need)
    vals = expect_rm(module, U, [k[0] for k in keys], [k[1] for k in keys], Wr, Hr, ref)
    for k, v in zip(keys, vals):
        need[k] = v
    px = []
    for cs in taps:
        s = [sum(need[k][c] * w for k, w in cs) for c in range(4)]
        px.append(compose(Uf, s, list(src)))
    return _GPL['stats'](px)


FLAT_TAIL.update({'ocean': ocean_rm, 'cloud': cloud_rm, 'blackhole': blackhole_rm, 'terrain': terrain_rm})
