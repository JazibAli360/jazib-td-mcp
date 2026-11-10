# Dump every creatable operator of one family in this TD build, with all parameters, to JSON.
# Run inside TD (td_exec):  FAMILY = 'TOP'; exec(open('<repo>/tools/op_dump.py').read(), globals())
# Device / network / process ops are listed but NOT created (they can open cameras, ports or prompts).
# Pure ASCII (TD reads it).
import json, os, re, time
import td

OUT_DIR = '~/Documents/StageLab_PrismFest/jazib-td-mcp/docs/research/ops'
SKIP = re.compile(r'(device|ndi|syphon|spout|video|audio(?!filter|filein|para|band|spect|oscil|dynam|rend|movie)|midi|serial|tcp|udp|'
                  r'websocket|webserver|webclient|webrender|osc|dmx|artnet|sacn|kinect|leap|realsense|oak|orbbec|'
                  r'ouster|zed|hokuyo|joystick|touchin|touchout|pipe|mqtt|renderstream|st2110|nvidia|vrinput|openvr|'
                  r'oculus|tuio|helios|etherdream|laser|ltc|blackmagic|aja|bluefish|camschnappr|sharedmem|vioso|'
                  r'scalable|posistage|psn|zigsim|piezo|keyboardin|mousein|multitouch|wacom|tablet|bodytrack|facetrack|'
                  r'stype|freed|mosys|ncam|trackr|pozyx|optitrack|vicon|natnet|qualisys|motive|slsp|subprocess|'
                  r'licen|engine)', re.I)


def _j(v):
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


def _par(p):
    d = {'name': p.name, 'label': p.label, 'page': p.page.name if p.page is not None else None,
         'style': p.style, 'default': _j(p.default), 'tuplet': p.tupletName}
    try:
        if p.isMenu:
            d['menu'] = list(p.menuNames)
            labels = list(p.menuLabels)
            if labels != d['menu']:
                d['menuLabels'] = labels
    except Exception:
        pass
    for a in ('normMin', 'normMax', 'clampMin', 'clampMax', 'min', 'max'):
        try:
            d[a] = _j(getattr(p, a))
        except Exception:
            pass
    return d


def dump(family):
    host = op('/project1').op('_opdump') or op('/project1').create(baseCOMP, '_opdump')
    if family == 'COMP':
        host.nodeX, host.nodeY = 0, -2200
    names = sorted(n for n in dir(td) if n.endswith(family) and n != family and isinstance(getattr(td, n), type))
    rows, skipped, failed = [], [], []
    for n in names:
        if SKIP.search(n):
            skipped.append(n)
            continue
        t0 = time.perf_counter()
        try:
            o = host.create(getattr(td, n), 'probe')
        except Exception as e:
            failed.append({'type': n, 'error': str(e)[:200]})
            continue
        try:
            rows.append({'type': n, 'label': o.OPType, 'pars': [_par(p) for p in o.pars()],
                         'inputs': len(o.inputConnectors), 'outputs': len(o.outputConnectors),
                         'warnings': o.warnings()[:200], 'errors': o.errors()[:200],
                         'create_ms': round((time.perf_counter() - t0) * 1000, 1)})
        except Exception as e:
            failed.append({'type': n, 'error': 'introspect: ' + str(e)[:200]})
        finally:
            try:
                o.destroy()
            except Exception:
                pass
    host.destroy()
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {'build': app.build, 'family': family, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'count_classes': len(names), 'dumped': rows, 'skipped_not_created': skipped, 'failed': failed}
    path = os.path.join(OUT_DIR, 'ops_{}_{}.json'.format(family, app.build))
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    return {'family': family, 'classes': len(names), 'dumped': len(rows), 'skipped': len(skipped),
            'failed': len(failed), 'file': path}


DUMP_RESULT = dump(FAMILY)
