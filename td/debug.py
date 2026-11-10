"""Jazib MCP for TouchDesigner -- debug / analysis toolkit (contract: docs/PROTOCOL.md "Debug toolkit").

Commands (registered by td/handlers.py): analyze, why, watch, debug_panel_build.

Loading: td/handlers.py reads THIS FILE from the folder of handlers.py and execs it into a fresh module object
(handlers._debug()); it is re-read whenever its mtime changes, so editing td/debug.py needs neither td_reload nor a
reinstall, and nothing is written into /jazib_mcp. Before every command handlers calls bind(globals()): this module
never imports td itself, it reaches TD (op, absTime, project, app, ui, run, td) and the handlers helpers (Pending,
safe_destroy, layout_stages, _plan_pars, cmd_custom_pars, ...) through the dict H. That keeps it testable with a fake H
and keeps the merge surface in handlers.py to a few lines.

Outside TD the same file is the read-only helper behind td_analyze_file (never executes project code):
    python3 -I td/debug.py analyze-expanded <x.toe.dir> [--root /] [--depth 99] [--packages] [--ops-dir DIR]
reads the text files TD's toeexpand wrote (.n, .parm, .text) and prints the same JSON summary as `analyze`.

Rules kept: read-only except debug_panel_build (one undo step); bounded (limits, caps, paging); big scans are cut into
frame-sized chunks with the Pending pattern so TD never freezes; T-70 (panels are refilled in place, safe_destroy);
T-67 (no functions in storage); pure ASCII.
"""
import json
import math
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(globals().get('__file__') or os.path.join('.', 'debug.py')))  # td/
H = {}  # handlers' globals, set by bind() before every command (tests pass a fake dict)


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


# ================================================================== tables (TD 2025.31550 par names; td_help data)

FAMILIES = ('TOP', 'CHOP', 'SOP', 'DAT', 'COMP', 'MAT', 'POP')
REF_STYLES = frozenset(('OP', 'COMP', 'TOP', 'CHOP', 'SOP', 'DAT', 'MAT', 'OBJ', 'PanelCOMP', 'Object', 'POP'))
FILE_STYLES = frozenset(('File', 'FileSave', 'Folder'))
SHORTCUT_PARS = ('opshortcut', 'parentshortcut', 'iopshortcut')
EXT_PAR_RE = re.compile(r'^(ext\d+(object|name|promote)|extension\d+|extname\d+|promoteextension\d+)$')
COOK_ALWAYS_PARS = ('cookalways', 'alwayscook')
PACKAGE_PARS = ('clone', 'externaltox', 'enableexternaltox')
# Execute-family DATs: their trigger toggles, and the par naming what they watch.
EXEC_TYPES = {
    'executeDAT': ('start', 'create', 'exit', 'framestart', 'frameend', 'playstatechange', 'devicechange',
                   'projectpresave', 'projectpostsave'),
    'parameterexecuteDAT': ('valuechange', 'valueschanged', 'onpulse', 'expressionchange', 'exportchange',
                            'enablechange', 'modechange'),
    'panelexecuteDAT': ('offtoon', 'whileon', 'ontooff', 'whileoff', 'valuechange'),
    'chopexecuteDAT': ('offtoon', 'whileon', 'ontooff', 'whileoff', 'valuechange'),
    'datexecuteDAT': ('tablechange', 'rowchange', 'colchange', 'cellchange', 'sizechange'),
    'opexecuteDAT': ('precook', 'postcook', 'destroy', 'flagchange', 'wirechange', 'namechange', 'pathchange',
                     'uichange', 'numchildrenchange', 'childrename', 'currentchildchange', 'extensionchange'),
}
EXEC_WATCH = {'parameterexecuteDAT': 'op', 'panelexecuteDAT': 'panels', 'chopexecuteDAT': 'chop',
              'datexecuteDAT': 'dat', 'opexecuteDAT': 'op'}
SCRIPT_TYPES = ('scriptTOP', 'scriptCHOP', 'scriptSOP', 'scriptDAT', 'scriptPOP')
# Devices + ports: type -> (kind, settings pars). Par names from TD's shipped param help (td_help, 31550).
DEVICES = {
    'oscinCHOP': ('OSC in', ('port', 'localaddress', 'protocol')),
    'oscinDAT': ('OSC in', ('port', 'localaddress', 'protocol')),
    'oscoutCHOP': ('OSC out', ('netaddress', 'port', 'protocol')),
    'oscoutDAT': ('OSC out', ('address', 'port', 'protocol')),
    'webserverDAT': ('Web server', ('port', 'secure')),
    'webclientDAT': ('Web client', ('url', 'reqmethod')),
    'websocketDAT': ('WebSocket', ('netaddress', 'port')),
    'socketioDAT': ('Socket.IO', ('url',)),
    'webrtcDAT': ('WebRTC', ('stun',)),
    'mqttclientDAT': ('MQTT', ('netaddress',)),
    'tcpipDAT': ('TCP/IP', ('mode', 'address', 'port')),
    'udpinDAT': ('UDP in', ('address', 'port', 'protocol')),
    'udpoutDAT': ('UDP out', ('address', 'port', 'protocol', 'localport')),
    'udtinDAT': ('UDT in', ('address', 'port')),
    'udtoutDAT': ('UDT out', ('port',)),
    'tuioinDAT': ('TUIO in', ('address', 'port')),
    'pipeinCHOP': ('Pipe in', ('mode', 'address', 'port')),
    'touchinTOP': ('Touch In', ('address', 'port')),
    'touchoutTOP': ('Touch Out', ('port',)),
    'touchinCHOP': ('Touch In', ('address', 'port')),
    'touchoutCHOP': ('Touch Out', ('port',)),
    'touchinDAT': ('Touch In', ('address', 'port')),
    'touchoutDAT': ('Touch Out', ('port',)),
    'ndiinTOP': ('NDI in', ('name',)),
    'ndioutTOP': ('NDI out', ('name', 'fps', 'includealpha')),
    'audiondiCHOP': ('NDI audio in', ('ndiintop',)),
    'syphonspoutinTOP': ('Syphon/Spout in', ('sendername',)),
    'syphonspoutoutTOP': ('Syphon/Spout out', ('sendername',)),
    'sharedmeminTOP': ('Shared memory in', ('name',)),
    'sharedmemoutTOP': ('Shared memory out', ('name',)),
    'dmxinCHOP': ('DMX/Art-Net/sACN in', ('interface', 'device', 'net', 'subnet', 'universe', 'multicast')),
    'dmxoutCHOP': ('DMX/Art-Net/sACN out', ('interface', 'device', 'netaddress', 'net', 'subnet', 'universe', 'rate')),
    'midiinCHOP': ('MIDI in', ('source', 'device', 'id')),
    'midiinDAT': ('MIDI in', ('device', 'id')),
    'midioutCHOP': ('MIDI out', ('destination', 'device', 'id')),
    'midioutDAT': ('MIDI out', ('device', 'id')),
    'midiinmapCHOP': ('MIDI in (map)', ('device', 'id')),
    'serialDAT': ('Serial', ('port', 'baudrate')),
    'serialCHOP': ('Serial', ('port', 'baudrate')),
    'videodeviceinTOP': ('Video device in', ('driver', 'device')),
    'videodeviceoutTOP': ('Video device out', ('library', 'device')),
    'audiodeviceinCHOP': ('Audio device in', ('driver', 'device')),
    'audiodeviceoutCHOP': ('Audio device out', ('driver', 'device')),
    'videostreaminTOP': ('Video stream in', ('mode', 'url')),
    'videostreamoutTOP': ('Video stream out', ('mode', 'port', 'url', 'streamname')),
    'audiostreaminCHOP': ('Audio stream in', ('url',)),
    'audiostreamoutCHOP': ('Audio stream out', ('port',)),
    'abletonlinkCHOP': ('Ableton Link', ('enable',)),
    'joystickCHOP': ('Joystick', ('source',)),
    'keyboardinDAT': ('Keyboard', ('keys',)),
    'keyboardinCHOP': ('Keyboard', ('keys',)),
    'mouseinCHOP': ('Mouse', ('monitor',)),
}
DEVICE_ACTIVE = ('active', 'enable')
# Ops that are an end of the line on purpose (they send / write / show), never dead branches.
SINK_TYPES = frozenset(('outTOP', 'outCHOP', 'outSOP', 'outPOP', 'outDAT', 'moviefileoutTOP', 'audiofileoutCHOP',
                        'ndioutTOP', 'syphonspoutoutTOP', 'sharedmemoutTOP', 'videodeviceoutTOP', 'touchoutTOP',
                        'touchoutCHOP', 'videostreamoutTOP', 'audiodeviceoutCHOP', 'audiostreamoutCHOP',
                        'oscoutCHOP', 'dmxoutCHOP', 'midioutCHOP', 'nullTOP', 'nullCHOP', 'nullSOP', 'nullPOP',
                        'renderTOP', 'opviewerTOP', 'feedbackTOP', 'feedbackCHOP', 'feedbackSOP'))
DEAD_FAMILIES = ('TOP', 'CHOP', 'SOP', 'POP')
# Offline par styles when a type is not in the op dump (I/O ops were not created for the dump).
FALLBACK_REF_PARS = frozenset(('callbacks', 'dat', 'chop', 'top', 'sop', 'pop', 'op', 'panels', 'panel', 'winop',
                               'opviewer', 'camera', 'geometry', 'lights', 'material', 'instanceop', 'audiochop',
                               'timecodeop', 'headerdat', 'fromop', 'resizecomp', 'repocomp', 'helpdat', 'ndiintop',
                               'videostreamintop', 'webrtc', 'device', 'grouptable', 'metadata', 'segdat',
                               'filterdat', 'routingtable', 'exporttable', 'autoexportroot'))
FALLBACK_FILE_PARS = frozenset(('file', 'externaltox', 'privatekey', 'certificate', 'folder'))

TEXT_CAP = 200000      # chars of one DAT's text kept for reference parsing
TABLE_TEXT_CAP = 20000  # tables: their text is TSV; less of it is kept
STR_CAP = 300          # par values / expressions kept per par
MSG_CAP = 400          # error / warning text per op
ENUM_MAX = 200000      # ops enumerated (paths only) at most
ANALYZE_LIMIT = 5000   # ops read in detail per page
MAX_ITEMS = 200        # per list in a reply
MAX_EDGES = 3000
BUDGET_MS = 8.0        # work per frame before handing the rest to the next frame (Pending)


# ================================================================== pure helpers (no TD)

def clip(s, n=STR_CAP):
    s = '' if s is None else str(s)
    return s if len(s) <= n else s[:n] + '...'


def rnd(v, sig=4):
    try:
        f = float(v)
    except Exception:
        return None
    if not math.isfinite(f):
        return None
    return 0.0 if f == 0 else float('%.*g' % (sig, f))


def jval(v, n=STR_CAP):
    """A par value made small and JSON-safe (OP -> path, numbers rounded, strings clipped)."""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return rnd(v, 6)
    if hasattr(v, 'path') and hasattr(v, 'OPType'):
        return v.path
    if isinstance(v, (list, tuple)):
        return [jval(x, 80) for x in list(v)[:16]]
    return clip(v, n)


def mode_code(m):
    """'c' | 'e' | 'x' | 'b' from a ParMode (or its name / an int 0..3)."""
    s = str(getattr(m, 'name', m)).upper()
    if s.endswith('EXPRESSION') or s == '1':
        return 'e'
    if s.endswith('EXPORT') or s == '2':
        return 'x'
    if s.endswith('BIND') or s == '3':
        return 'b'
    return 'c'


