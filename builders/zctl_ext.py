"""zctl_ext: extension class ZCtl for the zctl control surface COMP (runs inside TD; copied into Text DAT zctl_ext).

Promoted on the COMP, so anything can call op('<comp>').Bind('/path/op', 'tx ty'), .Store(), .Recall(2),
.Randomize(), .CtrlIn('Knob1', 0.5). Data lives in Table DATs `binds` + `presets` (plain data); knob values live in
the COMP's custom pars Knob<n> (0-1) on page Knobs, Lock<n> toggles beside them. Pure ASCII.
"""
import random
import time

AUTOUI = '/project1/show/tools/autoUI'
FLOAT_STYLES = ('Float', 'XY', 'XYZ', 'XYZW', 'UV', 'UVW', 'WH', 'RGB', 'RGBA')


class ZCtl:
    def __init__(self, ownerComp):
        self.owner = ownerComp
        self.morph = None
        self.rng = random.Random()
        self.ui_queued = False
        self._binds = None
        self._by_knob = None
        self.reopen = False
        self.tile = True
        self.widgets = 0

    # ---------------------------------------------------------------- helpers
    @property
    def L(self):
        return self.owner.op('zctl_logic').module

    def _table(self, name):
        return self.owner.op(name)

    def _rows(self, name):
        t = self._table(name)
        return self.L.rows_to_dicts([[c.val for c in r] for r in t.rows()])

    def _write(self, name, items, cols):
        t = self._table(name)
        t.clear()
        for r in self.L.dicts_to_rows(items, cols):
            t.appendRow(r)
        if name == 'binds':
            self.Invalidate()

    def Invalidate(self):
        """binds_watch (DAT Execute on the binds table) calls this on any edit, by hand or by code."""
        self._binds = None
        self._by_knob = None

    def Binds(self):
        """Parsed binds table, cached (a morph tick / knob change would otherwise re-parse it per knob: O(n^2))."""
        if self._binds is None:
            self._binds = self._rows('binds')
            self._by_knob = dict((b['knob'], b) for b in self._binds)
        return [dict(b) for b in self._binds]

    def _bind_of(self, knob):
        if self._by_knob is None:
            self.Binds()
        return self._by_knob.get(knob)

    def Presets(self):
        return self._rows('presets')

    def _err(self, msg):
        self.owner.par.Lasterror = str(msg)[:200]
        return msg

    def _status(self):
        o = self.owner
        o.par.Nbinds = len(self.Binds())
        o.par.Npresets = len(self.Presets())
        o.par.Morphing = self.morph is not None

    def _target(self, path):
        p = str(path).strip()
        if not p:
            return None
        return self.owner.op(p) if not p.startswith('/') else op(p)

    def _knob_page(self):
        for pg in self.owner.customPages:
            if pg.name == 'Knobs':
                return pg
        return self.owner.appendCustomPage('Knobs')

    def _ensure_pars(self, b):
        o, L = self.owner, self.L
        pg = self._knob_page()
        k, lk = b['knob'], L.lock_name(b['id'])
        if not hasattr(o.par, k):
            p = pg.appendFloat(k, label=b['label'])[0]
            p.min, p.max, p.normMin, p.normMax = 0, 1, 0, 1
            p.clampMin = p.clampMax = True
        else:
            o.par[k].label = b['label']
        if not hasattr(o.par, lk):
            pg.appendToggle(lk, label='lock')
        o.par[lk].label = '    lock (randomize skips)'
        o.par[lk].val = b.get('lock') in ('1', 'True', 'true')

    def Values(self):
        o = self.owner
        self.Binds()
        return dict((b['knob'], float(o.par[b['knob']].eval())) for b in self._binds if hasattr(o.par, b['knob']))

    def Locks(self):
        o, L = self.owner, self.L
        return dict((b['knob'], bool(o.par[L.lock_name(b['id'])].eval())) for b in self.Binds()
                    if hasattr(o.par, L.lock_name(b['id'])))

    # ---------------------------------------------------------------- binding
    def _describe(self, p):
        """-> (kind, lo, hi, menun) or None when the par can't be a knob."""
        st = p.style
        if p.readOnly or st in ('Pulse', 'Momentary', 'Header'):
            return None
        if st == 'Menu':
            return 'menu', 0, 0, len(p.menuNames)
        if st == 'Toggle':
            return 'toggle', 0, 1, 0
        if st == 'Int':
            lo, hi = p.normMin, p.normMax
        elif st in FLOAT_STYLES:
            lo, hi = p.normMin, p.normMax
        else:
            return None
        if hi == lo:
            lo, hi = 0, 1
        return ('int' if st == 'Int' else 'float'), lo, hi, 0

    def Bind(self, path, names):
        """Bind pars of one op as knobs. names: 'tx ty, period' (wildcards ok: 't?'). Returns the new knob names."""
        L, o = self.L, self.owner
        tgt = self._target(path)
        if tgt is None:
            self._err('Bind: no op {!r}'.format(path))
            return []
        binds = self.Binds()
        have = set((b['path'], b['par']) for b in binds)
        made = []
        for token in L.split_names(names):
            for p in tgt.pars(token):
                d = self._describe(p)
                if d is None or (tgt.path, p.name) in have:
                    continue
                kind, lo, hi, n = d
                i = L.next_id([b['id'] for b in binds])
                cur = p.menuIndex if kind == 'menu' else p.eval()
                b = {'id': str(i), 'knob': L.knob_name(i), 'label': '{} {}'.format(tgt.name, p.label.strip() or p.name),
                     'path': tgt.path, 'par': p.name, 'lo': repr(float(lo)), 'hi': repr(float(hi)), 'kind': kind,
                     'menun': str(n), 'lock': '0', 'src': ''}
                binds.append(b)
                have.add((tgt.path, p.name))
                self._ensure_pars(b)
                o.par[b['knob']] = L.from_target(cur, lo, hi, kind, n)
                made.append(b['knob'])
        if not made:
            self._err('Bind: nothing bindable on {} for {!r}'.format(tgt.path, names))
        self._write('binds', binds, L.BIND_COLS)
        self._status()
        if made:
            self.QueueUI()
            # a knob par made this frame is not watched by apply_exec until the next one: a value set right after
            # Bind in the same script would never reach the target, so apply once more next frame
            run('op({!r}).ext.ZCtl.ApplyAll()'.format(o.path), delayFrames=1, delayRef=op.TDResources)
        return made

    def BindSelected(self):
        """Bindpath set: that op. Empty: the ops selected in the network pane (else its current op), not this COMP."""
        o = self.owner
        names = o.par.Bindpar.eval().strip()
        if not names:
            self._err('Bind selected: set Bindpar (names, wildcards ok, e.g. "tx ty" or "*")')
            return []
        if o.par.Bindpath.eval().strip():
            return self.Bind(o.par.Bindpath.eval(), names)
        targets = []
        for pane in ui.panes:
            if pane.type != PaneType.NETWORKEDITOR:
                continue
            sel = list(pane.owner.selectedChildren) or ([pane.owner.currentChild] if pane.owner.currentChild else [])
            targets += [t for t in sel if t is not None and t != o and not t.path.startswith(o.path + '/controls')]
        made = []
        for t in targets:
            made += self.Bind(t.path, names)
        if not targets:
            self._err('Bind selected: nothing selected in a network pane')
        return made

    def Unbind(self, knob_id):
        L, o = self.L, self.owner
        binds = self.Binds()
        keep = [b for b in binds if b['id'] != str(int(knob_id))]
        if len(keep) == len(binds):
            self._err('Unbind: no knob {}'.format(knob_id))
            return False
        self._release_ui()  # T-70: window closed before the pars its widgets show go
        self._write('binds', keep, L.BIND_COLS)
        self._drop_from_presets([b['knob'] for b in binds if b not in keep])
        self.SyncPars()
        self._status()
        self.QueueUI()
        return True

    def _drop_from_presets(self, knobs):
        """Ids can come back (next id = max + 1), so a removed knob leaves no values behind in the presets."""
        L = self.L
        presets = self.Presets()
        for p in presets:
            d = L.preset_loads(p['values'])
            for k in knobs:
                d.pop(k, None)
            p['values'] = L.preset_dumps(d)
        self._write('presets', presets, L.PRESET_COLS)

    def ClearBinds(self):
        self._release_ui()
        self._drop_from_presets([b['knob'] for b in self.Binds()])
        self._write('binds', [], self.L.BIND_COLS)
        self.SyncPars()
        self._status()
        self.QueueUI()

    def SyncPars(self):
        """Knob/Lock pars match the binds table (rebuild from data; drop pars of removed binds)."""
        L, o = self.L, self.owner
        binds = self.Binds()
        want = set()
        for b in binds:
            self._ensure_pars(b)
            want.update([b['knob'], L.lock_name(b['id'])])
        for pg in o.customPages:
            if pg.name == 'Knobs':
                for p in list(pg.pars):
                    if p.name not in want:
                        p.destroy()

    # ---------------------------------------------------------------- apply
    def Apply(self, knob):
        o, L = self.owner, self.L
        if not o.par.Active.eval():
            return
        b = self._bind_of(knob)
        if b is not None:
            tgt = self._target(b['path'])
            p = getattr(tgt.par, b['par'], None) if tgt is not None else None
            if p is None:
                self._err('Apply: {}.{} not found'.format(b['path'], b['par']))
                return
            v = L.to_target(o.par[knob].eval(), float(b['lo']), float(b['hi']), b['kind'], int(b['menun'] or 0))
            if p.mode != ParMode.CONSTANT:
                self._err('Apply: {}.{} is not constant (mode {})'.format(b['path'], b['par'], p.mode))
            if b['kind'] == 'menu':
                if p.menuIndex != v:
                    p.menuIndex = v
            elif p.eval() != v:
                p.val = v
            return

    def ApplyAll(self):
        for b in self.Binds():
            self.Apply(b['knob'])

    def LockChanged(self, par):
        L = self.L
        binds = self.Binds()
        for b in binds:
            if L.lock_name(b['id']) == par.name:
                b['lock'] = '1' if par.eval() else '0'
        self._write('binds', binds, L.BIND_COLS)

    # ---------------------------------------------------------------- presets + morph
    def _pid(self, pid):
        return int(self.owner.par.Activepreset.eval() if pid is None else pid)

    def Store(self, pid=None, new=False):
        L, o = self.L, self.owner
        presets = self.Presets()
        pid = 0 if new else self._pid(pid)
        if pid <= 0 or not any(p['id'] == str(pid) for p in presets):
            pid = pid if pid > 0 else L.next_id([p['id'] for p in presets])
            presets.append({'id': str(pid), 'name': 'P{}'.format(pid), 'values': ''})
        for p in presets:
            if p['id'] == str(pid):
                p['values'] = L.preset_dumps(self.Values())
        self._write('presets', presets, L.PRESET_COLS)
        o.par.Activepreset = pid
        self._status()
        return pid

    def DeletePreset(self, pid=None):
        pid = self._pid(pid)
        presets = self.Presets()
        keep = [p for p in presets if p['id'] != str(pid)]
        self._write('presets', keep, self.L.PRESET_COLS)
        self._status()
        return len(keep) != len(presets)

    def Recall(self, pid=None, morphtime=None):
        pid = self._pid(pid)
        row = [p for p in self.Presets() if p['id'] == str(pid)]
        if not row:
            self._err('Recall: no preset {}'.format(pid))
            return False
        cur = self.Values()
        end = dict((k, v) for k, v in self.L.preset_loads(row[0]['values']).items() if k in cur)
        self.MorphTo(end, morphtime)
        return True

    def Randomize(self, amount=None):
        o = self.owner
        a = o.par.Randamount.eval() if amount is None else amount
        self.MorphTo(self.L.randomize(self.Values(), a, self.rng, self.Locks()))

    def MorphTo(self, end, morphtime=None):
        o = self.owner
        t = o.par.Morphtime.eval() if morphtime is None else float(morphtime)
        cur = self.Values()
        self.morph = self.L.Morph(cur, end, t, o.par.Morphcurve.eval(), time.perf_counter())
        o.op('morph_tick').par.active = True
        self.Tick()

    def StopMorph(self):
        self.morph = None
        self.owner.op('morph_tick').par.active = False
        self._status()

    def Tick(self):
        m, o = self.morph, self.owner
        if m is None:
            self.StopMorph()
            return
        vals, done = m.step(time.perf_counter(), self.Values())
        for k, v in vals.items():
            if hasattr(o.par, k):
                o.par[k] = v
        if done:
            self.StopMorph()
        else:
            o.par.Morphing = True

    # ---------------------------------------------------------------- control in (MIDI mapper hook)
    def CtrlIn(self, chan, value):
        """A channel on the in_ctrl input drives a knob: by the bind's src column, else 'Knob3' / 'k3' / '3'. 0-1."""
        k = self.L.ctrl_target(chan, self.Binds())
        if k is not None:
            self.owner.par[k] = self.L.clamp(float(value))
        return k

    # ---------------------------------------------------------------- UI (T-70 safe)
    def _window(self):
        return self.owner.op('controls_window')

    def _release_ui(self):
        """Before anything inside the panel goes (autoUI clears it, unbinding removes the pars its widgets show):
        close our window and send network panes looking inside the panel back to this COMP (T-70: TD crashed when a
        panel an open window showed was destroyed). Returns True when the window was open."""
        o, w = self.owner, self._window()
        was = bool(w is not None and w.isOpen)
        if was:
            w.par.winclose.pulse()
            self.reopen = True
        ui_ = o.op('controls')
        if ui_ is not None:
            for pane in ui.panes:
                try:
                    if pane.owner is not None and (pane.owner == ui_ or pane.owner.path.startswith(ui_.path + '/')):
                        pane.owner = o
                except Exception:
                    pass
        return was

    def QueueUI(self):
        """Refill the panel once, a few frames later (autoUI takes ~2 s for ~30 widgets; several binds = one refill)."""
        self._release_ui()
        if self.ui_queued:
            return
        self.ui_queued = True
        run('op({!r}).ext.ZCtl._rebuild1()'.format(self.owner.path), delayFrames=2, delayRef=op.TDResources)

    def RebuildUI(self, reopen=False):
        """Phase 0 (now): window closed, panes off the panel, the panel's node tile off. Phase 1 (2 frames later):
        autoUI refills it. Phase 2 (2 frames later): tile back on, window reopened if it was open."""
        if reopen:
            self.reopen = True
        self.QueueUI()

    def _rebuild1(self):
        self.ui_queued = False
        o = self.owner
        ui_ = o.op('controls')
        a = op(AUTOUI)
        if ui_ is not None and ui_.op('zk_rt') is not None:  # zkit panel (builders/zkit.py): re-read the pars in
            ui_.op('zk_rt').module.Rebuild()                # place (knob pars come and go with binds); no autoUI
            self.widgets = len(ui_.op('zk_rt').module.S['order'])
            run('op({!r}).ext.ZCtl._rebuild2()'.format(o.path), delayFrames=2, delayRef=op.TDResources)
            return self.widgets
        if ui_ is None or a is None:
            return self._err('RebuildUI: controls or autoUI missing')
        if self._window() is not None and self._window().isOpen:  # opened again meanwhile: start over
            return self.QueueUI()
        self.tile = ui_.viewer
        ui_.viewer = False
        keep = dict((n, a.par[n].eval()) for n in ('Pagescope', 'Pagetabs', 'Parameterscope', 'Header'))
        try:
            a.par.Pagescope = 'Zctl Knobs'
            a.par.Pagetabs = False
            a.par.Parameterscope = '*'
            a.par.Header = True
            a.ext.AutoUIExt.GenerateUI(customComp=o, ui=ui_, shortcutDialog=False)
        finally:
            for n, v in keep.items():
                a.par[n] = v
        ws = sorted([w for w in ui_.children if w.OPType == 'widgetCOMP'], key=lambda w: -w.nodeY)
        h = 0
        for i, w in enumerate(ws):
            w.par.alignorder.expr = ''
            w.par.alignorder.mode = ParMode.CONSTANT
            w.par.alignorder = i  # constant: a later re-flow of node positions must not reorder the panel
            w.par.hmode = 'fill'
            w.par.enablecloning = False
            if hasattr(w.par, 'Headerlabel'):
                w.par.Headerlabel = 'zctl control surface'
            # autoUI carries the old widget pars over by path (getParInfo), so a relabelled knob kept its old label
            if hasattr(w.par, 'Widgetlabel') and hasattr(o.par, w.name):
                w.par.Widgetlabel = o.par[w.name].label.strip()
            if hasattr(w.par, 'Labelwidth'):
                w.par.Labelwidth = 170
            h += int(w.par.h.eval())
        ui_.par.align = 'verttb'
        ui_.par.h = max(60, h + 4)
        win = self._window()
        if win is not None:
            win.par.winh = int(ui_.par.h.eval()) + 28
        self.widgets = len(ws)
        run('op({!r}).ext.ZCtl._rebuild2()'.format(o.path), delayFrames=2, delayRef=op.TDResources)
        return len(ws)

    def _rebuild2(self):
        o = self.owner
        ui_ = o.op('controls')
        if ui_ is not None:
            ui_.viewer = True
        if self.reopen and self._window() is not None:
            self._window().par.winopen.pulse()
        self.reopen = False

    def OpenControls(self):
        """Opencontrols pulse: open the window (after a pending refill, if one is queued)."""
        if self.ui_queued:
            self.reopen = True
            return
        self._window().par.winopen.pulse()
