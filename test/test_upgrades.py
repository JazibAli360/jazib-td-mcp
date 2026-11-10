"""Offline tests for the 27 Oct 2026 MCP upgrades in td/handlers.py: hex colours, mirror pars, About stamp, record CHOP,
dialog guard, td_shadertoy, td_osc_expose runtime, layer mixer + cook_active (stdlib only; no TouchDesigner).

Reuses the stub `td` module and fakes of test_handlers.py (imported first).
"""
import json
import os
import tempfile
import types
import unittest

from test_handlers import OPS, OP, FakeChan, RecComp, collect, handlers


class NoShadowing(unittest.TestCase):
    def test_no_duplicate_top_level_names(self):
        """T-72: a second top-level def with the same name silently replaces the first (merges of parallel work)."""
        import ast
        import collections
        with open(handlers.__file__) as fh:
            tree = ast.parse(fh.read())
        seen = collections.Counter()
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                seen[n.name] += 1
        self.assertEqual([k for k, v in seen.items() if v > 1], [])


class Hex(unittest.TestCase):
    def test_parse_and_round_trip(self):
        self.assertEqual(handlers.hex_rgba('#00baff'), (0.0, 0.729412, 1.0, None))
        self.assertEqual(handlers.hex_rgba('#FF000080')[3], 0.501961)
        for bad in ('00baff', '#abc', '#gg0000', 'red', None, 3):
            self.assertIsNone(handlers.hex_rgba(bad), bad)
        for h in ('#00baff', '#010203', '#fefefe', '#7f8081'):
            r, g, b, _a = handlers.hex_rgba(h)
            self.assertEqual(handlers.rgb_hex(r, g, b), h)
        self.assertEqual(handlers.rgb_hex(0.5, 0.5, 0.5), '#808080', 'rounded, not truncated (127.5 -> 128)')
        self.assertEqual(handlers.rgb_hex(2, -1, 0, 1), '#ff0000ff', 'clamped')

    def test_members(self):
        names = {'colorr', 'colorg', 'colorb', 'alpha', 'bgcolorr', 'bgcolorg', 'bgcolorb', 'bgalpha',
                 'Tintr', 'Tintg', 'Tintb', 'Tinta', 'Glowr', 'Glowg', 'Glowb'}
        has = names.__contains__
        self.assertEqual(handlers.colour_members('color', has), (['colorr', 'colorg', 'colorb'], 'alpha'))
        self.assertEqual(handlers.colour_members('colorr', has), (['colorr', 'colorg', 'colorb'], 'alpha'))
        self.assertEqual(handlers.colour_members('bgcolor', has)[1], 'bgalpha')
        self.assertEqual(handlers.colour_members('Tint', has), (['Tintr', 'Tintg', 'Tintb'], 'Tinta'))
        self.assertEqual(handlers.colour_members('Glow', has), (['Glowr', 'Glowg', 'Glowb'], None))
        self.assertIsNone(handlers.colour_members('size', has))

    def test_set_pars_expands_groups(self):
        o = OP('/p/const1', 'constantTOP', pars=[{'name': n} for n in ('colorr', 'colorg', 'colorb', 'alpha')]
               + [{'name': 'text'}])
        o.par['text'].style = 'Str'
        OPS[o.path] = o
        try:
            r = handlers.cmd_set_pars('/p/const1', {'color': '#ff800080', 'text': '#ff8000'})
            self.assertEqual([o.par[n].val for n in ('colorr', 'colorg', 'colorb', 'alpha')],
                             [1.0, 0.501961, 0.0, 0.501961])
            self.assertEqual(o.par['text'].val, '#ff8000', 'a Str par keeps the text')
            self.assertEqual(r['colors']['color']['pars'], ['colorr', 'colorg', 'colorb', 'alpha'])
            o.par['colorr'].style = 'RGBA'
            handlers.cmd_set_pars('/p/const1', {'colorr': {'val': '#000000'}})
            self.assertEqual(o.par['colorg'].val, 0.0, 'a member name sets the whole group')
            with self.assertRaises(ValueError):
                handlers.cmd_set_pars('/p/const1', {'nothere': '#000000'})
        finally:
            OPS.clear()

    def test_any_member_name_and_numeric_refusal(self):
        """QC 26 Oct (live 31550): {'Glowg': '#..'} raised TD's cast error mid-apply after earlier pars were set."""
        names = {'Glowr', 'Glowg', 'Glowb', 'Tintr', 'Tintg', 'Tintb', 'Tinta'}
        has = names.__contains__
        self.assertEqual(handlers.colour_members('Glowg', has), (['Glowr', 'Glowg', 'Glowb'], None))
        self.assertEqual(handlers.colour_members('Tinta', has), (['Tintr', 'Tintg', 'Tintb'], 'Tinta'))
        o = OP('/p/g2', 'baseCOMP', pars=[{'name': n} for n in ('Glowr', 'Glowg', 'Glowb', 'Size', 'Note')])
        for n in ('Glowr', 'Glowg', 'Glowb'):
            o.par[n].style = 'RGB'
        o.par['Size'].style = 'Float'
        o.par['Note'].style = 'Str'
        OPS[o.path] = o
        try:
            r = handlers.cmd_set_pars('/p/g2', {'Glowb': '#102030cc'})
            self.assertEqual(o.par['Glowr'].val, 0.062745)
            self.assertEqual(len(r['colors']['Glowb']['values']), len(r['colors']['Glowb']['pars']),
                             'values match the pars set (no ignored alpha)')
            o.par['Note'].val = 'keep'
            for bad in ({'Note': 'x', 'Size': '#ff0000'}, {'Note': 'x', 'Glowr': '#zz0000'}):
                with self.assertRaises(ValueError):
                    handlers.cmd_set_pars('/p/g2', bad)
                self.assertEqual(o.par['Note'].val, 'keep', 'nothing set before the refusal')
        finally:
            OPS.clear()

    def test_alpha_without_par_warns(self):
        o = OP('/p/g', 'baseCOMP', pars=[{'name': n} for n in ('Glowr', 'Glowg', 'Glowb')])
        OPS[o.path] = o
        try:
            r = handlers.cmd_set_pars('/p/g', {'Glow': '#ffffff80'})
            self.assertEqual(o.par['Glowb'].val, 1.0)
            self.assertIn('no alpha', r['warnings'][0])
        finally:
            OPS.clear()