def family_of(optype):
    m = re.search(r'(TOP|CHOP|SOP|DAT|COMP|MAT|POP)$', str(optype or ''))
    return m.group(1) if m else ''


def parent_path(p):
    if not p or p == '/':
        return None
    q = p.rsplit('/', 1)[0]
    return q or '/'


def join_path(base, rel):
    """Absolute path of rel against base (handles '.', '..', './x', absolute rel)."""
    rel = str(rel).strip()
    parts = [] if rel.startswith('/') else [x for x in str(base or '/').split('/') if x]
    for seg in rel.split('/'):
        if seg in ('', '.'):
            continue
        if seg == '..':
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    return '/' + '/'.join(parts)


def ancestor(p, n=1):
    for _ in range(max(1, int(n))):
        p = parent_path(p)
        if p is None:
            return None
    return p


def under(p, root):
    root = (root or '/').rstrip('/') or '/'
    return root == '/' or p == root or p.startswith(root + '/')


def truthy(v):
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'on', 'true', 'yes')
    return bool(v)


# ---------------------------------------------------------------- reference parsing (expressions, binds, DAT text)

REF_RE = re.compile(
    r"(?P<pre>(?:\bme|\bparent\((?P<pl>\d*)\))\.)?\bop\(\s*(?:'(?P<a>[^'\\\n]*)'|\"(?P<b>[^\"\\\n]*)\")\s*\)"
    r"|\bops\(\s*(?:'(?P<g1>[^'\n]*)'|\"(?P<g2>[^\"\n]*)\")"
    r'|\bparent\((?P<plev>\d*)\)'
    r'|\bparent\.(?P<pshort>[A-Z]\w*)'
    r'|(?<![\w.])op\.(?P<oshort>[A-Z]\w*)'
    r'|(?<![\w.])iop\.(?P<ishort>\w+)'
    r'|(?<![\w.])ipar\.(?P<ipshort>\w+)\.(?P<ippar>\w+)'
    r'|(?<![\w.])mod\.(?P<mod>[A-Za-z_]\w*)'
    r'|\bme\b')
TAIL_PAR_RE = re.compile(r'\s*\.par\.(\w+)')
TAIL_CHAN_RE = re.compile(r"""\s*\[\s*(?:'([^'\n]+)'|"([^"\n]+)")\s*\]""")
TAIL_MODULE_RE = re.compile(r'\s*\.(?:module|mod)\b')


def parse_refs(text, cap=500):
    """Op / par / channel references in an expression or script text. Each ref:
    {kind: op|ops|parent|pshort|oshort|iop|ipar|mod|me, arg, base ('me' | 'parent<N>' | 'obj' | None), par?, chan?,
    module?}. base 'obj' = some_comp.op('x'): relative to an object we cannot know (only absolute paths resolve)."""
    out = []
    if not text:
        return out
    s = str(text)
    for m in REF_RE.finditer(s):
        if len(out) >= cap:
            break
        g = m.groupdict()
        ref = None
        opstr = g.get('a') if g.get('a') is not None else g.get('b')
        if opstr is not None:
            pre = g.get('pre') or ''
            base = None
            if pre.startswith('me'):
                base = 'me'
            elif pre.startswith('parent'):
                base = 'parent' + (g.get('pl') or '1')
            elif m.start() > 0 and s[m.start() - 1] == '.':
                base = 'obj'
            ref = {'kind': 'op', 'arg': opstr, 'base': base}
        elif g.get('g1') is not None or g.get('g2') is not None:
            ref = {'kind': 'ops', 'arg': g.get('g1') if g.get('g1') is not None else g.get('g2')}
        elif g.get('plev') is not None:
            ref = {'kind': 'parent', 'arg': int(g['plev'] or 1)}
        elif g.get('pshort'):
            ref = {'kind': 'pshort', 'arg': g['pshort']}
        elif g.get('oshort'):
            ref = {'kind': 'oshort', 'arg': g['oshort']}
        elif g.get('ishort'):
            ref = {'kind': 'iop', 'arg': g['ishort']}
        elif g.get('ipshort'):
            ref = {'kind': 'ipar', 'arg': g['ipshort'], 'par': g['ippar']}
        elif g.get('mod'):
            ref = {'kind': 'mod', 'arg': g['mod']}
        else:
            ref = {'kind': 'me', 'arg': None}
        rest = s[m.end():m.end() + 120]
        t = TAIL_PAR_RE.match(rest)
        if t and ref['kind'] not in ('ipar', 'mod'):
            ref['par'] = t.group(1)
        else:
            c = TAIL_CHAN_RE.match(rest)
            if c and ref['kind'] in ('op', 'oshort', 'pshort', 'parent', 'me'):
                ref['chan'] = c.group(1) or c.group(2)
            elif TAIL_MODULE_RE.match(rest) and ref['kind'] in ('op', 'oshort', 'pshort', 'me', 'parent'):
                ref['module'] = True
        out.append(ref)
    return out


class Ctx(object):
    """What reference resolution needs: known paths, COMP paths, shortcuts, package prefixes (not entered)."""

    def __init__(self, paths=(), comps=(), op_shortcuts=None, parent_shortcuts=None, packages=()):
        self.paths = set(paths)
        self.comps = set(comps)
        self.op_sc = dict(op_shortcuts or {})
        self.parent_sc = dict(parent_shortcuts or {})   # COMP path -> its parentshortcut name
        self.packages = sorted(set(packages))

    def exists(self, p):
        if p in self.paths or p == '/sys' or p.startswith('/sys/'):  # /sys = TD's own system COMPs
            return True
        return any(p.startswith(k + '/') for k in self.packages)


def ref_candidates(ref, owner, owner_is_comp):
    """Paths a ref may point at, most likely first (resolution then picks the first that exists)."""
    k = ref['kind']
    if k == 'op':
        a = ref['arg']
        if a.startswith('/'):
            return [join_path('/', a)]
        if ref.get('base') == 'obj':
            return []
        if ref.get('base') == 'me':
            bases = [owner] if owner_is_comp else [parent_path(owner), owner]
        elif ref.get('base', '') and ref['base'].startswith('parent'):
            bases = [ancestor(owner, int(ref['base'][6:] or 1))]
        else:  # bare op(): relative to the owner's network (a COMP's own pars: the COMP first)
            bases = [owner, parent_path(owner)] if owner_is_comp else [parent_path(owner)]
        return [join_path(b, a) for b in bases if b]
    if k == 'parent':
        p = ancestor(owner, ref['arg'] or 1)
        return [p] if p else []
    if k == 'me':
        return [owner]
    return []


def resolve_ref(ref, owner, owner_is_comp, ctx):
    """(path or None, resolved: bool). Shortcuts resolve through ctx; op() paths must exist in ctx when it knows paths."""
    k = ref['kind']
    if k == 'oshort':
        p = ctx.op_sc.get(ref['arg'])
        return (p, True) if p else (None, False)
    if k == 'pshort':
        p = parent_path(owner)
        while p:
            if ctx.parent_sc.get(p) == ref['arg']:
                return p, True
            p = parent_path(p)
        if ctx.parent_sc.get('/') == ref['arg']:
            return '/', True
        return None, False
    cands = ref_candidates(ref, owner, owner_is_comp)
    if not cands:
        return None, False
    if not ctx.paths:
        return cands[0], True
    for c in cands:
        if ctx.exists(c):
            return c, True
    return cands[0], False


def ext_class(text):
    """Class name an extension object expression builds: op('./X').module.Cls(me) / mod.X.Cls(me)."""
    m = re.search(r'\.module\.(\w+)\s*\(', str(text or '')) or re.search(r'\bmod\.(?:\w+\.)*?(\w+)\s*\(', str(text or ''))
    return m.group(1) if m else None


# ---------------------------------------------------------------- which pars a record keeps

def need_value(optype, name, mode, style):
    """Cheap pre-filter (mode + style + name only) before the value is read."""
    if mode != 'c' or style in REF_STYLES or style in FILE_STYLES:
        return True
    if name in SHORTCUT_PARS or name in COOK_ALWAYS_PARS or name in PACKAGE_PARS or name == 'callbacks':
        return True
    if EXT_PAR_RE.match(name) or name.endswith('callback'):
        return True
    dev = DEVICES.get(optype)
    if dev and (name in dev[1] or name in DEVICE_ACTIVE):
        return True
    if optype in EXEC_TYPES and (name == 'active' or name in EXEC_TYPES[optype]):
        return True
    return False


def keep_par(optype, name, mode, style, val):
    if mode != 'c':
        return True
    empty = val is None or val == '' or val == []
    if style in REF_STYLES or style in FILE_STYLES or name in SHORTCUT_PARS or name == 'callbacks' \
            or name.endswith('callback') or EXT_PAR_RE.match(name) or name in ('clone', 'externaltox'):
        return not empty
    if name in COOK_ALWAYS_PARS or name == 'enableexternaltox':
        return truthy(val)
    return need_value(optype, name, mode, style)


def par_rec(name, mode, val, style='', expr='', bind='', ev=None, exporter=None):
    r = {'n': name, 'm': mode, 'v': jval(val)}
    if style:
        r['s'] = style
    if mode == 'e' and expr:
        r['e'] = clip(expr)
    if mode == 'b' and bind:
        r['e'] = clip(bind)
    if ev is not None and ev != r['v']:
        r['ev'] = jval(ev)
    if exporter:
        r['x'] = exporter
    return r


def pars_by_name(rec):
    return {p['n']: p for p in rec.get('pars') or []}


def package_kind(rec):
    """Why a COMP is not entered: a clone of another COMP, an op-shortcut package, or a palette .tox."""
    if not rec.get('comp'):
        return None
    pp = pars_by_name(rec)
    cl = pp.get('clone')
    if cl:
        v = cl.get('ev') or cl.get('v') or cl.get('e')
        if v and str(v) not in ('', rec['p'], '.', './', 'me'):
            return 'clone of {}'.format(v)
    sc = pp.get('opshortcut')
    if sc and sc.get('v'):
        return 'op shortcut {}'.format(sc['v'])
    et = pp.get('externaltox')
    if et and 'palette' in str(et.get('v', '')).lower():
        return 'palette {}'.format(os.path.basename(str(et['v'])))
    return None


# ================================================================== analysis (pure: records in, summary out)

def _cap(items, n):
    return items[:n], len(items)


def _edge_key(e):
    return (e[0], e[1], e[2], e[3])


def build_ctx(recs, paths=None, packages=()):
    comps, op_sc, parent_sc = set(), {}, {}
    for r in recs:
        if r.get('comp'):
            comps.add(r['p'])
            pp = pars_by_name(r)
            if pp.get('opshortcut') and pp['opshortcut'].get('v'):
                op_sc[str(pp['opshortcut']['v'])] = r['p']
            if pp.get('parentshortcut') and pp['parentshortcut'].get('v'):
                parent_sc[r['p']] = str(pp['parentshortcut']['v'])
    allp = set(paths) if paths else set(r['p'] for r in recs)
    allp.add('/')
    return Ctx(allp, comps, op_sc, parent_sc, packages)


