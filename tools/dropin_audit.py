"""Drop-in audit + fixer for lab COMPs (28 Oct 2026, user: "generally all comps are like that - that i can add it to
different scenes and still have it work"). docs/builds/DROPIN_AUDIT_28OCT.md.

A COMP is a drop-in when its library .tox loaded into ANY COMP of ANY project works: internal references relative,
shared systems optional, scene inputs through OP pars / inputs, copies independent.

In TD (exec; scoped to ONE COMP: never a project-wide scan, T-255; reads p.expr / p.val / text, never p.eval() sweeps):

  ns = dict(globals()); exec(open('<repo>/tools/dropin_audit.py').read(), ns)
  ns['audit'](op('/project1/lab/PX_pointfx'))                  # every absolute / escaping reference, classified
  ns['dropin_fix'](op('/project1/lab/PX_pointfx'), dry=True)    # what the fixer would change
  ns['dropin_fix'](op('/project1/lab/PX_pointfx'), dry=False)   # rewrite class (a) self refs (idempotent)

Classes: self (inside the COMP, or inside the path it was built at: storage/meta `source`) -> made relative;
shared (effectors, AU_features, FG_fps_governor, hotkeys, CQ_cuelist, TL_timeline, CS_cam_sequencer, palette) ->
reported with the Links-page plan; scene (another /project1 op) and unknown -> reported for a hand fix; builtin
(/sys, /ui, /local, TD's own) -> fine. Contexts: code (live), embedded (inside a larger string: an expression a script
writes, a docstring), comment.

Offline (no TD): the pure helpers below are tested by test/test_dropin_audit.py; `python3 tools/dropin_audit.py
scan builders/x.py` lists absolute paths in a builder's text.
"""
import io
import json
import os
import re
import sys
import tokenize

SHARED = ('effectors', 'AU_features', 'FG_fps_governor', 'hotkeys', 'CQ_cuelist', 'TL_timeline', 'CS_cam_sequencer',
          'palette', 'FX_palette_map')
BUILTIN_ROOTS = ('/sys', '/ui', '/local', '/perform')
FS_ROOTS = ('Users', 'Applications', 'System', 'Library', 'Volumes', 'private', 'tmp', 'var', 'usr', 'bin', 'opt',
            'etc', 'dev', 'sbin', 'cores', 'Network', 'home', 'mnt')
TD_GLOBAL_SHORTCUTS = ('TDResources', 'TDTox', 'TDDevices', 'TDBuiltins', 'TDJSON', 'TDFunctions', 'TDStoreTools')
# an op path inside quotes: '/name/name...' (segments may carry %s / {} placeholders: '/project1/lab/%s')
PATH_RE = re.compile(r'''(?P<q>['"])(?P<p>/[A-Za-z_][\w]*(?:/[\w.%{}*-]*)*)(?P=q)''')
PARENT_N_RE = re.compile(r'(?<![\w.])(?:me\.)?parent\((\d+)\)')
REL_UP_RE = re.compile(r'''op\(\s*['"]((?:\.\./)+|\.\.)''')
OPS_SKIP_PARS = ('externaltox', 'file', 'syncfile')


# ================================================================== pure helpers (tested offline)

def clean_path(p):
    """'/project1/lab/%s/x' -> '/project1/lab' (stop at the first placeholder segment); trailing '/' dropped."""
    out = []
    for seg in p.split('/')[1:]:
        if not seg or not re.match(r'^[A-Za-z_][\w.]*$', seg):
            break
        out.append(seg)
    return '/' + '/'.join(out) if out else '/'


def is_fs_path(p):
    seg = p.split('/')[1] if p.count('/') >= 1 else ''
    return seg in FS_ROOTS or '.' in p.split('/')[-1] and not p.startswith('/project')


def under(p, root):
    return bool(root) and (p == root or p.startswith(root.rstrip('/') + '/'))


def classify(path, comp_path, sources=()):
    """-> 'self' | 'shared' | 'scene' | 'builtin' | 'unknown' for an absolute op path seen inside comp_path."""
    p = clean_path(path)
    for root in (comp_path,) + tuple(s for s in sources if s):
        if under(p, root):
            return 'self'
    segs = p.split('/')[1:]
    if any(s in SHARED or s.startswith('palette') for s in segs):
        return 'shared'
    if any(under(p, r) for r in BUILTIN_ROOTS):
        return 'builtin'
    if under(p, '/project1'):
        return 'scene'
    return 'unknown'


def self_root(path, comp_path, sources=()):
    """The root (comp path or a source path) that `path` lies under, or None."""
    p = clean_path(path)
    for root in (comp_path,) + tuple(s for s in sources if s):
        if under(p, root):
            return root
    return None


def rel_inside(path, root):
    """'/C/a/b' under '/C' -> 'a/b' ('' for the root itself)."""
    return path[len(root):].lstrip('/')


def anc_expr(k):
    """Python for the COMP from an op k levels below it (k = depth of `me` inside the COMP)."""
    return 'me' if k <= 0 else ('me.parent()' if k == 1 else 'me.parent(%d)' % k)


def py_strings(text):
    """Python tokens of text -> [(kind, start_offset, end_offset, token_text)] with kind 'string' / 'comment'.
    Raises on text that is not Python."""
    lines = text.splitlines(True)
    starts = [0]
    for ln in lines:
        starts.append(starts[-1] + len(ln))
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            a = starts[tok.start[0] - 1] + tok.start[1]
            b = starts[tok.end[0] - 1] + tok.end[1]
            out.append(('string' if tok.type == tokenize.STRING else 'comment', a, b, tok.string))
    return out


def find_paths(text, python=None):
    """Absolute op paths in quotes inside text -> [{path, start, end, ctx, line}] with ctx 'code' (the whole string
    token is the path), 'embedded' (inside a larger string: an expression text, a docstring), 'comment'. python None =
    try Python tokenize, else plain text (GLSL / JSON / tables): '//' and '#' line comments are 'comment'."""
    if '/' not in text or not PATH_RE.search(text):
        return []                                    # fast path: nothing quoted that looks like an op path
    toks = None
    if python is not False:
        try:
            toks = py_strings(text)
        except Exception:
            toks = None
    out = []
    for m in PATH_RE.finditer(text):
        p = m.group('p')
        if is_fs_path(p):
            continue
        a, b = m.start(), m.end()
        ctx = 'code'
        pre = text[max(0, a - 40):a].rstrip()
        if pre.endswith('+') or pre.endswith('%') or pre.endswith('.join('):
            continue                                 # x.path + '/geo': a suffix of a computed path, not a root path
        if toks is not None:
            hit = next((t for t in toks if t[1] <= a and b <= t[2]), None)
            if hit is None:
                ctx = 'code'
            elif hit[0] == 'comment':
                ctx = 'comment'
            elif not (hit[1] == a and hit[2] == b) and not _plain_prefix_string(hit[3], m.group(0)):
                ctx = 'embedded'
        else:
            ls = text.rfind('\n', 0, a) + 1
            pre = text[ls:a]
            if '//' in pre or pre.lstrip().startswith('#'):
                ctx = 'comment'
        out.append({'path': p, 'start': a, 'end': b, 'ctx': ctx, 'line': text.count('\n', 0, a) + 1})
    return out