class HealthWalk(unittest.TestCase):
    def test_walk_skips_annotate_insides(self):
        """QC 26 Oct (31550): stage boxes' annotation/focusOrder filled td_health's never-cooked list."""
        root = OP('/p', 'baseCOMP', 'COMP')
        box = OP('/p/stage_A', 'annotateCOMP', 'COMP')
        sub = OP('/p/sub', 'baseCOMP', 'COMP')
        for c in (root, box, sub):
            c.isCOMP = True
        box.children = [OP('/p/stage_A/annotation', 'containerCOMP', 'COMP')]
        sub.children = [OP('/p/sub/n1')]
        root.children = [box, sub]
        got = [o.path for o in handlers._bounded_walk(root, 100)[0]]
        self.assertEqual(got, ['/p/stage_A', '/p/sub', '/p/sub/n1'])


class Mirror(unittest.TestCase):
    INFOS = [
        {'name': 'pageindex', 'tuplet': 'pageindex', 'style': 'Int', 'page': None},
        {'name': 'size', 'tuplet': 'size', 'style': 'Float', 'page': 'Blur', 'label': 'Size', 'mode': 'CONSTANT',
         'min': 0, 'max': 1},
        {'name': 'tx', 'tuplet': 't', 'style': 'XYZW', 'page': 'Transform', 'label': 'Translate'},
        {'name': 'ty', 'tuplet': 't', 'style': 'XYZW', 'page': 'Transform', 'label': 'Translate'},
        {'name': 'colorr', 'tuplet': 'color', 'style': 'RGBA', 'page': 'Blur'},
        {'name': 'colorg', 'tuplet': 'color', 'style': 'RGBA', 'page': 'Blur'},
        {'name': 'colorb', 'tuplet': 'color', 'style': 'RGBA', 'page': 'Blur'},
        {'name': 'resolutionw', 'tuplet': 'resolution', 'style': 'Int', 'page': 'Common'},
        {'name': 'resolutionh', 'tuplet': 'resolution', 'style': 'Int', 'page': 'Common'},
        {'name': 'type', 'tuplet': 'type', 'style': 'Menu', 'page': 'Blur', 'menuNames': ['a', 'b']},
        {'name': 'reset', 'tuplet': 'reset', 'style': 'Pulse', 'page': 'Blur'},
        {'name': 'cooked', 'tuplet': 'cooked', 'style': 'Float', 'page': 'Blur', 'readOnly': True},
        {'name': 'gain', 'tuplet': 'gain', 'style': 'Float', 'page': 'Blur', 'mode': 'EXPRESSION'},
        {'name': 'hdr', 'tuplet': 'hdr', 'style': 'Header', 'page': 'Blur'},
    ]

    def test_plan_groups_skips_and_styles(self):
        groups, skipped = handlers.mirror_plan(self.INFOS, exists=lambda n: n == 'Type')
        by = dict((g['cname'], g) for g in groups)
        self.assertEqual(sorted(by), ['Color', 'Reset', 'Size', 'T'])
        self.assertEqual((by['T']['append'], by['T']['members']), ('XY', ['tx', 'ty']))
        self.assertEqual(by['Color']['append'], 'RGB')
        self.assertTrue(by['Reset']['pulse'])
        why = dict((s['par'], s['why']) for s in skipped)
        self.assertIn('read-only', why['cooked'])
        self.assertIn('expression', why['gain'])
        self.assertIn('exists', why['type'])
        self.assertIn('Header', why['hdr'])
        self.assertNotIn('resolution', why, 'Common page is left out unless asked')

    def test_filters_prefix_replace(self):
        g, _s = handlers.mirror_plan(self.INFOS, patterns=['res*'], pages=['Common'], prefix='Op')
        self.assertEqual([(x['cname'], x['append'], x['size']) for x in g], [('Opresolution', 'Int', 2)])
        g, s = handlers.mirror_plan(self.INFOS, patterns=['gain'], replace_expr=True)
        self.assertEqual([x['cname'] for x in g], ['Gain'])
        self.assertEqual(handlers.mirror_custom_name('', 'blur_size'), 'Blursize')
        self.assertIsNone(handlers.mirror_custom_name('', '__'))


class About(unittest.TestCase):
    def test_values_and_bump(self):
        a = handlers.about_values(None, None, None, '2025.31550', now=0)
        self.assertEqual((a['Version'], a['Touchbuild']), ('0.1.0', '2025.31550'))
        self.assertEqual(handlers.about_values('1.2.3', bump='patch')['Version'], '1.2.4')
        self.assertEqual(handlers.about_values('1.2.3', bump='minor')['Version'], '1.3.0')
        self.assertEqual(handlers.about_values('1.2', bump='major')['Version'], '2.0.0')
        self.assertEqual(handlers.about_values('1.2.3', version='5.0.0')['Version'], '5.0.0')
        with self.assertRaises(ValueError):
            handlers.about_values('beta', bump='patch')
        with self.assertRaises(ValueError):
            handlers.about_values('1.0.0', bump='huge')


