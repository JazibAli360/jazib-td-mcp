"""Jazib MCP for TouchDesigner -- "lose nothing" (26 Oct 2026, after crashes T-64/T-70/T-74/T-76 and T-77).

Two guards (contract: docs/PROTOCOL.md "Lose nothing"; how to use: docs/USING_TD.md "Lose nothing"):

1. Pre-risk save. handlers.dispatch() asks pre_risk(cmd, args) before a command in handlers.PRESAVE_CMDS runs. When
   the call is risky (risk_reasons: an op type this project never had, a .tox / plugin / C++ op, font pars, a
   builder build, a destroy, a module reload, a checkpoint restore) the project is saved FIRST with
   handlers.cmd_save_project (the same in-place save as td_save_project / autosave: next free X.N.toe, T-37 safe,
   rotation T-71; an installed td_save_hook also writes its .jtdnet sidecar after it). Rate-limited: no save when any
   save (pre-risk, autosave, td_save_project) happened in the last min_s (60) seconds; skipped while realTime is off
   (offline render, T-64), in perform mode, or before the project was ever saved. Never raises into the command.
2. Per-COMP checkpoints. cmd_checkpoint saves one COMP as output/checkpoints/<comp>/<comp>_<stamp>.tox (+ a .json with
   where it lived: parent, xy, wiring, allowCooking, stage plan, build) after an optional error check, keeps the
   newest 5, and never turns the COMP into an externaltox COMP (COMP.save, par values checked before/after).
   cmd_restore_checkpoint reloads a COMP from one T-70-safely: the current COMP is first saved to
   <dir>/pre_restore/ (lose nothing), the .tox is loaded into the same parent with cooking off and a temp name, the old
   COMP goes through safe_destroy (windows closed, panes moved, destroy deferred), the new one takes the name, xy,
   wires and cooking state, its stage plan is re-applied (restage, T-69), and windows that were open reopen 10 frames
   later.

Loading: like td/debug.py. handlers._safety() reads THIS FILE from beside handlers.py and execs it into a module
object, re-read when its mtime changes (no td_reload for edits here); bind(globals()) hands it the handlers helpers
through H. It never imports td. State that must survive an edit of this file lives in handlers.PRESAVE.
Pure ASCII.
"""
import json
import os
import re
import time

H = {}  # handlers' globals, set by bind() (tests pass a fake dict)


def bind(g):
    global H
    H = g
    return H


def G(name, default=None):
    return H.get(name, default)


def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ================================================================== risk (pure)

OP_TYPE = r'[a-z][a-z0-9]*(?:TOP|CHOP|SOP|DAT|COMP|MAT|POP)'
CREATE_RE = re.compile(r'\bcreate\(\s*(?:td\.)?[\'"]?(' + OP_TYPE + r')\b')
MK_RE = re.compile(r'\b_mk\(\s*[^,()]+,\s*(?:td\.)?(' + OP_TYPE + r')\b')  # builders' _mk(comp, type, name)
CPP_RE = re.compile(r'cplusplus(?:TOP|CHOP|SOP|DAT|POP)|\.par\.plugin\b|\.plugin[\'"]|\.dylib\b|\.bundle[\'"]')
TOX_RE = re.compile(r'loadTox\(|\.par\.externaltox\b|enableexternaltoxpulse')
FONT_RE = re.compile(r'\.par\.font\w*\b|\bfontfile\b')
BUILDER_RE = re.compile(r'builders/\w+\.py|\[\s*[\'"]build\w*[\'"]\s*\]\s*\(')
DESTROY_RE = re.compile(r'\bsafe_destroy\(|\.destroy\(')
RELOAD_RE = re.compile(r'\breload\(|\bimportlib\b|\bcmd_reload\b')
OPT_OUT = '# no-presave'
FONT_PARS = re.compile(r'^font\w*$|^fontfile$')
PLUGIN_PARS = ('plugin', 'pluginpath')
TOX_CMDS = ('tox_load', 'tda_load', 'library_load')
BUILD_CMDS = ('comfy_build', 'isf', 'publish', 'osc_learn', 'link', 'live_audio', 'import_ae_anim', 'midi_build',
              'shadertoy', 'osc_expose', 'layer_mixer', 'debug_panel_build')