def _plain_prefix_string(tok, quoted):
    """A string token like r'/x' or b'/x' or f'/x/{n}' is the path itself (prefix letters only)."""
    t = tok.lstrip('rRbBuUfF')
    return t == quoted


def _op_call_span(text, a, b):
    """If text[a:b] (a quoted path) is the only argument of a bare op(...) call, -> (call_start, call_end)."""
    i = a - 1
    while i >= 0 and text[i] in ' \t':
        i -= 1
    if i < 0 or text[i] != '(':
        return None
    j = i - 1
    while j >= 0 and text[j] in ' \t':
        j -= 1
    if j < 1 or text[j - 1:j + 1] != 'op':
        return None
    s = j - 1
    if s > 0 and (text[s - 1].isalnum() or text[s - 1] in '_.'):
        return None                                  # x.op('...') or myop(...): not the global op()
    k = b
    while k < len(text) and text[k] in ' \t':
        k += 1
    if k >= len(text) or text[k] != ')':
        return None
    return s, k + 1


def rewrite_self(text, comp_path, sources, depth, python=None):
    """Rewrite 'code' self references in text (an expression or a DAT's Python) to forms relative to `me` (depth =
    levels from `me` down to... i.e. me.parent(depth) is the COMP). -> (new_text, [(old, new)]). Idempotent: the
    output has no absolute self path left in code context."""
    hits = [h for h in find_paths(text, python) if h['ctx'] == 'code'
            and self_root(h['path'], comp_path, sources) is not None]
    if not hits:
        return text, []
    anc = anc_expr(depth)
    out, done, pos = [], [], 0
    for h in hits:
        p = h['path']
        root = self_root(p, comp_path, sources)
        if clean_path(p) != p:                       # '/C/%s' or '/C/{x}' style: keep the placeholder tail
            tail = p[len(root):]
            new = "(%s.path + %r)" % (anc, tail) if tail else '%s.path' % anc
            a, b = h['start'], h['end']
        else:
            rel = rel_inside(p, root)
            span = _op_call_span(text, h['start'], h['end'])
            if span is not None:
                a, b = span
                new = anc if not rel else '%s.op(%r)' % (anc, rel)
            else:
                a, b = h['start'], h['end']
                new = '%s.path' % anc if not rel else "(%s.path + %r)" % (anc, '/' + rel)
        if a < pos:
            continue
        out.append(text[pos:a])
        out.append(new)
        done.append((text[a:b], new))
        pos = b
    out.append(text[pos:])
    return ''.join(out), done


IN_CHAN_RE = re.compile(r"""^\s*op\(\s*(['"])([A-Za-z_]\w*)\1\s*\)\s*\[\s*(['"])(\w+)\3\s*\]\s*$""")


def guard_in_chan(expr, in_names, default):
    """op('audio_in')['low'] where audio_in is an In CHOP (nothing wired in a dropped copy: the channel is None,
    float(None) errors) -> the same read, falling back to the par's constant. Other expressions -> None."""
    m = IN_CHAN_RE.match(expr or '')
    if not m or m.group(2) not in set(in_names):
        return None
    try:
        d = float(default)
    except (TypeError, ValueError):
        d = 0.0
    return "(lambda ch: ch.eval() if ch is not None else %r)(op(%r)[%r])" % (d, m.group(2), m.group(4))


def op_par_candidates(targets, owner):
    """Relative values for an OP par on `owner` that should name `targets`, best first: a path below the owner's
    parent (TD resolves most OP pars from the owner's network: a bare name = a sibling, T-244; Window COMP winop),
    then the '.'-based form ('..' = the owner's parent: Parameter Execute op). The caller keeps the first one the
    par itself resolves to the targets."""
    base = owner.rsplit('/', 1)[0]
    a, b = [], []
    for t in targets:
        a.append(t[len(base) + 1:] if t.startswith(base + '/') else rel_op_path(t, owner))
        b.append(rel_op_path(t, owner))
    out = []
    for c in (' '.join(a), ' '.join(b)):
        if c and c not in out:
            out.append(c)
    return out


STALE_FETCH_RE = re.compile(r"(?<!\)\()parent\(\)\.fetch\((['\"])(jz_\w+)\1,\s*-99,\s*search=False\)")


def guard_stale_frames(expr):
    """`absTime.frame - parent().fetch('jz_reset', -99, ...)` in a COMP loaded from another session: the stored frame
    is LATER than now, the difference is negative and `< 3` holds every frame (reset forever). -> the expression with
    such fetches read as -99 when they lie in the future, or None when nothing to change (idempotent)."""
    if 'absTime.frame' not in (expr or '') or 'fetch(' not in expr:
        return None
    out = STALE_FETCH_RE.sub(lambda m: "(lambda k, f: k if k <= f else -99)(parent().fetch(%r, -99, search=False), "
                                       "absTime.frame)" % m.group(2), expr)
    return out if out != expr else None


def rel_op_path(target, owner):
    """Relative OP-par path from owner to target ('.' = owner, '..' = its parent; T-244: './child' for a child)."""
    t = target.rstrip('/').split('/')
    o = owner.rstrip('/').split('/')
    n = 0
    while n < len(t) and n < len(o) and t[n] == o[n]:
        n += 1
    up = len(o) - n
    rest = '/'.join(t[n:])
    if up == 0:
        return './' + rest if rest else '.'
    return '/'.join(['..'] * up) + ('/' + rest if rest else '')


def escapes(text, depth):
    """parent(n) / me.parent(n) / op('../..') in text that climb above the COMP (n > depth) -> [str]."""
    out = []
    if 'parent(' not in text and '..' not in text:
        return out
    for m in PARENT_N_RE.finditer(text):
        if int(m.group(1)) > depth:
            out.append(m.group(0))
    for m in REL_UP_RE.finditer(text):
        ups = m.group(1).count('..')
        if ups > depth:                              # op() in an expression resolves from me's parent: '..' = +1
            out.append(m.group(0))
    return out


def summarize(refs):
    """Counts per class for the live (code) refs; embedded / comment counted apart."""
    s = {'self': 0, 'shared': 0, 'scene': 0, 'unknown': 0, 'builtin': 0, 'escape': 0, 'embedded': 0, 'comment': 0}
    for r in refs:
        if r.get('ctx') == 'comment':
            s['comment'] += 1
        elif r.get('ctx') == 'embedded':
            s['embedded'] += 1
            s[r['cls']] += 0
        else:
            s[r['cls']] += 1
    return s


def links_par_name(system):
    """Links-page OP par name for a shared system: 'effectors' -> 'Linkeffectors', 'AU_features' -> 'Linkaufeatures'."""
    return 'Link' + re.sub(r'[^a-z0-9]', '', system.lower())