def analyze(recs, root='/', top=10, max_items=MAX_ITEMS, paths=None, packages=None, now_frame=None,
            folder=None, file_exists=None, tree_depth=3, notes=None):
    """The X-ray of a network from op records (live: _op_record; offline: read_expanded). Pure."""
    root = (root or '/').rstrip('/') or '/'
    packages = list(packages or [])
    ctx = build_ctx(recs, paths, [p['p'] for p in packages])
    by = {r['p']: r for r in recs}
    edges, unresolved = [], []
    exprs, binds, exports, dat_refs, exts, files, devices = [], [], [], [], [], [], []
    exec_dats, callbacks, script_ops, modules, cook_always = [], [], [], {}, []
    errors, warnings, script_errors = [], [], []
    flags = {'bypass': [], 'lock': [], 'parked': [], 'display': 0, 'render': 0, 'viewer_on': 0, 'export': []}
    by_family, by_type = {}, {}
    sources = set()
    texts = []

    def edge(src, dst, kind, label):
        if not src or not dst or src == dst:
            return
        edges.append([src, dst, kind, label])
        sources.add(src)

    for r in recs:
        p, t = r['p'], r.get('t', '')
        f = r.get('f') or family_of(t)
        by_family[f] = by_family.get(f, 0) + 1
        by_type[t] = by_type.get(t, 0) + 1
        is_comp = bool(r.get('comp'))
        for i, src in enumerate(r.get('in') or []):
            if src:
                edge(src, p, 'wire', 'in{}'.format(i))
        pp = pars_by_name(r)
        for par in r.get('pars') or []:
            n, m, v, s = par['n'], par['m'], par.get('v'), par.get('s', '')
            if m in ('e', 'b'):
                item = {'p': p, 'par': n, 'expr': par.get('e', ''), 'refs': []}
                for ref in parse_refs(par.get('e', '')):
                    if ref['kind'] in ('me', 'mod', 'ops', 'iop', 'ipar'):
                        if ref['kind'] == 'mod':
                            modules.setdefault(ref['arg'], set()).add(p)
                        continue
                    tgt, ok = resolve_ref(ref, p, is_comp, ctx)
                    if ok:
                        edge(tgt, p, 'expr' if m == 'e' else 'bind', n + ('<-' + ref['par'] if ref.get('par') else ''))
                        item['refs'].append(tgt + ('.par.' + ref['par'] if ref.get('par') else '')
                                            + ("['{}']".format(ref['chan']) if ref.get('chan') else ''))
                    elif tgt:
                        unresolved.append({'p': p, 'par': n, 'ref': _ref_text(ref), 'tried': tgt})
                (exprs if m == 'e' else binds).append(item)
            elif m == 'x':
                x = par.get('x')
                exports.append({'p': p, 'par': n, 'from': x})
                if x:
                    edge(x, p, 'export', n)
            if m == 'c' and s in REF_STYLES and v not in (None, ''):
                tgt = par.get('ev') if isinstance(par.get('ev'), str) and str(par.get('ev')).startswith('/') else None
                if tgt is None:
                    for sv in str(v).split():
                        tg, ok = resolve_ref({'kind': 'op', 'arg': sv, 'base': None}, p, is_comp, ctx)
                        if ok:
                            edge(tg, p, 'ref', n)
                        else:
                            unresolved.append({'p': p, 'par': n, 'ref': sv, 'tried': tg})
                else:
                    edge(tgt, p, 'ref', n)
            if s in FILE_STYLES and m in ('e', 'b') and par.get('ev') in (None, '') and par.get('e'):
                files.append({'p': p, 'par': n, 'path': '=' + par['e'], 'dynamic': True})
            elif s in FILE_STYLES and v not in (None, '') and m in ('c', 'e', 'b'):
                if n == 'externaltox' and not truthy((pp.get('enableexternaltox') or {}).get('v')):
                    pass  # a loaded palette tox keeps its name with external off: not a dependency (T-53)
                else:
                    fp = par.get('ev', v) if m != 'c' else v
                    files.append(_file_item(p, n, fp, s, folder, file_exists))
            if (EXT_PAR_RE.match(n) and n.endswith('object')) or re.match(r'^extension\d+$', n):
                code = par.get('e') or v
                if code:
                    tgt = None
                    for ref in parse_refs(code):
                        if ref['kind'] == 'op':
                            tgt, _ok = resolve_ref(ref, p, True, ctx)
                            break
                    exts.append({'p': p, 'par': n, 'object': clip(code, 200), 'class': ext_class(code), 'dat': tgt})
                    if tgt:
                        edge(tgt, p, 'extension', n)
            if n in COOK_ALWAYS_PARS and truthy(v):
                cook_always.append({'p': p, 't': t, 'par': n})
        if t in DEVICES:
            kind, keys = DEVICES[t]
            st = {k: pp[k].get('ev', pp[k].get('v')) for k in keys if k in pp}
            act = next((pp[k].get('v') for k in DEVICE_ACTIVE if k in pp), None)
            devices.append({'p': p, 't': t, 'kind': kind, 'active': truthy(act) if act is not None else None,
                            'settings': st})
        if t in EXEC_TYPES:
            act = pp.get('active', {}).get('v')
            trig = [k for k in EXEC_TYPES[t] if truthy((pp.get(k) or {}).get('v'))]
            w = pp.get(EXEC_WATCH.get(t, ''), {})
            watched = None
            if w.get('v'):
                watched, _ok = resolve_ref({'kind': 'op', 'arg': str(w.get('ev', w['v'])).split()[0], 'base': None},
                                           p, False, ctx)
                if _ok:
                    edge(watched, p, 'watch', EXEC_WATCH[t])
            exec_dats.append({'p': p, 't': t, 'active': truthy(act) if act is not None else True, 'triggers': trig,
                              'watches': watched})
        for par in r.get('pars') or []:
            if (par['n'] == 'callbacks' or par['n'].endswith('callback')) and par.get('v'):
                cb, ok = resolve_ref({'kind': 'op', 'arg': str(par.get('ev', par['v'])), 'base': None}, p, is_comp, ctx)
                callbacks.append({'host': p, 'host_t': t, 'dat': cb if ok else par['v'], 'found': ok})
                if ok:
                    edge(cb, p, 'callbacks', par['n'])
        if t in SCRIPT_TYPES:
            script_ops.append({'p': p, 't': t})
        txt = r.get('text')
        if txt:
            texts.append(txt)
            refs = []
            for ref in parse_refs(txt, cap=300):
                if ref['kind'] == 'mod':
                    modules.setdefault(ref['arg'], set()).add(p)
                    continue
                if ref['kind'] not in ('op', 'parent', 'pshort', 'oshort'):
                    continue
                tgt, ok = resolve_ref(ref, p, False, ctx)
                if ok:
                    refs.append(tgt)
                    edge(tgt, p, 'script', 'module' if ref.get('module') else 'text')
                elif ref['kind'] == 'op' and tgt:
                    unresolved.append({'p': p, 'par': '(text)', 'ref': _ref_text(ref), 'tried': tgt})
            if refs:
                dat_refs.append({'p': p, 'refs': sorted(set(refs))[:40], 'count': len(set(refs))})
        e, w, se = r.get('err'), r.get('warn'), r.get('serr')
        if e:
            errors.append({'p': p, 't': t, 'msg': clip(e, MSG_CAP)})
        if w:
            warnings.append({'p': p, 't': t, 'msg': clip(w, MSG_CAP)})
        if se:
            script_errors.append({'p': p, 't': t, 'msg': clip(se, MSG_CAP)})
        fl = set(r.get('flags') or [])
        for k in ('bypass', 'lock', 'parked', 'export'):
            if k in fl:
                flags[k].append(p)
        for k, key in (('display', 'display'), ('render', 'render'), ('viewer', 'viewer_on')):
            if k in fl:
                flags[key] += 1
    # Python modules referenced as mod.X / op('x').module
    for r in recs:
        if r.get('f') == 'DAT' or family_of(r.get('t')) == 'DAT':
            nm = r['p'].rsplit('/', 1)[-1]
            if nm in modules:
                edge(r['p'], sorted(modules[nm])[0], 'module', 'mod.' + nm)
    tokens = set()
    for txt in texts:
        tokens.update(re.findall(r'[A-Za-z_]\w*', txt))
    dead = []
    for r in recs:
        f = r.get('f') or family_of(r.get('t'))
        if f not in DEAD_FAMILIES or r.get('t') in SINK_TYPES or r['p'] in sources:
            continue
        fl = set(r.get('flags') or [])
        if fl & {'display', 'render', 'export'} or r.get('outs'):
            continue
        name = r['p'].rsplit('/', 1)[-1]
        if name in tokens:
            continue
        dead.append(r['p'])
    heavy = sorted([r for r in recs if (r.get('cpu') or 0) + (r.get('gpu') or 0) > 0],
                   key=lambda r: -((r.get('cpu') or 0) + (r.get('gpu') or 0)))
    heavy_rows = []
    for r in heavy[:top]:
        row = {'p': r['p'], 't': r.get('t'), 'cpu_ms': rnd(r.get('cpu') or 0), 'gpu_ms': rnd(r.get('gpu') or 0),
               'cooks': r.get('cooks')}
        if now_frame is not None and r.get('caf') is not None:
            row['frames_since_cook'] = int(now_frame) - int(r['caf'])
            row['stale'] = row['frames_since_cook'] > 300
        heavy_rows.append(row)
    gmem = sorted([r for r in recs if r.get('gmem')], key=lambda r: -r['gmem'])[:top]
    # top-level flow: edges between the children of flow_root (ops deeper count for their top-level COMP). flow_root
    # starts at root and steps into a COMP child that holds >= 90% of the ops (e.g. / -> /project1), at most 3 times.
    def group(p, fr):
        if not under(p, fr) or p == fr:
            return None
        rest = p[len(fr):].lstrip('/') if fr != '/' else p.lstrip('/')
        return join_path(fr, rest.split('/')[0])

    flow_root = root
    for _i in range(3):
        groups = {}
        for r in recs:
            g = group(r['p'], flow_root)
            if g:
                groups[g] = groups.get(g, 0) + 1
        total = sum(groups.values())
        big = max(groups, key=groups.get) if groups else None
        if big and total >= 20 and groups[big] >= 0.9 * total and by.get(big, {}).get('comp') and len(groups) > 0:
            flow_root = big
            continue
        break
    agg = {}
    for s, d, k, _l in edges:
        a, b = group(s, flow_root), group(d, flow_root)
        if a and b and a != b:
            key = (a, b, k)
            agg[key] = agg.get(key, 0) + 1
    nodes = []
    for g in sorted(groups):
        rr = by.get(g, {})
        nodes.append({'p': g, 't': rr.get('t', '?'), 'ops': groups[g]})
    top_edges = [[a, b, k, n] for (a, b, k), n in sorted(agg.items(), key=lambda kv: (-kv[1], kv[0]))]
    edges.sort(key=_edge_key)
    by_kind = {}
    for e in edges:
        by_kind[e[2]] = by_kind.get(e[2], 0) + 1
    files.sort(key=lambda x: (x.get('exists') is not False, bool(x.get('dynamic')), x['p']))
    packages.sort(key=lambda x: (-(x.get('kids') or 0), x['p']))
    out = {
        'root': root,
        'ops': len(recs),
        'inventory': {
            'by_family': dict(sorted(by_family.items(), key=lambda kv: -kv[1])),
            'by_type': dict(sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0]))[:40]),
            'types': len(by_type),
            'comp_tree': comp_tree(recs, root, tree_depth, max_items),
            'packages': packages[:max_items],
        },
        'graph': {'edges_by_kind': by_kind, 'edges_total': len(edges), 'edges': edges[:MAX_EDGES],
                  'edges_truncated': len(edges) > MAX_EDGES,
                  'top_level': {'root': flow_root, 'nodes': nodes[:max_items], 'edges': top_edges[:max_items * 2]}},
        'expressions': _listing(exprs, max_items),
        'binds': _listing(binds, max_items),
        'exports': _listing(exports, max_items),
        'unresolved_refs': _listing(unresolved, max_items),
        'dat_refs': _listing(dat_refs, max_items),
        'extensions': _listing(exts, max_items),
        'python': {
            'exec_dats': _listing(exec_dats, max_items),
            'callbacks': _listing(callbacks, max_items),
            'script_ops': _listing(script_ops, max_items),
            'modules': _listing([{'name': k, 'used_by': sorted(v)[:10]} for k, v in sorted(modules.items())], max_items),
            'where': _python_where(exec_dats, callbacks, script_ops, exts),
        },
        'files': dict(_listing(files, max_items), missing=len([x for x in files if x.get('exists') is False])),
        'devices': _listing(devices, max_items),
        'health': {
            'errors': _listing(errors, max_items),
            'warnings': _listing(warnings, max_items),
            'script_errors': _listing(script_errors, max_items),
            'cook_always': _listing(cook_always, max_items),
            'bypassed': _listing(flags['bypass'], max_items),
            'locked': _listing(flags['lock'], max_items),
            'parked': _listing(flags['parked'], max_items),
            'exporting': _listing(flags['export'], max_items),
            'display_flags': flags['display'], 'render_flags': flags['render'],
            'viewers_on': flags['viewer_on'],
            'dead_branches': _listing(sorted(dead), max_items),
            'heavy': heavy_rows,
            'gpu_memory_mb': [{'p': r['p'], 'mb': rnd(r['gmem'] / 1048576.0, 3)} for r in gmem],
        },
    }
    if notes:
        out['notes'] = list(notes)
    return out


