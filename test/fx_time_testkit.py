"""Shared helpers for test_fx_glitch_timedisplace / timeshuffle / feedbackkill (not a test file itself).
GLSL checks compile with glslc (OpenGL target) against stubs of the TD compute declarations: a syntax/type check,
NOT a TD compile (that is LIVE CHECK 1 in each docs/builds/fx_glitch_<module>.md)."""
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
if BUILDERS not in sys.path:
    sys.path.insert(0, BUILDERS)

HAVE_GLSLC = bool(shutil.which('glslc'))

TD_STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[3];
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""


def load_module(name):
    """Exec builders/fx_glitch_<name>.py the way the rack does (HERE in its globals). TD names are not needed."""
    ns = {'HERE': BUILDERS}
    path = os.path.join(BUILDERS, 'fx_glitch_%s.py' % name)
    with open(path) as fh:
        exec(compile(fh.read(), path, 'exec'), ns)
    return ns


def source(name):
    with open(os.path.join(BUILDERS, name)) as fh:
        return fh.read()


def glslc(text):
    """Compile a compute shader body against the TD stub -> (ok, stderr)."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 's.comp')
        with open(p, 'w') as fh:
            fh.write(TD_STUB_COMPUTE + text)
        r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                            '-o', os.devnull, p], capture_output=True, text=True)
        return r.returncode == 0, r.stderr[:3000]


def declared_uniforms(text):
    return re.findall(r'^uniform vec4 (\w+);', text, re.M)


def check_module_contract(tc, ns, module):
    """Template rules (docs/builds/fx_glitch.md): MODULE, PAGES (Amount first), PANEL_PAGES, PRESETS, build."""
    tc.assertEqual(ns['MODULE'], module)
    pars = {}
    for _page, plist in ns['PAGES']:
        for name, style, default, o in plist:
            tc.assertNotIn(name, pars, 'duplicate par ' + name)
            tc.assertTrue(name[0].isupper() and name[1:] == name[1:].lower(), 'TD par name ' + name)
            pars[name] = (style, default, o)
    tc.assertEqual(ns['PAGES'][0][1][0][0], 'Amount')
    tc.assertIn('Seed', pars)
    tc.assertTrue(set(ns['PANEL_PAGES']) <= set(p for p, _ in ns['PAGES']))
    tc.assertTrue(3 <= len(ns['PRESETS']) <= 8)                    # zkit has 8 preset slots (zkit_rt.SLOTS)
    slots = set()
    for slot, pname, vals in ns['PRESETS']:
        tc.assertNotIn(slot, slots)
        slots.add(slot)
        for k, v in vals.items():
            tc.assertIn(k, pars, '%s preset %s: unknown par %s' % (module, pname, k))
            style, _d, o = pars[k]
            if style == 'Menu':
                tc.assertTrue(0 <= v < len(o['names']), '%s %s menu index %r' % (pname, k, v))
            if style == 'Toggle':
                tc.assertIn(v, (0, 1, True, False))
        tc.assertEqual(vals.get('Amount'), 1.0)
    for name, (style, default, o) in pars.items():
        if style == 'Menu':
            tc.assertIn(default, o['names'])
            tc.assertEqual(len(o['names']), len(o['labels']))
        if style in ('Float', 'Int'):
            tc.assertLess(o['min'], o['max'])
    tc.assertTrue(callable(ns['build']))
    return pars


def check_uniforms(tc, U, shader, pars):
    """Every uniform the builder sets is declared in the shader (and vice versa); expressions parse and only
    reference existing pars."""
    tc.assertEqual([u for u, _ in U], declared_uniforms(shader))
    for _u, exprs in U:
        tc.assertEqual(len(exprs), 4)
        for e in exprs:
            ast.parse(e, mode='eval')
            for ref in re.findall(r'parent\(\)\.par\.(\w+)', e):
                tc.assertIn(ref, pars, 'uniform expression references unknown par ' + ref)


def check_td_rules(tc, src):
    tc.assertNotIn('.destroy()', src)                    # safe_destroy only (T-70 / T-110)
    tc.assertNotIn('numpyArray', src)                    # no TOP readback in builders (T-74)
    tc.assertNotIn('cookRate', src)                      # never touch the project rate (T-64)
    tc.assertNotIn("mode = 'vertexpixel'", src)          # compute only (T-46/T-47)
    src.encode('ascii')                                  # files TD reads are pure ASCII (T-00a)