def exec_types(code):
    """Pure: op types an exec creates by name (create(noiseTOP), create('noiseTOP'), td.x, builders' _mk(c, x, ..))."""
    seen, out = set(), []
    for rx in (CREATE_RE, MK_RE):
        for m in rx.finditer(code or ''):
            t = m.group(1)
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def new_types(cmd, args, seen):
    """Pure: op types this call creates that `seen` (types the project already has) lacks. seen may be a callable,
    called only when the call creates something (the project scan is skipped for every other exec)."""
    if cmd == 'exec':
        cands = exec_types(args.get('code') or '')
    elif cmd == 'create':
        t = args.get('type')
        cands = [t] if isinstance(t, str) and t else []
    else:
        cands = []
    if not cands:
        return []
    seen = seen() if callable(seen) else seen
    return [t for t in cands if t not in seen]


def risk_reasons(cmd, args, seen, is_comp=lambda p: False):
    """Pure: why this call is risky enough to save the project first ([] = not risky). seen = op types the project
    already has (a set, or a callable returning one); is_comp(path) says whether a path is a COMP (td_delete of COMPs). '# no-presave' in exec code opts out."""
    args = args if isinstance(args, dict) else {}
    out = ['new op type ' + t for t in new_types(cmd, args, seen)]
    if cmd == 'exec':
        code = args.get('code') or ''
        if OPT_OUT in code:
            return []
        for rx, why in ((CPP_RE, 'C++ op / plugin'), (TOX_RE, 'loads a .tox'), (FONT_RE, 'font change'),
                        (BUILDER_RE, 'builder build'), (DESTROY_RE, 'destroy'), (RELOAD_RE, 'module reload')):
            if rx.search(code):
                out.append(why)
    elif cmd == 'create':
        if str(args.get('type') or '').startswith('cplusplus'):
            out.append('C++ op / plugin')
        out += _par_risks(args.get('pars'))
    elif cmd == 'set_pars':
        out += _par_risks(args.get('pars'))
    elif cmd in TOX_CMDS:
        out.append('loads a .tox')
    elif cmd == 'delete':
        paths = args.get('paths')
        paths = [paths] if isinstance(paths, str) else (paths or [])
        out += ['destroys COMP ' + p for p in paths if isinstance(p, str) and _try(lambda: is_comp(p), False)]
    elif cmd == 'reload':
        out.append('module reload')
    elif cmd == 'restore_checkpoint':
        out.append('checkpoint restore (tox load + destroy)')
    elif cmd in BUILD_CMDS:
        out.append('builder ' + cmd)
    return out


def _par_risks(pars):
    out = []
    names = list(pars) if isinstance(pars, dict) else []
    if any(FONT_PARS.match(str(n)) for n in names):
        out.append('font change')
    if any(str(n) in PLUGIN_PARS for n in names):
        out.append('C++ op / plugin')
    return out


def presave_due(now, last, min_s):
    """Pure: may a pre-risk save run now? (no save yet, or the last one is min_s or more ago)."""
    return last is None or now - last >= float(min_s)


def presave_skip(state, real_time, perform, has_folder, now):
    """Pure: why the pre-risk save is skipped (None = save)."""
    if not state.get('on', True):
        return 'pre-risk save is off (td_presave on:true)'
    if real_time is False:
        return 'realTime is off (offline render, T-64)'
    if perform:
        return 'perform mode (no save hitch during a show)'
    if not has_folder:
        return 'project was never saved (no folder)'
    if not presave_due(now, state.get('last'), state.get('min_s', 60)):
        return 'saved {:.0f} s ago (at most one save per {:.0f} s)'.format(now - state['last'], state.get('min_s', 60))
    return None