def _ref_text(ref):
    k = ref['kind']
    if k == 'op':
        b = {'me': 'me.', None: ''}.get(ref.get('base'), (ref.get('base') or '') + '().')
        b = b.replace('parent1().', 'parent().')
        return "{}op('{}')".format(b, ref['arg'])
    if k == 'pshort':
        return 'parent.' + ref['arg']
    if k == 'oshort':
        return 'op.' + ref['arg']
    if k == 'parent':
        return 'parent({})'.format(ref['arg'] if ref['arg'] != 1 else '')
    return k


def _listing(items, n):
    return {'count': len(items), 'items': items[:n]} if len(items) > n else {'count': len(items), 'items': items}


def _python_where(exec_dats, callbacks, script_ops, exts):
    return {'exec_dats': len(exec_dats), 'exec_dats_active': len([x for x in exec_dats if x['active']]),
            'frame_callbacks': [x['p'] for x in exec_dats if x['active'] and
                                set(x['triggers']) & {'framestart', 'frameend', 'whileon', 'whileoff'}][:50],
            'callback_dats': len(callbacks), 'script_ops': len(script_ops), 'extensions': len(exts)}


def _file_item(p, par, fp, style, folder, file_exists):
    fp = str(fp)
    item = {'p': p, 'par': par, 'path': fp}
    if style == 'FileSave':
        item['write'] = True
    if style == 'Folder':
        item['folder'] = True
    full = fp if os.path.isabs(fp) or not folder else os.path.join(str(folder), fp)
    if fp.startswith(('http:', 'https:', 'rtsp:', 'rtmp:', 'srt:', 'udp:')):
        item['url'] = True
        return item
    if file_exists is not None and style != 'FileSave' and not re.search(r'[\$`]', fp):
        item['exists'] = bool(_try(lambda: file_exists(full), None))
    return item


def comp_tree(recs, root, depth=3, cap=MAX_ITEMS):
    """Nested COMP tree under root with op counts (whole subtree), depth-limited, capped."""
    counts = {}
    comps = [r for r in recs if r.get('comp')]
    cset = set(r['p'] for r in comps)
    for r in recs:
        q = parent_path(r['p'])
        while q is not None:
            if q in cset or q == root:
                counts[q] = counts.get(q, 0) + 1
            if q == root or q == '/':
                break
            q = parent_path(q)
    by = {r['p']: r for r in comps}
    kids = {}
    for p in sorted(cset):
        if p == root:
            continue
        q = parent_path(p)
        while q is not None and q not in cset and q != root:
            q = parent_path(q)
        if q is None or not under(p, root):
            continue
        kids.setdefault(q, []).append(p)
    made = [0]

    def node(p, d):
        r = by.get(p, {})
        n = {'p': p, 't': r.get('t', ''), 'ops': counts.get(p, 0)}
        if r.get('pkg'):
            n['package'] = r['pkg']
        made[0] += 1
        ch = kids.get(p, [])
        if ch and d < depth and made[0] < cap:
            n['kids'] = [node(c, d + 1) for c in sorted(ch, key=lambda c: -counts.get(c, 0)) if made[0] < cap]
        elif ch:
            n['more_comps'] = len(ch)
        return n
    return node(root, 0)


# ================================================================== offline: TD's toeexpand output (read-only)

PROLOGUE = 27
EXPR_BIT = 0x10
BIND_BIT = 0x200


def read_payload(buf):
    """A DAT's text from a .text file: b'1\\n*' or b'2\\n*', six uint32, the payload (format: td-atlas, src/offline.js)."""
    if len(buf) < PROLOGUE or buf[0:1] not in (b'1', b'2') or buf[1:3] != b'\n*':
        return None
    return buf[PROLOGUE:].decode('utf-8', 'replace')


def _unq(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
        return re.sub(r'\\(["\\nt\'])', lambda m: {'n': '\n', 't': '\t'}.get(m.group(1), m.group(1)), s)
    return s


def _take(s):
    s = s.lstrip()
    if not s.startswith('"'):
        i = s.find(' ')
        return (s, '') if i < 0 else (s[:i], s[i + 1:])
    i = 1
    while i < len(s):
        if s[i] == '\\':
            i += 2
            continue
        if s[i] == '"':
            return _unq(s[:i + 1]), s[i + 1:]
        i += 1
    return _unq(s + '"'), ''


def read_node(text):
    """.n file -> {family, type, inputs: [(index, name)], flags: {k: v}, comment}."""
    n = {'family': '', 'type': '', 'inputs': [], 'flags': {}, 'comment': ''}
    block = None
    for raw in str(text).split('\n'):
        line = raw.strip()
        if not line:
            continue
        if block:
            if line == '}':
                block = None
            elif line != '{' and block == 'inputs':
                m = re.match(r'^(\d+)\s+(.+)$', line)
                if m:
                    n['inputs'].append((int(m.group(1)), m.group(2).strip()))
            continue
        if not n['family'] and re.match(r'^[A-Z]+:\S+$', line):
            n['family'], n['type'] = line.split(':', 1)
            continue
        head = line.split()[0]
        rest = line.split()[1:]
        if head == 'flags':
            t = [x for x in rest if x != '=']
            for i in range(0, len(t) - 1, 2):
                n['flags'][t[i]] = t[i + 1]
        elif head == 'comment':
            n['comment'] = _unq(line[8:])
        elif head in ('inputs', 'outputs', 'docked', 'wires'):
            block = head
        elif head == 'end':
            break
    return n


def read_parms(text):
    """.parm -> {name: {'mode': c|e|x|b, 'value', 'expr'?, 'bind'?}}. Flags word: low 2 bits = ParMode (0 constant,
    1 expression, 2 export, 3 bind; reverse-engineered on 31550 files: 17/49 expression, 2 export, 515 bind),
    0x10 = an expression string follows, 0x200 = a bind string follows."""
    out = {}
    for raw in str(text).split('\n'):
        line = raw.strip()
        m = re.match(r'^(\S+)\s+(-?\d+)\s?(.*)$', line)
        if not line or line == '?' or not m:
            continue
        flags = int(m.group(2))
        rest = m.group(3)
        val, rest = _take(rest)
        d = {'mode': 'cexb'[flags & 3], 'value': val}
        if flags & EXPR_BIT:
            e, rest = _take(rest)
            d['expr'] = e
        if flags & BIND_BIT:
            b, rest = _take(rest)
            d['bind'] = b
        out[m.group(1)] = d
    return out


def load_styles(ops_dir):
    """{optype: {par: style}} for reference / file styles from the live op dump (docs/research/ops)."""
    styles = {}
    if not ops_dir or not os.path.isdir(ops_dir):
        return styles
    for f in sorted(os.listdir(ops_dir)):
        if not (f.startswith('ops_') and f.endswith('.json')):
            continue
        try:
            with open(os.path.join(ops_dir, f), 'r', encoding='utf-8') as fh:
                d = json.load(fh)
        except Exception:
            continue
        for o in d.get('dumped') or []:
            m = {}
            for p in o.get('pars') or []:
                s = p.get('style')
                if s in REF_STYLES or s in FILE_STYLES:
                    m[p.get('name')] = s
            styles[o.get('type')] = m
    return styles


def style_of(styles, optype, name):
    m = styles.get(optype)
    if m is not None and name in m:
        return m[name]
    if name in FALLBACK_REF_PARS:
        return 'OP'
    if name in FALLBACK_FILE_PARS:
        return 'File'
    return ''


def _offline_rec(dirpath, rel, p, styles, text_cap):
    def rd(ext, binary=False):
        try:
            with open(os.path.join(dirpath, rel + ext), 'rb') as f:
                b = f.read()
            return b if binary else b.decode('utf-8', 'replace')
        except Exception:
            return None
    node = read_node(rd('.n') or '')
    fam = node['family'] or ''
    t = (node['type'] + fam) if fam else ''
    r = {'p': p, 't': t, 'f': fam}
    if fam == 'COMP':
        r['comp'] = True
    par_dir = parent_path(p)
    ins = []
    for i, src in sorted(node['inputs']):
        while len(ins) < i:
            ins.append(None)
        ins.append(join_path(par_dir, src) if not src.startswith('/') else src)
    if ins:
        r['in'] = ins
    fl = node['flags']
    flags = [k for k in ('display', 'render', 'bypass', 'lock', 'export') if fl.get(k) == 'on']
    if fl.get('viewer') == '1':
        flags.append('viewer')
    if fl.get('cook') == 'off':
        flags.append('parked')
    if flags:
        r['flags'] = flags
    if node['comment']:
        r['comment'] = clip(node['comment'], 200)
    pars = []
    for name, d in sorted(read_parms(rd('.parm') or '').items()):
        s = style_of(styles, t, name)
        mode = d['mode']
        expr = d.get('expr', '') if mode == 'e' else d.get('bind', '') if mode == 'b' else ''
        if mode == 'b' and not expr:
            expr = d.get('expr', '')
        if mode in ('e', 'b') and not expr:
            mode = 'c'
        if keep_par(t, name, mode, s, d['value']):
            pars.append(par_rec(name, mode, d['value'], s, expr if mode == 'e' else '', expr if mode == 'b' else ''))
    if pars:
        r['pars'] = pars
    if fam == 'DAT':
        b = rd('.text', binary=True)
        txt = read_payload(b) if b else None
        if txt:
            r['text'] = txt[:text_cap]
            r['text_len'] = len(txt)
    return r


def read_expanded(dirpath, root='/', depth=99, packages=False, styles=None, limit=None, text_cap=TEXT_CAP):
    """Walk a toeexpand .dir: (records, packages not entered, every op path seen). Depth-first by name."""
    styles = styles or {}
    root = (root or '/').rstrip('/') or '/'
    recs, pkgs, paths = [], [], []
    root_depth = 0 if root == '/' else root.count('/')

    def walk(rel_dir):
        d = os.path.join(dirpath, rel_dir) if rel_dir else dirpath
        try:
            names = sorted(os.listdir(d))
        except Exception:
            return
        for f in names:
            if not f.endswith('.n'):
                continue
            base = f[:-2]
            rel = (rel_dir + '/' + base) if rel_dir else base
            p = '/' + rel
            if not (under(p, root) or under(root, p)):
                continue
            inside = under(p, root)
            level = p.count('/') - root_depth
            if inside:
                paths.append(p)
                if limit is not None and len(recs) >= limit:
                    pass
                elif level <= depth:
                    r = _offline_rec(dirpath, rel, p, styles, text_cap)
                    recs.append(r)
                    kind = package_kind(r) if r.get('comp') and p != root else None
                    if kind and not packages:
                        r['pkg'] = kind
                        kids = _try(lambda: len([x for x in os.listdir(os.path.join(dirpath, rel)) if x.endswith('.n')]), 0)
                        r['kids'] = kids
                        pkgs.append({'p': p, 'kind': kind, 'kids': kids})
                        continue
            if os.path.isdir(os.path.join(dirpath, rel)) and (not inside or level < depth):
                walk(rel)
    walk('')
    return recs, pkgs, paths


def read_build(dirpath):
    out = {}
    try:
        with open(os.path.join(dirpath, '.build'), 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                k, _s, v = line.strip().partition(' ')
                if k:
                    out[k] = v
    except Exception:
        pass
    return out


def analyze_expanded(dirpath, root='/', depth=99, packages=False, ops_dir=None, top=10, max_items=MAX_ITEMS,
                     folder=None, file=None):
    t0 = time.time()
    recs, pkgs, paths = read_expanded(dirpath, root, depth, packages, load_styles(ops_dir))
    notes = ['offline (toeexpand): no cook times, errors or export sources; par styles from the 31550 op dump; '
             'custom par styles unknown']
    if not recs:
        raise ValueError('no operator {} in the expanded file'.format(root))
    s = analyze(recs, root, top, max_items, paths=paths, packages=pkgs, folder=folder,
                file_exists=os.path.exists if folder else None, notes=notes)
    b = read_build(dirpath)
    s.update({'source': 'file', 'file': file, 'build': b.get('build'), 'saved': b.get('time'),
              'total_ops': len(paths), 'ms': round((time.time() - t0) * 1000, 1)})
    return s


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='debug.py')
    ap.add_argument('cmd', choices=['analyze-expanded'])
    ap.add_argument('dir')
    ap.add_argument('--root', default='/')
    ap.add_argument('--depth', type=int, default=99)
    ap.add_argument('--packages', action='store_true')
    ap.add_argument('--ops-dir', default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                       'docs', 'research', 'ops'))
    ap.add_argument('--top', type=int, default=10)
    ap.add_argument('--max-items', type=int, default=MAX_ITEMS)
    ap.add_argument('--folder', default=None)
    ap.add_argument('--file', default=None)
    a = ap.parse_args(argv)
    s = analyze_expanded(a.dir, a.root, a.depth, a.packages, a.ops_dir, a.top, a.max_items, a.folder, a.file)
    sys.stdout.write(json.dumps(s, ensure_ascii=True, separators=(',', ':')))
    return 0