def scan_text_file(path):
    with open(path) as fh:
        text = fh.read()
    return [dict(h, text=text.splitlines()[h['line'] - 1].strip()[:140]) for h in find_paths(text)]


# ================================================================== offline: a toeexpand'ed .tox (no TD, T-262)
# `toeexpand X.tox` (TD's own tool, run on a COPY in the scratchpad) writes X.tox.dir/: X.parm (the COMP's pars),
# X/<op>.parm / .text (DAT text) / .table (table cells) / .n (node: type, comment) / .cparm (custom par definitions),
# children of a COMP in a sub-directory of the same name. A .parm line is `name flags value ["expression"]`; flags
# bit 1 = expression / bind mode active, bit 16 = an expression is stored, bit 2 = bind (31550, seen on the library).
SKIP_TABLE_PREFIX = ('zk_ts', 'zk_hs')
TEXT_PARS = ('Bodytext', 'Titletext', 'comment', 'text', 'help', 'label')   # display text (annotations, Text TOPs)
TABLE_PATH_RE = re.compile(r'(?<![\w.])/[A-Za-z_][\w]*(?:/[\w.]+)*')


def parm_tokens(line):
    """'chops 17 "" "op(\'/x\')"' -> ['chops', '17', '', "op('/x')"] (TD quotes with "..." and \" escapes)."""
    out, cur, i, n, inq, have = [], [], 0, len(line), False, False
    while i < n:
        ch = line[i]
        if inq:
            if ch == '\\' and i + 1 < n:
                cur.append(line[i + 1])
                i += 2
                continue
            if ch == '"':
                inq = False
            else:
                cur.append(ch)
        elif ch == '"':
            inq, have = True, True
        elif ch in ' \t':
            if cur or have:
                out.append(''.join(cur))
                cur, have = [], False
        else:
            cur.append(ch)
        i += 1
    if cur or have:
        out.append(''.join(cur))
    return out


def _annotate_dirs(root):
    """Directories that hold an annotate COMP's insides (TD's own network boxes): <dir>/<name>.n says annotateCOMP."""
    out = set()
    for d, _subs, files in os.walk(root):
        for f in files:
            if f.endswith('.n'):
                try:
                    with open(os.path.join(d, f), errors='replace') as fh:
                        head = fh.readline().strip()
                except Exception:
                    continue
                if head.startswith('COMP:annotate'):
                    out.add(os.path.join(d, f[:-2]))
    return out


def offline_audit(expanded_dir, source, name=None, sources=()):
    """Scan X.tox.dir (expanded_dir) of a COMP built at `source` (meta.json): every absolute / escaping reference,
    classified like audit(). -> {name, source, files, summary, refs}."""
    top = None
    if name and os.path.isdir(os.path.join(expanded_dir, name)):
        top = name                                   # one COMP out of a whole expanded project (main .toe copy)
    else:
        for f in os.listdir(expanded_dir):
            if f.endswith('.parm') and os.path.isdir(os.path.join(expanded_dir, f[:-5])):
                top = f[:-5]
    name = name or top
    ann = _annotate_dirs(expanded_dir)
    refs, nfiles = [], 0
    for d, subs, files in os.walk(expanded_dir):
        if any(d == a or d.startswith(a + os.sep) for a in ann):
            subs[:] = []
            continue
        for f in files:
            base, ext = os.path.splitext(f)
            if ext not in ('.parm', '.text', '.table'):
                continue
            full = os.path.join(d, f)
            rel = os.path.relpath(os.path.join(d, base), expanded_dir).replace(os.sep, '/')
            parts = rel.split('/')
            if parts[0] != top:
                continue
            depth = len(parts) - 1
            opn = '/'.join(parts[1:]) or '.'
            nfiles += 1
            try:
                with open(full, errors='replace') as fh:
                    text = fh.read()
            except Exception:
                continue
            if '/' not in text:
                continue

            def add(kind, par, path, ctx='code', cls=None, extra=None):
                r = {'op': '/' + opn if opn != '.' else '.', 'kind': kind, 'par': par, 'path': path,
                     'cls': cls or classify(path, source, tuple(sources)), 'ctx': ctx}
                if extra:
                    r.update(extra)
                refs.append(r)
            if ext == '.parm':
                for line in text.splitlines():
                    tk = parm_tokens(line)
                    if len(tk) < 3 or not tk[1].isdigit():
                        continue
                    nm, fl, rest = tk[0], int(tk[1]), tk[2:]
                    if nm in OPS_SKIP_PARS or nm in TEXT_PARS:
                        continue
                    active = bool(fl & 1)
                    stored = bool(fl & 16) or bool(fl & 2) or (active and len(rest) > 1)
                    val, ex = rest[0], (rest[-1] if len(rest) > 1 else '')
                    if active and ex:
                        kind = 'bind' if fl & 2 else 'expr'
                        for h in find_paths(ex, True):
                            add(kind, nm, h['path'], h['ctx'], extra={'text': ex[:160]})
                        for e in escapes(ex, depth):
                            add(kind, nm, e, 'code', 'escape', {'text': ex[:160]})
                    else:
                        for tok in val.split():
                            if re.match(r'^/[A-Za-z_]', tok) and not is_fs_path(tok):
                                add('const', nm, tok)
                            elif tok.startswith('..') and len(re.findall(r'\.\.', tok)) > depth:
                                add('const', nm, tok, 'code', 'escape')
                        if stored and ex:
                            for h in find_paths(ex, True):
                                add('expr', nm, h['path'], 'inactive', extra={'text': ex[:160]})
            elif ext == '.table':
                if base.startswith(SKIP_TABLE_PREFIX):
                    continue
                try:
                    with open(full, 'rb') as fh:
                        raw = fh.read().decode('latin-1')
                except Exception:
                    continue
                for m in TABLE_PATH_RE.finditer(raw):    # cells are length-prefixed binary strings
                    tok = m.group(0)
                    if not is_fs_path(tok):
                        add('table', base, tok)
            else:
                py = not base.endswith(('_glsl', '_frag', '_vert', '_comp', '_pixel', '_vertex', '_compute'))
                for h in find_paths(text, None if py else False):
                    add('dat', 'line %d' % h['line'], h['path'], h['ctx'])
                if py:
                    for e in escapes(text, depth):
                        add('dat', 'text', e, 'code', 'escape')
    return {'name': name, 'source': source, 'files': nfiles, 'summary': summarize(
        [r for r in refs if r['ctx'] != 'inactive']), 'refs': refs}


def expand_tox(tox, out_dir, toeexpand='/Applications/TouchDesigner 2.app/Contents/MacOS/toeexpand'):
    """Copy tox into out_dir and toeexpand the COPY there (never inside the repo). -> the X.tox.dir path."""
    import shutil
    import subprocess
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, os.path.basename(tox))
    shutil.copyfile(tox, dst)
    d = dst + '.dir'
    if os.path.isdir(d):
        shutil.rmtree(d)
    r = subprocess.run([toeexpand, os.path.basename(dst)], cwd=out_dir, capture_output=True, timeout=300)
    if not os.path.isdir(d):                         # toeexpand exits 1 even when it expanded (31550)
        raise RuntimeError('toeexpand failed on %s: %s' % (dst, (r.stdout + r.stderr)[-300:]))
    return d


