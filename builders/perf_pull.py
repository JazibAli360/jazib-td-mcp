# perf_pull - generic pull-and-measure sampler for a COMP's output (lane C; px_checks / px_lines_checks pattern,
# T-100 / T-102 / T-143): a run() chain pulls `out` once per frame (nothing else needs to view it; pane elsewhere),
# records cpu + gpu ms of every op under `comp` (recursive, maxDepth) that cooked for that pull, and the wall clock
# (real frames per second of the pulls). Storage holds only plain lists / dicts (no functions in op storage).
# Use (td_exec):  P = dict(globals()); exec(open('<repo>/builders/perf_pull.py').read(), P)
#   P['pump']('/project1/lab/GEN_sdf/scene1', 'out1', 120)      # starts the chain, returns at once
#   (>= n frames later, another exec)  print(P['report']('/project1/lab/GEN_sdf/scene1'))
# Never overlap two pumps (T-124 (3)). ASCII only.
PERF_FILE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/perf_pull.py'
KEY = 'perf_pull'


def _tick(comp, out, k, n, depth):
    import time
    c = op(comp)
    if c is None:
        return
    c.op(out).cook()
    rec = c.fetch(KEY, {}, search=False)
    rec.setdefault('wall', []).append(time.perf_counter())
    last = rec.setdefault('tc', {})
    tot = 0.0
    for x in c.findChildren(maxDepth=depth):
        try:
            tc = int(x.totalCooks)
            cooked = x.path in last and tc > last[x.path]
            last[x.path] = tc
            if not cooked:
                continue
            cpu, gpu = float(x.cpuCookTime), float(getattr(x, 'gpuCookTime', 0.0) or 0.0)
        except Exception:
            continue
        sp = rec.setdefault('split', {}).setdefault(x.path[len(comp) + 1:], [[], []])
        sp[0].append(cpu)
        sp[1].append(gpu)
        tot += cpu + gpu
    rec.setdefault('tot', []).append(tot)
    c.store(KEY, rec)
    if k + 1 < n:
        run("P = dict(globals()); exec(open(%r).read(), P); P['_tick'](%r, %r, %d, %d, %d)"
            % (PERF_FILE, comp, out, k + 1, n, depth), delayFrames=1, delayRef=op.TDResources)


def pump(comp, out='out1', n=120, depth=1):
    op(comp).store(KEY, {})
    _tick(comp, out, 0, n, depth)
    return n


def report(comp, keep=0.03):
    rec = op(comp).fetch(KEY, {}, search=False)
    w = rec.get('wall', [])
    med = lambda v: sorted(v)[len(v) // 2] if v else 0.0
    p90 = lambda v: sorted(v)[int(0.9 * (len(v) - 1))] if v else 0.0
    split = rec.get('split', {})
    ops = dict((k, {'cpu': round(med(v[0]), 3), 'gpu': round(med(v[1]), 3), 'gpu_p90': round(p90(v[1]), 3),
                    'cooks': len(v[0])})
               for k, v in split.items() if med(v[0]) + med(v[1]) > keep)
    return {'frames': len(w), 'pull_fps': round((len(w) - 1) / max(w[-1] - w[0], 1e-9), 1) if len(w) > 1 else 0.0,
            'total_ms_median': round(med(rec.get('tot', [])), 3), 'total_ms_p90': round(p90(rec.get('tot', [])), 3),
            'ops': ops}


# ---- paired A/B in the same frames (GEN_sdf perf-pass method): force-cook op a and op b every frame, alternating
# which goes first; GPU ms per op; the ratio of medians is stable under load where single medians are not.
def _ab_tick(a, b, k, n):
    oa, ob = op(a), op(b)
    if oa is None or ob is None:
        return
    first, second = (oa, ob) if k % 2 == 0 else (ob, oa)
    first.cook(force=True)
    second.cook(force=True)
    rec = oa.parent().fetch(KEY + '_ab', {}, search=False)
    rec.setdefault('a', []).append(float(getattr(oa, 'gpuCookTime', 0.0) or 0.0))
    rec.setdefault('b', []).append(float(getattr(ob, 'gpuCookTime', 0.0) or 0.0))
    oa.parent().store(KEY + '_ab', rec)
    if k + 1 < n:
        run("P = dict(globals()); exec(open(%r).read(), P); P['_ab_tick'](%r, %r, %d, %d)" % (PERF_FILE, a, b, k + 1, n),
            delayFrames=1, delayRef=op.TDResources)


def ab_pump(a, b, n=120):
    op(a).parent().store(KEY + '_ab', {})
    _ab_tick(a, b, 0, n)
    return n


def ab_report(a):
    rec = op(a).parent().fetch(KEY + '_ab', {}, search=False)
    med = lambda v: sorted(v)[len(v) // 2] if v else 0.0
    ma, mb = med(rec.get('a', [])[5:]), med(rec.get('b', [])[5:])        # first frames include compiles
    return {'n': len(rec.get('a', [])), 'a_gpu_median': round(ma, 3), 'b_gpu_median': round(mb, 3),
            'a_over_b': round(ma / mb, 3) if mb > 0 else None}