# ================================================================== pre-risk save (TD side)

ROOT_SKIP = ('sys', 'ui', 'local')  # TD's own trees: their op types say nothing about this project
SEEN_TTL_S = 120.0


def project_types():
    """Op types under every root child but /sys, /ui, /local (cached SEEN_TTL_S; the MCP COMP counts too)."""
    st = G('PRESAVE')
    now = time.monotonic()
    if st.get('seen') is not None and now - (st.get('seen_at') or 0) < SEEN_TTL_S:
        return st['seen']
    types = set(st.get('seen_extra') or ())
    root = G('op')('/')
    for c in list(_try(lambda: root.children, []) or []):
        if c.name in ROOT_SKIP:
            continue
        types.add(_try(lambda: c.OPType, ''))
        for o in _try(lambda: c.findChildren(), []) or []:
            types.add(_try(lambda: o.OPType, ''))
    types.discard('')
    st['seen'], st['seen_at'] = types, now
    return types


def _is_comp(path):
    o = _try(lambda: G('op')(path))
    return bool(o is not None and _try(lambda: o.isCOMP, False))


def pre_risk(cmd, args):
    """Called by handlers.dispatch before a PRESAVE_CMDS command. Returns None (not risky) or a dict for the reply's
    pre_save field: {reasons, saved?, ms?, skipped?, error?}. Never raises."""
    st = G('PRESAVE')
    try:
        reasons = risk_reasons(cmd, args, project_types, _is_comp)
    except Exception as e:
        return {'error': 'risk check: {}: {}'.format(type(e).__name__, e)}
    if not reasons:
        return None
    out = {'reasons': reasons}
    proj = G('project')
    now = time.monotonic()
    why = presave_skip(st, _try(lambda: proj.realTime, True), _try(lambda: G('ui').performMode, False),
                       bool(_try(lambda: str(proj.folder), '')), now)
    if why:
        st['skipped'] = st.get('skipped', 0) + 1
        out['skipped'] = why
    else:
        t0 = time.perf_counter()
        try:
            r = G('cmd_save_project')()
            out['saved'] = r['file']
            st['count'] = st.get('count', 0) + 1
            st['last_file'] = r['file']
        except Exception as e:
            st['last'] = now  # a failing save is retried after min_s, not before every risky call
            st['error'] = str(e)[:200]
            out['error'] = 'save failed: {}: {}'.format(type(e).__name__, e)
        out['ms'] = round((time.perf_counter() - t0) * 1000, 1)
    # the types this call creates count as seen from now on (TD survived the call or the save holds the state before)
    extra = st.setdefault('seen_extra', [])
    for t in new_types(cmd, args if isinstance(args, dict) else {}, ()):
        if t not in extra:
            extra.append(t)
        if st.get('seen') is not None:
            st['seen'].add(t)
    return out


def cmd_presave(on=None, min_s=None, check=None):
    """Read / set the pre-risk save. check {cmd, args}: say what would happen for that call (nothing saved)."""
    st = G('PRESAVE')
    if on is not None:
        st['on'] = bool(on)
    if min_s is not None:
        if float(min_s) < 10:
            raise ValueError('min_s must be >= 10 (a save costs TD a hitch)')
        st['min_s'] = float(min_s)
    r = {'on': st.get('on', True), 'min_s': st.get('min_s', 60), 'count': st.get('count', 0),
         'skipped': st.get('skipped', 0), 'last_file': st.get('last_file'), 'error': st.get('error'),
         'seen_types': len(project_types()), 'commands': sorted(G('PRESAVE_CMDS'))}
    last = st.get('last')
    r['last_save_s_ago'] = None if last is None else round(time.monotonic() - last, 1)
    if check is not None:
        if not isinstance(check, dict) or not isinstance(check.get('cmd'), str):
            raise ValueError('check must be {cmd, args}')
        c, a = check['cmd'], check.get('args') or {}
        reasons = risk_reasons(c, a, project_types, _is_comp) if c in G('PRESAVE_CMDS') else []
        proj = G('project')
        r['check'] = {'reasons': reasons, 'would_save': bool(reasons) and presave_skip(
            st, _try(lambda: proj.realTime, True), _try(lambda: G('ui').performMode, False),
            bool(_try(lambda: str(proj.folder), '')), time.monotonic()) is None}
    return r