# ================================================================== TD side (needs the exec namespace's TD globals)

def _depth(o, comp):
    p, cp = _path(o), _path(comp)
    if p == cp:
        return 0
    if not p.startswith(cp + '/'):
        return None
    return p[len(cp) + 1:].count('/') + 1


def _sources(comp):
    out = []
    for k in ('dropin_source', 'lib_source'):
        try:
            v = comp.fetch(k, None, search=False)
        except Exception:
            v = None
        if v:
            out.append(str(v))
    try:
        v = comp.par.Source.val if getattr(comp.par, 'Source', None) is not None else None
    except Exception:
        v = None
    lab = '/project1/lab/' + re.sub(r'_drop\d*$|\d+$', '', comp.name)
    if lab != comp.path:
        out.append(lab)                              # the lab path the builders used (copies, drops)
    return tuple(dict.fromkeys(out))


SKIP_DAT_PREFIX = ('zk_ts',)
ANNOTATE_CLONE = "op.TDAnnotate.op('annotate', includeUtility=True)"   # TD's own annotate clone expression (31550)                         # zkit text-spec tables: display strings, rebuilt by zkit


def _ops(comp):
    """comp + its children, minus the insides of annotate COMPs (TD's own network boxes) and zkit text specs.
    o.path costs ~0.1 ms per op on 31550 / Rosetta: read once per op, never in an inner loop (a 4171-op COMP took
    ~1 min with a per-annotation path check)."""
    out, ann = [comp], set()
    PATHS.clear()
    PATHS[id(comp)] = comp.path
    for o in comp.findChildren():
        pth = o.path
        par_ = pth.rsplit('/', 1)[0]
        hit = False
        while par_ and len(par_) > len(PATHS[id(comp)]):
            if par_ in ann:
                hit = True
                break
            par_ = par_.rsplit('/', 1)[0]
        if hit:
            continue
        if o.OPType == 'annotateCOMP':
            ann.add(pth)
            continue
        if o.isDAT and o.name.startswith(SKIP_DAT_PREFIX):
            continue
        PATHS[id(o)] = pth
        out.append(o)
    return out


PATHS = {}                                            # id(op) -> path, filled by _ops (one audit / fix at a time)


def _path(o):
    p = PATHS.get(id(o))
    return p if p is not None else o.path


def _is_python_dat(d):
    try:
        lang = d.par.language.eval() if getattr(d.par, 'language', None) is not None else ''
    except Exception:
        lang = ''
    if lang and lang != 'python':
        return False
    if d.OPType in ('glslDAT',) or d.name.endswith(('_glsl', '_frag', '_vert', '_comp', '_pixel', '_vertex')):
        return False
    return None


def audit(comp, sources=None, limit=400):
    """Every absolute / escaping reference inside comp (its pars, its children's pars, DAT texts and tables),
    classified. -> {comp, sources, ops, summary, refs: [{op, kind, par, path, cls, ctx, ...}]}."""
    src = tuple(sources) if sources is not None else _sources(comp)
    refs = []
    ops = _ops(comp)
    cp = comp.path

    def add(o, kind, par, path, ctx='code', extra=None):
        r = {'op': _path(o)[len(cp):] or '.', 'kind': kind, 'par': par, 'path': path,
             'cls': classify(path, cp, src), 'ctx': ctx}
        if extra:
            r.update(extra)
        refs.append(r)

    for o in ops:
        d = _depth(o, comp)
        try:
            pars = o.pars()
        except Exception:
            pars = []
        seen = set()
        for p in pars:
            if id(p) in seen:
                continue
            seen.add(id(p))
            try:
                mode = p.mode
                nm = p.name
            except Exception:
                continue
            if nm in OPS_SKIP_PARS:
                continue
            try:
                if mode == ParMode.EXPRESSION:
                    ex = p.expr or ''
                    for h in find_paths(ex, True):
                        add(o, 'expr', nm, h['path'], h['ctx'], {'text': ex[:160]})
                    for e in escapes(ex, d):
                        add(o, 'expr', nm, e, 'code', {'text': ex[:160], 'cls_force': 'escape'})
                elif mode == ParMode.BIND:
                    ex = p.bindExpr or ''
                    for h in find_paths(ex, True):
                        add(o, 'bind', nm, h['path'], h['ctx'], {'text': ex[:160]})
                    for e in escapes(ex, d):
                        add(o, 'bind', nm, e, 'code', {'text': ex[:160], 'cls_force': 'escape'})
                elif mode == ParMode.CONSTANT:
                    v = p.val
                    if isinstance(v, str) and v.startswith('/') and not is_fs_path(v):
                        for tok in v.split():
                            if tok.startswith('/') and not is_fs_path(tok):
                                add(o, 'oppar' if p.isOP else 'strpar', nm, tok)
                    elif isinstance(v, str) and p.isOP and v.startswith('..'):
                        ups = len(re.findall(r'\.\.', v.split()[0]))
                        if ups > d:
                            add(o, 'oppar', nm, v, 'code', {'cls_force': 'escape'})
            except Exception:
                continue
        if o.isDAT and o is not comp:
            try:
                if o.isTable:
                    for r_ in range(o.numRows):
                        for c_ in range(o.numCols):
                            v = o[r_, c_].val
                            if v.startswith('/') and not is_fs_path(v):
                                for tok in v.split():
                                    if tok.startswith('/') and not is_fs_path(tok):
                                        add(o, 'table', '%d,%d' % (r_, c_), tok)
                    continue
                txt = o.text
            except Exception:
                continue
            if not txt or '/' not in txt:
                continue
            py = _is_python_dat(o)
            for h in find_paths(txt, py):
                add(o, 'dat', 'line %d' % h['line'], h['path'], h['ctx'])
            if py is not False:
                for e in escapes(txt, d):
                    add(o, 'dat', 'text', e, 'code', {'cls_force': 'escape'})
    for r in refs:
        if r.pop('cls_force', None) == 'escape':
            r['cls'] = 'escape'
    s = summarize(refs)
    live = [r for r in refs if r['ctx'] == 'code' and r['cls'] != 'builtin']
    return {'comp': cp, 'sources': list(src), 'ops': len(ops), 'summary': s,
            'refs': (live + [r for r in refs if r not in live])[:limit], 'refs_total': len(refs)}