class DialogGuard(unittest.TestCase):
    def setUp(self):
        self.opened = []

        class RealUI(object):
            status = 'x'

            def messageBox(s, *a, **k):
                self.opened.append('messageBox')
                return 1

            def chooseFile(s, *a, **k):
                self.opened.append('chooseFile')
                return '/real'
        handlers.td.ui = RealUI()

    def tearDown(self):
        del handlers.td.ui
        handlers._EXEC_NS.pop('ui', None)

    def test_exec_never_opens_and_reports(self):
        r = handlers.cmd_exec("a = ui.messageBox('Delete?', 'sure', buttons=['Cancel', 'Delete'])\n"
                              "b = ui.chooseFile(load=True)\n(a, b, ui.status)")
        self.assertEqual(self.opened, [])
        self.assertEqual(r['result'], [0, None, 'x'], 'defaults; other ui attributes pass through')
        self.assertEqual([d['kind'] for d in r['dialogs']], ['messageBox', 'chooseFile'])
        self.assertIn('Delete?', r['dialogs'][0]['args'])
        r = handlers.cmd_exec("ui.messageBox('a', 'b')", dialogs={'messageBox': 1, 'chooseFolder': '/tmp'})
        self.assertEqual(r['result'], 1)
        self.assertEqual(handlers._DIALOGS['answers'], {}, 'answers do not leak into the next call')
        r = handlers.cmd_exec('1 + 1')
        self.assertNotIn('dialogs', r)

    def test_answers_checked(self):
        for bad in ({'messageBox': -1}, {'messageBox': True}, {'chooseFile': 3}, {'other': 1}, 'x'):
            with self.assertRaises(ValueError):
                handlers.check_dialog_answers(bad)


class FakeCHOP(object):
    def __init__(self, comp, name, chans):
        self.comp, self.name, self.path = comp, name, comp.path + '/' + name
        self.family, self.OPType = 'CHOP', 'nullCHOP'
        self._chans = chans
        self.nodeX = self.nodeY = 0
        self.nodeWidth, self.nodeHeight, self.dock = 130, 90, None

    def chans(self):
        return self._chans

    def parent(self):
        return self.comp

    def cook(self, force=False):
        pass


class RecordChop(unittest.TestCase):
    def setUp(self):
        handlers._PENDING.clear()
        handlers._runner = lambda script, frames: None
        handlers.tableDAT = 'tableDAT'
        self.comp = RecComp('/p')
        OPS['/p'] = self.comp
        self.v = [0.0]
        chans = [FakeChan('kick', []), FakeChan('snare', []), FakeChan('tx', [])]
        chans[0].eval = lambda: self.v[0]
        chans[1].eval = lambda: self.v[0] * 2
        chans[2].eval = lambda: 9.0
        self.chop = FakeCHOP(self.comp, 'audio', chans)
        self.comp.children.append(self.chop)
        OPS[self.chop.path] = self.chop
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        handlers._runner = None
        del handlers.tableDAT
        OPS.clear()

    def test_frames_to_table_and_csv(self):
        out, send = collect()
        f = os.path.join(self.tmp, 'rec', 'a.csv')
        handlers.dispatch(json.dumps({'id': 5, 'cmd': 'record_chop', 'args': {
            'chop': '/p/audio', 'frames': 3, 'channels': 'kick snare', 'file': f}}), send)
        self.assertEqual(out, [])
        for k in range(3):
            handlers.absTime.frame = 10 + k
            self.v[0] = float(k)
            handlers._finish(5)
        self.assertTrue(out[0]['ok'], out[0])
        r = out[0]['result']
        self.assertEqual((r['frames'], r['channels'], r['table']), (3, 2, '/p/audio_rec'))
        t = self.comp.op('audio_rec')
        self.assertEqual(t.text.splitlines()[0], 'frame\ttime\tkick\tsnare')
        self.assertEqual(t.text.splitlines()[3].split('\t')[2:], ['2.0', '4.0'])
        with open(f) as fh:
            lines = fh.read().splitlines()
        self.assertEqual(lines[0], 'frame,time,"kick","snare"')
        self.assertEqual(len(lines), 4)
        self.assertNotIn('notes', r)

    def test_refusals(self):
        for args in ({'chop': '/p/audio'}, {'chop': '/p/audio', 'frames': 2, 'seconds': 1},
                     {'chop': '/p/audio', 'frames': 0}, {'chop': '/p/audio', 'frames': 2, 'channels': 'zz*'},
                     {'chop': '/p/audio', 'frames': 2, 'file': 'rel.csv'},
                     {'chop': '/p/audio', 'frames': 2, 'table': 'bad name'}):
            with self.assertRaises(ValueError, msg=str(args)):
                handlers.cmd_record_chop(**args)
        self.assertIn('record_chop', handlers.MUTATING)


SHADER = '''// a comment with iChannel3 does not count
#version 300 es
uniform vec3 iResolution;
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    fragColor = texture(iChannel1, uv) * vec4(uv, 0.5 + 0.5 * sin(iTime), 1.0);
}
'''


