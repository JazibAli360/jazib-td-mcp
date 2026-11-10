"""gen_interactive_pigment_logic - float64 numpy twin of GEN_interactive 'pigment' (builders/glsl/
gen_interactive_pigment_{state,splat,trail,look}.glsl): curl field, particle step + respawn, scatter dots, trail and
look. Arrays [y, x, 4], y = 0 the bottom row (TD texel space, T-58). The state texture is [Side + 1, 2 Side, 4]:
texel (2i, j) = x y age life, (2i + 1, j) = anchor x y, seed, speed; row Side = meta. Live parity: freeze (Speed 0),
read state / splat / trail with numpyArray, compare one step from a read state (docs/builds/gen_interactive.md
LIVE CHECKS P*). numpy imported inside functions. ASCII only."""
import math
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SB = 16777216.0
MAXPTS = 256
_GI = {}


def gi():
    if not _GI:
        with open(os.path.join(HERE, 'gen_interactive_logic.py')) as fh:
            exec(fh.read(), _GI)
    return _GI


def _np():
    import numpy
    return numpy


def gs():
    return gi()['gs']()


def defaults():
    return dict(Amount=1.0, Side=256, Life=4.0, Lifevar=0.5, Spawnmode=0, Edge=0, Seed=1, Flowscale=300.0,
                Flowstrength=120.0, Evolve=0.15, Octaves=3, Fieldsource=2, Maskforce=0.0, Flowgain=1.0,
                Radius=220.0, Pointforce=250.0, Pointmode=0, Pointvel=0.5, Colormode=0, Atlascells=4,
                Atlasrate=0.1, Morph=0.0, Speedref=300.0, Size=2.0, Opacity=1.0, Agefade=0.2, Quality=0.5,
                Trail=1.5, Trailmode=0, Exposure=1.0, Glow=0.3, Glowwidth=6.0, Speed=1.0, Beatgain=0.0,
                Beatdecay=0.25, Audiogain=0.0, Manual=0.0, Palette=3, Palshift=0.0, Blend=0,
                Colora=(0.1, 0.3, 1.0), Colorb=(1.0, 0.4, 0.8))