# ================================================================== checkpoints (pure)

CKPT_KEEP = 5
STAMP_RE = r'(\d{8}-\d{6}(?:-\d+)?)'
OWNER_FILE = '.path'


def ckpt_name_re(name):
    return re.compile('^' + re.escape(name) + '_' + STAMP_RE + r'\.tox$')


def stamp_key(s):
    """Sort key of a stamp YYYYmmdd-HHMMSS[-n]: same second -> by n."""
    parts = s.split('-')
    return (parts[0], parts[1], int(parts[2]) if len(parts) > 2 else 1)


def ckpt_list(listing, name):
    """Pure: checkpoint files of COMP `name` in a folder listing, newest first: [(stamp, file)]."""
    rx = ckpt_name_re(name)
    out = [(m.group(1), n) for n, m in ((n, rx.match(n)) for n in listing) if m]
    out.sort(key=lambda x: stamp_key(x[0]), reverse=True)
    return out


def ckpt_prune(listing, name, keep=CKPT_KEEP):
    """Pure: the .tox files (and their .json) beyond the newest `keep`."""
    old = ckpt_list(listing, name)[max(1, int(keep)):]
    out = []
    for _s, f in old:
        out.append(f)
        j = f[:-4] + '.json'
        if j in listing:
            out.append(j)
    return out


def ckpt_stamp(listing, name, base):
    """Pure: a stamp that sorts after every one of this second in the folder (base, base-2, base-3 ...); pruned
    lower numbers are never reused (a reused base would sort oldest and be pruned at once)."""
    same = [stamp_key(s)[2] for s, _f in ckpt_list(listing, name) if s == base or s.startswith(base + '-')]
    return '{}-{}'.format(base, max(same) + 1) if same else base


def ckpt_pick(items, which='latest'):
    """Pure: one (stamp, file) of ckpt_list items. which: 'latest' / None, 'previous', an index (0 = latest), or a
    stamp prefix ('20261026-1612')."""
    if not items:
        raise ValueError('no checkpoints')
    if which in (None, '', 'latest'):
        return items[0]
    if which == 'previous':
        which = 1
    if isinstance(which, bool):
        raise ValueError('bad which {!r}'.format(which))
    if isinstance(which, int) or (isinstance(which, str) and which.isdigit() and len(which) < 4):
        i = int(which)
        if not 0 <= i < len(items):
            raise ValueError('which={} but there are {} checkpoints (0 = latest)'.format(i, len(items)))
        return items[i]
    hits = [x for x in items if x[0].startswith(str(which))]
    if not hits:
        raise ValueError('no checkpoint stamped {!r}; have: {}'.format(which, ', '.join(s for s, _f in items)))
    return hits[0]


def slug(path):
    return re.sub(r'[^A-Za-z0-9_]+', '_', path.strip('/')) or 'root'


def ckpt_dir_names(path):
    """Pure: candidate folder names for a COMP path: its name, then name__<parent slug> (same name elsewhere)."""
    name = path.rstrip('/').rsplit('/', 1)[-1]
    parent = path.rstrip('/').rsplit('/', 1)[0] or '/'
    return [name, '{}__{}'.format(name, slug(parent))]


# ================================================================== checkpoints (TD side)

def default_root():
    return os.path.join(os.path.dirname(os.path.dirname(G('handlers_file')())), 'output', 'checkpoints')