class Shadertoy(unittest.TestCase):
    def test_scan(self):
        s = handlers.shadertoy_scan(SHADER)
        self.assertEqual(s['channels'], [1])
        self.assertEqual(len(s['warnings']), 2)  # #version, uniform declaration
        with self.assertRaises(ValueError):
            handlers.shadertoy_scan('void main() { gl_FragColor = vec4(1.0); }')
        with self.assertRaises(ValueError):
            handlers.shadertoy_scan('void mainImage(out vec4 c, in vec2 p) {}\nvoid main() {}')
        cube = handlers.shadertoy_scan('uniform samplerCube x;\nvoid mainImage(out vec4 c, in vec2 p) {}')
        self.assertIn('cubemap', cube['warnings'][0])

    def test_wrap_pixel_and_compute(self):
        txt, head = handlers.shadertoy_wrap(SHADER, 2, False)
        lines = txt.splitlines()
        self.assertEqual(lines[head - 1], '#line 1', 'user code starts at line 1 of the compile log')
        self.assertIn('#define iChannel1 sTD2DInputs[1]', txt)
        self.assertNotIn('iChannel2 sTD2DInputs', txt)
        self.assertIn('iChannelResolution[1] = vec3(uTD2DInfos[1].res.zw, 1.0);', txt)
        self.assertIn('jzFragColor = TDOutputSwizzle(c);', txt)
        self.assertIn('// (declared by td_shadertoy) uniform vec3 iResolution;', txt)
        self.assertNotIn('\n#version', txt)
        ctxt, _h = handlers.shadertoy_wrap(SHADER, 0, True)
        self.assertIn('layout (local_size_x = 8, local_size_y = 8) in;', ctxt)
        self.assertIn('TDImageStoreOutput(0, ivec3(gl_GlobalInvocationID), c);', ctxt)
        self.assertNotIn('uTD2DInfos', ctxt)
        txt.encode('ascii')

    def test_uniform_exprs_compile(self):
        names = [n for n, _e in handlers.shadertoy_uniform_exprs()]
        self.assertEqual(tuple(names), handlers.ST_UNIFORMS)
        for _n, ex in handlers.shadertoy_uniform_exprs():
            for e in ex:
                compile(e, 'expr', 'eval')

    def test_registered(self):
        for c in ('shadertoy', 'osc_expose', 'layer_mixer', 'cook_active', 'record_chop'):
            self.assertIn(c, handlers.COMMANDS)
            self.assertIn(c, handlers.MUTATING)


def osc_rt():
    ns = {}
    exec(compile(handlers.OSCX_RT, 'osc_rt', 'exec'), ns)
    return ns


class FakeTable(object):
    def __init__(self, rows):
        self.rows = rows

    @property
    def numRows(self):
        return len(self.rows)

    def row(self, i):
        return [types.SimpleNamespace(val=v) for v in self.rows[i]]


class TPar(object):
    def __init__(self, name, val=0.0):
        self.name, self.val, self.pulsed = name, val, 0

    def eval(self):
        return self.val

    def pulse(self):
        self.pulsed += 1


