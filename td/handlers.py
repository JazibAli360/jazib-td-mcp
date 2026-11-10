"""Jazib MCP for TouchDesigner -- request handlers (protocol v1, see ../docs/PROTOCOL.md).

Lives in the Text DAT /jazib_mcp/handlers; the source of truth is td/handlers.py on disk (the `reload` command
re-reads it). The WebSocket DAT callbacks (td/callbacks.py) forward every event here.

Layout: pure-Python helpers first (no TD calls, unit-tested outside TD with a stub `td` module), then one function
per PROTOCOL command (cmd_<name>), then connection handling. Pending delayed replies (errors / screenshot /
exec frames>0) live in module globals; a reload drops them and the MCP sees a timeout, as the protocol says.

ASCII only (td-port LEARNINGS rule 1).
"""
import ast
import builtins
import contextlib
import fnmatch
import io
import json
import math
import numbers
import os
import re
import secrets
import time
import traceback

try:
    import td  # only importable inside TouchDesigner (tests inject a stub)
except ImportError:  # pragma: no cover - plain Python without the stub
    td = None
if td is not None:
    from td import *  # noqa: F401,F403 -- an imported module does not see TD's globals (LEARNINGS)

PROTOCOL = 1
COMP_PATH = '/jazib_mcp'
DEFAULT_HANDLERS_FILE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/td/handlers.py'
BRIDGE_PORT = 9335  # default; the COMP's Bridgeport par (td/install.py, JTD_BRIDGE_PORT) overrides it (T-83)
RECONNECT_SILENCE_S = 70.0  # bridge pings every 20 s; this much silence on an "open" socket = dead link

# ------------------------------------------------------------------ module state (dropped by a reload)

_PENDING = {}      # id -> {'send': fn, 'finish': fn}
_EXEC_NS = {}      # persistent namespace for exec (survives between calls, not reloads)
_CONN = {'connected': False, 'since': None, 'last_rx': None, 'phase': 'idle', 'attempts': 0}
_CTX = {'comp_path': COMP_PATH}
_runner = None     # tests replace this: fn(script_text, delay_frames)


# ================================================================== pure helpers (no TD calls)

def is_op(v):
    """True for a TD OP (or anything that looks like one in the tests)."""
    cls = getattr(td, 'OP', None) if td is not None else None
    if isinstance(cls, type):
        try:
            if isinstance(v, cls):
                return True
        except Exception:
            pass
    return hasattr(v, 'path') and hasattr(v, 'OPType') and not isinstance(v, type)


def to_json(v, _depth=0):
    """A value made JSON-safe: numbers, strings, bools, None, lists, dicts; an OP -> its path; else repr."""
    if v is None or isinstance(v, (bool, str)):
        return v
    if isinstance(v, numbers.Integral):
        return int(v)
    if isinstance(v, numbers.Real):
        f = float(v)
        return f if math.isfinite(f) else repr(f)
    if is_op(v):
        return v.path
    if _depth > 20:
        return repr(v)
    if isinstance(v, (list, tuple)):
        return [to_json(x, _depth + 1) for x in v]
    if isinstance(v, dict):
        return {str(k): to_json(x, _depth + 1) for k, x in v.items()}
    return repr(v)


def dumps(obj):
    return json.dumps(to_json(obj), allow_nan=False, ensure_ascii=True, separators=(',', ':'))


CUSTOM_NAME_RE = re.compile(r'^[A-Z][a-z0-9]*$')
OP_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def valid_custom_name(name):
    """TD custom parameter names: one capital letter, then only lowercase letters or digits."""
    return isinstance(name, str) and bool(CUSTOM_NAME_RE.match(name))


def valid_op_name(name):
    return isinstance(name, str) and bool(OP_NAME_RE.match(name))


def match_menu(names, labels, wanted):
    """(menu name or None, warning or None). Exact name/label match (case-insensitive) first, then a loose
    contains-match ignoring spaces. Idea from td-port/lib/tdport.py set_menu (copied, not imported)."""
    names = [str(n) for n in names]
    labels = [str(l) for l in labels] if labels is not None else []
    labels = labels + names[len(labels):]
    w = str(wanted).lower()
    for n, l in zip(names, labels):
        if n.lower() == w or l.lower() == w:
            return n, None
    wl = w.replace(' ', '')
    if wl:
        for n, l in zip(names, labels):
            if wl in n.lower() or wl in l.lower().replace(' ', ''):
                return n, None
    return None, 'no menu entry matches {!r} (names {})'.format(wanted, names)


def mode_name(mode):
    """'CONSTANT' from ParMode.CONSTANT (or from the string 'ParMode.CONSTANT')."""
    n = getattr(mode, 'name', None)
    if isinstance(n, str):
        return n
    return str(mode).split('.')[-1]


def values_differ(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) != bool(b)
    if isinstance(a, numbers.Real) and isinstance(b, numbers.Real):
        return abs(float(a) - float(b)) > 1e-9 * max(1.0, abs(float(a)), abs(float(b)))
    return a != b


def par_differs(mode, val, default):
    """Shown by `info` with allPars=false: a non-constant mode, or a value away from its default."""
    return mode_name(mode) != 'CONSTANT' or values_differ(val, default)


SPEC_KEYS = ('val', 'expr', 'bindExpr', 'mode', 'menu')
MODES = ('CONSTANT', 'EXPRESSION', 'EXPORT', 'BIND')


def plan_par_set(name, spec, is_menu=False, is_pulse=False, menu_names=(), menu_labels=()):
    """Actions for one set_pars entry, decided before anything changes.
    Returns (actions, warnings); actions are (kind, value) with kind in pulse/val/menuIndex/expr/bindExpr/mode.
    Raises ValueError for a malformed spec."""
    actions, warnings = [], []
    if isinstance(spec, dict):
        bad = [k for k in spec if k not in SPEC_KEYS]
        if bad:
            raise ValueError('{}: unknown keys {} (use {})'.format(name, bad, list(SPEC_KEYS)))
        spec = dict(spec)
    else:
        spec = {'val': spec}
    if 'menu' in spec:
        if not is_menu:
            warnings.append('{}: not a menu parameter; menu {!r} ignored'.format(name, spec['menu']))
        else:
            hit, warn = match_menu(menu_names, menu_labels, spec['menu'])
            if hit is None:
                warnings.append('{}: {}'.format(name, warn))
            else:
                actions.append(('val', hit))
    if 'val' in spec:
        v = spec['val']
        if is_pulse:
            if v is True or v == 1:
                actions.append(('pulse', None))
            else:
                warnings.append('{}: pulse parameter only takes true; {!r} ignored'.format(name, v))
        elif is_menu and isinstance(v, str) and v not in [str(n) for n in menu_names]:
            hit, warn = match_menu(menu_names, menu_labels, v)
            if hit is None:
                warnings.append('{}: {}'.format(name, warn))
            else:
                actions.append(('val', hit))
        elif is_menu and isinstance(v, int) and not isinstance(v, bool):
            actions.append(('menuIndex', v))
        else:
            actions.append(('val', v))
    if 'expr' in spec:
        actions.append(('expr', str(spec['expr'])))
    if 'bindExpr' in spec:
        actions.append(('bindExpr', str(spec['bindExpr'])))
        if 'mode' not in spec:
            spec['mode'] = 'BIND'
    if 'mode' in spec:
        m = str(spec['mode']).upper()
        if m not in MODES:
            raise ValueError('{}: mode {!r} is not one of {}'.format(name, spec['mode'], list(MODES)))
        actions.append(('mode', m))
    return actions, warnings


HEX_RE = re.compile(r'^#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$')


def hex_rgba(s):
    """'#rrggbb' / '#rrggbbaa' -> (r, g, b, a or None) as 0..1 floats (value/255, 6 digits); anything else -> None.
    Only with the '#': a bare 'ff0000' stays a plain string (a Str par may hold it)."""
    m = HEX_RE.match(s.strip()) if isinstance(s, str) else None
    if m is None:
        return None
    h = m.group(1)
    vals = [round(int(h[i:i + 2], 16) / 255.0, 6) for i in (0, 2, 4)]
    a = round(int(m.group(2), 16) / 255.0, 6) if m.group(2) else None
    return vals[0], vals[1], vals[2], a


def rgb_hex(r, g, b, a=None):
    """0..1 floats -> '#rrggbb' (+aa): rounded, not truncated (a round trip never drifts a level), clamped."""
    def b8(v):
        return max(0, min(255, int(round(float(v) * 255.0))))
    return '#' + ''.join('{:02x}'.format(b8(v)) for v in ((r, g, b) if a is None else (r, g, b, a)))


def colour_members(name, has):
    """The r/g/b par names (+ alpha name or None) of a colour group, or None. has(name) -> bool. Accepts the group
    name (constantTOP 'color' -> colorr colorg colorb + alpha; 'bgcolor' -> bgalpha; custom 'Tint' -> Tintr.. Tinta)
    or a member name ('colorr')."""
    bases = [name]
    for suf in ('alpha', 'r', 'g', 'b', 'a'):  # any member name: colorg / Tintb / Tinta work like colorr (QC 26 Oct)
        if len(name) > len(suf) and name.endswith(suf):
            bases.append(name[:-len(suf)])
    for b in bases:
        if b and all(has(b + s) for s in 'rgb'):
            cands = [b + 'a', b + 'alpha']
            for suf in ('color', 'col'):
                if b.lower().endswith(suf):
                    cands.append(b[:-len(suf)] + 'alpha')
            return [b + 'r', b + 'g', b + 'b'], next((c for c in cands if c and has(c)), None)
    return None


# ------------------------------------------------------------------ layout (pure; docs/research/G_network_layout.md)
# Node units: nodeX/nodeY = lower-left corner, y grows UP. Default tiles (live, 2025.31550): TOP/CHOP/DAT/SOP/MAT
# 130x90, COMP 160x130. Flow is left to right; columns by wire depth; the spine (input 0 back from each sink) on one
# row; side inputs on rows below; separate streams stacked as bands: CHOP, DAT, TOP/SOP/POP/MAT, COMP.

GAP_X, GAP_Y, BAND_GAP, DOCK_GAP = 95, 60, 120, 30
SINGLES_PER_ROW = 6
FAM_BAND = {'CHOP': 0, 'DAT': 1, 'TOP': 2, 'SOP': 2, 'POP': 2, 'MAT': 2, 'COMP': 3}


def snap(v, step=5):
    return int(round(float(v) / step) * step)


def rects_overlap(a, b):
    """a, b = (x, y, w, h)."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def free_spot(rects, x, y, w, h, step_down=None):
    """First (x, y') at or below y where a w x h tile hits none of rects (steps down by h + GAP_Y)."""
    step = step_down or (h + GAP_Y)
    for _ in range(500):
        if not any(rects_overlap((x, y, w, h), r) for r in rects):
            return snap(x), snap(y)
        y -= step
    return snap(x), snap(y)


def dock_extra(docks):
    """Height a host's row needs below it for its docked ops (docks = [(w, h), ...])."""
    return (max(h for _, h in docks) + DOCK_GAP) if docks else 0


def dock_offsets(host_xy, docks):
    """Positions for docked ops: a row under the host, left-aligned, DOCK_GAP apart."""
    x, y = host_xy
    out, cx = [], x
    for w, h in docks:
        out.append((snap(cx), snap(y - h - DOCK_GAP)))
        cx += w + DOCK_GAP
    return out


def plan_flow(nodes, edges, x0=0, y0=0):
    """nodes: {id: {'w', 'h', 'fam', 'docks': [(w, h)]}}; edges: [(src, dst, inIndex)] between ids in nodes.
    Returns {id: (x, y)}. Feedback (cycles) is ignored for depth; every node gets a spot, none overlap."""
    ids = sorted(nodes)
    ins = {i: [] for i in ids}
    outs = {i: [] for i in ids}
    for a, b, k in edges:
        if a in nodes and b in nodes and a != b:
            ins[b].append((k, a))
            outs[a].append(b)
    for i in ids:
        ins[i].sort()
    depth, state = {}, {}

    def dfs(n):
        if n in depth:
            return depth[n]
        if state.get(n) == 1:
            return -1  # back edge (feedback loop): ignored
        state[n] = 1
        d = 0
        for _, a in ins[n]:
            da = dfs(a)
            if da >= 0:
                d = max(d, da + 1)
        state[n] = 2
        depth[n] = d
        return d
    for n in ids:
        dfs(n)
    # sources sit just left of their nearest consumer (a mask feeding a late composite stays next to it)
    for n in ids:
        if not ins[n] and outs[n]:
            want = min(depth[o] for o in outs[n]) - 1
            if want > depth[n]:
                depth[n] = want
    # streams = weakly connected components
    seen, streams = set(), []
    for n in ids:
        if n in seen:
            continue
        stack, grp = [n], []
        while stack:
            a = stack.pop()
            if a in seen:
                continue
            seen.add(a)
            grp.append(a)
            stack += [x for _, x in ins[a]] + outs[a]
        streams.append(sorted(grp))

    def sink_of(g):
        return max(g, key=lambda n: (depth[n], -len(outs[n]), n))
    streams.sort(key=lambda g: (FAM_BAND.get(nodes[sink_of(g)]['fam'], 9), sink_of(g)))
    # unwired single ops (module COMPs, lone DATs) go in tidy rows under the wired streams, not one tall column
    singles = [g[0] for g in streams if len(g) == 1 and not ins[g[0]] and not outs[g[0]]]
    streams = [g for g in streams if not (len(g) == 1 and g[0] in singles)]
    pos = {}
    y_top = y0
    for g in streams:
        gs = set(g)
        row, used = {}, set()

        def claim(n, want):
            r = want
            while (depth[n], r) in used:
                r += 1
            used.add((depth[n], r))
            row[n] = r
            return r
        # walk back from sinks: input 0 keeps the row, other inputs take the next free rows
        sinks = sorted([n for n in g if not [o for o in outs[n] if o in gs]], key=lambda n: (-depth[n], n))
        nxt = 0
        for sk in sinks:
            base = claim(sk, nxt)
            todo = [(sk, base)]
            while todo:
                n, r = todo.pop(0)
                for idx, (_, a) in enumerate(ins[n]):
                    if a in row or a not in gs or depth[a] >= depth[n]:
                        continue
                    todo.append((a, claim(a, r if idx == 0 else r + 1)))
            nxt = max(r for _, r in used) + 1
        for n in g:  # anything left (pure cycles)
            if n not in row:
                claim(n, 0)
        nrows = max(row.values()) + 1
        heights = []
        for r in range(nrows):
            members = [n for n in g if row[n] == r]
            heights.append(max(nodes[n]['h'] + dock_extra(nodes[n].get('docks')) for n in members) if members else 0)
        colw = {}
        for n in g:
            d = nodes[n].get('docks') or []
            span = sum(w for w, _ in d) + DOCK_GAP * max(0, len(d) - 1)
            colw[depth[n]] = max(colw.get(depth[n], 0), nodes[n]['w'], span)
        colx, x = {}, x0
        for c in sorted(colw):
            colx[c] = x
            x += colw[c] + GAP_X
        rowy, y = [], y_top
        for r in range(nrows):
            top_h = max([nodes[n]['h'] for n in g if row[n] == r] or [0])
            rowy.append(y - top_h)
            y -= heights[r] + GAP_Y
        for n in g:
            pos[n] = (snap(colx[depth[n]]), snap(rowy[row[n]]))
        y_top = y - (BAND_GAP - GAP_Y)
    bands = {}
    for n in singles:
        bands.setdefault(FAM_BAND.get(nodes[n]['fam'], 9), []).append(n)
    for b in sorted(bands):
        row = sorted(bands[b])
        for i in range(0, len(row), SINGLES_PER_ROW):
            chunk = row[i:i + SINGLES_PER_ROW]
            h = max(nodes[n]['h'] + dock_extra(nodes[n].get('docks')) for n in chunk)
            x = x0
            for n in chunk:
                pos[n] = (snap(x), snap(y_top - nodes[n]['h']))
                x += nodes[n]['w'] + GAP_X
            y_top -= h + GAP_Y
        y_top -= BAND_GAP - GAP_Y
    return pos


def layout_check(nodes, edges, pos):
    """Problems in a layout: overlapping pairs, wires running right-to-left (feedback excluded), ops at (0,0).
    A back wire into or out of a Feedback TOP (node 'fb'), or out of the op its `top` par names (node 'fb_src'), is
    the loop by design and is not reported (T-163)."""
    ids = sorted(pos)
    rect = {n: (pos[n][0], pos[n][1], nodes[n]['w'], nodes[n]['h']) for n in ids}
    over = [[a, b] for i, a in enumerate(ids) for b in ids[i + 1:] if rects_overlap(rect[a], rect[b])]
    back = []
    for a, b, _ in edges:
        na, nb = nodes.get(a) or {}, nodes.get(b) or {}
        if na.get('fb') or nb.get('fb') or na.get('fb_src'):
            continue
        if a in rect and b in rect and rect[a][0] + rect[a][2] > rect[b][0]:
            back.append([a, b])
    origin = [n for n in ids if pos[n] == (0, 0)]
    return {'overlaps': over, 'back_wires': back, 'at_origin': origin if len(origin) > 1 else []}


# panels, windows and the scripts behind their buttons: an unwired op of these types joins the 'Controls' stage
CONTROL_TYPES = frozenset(('windowCOMP', 'containerCOMP', 'widgetCOMP', 'buttonCOMP', 'sliderCOMP', 'fieldCOMP',
                           'listCOMP', 'selectCOMP', 'parameterCOMP', 'parameterexecuteDAT', 'panelexecuteDAT'))
STAGE_BODIES = {'Controls': 'Panels, windows and their scripts', 'Other': 'Not sorted into a stage yet'}


def assign_new_ops(stages, names, edges, types):
    """Keep a stored stage plan true to the COMP (T-69). stages: [{title, ops, ...}] (not changed); names: the ops
    in the COMP now; edges: (src, dst, k); types: {name: OPType}. Gone ops leave (a stage left empty goes); a new op
    joins the stage of what feeds it (lowest input first), else of what it feeds; unwired panels/windows/their
    scripts -> 'Controls', anything else -> 'Other'. Pure. Returns (stages, {new op: stage title})."""
    have = set(names)
    out = []
    for s in stages:
        t = dict(s)
        t['ops'] = [n for n in (s.get('ops') or []) if n in have]
        if t['ops']:
            out.append(t)
    where = dict((n, k) for k, s in enumerate(out) for n in s['ops'])
    new = [n for n in names if n not in where]
    placed = {}
    changed = True
    while changed and new:  # repeat: a chain of new ops follows its first wired member
        changed = False
        for n in list(new):
            src = sorted((k, a) for a, b, k in edges if b == n and a in where)
            dst = [b for a, b, _k in edges if a == n and b in where]
            k = where[src[0][1]] if src else (where[dst[0]] if dst else None)
            if k is not None:
                out[k]['ops'].append(n)
                where[n] = k
                placed[n] = out[k].get('title')
                new.remove(n)
                changed = True
    for n in new:
        title, role = ('Controls', 'control') if types.get(n) in CONTROL_TYPES else ('Other', 'note')
        k = next((i for i, s in enumerate(out) if s.get('title') == title), None)
        if k is None:
            out.append({'title': title, 'role': role, 'body': STAGE_BODIES[title], 'ops': []})
            k = len(out) - 1
        out[k]['ops'].append(n)
        placed[n] = title
    return out, placed


def box_problems(boxes, rects, members):
    """What makes stage boxes lie (T-69). boxes: {box: (x, y, w, h)}; rects: {op: (x, y, w, h)}; members: {op: box}.
    intruders: an op overlapping a box it is not in; unboxed: an op in no stage; box_overlaps: boxes on each other."""
    intr = [[o, b] for o in sorted(rects) for b in sorted(boxes)
            if members.get(o) != b and rects_overlap(rects[o], boxes[b])]
    unboxed = [o for o in sorted(rects) if members.get(o) not in boxes]
    ids = sorted(boxes)
    over = [[a, b] for i, a in enumerate(ids) for b in ids[i + 1:] if rects_overlap(boxes[a], boxes[b])]
    return {'intruders': intr, 'unboxed': unboxed, 'box_overlaps': over}


TOE_SIBLING_RE = re.compile(r'^(?P<base>.+?)(\.\d+)?\.toe$')


def save_conflicts(file, names):
    """Files in `names` (one folder's listing) that a save to `file` would collide with: the file itself and its
    numbered versions (X.toe -> X.toe, X.1.toe, X.12.toe), matched the way TD numbers saves (T-06, T-37)."""
    m = TOE_SIBLING_RE.match(os.path.basename(file))
    if not m:
        return []
    base = m.group('base')
    out = []
    for n in names:
        k = TOE_SIBLING_RE.match(n)
        if k and k.group('base') == base:
            out.append(n)
    return sorted(out)


def split_last_expr(code, filename='<jazib_mcp exec>'):
    """(code object for the body or None, code object for a last-line expression or None)."""
    tree = ast.parse(code, filename, 'exec')
    last = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = ast.Expression(body=tree.body.pop().value)
    body = compile(tree, filename, 'exec') if tree.body else None
    return body, (compile(last, filename, 'eval') if last is not None else None)


def run_code(code, ns):
    """exec `code` in `ns` with stdout/stderr captured. Returns {stdout, stderr, result}.
    On an exception raises ExecError carrying the traceback and whatever was printed first."""
    out, err = io.StringIO(), io.StringIO()
    result = None
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            body, last = split_last_expr(code)
            if body is not None:
                exec(body, ns)
            if last is not None:
                result = eval(last, ns)
    except BaseException as e:  # noqa: BLE001 -- user code; report everything, even SystemExit
        if isinstance(e, KeyboardInterrupt):
            raise
        raise ExecError('{}: {}'.format(type(e).__name__, e), traceback.format_exc(), out.getvalue(), err.getvalue())
    return {'stdout': out.getvalue(), 'stderr': err.getvalue(), 'result': to_json(result)}


class ExecError(Exception):
    def __init__(self, msg, tb, stdout='', stderr=''):
        Exception.__init__(self, msg)
        self.tb, self.stdout, self.stderr = tb, stdout, stderr

    def full_traceback(self):
        t = self.tb
        if self.stdout:
            t += '\n--- stdout before the error ---\n' + self.stdout
        if self.stderr:
            t += '\n--- stderr before the error ---\n' + self.stderr
        return t


class Pending(object):
    """Returned by a command that replies later: `finish()` runs `frames` frames from now and returns the result."""

    def __init__(self, frames, finish):
        self.frames = max(1, int(frames))
        self.finish = finish


def error_reply(rid, msg, tb=None):
    r = {'id': rid, 'ok': False, 'error': str(msg)}
    if tb:
        r['traceback'] = tb
    return r


def _reply_from_exception(rid, e, pre=None):
    if isinstance(e, ExecError):
        r = error_reply(rid, str(e), e.full_traceback())
    else:
        r = error_reply(rid, '{}: {}'.format(type(e).__name__, e), traceback.format_exc())
    if pre:
        r['pre_save'] = pre  # the save ran before the call failed: say where it is
    return r


def _send_json(send, obj):
    try:
        text = dumps(obj)
    except Exception as e:  # result not serializable after all
        text = dumps(error_reply(obj.get('id'), 'reply not JSON-serializable: {}'.format(e), traceback.format_exc()))
    send(text)


# Commands that change the network: each call is one undo step in TD (Ctrl+Z reverses it; live-checked on
# 2025.31550, T-54; idea from Derivative's TDMCP and Embody). Read-only commands stay out of the undo stack.
MUTATING = frozenset(('create', 'delete', 'rename', 'move', 'connect', 'disconnect', 'set_pars', 'dat_text',
                      'custom_pars', 'tox_load', 'layout', 'exec', 'comfy_build', 'publish', 'osc_learn', 'link',
                      'live_audio', 'tda_load', 'import_ae_anim', 'import_blender', 'midi_build', 'midi_learn', 'midi_map',
                      'midi_unmap', 'midi_bank', 'midi_load', 'midi_simulate', 'midi_preset', 'save_hook',
                      'record_chop', 'shadertoy', 'osc_expose', 'layer_mixer', 'cook_active'))


def undo_block(cmd, fn):
    """Run fn() inside one TD undo block named after the command; without TD's undo (tests) it just runs fn."""
    u = _try(lambda: ui.undo, None)  # noqa: F405
    if u is None:
        return fn()
    _try(lambda: u.startBlock('jazib-td: ' + str(cmd)))
    try:
        return fn()
    finally:
        _try(u.endBlock)


def dispatch(msg_text, send):
    """Handle one text frame from the bridge. Requests run here (callbacks are on TD's main thread) and the reply
    goes out through send(json_text), now or from a delayed run() for Pending commands."""
    try:
        msg = json.loads(msg_text)
    except Exception as e:
        _send_json(send, error_reply(None, 'bad JSON: {}'.format(e), traceback.format_exc()))
        return
    if not isinstance(msg, dict):
        _send_json(send, error_reply(None, 'message is not a JSON object'))
        return
    if msg.get('type') == 'ping':
        send(dumps({'type': 'pong'}))
        return
    if 'cmd' not in msg:
        return  # unknown / unsolicited types are ignored (protocol)
    rid = msg.get('id')
    cmd = msg.get('cmd')
    args = msg.get('args') or {}
    fn = COMMANDS.get(cmd) if isinstance(cmd, str) else None
    if fn is None:
        _send_json(send, error_reply(rid, 'unknown command {!r} (known: {})'.format(cmd, sorted(COMMANDS))))
        return
    if not isinstance(args, dict):
        _send_json(send, error_reply(rid, 'args must be a JSON object'))
        return
    pre = _pre_risk(cmd, args) if cmd in PRESAVE_CMDS else None  # lose nothing: save before a risky call (safety.py)
    try:
        call = (lambda: fn(**args)) if _accepts(fn, args) else (lambda: _bad_args(fn, cmd, args))
        result = undo_block(cmd, call) if cmd in MUTATING else call()
    except Exception as e:
        _send_json(send, _reply_from_exception(rid, e, pre))
        return
    if isinstance(result, Pending):
        finish = result.finish
        if cmd in MUTATING:
            finish = (lambda f: (lambda: undo_block(cmd, f)))(finish)
        if pre:
            finish = (lambda f: (lambda: _with_pre(f(), pre)))(finish)  # a chain passes it on to its last step
        _PENDING[rid] = {'send': send, 'finish': finish}
        try:
            _schedule(rid, result.frames)
        except Exception as e:
            _PENDING.pop(rid, None)
            _send_json(send, _reply_from_exception(rid, e))
        return
    _send_json(send, {'id': rid, 'ok': True, 'result': _with_pre(result, pre)})


def _with_pre(result, pre):
    """The pre-risk save outcome goes into a dict reply as pre_save (Pending chains: on the last step only)."""
    if pre and isinstance(result, Pending):
        f = result.finish
        result.finish = lambda: _with_pre(f(), pre)
    elif pre and isinstance(result, dict):
        result.setdefault('pre_save', pre)
    return result


def _accepts(fn, args):
    import inspect
    try:
        inspect.signature(fn).bind(**args)
        return True
    except TypeError:
        return False


def _bad_args(fn, cmd, args):
    import inspect
    raise TypeError('{}: bad args {} (signature {})'.format(cmd, sorted(args), inspect.signature(fn)))


def _schedule(rid, frames):
    script = "op({!r}).module._finish({!r})".format(handlers_path(), rid)
    if _runner is not None:
        _runner(script, frames)
    else:
        # delayRef = a COMP outside /local/time: with the default (me) a paused timeline never fires the reply
        # (T-57, reproduced 26 Oct on 2025.31550: td_errors timed out). TDMCP schedules on op.TDResources too.
        ref = _try(lambda: op.TDResources, None)  # noqa: F405
        if ref is not None:
            run(script, delayFrames=frames, delayRef=ref)  # noqa: F405 -- td.run
        else:
            run(script, delayFrames=frames)  # noqa: F405


def _finish(rid):
    """Called by the delayed run(): compute and send the pending reply. Unknown id (after a reload): ignored."""
    p = _PENDING.pop(rid, None)
    if p is None:
        return
    try:
        res = p['finish']()
        if isinstance(res, Pending):  # a multi-step command (offline_render, export_ae_data): run on later
            _PENDING[rid] = {'send': p['send'], 'finish': res.finish}
            _schedule(rid, res.frames)
            return
        reply = {'id': rid, 'ok': True, 'result': res}
    except Exception as e:
        _PENDING.pop(rid, None)
        reply = _reply_from_exception(rid, e)
    _send_json(p['send'], reply)


# ------------------------------------------------------------------ token + hello (pure, testable)

TOKEN_RE = re.compile(r'^[0-9a-f]{48}$')


def state_dir():
    d = os.environ.get('JTD_STATE_DIR')
    if d:
        return d
    return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'JazibTDMCP')


def read_or_create_token(directory=None):
    """The shared token (48 lowercase hex, file mode 600). Created here if the bridge has not made it yet."""
    directory = directory or state_dir()
    path = os.path.join(directory, 'token')
    if not os.path.exists(path):
        os.makedirs(directory, mode=0o700, exist_ok=True)
        tok = secrets.token_hex(24)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass  # the bridge won the race; read its token below
        else:
            with os.fdopen(fd, 'w') as f:
                f.write(tok + '\n')
            os.chmod(path, 0o600)
    with open(path, 'r', encoding='ascii') as f:
        tok = f.read().strip()
    if not TOKEN_RE.match(tok):
        raise ValueError('token file {} is not 48 lowercase hex characters'.format(path))
    return tok


def build_hello(token, info):
    return {'type': 'hello', 'token': token, 'td': info}


def td_build_string(version, build):
    """'2025.31550' from app.version '2025' + app.build '31550' (or as-is if build already has the year)."""
    b, v = str(build), str(version)
    if '.' in b or not v:
        return b
    return '{}.{}'.format(v.split('.')[0], b)


# ------------------------------------------------------------------ focus / selection (pure parts)
# Idea: Derivative TDMCP's "node following" (the editor pans to what the agent touches) and Embody's get_focus /
# satoruhiga's td_selection (MIT); written here from the TD Pane / NetworkEditor / COMP docs, nothing copied.

FLASH_COLOR = (1.0, 0.85, 0.1)   # a yellow no role colour uses (ROLE_COLORS)
FLASH_KEY = 'jazib_flash_orig'    # op storage: the colour to put back (survives a handlers reload)
FLASH_MS = 500
SELECTION_CAP = 50


def is_network_pane(pane):
    return 'NETWORK' in str(getattr(pane, 'type', '')).upper()


def pick_network_pane(panes, current=None):
    """The network editor to use: the pane the user is in (ui.panes.current) if it is one, else the first one."""
    if current is not None and is_network_pane(current):
        return current
    for p in panes:
        if is_network_pane(p):
            return p
    return None


def pick_this(selected, current):
    """What "this node" means (AF #5): the current op if it is selected or nothing is; else a lone selected op.
    Several selected and the current one not among them: None (ask). Never the rollover op."""
    key = lambda x: getattr(x, 'path', x)  # noqa: E731 -- compare ops by path, not object identity
    if current is not None and (key(current) in [key(s) for s in selected] or not selected):
        return current
    if len(selected) == 1:
        return selected[0]
    return None


def colors_close(a, b, eps=1e-3):
    try:
        return len(a) == len(b) and all(abs(float(x) - float(y)) <= eps for x, y in zip(a, b))
    except Exception:
        return False
# ------------------------------------------------------------------ inspect helpers (numeric readback)
# Idea (not code) from the peer MCPs' value inspectors: Embody / 8beeeaaat touchdesigner-mcp / Derivative TDMCP
# (research AF #4). Replies stay small: capped lists, rounded numbers.

INSPECT_MAX_CHANS = 32     # channels with stats per reply
INSPECT_MAX_ROWS = 100     # hard cap for rows / lines / samples / points heads
INSPECT_MAX_GRID = 16      # TOP sample grid side
INSPECT_MAX_VALS = 200000  # samples per channel used for stats
INSPECT_DETAILS = ('summary', 'full')
POP_MIN_BUILD = 30000      # POPs arrived in 2025.30000 (release notes); offline help on 31550 documents the class


def build_num(build):
    """31550.0 from '31550' or '2025.31550'; None when unparsable."""
    b = str(build or '').strip()
    if '.' in b:
        b = b.rsplit('.', 1)[-1]
    try:
        return float(b)
    except Exception:
        return None


def build_gate(build, needed, why):
    """None when the build is new enough (or unknown: then the API try decides), else a note dict (never raises)."""
    n = build_num(build)
    if n is not None and n < needed:
        return {'available': False, 'note': 'needs TD >= {}: {}'.format(int(needed), why)}
    return None


def rnd(v, sig=5):
    """A number rounded to `sig` significant digits (JSON-safe; non-finite -> repr, non-number -> to_json)."""
    if isinstance(v, bool):
        return v
    try:
        f = float(v)
    except Exception:
        return to_json(v)
    if not math.isfinite(f):
        return repr(f)
    if f == 0:
        return 0.0
    return float('%.*g' % (sig, f))


def clamp_int(v, default, lo, hi):
    try:
        i = int(v)
    except Exception:
        i = default
    return max(lo, min(hi, i))


def num_stats(vals):
    """{min, max, mean} of the finite numbers in vals (None when there are none); `nonfinite` counts the rest."""
    n, lo, hi, s, bad = 0, None, None, 0.0, 0
    for v in vals:
        try:
            f = float(v)
        except Exception:
            bad += 1
            continue
        if not math.isfinite(f):
            bad += 1
            continue
        n += 1
        s += f
        lo = f if lo is None or f < lo else lo
        hi = f if hi is None or f > hi else hi
    d = {'min': rnd(lo) if n else None, 'max': rnd(hi) if n else None, 'mean': rnd(s / n) if n else None}
    if bad:
        d['nonfinite'] = bad
    return d


def glob_pick(names, pattern=None, cap=INSPECT_MAX_CHANS):
    """(names matching the glob(s), total matched). pattern: None, 'tx ty*' (TD-style, space-separated) or a list."""
    if pattern is None or pattern == '' or pattern == []:
        pats = None
    elif isinstance(pattern, str):
        pats = pattern.split()
    else:
        pats = [str(p) for p in pattern]
    picked = [n for n in names if pats is None or any(fnmatch.fnmatchcase(n, p) for p in pats)]
    return picked[:max(0, int(cap))], len(picked)


def channel_stats(pixels, names='rgba'):
    """Per-channel stats of a list of pixels (each a sequence of channel values): {'r': {min,max,mean}, ...}."""
    pixels = [list(p) for p in pixels]
    k = max([len(p) for p in pixels] or [0])
    return {names[i] if i < len(names) else 'c{}'.format(i): num_stats([p[i] for p in pixels if len(p) > i])
            for i in range(k)}


def clip_str(s, n=80):
    s = '' if s is None else str(s)
    return s if len(s) <= n else s[:n] + '...'


def head_table(rows, n, max_cols=20, max_len=80):
    """First n rows of a table (list of lists of cell strings), each cut to max_cols cells of max_len chars."""
    return [[clip_str(c, max_len) for c in list(r)[:max_cols]] for r in list(rows)[:max(0, int(n))]]


def head_lines(text, n, max_len=200):
    """(first n lines of text, each cut to max_len chars; total line count)."""
    lines = (text or '').splitlines()
    return [clip_str(l, max_len) for l in lines[:max(0, int(n))]], len(lines)


def count_by(keys, top=None):
    """{key: count} sorted by count desc then key; top keeps the first N."""
    d = {}
    for k in keys:
        d[k] = d.get(k, 0) + 1
    items = sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))
    return dict(items[:top] if top else items)


def inspect_defaults(detail, rows, sample, family):
    """Checked (detail, rows, sample grid side) for an inspect call."""
    detail = (detail or 'summary').lower()
    if detail not in INSPECT_DETAILS:
        raise ValueError('detail must be one of {}, got {!r}'.format(INSPECT_DETAILS, detail))
    full = detail == 'full'
    rows = clamp_int(rows, 20 if full else 5, 0, INSPECT_MAX_ROWS) if rows is not None else (20 if full else 5)
    if sample is None:
        grid = 4 if (full and family == 'TOP') else 0
    else:
        grid = 0 if not sample else clamp_int(sample, 4, 1, INSPECT_MAX_GRID)
    return detail, rows, grid


# ================================================================== TD side

def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def comp_path():
    return _CTX.get('comp_path') or COMP_PATH


def handlers_path():
    return comp_path() + '/handlers'


def _op(path, what='path'):
    if not isinstance(path, str) or not path.startswith('/'):
        raise ValueError('{} must be an absolute TD path, got {!r}'.format(what, path))
    o = op(path)  # noqa: F405
    if o is None:
        raise ValueError('no operator at {}'.format(path))
    return o


def _abs_file(file, exts):
    if not isinstance(file, str) or not os.path.isabs(file):
        raise ValueError('file must be an absolute path, got {!r}'.format(file))
    if not file.lower().endswith(exts):
        raise ValueError('file must end with {}: {!r}'.format(' or '.join(exts), file))
    return file


def handlers_file():
    c = op(comp_path())  # noqa: F405
    if c is not None:
        p = _try(lambda: c.par.Handlersfile.eval())
        if p:
            return str(p)
        s = _try(lambda: c.fetch('handlersFile', None, search=False))
        if s:
            return str(s)
    return DEFAULT_HANDLERS_FILE


def td_info():
    a = app  # noqa: F405
    proj = project  # noqa: F405
    return {
        'build': td_build_string(_try(lambda: a.version, ''), _try(lambda: a.build, '')),
        'version': str(_try(lambda: a.version, '')),
        'osName': str(_try(lambda: a.osName, '')),
        'project': str(_try(lambda: proj.name, '')),
        'folder': str(_try(lambda: proj.folder, '')),
        'pid': os.getpid(),
        'protocol': PROTOCOL,
        'bridge_port': bridge_port(),
        'scratch': is_scratch(),
        'instance': instance(),
    }


def bridge_port(comp=None):
    """The port /jazib_mcp dials: its Bridgeport par (T-83), else BRIDGE_PORT."""
    c = comp if comp is not None else _try(lambda: op(comp_path()))  # noqa: F405
    v = _try(lambda: int(c.par.Bridgeport.eval())) if c is not None else None
    return v if v else BRIDGE_PORT


def _family(o):
    return str(_try(lambda: o.family, ''))


def _inputs(o):
    out = []
    for c in _try(lambda: list(o.inputConnectors), []):
        conns = _try(lambda: list(c.connections), [])
        out.append(conns[0].owner.path if conns else None)
    return out


def _outputs(o):
    out = []
    for c in _try(lambda: list(o.outputConnectors), []):
        for t in _try(lambda: list(c.connections), []):
            out.append([t.owner.path, _try(lambda: t.index, None)])
    return out


def par_obj(p):
    d = {
        'name': p.name,
        'label': _try(lambda: p.label, ''),
        'page': _try(lambda: p.page.name, ''),
        'style': _try(lambda: p.style, ''),
        'mode': mode_name(_try(lambda: p.mode, 'CONSTANT')),
        'val': to_json(_try(lambda: p.eval())),
        'expr': _try(lambda: p.expr, ''),
        'default': to_json(_try(lambda: p.default)),
        'readOnly': bool(_try(lambda: p.readOnly, False)),
        'custom': bool(_try(lambda: p.isCustom, False)),
    }
    if _try(lambda: p.isMenu, False):
        d['menuNames'] = to_json(_try(lambda: list(p.menuNames), []))
        d['menuLabels'] = to_json(_try(lambda: list(p.menuLabels), []))
    if _try(lambda: p.isNumber, False):
        d['min'] = to_json(_try(lambda: p.min))
        d['max'] = to_json(_try(lambda: p.max))
    return d


def _walk(root, depth):
    """Children of root, breadth-first, `depth` levels down."""
    level = [root]
    for _ in range(max(1, int(depth))):
        nxt = []
        for o in level:
            for ch in _try(lambda: list(o.children), []):
                yield ch
                nxt.append(ch)
        level = nxt
        if not level:
            break


# ------------------------------------------------------------------ commands

def cmd_status():
    i = td_info()
    proj = project  # noqa: F405
    return {
        'build': i['build'], 'version': i['version'], 'osName': i['osName'],
        'project': i['project'], 'folder': i['folder'],
        'fps': to_json(_try(lambda: proj.cookRate)),
        'realTime': to_json(_try(lambda: proj.realTime)),
        'perform': to_json(_try(lambda: proj.performMode)),
        'frame': to_json(_try(lambda: absTime.frame)),  # noqa: F405
        'absSeconds': to_json(_try(lambda: absTime.seconds)),  # noqa: F405
        'timelinePlaying': to_json(_try(lambda: op('/').time.play)),  # noqa: F405
        'protocol': PROTOCOL,
        'handlersFile': handlers_file(),
    }


def cmd_list(path='/', depth=1, family=None, type=None, limit=500):
    root = _op(path)
    ops_, truncated = [], False
    fam = family.upper() if family else None
    want = type.lower() if type else None
    for o in _walk(root, depth):
        if fam and _family(o) != fam:
            continue
        if want and want not in (str(_try(lambda: o.OPType, '')).lower(), str(_try(lambda: o.type, '')).lower()):
            continue
        if len(ops_) >= int(limit):
            truncated = True
            break
        ops_.append({
            'path': o.path, 'name': o.name, 'type': _try(lambda: o.OPType, ''), 'family': _family(o),
            'errors': bool(_try(lambda: o.errors(), '')), 'warnings': bool(_try(lambda: o.warnings(), '')),
            'children': len(o.children) if _try(lambda: o.isCOMP, False) else None,
        })
    return {'ops': ops_, 'truncated': truncated}


def cmd_info(path, allPars=False):
    o = _op(path)
    r = {
        'path': o.path, 'name': o.name, 'type': _try(lambda: o.OPType, ''), 'family': _family(o),
        'comment': _try(lambda: o.comment, ''),
        'inputs': _inputs(o), 'outputs': _outputs(o),
        'errors': _try(lambda: o.errors(), ''), 'warnings': _try(lambda: o.warnings(), ''),
        'cookTime': to_json(_try(lambda: o.cookTime)),
        'cpuCookTime': to_json(_try(lambda: o.cpuCookTime)),
        'gpuCookTime': to_json(_try(lambda: o.gpuCookTime)),
    }
    label = _try(lambda: o.label)
    if isinstance(label, str):
        r['label'] = label
    fam = r['family']
    if fam == 'TOP':
        r['width'], r['height'] = _try(lambda: o.width), _try(lambda: o.height)
    elif fam == 'CHOP':
        r['numChans'], r['numSamples'] = _try(lambda: o.numChans), _try(lambda: o.numSamples)
    elif fam == 'DAT':
        r['numRows'], r['numCols'] = _try(lambda: o.numRows), _try(lambda: o.numCols)
        r['text_len'] = _try(lambda: len(o.text))
    pars = []
    for p in _try(lambda: list(o.pars()), []):
        if allPars or par_differs(_try(lambda: p.mode, 'CONSTANT'), _try(lambda: p.eval()), _try(lambda: p.default)):
            pars.append(par_obj(p))
    r['pars'] = pars
    return r


def cmd_get_pars(path, names=None, page=None):
    o = _op(path)
    every = list(o.pars())
    if names:
        if isinstance(names, str):
            names = [names]
        missing = [n for n in names if not any(fnmatch.fnmatchcase(p.name, n) for p in every)]
        if missing:
            raise ValueError('{} has no parameter matching {}'.format(o.path, missing))
        every = [p for p in every if any(fnmatch.fnmatchcase(p.name, n) for n in names)]
    if page:
        every = [p for p in every if str(_try(lambda: p.page.name, '')).lower() == str(page).lower()]
    return {'pars': [par_obj(p) for p in every]}


NUMERIC_STYLES = ('Float', 'Int', 'Toggle', 'RGB', 'RGBA', 'XY', 'XYZ', 'XYZW', 'UV', 'UVW', 'WH')


def _plan_pars(o, pars, colors=None):
    """Validate every entry first (LEARNINGS rule 2), return [(par, actions)], warnings.
    A '#rrggbb' / '#rrggbbaa' value on an RGB(A) group name (or one of its members) sets the whole group (research AM,
    Hexler idea); colors (a dict) collects what each hex became."""
    if not isinstance(pars, dict):
        raise ValueError('pars must be an object {name: value}')
    plans, warnings, missing = [], [], []
    for name, spec in pars.items():
        p = o.par[name]
        hx = spec.get('val') if isinstance(spec, dict) and list(spec) == ['val'] else spec
        rgba = hex_rgba(hx) if isinstance(hx, str) else None
        if rgba is not None and (p is None or _try(lambda: p.style, '') in ('RGB', 'RGBA')):
            mem = colour_members(name, lambda n: o.par[n] is not None)
            if mem is not None:
                rgb_names, alpha_name = mem
                for n, v in zip(rgb_names, rgba[:3]):
                    plans.append((o.par[n], [('val', v)]))
                if rgba[3] is not None:
                    if alpha_name:
                        plans.append((o.par[alpha_name], [('val', rgba[3])]))
                    else:
                        warnings.append('{}: {} has no alpha parameter; alpha {} ignored'.format(name, hx, rgba[3]))
                if colors is not None:
                    with_alpha = bool(alpha_name and rgba[3] is not None)
                    colors[name] = {'hex': hx, 'pars': rgb_names + ([alpha_name] if with_alpha else []),
                                    'values': list(rgba[:3]) + ([rgba[3]] if with_alpha else [])}
                continue
        if isinstance(hx, str) and hx.strip().startswith('#') and p is not None \
                and _try(lambda: p.style, '') in NUMERIC_STYLES:
            # refuse here, before anything is set: TD's cast error at apply time left earlier pars changed (QC 26 Oct)
            raise ValueError('{}.{} ({}) is numeric: {!r} is {}'.format(
                o.path, name, p.style, hx, 'not a colour group member' if rgba is not None
                else 'not a #rrggbb / #rrggbbaa colour'))
        if p is None:
            missing.append(name)
            continue
        actions, warns = plan_par_set(
            name, spec,
            # StrMenu = free text with suggestions (channel names, paths): only a strict Menu is matched (T-62)
            is_menu=bool(_try(lambda: p.isMenu, False)) and _try(lambda: p.style, '') != 'StrMenu',
            is_pulse=bool(_try(lambda: p.isPulse, False)),
            menu_names=_try(lambda: list(p.menuNames), []), menu_labels=_try(lambda: list(p.menuLabels), []))
        plans.append((p, actions))
        warnings.extend(warns)
    if missing:
        raise ValueError('{} has no parameter {}'.format(o.path, missing))
    return plans, warnings


def _apply_plans(plans):
    done = []
    for p, actions in plans:
        for kind, v in actions:
            if kind == 'pulse':
                p.pulse()
            elif kind == 'val':
                p.val = v
            elif kind == 'menuIndex':
                p.menuIndex = v
            elif kind == 'expr':
                p.expr = v
            elif kind == 'bindExpr':
                p.bindExpr = v
            elif kind == 'mode':
                p.mode = getattr(ParMode, v)  # noqa: F405
        if actions:
            done.append(p.name)
    return done


def cmd_set_pars(path, pars):
    o = _op(path)
    colors = {}
    plans, warnings = _plan_pars(o, pars, colors)
    r = {'set': _apply_plans(plans), 'warnings': warnings}
    if colors:
        r['colors'] = colors
        r['note'] = 'hex = 8-bit values written as they are (value/255, no sRGB-to-linear step)'
    return r


def _auto_xy(par_, o, after=None):
    """A clean spot for a new op: right of `after` on its row (stepping down on a collision), else a new row
    under everything in the COMP. Never the (0,0) pile-up of a bare create()."""
    others = [k for k in par_.children if k != o and _try(lambda: k.dock, None) is None]
    rects = [(k.nodeX, k.nodeY, k.nodeWidth, k.nodeHeight) for k in others]
    w, h = int(o.nodeWidth), int(o.nodeHeight)
    if after is not None:
        a = _op(after, 'after')
        return free_spot(rects, a.nodeX + a.nodeWidth + GAP_X, a.nodeY, w, h)
    if not rects:
        return 0, 0
    x = min(r[0] for r in rects)
    y = min(r[1] for r in rects) - GAP_Y - h
    return free_spot(rects, x, y, w, h)


DEFAULT_RES = (1080, 1920)  # user rule 16 Oct 2026: every TD look is vertical 1080p
GENERATOR_TOPS = ('noiseTOP', 'constantTOP', 'rampTOP', 'circleTOP', 'rectangleTOP', 'textTOP', 'glslTOP',
                  'glslmultiTOP', 'renderTOP', 'scriptTOP')


def default_res_plan(op_type, pars, res):
    """Pars to add so a new generator TOP renders at the build size, or {} (filters follow their input; the
    caller's own resolution pars or res=False win)."""
    if res is False or op_type not in GENERATOR_TOPS:
        return {}
    if pars and any(k in pars for k in ('outputresolution', 'resolutionw', 'resolutionh', 'resolution')):
        return {}
    w, h = (res if isinstance(res, (list, tuple)) and len(res) == 2 else DEFAULT_RES)
    return {'outputresolution': {'menu': 'custom'}, 'resolutionw': int(w), 'resolutionh': int(h)}


def cmd_create(parent, type, name=None, xy=None, pars=None, after=None, arrange=True, res=None):
    par_ = _op(parent, 'parent')
    if not _try(lambda: par_.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(par_.path))
    cls = getattr(td, str(type), None)
    if cls is None or not isinstance(cls, builtins.type):
        raise ValueError('unknown operator type {!r} (use the class name, e.g. noiseTOP)'.format(type))
    if name is not None:
        if not valid_op_name(name):
            raise ValueError('bad operator name {!r}'.format(name))
        if par_.op(name) is not None:
            raise ValueError('{}/{} already exists'.format(par_.path.rstrip('/'), name))
    if xy is not None and (not isinstance(xy, (list, tuple)) or len(xy) != 2):
        raise ValueError('xy must be [x, y]')
    o = par_.create(cls, name) if name else par_.create(cls)
    try:
        if xy is not None:
            o.nodeX, o.nodeY = int(xy[0]), int(xy[1])
        else:
            o.nodeX, o.nodeY = _auto_xy(par_, o, after)
        extra = default_res_plan(str(type), pars, res)
        allpars = dict(extra, **(pars or {}))
        if allpars:
            plans, _w = _plan_pars(o, allpars)
            _apply_plans(plans)
        if _family(o) in VIEWER_FAMILIES:
            _try(lambda: setattr(o, 'viewer', True))  # the user watches the network live (26 Oct 2026)
    except Exception:
        _try(o.destroy)  # just made, nothing refers to it yet
        raise
    lay = _arrange(par_, arrange and xy is None)
    return {'path': o.path, 'type': _try(lambda: o.OPType, str(type)), 'xy': [o.nodeX, o.nodeY], 'layout': lay}


def _protected(path):
    """Our own COMP, its ancestors and '/' are never deleted (that would cut this very connection)."""
    me_ = comp_path().rstrip('/')
    p = path.rstrip('/') or '/'
    return p == '/' or me_ == p or me_.startswith(p + '/') or p.startswith(me_ + '/')


def _inside(p, root):
    return p == root or p.startswith(root + '/')


def open_windows():
    """Window COMPs that are open now: [(window, target op or None)]."""
    out = []
    for w in _try(lambda: op('/').findChildren(type=td.windowCOMP), []) or []:  # noqa: F405
        if _try(lambda: w.isOpen, False):
            out.append((w, _try(lambda: w.par.winop.eval())))
    return out


def ui_release(o):
    """T-70: TD crashed (SIGBUS on the UI draw thread, libOPUI -> libUI) when a panel shown in an open Window COMP was
    destroyed. Before o goes: close every open window showing o or anything inside it (or living inside it), and send
    network panes looking inside o to o's parent."""
    root = o.path
    closed = []
    for w, tgt in open_windows():
        tp = _try(lambda: tgt.path, '') if tgt is not None else ''
        if (tp and _inside(tp, root)) or _inside(w.path, root):
            _try(lambda: w.par.winclose.pulse())
            closed.append(w.path)
    moved = 0
    for pn in list(_try(lambda: ui.panes, []) or []):  # noqa: F405
        ow = _try(lambda: pn.owner)
        if ow is not None and _inside(ow.path, root):
            _try(lambda: setattr(pn, 'owner', o.parent()))
            moved += 1
    return {'windows_closed': closed, 'panes_moved': moved}


def safe_destroy(o, frames=3):
    """Destroy o without racing TD's UI thread (T-70). Panes leave it first; if an open window showed it, the window is
    closed, o is renamed out of the way (its name is free at once for a rebuild) and destroyed `frames` frames later."""
    if o is None or not _try(lambda: o.valid, True):
        return {'destroyed': None}
    rel = ui_release(o)
    path = o.path
    if not rel['windows_closed']:
        o.destroy()
        rel['destroyed'] = path
        return rel
    tmp = '{}_gone{}'.format(o.name, int(o.id))
    _try(lambda: setattr(o, 'name', tmp))
    _try(lambda: setattr(o, 'allowCooking', False))
    script = "o = op({!r})\nif o is not None: o.destroy()".format(int(o.id))
    run(script, delayFrames=max(1, int(frames)), delayRef=op.TDResources)  # noqa: F405
    rel['deferred'] = path
    return rel


def cmd_delete(paths, arrange=True):
    if isinstance(paths, str):
        paths = [paths]
    found, missing = [], []
    for p in paths:
        if _protected(p):
            raise ValueError('refusing to delete {} (the MCP COMP, its contents or an ancestor)'.format(p))
        o = op(p) if isinstance(p, str) and p.startswith('/') else None  # noqa: F405
        (found if o is not None else missing).append((p, o))
    deleted, parents = [], {}
    for p, o in found:
        if not _try(lambda: o.valid, True):  # went with a docked host (LEARNINGS T-28)
            deleted.append(p)
            continue
        path = o.path
        par_ = _try(lambda: o.parent())
        if par_ is not None:
            parents[par_.path] = par_
        safe_destroy(o)  # windows closed + panes moved off first (T-70)
        deleted.append(path)
    lay = [_arrange(c, arrange) for c in parents.values() if _try(lambda: c.valid, True)]
    return {'deleted': deleted, 'missing': [p for p, _ in missing], 'layout': [x for x in lay if x]}


def cmd_rename(path, name):
    o = _op(path)
    if not valid_op_name(name):
        raise ValueError('bad operator name {!r}'.format(name))
    if _protected(o.path):
        raise ValueError('refusing to rename {}'.format(o.path))
    o.name = name
    return {'path': o.path}


def cmd_move(path, xy):
    o = _op(path)
    if not isinstance(xy, (list, tuple)) or len(xy) != 2:
        raise ValueError('xy must be [x, y]')
    o.nodeX, o.nodeY = int(xy[0]), int(xy[1])
    return {'path': o.path, 'xy': [o.nodeX, o.nodeY]}


GLSL_TYPES = ('glslTOP', 'glslmultiTOP')


def connector_error(dst_path, dst_type, in_index, count):
    msg = '{} has {} input connector(s); inIndex {} is out of range'.format(dst_path, count, in_index)
    if dst_type in GLSL_TYPES:
        msg += ' (a GLSL TOP has 3; put more inputs in its `tops` parameter, numbered after the wired ones)'
    return msg


def cmd_connect(src, dst, outIndex=0, inIndex=0, arrange=True):
    s, d = _op(src, 'src'), _op(dst, 'dst')
    outs, ins = list(s.outputConnectors), list(d.inputConnectors)
    if not 0 <= int(outIndex) < len(outs):
        raise ValueError('{} has {} output connector(s); outIndex {} is out of range'.format(s.path, len(outs), outIndex))
    if not 0 <= int(inIndex) < len(ins):
        raise ValueError(connector_error(d.path, _try(lambda: d.OPType, ''), inIndex, len(ins)))
    target = ins[int(inIndex)]
    # Connector-to-connector lands on that exact input. Never src.outputConnectors[0].connect(dst): that always
    # replaces input 0 (td-port LEARNINGS, wrong wiring then a TD crash).
    try:
        outs[int(outIndex)].connect(target)
    except Exception:
        if int(outIndex) != 0:
            raise
        target.connect(s)
    got = _inputs(d)
    if int(inIndex) >= len(got) or got[int(inIndex)] != s.path:
        raise RuntimeError('connect check failed: {} input {} is {}, wanted {} (inputs now {})'.format(
            d.path, inIndex, got[int(inIndex)] if int(inIndex) < len(got) else None, s.path, got))
    return {'inputs': got, 'layout': _arrange(_try(lambda: d.parent()), arrange)}


def cmd_disconnect(dst, inIndex, arrange=True):
    d = _op(dst, 'dst')
    ins = list(d.inputConnectors)
    if not 0 <= int(inIndex) < len(ins):
        raise ValueError(connector_error(d.path, _try(lambda: d.OPType, ''), inIndex, len(ins)))
    ins[int(inIndex)].disconnect()
    return {'inputs': _inputs(d), 'layout': _arrange(_try(lambda: d.parent()), arrange)}


def cmd_dat_text(path, text=None, append=False):
    o = _op(path)
    if _family(o) != 'DAT':
        raise ValueError('{} is not a DAT'.format(o.path))
    if text is None:
        return {'text': o.text}
    o.text = (o.text + str(text)) if append else str(text)
    return {'len': len(o.text)}


def _glsl_log(target):
    """Compile log of a GLSL op through a reusable Info DAT inside our COMP (made on first use)."""
    c = op(comp_path())  # noqa: F405
    if c is None:
        return ''
    info = c.op('glsl_info')
    if info is None:
        info = c.create(infoDAT, 'glsl_info')  # noqa: F405
        info.nodeX, info.nodeY = 400, -400
    info.par.op = target.path
    _try(lambda: info.cook(force=True))
    return _try(lambda: info.text, '') or ''


def cmd_errors(path='/', frames=2, recurse=True, cook=True):
    root = _op(path)
    targets = [root] + (list(root.findChildren()) if recurse else list(_try(lambda: root.children, [])))
    if cook:  # an op nothing views never cooks, so it never reports (T-02)
        for o in targets:
            _try(lambda: o.cook(force=True))

    def finish():
        own = comp_path().rstrip('/') + '/glsl_info'
        items = []
        for o in targets:
            if o.path == own:
                continue
            e, w = _try(lambda: o.errors(), '') or '', _try(lambda: o.warnings(), '') or ''
            s = _try(lambda: o.scriptErrors(), '') or ''  # callback / extension / Script-op exceptions (T-55)
            if s:
                e = (e + '\n' if e else '') + 'Script: ' + s
            if not (e or w):
                continue
            if _try(lambda: o.OPType, '') in ('glslTOP', 'glslmultiTOP', 'glslMAT', 'glslPOP'):
                log = _try(lambda: _glsl_log(o), '')
                if log.strip():
                    e = (e + '\n' if e else '') + log.strip()
            items.append({'path': o.path, 'type': _try(lambda: o.OPType, ''), 'errors': e, 'warnings': w})
        return {'items': items}
    return Pending(max(1, int(frames)), finish)


def cmd_screenshot(path, file):
    o = _op(path)
    _abs_file(file, ('.png',))
    if _family(o) != 'TOP':
        raise ValueError('{} is not a TOP (point screenshot at a TOP)'.format(o.path))

    def finish():
        os.makedirs(os.path.dirname(file), exist_ok=True)
        _try(lambda: o.cook(force=True))
        o.save(file)
        if not os.path.isfile(file):
            raise RuntimeError('TOP.save did not write {}'.format(file))
        return {'file': file, 'width': _try(lambda: o.width), 'height': _try(lambda: o.height)}
    return Pending(1, finish)


STYLES = ('Float', 'Int', 'Toggle', 'Pulse', 'Menu', 'Str', 'RGB', 'XY', 'File')


def check_custom_specs(pars):
    """Validate every custom_pars entry before anything changes; raises ValueError listing all problems."""
    if not isinstance(pars, list) or not pars:
        raise ValueError('pars must be a non-empty list')
    bad = []
    for s in pars:
        if not isinstance(s, dict):
            bad.append('{!r}: not an object'.format(s))
            continue
        if not valid_custom_name(s.get('name')):
            bad.append('{!r}: name must be one capital letter then lowercase letters/digits'.format(s.get('name')))
        if s.get('style') not in STYLES:
            bad.append('{!r}: style {!r} is not one of {}'.format(s.get('name'), s.get('style'), list(STYLES)))
        if s.get('style') == 'Menu' and not s.get('menuNames'):
            bad.append('{!r}: a Menu needs menuNames'.format(s.get('name')))
    if bad:
        raise ValueError('; '.join(bad))


def _custom_exists(o, name):
    if o.par[name] is not None:
        return True
    return any(_try(lambda: p.tupletName, None) == name for p in _try(lambda: list(o.customPars), []))


def cmd_custom_pars(path, page, pars=None, mirror=None):
    o = _op(path)
    if not _try(lambda: o.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(o.path))
    if mirror is not None:
        if pars:
            raise ValueError('give pars or mirror, not both')
        return custom_pars_mirror(o, page, mirror)
    check_custom_specs(pars)
    pg = None
    for cp in _try(lambda: list(o.customPages), []):
        if cp.name == page:
            pg = cp
    added, skipped = [], []
    for s in pars:
        name = s['name']
        if _custom_exists(o, name):
            skipped.append(name)
            continue
        if pg is None:
            pg = o.appendCustomPage(page)
        label = s.get('label', name)
        style = s['style']
        kw = {'label': label}
        if style in ('Float', 'Int') and s.get('size'):
            kw['size'] = int(s['size'])
        group = list(getattr(pg, 'append' + style)(name, **kw))
        if style == 'Menu':
            group[0].menuNames = list(s['menuNames'])
            group[0].menuLabels = list(s.get('menuLabels') or s['menuNames'])
        default = s.get('default')
        for i, p in enumerate(group):
            for key in ('min', 'max', 'normMin', 'normMax', 'clampMin', 'clampMax'):
                if key in s:
                    setattr(p, key, s[key])
            if default is not None and style != 'Pulse':
                v = default[i] if isinstance(default, (list, tuple)) else default
                p.default = v
                p.val = v
        added.append(name)
    return {'added': added, 'skipped': skipped}


def cmd_tox_save(path, file, stamp=True, version=None, bump=None):
    """Save a COMP as .tox. stamp (default on): an About page on the COMP with Version / Touchbuild / Saved set first
    (research AM, TDXComponents convention), so the .tox says which build made it. version sets it; bump
    major|minor|patch counts it up; else the COMP keeps its Version (0.1.0 the first time)."""
    o = _op(path)
    _abs_file(file, ('.tox',))
    if not _try(lambda: o.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(o.path))
    about = None
    if stamp:
        cur = _try(lambda: o.par.Version.eval(), None)
        about = about_values(cur, version, bump, td_build_string(_try(lambda: app.version, ''),  # noqa: F405
                                                                  _try(lambda: app.build, '')))  # noqa: F405
        _stamp_about(o, about)
    elif version is not None or bump is not None:
        raise ValueError('version / bump need stamp:true')
    os.makedirs(os.path.dirname(file), exist_ok=True)
    o.save(file)
    r = {'file': file}
    if about is not None:
        r['about'] = about
    return r


def cmd_tox_load(parent, file, name=None, arrange=True):
    par_ = _op(parent, 'parent')
    _abs_file(file, ('.tox',))
    if not os.path.isfile(file):
        raise ValueError('no such file {}'.format(file))
    if name is not None and not valid_op_name(name):
        raise ValueError('bad operator name {!r}'.format(name))
    o = par_.loadTox(file)
    if name:
        o.name = name
    return {'path': o.path, 'layout': _arrange(par_, arrange)}


def next_save_name(name, listing):
    """Pure: the next free numbered save for project file `name` (X.toe / X.N.toe -> X.(max N + 1).toe) given the
    folder listing, so a save never collides with an existing sibling (T-37)."""
    m = TOE_SIBLING_RE.match(name)
    base = m.group('base') if m else name[:-4] if name.endswith('.toe') else name
    hi = 0
    for n in listing:
        k = TOE_SIBLING_RE.match(n)
        if k and k.group('base') == base:
            mm = re.match(r'^.+\.(\d+)\.toe$', n)
            hi = max(hi, int(mm.group(1)) if mm else 0)
    return '{}.{}.toe'.format(base, hi + 1)


def cmd_save_project(file=None):
    proj = project  # noqa: F405
    conflicts = []
    if file:
        _abs_file(file, ('.toe',))
        # TD asks "replace?" in a prompt Claude can't see when the file OR a numbered sibling (X.1.toe ...) exists;
        # the call then never returns and the reply is lost (LEARNINGS T-37, confirmed by the user 16 Oct). So move
        # every conflicting file to output/backups/ first: TD then has nothing to ask.
        folder = os.path.dirname(file)
        conflicts = save_conflicts(file, _try(lambda: os.listdir(folder), []))
        if conflicts:
            bdir = os.path.join(os.path.dirname(os.path.dirname(handlers_file())), 'output', 'backups')
            os.makedirs(bdir, exist_ok=True)
            stamp = time.strftime('%Y%m%d-%H%M%S')
            for n in conflicts:
                os.replace(os.path.join(folder, n), os.path.join(bdir, '{}.bak-{}.toe'.format(n[:-4], stamp)))
        proj.save(file)
    else:
        # never let TD pick the next .N itself: if that file exists TD asks "replace?" and hangs (T-37, T-71)
        folder = str(proj.folder)
        proj.save(os.path.join(folder, next_save_name(str(proj.name), _try(lambda: os.listdir(folder), []))))
    # TD may add a .N suffix (td-port LEARNINGS): report the file it really has open
    cur = os.path.join(str(proj.folder), str(proj.name))
    PRESAVE['last'] = time.monotonic()  # any save counts for the pre-risk rate limit (safety.py)
    rotated = _try(lambda: rotate_saves(cur), [])
    return {'file': cur, 'backed_up': conflicts if file else [], 'rotated': rotated}


SAVE_KEEP = 10


def saves_to_rotate(name, listing, keep=SAVE_KEEP):
    """Pure (T-71): numbered siblings X.N.toe of project file `name` beyond the newest `keep` (by N), oldest first.
    The base X.toe and crash autosaves are never rotated."""
    m = TOE_SIBLING_RE.match(name)
    base = m.group('base') if m else name
    nums = []
    for n in listing:
        mm = re.match(r'^(.+)\.(\d+)\.toe$', n)
        if mm and mm.group(1) == base:
            nums.append((int(mm.group(2)), n))
    nums.sort()
    return [n for _k, n in nums[:-keep]] if len(nums) > keep else []


def rotate_saves(cur, keep=SAVE_KEEP):
    """Move numbered saves beyond the newest `keep` to output/backups/saves/ (never deletes)."""
    folder, name = os.path.dirname(cur), os.path.basename(cur)
    old = [n for n in saves_to_rotate(name, os.listdir(folder), keep) if n != name]
    if not old:
        return []
    bdir = os.path.join(os.path.dirname(os.path.dirname(handlers_file())), 'output', 'backups', 'saves')
    os.makedirs(bdir, exist_ok=True)
    for n in old:
        os.replace(os.path.join(folder, n), os.path.join(bdir, n))
    return old


def cmd_perf(path='/', top=20):
    root = _op(path)
    rows = []
    for o in [root] + list(root.findChildren()):
        ct = _try(lambda: o.cookTime)
        rows.append({'path': o.path, 'type': _try(lambda: o.OPType, ''), 'cookTime': to_json(ct),
                     'cpuCookTime': to_json(_try(lambda: o.cpuCookTime)),
                     'gpuCookTime': to_json(_try(lambda: o.gpuCookTime))})
    rows.sort(key=lambda r: r['cookTime'] if isinstance(r['cookTime'], (int, float)) else -1, reverse=True)
    return {'ops': rows[:max(0, int(top))]}


def exec_namespace():
    """_EXEC_NS refreshed with TD's globals: `from td import *` names plus op, me, parent, project, app, absTime."""
    ns = _EXEC_NS
    ns.setdefault('__builtins__', builtins)
    ns.setdefault('__name__', '__jazib_mcp_exec__')
    if td is not None:
        exec('from td import *', ns)
        ns['td'] = td
        # ParMode, PaneType, ParStyle...: DAT modules see them, `from td import *` doesn't (T-51)
        _try(lambda: exec('from tdutils.TDDefinitions import *', ns))
    me_ = _try(lambda: op(handlers_path()))  # noqa: F405
    ns['me'] = me_
    if me_ is not None:
        ns['parent'] = lambda n=1: me_.parent(n)
    for name in ('op', 'ops', 'project', 'app', 'absTime', 'root', 'ui', 'run', 'mod', 'tdu', 'iop', 'ipar'):
        v = getattr(td, name, None) if td is not None else None
        if v is not None:
            ns[name] = v
    ns['safe_destroy'] = safe_destroy  # use instead of o.destroy() for anything a window or pane may show (T-70)
    ns['ui_release'] = ui_release
    real_ui = ns.get('ui')
    if real_ui is not None:  # modal dialogs block TD's main thread and the reply with it (research AM): never open
        ns['ui'] = DialogGuardUI(real_ui, _DIALOGS['notes'], _DIALOGS['answers'])
    return ns


# ------------------------------------------------------------------ dialog guard (research AM: modal boxes block TD)
DIALOG_KINDS = ('messageBox', 'chooseFile', 'chooseFolder')
_DIALOGS = {'notes': [], 'answers': {}}


class DialogGuardUI(object):
    """td_exec's `ui`: everything goes to TD's real ui except the modal calls, which return an answer at once (the
    caller's `dialogs` answer, else the default: messageBox -> 0 = first button, chooseFile/chooseFolder -> None)
    and leave a note. Only the exec namespace is guarded: code inside DAT modules / extensions sees the real ui."""

    def __init__(self, real, notes, answers):
        object.__setattr__(self, '_real', real)
        object.__setattr__(self, '_notes', notes)
        object.__setattr__(self, '_answers', answers)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, '_real'), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, '_real'), name, value)

    def _blocked(self, kind, args, kw, default):
        ans = self._answers.get(kind, default)
        self._notes.append({'kind': kind, 'args': to_json(list(args))[:4], 'kw': to_json(dict(kw)),
                            'returned': to_json(ans)})
        return ans

    def messageBox(self, *args, **kw):
        return self._blocked('messageBox', args, kw, 0)

    def chooseFile(self, *args, **kw):
        return self._blocked('chooseFile', args, kw, None)

    def chooseFolder(self, *args, **kw):
        return self._blocked('chooseFolder', args, kw, None)


def check_dialog_answers(dialogs):
    """{messageBox: int >= 0, chooseFile: str|None, chooseFolder: str|None} or None -> a clean dict (raises)."""
    if dialogs is None:
        return {}
    if not isinstance(dialogs, dict):
        raise ValueError('dialogs must be an object {messageBox?, chooseFile?, chooseFolder?}')
    bad = [k for k in dialogs if k not in DIALOG_KINDS]
    if bad:
        raise ValueError('dialogs: unknown keys {} (use {})'.format(bad, list(DIALOG_KINDS)))
    mb = dialogs.get('messageBox', 0)
    if isinstance(mb, bool) or not isinstance(mb, int) or mb < 0:
        raise ValueError('dialogs.messageBox must be a button index >= 0')
    for k in ('chooseFile', 'chooseFolder'):
        if dialogs.get(k) is not None and not isinstance(dialogs[k], str):
            raise ValueError('dialogs.{} must be a path string or null'.format(k))
    return dict(dialogs)


VIEWER_FAMILIES = ('TOP', 'CHOP', 'SOP', 'POP', 'DAT')


def _op_ids():
    root = op('/')  # noqa: F405
    return set(o.id for o in _try(lambda: root.findChildren(), []))


def _show_new(before):
    """User, 26 Oct 2026: "open the node viewers - dont close them - user cant see what ur doing" and no ops piled
    on each other. Ops an exec made get their viewer on, their COMP re-flowed, the network pane sent there."""
    new = [o for o in _try(lambda: op('/').findChildren(), []) if o.id not in before  # noqa: F405
           and not _protected(o.path) and _try(lambda: o.dock, None) is None]
    # stage boxes a layout just drew (and their insides) are not new work (T-69)
    boxes = [o.path + '/' for o in new if _try(lambda: o.OPType, '') == 'annotateCOMP']
    new = [o for o in new if _try(lambda: o.OPType, '') != 'annotateCOMP'
           and not any(o.path.startswith(b) for b in boxes)]
    # only the top of what was made: a loaded .tox brings thousands of internal ops whose layout is not ours (T-50)
    tops = sorted(set(o.path for o in new), key=len)
    keep = []
    for p in tops:
        if not any(p.startswith(k + '/') for k in keep):
            keep.append(p)
    keep = set(keep)
    new = [o for o in new if o.path in keep]
    if not new:
        return None
    comps, shown = {}, 0
    for o in new:
        if _family(o) in VIEWER_FAMILIES and not _try(lambda: o.viewer, True):
            _try(lambda: setattr(o, 'viewer', True))
            shown += 1
        p = _try(lambda: o.parent())
        if p is not None:
            comps[p.path] = comps.get(p.path, 0) + 1
    lay = [x for x in (_arrange(op(p)) for p in comps) if x]  # noqa: F405
    for o in new:  # a COMP built together with its insides: flow those too, ours only (T-65)
        if _try(lambda: o.isCOMP, False):
            lay += _flow_new_insides(o)
    focus = max(comps, key=comps.get)
    _point_pane(_try(lambda: op(focus)))  # noqa: F405
    return {'new_ops': len(new), 'viewers_on': shown, 'pane': focus, 'layout': lay}


# ------------------------------------------------------------------ focus / selection / flash (TD side)

def _net_pane():
    ps = _try(lambda: ui.panes, None)  # noqa: F405
    if ps is None:
        return None
    return pick_network_pane(_try(lambda: list(ps), []), _try(lambda: ps.current, None))


def _point_pane(owner, home_op=None, zoom=False, home=True):
    """Network pane -> owner, then homed (on home_op if given, else the whole network; home=False: not homed).
    Returns the pane or None; never raises (a missing pane is a note, not an error)."""
    pane = _net_pane()
    if pane is None or owner is None:
        return None
    if instance() != 'main' and os.environ.get('JTD_QUIET_UI', '1') != '0':
        # T-252: side TDs crashed 6x in the UI thread drawing ops an exec was changing (T-213/215/227/246/249);
        # nobody watches a build TD, so its pane rests on /local and never shows the work in flight.
        owner, home_op = _try(lambda: op('/local'), owner), None  # noqa: F405
    _try(lambda: setattr(pane, 'owner', owner))
    if not home:
        return pane
    if home_op is not None:
        if _try(lambda: pane.home(zoom=bool(zoom), op=home_op), 'x') == 'x':
            _try(pane.home)
    else:
        _try(pane.home)
    return pane


def _flash(o, ms=FLASH_MS):
    """Tint o for ~ms, then put its colour back. The original lives in o's storage (not module state) so a reload
    or a second flash never loses it. Returns a note or None."""
    orig = _try(lambda: o.fetch(FLASH_KEY, None, search=False))
    if orig is None:
        orig = _try(lambda: [float(c) for c in o.color])
        if orig is None or _try(lambda: o.store(FLASH_KEY, orig), 'x') == 'x':
            return 'flash skipped: cannot read/store the colour of {}'.format(o.path)
    script = 'op({!r}).module._unflash({!r}, {!r})'.format(handlers_path(), int(o.id), o.path)
    try:
        run(script, delayMilliSeconds=int(ms))  # noqa: F405
    except TypeError:
        try:
            run(script, delayFrames=max(1, int(round(ms * 60 / 1000.0))))  # noqa: F405
        except Exception as e:
            _unflash(o.id, o.path)
            return 'flash skipped: run() failed: {}'.format(e)
    except Exception as e:
        _unflash(o.id, o.path)
        return 'flash skipped: run() failed: {}'.format(e)
    _try(lambda: setattr(o, 'color', FLASH_COLOR))
    return None


def _unflash(op_id, path=None):
    """Delayed half of _flash. The op may be gone (nothing to do) or back from an undo with a new id (found by path
    and its stored key). A colour the user set meanwhile wins."""
    o = _try(lambda: op(op_id))  # noqa: F405
    if o is None or not _try(lambda: o.valid, True):
        o = _try(lambda: op(path)) if path else None  # noqa: F405
    if o is None or not _try(lambda: o.valid, True):
        return False
    orig = _try(lambda: o.fetch(FLASH_KEY, None, search=False))
    if orig is None:
        return False
    if colors_close(_try(lambda: tuple(o.color), ()), FLASH_COLOR):
        _try(lambda: setattr(o, 'color', tuple(orig)))
    _try(lambda: o.unstore(FLASH_KEY))
    return True


def cmd_focus(path, select=True, zoom=False, flash=False):
    """Show the user an op: network pane on its parent, the op current + selected (others deselected), homed.
    UI state only (pane, selection flags, opt-in 0.5 s tint: it touches the user's node colours): no network data changes, so not in MUTATING."""
    o = _op(path)
    owner = _try(lambda: o.parent()) or o  # '/' has no parent: show it from itself
    notes = []
    if select:
        for s in _try(lambda: list(owner.selectedChildren), []):
            if _try(lambda: s.path) != o.path:
                _try(lambda: setattr(s, 'selected', False))
        _try(lambda: setattr(o, 'current', True))
        _try(lambda: setattr(o, 'selected', True))
    pane = _point_pane(owner, o, zoom is True, home=not select)
    if pane is None:
        notes.append('no network editor pane open; selection set, nothing panned')
    else:
        if select:
            if _try(lambda: pane.homeSelected(zoom=zoom is True), 'x') == 'x':
                _try(lambda: pane.home(op=o))
        if isinstance(zoom, numbers.Real) and not isinstance(zoom, bool) and zoom > 0:
            _try(lambda: setattr(pane, 'zoom', float(zoom)))
    if flash:
        n = _flash(o)
        if n:
            notes.append(n)
    r = {'path': o.path, 'pane': _try(lambda: pane.name) if pane is not None else None,
         'owner': owner.path, 'selected': bool(_try(lambda: o.selected, False)),
         'current': bool(_try(lambda: o.current, False))}
    if pane is not None:
        r['zoom'] = to_json(_try(lambda: pane.zoom))
    if notes:
        r['notes'] = notes
    return r


def cmd_selection():
    """What the user is pointing at now: the network pane's COMP, its selected children, current child, the op under
    the mouse, and `this` (current/selected, never the rollover; see pick_this). Read-only."""
    ps = _try(lambda: ui.panes, None)  # noqa: F405
    panes = _try(lambda: list(ps), []) if ps is not None else []
    cur_pane = _try(lambda: ps.current) if ps is not None else None
    pane = pick_network_pane(panes, cur_pane)
    r = {'panes': [{'name': _try(lambda: p.name), 'type': str(_try(lambda: p.type, '')).split('.')[-1],
                    'owner': to_json(_try(lambda: p.owner)),
                    'current': bool(_try(lambda: p.id == cur_pane.id, False))} for p in panes[:12]]}
    owner = _try(lambda: pane.owner) if pane is not None else None
    if owner is None:
        r['notes'] = ['no network editor pane open']
    sel = list(_try(lambda: owner.selectedChildren, []) or []) if owner is not None else []
    cur = _try(lambda: owner.currentChild) if owner is not None else None
    roll = _try(lambda: ui.rolloverOp)  # noqa: F405
    this = pick_this(sel, cur)

    def brief(o):
        return {'path': o.path, 'type': _try(lambda: o.OPType, ''), 'family': _family(o)} if o is not None else None
    r.update({
        'pane': _try(lambda: pane.name) if pane is not None else None,
        'owner': to_json(owner),
        'selected': [x.path for x in sel[:SELECTION_CAP]], 'selected_count': len(sel),
        'current': brief(cur), 'rollover': brief(roll), 'this': brief(this),
    })
    if len(sel) > 1 and this is None:
        r.setdefault('notes', []).append('several ops selected and none is current: ask which one')
    return r


def _exec_visible(code, dialogs=None):
    before = _op_ids()
    wins = [w.path for w, _t in (_try(open_windows, []) or [])] if '.destroy(' in code else []
    _DIALOGS['notes'][:] = []
    _DIALOGS['answers'].clear()
    _DIALOGS['answers'].update(dialogs or {})
    try:
        r = run_code(code, exec_namespace())
    finally:
        seen = list(_DIALOGS['notes'])
        _DIALOGS['notes'][:] = []
        _DIALOGS['answers'].clear()
    if seen:
        r['dialogs'] = seen
        r.setdefault('notes', []).append('{} modal dialog call(s) answered without opening (td_exec dialog guard); '
                                         'pass dialogs:{{messageBox, chooseFile, chooseFolder}} to choose the '
                                         'answer'.format(len(seen)))
    if wins:  # T-70: destroying a panel an open window shows crashed TD; say so every time
        r.setdefault('notes', []).append('code calls .destroy() while windows are open ({}): use safe_destroy(op) for '
                                         'anything a window or pane may show (T-70)'.format(', '.join(wins[:4])))
    if '# jtd:nofollow' in code:  # T-261: building a big COMP and pointing the pane into it in one go crashed TD (T-246)
        return r
    vis = _try(lambda: _show_new(before))
    if vis:
        r['visible'] = vis
    return r


# ------------------------------------------------------------------ crash guard (td/crashdb.py + logs/crash_patterns.json)
# Generalises the T-74/T-76 readback_hazard: every td_exec is checked against the crash fingerprints in
# logs/crash_patterns.json (T-64, T-70, T-74, T-76 seeded; new ones come from td_crash_report proposals). td/crashdb.py
# is read from beside this file and exec'd into its own module like td/debug.py; it and the pattern file are re-read
# when their mtime changes (no td_reload).
CRASHDB_FILE = 'crashdb.py'
CRASHDB_DIR = None       # tests point this at td/; default = this file's folder if it has crashdb.py, else handlers_file()'s
CRASH_PATTERNS = None    # default <repo>/logs/crash_patterns.json (repo = the folder above CRASHDB_DIR)
_CRASHDB = {'mod': None, 'mtime': None, 'file': None, 'pats': None, 'pkey': None, 'perr': None}


READBACK_METHODS = ('numpyArray(', 'evalTextSize(')  # T-74 + T-76: TOP Python reads that crashed TD
READBACK_HAZARDS = ('create(', '.cook(force', 'fontsize', 'resolution', '.par.font', '.par.text', 'pixelformat',
                    '.par.format', 'outputresolution')


# T-83 scratch TD (tools/scratch_td.py): a disposable second TD on its own bridge port for risky experiments. These
# rules say when code is worth running there first (td_exec target:'scratch'); each names the crash it comes from.
SCRATCH_RULES = (
    (('numpyArray(', 'evalTextSize('), 'TOP read (numpyArray / evalTextSize): crashes 3 + 4 (T-74, T-76)'),
    (('cookRate =', 'cookRate=', 'realTime = False', 'realTime=False'), 'cook rate / realTime change: crash 1 (T-64)'),
    (('.destroy(',), 'destroying ops a window or pane may show: crash 2 (T-70); prefer safe_destroy'),
    (('Nastaliq', 'Noto Naskh', 'Urdu'), 'complex-script fonts in a Text TOP: crash 4 (T-76), Urdu job blocked live'),
    (('windowCOMP', '.par.winopen', 'winopen.pulse'), 'window COMPs built or opened from code: crash 5 (T-79)'),
)


def is_scratch():
    """True inside the scratch TD (tools/scratch_td.py sets JTD_SCRATCH=1 before installing /jazib_mcp)."""
    return os.environ.get('JTD_SCRATCH') == '1'


def instance():
    """Which TD this is (T-120): 'main', 'scratch' or a build TD 'b2' / 'b3' (JTD_INSTANCE, set by scratch_td.py)."""
    return os.environ.get('JTD_INSTANCE') or ('scratch' if is_scratch() else 'main')


def scratch_hint(code):
    """Pure (T-83): the SCRATCH_RULES this code matches, as short reasons ([] = nothing known risky)."""
    if not isinstance(code, str):
        return []
    return [why for pats, why in SCRATCH_RULES if any(p in code for p in pats)]


SCRATCH_HOW = ("run it on the scratch TD first: td_exec target:'scratch' (start it with "
               "python3 tools/scratch_td.py start; a crash there only loses the scratch TD)")


def readback_hazard(code):
    """Pure (T-74; kept as the substring check behind the scratch TD note; td_exec's guard is crash_guard): does this exec read TOP pixels in the same script that creates/changes/force-cooks TOPs?
    Returns the hazards found ([] = fine). '# allow-readback' in the code opts out."""
    if '# allow-readback' in code or not any(m in code for m in READBACK_METHODS):
        return []
    return [h for h in READBACK_HAZARDS if h in code]


def _crashdb_dir():
    if CRASHDB_DIR:
        return CRASHDB_DIR
    here = globals().get('__file__')
    if isinstance(here, str) and os.path.isfile(os.path.join(os.path.dirname(here), CRASHDB_FILE)):
        return os.path.dirname(os.path.abspath(here))
    return os.path.dirname(handlers_file())


def _crashdb():
    import types as _types
    p = os.path.join(_crashdb_dir(), CRASHDB_FILE)
    mt = os.path.getmtime(p)
    if _CRASHDB['mod'] is None or _CRASHDB['mtime'] != mt or _CRASHDB['file'] != p:
        with open(p, 'r', encoding='utf-8') as f:
            text = f.read()
        text.encode('ascii')  # LEARNINGS rule 1
        m = _types.ModuleType('jazib_crashdb')
        m.__file__ = p
        exec(compile(text, p, 'exec'), m.__dict__)
        _CRASHDB.update(mod=m, mtime=mt, file=p, pkey=None)
    return _CRASHDB['mod']


def crash_patterns_file():
    return CRASH_PATTERNS or os.path.join(os.path.dirname(_crashdb_dir()), 'logs', 'crash_patterns.json')


def crash_patterns(mod=None):
    """(patterns, error): logs/crash_patterns.json, cached by mtime; unreadable -> crashdb.FALLBACK + the error."""
    mod = mod or _crashdb()
    path = crash_patterns_file()
    key = (path, _try(lambda: os.path.getmtime(path)), _CRASHDB['mtime'])
    if _CRASHDB['pkey'] != key:
        pats, err = mod.load_patterns(path)
        _CRASHDB.update(pats=pats, perr=err, pkey=key)
    return _CRASHDB['pats'], _CRASHDB['perr']


def crash_guard(code, frames=0):
    """(matches, notes) for a td_exec. matches: crashdb.check() rows (blocked ones refuse the call). Open windows are
    looked up only when the code calls destroy (T-70 pattern's `when`). A broken crashdb.py never blocks td_exec: it
    comes back as a note."""
    try:
        mod = _crashdb()
        pats, err = crash_patterns(mod)
        ctx = {}
        if 'destroy' in code:
            ctx['open_windows'] = [w.path for w, _t in (_try(open_windows, []) or [])]
        matches = mod.check(code, pats, frames, ctx)
        notes = mod.notes_for(matches)
        if err:
            notes.append('crash guard: pattern file problem, using the built-in readback guard only: {}'.format(err))
        return matches, notes
    except Exception as e:  # noqa: BLE001
        return [], ['crash guard unavailable: {}: {}'.format(type(e).__name__, e)]


def _with_notes(r, notes):
    if notes:
        r.setdefault('notes', []).extend(notes)
    return r


def cmd_exec(code, frames=0, dialogs=None):
    if not isinstance(code, str):
        raise ValueError('code must be a string')
    scratch = is_scratch()
    matches, notes = crash_guard(code, int(frames))
    here = instance()  # a pattern with `only` (e.g. ["main"]) blocks on those TDs only (T-134)
    blocked = [m for m in matches if m.get('blocked') and (not m.get('only') or here in m['only'])]
    # the scratch TD is where this may be tried (T-83), except patterns that take the OTHER TDs down too (T-124)
    if blocked and (not scratch or any(m.get('everywhere') for m in blocked)):
        raise ValueError('{}\nOr {}.'.format(_crashdb().refusal_text(matches, crash_patterns_file()), SCRATCH_HOW))
    hz = readback_hazard(code)
    if scratch and (blocked or (hz and int(frames) <= 0)):
        notes.append('scratch TD: crash guard waived ({})'.format(
            ', '.join([str(m.get('learnings') or m.get('id')) for m in blocked] + hz)))
    compile(code, '<jazib_mcp exec>', 'exec')  # a syntax error fails now, not frames later
    answers = check_dialog_answers(dialogs)
    hints = scratch_hint(code)

    def run():
        r = _with_notes(_exec_visible(code, answers), notes)
        if isinstance(r, dict):
            if scratch:
                r['scratch'] = True
            elif hints:
                r.setdefault('notes', []).append('known crash pattern(s): {}; next time {}'.format(
                    '; '.join(hints), SCRATCH_HOW))
        return r
    if int(frames) > 0:
        return Pending(int(frames), run)
    return run()


# ------------------------------------------------------------------ faulthandler (crash stacks of every Python thread)
# A SIGSEGV/SIGBUS in TD kills the process before any Python error handling runs. faulthandler (stdlib, Python 3.11:
# faulthandler.enable(file, all_threads=True)) installs C-level handlers for SIGSEGV, SIGFPE, SIGABRT, SIGBUS and
# SIGILL that write the Python traceback of every thread to `file`, then restore the previous handler and re-raise,
# so TD's own crash handler / CrashAutoSave still run. The file must stay open: it is kept on a module in
# sys.modules (survives td_reload), opened in append mode, one header line per TD process. Read after a crash with
# td_crash_report (or logs/td_faulthandler.log by hand).
FAULT_LOG = 'td_faulthandler.log'
FAULT_LOG_MAX = 1024 * 1024        # rotated to .1 at install when bigger
_FH_STATE = 'jazib_td_faulthandler_state'


def fault_header(pid, build, project_name, when, py):
    """Pure: the session line crashdb.parse_fh_log looks for (no spaces inside values)."""
    def v(x):
        return re.sub(r'\s+', '_', str(x)) or '?'
    return '=== jazib-td faulthandler session pid={} build={} project={} started={} python={} ===\n'.format(
        v(pid), v(build), v(project_name), v(when), v(py))


def _fh_state():
    import sys as _sys
    import types as _types
    st = _sys.modules.get(_FH_STATE)
    if st is None:
        st = _types.ModuleType(_FH_STATE)
        st.file, st.pid, st.path, st.since = None, None, None, None
        _sys.modules[_FH_STATE] = st
    return st


def _logs_dir():
    return os.path.join(os.path.dirname(os.path.dirname(handlers_file())), 'logs')


def install_faulthandler(log_dir=None, force=False):
    """Idempotent: enable faulthandler into <repo>/logs/td_faulthandler.log for this TD process. A reload or a second
    call keeps the open file (no new header) unless force."""
    import faulthandler
    import sys as _sys
    st = _fh_state()
    pid = os.getpid()
    path = os.path.join(log_dir or _logs_dir(), FAULT_LOG)
    f = st.file
    if not force and f is not None and not f.closed and st.pid == pid and st.path == path and faulthandler.is_enabled():
        return {'enabled': True, 'log': path, 'pid': pid, 'since': st.since, 'new': False}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.isfile(path) and os.path.getsize(path) > FAULT_LOG_MAX:
        _try(lambda: os.replace(path, path + '.1'))
    when = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    build = _try(lambda: td_build_string(app.version, app.build), '?')  # noqa: F405
    proj = _try(lambda: project.name, '?')  # noqa: F405
    nf = open(path, 'a', encoding='ascii', errors='replace')
    nf.write(fault_header(pid, build, proj, when, _sys.version.split()[0]))
    nf.flush()
    faulthandler.enable(file=nf, all_threads=True)
    old = st.file
    st.file, st.pid, st.path, st.since = nf, pid, path, when
    if old is not None and old is not nf:
        _try(old.close)
    return {'enabled': True, 'log': path, 'pid': pid, 'since': when, 'new': True}


def faulthandler_status():
    import faulthandler
    st = _fh_state()
    return {'enabled': faulthandler.is_enabled(), 'log': st.path, 'pid': st.pid, 'since': st.since,
            'ours': st.file is not None and not st.file.closed and st.pid == os.getpid()}


def _in_td():
    """True only inside a real TouchDesigner (tests' stub td has no app.binFolder); JTD_FAULTHANDLER=0 turns it off."""
    return td is not None and os.environ.get('JTD_FAULTHANDLER', '1') != '0' and \
        bool(_try(lambda: app.binFolder, None))  # noqa: F405


def cmd_reload():
    path = handlers_file()
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    text.encode('ascii')  # LEARNINGS rule 1: refuse non-ASCII before touching the DAT
    compile(text, path, 'exec')  # and a syntax error
    dat = _op(handlers_path())
    carry = dict(_CONN)
    stamp = time.strftime('%Y-%m-%dT%H:%M:%S')
    # a stamp keeps the text distinct: identical text does not reload the module (td-port LEARNINGS)
    dat.text = text.rstrip('\n') + '\n# jazib_mcp reload stamp ' + stamp + '\n'
    new = _try(lambda: dat.module)
    if new is not None:
        _try(lambda: new._CONN.update(carry))
        _try(lambda: new._CTX.update(_CTX))
    return {'handlersFile': path, 'loadedAt': stamp}


# ------------------------------------------------------------------ layout commands

ROLE_COLORS = {'input': (0.35, 0.5, 0.8), 'control': (0.8, 0.6, 0.25), 'output': (0.35, 0.7, 0.4),
               'feedback': (0.75, 0.35, 0.35)}


def _layout_nodes(c):
    kids = [o for o in c.children if _try(lambda: o.dock, None) is None
            and _try(lambda: o.OPType, '') != 'annotateCOMP']
    by = {o.name: o for o in kids}
    nodes, edges = {}, []
    for o in kids:
        docks = [d for d in _try(lambda: list(o.docked), []) if d is not None]
        nodes[o.name] = {'w': int(o.nodeWidth), 'h': int(o.nodeHeight), 'fam': _family(o),
                         'docks': [(int(d.nodeWidth), int(d.nodeHeight)) for d in docks]}
        for k, conn in enumerate(_try(lambda: list(o.inputConnectors), [])):
            for src in _try(lambda: list(conn.connections), []):
                if src.owner.name in by and src.owner.parent() == c:
                    edges.append((src.owner.name, o.name, k))
    for o in kids:  # feedback loops: their back wires are by design (T-163)
        if _try(lambda: o.OPType, '') != 'feedbackTOP':
            continue
        nodes[o.name]['fb'] = True
        t = _try(lambda: o.par.top.eval(), None)
        t = _try(lambda: t.name, None) if t is not None and not isinstance(t, str) else (t or '').rsplit('/', 1)[-1]
        if t in nodes:
            nodes[t]['fb_src'] = True
    return kids, by, nodes, edges


def _role(o, nodes, edges):
    n = o.name
    has_in = any(b == n for _, b, _k in edges)
    has_out = any(a == n for a, _b, _k in edges)
    t = _try(lambda: o.OPType, '')
    if 'feedback' in t:
        return 'feedback'
    if _family(o) == 'CHOP':
        return 'control'
    if not has_in and has_out:
        return 'input'
    if has_in and not has_out:
        return 'output'
    return None


def cmd_layout(path, mode='flow', ops=None, title=None, colors=False, xy=None, stages=None, arrange=None):
    """flow: arrange the COMP (left-to-right by wire depth, spine on one row, bands per family, docked ops under
    their host); check: report problems only; annotate: a titled network box around ops (default all)."""
    c = _op(path)
    if not _try(lambda: c.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(c.path))
    kids, by, nodes, edges = _layout_nodes(c)
    if mode == 'check':
        pos = {n: (int(by[n].nodeX), int(by[n].nodeY)) for n in by}
        res = layout_check(nodes, edges, pos)
        # storyboard stages (mode stages, rows): a wire from one stage row to the next runs right-to-left by design;
        # only a back-wire inside one box, or between ops in no box, counts (T-66)
        member = {}
        for a, ms, _m in box_members(c, kids):
            for o in ms:
                member.setdefault(o.name, a.name)
        if member:
            res['back_wires'] = [w for w in res['back_wires'] if member.get(w[0]) == member.get(w[1])]
        res['ops'] = len(kids)
        res['ok'] = not (res['overlaps'] or res['back_wires'] or res['at_origin'])
        plan = _stage_plan(c)
        if plan:  # a staged COMP: every op inside its own box, no box over another (T-69)
            bp = _stage_box_problems(c, plan, kids)
            res.update(bp)
            res['ok'] = res['ok'] and not (bp['intruders'] or bp['unboxed'] or bp['box_overlaps'])
        return res
    if mode == 'unstage':
        _try(lambda: c.unstore(STAGE_KEY))
        gone = _drop_stage_boxes(c)
        r = _flow(c, xy, colors)
        r['boxes_removed'] = gone
        return r
    if mode == 'flow':
        if _stage_plan(c):  # staged COMP: re-apply its stored plan, never a plain flow over the boxes (T-69)
            return restage(c)
        return _flow(c, xy, colors)
    if mode == 'annotate':
        names = list(ops) if ops else list(by)
        sel = []
        for n in names:
            o = c.op(n) if '/' not in str(n) else _op(n)
            if o is None:
                raise ValueError('no op {!r} in {}'.format(n, c.path))
            sel.append(o)
            sel += [d for d in _try(lambda: list(o.docked), []) if d is not None]
        if not sel:
            raise ValueError('nothing to annotate')
        pad, th = 40, 30
        x1 = min(o.nodeX for o in sel) - pad
        y1 = min(o.nodeY for o in sel) - pad
        x2 = max(o.nodeX + o.nodeWidth for o in sel) + pad
        y2 = max(o.nodeY + o.nodeHeight for o in sel) + pad + th
        a = c.create(td.annotateCOMP)
        a.par.Mode = 'networkbox'
        if title:
            a.par.Titletext = str(title)
            nm = re.sub(r'[^A-Za-z0-9_]', '_', str(title)).strip('_')[:40]
            if nm and valid_op_name('box_' + nm) and c.op('box_' + nm) is None:
                _try(lambda: setattr(a, 'name', 'box_' + nm))
        a.nodeX, a.nodeY = snap(x1), snap(y1)
        a.nodeWidth, a.nodeHeight = snap(x2 - x1), snap(y2 - y1)
        return {'path': a.path, 'xywh': [a.nodeX, a.nodeY, a.nodeWidth, a.nodeHeight], 'ops': [o.path for o in sel]}
    if mode == 'stages':
        return layout_stages(c, stages, colors, arrange=arrange or 'mixed')
    raise ValueError("mode must be 'flow', 'check', 'annotate', 'stages' or 'unstage'")


STAGE_KEY = 'jz_stages'  # the stage plan stored on a COMP: plain dicts/lists/strings only (T-67: no functions)


def _stage_plan(c):
    p = _try(lambda: c.fetch(STAGE_KEY, None, search=False), None)
    return p if isinstance(p, dict) and p.get('stages') else None


def _drop_stage_boxes(c):
    gone = 0
    for a in [x for x in _try(lambda: list(c.children), []) if _try(lambda: x.OPType, '') == 'annotateCOMP'
              and str(x.name).startswith('stage_')]:
        a.destroy()  # our own stage boxes; boxes made by hand stay
        gone += 1
    return gone


def _stage_box_problems(c, plan, kids):
    members, boxes = {}, {}
    for s in plan['stages']:
        a = c.op(s.get('box') or '')
        if a is None:
            continue
        boxes[a.name] = (a.nodeX, a.nodeY, a.nodeWidth, a.nodeHeight)
        for n in s.get('ops') or []:
            o = c.op(n)
            if o is None:
                continue
            members[n] = a.name
            for d in [d for d in _try(lambda: list(o.docked), []) if d is not None]:
                members[d.name] = a.name
    rects = {}
    for o in kids:
        rects[o.name] = (o.nodeX, o.nodeY, o.nodeWidth, o.nodeHeight)
        for d in [d for d in _try(lambda: list(o.docked), []) if d is not None]:
            rects[d.name] = (d.nodeX, d.nodeY, d.nodeWidth, d.nodeHeight)
    return box_problems(boxes, rects, members)


def restage(c):
    """Re-apply c's stored stage plan after a change: gone ops dropped, new ones placed by assign_new_ops (T-69)."""
    plan = _stage_plan(c)
    stages = []
    for s in plan['stages']:
        t = dict(s)
        t['ops'] = [n for n in (s.get('ops') or []) if c.op(n) is not None]
        if t['ops']:
            stages.append(t)
    if not stages:
        _try(lambda: c.unstore(STAGE_KEY))
        _drop_stage_boxes(c)
        return _flow(c, None, plan.get('colors', True))
    return layout_stages(c, stages, plan.get('colors', True), arrange=plan.get('arrange') or 'mixed')


def _flow(c, xy=None, colors=False):
    """Plain left-to-right flow of c (no stage plan): wire depth = column, docked ops under their host."""
    kids, by, nodes, edges = _layout_nodes(c)
    if xy is not None:
        x0, y0 = int(xy[0]), int(xy[1])
    elif kids:
        x0 = min(int(o.nodeX) for o in kids)
        y0 = max(int(o.nodeY + o.nodeHeight) for o in kids)
    else:
        x0, y0 = 0, 0
    pos = plan_flow(nodes, edges, x0, y0)
    boxes = box_members(c, kids)  # annotate boxes follow their ops through a re-flow (T-66)
    for n, (x, y) in pos.items():
        o = by[n]
        o.nodeX, o.nodeY = x, y
        docks = [d for d in _try(lambda: list(o.docked), []) if d is not None]
        for d, (dx, dy) in zip(docks, dock_offsets((x, y), [(int(d.nodeWidth), int(d.nodeHeight)) for d in docks])):
            d.nodeX, d.nodeY = dx, dy
        if colors:
            r = _role(o, nodes, edges)
            if r:
                o.color = ROLE_COLORS[r]
    refit_boxes(boxes)
    res = layout_check(nodes, edges, pos)
    res['ops'] = len(kids)
    res['moved'] = len(pos)
    res['ok'] = not (res['overlaps'] or res['at_origin'])
    return res


STAGE_COLORS = {'input': (0.20, 0.32, 0.55), 'process': (0.38, 0.22, 0.52), 'control': (0.55, 0.40, 0.15),
                'output': (0.20, 0.45, 0.28), 'feedback': (0.55, 0.22, 0.22), 'note': (0.30, 0.30, 0.32)}


def stage_box_geom(bbox, body, minw=300, pad=24):
    """(x, y, w, h) of a stage box around bbox (x1, y1, x2, y2) leaving room on top for the title + body lines."""
    x1, y1, x2, y2 = bbox
    lines = (body.count('\n') + 1) if body else 0
    head = 34 + 15 * lines + (14 if lines else 0)
    bx1, bx2 = x1 - pad, max(x2 + pad, x1 - pad + minw)
    return int(bx1), int(y1 - pad), int(bx2 - bx1), int(y2 + head - (y1 - pad))


REF_INPUT = 99  # input index given to a parameter-reference edge (a side input, never the main lane)


def _op_sources(o):
    """[(source op, input index)] feeding o: wires, then OP-reference parameters (Render TOP camera/geometry/lights,
    a light's projection map, a geo's material, a Select's op...). Those are flow too: a COMP linked only through
    references would otherwise stack every stage in one column (T-69)."""
    out = []
    for k, conn in enumerate(_try(lambda: list(o.inputConnectors), [])):
        for src in _try(lambda: list(conn.connections), []):
            out.append((src.owner, k))
    for p in _try(lambda: list(o.pars()), []):
        if not _try(lambda: p.isOP, False):
            continue
        v = _try(lambda: p.evalOPs(), None)
        if v is None:
            v = _try(lambda: p.eval(), None)
        for t in (v if isinstance(v, (list, tuple)) else [v]):
            if t is not None and _try(lambda: t.parent() == o.parent(), False) and t != o:
                out.append((t, REF_INPUT))
    return out


def _stage_edges(ops_):
    names = set(o.name for o in ops_)
    edges = []
    for o in ops_:
        for src, k in _op_sources(o):
            if src.name in names and (src.name, o.name, k) not in edges:
                edges.append((src.name, o.name, k))
    return edges


GRID_COLS = 6  # unwired ops in one stage lay out in rows of this many (T-98)


def stage_slots(names, edges):
    """{name: (column, row)} inside one stage: column = wire depth within the stage, row = branch lane (an op takes
    its input-0 parent's lane when that cell is free, else a new lane). Pure; deterministic for a given order."""
    preds = dict((n, []) for n in names)
    for a, b, k in edges:
        if a in preds and b in preds:
            preds[b].append((k, a))
    if not any(preds.values()):  # no wires inside the stage (a catalog of COMPs): a grid, rows of GRID_COLS, L->R
        return dict((n, (i % GRID_COLS, i // GRID_COLS)) for i, n in enumerate(names))
    wired = set(a for a, b, _k in edges if a in preds and b in preds) | set(b for a, b, _k in edges
                                                                         if a in preds and b in preds)
    loose = [n for n in names if n not in wired]
    if loose:  # wired ops keep their flow; ops with no wire in this stage fill a grid below them (T-98)
        slot = stage_slots([n for n in names if n in wired], edges)
        top = max(r for _c, r in slot.values()) + 1
        for i, n in enumerate(loose):
            slot[n] = (i % GRID_COLS, top + i // GRID_COLS)
        return slot
    depth = {}

    def d(n, seen=()):
        if n in depth:
            return depth[n]
        if n in seen:
            return 0
        ps = [a for _k, a in preds[n]]
        depth[n] = 0 if not ps else 1 + max(d(a, seen + (n,)) for a in ps)
        return depth[n]
    for n in names:
        d(n)
    order = sorted(names, key=lambda n: (depth[n], names.index(n)))
    slot, used, lanes = {}, set(), 0
    for n in order:
        main = sorted(preds[n])[0][1] if preds[n] else None
        row = slot[main][1] if main in slot else None
        if row is None or (depth[n], row) in used:
            row = lanes
            lanes += 1
        slot[n] = (depth[n], row)
        used.add((depth[n], row))
    return slot


def stage_grid(n_stages, stage_edges, after=None):
    """{stage index: (column, row)}: column = longest path in the stage graph (a stage that feeds another sits to its
    left), row = order among stages in the same column (parallel work stacks top to bottom). Pure."""
    preds = dict((i, set()) for i in range(n_stages))
    for a, b in stage_edges:
        if a != b and a in preds and b in preds:
            preds[b].add(a)
    for b, aa in (after or {}).items():
        preds.setdefault(b, set()).update(a for a in aa if a != b)
    col = {}

    def d(i, seen=()):
        if i in col:
            return col[i]
        if i in seen:
            return 0
        col[i] = 0 if not preds[i] else 1 + max(d(a, seen + (i,)) for a in preds[i])
        return col[i]
    for i in range(n_stages):
        d(i)
    rows, out = {}, {}
    for i in range(n_stages):
        r = rows.get(col[i], 0)
        out[i] = (col[i], r)
        rows[col[i]] = r + 1
    return out


def _stage_block(ops_, body, gap_x=40):
    """Lay one stage out at (0, 0) as its own little grid (wire depth L->R, branch lanes T->B). Returns (w, h, head)
    and leaves ops at block-local positions (top-left origin, y down negative)."""
    slots = stage_slots([o.name for o in ops_], _stage_edges(ops_))
    byn = dict((o.name, o) for o in ops_)
    cell_w = max(int(o.nodeWidth) for o in ops_) + gap_x
    dock_h = max([sum(int(d.nodeHeight) + 20 for d in _try(lambda: list(o.docked), []) if d is not None)
                  for o in ops_] + [0])
    cell_h = max(int(o.nodeHeight) for o in ops_) + dock_h + 30
    lines = (body.count('\n') + 1) if body else 0
    head = 34 + 15 * lines + (14 if lines else 0)
    top = -head - int(max(o.nodeHeight for o in ops_))
    for n, (cx, ry) in slots.items():
        o = byn[n]
        o.nodeX, o.nodeY = cx * cell_w, top - ry * cell_h
        dy = o.nodeY
        for dk in [dk for dk in _try(lambda: list(o.docked), []) if dk is not None]:
            dy -= int(dk.nodeHeight) + 20
            dk.nodeX, dk.nodeY = o.nodeX, dy
    allo = ops_ + [dk for o in ops_ for dk in _try(lambda: list(o.docked), []) if dk is not None]
    x1, y1 = min(o.nodeX for o in allo), min(o.nodeY for o in allo)
    x2 = max(o.nodeX + o.nodeWidth for o in allo)
    return x2 - x1, -y1, allo


def layout_stage_mixed(c, plan, after=None, gap_x=80, gap_y=70, pad=24, minw=300):
    """The mixed layout (user, 26 Oct: "a mixture of both is needed"): stages that feed others to their left,
    parallel stages stacked top to bottom; inside a stage wire depth L->R and branch lanes T->B."""
    idx = dict((o.name, i) for i, (_s, ops_) in enumerate(plan) for o in ops_)
    sedges = set()
    for i, (_s, ops_) in enumerate(plan):
        for o in ops_:
            for src, _k in _op_sources(o):
                j = idx.get(src.name)
                if j is not None and j != i:
                    sedges.add((j, i))
    grid = stage_grid(len(plan), sedges, after)
    blocks = []
    for i, (s, ops_) in enumerate(plan):
        w, h, allo = _stage_block(ops_, str(s.get('body') or ''))
        blocks.append((max(w + 2 * pad, minw), h + pad, allo))
    ncol = max(cr[0] for cr in grid.values()) + 1
    col_w = [0] * ncol
    for i, (cx, _r) in grid.items():
        col_w[cx] = max(col_w[cx], blocks[i][0])
    col_x = [sum(col_w[:k]) + k * gap_x for k in range(ncol)]
    col_y = [0] * ncol
    out = []
    for i in sorted(grid, key=lambda k: (grid[k][0], grid[k][1])):
        cx, _r = grid[i]
        bw, bh, allo = blocks[i]
        ox, oy = col_x[cx] + pad, col_y[cx]
        for o in allo:
            o.nodeX, o.nodeY = o.nodeX + ox, o.nodeY + oy
        x1, y1 = min(o.nodeX for o in allo), min(o.nodeY for o in allo)
        x2, y2 = max(o.nodeX + o.nodeWidth for o in allo), max(o.nodeY + o.nodeHeight for o in allo)
        out.append((plan[i][0], plan[i][1], (x1, y1, x2, y2)))
        col_y[cx] = y1 - pad - gap_y
    return out


def layout_stage_rows(c, plan, gap_x=40, gap_y=90):
    """Storyboard layout: stage k = row k (top to bottom), its ops left to right in wire order (the flow's x order),
    docked DATs under their host. Returns [(stage, ops, bbox)]."""
    y_top, out = 0, []
    for s, ops_ in plan:
        body = str(s.get('body') or '')
        slots = stage_slots([o.name for o in ops_], _stage_edges(ops_))
        byn = dict((o.name, o) for o in ops_)
        cell_w = max(int(o.nodeWidth) for o in ops_) + gap_x
        dock_h = max([sum(int(d.nodeHeight) + 20 for d in _try(lambda: list(o.docked), []) if d is not None)
                      for o in ops_] + [0])
        cell_h = max(int(o.nodeHeight) for o in ops_) + dock_h + 30
        lines = (body.count('\n') + 1) if body else 0
        head = 34 + 15 * lines + (14 if lines else 0)
        y0 = y_top - head - int(max(o.nodeHeight for o in ops_))
        for n, (col, row) in slots.items():
            o = byn[n]
            o.nodeX, o.nodeY = col * cell_w, y0 - row * cell_h
            dy = o.nodeY
            for d in [d for d in _try(lambda: list(o.docked), []) if d is not None]:
                dy -= int(d.nodeHeight) + 20
                d.nodeX, d.nodeY = o.nodeX, dy
        allo = ops_ + [d for o in ops_ for d in _try(lambda: list(o.docked), []) if d is not None]
        bb = (min(o.nodeX for o in allo), min(o.nodeY for o in allo),
              max(o.nodeX + o.nodeWidth for o in allo), max(o.nodeY + o.nodeHeight for o in allo))
        out.append((s, ops_, bb))
        y_top = bb[1] - 24 - gap_y
    return out


def _stage_box(c, s, bb, made, geom=None):
    body = str(s.get('body') or '')
    x, y, w, h = geom if geom else stage_box_geom(bb, body)
    a = c.create(td.annotateCOMP)
    nm = 'stage_' + re.sub(r'[^A-Za-z0-9]+', '_', str(s.get('title') or 'stage')).strip('_')[:28]
    _try(lambda: setattr(a, 'name', nm if c.op(nm) is None else nm + str(len(made))))
    a.par.Mode = 'annotate'
    a.par.Titletext = str(s.get('title') or '')
    a.par.Bodytext = body
    _try(lambda: setattr(a.par, 'Bodyfontsize', 9))
    _try(lambda: setattr(a.par, 'Titleheight', 26))
    col = STAGE_COLORS.get(str(s.get('role') or 'process'), STAGE_COLORS['process'])
    a.par.Backcolorr, a.par.Backcolorg, a.par.Backcolorb = col
    _try(lambda: setattr(a.par, 'Backcoloralpha', 0.35))
    a.nodeX, a.nodeY, a.nodeWidth, a.nodeHeight = x, y, w, h
    return a.path


def layout_stages(c, stages, colors=True, gap=60, arrange='mixed'):
    """Human-readable layout (user, 26 Oct: "make it all clear and understandable"): flow the COMP, then give each
    stage its own titled, coloured box with a short note, stages spaced left to right so boxes never overlap.
    stages: [{ops: [names], title, body?, role?: input|process|control|output|feedback|note, after?}].
    The plan is stored on c (T-69): every later change re-applies it, ops not listed are placed by assign_new_ops."""
    if not isinstance(stages, list) or not stages:
        raise ValueError('stages must be a list of {ops, title, body?, role?}')
    for s in stages:
        for n in (s.get('ops') or []):
            if c.op(n) is None:
                raise ValueError('stage {!r}: no op {!r} in {}'.format(s.get('title'), n, c.path))
    kids, _by, _nodes, edges = _layout_nodes(c)
    stages, placed_new = assign_new_ops(stages, [o.name for o in kids], edges, dict((o.name, o.OPType) for o in kids))
    _drop_stage_boxes(c)  # redo our own stage boxes; boxes made by hand stay
    _flow(c, None, colors)
    stages = [s for s in stages if s.get('role') == 'control'] + [s for s in stages if s.get('role') != 'control']
    plan = [(s, [c.op(n) for n in s['ops']]) for s in stages]  # controls first: on top of their column
    made, boxes, edge = [], [], None  # stages keep the caller's order (reading order)
    if arrange in ('rows', 'mixed'):
        after = {}
        titles = dict((str(st.get('title')), k) for k, (st, _o) in enumerate(plan))
        for k, (st, _o) in enumerate(plan):
            aa = [titles[t] for t in (st.get('after') or []) if t in titles]
            if aa:
                after[k] = aa
        placed = layout_stage_mixed(c, plan, after) if arrange == 'mixed' else layout_stage_rows(c, plan)
        for s, ops_, bb in placed:
            made.append(_stage_box(c, s, bb, made))
            boxes.append((s, made[-1]))
    else:
        for k, (s, ops_) in enumerate(plan):
            allo = ops_ + [d for o in ops_ for d in _try(lambda: list(o.docked), []) if d is not None]
            body = str(s.get('body') or '')
            bb = (min(o.nodeX for o in allo), min(o.nodeY for o in allo),
                  max(o.nodeX + o.nodeWidth for o in allo), max(o.nodeY + o.nodeHeight for o in allo))
            x, y, w, h = stage_box_geom(bb, body)
            if edge is not None and x < edge + gap:  # push this stage (and everything right of it) clear of the last box
                dx = int(edge + gap - x)
                later = [o for _s, os_ in plan[k:] for o in os_]  # this stage and the ones after it, not earlier ones
                for o in later + [d for o in later for d in _try(lambda: list(o.docked), []) if d is not None]:
                    o.nodeX += dx
                x += dx
            a = _stage_box(c, s, None, made, geom=(x, y, w, h))
            edge = x + w
            made.append(a)
            boxes.append((s, a))
    keep = []
    for s, path in boxes:
        t = dict((k, v) for k, v in s.items() if k in ('title', 'body', 'role', 'after', 'ops'))
        t['ops'] = [str(n) for n in t.get('ops') or []]
        t['box'] = path.rsplit('/', 1)[-1]
        keep.append(t)
    c.store(STAGE_KEY, {'arrange': arrange, 'colors': bool(colors), 'stages': keep})
    r = cmd_layout(c.path, 'check')
    r['stages'] = made
    r['arrange'] = arrange
    if placed_new:
        r['placed'] = placed_new
    return r


def _foreign_comp(o):
    """A clone, an op-shortcut package or an external tox: its layout is not ours to change (T-50). Only a NON-EMPTY
    externaltox path counts: builder-made COMPs have enableexternaltox on with an empty path (T-163)."""
    cl = _try(lambda: o.par.clone.eval(), None)
    return bool((cl and cl != o) or _try(lambda: o.par.opshortcut.eval(), '')
                or (_try(lambda: o.par.enableexternaltox.eval(), False)
                    and str(_try(lambda: o.par.externaltox.eval(), '') or '').strip()))


def _flow_new_insides(comp, depth=4):
    """Flow comp (and its own sub-COMPs) where the layout check fails (piled / overlapping). Returns layout reports."""
    out = []
    if depth <= 0 or _foreign_comp(comp) or _protected(comp.path):
        return out
    r = _try(lambda: cmd_layout(comp.path, 'check'), None)
    if r is not None and not r['ok']:
        x = _arrange(comp)
        if x:
            out.append(x)
    for ch in _try(lambda: list(comp.children), []):
        if _try(lambda: ch.isCOMP, False) and _try(lambda: ch.OPType, '') != 'annotateCOMP':
            out += _flow_new_insides(ch, depth - 1)
    return out


def box_members(c, kids):
    """Before a re-flow: each annotate box (network box / annotate mode) with the ops whose centre lies inside it and
    the box's margins around their bounding box, so refit_boxes can put it back around them (T-66)."""
    out = []
    for a in _try(lambda: list(c.children), []):
        if _try(lambda: a.OPType, '') != 'annotateCOMP' or _try(lambda: a.par.Mode.eval(), '') == 'comment':
            continue
        ax, ay, aw, ah = a.nodeX, a.nodeY, a.nodeWidth, a.nodeHeight
        ms = []
        for o in kids:
            cx, cy = o.nodeX + o.nodeWidth / 2.0, o.nodeY + o.nodeHeight / 2.0
            if ax <= cx <= ax + aw and ay <= cy <= ay + ah:
                ms.append(o)
                ms += [d for d in _try(lambda: list(o.docked), []) if d is not None]
        if not ms:
            continue
        bx1, by1 = min(o.nodeX for o in ms), min(o.nodeY for o in ms)
        bx2, by2 = max(o.nodeX + o.nodeWidth for o in ms), max(o.nodeY + o.nodeHeight for o in ms)
        out.append((a, ms, (bx1 - ax, by1 - ay, ax + aw - bx2, ay + ah - by2)))
    return out


def refit_boxes(boxes):
    for a, ms, (ml, mb, mr, mt) in boxes:
        if not _try(lambda: a.valid, True):
            continue
        bx1, by1 = min(o.nodeX for o in ms), min(o.nodeY for o in ms)
        bx2, by2 = max(o.nodeX + o.nodeWidth for o in ms), max(o.nodeY + o.nodeHeight for o in ms)
        a.nodeX, a.nodeY = int(bx1 - ml), int(by1 - mb)
        a.nodeWidth, a.nodeHeight = int(bx2 - bx1 + ml + mr), int(by2 - by1 + mb + mt)


def _arrange(comp, arrange=True):
    """Always-arrange (user, 16 Oct 2026: "always arrange - a layout should make sense"): re-flow the COMP a change
    touched and report the check. A failure never undoes the change; it comes back as layout.error."""
    if not arrange or comp is None or not _try(lambda: comp.isCOMP, False) or _protected(comp.path):
        return None
    try:
        r = cmd_layout(comp.path, 'flow')  # a staged COMP re-applies its plan (T-69)
        out = {'comp': comp.path, 'ok': r['ok'], 'overlaps': len(r['overlaps']), 'back_wires': len(r['back_wires'])}
        for k in ('intruders', 'unboxed', 'box_overlaps'):
            if r.get(k):
                out[k] = r[k][:8]
        if r.get('placed'):
            out['placed'] = r['placed']
        return out
    except Exception as e:
        return {'comp': comp.path, 'error': str(e)[:200]}


# ------------------------------------------------------------------ housekeeping (docs/research/U_housekeeping_workspace.md)

_DEBUG_NAME = re.compile(r'^(_?probe|_?tmp|_?test|scratch)', re.I)
_REF_STYLES = ('OP', 'COMP', 'TOP', 'CHOP', 'SOP', 'DAT', 'MAT', 'OBJ', 'PanelCOMP', 'Object', 'POP')


def default_named(name, optype):
    """noise1 for a noiseTOP: a name TD gave it, never chosen."""
    base = re.sub(r'(TOP|CHOP|SOP|DAT|COMP|MAT|POP)$', '', str(optype or ''))
    return bool(base) and re.match(r'^' + re.escape(base) + r'\d+$', str(name)) is not None


def _scope_ops(root_):
    """Ops we own under root_: the inside of clones, shipped packages (an op shortcut) and /jazib_mcp is not ours."""
    out, stack = [], list(_try(lambda: root_.children, []))
    while stack:
        o = stack.pop()
        if _protected(o.path):
            continue
        out.append(o)
        if _try(lambda: o.isCOMP, False):
            foreign = bool(_try(lambda: o.par.clone.eval(), None)) and o.par.clone.eval() != o
            foreign = foreign or bool(_try(lambda: o.par.opshortcut.eval(), ''))
            if not foreign:
                stack += list(_try(lambda: o.children, []))
    return out


def cmd_housekeeping(path='/project1', top=8):
    """Read-only report (spec U section A): errors, layout, names, cook cost, flags, orphan candidates, debug leftovers,
    files, look resolutions, project. Changes nothing; orphans are candidates only (U section C)."""
    t0 = time.perf_counter()
    r0 = _op(path)
    ops_ = _scope_ops(r0)
    refs = []
    for o in ops_:
        for p in _try(lambda: o.pars(), []):
            m = _try(lambda: str(p.mode), '')
            if m.endswith('EXPRESSION'):
                refs.append(str(p.expr))
            elif m.endswith('BIND'):
                refs.append(str(p.bindExpr))
            elif _try(lambda: p.style, '') in _REF_STYLES and _try(lambda: p.val, ''):
                refs.append(str(p.val))
        if _family(o) == 'DAT' and _try(lambda: o.dock, None) is None:
            refs.append(str(_try(lambda: o.text, ''))[:20000])
    blob = '\n'.join(refs)
    rep = {'path': r0.path, 'ops': len(ops_), 'build': _try(lambda: app.build, None)}  # noqa: F405
    rep['errors'] = [o.path for o in ops_ if _try(lambda: o.errors(), '')]
    rep['warnings'] = [o.path for o in ops_ if _try(lambda: o.warnings(), '')]
    lay = []
    for c in [r0] + [o for o in ops_ if _try(lambda: o.isCOMP, False)]:
        r = _try(lambda: cmd_layout(c.path, 'check'), None)
        if r and not r['ok']:
            lay.append({'comp': c.path, 'overlaps': len(r['overlaps']), 'back_wires': len(r['back_wires']),
                        'at_origin': len(r['at_origin'])})
    rep['layout_not_ok'] = lay
    rep['default_names'] = [o.path for o in ops_ if default_named(o.name, _try(lambda: o.OPType, ''))
                            and _try(lambda: o.dock, None) is None]
    sc = {}
    for o in _try(lambda: op('/').findChildren(type=td.COMP), []):  # noqa: F405
        s = _try(lambda: o.par.opshortcut.eval(), '')
        if s:
            sc.setdefault(s, []).append(o.path)
    rep['duplicate_shortcuts'] = {k: v for k, v in sc.items() if len(v) > 1}
    cost = sorted(ops_, key=lambda o: -(_try(lambda: o.cpuCookTime, 0) + _try(lambda: o.gpuCookTime, 0)))
    rep['slowest'] = [[o.path, round(_try(lambda: o.cpuCookTime, 0), 3), round(_try(lambda: o.gpuCookTime, 0), 3)]
                      for o in cost[:top]]
    mem = sorted(ops_, key=lambda o: -_try(lambda: o.gpuMemory, 0))
    rep['gpu_memory_mb'] = [[o.path, round(_try(lambda: o.gpuMemory, 0) / 1048576.0, 1)] for o in mem[:top]
                            if _try(lambda: o.gpuMemory, 0)]
    rep['flags'] = {'locked': [o.path for o in ops_ if _try(lambda: o.lock, False)],
                    'bypassed': [o.path for o in ops_ if _try(lambda: o.bypass, False)],
                    'hidden': [o.path for o in ops_ if not _try(lambda: o.expose, True)],
                    'viewers_off': len([o for o in ops_ if _family(o) in ('TOP', 'CHOP')
                                        and _try(lambda: o.dock, None) is None and not _try(lambda: o.viewer, True)])}
    orphans = []
    for o in ops_:
        if _family(o) not in ('TOP', 'CHOP', 'SOP', 'POP') or 'keep' in _try(lambda: list(o.tags), []):
            continue
        if _try(lambda: o.OPType, '') in ('outTOP', 'outCHOP', 'outSOP', 'outPOP'):
            continue
        outs = any(_try(lambda: c.connections, []) for c in _try(lambda: o.outputConnectors, []))
        if outs or _try(lambda: o.display, False) or _try(lambda: o.render, False):
            continue
        if re.search(r'\b' + re.escape(o.name) + r'\b', blob):
            continue
        orphans.append(o.path)
    rep['orphan_candidates'] = orphans
    rep['debug_leftovers'] = [o.path for o in ops_ if _DEBUG_NAME.match(o.name)
                              or 'debug' in _try(lambda: list(o.tags), [])
                              or 'todo' in str(_try(lambda: o.comment, '')).lower()]
    files = {'missing_externaltox': [], 'missing_syncfile': []}
    for o in ops_:
        f = _try(lambda: o.par.externaltox.eval(), '') if _try(lambda: o.par.enableexternaltox.eval(), False) else ''
        if f and not os.path.exists(f if os.path.isabs(f) else os.path.join(project.folder, f)):  # noqa: F405
            files['missing_externaltox'].append([o.path, f])
        if _family(o) == 'DAT' and _try(lambda: o.par.syncfile.eval(), False):
            f = _try(lambda: o.par.file.eval(), '')
            if f and not os.path.exists(f if os.path.isabs(f) else os.path.join(project.folder, f)):  # noqa: F405
                files['missing_syncfile'].append([o.path, f])
    folder = _try(lambda: project.folder, '')  # noqa: F405
    names = _try(lambda: os.listdir(folder), [])
    files['crash_autosaves'] = [n for n in names if n.startswith('CrashAutoSave')]
    files['numbered_toes'] = len([n for n in names if re.match(r'.+\.\d+\.toe$', n)])
    rep['files'] = files
    res = {}
    for c in [o for o in ops_ if o.name == 'looks' and _try(lambda: o.isCOMP, False)]:
        for lk in c.children:
            out = _try(lambda: lk.op('out'), None)
            if out is not None and _family(out) == 'TOP':
                res[lk.path] = [_try(lambda: out.width, 0), _try(lambda: out.height, 0)]
    rep['look_resolutions'] = res
    rep['look_resolutions_differ'] = len(set(tuple(v) for v in res.values())) > 1
    rep['project'] = {k: str(_try(lambda: getattr(project, k), None)) for k in  # noqa: F405
                      ('name', 'folder', 'cookRate', 'realTime', 'performWindowPath', 'performOnStart')}
    rep['ms'] = round((time.perf_counter() - t0) * 1000, 1)
    issues = len(rep['errors']) + len(lay) + len(orphans) + len(rep['debug_leftovers']) \
        + len(rep['duplicate_shortcuts']) + len(files['missing_externaltox']) + len(files['missing_syncfile'])
    rep['ok'] = issues == 0 and not rep['look_resolutions_differ']
    return rep


# ------------------------------------------------------------------ inspect (numeric readback, read-only)

def _err_note(what, e):
    return '{} failed ({}: {})'.format(what, type(e).__name__, clip_str(e, 120))


def _xyz(v):
    if v is None:
        return None
    got = [_try(lambda k=k: getattr(v, k)) for k in ('x', 'y', 'z')]
    if all(g is not None for g in got):
        return [rnd(g) for g in got]
    seq = _try(lambda: list(v))
    return [rnd(g) for g in seq] if seq else to_json(v)


def _bounds(b):
    if b is None:
        return None
    return {k: _xyz(_try(lambda k=k: getattr(b, k))) for k in ('min', 'max', 'center', 'size')}


def _attr_names(attrs):
    out = []
    for a in _try(lambda: list(attrs), []) or []:
        n = _try(lambda: a.name)
        out.append(str(n) if n is not None else str(a))
    return out[:40]


def _inspect_chop(o, r, detail, channels, rows, notes):
    r.update({'numChans': _try(lambda: o.numChans), 'numSamples': _try(lambda: o.numSamples),
              'rate': rnd(_try(lambda: o.rate)), 'start': rnd(_try(lambda: o.start)), 'end': rnd(_try(lambda: o.end)),
              'isTimeSlice': _try(lambda: bool(o.isTimeSlice))})
    chans = _try(lambda: list(o.chans()), []) or []
    by_name = {}
    for c in chans:
        by_name.setdefault(str(_try(lambda: c.name, '')), c)
    names, matched = glob_pick(list(by_name), channels, INSPECT_MAX_CHANS)
    out = []
    for n in names:
        c = by_name[n]
        try:
            vals = list(c.vals)
        except Exception as e:
            out.append({'name': n, 'note': _err_note('vals', e)})
            continue
        d = {'name': n}
        d.update(num_stats(vals[:INSPECT_MAX_VALS]))
        d['last'] = rnd(vals[-1]) if vals else None
        if detail == 'full' and rows:
            d['head'] = [rnd(v) for v in vals[:rows]]
        out.append(d)
    if (r.get('numSamples') or 0) > INSPECT_MAX_VALS:
        notes.append('stats use the first {} samples per channel'.format(INSPECT_MAX_VALS))
    r['channels'] = out
    if matched > len(names):
        r['channels_matched'] = matched
    if channels and not matched:
        notes.append('no channel matches {!r}'.format(channels))


def _top_numpy(o, grid, r, notes):
    """Stats (+ grid) from TOP.numpyArray(delayed=False). False when numpy is unusable (T-48)."""
    try:
        a = o.numpyArray(delayed=False)
    except Exception as e:  # numpy can be broken for a whole TD session (T-48)
        notes.append(_err_note('numpyArray', e) + '; numpy may be broken for this TD session: restart TD (T-48)')
        return False
    try:
        if a.ndim == 2:
            a = a.reshape(a.shape[0], a.shape[1], 1)
        h, w, k = a.shape
        flat = a.reshape(-1, k)
        lo, hi, mean = flat.min(axis=0).tolist(), flat.max(axis=0).tolist(), flat.mean(axis=0).tolist()
        names = 'rgba'
        r['stats'] = {names[i] if i < 4 else 'c{}'.format(i): {'min': rnd(lo[i]), 'max': rnd(hi[i]),
                                                                'mean': rnd(mean[i])} for i in range(k)}
        r['stats_source'] = 'numpyArray {}x{} (all pixels)'.format(w, h)
        if grid:
            n = max(1, min(grid, h, w))
            hh, ww = (h // n) * n, (w // n) * n
            # numpyArray row 0 is the bottom of the image (Embody docs, measured 2025.33230): flip so row 0 = top
            cells = a[:hh, :ww].reshape(n, hh // n, n, ww // n, k).mean(axis=(1, 3))[::-1]
            r['grid'] = [[[rnd(v, 4) for v in cell] for cell in row] for row in cells.tolist()]
            r['grid_note'] = '{0}x{0} cell means, row 0 = top of the image'.format(n)
        return True
    except Exception as e:
        notes.append(_err_note('pixel stats', e))
        return False


def _top_sample(o, grid, r, notes):
    """Fallback without numpy: a small grid of TOP.sample() points (each call downloads the texture: slow)."""
    n = max(1, min(grid or 3, 4))
    rows_ = []
    try:
        for i in range(n):
            v = 1.0 - (i + 0.5) / n  # row 0 = top (sample v=0 is the bottom)
            rows_.append([list(o.sample(u=(j + 0.5) / n, v=v)) for j in range(n)])
    except Exception as e:
        notes.append(_err_note('TOP.sample fallback', e))
        return
    r['stats'] = channel_stats([p for row in rows_ for p in row])
    r['stats_source'] = 'approx: {0}x{0} point samples (numpy unavailable)'.format(n)
    if grid:
        r['grid'] = [[[rnd(v, 4) for v in p] for p in row] for row in rows_]
        r['grid_note'] = '{0}x{0} point samples, row 0 = top'.format(n)


def _inspect_top(o, r, grid, notes):
    r.update({'width': _try(lambda: o.width), 'height': _try(lambda: o.height),
              'format': str(_try(lambda: o.pixelFormat, '')), 'depth': _try(lambda: o.depth)})
    if not _top_numpy(o, grid, r, notes):
        _top_sample(o, grid, r, notes)
    st = r.get('stats') or {}
    rgb_max = [st[c]['max'] for c in 'rgb' if c in st and isinstance(st[c].get('max'), float)]
    if rgb_max and max(rgb_max) <= 0:
        r['black'] = True
        notes.append('all RGB zero: if it should show something, re-read a call later (T-13) and check td_errors')


def _inspect_dat(o, r, rows):
    is_table = bool(_try(lambda: o.isTable, False))
    r['isTable'] = is_table
    if is_table:
        r['numRows'], r['numCols'] = _try(lambda: o.numRows), _try(lambda: o.numCols)
        table = _try(lambda: [[c.val for c in row] for row in o.rows()[:rows]], None)
        if table is None:
            table = [[_try(lambda i=i, j=j: o[i, j].val, '') for j in range(min(20, r['numCols'] or 0))]
                     for i in range(min(rows, r['numRows'] or 0))]
        r['rows'] = head_table(table, rows)
    else:
        lines, total = head_lines(_try(lambda: o.text, ''), rows)
        r['numLines'], r['lines'] = total, lines
        r['text_len'] = _try(lambda: len(o.text))


def _inspect_sop(o, r, detail, rows):
    r['numPoints'], r['numPrims'] = _try(lambda: o.numPoints), _try(lambda: o.numPrims)
    # SOP.bounds() is right on 2025.31550; computeBounds() returned all zeros for a cooked boxSOP (T-58)
    bb = _try(lambda: o.bounds() if callable(getattr(o, 'bounds', None)) else None)
    r['bounds'] = _bounds(bb if bb is not None else _try(lambda: o.computeBounds()))
    r['attribs'] = {'point': _attr_names(_try(lambda: o.pointAttribs)),
                    'prim': _attr_names(_try(lambda: o.primAttribs)),
                    'vertex': _attr_names(_try(lambda: o.vertexAttribs))}
    if detail == 'full' and rows:
        r['points_head'] = _try(lambda: [_xyz(p.P) for p in list(o.points)[:rows]], None)


def _inspect_pop(o, r, detail, rows, notes):
    g = build_gate(_try(lambda: app.build, ''), POP_MIN_BUILD, 'POP Python class (numPoints/bounds/points)')  # noqa: F405
    if g is None and not callable(_try(lambda: o.numPoints)):
        g = {'available': False, 'note': 'POP numPoints() missing on this build'}
    if g is not None:
        r['pop'] = g
        notes.append(g['note'])
        return
    for key, fn in (('numPoints', lambda: o.numPoints(delayed=False)), ('numPrims', lambda: o.numPrims(delayed=False)),
                    ('numVerts', lambda: o.numVerts(delayed=False)),
                    ('maxPoints', lambda: o.numPoints(max=True))):
        try:
            r[key] = to_json(fn())
        except Exception as e:
            notes.append(_err_note(key, e))
    try:
        r['bounds'] = _bounds(o.bounds(delayed=False))
    except Exception as e:
        notes.append(_err_note('bounds', e))
    r['attribs'] = {'point': _attr_names(_try(lambda: o.pointAttributes)),
                    'prim': _attr_names(_try(lambda: o.primAttributes)),
                    'vertex': _attr_names(_try(lambda: o.vertAttributes))}
    if detail == 'full' and rows:
        try:
            vals = list(o.points('P', startIndex=0, count=rows))
            r['P_head'] = [_xyz(v) if not isinstance(v, numbers.Real) else rnd(v) for v in vals[:rows * 3]]
        except Exception as e:
            notes.append(_err_note("points('P')", e))


def _inspect_comp(o, r):
    kids = _try(lambda: list(o.children), []) or []
    r['children'] = len(kids)
    r['by_family'] = count_by([_family(c) or '?' for c in kids])
    r['by_type'] = count_by([str(_try(lambda c=c: c.OPType, '?')) for c in kids], top=8)


def cmd_inspect(path, detail='summary', channels=None, rows=None, sample=None, cook=True):
    """Numeric readback of one op by family (read-only). Force-cooks it (unless cook=false), reads 1 frame later
    (numpyArray is zero in the same call as a forced cook, T-13). Never raises for a missing API: notes instead."""
    o = _op(path)
    fam = _family(o)
    detail, rows, grid = inspect_defaults(detail, rows, sample, fam)
    if cook:
        _try(lambda: o.cook(force=True))

    def finish():
        notes = []
        r = {'path': o.path, 'type': _try(lambda: o.OPType, ''), 'family': fam, 'detail': detail}
        err = _try(lambda: o.errors(), '')
        if err:
            r['errors'] = clip_str(err, 300)
        if _try(lambda: o.isCOMP, False):
            _inspect_comp(o, r)
        elif fam == 'CHOP':
            _inspect_chop(o, r, detail, channels, rows, notes)
        elif fam == 'TOP':
            _inspect_top(o, r, grid, notes)
        elif fam == 'DAT':
            _inspect_dat(o, r, rows)
        elif fam == 'SOP':
            _inspect_sop(o, r, detail, rows)
        elif fam == 'POP':
            _inspect_pop(o, r, detail, rows, notes)
        else:
            notes.append('no numeric readback for family {!r}; see td_info'.format(fam))
        if notes:
            r['notes'] = notes
        return r
    return Pending(1, finish)
# ------------------------------------------------------------------ network as text (net_export; diff: src/netdiff.js)
# Idea adapted from Embody's TDXN (github.com/dylanroscover/Embody, MIT, (c) Dylan Roscover): non-default built-in
# pars only, '=' expression / '~' bind prefixes, a constant string starting with a prefix gets it doubled, wires by
# name, custom pars grouped by page, DAT text kept. Our own format is JSON lines (stdlib, one op per line, keys in a
# fixed order, floats rounded) so it is deterministic and line-diffable; no code copied. Read-only.

NET_FORMAT = 'jtd-net'
NET_VERSION = 1
NET_SKIP_STYLES = ('Pulse', 'Momentary', 'Header')
NET_SKIP_PARS = ('pageindex',)
NET_SMALL_TEXT = 400        # DAT text up to this many chars goes in whole; longer -> hash + first lines
NET_HEAD_LINES = 6
NET_MAX_OPS = 5000
NET_KEY_ORDER = ('p', 't', 'skip', 'kids', 'dock', 'in', 'cin', 'flags', 'comment', 'tags', 'pars', 'cp',
                 'text', 'text_len', 'text_lines', 'text_sha1', 'text_head', 'xy', 'color')


def net_value(v):
    """JSON-safe and stable: floats rounded to 6 decimals (-0.0 -> 0.0), lists recursively."""
    v = to_json(v)
    if isinstance(v, float):
        r = round(v, 6)
        return 0.0 if r == 0 else r
    if isinstance(v, list):
        return [net_value(x) for x in v]
    return v


def net_par_code(mode, val, expr='', bind=''):
    """One par as text: '=expr', '~bind', '@export', or the constant (a string starting with = ~ @ gets it doubled)."""
    m = mode_name(mode)
    if m == 'EXPRESSION':
        return '=' + str(expr)
    if m == 'BIND':
        return '~' + str(bind)
    if m == 'EXPORT':
        return '@export'
    v = net_value(val)
    if isinstance(v, str) and v[:1] in ('=', '~', '@'):
        return v[0] + v
    return v


def net_text_fields(text, small=NET_SMALL_TEXT, head=NET_HEAD_LINES):
    """DAT text: whole when small, else length + line count + sha1 (16 hex) + the first lines (160 chars each)."""
    import hashlib
    text = str(text)
    if len(text) <= small:
        return {'text': text}
    lines = text.splitlines()
    return {'text_len': len(text), 'text_lines': len(lines),
            'text_sha1': hashlib.sha1(text.encode('utf-8', 'replace')).hexdigest()[:16],
            'text_head': [ln[:160] for ln in lines[:head]]}


def net_ref(src_path, owner_path, root_path):
    """How a wire names its source: sibling -> name, inside the export root -> path relative to it, else absolute."""
    src_parent = src_path.rsplit('/', 1)[0] or '/'
    own_parent = owner_path.rsplit('/', 1)[0] or '/'
    if src_parent == own_parent:
        return src_path.rsplit('/', 1)[-1]
    pre = root_path.rstrip('/') + '/'
    if src_path.startswith(pre):
        return src_path[len(pre):]
    return src_path


def _net_sorted(v):
    if isinstance(v, dict):
        return {k: _net_sorted(v[k]) for k in sorted(v)}
    if isinstance(v, list):
        return [_net_sorted(x) for x in v]
    return v


def net_line(rec):
    """One record as one JSON line: top keys in NET_KEY_ORDER (then the rest sorted), nested keys sorted, ASCII."""
    keys = [k for k in NET_KEY_ORDER if k in rec] + sorted(k for k in rec if k not in NET_KEY_ORDER)
    return json.dumps({k: _net_sorted(rec[k]) for k in keys}, ensure_ascii=True, separators=(',', ':'),
                      allow_nan=False)


def net_render(header, recs, max_chars):
    """Header line, op lines, an end line {end, ops, total, truncated}. Stops adding ops before max_chars."""
    lines = [net_line(header)]
    size = len(lines[0]) + 1
    n = 0
    for r in recs:
        ln = net_line(r)
        if max_chars and size + len(ln) + 1 > max_chars - 80:
            break
        lines.append(ln)
        size += len(ln) + 1
        n += 1
    truncated = n < len(recs)
    lines.append(net_line({'end': True, 'ops': n, 'total': len(recs), 'truncated': truncated}))
    return '\n'.join(lines) + '\n', n, truncated


def _net_foreign(o):
    """'clone' / 'package' for a COMP whose inside is not ours (same rule as _scope_ops), else None."""
    c = _try(lambda: o.par.clone.eval(), None)
    if c and c != o and _try(lambda: c.path, c) != o.path:
        return 'clone'
    if _try(lambda: o.par.opshortcut.eval(), ''):
        return 'package'
    return None


def _net_custom(p):
    style = str(_try(lambda: p.style, ''))
    d = {'style': style}
    label = _try(lambda: p.label, '')
    if label and label != p.name:
        d['label'] = label
    if style not in NET_SKIP_STYLES:
        d['v'] = net_par_code(_try(lambda: p.mode, 'CONSTANT'), _try(lambda: p.eval()), _try(lambda: p.expr, ''),
                              _try(lambda: p.bindExpr, ''))
        d['def'] = net_value(_try(lambda: p.default))
    if _try(lambda: p.isNumber, False):
        for k, a in (('min', 'min'), ('max', 'max'), ('nmin', 'normMin'), ('nmax', 'normMax'),
                     ('cmin', 'clampMin'), ('cmax', 'clampMax')):
            v = _try(lambda: getattr(p, a), None)
            if v is not None:
                d[k] = net_value(v)
    if _try(lambda: p.isMenu, False):
        d['menu'] = [str(x) for x in _try(lambda: list(p.menuNames), [])[:50]]
    return d


def _net_rec(o, rel, root_path, include_defaults, dat_text, xy):
    rec = {'p': rel, 't': str(_try(lambda: o.OPType, ''))}
    for key, conns_of in (('in', lambda: o.inputConnectors), ('cin', lambda: o.inputCOMPConnectors)):
        wires = []
        for c in _try(lambda: list(conns_of()), []) or []:
            cs = _try(lambda: list(c.connections), [])
            if cs:
                src = cs[0]
                wires.append([net_ref(src.owner.path, o.path, root_path), _try(lambda: int(src.index), 0)])
            else:
                wires.append(None)
        while wires and wires[-1] is None:
            wires.pop()
        if wires:
            rec[key] = wires
    dock = _try(lambda: o.dock, None)
    if dock is not None:
        rec['dock'] = net_ref(dock.path, o.path, root_path)
    flags = [f for f in ('bypass', 'lock', 'display', 'render') if _try(lambda: bool(getattr(o, f)), False)]
    if not _try(lambda: o.expose, True):
        flags.append('hidden')
    if flags:
        rec['flags'] = flags
    comment = _try(lambda: o.comment, '')
    if comment:
        rec['comment'] = str(comment)
    tags = sorted(str(t) for t in (_try(lambda: list(o.tags), []) or []))
    if tags:
        rec['tags'] = tags
    pars, cp = {}, {}
    for p in _try(lambda: list(o.pars()), []) or []:
        if _try(lambda: p.isCustom, False):
            page = str(_try(lambda: p.page.name, ''))
            cp.setdefault(page, {})[p.name] = _net_custom(p)
            continue
        if p.name in NET_SKIP_PARS or _try(lambda: p.readOnly, False):
            continue
        if str(_try(lambda: p.style, '')) in NET_SKIP_STYLES:
            continue
        mode, val = _try(lambda: p.mode, 'CONSTANT'), _try(lambda: p.eval())
        if include_defaults or par_differs(mode, val, _try(lambda: p.default)):
            pars[p.name] = net_par_code(mode, val, _try(lambda: p.expr, ''), _try(lambda: p.bindExpr, ''))
    if pars:
        rec['pars'] = pars
    if cp:
        rec['cp'] = cp
    if dat_text and _family(o) == 'DAT' and _try(lambda: o.isEditable, False):
        rec.update(net_text_fields(_try(lambda: o.text, '')))
    if xy:
        rec['xy'] = [net_value(_try(lambda: o.nodeX, 0)), net_value(_try(lambda: o.nodeY, 0))]
        col = _try(lambda: [round(float(x), 3) for x in o.color], None)
        if col:
            rec['color'] = col
    return rec


def net_collect(root_, depth=99, include_defaults=False, dat_text=True, xy=False, max_ops=NET_MAX_OPS):
    """Records for root_ ('.') and its ops, depth-first, children by name. Clones / op-shortcut packages are listed
    (their own pars) but not entered; /jazib_mcp is skipped. Returns (recs, notes)."""
    root_path = root_.path
    recs = [_net_rec(root_, '.', root_path, include_defaults, dat_text, xy)]
    notes = []

    def visit(comp, prefix, level):
        kids = sorted(_try(lambda: list(comp.children), []) or [], key=lambda c: c.name)
        for ch in kids:
            if len(recs) >= max_ops:
                if not notes or not notes[-1].startswith('max_ops'):
                    notes.append('max_ops {} reached: export stops there'.format(max_ops))
                return
            if _protected(ch.path):
                notes.append('skipped {} (the MCP itself)'.format(ch.path))
                continue
            rel = prefix + ch.name
            rec = _net_rec(ch, rel, root_path, include_defaults, dat_text, xy)
            recs.append(rec)
            if not _try(lambda: ch.isCOMP, False):
                continue
            n = len(_try(lambda: ch.children, []) or [])
            f = _net_foreign(ch)
            if f:
                rec['skip'], rec['kids'] = f, n
            elif level >= depth:
                if n:
                    rec['kids'] = n
            else:
                visit(ch, rel + '/', level + 1)

    if _try(lambda: root_.isCOMP, False):
        visit(root_, '', 1)
    return recs, notes


def cmd_net_export(path, depth=99, include_defaults=False, dat_text=True, xy=False, max_chars=60000):
    """Read-only: a COMP (or one op) as JSON-lines text (format jtd-net v1, docs/PROTOCOL.md). No timestamp, so two
    exports of an unchanged network are byte-identical."""
    r0 = _op(path)
    recs, notes = net_collect(r0, int(depth), bool(include_defaults), bool(dat_text), bool(xy))
    header = {'format': NET_FORMAT, 'v': NET_VERSION, 'root': r0.path, 'type': str(_try(lambda: r0.OPType, '')),
              'build': td_build_string(_try(lambda: app.version, ''), _try(lambda: app.build, '')),  # noqa: F405
              'depth': int(depth), 'include_defaults': bool(include_defaults), 'dat_text': bool(dat_text),
              'xy': bool(xy)}
    text, n, truncated = net_render(header, recs, int(max_chars) if max_chars else 0)
    return {'text': text, 'ops': n, 'total': len(recs), 'chars': len(text), 'truncated': truncated, 'notes': notes}


# ------------------------------------------------------------------ ComfyUI (docs/research/AL_td_comfyui.md 4.2)
# The client (td/comfy_client.py) lives in a Text DAT inside the built COMP: stdlib threads do all HTTP with plain
# data, an Execute DAT drains their results on the main thread. These commands never wait on the network.

COMFY_CLIENT_FILE = 'comfy_client.py'
COMFY_ACTIVE = ('starting', 'checking', 'uploading', 'queueing', 'queued', 'running', 'fetching', 'cancelling')
COMFY_JOB_RE = re.compile(r'^[0-9A-Za-z-]{1,64}$')
COMFY_MAX_WORKFLOW = 5 * 1024 * 1024
COMFY_PUMP = ("# Jazib MCP: hands ComfyUI thread results to the main thread (cheap when idle). td/comfy_client.py\n"
              "def onFrameStart(frame):\n"
              "    op('client').module.pump(parent())\n"
              "    return\n")


def _comfy_client_text():
    p = os.path.join(os.path.dirname(handlers_file()), COMFY_CLIENT_FILE)
    with open(p, 'r', encoding='utf-8') as f:
        t = f.read()
    t.encode('ascii')
    compile(t, p, 'exec')
    return t, p


def _comfy(comp):
    c = _op(comp, 'comp')
    cl = c.op('client')
    m = _try(lambda: cl.module) if cl is not None else None
    if m is None or not hasattr(m, 'pump'):
        raise ValueError('{} is not a comfy COMP (no client DAT): run td_comfy_build first'.format(c.path))
    return c, m


def _comfy_url(c, m):
    return m.check_url(_try(lambda: c.par.Url.eval(), None) or m.DEFAULT_URL)


def _comfy_out_dir(out_dir):
    if out_dir:
        return str(out_dir)
    return os.path.join(os.path.dirname(os.path.dirname(handlers_file())), 'output', 'comfy')


def cmd_comfy_build(parent='/project1', name='comfy', url='http://127.0.0.1:8188'):
    text, src = _comfy_client_text()
    ns = {'__name__': 'jazib_comfy_check'}
    exec(compile(text, src, 'exec'), ns)
    base = ns['check_url'](url)  # refuses non-loopback before anything changes
    par_ = _op(parent, 'parent')
    if not _try(lambda: par_.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(par_.path))
    if not valid_op_name(name):
        raise ValueError('bad operator name {!r}'.format(name))
    c = par_.op(name)
    if c is not None and _try(lambda: c.OPType) != 'baseCOMP':
        raise ValueError('{} exists and is a {}, not a Base COMP; pick another name'.format(c.path, c.OPType))
    created = c is None
    if created:
        c = par_.create(baseCOMP, name)  # noqa: F405
        c.nodeX, c.nodeY = _auto_xy(par_, c)
    c.comment = 'ComfyUI bridge (jazib-td): loopback HTTP from threads; client = td/comfy_client.py'
    made = []

    def child(cls_name, nm):
        o = c.op(nm)
        if o is None:
            o = c.create(getattr(td, cls_name), nm)
            made.append(nm)
        if _family(o) in VIEWER_FAMILIES:
            _try(lambda: setattr(o, 'viewer', True))
        return o

    client = child('textDAT', 'client')
    client.text = text
    wf = child('textDAT', 'workflow')
    if 'workflow' in made:
        wf.text = ''
    child('tableDAT', 'status')
    child('tableDAT', 'jobs')
    pump = child('executeDAT', 'pump')
    pump.text = COMFY_PUMP
    _try(lambda: setattr(pump.par.framestart, 'val', True))
    res = child('moviefileinTOP', 'result')
    out = child('nullTOP', 'out')
    if not _inputs(out) or _inputs(out)[0] != res.path:
        cmd_connect(res.path, out.path, arrange=False)
    cmd_custom_pars(c.path, 'Comfy', [{'name': 'Url', 'label': 'ComfyUI URL', 'style': 'Str', 'default': base}])
    c.par.Url = base
    m = client.module
    m.mark_dirty()
    m.kick_probe(base)
    return {'path': c.path, 'created': created, 'new_ops': made, 'url': base, 'client_file': src,
            'result_top': out.path, 'layout': _arrange(c), 'parent_layout': _arrange(par_),
            'hint': 'td_comfy_status in ~1 s says whether ComfyUI answers'}


def cmd_comfy_status(comp, frames=20):
    c, m = _comfy(comp)
    base = _comfy_url(c, m)
    m.kick_probe(base)

    def finish():
        m.pump(c)
        s = dict(m._STATE['status'])
        if s.get('url') != base or m._PROBE['busy']:
            s['probing'] = True
        order = m._STATE['order']
        r = {'comp': c.path, 'url': base, 'status': s, 'jobs_total': len(order),
             'jobs': [m.job_view(m._STATE['jobs'][j]) for j in reversed(order[-5:]) if j in m._STATE['jobs']],
             'result_top': c.path + '/out'}
        a = m._STATE.get('last_action')
        if a:
            r['last_action'] = a
        if m._STATE.get('pump_error'):
            r['pump_error'] = m._STATE['pump_error']
        if s.get('reachable') is False:
            r['hint'] = 'ComfyUI is closed or on another port: open Comfy Desktop (user), or set the Url par'
        return r
    return Pending(clamp_int(frames, 20, 1, 300), finish)


def _comfy_workflow_src(c, workflow):
    if workflow is None or workflow == '':
        w = c.op('workflow')
        t = _try(lambda: w.text, '') if w is not None else ''
        if not t.strip():
            raise ValueError('no workflow: pass workflow (API-format JSON, a .json file or a DAT path) or fill '
                             '{}/workflow'.format(c.path))
        return t
    if isinstance(workflow, dict):
        return workflow
    s = str(workflow).strip()
    if s.startswith('{'):
        return s
    if os.path.isabs(s) and os.path.isfile(s):
        if os.path.getsize(s) > COMFY_MAX_WORKFLOW:
            raise ValueError('workflow file over 5 MB: {}'.format(s))
        with open(s, 'r', encoding='utf-8') as f:
            return f.read()
    if s.startswith('/'):
        o = op(s)  # noqa: F405
        if o is not None and _family(o) == 'DAT':
            return o.text
    raise ValueError('workflow {!r} is not JSON, an existing absolute file, or a DAT path'.format(s[:200]))


def _top_png(top, out_dir, jid):
    """(bytes or None, file or None, note). saveByteArray first (in memory), else TOP.save to out_dir."""
    for ext in ('.png', 'png'):
        b = _try(lambda: top.saveByteArray(ext))
        if b:
            return bytes(b), None, None
    os.makedirs(out_dir, exist_ok=True)
    f = os.path.join(out_dir, 'in_{}.png'.format(jid[:8]))
    top.save(f)
    return None, f, 'saveByteArray unavailable: sent via file ' + f


def cmd_comfy_send(comp, workflow=None, inputs=None, image_from=None, confirm_spend=False, out_dir=None,
                   timeout_s=600, load=True):
    c, m = _comfy(comp)
    base = _comfy_url(c, m)
    m.pump(c)
    graph = m.parse_workflow(_comfy_workflow_src(c, workflow))
    if inputs is not None and not isinstance(inputs, dict):
        raise ValueError('inputs must be {"<node>.<input>": value}')
    hits = m.partner_nodes(graph)
    if hits and not confirm_spend:
        raise ValueError('refused: the workflow has partner/API nodes that spend credits ({}). Ask the user; only '
                         'with their go-ahead resend with confirm_spend=true'.format(
                             ', '.join('{} {}'.format(*h) for h in hits[:8])))
    m.apply_inputs(graph, inputs, 'td_check.png' if image_from else None)  # fail early, before any thread
    jid = m.new_prompt_id()
    out_dir = _comfy_out_dir(out_dir)
    image = image_file = note = None
    if image_from:
        top = _op(image_from, 'image_from')
        if _family(top) != 'TOP':
            raise ValueError('image_from must be a TOP, got {} ({})'.format(top.path, _family(top)))
        image, image_file, note = _top_png(top, out_dir, jid)
    job = {'id': jid, 'base': base, 'graph': graph, 'inputs': dict(inputs or {}), 'image': image,
           'image_file': image_file, 'confirm_spend': bool(confirm_spend), 'out_dir': out_dir,
           'timeout_s': clamp_int(timeout_s, 600, 5, 3600)}
    m.track(jid, state='starting', autoload=bool(load), spend_confirmed=bool(confirm_spend and hits) or None)
    m.start(m.run_job, job)
    r = {'job': jid, 'state': 'starting', 'url': base, 'nodes': len(graph), 'out_dir': out_dir,
         'image_bytes': len(image) if image else None,
         'hint': 'td_comfy_result {comp, job} (or td_comfy_status) to follow it; the image loads into ' + c.path + '/out'}
    if note:
        r['note'] = note
    return {k: v for k, v in r.items() if v is not None}


def cmd_comfy_result(comp, job=None, load=True, out_dir=None, timeout_s=120):
    c, m = _comfy(comp)
    m.pump(c)
    order = m._STATE['order']
    if job is None:
        if not order:
            raise ValueError('no jobs yet on {}: td_comfy_send first (or pass job = a prompt_id)'.format(c.path))
        job = order[-1]
    j = m._STATE['jobs'].get(job)
    if j is None:
        if not COMFY_JOB_RE.match(str(job)):
            raise ValueError('job must be a ComfyUI prompt_id, got {!r}'.format(job))
        base = _comfy_url(c, m)
        m.track(job, state='fetching', autoload=bool(load))
        m.start(m.fetch_job, base, job, _comfy_out_dir(out_dir), clamp_int(timeout_s, 120, 5, 3600))
        return {'job': job, 'state': 'fetching', 'hint': 'not sent from this COMP: polling /history; call again'}
    r = m.job_view(j)
    if j.get('state') == 'done' and j.get('files'):
        if load:
            r['loaded'] = m.load_result(c, j['files'][0])
        r['result_top'] = c.path + '/out'
        r['hint'] = 'td_screenshot ' + c.path + '/out to see it'
    elif j.get('state') in COMFY_ACTIVE:
        r['hint'] = 'still {}: call again in a few seconds'.format(j.get('state'))
    return r


def cmd_comfy_cancel(comp, job=None):
    c, m = _comfy(comp)
    m.pump(c)
    base = _comfy_url(c, m)
    if job is None:
        act = [k for k in m._STATE['order'] if (m._STATE['jobs'].get(k) or {}).get('state') in COMFY_ACTIVE]
        if not act:
            raise ValueError('nothing running on {} (pass job to cancel a prompt_id anyway)'.format(c.path))
        job = act[-1]
    if not COMFY_JOB_RE.match(str(job)):
        raise ValueError('job must be a ComfyUI prompt_id, got {!r}'.format(job))
    m.track(job, state='cancelling')
    m.start(m.cancel_job, base, job)
    return {'job': job, 'state': 'cancelling', 'hint': 'POST /queue delete + /interrupt sent from a thread'}


def cmd_comfy_free(comp):
    c, m = _comfy(comp)
    base = _comfy_url(c, m)
    m.start(m.simple_post, base, 'free', '/free', {'unload_models': True, 'free_memory': True})
    return {'sent': 'free', 'url': base, 'hint': 'td_comfy_status shows last_action'}
# ================================================================== TD -> Resolume Arena (26 Oct 2026)
# Spec: docs/research/AI_td_resolume.md "Proposed upgrades" (td_publish, td_publish_status, OSC learn). Pars from TD's
# offline help (Syphon_Spout_Out_TOP, NDI_Out_TOP, OSC_In_DAT, OscinDAT_Class; the op dump could not create those
# ops), LEARNINGS T-43 (NDI skip frames). The learn idea is resolume7-fx-pipeline tools/learn_osc.py (passive sniff),
# rewritten for TD (nothing imported, ADR-004). Never writes Arena's files. Senders and listeners are built inactive.

PUBLISH_PREFIX = 'publish_'
PUBLISH_KEY = 'jazib_publish'       # COMP storage: the config it was built with
PUBLISH_TRANSPORTS = ('syphon', 'ndi', 'both')
PUBLISH_ALPHAS = ('premultiplied', 'straight', 'none')
SOURCE_ALPHAS = ('premultiplied', 'straight')
PUBLISH_NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,39}$')
SENDER_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_ .-]{0,62}$')
SENDER_TYPES = {'syphon': 'syphonspoutoutTOP', 'ndi': 'ndioutTOP'}
SENDER_OPS = {'syphon': 'syphon_out', 'ndi': 'ndi_out'}
PUBLISH_STATUS_CAP = 50
RES_LIMITS = (16, 16384)

# Single-pass GLSL TOP pixel shaders (TD's GLSL rules: no #version, sTD2DInputs, vUV, TDOutputSwizzle).
GLSL_ALPHA = {
    'unpremult': ('// td_publish: premultiplied in -> straight out\nout vec4 fragColor;\nvoid main() {\n'
                  '    vec4 c = texture(sTD2DInputs[0], vUV.st);\n'
                  '    fragColor = TDOutputSwizzle(vec4(c.rgb / max(c.a, 1e-4), c.a));\n}\n'),
    'opaque': ('// td_publish: premultiplied in -> opaque out (= over black)\nout vec4 fragColor;\nvoid main() {\n'
               '    vec4 c = texture(sTD2DInputs[0], vUV.st);\n'
               '    fragColor = TDOutputSwizzle(vec4(c.rgb, 1.0));\n}\n'),
    'opaque_straight': ('// td_publish: straight in -> opaque out (= over black)\nout vec4 fragColor;\nvoid main() {\n'
                        '    vec4 c = texture(sTD2DInputs[0], vUV.st);\n'
                        '    fragColor = TDOutputSwizzle(vec4(c.rgb * c.a, 1.0));\n}\n'),
}

RESOLUME_723_NEXT = [
    'resolume_get_composition (find the layer/clip that holds the TD source)',
    'resolume_set_layer_blend_mode (Add for live looks: no alpha needed)',
    'resolume_trigger_clip / resolume_trigger_column (fire it)',
    'resolume_set_layer_opacity / resolume_set_layer_bypass (mix, and the Arena-side kill)',
    'resolume_get_clip_thumbnail next to td_screenshot (look at it)',
]


def check_res(res):
    """None (follow the input) or [w, h] ints within RES_LIMITS; anything else raises."""
    if res is None:
        return None
    if not isinstance(res, (list, tuple)) or len(res) != 2:
        raise ValueError('res must be [w, h], got {!r}'.format(res))
    out = []
    for v in res:
        if isinstance(v, bool) or not isinstance(v, numbers.Real) or int(v) != v:
            raise ValueError('res values must be whole numbers, got {!r}'.format(res))
        if not RES_LIMITS[0] <= int(v) <= RES_LIMITS[1]:
            raise ValueError('res values must be {}..{}, got {!r}'.format(RES_LIMITS[0], RES_LIMITS[1], res))
        out.append(int(v))
    return out


def ndi_source_name(host, sender):
    """How NDI receivers (Arena, NDI In TOP) list a source: 'MACHINE (name)'. Machine = host without the domain,
    upper case (NDI convention; the exact Arena label is unverified, research AI open question 4)."""
    h = str(host or '').split('.')[0].upper() or 'HOST'
    return '{} ({})'.format(h, sender)


def alpha_step(alpha, source_alpha):
    """The one op that turns source_alpha into alpha, or None. TD composites are premultiplied by default
    (research AI Patterns 3), so the default pair (premultiplied -> premultiplied) needs nothing."""
    if alpha not in PUBLISH_ALPHAS:
        raise ValueError('alpha must be one of {}, got {!r}'.format(PUBLISH_ALPHAS, alpha))
    if source_alpha not in SOURCE_ALPHAS:
        raise ValueError('source_alpha must be one of {}, got {!r}'.format(SOURCE_ALPHAS, source_alpha))
    if alpha == source_alpha:
        return None
    if alpha == 'premultiplied':
        return {'name': 'alpha', 'type': 'levelTOP', 'pars': {'premultrgbbyalpha': True}, 'does': 'premultiply'}
    if alpha == 'straight':
        return {'name': 'alpha', 'type': 'glslTOP', 'shader': 'unpremult', 'does': 'un-premultiply'}
    key = 'opaque' if source_alpha == 'premultiplied' else 'opaque_straight'
    return {'name': 'alpha', 'type': 'glslTOP', 'shader': key, 'does': 'drop alpha (over black)'}


def plan_publish(name, source, transport='syphon', alpha='premultiplied', source_alpha='premultiplied', res=None,
                 sender=None, host='', available=('syphon', 'ndi'), cook_rate=60):
    """Everything td_publish builds, as data (no TD calls). Raises ValueError on bad args; returns
    {available: False, note} when no requested transport can be created on this build/platform."""
    if not isinstance(name, str) or not PUBLISH_NAME_RE.match(name):
        raise ValueError('name must be a letter then letters/digits/_ (max 40), got {!r}'.format(name))
    if not isinstance(source, str) or not source.startswith('/'):
        raise ValueError('source must be an absolute TOP path, got {!r}'.format(source))
    if transport not in PUBLISH_TRANSPORTS:
        raise ValueError('transport must be one of {}, got {!r}'.format(PUBLISH_TRANSPORTS, transport))
    res = check_res(res)
    step = alpha_step(alpha, source_alpha)
    sender = 'TD_' + name if sender is None else sender
    if not isinstance(sender, str) or not SENDER_NAME_RE.match(sender):
        raise ValueError('sender must be 1-63 chars of letters/digits/space/_.- , got {!r}'.format(sender))
    want = ['syphon', 'ndi'] if transport == 'both' else [transport]
    kinds = [k for k in want if k in available]
    notes = ['{} Out cannot be created on this build/platform: skipped'.format(k) for k in want if k not in kinds]
    if not kinds:
        return {'available': False, 'note': 'needs {}: not creatable in this TD'.format(
            ' / '.join(SENDER_TYPES[k] for k in want))}
    chain = [{'name': 'src', 'type': 'selectTOP', 'pars': {'top': source}}]
    if res:
        chain.append({'name': 'fit', 'type': 'fitTOP', 'pars': {
            'fit': {'menu': 'fitbest'}, 'outputresolution': {'menu': 'custom'},
            'resolutionw': res[0], 'resolutionh': res[1]}})
    if step:
        chain.append(step)
    chain.append({'name': 'out', 'type': 'nullTOP', 'pars': {}})
    senders, arena = [], {}
    for k in kinds:
        if k == 'syphon':
            pars = {'sendername': sender}
            arena['syphon'] = sender
        else:
            fps = cook_rate if isinstance(cook_rate, numbers.Real) and cook_rate > 0 else 60
            pars = {'name': sender, 'fps': fps, 'lowperformancebehavior': {'menu': 'skipframes'},  # T-43
                    'outputpixelformat': {'menu': 'fixed8'}, 'includealpha': alpha != 'none'}
            arena['ndi'] = ndi_source_name(host, sender)
        senders.append({'kind': k, 'name': SENDER_OPS[k], 'type': SENDER_TYPES[k], 'pars': pars})
    return {'comp': PUBLISH_PREFIX + name, 'sender': sender, 'chain': chain, 'senders': senders, 'arena': arena,
            'res': res, 'alpha': {'out': alpha, 'source': source_alpha, 'step': step['does'] if step else None},
            'notes': notes,
            'config': {'source': source, 'transport': transport, 'alpha': alpha, 'source_alpha': source_alpha,
                       'res': res, 'sender': sender}}


def publish_conflicts(stored, given):
    """Keys where a call asks for something else than the COMP was built with (None in given = not asked)."""
    out = []
    for k, v in sorted(given.items()):
        if v is None:
            continue
        s = stored.get(k)
        if k == 'res':
            v = list(v)
            s = list(s) if s else None
        if v != s:
            out.append(k)
    return out


def alpha_note(alpha):
    if alpha == 'premultiplied':
        return ('premultiplied out (bundle rule): leave the Arena clip Alpha Type on its default Premultiplied; '
                'halos -> try Straight, do not guess. Not checked in Arena until the ramp test (AI T5).')
    if alpha == 'straight':
        return 'straight out: set the Arena clip Alpha Type to Straight. Not checked in Arena (AI T5).'
    return 'no alpha (opaque, over black): use Add blend in Arena.'


def publish_reply(comp_path, cfg, arena, active, built, cook_rate):
    """The compact reply: what to pick in Arena and which resolume-723 tools come next."""
    pick = {}
    if 'syphon' in arena:
        pick['syphon'] = {'sendername': arena['syphon'],
                          'arena': 'Sources > Syphon/Spout: "{}" (Arena may show the app name with it: '
                                   'unverified)'.format(arena['syphon'])}
    if 'ndi' in arena:
        pick['ndi'] = {'name': cfg.get('sender'), 'arena': 'Sources > NDI: "{}" (Wi-Fi off, Arena allowed in '
                                                           'Local Network privacy)'.format(arena['ndi'])}
    r = {'comp': comp_path, 'built': bool(built), 'active': bool(active), 'pick_in_arena': pick,
         'res': cfg.get('res') or 'input', 'cookRate': cook_rate, 'alpha': alpha_note(cfg.get('alpha'))}
    if active:
        r['next'] = ('Arena (scratch composition, not the show file): drag the source onto a clip; then the '
                     'resolume-723 tools below. Each Arena call = the user\'s go-ahead.')
        r['resolume_723'] = list(RESOLUME_723_NEXT)
    else:
        r['next'] = ('inactive: nothing is published. td_publish {name, active:true} starts it '
                     '(a Syphon/NDI sender = the user\'s go-ahead).')
    return r


def dup_senders(rows):
    """Sender names used by more than one active-or-not sender of the same kind (Arena keeps sources by name)."""
    seen = {}
    for r in rows:
        key = (r.get('kind'), r.get('sender'))
        seen[key] = seen.get(key, 0) + 1
    return sorted('{} "{}" x{}'.format(k, s, n) for (k, s), n in seen.items() if n > 1 and s)


def _sender_kind(o):
    t = _try(lambda: o.OPType, '')
    for k, v in SENDER_TYPES.items():
        if t == v:
            return k
    return None


def _set_one(o, name, value, notes):
    """One par, never raising for a par the build lacks (NDI/Syphon pars are help-only, not in our dump)."""
    try:
        plans, _w = _plan_pars(o, {name: value})
        _apply_plans(plans)
    except Exception as e:
        notes.append('{}.{} not set: {}'.format(o.name, name, str(e)[:120]))


def _wire(src, dst):
    src.outputConnectors[0].connect(dst.inputConnectors[0])  # connector to connector (T-00c)
    if _inputs(dst)[:1] != [src.path]:
        raise RuntimeError('wire check failed: {} input 0 is not {}'.format(dst.path, src.path))


def _sender_active(o, value):
    """Set a sender's / listener's `active` par; a missing par raises (never leave a network op in an unknown state)."""
    p = o.par['active']
    if p is None:
        raise RuntimeError('{} has no active par: refusing to leave it in an unknown state'.format(o.path))
    p.val = bool(value)


class NotCreatable(Exception):
    """An op type this TD cannot create here (licence, platform, missing device layer)."""


def _publish_build(par_, plan):
    """Build publish_<name>; senders are created and switched off before anything feeds them, with cooking off
    in the COMP while it is built. Any failure destroys the half-built COMP."""
    comp = par_.create(td.baseCOMP, plan['comp'])
    _try(lambda: setattr(comp, 'allowCooking', False))
    notes = list(plan['notes'])
    try:
        senders = []
        for s in plan['senders']:
            try:
                o = comp.create(getattr(td, s['type']), s['name'])
            except Exception as e:
                raise NotCreatable('{} could not be created: {}'.format(s['type'], str(e)[:160]))
            _sender_active(o, False)
            for k, v in s['pars'].items():
                _set_one(o, k, v, notes)
            senders.append(o)
        prev = None
        for step in plan['chain']:
            o = comp.create(getattr(td, step['type']), step['name'])
            if step.get('pars'):
                plans, _w = _plan_pars(o, step['pars'])
                _apply_plans(plans)
            if step.get('shader'):
                # a GLSL TOP may bring its own docked <name>_pixel DAT: reuse it, else make one
                d = comp.op(step['name'] + '_pixel') or comp.create(td.textDAT, step['name'] + '_pixel')
                d.text = GLSL_ALPHA[step['shader']]
                o.par.pixeldat = d.name
                _try(lambda: setattr(d, 'dock', o))
            if prev is not None:
                _wire(prev, o)
            prev = o
        for o in senders:
            _wire(prev, o)
        if any(s['kind'] == 'ndi' for s in plan['senders']):
            info = comp.create(td.infoCHOP, 'ndi_info')
            info.par.op = SENDER_OPS['ndi']
        comp.store(PUBLISH_KEY, plan['config'])
        _try(lambda: setattr(comp, 'comment', 'td_publish {} ({}); built inactive'.format(
            plan['sender'], plan['config']['transport'])))
        for o in comp.children:
            if _family(o) in VIEWER_FAMILIES:
                _try(lambda: setattr(o, 'viewer', True))
    except Exception:
        _try(comp.destroy)
        raise
    _try(lambda: setattr(comp, 'allowCooking', True))
    return comp, notes


def _publish_set_active(comp, active):
    for k in SENDER_OPS.values():
        o = comp.op(k)
        if o is not None:
            _sender_active(o, active)


def cmd_publish(name, source=None, transport=None, alpha=None, source_alpha=None, res=None, active=False,
                parent='/project1', sender=None):
    """Build publish_<name> (Select -> Fit? -> alpha? -> Null out -> Syphon/NDI Out, inactive), or on an existing
    one flip its senders to `active` (other args must match what it was built with)."""
    if not isinstance(name, str) or not PUBLISH_NAME_RE.match(name):
        raise ValueError('name must be a letter then letters/digits/_ (max 40), got {!r}'.format(name))
    par_ = _op(parent, 'parent')
    if not _try(lambda: par_.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(par_.path))
    cook_rate = to_json(_try(lambda: project.cookRate))  # noqa: F405
    host = _try(lambda: __import__('socket').gethostname(), '')
    comp = par_.op(PUBLISH_PREFIX + name)
    if comp is not None:
        cfg = _try(lambda: comp.fetch(PUBLISH_KEY, None, search=False))
        if not isinstance(cfg, dict):
            raise ValueError('{} exists but was not made by td_publish (no stored config): pick another name'.format(
                comp.path))
        given = {'source': source, 'transport': transport, 'alpha': alpha, 'source_alpha': source_alpha,
                 'res': check_res(res), 'sender': sender}
        diff = publish_conflicts(cfg, given)
        if diff:
            raise ValueError('{} exists with other {}: td_delete it first, or pass only name + active'.format(
                comp.path, diff))
        _publish_set_active(comp, active)
        arena = {}
        for k in SENDER_OPS:
            if comp.op(SENDER_OPS[k]) is not None:
                arena[k] = cfg['sender'] if k == 'syphon' else ndi_source_name(host, cfg['sender'])
        return publish_reply(comp.path, cfg, arena, active, False, cook_rate)
    if source is None:
        raise ValueError('source (an absolute TOP path) is needed to build {}{}'.format(PUBLISH_PREFIX, name))
    src = _op(source, 'source')
    if _family(src) != 'TOP':
        raise ValueError('source must be a TOP (for a COMP, pass its out TOP), got {} {}'.format(
            _try(lambda: src.OPType, '?'), src.path))
    have = tuple(k for k, t in SENDER_TYPES.items() if isinstance(getattr(td, t, None), builtins.type))
    plan = plan_publish(name, src.path, transport or 'syphon', alpha or 'premultiplied',
                        source_alpha or 'premultiplied', res, sender, host, have, cook_rate)
    if plan.get('available') is False:
        return plan
    try:
        comp, notes = _publish_build(par_, plan)
    except NotCreatable as e:
        return {'available': False, 'note': str(e)}
    if active:
        _publish_set_active(comp, True)
    r = publish_reply(comp.path, plan['config'], plan['arena'], active, True, cook_rate)
    r['ops'] = [o.name for o in comp.children]
    if notes:
        r['notes'] = notes
    lay = [x for x in (_arrange(comp), _arrange(par_)) if x]
    if lay:
        r['layout'] = lay
    _point_pane(comp)
    return r


def _publish_row(o):
    kind = _sender_kind(o)
    p = lambda n: to_json(_try(lambda: o.par[n].eval()))  # noqa: E731
    ins = _inputs(o)
    row = {'path': o.path, 'kind': kind, 'sender': p('sendername' if kind == 'syphon' else 'name'),
           'active': bool(_try(lambda: o.par['active'].eval(), False)),
           'width': to_json(_try(lambda: o.width)), 'height': to_json(_try(lambda: o.height)),
           'input': ins[0] if ins else None, 'cookTime': rnd(_try(lambda: o.cookTime, 0))}
    if kind == 'ndi':
        row.update({'fps': p('fps'), 'includealpha': p('includealpha'), 'lowperf': p('lowperformancebehavior'),
                    'pixelformat': p('outputpixelformat')})
        info = _try(lambda: o.parent().op('ndi_info'))
        if info is not None:
            for ch in ('skipped_frames', 'last_send_time'):
                v = _try(lambda: info[ch].eval())
                if v is not None:
                    row[ch] = rnd(v)
    pc = _try(lambda: o.parent())
    if pc is not None and isinstance(_try(lambda: pc.fetch(PUBLISH_KEY, None, search=False)), dict):
        row['comp'] = pc.path
    return row


def cmd_publish_status(name=None):
    """Read-only: every Syphon/NDI Out TOP in the project (publish COMPs first) with name, active, size, cook."""
    rows, comps = [], []
    for o in _try(lambda: op('/').findChildren(), []):  # noqa: F405
        if _protected(o.path):
            continue
        if _sender_kind(o):
            rows.append(o)
        elif str(_try(lambda: o.name, '')).startswith(PUBLISH_PREFIX):
            cfg = _try(lambda: o.fetch(PUBLISH_KEY, None, search=False))
            if isinstance(cfg, dict):
                comps.append({'path': o.path, 'config': cfg})
    if name:
        want = PUBLISH_PREFIX + str(name)
        rows = [o for o in rows if _try(lambda: o.parent().name) == want]
        comps = [c for c in comps if c['path'].rsplit('/', 1)[-1] == want]
    out = [_publish_row(o) for o in rows[:PUBLISH_STATUS_CAP]]
    out.sort(key=lambda r: (r.get('comp') is None, r['path']))
    r = {'senders': out, 'count': len(rows), 'truncated': len(rows) > PUBLISH_STATUS_CAP,
         'publish_comps': comps[:PUBLISH_STATUS_CAP], 'cookRate': to_json(_try(lambda: project.cookRate)),  # noqa: F405
         'active': sum(1 for x in out if x['active'])}
    d = dup_senders(out)
    if d:
        r['warnings'] = ['duplicate sender names (Arena keeps sources by name): ' + ', '.join(d)]
    if out and any(x['width'] in (None, 0) for x in out):
        r['notes'] = ['a size of 0/None = the sender has not cooked yet (inactive or unviewed)']
    return r


# ------------------------------------------------------------------ OSC learn (Arena OSC Output -> TD table)

OSC_LEARN_PREFIX = 'osc_learn_'
OSC_LEARN_KEY = 'jazib_osc_learn'
OSC_LEARN_HEADER = ['address', 'count', 'first_s', 'last_s', 'args']
OSC_LEARN_MAX_ADDR = 5000
OSC_LEARN_MAX_S = 600
OSC_LEARN_ACTIONS = ('build', 'start', 'stop', 'export')
OSC_PORT_NOTE = ('port {port}: Arena has one OSC Output target (prefs 127.0.0.1:7001). While this listener is active, '
                 'resolume-723 osc_query / osc_subscribe (they bind 7001) get EADDRINUSE and go quiet; osc_send still '
                 'works (it sends to 7000). Stop learn before using them, or use REST reads (research AI section 4).')

# Callbacks DAT text for the OSC In DAT: one row per address (count, first/last seen, last args). ASCII only.
OSC_LEARN_CB = '''# td_osc_learn callbacks (jazib-td): one row per OSC address in the sibling table "learned".
import time

def onReceiveOSC(dat, rowIndex, message, bytes, timeStamp, address, args, peer):
    t = dat.parent().op('learned')
    if t is None:
        return
    a = str(address)
    now = '%.3f' % time.time()
    vals = ' '.join(str(x) for x in list(args)[:4])[:80]
    r = t.row(a) if t.numRows > 1 else None
    if r is None:
        if t.numRows <= MAX_ADDR:
            t.appendRow([a, 1, now, now, vals])
        return
    c = t[a, 'count']
    c.val = int(c.val) + 1
    t[a, 'last_s'] = now
    t[a, 'args'] = vals
    return
'''.replace('MAX_ADDR', str(OSC_LEARN_MAX_ADDR))

# Execute DAT: keeps the OSC In DAT cooking while active even when no viewer shows it (T-02/T-29 pattern).
OSC_LEARN_EXEC = '''# td_osc_learn: force-cook the OSC In DAT each frame while it is active (unviewed ops do not cook).

def onFrameStart(frame):
    o = me.parent().op('osc_in')
    if o is not None and o.par.active.eval():
        o.cook(force=True)
    return
'''


def osc_export_name(arena_build=None):
    """osc_addresses_<build>.json; the build string is sanitised (default 'arena')."""
    b = re.sub(r'[^A-Za-z0-9._-]+', '_', str(arena_build or 'arena')).strip('._') or 'arena'
    return 'osc_addresses_{}.json'.format(b[:60])


def learned_export(rows, meta):
    """The export JSON from the learned table rows (row 0 = header). Sorted by address, counts as ints."""
    addrs = []
    for r in list(rows)[1:]:
        r = [str(x) for x in r] + [''] * (5 - len(r))
        try:
            n = int(float(r[1]))
        except Exception:
            n = 0
        addrs.append({'address': r[0], 'count': n, 'first_s': rnd(_try(lambda: float(r[2]), None)),
                      'last_s': rnd(_try(lambda: float(r[3]), None)), 'args': r[4]})
    addrs.sort(key=lambda a: a['address'])
    out = {'format': 'jtd-osc-learn', 'v': 1}
    out.update(meta)
    out.update({'count': len(addrs), 'messages': sum(a['count'] for a in addrs),
                'note': 'map = starting point, not gospel: re-learn on any Arena change; indices are 1-based',
                'addresses': addrs})
    return out


def learned_top(rows, n=15):
    """The n busiest addresses (compact reply)."""
    a = learned_export(rows, {})['addresses']
    a.sort(key=lambda x: -x['count'])
    return [[x['address'], x['count']] for x in a[:n]]


def _osc_learn_build(par_, port):
    comp = par_.create(td.baseCOMP, OSC_LEARN_PREFIX + str(port))
    _try(lambda: setattr(comp, 'allowCooking', False))
    notes = []
    try:
        try:
            o = comp.create(td.oscinDAT, 'osc_in')
        except Exception as e:
            raise NotCreatable('oscinDAT could not be created: {}'.format(str(e)[:160]))
        _sender_active(o, False)
        cb = comp.create(td.textDAT, 'osc_cb')
        cb.text = OSC_LEARN_CB
        for k, v in (('protocol', {'menu': 'msging'}), ('port', int(port)), ('callbacks', 'osc_cb')):
            _set_one(o, k, v, notes)
        _try(lambda: setattr(cb, 'dock', o))
        t = comp.create(td.tableDAT, 'learned')
        t.clear()
        t.appendRow(OSC_LEARN_HEADER)
        ex = comp.create(td.executeDAT, 'keep_cooking')
        ex.text = OSC_LEARN_EXEC
        _set_one(ex, 'framestart', True, notes)
        comp.store(OSC_LEARN_KEY, {'port': int(port)})
        _try(lambda: setattr(comp, 'comment', 'td_osc_learn port {}: built inactive'.format(port)))
        for k in comp.children:
            if _family(k) in VIEWER_FAMILIES:
                _try(lambda: setattr(k, 'viewer', True))
    except Exception:
        _try(comp.destroy)
        raise
    _try(lambda: setattr(comp, 'allowCooking', True))
    return comp, notes


def _osc_learn_export(comp, file, arena_build, port):
    t = comp.op('learned')
    rows = [[c.val for c in row] for row in _try(lambda: t.rows(), [])] if t is not None else []
    meta = {'arena_build': str(arena_build or 'unknown'), 'port': int(port),
            'td_build': td_build_string(_try(lambda: app.version, ''), _try(lambda: app.build, '')),  # noqa: F405
            'exported': time.strftime('%Y-%m-%dT%H:%M:%S')}
    data = learned_export(rows, meta)
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    return {'file': file, 'count': data['count'], 'messages': data['messages']}


def cmd_osc_learn(action='build', port=7001, seconds=None, parent='/project1', arena_build=None, file=None,
                  clear=False):
    """build: osc_learn_<port> (OSC In DAT inactive + callbacks + learned table); start: listen (seconds: stop and
    export after that long, reply then); stop: stop + export; export: write the file only."""
    if action not in OSC_LEARN_ACTIONS:
        raise ValueError('action must be one of {}, got {!r}'.format(OSC_LEARN_ACTIONS, action))
    port = clamp_int(port, 7001, 1, 65535)
    if seconds is not None and not (isinstance(seconds, numbers.Real) and 0 < seconds <= OSC_LEARN_MAX_S):
        raise ValueError('seconds must be 1..{}'.format(OSC_LEARN_MAX_S))
    if file is not None:
        _abs_file(file, ('.json',))
    if (action in ('stop', 'export') or (action == 'start' and seconds)) and file is None:
        raise ValueError('file (absolute .json) is needed to export (the MCP server passes it)')
    par_ = _op(parent, 'parent')
    comp = par_.op(OSC_LEARN_PREFIX + str(port))
    notes, built = [], False
    if comp is None:
        if action in ('stop', 'export'):
            raise ValueError('no {}{} under {}: action build first'.format(OSC_LEARN_PREFIX, port, par_.path))
        if not isinstance(getattr(td, 'oscinDAT', None), builtins.type):
            return {'available': False, 'note': 'oscinDAT is not in this TD build'}
        try:
            comp, notes = _osc_learn_build(par_, port)
        except NotCreatable as e:
            return {'available': False, 'note': str(e)}
        built = True
    osc = comp.op('osc_in')
    if osc is None:
        raise ValueError('{} has no osc_in DAT'.format(comp.path))
    r = {'comp': comp.path, 'built': built, 'port': port, 'port_note': OSC_PORT_NOTE.format(port=port)}
    if action == 'start':
        t = comp.op('learned')
        if clear and t is not None:
            t.clear()
            t.appendRow(OSC_LEARN_HEADER)
        _sender_active(osc, True)
    elif action == 'stop':
        _sender_active(osc, False)
    if built:
        lay = [x for x in (_arrange(comp), _arrange(par_)) if x]
        if lay:
            r['layout'] = lay
        _point_pane(comp)
    if notes:
        r['notes'] = notes

    def finish(stop=False):
        if stop:
            _sender_active(osc, False)
        t = comp.op('learned')
        rows = [[c.val for c in row] for row in _try(lambda: t.rows(), [])] if t is not None else []
        r['active'] = bool(_try(lambda: osc.par['active'].eval(), False))
        r['addresses'] = max(0, len(rows) - 1)
        r['top'] = learned_top(rows)
        if file is not None and (stop or action in ('stop', 'export')):
            r['export'] = _osc_learn_export(comp, file, arena_build, port)
        if r['active']:
            r['next'] = 'listening: wiggle Arena controls, then td_osc_learn {action:"stop"} to stop + export'
        elif action == 'build':
            r['next'] = ('inactive. User: Arena Preferences > OSC > Output on (127.0.0.1:{}); then td_osc_learn '
                         '{{action:"start", seconds:60}} (opens a UDP port = the user\'s go-ahead)'.format(port))
        return r
    if action == 'start' and seconds:
        rate = _try(lambda: float(project.cookRate), 60.0) or 60.0  # noqa: F405
        return Pending(int(math.ceil(float(seconds) * rate)) + 1, lambda: finish(stop=True))
    return finish()
# ------------------------------------------------------------------ Ableton (docs/research/AJ_td_ableton.md section 4)
# td_link: Ableton Link CHOP (pars from docs/research/ops/ops_CHOP_2025.31550.json, channel names from TD's offline
# help Ableton_Link_CHOP.htm). td_tda: TDAbleton palette (Derivative, Ivan DelSol; v2.6.3 ships in 2025.31550),
# pars read from its tdAbleton.cparm (toeexpand, 26 Oct 2026). td_live_audio: source of the AC_audio COMP.

# (Link CHOP channel, name in <link>/out)
LINK_OUT = (('beat', 'beat'), ('bar', 'bar'), ('ramp', 'bar_ramp'), ('tempo', 'tempo'), ('numpeers', 'peers'))
LINK_STATUS = ('numpeers', 'linked', 'waiting', 'synced')
LINK_INFO = ('ableton_is_playing', 'ableton_tempo', 'ableton_clock_diff', 'ableton_time_behind_link')
LINK_CHAN_CAP = 24


def plan_link(enable=False):
    """td_link ops in build order: (name, op type, pars, input op name or None). Link stays off unless asked."""
    return [
        ('link1', 'abletonlinkCHOP', {'enable': bool(enable), 'status': True, 'ramp': True, 'bar': True,
                                      'beat': True, 'tempo': True}, None),
        ('sel', 'selectCHOP', {'channames': ' '.join(a for a, _ in LINK_OUT)}, 'link1'),
        ('ren', 'renameCHOP', {'renamefrom': ' '.join(a for a, b in LINK_OUT if a != b),
                               'renameto': ' '.join(b for a, b in LINK_OUT if a != b)}, 'sel'),
        ('out', 'nullCHOP', {}, 'ren'),
        ('info', 'infoCHOP', {'op': 'link1'}, None),  # op resolved to link1's path when built
    ]


def link_summary(out_vals, link_vals, info_vals, enable):
    """Compact td_link / td_link_status reply from {channel: value} dicts of out, link1 and info."""
    want = [b for _, b in LINK_OUT]
    r = {'enable': bool(enable),
         'out': dict((k, rnd(out_vals[k])) for k in want if k in out_vals),
         'status': dict((k, rnd(link_vals[k])) for k in LINK_STATUS if k in link_vals),
         'info': dict((k, rnd(info_vals[k])) for k in LINK_INFO if k in info_vals)}
    missing = [k for k in want if k not in out_vals]
    if missing:
        r['missing'] = missing
        r['link_channels'] = sorted(link_vals)[:LINK_CHAN_CAP]
        r['note'] = 'out lacks {}: compare link_channels with the sel/ren pars'.format(missing)
    peers = r['status'].get('numpeers', r['out'].get('peers'))
    if not enable:
        r['hint'] = 'Link is off: td_link {enable:true} joins the session (then ableton-live set_ableton_link true)'
    elif not peers:
        r['hint'] = ('no Link peers: turn Link on in Live (ableton-live set_ableton_link true); same Mac or LAN; '
                     'macOS may ask for Local Network permission')
    return r


def _chop_vals(o, cap=64):
    """{channel name: current value} of a CHOP (first cap channels); {} when unreadable."""
    out = {}
    if o is None:
        return out
    _try(lambda: o.cook(force=True))
    for c in (_try(lambda: list(o.chans()), []) or [])[:cap]:
        n = str(_try(lambda: c.name, ''))
        v = _try(lambda: c.eval(), None)
        if v is None:
            v = _try(lambda: list(c.vals)[-1], None)
        if n:
            out[n] = v
    return out


def _build_chain(comp, plan):
    """Create plan ops inside comp (validated pars, viewers on, wired input 0), left to right. Returns the ops."""
    made, x = {}, 0
    for name, optype, pars, src in plan:
        cls = getattr(td, optype, None)
        if cls is None:
            raise ValueError('TD has no op type {}'.format(optype))
        o = comp.create(cls, name)
        o.nodeX, o.nodeY = x, 0 if src or optype != 'infoCHOP' else -160
        x += 160
        pars = dict(pars)
        if optype == 'infoCHOP' and 'op' in pars:
            pars['op'] = made[pars['op']].path
        if pars:
            plans, warns = _plan_pars(o, pars)
            if warns:  # a refused value must not vanish silently (T-62)
                raise ValueError('{}: {}'.format(o.path, '; '.join(warns)))
            _apply_plans(plans)
        if src:
            o.inputConnectors[0].connect(made[src].outputConnectors[0])
        _try(lambda: setattr(o, 'viewer', True))
        made[name] = o
    return made


def _link_reply(comp):
    link = comp.op('link1')
    r = link_summary(_chop_vals(comp.op('out')), _chop_vals(link), _chop_vals(comp.op('info')),
                     bool(_try(lambda: link.par.enable.eval(), False)))
    r['path'] = comp.path
    return r


def cmd_link(parent='/project1', name='link', enable=False):
    par_ = _op(parent, 'parent')
    if not _try(lambda: par_.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(par_.path))
    if not valid_op_name(name):
        raise ValueError('bad operator name {!r}'.format(name))
    comp = par_.op(name)
    if comp is not None:  # already built: only the enable switch changes (build first, enable on request)
        link = comp.op('link1')
        if link is None:
            raise ValueError('{} exists and is not a td_link COMP (no link1)'.format(comp.path))
        link.par.enable = bool(enable)
        r = _link_reply(comp)
        r['built'] = False
        return r
    comp = par_.create(td.baseCOMP, name)
    try:
        comp.nodeX, comp.nodeY = _auto_xy(par_, comp)
        _build_chain(comp, plan_link(enable))
        _try(lambda: setattr(comp, 'comment', 'Ableton Link -> out: beat bar bar_ramp tempo peers (jazib-td td_link)'))
    except Exception:
        _try(comp.destroy)
        raise
    lay = _arrange(comp)
    _arrange(par_)
    _point_pane(comp)
    r = _link_reply(comp)
    r.update({'built': True, 'layout': lay, 'ops': ['link1', 'sel', 'ren', 'out', 'info']})
    return r


def cmd_link_status(path='/project1/link'):
    comp = _op(path)
    if comp.op('link1') is None:
        raise ValueError('{} is not a td_link COMP (no link1)'.format(comp.path))
    return _link_reply(comp)


# --- TDAbleton

TDA_PALETTE_REL = ('Palette/TDAbleton/Live 11+',)
TDA_SCRIPT_REL = 'TDAbleton/Live 11+/TouchDesigner'
TDA_PACKAGE = 'tdAbletonPackage.tox'
TDA_RISK = ('TDAbleton\'s Live Remote Script binds its OSC server to 0.0.0.0:58888 and accepts /shell/runCode and '
            '/shell/consoleLine (Python exec inside Live) from any host on the network (AJ section 3/6); loading the '
            'TD side also opens UDP 58811 in TD. Pass accept_risk=true only with the user\'s go-ahead.')
# set on the tdAbleton master right after loadTox (same frame, before its delayed setupConnection runs)
TDA_SAFE_PARS = {'Listenonly': True, 'Abletonaddress': '127.0.0.1', 'Suppresspopupdialogs': True,
                 'Abletonbroadcast': False, 'Startonload': False}
TDA_NEVER = ('Install', 'Installtdableton', 'Updateabletoncomps', 'Start', 'Autostartlive')  # write/launch Live


def tda_load_pars(connect=False):
    """[(par, value)] td_tda load sets on the master, Connect first; never a TDA_NEVER par."""
    return [('Connect', bool(connect))] + sorted(TDA_SAFE_PARS.items())


def tda_version_from_py(text):
    m = re.search(r"^TDA_VERSION\s*=\s*['\"]([^'\"]+)['\"]", text or '', re.M)
    return m.group(1) if m else None


def user_library_from_cfg(text):
    """User Library folder from Live's Library.cfg text (<UserLibrary> ProjectPath + ProjectName); None if absent."""
    m = re.search(r'<UserLibrary>(.*?)</UserLibrary>', text or '', re.S)
    if not m:
        return None
    path = re.search(r'<ProjectPath Value="([^"]*)"', m.group(1))
    name = re.search(r'<ProjectName Value="([^"]*)"', m.group(1))
    if not path or not path.group(1):
        return None
    return os.path.join(path.group(1), name.group(1) if name and name.group(1) else 'User Library')


def _ver_key(s):
    return [int(x) for x in re.findall(r'\d+', s)]


def pick_live_prefs(names):
    """Newest 'Live 12.4.3'-style folder name, or None."""
    lives = [n for n in names if re.match(r'^Live \d', n)]
    return max(lives, key=_ver_key) if lives else None


def _read_text(p, limit=400000):
    try:
        with open(p, 'r', errors='replace') as f:
            return f.read(limit)
    except Exception:
        return None


def _tda_dirs(samples=None, palette=None):
    """(palette folder with the TDAbleton toxes or None, shipped Remote Script folder or None)."""
    samples = samples or _try(lambda: app.samplesFolder, '') or ''  # noqa: F405
    palette = palette or _try(lambda: app.paletteFolder, '') or ''  # noqa: F405
    cands = [os.path.join(palette, 'TDAbleton', 'Live 11+')] if palette else []
    cands += [os.path.join(samples, r) for r in TDA_PALETTE_REL] if samples else []
    pal = next((c for c in cands if os.path.isfile(os.path.join(c, TDA_PACKAGE))), None)
    scr = os.path.join(samples, TDA_SCRIPT_REL) if samples else None
    return pal, (scr if scr and os.path.isdir(scr) else None)


def tda_user_library(home=None):
    """(User Library folder, where it came from). Reads Live's Library.cfg only (never writes it)."""
    home = home or os.path.expanduser('~')
    prefs = os.path.join(home, 'Library', 'Preferences', 'Ableton')
    live = pick_live_prefs(_try(lambda: os.listdir(prefs), []) or [])
    if live:
        lib = user_library_from_cfg(_read_text(os.path.join(prefs, live, 'Library.cfg')))
        if lib:
            return lib, '{}/Library.cfg (read only)'.format(live)
    return os.path.join(home, 'Music', 'Ableton', 'User Library'), 'default'


def tda_check(samples=None, palette=None, home=None):
    pal, scr = _tda_dirs(samples, palette)
    lib, lib_from = tda_user_library(home)
    rs = os.path.join(lib, 'Remote Scripts')
    shipped_v = tda_version_from_py(_read_text(os.path.join(scr, 'TDA.py'))) if scr else None
    inst_dir = os.path.join(rs, 'TouchDesigner')
    inst_v = tda_version_from_py(_read_text(os.path.join(inst_dir, 'TDA.py'))) if os.path.isdir(inst_dir) else None
    r = {'palette': pal, 'palette_toxes': len([f for f in (_try(lambda: os.listdir(pal), []) or [])
                                               if f.endswith('.tox')]) if pal else 0,
         'version': shipped_v, 'shipped_remote_script': scr,
         'user_library': lib, 'user_library_from': lib_from,
         'remote_script_installed': os.path.isdir(inst_dir), 'remote_script_version': inst_v,
         'abletonmcp_installed': os.path.isdir(os.path.join(rs, 'AbletonMCP'))}
    go = []
    if not pal:
        go.append('no-go: TDAbleton palette not found in this TD install')
    if not r['remote_script_installed']:
        go.append('Live side missing: Remote Scripts/TouchDesigner not installed (manual copy of {} = user\'s go-ahead; '
                  'never the Install button, it edits Library.cfg)'.format(scr or TDA_SCRIPT_REL))
    elif shipped_v and inst_v and shipped_v != inst_v:
        go.append('version mismatch: installed {} vs shipped {}'.format(inst_v, shipped_v))
    go.append('security: ' + TDA_RISK)
    r['checks'] = go
    r['ready'] = bool(pal and r['remote_script_installed'] and (not shipped_v or inst_v == shipped_v))
    return r


def cmd_tda_check():
    r = tda_check()
    loaded = _tda_master()
    r['loaded'] = loaded.path if loaded is not None else None
    return r


def _tda_master(path=None):
    """The tdAbleton master COMP: at path (a package or the master), else op.TDAbleton, else a search."""
    def master_of(o):
        if o is None:
            return None
        if o.par['Abletonport'] is not None and o.par['Listenonly'] is not None:
            return o
        return _try(lambda: o.op('tdAbleton'))
    if path:
        m = master_of(_op(path))
        if m is None:
            raise ValueError('{} is not TDAbleton (no tdAbleton master)'.format(path))
        return m
    m = _try(lambda: op.TDAbleton, None)  # noqa: F405 -- its global op shortcut
    if m is not None:
        return m
    root_ = _try(lambda: op('/project1'), None)  # noqa: F405
    found = _try(lambda: root_.findChildren(name='tdAbleton', maxDepth=4), []) or []
    return found[0] if found else None


def cmd_tda_load(parent='/project1', name='tda', accept_risk=False, connect=False):
    if not accept_risk:
        return {'loaded': False, 'needs': 'accept_risk=true', 'why': TDA_RISK}
    par_ = _op(parent, 'parent')
    if not valid_op_name(name):
        raise ValueError('bad operator name {!r}'.format(name))
    if par_.op(name) is not None:
        raise ValueError('{}/{} already exists'.format(par_.path.rstrip('/'), name))
    pal, _scr = _tda_dirs()
    if not pal:
        raise ValueError('TDAbleton palette not found (app.samplesFolder / app.paletteFolder)')
    o = par_.loadTox(os.path.join(pal, TDA_PACKAGE))
    o.name = name
    m = _try(lambda: o.op('tdAbleton'))
    set_, notes = [], []
    if m is None:
        notes.append('no tdAbleton master inside the package: nothing set, check it by hand')
    else:
        # Connect first: a Listenonly/Abletonaddress change re-runs its setupConnection, which connects if Connect is on
        for k, v in tda_load_pars(connect):
            p = m.par[k]
            if p is None:
                notes.append('no par ' + k)
            elif _try(lambda: p.eval(), None) != v and _try(lambda: setattr(p, 'val', v) or True, False):
                set_.append(k)
    xy = _try(lambda: _auto_xy(par_, o))
    if xy:
        o.nodeX, o.nodeY = xy
    lay = _arrange(par_)
    _point_pane(o)
    return {'loaded': True, 'path': o.path, 'master': m.path if m is not None else None,
            'version': _try(lambda: str(m.par.Version.eval())), 'set': set_, 'connect': bool(connect),
            'never_pressed': list(TDA_NEVER), 'layout': lay, 'notes': notes,
            'hint': ('Connect is off: install the Live Remote Script first (td_tda check), then set Connect on'
                     if not connect else 'Connect on: Listen Only, 127.0.0.1; td_tda status to see the song')}


def dup_names(names):
    seen, dup = set(), []
    for n in names:
        if n in seen and n not in dup:
            dup.append(n)
        seen.add(n)
    return dup


def cmd_tda_status(path=None):
    m = _tda_master(path)
    if m is None:
        return {'loaded': False, 'hint': 'no TDAbleton in /project1: td_tda {action:"check"} then "load"'}
    pv = lambda k: to_json(_try(lambda: m.par[k].eval()))  # noqa: E731
    ext_ = _try(lambda: m.ext.TDAbletonExt)
    info = _try(lambda: ext_.SongInfo, {}) or {}
    tracks = _try(lambda: list(info.get('tracks', {})), []) or []
    return {'loaded': True, 'master': m.path, 'version': pv('Version'),
            'connected': bool(_try(lambda: ext_.Connected, False)),
            'pars': dict((k, pv(k)) for k in ('Connect', 'Listenonly', 'Abletonaddress', 'Abletonport', 'Inport',
                                                'Maxport', 'Abletonbroadcast')),
            'tracks': [clip_str(t, 40) for t in tracks[:30]], 'num_tracks': len(tracks),
            'duplicate_names': dup_names(tracks)[:20]}


# --- AC_audio source

AC_AUDIO = '/project1/lab/AC_audio'
LOOPBACK_RE = re.compile(r'blackhole|loopback|soundflower|aggregate|multi-output|vb-cable|existential', re.I)
HAL_DIRS = ('/Library/Audio/Plug-Ins/HAL', '~/Library/Audio/Plug-Ins/HAL')


def loopback_names(names):
    return [n for n in names if LOOPBACK_RE.search(str(n))]


def hal_drivers(dirs=HAL_DIRS):
    out = []
    for d in dirs:
        out += sorted(f for f in (_try(lambda: os.listdir(os.path.expanduser(d)), []) or []) if f.endswith('.driver'))
    return out


def _wire_in(dst, i, src):
    ins = list(dst.inputConnectors)
    if i >= len(ins):
        raise RuntimeError('{} has {} input(s), wanted input {}'.format(dst.path, len(ins), i))
    ins[i].connect(src.outputConnectors[0])


def _live_audio_build(comp, src, trim, sel, dev, activate, built):
    """src -> src_sel (in 0) -> trim, src_device = src_sel input 1; names appended to built as made."""
    if sel is None:
        sel = comp.create(td.switchCHOP, 'src_sel')
        sel.nodeX, sel.nodeY = src.nodeX + 160, src.nodeY
        _wire_in(sel, 0, src)
        _wire_in(trim, 0, sel)
        _try(lambda: setattr(sel, 'viewer', True))
        built.append('src_sel')
    if dev is None:
        dev = comp.create(td.audiodeviceinCHOP, 'src_device')
        dev.par.active = bool(activate)  # same frame as create: nothing cooks (or asks for the mic) before this
        dev.nodeX, dev.nodeY = src.nodeX, src.nodeY - 160
        _try(lambda: setattr(dev, 'viewer', True))
        built.append('src_device')
    if len(_try(lambda: list(sel.inputs), [])) < 2:
        _wire_in(sel, 1, dev)
    return sel, dev


def cmd_live_audio(mode='file', file=None, device=None, activate=False, path=AC_AUDIO):
    if mode not in ('file', 'device'):
        raise ValueError("mode must be 'file' or 'device'")
    comp = _op(path)
    src, trim = comp.op('src'), comp.op('trim')
    if src is None or trim is None:
        raise ValueError('{} is not AC_audio (needs src -> trim)'.format(comp.path))
    sel, dev = comp.op('src_sel'), comp.op('src_device')
    notes = []
    r = {'path': comp.path, 'mode': mode}
    if mode == 'file':
        if file:
            if not os.path.isfile(file):
                raise ValueError('no such file {}'.format(file))
            src.par.file = file
        if dev is not None:
            dev.par.active = False
        if sel is not None:
            sel.par.index = 0
        r.update({'source': 'file', 'file': to_json(_try(lambda: src.par.file.eval())),
                  'device_active': False if dev is not None else None})
        return r
    built = []
    try:
        sel, dev = _live_audio_build(comp, src, trim, sel, dev, activate, built)
    except Exception:
        for n in built:  # leave AC_audio as it was: src -> trim
            _try(lambda: comp.op(n).destroy())
        if 'src_sel' in built:
            _try(lambda: trim.inputConnectors[0].connect(src.outputConnectors[0]))
        raise
    labels = _try(lambda: list(dev.par.device.menuLabels), []) or []
    names_ = _try(lambda: list(dev.par.device.menuNames), []) or []
    if device:
        hit, warn = match_menu(names_, labels, device)
        if hit:
            dev.par.device = hit
        else:
            notes.append(warn)
    dev.par.active = bool(activate)
    sel.par.index = 1 if activate else 0
    if not activate:
        notes.append('device built inactive, analysis still on the file: activate=true (mic permission = user\'s go-ahead)')
    r.update({'source': 'device' if activate else 'file', 'built': built, 'device_active': bool(activate),
              'device': to_json(_try(lambda: dev.par.device.eval())),
              'devices': [clip_str(x, 50) for x in labels[:20]], 'num_devices': len(labels),
              'loopback': {'devices': list(dict.fromkeys(loopback_names(labels + names_)))[:10], 'hal_drivers': hal_drivers()[:10]},
              'layout': _arrange(comp), 'notes': notes})
    r['loopback']['blackhole'] = any('blackhole' in str(x).lower()
                                     for x in r['loopback']['devices'] + r['loopback']['hal_drivers'])
    return r


RENDER_CODECS = {
    # key: (videocodec, codec-type match {all, none}, pixel-format match {any} or None, alpha)
    'prores4444': ('prores', {'all': ('4444',), 'none': ('xq',)}, {'any': ('yuva', 'alpha', 'rgba')}, True),
    'prores422hq': ('prores', {'all': ('422', 'hq')}, None, False),
    'hapq': ('hap', {'all': ('q',), 'none': ('alpha', 'hdr')}, None, False),
}


RENDER_MAX_FRAMES = 18000


AE_DATA_FORMATS = ('json', 'csv')


AE_DATA_MAX_CELLS = 2000000


RENDER_OP = '_jz_render'


def pick_menu_entry(names, labels, all_of=(), none_of=(), any_of=()):
    """First menu name whose 'name label' (lower case) holds every all_of token, no none_of token and (when given)
    one any_of token; None when nothing fits. Menus whose names are filled in at run time (videocodectype)."""
    labels = list(labels or [])
    for i, n in enumerate(names or []):
        s = (str(n) + ' ' + str(labels[i] if i < len(labels) else '')).lower()
        if all(t in s for t in all_of) and not any(t in s for t in none_of) and (not any_of or any(t in s for t in any_of)):
            return n
    return None


def render_plan(codec, frames, fps):
    """Validated (codec spec, frames, fps) for offline_render; raises ValueError on a bad request."""
    if codec not in RENDER_CODECS:
        raise ValueError('codec must be one of {}, got {!r}'.format(sorted(RENDER_CODECS), codec))
    try:
        n, f = int(frames), float(fps)
    except Exception:
        raise ValueError('frames and fps must be numbers')
    if not (1 <= n <= RENDER_MAX_FRAMES):
        raise ValueError('frames must be 1..{}, got {}'.format(RENDER_MAX_FRAMES, frames))
    if not (1 <= f <= 240):
        raise ValueError('fps must be 1..240, got {}'.format(fps))
    return RENDER_CODECS[codec], n, f


def pump_script(mfo_path, frames, realtime, cookrate=None):
    """Text of the Execute DAT docked to the recorder: force-cooks it every frame end while Record is on (T-29),
    stops after `frames` and puts realTime back itself (so a handlers reload mid-take cannot leave it off)."""
    return ('# jazib-td offline_render pump (LEARNINGS T-29): force-cook the Movie File Out each frame end.\n'
            'N = {n}\nRT = {rt}\nCR = {cr!r}\nMFO = {p!r}\n\n'
            'def onFrameEnd(frame):\n'
            '    m = op(MFO)\n'
            '    if m is None or not m.par.record.eval():\n'
            '        return\n'
            '    m.cook(force=True)\n'
            '    k = m.fetch(\'jz_n\', 0) + 1\n'
            '    m.store(\'jz_n\', k)\n'
            '    if k >= N:\n'
            '        m.par.record = False\n'
            '        m.store(\'jz_done\', True)\n'
            '        project.realTime = RT\n'

            '    return\n').format(n=int(frames), rt=bool(realtime), cr=cookrate, p=str(mfo_path))


def tsv(rows):
    """Rows -> Table DAT text (tabs/newlines inside cells become spaces)."""
    def cell(v):
        if isinstance(v, float):
            v = rnd(v, 9)
        return re.sub(r'[\t\r\n]+', ' ', '' if v is None else str(v))
    return '\n'.join('\t'.join(cell(v) for v in r) for r in rows)


def ae_data_text(names, rows, fmt, fps, source, frame_col=None):
    """CHOP samples -> AE data footage text. json: {source, fps, frames, channels: {name: [..]}} (+ frame list);
    csv: header 'frame,<names>' then one row per sample (AE expression access: footage(...).dataValue [U])."""
    if fmt not in AE_DATA_FORMATS:
        raise ValueError('format must be json or csv, got {!r}'.format(fmt))
    frames = frame_col if frame_col is not None else list(range(len(rows)))
    if fmt == 'json':
        doc = {'source': source, 'fps': rnd(fps), 'frames': len(rows), 'frame': frames,
               'channels': dict((n, [rnd(r[i], 7) for r in rows]) for i, n in enumerate(names))}
        return json.dumps(doc, separators=(',', ':'))
    lines = [','.join(['frame'] + ['"{}"'.format(str(n).replace('"', "'")) for n in names])]
    for f, r in zip(frames, rows):
        lines.append(','.join([str(f)] + [repr(rnd(v, 7)) for v in r]))
    return '\n'.join(lines) + '\n'


def _setp(o, name, v):
    getattr(o.par, name).val = v


def _new_name(par_, base):
    n, i = base, 2
    while par_.op(n) is not None:
        n, i = '{}{}'.format(base, i), i + 1
    return n


def offline_render(source, file, frames, fps=30, codec='prores4444', timeout_s=None, on_start=None):
    """Shared offline recorder (Pending chain). A FRESH Movie File Out next to `source` (T-30) + docked pump Execute
    DAT (T-29); realTime off for the take, restored after (also on error, and by the pump itself); one movie
    frame per TD frame (content time follows the TD timeline); the temp ops are removed after. file: absolute .mov
    (the MCP keeps it under output/). Reply: frames asked/counted, codec type + pixel format picked, notes; the
    MCP side adds the ffprobe frame count. on_start(): called right after Record goes on (TL_timeline arms its clock
    there, timeline_record)."""
    spec, n, f = render_plan(codec, frames, fps)
    src = _op(source, 'source')
    if _family(src) != 'TOP':
        raise ValueError('{} is not a TOP'.format(src.path))
    _abs_file(file, ('.mov',))
    par_ = src.parent()
    os.makedirs(os.path.dirname(file), exist_ok=True)
    if os.path.isfile(file):
        os.remove(file)  # a new take; never an old file read back by ffprobe
    st = {'rt': None, 'rate': None, 'cooks': None, 'notes': [], 'm': None, 'ex': None, 't0': None,
          'timeout': float(timeout_s) if timeout_s else 60.0 + n * 2.0}
    root_ = _try(lambda: op('/'))  # noqa: F405
    rate = _try(lambda: float(root_.time.rate), None) or _try(lambda: float(project.cookRate), None)  # noqa: F405
    st['rate'] = rate
    if rate and abs(rate - f) > 1e-3:
        st['notes'].append('timeline {} fps, file {} fps: {} cooks for {} frames, content at real speed'.format(
            rnd(rate), rnd(f), int(math.ceil(n * rate / f)), n))
    if _try(lambda: root_.time.play, True) is False:
        st['notes'].append('timeline is paused: content driven by the timeline will not move (absTime still does)')

    def abort(e):
        m = st['m']
        if m is not None and _try(lambda: m.valid, False):
            _try(lambda: _setp(m, 'record', False))
        if st['rt'] is not None:
            _try(lambda: setattr(project, 'realTime', st['rt']))  # noqa: F405
        cleanup_ops()
        raise e

    def cleanup_ops():
        for k in ('m', 'ex'):
            o = st[k]
            if o is not None and _try(lambda: o.valid, False):  # the pump goes with its host (T-28)
                _try(o.destroy)

    try:
        m = par_.create(moviefileoutTOP, _new_name(par_, RENDER_OP))  # noqa: F405
        st['m'] = m
        _try(lambda: setattr(m, 'nodeX', src.nodeX + src.nodeWidth + GAP_X))
        _try(lambda: setattr(m, 'nodeY', src.nodeY - src.nodeHeight - GAP_Y))
        src.outputConnectors[0].connect(m.inputConnectors[0])  # connector to connector (cmd_connect note)
        ex = par_.create(executeDAT, m.name + '_pump')  # noqa: F405
        st['ex'] = ex
        _try(lambda: setattr(ex, 'dock', m))
        for k, v in (('type', 'movie'), ('moviecontainer', 'mov'), ('videocodec', spec[0]), ('file', file), ('fps', f)):
            _setp(m, k, v)
    except Exception as e:
        abort(e)

    def step_codec():
        try:
            m, ex = st['m'], st['ex']
            ct = getattr(m.par, 'videocodectype')
            pick = pick_menu_entry(ct.menuNames, ct.menuLabels, all_of=spec[1].get('all', ()), none_of=spec[1].get('none', ()))
            if pick is None:
                raise RuntimeError('no {} codec type in the menu {}'.format(codec, list(ct.menuLabels)[:12]))
            ct.val = pick
            st['codectype'] = pick
            if spec[2]:
                pf = getattr(m.par, 'videopixelformat')
                pp = pick_menu_entry(pf.menuNames, pf.menuLabels, any_of=spec[2]['any'])
                if pp is None:
                    raise RuntimeError('no alpha pixel format for {} in {}'.format(codec, list(pf.menuLabels)[:12]))
                pf.val = pp
                st['pixfmt'] = pp
            st['rt'] = bool(project.realTime)  # noqa: F405
            # Movie File Out writes by timeline time: a 60 fps timeline gives 1 movie frame per 2 cooks at 30 fps
            # (T-64). So pump n * rate / fps cooks; never change project.cookRate live (TD crashed doing that, T-64).
            cooks = int(math.ceil(n * (st['rate'] or f) / f))
            st['cooks'] = cooks
            ex.text = pump_script(m.path, cooks, st['rt'])
            _setp(ex, 'frameend', True)
            _setp(ex, 'active', True)
            m.store('jz_n', 0)
            m.store('jz_done', False)
            project.realTime = False  # noqa: F405 -- offline: no dropped frames (T-11)
            _setp(m, 'record', True)
            if on_start is not None:
                on_start()
            st['t0'] = time.time()
        except Exception as e:
            abort(e)
        return Pending(2, poll)

    def poll():
        try:
            m = st['m']
            done = bool(m.fetch('jz_done', False))
            if not done and time.time() - st['t0'] < st['timeout']:
                return Pending(5, poll)
            if not done:
                st['notes'].append('timed out after {} s with {} of {} frames'.format(
                    int(st['timeout']), m.fetch('jz_n', 0), n))
            _setp(m, 'record', False)
            project.realTime = st['rt']  # noqa: F405
            st['secs'] = rnd(time.time() - st['t0'], 4)
        except Exception as e:
            abort(e)
        return Pending(15, finish)  # the movie is finalised after Record goes off (A s4)

    def finish():
        counted = _try(lambda: st['m'].fetch('jz_n', 0), None)
        cleanup_ops()
        return {'file': file, 'frames_asked': n, 'cooks': st.get('cooks'), 'cooks_counted': counted, 'fps': f, 'codec': codec,
                'codectype': st.get('codectype'), 'pixfmt': st.get('pixfmt'), 'alpha': spec[3],
                'seconds': st.get('secs'), 'realtime_restored': bool(_try(lambda: project.realTime, None) == st['rt']),  # noqa: F405
                'source': src.path, 'notes': st['notes']}
    return Pending(1, step_codec)


def cmd_render_for_ae(source, file, frames, fps=30, alpha='premultiplied'):
    """TD -> AE footage: ProRes 4444 with alpha (premultiplied, TD's own TOP convention) or 422 HQ (alpha none)."""
    if alpha == 'straight':
        raise ValueError('alpha straight is not built yet (no unpremultiply step; docs/FUTURE.md): render premultiplied '
                         'and set AE footage.interpret alphaMode premultiplied')
    if alpha not in ('premultiplied', 'none'):
        raise ValueError('alpha must be premultiplied or none, got {!r}'.format(alpha))
    return offline_render(source, file, frames, fps, 'prores4444' if alpha == 'premultiplied' else 'prores422hq')


def cmd_export_ae_data(chop, file, format='json', frames=None):
    """Read-only: a CHOP's samples into an AE data-footage file (json/csv). frames: sample its current values on
    each of the next N TD frames (live curves, e.g. audio analysis); without it: the CHOP's own samples."""
    c = _op(chop, 'chop')
    if _family(c) != 'CHOP':
        raise ValueError('{} is not a CHOP'.format(c.path))
    if format not in AE_DATA_FORMATS:
        raise ValueError('format must be json or csv, got {!r}'.format(format))
    _abs_file(file, ('.' + format,))
    chans = list(c.chans())[:INSPECT_MAX_CHANS * 8]
    names = [ch.name for ch in chans]
    fps = _try(lambda: float(project.cookRate), 30.0)  # noqa: F405

    def write(rows, frame_col, rate):
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, 'w') as fh:
            fh.write(ae_data_text(names, rows, format, rate, c.path, frame_col))
        return {'file': file, 'format': format, 'channels': len(names), 'names': names[:20], 'samples': len(rows),
                'fps': rnd(rate), 'bytes': os.path.getsize(file)}

    if not frames:
        ns = int(c.numSamples)
        if ns * max(1, len(names)) > AE_DATA_MAX_CELLS:
            raise ValueError('{} samples x {} channels is over the cap {}'.format(ns, len(names), AE_DATA_MAX_CELLS))
        cols = [list(ch.vals) for ch in chans]
        rows = [[col[i] for col in cols] for i in range(ns)]
        return write(rows, None, _try(lambda: float(c.rate), fps))
    n = int(frames)
    if not (1 <= n <= RENDER_MAX_FRAMES) or n * max(1, len(names)) > AE_DATA_MAX_CELLS:
        raise ValueError('frames must be 1..{} (and frames x channels <= {})'.format(RENDER_MAX_FRAMES, AE_DATA_MAX_CELLS))
    rows, fcol = [], []

    def sample():
        _try(lambda: c.cook(force=True))
        rows.append([ch.eval() for ch in c.chans()][:len(names)])
        fcol.append(int(_try(lambda: absTime.frame, len(fcol))))  # noqa: F405
        if len(rows) < n:
            return Pending(1, sample)
        r = write(rows, fcol, fps)
        gaps = sum(1 for a, b in zip(fcol, fcol[1:]) if b - a != 1)
        if gaps:
            r['note'] = '{} frame gaps (realTime dropped frames): the frame column holds absTime.frame'.format(gaps)
        return r
    return Pending(1, sample)


AE_TABLES = ('meta', 'keys', 'text', 'markers', 'baked')


def cmd_import_ae_anim(parent, name, meta, keys, text, markers, baked, warnings=None, arrange=True):
    """Build one COMP from tables the MCP parsed out of an AE export: meta/keys/text/markers/baked Table DATs, baked
    -> DAT to CHOP (channel per column, one sample per comp frame) -> Null CHOP `out`, and a report DAT. Animation
    COMP (editable curves) is not built: its key-table layout is unprobed (docs/FUTURE.md)."""
    par_ = _op(parent, 'parent')
    if not _try(lambda: par_.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(par_.path))
    if not valid_op_name(name):
        raise ValueError('bad operator name {!r}'.format(name))
    if par_.op(name) is not None:
        raise ValueError('{}/{} already exists (pass another name)'.format(par_.path.rstrip('/'), name))
    data = {'meta': meta, 'keys': keys, 'text': text, 'markers': markers, 'baked': baked}
    for k, v in data.items():
        if not isinstance(v, list) or not v or not all(isinstance(r, list) for r in v):
            raise ValueError('{} must be a non-empty list of rows'.format(k))
    comp = par_.create(baseCOMP, name)  # noqa: F405
    try:
        xy0 = _try(lambda: _auto_xy(par_, comp))
        if xy0:
            comp.nodeX, comp.nodeY = xy0
        made = {}
        for k in AE_TABLES:
            t = comp.create(tableDAT, k)  # noqa: F405
            t.text = tsv(data[k])
            made[k] = t
        rep = comp.create(textDAT, 'report')  # noqa: F405
        rep.text = '\n'.join(['AE import report (jazib-td td_import_ae_anim)'] + ['- ' + str(w) for w in (warnings or [])]
                             + ['- Animation COMP not built: key-table layout unprobed (docs/FUTURE.md)'])
        ch = comp.create(dattoCHOP, 'baked_chop')  # noqa: F405
        for k, v in (('dat', made['baked'].path), ('output', 'chanpercol'), ('firstrow', 'names'), ('firstcolumn', 'values')):
            _setp(ch, k, v)
        out = comp.create(nullCHOP, 'out')  # noqa: F405
        ch.outputConnectors[0].connect(out.inputConnectors[0])
        for o in list(made.values()) + [rep, ch, out]:
            _try(lambda: setattr(o, 'viewer', True))
    except Exception:
        _try(comp.destroy)
        raise
    lay = [_arrange(comp, arrange), _arrange(par_, arrange)]
    return {'path': comp.path, 'out': out.path, 'channels': len(baked[0]), 'frames': len(baked) - 1,
            'keys': len(keys) - 1, 'text': len(text) - 1, 'markers': len(markers) - 1,
            'warnings': len(warnings or []), 'layout': [x for x in lay if x],
            'note': 'one sample per comp frame: play with a Lookup CHOP or op(out)[chan][absTime.frame % frames]'}


# ------------------------------------------------------------------ Blender -> TD (td_import_blender, 26 Oct 2026)
# The MCP (src/blender.js) turns the sidecar of tools/blender_export.py into op specs; this builds them as one
# self-contained COMP (nothing refers to /jazib_mcp). Only the op types below can be made.
BLENDER_OP_TYPES = ('usdCOMP', 'fbxCOMP', 'cameraCOMP', 'lightCOMP', 'ambientlightCOMP', 'moviefileinTOP', 'rampTOP',
                    'renderTOP', 'nullTOP', 'textDAT')
BLENDER_MAX_OPS = 200


def check_blender_specs(ops, wires):
    """Validate every op spec before anything is made; raises ValueError listing all problems."""
    if not isinstance(ops, list) or not ops or len(ops) > BLENDER_MAX_OPS:
        raise ValueError('ops must be a list of 1..{} specs'.format(BLENDER_MAX_OPS))
    bad, names = [], set()
    for s in ops:
        if not isinstance(s, dict):
            bad.append('{!r}: not an object'.format(s))
            continue
        n, t = s.get('name'), s.get('type')
        if not valid_op_name(n) or n in names or n in ('sidecar', 'report'):
            bad.append('{!r}: bad or duplicate op name'.format(n))
        names.add(n)
        if t not in BLENDER_OP_TYPES:
            bad.append('{!r}: type {!r} not allowed ({})'.format(n, t, ', '.join(BLENDER_OP_TYPES)))
        for k in ('pars', 'exprs'):
            if not isinstance(s.get(k) or {}, dict):
                bad.append('{!r}: {} must be an object'.format(n, k))
    for w in wires or []:
        if not (isinstance(w, list) and len(w) == 2 and all(x in names for x in w)):
            bad.append('wire {!r}: needs two op names from ops'.format(w))
    if bad:
        raise ValueError('; '.join(bad))


def cmd_import_blender(parent, name, ops, wires=None, controls=None, stages=None, sidecar='', report='',
                       arrange=True):
    """Build one COMP from Blender op specs: geometry (USD/FBX COMP), cameras, lights / projectors (+ maps),
    ambient, render -> out, sidecar + report Text DATs, controls on a 'Blender' page, stored stage plan (T-69)."""
    par_ = _op(parent, 'parent')
    if not _try(lambda: par_.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(par_.path))
    if not valid_op_name(name):
        raise ValueError('bad operator name {!r}'.format(name))
    if par_.op(name) is not None:
        raise ValueError('{}/{} already exists (pass another name)'.format(par_.path.rstrip('/'), name))
    check_blender_specs(ops, wires)
    if controls:
        check_custom_specs(controls)
    comp = par_.create(baseCOMP, name)  # noqa: F405
    made, notes = {}, []
    try:
        xy0 = _try(lambda: _auto_xy(par_, comp))
        if xy0:
            comp.nodeX, comp.nodeY = xy0
        if controls:  # first: the ops' expressions read these pars
            r = _try(lambda: cmd_custom_pars(comp.path, 'Blender', controls), None)
            if r is None:
                notes.append('controls page not made')
        for nm, txt in (('sidecar', sidecar), ('report', report)):
            t = comp.create(textDAT, nm)  # noqa: F405
            t.text = str(txt or '')
            made[nm] = t
        for s in ops:
            o = comp.create(globals()[s['type']], s['name'])
            made[s['name']] = o
            for k, v in (s.get('pars') or {}).items():
                p = getattr(o.par, k, None)
                if p is None:
                    notes.append('{}: no par {}'.format(s['name'], k))
                    continue
                p.val = v
            for k, e in (s.get('exprs') or {}).items():
                p = getattr(o.par, k, None)
                if p is None:
                    notes.append('{}: no par {}'.format(s['name'], k))
                    continue
                p.expr = e
                _try(lambda: setattr(p, 'mode', ParMode.EXPRESSION))  # noqa: F405
            if s.get('comment'):
                _try(lambda: setattr(o, 'comment', str(s['comment'])[:400]))
        for a, b in wires or []:
            made[a].outputConnectors[0].connect(made[b].inputConnectors[0])
        pulsed = []
        for s in ops:  # after every par is set: e.g. the USD COMP imports its file
            for k in s.get('pulse') or []:
                p = getattr(made[s['name']].par, k, None)
                if p is not None and _try(lambda: p.pulse(), False) is not False:
                    pulsed.append('{}.{}'.format(s['name'], k))
        for o in made.values():
            _try(lambda: setattr(o, 'viewer', True))
    except Exception:
        _try(lambda: safe_destroy(comp))
        raise
    lay = None
    if arrange and stages:
        lay = _try(lambda: layout_stages(comp, stages, arrange='mixed'), None)
        if lay is None:
            notes.append('stage plan not applied')
    lay2 = [_arrange(par_, arrange)]
    return {'path': comp.path, 'ops': sorted(made), 'pulsed': pulsed, 'notes': notes,
            'out': made['out'].path if 'out' in made else None, 'layout': [x for x in lay2 if x],
            'staged': bool(lay)}


# ------------------------------------------------------------------ MIDI mapping (own, clean-room; research AR section 6)
# td_midi_build makes a self-contained COMP: midi_core (td/midi_core.py, lane A: every value decision) + runtime
# (td/midi_runtime.py: TD I/O) Text DATs, plain tables, MIDI In DAT -> callbacks -> runtime, MIDI Out CHOP for LED
# feedback, Frame Start tick, Parameter Execute for its custom pars, a scrolling List COMP editor + window. Nothing in
# it refers to /jazib_mcp: it keeps working in a saved .toe without the MCP. The commands below call the same runtime
# functions the COMP uses itself; td_midi_simulate feeds raw bytes into runtime.on_receive like the MIDI In callback.

MIDI_DEFAULT = '/project1/jazib_midi'
MIDI_CORE_FILE = 'midi_core.py'
MIDI_RUNTIME_FILE = 'midi_runtime.py'
MIDI_DIR = None  # tests point this at a folder; default = the folder of handlers_file()
MIDI_PARS = ('Learn', 'Activebank', 'Sendfeedback', 'Openeditor', 'Refreshdevices')
MIDI_KINDS = ('cc', 'cc14', 'note', 'noteoff', 'pitchbend', 'aftertouch', 'program')
MIDI_MAX_SIM = 512

MIDI_CB = '''# jazib_midi: MIDI In DAT callbacks -> runtime.on_receive (td/midi_runtime.py). ASCII.
def onReceiveMIDI(dat, rowIndex, message, channel, index, value, input, byteData):
    # signature = TD 2025.31550's own MIDI In DAT template (last arg byteData: bytes)
    c = dat.parent()
    r = c.op('runtime')
    if r is not None:
        r.module.on_receive(c, message, channel, index, value, byteData)
    return
'''
MIDI_TICK = '''# jazib_midi: every frame -> runtime.on_frame (smoothing, learn window, 10 Hz poll: takeover + LED feedback).
def onFrameStart(frame):
    c = me.parent()
    r = c.op('runtime')
    if r is not None:
        r.module.on_frame(c, frame)
    return
'''
MIDI_PAREXEC = '''# jazib_midi: the COMP's own MIDI page pars -> runtime.on_par.
def onPulse(par):
    c = me.parent()
    c.op('runtime').module.on_par(c, par.name)
    return

def onValueChange(par, *args):
    if par.name == 'Activebank':
        c = me.parent()
        c.op('runtime').module.on_par(c, par.name)
    return
'''
MIDI_LIST_CB = '''# jazib_midi editor (List COMP): cells come from runtime.editor_cell; edits and clicks go back to the runtime.
def _m(comp):
    c = comp.parent(2)
    return c, c.op('runtime').module

def onInitTable(comp, attribs):
    c, rt = _m(comp)
    if hasattr(rt, 'editor_init_table'):  # look + cells live in the runtime (copied at build)
        rt.editor_init_table(c, attribs)
        return
    attribs.rowHeight = 22
    attribs.bgColor = (0.12, 0.12, 0.13, 1)
    attribs.textColor = (0.9, 0.9, 0.9, 1)
    return

def onInitCol(comp, col, attribs):
    c, rt = _m(comp)
    if col < len(rt.EDITOR_WIDTHS):
        attribs.colWidth = rt.EDITOR_WIDTHS[col]
    return

def onInitRow(comp, row, attribs):
    c, rt = _m(comp)
    if hasattr(rt, 'editor_init_row'):
        rt.editor_init_row(c, row, attribs)
        return
    if row == 0:
        attribs.bgColor = (0.25, 0.22, 0.12, 1)
    return

def onInitCell(comp, row, col, attribs):
    c, rt = _m(comp)
    if hasattr(rt, 'editor_init_cell'):
        rt.editor_init_cell(c, row, col, attribs)
        return
    attribs.text = rt.editor_cell(c, row, col)
    if row > 0 and rt.EDITOR_COLS[col] in rt.EDITOR_EDITABLE:
        attribs.editable = 2
    return

def onRollover(comp, row, col, coords, prevRow, prevCol, prevCoords):
    return

def onSelect(comp, startRow, startCol, startCoords, endRow, endCol, endCoords, start, end):
    if end:
        c, rt = _m(comp)
        rt.editor_select(c, startRow, startCol)
    return

def onRadio(comp, row, col, prevRow, prevCol):
    return

def onFocus(comp, row, col, prevRow, prevCol):
    return

def onEdit(comp, row, col, val):
    c, rt = _m(comp)
    rt.editor_edit(c, row, col, val)
    return

def onHoverGetAccept(comp, row, col, coords, prevRow, prevCol, prevCoords, dragItems):
    return False

def onDropGetAccept(comp, row, col, coords, prevRow, prevCol, prevCoords, dragItems):
    return False
'''


def _midi_text(name):
    d = MIDI_DIR or os.path.dirname(handlers_file())
    p = os.path.join(d, name)
    with open(p, 'r', encoding='utf-8') as f:
        t = f.read()
    t.encode('ascii')
    compile(t, p, 'exec')
    return t, p


def _midi(path):
    """(comp, runtime module) of a jazib_midi COMP."""
    c = _op(path or MIDI_DEFAULT, 'path')
    r = c.op('runtime')
    m = _try(lambda: r.module) if r is not None else None
    if m is None or not hasattr(m, 'on_receive') or c.op('midi_core') is None:
        raise ValueError('{} is not a jazib_midi COMP (no runtime/midi_core DAT): run td_midi_build first'.format(c.path))
    return c, m


def midi_file(file, write=False):
    """A mappings file: relative = under the project folder (default folder midi_maps/), .json only; a save never
    leaves the project folder."""
    if not isinstance(file, str) or not file.strip():
        raise ValueError('file is required (e.g. "midi_maps/show.json", relative to the project folder)')
    if not file.lower().endswith('.json'):
        raise ValueError('file must end with .json: {!r}'.format(file))
    base = os.path.realpath(str(_try(lambda: project.folder, '') or '.'))  # noqa: F405
    p = file if os.path.isabs(file) else os.path.join(base, file if ('/' in file) else os.path.join('midi_maps', file))
    p = os.path.realpath(p)
    if write and not (p == base or p.startswith(base + os.sep)):
        raise ValueError('midi_save writes only under the project folder {}: {!r}'.format(base, file))
    return p


def _midi_set(o, name, value, notes):
    """One par; a missing par or a menu miss becomes a note (never silent, T-62), never an exception."""
    if o is None:
        return
    if isinstance(value, dict) and 'expr' in value and 'mode' not in value:
        value = dict(value, mode='EXPRESSION')
    try:
        plans, warns = _plan_pars(o, {name: value})
        _apply_plans(plans)
        notes.extend('{}.{}'.format(o.name, w) for w in warns)
    except Exception as e:
        notes.append('{}.{} not set: {}'.format(o.name, name, str(e)[:120]))


def _midi_build_ops(c, core_text, rt_text, notes):
    made = []

    def child(parent_, cls_name, nm):
        o = parent_.op(nm)
        if o is None:
            cls = getattr(td, cls_name, None)
            if not isinstance(cls, builtins.type):
                notes.append('{} not available in this build: {} not built'.format(cls_name, nm))
                return None
            try:
                o = parent_.create(cls, nm)
            except Exception as e:
                notes.append('{} could not be created: {}'.format(nm, str(e)[:160]))
                return None
            made.append(nm if parent_ is c else parent_.name + '/' + nm)
        if _family(o) in VIEWER_FAMILIES:
            _try(lambda: setattr(o, 'viewer', True))
        return o

    child(c, 'textDAT', 'midi_core').text = core_text
    child(c, 'textDAT', 'runtime').text = rt_text
    for t in ('bindings', 'config', 'events'):
        child(c, 'tableDAT', t)
    mi = child(c, 'midiinDAT', 'midi_in')
    cb = child(c, 'textDAT', 'midi_cb')
    cb.text = MIDI_CB
    if mi is not None:
        _try(lambda: setattr(cb, 'dock', mi))
        _midi_set(mi, 'active', {'expr': 'parent().par.Enable'}, notes)
        _midi_set(mi, 'id', {'expr': 'int(parent().par.Device.eval() or 1)'}, notes)
        _midi_set(mi, 'callbacks', 'midi_cb', notes)
        _midi_set(mi, 'bytes', True, notes)
        auto = c.op('midi_in_callbacks')  # live 31550: a new MIDI In DAT makes its own callbacks DAT; ours is midi_cb
        if auto is not None and auto is not cb:
            _try(lambda: safe_destroy(auto))
    mo = child(c, 'midioutCHOP', 'midi_out')
    if mo is not None:
        _midi_set(mo, 'active', {'expr': 'bool(parent().par.Enable) and bool(parent().par.Feedback)'}, notes)
        _midi_set(mo, 'destination', {'menu': 'device'}, notes)
        _midi_set(mo, 'id', {'expr': 'int(parent().par.Device.eval() or 1)'}, notes)
        for k, v in (('onebased', False), ('controlnorm', {'menu': 'off'}), ('notenorm', {'menu': 'off'}),
                     ('cookalways', True)):
            _midi_set(mo, k, v, notes)
    tick = child(c, 'executeDAT', 'tick')
    tick.text = MIDI_TICK
    _midi_set(tick, 'framestart', True, notes)
    pe = child(c, 'parameterexecuteDAT', 'par_exec')
    if pe is not None:
        pe.text = MIDI_PAREXEC
        for k, v in (('op', '..'), ('pars', ' '.join(MIDI_PARS)), ('onpulse', True), ('valuechange', True)):
            _midi_set(pe, k, v, notes)
    ed = child(c, 'containerCOMP', 'editor')
    if ed is not None:
        for k, v in (('w', 1000), ('h', 520)):
            _midi_set(ed, k, v, notes)
        hd = child(ed, 'textCOMP', 'header')
        lst = child(ed, 'listCOMP', 'list')
        lcb = child(ed, 'textDAT', 'list_cb')
        lcb.text = MIDI_LIST_CB
        for o, xywh in ((hd, (0, 490, 1000, 30)), (lst, (0, 0, 1000, 490))):
            if o is not None:
                for k, v in zip(('x', 'y', 'w', 'h'), xywh):
                    _midi_set(o, k, v, notes)
        if hd is not None:
            for k, v in (('alignx', {'menu': 'left'}), ('fontsize', 12)):
                _midi_set(hd, k, v, notes)
        if lst is not None:
            for k, v in (('callbacks', 'list_cb'), ('lockfirstrow', True), ('vscrollbar', True)):
                _midi_set(lst, k, v, notes)
        _arrange(ed)
    win = child(c, 'windowCOMP', 'editor_window')
    if win is not None:
        for k, v in (('winop', 'editor'), ('title', 'jazib MIDI mappings'), ('size', {'menu': 'custom'}),
                     ('winw', 1000), ('winh', 520)):
            _midi_set(win, k, v, notes)
    return made


def _midi_stages(c):
    st = [('MIDI in', 'input', ['midi_in'], 'MIDI In DAT (device = Device par) -> midi_cb -> runtime.on_receive'),
          ('Engine', 'process', ['midi_core', 'runtime', 'tick', 'par_exec'],
           'midi_core = value logic (td/midi_core.py); runtime = TD I/O (td/midi_runtime.py); tick = smoothing, '
           'learn, 10 Hz poll'),
          ('Data', 'note', ['bindings', 'config', 'events'], 'bindings = one row per mapping; config; last messages'),
          ('LED feedback', 'output', ['midi_out'], 'MIDI Out CHOP: CC / notes back to the controller'),
          ('Controls', 'control', ['editor', 'editor_window'], 'Openeditor pulse opens the mapping list')]
    return [{'title': t, 'role': r, 'ops': [n for n in ops if c.op(n) is not None], 'body': b}
            for t, r, ops, b in st if any(c.op(n) is not None for n in ops)]


def cmd_midi_build(path=MIDI_DEFAULT, device=None):
    """Build (or refresh in place: DAT code re-read from td/, tables kept) the self-contained MIDI mapping COMP."""
    core_text, core_src = _midi_text(MIDI_CORE_FILE)
    rt_text, rt_src = _midi_text(MIDI_RUNTIME_FILE)
    if not isinstance(path, str) or not path.startswith('/') or path.count('/') < 2:
        raise ValueError('path must be an absolute COMP path like /project1/jazib_midi, got {!r}'.format(path))
    parent_path, name = path.rsplit('/', 1)
    par_ = _op(parent_path or '/', 'parent')
    if not valid_op_name(name):
        raise ValueError('bad operator name {!r}'.format(name))
    c = par_.op(name)
    if c is not None and _try(lambda: c.OPType) != 'baseCOMP':
        raise ValueError('{} exists and is a {}, not a Base COMP'.format(c.path, c.OPType))
    created = c is None
    if created:
        c = par_.create(baseCOMP, name)  # noqa: F405
        c.nodeX, c.nodeY = _auto_xy(par_, c)
    c.comment = 'jazib MIDI mapping (self-contained; td/midi_core.py + td/midi_runtime.py, refreshed by td_midi_build)'
    notes = []
    made = _midi_build_ops(c, core_text, rt_text, notes)
    rt = c.op('runtime').module
    rt.reset_state(c)
    k = rt.core(c)
    b = c.op('bindings')
    if b.numRows == 0:
        for r in k.to_rows([]):
            b.appendRow(r)
    ev = c.op('events')
    if ev.numRows == 0:
        ev.appendRow(rt.EVENTS_HEADER)
    names, labels = rt.device_menu(rt.devices(c))
    cmd_custom_pars(c.path, 'MIDI', [
        {'name': 'Enable', 'label': 'Enable', 'style': 'Toggle', 'default': True},
        {'name': 'Device', 'label': 'Device (MIDI Device Mapper id)', 'style': 'Menu', 'menuNames': names,
         'menuLabels': labels},
        {'name': 'Activebank', 'label': 'Active bank (0 = always)', 'style': 'Int', 'default': 1, 'min': 1,
         'max': 16, 'normMin': 1, 'normMax': 8, 'clampMin': True},
        {'name': 'Learn', 'label': 'Learn (hover a par, move a control)', 'style': 'Pulse'},
        {'name': 'Feedback', 'label': 'LED feedback', 'style': 'Toggle', 'default': True},
        {'name': 'Sendfeedback', 'label': 'Send all feedback', 'style': 'Pulse'},
        {'name': 'Openeditor', 'label': 'Open editor', 'style': 'Pulse'},
        {'name': 'Refreshdevices', 'label': 'Refresh devices', 'style': 'Pulse'}])
    rt.refresh_devices(c)
    if device is not None:
        p = c.par.Device
        hit, _w = match_menu(list(p.menuNames), list(p.menuLabels), str(device))
        if hit is None:
            notes.append('device {!r} not in the MIDI Device Mapper ({}); Device left at {}'.format(
                device, ', '.join(labels), p.eval()))
        else:
            p.val = hit
    rt.init_config(c, str(_try(lambda: c.par.Device.eval(), '') or ''))
    lay = _try(lambda: layout_stages(c, _midi_stages(c), True), None)
    _try(lambda: rt.refresh_editor(c))
    _point_pane(c)
    r = {'path': c.path, 'created': created, 'new_ops': made, 'core_file': core_src, 'runtime_file': rt_src,
         'devices': [{'name': n, 'label': lb} for n, lb in zip(names, labels)], 'device': c.par.Device.eval(),
         'mappings': len(rt.mappings(c)), 'layout': {'ok': lay.get('ok')} if isinstance(lay, dict) else None,
         'parent_layout': _arrange(par_) if created else None,
         'hint': 'td_midi_learn {target, par} then move a control (or td_midi_simulate); Openeditor pulse shows the list'}
    if notes:
        r['notes'] = notes
    return r


def cmd_midi_status(path=MIDI_DEFAULT):
    c, rt = _midi(path)
    r = rt.status(c)
    mi = c.op('midi_in')
    r['path'] = c.path
    r['devices'] = rt.devices(c)
    r['device_table'] = rt.DEVICE_TABLE
    r['midi_in'] = None if mi is None else {'active': _try(lambda: bool(mi.par.active.eval())),
                                            'id': _try(lambda: mi.par.id.eval()), 'rows': _try(lambda: mi.numRows)}
    if not r['devices']:
        r['hint'] = 'no device in TD\'s MIDI Device Mapper (Dialogs > MIDI Device Mapper): add the controller there once'
    return r


def cmd_midi_learn(path=MIDI_DEFAULT, action='start', target=None, par=None, mode=None, id=None, wait_s=0,
                   min=None, max=None, curve=None, takeover=None, smooth=None, feedback=None, bank=None,
                   label=None, invert=None, clamp=None, step=None):
    """start: listen for the next control (par mode: target+par; hover: ui.rolloverPar while it moves; slot: id).
    wait_s > 0 replies when learned or after that long. stop / finish (classify now) / status."""
    c, rt = _midi(path)
    if action not in ('start', 'stop', 'finish', 'status'):
        raise ValueError('action must be start, stop, finish or status')
    if action == 'stop':
        return rt.learn_stop(c)
    if action == 'finish':
        return rt.learn_finish(c)
    if action == 'status':
        return rt.learn_status(c)
    mode = mode or ('slot' if id else ('par' if target else 'hover'))
    if mode == 'hover' and _try(lambda: hasattr(ui, 'rolloverPar'), False) is False:  # noqa: F405
        return {'available': False, 'note': 'ui.rolloverPar is not in this build: pass target + par'}
    if mode == 'par' and target and not str(target).startswith('/'):
        raise ValueError('target must be an absolute TD path')
    opts = dict((k, v) for k, v in (('min', min), ('max', max), ('curve', curve), ('takeover', takeover),
                                    ('smooth', smooth), ('feedback', feedback), ('bank', bank), ('label', label),
                                    ('invert', invert), ('clamp', clamp), ('step', step)) if v is not None)
    r = rt.learn_start(c, mode, target or '', par or '', id or '', opts)
    r['hint'] = ('move one control on the controller now' + (' while the mouse is over the parameter'
                 if mode == 'hover' else '') + ' (td_midi_simulate works too); then td_midi_learn {action:"status"}')
    wait = float(wait_s or 0)
    if wait <= 0:
        return r
    rate = _try(lambda: float(project.cookRate), 60.0) or 60.0  # noqa: F405
    deadline = time.time() + builtins.min(wait, 120.0)  # min/max are mapping args here

    def poll():
        s = rt.learn_status(c)
        if s['state'] != 'listening':
            return s
        if time.time() >= deadline:
            s = rt.learn_stop(c)
            s['note'] = 'nothing learned in {:g} s'.format(wait)
            return s
        return Pending(int(rate / 4) or 1, poll)
    return Pending(int(rate / 4) or 1, poll)


MAP_FIELDS = ('id', 'bank', 'label', 'kind', 'channel', 'number', 'target', 'par', 'min', 'max', 'default', 'curve',
              'invert', 'mode', 'takeover', 'smooth', 'clamp', 'feedback', 'step')


def cmd_midi_map(path=MIDI_DEFAULT, mapping=None):
    """Add a mapping (no id or a new id) or update one (known id: given fields merged). Fields: midi_core FIELDS."""
    c, rt = _midi(path)
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError('mapping must be an object of mapping fields: {}'.format(', '.join(MAP_FIELDS)))
    t = mapping.get('target')
    if t and not str(t).startswith('/'):
        raise ValueError('target must be an absolute TD path, got {!r}'.format(t))
    m = rt.put_mapping(c, mapping)
    return {'mapping': m, 'msg': rt.msg_text(m), 'mappings': len(rt.mappings(c))}


def cmd_midi_unmap(path=MIDI_DEFAULT, ids=None, target=None, par=None):
    c, rt = _midi(path)
    want = list(ids or [])
    if target:
        want += [m['id'] for m in rt.mappings(c) if m['target'] == target and (par is None or m['par'] == par)]
    if not want:
        raise ValueError('give ids, or target (+ par)')
    gone = rt.remove(c, want)
    return {'removed': gone, 'missing': [i for i in (ids or []) if i not in gone], 'mappings': len(rt.mappings(c))}


def cmd_midi_list(path=MIDI_DEFAULT, bank=None):
    c, rt = _midi(path)
    ms = rt.mappings(c)
    if bank is not None:
        ms = [m for m in ms if m['bank'] == int(bank)]
    return {'active_bank': rt.active_bank(c), 'count': len(ms),
            'mappings': [dict(m, msg=rt.msg_text(m), bound=rt.resolve(c, m)[1] is not None) for m in ms]}


def cmd_midi_bank(path=MIDI_DEFAULT, bank=None):
    c, rt = _midi(path)
    if bank is not None:
        rt.set_bank(c, bank)
    k = rt.core(c)
    ms = rt.mappings(c)
    return {'active_bank': rt.active_bank(c), 'banks': k.banks_in(ms),
            'live': [m['id'] for m in k.select_bank(ms, rt.active_bank(c))]}


def cmd_midi_save(path=MIDI_DEFAULT, file=None):
    c, rt = _midi(path)
    p = midi_file(file, write=True)
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    text = rt.to_json_text(c)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(text)
    return {'file': p, 'mappings': len(rt.mappings(c)), 'bytes': len(text)}


def cmd_midi_load(path=MIDI_DEFAULT, file=None, merge=False):
    c, rt = _midi(path)
    p = midi_file(file)
    with open(p, 'r', encoding='utf-8') as f:
        text = f.read()
    r = rt.load_json_text(c, text, merge=bool(merge))
    r['file'] = p
    return r


def cmd_midi_monitor(path=MIDI_DEFAULT, n=20):
    c, rt = _midi(path)
    return {'events': rt.monitor(c, clamp_int(n, 20, 1, rt.EVENTS_CAP)), 'sent_last': rt.state(c)['sent'][-10:],
            'last_error': rt.cfg(c, 'last_error')}


def cmd_midi_simulate(path=MIDI_DEFAULT, kind='cc', channel=1, number=0, value=0, value2=None, events=None,
                      frames=0):
    """Inject messages as raw MIDI bytes into runtime.on_receive (the MIDI In callback's own path). events =
    [{kind, channel, number, value, value2?}] for a burst. frames > 0: reply after that many frames (smoothing /
    learn window ran)."""
    c, rt = _midi(path)
    evs = events if events is not None else [{'kind': kind, 'channel': channel, 'number': number, 'value': value,
                                              'value2': value2}]
    if not isinstance(evs, list) or not evs or len(evs) > MIDI_MAX_SIM:
        raise ValueError('events must be a list of 1..{} messages'.format(MIDI_MAX_SIM))
    msgs = []
    for e in evs:
        if not isinstance(e, dict) or str(e.get('kind', 'cc')).lower() not in MIDI_KINDS:
            raise ValueError('bad event {!r}: kind one of {}'.format(e, ', '.join(MIDI_KINDS)))
        msgs += rt.sim_bytes(e.get('kind', 'cc'), e.get('channel', 1), e.get('number', 0), e.get('value', 0),
                             e.get('value2'))
    writes, errors, learn = [], [], None
    for b in msgs:
        r = rt.on_receive(c, None, None, None, None, b, source='sim')
        writes += r['writes']
        if r.get('error'):
            errors.append(r['error'])
        learn = r.get('learn') or learn
    out = {'sent': len(msgs), 'bytes': [' '.join('%02x' % x for x in b) for b in msgs[:20]], 'writes': writes}
    if errors:
        out['errors'] = errors
    if learn:
        out['learn'] = learn

    def finish():
        vals = {}
        for m in rt.mappings(c):
            o, p = rt.resolve(c, m)
            if p is not None and m['id'] in set(w['id'] for w in writes):
                vals[m['id']] = _try(lambda: p.eval())
        out['values'] = vals
        out['learn_state'] = rt.cfg(c, 'learn_state')
        return out
    if frames and int(frames) > 0:
        return Pending(int(frames), finish)
    return finish()


def cmd_midi_preset(path=MIDI_DEFAULT, name=None, bank=None):
    c, rt = _midi(path)
    k = rt.core(c)
    if not name:
        return {'presets': dict((n, {'description': p.get('description', ''), 'controls': len(p.get('controls', [])),
                                     'verified': p.get('verified', False)}) for n, p in k.CONTROLLER_PRESETS.items())}
    new = rt.apply_preset(c, name, bank)
    return {'added': [m['id'] for m in new], 'bank': new[0]['bank'] if new else None,
            'note': 'unbound slots: bind each with td_midi_map {mapping:{id, target, par}} or the editor',
            'verified': k.CONTROLLER_PRESETS[name].get('verified', False)}


# ------------------------------------------------------------------ health / trace / save hook (td-atlas port)
# Adapted from td-atlas by grigabyte (https://github.com/grigabyte/td-atlas, commit 7cf8f57fa486ea5f8ef7259c07b0f68c72f714c5,
# src/td_atlas/component/handler.py: m_health_sample, m_health_probe, m_script_errors_recheck, _trace_walk,
# _negative_float_risk, _clock_calls, sidecar_name, write_text_atomic). Their measurements were on 2025.32460; every TD
# read here goes through _try so a missing API on 2025.31550 becomes a note, never an error. The verdict for health is
# drawn MCP-side (src/health.js), from two samples an interval apart.

HEALTH_MAX_NODES = 3000      # ops sampled per call (the reply stays on the local bridge; Node draws the verdict)
HEALTH_SCAN_BUDGET_S = 0.05  # par pass (clock reads + missing files) + NaN CHOP pass, each
HEALTH_PROBE_BUDGET_S = 0.5  # cooking budget of one probe pass (td-atlas: half a second)
HEALTH_MAX_LIST = 50         # clock reads / missing files / nan chops listed per reply
HEALTH_NAN_MAX_VALS = 200000  # CHOPs bigger than this are not scanned for NaN
GAIN_TYPES = ('levelTOP', 'mathTOP', 'hsvadjustTOP', 'mathCHOP', 'mathPOP')
FEEDBACK_TARGETS = {'feedbackTOP': 'top', 'feedbackPOP': 'targetpop', 'feedbackCHOP': None}
OUTPUT_TYPES = {'audiodeviceoutCHOP': 'audio output', 'moviefileoutTOP': 'movie recording', 'midioutCHOP': 'MIDI output',
                'oscoutCHOP': 'OSC output', 'dmxoutCHOP': 'DMX output', 'serialDAT': 'serial output',
                'touchoutTOP': 'Touch Out', 'ndioutTOP': 'NDI output', 'videodeviceoutTOP': 'video output',
                'syphonspoutoutTOP': 'Syphon/Spout output'}
PROBE_NEVER_COOK = frozenset(list(OUTPUT_TYPES) + ['oscoutDAT', 'tcpipDAT', 'udpoutDAT', 'websocketDAT'])
SCRIPT_DATS = ('executeDAT', 'chopexecuteDAT', 'datexecuteDAT', 'opexecuteDAT', 'panelexecuteDAT',
               'parameterexecuteDAT', 'pargroupexecuteDAT')
SCRIPT_OPS = ('scriptCHOP', 'scriptTOP', 'scriptSOP', 'scriptDAT')
CLOCK_READ_RE = re.compile(r"\babsTime\.\w+|\btime\.time\s*\(\s*\)"
                           r"|\b(?:np\.|numpy\.)?random\.(?!seed\b|Random\b|default_rng\b)\w+\s*\(")
SEEDED_RE = re.compile(r"\brandom\.seed\s*\(")
NEGATIVE_DEPTH = 4
NEGATIVE_VISIT = 32
TRACE_MAX_NODES = 40
TRACE_DEFAULT_DEPTH = 8
TRACE_MAX_DEPTH = 20
TRACE_SIDE = 256             # pixels read along the longer side (stride over bigger images)
TRACE_BUDGET_S = 0.5
TRACE_EPS = 0.5 / 255
TRACE_PARS = ('opacity', 'blacklevel', 'brightness1', 'operand', 'contrast', 'inlow', 'outlow', 'clamp')
SAVE_HOOK_NAME = 'save_hook'
SAVE_HOOK_KEY = 'jazib_save_root'
SAVE_HOOK_MAX_OPS = 2000     # td-atlas: ~0.25-0.30 ms per op on 2025.32460, 2000 ops ~ half a second per save
SAVE_HOOK_EXT = '.jtdnet'


def clock_calls(text):
    """The clock / unseeded-random reads in a piece of code, each named once (pure)."""
    seeded = bool(SEEDED_RE.search(text or ''))
    calls = []
    for m in CLOCK_READ_RE.finditer(text or ''):
        c = re.sub(r'\s+', '', m.group(0))
        if c.endswith('('):
            if seeded:
                continue
            c += ')'
        if c not in calls:
            calls.append(c)
    return calls


def negative_settings(fmt, contrast, inlow, outlow, clamp, clamplow2):
    """{setting: value} that let a Level TOP output negative floats, or None (pure; td-atlas measurement on
    2025.32460: contrast > 1 and inlow > 0 go below zero, blacklevel stops at 0; outlow < 0 included unmeasured)."""
    fmt = str(fmt or '')
    if 'float' not in fmt or '11float' in fmt:
        return None
    s = {}
    for name, v, bad in (('contrast', contrast, lambda x: x > 1), ('inlow', inlow, lambda x: x > 0),
                         ('outlow', outlow, lambda x: x < 0)):
        if isinstance(v, numbers.Number) and not isinstance(v, bool) and bad(v):
            s[name] = round(float(v), 4)
    if not s:
        return None
    if clamp and isinstance(clamplow2, numbers.Number) and clamplow2 >= 0:
        return None
    return s


def trace_state(stats):
    """'unsampled' | 'nan' | 'negative' | 'black' | 'transparent' | 'ok' for one image's stats (pure)."""
    if not stats:
        return 'unsampled'
    if stats.get('nan') or stats.get('inf'):
        return 'nan'
    lo = [v for v in (stats.get('min') or [])[:3] if isinstance(v, numbers.Number)]
    hi = [v for v in (stats.get('max') or [])[:3] if isinstance(v, numbers.Number)]
    if lo and min(lo) < -TRACE_EPS:
        return 'negative'
    if hi and max(hi) <= TRACE_EPS:
        return 'black'
    a = (stats.get('max') or [])[3:4]
    if a and isinstance(a[0], numbers.Number) and a[0] <= TRACE_EPS:
        return 'transparent'
    return 'ok'


def trace_facts(e):
    """What a node's own flags / pars say about a lost signal (pure)."""
    f = []
    if e.get('bypass'):
        f.append('bypass')
    if e.get('lock'):
        f.append('locked: holds a frozen image')
    need = e.get('minInputs')
    if isinstance(need, int) and len(e.get('inputs') or []) < need:
        f.append('input empty: {} of {} wired'.format(len(e.get('inputs') or []), need))
    p = e.get('pars') or {}
    op_ = p.get('opacity')
    if isinstance(op_, numbers.Number) and not isinstance(op_, bool) and op_ <= 0:
        f.append('opacity 0')
    bl = p.get('blacklevel')
    if isinstance(bl, numbers.Number) and not isinstance(bl, bool) and bl > 0:
        f.append('blacklevel {} cuts dark values to 0'.format(bl))
    if e.get('negativeFloat'):
        f.append('float format, no clamp at 0: ' + ', '.join('{} {}'.format(k, v)
                                                             for k, v in sorted(e['negativeFloat'].items())))
    if e.get('errors'):
        f.append('error: ' + clip_str(str(e['errors']).strip().splitlines()[0], 80))
    if e.get('compile'):
        f.append('GLSL compile failed: ' + clip_str(str(e['compile']), 100))
    elif e.get('warnings'):
        f.append('warning: ' + clip_str(str(e['warnings']).strip().splitlines()[0], 80))
    return f


def trace_failed(e):
    """True when the node itself is broken (error or GLSL compile failure): its picture is TD's error pattern, not
    the signal, whatever its stats say (QC 26 Oct: a failed GLSL TOP read 'ok' in td_trace)."""
    return bool(e.get('errors') or e.get('compile'))


def trace_marks(nodes):
    """{path: [marker, reasons]} where the signal was lost (pure; td-atlas bridge/trace.py verdicts)."""
    by = {n['path']: n for n in nodes}
    st = {p: trace_state(n.get('stats')) for p, n in by.items()}
    marks = {}
    for e in nodes:
        p = e['path']
        mine = st[p]
        ins = e.get('inputs') or []
        known = [i for i in ins if st.get(i, 'unsampled') != 'unsampled']
        unknown = [i for i in ins if i not in known]
        seen = [st[i] for i in known]
        q = '?' if unknown else ''
        hedge = ['input {} not read ({}): the loss may come from there'.format(
            i, clip_str((by.get(i) or {}).get('unsampled') or 'beyond the walk', 40)) for i in unknown]
        if trace_failed(e) and not any(trace_failed(by[i]) for i in ins if i in by):
            marks[p] = ['broken here', trace_facts(e)]
            continue
        if mine == 'nan' and 'nan' not in seen:
            s = e['stats']
            marks[p] = ['NaN/Inf start here' + q, ['{} NaN, {} Inf'.format(s.get('nan', 0), s.get('inf', 0))]
                        + trace_facts(e) + hedge]
            continue
        if mine == 'negative' and not ({'nan', 'negative'} & set(seen)):
            marks[p] = ['negative values start here' + q, trace_facts(e) + hedge]
            continue
        neg_in = [i for i in known if st[i] == 'negative']
        adds = e.get('type') == 'addTOP' or (e.get('type') == 'compositeTOP'
                                             and (e.get('pars') or {}).get('operand') == 'add')
        if adds and neg_in and mine != 'nan':
            marks[p] = ['dropped here', ['adds {} which holds negative values, so it subtracts'.format(
                ', '.join(neg_in))] + trace_facts(e)]
            continue
        if mine == 'transparent':
            if 'ok' in seen or not ins:
                marks[p] = ['alpha goes to 0 here', trace_facts(e)]
            elif not seen:
                marks[p] = ['alpha goes to 0 here?', trace_facts(e) + hedge]
            continue
        if mine != 'black':
            continue
        if 'ok' in seen or not ins:
            marks[p] = ['dropped here', trace_facts(e)]
        elif not seen:
            marks[p] = ['dropped here?', trace_facts(e) + hedge]
    return marks


def sidecar_name(project_name, root_path):
    """'JazibTD_home.3.toe', '/project1' -> 'JazibTD_home.project1.jtdnet' (pure). The save number TD adds is dropped,
    so one project keeps one text and git holds the history (td-atlas sidecar_name)."""
    stem = str(project_name or '')
    for suf in ('.toe', '.tox'):
        if stem.lower().endswith(suf):
            stem = stem[:-len(suf)]
            break
    head, dot, tail = stem.rpartition('.')
    if dot and tail.isdigit():
        stem = head
    root = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(root_path or '').strip('/')) or 'root'
    return '{}.{}{}'.format(stem or 'project', root, SAVE_HOOK_EXT)


def is_our_net_text(head):
    """True when a file's first line is a jtd-net header (the guard against overwriting someone else's file)."""
    try:
        d = json.loads((head or '').splitlines()[0])
    except Exception:
        return False
    return isinstance(d, dict) and d.get('format') == NET_FORMAT


def write_text_atomic(path, text):
    """Temp file in the same folder, then os.replace: a reader sees the old file or the new one, never half."""
    folder = os.path.dirname(path) or '.'
    tmp = os.path.join(folder, '.{}.{}.tmp'.format(os.path.basename(path), os.getpid()))
    try:
        with open(tmp, 'w', encoding='ascii', newline='\n') as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            _try(lambda: os.remove(tmp))
    return path


# ---- TD side

def _pv(o, name):
    """A par's evaluated value, or None when absent/unreadable."""
    return _try(lambda: o.par[name].eval() if o.par[name] is not None else None)


def _bounded_walk(root_, limit):
    """Ops under root_ breadth-first (skipping /jazib_mcp), at most `limit`; returns (ops, not_visited_floor)."""
    out, queue = [], list(_try(lambda: root_.children, []) or [])
    while queue and len(out) < limit:
        o = queue.pop(0)
        if _protected(o.path):
            continue
        out.append(o)
        # an annotate box's insides are TD's own widget (focusOrder...): never cooked, never the user's work; they
        # filled td_health's never-cooked list and its par budget (QC 26 Oct, 31550)
        if _try(lambda: o.isCOMP, False) and _try(lambda: o.OPType, '') != 'annotateCOMP':
            queue.extend(_try(lambda: o.children, []) or [])
    return out, len(queue)


def _pixel_format(o):
    return str(_try(lambda: o.pixelFormatName, None) or _try(lambda: o.pixelFormat, '') or '')


def _negative_risk(level):
    s = negative_settings(_pixel_format(level), _pv(level, 'contrast'), _pv(level, 'inlow'), _pv(level, 'outlow'),
                          _pv(level, 'clamp'), _pv(level, 'clamplow2'))
    if not s:
        return None
    adds, seen, front = [], set(), list(_try(lambda: level.outputs, []) or [])
    for _ in range(NEGATIVE_DEPTH):
        nxt = []
        for n in front:
            p = _try(lambda: n.path, None)
            if p is None or p in seen or len(seen) >= NEGATIVE_VISIT:
                continue
            seen.add(p)
            t = _try(lambda: n.OPType, '')
            if t == 'addTOP' or (t == 'compositeTOP' and _pv(n, 'operand') == 'add'):
                adds.append(p)
            nxt.extend(_try(lambda: n.outputs, []) or [])
        front = nxt
    return {'format': _pixel_format(level), 'settings': s, 'adds': adds}


def _file_missing(v):
    """True when a file par's value names a local file that does not exist (URLs and empties are skipped)."""
    s = str(v or '').strip()
    if not s or '://' in s or s.startswith('$'):
        return False
    full = _try(lambda: tdu.expandPath(s), None) or s  # noqa: F405 -- project.paths aware
    if not os.path.isabs(full):
        full = os.path.join(str(_try(lambda: project.folder, '') or ''), full)  # noqa: F405
    return not os.path.exists(full)


def _par_scan(ops_, budget):
    """Clock reads (scripts first, then expression pars) and missing files under one deadline."""
    reads, missing, deadline = [], [], time.perf_counter() + budget
    scripts = [o for o in ops_ if _try(lambda: o.OPType, '') in SCRIPT_DATS + SCRIPT_OPS]
    s_done = 0
    for o in scripts:
        if time.perf_counter() >= deadline:
            break
        s_done += 1
        if o.OPType in SCRIPT_DATS:
            for c in clock_calls(str(_try(lambda: o.text, '') or '')):
                reads.append([o.path, 'text', c])
        else:
            d = _pv(o, 'callbacks')
            for c in clock_calls(str(_try(lambda: d.text, '') or '')):
                reads.append([_try(lambda: d.path, o.path), 'callbacks of ' + o.path, c])
    p_done = 0
    for o in ops_:
        if time.perf_counter() >= deadline:
            break
        p_done += 1
        for p in _try(lambda: o.pars(), []) or []:
            m = str(_try(lambda: p.mode, ''))
            if 'EXPRESSION' in m.upper():
                for c in clock_calls(str(_try(lambda: p.expr, '') or '')):
                    reads.append([o.path, p.name, c])
            elif _try(lambda: p.style, '') in ('File', 'Folder'):
                v = _try(lambda: p.eval(), '')
                if v and v != _try(lambda: p.default, None) and _file_missing(v):
                    missing.append([o.path, p.name, clip_str(v, 160)])
    scan = {'pars': [p_done, len(ops_)], 'scripts': [s_done, len(scripts)]}
    return reads, missing, scan


def _nan_scan(ops_, budget):
    """CHOPs holding NaN / Inf samples (numpy; skipped with a note when numpy is unusable)."""
    found, deadline, done, note = [], time.perf_counter() + budget, 0, None
    try:
        import numpy
    except Exception as e:
        return found, [0, 0], _err_note('import numpy', e)
    chops = [o for o in ops_ if _family(o) == 'CHOP']
    for o in chops:
        if time.perf_counter() >= deadline:
            break
        done += 1
        n = (_try(lambda: o.numChans, 0) or 0) * (_try(lambda: o.numSamples, 0) or 0)
        if not n or n > HEALTH_NAN_MAX_VALS or _try(lambda: o.totalCooks, 1) == 0:
            continue
        try:
            a = o.numpyArray()
            bad = int(a.size - numpy.isfinite(a).sum())
        except Exception as e:
            note = note or _err_note('CHOP.numpyArray', e)
            continue
        if bad:
            found.append([o.path, bad, int(a.size)])
    return found, [done, len(chops)], note


def _time_state():
    t = _try(lambda: op('/').time, None)  # noqa: F405
    return {'frame': _try(lambda: absTime.frame, None),  # noqa: F405
            'playing': _try(lambda: bool(t.play), None), 'rate': _try(lambda: t.rate, None),
            'timelineFrame': _try(lambda: t.frame, None)}


def cmd_health_sample(path='/project1', counts_only=False, limit=HEALTH_MAX_NODES):
    """Read-only snapshot for td_health (src/health.js draws the verdict). counts_only: cook counts + frame only, and
    nothing is read that could cook (td-atlas: reading pixelFormatName cooks a Level TOP)."""
    r0 = _op(path)
    if _family(r0) != 'COMP':
        raise ValueError('health walks a COMP; {} is a {} ({})'.format(r0.path, _family(r0), _try(lambda: r0.OPType)))
    ops_, unvisited = _bounded_walk(r0, clamp_int(limit, HEALTH_MAX_NODES, 1, 20000))
    counts = {o.path: _try(lambda: o.totalCooks, None) for o in ops_}
    ts = _time_state()
    if counts_only:
        return dict(ts, counts=counts)
    notes = []
    if all(v is None for v in counts.values()) and counts:
        notes.append('OP.totalCooks unreadable on this build: cooking cannot be judged')
    nodes = []
    scripted = {}
    raw = _try(lambda: r0.scriptErrors(recurse=True), None)
    if raw is None:
        notes.append('scriptErrors(recurse=True) unreadable: script errors unknown, not clean')
    for o in ops_:
        t = _try(lambda: o.OPType, '')
        e = {'path': o.path, 'type': t, 'family': _family(o), 'cooks': counts.get(o.path),
             'cookTime': rnd(_try(lambda: o.cookTime, 0) or 0, 4)}
        for k in ('cookAbsFrame', 'cookFrame'):
            v = _try(lambda: getattr(o, k), None)
            if isinstance(v, numbers.Number):
                e[k] = v
        if _try(lambda: o.bypass, False):
            e['bypass'] = True
        er, wr = _try(lambda: o.errors(recurse=False), '') or '', _try(lambda: o.warnings(recurse=False), '') or ''
        if er:
            e['errors'] = clip_str(er, 200)
        if wr:
            e['warnings'] = clip_str(wr, 200)
        if t in FEEDBACK_TARGETS:
            tgt = _pv(o, FEEDBACK_TARGETS[t]) if FEEDBACK_TARGETS[t] else None
            e['feedback'] = {'target': str(_try(lambda: tgt.path, tgt) or ''), 'reset': bool(_pv(o, 'reset'))}
        if _try(lambda: o.par['resetpulse'] is not None, False):
            e['history'] = True
        if t == 'levelTOP':
            risk = _negative_risk(o)
            if risk:
                e['negativeFloat'] = risk
        if t in OUTPUT_TYPES:
            for flag in ('active', 'record', 'play'):
                v = _pv(o, flag)
                if v is not None:
                    e[flag] = bool(v)
        if t in GLSL_TYPES or t in ('glslMAT', 'glslPOP'):
            cr = _try(lambda: o.compileResult, None)
            if cr and 'ERROR' in str(cr):
                e['compile'] = clip_str(next((ln.strip() for ln in str(cr).splitlines() if 'ERROR' in ln), ''), 160)
        if raw:
            s = _try(lambda: o.scriptErrors(recurse=False), '')
            if s:
                scripted[o.path] = clip_str(s, 300)
        nodes.append(e)
    if raw:
        s = _try(lambda: r0.scriptErrors(recurse=False), '')
        if s:
            scripted[r0.path] = clip_str(s, 300)
    reads, missing, scan = _par_scan([r0] + ops_, HEALTH_SCAN_BUDGET_S)
    nan, nan_scan, nan_note = _nan_scan(ops_, HEALTH_SCAN_BUDGET_S)
    if nan_note:
        notes.append(nan_note)
    rep = dict(ts, path=r0.path, build=td_build_string(_try(lambda: app.version, ''), _try(lambda: app.build, '')),  # noqa: F405
               realTime=_try(lambda: bool(project.realTime), None),  # noqa: F405
               product=str(_try(lambda: app.product, '') or ''), nodes=nodes, scanned=len(ops_) + 1,  # noqa: F405
               scriptErrors=scripted, scriptErrorsRaw=clip_str(raw or '', 300),
               clockReads=reads[:HEALTH_MAX_LIST], clockReadsCount=len(reads), missingFiles=missing[:HEALTH_MAX_LIST],
               missingFilesCount=len(missing), nanChops=nan[:HEALTH_MAX_LIST], scan=dict(scan, nan=nan_scan), notes=notes)
    if unvisited:
        rep.update(truncated=True, notScanned=unvisited, limit=limit)
    return rep


def cmd_health_probe(paths=()):
    """Ask quiet ops to cook (cook() without force: only what has something new to compute cooks). Outputs, COMPs
    and never-cooked ops are not asked. td_health calls it twice 0.2 s apart and reads the second answer."""
    targets, never, skipped, missing = [], [], [], []
    for p in list(paths or [])[:HEALTH_MAX_NODES]:
        o = op(p) if isinstance(p, str) else None  # noqa: F405
        if o is None:
            missing.append(p)
        elif _family(o) == 'COMP' or _try(lambda: o.OPType, '') in PROBE_NEVER_COOK:
            skipped.append(p)
        elif _try(lambda: o.totalCooks, 0) == 0:
            never.append(p)
        else:
            targets.append(o)
    before = {o.path: _try(lambda: o.totalCooks, 0) for o in targets}
    deadline, unprobed = time.perf_counter() + HEALTH_PROBE_BUDGET_S, []
    for i, o in enumerate(targets):
        if time.perf_counter() > deadline:
            unprobed = [t.path for t in targets[i:]]
            break
        _try(lambda: o.cook())
    left = set(unprobed)
    cooked = [o.path for o in targets if o.path not in left and _try(lambda: o.totalCooks, 0) != before[o.path]]
    quiet = [o.path for o in targets if o.path not in left and o.path not in cooked]
    return {'cooked': cooked, 'quiet': quiet, 'never': never, 'skipped': skipped, 'missing': missing,
            'unprobed': unprobed}


def _callback_users(target):
    users = []
    for sib in _try(lambda: target.parent().children, []) or []:
        if _try(lambda: sib.par['callbacks'] is not None and sib.par['callbacks'].eval() == target, False):
            users.append(sib)
    return users


def bare_script_error(text, path):
    """A kept traceback as addScriptError wants it back: one 'Error: ' and one ' (path)' fewer (pure)."""
    t = str(text or '').strip()
    if t.startswith('Error: '):
        t = t[len('Error: '):]
    suf = ' ({})'.format(path)
    if t.endswith(suf):
        t = t[:-len(suf)]
    return t


def cmd_script_errors_recheck(step, paths=None, state=None):
    """td_health recheck (opt-in): clear kept tracebacks, read 0.2 s later. back = live; not back while the code ran =
    stale (left cleared); else unknown (the text is put back). step 'restore' puts every saved text back."""
    probe = op(comp_path())  # noqa: F405
    if probe is None or not hasattr(probe, 'clearScriptErrors') or not hasattr(probe, 'addScriptError'):
        return {'available': False, 'note': 'OP.clearScriptErrors/addScriptError missing on this build'}
    if step == 'clear':
        st = {}
        for p in list(paths or [])[:200]:
            o = op(p)  # noqa: F405
            text = _try(lambda: o.scriptErrors(), '') if o is not None else ''
            if not text:
                continue
            users = _callback_users(o) + ([o] if _family(o) != 'DAT' else [])
            st[p] = {'text': text, 'users': {u.path: _try(lambda: u.totalCooks, 0) for u in users}}
            _try(o.clearScriptErrors)
        return {'state': st}
    if step == 'read':
        v = {}
        for p, saved in (state or {}).items():
            o = op(p)  # noqa: F405
            if o is None:
                continue
            now = _try(lambda: o.scriptErrors(), '')
            if now:
                v[p] = {'verdict': 'live', 'text': clip_str(now, 300)}
                continue
            cooked = 0
            for u, b in (saved.get('users') or {}).items():
                uo = op(u)  # noqa: F405
                if uo is not None:
                    cooked += max(0, (_try(lambda: uo.totalCooks, 0) or 0) - b)
            if cooked and ('onCook' in saved.get('text', '') or _family(o) != 'DAT'):
                v[p] = {'verdict': 'stale', 'cooks': cooked, 'text': clip_str(saved.get('text'), 300)}
                continue
            _try(lambda: o.addScriptError(bare_script_error(saved.get('text'), p)))
            v[p] = {'verdict': 'unknown', 'text': clip_str(saved.get('text'), 300)}
        return {'verdicts': v}
    if step == 'restore':
        done = []
        for p, saved in (state or {}).items():
            o = op(p)  # noqa: F405
            if o is None or _try(lambda: o.scriptErrors(), ''):
                continue
            _try(lambda: o.addScriptError(bare_script_error(saved.get('text'), p)))
            done.append(p)
        return {'restored': done}
    raise ValueError("step must be 'clear', 'read' or 'restore'")


def _trace_stats(a):
    import numpy
    h, w = int(a.shape[0]), int(a.shape[1])
    stride = max(1, -(-max(h, w) // TRACE_SIDE))
    v = a[::stride, ::stride]
    k = 1 if v.ndim == 2 else int(v.shape[2])
    flat = v.reshape(-1, k)
    lo, mean, hi = [], [], []
    for i in range(k):
        col = flat[:, i]
        fin = col[numpy.isfinite(col)]
        lo.append(rnd(float(fin.min()), 4) if fin.size else None)
        mean.append(rnd(float(fin.mean()), 4) if fin.size else None)
        hi.append(rnd(float(fin.max()), 4) if fin.size else None)
    return {'min': lo, 'mean': mean, 'max': hi, 'nan': int(numpy.isnan(flat).sum()),
            'inf': int(numpy.isinf(flat).sum()), 'stride': stride}


def cmd_trace(path, depth=TRACE_DEFAULT_DEPTH):
    """Read-only 'why is this TOP black': walk up the wired inputs (breadth-first, <= 40 nodes), read each TOP's
    min/mean/max per RGBA (numpyArray, no forced cook), mark where the signal was lost (trace_marks)."""
    r0 = _op(path)
    if _family(r0) != 'TOP':
        raise ValueError('trace follows a TOP up its inputs; {} is a {}'.format(r0.path, _family(r0)))
    depth = clamp_int(depth, TRACE_DEFAULT_DEPTH, 0, TRACE_MAX_DEPTH)
    t0 = time.perf_counter()
    deadline = t0 + TRACE_BUDGET_S
    nodes, seen, queue, stopped, numpy_bad = [], {r0.path}, [(r0, 0)], False, None
    while queue and len(nodes) < TRACE_MAX_NODES:
        o, lvl = queue.pop(0)
        ins = [i.path for i in (_try(lambda: o.inputs, []) or []) if _try(lambda: i.path, None)]
        e = {'path': o.path, 'type': _try(lambda: o.OPType, ''), 'family': _family(o), 'depth': lvl, 'inputs': ins,
             'cooks': _try(lambda: o.totalCooks, None)}
        mi = _try(lambda: o.minInputs, None)
        if isinstance(mi, int) and mi:
            e['minInputs'] = mi
        for k in ('bypass', 'lock'):
            if _try(lambda: bool(getattr(o, k)), False):
                e[k] = True
        er = _try(lambda: o.errors(recurse=False), '')
        if er:
            e['errors'] = clip_str(er, 160)
        wr = _try(lambda: o.warnings(recurse=False), '')
        if wr:
            e['warnings'] = clip_str(wr, 160)
            if 'compile error' in str(wr).lower():  # TD reports a failed GLSL compile as a warning
                cr = str(_try(lambda: o.compileResult, '') or '')
                e['compile'] = clip_str(next((ln.strip() for ln in cr.splitlines() if 'ERROR' in ln), '')
                                        or wr, 160)
        nodes.append(e)
        if e['family'] != 'TOP':
            e['unsampled'] = 'not a TOP ({}): the walk stops there'.format(e['family'])
            continue
        e['res'] = [_try(lambda: o.width), _try(lambda: o.height)]
        pars = {n: _pv(o, n) for n in TRACE_PARS}
        e['pars'] = {k: v for k, v in pars.items() if isinstance(v, (bool, int, float, str))}
        if e['type'] == 'levelTOP':
            risk = _negative_risk(o)
            if risk:
                e['negativeFloat'] = risk['settings']
        if e['cooks'] == 0:
            e['unsampled'] = 'never cooked: nothing asks for this image'
        elif numpy_bad:
            e['unsampled'] = 'numpy unusable'
        elif time.perf_counter() >= deadline:
            stopped = True
            e['unsampled'] = 'time budget ({} s) ran out'.format(TRACE_BUDGET_S)
        else:
            try:
                a = o.numpyArray(delayed=False)
                if a is None:
                    e['unsampled'] = 'no image (numpyArray returned None)'
                else:
                    e['stats'] = _trace_stats(a)
            except Exception as ex:
                if 'numpy' in str(ex).lower() or isinstance(ex, ImportError):
                    numpy_bad = _err_note('numpyArray', ex) + ' (T-48: restart TD)'
                e['unsampled'] = clip_str(_err_note('numpyArray', ex), 120)
        if lvl >= depth:
            if ins:
                e['deeper'] = True
            continue
        for i in _try(lambda: o.inputs, []) or []:
            p = _try(lambda: i.path, None)
            if p and p not in seen:
                seen.add(p)
                queue.append((i, lvl + 1))
    marks = trace_marks(nodes)
    for e in nodes:
        e['state'] = trace_state(e.get('stats'))
        if e['path'] in marks:
            e['mark'], e['why'] = marks[e['path']]
    notes = ['wires only: an image reached through a parameter (Select TOP, Render TOP camera/geometry) is not followed']
    if numpy_bad:
        notes.append(numpy_bad)
    if nodes and nodes[0].get('cooks') == 0:
        notes.append('{} has never cooked: nothing views, displays or outputs it'.format(r0.path))
    if queue:
        notes.append('{} input(s) past the {}-node cap not visited: trace again from a lower node'.format(
            len(queue), TRACE_MAX_NODES))
    if stopped:
        notes.append('read budget ran out: later nodes walked but not read')
    return {'root': r0.path, 'depth': depth, 'frame': _try(lambda: absTime.frame, None),  # noqa: F405
            'look_at': [[p, m[0]] for p, m in marks.items()], 'nodes': nodes, 'notes': notes,
            'ms': round((time.perf_counter() - t0) * 1000, 1)}


SAVE_HOOK_TEXT = '''# Jazib MCP save hook (td_save_hook): writes the network text (jtd-net) beside the .toe after each save.
# The work is in the handlers DAT beside this one; it never raises into TD's save.

def onProjectPostSave():
    h = me.parent().op('handlers')
    if h is not None:
        h.module.save_hook_write(me)
    return
'''


def _save_hook_target(root_path):
    folder = str(_try(lambda: project.folder, '') or '')  # noqa: F405
    return os.path.join(folder, sidecar_name(_try(lambda: project.name, ''), root_path))  # noqa: F405


def save_hook_write(hook=None, root_path=None):
    """Called by the save_hook Execute DAT after a save (and by save_hook write_now). Never raises: problems go to the
    status DAT and the return value."""
    try:
        h = hook if hook is not None else _try(lambda: op(comp_path()).op(SAVE_HOOK_NAME), None)  # noqa: F405
        if h is not None:
            root_path = _try(lambda: h.fetch(SAVE_HOOK_KEY, None, search=False), None) or root_path
        root_path = root_path or '/project1'
        r0 = op(root_path)  # noqa: F405
        if r0 is None:
            raise ValueError('no operator at {}'.format(root_path))
        n = len(_bounded_walk(r0, SAVE_HOOK_MAX_OPS + 1)[0])
        if n > SAVE_HOOK_MAX_OPS:
            raise ValueError('{} has over {} ops: not written (it would slow every save)'.format(root_path,
                                                                                              SAVE_HOOK_MAX_OPS))
        target = _save_hook_target(root_path)
        if os.path.exists(target):
            with open(target, 'r', encoding='utf-8', errors='replace') as f:
                if not is_our_net_text(f.readline()):
                    raise ValueError('{} exists and is not a jtd-net text: left alone'.format(target))
        t0 = time.perf_counter()
        r = cmd_net_export(root_path, max_chars=0)
        write_text_atomic(target, r['text'])
        out = {'file': target, 'ops': r['ops'], 'ms': round((time.perf_counter() - t0) * 1000, 1)}
        _try(lambda: _status_comp('save hook wrote {} ({} ops)'.format(os.path.basename(target), r['ops'])))
        return out
    except Exception as e:
        msg = 'save hook: {}: {}'.format(type(e).__name__, e)
        _try(lambda: _status_comp(msg))
        print('jazib_mcp:', msg)
        return {'error': msg}


def _status_comp(text):
    st = op(comp_path()).op('status')  # noqa: F405
    if st is not None:
        st.text = '{}  {}\n'.format(time.strftime('%Y-%m-%d %H:%M:%S'), text)


def cmd_save_hook(on=None, path='/project1', write_now=False):
    """Network text on save (td-atlas text_on_save; default off). on true: an Execute DAT /jazib_mcp/save_hook with
    Project Post-Save on writes <project>.<root>.jtdnet beside the .toe after every save (root = path, <= 2000 ops,
    atomic, never over a file that is not ours). on false: removes it. on omitted: status. write_now: write once now."""
    c = _op(comp_path(), 'MCP COMP')
    h = c.op(SAVE_HOOK_NAME)
    out = {}
    if on is True:
        root_ = _op(path)
        if h is None:
            h = c.create(executeDAT, SAVE_HOOK_NAME)  # noqa: F405
            h.nodeX, h.nodeY = 600, -400
        for p in ('start', 'create', 'exit', 'framestart', 'frameend', 'playstatechange', 'devicechange',
                  'projectpresave'):
            if h.par[p] is not None:
                h.par[p] = False
        if h.par['projectpostsave'] is None:
            raise RuntimeError('executeDAT has no projectpostsave par on this build')
        h.par.projectpostsave = True
        h.par.active = True
        h.text = SAVE_HOOK_TEXT
        h.store(SAVE_HOOK_KEY, root_.path)
        h.comment = 'td_save_hook: writes {} after each save'.format(sidecar_name('<project>', root_.path))
    elif on is False:
        if h is not None:
            h.destroy()
        h = None
        out['removed'] = True
    root_path = (_try(lambda: h.fetch(SAVE_HOOK_KEY, None, search=False), None) if h is not None else None) or path
    out.update({'installed': h is not None, 'root': root_path, 'file': _save_hook_target(root_path),
                'project_saved_once': bool(_try(lambda: project.folder, ''))})  # noqa: F405
    if write_now:
        out['wrote'] = save_hook_write(h, root_path)
    if h is not None:
        out['note'] = 'lives in {} (saved with the .toe); reinstalling the MCP COMP removes it'.format(h.path)
    return out


# ================================================================== MCP upgrades 27 Oct 2026
# About stamp, mirror pars, record CHOP (research AM_tdxcomponents), td_shadertoy (AN), td_osc_expose (AY),
# layer mixer + cook_active (AU). Builders make self-contained COMPs: custom pars drive the insides, Out ops carry
# the output only, own `controls` panel (Parameter COMP on the COMP's own pages) + `controls_window` opened by an
# Opencontrols pulse; rebuilds update in place (T-70) and re-apply the stage plan (T-69).

SEMVER_RE = re.compile(r'^\s*(\d+)(?:\.(\d+))?(?:\.(\d+))?')
ABOUT_LABELS = (('Version', 'Version'), ('Touchbuild', 'Touch build'), ('Saved', 'Saved'))


def about_values(current=None, version=None, bump=None, build='', now=None):
    """Pure: the About page values for a tox save. version wins over the COMP's current one (default 0.1.0);
    bump major|minor|patch counts it up (x.y.z)."""
    if bump not in (None, 'major', 'minor', 'patch'):
        raise ValueError('bump must be major, minor or patch, got {!r}'.format(bump))
    v = str(version) if version is not None else (str(current) if current else '0.1.0')
    if bump:
        m = SEMVER_RE.match(v)
        if m is None:
            raise ValueError('cannot bump version {!r} (want x.y.z)'.format(v))
        a, b, c = int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)
        a, b, c = (a + 1, 0, 0) if bump == 'major' else ((a, b + 1, 0) if bump == 'minor' else (a, b, c + 1))
        v = '{}.{}.{}'.format(a, b, c)
    t = time.localtime(now) if now is not None else time.localtime()
    return {'Version': v, 'Touchbuild': str(build), 'Saved': time.strftime('%Y-%m-%d %H:%M', t)}


def _stamp_about(o, about):
    """Str pars Version / Touchbuild / Saved on an About page (made once; pars found elsewhere are just set)."""
    pg = None
    for name, label in ABOUT_LABELS:
        if o.par[name] is None:
            if pg is None:
                pg = next((cp for cp in _try(lambda: list(o.customPages), []) if cp.name == 'About'), None) \
                    or o.appendCustomPage('About')
            pg.appendStr(name, label=label)
        o.par[name].val = about[name]


# ------------------------------------------------------------------ td_custom_pars mirror (Optimeister idea, AM)
MIRROR_KEYS = ('src', 'pars', 'pages', 'prefix', 'replace_expr')
MIRROR_SKIP_STYLES = ('Header', 'Sequence')
MIRROR_SKIP_PAGES = ('common',)
MIRROR_VECTORS = {'XY': 'XYZW', 'XYZ': 'XYZW', 'XYZW': 'XYZW', 'UV': 'UVW', 'UVW': 'UVW', 'WH': 'WH', 'RGB': 'RGBA',
                  'RGBA': 'RGBA'}
MIRROR_BY_SIZE = {'XYZW': {2: 'XY', 3: 'XYZ', 4: 'XYZW'}, 'UVW': {2: 'UV', 3: 'UVW'}, 'WH': {2: 'WH'},
                  'RGBA': {3: 'RGB', 4: 'RGBA'}}
MIRROR_SINGLES = {'Float': 'Float', 'Int': 'Int', 'Toggle': 'Toggle', 'Pulse': 'Pulse', 'Momentary': 'Momentary',
                  'Menu': 'Menu', 'StrMenu': 'StrMenu', 'Str': 'Str', 'File': 'File', 'FileSave': 'FileSave',
                  'Folder': 'Folder', 'Python': 'Python', 'TOP': 'TOP', 'CHOP': 'CHOP', 'SOP': 'SOP', 'DAT': 'DAT',
                  'MAT': 'MAT', 'COMP': 'COMP', 'OP': 'OP', 'OBJ': 'OBJ', 'Object': 'OBJ', 'PanelCOMP': 'PanelCOMP',
                  'POP': 'POP'}
MIRROR_RANGE_KEYS = ('min', 'max', 'normMin', 'normMax', 'clampMin', 'clampMax')
MIRROR_PULSE_KEY = 'jz_mirror_pulses'   # COMP storage: {custom pulse name: [inner op path relative to COMP, par]}
MIRROR_PULSE_TEXT = '''# jazib-td mirror pulses (td_custom_pars mirror): a pulse on the COMP pulses the inner op's own pulse.
def onPulse(par):
    t = parent().fetch('jz_mirror_pulses', {}, search=False).get(par.name)
    if t:
        o = parent().op(t[0])
        if o is not None and o.par[t[1]] is not None:
            o.par[t[1]].pulse()
'''


def mirror_custom_name(prefix, tuplet):
    """Builtin tuplet name -> a valid custom par name (one capital, then lowercase letters/digits) or None."""
    s = re.sub(r'[^a-z0-9]', '', (str(prefix or '') + str(tuplet or '')).lower())
    n = s[:1].upper() + s[1:]
    return n if valid_custom_name(n) else None


def mirror_plan(infos, patterns=None, pages=None, prefix='', replace_expr=False, exists=lambda n: False):
    """Pure: which builtin pars of the inner op become custom pars on the COMP. infos = [{name, tuplet, style, page,
    label, readOnly, mode, ...ranges, menuNames, menuLabels}] in par order. Returns (groups, skipped); a group =
    {cname, append, size, label, members, infos, pulse}. Tuplets stay together (tx ty -> one XY par)."""
    order, by = [], {}
    for i in infos:
        t = i.get('tuplet') or i['name']
        if t not in by:
            by[t] = []
            order.append(t)
        by[t].append(i)
    pats = [p for p in (patterns or ['*']) if p]
    pg = [str(p).lower() for p in pages] if pages else None
    groups, skipped = [], []
    for t in order:
        ms = by[t]
        names = [m['name'] for m in ms]
        if t == 'pageindex' or 'pageindex' in names:
            continue
        if not any(fnmatch.fnmatchcase(n, p) for p in pats for n in names + [t]):
            continue
        page = str(ms[0].get('page') or '').lower()
        if (pg is not None and page not in pg) or (pg is None and (not page or page in MIRROR_SKIP_PAGES)):
            continue
        style = ms[0].get('style') or ''
        why = None
        if style in MIRROR_SKIP_STYLES:
            why = 'style {} is not mirrored'.format(style)
        elif any(m.get('readOnly') for m in ms):
            why = 'read-only (an output value)'
        elif not replace_expr and any(str(m.get('mode') or 'CONSTANT') != 'CONSTANT' for m in ms):
            why = 'has an expression/bind/export (replace_expr:true replaces it with the binding)'
        n = len(ms)
        app, size = None, 1
        if why is None:
            if style in MIRROR_VECTORS:
                app = MIRROR_BY_SIZE[MIRROR_VECTORS[style]].get(n)
                if app is None:
                    app, size = 'Float', n
            elif style in ('Float', 'Int'):
                app, size = style, n
            elif n == 1 and style in MIRROR_SINGLES:
                app = MIRROR_SINGLES[style]
            else:
                why = 'style {} with {} members is not mirrored'.format(style, n)
        cname = mirror_custom_name(prefix, t) if why is None else None
        if why is None and cname is None:
            why = 'no valid custom name from {!r}'.format(t)
        if why is None and exists(cname):
            why = 'custom par {} exists on the COMP'.format(cname)
        if why is not None:
            skipped.append({'par': t, 'members': names, 'why': why})
            continue
        label = str(ms[0].get('label') or t)
        groups.append({'cname': cname, 'append': app, 'size': size, 'label': label, 'members': names, 'infos': ms,
                       'pulse': app == 'Pulse'})
    return groups, skipped


def _par_info(p):
    d = {'name': p.name, 'tuplet': _try(lambda: p.tupletName, p.name) or p.name, 'style': _try(lambda: p.style, ''),
         'page': _try(lambda: p.page.name, ''), 'label': _try(lambda: p.label, p.name),
         'readOnly': bool(_try(lambda: p.readOnly, False)), 'mode': mode_name(_try(lambda: p.mode, 'CONSTANT'))}
    if _try(lambda: p.isMenu, False):
        d['menuNames'] = [str(x) for x in _try(lambda: list(p.menuNames), [])]
        d['menuLabels'] = [str(x) for x in _try(lambda: list(p.menuLabels), [])]
    if _try(lambda: p.isNumber, False):
        for k in MIRROR_RANGE_KEYS:
            v = _try(lambda: getattr(p, k), None)
            if v is not None:
                d[k] = v
    return d


def custom_pars_mirror(c, page, mirror):
    """td_custom_pars mirror mode: every builtin par of an op INSIDE c (filtered by pars globs / pages) becomes a custom
    par on c's page, and the inner par is bound to it (inner.bindExpr = parent(n).par.<Custom>, mode BIND): the COMP's
    custom pars drive its insides (self-contained rule). Pulses are relayed by a Parameter Execute DAT (mirror_pulse)."""
    if not isinstance(mirror, dict) or not mirror.get('src'):
        raise ValueError('mirror must be {src, pars?, pages?, prefix?, replace_expr?}')
    bad = [k for k in mirror if k not in MIRROR_KEYS]
    if bad:
        raise ValueError('mirror: unknown keys {} (use {})'.format(bad, list(MIRROR_KEYS)))
    src = str(mirror['src'])
    s = op(src) if src.startswith('/') else c.op(src[2:] if src.startswith('./') else src)  # noqa: F405
    if s is None:
        raise ValueError('mirror src {!r}: no op (relative = inside {})'.format(src, c.path))
    if not s.path.startswith(c.path.rstrip('/') + '/'):
        raise ValueError('mirror src {} is not inside {} (its custom pars drive its own insides)'.format(s.path, c.path))
    rel = s.path[len(c.path.rstrip('/')) + 1:]
    depth = rel.count('/') + 1
    infos = [_par_info(p) for p in _try(lambda: list(s.pars()), []) if not _try(lambda: p.isCustom, False)]
    pats = mirror.get('pars')
    if isinstance(pats, str):
        pats = pats.split()
    groups, skipped = mirror_plan(infos, pats, mirror.get('pages'), mirror.get('prefix') or '',
                                  bool(mirror.get('replace_expr')), lambda n: _custom_exists(c, n))
    pg = next((cp for cp in _try(lambda: list(c.customPages), []) if cp.name == page), None)
    done, pulses = [], dict(_try(lambda: c.fetch(MIRROR_PULSE_KEY, {}, search=False), {}) or {})
    for g in groups:
        if pg is None:
            pg = c.appendCustomPage(page)
        kw = {'label': g['label']}
        if g['append'] in ('Float', 'Int') and g['size'] > 1:
            kw['size'] = g['size']
        meth = getattr(pg, 'append' + g['append'], None)
        if meth is None:
            skipped.append({'par': g['cname'], 'members': g['members'],
                            'why': 'append{} not in this build'.format(g['append'])})
            continue
        try:
            made = list(meth(g['cname'], **kw))
        except Exception as e:
            skipped.append({'par': g['cname'], 'members': g['members'], 'why': str(e)[:160]})
            continue
        bound = []
        for cp, info in zip(made, g['infos']):
            bp = s.par[info['name']]
            if info.get('menuNames') is not None:
                _try(lambda: setattr(cp, 'menuNames', info['menuNames']))
                _try(lambda: setattr(cp, 'menuLabels', info.get('menuLabels') or info['menuNames']))
            for k in MIRROR_RANGE_KEYS:
                if k in info:
                    _try(lambda: setattr(cp, k, info[k]))
            if g['pulse']:
                pulses[cp.name] = [rel, info['name']]
                bound.append([cp.name, info['name'], 'pulse relay'])
                continue
            _try(lambda: setattr(cp, 'default', bp.default))
            cur = bp.eval() if str(info.get('mode')) != 'CONSTANT' else bp.val
            _try(lambda: setattr(cp, 'val', cur))
            bp.bindExpr = 'parent({}).par.{}'.format(depth, cp.name)
            bp.mode = ParMode.BIND  # noqa: F405
            bound.append([cp.name, info['name']])
        done.append({'name': g['cname'], 'style': g['append'], 'bound': bound})
    r = {'src': s.path, 'page': page, 'mirrored': done, 'skipped': skipped}
    if pulses:
        c.store(MIRROR_PULSE_KEY, pulses)
        pe = c.op('mirror_pulse')
        if pe is None:
            pe = c.create(parameterexecuteDAT, 'mirror_pulse')  # noqa: F405
        pe.text = MIRROR_PULSE_TEXT
        notes = []
        for k, v in (('op', '..'), ('pars', ' '.join(sorted(pulses))), ('custom', True), ('builtin', False),
                     ('onpulse', True), ('valuechange', False)):
            _midi_set(pe, k, v, notes)
        r['pulse_relay'] = pe.path
        if notes:
            r['notes'] = notes
        r['layout'] = _arrange(c)
    return r


# ------------------------------------------------------------------ td_record_chop (Chop Recorder idea, AM)
REC_MAX_CHANS = 256


def record_csv(names, frames, times, rows):
    lines = [','.join(['frame', 'time'] + ['"{}"'.format(str(n).replace('"', "'")) for n in names])]
    for f, t, r in zip(frames, times, rows):
        lines.append(','.join([str(f), repr(rnd(t, 6))] + ['' if v is None else repr(rnd(v, 7)) for v in r]))
    return '\n'.join(lines) + '\n'


def cmd_record_chop(chop, seconds=None, frames=None, table=None, file=None, channels=None, append=False):
    """Record a CHOP's current values once per TD frame for N frames (or seconds x cookRate) into a Table DAT
    (frame, time, one column per channel; default <chop parent>/<chop>_rec) and optionally a .csv. Pending chain;
    the table is written once at the end (one undo step)."""
    c = _op(chop, 'chop')
    if _family(c) != 'CHOP':
        raise ValueError('{} is not a CHOP'.format(c.path))
    if (seconds is None) == (frames is None):
        raise ValueError('give seconds or frames (one of them)')
    rate = float(_try(lambda: project.cookRate, 60.0) or 60.0)  # noqa: F405
    n = int(math.ceil(float(seconds) * rate)) if seconds is not None else int(frames)
    if not 1 <= n <= RENDER_MAX_FRAMES:
        raise ValueError('frames must be 1..{} (seconds x cookRate {})'.format(RENDER_MAX_FRAMES, rate))
    all_names = [ch.name for ch in c.chans()]
    pats = channels.split() if isinstance(channels, str) else list(channels or [])
    idx = [i for i, nm in enumerate(all_names) if not pats or any(fnmatch.fnmatchcase(nm, p) for p in pats)]
    idx = idx[:REC_MAX_CHANS]
    if not idx:
        raise ValueError('{}: no channel matches {} (channels: {})'.format(c.path, pats, all_names[:20]))
    if n * len(idx) > AE_DATA_MAX_CELLS:
        raise ValueError('{} frames x {} channels is over the cap {}'.format(n, len(idx), AE_DATA_MAX_CELLS))
    if file is not None:
        _abs_file(file, ('.csv',))
    names = [all_names[i] for i in idx]
    if table is None:
        tpar, tname = c.parent(), c.name + '_rec'
    elif isinstance(table, str) and table.startswith('/'):
        tpar, tname = _op(table.rsplit('/', 1)[0] or '/', 'table parent'), table.rsplit('/', 1)[1]
    else:
        tpar, tname = c.parent(), str(table)
    if not valid_op_name(tname):
        raise ValueError('bad table name {!r}'.format(tname))
    t_old = tpar.op(tname)
    if t_old is not None and _try(lambda: t_old.OPType, '') != 'tableDAT':
        raise ValueError('{} exists and is a {}, not a Table DAT'.format(t_old.path, t_old.OPType))
    rows, fcol, tcol = [], [], []
    t0 = float(_try(lambda: absTime.seconds, 0.0))  # noqa: F405

    def sample():
        _try(lambda: c.cook(force=True))
        vals = [ch.eval() for ch in c.chans()]
        rows.append([vals[i] if i < len(vals) else None for i in idx])
        fcol.append(int(_try(lambda: absTime.frame, len(fcol))))  # noqa: F405
        tcol.append(float(_try(lambda: absTime.seconds, t0)) - t0)  # noqa: F405
        if len(rows) < n:
            return Pending(1, sample)
        return finish()

    def finish():
        t = tpar.op(tname)
        created = t is None
        if created:
            t = tpar.create(tableDAT, tname)  # noqa: F405
            t.nodeX, t.nodeY = _auto_xy(tpar, t, c.path if _try(lambda: c.parent().path) == tpar.path else None)
            _try(lambda: setattr(t, 'viewer', True))
        body = [[f, rnd(s, 6)] + [rnd(v, 7) if v is not None else '' for v in r] for f, s, r in zip(fcol, tcol, rows)]
        header = ['frame', 'time'] + names
        notes = []
        if append and _try(lambda: t.numRows, 0):
            old = [str(x) for x in _try(lambda: [cell.val for cell in t.row(0)], [])]
            if old != header:
                notes.append('append: header differs from the table\'s first row ({} vs {})'.format(old[:6], header[:6]))
            t.text = t.text.rstrip('\n') + '\n' + tsv(body)
        else:
            t.text = tsv([header] + body)
        r = {'table': t.path, 'frames': len(rows), 'channels': len(names), 'names': names[:20], 'fps': rnd(rate),
             'seconds': rnd(tcol[-1] if tcol else 0.0, 4), 'created': created}
        if file:
            os.makedirs(os.path.dirname(file), exist_ok=True)
            with open(file, 'w') as fh:
                fh.write(record_csv(names, fcol, tcol, rows))
            r['file'], r['bytes'] = file, os.path.getsize(file)
        gaps = sum(1 for a, b in zip(fcol, fcol[1:]) if b - a != 1)
        if gaps:
            notes.append('{} frame gaps (realTime dropped frames): the frame column holds absTime.frame'.format(gaps))
        if notes:
            r['notes'] = notes
        if created:
            r['layout'] = _arrange(tpar)
        return r
    return Pending(1, sample)


# ------------------------------------------------------------------ builder kit (self-contained COMPs)
KIT_KEY = 'jz_kit'  # COMP storage: which builder made it ({'kind': ..., ...} plain data, T-67)


def _kit_comp(parent, name, kind, default_name):
    """Find (ours, same kind) or create the builder's baseCOMP. Returns (comp, created)."""
    par_ = _op(parent or '/project1', 'parent')
    if not _try(lambda: par_.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(par_.path))
    name = name or default_name
    if not valid_op_name(name):
        raise ValueError('bad operator name {!r}'.format(name))
    c = par_.op(name)
    if c is not None:
        k = _try(lambda: c.fetch(KIT_KEY, {}, search=False), {}) or {}
        if _try(lambda: c.OPType, '') != 'baseCOMP' or k.get('kind') != kind:
            raise ValueError('{} exists and is not a {} COMP made by this tool (pick another name)'.format(c.path, kind))
        return c, False
    c = par_.create(baseCOMP, name)  # noqa: F405
    c.nodeX, c.nodeY = _auto_xy(par_, c)
    c.store(KIT_KEY, {'kind': kind})
    return c, True


def _kit_child(parent_, cls_name, nm, made, notes):
    """Reuse the op when it exists with that type (rebuild in place, T-70), else create it (viewer on)."""
    o = parent_.op(nm)
    if o is not None and _try(lambda: o.OPType, '') == cls_name:
        return o
    cls = getattr(td, cls_name, None)
    if not isinstance(cls, builtins.type):
        notes.append('{} not available in this build: {} not built'.format(cls_name, nm))
        return None
    if o is not None:
        old_type = _try(lambda: o.OPType, '?')  # read first: an immediate destroy leaves o invalid (QC 26 Oct)
        safe_destroy(o)
        notes.append('{} was a {}: replaced'.format(nm, old_type))
    try:
        o = parent_.create(cls, nm)
    except Exception as e:
        notes.append('{} could not be created: {}'.format(nm, str(e)[:160]))
        return None
    made.append(nm)
    if _family(o) in VIEWER_FAMILIES:
        _try(lambda: setattr(o, 'viewer', True))
    return o


def _kit_pars(c, page_name, specs):
    """Custom pars made once, existing values kept. spec = (name, style, default, opts) with style Float, Int, Toggle,
    Pulse, Menu, Str, TOP, COMP, OP, XY, RGB; opts: label, min, max (norm range + clamp for Int), names, labels."""
    page = next((pg for pg in _try(lambda: list(c.customPages), []) if pg.name == page_name), None)
    made = []
    for name, style, default, o in specs:
        o = o or {}
        if _custom_exists(c, name):
            if style == 'Menu' and 'names' in o:  # menus follow the build (sources change)
                p = c.par[name]
                cur = p.eval()
                p.menuNames, p.menuLabels = list(o['names']), list(o.get('labels') or o['names'])
                if cur in o['names']:
                    p.val = cur
            continue
        if page is None:
            page = c.appendCustomPage(page_name)
        label = o.get('label', name)
        grp = list(getattr(page, 'append' + style)(name, label=label))
        if style == 'Menu':
            grp[0].menuNames, grp[0].menuLabels = list(o['names']), list(o.get('labels') or o['names'])
        for p in grp:
            if 'min' in o and style in ('Float', 'Int', 'XY'):
                p.normMin, p.normMax = o['min'], o['max']
                if style == 'Int' or o.get('clamp'):
                    p.clampMin, p.min = True, o['min']
                    if o.get('clamp'):
                        p.clampMax, p.max = True, o['max']
        if default is not None and style != 'Pulse':
            vals = default if isinstance(default, (list, tuple)) else [default] * len(grp)
            for p, v in zip(grp, vals):
                p.default = v
                p.val = v
        made.append(name)
    return made


CONTROLS_EXEC = '''# {kind} controls (jazib-td): pulses on the COMP. Opencontrols opens this COMP's own controls window.
def onPulse(par):
    c = parent()
    if par.name == 'Opencontrols':
        c.op('controls_window').par.winopen.pulse()
{more}'''


def _kit_controls(c, kind, made, notes, w=420, h=600, pagescope='*', more='', pulses=('Opencontrols',)):
    """Own controls: a Parameter COMP showing this COMP's custom pages + a Window COMP, opened by Opencontrols."""
    panel = _kit_child(c, 'parameterCOMP', 'controls', made, notes)
    if panel is not None:
        for k, v in (('op', '..'), ('builtin', False), ('custom', True), ('pagescope', pagescope),
                     ('header', False), ('pagenames', True), ('w', int(w)), ('h', int(h))):
            _midi_set(panel, k, v, notes)
        _try(lambda: setattr(panel, 'comment', '{} controls: the COMP\'s own custom pages. Open: Opencontrols pulse'
                             .format(kind)))
    win = _kit_child(c, 'windowCOMP', 'controls_window', made, notes)
    if win is not None:
        for k, v in (('winop', 'controls'), ('title', '{} controls'.format(c.name)), ('size', {'menu': 'custom'}),
                     ('winw', int(w)), ('winh', int(h))):
            _midi_set(win, k, v, notes)
    pe = _kit_child(c, 'parameterexecuteDAT', 'controls_exec', made, notes)
    if pe is not None:
        pe.text = CONTROLS_EXEC.format(kind=kind, more=more)
        for k, v in (('op', '..'), ('pars', ' '.join(pulses)), ('custom', True), ('builtin', False),
                     ('onpulse', True), ('valuechange', False)):
            _midi_set(pe, k, v, notes)
    return ['controls', 'controls_window', 'controls_exec']


def _kit_wire(srcs, dst, notes):
    """Wire srcs[i] -> dst input i, connector to connector (never output.connect(op): that replaces input 0).
    Multi-input ops grow a free connector after each wire. Checked like td_connect; a miss is a note."""
    for i, s in enumerate(srcs):
        if s is None or dst is None:
            continue
        ins = _try(lambda: list(dst.inputConnectors), []) or []
        if i >= len(ins):
            notes.append('{}: no input {} for {}'.format(dst.path, i, s.path))
            continue
        _try(lambda: s.outputConnectors[0].connect(ins[i]))
    if dst is not None:
        got = _inputs(dst)
        want = [s.path if s is not None else None for s in srcs]
        if got[:len(want)] != want:
            notes.append('wire check: {} inputs {} (wanted {})'.format(dst.path, got[:len(want)], want))


def _kit_finish(c, stages, created, par_, notes):
    lay = _try(lambda: layout_stages(c, [s for s in stages if s['ops']], True), None)
    _point_pane(c)
    return {'layout': {'ok': lay.get('ok')} if isinstance(lay, dict) else None,
            'parent_layout': _arrange(par_) if created else None}


def _stage(c, title, role, ops_, body):
    return {'title': title, 'role': role, 'ops': [n for n in ops_ if c.op(n) is not None], 'body': body}


# ------------------------------------------------------------------ td_shadertoy (research AN #1)
ST_KIND = 'shadertoy'
ST_UNIFORMS = ('iResolution', 'iTime', 'iTimeDelta', 'iFrameF', 'iMouse', 'iDate', 'iFrameRate')
ST_DECL_RE = re.compile(r'^\s*uniform\s+\w+\s+(iResolution|iTime|iTimeDelta|iFrame|iFrameRate|iMouse|iDate|'
                        r'iSampleRate|iChannel[0-3]|iChannelTime|iChannelResolution)\b[^;]*;', re.M)
ST_CHANNEL_RE = re.compile(r'\biChannel([0-3])\b')
ST_FORMATS = ('rgba8fixed', 'rgba16float', 'rgba32float')
ST_MAX_CODE = 512 * 1024


def shadertoy_scan(code):
    """Pure: check Shadertoy image-shader source. Returns {channels: [used indices], warnings}; raises ValueError for
    what cannot run (no mainImage, its own main())."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError('code must be the Shadertoy source (the Image tab)')
    if len(code) > ST_MAX_CODE:
        raise ValueError('code is over {} bytes'.format(ST_MAX_CODE))
    body = re.sub(r'//[^\n]*|/\*.*?\*/', ' ', code, flags=re.S)
    if not re.search(r'\bvoid\s+mainImage\s*\(', body):
        raise ValueError('no mainImage(out vec4 fragColor, in vec2 fragCoord): not a Shadertoy image shader')
    if re.search(r'\bvoid\s+main\s*\(\s*(void)?\s*\)', body):
        raise ValueError('the code has its own main(): paste the Shadertoy Image tab (mainImage), not a full shader')
    w = []
    if re.search(r'\bsamplerCube\b|\btextureCube\b', body):
        w.append('cubemap channels are not supported (TD inputs are 2D): sample a 2D TOP or rewrite those lines')
    if re.search(r'\bmainSound\s*\(', body):
        w.append('mainSound (sound shader) is ignored: TD audio comes from CHOPs')
    if re.search(r'^\s*#\s*version\b', code, re.M):
        w.append('#version line removed (TD sets the GLSL version)')
    if ST_DECL_RE.search(code):
        w.append('uniform declarations of Shadertoy inputs commented out (the wrapper declares them)')
    used = sorted(set(int(m) for m in ST_CHANNEL_RE.findall(body)))
    return {'channels': used, 'warnings': w}


def shadertoy_wrap(code, n_inputs=0, compute=False):
    """Pure: wrap Shadertoy source for a TD GLSL TOP (pixel or compute). Returns (glsl text, header line count).
    Uniforms come from the GLSL TOP's Vectors page; iChannelN = sTD2DInputs[N]; '#line 1' before the user code so
    compile-log line numbers are the user's own."""
    user = re.sub(r'^\s*#\s*version\b[^\n]*', '// (#version removed by td_shadertoy)', code, flags=re.M)
    user = ST_DECL_RE.sub(lambda m: '// (declared by td_shadertoy) ' + m.group(0).strip(), user)
    n = max(0, min(4, int(n_inputs)))
    h = ['// td_shadertoy wrapper (jazib-td). Edit the `source` DAT and call td_shadertoy again; this text is rebuilt.',
         'uniform vec3 iResolution;', 'uniform float iTime;', 'uniform float iTimeDelta;', 'uniform float iFrameF;',
         'uniform vec4 iMouse;', 'uniform vec4 iDate;', 'uniform float iFrameRate;', '#define iFrame int(iFrameF)',
         '#define iSampleRate 44100.0']
    h += ['#define iChannel{0} sTD2DInputs[{0}]'.format(i) for i in range(n)]
    h += ['vec3 iChannelResolution[4];', 'float iChannelTime[4];']
    h += (['layout (local_size_x = 8, local_size_y = 8) in;'] if compute
          else ['layout(location = 0) out vec4 jzFragColor;'])
    h.append('#line 1')
    tail = ['', '#line 100000', 'void main()', '{']
    tail += ['\tiChannelResolution[{0}] = vec3(uTD2DInfos[{0}].res.zw, 1.0);'.format(i) for i in range(n)]
    tail += ['\tiChannelResolution[{}] = vec3(0.0);'.format(i) for i in range(n, 4)]
    tail += ['\tiChannelTime[{}] = iTime;'.format(i) for i in range(4)]
    tail.append('\tvec4 c = vec4(0.0, 0.0, 0.0, 1.0);')
    if compute:
        tail += ['\tivec2 p = ivec2(gl_GlobalInvocationID.xy);',
                 '\tif (p.x >= int(iResolution.x) || p.y >= int(iResolution.y)) return;',
                 '\tmainImage(c, vec2(p) + 0.5);',
                 '\tTDImageStoreOutput(0, ivec3(gl_GlobalInvocationID), c);']
    else:
        tail += ['\tmainImage(c, gl_FragCoord.xy);', '\tjzFragColor = TDOutputSwizzle(c);']
    tail.append('}')
    return '\n'.join(h) + '\n' + user.rstrip('\n') + '\n' + '\n'.join(tail) + '\n', len(h)


def shadertoy_uniform_exprs():
    """Uniform name -> [x, y, z, w] Python expressions (GLSL TOP Vectors page), evaluated in the glsl op."""
    t = "__import__('time')"
    return [
        ('iResolution', ['parent().par.Resw', 'parent().par.Resh', '1', '0']),
        ('iTime', ["op('clock')['seconds'].eval()", '0', '0', '0']),
        ('iTimeDelta', ['parent().par.Speed * float(parent().par.Play) / me.time.rate', '0', '0', '0']),
        ('iFrameF', ["op('clock')['frames'].eval()", '0', '0', '0']),
        ('iMouse', ['parent().par.Mousex * parent().par.Resw', 'parent().par.Mousey * parent().par.Resh',
                    '(1 if parent().par.Mousedown else -1) * parent().par.Mouseclickx * parent().par.Resw',
                    '(1 if parent().par.Mousedown else -1) * parent().par.Mouseclicky * parent().par.Resh']),
        ('iDate', ['{}.localtime().tm_year'.format(t), '{}.localtime().tm_mon - 1'.format(t),
                   '{}.localtime().tm_mday'.format(t),
                   '(lambda a, s: a.tm_hour * 3600 + a.tm_min * 60 + a.tm_sec + s % 1)({0}.localtime(), {0}.time())'
                   .format(t)]),
        ('iFrameRate', ['project.cookRate', '0', '0', '0']),
    ]


ST_SOURCE_HEAD = ('// Shadertoy source for td_shadertoy (jazib-td). Licence: {licence}. Author: {author}. URL: {url}\n'
                  '// Shadertoy shaders default to CC BY-NC-SA 3.0 unless the author says otherwise: keep this note.\n')


def cmd_shadertoy(code, parent='/project1', name='shadertoy', compute=False, res=None, channels=None, licence=None,
                  author=None, url=None, frames=3):
    """Shadertoy Image-tab source -> a self-contained COMP: source + shader DATs, GLSL TOP (pixel, or compute: T-47),
    iChannel0..3 Select TOPs (custom Channel0..3 pars, black when empty), clock (Play / Speed / Reset), Out TOP,
    own controls. Called again on the same COMP it updates in place. Replies after `frames` with the compile result."""
    scan = shadertoy_scan(code)
    if channels is not None and (not isinstance(channels, list) or len(channels) > 4):
        raise ValueError('channels must be a list of up to 4 TOP paths (iChannel0..3)')
    chans = list(channels or [])
    n_in = max([i + 1 for i in scan['channels']] + [len([x for x in chans if x])] + [0])
    if res is not None and (not isinstance(res, (list, tuple)) or len(res) != 2):
        raise ValueError('res must be [w, h]')
    for p in chans:
        if p and (not isinstance(p, str) or not p.startswith('/')):
            raise ValueError('channels: absolute TOP paths, got {!r}'.format(p))
    c, created = _kit_comp(parent, name, ST_KIND, 'shadertoy')
    par_ = c.parent()
    w, h = (int(res[0]), int(res[1])) if res else DEFAULT_RES
    made, notes = [], []
    _kit_pars(c, 'Shader', [
        ('Play', 'Toggle', True, {'label': 'Play'}),
        ('Speed', 'Float', 1.0, {'label': 'Speed', 'min': 0.0, 'max': 4.0}),
        ('Reset', 'Pulse', None, {'label': 'Reset time + frame'}),
        ('Resw', 'Int', w, {'label': 'Width', 'min': 16, 'max': 4096}),
        ('Resh', 'Int', h, {'label': 'Height', 'min': 16, 'max': 4096}),
        ('Format', 'Menu', 'rgba8fixed', {'label': 'Pixel format', 'names': list(ST_FORMATS),
                                          'labels': ['8-bit fixed', '16-bit float', '32-bit float']}),
        ('Mouse', 'XY', [0.5, 0.5], {'label': 'iMouse xy (0..1)'}),
        ('Mouseclick', 'XY', [0.5, 0.5], {'label': 'iMouse click (0..1)'}),
        ('Mousedown', 'Toggle', False, {'label': 'iMouse button down'})])
    _kit_pars(c, 'Channels', [('Channel{}'.format(i), 'TOP', None, {'label': 'iChannel{}'.format(i)})
                              for i in range(4)])
    _kit_pars(c, 'Controls', [('Opencontrols', 'Pulse', None, {'label': 'Open controls'})])
    _kit_pars(c, 'About', [('Licence', 'Str', '', {'label': 'Licence'}), ('Author', 'Str', '', {'label': 'Author'}),
                           ('Url', 'Str', '', {'label': 'Shadertoy URL'})])
    for k, v in (('Licence', licence), ('Author', author), ('Url', url)):
        if v is not None:
            c.par[k].val = str(v)
    for i, p in enumerate(chans):
        if p:
            c.par['Channel{}'.format(i)].val = p
    if res:
        c.par.Resw.val, c.par.Resh.val = w, h
    src = _kit_child(c, 'textDAT', 'source', made, notes)
    lic = {'licence': c.par.Licence.eval() or 'not given', 'author': c.par.Author.eval() or 'not given',
           'url': c.par.Url.eval() or 'not given'}
    src.text = ST_SOURCE_HEAD.format(**lic) + code
    glsl_text, head = shadertoy_wrap(code, n_in, bool(compute))
    sh = _kit_child(c, 'textDAT', 'shader', made, notes)
    sh.text = glsl_text
    black = _kit_child(c, 'constantTOP', 'ch_black', made, notes)
    for k, v in (('colorr', 0), ('colorg', 0), ('colorb', 0), ('alpha', 1), ('outputresolution', {'menu': 'custom'}),
                 ('resolutionw', 16), ('resolutionh', 16)):
        _midi_set(black, k, v, notes)
    sels = []
    for i in range(n_in):
        s = _kit_child(c, 'selectTOP', 'ichannel{}'.format(i), made, notes)
        _midi_set(s, 'top', {'expr': "parent().par.Channel{}.eval() or op('ch_black')".format(i)}, notes)
        sels.append(s)
    for i in range(n_in, 4):
        old = c.op('ichannel{}'.format(i))
        if old is not None:
            safe_destroy(old)
    rate = _kit_child(c, 'constantCHOP', 'rate', made, notes)
    _try(lambda: setattr(rate.seq.const, 'numBlocks', 2))
    for k, v in (('const0name', 'seconds'), ('const0value', {'expr': 'parent().par.Speed * float(parent().par.Play)'}),
                 ('const1name', 'frames'), ('const1value', {'expr': 'float(parent().par.Play) * project.cookRate'})):
        _midi_set(rate, k, v, notes)
    clock = _kit_child(c, 'speedCHOP', 'clock', made, notes)
    _kit_wire([rate], clock, notes)
    g = _kit_child(c, 'glslTOP', 'glsl', made, notes)
    mode = 'compute' if compute else 'vertexpixel'
    for k, v in (('glslversion', {'menu': 'glsl460'}), ('mode', {'menu': mode}),
                 ('computedat' if compute else 'pixeldat', 'shader'), ('outputresolution', {'menu': 'custom'}),
                 ('resolutionw', {'expr': 'parent().par.Resw'}), ('resolutionh', {'expr': 'parent().par.Resh'}),
                 ('format', {'expr': 'parent().par.Format.eval()'})):
        _midi_set(g, k, v, notes)
    _midi_set(g, 'pixeldat' if compute else 'computedat', '', notes)
    unis = shadertoy_uniform_exprs()
    _try(lambda: setattr(g.seq.vec, 'numBlocks', len(unis)))
    for i, (uname, ex) in enumerate(unis):
        _midi_set(g, 'vec{}name'.format(i), uname, notes)
        for comp_, e in zip('xyzw', ex):
            _midi_set(g, 'vec{}value{}'.format(i, comp_), {'expr': e}, notes)
    for i in range(3):
        if i < len(_try(lambda: list(g.inputConnectors), []) or []):
            _try(lambda: g.inputConnectors[i].disconnect())
    _kit_wire(sels[:3], g, notes)
    _midi_set(g, 'tops', 'ichannel3' if n_in == 4 else '', notes)
    out = _kit_child(c, 'outTOP', 'out1', made, notes)
    _kit_wire([g], out, notes)
    ctl = _kit_controls(c, 'Shadertoy', made, notes, 420, 560, 'Shader Channels About',
                        more="    elif par.name == 'Reset':\n        c.op('clock').par.resetpulse.pulse()\n",
                        pulses=('Opencontrols', 'Reset'))
    c.store(KIT_KEY, {'kind': ST_KIND, 'compute': bool(compute), 'channels': n_in})
    c.comment = 'td_shadertoy: Shadertoy image shader ({} mode). Licence: {}'.format(mode, lic['licence'])
    about = about_values(_try(lambda: c.par.Version.eval(), None), None, None,
                         td_build_string(_try(lambda: app.version, ''), _try(lambda: app.build, '')))  # noqa: F405
    _stamp_about(c, about)
    stages = [_stage(c, 'Source', 'input', ['source', 'shader'], 'Shadertoy code (+ licence note) and the TD wrapper'),
              _stage(c, 'Channels', 'input', ['ch_black'] + ['ichannel{}'.format(i) for i in range(n_in)],
                     'iChannel0..3 = Select TOPs on the Channel pars (black when empty)'),
              _stage(c, 'Clock', 'control', ['rate', 'clock'], 'iTime / iFrame: Play, Speed, Reset'),
              _stage(c, 'Shader', 'process', ['glsl'], 'GLSL TOP ({}); uniforms on its Vectors page'.format(mode)),
              _stage(c, 'Output', 'output', ['out1'], 'Out TOP: the image only'),
              _stage(c, 'Controls', 'control', ctl, 'Opencontrols opens the panel')]
    fin = _kit_finish(c, stages, created, par_, notes)

    def finish():
        _try(lambda: g.cook(force=True))
        err = (_try(lambda: g.errors(), '') or '') + '\n' + (_try(lambda: g.warnings(), '') or '')
        log = _try(lambda: _glsl_log(g), '') or ''
        bad = [ln for ln in (err + '\n' + log).splitlines() if re.search(r'error', ln, re.I)]
        r = {'path': c.path, 'created': created, 'mode': mode, 'glsl': g.path, 'out': out.path if out else None,
             'channels_used': scan['channels'], 'inputs': n_in, 'compile': {'ok': not bad, 'errors': bad[:20],
                                                                           'log': log.strip()[:4000]},
             'line_note': 'compile-log line numbers are your source lines (#line 1); 100000+ = the wrapper main()',
             'header_lines': head, 'licence': lic, 'new_ops': made, 'warnings': scan['warnings']}
        r.update(fin)
        if notes:
            r['notes'] = notes
        r['hint'] = ('Opencontrols on {} opens its panel; Channel0..3 pars pick the iChannel TOPs; Licence/Author/Url '
                     'keep the source note'.format(c.path))
        return r
    return Pending(max(1, int(frames)), finish)


# ------------------------------------------------------------------ td_osc_expose (research AY)
OSCX_KIND = 'osc_expose'
OSCX_LAYOUTS = ('plain', 'osct')
OSCX_RT = '''# jazib-td osc_expose runtime (td_osc_expose). Lives in <expose COMP>/runtime; the DAT callbacks call it.
# Incoming OSC only writes the custom pars listed in the map table (an allow-list), values coerced to the par style:
# no eval, no exec, no command route.
import fnmatch
import json
import time

MAP_HEADER = ['address', 'in_address', 'par', 'members', 'style', 'type', 'min', 'max', 'menu', 'label']
VEC_STYLES = {'XY': 2, 'XYZ': 3, 'XYZW': 4, 'UV': 2, 'UVW': 3, 'WH': 2, 'RGB': 3, 'RGBA': 4}
OSCT_TYPES = {'Float': 'FLOAT', 'Int': 'INT', 'Toggle': 'BOOL', 'Momentary': 'BOOL', 'Pulse': 'EVENT',
              'Str': 'STRING', 'StrMenu': 'STRING', 'Menu': 'STRING', 'XY': 'VEC2', 'UV': 'VEC2', 'WH': 'VEC2',
              'XYZ': 'VEC3', 'UVW': 'VEC3', 'RGB': 'COLOR', 'RGBA': 'COLOR', 'XYZW': 'COLOR'}
QUERY_TYPES = {'Float': 'f', 'Int': 'i', 'Toggle': 'T', 'Momentary': 'T', 'Pulse': 'I', 'Str': 's', 'StrMenu': 's',
               'Menu': 's'}
SKIP_STYLES = ('Header', 'Sequence', 'Python', 'File', 'FileSave', 'Folder', 'TOP', 'CHOP', 'SOP', 'DAT', 'MAT',
               'COMP', 'OP', 'OBJ', 'Object', 'PanelCOMP', 'POP')


def seg(s):
    out = ''.join(ch if ch.isalnum() or ch in '_-.' else '_' for ch in str(s))
    return out.strip('_') or 'x'


def addresses(prefix, group, style, layout):
    """(send address, receive address) of one par group."""
    if layout == 'osct':
        name = seg(prefix.strip('/').replace('/', '_')) + '_' + seg(group)
        t = OSCT_TYPES.get(style, 'FLOAT')
        return '/OSCT/R/{}/{}'.format(t, name), '/OSCT/S/{}/{}'.format(t, name)
    a = '/' + '/'.join(seg(x) for x in prefix.strip('/').split('/') if x) + '/' + seg(group)
    return a, a


def plan(groups, prefix, layout, pats=None, pages=None):
    """groups = [{par (group name), members, style, page, label, min, max, menu}] -> (map rows, skipped)."""
    rows, skipped = [], []
    pg = [p.lower() for p in pages] if pages else None
    for g in groups:
        if pats and not any(fnmatch.fnmatchcase(g['par'], p) for p in pats):
            continue
        if pg is not None and str(g.get('page', '')).lower() not in pg:
            continue
        if g['style'] in SKIP_STYLES or (g['style'] not in VEC_STYLES and g['style'] not in QUERY_TYPES
                                         and len(g['members']) == 1):
            skipped.append([g['par'], 'style ' + g['style']])
            continue
        if g.get('page') == 'Controls' or g['par'] == 'Opencontrols':
            continue
        a, ia = addresses(prefix, g['par'], g['style'], layout)
        n = len(g['members'])
        if g['style'] in ('Float', 'Int'):
            typ = ('f' if g['style'] == 'Float' else 'i') * n
        elif g['style'] in VEC_STYLES:
            typ = 'f' * n
        else:
            typ = QUERY_TYPES[g['style']]
        rows.append([a, ia, g['par'], ' '.join(g['members']), g['style'], typ, g.get('min', ''), g.get('max', ''),
                     ' '.join(g.get('menu') or []), g.get('label', g['par'])])
    return rows, skipped


def encode(style, vals, layout='plain'):
    """Par values -> OSC args."""
    if style == 'Pulse':
        return [] if layout == 'osct' else [1]
    if style in ('Toggle', 'Momentary'):
        return [int(bool(vals[0]))]
    if style == 'Int':
        return [int(v) for v in vals]
    if style in ('Str', 'StrMenu', 'Menu'):
        return [str(vals[0])]
    out = [float(v) for v in vals]
    if layout == 'osct' and style == 'RGB':
        out.append(1.0)
    return out


def decode(style, args, n=1, menu=()):
    """OSC args -> par values (raises ValueError on anything that does not fit)."""
    args = list(args or [])
    if style == 'Pulse':
        return []
    if len(args) < n:
        raise ValueError('{} wants {} arg(s), got {}'.format(style, n, len(args)))
    if style in ('Toggle', 'Momentary'):
        v = args[0]
        if isinstance(v, str):
            if v.lower() not in ('true', 'false', '1', '0', 'on', 'off'):
                raise ValueError('not a bool: {!r}'.format(v))
            return [v.lower() in ('true', '1', 'on')]
        return [bool(float(v))]
    if style == 'Int':
        return [int(round(float(v))) for v in args[:n]]
    if style == 'Menu':
        v = args[0]
        if isinstance(v, str) and v in menu:
            return [v]
        if not isinstance(v, str) and float(v) == int(float(v)) and 0 <= int(float(v)) < len(menu):
            return [menu[int(float(v))]]
        raise ValueError('not a menu entry: {!r}'.format(v))
    if style in ('Str', 'StrMenu'):
        return [str(args[0])]
    return [float(v) for v in args[:n]]


def query_tree(rows, values, host_name, writable):
    """OSCQuery namespace JSON (FULL_PATH / CONTENTS / TYPE / VALUE / RANGE / ACCESS / DESCRIPTION)."""
    root = {'FULL_PATH': '/', 'CONTENTS': {}}
    for r in rows:
        parts = [p for p in r[0].split('/') if p]
        node = root
        for k, p in enumerate(parts[:-1]):
            node = node['CONTENTS'].setdefault(p, {'FULL_PATH': '/' + '/'.join(parts[:k + 1]), 'CONTENTS': {}})
        leaf = {'FULL_PATH': r[0], 'TYPE': r[5], 'ACCESS': 3 if writable else 1, 'DESCRIPTION': r[9]}
        v = values.get(r[2])
        if v is not None and r[4] != 'Pulse':
            leaf['VALUE'] = v
        if r[8]:
            leaf['RANGE'] = [{'VALS': r[8].split()}]
        elif r[6] != '' and r[7] != '':
            leaf['RANGE'] = [{'MIN': r[6], 'MAX': r[7]} for _ in r[3].split()]
        node.setdefault('CONTENTS', {})[parts[-1]] = leaf
    return root


def host_info(name, in_port, receive):
    d = {'NAME': name, 'OSC_TRANSPORT': 'UDP', 'EXTENSIONS': {'ACCESS': True, 'VALUE': True, 'RANGE': True,
                                                             'DESCRIPTION': True, 'TYPE': True}}
    if receive:
        d['OSC_PORT'] = int(in_port)
        d['OSC_IP'] = '127.0.0.1'
    return d


def is_loopback(addr):
    a = str(addr or '').split('%')[0]
    return a.startswith('127.') or a in ('::1', 'localhost') or a.startswith('::ffff:127.')


# ---------------------------------------------------------------- TD side (called from the DAT callbacks)
def target(c):
    t = c.par.Target.eval()
    if isinstance(t, str):  # a path (an OP par holding text)
        t = op(t) if t else None
    return t


def groups_of(t):
    out, by = [], {}
    for p in t.customPars:
        g = p.tupletName or p.name
        if g not in by:
            by[g] = {'par': g, 'members': [], 'style': p.style, 'page': p.page.name, 'label': p.label}
            if p.isNumber:
                by[g]['min'], by[g]['max'] = p.normMin, p.normMax
            if p.style == 'Menu':
                by[g]['menu'] = [str(x) for x in p.menuNames]
            out.append(by[g])
        by[g]['members'].append(p.name)
    return out


def build_map(c):
    t = target(c)
    if t is None:
        raise ValueError('Target is empty')
    prefix = c.par.Prefix.eval() or t.name
    pats = c.par.Pars.eval().split() or None
    pages = c.par.Pages.eval().split() or None
    rows, skipped = plan(groups_of(t), prefix, c.par.Layout.eval(), pats, pages)
    m = c.op('map')
    m.clear()
    m.appendRow(MAP_HEADER)
    for r in rows:
        m.appendRow(r)
    write_query(c)
    c.store('jz_osc_dirty', [])
    return {'addresses': len(rows), 'skipped': skipped}


def rows(c):
    m = c.op('map')
    return [[str(x.val) for x in m.row(i)] for i in range(1, m.numRows)]


def values(c, t, rs):
    out = {}
    for r in rs:
        vs = [t.par[n].eval() for n in r[3].split() if t.par[n] is not None]
        out[r[2]] = vs if len(vs) > 1 else (vs[0] if vs else None)
    return out


def write_query(c):
    t = target(c)
    rs = rows(c)
    tree = query_tree(rs, values(c, t, rs) if t is not None else {}, c.name, bool(c.par.Receive.eval()))
    c.op('oscquery').text = json.dumps(tree, indent=1)


def send_row(c, t, r):
    vals = [t.par[n].eval() for n in r[3].split() if t.par[n] is not None]
    c.op('osc_out').sendOSC(r[0], encode(r[4], vals, c.par.Layout.eval()))


def mark(c, name):
    if not c.par.Active.eval():
        return
    mute = c.fetch('jz_osc_mute', {}, search=False) or {}
    if name in mute:
        mute[name] -= 1
        if mute[name] <= 0:
            mute.pop(name)
        c.store('jz_osc_mute', mute)
        return
    d = c.fetch('jz_osc_dirty', [], search=False)
    if name not in d:
        d.append(name)
        c.store('jz_osc_dirty', d)


def on_value(c, par):
    mark(c, par.tupletName or par.name)


def on_pulse(c, par):
    if not c.par.Active.eval():
        return
    t = target(c)
    for r in rows(c):
        if r[2] == par.name:
            send_row(c, t, r)


def tick(c):
    if not c.par.Active.eval():
        return
    now = time.time()
    if now - c.fetch('jz_osc_last', 0.0, search=False) < 1.0 / max(0.1, float(c.par.Rate.eval())):
        return
    d = c.fetch('jz_osc_dirty', [], search=False)
    if not d:
        return
    c.store('jz_osc_dirty', [])
    c.store('jz_osc_last', now)
    t = target(c)
    for r in rows(c):
        if r[2] in d and r[4] != 'Pulse':
            send_row(c, t, r)


def send_all(c):
    t = target(c)
    for r in rows(c):
        if r[4] != 'Pulse':
            send_row(c, t, r)
    return len(rows(c))


def on_receive(c, address, args, peer=None):
    """Allow-list write: address must be a map row's in_address."""
    st = c.fetch('jz_osc_stats', {}, search=False) or {}
    st['received'] = st.get('received', 0) + 1
    hit = None
    for r in rows(c):
        if r[1] == address:
            hit = r
            break
    t = target(c)
    if hit is None or t is None:
        st['ignored'] = st.get('ignored', 0) + 1
        st['last_ignored'] = str(address)[:120]
        c.store('jz_osc_stats', st)
        return False
    members = hit[3].split()
    try:
        vals = decode(hit[4], args, 1 if hit[4] in ('Toggle', 'Momentary', 'Menu', 'Str', 'StrMenu')
                      else len(members), hit[8].split())
    except Exception as e:
        st['bad'] = st.get('bad', 0) + 1
        st['last_bad'] = '{} {}'.format(address, e)[:160]
        c.store('jz_osc_stats', st)
        return False
    if hit[4] == 'Pulse':
        t.par[members[0]].pulse()
    else:
        mute = c.fetch('jz_osc_mute', {}, search=False) or {}
        mute[hit[2]] = len(members)  # one value-change callback per member: none of them echoes back
        c.store('jz_osc_mute', mute)
        for n, v in zip(members, vals):
            if t.par[n] is not None:
                t.par[n].val = v
    st['written'] = st.get('written', 0) + 1
    st['last'] = str(address)[:120]
    c.store('jz_osc_stats', st)
    return True


def on_http(c, request, response):
    client = request.get('clientAddress', '')
    if c.par.Loopbackonly.eval() and not is_loopback(client):
        response['statusCode'] = 403
        response['statusReason'] = 'Forbidden'
        response['data'] = 'loopback only'
        return response
    uri = str(request.get('uri', '/'))
    q = request.get('pars', {}) or {}
    if 'HOST_INFO' in q or 'HOST_INFO' in uri:
        body = host_info(c.name, c.par.Inport.eval(), c.par.Receive.eval())
    else:
        write_query(c)
        body = json.loads(c.op('oscquery').text)
    response['statusCode'] = 200
    response['statusReason'] = 'OK'
    response['content-type'] = 'application/json'
    response['data'] = json.dumps(body)
    return response
'''
OSCX_WATCH = '''# osc_expose: Target's custom pars changed -> marked; tick sends them (rate-limited, change-only).
def onValueChange(par, prev):
    parent().op('runtime').module.on_value(parent(), par)

def onPulse(par):
    parent().op('runtime').module.on_pulse(parent(), par)
'''
OSCX_TICK = '''# osc_expose: send the marked pars at most Rate times a second.
def onFrameStart(frame):
    parent().op('runtime').module.tick(parent())
'''
OSCX_IN_CB = '''# osc_expose: incoming OSC -> runtime.on_receive (allow-list of the map table; no eval).
def onReceiveOSC(dat, rowIndex, message, bytes, timeStamp, address, args, peer):
    parent().op('runtime').module.on_receive(parent(), address, args, peer)
'''
OSCX_HTTP_CB = '''# osc_expose: OSCQuery over HTTP (Web Server DAT). Loopbackonly refuses other clients (403).
def onHTTPRequest(webServerDAT, request, response):
    return parent().op('runtime').module.on_http(parent(), request, response)
'''
OSCX_EXEC_MORE = ("    elif par.name == 'Sendall':\n        c.op('runtime').module.send_all(c)\n"
                  "    elif par.name == 'Rebuildmap':\n        c.op('runtime').module.build_map(c)\n")


def cmd_osc_expose(comp, name=None, parent=None, host='127.0.0.1', port=None, active=False, receive=False,
                   in_host='127.0.0.1', in_port=None, rate_hz=30, layout='plain', prefix=None, pages=None, pars=None,
                   oscquery=False, oscquery_port=None, loopback_only=True):
    """Publish a COMP's custom pars as an OSC address tree (/<prefix>/<Par>, or OSCToolset /OSCT/R/<TYPE>/<name>)
    from a self-contained sibling COMP: map table + runtime + OSC Out (send) + OSC In (receive, allow-list) + optional
    OSCQuery (Web Server DAT, loopback clients only by default). Sender, listener and server stay off unless asked."""
    t = _op(comp, 'comp')
    if not _try(lambda: t.isCOMP, False):
        raise ValueError('{} is not a COMP'.format(t.path))
    if _protected(t.path):
        raise ValueError('{} is the MCP COMP or holds it'.format(t.path))
    if layout not in OSCX_LAYOUTS:
        raise ValueError('layout must be one of {}'.format(list(OSCX_LAYOUTS)))
    port = int(port or (9999 if layout == 'osct' else 9000))
    in_port = int(in_port or (9998 if layout == 'osct' else 9001))
    qport = int(oscquery_port or (in_port + 1))
    for nm, v in (('port', port), ('in_port', in_port), ('oscquery_port', qport)):
        if not 1 <= v <= 65535:
            raise ValueError('{} must be 1..65535'.format(nm))
    if not 0.1 <= float(rate_hz) <= 240:
        raise ValueError('rate_hz must be 0.1..240')
    c, created = _kit_comp(parent or t.parent().path, name, OSCX_KIND, t.name + '_osc')
    par_ = c.parent()
    made, notes = [], []
    _kit_pars(c, 'OSC', [
        ('Target', 'COMP', None, {'label': 'Target COMP'}),
        ('Active', 'Toggle', False, {'label': 'Send'}),
        ('Host', 'Str', '127.0.0.1', {'label': 'Send to host'}),
        ('Port', 'Int', port, {'label': 'Send port', 'min': 1, 'max': 65535}),
        ('Rate', 'Float', 30.0, {'label': 'Max sends / s', 'min': 1.0, 'max': 120.0}),
        ('Receive', 'Toggle', False, {'label': 'Receive (opens a UDP port)'}),
        ('Inhost', 'Str', '127.0.0.1', {'label': 'Receive on address'}),
        ('Inport', 'Int', in_port, {'label': 'Receive port', 'min': 1, 'max': 65535}),
        ('Layout', 'Menu', 'plain', {'label': 'Address layout', 'names': list(OSCX_LAYOUTS),
                                     'labels': ['/<prefix>/<Par>', 'OSCToolset /OSCT/R/<TYPE>/<name>']}),
        ('Prefix', 'Str', '', {'label': 'Prefix (empty = target name)'}),
        ('Pages', 'Str', '', {'label': 'Pages (empty = all)'}),
        ('Pars', 'Str', '', {'label': 'Par globs (empty = all)'}),
        ('Sendall', 'Pulse', None, {'label': 'Send all now'}),
        ('Rebuildmap', 'Pulse', None, {'label': 'Rebuild map'})])
    _kit_pars(c, 'OSCQuery', [
        ('Oscquery', 'Toggle', False, {'label': 'OSCQuery server (opens a TCP port)'}),
        ('Oscqueryport', 'Int', qport, {'label': 'OSCQuery port', 'min': 1, 'max': 65535}),
        ('Loopbackonly', 'Toggle', True, {'label': 'Answer loopback clients only'})])
    _kit_pars(c, 'Controls', [('Opencontrols', 'Pulse', None, {'label': 'Open controls'})])
    c.par.Target.val = t.path
    sets = {'Active': bool(active), 'Host': str(host), 'Port': port, 'Rate': float(rate_hz), 'Receive': bool(receive),
            'Inhost': str(in_host), 'Inport': in_port, 'Layout': layout, 'Prefix': str(prefix or ''),
            'Pages': ' '.join(pages or []), 'Pars': ' '.join(pars or []), 'Oscquery': bool(oscquery),
            'Oscqueryport': qport, 'Loopbackonly': bool(loopback_only)}
    for k, v in sets.items():
        c.par[k].val = v
    rt = _kit_child(c, 'textDAT', 'runtime', made, notes)
    rt.text = OSCX_RT
    m = _kit_child(c, 'tableDAT', 'map', made, notes)
    q = _kit_child(c, 'textDAT', 'oscquery', made, notes)
    w = _kit_child(c, 'parameterexecuteDAT', 'watch', made, notes)
    if w is not None:
        w.text = OSCX_WATCH
        for k, v in (('op', {'expr': 'parent().par.Target.eval()'}), ('pars', '*'), ('custom', True),
                     ('builtin', False), ('valuechange', True), ('onpulse', True)):
            _midi_set(w, k, v, notes)
    tk = _kit_child(c, 'executeDAT', 'tick', made, notes)
    if tk is not None:
        tk.text = OSCX_TICK
        _midi_set(tk, 'framestart', True, notes)
    oo = _kit_child(c, 'oscoutDAT', 'osc_out', made, notes)
    if oo is not None:
        for k, v in (('active', {'expr': 'parent().par.Active'}), ('address', {'expr': 'parent().par.Host'}),
                     ('port', {'expr': 'parent().par.Port'})):
            _midi_set(oo, k, v, notes)
    oi = _kit_child(c, 'oscinDAT', 'osc_in', made, notes)
    icb = _kit_child(c, 'textDAT', 'osc_in_cb', made, notes)
    if icb is not None:
        icb.text = OSCX_IN_CB
    if oi is not None:
        for k, v in (('active', {'expr': 'parent().par.Receive'}), ('port', {'expr': 'parent().par.Inport'}),
                     ('localaddress', {'expr': 'parent().par.Inhost'}), ('callbacks', 'osc_in_cb'),
                     ('clamp', True), ('maxlines', 50)):
            _midi_set(oi, k, v, notes)
        if icb is not None:
            _try(lambda: setattr(icb, 'dock', oi))
    ws = _kit_child(c, 'webserverDAT', 'oscquery_server', made, notes)
    hcb = _kit_child(c, 'textDAT', 'oscquery_cb', made, notes)
    if hcb is not None:
        hcb.text = OSCX_HTTP_CB
    if ws is not None:
        for k, v in (('active', {'expr': 'parent().par.Oscquery'}), ('port', {'expr': 'parent().par.Oscqueryport'}),
                     ('callbacks', 'oscquery_cb')):
            _midi_set(ws, k, v, notes)
        if hcb is not None:
            _try(lambda: setattr(hcb, 'dock', ws))
    ctl = _kit_controls(c, 'OSC expose', made, notes, 420, 620, 'OSC OSCQuery', more=OSCX_EXEC_MORE,
                        pulses=('Opencontrols', 'Sendall', 'Rebuildmap'))
    c.comment = 'td_osc_expose: custom pars of {} as OSC ({}); map = allow-list for incoming writes'.format(t.path,
                                                                                                           layout)
    try:
        built = rt.module.build_map(c)
    except Exception as e:
        notes.append('map not built ({}: {}): pulse Rebuildmap after fixing'.format(type(e).__name__, str(e)[:200]))
        built = {'addresses': 0, 'skipped': []}
    rows_ = [[str(x.val) for x in m.row(i)] for i in range(1, m.numRows)] if m is not None else []
    _about = about_values(_try(lambda: c.par.Version.eval(), None), None, None,
                          td_build_string(_try(lambda: app.version, ''), _try(lambda: app.build, '')))  # noqa: F405
    _stamp_about(c, _about)
    stages = [_stage(c, 'Map', 'input', ['map', 'runtime', 'oscquery'],
                     'map = one row per exposed par group (the allow-list); runtime = encode/decode/send'),
              _stage(c, 'Send', 'output', ['watch', 'tick', 'osc_out'],
                     'Target par changes -> marked -> sent at most Rate/s (Active)'),
              _stage(c, 'Receive', 'input', ['osc_in'], 'OSC In (Receive, Inhost:Inport) -> map lookup -> par.val'),
              _stage(c, 'OSCQuery', 'output', ['oscquery_server'], 'Web Server DAT (Oscquery); loopback clients only'),
              _stage(c, 'Controls', 'control', ctl, 'Opencontrols opens the panel')]
    r = {'path': c.path, 'target': t.path, 'created': created, 'layout': layout, 'count': built['addresses'],
         'addresses': [{'par': x[2], 'send': x[0], 'receive': x[1], 'type': x[5]} for x in rows_[:40]],
         'skipped': built['skipped'][:20], 'new_ops': made,
         'send': {'host': str(host), 'port': port, 'active': bool(active), 'rate_hz': float(rate_hz)},
         'receive': {'on': bool(receive), 'host': str(in_host), 'port': in_port, 'allow_list': 'map table only'},
         'oscquery': {'on': bool(oscquery), 'port': qport, 'loopback_only': bool(loopback_only),
                      'json_dat': q.path if q is not None else None}}
    r.update(_kit_finish(c, stages, created, par_, notes))
    if notes:
        r['notes'] = notes
    r['hint'] = 'Active sends, Receive listens, Oscquery serves JSON: each opens traffic, the user\'s go-ahead.'
    return r


# ------------------------------------------------------------------ layer mixer + cook_active (research AU)
MIX_KIND = 'layer_mixer'
MIX_BLENDS = ('over', 'add', 'screen', 'multiply', 'subtract', 'difference', 'maximum', 'minimum', 'overlay',
              'softlight', 'hardlight', 'under', 'inside', 'outside', 'atop', 'average')
MIX_FITS = ('fill', 'fithorz', 'fitvert', 'fitbest', 'fitoutside', 'nativeres')
MIX_MAX_LAYERS = 16
MIX_MAX_SOURCES = 64
MIX_RT = '''# jazib-td layer mixer runtime (td_layer_mixer): cook guard. COMP sources nothing visible shows get
# allowCooking off (research AU: one live source per layer); Cookguard off turns every source back on.


def eff(c, n):
    p = c.par
    solo = any(p['L{}solo'.format(i)].eval() for i in range(1, int(c.fetch('jz_layers', 0, search=False)) + 1))
    if p['L{}mute'.format(n)].eval() or (solo and not p['L{}solo'.format(n)].eval()):
        return 0.0
    return float(p['L{}opacity'.format(n)].eval())


def active_sources(c):
    n = int(c.fetch('jz_layers', 0, search=False))
    return sorted(set(c.par['L{}source'.format(i)].menuIndex for i in range(1, n + 1) if eff(c, i) > 0))


def apply(c):
    t = c.op('sources')
    act = set(active_sources(c))
    guard = bool(c.par.Cookguard.eval())
    out = {'on': [], 'off': []}
    for r in range(1, t.numRows):
        k, path, is_comp = int(t[r, 'index'].val), t[r, 'path'].val, t[r, 'comp'].val == '1'
        if not is_comp:
            continue
        o = op(path)
        if o is None:
            continue
        on = (k in act) or not guard
        if o.allowCooking != on:
            o.allowCooking = on
        out['on' if on else 'off'].append(path)
    return out
'''
MIX_GUARD = '''# layer mixer: any custom par change -> cook guard (runtime.apply).
def onValueChange(par, prev):
    parent().op('runtime').module.apply(parent())
'''


def mixer_eff_expr(n, layers):
    """Pure: effective opacity of layer n as a TD expression (mute, solo across all layers)."""
    solo_any = ' or '.join('parent().par.L{}solo'.format(i) for i in range(1, layers + 1))
    return ('parent().par.L{n}opacity * (0 if parent().par.L{n}mute else 1) * '
            '(1 if (parent().par.L{n}solo or not ({s})) else 0)').format(n=n, s=solo_any)


def mixer_source_rows(items):
    """Pure: [(path, optype, out_top_path or None)] -> sources table rows (index, label, path, top, comp)."""
    rows = [['index', 'label', 'path', 'top', 'comp']]
    for k, (path, optype, top) in enumerate(items):
        is_comp = str(optype).endswith('COMP')
        rows.append([k, path.rstrip('/').rsplit('/', 1)[-1], path, top or '', '1' if is_comp else '0'])
    return rows


def _source_top(o):
    """A TOP source is itself; a COMP source = its first Out TOP (by connector order), else out1/out/null_out."""
    if _family(o) == 'TOP':
        return o.path
    if not _try(lambda: o.isCOMP, False):
        return None
    outs = [ch for ch in _try(lambda: list(o.children), []) if _try(lambda: ch.OPType, '') == 'outTOP']
    if outs:
        return sorted(outs, key=lambda x: (_try(lambda: x.par.connectorder.eval(), 0), x.name))[0].path
    for nm in ('out1', 'out', 'null_out'):
        k = o.op(nm)
        if k is not None and _family(k) == 'TOP':
            return k.path
    return None


def cmd_layer_mixer(parent='/project1', name='mixer', layers=4, sources=None, blend='over', res=None, fit='fill',
                    cook_guard=True):
    """N-layer mixer COMP: per layer Source (menu over a shared source bank), Opacity, Blend (Composite operand),
    Mute, Solo; Master opacity, a master FX slot (fx_slot COMP, bypass with Masterfx), Out TOP only. Layer n =
    mix(below, composite(source, below), effective opacity), skipped (Switch) at 0. COMP sources nothing shows get
    allowCooking off (Cookguard). Called again: updates in place (more/fewer layers, new sources)."""
    layers = int(layers)
    if not 1 <= layers <= MIX_MAX_LAYERS:
        raise ValueError('layers must be 1..{}'.format(MIX_MAX_LAYERS))
    if blend not in MIX_BLENDS:
        raise ValueError('blend must be one of {}'.format(list(MIX_BLENDS)))
    if fit not in MIX_FITS:
        raise ValueError('fit must be one of {}'.format(list(MIX_FITS)))
    if res is not None and (not isinstance(res, (list, tuple)) or len(res) != 2):
        raise ValueError('res must be [w, h]')
    if sources is not None and (not isinstance(sources, list) or len(sources) > MIX_MAX_SOURCES):
        raise ValueError('sources must be a list of up to {} TOP/COMP paths'.format(MIX_MAX_SOURCES))
    items = None
    if sources is not None:
        items, bad = [], []
        for p in sources:
            o = op(p) if isinstance(p, str) and p.startswith('/') else None  # noqa: F405
            top = _source_top(o) if o is not None else None
            if top is None:
                bad.append(p)
            else:
                items.append((o.path, _try(lambda: o.OPType, ''), top))
        if bad:
            raise ValueError('sources not found or without a TOP output (COMP: an Out TOP): {}'.format(bad))
    c, created = _kit_comp(parent, name, MIX_KIND, 'mixer')
    par_ = c.parent()
    made, notes = [], []
    tab = _kit_child(c, 'tableDAT', 'sources', made, notes)
    if items is not None:
        tab.text = tsv(mixer_source_rows(items))
    elif _try(lambda: tab.numRows, 0) == 0:
        tab.text = tsv(mixer_source_rows([]))
    srows = [[str(x.val) for x in tab.row(i)] for i in range(1, tab.numRows)]
    k_src = len(srows)
    old_layers = int(_try(lambda: c.fetch('jz_layers', 0, search=False), 0) or 0)
    w, h = (int(res[0]), int(res[1])) if res else DEFAULT_RES
    _kit_pars(c, 'Mixer', [
        ('Master', 'Float', 1.0, {'label': 'Master opacity', 'min': 0.0, 'max': 1.0}),
        ('Masterfx', 'Toggle', False, {'label': 'Master FX on (fx_slot)'}),
        ('Resw', 'Int', w, {'label': 'Width', 'min': 16, 'max': 8192}),
        ('Resh', 'Int', h, {'label': 'Height', 'min': 16, 'max': 8192}),
        ('Fit', 'Menu', fit, {'label': 'Fit sources', 'names': list(MIX_FITS)}),
        ('Cookguard', 'Toggle', bool(cook_guard), {'label': 'Unshown COMP sources stop cooking'})])
    if res:
        c.par.Resw.val, c.par.Resh.val = w, h
    names = ['src{}'.format(k) for k in range(k_src)] or ['none']
    labels = ['{}: {}'.format(k, r[1]) for k, r in enumerate(srows)] or ['(no sources)']
    for n in range(1, layers + 1):
        _kit_pars(c, 'Layer{}'.format(n), [
            ('L{}source'.format(n), 'Menu', names[min(n - 1, len(names) - 1)],
             {'label': 'Source', 'names': names, 'labels': labels}),
            ('L{}opacity'.format(n), 'Float', 1.0 if n == 1 else 0.0, {'label': 'Opacity', 'min': 0.0, 'max': 1.0}),
            ('L{}blend'.format(n), 'Menu', blend, {'label': 'Blend', 'names': list(MIX_BLENDS)}),
            ('L{}mute'.format(n), 'Toggle', False, {'label': 'Mute'}),
            ('L{}solo'.format(n), 'Toggle', False, {'label': 'Solo'})])
    _kit_pars(c, 'Controls', [('Opencontrols', 'Pulse', None, {'label': 'Open controls'})])
    removed = []
    for n in range(layers + 1, max(old_layers, layers) + 1):  # fewer layers than before: their ops and page go
        for suf in ('switch', 'comp', 'mix', 'gate'):
            o = c.op('l{}_{}'.format(n, suf))
            if o is not None:
                removed.append(o.name)  # before the destroy: o.name on a destroyed op raises (QC 26 Oct)
                safe_destroy(o)
        pg = next((cp for cp in _try(lambda: list(c.customPages), []) if cp.name == 'Layer{}'.format(n)), None)
        if pg is not None:
            _try(pg.destroy)
    c.store('jz_layers', layers)
    sel = []
    for k, r in enumerate(srows):
        s = _kit_child(c, 'selectTOP', 'src{}'.format(k), made, notes)
        _midi_set(s, 'top', r[3], notes)
        sel.append(s)
    k = k_src
    while c.op('src{}'.format(k)) is not None:
        safe_destroy(c.op('src{}'.format(k)))
        k += 1
    black = _kit_child(c, 'constantTOP', 'black', made, notes)
    for kk, v in (('colorr', 0), ('colorg', 0), ('colorb', 0), ('alpha', 0), ('outputresolution', {'menu': 'custom'}),
                  ('resolutionw', {'expr': 'parent().par.Resw'}), ('resolutionh', {'expr': 'parent().par.Resh'})):
        _midi_set(black, kk, v, notes)
    below = black
    layer_ops = []
    for n in range(1, layers + 1):
        sw = _kit_child(c, 'switchTOP', 'l{}_switch'.format(n), made, notes)
        cp = _kit_child(c, 'compositeTOP', 'l{}_comp'.format(n), made, notes)
        mx = _kit_child(c, 'crossTOP', 'l{}_mix'.format(n), made, notes)
        gt = _kit_child(c, 'switchTOP', 'l{}_gate'.format(n), made, notes)
        for o in (sw, cp, mx, gt):
            for i in range(len(_try(lambda: list(o.inputConnectors), []) or []) - 1, -1, -1):
                _try(lambda: o.inputConnectors[i].disconnect())
        _kit_wire(sel or [black], sw, notes)
        _midi_set(sw, 'index', {'expr': 'parent().par.L{}source.menuIndex'.format(n)}, notes)
        _kit_wire([sw, below], cp, notes)
        for kk, v in (('operand', {'expr': 'parent().par.L{}blend.eval()'.format(n)}),
                      ('outputresolution', {'menu': 'custom'}), ('resolutionw', {'expr': 'parent().par.Resw'}),
                      ('resolutionh', {'expr': 'parent().par.Resh'}), ('prefit', {'expr': 'parent().par.Fit.eval()'})):
            _midi_set(cp, kk, v, notes)
        e = mixer_eff_expr(n, layers)
        _kit_wire([below, cp], mx, notes)
        _midi_set(mx, 'cross', {'expr': e}, notes)
        _kit_wire([below, mx], gt, notes)
        _midi_set(gt, 'index', {'expr': '1 if ({}) > 0 else 0'.format(e)}, notes)
        layer_ops += ['l{}_switch'.format(n), 'l{}_comp'.format(n), 'l{}_mix'.format(n), 'l{}_gate'.format(n)]
        below = gt
    fx = _kit_child(c, 'baseCOMP', 'fx_slot', made, notes)
    if fx is not None and fx.op('in1') is None:
        fi = fx.create(inTOP, 'in1')  # noqa: F405
        fo = fx.create(outTOP, 'out1')  # noqa: F405
        _kit_wire([fi], fo, notes)
        fx.comment = 'Master FX slot: put an effect between in1 and out1 (or load a .tox in here); Masterfx turns it on'
        _arrange(fx)
    _try(lambda: fx.inputConnectors[0].disconnect())
    _kit_wire([below], fx, notes)
    byp = _kit_child(c, 'switchTOP', 'fx_bypass', made, notes)
    for i in range(len(_try(lambda: list(byp.inputConnectors), []) or []) - 1, -1, -1):
        _try(lambda: byp.inputConnectors[i].disconnect())
    _kit_wire([below, fx], byp, notes)
    _midi_set(byp, 'index', {'expr': '1 if parent().par.Masterfx else 0'}, notes)
    master = _kit_child(c, 'crossTOP', 'master', made, notes)
    for i in range(len(_try(lambda: list(master.inputConnectors), []) or []) - 1, -1, -1):
        _try(lambda: master.inputConnectors[i].disconnect())
    _kit_wire([black, byp], master, notes)
    _midi_set(master, 'cross', {'expr': 'parent().par.Master'}, notes)
    out = _kit_child(c, 'outTOP', 'out1', made, notes)
    _try(lambda: out.inputConnectors[0].disconnect())
    _kit_wire([master], out, notes)
    rt = _kit_child(c, 'textDAT', 'runtime', made, notes)
    rt.text = MIX_RT
    gd = _kit_child(c, 'parameterexecuteDAT', 'guard_exec', made, notes)
    if gd is not None:
        gd.text = MIX_GUARD
        for kk, v in (('op', '..'), ('pars', '*'), ('custom', True), ('builtin', False), ('valuechange', True),
                      ('onpulse', False)):
            _midi_set(gd, kk, v, notes)
    ctl = _kit_controls(c, 'Mixer', made, notes, 440, 680)
    c.store(KIT_KEY, {'kind': MIX_KIND})
    c.comment = 'td_layer_mixer: {} layers over {} sources; Out TOP out1 = the mix only'.format(layers, k_src)
    guard = _try(lambda: rt.module.apply(c), None)
    if guard is None and k_src:
        notes.append('cook guard did not run: td_errors {}/runtime'.format(c.path))
    _about = about_values(_try(lambda: c.par.Version.eval(), None), None, None,
                          td_build_string(_try(lambda: app.version, ''), _try(lambda: app.build, '')))  # noqa: F405
    _stamp_about(c, _about)
    stages = [_stage(c, 'Sources', 'input', ['sources'] + ['src{}'.format(k) for k in range(k_src)] + ['black'],
                     'Shared source bank (sources table); each layer picks one with its Source menu'),
              _stage(c, 'Layers', 'process', layer_ops,
                     'Per layer: switch (source) -> composite (Blend) -> cross (Opacity x mute/solo) -> gate (skip at 0)'),
              _stage(c, 'Master', 'process', ['fx_slot', 'fx_bypass', 'master'], 'Master FX slot (Masterfx) and opacity'),
              _stage(c, 'Output', 'output', ['out1'], 'Out TOP: the mix only'),
              _stage(c, 'Engine', 'note', ['runtime', 'guard_exec'], 'Cook guard: unshown COMP sources stop cooking'),
              _stage(c, 'Controls', 'control', ctl, 'Opencontrols opens the panel')]
    r = {'path': c.path, 'created': created, 'layers': layers, 'sources': [{'index': int(x[0]), 'path': x[2], 'top': x[3],
                                                                           'comp': x[4] == '1'} for x in srows],
         'out': out.path if out is not None else None, 'new_ops': made, 'removed': removed,
         'cook_guard': guard, 'blend_order': 'Composite TOP inputs: 0 = layer source, 1 = layers below'}
    r.update(_kit_finish(c, stages, created, par_, notes))
    if notes:
        r['notes'] = notes
    r['hint'] = 'L<n>source/opacity/blend/mute/solo per layer; Opencontrols opens the panel; put master FX in fx_slot'
    return r


def cook_split(candidates, active):
    """Pure: [(name, path)] + active names/paths -> (on paths, off paths, unknown active entries)."""
    act = set(str(a) for a in (active or []))
    on = [p for n, p in candidates if n in act or p in act]
    off = [p for n, p in candidates if not (n in act or p in act)]
    known = set(n for n, _p in candidates) | set(p for _n, p in candidates)
    return on, off, sorted(act - known)


def _cook_guard_skip(path):
    """cook_active never switches these: the MCP COMP, its ancestors, '/' and the top-level COMPs."""
    p = path.rstrip('/') or '/'
    return _protected(p) or p.count('/') <= 1


def cmd_cook_active(active=None, paths=None, parent=None, pattern='*'):
    """allowCooking on for the active COMPs and off for the other candidates (research AU: one live source). Candidates
    = paths (COMPs) or the child COMPs of parent matching pattern. Never touches the MCP COMP or its ancestors."""
    if (paths is None) == (parent is None):
        raise ValueError('give paths (COMPs) or parent (its child COMPs), one of them')
    cands = []
    if paths is not None:
        for p in paths:
            o = _op(p)
            if not _try(lambda: o.isCOMP, False):
                raise ValueError('{} is not a COMP (allowCooking is a COMP switch)'.format(o.path))
            cands.append(o)
    else:
        par_ = _op(parent, 'parent')
        cands = [ch for ch in _try(lambda: list(par_.children), []) if _try(lambda: ch.isCOMP, False)
                 and fnmatch.fnmatchcase(ch.name, pattern or '*')
                 and _try(lambda: ch.OPType, '') not in ('annotateCOMP', 'windowCOMP')]
    # top-level COMPs (/project1, /local, /perform...) are skipped too: switching one off stops the whole project
    # and every other lane's work (QC 26 Oct: paths ['/project1'] active [] turned /project1 off)
    skipped = [o.path for o in cands if _cook_guard_skip(o.path)]
    cands = [o for o in cands if not _cook_guard_skip(o.path)]
    on, off, unknown = cook_split([(o.name, o.path) for o in cands], active)
    if unknown:
        raise ValueError('active names not among the candidates: {}'.format(unknown))
    for o in cands:
        want = o.path in on
        if bool(_try(lambda: o.allowCooking, True)) != want:
            o.allowCooking = want
    r = {'on': on, 'off': off}
    if skipped:
        r['skipped'] = skipped
    return r


COMMANDS = {
    'status': cmd_status,
    'list': cmd_list,
    'info': cmd_info,
    'get_pars': cmd_get_pars,
    'set_pars': cmd_set_pars,
    'create': cmd_create,
    'delete': cmd_delete,
    'rename': cmd_rename,
    'move': cmd_move,
    'connect': cmd_connect,
    'disconnect': cmd_disconnect,
    'dat_text': cmd_dat_text,
    'errors': cmd_errors,
    'screenshot': cmd_screenshot,
    'custom_pars': cmd_custom_pars,
    'tox_save': cmd_tox_save,
    'tox_load': cmd_tox_load,
    'save_project': cmd_save_project,
    'perf': cmd_perf,
    'exec': cmd_exec,
    'reload': cmd_reload,
    'layout': cmd_layout,
    'housekeeping': cmd_housekeeping,
    'focus': cmd_focus,
    'selection': cmd_selection,
    'inspect': cmd_inspect,
    'net_export': cmd_net_export,
    'comfy_build': cmd_comfy_build,
    'comfy_status': cmd_comfy_status,
    'comfy_send': cmd_comfy_send,
    'comfy_result': cmd_comfy_result,
    'comfy_cancel': cmd_comfy_cancel,
    'comfy_free': cmd_comfy_free,
    'publish': cmd_publish,
    'publish_status': cmd_publish_status,
    'osc_learn': cmd_osc_learn,
    'link': cmd_link,
    'link_status': cmd_link_status,
    'live_audio': cmd_live_audio,
    'tda_check': cmd_tda_check,
    'tda_load': cmd_tda_load,
    'tda_status': cmd_tda_status,
    'import_ae_anim': cmd_import_ae_anim,
    'import_blender': cmd_import_blender,
    'export_ae_data': cmd_export_ae_data,
    'render_for_ae': cmd_render_for_ae,
    'midi_build': cmd_midi_build,
    'midi_status': cmd_midi_status,
    'midi_learn': cmd_midi_learn,
    'midi_map': cmd_midi_map,
    'midi_unmap': cmd_midi_unmap,
    'midi_list': cmd_midi_list,
    'midi_bank': cmd_midi_bank,
    'midi_save': cmd_midi_save,
    'midi_load': cmd_midi_load,
    'midi_monitor': cmd_midi_monitor,
    'midi_simulate': cmd_midi_simulate,
    'midi_preset': cmd_midi_preset,
    'health_sample': cmd_health_sample, 'health_probe': cmd_health_probe,
    'script_errors_recheck': cmd_script_errors_recheck, 'trace': cmd_trace, 'save_hook': cmd_save_hook,
    'record_chop': cmd_record_chop, 'shadertoy': cmd_shadertoy, 'osc_expose': cmd_osc_expose,
    'layer_mixer': cmd_layer_mixer, 'cook_active': cmd_cook_active,
}


# ================================================================== connection (called from callbacks.py)

def _remember(dat):
    c = _try(lambda: dat.parent())
    if c is not None:
        _CTX['comp_path'] = c.path


def _status(dat, text):
    st = _try(lambda: dat.parent().op('status'))
    if st is not None:
        _try(lambda: setattr(st, 'text', '{}  {}\n'.format(time.strftime('%Y-%m-%d %H:%M:%S'), text)))


def log(dat, level, msg):
    """Unsolicited log line to the bridge (bridge.log)."""
    if _CONN.get('connected'):
        _try(lambda: dat.sendText(dumps({'type': 'log', 'level': level, 'msg': str(msg)})))


def on_connect(dat):
    _remember(dat)
    now = time.monotonic()
    _CONN.update(connected=True, since=now, last_rx=now, phase='idle', attempts=0)
    try:
        tok = read_or_create_token()
    except Exception as e:
        _status(dat, 'connected, but no token: {}'.format(e))
        print('jazib_mcp: token error:', e)
        return
    dat.sendText(dumps(build_hello(tok, td_info())))
    _status(dat, 'connected to 127.0.0.1:{} (hello sent)'.format(bridge_port()))


def on_disconnect(dat):
    _remember(dat)
    _CONN.update(connected=False, since=time.monotonic())
    _PENDING.clear()  # their replies have nowhere to go
    _status(dat, 'disconnected (retrying every few seconds)')


def on_text(dat, message):
    _remember(dat)
    _CONN['last_rx'] = time.monotonic()
    if not _CONN.get('connected'):  # a frame proves the socket is open even if onConnect was missed
        _CONN['connected'] = True
    _try(lambda: mcp_beat('ws'))  # T-95: independent of frame callbacks
    dispatch(message, dat.sendText)


def on_binary(dat, contents):
    _CONN['last_rx'] = time.monotonic()  # protocol uses text frames only; ignore


def on_ping(dat, contents):
    _CONN['last_rx'] = time.monotonic()
    _try(lambda: dat.sendPong(contents))


def on_pong(dat, contents):
    _CONN['last_rx'] = time.monotonic()


def _ws(comp):
    return _try(lambda: comp.op('ws'))


# T-71 autosave (user, 26 Oct: "save ur proejcts always so u dont loose ur progress"): every AUTOSAVE['minutes'] the
# project is saved the way td_save_project saves in place (TD adds the next .N); only the newest AUTOSAVE['keep']
# autosaves are kept (older ones WE made go to output/backups/autosave/). Skipped while realTime is off (an offline
# render, T-64). minutes = 0 turns it off.
def _autosave_default():
    """5 min, or JTD_AUTOSAVE_MIN (the scratch TD sets 0: it never autosaves, T-83)."""
    try:
        return float(os.environ.get('JTD_AUTOSAVE_MIN', '5'))
    except ValueError:
        return 5.0


AUTOSAVE = {'minutes': _autosave_default(), 'keep': 5, 'last': None, 'made': [], 'error': None}


def autosave_due(now, last, minutes):
    """Pure: is an autosave due? (first call only arms the timer)."""
    if not minutes or minutes <= 0:
        return False
    return last is not None and now - last >= minutes * 60.0


def _autosave_check():
    now = time.monotonic()
    if AUTOSAVE['last'] is None:
        AUTOSAVE['last'] = now
        return None
    if not autosave_due(now, AUTOSAVE['last'], AUTOSAVE['minutes']):
        return None
    AUTOSAVE['last'] = now
    if _try(lambda: project.realTime, True) is False:  # noqa: F405
        return None
    try:
        r = cmd_save_project()
    except Exception as e:
        AUTOSAVE['error'] = str(e)[:200]
        return None
    AUTOSAVE['made'].append(r['file'])
    while len(AUTOSAVE['made']) > max(1, int(AUTOSAVE['keep'])):
        old = AUTOSAVE['made'].pop(0)
        if old != r['file'] and os.path.isfile(old):
            bdir = os.path.join(os.path.dirname(os.path.dirname(handlers_file())), 'output', 'backups', 'autosave')
            _try(lambda: os.makedirs(bdir, exist_ok=True))
            _try(lambda: os.replace(old, os.path.join(bdir, os.path.basename(old))))
    return r['file']


def cmd_autosave(minutes=None, keep=None, now=False):
    """Read or set the autosave (minutes 0 = off); now=true saves at once."""
    if minutes is not None:
        AUTOSAVE['minutes'] = float(minutes)
    if keep is not None:
        AUTOSAVE['keep'] = int(keep)
    saved = cmd_save_project()['file'] if now else None
    return {'minutes': AUTOSAVE['minutes'], 'keep': AUTOSAVE['keep'], 'saved': saved,
            'made': list(AUTOSAVE['made']), 'error': AUTOSAVE['error']}


COMMANDS['autosave'] = cmd_autosave  # defined after the table; read-only unless now=true (a save is not undoable)


# T-95 second heartbeat (26 Oct): the /watchdog_hb Execute DAT beats from onFrameEnd only, so it stops whenever TD's
# frame loop stops (T-78: absTime.frame froze at 23202 while execs kept answering). This one is written from the
# WebSocket callbacks (every message, incl. the bridge ping every 20 s) and from tick(), so it keeps going while TD
# still services the network. It carries absTime.frame + wall time: frame frozen + this file fresh = "frames
# stopped, TD alive" (watchdog warns, never kills). At most one write per MCP_BEAT_MIN_S.
MCP_BEAT_FILE = 'heartbeat_mcp.json'
MCP_BEAT_MIN_S = 1.0
_MCP_BEAT = {'last': 0.0, 'frame': None, 'frame_wall': None}


def mcp_beat_record(now, frame, src, pid, prev):
    """Pure: the heartbeat_mcp.json dict. prev = {'frame', 'frame_wall'} (updated in place): frame_wall is the wall
    time the frame number last CHANGED, so a reader sees how long the frame clock has been frozen."""
    if frame is None or frame != prev.get('frame'):
        prev['frame'] = frame
        prev['frame_wall'] = now
    return {'time': now, 'pid': pid, 'frame': frame, 'frame_changed_at': prev.get('frame_wall'), 'src': src}


def mcp_beat(src):
    if instance() != 'main':  # side TDs never beat (T-83, T-120): heartbeat_mcp.json is the main TD's
        return None
    now = time.time()
    if now - _MCP_BEAT['last'] < MCP_BEAT_MIN_S:
        return None
    _MCP_BEAT['last'] = now
    frame = _try(lambda: int(absTime.frame))  # noqa: F405
    d = mcp_beat_record(now, frame, src, os.getpid(), _MCP_BEAT)
    path = os.path.join(state_dir(), MCP_BEAT_FILE)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            f.write(json.dumps(d))
        os.replace(tmp, path)
    except Exception:
        return None
    return path


def tick(comp):
    """Called every ~2 s by the reconnect Execute DAT. Cheap: a few dict reads unless a reconnect is due.
    Disconnected: Active off on one tick, back on the next (one attempt every ~4 s). Also drives the autosave."""
    _try(lambda: mcp_beat('tick'))
    _try(_autosave_check)
    ws = _ws(comp)
    if ws is None or ws.par['active'] is None:
        return
    want = _try(lambda: int(comp.par.Bridgeport.eval()))  # None when the COMP predates the par
    if want and _try(lambda: int(ws.par.port.eval())) not in (None, want):
        ws.par.port = want  # Bridgeport changed (T-83): dial the new port
        _CONN['connected'] = False
        _status(ws, 'bridge port -> {}; reconnecting'.format(want))
    if _CONN.get('connected'):
        last = _CONN.get('last_rx')
        if last is not None and time.monotonic() - last > RECONNECT_SILENCE_S:
            _CONN['connected'] = False  # half-open link: no ping for too long
            _status(ws, 'no traffic for {:.0f} s; reconnecting'.format(RECONNECT_SILENCE_S))
        else:
            return
    if ws.par.active.eval():
        ws.par.active = False
        _CONN['phase'] = 'off'
    else:
        ws.par.active = True
        _CONN['phase'] = 'dialing'
        _CONN['attempts'] = _CONN.get('attempts', 0) + 1


def reconnect_now(comp):
    """The Reconnect pulse: drop the socket now; the next ticks dial again."""
    ws = _ws(comp)
    if ws is None:
        return
    _CONN['connected'] = False
    ws.par.active = False
    _CONN['phase'] = 'off'
    _status(ws, 'reconnect requested')


# ================================================================== debug toolkit (td/debug.py; PROTOCOL "Debug toolkit")
# td/debug.py is read from beside this file and exec'd into its own module (no DAT, nothing written into /jazib_mcp);
# it is re-read whenever its mtime changes, so editing it needs no td_reload. bind(globals()) hands it these helpers
# (Pending, safe_destroy, layout_stages, _plan_pars, op, absTime...). Commands: analyze, why, watch (read-only),
# debug_panel_build (mutating: one undo step).
DEBUG_FILE = 'debug.py'
DEBUG_DIR = None  # tests point this at td/; default = the folder of handlers_file()
_DEBUG = {'mod': None, 'mtime': None, 'file': None}


def _debug():
    import types as _types
    p = os.path.join(DEBUG_DIR or os.path.dirname(handlers_file()), DEBUG_FILE)
    mt = os.path.getmtime(p)
    if _DEBUG['mod'] is None or _DEBUG['mtime'] != mt or _DEBUG['file'] != p:
        with open(p, 'r', encoding='utf-8') as f:
            text = f.read()
        text.encode('ascii')  # LEARNINGS rule 1
        m = _types.ModuleType('jazib_debug')
        m.__file__ = p
        exec(compile(text, p, 'exec'), m.__dict__)
        _DEBUG.update(mod=m, mtime=mt, file=p)
    m = _DEBUG['mod']
    m.bind(globals())
    return m


def _debug_cmd(name):
    def run_debug(**kw):
        return getattr(_debug(), 'cmd_' + name)(**kw)
    run_debug.__name__ = 'cmd_' + name
    return run_debug


for _dbg_name in ('analyze', 'why', 'watch', 'debug_panel_build'):
    COMMANDS[_dbg_name] = _debug_cmd(_dbg_name)
MUTATING = MUTATING | frozenset(('debug_panel_build',))  # kept out of the literal above (journal parity test)


# ================================================================== lose nothing (td/safety.py; PROTOCOL "Lose nothing")
# Pre-risk save + per-COMP .tox checkpoints. td/safety.py loads like td/debug.py (own module, re-read on mtime change,
# bind(globals())). Only the hook below and PRESAVE live here: PRESAVE survives an edit of safety.py.
SAFETY_FILE = 'safety.py'
SAFETY_DIR = None  # tests point this at td/; default = the folder of handlers_file()
_SAFETY = {'mod': None, 'mtime': None, 'file': None}
PRESAVE = {'on': not is_scratch(),  # the scratch TD never saves itself (T-83)
           'min_s': 300.0, 'last': None, 'count': 0,  # a save stalls TD ~5 s on this project (T-96)
           'skipped': 0, 'last_file': None, 'error': None,
           'seen': None, 'seen_at': None, 'seen_extra': []}
# Commands the pre-risk check looks at (everything else never pays for it).
PRESAVE_CMDS = frozenset(('exec', 'create', 'set_pars', 'delete', 'tox_load', 'tda_load', 'reload', 'comfy_build',
                          'publish', 'osc_learn', 'link', 'live_audio', 'import_ae_anim', 'import_blender', 'midi_build', 'shadertoy',
                          'osc_expose', 'layer_mixer', 'debug_panel_build', 'restore_checkpoint'))


def _safety():
    import types as _types
    p = os.path.join(SAFETY_DIR or os.path.dirname(handlers_file()), SAFETY_FILE)
    mt = os.path.getmtime(p)
    if _SAFETY['mod'] is None or _SAFETY['mtime'] != mt or _SAFETY['file'] != p:
        with open(p, 'r', encoding='utf-8') as f:
            text = f.read()
        text.encode('ascii')  # LEARNINGS rule 1
        m = _types.ModuleType('jazib_safety')
        m.__file__ = p
        exec(compile(text, p, 'exec'), m.__dict__)
        _SAFETY.update(mod=m, mtime=mt, file=p)
    m = _SAFETY['mod']
    m.bind(globals())
    return m


def _pre_risk(cmd, args):
    """Never raises and never blocks the command: a broken safety.py only costs the pre-save."""
    try:
        return _safety().pre_risk(cmd, args)
    except Exception as e:
        return {'error': 'pre-risk check failed: {}: {}'.format(type(e).__name__, e)}


def _safety_cmd(name):
    def run_safety(**kw):
        return getattr(_safety(), 'cmd_' + name)(**kw)
    run_safety.__name__ = 'cmd_' + name
    return run_safety


for _sf_name in ('checkpoint', 'restore_checkpoint', 'presave'):
    COMMANDS[_sf_name] = _safety_cmd(_sf_name)
MUTATING = MUTATING | frozenset(('restore_checkpoint',))  # out of the literal (journal parity test)


# ================================================================== component library (td/library.py; PROTOCOL "Component library")
# Loads like td/debug.py: own module, re-read on mtime change (no td_reload for edits there), bind(globals()).
LIBRARY_FILE = 'library.py'
LIBRARY_DIR = None  # tests point this at td/; default = the folder of handlers_file()
_LIBRARY = {'mod': None, 'mtime': None, 'file': None}


def _library():
    import types as _types
    p = os.path.join(LIBRARY_DIR or os.path.dirname(handlers_file()), LIBRARY_FILE)
    mt = os.path.getmtime(p)
    if _LIBRARY['mod'] is None or _LIBRARY['mtime'] != mt or _LIBRARY['file'] != p:
        with open(p, 'r', encoding='utf-8') as f:
            text = f.read()
        text.encode('ascii')  # LEARNINGS rule 1
        m = _types.ModuleType('jazib_library')
        m.__file__ = p
        exec(compile(text, p, 'exec'), m.__dict__)
        _LIBRARY.update(mod=m, mtime=mt, file=p)
    m = _LIBRARY['mod']
    m.bind(globals())
    return m


def _library_cmd(name):
    def run_library(**kw):
        return getattr(_library(), 'cmd_' + name)(**kw)
    run_library.__name__ = 'cmd_' + name
    return run_library


for _lb_name in ('library_export', 'library_list', 'library_info', 'library_load'):
    COMMANDS[_lb_name] = _library_cmd(_lb_name)
MUTATING = MUTATING | frozenset(('library_load',))  # one undo step (out of the literal: journal parity test)
PRESAVE_CMDS = PRESAVE_CMDS | frozenset(('library_load',))  # a .tox load: pre-risk save first


# ================================================================== TL_timeline agent API (phase 4; PROTOCOL "Timeline API")
# Thin: every command calls the COMP's TimelineExt (builders/timeline_ext.py), which owns the logic
# (builders/timeline_api_logic.py, tested offline). The ext is stateless, so a fresh TimelineExt(comp) from its DAT
# module is used when TD has no initialised extension object.
TL_DEFAULT = '/project1/lab/TL_timeline'
TL_RECORD_CODECS = ('prores422hq', 'prores4444', 'hapq')
TL_EXPORTS = {'show': '.json', 'lanes_csv': '.csv', 'markers_json': '.json', 'markers_csv': '.csv'}


def _tl(comp=None):
    c = _op(comp or TL_DEFAULT, 'comp')
    d = c.op('TimelineExt')
    if d is None or c.op('tl_api_logic') is None or c.op('tl_actions') is None:
        raise ValueError('{} has no timeline API (TimelineExt + tl_api_logic): build it with builders/timeline.py '
                         'build() (api=True is the default)'.format(c.path))
    x = _try(lambda: c.ext.TimelineExt, None)
    return x if x is not None else d.module.TimelineExt(c)


def cmd_timeline_state(comp=None, at=None):
    return _tl(comp).State(at)


def cmd_timeline_show(comp=None, parts=None):
    return _tl(comp).Show(parts)


def cmd_timeline_edit(ops, comp=None, atomic=True, dry=False):
    return _tl(comp).Edit(ops, atomic=bool(atomic), dry=bool(dry))


def cmd_timeline_load(show, comp=None, mode='replace', dry=False):
    return _tl(comp).Load(show, mode=mode, dry=bool(dry))


def cmd_timeline_transport(comp=None, action=None, t=None, frame=None, n=None, lane=None, rate=None, loop=None,
                           inpoint=None, outpoint=None):
    kw = dict((k, v) for k, v in (('t', t), ('frame', frame), ('n', n), ('lane', lane), ('rate', rate),
                                  ('loop', loop), ('inpoint', inpoint), ('outpoint', outpoint)) if v is not None)
    return _tl(comp).Transport(action, **kw)


def cmd_timeline_export(file, comp=None, what='show', start=None, end=None, fps=None, lanes=None):
    if what not in TL_EXPORTS:
        raise ValueError('what must be one of {}'.format(sorted(TL_EXPORTS)))
    _abs_file(file, (TL_EXPORTS[what],))
    return _tl(comp).Export(what, file, start, end, fps, lanes)


def _tl_take(p, x, plan):
    """Wrap an offline_render Pending chain: the timeline's transport goes back (RecordFinish) at the end, on an
    error too; the reply gains timeline (the take plan) + restored."""
    f = p.finish

    def finish():
        try:
            r = f()
        except Exception:
            _try(x.RecordFinish)
            raise
        if isinstance(r, Pending):
            return _tl_take(r, x, plan)
        restored = x.RecordFinish()
        r = dict(r)
        r['timeline'] = plan
        r['restored'] = restored
        return r
    return Pending(p.frames, finish)


def cmd_timeline_record(file, comp=None, start=None, end=None, fps=None, source=None, codec='prores422hq'):
    """Stepped take of TL_timeline [start, end) to a .mov: transport parked (RecordPrepare), offline_render with
    the clock armed when Record goes on (one 1/cookRate step per TD frame), transport restored after."""
    if codec not in TL_RECORD_CODECS:
        raise ValueError('codec must be one of {}'.format(list(TL_RECORD_CODECS)))
    _abs_file(file, ('.mov',))
    x = _tl(comp)
    plan = x.RecordPrepare(start, end, fps, source)
    try:
        p = offline_render(plan['source'], file, plan['frames'], plan['fps'], codec, on_start=x.RecordArm)
    except Exception:
        _try(x.RecordFinish)
        raise
    return _tl_take(p, x, plan)


COMMANDS.update({'timeline_state': cmd_timeline_state, 'timeline_show': cmd_timeline_show,
                 'timeline_edit': cmd_timeline_edit, 'timeline_load': cmd_timeline_load,
                 'timeline_transport': cmd_timeline_transport, 'timeline_export': cmd_timeline_export,
                 'timeline_record': cmd_timeline_record})
MUTATING = MUTATING | frozenset(('timeline_edit', 'timeline_load'))  # one undo step per edit (out of the literal)


# ================================================================== td_isf (td/isf.py; PROTOCOL `isf`)
# ISF .fs (+ .vs) -> GLSL TOP COMP. Loads like td/library.py: own module, re-read on mtime change, bind(globals()).
ISF_FILE = 'isf.py'
ISF_DIR = None  # tests point this at td/; default = the folder of handlers_file()
_ISF = {'mod': None, 'mtime': None, 'file': None}


def _isf():
    import types as _types
    p = os.path.join(ISF_DIR or os.path.dirname(handlers_file()), ISF_FILE)
    mt = os.path.getmtime(p)
    if _ISF['mod'] is None or _ISF['mtime'] != mt or _ISF['file'] != p:
        with open(p, 'r', encoding='utf-8') as f:
            text = f.read()
        text.encode('ascii')  # LEARNINGS rule 1
        m = _types.ModuleType('jazib_isf')
        m.__file__ = p
        exec(compile(text, p, 'exec'), m.__dict__)
        _ISF.update(mod=m, mtime=mt, file=p)
    m = _ISF['mod']
    m.bind(globals())
    return m


def cmd_isf(**kw):
    return _isf().cmd_isf(**kw)


COMMANDS['isf'] = cmd_isf
MUTATING = MUTATING | frozenset(('isf',))  # one undo step (out of the literal: journal parity test)
PRESAVE_CMDS = PRESAVE_CMDS | frozenset(('isf',))


# ================================================================== td_vat_load / td_metavido (td/vat.py, td/metavido.py)
# Same loading as td_isf: own module beside handlers.py, re-read on mtime change, bind(globals()). Lane T, 27 Oct.
_EXT = {}


def _ext_module(fname):
    import types as _types
    p = os.path.join(ISF_DIR or os.path.dirname(handlers_file()), fname)
    mt = os.path.getmtime(p)
    e = _EXT.get(fname)
    if e is None or e['mtime'] != mt or e['file'] != p:
        with open(p, 'r', encoding='utf-8') as f:
            text = f.read()
        text.encode('ascii')  # LEARNINGS rule 1
        m = _types.ModuleType('jazib_' + fname[:-3])
        m.__file__ = p
        exec(compile(text, p, 'exec'), m.__dict__)
        e = _EXT[fname] = {'mod': m, 'mtime': mt, 'file': p}
    e['mod'].bind(globals())
    return e['mod']


def cmd_vat_load(**kw):
    return _ext_module('vat.py').cmd_vat_load(**kw)


def cmd_metavido(**kw):
    return _ext_module('metavido.py').cmd_metavido(**kw)


COMMANDS['vat_load'] = cmd_vat_load
COMMANDS['metavido'] = cmd_metavido
MUTATING = MUTATING | frozenset(('vat_load', 'metavido'))  # one undo step each (out of the literal: parity test)
PRESAVE_CMDS = PRESAVE_CMDS | frozenset(('vat_load', 'metavido'))


# ================================================================== on load: faulthandler (see install_faulthandler)
# Runs whenever TD (re)loads this module (first callback, td_reload); idempotent: one header per TD process.
if _in_td():
    _try(install_faulthandler)