def dropin_fix(comp, dry=True, sources=None, report=True):
    """Class (a) self references -> relative forms (idempotent, UI-safe: no op created / destroyed, no pane or
    viewer touched, values kept: only expression texts, OP-par paths and DAT texts that point inside the COMP change,
    each to a form that resolves to the same op). Shared / scene / unknown refs are reported (shared with the Links
    par a hand fix should read). dry=True only reports. -> {changed: [...], skipped: [...], report: {...}}."""
    import time as _t
    t0 = _t.perf_counter()
    src = tuple(sources) if sources is not None else _sources(comp)
    cp = comp.path
    changed, skipped = [], []
    in_cache = {}
    for o in _ops(comp):
        d = _depth(o, comp)
        try:
            pars = o.pars()
        except Exception:
            pars = []
        seen = set()
        for p in pars:
            if id(p) in seen:
                continue
            seen.add(id(p))
            try:
                mode, nm = p.mode, p.name
            except Exception:
                continue
            if nm in OPS_SKIP_PARS:
                continue
            try:
                if mode == ParMode.EXPRESSION and o.parent() is not None and IN_CHAN_RE.match(p.expr or ''):
                    pk = o.parent().path
                    if pk not in in_cache:
                        in_cache[pk] = [x.name for x in o.parent().children if x.OPType == 'inCHOP']
                    ins = in_cache[pk]
                    g = guard_in_chan(p.expr, ins, p.val) if ins else None
                    if g:
                        changed.append({'op': _path(o)[len(cp):] or '.', 'par': nm, 'kind': 'in_guard', 'old': p.expr,
                                        'new': g})
                        if not dry:
                            p.expr = g
                        continue
                if mode == ParMode.EXPRESSION:
                    g = guard_stale_frames(p.expr)
                    if g:
                        changed.append({'op': _path(o)[len(cp):] or '.', 'par': nm, 'kind': 'stale_frame',
                                        'old': p.expr, 'new': g})
                        if not dry:
                            p.expr = g
                if mode in (ParMode.EXPRESSION, ParMode.BIND):
                    ex = (p.expr if mode == ParMode.EXPRESSION else p.bindExpr) or ''
                    new, done = rewrite_self(ex, cp, src, d, True)
                    if done:
                        changed.append({'op': _path(o)[len(cp):] or '.', 'par': nm, 'kind': 'expr', 'old': ex[:200],
                                        'new': new[:200]})
                        if not dry:
                            if mode == ParMode.EXPRESSION:
                                p.expr = new
                            else:
                                p.bindExpr = new
                elif mode == ParMode.CONSTANT:
                    v = p.val
                    if not (isinstance(v, str) and v.startswith('/')) or is_fs_path(v):
                        continue
                    toks = v.split()
                    if not any(self_root(t, cp, src) for t in toks):
                        continue
                    if p.isOP and o.OPType == 'windowCOMP' and getattr(o, 'isOpen', False):
                        skipped.append({'op': _path(o)[len(cp):], 'par': nm, 'kind': 'oppar', 'old': v,
                                        'why': 'window is open: close it, then run again (T-70)'})
                        continue
                    if p.isOP:
                        want = [cp + t[len(self_root(t, cp, src)):] if self_root(t, cp, src) else t for t in toks]
                        opath = _path(o)
                        cands = op_par_candidates(want, opath)
                        rec = {'op': opath[len(cp):] or '.', 'par': nm, 'kind': 'oppar', 'old': v, 'new': cands[0]}
                        if not dry:
                            ok = None
                            for cand in cands:          # TD resolves OP pars per par type: check the par itself
                                p.val = cand
                                if _eval_paths(p) == want:
                                    ok = cand
                                    break
                            if ok is None:
                                p.val = v
                                rec['reverted'] = 'no relative form resolved to %s' % want
                                skipped.append(rec)
                                continue
                            rec['new'] = ok
                        changed.append(rec)
                    else:
                        root = self_root(toks[0], cp, src)
                        if len(toks) != 1 or root is None or p.readOnly:
                            skipped.append({'op': _path(o)[len(cp):] or '.', 'par': nm, 'kind': 'strpar', 'old': v,
                                            'why': 'several paths / read only: hand fix'})
                            continue
                        rel = rel_inside(clean_path(v), root) + v[len(clean_path(v)):]
                        ex = '%s.path' % anc_expr(d) if not rel else '%s.path + %r' % (anc_expr(d), '/' + rel)
                        changed.append({'op': _path(o)[len(cp):] or '.', 'par': nm, 'kind': 'strpar', 'old': v,
                                        'new': '= ' + ex})
                        if not dry:
                            p.expr = ex
                            p.mode = ParMode.EXPRESSION
            except Exception as e:
                skipped.append({'op': _path(o)[len(cp):] or '.', 'par': getattr(p, 'name', '?'),
                                'why': '%s: %s' % (type(e).__name__, e)})
        if o.isDAT and o.name == 'vc_slots' and getattr(o, 'isTable', False) and o.parent() is comp:
            for r_ in range(1, o.numRows):                # MX vertex cache: read by op(cell) from DATs in the COMP
                for k_ in range(o.numCols):
                    v_ = o[r_, k_].val
                    root = self_root(v_, cp, src) if v_.startswith('/') else None
                    if root is not None and v_ != root:
                        new_ = v_[len(root) + 1:]
                        changed.append({'op': '/vc_slots', 'par': '%d,%d' % (r_, k_), 'kind': 'table', 'old': v_,
                                        'new': new_})
                        if not dry:
                            o[r_, k_] = new_
            continue
        if o.isDAT and o is not comp and o.name == 'zk_cfg' and getattr(o, 'isTable', False):
            _fix_zk_cfg(o, comp, cp, src, dry, changed, skipped)
            continue
        if o.isDAT and o is not comp:
            try:
                if o.isTable:
                    continue
                txt = o.text
            except Exception:
                continue
            if not txt or '/' not in txt:
                continue
            py = _is_python_dat(o)
            if py is False:
                continue
            try:
                new, done = rewrite_self(txt, cp, src, d, True)
            except Exception as e:
                skipped.append({'op': _path(o)[len(cp):], 'kind': 'dat', 'why': '%s: %s' % (type(e).__name__, e)})
                continue
            if done:
                changed.append({'op': _path(o)[len(cp):], 'kind': 'dat', 'edits': done[:20], 'n': len(done)})
                if not dry:
                    try:
                        if o.par.file.eval() and getattr(o.par, 'syncfile', None) is not None and o.par.syncfile.eval():
                            skipped.append({'op': _path(o)[len(cp):], 'kind': 'dat', 'why': 'synced to a file'})
                            changed.pop()
                            continue
                    except Exception:
                        pass
                    o.text = new
    # a check routine's freeze() left the demo clip paused and Input on 'test' (FX_track exported like that: black
    # first frame in every copy) -> playing again, Input auto. Only these two values, only when both say frozen.
    for tc in comp.findChildren(name='test_clip', maxDepth=1):
        try:
            inp = getattr(comp.par, 'Input', None)
            if (tc.OPType == 'moviefileinTOP' and tc.par.play.mode == ParMode.CONSTANT and not tc.par.play.eval()
                    and inp is not None and inp.eval() == 'test' and 'auto' in inp.menuNames):
                changed.append({'op': tc.path[len(cp):], 'par': 'play', 'kind': 'frozen_clip', 'new': 'on; Input auto'})
                if not dry:                           # GEN_sdf pauses its clip on purpose (no Input par): untouched
                    tc.par.play = True
                    inp.val = 'auto'
        except Exception as e:
            skipped.append({'op': '/test_clip', 'kind': 'frozen_clip', 'why': str(e)})
    # annotate boxes whose clone par was blanked (TL_timeline's panel boxes): AnnotateExt.__init__ reads
    # par.clone.eval().par.Version and dies, so the box errors in every copy -> TD's own clone expression back
    for a in comp.findChildren(type=annotateCOMP, maxDepth=4):
        try:
            q = a.par.clone
            if q.mode == ParMode.CONSTANT and not q.val:
                rec = {'op': a.path[len(cp):], 'par': 'clone', 'kind': 'annotate_clone', 'new': '= ' + ANNOTATE_CLONE}
                changed.append(rec)
                if not dry:                           # as builders/timeline.py repair_annotates (T-165)
                    q.expr = ANNOTATE_CLONE
                    q.mode = ParMode.EXPRESSION
                    a.initializeExtensions()
        except Exception as e:
            skipped.append({'op': a.path[len(cp):], 'kind': 'annotate_clone', 'why': str(e)})
    t1 = _t.perf_counter()
    if not report:                                   # main: keep the frame short; re-audit in its own exec
        return {'comp': cp, 'dry': dry, 'ms': {'fix': round((t1 - t0) * 1000)}, 'changed': changed,
                'skipped': skipped}
    rep = audit(comp, src)
    t2 = _t.perf_counter()
    left = [r for r in rep['refs'] if r['ctx'] == 'code' and r['cls'] in ('shared', 'scene', 'unknown', 'escape')]
    for r in left:
        if r['cls'] == 'shared':
            sysname = next((s for s in clean_path(r['path']).split('/') if s in SHARED or s.startswith('palette')), '')
            r['links_par'] = links_par_name(sysname)
    return {'comp': cp, 'dry': dry, 'ms': {'fix': round((t1 - t0) * 1000), 'audit': round((t2 - t1) * 1000)},
            'changed': changed, 'skipped': skipped, 'summary_after': rep['summary'],
            'hand_fix': left[:200], 'self_left': [r for r in rep['refs'] if r['cls'] == 'self'][:50]}