class OscExpose(unittest.TestCase):
    def test_addresses_and_plan(self):
        rt = osc_rt()
        self.assertEqual(rt['addresses']('look1', 'Speed', 'Float', 'plain'), ('/look1/Speed', '/look1/Speed'))
        self.assertEqual(rt['addresses']('/show/look 1', 'Tint', 'RGB', 'osct'),
                         ('/OSCT/R/COLOR/show_look_1_Tint', '/OSCT/S/COLOR/show_look_1_Tint'))
        groups = [{'par': 'Speed', 'members': ['Speed'], 'style': 'Float', 'page': 'Look', 'min': 0, 'max': 2},
                  {'par': 'Tint', 'members': ['Tintr', 'Tintg', 'Tintb'], 'style': 'RGB', 'page': 'Look'},
                  {'par': 'Mode', 'members': ['Mode'], 'style': 'Menu', 'page': 'Look', 'menu': ['a', 'b']},
                  {'par': 'Size', 'members': ['Size1', 'Size2'], 'style': 'Int', 'page': 'Look'},
                  {'par': 'Src', 'members': ['Src'], 'style': 'TOP', 'page': 'Look'},
                  {'par': 'Opencontrols', 'members': ['Opencontrols'], 'style': 'Pulse', 'page': 'Controls'}]
        rows, skipped = rt['plan'](groups, 'look1', 'plain')
        self.assertEqual([(r[2], r[5]) for r in rows], [('Speed', 'f'), ('Tint', 'fff'), ('Mode', 's'), ('Size', 'ii')])
        self.assertEqual(skipped, [['Src', 'style TOP']])
        rows2, _s = rt['plan'](groups, 'look1', 'plain', pats=['T*'])
        self.assertEqual([r[2] for r in rows2], ['Tint'])

    def test_encode_decode(self):
        rt = osc_rt()
        enc, dec = rt['encode'], rt['decode']
        self.assertEqual(enc('Toggle', [True]), [1])
        self.assertEqual(enc('Pulse', [], 'osct'), [])
        self.assertEqual(enc('RGB', [1, 0, 0], 'osct'), [1.0, 0.0, 0.0, 1.0])
        self.assertEqual(enc('Menu', ['b']), ['b'])
        self.assertEqual(dec('Toggle', ['true']), [True])
        self.assertEqual(dec('Int', [2.6]), [3])
        self.assertEqual(dec('Menu', [1], 1, ['a', 'b']), ['b'])
        self.assertEqual(dec('Menu', ['a'], 1, ['a', 'b']), ['a'])
        self.assertEqual(dec('RGB', [0.1, 0.2, 0.3, 1.0], 3), [0.1, 0.2, 0.3])
        for args in (('Toggle', ['maybe']), ('Menu', ['zz'], 1, ['a']), ('RGB', [0.1], 3), ('Float', ['x'])):
            with self.assertRaises(ValueError):
                dec(*args)

    def test_query_tree_and_loopback(self):
        rt = osc_rt()
        rows = [['/look1/Speed', '/look1/Speed', 'Speed', 'Speed', 'Float', 'f', 0, 2, '', 'Speed'],
                ['/look1/Mode', '/look1/Mode', 'Mode', 'Mode', 'Menu', 's', '', '', 'a b', 'Mode']]
        t = rt['query_tree'](rows, {'Speed': 1.5, 'Mode': 'a'}, 'look1_osc', True)
        leaf = t['CONTENTS']['look1']['CONTENTS']['Speed']
        self.assertEqual((leaf['TYPE'], leaf['VALUE'], leaf['ACCESS']), ('f', 1.5, 3))
        self.assertEqual(t['CONTENTS']['look1']['CONTENTS']['Mode']['RANGE'], [{'VALS': ['a', 'b']}])
        json.dumps(t)
        self.assertTrue(rt['is_loopback']('127.0.0.1') and rt['is_loopback']('::1'))
        self.assertFalse(rt['is_loopback']('192.168.1.5'))
        self.assertEqual(rt['host_info']('x', 9001, False).get('OSC_PORT'), None)

    def test_on_receive_allow_list(self):
        rt = osc_rt()
        pars = {n: TPar(n) for n in ('Speed', 'Tintr', 'Tintg', 'Tintb', 'Go')}
        tgt = types.SimpleNamespace(par=type('P', (), {'__getitem__': lambda s, k: pars.get(k)})())
        store = {}
        table = FakeTable([['h'] * 10,
                           ['/l/Speed', '/l/Speed', 'Speed', 'Speed', 'Float', 'f', '0', '2', '', 'Speed'],
                           ['/l/Tint', '/l/Tint', 'Tint', 'Tintr Tintg Tintb', 'RGB', 'fff', '', '', '', 'Tint'],
                           ['/l/Go', '/l/Go', 'Go', 'Go', 'Pulse', 'I', '', '', '', 'Go']])
        c = types.SimpleNamespace(
            par=types.SimpleNamespace(Target=types.SimpleNamespace(eval=lambda: tgt),
                                      Active=types.SimpleNamespace(eval=lambda: True)),
            op=lambda n: table if n == 'map' else None,
            fetch=lambda k, d=None, search=False: store.get(k, d), store=lambda k, v: store.__setitem__(k, v))
        self.assertTrue(rt['on_receive'](c, '/l/Speed', [1.25]))
        self.assertEqual(pars['Speed'].val, 1.25)
        self.assertTrue(rt['on_receive'](c, '/l/Tint', [0.1, 0.2, 0.3]))
        self.assertEqual([pars[n].val for n in ('Tintr', 'Tintg', 'Tintb')], [0.1, 0.2, 0.3])
        self.assertTrue(rt['on_receive'](c, '/l/Go', []))
        self.assertEqual(pars['Go'].pulsed, 1)
        self.assertFalse(rt['on_receive'](c, '/l/exec', ['import os']), 'unknown address: ignored')
        self.assertFalse(rt['on_receive'](c, '/l/Speed', ['fast']), 'bad value: refused')
        st = store['jz_osc_stats']
        self.assertEqual((st['written'], st['ignored'], st['bad']), (3, 1, 1))
        # echo guard: the 3 value changes of the RGB write are muted, the next real change is marked
        for n in ('Tintr', 'Tintg', 'Tintb'):
            rt['on_value'](c, types.SimpleNamespace(tupletName='Tint', name=n))
        self.assertNotIn('Tint', store.get('jz_osc_dirty', []))
        rt['on_value'](c, types.SimpleNamespace(tupletName='Tint', name='Tintr'))
        self.assertIn('Tint', store['jz_osc_dirty'])
        handlers.OSCX_RT.encode('ascii')

    def test_refusals(self):
        t = OP('/p/look', 'baseCOMP')
        t.isCOMP = True
        OPS['/p/look'] = t
        try:
            for kw in ({'layout': 'nope'}, {'port': 70000}, {'rate_hz': 0}):
                with self.assertRaises(ValueError, msg=str(kw)):
                    handlers.cmd_osc_expose('/p/look', **kw)
        finally:
            OPS.clear()


class Mixer(unittest.TestCase):
    def ev(self, expr, **pars):
        P = types.SimpleNamespace(par=types.SimpleNamespace(**pars))
        return eval(expr, {'parent': lambda: P})

    def test_eff_expr_mute_solo(self):
        e2 = handlers.mixer_eff_expr(2, 3)
        base = dict(L1opacity=1, L2opacity=0.5, L3opacity=1, L1mute=0, L2mute=0, L3mute=0, L1solo=0, L2solo=0,
                    L3solo=0)
        self.assertEqual(self.ev(e2, **base), 0.5)
        self.assertEqual(self.ev(e2, **dict(base, L2mute=1)), 0)
        self.assertEqual(self.ev(e2, **dict(base, L3solo=1)), 0, 'another layer soloed')
        self.assertEqual(self.ev(e2, **dict(base, L2solo=1, L3solo=1)), 0.5)

    def test_rt_active_sources(self):
        ns = {}
        exec(compile(handlers.MIX_RT, 'mix_rt', 'exec'), ns)
        vals = dict(L1opacity=1.0, L2opacity=0.0, L3opacity=0.7, L1mute=False, L2mute=False, L3mute=True,
                    L1solo=False, L2solo=False, L3solo=False)
        src = {1: 2, 2: 0, 3: 1}

        class Pars(object):
            def __getitem__(self, k):
                if k.endswith('source'):
                    return types.SimpleNamespace(menuIndex=src[int(k[1:-6])])
                return types.SimpleNamespace(eval=lambda: vals[k])
        c = types.SimpleNamespace(par=Pars(), fetch=lambda k, d=None, search=False: 3)
        self.assertEqual(ns['active_sources'](c), [2])
        vals['L3mute'] = False
        self.assertEqual(ns['active_sources'](c), [1, 2])
        vals['L1solo'] = True
        self.assertEqual(ns['active_sources'](c), [2])
        handlers.MIX_RT.encode('ascii')

    def test_source_rows_and_split(self):
        rows = handlers.mixer_source_rows([('/p/a', 'baseCOMP', '/p/a/out1'), ('/p/n', 'noiseTOP', '/p/n')])
        self.assertEqual(rows[1], [0, 'a', '/p/a', '/p/a/out1', '1'])
        self.assertEqual(rows[2][4], '0')
        on, off, unknown = handlers.cook_split([('a', '/p/a'), ('b', '/p/b'), ('c', '/p/c')], ['b', '/p/c', 'zz'])
        self.assertEqual((on, off, unknown), (['/p/b', '/p/c'], ['/p/a'], ['zz']))

    def test_refusals(self):
        for kw in ({'layers': 0}, {'layers': 17}, {'blend': 'nope'}, {'fit': 'x'}, {'res': [1]}, {'sources': 'x'}):
            with self.assertRaises(ValueError, msg=str(kw)):
                handlers.cmd_layer_mixer(**kw)
        with self.assertRaises(ValueError):
            handlers.cmd_cook_active(active=['a'])  # neither paths nor parent


