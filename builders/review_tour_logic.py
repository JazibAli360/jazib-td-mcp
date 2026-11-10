# review_tour logic - pure Python, no td. Copied into /project1/review_tour/tour_logic by builders/review_tour.py.
# Offline tests: test/test_review_tour.py. ASCII only.
#
# The tour lists every lab COMP grouped like the lab's stage boxes, shows one at a time and cooks ONLY that one:
# a COMP the tour woke is parked again when the tour leaves it; a COMP that was cooking before the tour started
# (or a live lane's COMP, or a top-level COMP) is never parked.

LIST_W, VIEW_W, VIEW_H = 380, 450, 800
PAD_X, PAD_TOP, LINE_H = 10, 8, 18
FONT_PX = 13
CHAR_W = 7.8            # Menlo 13 px advance (~0.6 em)
HEAD_LINES = 2          # title + hint, then the groups
OTHER = 'Other'


def build_items(stages, children):
    """stages: [{'title', 'ops'}] (the lab's stored jz_stages plan, in box order); children: [names] of the lab's
    reviewable COMPs (no annotate boxes). -> [{'group', 'name'}] in stage order; COMPs no box lists go to 'Other'."""
    kids = list(children)
    seen, out = set(), []
    for s in stages or []:
        title = str(s.get('title') or OTHER)
        for n in s.get('ops') or []:
            if n in kids and n not in seen:
                out.append({'group': title, 'name': n})
                seen.add(n)
    rest = sorted(n for n in kids if n not in seen)
    if rest:
        tail = [x for x in out if x['group'] == OTHER]
        out = [x for x in out if x['group'] != OTHER] + tail + [{'group': OTHER, 'name': n} for n in rest]
    return out


def step(idx, n, d):
    """Prev/Next with wrap-around."""
    if n <= 0:
        return 0
    return (int(idx) + int(d)) % n


def clamp_index(idx, n):
    if n <= 0:
        return 0
    return max(0, min(int(idx), n - 1))


def key_action(key, char=''):
    """Keyboard In key name -> 'prev' / 'next' / 'ctl' / 'close' / None."""
    k = str(key or '').lower()
    ch = str(char or '')
    if k in ('left', 'up', 'pageup', 'arrowleft', 'arrowup') or ch in ('[', ',', 'p'):
        return 'prev'
    if k in ('right', 'down', 'pagedown', 'arrowright', 'arrowdown', 'space') or ch in (']', '.', 'n', ' '):
        return 'next'
    if k in ('enter', 'return') or ch in ('c',):
        return 'ctl'
    if k in ('esc', 'escape'):
        return 'close'
    return None


def cook_plan(shown, cooking, before, owned, protected):
    """shown: path to show (or None = tour closing); cooking: {path: allowCooking now} for the candidates;
    before: paths cooking when the tour started; owned: paths the tour woke; protected: never parked.
    -> (wake, park, owned). Only what the tour woke is ever parked, and never what was cooking before."""
    before, protected = set(before), set(protected)
    owned = [p for p in owned if p in cooking]
    wake, park = [], []
    if shown is not None and shown in cooking and not cooking[shown]:
        wake.append(shown)
        if shown not in owned:
            owned.append(shown)
    keep = []
    for p in owned:
        if p == shown:
            keep.append(p)
        elif p in before or p in protected or p.count('/') <= 1:
            pass                                    # forget it, never park it
        elif cooking.get(p, False) or p in wake:
            park.append(p)
        # already parked by someone else: nothing to do
    return wake, park, keep


def list_window(n_items_lines, sel_line, max_lines):
    """First line to draw so the selected line stays visible (centred when the list is longer than the panel)."""
    if n_items_lines <= max_lines:
        return 0
    first = sel_line - max_lines // 2
    return max(0, min(first, n_items_lines - max_lines))


def fit(text, chars):
    t = str(text)
    if len(t) <= chars:
        return t + ' ' * (chars - len(t))
    return t[:max(0, chars - 1)] + '~'


def list_lines(items, sel, cooking_names, has_top, h=VIEW_H, w=LIST_W):
    """-> [(kind, text, item_index or None)], kinds head / group / body / sel / dim. Fixed slots: line i is drawn at
    i * LINE_H from the top, so a click maps back by line_at()."""
    chars = int((w - 2 * PAD_X) // CHAR_W)
    max_lines = int((h - 2 * PAD_TOP) // LINE_H)
    n = len(items)
    head = [('head', fit('LAB REVIEW  %d/%d' % (sel + 1 if n else 0, n), chars), None),
            ('dim', fit('<- -> keys or click  |  * = cooking', chars), None)]
    body = []
    sel_line = 0
    last = None
    for i, it in enumerate(items):
        if it['group'] != last:
            body.append(('group', fit(it['group'].upper(), chars), None))
            last = it['group']
        mark = '*' if it['name'] in cooking_names else ' '
        tail = '' if has_top.get(it['name'], True) else ' (no out)'
        kind = 'sel' if i == sel else 'body'
        if i == sel:
            sel_line = len(body)
        body.append((kind, fit(' %s %s%s' % (mark, it['name'], tail), chars), i))
    room = max_lines - len(head)
    first = list_window(len(body), sel_line, room)
    return head + body[first:first + room]


def spec_rows(lines, kind, h=VIEW_H, pad_x=PAD_X, pad_top=PAD_TOP, line_h=LINE_H):
    """Text TOP spec rows (x, y, text; aligny bottom, y from the bottom) for the lines of one kind."""
    rows = []
    for i, (k, text, _i) in enumerate(lines):
        if k == kind and text:
            rows.append([pad_x, h - pad_top - (i + 1) * line_h + 4, text.rstrip()])
    return rows


def sel_bar(lines, h=VIEW_H, w=LIST_W, pad_top=PAD_TOP, line_h=LINE_H):
    """(x, y, w, h) of the highlight bar in pixels from the bottom-left, or None."""
    for i, (k, _t, _i) in enumerate(lines):
        if k == 'sel':
            return (4, h - pad_top - (i + 1) * line_h, w - 8, line_h)
    return None


def bar_center(bar, w=LIST_W, h=VIEW_H):
    """Rectangle TOP centre (pixels, origin = image centre) of a bar given from the bottom-left."""
    x, y, bw, bh = bar
    return x + bw / 2.0 - w / 2.0, y + bh / 2.0 - h / 2.0


def line_at(v, n_lines, h=VIEW_H, pad_top=PAD_TOP, line_h=LINE_H):
    """Panel v (0 bottom .. 1 top) -> line index or None."""
    try:
        y = (1.0 - float(v)) * h - pad_top
    except Exception:
        return None
    if y < 0:
        return None
    i = int(y // line_h)
    return i if 0 <= i < n_lines else None


def item_at(lines, v, h=VIEW_H):
    i = line_at(v, len(lines), h)
    if i is None:
        return None
    return lines[i][2]


def view_title(item, idx, n, cooking, has_top, has_ctl):
    """Two lines over the big view."""
    if item is None:
        return 'no lab COMPs found', ''
    a = '%s   (%d/%d, %s)' % (item['name'], idx + 1, n, item['group'])
    b = ('cooking' if cooking else 'parked') + ('' if has_top else '  |  no Out TOP') + \
        ('  |  [ controls ]  click here / Enter' if has_ctl else '  |  no controls panel')
    return a, b
