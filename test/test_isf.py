"""Offline tests for td/isf.py (td_isf: ISF -> GLSL TOP COMP) and its registration in td/handlers.py.

Real files: the MIT Vidvox ISF set in media/demo/isf/ (git-ignored; see its SOURCES.md). Those tests skip when the
folder is missing; the synthetic cases always run. No TouchDesigner (the builder runs on the fakes of
test_upgrades.py). Run: python3 -I -m unittest discover -s test -p 'test_*.py'
"""
import importlib.util
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TD_DIR = os.path.join(os.path.dirname(HERE), 'td')
ISF_DIR = os.path.join(os.path.dirname(HERE), 'media', 'demo', 'isf')
sys.path.insert(0, HERE)
import test_upgrades as TU  # noqa: E402  (stub td module, handlers, MOp fakes)

handlers = TU.handlers
OPS = TU.OPS


def load():
    spec = importlib.util.spec_from_file_location('jazib_isf_test', os.path.join(TD_DIR, 'isf.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


I = load()


def real(name):
    p = os.path.join(ISF_DIR, name)
    if not os.path.isfile(p):
        raise unittest.SkipTest('demo ISF file missing: {} (see media/demo/isf/SOURCES.md)'.format(name))
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()


GEN = '''/*{
  "DESCRIPTION": "synthetic", "CREDIT": "test", "ISFVSN": "2",
  "INPUTS": [
    {"NAME": "amount", "TYPE": "float", "MIN": 0.0, "MAX": 2.0, "DEFAULT": 0.5, "LABEL": "Amount"},
    {"NAME": "on", "TYPE": "bool", "DEFAULT": true},
    {"NAME": "kick", "TYPE": "event"},
    {"NAME": "mode", "TYPE": "long", "VALUES": [0, 1, 2], "LABELS": ["A", "B", "C"], "DEFAULT": 1},
    {"NAME": "count", "TYPE": "long", "MIN": 1, "MAX": 8, "DEFAULT": 3},
    {"NAME": "center", "TYPE": "point2D", "DEFAULT": [0.5, 0.5], "MIN": [0, 0], "MAX": [1, 1]},
    {"NAME": "tint", "TYPE": "color", "DEFAULT": [1, 0, 0]},
  ],
}*/
uniform float amount;
void main() {
  gl_FragColor = tint * amount * float(mode + count) + vec4(isf_FragNormCoord, TIME, 1.0);
}
'''


class Header(unittest.TestCase):
    def test_lenient_json_and_errors(self):
        s = I.parse_isf(GEN)  # trailing commas in the header
        self.assertEqual([i['name'] for i in s['inputs']], ['amount', 'on', 'kick', 'mode', 'count', 'center', 'tint'])
        self.assertEqual(s['meta']['credit'], 'test')
        for bad in ('void main() {}', '/* just a comment */ void main() {}', '/*{"INPUTS": 3}*/ void main(){}',
                    '/*{}*/ float f() { return 1.0; }', '/*{ "INPUTS": [{"NAME": "a b", "TYPE": "float"}] }*/void main(){}',
                    '/*{ "INPUTS": [{"NAME": "a", "TYPE": "float"}, {"NAME": "a", "TYPE": "bool"}] }*/void main(){}',
                    '/*{ "INPUTS": [{"NAME": "TIME", "TYPE": "float"}] }*/void main(){}',
                    '/*{ "PASSES": [{"TARGET": "a"}, {"TARGET": "a"}] }*/void main(){}', ''):
            with self.assertRaises(ValueError, msg=bad):
                I.parse_isf(bad)
        with self.assertRaises(ValueError):
            I.parse_isf('/*{}*/ void main() {}', 'float x;')  # .vs without main

    def test_input_normalisation(self):
        s = I.parse_isf(GEN)
        by = dict((i['name'], i) for i in s['inputs'])
        self.assertEqual((by['amount']['min'], by['amount']['max'], by['amount']['default'], by['amount']['clamp']),
                         (0.0, 2.0, 0.5, True))
        self.assertEqual(by['amount']['label'], 'Amount')
        self.assertIs(by['on']['default'], True)
        self.assertEqual((by['mode']['values'], by['mode']['labels'], by['mode']['default']), ([0, 1, 2], ['A', 'B', 'C'], 1))
        self.assertEqual((by['count']['min'], by['count']['max'], by['count']['default']), (1, 8, 3))
        self.assertEqual(by['tint']['default'], [1.0, 0.0, 0.0, 1.0], 'alpha padded')
        self.assertEqual(by['center']['max'], [1.0, 1.0])
        self.assertEqual([by[n]['par'] for n in ('amount', 'on', 'kick', 'mode', 'center')],
                         ['Amount', 'On', 'Kick', 'Mode', 'Center'])
        self.assertEqual(by['on']['uniform'], 'isf_in_on')
        self.assertEqual(by['amount']['uniform'], 'amount')
        s2 = I.parse_isf('/*{"INPUTS": [{"NAME": "x", "TYPE": "cube"}]}*/ void main() {}')
        self.assertEqual(s2['inputs'], [])
        self.assertIn('cube', s2['warnings'][0])

    def test_par_names(self):
        taken = set()
        self.assertEqual(I.par_name('blurAmount', taken), 'Bluramount')
        self.assertEqual(I.par_name('blur_amount', taken), 'Bluramount2')
        self.assertEqual(I.par_name('3d', taken), 'P3d')
        self.assertEqual(I.par_name('speed', taken), 'Speed2', 'our own Speed par is reserved')
        self.assertEqual(I.par_name('zkd', taken), 'Izkd', 'zkit names reserved')
        for n in taken:
            self.assertTrue(re.match(r'^[A-Z][a-z0-9]*$', n), n)

    def test_default_comp_name(self):
        self.assertEqual(I.default_comp_name('/a/Bad TV.fs'), 'isf_Bad_TV')
        self.assertEqual(I.default_comp_name('VVMotionBlur 3.0.fs'), 'isf_VVMotionBlur_3_0')
        self.assertEqual(I.default_comp_name(None), 'isf')


class Sizes(unittest.TestCase):
    def test_size_expressions(self):
        ins = I.parse_isf('/*{"INPUTS": [{"NAME": "blurAmount", "TYPE": "float"}, {"NAME": "img", "TYPE": "image"}]}*/'
                          'void main() {}')['inputs']
        self.assertIsNone(I.size_expr(None))
        self.assertIsNone(I.size_expr(' '))
        self.assertEqual(I.size_expr(512), '512')
        self.assertEqual(I.size_expr('512'), 'max(1, int(512))')
        self.assertEqual(I.size_expr('$WIDTH/8.0'), 'max(1, int(parent().par.Resw / 8.0))')
        self.assertEqual(I.size_expr('floor($HEIGHT*0.25)'),
                         "max(1, int(__import__('math').floor ( parent().par.Resh * 0.25 )))")
        self.assertIn('parent().par.Bluramount', I.size_expr('$blurAmount*2', ins))
        self.assertIn('**', I.size_expr('$WIDTH^0.5'))
        for bad in ('$img', '$nope', 'system(1)', '$WIDTH; import os', '__import__', 'a.b', True):
            with self.assertRaises(ValueError, msg=bad):
                I.size_expr(bad, ins)

    def test_size_expressions_evaluate(self):
        class P(object):
            Resw, Resh, Bluramount = 1080, 1920, 3.0
        env = {'parent': lambda: type('C', (), {'par': P})()}
        ins = [{'name': 'blurAmount', 'type': 'float', 'par': 'Bluramount'}]
        for ex, want in (('$WIDTH/8.0', 135), ('floor($HEIGHT*0.25)', 480), ('$blurAmount*2', 6), ('$WIDTH/4096', 1),
                         ('max($WIDTH, $HEIGHT)/2', 960)):
            self.assertEqual(eval(I.size_expr(ex, ins), env), want, ex)  # noqa: S307 (our own translated text)


class Translate(unittest.TestCase):
    def test_wrapper_generator(self):
        s = I.parse_isf(GEN)
        t = I.translate(s, GEN)
        g = t['glsl']
        self.assertTrue(g.isascii())
        self.assertIn('uniform float amount;', g)
        self.assertIn('// (declared by td_isf) uniform float amount;', g, 'the file\'s own declaration commented')
        self.assertIn('uniform float isf_in_on;\nbool on;', g)
        self.assertIn('\ton = isf_in_on > 0.5;', g)
        self.assertIn('\tmode = int(floor(isf_in_mode + 0.5));', g)
        self.assertIn('uniform vec2 center;', g)
        self.assertIn('uniform vec4 tint;', g)
        self.assertIn('isf_FragColor = tint', g)
        self.assertNotIn('gl_FragColor', g)
        self.assertIn('void isf_main()', g)
        self.assertEqual(len(re.findall(r'\bvoid\s+main\s*\(', g)), 1, 'one main: the wrapper')
        self.assertIn('#define RENDERSIZE (uTDOutputInfo.res.zw)', g)
        self.assertIn('jzFragColor = TDOutputSwizzle(isf_FragColor);', g)
        self.assertNotIn('isf_vs_main', g)
        self.assertNotIn('#version', g)
        fs_at = g.index('#line 1 0')
        self.assertEqual(g[fs_at:].split('\n')[1], '/*{', 'fs line 1 right after #line 1')
        self.assertNotIn('#define gl_', g, 'gl_ names are reserved for macros')

    def test_img_calls(self):
        fs = ('/*{"INPUTS": [{"NAME": "inputImage", "TYPE": "image"}, {"NAME": "other", "TYPE": "image"}],'
              '"PASSES": [{"TARGET": "buf", "PERSISTENT": true}, {}]}*/\n'
              'uniform sampler2D inputImage;\n'
              'void main() {\n'
              '  vec4 a = IMG_PIXEL(inputImage, gl_FragCoord.xy);\n'
              '  vec4 b = IMG_NORM_PIXEL( other , vec2(0.5, 0.5));\n'
              '  vec4 c = IMG_THIS_PIXEL(buf) + IMG_THIS_NORM_PIXEL(inputImage);\n'
              '  vec2 s = IMG_SIZE(other) + _inputImage_imgSize;\n'
              '  vec4 d = IMG_PIXEL(mystery, vec2(1.0)) + texture(inputImage, vec2(0.0));\n'
              '  vec4 other = IMG_PIXEL(other, vec2(0.5));  // a local shadows the image name (Interlace.fs)\n'
              '  gl_FragColor = a + b + c + d + vec4(s, 0, 0);\n'
              '}\n')
        s = I.parse_isf(fs)
        self.assertEqual([(x['name'], x['kind'], x['index']) for x in s['slots']],
                         [('inputImage', 'image', 0), ('other', 'image', 1), ('buf', 'target', 2)])
        t = I.translate(s, fs)
        g = t['glsl']
        self.assertIn('isf_px(0, gl_FragCoord.xy)', g)
        self.assertIn('isf_npx(1, vec2(0.5, 0.5))', g)
        self.assertIn('isf_npx(2, isf_FragNormCoord) + isf_npx(0, isf_FragNormCoord)', g)
        self.assertIn('isf_size(1)', g)
        self.assertIn('IMG_PIXEL(mystery, vec2(1.0))', g, 'unknown name left for the generic macro')
        self.assertTrue(any('mystery' in x for x in t['warnings']))
        self.assertIn('#define inputImage sTD2DInputs[0]', g)
        self.assertNotIn('#define buf ', g, 'no bare use left: no macro')
        self.assertNotIn('#define other ', g, 'declared as a local: no macro')
        self.assertIn('vec4 other = isf_px(1, vec2(0.5));', g)
        self.assertIn('// (declared by td_isf) uniform sampler2D inputImage;', g)

    def test_vs_folded(self):
        fs, vs = real('Life.fs'), real('Life.vs')
        s = I.parse_isf(fs, vs)
        t = I.translate(s, fs, vs)
        g = t['glsl']
        self.assertIn('void isf_vs_main()', g)
        self.assertIn('\tisf_vs_main();\n\tisf_main();', g)
        self.assertRegex(g, r'\n\s*vec2 left_coord;')            # .vs out -> plain global
        self.assertRegex(g, r'// \(td_isf\) in vec2 left_coord;')  # .fs in -> dropped
        self.assertRegex(g, r'// \(td_isf\) varying vec2 left_coord;')
        self.assertEqual(g.count('#line 1 1'), 1)
        self.assertLess(g.index('#line 1 1'), g.index('#line 1 0'), '.vs before .fs (its globals first)')
        self.assertEqual([w for w in t['warnings'] if 'never declares' in w], [])

    def test_vs_name_clash_renamed(self):
        fs = '/*{}*/\nfloat helper(float x) { return x; }\nin vec2 uvx;\nvoid main() { gl_FragColor = vec4(helper(uvx.x)); }\n'
        vs = 'out vec2 uvx;\nfloat helper(float x) { return 2.0 * x; }\nvoid main() { isf_vertShaderInit(); uvx = vec2(helper(1.0)); gl_Position = vec4(0.0); }\n'
        s = I.parse_isf(fs, vs)
        t = I.translate(s, fs, vs)
        self.assertEqual(t['vs_renamed'], ['helper'])
        self.assertIn('float isf_vs_helper(float x)', t['glsl'])
        self.assertIn('uvx = vec2(isf_vs_helper(1.0))', t['glsl'])
        self.assertIn('isf_Position = vec4(0.0)', t['glsl'])
        self.assertTrue(any('gl_Position' in w for w in s['warnings']))

    def test_no_vs_varyings(self):
        fs = '/*{}*/\nvarying vec2 v;\nvoid main() { gl_FragColor = vec4(v, 0.0, 1.0); }\n'
        t = I.translate(I.parse_isf(fs), fs)
        self.assertIn('\nvec2 v;', t['glsl'])
        self.assertTrue(any('no .vs' in w for w in t['warnings']))


class Passes(unittest.TestCase):
    def test_persistent_feedback_sources(self):
        fs = real('VVMotionBlur 3.0.fs')
        s = I.parse_isf(fs)
        self.assertEqual([(p['target'], p['persistent'], p['float']) for p in s['passes']],
                         [('bufferVariableNameA', True, True), (None, False, False)])
        self.assertEqual(I.pass_sources(s), [['img_inputImage', 'fb_bufferVariableNameA'],
                                             ['img_inputImage', 'pass0']])

    def test_multipass_blur(self):
        fs, vs = real('Multi Pass Gaussian Blur.fs'), real('Multi Pass Gaussian Blur.vs')
        s = I.parse_isf(fs, vs)
        n = len(s['passes'])
        self.assertGreater(n, 5)
        targets = [p['target'] for p in s['passes'] if p['target']]
        self.assertEqual(len(s['slots']), 1 + len(targets))
        src = I.pass_sources(s)
        for p in s['passes']:
            row = src[p['index']]
            for sl in s['slots']:
                if sl['kind'] == 'target':
                    want = 'pass{}'.format(sl['pass']) if sl['pass'] < p['index'] else 'isf_black'
                    self.assertEqual(row[sl['index']], want)
        for p in s['passes']:
            for key in ('width', 'height'):
                if p[key] is not None:
                    self.assertTrue(I.size_expr(p[key], s['inputs']).startswith('max(1, int('))
        g = I.translate(s, fs, vs)['glsl']
        self.assertIn('PASSINDEX = int(isf_passF + 0.5);', g)
        self.assertIn('vec2\t\ttexOffsets[5];', g)

    def test_v1_persistent_buffers(self):
        fs = '/*{"PERSISTENT_BUFFERS": ["acc"], "PASSES": [{"TARGET": "acc"}, {}]}*/ void main() { gl_FragColor = vec4(1.0); }'
        s = I.parse_isf(fs)
        self.assertTrue(s['passes'][0]['persistent'])
        self.assertEqual(s['meta']['isfvsn'], '1')

    def test_uniform_exprs(self):
        s = I.parse_isf(GEN)
        u = dict(I.uniform_exprs(s, 2))
        self.assertEqual(u['isf_passF'][0], '2')
        self.assertEqual(u['amount'], ['parent().par.Amount', '0', '0', '0'])
        self.assertEqual(u['center'][:2], ['parent().par.Centerx', 'parent().par.Centery'])
        self.assertEqual(u['tint'], ['parent().par.Tintr', 'parent().par.Tintg', 'parent().par.Tintb', 'parent().par.Tinta'])
        self.assertEqual(u['isf_in_mode'][0], 'float(parent().par.Mode.eval())')
        self.assertEqual(u['isf_in_count'][0], 'float(parent().par.Count)')
        self.assertIn("fetch('isf_ev_Kick'", u['isf_in_kick'][0])
        for name in ('TIME', 'TIMEDELTA', 'isf_frameF', 'DATE'):
            self.assertIn(name, u)
        for _n, ex in I.uniform_exprs(s, 0):
            self.assertEqual(len(ex), 4)
            for e in ex:
                compile(e, 'expr', 'eval')

    def test_audio_and_imported(self):
        fs = real('FFT Spectrogram.fs')
        s = I.parse_isf(fs)
        self.assertEqual([(x['name'], x['kind']) for x in s['slots']], [('fftImage', 'audioFFT'), ('fftValues', 'target')])
        self.assertEqual(s['passes'][0]['height'], '512')
        self.assertEqual(I.pass_sources(s)[0], ['aud_fftImage', 'fb_fftValues'])
        fs2 = ('/*{"IMPORTED": {"noise": {"PATH": "noise2d.png"}, "c": {"PATH": "x.png", "TYPE": "cube"}},'
               '"INPUTS": [{"NAME": "w", "TYPE": "audio", "MAX": 256}]}*/ void main() { gl_FragColor = IMG_NORM_PIXEL(noise, vec2(0.0)); }')
        s2 = I.parse_isf(fs2)
        self.assertEqual([(x['name'], x['kind'], x['index']) for x in s2['slots']], [('w', 'audio', 0), ('noise', 'imported', 1)])
        self.assertTrue(any('cube' in w for w in s2['warnings']))
        self.assertIn('isf_npx(1, vec2(0.0))', I.translate(s2, fs2)['glsl'])
        s3 = I.parse_isf('/*{"IMPORTED": [{"NAME": "a", "PATH": "a.png"}]}*/ void main() {}')
        self.assertEqual(s3['imported'], [{'name': 'a', 'path': 'a.png'}])


class RealFiles(unittest.TestCase):
    FILES = [('Bad TV.fs', None), ('Zoom.fs', None), ('Multi Pass Gaussian Blur.fs', 'Multi Pass Gaussian Blur.vs'),
             ('VVMotionBlur 3.0.fs', None), ('Life.fs', 'Life.vs'), ('Audio Waveform Shape.fs', None),
             ('FFT Spectrogram.fs', None), ('Kaleidoscope.fs', None), ('Tiny Date Time Overlay.fs', None),
             ('Color Replacement.fs', None), ('Simplex Noise.fs', None), ('Strobe.fs', None), ('Echo Trace.fs', None),
             ('v002-CRT-Displacement.fs', None), ('Color Bars.fs', None), ('Edges.fs', 'Edges.vs'),
             ('Dot Screen.fs', 'Dot Screen.vs'), ('Bloom.fs', 'Bloom.vs')]

    def test_every_demo_file_translates(self):
        if not os.path.isdir(ISF_DIR):
            raise unittest.SkipTest('media/demo/isf missing')
        done = 0
        for fs_name, vs_name in self.FILES:
            if not os.path.isfile(os.path.join(ISF_DIR, fs_name)):
                continue
            fs = real(fs_name)
            vs = real(vs_name) if vs_name else None
            s = I.parse_isf(fs, vs)
            t = I.translate(s, fs, vs)
            g = t['glsl']
            self.assertTrue(g.isascii() or not fs.isascii(), fs_name)
            self.assertEqual(len(re.findall(r'\bvoid\s+main\s*\(', g)), 1, fs_name)
            self.assertNotRegex(g, r'\bgl_FragColor\b', fs_name)
            if not any('not ISF images' in w for w in t['warnings']):
                self.assertNotRegex(I._strip_comments(g[g.index('#line 1 '):]), r'\bIMG_(PIXEL|NORM_PIXEL|THIS_PIXEL|THIS_NORM_PIXEL|SIZE)'
                                    r'\s*\(\s*\w', fs_name + ': every IMG_* call on a known image is a slot macro')
            self.assertEqual(g.count('{') - g.count('}'), fs.count('{') - fs.count('}') + (
                (vs.count('{') - vs.count('}')) if vs else 0), fs_name + ': braces balanced as in the source')
            for p in s['passes']:
                for key in ('width', 'height'):
                    I.size_expr(p[key], s['inputs'])
            for _n, ex in I.uniform_exprs(s, 0):
                for e in ex:
                    compile(e, fs_name, 'eval')
            done += 1
        self.assertGreater(done, 10)


TD_STUB = ('#version 460\nlayout(binding = 0) uniform sampler2D sTD2DInputs[{n}];\n'
           'struct TDTexInfo {{ vec4 res; vec4 depth; }};\nuniform TDTexInfo uTD2DInfos[{n}];\n'
           'uniform TDTexInfo uTDOutputInfo;\nvec4 TDOutputSwizzle(vec4 c) {{ return c; }}\n')


class GlslCompile(unittest.TestCase):
    """Optional: compile every demo file's translation with glslc (shaderc, if installed) behind a stub of TD's
    GLSL TOP declarations. 26 Oct: all 327 Vidvox ISF-Files .fs compile this way."""

    def test_demo_files_compile(self):
        import shutil
        import subprocess
        import tempfile
        glslc = shutil.which('glslc')
        if glslc is None or not os.path.isdir(ISF_DIR):
            raise unittest.SkipTest('glslc or media/demo/isf missing')
        with tempfile.TemporaryDirectory() as d:
            for fs_name, vs_name in RealFiles.FILES:
                if not os.path.isfile(os.path.join(ISF_DIR, fs_name)):
                    continue
                fs = real(fs_name)
                vs = real(vs_name) if vs_name else None
                s = I.parse_isf(fs, vs)
                src = TD_STUB.format(n=max(1, len(s['slots']))) + I.translate(s, fs, vs)['glsl']
                p = os.path.join(d, 't.frag')
                with open(p, 'w', encoding='utf-8') as f:
                    f.write(src)
                r = subprocess.run([glslc, '-fshader-stage=frag', '--target-env=opengl', '-fauto-map-locations',
                                    '-fauto-bind-uniforms', '-o', os.devnull, p], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, '{}: {}'.format(fs_name, r.stderr[:800]))


class Builder(unittest.TestCase):
    CLASSES = TU.CLASSES + ('feedbackTOP', 'selectCHOP', 'mathCHOP', 'choptoTOP', 'audiospectrumCHOP', 'moviefileinTOP')

    def setUp(self):
        OPS.clear()
        handlers._PENDING.clear()
        handlers._runner = lambda script, frames: None
        handlers.ISF_DIR = TD_DIR
        for n in self.CLASSES:
            cls = type(n, (), {})
            setattr(handlers.td, n, cls)
            setattr(handlers, n, cls)
        TU.N_IN.setdefault('feedbackTOP', 1)
        TU.MPar.destroy = lambda p: (p.owner.customPars.remove(p), p.owner.par._d.pop(p.name, None))
        self.root = TU.MOp(None, '/project1', 'baseCOMP')

    def tearDown(self):
        handlers._runner = None
        del TU.MPar.destroy
        for n in self.CLASSES:
            delattr(handlers, n)
            delattr(handlers.td, n)
        OPS.clear()

    def test_registered(self):
        self.assertIn('isf', handlers.COMMANDS)
        self.assertIn('isf', handlers.MUTATING)
        self.assertIn('isf', handlers.PRESAVE_CMDS)
        with open(os.path.join(TD_DIR, 'isf.py'), 'rb') as f:
            f.read().decode('ascii')

    def test_build_persistent_and_rebuild(self):
        fs = real('VVMotionBlur 3.0.fs')
        r = handlers.cmd_isf(code=fs, source_name='VVMotionBlur 3.0.fs', panel='plain', licence='MIT').finish()
        c = OPS['/project1/isf_VVMotionBlur_3_0']
        self.assertTrue(r['compile']['ok'])
        p0, p1 = c.op('pass0'), c.op('pass1')
        self.assertEqual(p0.par.pixeldat.val, 'shader')
        self.assertEqual(p0.par.format.val, 'rgba32float', 'FLOAT: true')
        self.assertEqual(handlers._inputs(p0)[:2], [c.op('img_inputImage').path, c.op('fb_bufferVariableNameA').path])
        self.assertEqual(handlers._inputs(p1)[:2], [c.op('img_inputImage').path, p0.path])
        self.assertEqual(c.op('fb_bufferVariableNameA').par.top.val, 'pass0')
        self.assertEqual(handlers._inputs(c.op('fb_bufferVariableNameA')), [c.op('clr_bufferVariableNameA').path])
        self.assertEqual(handlers._inputs(c.op('out1')), [p1.path])
        self.assertEqual(p1.par.vec0name.val, 'isf_passF')
        self.assertEqual(p1.par.vec0valuex.val, 1.0)
        self.assertIn('Bluramount', [p.name for p in c.customPars])
        self.assertIn('Inputimage', [p.name for p in c.customPars])
        self.assertIsNotNone(c.op('in1'))
        self.assertIn("op('in1')", c.op('img_inputImage').par.top.expr)
        self.assertEqual(c.par.Licence.val, 'MIT')
        self.assertEqual(c.par.Author.val, 'by zoidberg', 'CREDIT -> Credit par')
        self.assertIn('Reset', c.op('isf_events').par.pars.val)
        self.assertEqual(r['persistent'], ['bufferVariableNameA'])
        # rebuild the same COMP with a single-pass generator: stale passes, buffers, image pars go
        gen = GEN
        r2 = handlers.cmd_isf(code=gen, name='isf_VVMotionBlur_3_0', panel='plain').finish()
        self.assertIsNone(c.op('pass1'))
        self.assertIsNone(c.op('fb_bufferVariableNameA'))
        self.assertIsNone(c.op('img_inputImage'))
        self.assertIsNone(c.op('in1'))
        names = [p.name for p in c.customPars]
        self.assertNotIn('Bluramount', names)
        self.assertNotIn('Inputimage', names)
        for n in ('Amount', 'On', 'Kick', 'Mode', 'Count', 'Centerx', 'Centery', 'Tintr', 'Tinta'):
            self.assertIn(n, names)
        self.assertEqual(c.par.Mode.menuNames, ['0', '1', '2'])
        self.assertEqual(c.par.Mode.val, '1')
        self.assertIn('Kick', c.op('isf_events').par.pars.val)
        self.assertEqual(r2['inputs'][0], {'isf': 'amount', 'par': 'Amount', 'style': 'Float'})
        self.root.create(handlers.baseCOMP, 'taken')
        with self.assertRaises(ValueError):
            handlers.cmd_isf(code=gen, name='taken')
        with self.assertRaises(ValueError):
            handlers.cmd_isf(code=gen, images={'nope': '/x'})

    def test_many_slots_use_tops(self):
        fs, vs = real('Multi Pass Gaussian Blur.fs'), real('Multi Pass Gaussian Blur.vs')
        handlers.cmd_isf(code=fs, vs=vs, source_name='blur.fs', panel='plain').finish()
        c = OPS['/project1/isf_blur']
        s = I.parse_isf(fs, vs)
        last = c.op('pass{}'.format(len(s['passes']) - 1))
        row = I.pass_sources(s)[-1]
        self.assertEqual(len(handlers._inputs(last)), 3, 'T-88: 3 wired')
        self.assertEqual(last.par.tops.val, ' '.join(row[3:]))
        self.assertIsNotNone(c.op('vsource'))


if __name__ == '__main__':
    unittest.main()