# ================================================================== TD side: records from live ops

def _optype(o):
    return str(_try(lambda: o.OPType, '') or '')


def _fam(o):
    return str(_try(lambda: o.family, '') or '')


def _is_comp(o):
    return bool(_try(lambda: o.isCOMP, False))


def _src_paths(o):
    out = []
    for c in _try(lambda: list(o.inputConnectors), []) or []:
        conns = _try(lambda: list(c.connections), []) or []
        out.append(_try(lambda: conns[0].owner.path) if conns else None)
    while out and out[-1] is None:
        out.pop()
    return out


def _n_outs(o):
    n = 0
    for c in _try(lambda: list(o.outputConnectors), []) or []:
        n += len(_try(lambda: list(c.connections), []) or [])
    return n


def _live_par(p, optype):
    name = _try(lambda: p.name, '')
    if not name:
        return None
    mode = mode_code(_try(lambda: p.mode, 'CONSTANT'))
    style = str(_try(lambda: p.style, '') or '')
    if not need_value(optype, name, mode, style):
        return None
    val = _try(lambda: p.val)
    if not keep_par(optype, name, mode, style, val):
        return None
    expr = _try(lambda: p.expr, '') if mode == 'e' else ''
    bind = _try(lambda: p.bindExpr, '') if mode == 'b' else ''
    ev = None
    if style in REF_STYLES or (mode != 'c' and style in FILE_STYLES):
        e = _try(lambda: p.eval())
        ev = e.path if hasattr(e, 'path') else (jval(e) if e not in (None, '') else None)
    exporter = None
    if mode == 'x':
        x = _try(lambda: p.exportOP)
        exporter = _try(lambda: x.path) if x is not None else None
    return par_rec(name, mode, val, style, expr, bind, ev, exporter)


def op_record(o, text_cap=TEXT_CAP):
    """A live op as an analysis record (read-only; never cooks). Mirrors _offline_rec plus runtime fields."""
    t = _optype(o)
    f = _fam(o)
    r = {'p': o.path, 't': t, 'f': f}
    if _is_comp(o):
        r['comp'] = True
        r['kids'] = len(_try(lambda: o.children, []) or [])
    ins = _src_paths(o)
    if ins:
        r['in'] = ins
    outs = _n_outs(o)
    if outs:
        r['outs'] = outs
    pars = []
    for p in _try(lambda: o.pars(), []) or []:
        pr = _live_par(p, t)
        if pr:
            pars.append(pr)
    if pars:
        r['pars'] = pars
    fl = []
    for k in ('display', 'render', 'bypass', 'lock'):
        if _try(lambda: getattr(o, k), False) is True:
            fl.append(k)
    if f == 'CHOP' and _try(lambda: o.export, False) is True:
        fl.append('export')
    if _try(lambda: o.viewer, False) is True:
        fl.append('viewer')
    if r.get('comp') and _try(lambda: o.allowCooking, True) is False:
        fl.append('parked')
    if fl:
        r['flags'] = fl
    if f == 'DAT':
        txt = _try(lambda: o.text, '') or ''
        if txt:
            cap = TABLE_TEXT_CAP if _try(lambda: o.isTable, False) else text_cap
            r['text'] = txt[:cap]
            r['text_len'] = len(txt)
    e = _try(lambda: o.errors(), '') or ''
    w = _try(lambda: o.warnings(), '') or ''
    s = _try(lambda: o.scriptErrors(), '') or ''
    if e:
        r['err'] = clip(e, MSG_CAP)
    if w:
        r['warn'] = clip(w, MSG_CAP)
    if s:
        r['serr'] = clip(s, MSG_CAP)
    cpu, gpu = _try(lambda: float(o.cpuCookTime), 0.0), _try(lambda: float(o.gpuCookTime), 0.0)
    if cpu:
        r['cpu'] = rnd(cpu)
    if gpu:
        r['gpu'] = rnd(gpu)
    c = _try(lambda: int(o.totalCooks))
    if c is not None:
        r['cooks'] = c
    caf = _try(lambda: int(o.cookAbsFrame))
    if caf is not None:
        r['caf'] = caf
    gm = _try(lambda: int(o.gpuMemory), 0)
    if gm:
        r['gmem'] = gm
    return r


def live_package_kind(o):
    if not _is_comp(o):
        return None
    cl = _try(lambda: o.par.clone.eval())
    cp = _try(lambda: cl.path) if cl is not None else None
    if cp and cp != o.path:
        return 'clone of {}'.format(cp)
    sc = _try(lambda: o.par.opshortcut.eval(), '')
    if sc:
        return 'op shortcut {}'.format(sc)
    et = str(_try(lambda: o.par.externaltox.eval(), '') or '')
    if 'palette' in et.lower():
        return 'palette {}'.format(os.path.basename(et))
    return None


def _mcp_path():
    f = G('comp_path')
    return _try(f, '/jazib_mcp') if f else '/jazib_mcp'


def walk_ops(root, depth=99, packages=False, mcp=False, skip=()):
    """Pre-order DFS by name: yields (op, package_kind or None). Root first (unless '/')."""
    me_ = _mcp_path().rstrip('/')
    skip = tuple(s.rstrip('/') for s in skip if s) + ('/sys',)  # TD's own system COMPs are never walked
    rp = _try(lambda: root.path, '/')
    if rp != '/':
        yield root, None
    stack = [(c, 1) for c in reversed(_sorted_kids(root))]
    while stack:
        o, lv = stack.pop()
        p = _try(lambda: o.path)
        if not p or not _try(lambda: o.valid, True):
            continue
        if not mcp and (p == me_ or p.startswith(me_ + '/')):
            continue
        if any(p == s or p.startswith(s + '/') for s in skip):
            continue
        kind = live_package_kind(o) if _is_comp(o) else None
        yield o, kind
        if lv < depth and (kind is None or packages) and _is_comp(o):
            stack.extend((c, lv + 1) for c in reversed(_sorted_kids(o)))


def _sorted_kids(o):
    return sorted(_try(lambda: list(o.children), []) or [], key=lambda c: str(_try(lambda: c.name, '')))


def _now():
    return time.perf_counter()


def _root_op(path):
    f = G('_op')
    if f is not None:
        return f(path)
    o = G('op')(path)
    if o is None:
        raise ValueError('no operator at {}'.format(path))
    return o


def _pending(frames, fn):
    return G('Pending')(frames, fn)


def _frame():
    return _try(lambda: int(G('absTime').frame))


def _build():
    a = G('app')
    return _try(lambda: '{}.{}'.format(str(a.version).split('.')[0], a.build), None)


def _runs():
    """Delayed run() scripts waiting now (td.runs; attribute names unconfirmed on 31550 -> best effort)."""
    td_ = G('td')
    rs = _try(lambda: list(getattr(td_, 'runs')), None)
    if rs is None:
        return {'available': False}
    out = []
    for r in rs[:50]:
        out.append({'source': clip(_try(lambda: r.source, '') or str(r), 160),
                    'frames': _try(lambda: r.remainingFrames), 'ms': _try(lambda: r.remainingMilliseconds),
                    'active': _try(lambda: r.active)})
    return {'available': True, 'count': len(rs), 'items': out}


