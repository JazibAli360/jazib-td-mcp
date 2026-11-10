"""Jazib MCP for TouchDesigner -- component library (27 Oct 2026).

A COMP that works goes into library/<Name>/ as a reusable .tox (contract: docs/PROTOCOL.md "Component library";
how to use: docs/USING_TD.md "Component library"):

  <Name>.tox   COMP.save() (safety.save_tox: temp file + replace, externaltox never switched on)
  thumb.png    the COMP's first Out TOP, saveByteArray('.png') taken >= 3 frames after a force-cook that follows the
               un-park (T-74: never a TOP read in the script that changed it); the MCP shrinks it to <= 480 px
  README.md    first lines of docs/builds/<name>.md + ins/outs + custom pars by page + cook ms at export
  meta.json    name, version, td_build, created, source, inputs/outputs, pars (with values), files (file pars and
               where they point: repo / td_app / outside, exists), sha256, size, in_git
  library/index.json + INDEX.md are regenerated on every export; a .tox over 5 MB is listed in library/.gitignore
  (meta + sha stay in git).

Export refuses a COMP listed in logs/active_lanes.json (someone is building it) unless force. A parked COMP is
un-parked for the thumbnail and parked again; one that was cooking stays cooking; without an Out TOP or with
thumb:false (device outputs: audio, DMX, NDI, MIDI) it is never un-parked. Load = loadTox into parent under
newname, parked (allowCooking False), viewers on, stage plan re-applied (restage, T-69).

Loading: like td/debug.py. handlers._library() reads THIS FILE from beside handlers.py, execs it into a module,
re-reads it when its mtime changes; bind(globals()) hands it the handlers helpers through H. Pure ASCII.
"""
import hashlib
import json
import os
import re
import time

H = {}

BIG_TOX = 5 * 1024 * 1024
README_LINES = 12
IO_RE = re.compile(r'^(in|out)(TOP|CHOP|SOP|DAT|MAT|COMP|POP)$')
GITIGNORE_HEAD = '# written by td/library.py: .tox files over 5 MB stay out of git (meta.json keeps sha256 + size)'


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


# ================================================================== pure helpers (tested offline)

def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(G('handlers_file')())))


def lib_root(root=None):
    return os.path.abspath(root) if root else os.path.join(repo_root(), 'library')


def doc_candidates(name):
    """docs/builds/<file>.md names tried for COMP name: full lower (au_features), then without the prefix (physarum)."""
    low = name.lower()
    out = [low]
    if '_' in low:
        out.append(low.split('_', 1)[1])
    return out


def doc_head(text, n=README_LINES):
    """The doc's title (without #) and its first lines up to n, stopping at the second heading."""
    lines = (text or '').splitlines()
    title, body, seen_head = None, [], False
    for ln in lines:
        if ln.startswith('#'):
            if title is None:
                title = ln.lstrip('#').strip()
                seen_head = True
                continue
            if body:
                break
            continue
        if not seen_head and title is None and not ln.strip():
            continue
        body.append(ln.rstrip())
        if len(body) >= n:
            break
    while body and not body[-1].strip():
        body.pop()
    while body and not body[0].strip():
        body.pop(0)
    return title, body


def classify_file(value, project_folder, repo, app_folder=None, exists=os.path.exists):
    """Where a file par points: {value, resolved, where: repo|td_app|outside, exists}; None for an empty value."""
    v = str(value or '').strip()
    if not v:
        return None
    p = v if os.path.isabs(v) else os.path.join(project_folder or '', v)
    p = os.path.normpath(p)
    where = 'outside'
    if repo and (p == repo or p.startswith(repo.rstrip('/') + '/')):
        where = 'repo'
    elif app_folder and p.startswith(app_folder.rstrip('/') + '/'):
        where = 'td_app'
    return {'value': v, 'resolved': p, 'where': where, 'exists': bool(_try(lambda: exists(p), False))}


def needs_care(f):
    """A file par the .tox cannot bring along: outside the repo and TD's install, or missing."""
    return f.get('where') == 'outside' or not f.get('exists')


def version_for(arg, comp_version, prev):
    """version arg > the COMP's Version par > the previous export's version > 0.1.0."""
    for v in (arg, comp_version, prev):
        if v:
            return str(v)
    return '0.1.0'


