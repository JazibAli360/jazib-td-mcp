# menu_logic - live dropdowns for custom pars that name things (TD 2025.31550). Copied into a Text DAT `menu_logic`
# by builders/px.py (PX_pointfx) and builders/effectors.py (/project1/effectors). Pure: no TD globals.
# A par's menuSource is an expression that returns an object with menuNames / menuLabels (duck-typed works, live
# 31550). TD re-evaluates it on every menuNames read (menu open, panel build), never per frame: idle cost 0 (T-233);
# on a parked COMP (allowCooking off) it is not re-evaluated: the menu shows its last items until the COMP cooks.
# Fields stay StrMenu (free text kept: a new preset name, a pattern, a path); a strict Menu falls back to item 0 when
# its item disappears and takes an int as an index, so it is never used for names (T-233). ASCII only.


BUILT = [0]                        # menus built since this module loaded (live check: stays put while idle)


class Menu(object):
    """What a menuSource expression returns (tdu.TableMenu's MenuObject has the same two members)."""

    def __init__(self, names=(), labels=None):
        BUILT[0] += 1
        self.menuNames = [str(n) for n in names]
        self.menuLabels = [str(x) for x in (labels if labels is not None else self.menuNames)]


EMPTY_SRC = "type('M', (), {'menuNames': [], 'menuLabels': []})()"
NONE_LABEL = '(none)'
# TD rejects '' as a menu name ("Invalid menu items": the whole menu falls back, live 31550); ' ' works, and every
# reader splits / strips, so ' ' is the empty value an item can set (T-233).
NONE = ' '


def tokens(text):
    return str(text or '').replace(',', ' ').split()


def _unique(pairs):
    seen, out = set(), []
    for n, lab in pairs:
        if n not in seen:
            seen.add(n)
            out.append((n, lab))
    return out


def name_menu(names, labels=None, none=False, none_label=NONE_LABEL):
    """One name per item (Target, Effname, Presetname, follow fields). none: a first '' item ('(none)')."""
    names = [str(n) for n in names]
    labels = [str(x) for x in labels] if labels is not None else list(names)
    pairs = ([(NONE, none_label)] if none else []) + [(n, lab) for n, lab in zip(names, labels) if n.strip()]
    pairs = _unique(pairs)
    return Menu([p[0] for p in pairs], [p[1] for p in pairs])


def select_menu(cur, names, tags=(), all_word='all', kinds=None, extra=()):
    """Helper menu for a selection expression ('all / names / #tags'): each item's NAME is the whole new text, so
    picking it sets a valid value at once (no callback, no half-written value): '+ X' adds X, '- X' removes a word
    already there (also typed words not in the lists), all_word replaces everything, '(clear)' empties it.
    kinds: {name: kind} shown in the labels; extra: more [(word, label)] offered before the names (e.g. 'eff*')."""
    toks = tokens(cur)
    base = [] if (all_word and toks == [all_word]) else toks
    pairs = []
    if all_word:
        pairs.append((all_word, all_word + ' (every one)'))
    words = [(w, lab) for w, lab in extra] + \
        [(n, '%s (%s)' % (n, kinds[n]) if kinds and kinds.get(n) else n) for n in names] + \
        [('#' + t, '#' + t) for t in tags]
    for w, lab in words:
        if w in base:
            continue
        pairs.append((' '.join(base + [w]), '+ ' + lab))
    for w in base:
        pairs.append((' '.join(x for x in base if x != w), '- ' + w))
    if len(base) > 1:
        pairs.append((NONE, '(clear)'))
    pairs = _unique([(n or NONE, lab) for n, lab in pairs])
    return Menu([p[0] for p in pairs], [p[1] for p in pairs])


def shared_source(name, kind='select', root='/project1/effectors/eff_rt'):
    """menuSource for a par on ANY COMP whose menu comes from the shared list runtime (eff_rt.menu(comp, name, kind));
    an empty menu (free text still works) while the list is missing, never an error on the COMP."""
    # me goes in as an argument: TD's expression names are not visible inside a lambda (T-159, T-233)
    return "(lambda r, m: r.module.menu(m, %r, %r) if r is not None else %s)(op(%r), me)" % (name, kind, EMPTY_SRC,
                                                                                               root)


def local_source(name, dat):
    """menuSource for a par whose COMP holds the runtime itself (PX: px_rt, the shared list: eff_rt)."""
    return "me.op(%r).module.menu(me, %r)" % (dat, name)


def to_strmenu(comp, name, source):
    """Make comp.par.<name> a StrMenu with this menuSource, in place: same name, page position, label, default,
    value (an Int's value as text), mode + expression / bind, help, readOnly, enable expression, section start.
    Expressions elsewhere that read the par by name re-bind (live 31550). Idempotent. Returns 'source' (only the
    menuSource changed), 'converted', 'same' or None (no such par / not Str / Int)."""
    p = getattr(comp.par, name, None)
    if p is None:
        return None
    if p.style == 'StrMenu':
        if p.menuSource != source:
            p.menuSource = source
            return 'source'
        return 'same'
    if p.style not in ('Str', 'Int'):
        return None
    page = p.page
    order = [t[0].tupletName for t in page.parTuplets]      # sort() takes tuplet names, not Effcentrex (T-234)
    keep = {'val': p.val, 'default': p.default, 'label': p.label, 'mode': p.mode, 'expr': p.expr,
            'bindExpr': p.bindExpr, 'help': p.help, 'readOnly': p.readOnly, 'enableExpr': p.enableExpr,
            'startSection': p.startSection}
    p.destroy()
    q = page.appendStrMenu(name, label=keep['label'])[0]
    q.menuSource = source
    q.default = str(keep['default'])
    q.val = str(keep['val'])
    for k in ('help', 'enableExpr', 'startSection', 'readOnly'):
        if keep[k]:
            setattr(q, k, keep[k])
    mode = getattr(keep['mode'], 'name', str(keep['mode']))
    if mode == 'EXPRESSION' and keep['expr']:
        q.expr = keep['expr']
    elif mode == 'BIND' and keep['bindExpr']:
        q.bindExpr = keep['bindExpr']
    if mode in ('EXPRESSION', 'BIND'):
        q.mode = keep['mode']
    page.sort(*order)
    return 'converted'
