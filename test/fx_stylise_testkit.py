"""Shared helpers for test_fx_stylise_* / test_fx_glass_* (not a test file itself). Builds on fx_time_testkit (glslc
against stubs of TD's compute globals: a syntax/type check, NOT a TD compile)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402


def load(module, rack='fx_stylise'):
    ns = {'HERE': K.BUILDERS}
    path = os.path.join(K.BUILDERS, '%s_%s.py' % (rack, module))
    with open(path) as fh:
        exec(compile(fh.read(), path, 'exec'), ns)
    return ns


def pars_of(ns):
    """Page defaults as the mirrors take them (menus = index, toggles = int)."""
    out = {}
    for _pg, pl in ns['PAGES']:
        for n, s, d, o in pl:
            out[n] = o['names'].index(d) if s == 'Menu' else (int(d) if s == 'Toggle' else d)
    return out


def check_module(tc, ns, module, rack='fx_stylise', extra_texts=None):
    """Template contract + full-state presets + uniforms vs shaders + TD rules + <= 3 inputs; returns pars."""
    pars = K.check_module_contract(tc, ns, module)
    keys = set(n for n, (s, _d, _o) in pars.items() if s not in ('Str', 'Pulse', 'TOP', 'CHOP'))
    for _s, name, vals in ns['PRESETS']:
        tc.assertEqual(set(vals), keys, name)                    # full state (T-124 (1))
        for k, v in vals.items():
            if pars[k][0] in ('Menu', 'Int', 'Toggle'):
                tc.assertIsInstance(v, int, (name, k))
            else:
                tc.assertIsInstance(v, float, (name, k))
    U = ns['uniforms']()
    texts = dict(ns['SHADERS'])
    texts.update(extra_texts or {})
    tc.assertEqual(set(U), set(texts))
    for name, text in texts.items():
        decl = [u for u in K.declared_uniforms(text) if u != 'uPalCtl']
        tc.assertEqual([u for u, _ in U[name]], decl, name)
        K.check_uniforms(tc, U[name], '\n'.join('uniform vec4 %s;' % u for u in decl), pars)
        tc.assertNotIn('sTD2DInputs[3]', text, name)
        text.encode('ascii')
    K.check_td_rules(tc, K.source('%s_%s.py' % (rack, module)))
    return pars


STUB = """#version 460
%s
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
uniform int uTDPass;
"""


def glslc_n(text, n):
    """glslc with sTD2DInputs[] sized to the pass's wired inputs, as TD declares it (live 31550: a shader reading
    sTD2DInputs[1] on a 1-input GLSL TOP fails 'array index out of range')."""
    import subprocess
    import tempfile
    decl = 'uniform sampler2D sTD2DInputs[%d];' % n if n > 0 else ''
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 's.comp')
        with open(p, 'w') as fh:
            fh.write(STUB % decl + text)
        r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                            '-o', os.devnull, p], capture_output=True, text=True)
        return r.returncode == 0, r.stderr[:3000]


def compile_all(tc, ns, extra_texts=None):
    """Every pass compiles with sTD2DInputs[] sized to ns['NIN'][pass] (the wired input count)."""
    texts = dict(ns['SHADERS'])
    texts.update(extra_texts or {})
    nin = ns['NIN']
    tc.assertEqual(set(nin), set(texts))
    for name, text in texts.items():
        ok, err = glslc_n(text, nin[name])
        tc.assertTrue(ok, name + ': ' + err)