def _fix_zk_cfg(t, comp, cp, src, dry, changed, skipped):
    """zkit panel target -> '..' per level, only when the panel's zk_rt resolves relative targets (zkit after
    28 Oct: P.op(v)); an older panel is reported (zkit refresh_panel rewrites runtime + target together)."""
    cell = t['target', 1]
    if cell is None or not cell.val.startswith('/') or self_root(cell.val, cp, src) is None:
        return
    panel = t.parent()
    rt = panel.op('zk_rt')
    rec = {'op': t.path[len(cp):], 'kind': 'zk_cfg', 'old': cell.val}
    if rt is None or 'P.op(v)' not in rt.text:
        rec['why'] = 'panel runtime predates relative targets: zkit refresh_panel'
        skipped.append(rec)
        return
    depth = len(panel.path[len(cp) + 1:].split('/')) if panel.path.startswith(cp + '/') else 0
    want = cp + cell.val[len(self_root(cell.val, cp, src)):]
    new = '/'.join(['..'] * depth) if want == cp else rel_op_path(want, panel.path)
    rec['new'] = new
    if not dry:
        old = cell.val
        t['target', 1] = new
        x = panel.op(new)
        if x is None or x.path != want:
            t['target', 1] = old
            rec['reverted'] = 'resolved %s' % (x.path if x is not None else None)
            skipped.append(rec)
            return
        try:
            rt.module.S['host'] = None                 # the panel re-resolves its host
        except Exception:
            pass
    changed.append(rec)


REPO = os.path.dirname(os.path.dirname(os.path.abspath(THIS_FILE))) if 'THIS_FILE' in globals() and THIS_FILE else \
    '~/Documents/StageLab_PrismFest/jazib-td-mcp'
# sha1 of the runtime texts as they were before the 28 Oct drop-in changes (main .1394 + the library hold these):
# a text is synced from builders/ only when it is exactly this, so nothing else a lane changed is overwritten.
PRE_DROPIN_SHA = {
    'urdu_rt': 'f755349575dc855f9eaa336fb1312fe8eb97a410',
    'fluid2d_logic': '500e6bbc532bfc973b8ebad5cfd0b4c1bd8cd571',
    'engine_callbacks': 'c284c2abfd262c0f32abc9f4b6ada23e8ca548fc',
}


def _sha(t):
    import hashlib
    return hashlib.sha1(t.encode()).hexdigest()


def _builder_ns(name):
    ns = dict(globals())
    ns['__name__'] = 'jtd_builder_' + name
    exec(open(os.path.join(REPO, 'builders', name)).read(), ns)
    return ns


def dropin_main(comp, dry=True):
    """One COMP on main (or anywhere): dropin_fix (report off: short frame) + the COMP's own drop-in extras, each
    guarded and idempotent. dry=True lists what would change. Re-audit in a LATER exec: audit(comp)['summary'].
    Extras: BJ_urdu_type urdu_rt (re-anchors a stale start time), BN_fluid2d idle Status + texts, POP_meshwarp demo
    input, FX_film dof Depthop. PX_pointfx*: px_rt goes through px.presetsrc_upgrade (staged, UI-safe), not here."""
    out = {'comp': _path(comp) if id(comp) in PATHS else comp.path, 'dry': dry, 'extras': [], 'notes': []}
    r = dropin_fix(comp, dry=dry, report=False)
    out['fix'] = {'ms': r['ms'], 'changed': [(x.get('op'), x.get('par'), x['kind'], str(x.get('new', ''))[:60])
                                             for x in r['changed']],
                  'skipped': [(x.get('op'), x.get('why') or x.get('reverted')) for x in r['skipped']]}
    d = comp.op('urdu_rt')
    if d is not None:
        new = open(os.path.join(REPO, 'builders', 'urdu_type_rt.py')).read()
        if d.text != new:
            if _sha(d.text) == PRE_DROPIN_SHA['urdu_rt']:
                out['extras'].append('urdu_rt <- builders/urdu_type_rt.py')
                if not dry:
                    d.text = new
            else:
                out['notes'].append('urdu_rt differs from the pre-drop-in text: not synced (check by hand)')
    if comp.op('engine_callbacks') is not None and comp.op('fluid2d_logic') is not None:
        shas = (_sha(comp.op('fluid2d_logic').text), _sha(comp.op('engine_callbacks').text))
        b = _builder_ns('fluid2d.py')
        new = (open(os.path.join(REPO, 'builders', 'fluid2d_logic.py')).read(), b['ENGINE_CB'])
        ok = all(t == n or s_ == PRE_DROPIN_SHA[k] for t, n, s_, k in zip(
            (comp.op('fluid2d_logic').text, comp.op('engine_callbacks').text), new, shas,
            ('fluid2d_logic', 'engine_callbacks')))
        if not ok:
            out['notes'].append('BN_fluid2d texts differ from the pre-drop-in versions: idle_upgrade skipped')
        elif dry:
            out['extras'].append('fluid idle_upgrade (Status + texts)')
        else:
            out['extras'].append('fluid idle_upgrade: %s' % b['idle_upgrade'](comp))
    if comp.op('sheet') is not None and comp.op('mat') is not None and comp.op('in1') is not None \
            and comp.op('img_src') is None and comp.name.startswith('POP_meshwarp'):
        out['extras'].append('meshwarp demo_upgrade')
        if not dry:
            out['extras'][-1] += ': %s' % _builder_ns('pop_meshwarp.py')['demo_upgrade'](comp)
    if comp.findChildren(name='depth_sel', maxDepth=2):
        b = _builder_ns('fx_film_dof.py')
        if dry:
            n = sum(1 for ds in comp.findChildren(name='depth_sel', maxDepth=2)
                    if getattr(ds.parent().par, 'Depthop', None) is None)
            if n:
                out['extras'].append('dof depthop_upgrade (%d module(s))' % n)
        else:
            done = b['depthop_upgrade'](comp)
            if done:
                out['extras'].append('dof depthop_upgrade: %s' % done)
    if comp.op('px_rt') is not None:
        out['notes'].append('PX: px_rt drop-in fallbacks come with px.presetsrc_upgrade (rerun it; changed [px_rt])')
    return out


