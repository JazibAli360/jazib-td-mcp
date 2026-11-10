"""Offline validator for builders/zk_essentials.json (the zkit default Main tab + macro knobs, no TD).

Run: cd <repo> && python3 -I -m unittest discover -s test -p 'test_zk_essentials.py'
Check a draft fragment instead: ZK_ESSENTIALS=/path/frag.json python3 -I -m unittest discover -s test -p 'test_zk_essentials.py'

Rules checked per COMP entry {"main": [...], "macros": [...], "why": "..."}:
  * main: 8-16 unique par names (or [] with a "why" that says the par names could not be determined from code);
    names look like TD custom pars (Capitalised, then lower case / digits) and are not Zkit-page pars.
  * macros: names Zkm1..Zkm4 in order (2-4 when main is not empty), a label, 2-5 drives {par, from, to}
    (numbers, from != to), no par driven twice in the COMP, optional "default" in 0..1, no menu / toggle / pulse pars.
  * every listed par name (main + drives) appears as a whole word in the COMP's builder source files (BUILDERS below).
  * best effort: when the builder spells a par as ('Name', 'Float', default, {'min': a, 'max': b}), from/to stay inside
    a..b and the macro default matches where the par default sits.
"""
import ast
import glob
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
B = os.path.join(ROOT, 'builders')
PATH = os.environ.get('ZK_ESSENTIALS') or os.path.join(B, 'zk_essentials.json')

# COMP name -> builder source globs (relative to builders/). A rack's modules live in <rack>_<module>*.py.
BUILDERS = {
    'PX_pointfx': ['px.py', 'px_logic.py', 'px_looks.py', 'px_rt.py'],
    'PX_lines': ['px_lines*.py'],
    'FX_haze': ['px_haze*.py'],
    'BL_splat_render': ['splat_render*.py'],
    'BL_cloud_morph': ['pointcloud*.py'],
    'BO_particles': ['particles*.py'],
    'MX_prox_material': ['prox_mat*.py'],
    'GN_reaction_diffusion': ['reaction_diffusion*.py'],
    'GN_physarum': ['physarum*.py'],
    'BN_cloth': ['cloth*.py'],
    'BN_fluid2d': ['fluid2d*.py'],
    'GEN_clone': ['gen_clone*.py'],
    'BK_dmx_patch': ['dmx_patch*.py', 'dmx_logic.py'],
    'BK_dmx_out': ['dmx_out.py', 'dmx_logic.py', 'dmx_rt.py'],
    'LP_laser_path': ['laser_path*.py'],
    'PV_previz_stage': ['previz_stage*.py'],
    'CQ_cuelist': ['cuelist*.py'],
    'LK_projection_room': ['projector_dome*.py'],
    'BJ_urdu_type': ['urdu_type*.py'],
    'LY_lyrics_feed': ['lyrics_feed*.py'],
    'TL_timeline': ['timeline*.py'],
    'ZK_controls_kit': ['zkit.py'],
    'AU_db_meter': ['db_meter*.py'],
    'AU_features': ['au_features*.py'],
    'AC_audio': ['ac_audio_features.py'],
    'FT_face_track': ['face_track*.py'],
    'CV_person_mask': ['person_mask*.py'],
    'DC_depth_cam': ['depth_cam*.py'],
    'BP_io_router': ['io_router*.py'],
    'ZC_control_surface': ['zctl*.py'],
    'TP_test_pattern': ['test_pattern*.py'],
    'FX_motion_trail': ['motion_trail*.py'],
    'FX_palette_map': ['palette_map*.py'],
    'FX_strobe': ['strobe*.py'],
    'FX_trans': ['fx_trans*.py'],
    'show_rig': ['show_rig*.py'],
    'review_tour': ['review_tour*.py'],
    'Effectors': ['effectors*.py'],
    'CS_cam_sequencer': ['cam_seq*.py'],
    'FG_fps_governor': ['fps_gov*.py'],
    # made ad hoc in TD, no builder in builders/: fallback entries only (empty main)
    'LK_spectrum_glass': [], 'LK_typecore': [], 'MIDI_mapper': [], 'QC_mcp_checks': [], 'BX_blender_scene': [],
}
BUILDERS['PX_pointfx1'] = BUILDERS['PX_pointfx']   # the user's copy (28 Oct) shares PX's builder
for _n in ('analog', 'destroy', 'film', 'glass', 'glitch', 'retro', 'scope', 'stylise', 'synth', 'track'):
    BUILDERS['FX_' + _n] = ['fx_%s*.py' % _n]
for _n in ('interactive', 'pattern', 'points', 'sdf', 'sim'):
    BUILDERS['GEN_' + _n] = ['gen_%s*.py' % _n]
for _n in ('branching', 'caustics', 'collide', 'crack3d', 'fillbody', 'linegrowth', 'meshwarp', 'rd3d', 'terrain',
           'tree', 'tubes'):
    BUILDERS['POP_' + _n] = ['pop_%s*.py' % _n, 'pop_common.py']