# ---------------------------------------------------------------- a fuller fake TD for the builders
MULTI_IN = ('switchTOP', 'compositeTOP')
N_IN = {'glslTOP': 3, 'crossTOP': 2, 'selectTOP': 0, 'constantTOP': 0, 'textDAT': 0, 'tableDAT': 0,
        'constantCHOP': 0, 'parameterCOMP': 0, 'windowCOMP': 0, 'parameterexecuteDAT': 0, 'executeDAT': 0,
        'oscoutDAT': 0, 'oscinDAT': 0, 'webserverDAT': 0, 'inTOP': 0}
SUFFIX = {'XY': 'xy', 'XYZ': 'xyz', 'XYZW': 'xyzw', 'UV': 'uv', 'UVW': 'uvw', 'WH': 'wh', 'RGB': 'rgb', 'RGBA': 'rgba'}


class MPar(object):
    def __init__(self, owner, name, style='Float', custom=False, tuplet=None, page='', label=None):
        self.owner, self.name, self.style, self.isCustom = owner, name, style, custom
        self.tupletName, self.page, self.label = tuplet or name, types.SimpleNamespace(name=page), label or name
        self.val, self.default, self.expr, self.bindExpr = 0, 0, '', ''
        self.mode = handlers.ParMode.CONSTANT
        self.menuNames, self.menuLabels, self.pulsed = [], [], 0
        self.isMenu = style in ('Menu', 'StrMenu')
        self.isPulse = style == 'Pulse'
        self.isNumber = style in ('Float', 'Int') or style in SUFFIX
        self.readOnly = False
        self.normMin, self.normMax, self.min, self.max, self.clampMin, self.clampMax = 0, 1, 0, 1, False, False

    @property
    def menuIndex(self):
        return self.menuNames.index(self.val) if self.val in self.menuNames else 0

    def eval(self):
        return self.val

    def pulse(self):
        self.pulsed += 1


class MPars(object):
    def __init__(self, owner):
        object.__setattr__(self, '_owner', owner)
        object.__setattr__(self, '_d', {})

    def __getitem__(self, k):
        if k in self._d:
            return self._d[k]
        if k[:1].islower():  # builtin pars exist on demand; custom ones (Capital) only once appended
            self._d[k] = MPar(self._owner, k)
            return self._d[k]
        return None

    def __getattr__(self, k):
        p = self[k]
        if p is None:
            raise AttributeError(k)
        return p


class MPage(object):
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def __getattr__(self, attr):
        if not attr.startswith('append'):
            raise AttributeError(attr)
        style = attr[6:]

        def append(name, label=None, size=1):
            sufs = list(SUFFIX.get(style, '')) or ([''] if size == 1 else [str(i + 1) for i in range(size)])
            out = []
            for s_ in sufs:
                p = MPar(self.owner, name + s_, style, True, name, self.name, label)
                self.owner.par._d[p.name] = p
                self.owner.customPars.append(p)
                out.append(p)
            return out
        return append

    def destroy(self):
        self.owner.customPages.remove(self)
        for p in [p for p in self.owner.customPars if p.page.name == self.name]:
            self.owner.customPars.remove(p)
            self.owner.par._d.pop(p.name, None)


class MConn(object):
    def __init__(self, owner, index, is_input):
        self.owner, self.index, self.is_input, self.connections = owner, index, is_input, []

    def connect(self, other):
        src, dst = (self, other) if not self.is_input else (other, self)
        dst.connections = [src]
        src.connections.append(dst)
        o = dst.owner
        if o.OPType in MULTI_IN and dst.index == len(o.inputConnectors) - 1:
            o.inputConnectors.append(MConn(o, len(o.inputConnectors), True))

    def disconnect(self):
        self.connections = []


