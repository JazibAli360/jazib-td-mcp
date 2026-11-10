"""gen_interactive_flowers_logic - float64 numpy twin of GEN_interactive 'flowers' (builders/glsl/
gen_interactive_flowers_{state,water,draw}.glsl): flower slots, waterfall drops and the per-pixel draw. Arrays are
[y, x, 4] with y = 0 the bottom row (TD texel space, T-58). Hashes are GEN_sim's hash3 (exact in float32 on the GPU).
Live parity: freeze (Speed 0), read state / water / mask / pts with numpyArray, step them here with the same uniforms,
compare (docs/builds/gen_interactive.md LIVE CHECKS F*). numpy imported inside functions. ASCII only."""
import math
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SPN = (9, 5, 6, 8, 5, 6)
SPA = (1.0, 0.7, 1.4, 1.2, 0.5, 0.8)
SPB = (0.5, 0.6, 0.8, 1.2, 1.5, 0.3)
SPW = (0.18, 0.45, 0.40, 0.35, 0.30, 0.55)
_GI = {}


def gi():
    if not _GI:
        with open(os.path.join(HERE, 'gen_interactive_logic.py')) as fh:
            exec(fh.read(), _GI)
    return _GI


def _np():
    import numpy
    return numpy


def h3(i, j, s):
    return float(gi()['gs']()['hash3'](i, j, s))


def defaults():
    """Par defaults of the flowers pages (menus as index, RGB as tuples) == gen_interactive_flowers.py."""
    return dict(Amount=1.0, Mode=0, Count=400, Spawnrate=0.5, Stillness=1.0, Scatterthresh=0.15, Nearshare=0.0,
                Spawnnear=120.0, Species=0, Seed=1, Bloomtime=4.0, Life=20.0, Lifevar=0.4, Wilttime=4.0,
                Falltime=3.0, Size=70.0, Sizevar=0.4, Petalwidth=1.0, Scatterspeed=220.0, Petalgravity=260.0,
                Spin=3.0, Wind=0.0, Wilt=0.8, Colorvar=0.3, Centrecolor=(1.0, 0.85, 0.3), Centresize=0.18,
                Drops=1200, Fallspeed=700.0, Gravity=900.0, Part=3000.0, Topspread=1.0, Dropvar=0.3, Streak=0.025,
                Dropwidth=2.5, Watercolor=(0.7, 0.85, 1.0), Wateralpha=0.6, Splash=0.6, Speed=1.0, Beatgain=0.0,
                Beatdecay=0.25, Audiogain=0.0, Manual=0.0, Palette=4, Palshift=0.0, Blend=1,
                Colora=(1.0, 0.45, 0.6), Colorb=(1.0, 0.95, 0.8))


def _drive(P, drive):
    G = gi()
    return (G['env'](drive[0], drive[1], P['Beatgain'], P['Beatdecay']),
            G['level'](drive[2], P['Audiogain'], P['Manual']))


def _mask_at(mask, x, y, W, H):
    mh, mw = mask.shape[0], mask.shape[1]
    qx = min(max(int(x / W * mw), 0), mw - 1)         # GLSL int() truncates toward 0
    qy = min(max(int(y / H * mh), 0), mh - 1)
    return mask[qy, qx, 0], mask[qy, qx, 1]


def _meta(state, rows, epoch, now):
    np = _np()
    fresh = state is None or state.shape[0] != rows + 1 or state.shape[1] != 128
    m0 = None if fresh else state[rows, 0].copy()
    fresh = fresh or m0[3] != epoch
    if fresh:
        m0 = np.array([0.0, 0.0, now, epoch])
    return fresh, m0


