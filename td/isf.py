"""Jazib MCP for TouchDesigner -- td_isf: ISF (Interactive Shader Format) .fs (+ .vs) -> a GLSL TOP COMP.

Contract: docs/PROTOCOL.md `isf`; how to use: docs/USING_TD.md "ISF shaders". Research: docs/research/FX0 (G-ISF),
FX4 (ISF notes). ISF spec: https://github.com/mrRay/ISF_Spec (v2; v1 names vv_* and PERSISTENT_BUFFERS accepted).

Two halves:
  * pure (no TD; tested offline in test/test_isf.py on real Vidvox ISF files + synthetic cases):
      parse_isf(fs, vs) -> spec (inputs with TD par names, passes, imported images, texture slots, warnings)
      translate(spec, fs, vs) -> {glsl, warnings}: one GLSL 4.60 pixel shader shared by every pass
      size_expr(), uniform_exprs(), pass_sources(), default_comp_name()
  * TD builder cmd_isf(): a self-contained baseCOMP (storage jz_kit kind 'isf'): source DATs, `shader` DAT, one
    GLSL TOP per ISF pass (pass0..N, PASSINDEX = a uniform), Feedback TOPs for PERSISTENT targets, Select TOPs for
    image inputs (custom TOP pars; the first one falls back to the COMP's in1), CHOP -> TOP chains for audio /
    audioFFT inputs, Movie File In TOPs for IMPORTED, clock (Play / Speed / Reset), Out TOP out1, controls (zkit
    panel, or the plain Parameter COMP panel).

How ISF maps to TD:
  * uniforms: float/point2D/color = `uniform float/vec2/vec4 NAME` from the GLSL TOP Vectors page (par
    expressions); bool/event/long = `uniform float isf_in_NAME` turned into a global bool/int at the top of main().
  * images (inputs, audio, IMPORTED, pass TARGETs) = texture slots sTD2DInputs[k], same k in every pass; the first
    3 are wired, the rest go in the GLSL TOP `tops` par (T-88). IMG_PIXEL / IMG_NORM_PIXEL / IMG_THIS_PIXEL /
    IMG_THIS_NORM_PIXEL / IMG_SIZE with a known image name become macros on slot k (uTD2DInfos[k]); generic
    textureSize() fallbacks cover the rest.
  * a target read by pass p: written by an earlier pass -> that pass's GLSL TOP (this frame); written by p or a
    later pass -> its Feedback TOP when PERSISTENT (last frame), else black (ISF leaves it undefined).
  * the .vs is folded into the fragment shader: its `out`/`varying` globals become plain globals, its main() runs
    per pixel before the fragment main() (exact for the usual affine offsets; gl_Position edits are ignored).
  * RENDERSIZE = uTDOutputInfo.res.zw (the pass size), isf_FragNormCoord = gl_FragCoord.xy / RENDERSIZE,
    TIME / TIMEDELTA / FRAMEINDEX from the clock, DATE = (year, month 1-12, day, seconds of the day).

Loading: like td/library.py. handlers._isf() reads THIS FILE from beside handlers.py, execs it into a module,
re-reads it when its mtime changes; bind(globals()) hands it the handlers helpers through H. Pure ASCII.
"""
import json
import os
import re
import time

H = {}


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


# ================================================================== pure: parse
ISF_KIND = 'isf'
ISF_TYPES = ('event', 'bool', 'long', 'float', 'point2D', 'color', 'image', 'audio', 'audioFFT')
IMAGE_TYPES = ('image', 'audio', 'audioFFT')
MAX_CODE = 512 * 1024
FORMATS = ('rgba8fixed', 'rgba16float', 'rgba32float')
IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
# our own custom pars (ISF inputs never take these names)
OWN_PARS = ('Play', 'Speed', 'Reset', 'Resw', 'Resh', 'Format', 'Opencontrols', 'Licence', 'Author', 'Url',
            'Description', 'Isffile', 'Version', 'Touchbuild', 'Saved')
BUILTIN_UNIFORMS = ('PASSINDEX', 'RENDERSIZE', 'TIME', 'TIMEDELTA', 'FRAMEINDEX', 'DATE', 'isf_FragNormCoord')
SLOTS_WARN = 16