BUILDERS['POP_fillbody'].append('pop_collide_logic.py')      # its Look page is POP_collide's LOOK_PAGE

# the COMPs the user's panel rollout must cover at least (task of 28 Oct 2026)
REQUIRED = ['PX_pointfx', 'PX_lines', 'BO_particles', 'MX_prox_material', 'GN_reaction_diffusion', 'GN_physarum',
            'BN_cloth', 'GEN_clone', 'BK_dmx_patch', 'LP_laser_path', 'POP_collide', 'PV_previz_stage', 'CQ_cuelist',
            'LK_projection_room', 'BL_splat_render']

NAME_RE =re.compile(r'^[A-Z][a-z0-9]*$')
SKIP_STYLES = ('Menu', 'Toggle', 'Pulse', 'Str', 'File', 'Folder', 'TOP', 'CHOP', 'RGB', 'XYZ')
_SRC = {}


def _source(comp):
    if comp not in _SRC:
        text = []
        for pat in BUILDERS.get(comp, []):
            for f in sorted(glob.glob(os.path.join(B, pat))):
                with open(f, encoding='utf-8', errors='replace') as fh:
                    text.append(fh.read())
        _SRC[comp] = '\n'.join(text)
    return _SRC[comp]


def _has_word(src, name):
    return re.search(r'(?<![A-Za-z0-9_])' + re.escape(name) + r'(?![A-Za-z0-9_])', src, re.I) is not None