# ------------------------------------------------------------------ state (== flowers_state.glsl)
def state_step(state, mask, pts, now, P, epoch=1.0, W=1080, H=1920, drive=(0.0, 120.0, 0.0, 0.0)):
    """One cook. state [rows + 1, 128, 4] or None, mask [mh, mw, 4] (r presence, g motion), pts [(x, y, vx, vy)]."""
    np = _np()
    N = max(int(P['Count']), 1)
    rows = (N + 63) // 64
    fresh, m0 = _meta(state, rows, epoch, now)
    if not fresh and m0[2] == now:
        return state.copy()
    dt = (0.0 if fresh else min(max(now - m0[2], 0.0), 0.1)) * P['Speed']
    T = m0[1] + dt
    cook = int(round(m0[0]))
    out = np.zeros((rows + 1, 128, 4))
    out[rows, 0] = [cook + 1, T, now, epoch]
    env, level = _drive(P, drive)
    sd = int(P['Seed'])
    for f in range(rows * 64):
        y, x = f // 64, 2 * (f % 64)
        A = np.zeros(4) if fresh else state[y, x].copy()
        B = np.array([0.0, 0.0, -1.0, 0.0]) if fresh else state[y, x + 1].copy()
        if f >= N or P['Mode'] == 1:
            A, B = np.zeros(4), np.array([0.0, 0.0, -1.0, 0.0])
        elif A[3] > 0.0:
            age = T - A[2]
            if B[2] < 0.0 and 0.0 <= age < A[3]:
                thr = P['Scatterthresh'] / (1.0 + max(level, 0.0))
                if _mask_at(mask, A[0], A[1], W, H)[1] > thr:
                    B[2] = T
            dead = (T - B[2] >= P['Falltime']) if B[2] >= 0.0 else (age >= A[3] + P['Falltime'])
            if dead:
                A, B = np.zeros(4), np.array([0.0, 0.0, -1.0, 0.0])
        elif dt > 0.0:
            hh = [h3(f, cook * 8 + k, sd) for k in range(8)]
            h7, h0, h1, h2, h3_, h4, h5, h6 = hh
            pos = (h1 * W, h2 * H)
            ok = False
            rate = P['Spawnrate'] * dt * (1.0 + env + max(level, 0.0))
            if h3_ < P['Nearshare']:
                n = max(len(pts), 1)
                k = min(int(h4 * n), n - 1)
                q = pts[k] if k < len(pts) else (-10.0, -10.0, 0.0, 0.0)
                if q[0] > -1.0:
                    pos = (q[0] * W + (h1 * 2 - 1) * P['Spawnnear'], q[1] * H + (h2 * 2 - 1) * P['Spawnnear'])
                    ok = h0 < rate
            else:
                pr, mo = _mask_at(mask, pos[0], pos[1], W, H)
                still = min(max(1.0 - mo / max(P['Scatterthresh'], 1e-6), 0.0), 1.0)
                ok = h0 < rate * min(max(pr, 0.0), 1.0) * still ** max(P['Stillness'], 0.0)
            if ok:
                life = max(P['Life'] * (1.0 + P['Lifevar'] * (2 * h5 - 1)), 1e-3)
                size = P['Size'] * (1.0 + P['Sizevar'] * (2 * h4 - 1))
                sp = int(P['Species'])
                species = float(sp - 1) if sp > 0 else min(math.floor(h7 * 6.0), 5.0)
                A = np.array([pos[0], pos[1], T, life])
                B = np.array([h6, size, -1.0, species])
        out[y, x], out[y, x + 1] = A, B
    return out


def alive(state):
    rows = state.shape[0] - 1
    return state[:rows, 0::2, 3] > 0.0


# ------------------------------------------------------------------ water (== flowers_water.glsl)
def water_step(water, mask, now, P, epoch=1.0, W=1080, H=1920):
    np = _np()
    N = max(int(P['Drops']), 1)
    rows = (N + 63) // 64
    fresh, m0 = _meta(water, rows, epoch, now)
    if not fresh and m0[2] == now:
        return water.copy()
    dt = (0.0 if fresh else min(max(now - m0[2], 0.0), 0.1)) * P['Speed']
    T = m0[1] + dt
    cook = int(round(m0[0]))
    out = np.zeros((rows + 1, 128, 4))
    out[rows, 0] = [cook + 1, T, now, epoch]
    mh, mw = mask.shape[0], mask.shape[1]
    sd = int(P['Seed']) + 101

    def pres(qx, qy):
        return mask[min(max(qy, 0), mh - 1), min(max(qx, 0), mw - 1), 0]

    for d in range(rows * 64):
        y, x = d // 64, 2 * (d % 64)
        A = np.zeros(4) if fresh else water[y, x].copy()
        B = np.zeros(4) if fresh else water[y, x + 1].copy()
        if d >= N or P['Mode'] == 0:
            A, B = np.zeros(4), np.zeros(4)
        else:
            if B[2] > 0.5 and dt > 0.0:
                v = A[2:4] + np.array([P['Wind'], -P['Gravity']]) * dt
                qx, qy = int(A[0] / W * mw), int(A[1] / H * mh)
                if 0 <= qx < mw and 0 <= qy < mh and pres(qx, qy) > 0.5:
                    g = np.array([pres(qx + 1, qy) - pres(qx - 1, qy), pres(qx, qy + 1) - pres(qx, qy - 1)])
                    n = -g / np.linalg.norm(g) if g.dot(g) > 1e-8 else np.array([-1.0 if B[1] < 0.5 else 1.0, 0.0])
                    v = v - n * min(v.dot(n), 0.0)
                    v = v + n * P['Part'] * dt
                    B[0] = 1.0
                else:
                    B[0] *= math.exp(-dt / 0.3)
                A = np.array([A[0] + v[0] * dt, A[1] + v[1] * dt, v[0], v[1]])
                if A[1] < -(64.0 + abs(A[3]) * max(P['Streak'], 0.0)) or A[0] < -64.0 or A[0] > W + 64.0:
                    B[2] = 0.0
            if B[2] < 0.5 and (dt > 0.0 or fresh):
                q1, q2, q3 = (h3(d, cook * 4 + k, sd) for k in (1, 2, 3))
                A = np.array([q1 * W, H * (1.0 + max(P['Topspread'], 0.0) * q2), 0.0,
                              -P['Fallspeed'] * (1.0 + P['Dropvar'] * (2 * q3 - 1))])
                B = np.array([0.0, q3, 1.0, 0.0])
        out[y, x], out[y, x + 1] = A, B
    return out