class MOp(object):
    def __init__(self, parent, name, optype):
        self._parent, self.name, self.OPType = parent, name, optype
        self.path = (parent.path.rstrip('/') + '/' + name) if parent is not None else name
        fam = [f for f in ('TOP', 'CHOP', 'SOP', 'DAT', 'COMP', 'MAT') if optype.endswith(f)]
        self.family = fam[0] if fam else 'COMP'
        self.isCOMP = self.family == 'COMP'
        self.children, self.customPages, self.customPars, self._store = [], [], [], {}
        self.par = MPars(self)
        n = N_IN.get(optype, 1)
        self.inputConnectors = [MConn(self, i, True) for i in range(n)]
        self.outputConnectors = [MConn(self, 0, False)]
        self.valid, self.viewer, self.allowCooking, self.dock, self.comment = True, False, True, None, ''
        self.id = id(self)
        self.nodeX = self.nodeY = 0
        self.nodeWidth, self.nodeHeight = 130, 90
        self.seq = types.SimpleNamespace(vec=types.SimpleNamespace(numBlocks=0),
                                         const=types.SimpleNamespace(numBlocks=1))
        self.text = ''
        OPS[self.path] = self

    def parent(self, n=1):
        return self._parent

    def create(self, cls, name):
        o = MOp(self, name, cls.__name__ if isinstance(cls, type) else str(cls))
        self.children.append(o)
        return o

    def op(self, rel):
        cur = self
        for part in rel.split('/'):
            cur = next((c for c in cur.children if c.name == part and c.valid), None) if cur is not None else None
        return cur

    def findChildren(self, type=None):
        out = []
        for c in self.children:
            out.append(c)
            out += c.findChildren()
        return out

    def appendCustomPage(self, name):
        pg = MPage(self, name)
        self.customPages.append(pg)
        return pg

    def store(self, k, v):
        self._store[k] = v

    def fetch(self, k, d=None, search=True):
        return self._store.get(k, d)

    def unstore(self, k):
        self._store.pop(k, None)

    def destroy(self):
        self.valid = False
        if self._parent is not None and self in self._parent.children:
            self._parent.children.remove(self)
        OPS.pop(self.path, None)

    def cook(self, force=False):
        pass

    def errors(self):
        return ''

    def warnings(self):
        return ''

    # Table DAT
    @property
    def numRows(self):
        return len([ln for ln in self.text.split('\n') if ln]) if self.text else 0

    def row(self, i):
        return [types.SimpleNamespace(val=v) for v in self.text.split('\n')[i].split('\t')]

    def __getitem__(self, rc):
        r, col = rc
        head = self.text.split('\n')[0].split('\t')
        return types.SimpleNamespace(val=self.text.split('\n')[r].split('\t')[head.index(col)])

    def clear(self):
        self.text = ''

    def appendRow(self, cells):
        line = '\t'.join(str(c) for c in cells)
        self.text = (self.text + '\n' + line) if self.text else line

    @property
    def module(self):
        ns = {'op': OPS.get, '__name__': self.name}
        exec(compile(self.text, self.path, 'exec'), ns)
        return types.SimpleNamespace(**ns)


def real_notes(r):
    """Builder notes minus the fake's own gap (its builtin pars are never menus)."""
    return [n for n in r.get('notes', []) if 'not a menu parameter' not in n]


CLASSES = ('baseCOMP', 'textDAT', 'tableDAT', 'constantTOP', 'selectTOP', 'constantCHOP', 'speedCHOP', 'glslTOP',
           'outTOP', 'inTOP', 'parameterCOMP', 'windowCOMP', 'parameterexecuteDAT', 'executeDAT', 'oscoutDAT',
           'oscinDAT', 'webserverDAT', 'switchTOP', 'compositeTOP', 'crossTOP')