def _eval_paths(p):
    """The op path(s) an OP par resolves to now (one targeted eval, not a sweep, T-255)."""
    try:
        v = p.eval()
    except Exception:
        return None
    if v is None:
        return [None]
    if isinstance(v, (list, tuple)):
        return [x.path if x is not None else None for x in v]
    return [v.path] if hasattr(v, 'path') else [None]


def _resolve_tokens(o, val):
    out = []
    for t in val.split():
        x = None
        try:
            x = o.op(t) if t.startswith('.') else o.parent().op(t)
        except Exception:
            x = None
        out.append(x.path if x is not None else None)
    return out


# ---- live drop-in test steps (one per exec, a few frames apart; T-252 / T-254: parked on load, no viewers) ----
DROP_ROOT = '/project1/dropin'


def drop_load(tox, n, name, source=None):
    """Step 1: /project1/dropin/host_<n> (Base COMP) + loadTox under '<name>_drop', parked in the same exec."""
    root = op(DROP_ROOT)
    if root is None:
        root = op('/project1').create(baseCOMP, 'dropin')
        root.viewer = False
    h = root.op('host_%d' % n)
    if h is None:
        h = root.create(baseCOMP, 'host_%d' % n)
        h.viewer = False
    o = h.loadTox(tox)
    o.allowCooking = False
    o.viewer = False
    o.name = name + '_drop'
    o.store('dropin_source', source or '/project1/lab/' + name)
    for x in list(o.children):
        try:
            x.viewer = False
        except Exception:
            pass
    return {'path': o.path, 'parked': True}


def drop_unpark(path):
    o = op(path)
    o.allowCooking = True
    o.store('dropin_t0', absTime.frame)
    return {'path': path, 'frame': absTime.frame}


def _first_out(o):
    outs = [x for x in o.children if x.OPType == 'outTOP']
    outs.sort(key=lambda x: (x.name != 'out1', x.name))
    return outs[0] if outs else None


def drop_read(path, sources=None):
    """Step 3 (>= 60 frames after the un-park): errors / warnings, Status, main Out TOP size (not read back: the
    caller checks black in a LATER exec with drop_pixels, T-74), the audit summary."""
    o = op(path)
    errs, warns = [], []
    for x in [o] + list(o.findChildren()):
        try:
            e = x.errors()
            w = x.warnings()
        except Exception:
            continue
        if e:
            errs.append((x.path[len(path):] or '.', e[:160]))
        if w:
            warns.append((x.path[len(path):] or '.', w[:160]))
    st = None
    try:
        st = o.par.Status.val if getattr(o.par, 'Status', None) is not None else None
    except Exception:
        pass
    out = _first_out(o)
    a = audit(o, sources)
    return {'path': path, 'frames': absTime.frame - int(o.fetch('dropin_t0', absTime.frame, search=False)),
            'errors': errs[:12], 'n_errors': len(errs), 'warnings': warns[:8], 'n_warnings': len(warns),
            'status': st, 'out': out.name if out else None,
            'out_res': (out.width, out.height) if out else None, 'summary': a['summary'],
            'refs': [r for r in a['refs'] if r['ctx'] == 'code' and r['cls'] != 'builtin'][:60]}


def drop_pixels(path):
    """Step 4 (a later exec than any change, T-74): is the main Out TOP non-black? (numpy of a small copy)"""
    o = op(path)
    out = _first_out(o)
    if out is None:
        return {'path': path, 'out': None}
    try:
        a = out.numpyArray(delayed=False)
    except Exception as e:
        return {'path': path, 'out': out.name, 'error': str(e)}
    if a is None:
        return {'path': path, 'out': out.name, 'pixels': None}
    rgb = a[..., :3]
    return {'path': path, 'out': out.name, 'max': float(rgb.max()), 'mean': float(rgb.mean()),
            'nonblack': bool(rgb.max() > 0.004), 'shape': list(a.shape)}


def cook_for(path, n=60, tool=None):
    """Force-cook path's main Out TOP once a frame for n frames (a parked-host Out nobody views never cooks); the
    chain runs after this exec, one run() per frame. Read the result >= 3 frames after the last cook (T-74)."""
    o = op(path)
    out = _first_out(o) if o is not None else None
    if out is None:
        return {'path': path, 'out': None}
    out.cook(force=True)
    if n > 1 and tool and o.allowCooking:
        run("ns = dict(globals()); exec(open(%r).read(), ns); ns['cook_for'](%r, %d, %r)" % (tool, path, n - 1, tool),
            delayFrames=1, delayRef=op.TDResources)
    return {'path': path, 'out': out.name, 'left': n - 1}


def drop_park(path):
    o = op(path)
    o.allowCooking = False
    return {'path': path, 'parked': True}


def drop_destroy(n):
    """Last step, a later exec after drop_park (pane on /local on side TDs, T-252): destroy host_<n>."""
    h = op(DROP_ROOT + '/host_%d' % n)
    if h is None:
        return {'host': n, 'gone': True}
    h.destroy()
    return {'host': n, 'destroyed': True}


# ---- whole-library queue (one kickoff exec; steps chained inside TD with run(), results appended to a JSON file) --
THIS_FILE = os.path.abspath(__file__) if '__file__' in globals() else None
Q_WAIT_LOAD = 600          # frames parked after loadTox before the un-park (T-254: >= 10 s)
Q_COOK = 60                # frames cooked (Out force-cooked each frame) before the read
Q_GAP = 30                 # frames between the other steps


def _later(step, delay):
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['q_step'](%r)" % (QFILE_TD[0], step),
        delayFrames=max(1, int(delay)), delayRef=op.TDResources)


QFILE_TD = [None]


def _qstate():
    r = op(DROP_ROOT)
    return r.fetch('dropin_q', None, search=False) if r is not None else None


def _qsave(st):
    op(DROP_ROOT).store('dropin_q', st)