def cmd_analyze(path='/', depth=99, include=None, limit=ANALYZE_LIMIT, offset=0, top=10, max_items=MAX_ITEMS,
                budget_ms=BUDGET_MS):
    """X-ray of any open project / COMP (read-only). Ops are enumerated depth-first by name; ops offset..offset+limit
    are read in detail, in chunks of budget_ms per frame (Pending) so TD keeps running; then analyze()."""
    root = _root_op(path)
    inc = set(include or [])
    limit = max(1, min(int(limit), 50000))
    offset = max(0, int(offset))
    budget = max(1.0, min(float(budget_ms), 50.0)) / 1000.0
    st = {'gen': walk_ops(root, int(depth), 'packages' in inc, 'mcp' in inc), 'paths': [], 'recs': [], 'pkgs': [],
          'n': 0, 'frames': 0, 't0': _now(), 'work_ms': 0.0, 'done': False, 'capped': False}
    folder = _try(lambda: G('project').folder, None)

    def step():
        st['frames'] += 1
        t_start = _now()
        end = t_start + budget
        for o, kind in st['gen']:
            p = _try(lambda: o.path)
            if p is None:
                continue
            st['paths'].append(p)
            i = st['n']
            st['n'] += 1
            if offset <= i < offset + limit:
                r = _try(lambda: op_record(o))
                if r is not None:
                    if kind:
                        r['pkg'] = kind
                        st['pkgs'].append({'p': p, 'kind': kind, 'kids': r.get('kids')})
                    st['recs'].append(r)
            if st['n'] >= ENUM_MAX:
                st['capped'] = True
                break
            if _now() > end:
                st['work_ms'] += (_now() - t_start) * 1000
                return _pending(1, step)
        st['work_ms'] += (_now() - t_start) * 1000
        return finish()

    def finish():
        notes = []
        if st['capped']:
            notes.append('enumeration stopped at {} ops'.format(ENUM_MAX))
        if 'packages' not in inc and st['pkgs']:
            notes.append('{} package COMPs (clones / op-shortcut packages / palette) listed, not entered: include '
                         '["packages"] enters them'.format(len(st['pkgs'])))
        s = analyze(st['recs'], root.path, int(top), int(max_items), paths=st['paths'], packages=st['pkgs'],
                    now_frame=_frame(), folder=folder, file_exists=os.path.exists, notes=notes)
        nxt = offset + limit if st['n'] > offset + limit else None
        s.update({'source': 'live', 'build': _build(), 'project': _try(lambda: G('project').name),
                  'folder': folder, 'total_ops': st['n'], 'offset': offset, 'limit': limit,
                  'page_ops': len(st['recs']), 'frames': st['frames'], 'work_ms': round(st['work_ms'], 1),
                  'ms': round((_now() - st['t0']) * 1000, 1), 'runs': _runs(),
                  'cook_rate': _try(lambda: G('project').cookRate)})
        if nxt is not None:
            s['next_offset'] = nxt
            s.setdefault('notes', []).append('page {}..{} of {} ops: call again with offset {} (refs to ops on '
                                             'other pages still resolve)'.format(offset, offset + limit, st['n'], nxt))
        return s
    return step()


# ================================================================== why: what drives this op / par

def _par_of(o, name):
    p = _try(lambda: o.par[name])
    if p is None:
        raise ValueError('{} has no parameter {!r}'.format(o.path, name))
    return p


def _live_resolve(ref, owner, is_comp):
    k = ref['kind']
    o = _try(lambda: G('op')(owner))
    if k == 'oshort':
        t = _try(lambda: getattr(G('op'), ref['arg']))
        return _try(lambda: t.path)
    if k == 'pshort':
        t = _try(lambda: getattr(o.parent, ref['arg'])) if o is not None else None
        return _try(lambda: t.path)
    cands = ref_candidates(ref, owner, is_comp)
    for c in cands:
        if _try(lambda: G('op')(c)) is not None:
            return c
    return cands[0] if cands else None


def _refs_live(o, pr):
    is_comp = _is_comp(o)
    out = []
    m, n = pr['m'], pr['n']
    if m in ('e', 'b'):
        for ref in parse_refs(pr.get('e', '')):
            if ref['kind'] in ('me', 'ops', 'iop', 'ipar'):
                continue
            if ref['kind'] == 'mod':
                out.append((None, '{} {} uses mod.{}'.format('expr' if m == 'e' else 'bind', n, ref['arg'])))
                continue
            tgt = _live_resolve(ref, o.path, is_comp)
            via = '{} {}'.format('expr' if m == 'e' else 'bind', n)
            if ref.get('par'):
                via += ' <- .par.' + ref['par']
            if ref.get('chan'):
                via += " <- ['{}']".format(ref['chan'])
            out.append((tgt, via))
    elif m == 'x':
        out.append((pr.get('x'), 'export -> ' + n))
    if pr.get('s') in REF_STYLES:
        ev = pr.get('ev')
        if isinstance(ev, str) and ev.startswith('/'):
            out.append((ev, 'ref par ' + n))
    return out


WRITE_RE = r'(\.val\s*=(?!=)|\s=(?!=)|\.expr\s*=|\.bindExpr\s*=|\.mode\s*=|\.pulse\(|\.default\s*=)'


def script_hits(texts, name, path, par=None, cap=50):
    """Pure: lines in DAT texts that write (or mention) an op / par. texts: [(dat path, text)].
    -> {'writes': [{dat, line, text}], 'mentions': [...]}"""
    writes, mentions = [], []
    pat_op = re.compile(r"""(op\(\s*['"][^'"]*\b{n}['"]\s*\)|{p}\b)""".format(n=re.escape(name), p=re.escape(path)))
    pat_par = re.compile(r'\.par\.{}\b'.format(re.escape(par))) if par else None
    pat_write = re.compile(r'\.par\.{}\b\s*'.format(re.escape(par)) + WRITE_RE) if par else \
        re.compile(r'(\.par\.\w+\s*' + WRITE_RE + r'|\.text\s*=(?!=)|\.appendRow\(|\.connect\(|\.destroy\(|\.cook\()')
    for dat, txt in texts:
        mentions_op = bool(pat_op.search(txt))
        for i, line in enumerate(txt.split('\n')):
            hit_op = pat_op.search(line)
            if par:
                if not pat_par.search(line):
                    continue
                if not (hit_op or mentions_op):
                    continue
                item = {'dat': dat, 'line': i + 1, 'text': clip(line.strip(), 200)}
                (writes if pat_write.search(line) else mentions).append(item)
            elif hit_op:
                item = {'dat': dat, 'line': i + 1, 'text': clip(line.strip(), 200)}
                (writes if pat_write.search(line) else mentions).append(item)
            if len(writes) + len(mentions) >= cap * 2:
                break
    return {'writes': writes[:cap], 'mentions': mentions[:cap], 'truncated': len(writes) > cap or len(mentions) > cap}


def cmd_why(path, par=None, depth=4, max_nodes=150, scope='/', scan_dats=True, max_dats=3000):
    """What drives this op (or one par): wired inputs, expressions / binds (op/par/channel refs), CHOP exports,
    OP-reference pars, recursively to depth; plus DAT scripts that write it (text search) and Execute DATs watching
    it. Read-only; bounded by max_nodes / max_dats."""
    o = _root_op(path)
    depth = max(1, min(int(depth), 12))
    max_nodes = max(5, min(int(max_nodes), 1000))
    seen = set()
    count = [0]
    notes = []

    def op_node(x, level, via):
        p = x.path
        n = {'p': p, 't': _optype(x), 'via': via}
        count[0] += 1
        if p in seen:
            n['seen'] = True
            return n
        seen.add(p)
        if level >= depth or count[0] >= max_nodes:
            n['more'] = True
            return n
        up = []
        for i, src in enumerate(_src_paths(x)):
            if src and count[0] < max_nodes:
                so = _try(lambda: G('op')(src))
                if so is not None:
                    up.append(op_node(so, level + 1, 'wire in{}'.format(i)))
        t = _optype(x)
        for p_ in _try(lambda: x.pars(), []) or []:
            pr = _live_par(p_, t)
            if not pr or pr['n'] in ('callbacks',) or (pr['m'] == 'c' and pr.get('s') not in REF_STYLES):
                continue
            for tgt, via2 in _refs_live(x, pr):
                if count[0] >= max_nodes:
                    break
                if tgt is None:
                    up.append({'p': None, 'via': via2})
                    continue
                to = _try(lambda: G('op')(tgt))
                if to is None:
                    up.append({'p': tgt, 'via': via2, 'missing': True})
                else:
                    up.append(op_node(to, level + 1, via2))
        if up:
            n['up'] = up
        return n

    tree = None
    par_info = None
    if par:
        p_ = _par_of(o, par)
        mode = mode_code(_try(lambda: p_.mode, 'CONSTANT'))
        pr = par_rec(p_.name, mode, _try(lambda: p_.eval()), str(_try(lambda: p_.style, '') or ''),
                     _try(lambda: p_.expr, '') if mode == 'e' else '', _try(lambda: p_.bindExpr, '') if mode == 'b' else '',
                     None, _try(lambda: p_.exportOP.path) if mode == 'x' else None)
        par_info = {'name': p_.name, 'mode': {'c': 'CONSTANT', 'e': 'EXPRESSION', 'x': 'EXPORT', 'b': 'BIND'}[mode],
                    'value': pr.get('v'), 'expr': pr.get('e'), 'export_from': pr.get('x'),
                    'default': jval(_try(lambda: p_.default)), 'custom': bool(_try(lambda: p_.isCustom, False))}
        if mode == 'x':
            par_info['export_source'] = clip(_try(lambda: str(p_.exportSource), ''), 120)
        tree = {'p': o.path, 't': _optype(o), 'par': p_.name, 'via': 'target', 'up': []}
        seen.add(o.path + '.par.' + p_.name)
        for tgt, via in _refs_live(o, dict(pr, s='')):
            to = _try(lambda: G('op')(tgt)) if tgt else None
            if to is None:
                tree['up'].append({'p': tgt, 'via': via, 'missing': tgt is not None})
            else:
                tree['up'].append(op_node(to, 1, via))
        if mode == 'c':
            notes.append('constant: nothing drives it in the network; scripts that set it are listed below')
    else:
        tree = op_node(o, 0, 'target')
    scripts, watchers = None, []
    if scan_dats:
        sc = _try(lambda: G('op')(scope)) or G('op')('/')
        dats = _try(lambda: list(sc.findChildren(type=G('td').DAT)), None)
        if dats is None:
            dats = [d for d in _try(lambda: list(sc.findChildren()), []) if _fam(d) == 'DAT']
        mcp = _mcp_path()
        dats = [d for d in dats if not d.path.startswith(mcp + '/')]
        if len(dats) > max_dats:
            notes.append('{} DATs in scope; scanned the first {}'.format(len(dats), max_dats))
            dats = dats[:max_dats]
        texts = []
        for d in dats:
            t = _optype(d)
            if t in EXEC_TYPES:
                w = EXEC_WATCH.get(t)
                tgt = _try(lambda: d.par[w].eval()) if w else None
                tl = tgt if isinstance(tgt, (list, tuple)) else [tgt]
                if any(_try(lambda: x.path) == o.path for x in tl if x is not None):
                    watchers.append({'dat': d.path, 't': t, 'active': bool(_try(lambda: d.par.active.eval(), True)),
                                     'pars': clip(_try(lambda: d.par.pars.eval(), ''), 80) if t == 'parameterexecuteDAT' else None})
            if _try(lambda: d.isTable, False):
                continue
            txt = _try(lambda: d.text, '') or ''
            if txt and (o.name in txt or o.path in txt):
                texts.append((d.path, txt[:TEXT_CAP]))
        scripts = script_hits(texts, o.name, o.path, par)
        scripts['dats_scanned'] = len(dats)
    r = {'path': o.path, 'type': _optype(o), 'tree': tree, 'nodes': count[0], 'truncated': count[0] >= max_nodes,
         'depth': depth}
    if par_info:
        r['par'] = par_info
    if scripts is not None:
        r['scripts'] = scripts
    if watchers:
        r['watchers'] = watchers
    if notes:
        r['notes'] = notes
    return r


# ================================================================== watch: live recorder

WATCH_MAX_S = 120.0
WATCH_EVENTS_CAP = 2000


def watch_new(meta):
    return {'meta': meta, 'samples': [], 'cooks0': {}, 'cooks': {}, 'ms': {}, 'pars0': {}, 'pars': {},
            'par_changes': {}, 'events': [], 'errs': {}, 'last': None, 'events_dropped': 0}