def _flt(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _px_dynamic(name):
    """PX_pointfx instance pars are generated as 'M<uid><param>' (px_logic.par_name). Resolve against the builder's
    DEFAULT_STACK (uids 1.. in order) -> (style, default, lo, hi), or None."""
    m = re.match(r'^M(\d+)([A-Za-z0-9]+)$', name)
    if not m:
        return None
    sys.path.insert(0, B)
    try:
        import px_logic as L
    finally:
        sys.path.remove(B)
    with open(os.path.join(B, 'px.py'), encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    stack = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'DEFAULT_STACK' for t in node.targets):
            stack = ast.literal_eval(node.value)
    uid, pname = int(m.group(1)), m.group(2).lower()
    if not stack or not 1 <= uid <= len(stack):
        return None
    mtype, over = stack[uid - 1]
    for p in L.HEADER + L.MODULES[mtype]['params']:
        if p['name'] == pname:
            style = {'float': 'Float', 'int': 'Int', 'toggle': 'Toggle', 'menu': 'Menu', 'xyz': 'XYZ',
                     'rgb': 'RGB'}[p['kind']]
            d = over.get(pname, p['default'])
            return (style, _flt(d), p['lo'], p['hi'])
    return None


def _specs(comp, src, name):
    """Spec spellings of a par: [(style, default or None, lo or None, hi or None)]. Tuple form
    ('Name', 'Style', default, {'min': a, 'max': b}); PX instance pars resolve through px_logic."""
    dyn = _px_dynamic(name) if comp in ('PX_pointfx', 'PX_pointfx1') else None
    if dyn:
        return [dyn]
    rx = re.compile(r"\(\s*['\"]%s['\"]\s*,\s*['\"](\w+)['\"]\s*,\s*([^,{]+?)\s*,\s*\{([^{}]*)\}" % re.escape(name))
    out = []
    for style, dflt, dtxt in rx.findall(src):
        lo = re.search(r"['\"]min['\"]\s*:\s*(-?[0-9.eE+-]+)", dtxt)
        hi = re.search(r"['\"]max['\"]\s*:\s*(-?[0-9.eE+-]+)", dtxt)
        out.append((style, _flt(dflt), _flt(lo.group(1)) if lo else None, _flt(hi.group(1)) if hi else None))
    return out


def _has_par(comp, src, name):
    return _has_word(src, name) or (comp in ('PX_pointfx', 'PX_pointfx1') and _px_dynamic(name) is not None)


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def load():
    with open(PATH, encoding='utf-8') as fh:
        return json.load(fh)


class Essentials(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()

    def test_shape(self):
        self.assertIsInstance(self.data, dict)
        self.assertGreater(len(self.data), 0)
        for comp, e in self.data.items():
            self.assertIn(comp, BUILDERS, '%s: no builder mapping in test/test_zk_essentials.py BUILDERS' % comp)
            self.assertEqual(set(e), {'main', 'macros', 'why'}, comp)
            self.assertIsInstance(e['main'], list, comp)
            self.assertIsInstance(e['macros'], list, comp)
            self.assertTrue(isinstance(e['why'], str) and e['why'].strip(), '%s: why is empty' % comp)

    @unittest.skipUnless(PATH == os.path.join(B, 'zk_essentials.json'), 'draft fragment: coverage not checked')
    def test_required_comps(self):
        for comp in REQUIRED:
            self.assertIn(comp, self.data, '%s missing from zk_essentials.json' % comp)

    def test_main(self):
        for comp, e in self.data.items():
            with self.subTest(comp=comp):
                main = e['main']
                if not main:
                    self.assertEqual(e['macros'], [], '%s: a fallback entry has no macros' % comp)
                    continue
                self.assertTrue(8 <= len(main) <= 16, '%s: %d main entries (need 8-16)' % (comp, len(main)))
                self.assertEqual(len(set(main)), len(main), '%s: duplicate main names' % comp)
                src = _source(comp)
                self.assertTrue(src, '%s: builder source not found' % comp)
                for n in main:
                    self.assertRegex(n, NAME_RE, '%s: %r is not a TD custom par name' % (comp, n))
                    if comp != 'ZK_controls_kit':
                        self.assertFalse(n.startswith('Zk') or n == 'Opencontrols', '%s: %s is a Zkit par' % (comp, n))
                    self.assertTrue(_has_par(comp, src, n), '%s: main par %s not in its builder source' % (comp, n))

    def test_macros(self):
        for comp, e in self.data.items():
            with self.subTest(comp=comp):
                macros = e['macros']
                if not e['main']:
                    continue
                self.assertLessEqual(len(macros), 4, '%s: %d macros (max 4)' % (comp, len(macros)))
                src = _source(comp)
                driven = set()
                for i, m in enumerate(macros, 1):
                    self.assertEqual(m.get('name'), 'Zkm%d' % i, '%s: macro %d name' % (comp, i))
                    self.assertTrue(isinstance(m.get('label'), str) and m['label'].strip(), '%s: macro label' % comp)
                    self.assertTrue(set(m) <= {'name', 'label', 'drives', 'default'}, '%s: macro keys %s' % (comp, set(m)))
                    drives = m.get('drives')
                    self.assertTrue(isinstance(drives, list) and 2 <= len(drives) <= 5,
                                    '%s/%s: needs 2-5 drives' % (comp, m['name']))
                    if 'default' in m:
                        self.assertTrue(_num(m['default']) and 0 <= m['default'] <= 1, '%s/%s: default' % (comp, m['name']))
                    for d in drives:
                        self.assertEqual(set(d), {'par', 'from', 'to'}, '%s/%s: drive keys' % (comp, m['name']))
                        p, a, b = d['par'], d['from'], d['to']
                        self.assertRegex(p, NAME_RE, '%s: drive par %r' % (comp, p))
                        self.assertFalse(p.startswith('Zk'), '%s: drive %s' % (comp, p))
                        self.assertTrue(_num(a) and _num(b), '%s/%s: from/to of %s must be numbers' % (comp, m['name'], p))
                        self.assertNotEqual(a, b, '%s/%s: %s from == to' % (comp, m['name'], p))
                        self.assertNotIn(p, driven, '%s: %s driven twice' % (comp, p))
                        driven.add(p)
                        self.assertTrue(_has_par(comp, src, p), '%s: drive par %s not in its builder source' % (comp, p))
                        # racks: a par name can be spelled by several modules with other ranges; one spelling
                        # (the module the entry is about) must fit, and not every spelling may be a menu / toggle
                        specs = _specs(comp, src, p)
                        if specs:
                            self.assertFalse(all(sp[0] in SKIP_STYLES for sp in specs),
                                             '%s: %s is a menu / toggle / pulse par; macros drive floats / ints only'
                                             % (comp, p))
                            fits = [sp for sp in specs if sp[0] not in SKIP_STYLES and (
                                sp[2] is None or sp[3] is None or
                                all(sp[2] - 1e-9 <= v <= sp[3] + 1e-9 for v in (a, b)))]
                            self.assertTrue(fits, '%s/%s: %s %s..%s is outside its range in every spelling %s'
                                            % (comp, m['name'], p, a, b, [(sp[2], sp[3]) for sp in specs]))

    def test_macro_default_matches_par_defaults(self):
        """Best effort: a macro's default should put each driven par near its own default (tolerance 0.15 of the span)."""
        for comp, e in self.data.items():
            src = _source(comp)
            for m in e['macros']:
                if 'default' not in m:
                    continue
                for d in m['drives']:
                    specs = [sp for sp in _specs(comp, src, d['par']) if sp[1] is not None and sp[0] not in SKIP_STYLES]
                    if not specs:
                        continue
                    v = d['from'] + (d['to'] - d['from']) * m['default']
                    span = abs(d['to'] - d['from'])
                    with self.subTest(comp=comp, macro=m['name'], par=d['par']):
                        self.assertTrue(any(abs(v - sp[1]) <= 0.15 * span + 1e-9 for sp in specs),
                                        '%s/%s: at default %.2f %s = %.4g but the par default is %s'
                                        % (comp, m['name'], m['default'], d['par'], v, [sp[1] for sp in specs]))


if __name__ == '__main__':
    unittest.main()