def _qwrite(st, rec):
    try:
        with open(st['out'], 'a') as fh:
            fh.write(json.dumps(rec, default=str) + '\n')
    except Exception:
        pass


def q_start(items, out_file, tool_file, start_n=1):
    """items = [{name, tox, source, mode: 'live' | 'static', keep: bool}] -> runs them one after another. mode
    static = load + audit only (devices: audio / DMX / MIDI / camera / network are never cooked); keep = park and
    leave the host (PX-sized COMPs: a destroy crashed b3, T-254)."""
    root = op(DROP_ROOT)
    if root is None:
        root = op('/project1').create(baseCOMP, 'dropin')
        root.viewer = False
    st = {'items': items, 'i': 0, 'n0': int(start_n), 'out': out_file, 'tool': tool_file, 'state': 'running',
          'step': 'load', 'cook_left': 0, 'started': absTime.frame}
    _qsave(st)
    QFILE_TD[0] = tool_file
    _later('load', 2)
    return {'queued': len(items), 'out': out_file}


def q_stop():
    st = _qstate()
    if st:
        st['state'] = 'stopped'
        _qsave(st)
    return st and {'stopped_at': st['i']}


def q_status():
    st = _qstate()
    if not st:
        return None
    return {k: st.get(k) for k in ('i', 'state', 'step', 'current')} | {'n': len(st['items'])}


def q_step(step):
    st = _qstate()
    QFILE_TD[0] = (st or {}).get('tool') or QFILE_TD[0]
    if not st or st.get('state') != 'running':
        return
    if st['i'] >= len(st['items']):
        st['state'] = 'done'
        _qsave(st)
        return
    it = st['items'][st['i']]
    n = st['n0'] + st['i']
    nxt, delay = None, Q_GAP
    try:
        if step == 'load':
            r = drop_load(it['tox'], n, it['name'], it.get('source'))
            st['current'] = r['path']
            st['rec'] = {'name': it['name'], 'n': n, 'path': r['path'], 'mode': it.get('mode', 'live'),
                         't_load': absTime.frame}
            if it.get('mode') == 'static':
                nxt, delay = 'read', Q_GAP
            else:
                nxt, delay = 'unpark', Q_WAIT_LOAD
        elif step == 'unpark':
            drop_unpark(st['current'])
            st['cook_left'] = Q_COOK
            nxt, delay = 'cook', 1
        elif step == 'cook':
            o = op(st['current'])
            out = _first_out(o) if o is not None else None
            if out is not None:
                out.cook(force=True)
            st['cook_left'] -= 1
            nxt, delay = ('cook', 1) if st['cook_left'] > 0 else ('read', 3)
        elif step == 'read':
            st['rec']['read'] = drop_read(st['current'], it.get('sources'))
            nxt, delay = ('pixels', 3) if it.get('mode') != 'static' else ('park', 2)
        elif step == 'pixels':
            st['rec']['pixels'] = drop_pixels(st['current'])
            nxt, delay = 'park', 2
        elif step == 'park':
            drop_park(st['current'])
            nxt, delay = ('destroy', 60) if not it.get('keep') else ('next', 2)
        elif step == 'destroy':
            st['rec']['destroy'] = drop_destroy(n)
            nxt, delay = 'next', Q_GAP
        elif step == 'next':
            st['rec']['t_end'] = absTime.frame
            _qwrite(st, st['rec'])
            st['i'] += 1
            st['rec'] = None
            nxt, delay = 'load', Q_GAP
    except Exception as e:
        rec = st.get('rec') or {'name': it['name'], 'n': n}
        rec.setdefault('fail', []).append('%s at %s: %s' % (type(e).__name__, step, e))
        st['rec'] = rec
        try:
            if st.get('current') and op(st['current']) is not None:
                op(st['current']).allowCooking = False
        except Exception:
            pass
        if step == 'next':
            st['i'] += 1
            nxt, delay = 'load', Q_GAP
        else:
            nxt, delay = 'next', 2
    st['step'] = nxt
    _qsave(st)
    if nxt:
        _later(nxt, delay)


if __name__ == '__main__' and 'ParMode' not in globals():
    if len(sys.argv) >= 4 and sys.argv[1] == 'library':
        # python3 tools/dropin_audit.py library <library dir> <scratch out dir> [names...] -> <out>/offline.json
        lib, outd = sys.argv[2], sys.argv[3]
        names = sys.argv[4:] or sorted(n for n in os.listdir(lib) if os.path.isfile(os.path.join(lib, n, 'meta.json')))
        res = []
        for n in names:
            toxes = [f for f in os.listdir(os.path.join(lib, n)) if f.endswith('.tox')]
            if not toxes:
                continue
            meta = json.load(open(os.path.join(lib, n, 'meta.json')))
            d = expand_tox(os.path.join(lib, n, toxes[0]), os.path.join(outd, n))
            r = offline_audit(d, meta.get('source') or '/project1/lab/' + n, n)
            res.append(r)
            print('%-24s files %4d  %s' % (n, r['files'], r['summary']))
        with open(os.path.join(outd, 'offline.json'), 'w') as fh:
            json.dump(res, fh, indent=0)
    elif len(sys.argv) >= 3 and sys.argv[1] == 'scan':
        for f in sys.argv[2:]:
            for h in scan_text_file(f):
                print('%s:%d [%s] %s  | %s' % (f, h['line'], h['ctx'], h['path'], h['text']))
    else:
        print(__doc__)


def profile_audit(comp, budget_s=20.0):
    """Where does audit() spend its time? Per op: par loop ms, DAT text ms (text length); stops after budget_s.
    -> {done, ops, slow: [(op, kind, ms, size)]}."""
    import time as _t
    t_end = _t.perf_counter() + budget_s
    src = _sources(comp)
    out, n = [], 0
    for o in _ops(comp):
        if _t.perf_counter() > t_end:
            return {'done': False, 'ops': n, 'slow': sorted(out, key=lambda x: -x[2])[:12]}
        n += 1
        t0 = _t.perf_counter()
        d = _depth(o, comp)
        for p in o.pars():
            try:
                if p.mode == ParMode.EXPRESSION:
                    find_paths(p.expr or '', True)
                    escapes(p.expr or '', d)
                elif p.mode == ParMode.CONSTANT:
                    v = p.val
            except Exception:
                pass
        t1 = _t.perf_counter()
        out.append((_path(o)[len(comp.path):], 'pars', round((t1 - t0) * 1000, 1), len(o.pars())))
        if o.isDAT and o is not comp and not getattr(o, 'isTable', False):
            try:
                txt = o.text
            except Exception:
                txt = ''
            t2 = _t.perf_counter()
            find_paths(txt, _is_python_dat(o))
            out.append((_path(o)[len(comp.path):], 'text', round((_t.perf_counter() - t2) * 1000, 1), len(txt)))
    return {'done': True, 'ops': n, 'slow': sorted(out, key=lambda x: -x[2])[:12],
            'total_ms': round(sum(x[2] for x in out))}