def _strip_comments(text):
    """Comments -> spaces (newlines kept, so line numbers and offsets stay)."""
    return re.sub(r'//[^\n]*|/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m.group(0)), text, flags=re.S)


def _loads_lenient(s):
    try:
        return json.loads(s)
    except ValueError:
        pass
    t = re.sub(r',(\s*[}\]])', r'\1', s)  # trailing commas (seen in hand-written ISF headers)
    try:
        return json.loads(t)
    except ValueError as e:
        raise ValueError('ISF header JSON does not parse: {}'.format(e))


def split_header(fs):
    """Pure: the ISF JSON header (the first /* ... */ comment whose text starts with '{'). Returns the dict."""
    if not isinstance(fs, str) or not fs.strip():
        raise ValueError('code must be the ISF fragment shader (.fs) text')
    if len(fs) > MAX_CODE:
        raise ValueError('ISF file is over {} bytes'.format(MAX_CODE))
    for m in re.finditer(r'/\*(.*?)\*/', fs, re.S):
        body = m.group(1).strip()
        if body.startswith('{'):
            d = _loads_lenient(body)
            if not isinstance(d, dict):
                raise ValueError('ISF header must be a JSON object')
            return d
        break  # ISF: the header is the first comment
    raise ValueError('no ISF JSON header (/*{ ... }*/ at the top of the .fs): not an ISF shader')


def par_name(isf_name, taken):
    """Pure: ISF input name -> a TD custom par name (Capital first, then lower case letters / digits), unique in
    `taken` (a set, updated). 'blurAmount' -> 'Bluramount'."""
    s = re.sub(r'[^A-Za-z0-9]', '', str(isf_name))
    if not s or not s[0].isalpha():
        s = 'P' + s
    s = s[0].upper() + s[1:].lower()
    if s.startswith('Zk'):  # the zkit page owns Zk* names
        s = 'I' + s.lower()
    base, n = s, 2
    while s in taken or s in OWN_PARS:
        s = '{}{}'.format(base, n)
        n += 1
    taken.add(s)
    return s


def _num(v, default=0.0):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return default
    return default


def _vec(v, n, default):
    if isinstance(v, (list, tuple)):
        out = [_num(x) for x in v[:n]]
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        out = [float(v)] * n
    else:
        out = []
    return out + list(default[len(out):n])


def _truth(v):
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(v)


def _input(raw, taken, warnings):
    if not isinstance(raw, dict):
        raise ValueError('INPUTS entries must be objects, got {!r}'.format(raw))
    name = raw.get('NAME')
    if not isinstance(name, str) or not IDENT_RE.match(name):
        raise ValueError('INPUTS: bad NAME {!r} (must be a GLSL identifier)'.format(name))
    typ = raw.get('TYPE')
    if typ not in ISF_TYPES:
        warnings.append('input {}: TYPE {!r} not supported (skipped; the shader will not compile if it uses it)'
                        .format(name, typ))
        return None
    d = {'name': name, 'type': typ, 'label': str(raw.get('LABEL') or name)}
    if typ == 'float':
        lo, hi = raw.get('MIN'), raw.get('MAX')
        d['clamp'] = lo is not None and hi is not None
        d['min'], d['max'] = _num(lo, 0.0), _num(hi, 1.0)
        if d['max'] < d['min']:
            d['min'], d['max'] = d['max'], d['min']
        dflt = raw.get('DEFAULT', raw.get('IDENTITY', d['min'] if lo is not None else 0.0))
        d['default'] = _num(dflt, d['min'])
    elif typ in ('bool', 'event'):
        d['default'] = _truth(raw.get('DEFAULT', False)) if typ == 'bool' else False
    elif typ == 'long':
        vals = raw.get('VALUES')
        if isinstance(vals, list) and vals:
            d['values'] = [int(_num(v)) for v in vals]
            labs = raw.get('LABELS')
            d['labels'] = ([str(x) for x in labs] if isinstance(labs, list) and len(labs) == len(vals)
                           else [str(v) for v in d['values']])
            dv = int(_num(raw.get('DEFAULT', d['values'][0])))
            d['default'] = dv if dv in d['values'] else d['values'][0]
        else:
            d['min'] = int(_num(raw.get('MIN', 0)))
            d['default'] = int(_num(raw.get('DEFAULT', d['min'])))
            d['max'] = int(_num(raw.get('MAX', max(10, d['default']))))
            d['clamp'] = 'MIN' in raw and 'MAX' in raw
    elif typ == 'point2D':
        d['default'] = _vec(raw.get('DEFAULT'), 2, [0.0, 0.0])
        d['min'] = _vec(raw.get('MIN'), 2, [0.0, 0.0])
        d['max'] = _vec(raw.get('MAX'), 2, [1.0, 1.0])
        d['clamp'] = raw.get('MIN') is not None and raw.get('MAX') is not None
    elif typ == 'color':
        d['default'] = _vec(raw.get('DEFAULT'), 4, [0.0, 0.0, 0.0, 1.0])
    elif typ == 'audio' or typ == 'audioFFT':
        d['samples'] = int(_num(raw.get('MAX', 0))) or None
    d['par'] = par_name(name, taken)
    if typ in ('bool', 'event', 'long'):
        d['uniform'] = 'isf_in_' + name
    elif typ in IMAGE_TYPES:
        d['uniform'] = None
    else:
        d['uniform'] = name
    return d


def _imported(raw, warnings):
    out = []
    items = []
    if isinstance(raw, dict):
        items = [(k, v) for k, v in raw.items()]
    elif isinstance(raw, list):
        items = [(v.get('NAME') if isinstance(v, dict) else None, v) for v in raw]
    for name, v in items:
        if not isinstance(v, dict) or not isinstance(name, str) or not IDENT_RE.match(name):
            warnings.append('IMPORTED entry {!r} skipped (needs NAME and PATH)'.format(name))
            continue
        if str(v.get('TYPE', '')).lower() == 'cube':
            warnings.append('IMPORTED {}: cube maps are not supported (TD inputs are 2D): skipped'.format(name))
            continue
        p = v.get('PATH')
        if not isinstance(p, str) or not p:
            warnings.append('IMPORTED {}: no PATH (skipped)'.format(name))
            continue
        out.append({'name': name, 'path': p})
    return out


def parse_isf(fs, vs=None):
    """Pure: ISF source -> spec {meta, inputs, passes, imported, slots, warnings}. Raises ValueError for what cannot
    run (no header, no main(), bad names, duplicate targets)."""
    h = split_header(fs)
    w = []
    body = _strip_comments(fs)
    if not re.search(r'\bvoid\s+main\s*\(', body):
        raise ValueError('the .fs has no void main(): not an ISF fragment shader')
    if vs is not None and not re.search(r'\bvoid\s+main\s*\(', _strip_comments(vs)):
        raise ValueError('the .vs has no void main()')
    cats = h.get('CATEGORIES')
    meta = {'description': str(h.get('DESCRIPTION') or ''), 'credit': str(h.get('CREDIT') or ''),
            'categories': [str(c) for c in cats] if isinstance(cats, list) else [],
            'isfvsn': str(h.get('ISFVSN') or ('1' if 'PERSISTENT_BUFFERS' in h else '2')),
            'vsn': str(h.get('VSN') or '')}
    taken = set()
    inputs = []
    raw_inputs = h.get('INPUTS') or []
    if not isinstance(raw_inputs, list):
        raise ValueError('INPUTS must be a list')
    for raw in raw_inputs:
        d = _input(raw, taken, w)
        if d is None:
            continue
        if any(i['name'] == d['name'] for i in inputs):
            raise ValueError('INPUTS: duplicate NAME {}'.format(d['name']))
        if d['name'] in BUILTIN_UNIFORMS:
            raise ValueError('INPUTS: {} is an ISF built-in name'.format(d['name']))
        inputs.append(d)
    # passes
    raw_passes = h.get('PASSES')
    if raw_passes in (None, [], {}):
        raw_passes = [{}]
    if not isinstance(raw_passes, list):
        raise ValueError('PASSES must be a list')
    pb = h.get('PERSISTENT_BUFFERS')  # ISF v1
    v1_persist = set(pb if isinstance(pb, list) else (pb.keys() if isinstance(pb, dict) else []))
    passes, seen = [], {}
    in_names = set(i['name'] for i in inputs)
    for q, raw in enumerate(raw_passes):
        raw = raw if isinstance(raw, dict) else {}
        t = raw.get('TARGET')
        if t is not None and (not isinstance(t, str) or not IDENT_RE.match(t)):
            raise ValueError('PASSES[{}]: bad TARGET {!r}'.format(q, t))
        if t in seen:
            raise ValueError('PASSES: target {} is written by passes {} and {} (one writer per target)'
                             .format(t, seen[t], q))
        if t in in_names:
            raise ValueError('PASSES[{}]: TARGET {} is also an input name'.format(q, t))
        if t:
            seen[t] = q
        v1 = pb.get(t) if isinstance(pb, dict) and t in pb and isinstance(pb.get(t), dict) else {}
        p = {'index': q, 'target': t or None,
             'persistent': bool(t) and (_truth(raw.get('PERSISTENT', False)) or t in v1_persist),
             'float': _truth(raw.get('FLOAT', v1.get('FLOAT', False))),
             'width': raw.get('WIDTH', v1.get('WIDTH')), 'height': raw.get('HEIGHT', v1.get('HEIGHT'))}
        passes.append(p)
    for t in sorted(v1_persist - set(seen)):
        w.append('PERSISTENT_BUFFERS {} has no pass that renders it (ignored)'.format(t))
    imported = _imported(h.get('IMPORTED'), w)
    for im in imported:
        if im['name'] in in_names or im['name'] in seen:
            raise ValueError('IMPORTED {} clashes with an input / target name'.format(im['name']))
    # texture slots: image inputs, audio inputs, imported, targets (same index in every pass)
    slots = []
    for kind in ('image', 'audio'):
        for i in inputs:
            if (i['type'] == 'image') if kind == 'image' else (i['type'] in ('audio', 'audioFFT')):
                slots.append({'name': i['name'], 'kind': i['type'], 'input': i['name']})
    for im in imported:
        slots.append({'name': im['name'], 'kind': 'imported', 'path': im['path']})
    for p in passes:
        if p['target']:
            slots.append({'name': p['target'], 'kind': 'target', 'pass': p['index'], 'persistent': p['persistent']})
    for k, s in enumerate(slots):
        s['index'] = k
    if len(slots) > SLOTS_WARN:
        w.append('{} texture slots (over {}): every pass gets all of them'.format(len(slots), SLOTS_WARN))
    scan = body + '\n' + _strip_comments(vs or '')
    if re.search(r'\bsamplerCube\b|\btextureCube\b', scan):
        w.append('cube maps are not supported (TD inputs are 2D)')
    if re.search(r'\btexture2DRect\b', scan):
        w.append('texture2DRect -> texture(): rect textures take 0..1 coords in TD; check those lines')
    if re.search(r'\bgl_FragData\s*\[\s*[1-9]', scan):
        w.append('gl_FragData[1+] (several outputs) is not supported: only colour 0 is written')
    if vs is not None and re.search(r'\bgl_Position\s*=', _strip_comments(vs)):
        w.append('the .vs writes gl_Position: vertex displacement is ignored (the .vs runs per pixel)')
    if vs is not None and re.search(r'\bgl_(Vertex|MultiTexCoord\d|Normal)\b', _strip_comments(vs)):
        w.append('the .vs uses fixed-function attributes (gl_Vertex...): not supported')
    return {'meta': meta, 'inputs': inputs, 'passes': passes, 'imported': imported, 'slots': slots, 'warnings': w,
            'has_vs': vs is not None}


def default_comp_name(source_name=None):
    """Pure: 'Bad TV.fs' -> 'isf_Bad_TV' (a valid TD op name)."""
    stem = os.path.splitext(os.path.basename(str(source_name or '')))[0]
    s = re.sub(r'[^A-Za-z0-9_]+', '_', stem).strip('_')
    return ('isf_' + s)[:60] if s else 'isf'


# ================================================================== pure: pass sizes
SIZE_TOKEN_RE = re.compile(r'\s*(?:(\$[A-Za-z_]\w*)|(\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?)|'
                           r'([A-Za-z_]\w*)|(\*\*|[-+*/%(),^]))')
SIZE_FUNCS = {'floor': "__import__('math').floor", 'ceil': "__import__('math').ceil", 'sqrt': "__import__('math').sqrt",
              'pow': 'pow', 'abs': 'abs', 'min': 'min', 'max': 'max', 'round': 'round',
              'log': "__import__('math').log", 'exp': "__import__('math').exp",
              'clamp': '(lambda v, a, b: min(max(v, a), b))'}


def _input_expr(inp):
    p = 'parent().par.' + inp['par']
    if inp['type'] == 'long' and inp.get('values'):
        return 'float({}.eval())'.format(p)
    if inp['type'] in ('bool', 'event', 'long'):
        return 'float({})'.format(p)
    if inp['type'] == 'point2D':
        return p + 'x'
    if inp['type'] == 'color':
        return p + 'r'
    return p


def size_expr(expr, inputs=()):
    """Pure: an ISF pass WIDTH/HEIGHT ("$WIDTH/8.0", "floor($HEIGHT*0.5)", 512, "$blurAmount*2") -> a TD par
    Python expression giving an int >= 1, or None (= full size). Raises ValueError for anything else."""
    if expr is None or (isinstance(expr, str) and not expr.strip()):
        return None
    if isinstance(expr, bool):
        raise ValueError('size must be a number or an expression, got {!r}'.format(expr))
    if isinstance(expr, (int, float)):
        return str(max(1, int(expr)))
    if not isinstance(expr, str):
        raise ValueError('size must be a number or an expression, got {!r}'.format(expr))
    by_name = dict((i['name'], i) for i in inputs)
    out, pos, s = [], 0, expr.strip()
    while pos < len(s):
        m = SIZE_TOKEN_RE.match(s, pos)
        if m is None or m.end() == pos:
            raise ValueError('size expression {!r}: cannot read {!r}'.format(expr, s[pos:pos + 8]))
        pos = m.end()
        var, num, ident, opr = m.groups()
        if var:
            v = var[1:]
            if v == 'WIDTH':
                out.append('parent().par.Resw')
            elif v == 'HEIGHT':
                out.append('parent().par.Resh')
            elif v in by_name and by_name[v]['type'] not in IMAGE_TYPES:
                out.append(_input_expr(by_name[v]))
            else:
                raise ValueError('size expression {!r}: unknown variable {}'.format(expr, var))
        elif num:
            out.append(num)
        elif ident:
            if ident not in SIZE_FUNCS:
                raise ValueError('size expression {!r}: unknown function {}'.format(expr, ident))
            out.append(SIZE_FUNCS[ident])
        else:
            out.append('**' if opr == '^' else opr)
    return 'max(1, int({}))'.format(' '.join(out))


# ================================================================== pure: GLSL translation
DECL_IO_RE = re.compile(r'^(\s*)(?:(?:flat|smooth|noperspective|centroid)\s+)?(varying|in|out|attribute)\s+'
                        r'((?:(?:highp|mediump|lowp)\s+)?[A-Za-z_]\w*\s+[^;{}()]+;)(.*)$')
UNIFORM_DECL_RE = re.compile(r'^\s*uniform\s+(?:(?:highp|mediump|lowp)\s+)?\w+\s+([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*;')
FUNC_DEF_RE = re.compile(r'^\s*(?:(?:highp|mediump|lowp|const|inline)\s+)*([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\(')
GLOBAL_DECL_RE = re.compile(r'^\s*(?:const\s+)?(?:(?:highp|mediump|lowp)\s+)?([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*'
                            r'(?:\[[^\]]*\])?\s*(?:=|;|,)')
NOT_TYPES = frozenset(('return', 'uniform', 'in', 'out', 'varying', 'attribute', 'precision', 'layout', 'struct',
                       'else', 'if', 'for', 'while', 'do', 'switch', 'case', 'define', 'undef'))
IMG_CALL_RE = re.compile(r'\b(IMG_PIXEL|IMG_NORM_PIXEL|IMG_THIS_PIXEL|IMG_THIS_NORM_PIXEL|IMG_SIZE)\s*\(\s*'
                         r'([A-Za-z_]\w*)\s*([,)])')
MAIN_RE = re.compile(r'\bvoid\s+main\s*\(\s*(?:void)?\s*\)')


def _line_depths(text):
    """Pure: [(line, brace depth at line start, starts inside a block comment)] ignoring braces in comments."""
    out, depth, in_block = [], 0, False
    for line in text.split('\n'):
        out.append((line, depth, in_block))
        i, n = 0, len(line)
        while i < n:
            if in_block:
                j = line.find('*/', i)
                if j < 0:
                    break
                in_block, i = False, j + 2
                continue
            two = line[i:i + 2]
            if two == '//':
                break
            if two == '/*':
                in_block, i = True, i + 2
                continue
            ch = line[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth = max(0, depth - 1)
            i += 1
    return out


def _decl_names(decl):
    """'vec2 a, b[5] = x;' -> ['a', 'b']"""
    body = re.sub(r'^\s*(?:(?:highp|mediump|lowp)\s+)?[A-Za-z_]\w*\s+', '', decl.rstrip(';'))
    names = []
    for part in body.split(','):
        m = re.match(r'\s*([A-Za-z_]\w*)', part)
        if m:
            names.append(m.group(1))
    return names


def _top_level_names(text):
    """Pure: names of functions and global variables declared at depth 0 (not uniforms / ins / outs)."""
    names = set()
    for line, depth, in_c in _line_depths(text):
        if depth or in_c or line.lstrip().startswith('#'):
            continue
        m = FUNC_DEF_RE.match(line)
        if m and m.group(1) not in NOT_TYPES:
            names.add(m.group(2))
            continue
        m = GLOBAL_DECL_RE.match(line)
        if m and m.group(1) not in NOT_TYPES:
            names.update(_decl_names(line.strip().split('=')[0] + ';') if ',' in line else [m.group(2)])
    names.discard('main')
    return names


def _io_globals(text, keep_kinds, drop_names=None, comment='// (td_isf)'):
    """Pure: depth-0 `in/out/varying/attribute T x;` lines. Kinds in keep_kinds become plain globals; others (or
    names in drop_names) are commented out. Returns (text, declared names kept, dropped names)."""
    kept, dropped, out = [], [], []
    for line, depth, in_c in _line_depths(text):
        m = None if (depth or in_c) else DECL_IO_RE.match(line)
        if m is None:
            out.append(line)
            continue
        ind, kind, decl, rest = m.groups()
        names = _decl_names(decl)
        if kind in keep_kinds and not (drop_names and all(n in drop_names for n in names)):
            out.append('{}{}{}'.format(ind, decl, rest))
            kept += names
        else:
            out.append('{}{} {} {}{}'.format(ind, comment, kind, decl, rest))
            dropped += names
    return '\n'.join(out), kept, dropped


def _img_calls(text, slot_of, unknown):
    def rep(m):
        fn, name, tail = m.groups()
        k = slot_of.get(name)
        if k is None:
            unknown.add(name)
            return m.group(0)
        if fn == 'IMG_PIXEL' and tail == ',':
            return 'isf_px({},'.format(k)
        if fn == 'IMG_NORM_PIXEL' and tail == ',':
            return 'isf_npx({},'.format(k)
        if fn in ('IMG_THIS_PIXEL', 'IMG_THIS_NORM_PIXEL') and tail == ')':
            return 'isf_npx({}, isf_FragNormCoord)'.format(k)
        if fn == 'IMG_SIZE' and tail == ')':
            return 'isf_size({})'.format(k)
        return m.group(0)
    return IMG_CALL_RE.sub(rep, text)


def _common_fixes(text, names):
    t = re.sub(r'^(\s*)#\s*version\b([^\n]*)', r'\1// (#version removed by td_isf)\2', text, flags=re.M)
    t = re.sub(r'\bgl_FragData\s*\[\s*0\s*\]', 'isf_FragColor', t)
    t = re.sub(r'\bgl_FragColor\b', 'isf_FragColor', t)
    t = re.sub(r'\bgl_Position\b', 'isf_Position', t)

    out = []
    for line, depth, in_c in _line_depths(t):
        m = None if (depth or in_c) else UNIFORM_DECL_RE.match(line)
        if m and m.group(1) in names:
            line = '// (declared by td_isf) ' + line.strip()
        out.append(line)
    return '\n'.join(out)


def translate(spec, fs, vs=None):
    """Pure: ISF .fs (+ .vs) -> one GLSL 4.60 pixel shader for every pass of a TD GLSL TOP.
    Returns {glsl, header_lines, warnings, vs_renamed}. Line numbers: header 90000+, .vs = source 1 line N
    ('1:N' in the log), .fs = its own line N, the wrapper main() 100000+."""
    w = []
    slot_of = dict((s['name'], s['index']) for s in spec['slots'])
    names = set(i['name'] for i in spec['inputs']) | set(BUILTIN_UNIFORMS) | set(slot_of)
    unknown = set()
    f = _common_fixes(_img_calls(fs, slot_of, unknown), names)
    f = MAIN_RE.sub('void isf_main()', f, count=1)
    v_txt, renamed = None, []
    if vs is not None:
        v_txt = _common_fixes(_img_calls(vs, slot_of, unknown), names)
        v_txt = MAIN_RE.sub('void isf_vs_main()', v_txt, count=1)
        v_txt, v_vars, _d = _io_globals(v_txt, ('out', 'varying'))
        f, _k, f_drop = _io_globals(f, ())
        missing = sorted(set(f_drop) - set(v_vars))
        if missing:
            w.append('the .fs reads varyings the .vs never declares: {}'.format(', '.join(missing)))
        clash = sorted((_top_level_names(v_txt) & _top_level_names(f)) - set(v_vars))
        for n in clash:  # the .vs is folded into the same shader: its own helpers get a prefix
            v_txt = re.sub(r'\b{}\b'.format(re.escape(n)), 'isf_vs_' + n, v_txt)
            renamed.append(n)
        if renamed:
            w.append('.vs names also used by the .fs renamed isf_vs_*: {}'.format(', '.join(renamed)))
    else:
        f, kept, _d = _io_globals(f, ('in', 'varying'))
        if kept:
            w.append('no .vs: varyings {} become plain globals (never set; give the .vs)'.format(', '.join(kept)))
    unknown = set(m.group(2) for m in IMG_CALL_RE.finditer(_strip_comments(f + '\n' + (v_txt or ''))))
    if unknown:
        w.append('IMG_* calls on names that are not ISF images: {} (generic textureSize fallback)'
                 .format(', '.join(sorted(unknown))))
    hdr = ['#line 90000',
           '// td_isf wrapper (jazib-td). Edit the `source` DAT (+ `vsource`) and call td_isf again: rebuilt.',
           'uniform float isf_passF;', 'uniform float TIME;', 'uniform float TIMEDELTA;', 'uniform float isf_frameF;',
           'uniform vec4 DATE;', 'int PASSINDEX;', 'int FRAMEINDEX;', 'vec2 isf_FragNormCoord;', 'vec4 isf_FragColor;',
           'vec4 isf_Position;',
           '#define RENDERSIZE (uTDOutputInfo.res.zw)', '#define vv_FragNormCoord isf_FragNormCoord',
           '#define texture2D texture', '#define texture2DRect texture', '#define texture2DProj textureProj',
           '#define isf_npx(k, c) texture(sTD2DInputs[k], (c))',
           '#define isf_px(k, c) texture(sTD2DInputs[k], (c) * uTD2DInfos[k].res.xy)',
           '#define isf_size(k) (uTD2DInfos[k].res.zw)',
           '#define IMG_NORM_PIXEL(img, c) texture(img, (c))',
           '#define IMG_PIXEL(img, c) texture(img, (c) / vec2(textureSize(img, 0)))',
           '#define IMG_THIS_PIXEL(img) texture(img, isf_FragNormCoord)',
           '#define IMG_THIS_NORM_PIXEL(img) texture(img, isf_FragNormCoord)',
           '#define IMG_SIZE(img) vec2(textureSize(img, 0))',
           'void isf_vertShaderInit() {}', '#define vv_vertShaderInit isf_vertShaderInit']
    sets = []
    for i in spec['inputs']:
        t, n = i['type'], i['name']
        if t == 'float':
            hdr.append('uniform float {};'.format(n))
        elif t == 'point2D':
            hdr.append('uniform vec2 {};'.format(n))
        elif t == 'color':
            hdr.append('uniform vec4 {};'.format(n))
        elif t in ('bool', 'event'):
            hdr += ['uniform float isf_in_{};'.format(n), 'bool {};'.format(n)]
            sets.append('\t{0} = isf_in_{0} > 0.5;'.format(n))
        elif t == 'long':
            hdr += ['uniform float isf_in_{};'.format(n), 'int {};'.format(n)]
            sets.append('\t{0} = int(floor(isf_in_{0} + 0.5));'.format(n))
    code_nc = _strip_comments(f + '\n' + (v_txt or ''))
    for s in spec['slots']:
        k, n = s['index'], s['name']
        # the bare name -> the sampler only when the code still uses it and never declares it itself (a local
        # `vec4 lastRow = IMG_PIXEL(lastRow, ...)` in Interlace.fs shadows the image name)
        if re.search(r'\b{}\b'.format(re.escape(n)), code_nc) and not re.search(
                r'\b[A-Za-z_]\w*\s+{}\s*(\[[^\]]*\])?\s*[=;,)]'.format(re.escape(n)), code_nc):
            hdr.append('#define {} sTD2DInputs[{}]'.format(n, k))
        hdr += ['#define _{}_imgSize (uTD2DInfos[{}].res.zw)'.format(n, k),
                '#define _{}_imgRect vec4(0.0, 0.0, uTD2DInfos[{}].res.zw)'.format(n, k),
                '#define _{}_flip false'.format(n)]
    hdr.append('layout(location = 0) out vec4 jzFragColor;')
    parts = ['\n'.join(hdr)]
    if v_txt is not None:
        parts += ['#line 1 1', v_txt.rstrip('\n')]
    parts += ['#line 1 0', f.rstrip('\n')]
    tail = ['', '#line 100000 0', 'void main()', '{',
            '\tisf_FragNormCoord = gl_FragCoord.xy / uTDOutputInfo.res.zw;',
            '\tPASSINDEX = int(isf_passF + 0.5);', '\tFRAMEINDEX = int(isf_frameF + 0.5);'] + sets + [
            '\tisf_FragColor = vec4(0.0);', '\tisf_Position = vec4(0.0);']
    if v_txt is not None:
        tail.append('\tisf_vs_main();')
    tail += ['\tisf_main();', '\tjzFragColor = TDOutputSwizzle(isf_FragColor);', '}']
    parts.append('\n'.join(tail))
    return {'glsl': '\n'.join(parts) + '\n', 'header_lines': len(hdr), 'warnings': w, 'vs_renamed': renamed}


# ================================================================== pure: uniforms + per-pass sources
def uniform_exprs(spec, pass_index):
    """Pure: [(uniform name, [x, y, z, w] Python expressions)] for one pass's GLSL TOP Vectors page."""
    t = "__import__('time')"
    out = [('isf_passF', [str(int(pass_index)), '0', '0', '0']),
           ('TIME', ["op('clock')['seconds'].eval()", '0', '0', '0']),
           ('TIMEDELTA', ['parent().par.Speed * float(parent().par.Play) / me.time.rate', '0', '0', '0']),
           ('isf_frameF', ["op('clock')['frames'].eval()", '0', '0', '0']),
           ('DATE', ['{}.localtime().tm_year'.format(t), '{}.localtime().tm_mon'.format(t),
                     '{}.localtime().tm_mday'.format(t),
                     '(lambda a, s: a.tm_hour * 3600 + a.tm_min * 60 + a.tm_sec + s % 1)({0}.localtime(), {0}.time())'
                     .format(t)])]
    for i in spec['inputs']:
        p = 'parent().par.' + i['par']
        typ = i['type']
        if typ in IMAGE_TYPES:
            continue
        if typ == 'float':
            ex = [p, '0', '0', '0']
        elif typ == 'point2D':
            ex = [p + 'x', p + 'y', '0', '0']
        elif typ == 'color':
            ex = [p + 'r', p + 'g', p + 'b', p + 'a']
        elif typ == 'event':
            ex = ["1 if absTime.frame - parent().fetch('isf_ev_{}', -99, search=False) <= 1 else 0"
                  .format(i['par']), '0', '0', '0']
        else:
            ex = [_input_expr(i), '0', '0', '0']
        out.append((i['uniform'], ex))
    return out


def slot_op(slot):
    """Pure: the op that feeds an image-like slot (targets are per pass: pass_sources)."""
    if slot['kind'] == 'image':
        return 'img_' + slot['name']
    if slot['kind'] in ('audio', 'audioFFT'):
        return 'aud_' + slot['name']
    if slot['kind'] == 'imported':
        return 'imp_' + slot['name']
    return None


def pass_sources(spec):
    """Pure: per pass, the op name feeding each texture slot (index order). A target written by an earlier pass
    = that pass's GLSL TOP; by this or a later pass = fb_<target> when PERSISTENT, else isf_black."""
    out = []
    for p in spec['passes']:
        row = []
        for s in spec['slots']:
            if s['kind'] != 'target':
                row.append(slot_op(s))
            elif s['pass'] < p['index']:
                row.append('pass{}'.format(s['pass']))
            elif s['persistent']:
                row.append('fb_' + s['name'])
            else:
                row.append('isf_black')
        out.append(row)
    return out


# ================================================================== TD builder
SOURCE_HEAD = ('// ISF source for td_isf (jazib-td). File: {file}. Licence: {licence}. Credit: {credit}. URL: {url}\n'
               '// Vidvox ISF-Files are MIT; other ISF files carry their own licence: keep this note.\n')
PREFIXES = ('pass', 'fb_', 'clr_', 'img_', 'aud_', 'imp_')


def _set(o, name, value, notes):
    G('_midi_set')(o, name, value, notes)


def _make_par(c, page, inp):
    """One ISF input as a custom par (created once; range / default / menu follow the build, the value is kept
    unless the style changed)."""
    styles = {'float': 'Float', 'bool': 'Toggle', 'event': 'Pulse', 'point2D': 'XY', 'color': 'RGBA',
              'image': 'TOP', 'audio': 'CHOP', 'audioFFT': 'CHOP'}
    t = inp['type']
    style = styles.get(t) or ('Menu' if inp.get('values') else 'Int')
    name = inp['par']
    grp = [p for p in _try(lambda: list(c.customPars), []) if _try(lambda: p.tupletName, p.name) == name]
    old_style = _try(lambda: grp[0].style, None) if grp else None
    fresh = not grp
    if grp and old_style != style:
        for p in grp:
            _try(p.destroy)
        fresh = True
    if fresh:
        grp = list(getattr(page, 'append' + style)(name, label=inp['label']))
    for p in grp:
        _try(lambda: setattr(p, 'label', inp['label']))
    if style == 'Menu':
        grp[0].menuNames = [str(v) for v in inp['values']]
        grp[0].menuLabels = list(inp['labels'])
        grp[0].default = str(inp['default'])
        if fresh or grp[0].eval() not in grp[0].menuNames:
            grp[0].val = str(inp['default'])
        return name, style
    if style in ('Float', 'Int'):
        p = grp[0]
        p.normMin, p.normMax = inp['min'], inp['max']
        if inp.get('clamp'):
            p.clampMin, p.min, p.clampMax, p.max = True, inp['min'], True, inp['max']
    if style == 'XY':
        for k, p in enumerate(grp[:2]):
            p.normMin, p.normMax = inp['min'][k], inp['max'][k]
            if inp.get('clamp'):
                p.clampMin, p.min, p.clampMax, p.max = True, inp['min'][k], True, inp['max'][k]
    if style == 'RGBA':
        for p in grp[:4]:
            p.normMin, p.normMax = 0.0, 1.0
    if style in ('Float', 'Int', 'Toggle', 'XY', 'RGBA'):
        d = inp['default']
        vals = d if isinstance(d, (list, tuple)) else [d] * len(grp)
        for p, v in zip(grp, vals):
            v = int(v) if style == 'Int' else (bool(v) if style == 'Toggle' else v)
            p.default = v
            if fresh:
                p.val = v
    return name, style


def _sync_pars(c, page_name, inputs):
    page = next((pg for pg in _try(lambda: list(c.customPages), []) if pg.name == page_name), None)
    if page is None and inputs:
        page = c.appendCustomPage(page_name)
    want = set(i['par'] for i in inputs)
    if page is not None:  # pars of an older build that this file no longer has
        for p in list(_try(lambda: list(c.customPars), [])):
            if _try(lambda: p.page.name, None) == page_name and _try(lambda: p.tupletName, p.name) not in want:
                _try(p.destroy)
    made = [_make_par(c, page, i) for i in inputs]
    if page is not None and not inputs:
        _try(page.destroy)
    return made


def _pass_res(spec, p, notes):
    out = []
    for key, full in (('width', 'parent().par.Resw'), ('height', 'parent().par.Resh')):
        try:
            e = size_expr(p[key], spec['inputs'])
        except ValueError as e_:
            notes.append('pass {} {}: {} (full size used)'.format(p['index'], key.upper(), e_))
            e = None
        out.append(e or full)
    return out


def _zkit_panel(c, notes):
    """The zerror-style knob panel (builders/zkit.py build_controls) for the ISF + Shader pages. None on failure."""
    f = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(G('handlers_file')()))), 'builders', 'zkit.py')
    try:
        ns = dict(G('exec_namespace')())
        with open(f, 'r', encoding='utf-8') as fh:
            exec(compile(fh.read(), f, 'exec'), ns)
        pages = [n for n in ('ISF', 'Shader') if any(pg.name == n for pg in c.customPages)]
        return ns['build_controls'](c.path, pages=pages, d=56, cols=6)
    except Exception as e:
        notes.append('zkit panel failed ({}: {}): plain panel used'.format(type(e).__name__, str(e)[:160]))
        return None


