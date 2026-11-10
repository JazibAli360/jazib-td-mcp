# fx_glass builder - FX_glass: glass / lens surfaces over any picture (liquid glass, holo foil, rain on glass, frost /
# reeded / fly-eye, wet mirror floor). BUILD_PLAN_27OCT s2: a rack of its own (not FX_film). The FX_glitch rack reused
# through builders/fx_stylise.py (palette logic DAT, H['pas'] / H['glsl']) with its own COMP name, module files
# builders/fx_glass_<X>.py and 'liquid1' (enabled 0) as the first row. Rack addition used by 2+ glass modules
# (liquid, rain, frost): H['backdrop'](m, src) = a pre-blurred copy of the module's input (Resolution TOP at 1/Down +
# Blur TOP, `Backblur` / `Backdown` pars on the module). Doc: docs/builds/fx_glass.md. Rest state: every slot off.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_glass.py').read(), ns)
#   ns['build']('/project1/lab')                          # rack + liquid1 (enabled 0); idempotent
#   ns['add']('/project1/lab/FX_glass', 'foil')
# ASCII only.
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
with open(os.path.join(HERE, 'fx_stylise.py')) as _fh:
    exec(_fh.read(), globals())                          # the rack (via fx_glitch.py) + palette DAT + pas / glsl

NAME = 'FX_glass'
PREFIX = 'fx_glass'
FIRST = ('liquid1', 'liquid')
LABEL = ('FX_glass: glass / lens rack (liquid glass, holo foil, rain on glass, frost / reeded / fly-eye, wet floor). '
         'In: in1 TOP. Out: out1 TOP. Slots from `slots` (builders/fx_glass.py add/remove/rewire). Panic = instant '
         'passthrough.')

BACKDROP_PAGE = ('Backdrop', [
    ('Backblur', 'Float', 24.0, {'min': 0, 'max': 200, 'label': 'Backdrop blur px (full-res px)'}),
    ('Backdown', 'Menu', 'half', {'names': ['full', 'half', 'quarter'], 'labels': ['Full', 'Half', 'Quarter'],
                                  'label': 'Backdrop resolution'}),
])


def _backdrop(m, src):
    """Pre-blurred backdrop of `src` inside module m: bd_down (Resolution TOP) -> bd (Blur TOP, gaussian, size =
    Backblur / down factor). Returns bd. The module declares BACKDROP_PAGE in its PAGES."""
    dn = _mk(m, resolutionTOP, 'bd_down')
    dn.inputConnectors[0].connect(src)
    dn.par.outputresolution = 'custom'
    f = "(1 if parent().par.Backdown.eval() == 'full' else (2 if parent().par.Backdown.eval() == 'half' else 4))"
    _expr(dn.par.resolutionw, "max(1, int(me.inputs[0].width / %s))" % f)
    _expr(dn.par.resolutionh, "max(1, int(me.inputs[0].height / %s))" % f)
    dn.par.filtertype = 'mipmap'
    dn.par.format = 'rgba16float'
    dn.comment = 'Backdrop at 1 / Backdown.'
    bd = _mk(m, blurTOP, 'bd')
    bd.inputConnectors[0].connect(dn)
    _expr(bd.par.size, "max(0.0, parent().par.Backblur.eval() / %s)" % f)
    bd.par.type = 'gaussian'
    bd.par.extend = 'hold'
    bd.comment = 'Pre-blurred backdrop (glass inside / frosted look).'
    return bd


H = dict(H, backdrop=_backdrop)