# ------------------------------------------------------------------ draw (== flowers_draw.glsl)
def flower_geom(A, B, T, P, boost):
    """(centre, Lp, Wp, rot, ts, spd, alpha, wilt, n, species, open) of one flower slot."""
    age = T - A[2]
    t = min(max(age / max(P['Bloomtime'], 1e-3), 0.0), 1.0)
    open_ = t * t * (3 - 2 * t)
    sp = min(max(int(round(B[3])), 0), 5)
    n = SPN[sp]
    Lp = B[1] * (0.15 + 0.85 * open_) * boost
    Wp = Lp * P['Petalwidth'] * SPW[sp] * (0.4 + 0.6 * open_)
    ts, spd = -1.0, 0.0
    if B[2] >= 0.0:
        ts, spd = T - B[2], P['Scatterspeed']
    elif age >= A[3]:
        ts, spd = age - A[3], P['Scatterspeed'] * 0.15
    alpha = min(max(1.0 - ts / max(P['Falltime'], 1e-3), 0.0), 1.0) if ts >= 0.0 else 1.0
    wilt = min(max((min(age, A[3]) - (A[3] - P['Wilttime'])) / max(P['Wilttime'], 1e-3), 0.0), 1.0)
    return {'c': (A[0], A[1]), 'Lp': Lp, 'Wp': Wp, 'rot': B[0] * 2 * math.pi, 'ts': ts, 'spd': spd, 'alpha': alpha,
            'wilt': wilt, 'n': n, 'sp': sp, 'open': open_, 'seed': B[0]}


def petal_pose(g, j, P):
    """Base point (relative to the centre) and angle of petal j."""
    th = g['rot'] + j * 2 * math.pi / g['n']
    if g['ts'] < 0.0:
        return (0.0, 0.0), th
    hj = h3(int(g['seed'] * 65536.0), j, 7)
    dv = th + (hj - 0.5) * 1.2
    vx = math.cos(dv) * g['spd'] * (0.5 + hj)
    vy = math.sin(dv) * g['spd'] * (0.5 + hj) + g['spd'] * 0.3
    ts = g['ts']
    px = 0.5 * g['Lp'] * math.cos(th) + vx * ts + P['Wind'] * ts
    py = 0.5 * g['Lp'] * math.sin(th) + vy * ts - 0.5 * P['Petalgravity'] * ts * ts
    phi = th + P['Spin'] * (2 * hj - 1) * ts
    return (px - math.cos(phi) * g['Lp'] * 0.5, py - math.sin(phi) * g['Lp'] * 0.5), phi