def sha256_file(file):
    h = hashlib.sha256()
    with open(file, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read_json(file):
    try:
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _read_text(file):
    try:
        with open(file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''


def write_text(file, text):
    tmp = file + '.part'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, file)


def write_json(file, data):
    write_text(file, json.dumps(data, indent=1, sort_keys=True) + '\n')


def _md(s):
    return str(s if s is not None else '').replace('|', '\\|').replace('\n', ' ')


def readme_text(meta, title, body):
    m = meta
    out = ['# {}'.format(m['name']), '']
    if title:
        out += ['> ' + title, '']
    out += ['v{} - TD {} - exported {} from `{}`'.format(m['version'], m['td_build'], m['created'], m['source'])]
    if body:
        out += [''] + body
    if m.get('doc'):
        out += ['', 'Build doc: `{}`'.format(m['doc'])]
    out += ['', '## Inputs / outputs', '']
    io = m.get('inputs', []) + m.get('outputs', [])
    out += ['- {} `{}` ({}){}'.format('in' if x in m.get('inputs', []) else 'out', x['name'], x['type'],
                                      ' {}x{}'.format(x['width'], x['height']) if x.get('width') else '')
            for x in io] or ['- none']
    out += ['', '## Custom parameters']
    if not m.get('pars'):
        out += ['', 'none']
    for page in m.get('pars', []):
        out += ['', '### ' + page['page'], '', '| name | label | style | default | value |', '|---|---|---|---|---|']
        for p in page['pars']:
            out.append('| {} | {} | {} | {} | {} |'.format(_md(p['name']), _md(p.get('label')), _md(p.get('style')),
                                                         _md(p.get('default')), _md(p.get('value'))))
    perf = m.get('perf') or {}
    out += ['', '## Perf', '', ('cook {} ms (CPU {} / GPU {}) summed over the {} ops that cooked in the last frame at export ({} frames '
                                'after un-park, Out TOP force-cooked each frame; indicative)'.format(perf.get('cook_ms'), perf.get('cpu_ms'), perf.get('gpu_ms'),
                                                              perf.get('ops'), perf.get('frames'))) if perf else 'unknown']
    ext = [f for f in m.get('files', []) if needs_care(f)]
    out += ['', '## Files outside the repo / TD install (or missing)', '']
    out += ['- `{}` {} `{}` ({}{})'.format(f['op'], f['par'], f['value'], f['where'], '' if f['exists'] else ', MISSING')
            for f in ext] or ['- none']
    out += ['', '## Load', '', '`td_library_load {{"name": "{}", "parent": "/project1/lab"}}` (lands parked)'.format(
        m['name']), '']
    return '\n'.join(out)


def scan_index(root):
    items = []
    for n in sorted(_try(lambda: os.listdir(root), []) or []):
        m = read_json(os.path.join(root, n, 'meta.json'))
        if isinstance(m, dict) and m.get('name'):
            items.append({k: m.get(k) for k in ('name', 'version', 'td_build', 'created', 'source', 'size', 'sha256',
                                                'in_git', 'summary', 'thumb')})
            items[-1]['outside_files'] = len([f for f in m.get('files', []) if needs_care(f)])
    return items


def index_md(items):
    out = ['# Component library', '', 'Reusable COMPs exported with `td_library_export`; load one with '
           '`td_library_load {name, parent}`. Regenerated on every export (td/library.py).', '',
           '| COMP | version | TD | size | in git | outside files | summary |', '|---|---|---|---|---|---|---|']
    for i in items:
        out.append('| [{0}]({0}/README.md) | {1} | {2} | {3:.2f} MB | {4} | {5} | {6} |'.format(
            i['name'], i.get('version'), i.get('td_build'), (i.get('size') or 0) / 1048576.0,
            'yes' if i.get('in_git') else 'no (> 5 MB)', i.get('outside_files', 0), _md(i.get('summary') or '')[:120]))
    return '\n'.join(out) + '\n'


def gitignore_lines(text, name, big):
    """library/.gitignore lines after an export of name (big = keep its .tox out of git)."""
    entry = '/{0}/{0}.tox'.format(name)
    lines = [ln for ln in (text or '').splitlines() if ln.strip() and ln.strip() != entry
             and not ln.startswith('#')]
    if big:
        lines.append(entry)
    return [GITIGNORE_HEAD] + sorted(set(lines))


def write_index(root):
    items = scan_index(root)
    write_json(os.path.join(root, 'index.json'), {'format': 'jtd-library', 'v': 1, 'count': len(items),
                                                    'items': items})
    write_text(os.path.join(root, 'INDEX.md'), index_md(items))
    return items


def active_lanes(repo):
    d = read_json(os.path.join(repo, 'logs', 'active_lanes.json'))
    return d if isinstance(d, dict) else {}


def lib_name(name):
    if not G('valid_op_name')(name):
        raise ValueError('bad library name {!r} (letters, digits, _)'.format(name))
    return name


# ================================================================== TD side

def _comp(path):
    c = G('_op')(path)
    if not _try(lambda: c.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(c.path))
    if G('_protected')(c.path):
        raise ValueError('refusing {} (the MCP COMP, its contents or an ancestor)'.format(c.path))
    return c


def first_out_top(c):
    for cn in list(_try(lambda: c.outputConnectors, []) or []):
        o = _try(lambda: cn.outOP)
        if o is not None and _try(lambda: o.OPType, '') == 'outTOP':
            return o
    outs = [o for o in (_try(lambda: list(c.children), []) or []) if _try(lambda: o.OPType, '') == 'outTOP']
    return sorted(outs, key=lambda o: o.name)[0] if outs else None


def _io(c):
    ins, outs = [], []
    for o in sorted(_try(lambda: list(c.children), []) or [], key=lambda o: o.name):
        t = _try(lambda: o.OPType, '')
        m = IO_RE.match(t)
        if not m:
            continue
        d = {'name': o.name, 'type': t}
        if m.group(2) == 'TOP':
            d.update(width=_try(lambda: int(o.width), None), height=_try(lambda: int(o.height), None))
        (ins if m.group(1) == 'in' else outs).append(d)
    return ins, outs


def _plain(v):
    v = G('to_json')(v) if G('to_json') else v
    return v if isinstance(v, (str, int, float, bool)) or v is None else str(v)


def custom_pars(c):
    pages = []
    for pg in list(_try(lambda: c.customPages, []) or []):
        ps = []
        for p in list(_try(lambda: pg.pars, []) or []):
            ps.append({'name': p.name, 'label': _try(lambda: p.label, ''), 'style': _try(lambda: p.style, ''),
                       'default': _plain(_try(lambda: p.default)), 'value': _plain(_try(lambda: p.eval()))})
        pages.append({'page': pg.name, 'pars': ps})
    return pages


def file_pars(c, repo):
    proj = G('project')
    folder = str(_try(lambda: proj.folder, '') or '')
    app_folder = str(_try(lambda: G('app').installFolder, '') or '') or None
    out = []
    for o in [c] + list(_try(lambda: c.findChildren(), []) or []):
        for p in list(_try(lambda: o.pars(), []) or []):
            if _try(lambda: p.style, '') not in ('File', 'Folder'):
                continue
            f = classify_file(_try(lambda: p.eval(), ''), folder, repo, app_folder)
            if f:
                rel = '.' if o is c else o.path[len(c.path) + 1:]
                f.update(op=rel, par=p.name)
                out.append(f)
    return out


def perf_sum(c, frames):
    """Cook ms of the ops that cooked in the latest frame (cookAbsFrame within 1 of the newest, T-102: compare an
    op's cookAbsFrame with its siblings', never with absTime.frame); one-off cooks (help DATs, loads) left out."""
    ops = [o for o in [c] + list(_try(lambda: c.findChildren(), []) or []) if not _try(lambda: o.isCOMP, False)]
    fr = [(_try(lambda: int(o.cookAbsFrame), -1), o) for o in ops]
    ref = max([f for f, _o in fr] or [-1])
    cook = cpu = gpu = 0.0
    n = 0
    for f, o in fr:
        if ref < 0 or f < ref - 1:
            continue
        n += 1
        cook += float(_try(lambda: o.cookTime, 0) or 0)
        cpu += float(_try(lambda: o.cpuCookTime, 0) or 0)
        gpu += float(_try(lambda: o.gpuCookTime, 0) or 0)
    return {'cook_ms': round(cook, 3), 'cpu_ms': round(cpu, 3), 'gpu_ms': round(gpu, 3), 'ops': n, 'frames': frames}


def save_thumb(top, file):
    """PNG of the Out TOP (called >= 3 frames after its force-cook, never in the changing script, T-74)."""
    if top is None:
        return {'ok': False, 'why': 'no Out TOP (or thumb:false)'}
    data = _try(lambda: top.saveByteArray('.png'))
    if data:
        with open(file, 'wb') as f:
            f.write(bytes(data))
    else:
        _try(lambda: top.save(file))
    ok = os.path.isfile(file) and os.path.getsize(file) > 0
    return {'ok': ok, 'top': top.name, 'width': _try(lambda: int(top.width)), 'height': _try(lambda: int(top.height)),
            'bytes': os.path.getsize(file) if ok else 0}


def find_doc(name, doc=None):
    repo = repo_root()
    names = [doc] if doc else doc_candidates(name)
    for n in names:
        rel = n if n.endswith('.md') and '/' in n else os.path.join('docs', 'builds', n if n.endswith('.md') else n + '.md')
        p = os.path.join(repo, rel)
        if os.path.isfile(p):
            with open(p, 'r', encoding='utf-8', errors='replace') as f:
                return rel, f.read()
    if doc:
        return None, ''
    d = os.path.join(repo, 'docs', 'builds')  # else the build doc whose title names the COMP
    for n in sorted(_try(lambda: os.listdir(d), []) or []):
        if n.endswith('.md'):
            text = _read_text(os.path.join(d, n))
            if name in (doc_head(text, 1)[0] or ''):
                return os.path.join('docs', 'builds', n), text
    return None, ''


def write_export(c, name, version, root, out_top, was_parked, frames, doc=None):
    repo = repo_root()
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    tox = os.path.join(d, name + '.tox')
    thumb = save_thumb(out_top, os.path.join(d, 'thumb.png'))
    perf = perf_sum(c, frames)
    prev = read_json(os.path.join(d, 'meta.json')) or {}
    app = G('app')
    ins, outs = _io(c)
    notes = list(_try(lambda: G('_safety')().save_tox(c, tox), None) or [])
    size = os.path.getsize(tox)
    rel_doc, text = find_doc(name, doc)
    title, body = doc_head(text)
    meta = {'name': name, 'source': c.path, 'type': _try(lambda: c.OPType, ''),
            'version': version_for(version, _try(lambda: c.par.Version.eval(), None), prev.get('version')),
            'td_build': G('td_build_string')(_try(lambda: app.version, ''), _try(lambda: app.build, '')),
            'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'inputs': ins, 'outputs': outs, 'pars': custom_pars(c),
            'files': file_pars(c, repo), 'sha256': sha256_file(tox), 'size': size, 'in_git': size <= BIG_TOX,
            'thumb': thumb, 'perf': perf, 'doc': rel_doc, 'summary': title or '',
            'ops': len(_try(lambda: c.findChildren(), []) or []), 'was_parked': was_parked}
    write_json(os.path.join(d, 'meta.json'), meta)
    write_text(os.path.join(d, 'README.md'), readme_text(meta, title, body))
    gi = os.path.join(root, '.gitignore')
    old = _read_text(gi)
    write_text(gi, '\n'.join(gitignore_lines(old, name, size > BIG_TOX)) + '\n')
    items = write_index(root)
    r = {'name': name, 'dir': d, 'tox': tox, 'size': size, 'sha256': meta['sha256'], 'in_git': meta['in_git'],
         'version': meta['version'], 'thumb': thumb, 'perf': perf, 'doc': rel_doc,
         'outside_files': [f for f in meta['files'] if needs_care(f)], 'index': len(items)}
    if notes:
        r['notes'] = notes
    return r


def cmd_library_export(path, name=None, version=None, root=None, frames=30, force=False, doc=None, thumb=True):
    """Export COMP path to library/<name>/: un-park if parked, force-cook its Out TOP 2 frames later, read the
    thumbnail >= 3 frames after that, save .tox + meta + README, re-park, regenerate the index. No Out TOP or
    thumb:false (COMPs with audio/DMX/NDI/MIDI outputs): exported at once, never un-parked, no thumbnail."""
    c = _comp(path)
    name = lib_name(name or c.name)
    root = lib_root(root)
    lane = active_lanes(repo_root()).get(c.path)
    if lane and not force:
        raise ValueError('{} is in logs/active_lanes.json ({}): someone is building it; export it later or '
                         'force:true'.format(c.path, lane.get('agent') if isinstance(lane, dict) else lane))
    frames = max(5, int(frames))
    top = first_out_top(c) if thumb else None
    if top is None:  # nothing to picture (no Out TOP, or thumb:false for a COMP with device outputs): stays as it is
        r = write_export(c, name, version, root, None, None, 0, doc)
        r['reparked'] = False
        return r
    was_parked = not bool(_try(lambda: c.allowCooking, True))
    if was_parked:
        c.allowCooking = True
    Pending = G('Pending')

    def repark():
        if was_parked and _try(lambda: c.valid, True):
            _try(lambda: setattr(c, 'allowCooking', False))

    def read():
        try:
            if not _try(lambda: c.valid, True):
                raise ValueError('{} is gone (destroyed during the export)'.format(path))
            r = write_export(c, name, version, root, top, was_parked, frames, doc)
        finally:
            repark()
        r['reparked'] = was_parked
        return r

    left = {'n': frames - 5}  # force-cook the Out TOP once a frame (media load, sims warm up), then read 3 frames later

    def cook():
        try:
            if top is not None:
                top.cook(force=True)
        except Exception:
            repark()
            raise
        left['n'] -= 1
        return Pending(1, cook) if left['n'] > 0 else Pending(3, read)  # read >= 3 frames after the last cook (T-74)
    return Pending(2, cook)


def cmd_library_list(root=None):
    root = lib_root(root)
    items = scan_index(root)
    return {'root': root, 'count': len(items), 'items': items}


def _entry(name, root):
    name = lib_name(name)
    d = os.path.join(lib_root(root), name)
    meta = read_json(os.path.join(d, 'meta.json'))
    if not isinstance(meta, dict):
        raise ValueError('no library entry {!r} (td_library_list)'.format(name))
    return d, meta


def cmd_library_info(name, root=None):
    d, meta = _entry(name, root)
    tox = os.path.join(d, name + '.tox')
    rd = os.path.join(d, 'README.md')
    readme = _read_text(rd)
    have = os.path.isfile(tox)
    return {'name': name, 'dir': d, 'meta': meta, 'readme': readme, 'tox_present': have,
            'sha_ok': (sha256_file(tox) == meta.get('sha256')) if have else None,
            'thumb': os.path.join(d, 'thumb.png') if os.path.isfile(os.path.join(d, 'thumb.png')) else None}


def cmd_library_load(name, parent, newname=None, root=None, arrange=True):
    """loadTox library/<name>/<name>.tox into parent as newname (default name), parked, viewers on, stage plan
    re-applied."""
    d, meta = _entry(name, root)
    tox = os.path.join(d, name + '.tox')
    if not os.path.isfile(tox):
        raise ValueError('{} is missing (a > 5 MB .tox is kept out of git: re-export it on this machine)'.format(tox))
    par_ = G('_op')(parent, 'parent')
    target = lib_name(newname or name)
    if par_.op(target) is not None:
        raise ValueError('{}/{} exists: pick a newname'.format(par_.path, target))
    sha_ok = sha256_file(tox) == meta.get('sha256')
    o = par_.loadTox(tox)
    o.allowCooking = False  # lands parked: the user (or a builder) turns it on
    o.name = target
    shown = 0
    for x in [o] + list(_try(lambda: list(o.children), []) or []):
        if (G('_family')(x) in G('VIEWER_FAMILIES', ()) + ('COMP',) and _try(lambda: x.OPType, '') != 'annotateCOMP'
                and not _try(lambda: x.viewer, True)):
            _try(lambda: setattr(x, 'viewer', True))
            shown += 1
    staged = None
    if G('_stage_plan')(o):
        staged = _try(lambda: G('restage')(o), None)
    lay = G('_arrange')(par_, arrange)
    notes = [] if sha_ok else ['sha256 differs from meta.json (the .tox changed since the export)']
    missing = [f for f in meta.get('files', []) if not f.get('exists')]
    if missing:
        notes.append('{} file par(s) pointed at missing files at export (meta.json files)'.format(len(missing)))
    r = {'path': o.path, 'file': tox, 'version': meta.get('version'), 'parked': True, 'viewers_on': shown,
         'staged': staged, 'layout': lay, 'sha_ok': sha_ok}
    if notes:
        r['notes'] = notes
    return r