# ------------------------------------------------------------------ sampling (== texture() with hold, linear)
def bilinear(img, u, v):
    """texture(sampler, (u, v)) of img [h, w, 4] with inputextenduv hold + linear filter; u, v arrays -> [..., 4]."""
    np = _np()
    img = np.asarray(img, dtype=np.float64)
    h, w = img.shape[0], img.shape[1]
    x = np.asarray(u, dtype=np.float64) * w - 0.5
    y = np.asarray(v, dtype=np.float64) * h - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    xi0 = np.clip(x0.astype(np.int64), 0, w - 1)
    xi1 = np.clip(x0.astype(np.int64) + 1, 0, w - 1)
    yi0 = np.clip(y0.astype(np.int64), 0, h - 1)
    yi1 = np.clip(y0.astype(np.int64) + 1, 0, h - 1)
    a, b = img[yi0, xi0], img[yi0, xi1]
    c, d = img[yi1, xi0], img[yi1, xi1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _h(sb, k, seed):
    return gs()['hash3'](sb, k, seed)


# ------------------------------------------------------------------ field
def fbm(qx, qy, z, P):
    G = gs()
    v = 0.0
    a = 0.5
    for o in range(min(max(int(P['Octaves'] + 0.5), 1), 6)):
        v = v + a * G['vnoise'](qx + z + o * 5.3, qy + 0.61 * z + o * 9.1, int(P['Seed']) + 31 + o)
        qx, qy = qx * 2.0, qy * 2.0
        a *= 0.5
    return v


def curl(px, py, T, P):
    """Curl of the fbm potential at px, py (pixels), noise units per noise unit (== pg_curl)."""
    np = _np()
    px, py = np.asarray(px, dtype=np.float64), np.asarray(py, dtype=np.float64)
    s = max(P['Flowscale'], 1e-3)
    qx, qy = px / s, py / s
    z = T * P['Evolve']
    e = 0.01
    dx = fbm(qx + e, qy, z, P) - fbm(qx - e, qy, z, P)
    dy = fbm(qx, qy + e, z, P) - fbm(qx, qy - e, z, P)
    return dy / (2 * e), -dx / (2 * e)


def velocity(px, py, T, P, pts=(), field=None, W=1080, H=1920, drive=(0.0, 120.0, 0.0, 0.0)):
    """Velocity px/s at px, py (== pg_vel). pts = rack points [(x, y, vx, vy)]; field = in2 image (mask: r =
    presence; flowtop: xy = velocity cells/s at its own res)."""
    np = _np()
    G = gi()
    px, py = np.asarray(px, dtype=np.float64), np.asarray(py, dtype=np.float64)
    boost = 1.0 + G['env'](drive[0], drive[1], P['Beatgain'], P['Beatdecay']) + \
        G['level'](drive[2], P['Audiogain'], P['Manual'])
    cx, cy = curl(px, py, T, P)
    vx, vy = P['Flowstrength'] * boost * cx, P['Flowstrength'] * boost * cy
    fs = int(P['Fieldsource'])
    if field is not None and fs == 0 and P['Maskforce'] != 0.0:
        fh, fw = field.shape[0], field.shape[1]
        ex, ey = W / float(fw), H / float(fh)
        pr = lambda x, y: bilinear(field, x / W, y / H)[..., 0]
        gx = (pr(px + ex, py) - pr(px - ex, py)) / (2 * ex)
        gy = (pr(px, py + ey) - pr(px, py - ey)) / (2 * ey)
        vx, vy = vx + P['Maskforce'] * gx * 100.0, vy + P['Maskforce'] * gy * 100.0
    elif field is not None and fs == 1:
        f = bilinear(field, px / W, py / H)
        k = H / float(field.shape[0])
        vx, vy = vx + P['Flowgain'] * f[..., 0] * k, vy + P['Flowgain'] * f[..., 1] * k
    R = max(P['Radius'], 1e-3)
    pm = int(P['Pointmode'])
    for q in list(pts)[:MAXPTS]:
        if q[0] <= -1.0:
            continue
        dx, dy = px - q[0] * W, py - q[1] * H
        r = np.hypot(dx, dy)
        inside = r < R
        w = np.where(inside, (1 - r / R) ** 2, 0.0)
        safe = np.where(r > 1e-6, r, 1.0)
        nx, ny = np.where(r > 1e-6, dx / safe, 0.0), np.where(r > 1e-6, dy / safe, 0.0)
        if pm == 1:
            fx, fy = -nx, -ny
        elif pm == 2:
            fx, fy = -ny, nx
        else:
            fx, fy = nx, ny
        vx = vx + w * (P['Pointforce'] * fx + P['Pointvel'] * q[2] * W)
        vy = vy + w * (P['Pointforce'] * fy + P['Pointvel'] * q[3] * H)
    return vx, vy


# ------------------------------------------------------------------ spawn + state step (== state.glsl)
def spawn(s, P, W, H, pts=(), field=None):
    """Arrays of seeds s -> (x, y, life) of their new lives (== pg_spawn)."""
    np = _np()
    s = np.asarray(s, dtype=np.float64)
    sb = (s * SB).astype(np.int64)
    sd = int(P['Seed'])
    h1, h2, h3, h4 = (_h(sb, k, sd) for k in (1, 2, 3, 4))
    x, y = h1 * W, h2 * H
    mode = int(P['Spawnmode'])
    if mode == 1 and len(pts):
        n = len(pts)
        k = np.minimum((h3 * n).astype(np.int64), n - 1)
        q = np.array(pts, dtype=np.float64)[k]
        ok = q[:, 0] > -1.0
        a = 2 * math.pi * _h(sb, 5, sd)
        r = P['Radius'] * np.sqrt(h4)
        x = np.where(ok, q[:, 0] * W + r * np.cos(a), x)
        y = np.where(ok, q[:, 1] * H + r * np.sin(a), y)
    elif mode == 2 and int(P['Fieldsource']) == 0 and field is not None:
        done = np.zeros(s.shape, dtype=bool)
        for t in range(4):
            cx, cy = _h(sb, 10 + 2 * t, sd) * W, _h(sb, 11 + 2 * t, sd) * H
            x, y = np.where(done, x, cx), np.where(done, y, cy)
            done = done | (bilinear(field, x / W, y / H)[..., 0] > 0.5)
    elif mode == 3:
        y = h2 * 0.02 * H
    life = np.maximum(P['Life'] * (1 + P['Lifevar'] * (2 * h3 - 1)), 0.05)
    return x, y, life


def state_step(state, P, now, epoch, W=1080, H=1920, pts=(), field=None, drive=(0.0, 120.0, 0.0, 0.0)):
    """One cook (== state.glsl). state = [S + 1, 2S, 4] or None. Returns the new state (float64)."""
    np = _np()
    S = max(8, int(P['Side']))
    fresh = state is None or state.shape != (S + 1, 2 * S, 4)
    if not fresh:
        m0, m1 = state[S, 0], state[S, 1]
        fresh = m0[3] != epoch
        if not fresh and m0[2] == now:
            return state.copy()
    dt = 0.0 if fresh else min(max(now - m0[2], 0.0), 0.1)
    dts = dt * P['Speed']
    T = (0.0 if fresh else m0[1]) + dts
    out = np.zeros((S + 1, 2 * S, 4))
    j, i = np.mgrid[0:S, 0:S]
    if fresh:
        s = gs()['hash3'](i, j, int(P['Seed']))
        x, y, life = spawn(s, P, W, H, pts, field)
        age = _h((s * SB).astype(np.int64), 6, int(P['Seed'])) * life
        A = np.stack([x, y, age, life], -1)
        B = np.stack([x, y, s, np.zeros(s.shape)], -1)
    else:
        A = state[:S, 0::2].copy()
        B = state[:S, 1::2].copy()
        if dts != 0.0:
            vx, vy = velocity(A[..., 0], A[..., 1], T, P, pts, field, W, H, drive)
            A[..., 0] += vx * dts
            A[..., 1] += vy * dts
            A[..., 2] += abs(dts)
            B[..., 3] = np.hypot(vx, vy)
            k = min(max(P['Morph'] * abs(dts), 0.0), 1.0)
            B[..., 0] += (A[..., 0] - B[..., 0]) * k
            B[..., 1] += (A[..., 1] - B[..., 1]) * k
            m = 0.05 * H
            out_ = (A[..., 0] < -m) | (A[..., 1] < -m) | (A[..., 0] > W + m) | (A[..., 1] > H + m)
            if int(P['Edge']) == 1:
                wx, wy = np.mod(A[..., 0], W), np.mod(A[..., 1], H)
                B[..., 0] = np.where(out_, B[..., 0] + wx - A[..., 0], B[..., 0])
                B[..., 1] = np.where(out_, B[..., 1] + wy - A[..., 1], B[..., 1])
                A[..., 0], A[..., 1] = np.where(out_, wx, A[..., 0]), np.where(out_, wy, A[..., 1])
                out_ = np.zeros(out_.shape, dtype=bool)
            dead = (A[..., 2] >= A[..., 3]) | out_
            if dead.any():
                sn = _h((B[..., 2] * SB).astype(np.int64), 7, int(P['Seed']))
                x, y, life = spawn(sn, P, W, H, pts, field)
                A = np.where(dead[..., None], np.stack([x, y, np.zeros(x.shape), life], -1), A)
                B = np.where(dead[..., None], np.stack([x, y, sn, np.zeros(x.shape)], -1), B)
    out[:S, 0::2] = A
    out[:S, 1::2] = B
    out[S, 0] = [0.0, T, now, epoch]
    out[S, 1] = [dts, (0.0 if fresh else state[S, 1][1]) + 1.0, 0.0, 0.0]
    return out


# ------------------------------------------------------------------ splat / trail / look
def splat(state, P, colsrc, W=1080, H=1920):
    """Scatter dots (== splat.glsl, particles in row-major order; the GPU's write order differs only where dots
    overlap). Returns [th, tw, 4] premultiplied rgb + a."""
    np = _np()
    S = state.shape[0] - 1
    T = state[S, 0][1]
    Q = P['Quality']
    tw, th = max(1, int(W * Q + 0.5)), max(1, int(H * Q + 0.5))
    out = np.zeros((th, tw, 4))
    A = state[:S, 0::2].reshape(-1, 4)
    B = state[:S, 1::2].reshape(-1, 4)
    live = (A[:, 3] > 0) & (A[:, 2] >= 0)
    af = max(P['Agefade'], 1e-4) * A[:, 3]
    safe = np.where(af > 0, af, 1.0)
    a = P['Opacity'] * np.clip(A[:, 2] / safe, 0, 1) * np.clip((A[:, 3] - A[:, 2]) / safe, 0, 1)
    live &= a > 0
    mode = int(P['Colormode'])
    u, v = B[:, 0] / W, B[:, 1] / H
    if mode == 0:
        col = bilinear(colsrc, u, v)[:, :3]
    elif mode == 1:
        N = max(math.floor(P['Atlascells'] + 0.5), 1.0)
        k = B[:, 2] * N * N + T * P['Atlasrate']
        f = k - np.floor(k)
        f = f * f * (3 - 2 * f)

        def cell(c):
            c = np.mod(c, N * N)
            ox, oy = np.mod(c, N), np.floor(c / N)
            return bilinear(colsrc, (ox + np.clip(u, 0, 1)) / N, (oy + np.clip(v, 0, 1)) / N)[:, :3]
        col = cell(np.floor(k)) * (1 - f)[:, None] + cell(np.floor(k) + 1) * f[:, None]
    else:
        key = B[:, 3] / max(P['Speedref'], 1e-6) if mode == 2 else (A[:, 2] / np.where(A[:, 3] > 0, A[:, 3], 1.0)
                                                                    if mode == 3 else B[:, 2])
        col = gs()['palette'](key, int(P['Palette']), P['Colora'], P['Colorb'], P['Palshift'])
    s = min(max(int(P['Size'] * Q + 0.5), 1), 16)
    c0x = np.floor(A[:, 0] * Q).astype(np.int64) - (s - 1) // 2
    c0y = np.floor(A[:, 1] * Q).astype(np.int64) - (s - 1) // 2
    o = np.concatenate([col * a[:, None], a[:, None]], 1)
    idx = np.nonzero(live)[0]
    for dy in range(s):
        for dx in range(s):
            qx, qy = c0x[idx] + dx, c0y[idx] + dy
            ok = (qx >= 0) & (qy >= 0) & (qx < tw) & (qy < th)
            out[qy[ok], qx[ok]] = o[idx[ok]]
    return out


def trail_step(spl, fb, dts, P):
    np = _np()
    f = fb if fb is not None and fb.shape == spl.shape else np.zeros(spl.shape)
    decay = math.exp(-abs(dts) / P['Trail']) if P['Trail'] > 0 else 0.0
    mode = int(P['Trailmode'])
    if mode == 1:
        return f * decay + spl
    if mode == 2:
        return np.where(spl[..., 3:4] > 0, spl, f * decay)
    return np.maximum(f * decay, spl)


def look(base, trail, P, pix):
    """rgba at pixels [(x, y)] of the slot (== look.glsl + gs_blend)."""
    np = _np()
    H, W = base.shape[0], base.shape[1]
    out = []
    for x, y in pix:
        cx, cy = x + 0.5, y + 0.5
        t = bilinear(trail, np.array([cx / W]), np.array([cy / H]))[0]
        gl = np.zeros(3)
        if P['Glow'] > 0:
            r = max(P['Glowwidth'], 0.5)
            for k in range(12):
                a = 2 * math.pi * (k + 0.5) / 12.0
                gl += bilinear(trail, np.array([(cx + r * math.cos(a)) / W]), np.array([(cy + r * math.sin(a)) / H]))[0, :3]
                if k % 2 == 0:
                    gl += bilinear(trail, np.array([(cx + 0.5 * r * math.cos(a + 0.26)) / W]),
                                   np.array([(cy + 0.5 * r * math.sin(a + 0.26)) / H]))[0, :3]
            gl *= P['Glow'] / 18.0
        col = (t[:3] + gl) * P['Exposure']
        lum = 0.2126 * gl[0] + 0.7152 * gl[1] + 0.0722 * gl[2]
        a = min(max((t[3] + lum) * P['Exposure'], 0.0), 1.0)
        out.append(gs()['blend'](base[y, x][None, :], col[None, :], np.array([a]), int(P['Blend']), P['Amount'])[0])
    return np.array(out)


def run(P, frames, W=270, H=480, fps=60.0, pts_fn=None, field=None, colsrc=None, epoch=1.0):
    """frames cooks of state + splat + trail; returns (state, trail)."""
    np = _np()
    st, tr = None, None
    colsrc = colsrc if colsrc is not None else np.full((H, W, 4), 0.5)
    for k in range(frames):
        pts = pts_fn(k) if pts_fn else ()
        st = state_step(st, P, 100.0 + k / fps, epoch, W, H, pts, field)
        sp = splat(st, P, colsrc, W, H)
        S = st.shape[0] - 1
        tr = trail_step(sp, tr, st[S, 1][0], P)
    return st, tr