def ckpt_dir(path, root=None, create=False):
    """The folder for COMP `path`: <root>/<name> owned by that path (OWNER_FILE), else <name>__<parent slug>."""
    root = root or default_root()
    for n in ckpt_dir_names(path):
        d = os.path.join(root, n)
        own = os.path.join(d, OWNER_FILE)
        if os.path.isfile(own):
            with open(own, 'r', encoding='utf-8') as f:
                if f.read().strip() == path:
                    return d
            continue
        if os.path.isdir(d) and os.listdir(d):
            continue  # someone else's files, no owner note: leave them
        if create:
            os.makedirs(d, exist_ok=True)
            with open(own, 'w', encoding='utf-8') as f:
                f.write(path + '\n')
        return d
    raise ValueError('no free checkpoint folder for {} under {}'.format(path, root))


def _conns(c):
    ins, outs = [], []
    for cn in list(_try(lambda: c.inputConnectors, []) or []):
        src = [x for x in (_try(lambda: cn.connections, []) or [])]
        ins.append([src[0].owner.path, int(src[0].index)] if src else None)
    for j, cn in enumerate(list(_try(lambda: c.outputConnectors, []) or [])):
        for x in (_try(lambda: cn.connections, []) or []):
            outs.append([j, x.owner.path, int(x.index)])
    return ins, outs


def comp_state(c):
    """Plain data about where/how COMP c lives (kept in the checkpoint .json and used by a restore)."""
    ins, outs = _conns(c)
    plan = _try(lambda: c.fetch(G('STAGE_KEY'), None, search=False), None)
    wins = []
    for w, tgt in (_try(G('open_windows'), []) or []):
        if w.path.startswith(c.path + '/'):
            wins.append(w.path[len(c.path) + 1:])
    col = _try(lambda: list(c.color), None)
    return {'path': c.path, 'name': c.name, 'parent': c.parent().path, 'type': _try(lambda: c.OPType, ''),
            'xy': [_try(lambda: int(c.nodeX), 0), _try(lambda: int(c.nodeY), 0)],
            'color': col, 'comment': _try(lambda: c.comment, ''),
            'allowCooking': bool(_try(lambda: c.allowCooking, True)),
            'externaltox': str(_try(lambda: c.par.externaltox.eval(), '') or ''),
            'enableexternaltox': _try(lambda: bool(c.par.enableexternaltox.eval()), None),
            'inputs': ins, 'outputs': outs, 'stages': plan if isinstance(plan, dict) else None,
            'open_windows': wins, 'ops': len(_try(lambda: c.findChildren(), []) or [])}


def _ext_state(c):
    return (str(_try(lambda: c.par.externaltox.val, '') or ''), _try(lambda: c.par.enableexternaltox.val, None))


def save_tox(c, file):
    """COMP.save to a temp name, then os.replace; externaltox / enableexternaltox put back if the save moved them."""
    before = _ext_state(c)
    tmp = file[:-4] + '.part.tox'
    c.save(tmp)
    os.replace(tmp, file)
    after = _ext_state(c)
    notes = []
    if after != before:  # never seen on 31550; the task rule is "never turn it into an externaltox COMP"
        _try(lambda: setattr(c.par.externaltox, 'val', before[0]))
        if before[1] is not None:
            _try(lambda: setattr(c.par.enableexternaltox, 'val', before[1]))
        notes.append('the save changed externaltox/enableexternaltox; put back')
    return notes


def _write_json(file, data):
    tmp = file + '.part'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, file)


def _read_json(file):
    try:
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _comp(path):
    c = G('_op')(path)
    if not _try(lambda: c.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(c.path))
    if G('_protected')(c.path):
        raise ValueError('refusing {} (the MCP COMP, its contents or an ancestor)'.format(c.path))
    return c


def _errors_under(c):
    items = []
    for o in [c] + list(_try(lambda: c.findChildren(), []) or []):
        e = _try(lambda: o.errors(), '') or ''
        s = _try(lambda: o.scriptErrors(), '') or ''
        if e or s:
            items.append({'path': o.path, 'errors': (e + ('\nScript: ' + s if s else '')).strip()})
    return items