EVENTS_EXEC = '''# td_isf events (jazib-td): Reset restarts the clock + clears persistent buffers; ISF event inputs are true
# for the frame they are pulsed in (+1).
def onPulse(par):
    c = parent()
    if par.name == 'Reset':
        c.op('clock').par.resetpulse.pulse()
        for o in c.ops('fb_*'):
            o.par.resetpulse.pulse()
    else:
        c.store('isf_ev_' + par.name, absTime.frame)
'''


def cmd_isf(code, vs=None, parent='/project1', name=None, source_name=None, base_dir=None, res=None, panel='zkit',
            images=None, licence=None, author=None, url=None, frames=3):
    """ISF .fs (+ .vs) -> a self-contained COMP (see the module docstring). Called again on the same COMP it
    updates in place (ops reused by name, stale passes / slots / pars removed). Replies after `frames`."""
    spec = parse_isf(code, vs)
    tr = translate(spec, code, vs)
    if panel not in ('zkit', 'plain'):
        raise ValueError("panel must be 'zkit' or 'plain'")
    if res is not None and (not isinstance(res, (list, tuple)) or len(res) != 2):
        raise ValueError('res must be [w, h]')
    images = images or {}
    if not isinstance(images, dict):
        raise ValueError('images must be {isf image input name: TOP path}')
    img_inputs = [i for i in spec['inputs'] if i['type'] in IMAGE_TYPES]
    for k, v in images.items():
        i = next((x for x in img_inputs if x['name'] == k), None)
        if i is None:
            raise ValueError('images: {} is not an image/audio input of this ISF ({})'.format(
                k, ', '.join(x['name'] for x in img_inputs) or 'none'))
        if not isinstance(v, str) or not v.startswith('/'):
            raise ValueError('images: absolute op paths, got {!r}'.format(v))
    kit_comp, kit_child, kit_pars, kit_wire = G('_kit_comp'), G('_kit_child'), G('_kit_pars'), G('_kit_wire')
    stage, safe_destroy = G('_stage'), G('safe_destroy')
    c, created = kit_comp(parent, name or default_comp_name(source_name), ISF_KIND, 'isf')
    par_ = c.parent()
    w, h = (int(res[0]), int(res[1])) if res else G('DEFAULT_RES')
    made, notes = [], []
    kit_pars(c, 'Shader', [
        ('Play', 'Toggle', True, {'label': 'Play'}),
        ('Speed', 'Float', 1.0, {'label': 'Speed', 'min': 0.0, 'max': 4.0}),
        ('Reset', 'Pulse', None, {'label': 'Reset time + buffers'}),
        ('Resw', 'Int', w, {'label': 'Width (RENDERSIZE)', 'min': 16, 'max': 4096}),
        ('Resh', 'Int', h, {'label': 'Height (RENDERSIZE)', 'min': 16, 'max': 4096}),
        ('Format', 'Menu', 'rgba8fixed', {'label': 'Pixel format', 'names': list(FORMATS),
                                          'labels': ['8-bit fixed', '16-bit float', '32-bit float']})])
    if res:
        c.par.Resw.val, c.par.Resh.val = w, h
    in_pars = _sync_pars(c, 'ISF', [i for i in spec['inputs'] if i['type'] not in IMAGE_TYPES])
    img_pars = _sync_pars(c, 'Images', img_inputs)
    for k, v in images.items():
        c.par[next(x['par'] for x in img_inputs if x['name'] == k)].val = v
    kit_pars(c, 'About', [('Licence', 'Str', '', {'label': 'Licence'}), ('Author', 'Str', '', {'label': 'Credit'}),
                          ('Url', 'Str', '', {'label': 'Source URL'}), ('Description', 'Str', '', {'label': 'ISF description'}),
                          ('Isffile', 'Str', '', {'label': 'ISF file'})])
    for k, v in (('Licence', licence), ('Author', author if author is not None else (spec['meta']['credit'] or None)),
                 ('Url', url), ('Description', spec['meta']['description'] or None), ('Isffile', source_name)):
        if v is not None:
            c.par[k].val = str(v)
    lic = {'licence': c.par.Licence.eval() or 'not given', 'credit': c.par.Author.eval() or 'not given',
           'url': c.par.Url.eval() or 'not given', 'file': c.par.Isffile.eval() or 'pasted'}
    # sources + shader
    src = kit_child(c, 'textDAT', 'source', made, notes)
    src.text = SOURCE_HEAD.format(**lic) + code
    expected = {'source', 'shader', 'isf_map', 'isf_black', 'rate', 'clock', 'out1', 'isf_events'}
    if vs is not None:
        vsrc = kit_child(c, 'textDAT', 'vsource', made, notes)
        vsrc.text = vs
        expected.add('vsource')
    sh = kit_child(c, 'textDAT', 'shader', made, notes)
    sh.text = tr['glsl']
    black = kit_child(c, 'constantTOP', 'isf_black', made, notes)
    for k, v in (('colorr', 0), ('colorg', 0), ('colorb', 0), ('alpha', 0), ('outputresolution', {'menu': 'custom'}),
                 ('resolutionw', 16), ('resolutionh', 16)):
        _set(black, k, v, notes)
    # image inputs
    slot_ops = []
    first_img = next((i for i in img_inputs if i['type'] == 'image'), None)
    if first_img is not None:
        kit_child(c, 'inTOP', 'in1', made, notes)
        expected.add('in1')
    for i in img_inputs:
        nm = 'aud_' + i['name'] if i['type'] != 'image' else 'img_' + i['name']
        if i['type'] == 'image':
            s = kit_child(c, 'selectTOP', nm, made, notes)
            fb = "op('in1')" if i is first_img else "op('isf_black')"
            _set(s, 'top', {'expr': "parent().par.{}.eval() or {}".format(i['par'], fb)}, notes)
            expected.add(nm)
            slot_ops.append(nm)
            continue
        sel = kit_child(c, 'selectCHOP', nm + '_sel', made, notes)
        _set(sel, 'chop', {'expr': "parent().par.{}.eval() or op('aud_silence')".format(i['par'])}, notes)
        chain = [nm + '_sel']
        last = sel
        if i['type'] == 'audioFFT':
            fft = kit_child(c, 'audiospectrumCHOP', nm + '_fft', made, notes)
            kit_wire([sel], fft, notes)
            last = fft
            chain.append(nm + '_fft')
        mth = kit_child(c, 'mathCHOP', nm + '_math', made, notes)
        kit_wire([last], mth, notes)
        if i['type'] == 'audio':  # ISF audio images: 0.5 = silence
            _set(mth, 'gain', 0.5, notes)
            _set(mth, 'postoff', 0.5, notes)
        tt = kit_child(c, 'choptoTOP', nm, made, notes)
        _set(tt, 'chop', nm + '_math', notes)
        _set(tt, 'format', 'rgba32float', notes)
        expected.update(chain + [nm + '_math', nm, 'aud_silence'])
        slot_ops.append(nm)
    if any(i['type'] in ('audio', 'audioFFT') for i in img_inputs):
        sil = kit_child(c, 'constantCHOP', 'aud_silence', made, notes)
        _set(sil, 'const0name', 'chan1', notes)
        _set(sil, 'const0value', 0, notes)
    for im in spec['imported']:
        nm = 'imp_' + im['name']
        mv = kit_child(c, 'moviefileinTOP', nm, made, notes)
        pth = im['path'] if os.path.isabs(im['path']) or not base_dir else os.path.join(base_dir, im['path'])
        if not base_dir and not os.path.isabs(im['path']):
            notes.append('IMPORTED {}: relative PATH {} and no base_dir (give file:)'.format(im['name'], im['path']))
        elif not os.path.isfile(pth):
            notes.append('IMPORTED {}: file not found: {}'.format(im['name'], pth))
        _set(mv, 'file', pth, notes)
        expected.add(nm)
    # clock
    rate = kit_child(c, 'constantCHOP', 'rate', made, notes)
    _try(lambda: setattr(rate.seq.const, 'numBlocks', 2))
    for k, v in (('const0name', 'seconds'), ('const0value', {'expr': 'parent().par.Speed * float(parent().par.Play)'}),
                 ('const1name', 'frames'), ('const1value', {'expr': 'float(parent().par.Play) * project.cookRate'})):
        _set(rate, k, v, notes)
    clock = kit_child(c, 'speedCHOP', 'clock', made, notes)
    kit_wire([rate], clock, notes)
    # passes
    srcs = pass_sources(spec)
    pass_ops = []
    for p in spec['passes']:
        nm = 'pass{}'.format(p['index'])
        g = kit_child(c, 'glslTOP', nm, made, notes)
        rw, rh = _pass_res(spec, p, notes)
        fmt = 'rgba32float' if p['float'] else {'expr': 'parent().par.Format.eval()'}
        for k, v in (('glslversion', {'menu': 'glsl460'}), ('mode', {'menu': 'vertexpixel'}), ('pixeldat', 'shader'),
                     ('outputresolution', {'menu': 'custom'}), ('resolutionw', {'expr': rw}),
                     ('resolutionh', {'expr': rh}), ('format', fmt)):
            _set(g, k, v, notes)
        unis = uniform_exprs(spec, p['index'])
        _try(lambda: setattr(g.seq.vec, 'numBlocks', len(unis)))
        for k, (uname, ex) in enumerate(unis):
            _set(g, 'vec{}name'.format(k), uname, notes)
            for comp_, e in zip('xyzw', ex):
                _set(g, 'vec{}value{}'.format(k, comp_), {'expr': e} if not re.match(r'^-?\d+(\.\d+)?$', e)
                     else float(e), notes)
        pass_ops.append((p, g, rw, rh, fmt))
        expected.add(nm)
    for p, g, rw, rh, fmt in pass_ops:
        if p['persistent']:
            t = p['target']
            clr = kit_child(c, 'constantTOP', 'clr_' + t, made, notes)
            for k, v in (('colorr', 0), ('colorg', 0), ('colorb', 0), ('alpha', 0),
                         ('outputresolution', {'menu': 'custom'}), ('resolutionw', {'expr': rw}),
                         ('resolutionh', {'expr': rh}), ('format', fmt)):
                _set(clr, k, v, notes)
            fb = kit_child(c, 'feedbackTOP', 'fb_' + t, made, notes)
            kit_wire([clr], fb, notes)
            _set(fb, 'top', g.name, notes)
            expected.update(['clr_' + t, 'fb_' + t])
    for (p, g, _rw, _rh, _f), row in zip(pass_ops, srcs):
        ins = [c.op(n) for n in row]
        for k in range(len(_try(lambda: list(g.inputConnectors), []) or [])):
            _try(lambda: g.inputConnectors[k].disconnect())
        kit_wire(ins[:3], g, notes)
        _set(g, 'tops', ' '.join(row[3:]), notes)
    last = pass_ops[-1][1]
    out = kit_child(c, 'outTOP', 'out1', made, notes)
    kit_wire([last], out, notes)
    # map table (what is what, for people)
    mp = kit_child(c, 'tableDAT', 'isf_map', made, notes)
    _try(mp.clear)
    _try(lambda: mp.appendRow(['isf', 'type', 'par', 'uniform_or_slot', 'range']))
    for i in spec['inputs']:
        slot = next((s['index'] for s in spec['slots'] if s['name'] == i['name']), None)
        rng = (i.get('values') and ' '.join(str(v) for v in i['values'])) or (
            '{} .. {}'.format(i['min'], i['max']) if 'min' in i else '')
        _try(lambda: mp.appendRow([i['name'], i['type'], i['par'],
                                   i['uniform'] if i['uniform'] else 'sTD2DInputs[{}]'.format(slot), rng]))
    for s in spec['slots']:
        if s['kind'] in ('imported', 'target'):
            _try(lambda: mp.appendRow([s['name'], s['kind'] + (' persistent' if s.get('persistent') else ''), '',
                                       'sTD2DInputs[{}]'.format(s['index']), '']))
    # events + Reset
    ev = kit_child(c, 'parameterexecuteDAT', 'isf_events', made, notes)
    ev.text = EVENTS_EXEC
    evs = ['Reset'] + [i['par'] for i in spec['inputs'] if i['type'] == 'event']
    for k, v in (('op', '..'), ('pars', ' '.join(evs)), ('custom', True), ('builtin', False), ('onpulse', True),
                 ('valuechange', False)):
        _set(ev, k, v, notes)
    # stale ops of an older build
    for ch in list(_try(lambda: list(c.children), [])):
        n = _try(lambda: ch.name, '')
        if n.startswith(PREFIXES) and n not in expected:
            safe_destroy(ch)
        elif n in ('vsource', 'in1', 'aud_silence') and n not in expected:
            safe_destroy(ch)
    # controls
    ctl, used_panel = [], panel
    info = _zkit_panel(c, notes) if panel == 'zkit' else None
    if info is not None:
        ctl = ['controls', 'controls_window']
    else:
        used_panel = 'plain'
        G('_kit_pars')(c, 'Controls', [('Opencontrols', 'Pulse', None, {'label': 'Open controls'})])
        ctl = G('_kit_controls')(c, 'ISF', made, notes, 420, 560, 'ISF Shader Images About')
    c.store(G('KIT_KEY'), {'kind': ISF_KIND, 'passes': len(spec['passes']), 'slots': len(spec['slots']),
                           'panel': used_panel})
    c.comment = 'td_isf: ISF shader {} ({} pass{}). Licence: {}'.format(
        lic['file'], len(spec['passes']), '' if len(spec['passes']) == 1 else 'es', lic['licence'])
    about = G('about_values')(_try(lambda: c.par.Version.eval(), None), None, None,
                              G('td_build_string')(_try(lambda: G('app').version, ''), _try(lambda: G('app').build, '')))
    G('_stamp_about')(c, about)
    img_ops = [n for n in sorted(expected) if n.startswith(('img_', 'aud_', 'imp_'))]
    stages = [stage(c, 'Source', 'input', ['source', 'vsource', 'shader', 'isf_map'],
                    'ISF code (+ licence note), the folded .vs, the TD wrapper; isf_map = input -> par / slot'),
              stage(c, 'Images', 'input', ['in1', 'isf_black'] + img_ops,
                    'image inputs (TOP pars; the first falls back to in1), audio CHOP -> TOP, IMPORTED files'),
              stage(c, 'Clock', 'control', ['rate', 'clock', 'isf_events'], 'TIME / FRAMEINDEX: Play, Speed, Reset'),
              stage(c, 'Passes', 'process', ['pass{}'.format(p['index']) for p in spec['passes']] +
                    [n for n in sorted(expected) if n.startswith(('clr_', 'fb_'))],
                    'one GLSL TOP per ISF pass (PASSINDEX uniform); fb_* = PERSISTENT buffers'),
              stage(c, 'Output', 'output', ['out1'], 'Out TOP: the last pass'),
              stage(c, 'Controls', 'control', ctl, 'Opencontrols opens the panel')]
    fin = G('_kit_finish')(c, stages, created, par_, notes)
    glsls = [g for _p, g, _a, _b, _c in pass_ops]

    def finish():
        bad, log = [], ''
        for g in glsls:
            _try(lambda: g.cook(force=True))
            err = (_try(lambda: g.errors(), '') or '') + '\n' + (_try(lambda: g.warnings(), '') or '')
            bad += ['{}: {}'.format(g.name, ln) for ln in err.splitlines() if re.search(r'error', ln, re.I)]
        if glsls:
            log = _try(lambda: G('_glsl_log')(glsls[0]), '') or ''
            bad += [ln for ln in log.splitlines() if re.search(r'error', ln, re.I)]
        r = {'path': c.path, 'created': created, 'passes': [g.path for g in glsls], 'out': out.path if out else None,
             'inputs': [{'isf': n, 'par': p, 'style': s} for n, (p, s) in
                        zip([i['name'] for i in spec['inputs'] if i['type'] not in IMAGE_TYPES], in_pars)],
             'images': [{'isf': i['name'], 'type': i['type'], 'par': i['par']} for i in img_inputs],
             'slots': [{'name': s['name'], 'kind': s['kind'], 'index': s['index']} for s in spec['slots']],
             'persistent': [p['target'] for p in spec['passes'] if p['persistent']],
             'compile': {'ok': not bad, 'errors': bad[:20], 'log': log.strip()[:4000]},
             'line_note': ('log line numbers: N or 0:N = your .fs line N; 1:N = .vs line N; 90000+ = wrapper header, '
                           '100000+ = wrapper main()'),
             'panel': used_panel, 'licence': lic, 'meta': spec['meta'], 'new_ops': made,
             'warnings': spec['warnings'] + tr['warnings']}
        r.update(fin)
        if notes:
            r['notes'] = notes
        r['hint'] = ('pars: ISF page (inputs), Images page (TOP/CHOP pars; the first image input falls back to the '
                     "COMP's in1); Reset clears persistent buffers; Opencontrols opens the panel")
        return r
    return G('Pending')(max(1, int(frames)), finish)