def watch_sample(st, s):
    """Pure: fold one sample into the state. s = {t (s since start), frame, cooks:{p: total}, cms:{p: last ms},
    pars:{key: val}, errs:{p: {'error','warning','script'}} (only ops checked this sample), err_checked:[p]}."""
    last = st['last']
    row = {'t': rnd(s['t'], 5), 'frame': s.get('frame')}
    if last is not None and s.get('frame') is not None and last.get('frame') is not None:
        dt = s['t'] - last['t']
        df = s['frame'] - last['frame']
        row['fps'] = rnd(df / dt, 4) if dt > 0 else None
    st['samples'].append(row)
    for p, n in (s.get('cooks') or {}).items():
        if p not in st['cooks0']:
            st['cooks0'][p] = n
            st['cooks'][p] = n
            continue
        d = n - st['cooks'][p]
        if d > 0:
            st['ms'][p] = st['ms'].get(p, 0.0) + d * float((s.get('cms') or {}).get(p) or 0.0)
        st['cooks'][p] = n
    for k, v in (s.get('pars') or {}).items():
        if k not in st['pars0']:
            st['pars0'][k] = v
            st['pars'][k] = v
            continue
        if v != st['pars'][k]:
            c = st['par_changes'].setdefault(k, {'changes': 0, 'first': st['pars0'][k], 'values': []})
            c['changes'] += 1
            c['last'] = v
            if len(c['values']) < 8:
                c['values'].append([row['t'], v])
            st['pars'][k] = v
    for p in s.get('err_checked') or []:
        now = (s.get('errs') or {}).get(p) or {}
        before = st['errs'].get(p) or {}
        for kind in ('error', 'warning', 'script'):
            a, b = before.get(kind) or '', now.get(kind) or ''
            if a == b:
                continue
            what = 'appeared' if b and not a else 'cleared' if a and not b else 'changed'
            if last is None and what == 'appeared':
                what = 'present'
            if len(st['events']) < WATCH_EVENTS_CAP:
                st['events'].append({'t': row['t'], 'p': p, 'kind': kind, 'what': what, 'msg': clip(b or a, 200)})
            else:
                st['events_dropped'] += 1
        st['errs'][p] = now
    st['last'] = row


def watch_summary(st, top=15, max_pars=60):
    """Pure: compact result of a recording."""
    smp = st['samples']
    fps = [x['fps'] for x in smp if x.get('fps') is not None]
    dur = smp[-1]['t'] - smp[0]['t'] if len(smp) > 1 else 0.0
    frames = (smp[-1]['frame'] - smp[0]['frame']) if len(smp) > 1 and smp[0].get('frame') is not None else None
    cook = []
    for p, n in st['cooks'].items():
        d = n - st['cooks0'].get(p, n)
        if d > 0:
            ms = st['ms'].get(p, 0.0)
            cook.append({'p': p, 'cooks': d, 'est_ms': rnd(ms), 'ms_per_s': rnd(ms / dur) if dur > 0 else None,
                         'cooks_per_s': rnd(d / dur, 3) if dur > 0 else None})
    cook.sort(key=lambda x: (-(x['est_ms'] or 0), -x['cooks']))
    changes = [dict(v, par=k) for k, v in st['par_changes'].items()]
    changes.sort(key=lambda x: -x['changes'])
    target = st['meta'].get('cook_rate')
    out = {
        'duration_s': rnd(dur, 4), 'samples': len(smp), 'frames': frames,
        'fps': {'avg': rnd(frames / dur, 4) if frames is not None and dur > 0 else None,
                'min': min(fps) if fps else None, 'max': max(fps) if fps else None, 'target': target,
                'below_target_samples': len([f for f in fps if target and f < 0.9 * float(target)])},
        'cooking_ops': len(cook), 'watched_ops': len(st['cooks']), 'top_cook': cook[:top],
        'est_cook_ms_per_s': rnd(sum(x['est_ms'] or 0 for x in cook) / dur) if dur > 0 else None,
        'par_changes': {'count': len(changes), 'watched': len(st['pars']), 'items': changes[:max_pars]},
        'events': st['events'][:200], 'events_count': len(st['events']) + st['events_dropped'],
        'errors_now': sorted(p for p, e in st['errs'].items() if e.get('error') or e.get('script')),
    }
    return out


def _watch_pars(o, t, max_left):
    """Pars worth sampling on one op: custom pars + pars not in CONSTANT mode + non-default constants (bounded)."""
    out = []
    for p in _try(lambda: o.pars(), []) or []:
        if len(out) >= max_left:
            break
        style = str(_try(lambda: p.style, '') or '')
        if style in ('Pulse', 'Momentary', 'Header', 'Sequence'):
            continue
        custom = bool(_try(lambda: p.isCustom, False))
        mode = mode_code(_try(lambda: p.mode, 'CONSTANT'))
        if custom or mode != 'c':
            out.append(p)
            continue
        if _try(lambda: p.isDefault, True) is False:
            out.append(p)
    return out


def _sval(v):
    if hasattr(v, 'path'):
        return v.path
    if isinstance(v, float):
        return rnd(v, 6)
    if isinstance(v, (int, bool)) or v is None:
        return v
    return clip(v, 80)


def cmd_watch(path='/', seconds=5.0, sample_hz=4.0, max_ops=3000, max_pars=400, budget_ms=BUDGET_MS,
              include=None, top=15):
    """Live recorder (read-only): cook-count deltas + estimated cook ms per op, par value changes (custom, non-constant
    and non-default pars, bounded), errors / warnings / script errors appearing and clearing, fps timeline (frame vs
    wall clock). Setup and every sample are bounded by budget_ms per frame; replies when seconds have passed."""
    root = _root_op(path)
    inc = set(include or [])
    seconds = max(0.5, min(float(seconds), WATCH_MAX_S))
    hz = max(0.5, min(float(sample_hz), 30.0))
    rate = _try(lambda: float(G('project').cookRate), 60.0) or 60.0
    every = max(1, int(round(rate / hz)))
    budget = max(1.0, min(float(budget_ms), 50.0)) / 1000.0
    meta = {'path': root.path, 'seconds': seconds, 'sample_hz': hz, 'frames_per_sample': every, 'cook_rate': rate,
            'build': _build(), 'max_ops': max_ops, 'max_pars': max_pars}
    st = watch_new(meta)
    w = {'gen': walk_ops(root, 99, 'packages' in inc, False), 'ops': [], 'pars': [], 'setup_frames': 0,
         'cursor': 0, 't0': None, 'capped': False}

    def setup():
        w['setup_frames'] += 1
        end = _now() + budget
        for o, _k in w['gen']:
            if len(w['ops']) >= int(max_ops):
                w['capped'] = True
                break
            t = _optype(o)
            w['ops'].append(o)
            left = int(max_pars) - len(w['pars'])
            if left > 0:
                for p in _watch_pars(o, t, left):
                    w['pars'].append((o.path + ':' + p.name, p))
            if _now() > end:
                return _pending(1, setup)
        w['t0'] = _now()
        return sample()

    def sample():
        t_end = _now() + budget
        s = {'t': _now() - w['t0'], 'frame': _frame(), 'cooks': {}, 'cms': {}, 'pars': {}, 'errs': {},
             'err_checked': []}
        for o in w['ops']:
            if not _try(lambda: o.valid, True):
                continue
            p = _try(lambda: o.path)
            n = _try(lambda: int(o.totalCooks))
            if p is None or n is None:
                continue
            s['cooks'][p] = n
            s['cms'][p] = _try(lambda: float(o.cpuCookTime), 0.0) + _try(lambda: float(o.gpuCookTime), 0.0)
        for k, p in w['pars']:
            v = _try(lambda: p.eval(), '<gone>')
            s['pars'][k] = _sval(v)
        # errors: a rotating slice, as many as the budget allows (every op at least once per ~second on small nets)
        ops = w['ops']
        if ops:
            i, checked = w['cursor'], 0
            while checked < len(ops) and (_now() < t_end or checked < 50):
                o = ops[i % len(ops)]
                i += 1
                checked += 1
                p = _try(lambda: o.path)
                if p is None:
                    continue
                e = {}
                for kind, fn in (('error', 'errors'), ('warning', 'warnings'), ('script', 'scriptErrors')):
                    m = _try(lambda: getattr(o, fn)(), '') or ''
                    if m:
                        e[kind] = clip(m, MSG_CAP)
                s['errs'][p] = e
                s['err_checked'].append(p)
            w['cursor'] = i % len(ops)
        watch_sample(st, s)
        if s['t'] >= seconds:
            return finish()
        return _pending(every, sample)

    def finish():
        out = watch_summary(st, int(top))
        out['meta'] = dict(meta, setup_frames=w['setup_frames'], ops=len(w['ops']), pars=len(w['pars']),
                           capped=w['capped'])
        out['timeline'] = st['samples']
        out['par_changes_all'] = [dict(v, par=k) for k, v in st['par_changes'].items()][:2000]
        if w['capped']:
            out['notes'] = ['watched the first {} ops (max_ops)'.format(max_ops)]
        return out
    return setup()


# ================================================================== debug panel (self-contained Container COMP)

PANEL_DEFAULT = '/project1/debug'
PANEL_W, VIEW_H, GRAPH_H = 440, 520, 110
PANEL_H = VIEW_H + GRAPH_H
PANEL_RT_FILE = 'debug_panel_rt.py'
PANEL_TABLES = {'top_ops': ['path', 'ms', 'cooks/s', 'type'], 'errs': ['path', 'kind', 'message'],
                'acts': ['time', 'tool', 'what', 'ok'], 'fps_hist': ['fps']}
# text view: one Text TOP per colour, fed by a spec table (x, y, text) that rt rewrites only on change (T-72)
PANEL_TEXT = (('head', (1.0, 0.82, 0.35)), ('title', (0.95, 0.68, 0.2)), ('body', (0.86, 0.86, 0.86)),
              ('err', (1.0, 0.42, 0.38)))
PANEL_FONT, PANEL_FONT_PX = 'Menlo', 12
# ops of the first panel (List COMPs, Perform CHOP graph): removed on a rebuild, through safe_destroy (T-70)
PANEL_OBSOLETE = ('header', 'header_callbacks', 'perform', 'fps_sel', 'fps_trail', 'top_list', 'err_list',
                  'act_list', 'top_list_callbacks', 'err_list_callbacks', 'act_list_callbacks', 'list_cb')
PANEL_CLICK = '''# debug panel: a left click on the text view focuses that row's op (rt.click maps v to the line).
def onOffToOn(panelValue):
    c = parent()
    c.op('rt').module.click(c, float(panelValue.owner.panel.v))
    return
'''
PANEL_TICK = '''# debug panel: every frame a small slice of ops is read (Slice par, time-capped); Refreshhz the panel refreshes,
# one phase per frame; the text view is redrawn only while the window is open and only what changed.
def onFrameStart(frame):
    op('rt').module.tick(parent())
    return
'''


def panel_rt_text():
    p = os.path.join(HERE, PANEL_RT_FILE)
    with open(p, 'r', encoding='utf-8') as f:
        t = f.read()
    t.encode('ascii')
    compile(t, p, 'exec')
    return t, p


def panel_stages(c):
    st = [('Runtime', 'process', ['rt', 'tick', 'click'],
           'rt = td/debug_panel_rt.py; tick: real frame times + a slice of ops per frame; publishes staggered'),
          ('Data', 'note', ['top_ops', 'errs', 'acts', 'fps_hist'],
           'top cook ops, current errors, recent MCP actions (logs/), real fps per 0.25 s'),
          ('View', 'input', ['fps_chop'] + ['sp_' + k for k, _c in PANEL_TEXT] + ['tx_' + k for k, _c in PANEL_TEXT]
           + ['view_bg', 'zk_bg_glsl', 'zk_bg', 'view_comp', 'view', 'zk_graph_glsl', 'zk_graph'],
           'spec tables -> one Text TOP per colour -> composite (cooks only on change, never while closed); '
           'zk_* = zkit skin (static band bg, GLSL fps graph)'),
          ('Panel', 'control', ['fps_graph', 'table_view', 'debug_window'],
           'click a row: the network editor jumps to that op')]
    return [{'title': t, 'role': r, 'ops': [n for n in ops if c.op(n) is not None], 'body': b}
            for t, r, ops, b in st if any(c.op(n) is not None for n in ops)]