def write_checkpoint(c, root=None, keep=CKPT_KEEP, note=None, kind='checkpoint'):
    """Save COMP c now. kind 'checkpoint' -> <dir>/<name>_<stamp>.tox, 'pre_restore' -> <dir>/pre_restore/."""
    t0 = time.perf_counter()
    d = ckpt_dir(c.path, root, create=True)
    if kind == 'pre_restore':
        d = os.path.join(d, 'pre_restore')
        os.makedirs(d, exist_ok=True)
    ls = os.listdir(d)
    stamp = ckpt_stamp(ls, c.name, time.strftime('%Y%m%d-%H%M%S'))
    file = os.path.join(d, '{}_{}.tox'.format(c.name, stamp))
    meta = comp_state(c)
    proj = G('project')
    meta.update({'stamp': stamp, 'kind': kind, 'note': note, 'saved': time.strftime('%Y-%m-%d %H:%M:%S'),
                 'build': G('td_build_string')(_try(lambda: G('app').version, ''), _try(lambda: G('app').build, '')),
                 'project': os.path.join(str(_try(lambda: proj.folder, '')), str(_try(lambda: proj.name, '')))})
    notes = save_tox(c, file)
    _write_json(file[:-4] + '.json', meta)
    pruned = ckpt_prune(os.listdir(d), c.name, keep)
    for f in pruned:
        _try(lambda: os.remove(os.path.join(d, f)))
    r = {'file': file, 'stamp': stamp, 'bytes': _try(lambda: os.path.getsize(file), 0),
         'kept': len(ckpt_list(os.listdir(d), c.name)), 'pruned': [f for f in pruned if f.endswith('.tox')],
         'ops': meta['ops'], 'ms': round((time.perf_counter() - t0) * 1000, 1)}
    if notes:
        r['notes'] = notes
    return r


def cmd_checkpoint(path, verify=True, frames=2, keep=CKPT_KEEP, note=None, force=False, root=None, list_only=False):
    """Checkpoint a COMP as .tox (after a clean error check when verify). list_only: only list its checkpoints."""
    if list_only:
        return list_checkpoints(path, root)
    c = _comp(path)
    keep = max(1, min(50, int(keep)))
    if not verify:
        return write_checkpoint(c, root, keep, note)
    p = G('cmd_errors')(c.path, max(2, int(frames)))  # force-cooks the COMP's ops, reads errors frames later

    def finish():
        items = [x for x in (p.finish().get('items') or []) if x.get('errors')]
        if not _try(lambda: c.valid, True):
            raise ValueError('{} is gone (destroyed while being checked)'.format(path))
        if items and not force:
            return {'saved': False, 'errors': items[:20], 'error_count': len(items),
                    'hint': 'fix the errors first (a checkpoint should be a known-good state), or force:true'}
        r = write_checkpoint(c, root, keep, note)
        r['saved'] = True
        r['verified'] = not items
        if items:
            r['errors'] = items[:20]
        return r
    return G('Pending')(p.frames, finish)


def list_checkpoints(path, root=None):
    try:
        d = ckpt_dir(path, root, create=False)
    except ValueError:
        return {'path': path, 'dir': None, 'checkpoints': []}
    name = path.rstrip('/').rsplit('/', 1)[-1]
    ls = os.listdir(d) if os.path.isdir(d) else []
    items = []
    for s, f in ckpt_list(ls, name):
        m = _read_json(os.path.join(d, f[:-4] + '.json')) or {}
        items.append({'stamp': s, 'file': os.path.join(d, f), 'saved': m.get('saved'), 'note': m.get('note'),
                      'ops': m.get('ops'), 'build': m.get('build')})
    pre = os.path.join(d, 'pre_restore')
    return {'path': path, 'dir': d, 'checkpoints': items,
            'pre_restore': [os.path.join(pre, f) for _s, f in ckpt_list(os.listdir(pre), name)] if os.path.isdir(pre)
            else []}