class Builders(unittest.TestCase):
    def setUp(self):
        OPS.clear()
        handlers._PENDING.clear()
        handlers._runner = lambda script, frames: None
        for n in CLASSES:
            cls = type(n, (), {})
            setattr(handlers.td, n, cls)
            setattr(handlers, n, cls)
        self.root = MOp(None, '/project1', 'baseCOMP')

    def tearDown(self):
        handlers._runner = None
        for n in CLASSES:
            delattr(handlers, n)
            delattr(handlers.td, n)
        OPS.clear()

    def test_shadertoy_build_and_rebuild(self):
        p = handlers.cmd_shadertoy(SHADER, compute=False, licence='CC BY-NC-SA 3.0', author='me')
        r = p.finish()
        c = OPS['/project1/shadertoy']
        g = c.op('glsl')
        self.assertEqual(r['inputs'], 2)
        self.assertTrue(r['compile']['ok'])
        self.assertEqual(g.par.pixeldat.val, 'shader')
        self.assertEqual(g.seq.vec.numBlocks, 7)
        self.assertEqual(g.par.vec1name.val, 'iTime')
        self.assertEqual(handlers._inputs(g)[:2], ['/project1/shadertoy/ichannel0', '/project1/shadertoy/ichannel1'])
        self.assertEqual(handlers._inputs(c.op('out1')), [g.path])
        self.assertEqual(c.par.Licence.val, 'CC BY-NC-SA 3.0')
        self.assertIn('CC BY-NC-SA 3.0', c.op('source').text)
        self.assertEqual(c.par.Version.val, '0.1.0')
        self.assertIn('Opencontrols', c.op('controls_exec').par.pars.val)
        self.assertEqual(real_notes(r), [])
        r2 = handlers.cmd_shadertoy(SHADER.replace('iChannel1', 'iChannel0'), compute=True).finish()
        self.assertEqual(r2['new_ops'], [], 'rebuild in place')
        self.assertIsNone(c.op('ichannel1'))
        self.assertEqual(g.par.computedat.val, 'shader')
        self.assertEqual(g.par.pixeldat.val, '')
        self.root.create(handlers.baseCOMP, 'taken')
        with self.assertRaises(ValueError):
            handlers.cmd_shadertoy(SHADER, name='taken')

    def test_osc_expose_build(self):
        t = self.root.create(handlers.baseCOMP, 'look1')
        pg = t.appendCustomPage('Look')
        pg.appendFloat('Speed')
        pg.appendRGB('Tint')
        m = pg.appendMenu('Mode')[0]
        m.menuNames = ['a', 'b']
        r = handlers.cmd_osc_expose('/project1/look1')
        c = OPS['/project1/look1_osc']
        self.assertEqual(r['count'], 3, r)
        self.assertEqual([a['send'] for a in r['addresses']], ['/look1/Speed', '/look1/Tint', '/look1/Mode'])
        self.assertFalse(c.par.Active.val or c.par.Receive.val or c.par.Oscquery.val, 'all traffic off by default')
        self.assertEqual(c.op('osc_in').par.callbacks.val, 'osc_in_cb')
        self.assertEqual(json.loads(c.op('oscquery').text)['CONTENTS']['look1']['CONTENTS']['Speed']['TYPE'], 'f')
        self.assertEqual(real_notes(r), [])
        r2 = handlers.cmd_osc_expose('/project1/look1', layout='osct', pars=['T*'])
        self.assertEqual([a['send'] for a in r2['addresses']], ['/OSCT/R/COLOR/look1_Tint'])
        self.assertEqual(r2['send']['port'], 9999)

    def test_layer_mixer_build_shrink_and_guard(self):
        gen = self.root.create(handlers.baseCOMP, 'gen1')
        gen.create(handlers.outTOP, 'out1')
        self.root.create(handlers.constantTOP, 'const1')
        r = handlers.cmd_layer_mixer(layers=3, sources=['/project1/gen1', '/project1/const1'])
        c = OPS['/project1/mixer']
        self.assertEqual([s['top'] for s in r['sources']], ['/project1/gen1/out1', '/project1/const1'])
        self.assertEqual(c.par.L1source.menuNames, ['src0', 'src1'])
        self.assertEqual(handlers._inputs(c.op('l1_switch'))[:2], ['/project1/mixer/src0', '/project1/mixer/src1'])
        self.assertEqual(handlers._inputs(c.op('l2_comp'))[:2], ['/project1/mixer/l2_switch', '/project1/mixer/l1_gate'])
        self.assertEqual(handlers._inputs(c.op('out1')), ['/project1/mixer/master'])
        self.assertIn('L3solo', c.op('l1_mix').par.cross.expr)
        self.assertEqual(r['cook_guard'], {'on': ['/project1/gen1'], 'off': []}, 'layer 1 shows gen1')
        c.par.L1opacity.val = 0.0
        self.assertEqual(c.op('runtime').module.apply(c), {'on': [], 'off': ['/project1/gen1']})
        self.assertFalse(gen.allowCooking)
        self.assertEqual(real_notes(r), [])
        class Dead(MOp):  # TD: any attribute of a destroyed op raises (QC 26 Oct: removed.append(o.name) after it)
            def __getattribute__(self, k):
                if k in ('name', 'OPType', 'id') and not object.__getattribute__(self, 'valid'):
                    raise RuntimeError('tdError: invalid OP')
                return object.__getattribute__(self, k)
        for s in ('switch', 'comp', 'mix', 'gate'):
            c.op('l3_' + s).__class__ = Dead
        r2 = handlers.cmd_layer_mixer(layers=2)
        self.assertIsNone(c.op('l3_gate'))
        self.assertIsNone(c.par['L3opacity'])
        self.assertEqual(sorted(r2['removed']), ['l3_comp', 'l3_gate', 'l3_mix', 'l3_switch'])
        self.assertNotIn('L3solo', c.op('l1_mix').par.cross.expr)

    def test_cook_active(self):
        for n in ('a', 'b', 'c'):
            self.root.create(handlers.baseCOMP, n)
        r = handlers.cmd_cook_active(active=['b'], parent='/project1')
        self.assertEqual((r['on'], r['off']), (['/project1/b'], ['/project1/a', '/project1/c']))
        self.assertFalse(OPS['/project1/a'].allowCooking)
        with self.assertRaises(ValueError):
            handlers.cmd_cook_active(active=['zz'], parent='/project1')

    def test_cook_active_skips_top_level(self):
        # QC 26 Oct: paths ['/project1'] with active [] switched the whole project off
        self.root.create(handlers.baseCOMP, 'a')
        r = handlers.cmd_cook_active(active=[], paths=['/project1', '/project1/a'])
        self.assertEqual(r['off'], ['/project1/a'])
        self.assertIn('/project1', r['skipped'])
        self.assertTrue(handlers._cook_guard_skip('/project1'))
        self.assertFalse(handlers._cook_guard_skip('/project1/lab/x'))

    def test_mirror_on_fake_comp(self):
        c = self.root.create(handlers.baseCOMP, 'fx')
        inner = c.create(handlers.constantTOP, 'gen')
        for n, st, tp, pg in (('amp', 'Float', 'amp', 'Noise'), ('tx', 'XYZW', 't', 'Transform'),
                              ('ty', 'XYZW', 't', 'Transform'), ('resetpulse', 'Pulse', 'resetpulse', 'Noise')):
            p = MPar(inner, n, st, False, tp, pg)
            p.val = 0.25
            inner.par._d[n] = p
        inner.pars = lambda: list(inner.par._d.values())
        r = handlers.cmd_custom_pars('/project1/fx', 'Noise', mirror={'src': 'gen'})
        self.assertEqual(sorted(x['name'] for x in r['mirrored']), ['Amp', 'Resetpulse', 'T'])
        self.assertEqual(inner.par.amp.bindExpr, 'parent(1).par.Amp')
        self.assertEqual(c.par.Amp.val, 0.25)
        self.assertEqual(inner.par.ty.bindExpr, 'parent(1).par.Ty')
        self.assertEqual(c.fetch('jz_mirror_pulses'), {'Resetpulse': ['gen', 'resetpulse']})
        self.assertIn('Resetpulse', c.op('mirror_pulse').par.pars.val)
        with self.assertRaises(ValueError):
            handlers.cmd_custom_pars('/project1/fx', 'X', mirror={'src': '/project1'})


if __name__ == '__main__':
    unittest.main()