def items(state, water, P, drive=(0.0, 120.0, 0.0, 0.0)):
    """Drawable items in the shader's order: ('f', geom) for living flowers, ('d', A, B) for live drops."""
    env, level = _drive(P, drive)
    boost = 1.0 + 0.5 * (env + level)
    out = []
    mode = int(P['Mode'])
    if mode != 1:
        rows = state.shape[0] - 1
        T = state[rows, 0, 1]
        NF = min(max(int(P['Count']), 0), rows * 64)
        for f in range(NF):
            A, B = state[f // 64, 2 * (f % 64)], state[f // 64, 2 * (f % 64) + 1]
            if A[3] > 0.0:
                g = flower_geom(A, B, T, P, boost)
                if g['alpha'] > 0.0:
                    out.append(('f', g))
    if mode != 0:
        rows = water.shape[0] - 1
        ND = min(max(int(P['Drops']), 0), rows * 64)
        for d in range(ND):
            A, B = water[d // 64, 2 * (d % 64)], water[d // 64, 2 * (d % 64) + 1]
            if B[2] > 0.5:
                out.append(('d', A.copy(), B.copy()))
    return out


def shade_grid(xs, ys, its, P):
    """(premultiplied rgb [..., 3], coverage [...]) at pixel centres, painter's order (== the draw pass)."""
    np = _np()
    gs = gi()['gs']()
    x, y = np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)
    acc = np.zeros(x.shape + (3,))
    aa = np.zeros(x.shape)
    cc = np.array(P['Centrecolor'])
    for it in its:
        if it[0] == 'f':
            g = it[1]
            key = g['sp'] / 6.0 + (g['seed'] - 0.5) * P['Colorvar']
            pc = gs['palette'](np.array([key]), int(P['Palette']), P['Colora'], P['Colorb'], P['Palshift'])[0]
            lum = pc[0] * 0.2126 + pc[1] * 0.7152 + pc[2] * 0.0722
            pc = pc + (lum * 0.55 + np.array([0.08, 0.05, 0.0]) - pc) * (g['wilt'] * P['Wilt'])
            fv = np.zeros(x.shape)
            col = np.broadcast_to(pc, x.shape + (3,)).copy()
            for j in range(g['n']):
                (bx, by), phi = petal_pose(g, j, P)
                qx, qy = x - g['c'][0] - bx, y - g['c'][1] - by
                cs, sn = math.cos(phi), math.sin(phi)
                lx, ly = cs * qx + sn * qy, -sn * qx + cs * qy
                t = np.clip(lx / max(g['Lp'], 1e-3), 0.0, 1.0)
                hw = g['Wp'] * np.maximum(np.sin(math.pi * t ** SPA[g['sp']]), 0.0) ** SPB[g['sp']]
                dd = np.maximum(np.abs(ly) - hw, np.maximum(-lx, lx - g['Lp']))
                cv = np.clip(0.5 - dd, 0.0, 1.0)
                w = cv > fv
                fv = np.where(w, cv, fv)
                col = np.where(w[..., None], pc * (0.65 + 0.35 * t)[..., None], col)
            if g['ts'] < 0.0:
                cv = np.clip(0.5 - (np.hypot(x - g['c'][0], y - g['c'][1]) - g['Lp'] * P['Centresize']), 0.0, 1.0)
                col = col + (cc - col) * cv[..., None]
                fv = np.maximum(fv, cv)
            v = fv * g['alpha']
        else:
            A, B = it[1], it[2]
            ax, ay = A[0], A[1]
            bx, by = A[0] - A[2] * P['Streak'], A[1] - A[3] * P['Streak']
            bax, bay = bx - ax, by - ay
            bb = bax * bax + bay * bay
            pax, pay = x - ax, y - ay
            h = np.clip((pax * bax + pay * bay) / bb, 0.0, 1.0) if bb > 1e-12 else np.zeros(x.shape)
            dd = np.hypot(pax - bax * h, pay - bay * h) - 0.5 * P['Dropwidth'] * (1.0 + B[0])
            v = np.clip(np.clip(0.5 - dd, 0.0, 1.0) * P['Wateralpha'] * (1.0 + B[0]), 0.0, 1.0)
            col = np.broadcast_to(np.array(P['Watercolor']) + B[0] * P['Splash'], x.shape + (3,))
        acc = acc * (1.0 - v)[..., None] + col * v[..., None]
        aa = aa * (1.0 - v) + v
    return acc, aa


def run(P, frames, mask_fn, pts_fn=lambda k: [], fps=60.0, W=1080, H=1920, epoch=1.0, water=False):
    """Step the state (and the drops when water) `frames` cooks; mask_fn(k) -> mask array. Returns (state, water)."""
    st = wa = None
    for k in range(frames):
        now = 100.0 + k / fps
        m = mask_fn(k)
        st = state_step(st, m, pts_fn(k), now, P, epoch, W, H)
        if water:
            wa = water_step(wa, m, now, P, epoch, W, H)
    return st, wa


def synthetic_mask(mw=27, mh=48, box=(0.3, 0.7, 0.0, 0.6), motion=0.0):
    """A 'person' box (x0, x1, y0, y1 in 0..1) of presence 1 with uniform motion inside, 0 elsewhere."""
    np = _np()
    m = np.zeros((mh, mw, 4))
    x0, x1, y0, y1 = box
    m[int(y0 * mh):int(y1 * mh), int(x0 * mw):int(x1 * mw), 0] = 1.0
    m[int(y0 * mh):int(y1 * mh), int(x0 * mw):int(x1 * mw), 1] = motion
    m[..., 3] = 1.0
    return m
