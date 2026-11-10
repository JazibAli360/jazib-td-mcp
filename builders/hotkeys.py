# Hotkeys (user, 28 Oct 2026: "can u have 1 key for refresh?"): one key pulses Reset on every lab COMP that is cooking.
# Run in TD (td_exec):  ns = dict(globals()); exec(open('<repo>/builders/hotkeys.py').read(), ns); ns['build']()
# Lives at /project1/hotkeys, outside /project1/lab, so recovery never parks it (T-100: a parked COMP stays silent).
# Change the key with the COMP's `Key` par (TD key names: 'f5', 'f6', ...). Idle cost: 0 cooks (Keyboard In only fires on keys).

CB = '''# hotkeys: the Key par refreshes every cooking lab COMP that has a Reset pulse (builders/hotkeys.py)
def onKey(dat, keyInfo):
    if not keyInfo.state or keyInfo.key != parent().par.Key.eval():
        return
    done = []
    for c in op('/project1/lab').children:
        if c.isCOMP and c.allowCooking and getattr(c.par, 'Reset', None) is not None and c.par.Reset.isPulse:
            c.par.Reset.pulse()
            done.append(c.name)
    parent().par.Last = ' '.join(done) or '(nothing cooking has a Reset)'
'''


def build(parent_path='/project1', name='hotkeys', key='f5'):
    root = op(parent_path)
    hk = root.op(name) or root.create(baseCOMP, name)
    page = next((p for p in hk.customPages if p.name == 'Hotkeys'), None) or hk.appendCustomPage('Hotkeys')
    if not hasattr(hk.par, 'Key'):
        page.appendStr('Key', label='Refresh key')[0].default = key
        hk.par.Key = key
    if not hasattr(hk.par, 'Last'):
        page.appendStr('Last', label='Last refreshed')
        hk.par.Last.readOnly = True
    cb = hk.op('keys_cb') or hk.create(textDAT, 'keys_cb')
    cb.text = CB
    kin = hk.op('keys') or hk.create(keyboardinDAT, 'keys')
    kin.par.callbacks = cb
    kin.par.active = True
    for leftover in ('keys_callbacks',):          # Keyboard In makes its own callbacks DAT once (zkit.py)
        lo_ = hk.op(leftover)
        if lo_ is not None:
            lo_.destroy()
    kin.nodeX, kin.nodeY, cb.nodeX, cb.nodeY = 0, 0, 0, -150
    hk.comment = 'Press the Key par (default F5) to pulse Reset on every cooking lab COMP. builders/hotkeys.py'
    return {'path': hk.path, 'key': hk.par.Key.eval()}