def _set(o, name, value, notes):
    if o is None:
        return
    if isinstance(value, dict) and 'expr' in value and 'mode' not in value:
        value = dict(value, mode='EXPRESSION')
    try:
        plans, warns = G('_plan_pars')(o, {name: value})
        G('_apply_plans')(plans)
        notes.extend('{}.{}'.format(o.name, w) for w in warns)
    except Exception as e:
        notes.append('{}.{} not set: {}'.format(o.name, name, str(e)[:120]))


def _close_window(c):
    w = c.op('debug_window')
    if w is not None and _try(lambda: w.isOpen, False):
        _try(lambda: w.par.winclose.pulse())
        return True
    return False


def _kit_hook(c, style, notes):
    """Later theming: builders/zkit.py may define style_debug_panel(comp); style 'zkit' calls it when present."""
    if style != 'zkit':
        return None
    f = os.path.join(os.path.dirname(HERE), 'builders', 'zkit.py')
    if not os.path.isfile(f):
        notes.append('style zkit: builders/zkit.py not found; plain panel kept')
        return False
    ns = {'__name__': 'zkit_for_debug', 'op': G('op'), 'td': G('td'), 'safe_destroy': G('safe_destroy')}
    try:
        with open(f, 'r', encoding='utf-8') as fh:
            exec(compile(fh.read(), f, 'exec'), ns)
    except Exception as e:
        notes.append('style zkit: loading builders/zkit.py failed: {}'.format(str(e)[:160]))
        return False
    fn = ns.get('style_debug_panel')
    if fn is None:
        notes.append('style zkit: builders/zkit.py has no style_debug_panel(comp) yet; plain panel kept')
        return False
    fn(c)
    return True


def _reopen_later(win, td_, frames=10):
    """Reopen after safe_destroy's deferred destroys (3 frames) are done (T-70); falls back to a direct pulse."""
    if _try(lambda: td_.run("o = op({!r})\nif o is not None: o.par.winopen.pulse()".format(win.path),
                            delayFrames=frames), 'no') == 'no':
        _try(lambda: win.par.winopen.pulse())


def cmd_debug_panel_build(path=PANEL_DEFAULT, scope='/project1', open_window=False, style='plain', slice_ops=None):
    """Build or refresh in place a self-contained debug Container COMP: real-fps graph, top-10 cook ops, current
    errors, recent MCP actions; a row click focuses the op. Rebuild = refill in place (T-70): the container is never
    destroyed, its window is closed first and reopened 10 frames later, wrong-type / obsolete children go through
    safe_destroy. Holds 60 fps with the window open (T-72): text view = spec tables -> Text TOPs, no List COMPs."""
    rt_text, rt_src = panel_rt_text()
    if not isinstance(path, str) or not path.startswith('/') or path.count('/') < 2:
        raise ValueError('path must be an absolute COMP path like /project1/debug, got {!r}'.format(path))
    parent_path_, name = path.rsplit('/', 1)
    par_ = _root_op(parent_path_ or '/')
    if not G('valid_op_name')(name):
        raise ValueError('bad operator name {!r}'.format(name))
    td_ = G('td')
    c = par_.op(name)
    if c is not None and _optype(c) != 'containerCOMP':
        raise ValueError('{} exists and is a {}, not a Container COMP'.format(c.path, _optype(c)))
    created = c is None
    if created:
        c = par_.create(td_.containerCOMP, name)
        xy = _try(lambda: G('_auto_xy')(par_, c))
        if xy:
            _try(lambda: setattr(c, 'nodeX', xy[0]))
            _try(lambda: setattr(c, 'nodeY', xy[1]))
    c.allowCooking = True
    c.comment = 'jazib-td debug panel (self-contained; td/debug_panel_rt.py, refreshed by td_debug_panel)'
    notes, made, removed = [], [], []
    was_open = _close_window(c)

    def child(cls_name, nm, viewer=True):
        o = c.op(nm)
        if o is not None and _optype(o) != cls_name:
            G('safe_destroy')(o)
            notes.append('replaced {} (was a {})'.format(nm, _optype(o)))
            o = None
        if o is None:
            cls = getattr(td_, cls_name, None)
            if cls is None:
                notes.append('{} not available in this build: {} not built'.format(cls_name, nm))
                return None
            try:
                o = c.create(cls, nm)
            except Exception as e:
                notes.append('{} could not be created: {}'.format(nm, str(e)[:160]))
                return None
            made.append(nm)
        if _fam(o) in ('TOP', 'CHOP', 'DAT'):
            _try(lambda: setattr(o, 'viewer', viewer))
        return o

    for k, v in (('w', PANEL_W), ('h', PANEL_H)):
        _set(c, k, v, notes)
    rt = child('textDAT', 'rt')
    rt.text = rt_text
    tick = child('executeDAT', 'tick')
    tick.text = PANEL_TICK
    _set(tick, 'framestart', True, notes)
    _set(tick, 'active', {'expr': 'parent().par.Active'}, notes)
    for tn, hdr in PANEL_TABLES.items():
        t = child('tableDAT', tn)
        if t is not None and (_try(lambda: t.numRows, 0) == 0 or created):
            _try(lambda: t.clear())
            _try(lambda: t.appendRow(hdr))
    fchop = child('dattoCHOP', 'fps_chop')
    if fchop is not None:
        for k, v in (('dat', 'fps_hist'), ('output', {'menu': 'chanpercol'}), ('firstrow', {'menu': 'names'}),
                     ('firstcolumn', {'menu': 'values'})):
            _set(fchop, k, v, notes)
    graph = child('opviewerCOMP', 'fps_graph')
    if graph is not None:   # re-pointed before the old trail goes (T-70: nothing shown is destroyed under the UI)
        _set(graph, 'opviewer', {'expr': "parent().op('fps_chop')"}, notes)
    # text view: spec tables -> Text TOPs (one colour each) -> composite over a dark background -> view
    texts = []
    for kind, col in PANEL_TEXT:
        sp = child('tableDAT', 'sp_' + kind)
        if sp is not None and (_try(lambda: sp.numRows, 0) == 0 or created):
            _try(lambda: sp.clear())
            _try(lambda: sp.appendRow(['x', 'y', 'text']))
        tx = child('textTOP', 'tx_' + kind, viewer=False)
        texts.append(tx)
        for k, v in (('specdat', 'sp_' + kind), ('text', ''), ('font', PANEL_FONT), ('fontsizexunit', {'menu': 'pixels'}),
                     ('fontsizex', PANEL_FONT_PX), ('alignx', {'menu': 'left'}), ('aligny', {'menu': 'bottom'}),
                     ('positionunit', {'menu': 'pixels'}), ('outputresolution', {'menu': 'custom'}),
                     ('resolutionw', PANEL_W), ('resolutionh', VIEW_H), ('bgalpha', 0),
                     ('fontcolorr', col[0]), ('fontcolorg', col[1]), ('fontcolorb', col[2])):
            _set(tx, k, v, notes)
    bg = child('constantTOP', 'view_bg', viewer=False)
    for k, v in (('outputresolution', {'menu': 'custom'}), ('resolutionw', PANEL_W), ('resolutionh', VIEW_H),
                 ('colorr', 0.08), ('colorg', 0.08), ('colorb', 0.09), ('alpha', 1)):
        _set(bg, k, v, notes)
    comp = child('compositeTOP', 'view_comp', viewer=False)
    if comp is not None:
        _set(comp, 'operand', {'menu': 'over'}, notes)
        for i, src in enumerate([t for t in texts if t is not None] + [bg]):
            _try(lambda: comp.inputConnectors[i].connect(src))
    view = child('nullTOP', 'view', viewer=False)
    if view is not None and comp is not None:
        _try(lambda: view.inputConnectors[0].connect(comp))
    tv = child('containerCOMP', 'table_view')
    click = child('panelexecuteDAT', 'click')
    if click is not None:
        click.text = PANEL_CLICK
        for k, v in (('panels', 'table_view'), ('panelvalue', 'lselect'), ('offtoon', True), ('whileon', False),
                     ('ontooff', False), ('valuechange', False)):
            _set(click, k, v, notes)
    win = child('windowCOMP', 'debug_window')
    for o, xywh in ((graph, (0, VIEW_H, PANEL_W, GRAPH_H)), (tv, (0, 0, PANEL_W, VIEW_H))):
        for k, v in zip(('x', 'y', 'w', 'h'), xywh):
            _set(o, k, v, notes)
    if tv is not None:
        _set(tv, 'top', 'view', notes)
    for nm in PANEL_OBSOLETE:   # window is closed above; safe_destroy also closes/moves anything showing it
        o = c.op(nm)
        if o is not None:
            G('safe_destroy')(o)
            removed.append(nm)
    if win is not None:
        for k, v in (('winop', {'expr': 'parent()'}), ('title', 'jazib-td debug'), ('size', {'menu': 'custom'}),
                     ('winw', PANEL_W), ('winh', PANEL_H)):
            _set(win, k, v, notes)
    logs = os.path.join(os.path.dirname(HERE), 'logs')
    G('cmd_custom_pars')(c.path, 'Debug', [
        {'name': 'Active', 'label': 'Active', 'style': 'Toggle', 'default': True},
        {'name': 'Scope', 'label': 'Scope (COMP to watch)', 'style': 'Str', 'default': scope},
        {'name': 'Refreshhz', 'label': 'Refresh (Hz)', 'style': 'Float', 'default': 2, 'min': 0.5, 'max': 10,
         'normMin': 0.5, 'normMax': 10, 'clampMin': True},
        {'name': 'Slice', 'label': 'Ops read per frame', 'style': 'Int', 'default': 30, 'min': 5, 'max': 2000,
         'normMin': 10, 'normMax': 400, 'clampMin': True},
        {'name': 'Logdir', 'label': 'MCP logs folder', 'style': 'Str', 'default': logs}])
    if slice_ops is not None:
        _try(lambda: setattr(c.par.Slice, 'val', int(slice_ops)))
    if created or scope != '/project1':
        _try(lambda: setattr(c.par.Scope, 'val', scope))
    if created:
        _try(lambda: setattr(c.par.Logdir, 'val', logs))
    m = _try(lambda: rt.module)
    if m is not None:
        _try(lambda: m.reset(c))
    styled = _kit_hook(c, style, notes)
    lay = _try(lambda: G('layout_stages')(c, panel_stages(c), True), None)
    if (open_window or was_open) and win is not None:
        _reopen_later(win, td_, 10 if (removed or was_open) else 1)
    r = {'path': c.path, 'created': created, 'new_ops': made, 'removed_ops': removed, 'runtime_file': rt_src,
         'scope': scope, 'layout': {'ok': lay.get('ok')} if isinstance(lay, dict) else None, 'styled': styled,
         'window_open': bool(open_window or was_open),
         'parent_layout': G('_arrange')(par_) if created else None,
         'hint': 'check the cost with the window OPEN: rt stats() real_fps_2s / slow_2s / tick ms (T-72); '
                 'Active off parks it'}
    if notes:
        r['notes'] = notes
    return r


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