def _rewire(c, ins, outs, notes):
    op_ = G('op')
    n_in = len(_try(lambda: c.inputConnectors, []) or [])
    for i, src in enumerate(ins or []):
        if not src:
            continue
        s = op_(src[0])
        if s is None or i >= n_in or src[1] >= len(s.outputConnectors):
            notes.append('input {} from {} not restored'.format(i, src[0]))
            continue
        c.inputConnectors[i].connect(s.outputConnectors[src[1]])
    n_out = len(_try(lambda: c.outputConnectors, []) or [])
    for j, dst, k in outs or []:
        t = op_(dst)
        if t is None or j >= n_out or k >= len(t.inputConnectors):
            notes.append('output {} to {} input {} not restored'.format(j, dst, k))
            continue
        t.inputConnectors[k].connect(c.outputConnectors[j])


def cmd_restore_checkpoint(path, which='latest', root=None, frames=10, reopen=True):
    """Reload COMP `path` from one of its checkpoints, T-70-safely (see the module doc)."""
    path = path.rstrip('/')
    name = path.rsplit('/', 1)[-1]
    parent = G('_op')(path.rsplit('/', 1)[0] or '/', 'parent')
    if G('_protected')(path):
        raise ValueError('refusing {} (the MCP COMP, its contents or an ancestor)'.format(path))
    if not G('valid_op_name')(name):
        raise ValueError('bad COMP name {!r}'.format(name))
    d = ckpt_dir(path, root, create=False)
    _stamp, f = ckpt_pick(ckpt_list(os.listdir(d) if os.path.isdir(d) else [], name), which)
    file = os.path.join(d, f)
    meta = _read_json(file[:-4] + '.json') or {}
    notes = []
    old = G('op')(path)
    pre = None
    if old is not None:
        if not _try(lambda: old.isCOMP, False):
            raise ValueError('{} exists and is not a COMP'.format(path))
        pre = write_checkpoint(old, root, CKPT_KEEP, 'before restore of ' + f, kind='pre_restore')  # lose nothing
        state = comp_state(old)
    else:
        state = meta
        notes.append('{} was not in the project: placed and wired from the checkpoint record'.format(path))
    new = parent.loadTox(file)
    new.allowCooking = False  # never two live copies (ports, senders, MIDI) while they swap
    new.name = '{}_restoring{}'.format(name, int(_try(lambda: new.id, 0) or 0))
    released = None
    if old is not None:
        released = G('safe_destroy')(old)  # T-70: windows closed, panes moved, renamed + deferred if a window showed it
    new.name = name
    xy = state.get('xy') or meta.get('xy')
    if xy:
        new.nodeX, new.nodeY = int(xy[0]), int(xy[1])
    if state.get('color'):
        _try(lambda: setattr(new, 'color', tuple(state['color'])))
    if state.get('comment'):
        _try(lambda: setattr(new, 'comment', state['comment']))
    _rewire(new, state.get('inputs'), state.get('outputs'), notes)
    plan = _try(lambda: new.fetch(G('STAGE_KEY'), None, search=False), None)
    if not isinstance(plan, dict) and isinstance(meta.get('stages'), dict):
        new.store(G('STAGE_KEY'), meta['stages'])
    layout = None
    if G('_stage_plan')(new):
        layout = _try(lambda: G('restage')(new), None)
    cook = state.get('allowCooking', meta.get('allowCooking', True))
    new.allowCooking = bool(cook)
    wins = list(state.get('open_windows') or []) if reopen else []
    r = {'path': new.path, 'file': file, 'which': which, 'pre_restore': pre and pre['file'], 'released': released,
         'allowCooking': bool(cook), 'layout': layout}

    def finish():
        reopened = []
        for rel in wins:
            w = _try(lambda: new.op(rel))
            if w is not None and _try(lambda: w.par.winopen.pulse(), False) is not False:
                reopened.append(w.path)
        r['reopened'] = reopened
        r['errors'] = _errors_under(new)[:20]
        if notes:
            r['notes'] = notes
        return r
    return G('Pending')(max(1, int(frames)), finish)
