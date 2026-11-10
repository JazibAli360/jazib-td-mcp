# fx_stylise_pal - the W1-B palette (docs/builds/palette_convention.md) for FX_stylise / FX_glass modules that colour
# something (outline, saber, ink, foil ...). Shared by 2+ modules (no-bloat rule). A module execs this file into its
# own namespace (it needs HERE), adds PAL_PAGE to its PAGES and calls pal_bind(m, H, [glsl ops]) in build():
#   Script CHOP `pal` (16 samples r g b pos, recooks on palette par edits) + docked `pal_callbacks`;
#   every listed GLSL op gets Arrays `uPal` (uniformarray) + Vectors `uPalCtl` (count, Palshift, Palmode, Palinterp).
# The palette logic is the rack's Text DAT `palette_map_logic` (parent(2) of an op in the module). Shaders prepend
# PAL_GLSL (builders/glsl/px_palette.glsl). ASCII only.
import os
import sys

if HERE not in sys.path:                                  # noqa: F821 (HERE comes from the rack / test namespace)
    sys.path.insert(0, HERE)                              # noqa: F821
import palette_map_logic as _PML  # noqa: E402

PAL_SOURCE_NAMES = [k for k, _l in _PML.PAL_SOURCES if k != 'image']
PAL_SOURCE_LABELS = [lb for k, lb in _PML.PAL_SOURCES if k != 'image']
with open(os.path.join(HERE, 'glsl', 'px_palette.glsl')) as _fh:  # noqa: F821
    PAL_GLSL = _fh.read()


def pal_page(source='neon_trio', mode='gradient', stops='#00ff88 #00e5ff #ff2bd6'):
    return ('Palette', [
        ('Palsource', 'Menu', source, {'names': PAL_SOURCE_NAMES, 'labels': PAL_SOURCE_LABELS,
                                       'label': 'Palette source'}),
        ('Palstops', 'Str', stops, {'label': 'Custom stops (hex [hex ...])'}),
        ('Palfile', 'Str', '', {'label': 'Palette file (.txt .hex .json .gpl .pal .ase)'}),
        ('Palmode', 'Menu', mode, {'names': [m for m, _l in _PML.PAL_MODES], 'labels': [lb for _m, lb in _PML.PAL_MODES],
                                   'label': 'Palette mode'}),
        ('Palinterp', 'Menu', 'oklab', {'names': [m for m, _l in _PML.PAL_INTERP],
                                        'labels': [lb for _m, lb in _PML.PAL_INTERP], 'label': 'Blend space'}),
        ('Palreverse', 'Toggle', False, {'label': 'Reverse palette'}),
        ('Palshift', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Palette shift (bind a beat / LFO)'}),
    ])


def stops_of(m, Pm):
    """The module COMP m's palette stops (pure: duck-typed pars; tested offline with a fake)."""
    src = str(m.par.Palsource.eval())
    spec = {'source': src, 'mode': str(m.par.Palmode.eval()), 'reverse': bool(m.par.Palreverse.eval())}
    rows, fhex = None, None
    if src == 'custom':
        rows = [[h] for h in str(m.par.Palstops.eval()).split()] or [['#ffffff']]
    elif src == 'file':
        path = str(m.par.Palfile.eval())
        try:
            with open(path, 'rb') as fh:
                data = fh.read()
            fhex = Pm.parse_file(path, data)
            if isinstance(fhex, tuple):
                fhex = fhex[0]
        except Exception:
            fhex = []
    return Pm.palette_stops(spec, rows, fhex)


PAL_CB = '''# pal: W1-B palette of this module (fx_stylise_pal.py). Logic = the rack's palette_map_logic Text DAT.
def _pm(m):
\treturn m.parent().op('palette_map_logic').module

def _stops(m, Pm):
\tsrc = str(m.par.Palsource.eval())
\tspec = {'source': src, 'mode': str(m.par.Palmode.eval()), 'reverse': bool(m.par.Palreverse.eval())}
\trows, fhex = None, None
\tif src == 'custom':
\t\trows = [[h] for h in str(m.par.Palstops.eval()).split()] or [['#ffffff']]
\telif src == 'file':
\t\tpath = str(m.par.Palfile.eval())
\t\ttry:
\t\t\tdata = open(path, 'rb').read()
\t\t\tfhex = Pm.parse_file(path, data)
\t\t\tif isinstance(fhex, tuple):
\t\t\t\tfhex = fhex[0]
\t\texcept Exception:
\t\t\tfhex = []
\treturn Pm.palette_stops(spec, rows, fhex)

def count(m):
\tPm = _pm(m)
\treturn float(min(len(_stops(m, Pm)), Pm.PAL_MAX))

def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tm = scriptOp.parent()
\tPm = _pm(m)
\tPm.cook_chop(scriptOp, Pm.pal_rows(_stops(m, Pm)))
'''

PAL_CTL = ["op('pal_callbacks').module.count(parent())", 'parent().par.Palshift.eval()',
           'parent().par.Palmode.menuIndex', 'parent().par.Palinterp.menuIndex']


def pal_bind(m, H, glsl_ops):
    """TD side: Script CHOP `pal` + docked callbacks in module COMP m; uPal / uPalCtl on each GLSL op."""
    s = H['mk'](m, scriptCHOP, 'pal')  # noqa: F821 (TD name)
    d = m.op('pal_callbacks')
    if d is None:
        d = H['mk'](m, textDAT, 'pal_callbacks')  # noqa: F821
    if d.text != PAL_CB:
        d.text = PAL_CB
    d.dock = s
    s.par.callbacks = 'pal_callbacks'
    s.comment = 'uPal: 16 palette stops r g b pos (W1-B), recooks on Palette page edits.'
    for g in glsl_ops:
        _PML.bind_glsl(g, 'pal', PAL_CTL, ParMode)  # noqa: F821
    return s
