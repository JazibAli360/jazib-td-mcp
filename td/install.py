"""Jazib MCP for TouchDesigner -- installer. Builds /jazib_mcp in the open project and saves td/JazibTDMCP.tox.

HOW TO USE (README note)
  1. Start the bridge/MCP side (see ../README.md); it listens on 127.0.0.1:9335. TD opens no port: it dials out.
  2. In TouchDesigner 2025.31550 open the Textport (Dialogs > Textport and DATs) and run this one line:
       exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/td/install.py').read())
  3. It prints a summary. /jazib_mcp connects by itself, retries every ~4 s while the bridge is down (the timeline
     must be playing: frame callbacks barely fire when it is paused) and shows its state in /jazib_mcp/status.
  4. Later edits to td/handlers.py: call the `reload` command (no reinstall). Edits to callbacks.py or install.py:
     rerun the line above. Reconnect by hand: the Reconnect pulse on the COMP's "Jazib MCP" page.
  5. Other projects: drag td/JazibTDMCP.tox in at the root so the COMP is /jazib_mcp (the protocol's path).

What it builds (/jazib_mcp, a Base COMP at the root):
  ws         WebSocket DAT, client to 127.0.0.1:9335, callbacks = the callbacks DAT
  callbacks  Text DAT  <- td/callbacks.py   (forwards every event to handlers)
  handlers   Text DAT  <- td/handlers.py    (the protocol; source of truth stays on disk)
  status     Text DAT  (connect / disconnect events; never written per frame)
  reconnect  Execute DAT, Frame Start: every 120 frames asks handlers.tick() whether to redial
  pulse_exec Parameter Execute DAT: the Reconnect pulse
  Custom page "Jazib MCP": Handlersfile (File), Reconnect (Pulse)

The shared token is read from ~/Library/Application Support/JazibTDMCP/token each time TD connects; it is never put
in the network or the .tox. Rules followed (td-port/LEARNINGS.md): ASCII only, everything that can fail (reading and
compiling files, class checks, output folder) happens before the network changes, an existing /jazib_mcp is updated
in place (keeps its position; nothing destroyed), `par.val = x`, parameters set only if they exist.
Unknown WebSocket DAT parameter names are probed: their list goes to the Textport and td/build/install_probe.json.

Overrides (environment of the TD process; tools/scratch_td.py sets them for the disposable scratch TD, LEARNINGS T-83):
  JTD_BRIDGE_PORT       bridge port to dial (default 9335). Kept on the COMP as the Bridgeport par; handlers.tick()
                        keeps the ws DAT on it, so changing the par re-dials.
  JTD_TD_DIR            folder holding handlers.py / callbacks.py (default this repo's td/).
  JTD_INSTALL_SAVE_TOX  '0' = do not write td/JazibTDMCP.tox (a scratch install must never replace the shared .tox).
"""
import json as _jtd_json
import os as _jtd_os
import time as _jtd_time

import td as _jtd_td


def _jtd_install():
    base = _jtd_os.environ.get('JTD_TD_DIR') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/td'
    port = int(_jtd_os.environ.get('JTD_BRIDGE_PORT') or 9335)
    save_tox = _jtd_os.environ.get('JTD_INSTALL_SAVE_TOX', '1') != '0'
    tox_path = _jtd_os.path.join(base, 'JazibTDMCP.tox')
    build_dir = _jtd_os.path.join(base, 'build')
    probe_path = _jtd_os.path.join(build_dir, 'install_probe.json' if port == 9335 else 'install_probe_{}.json'.format(port))
    warn = []

    # ---------------------------------------------------------------- 1. everything fallible first
    texts = {}
    for key in ('handlers', 'callbacks'):
        path = _jtd_os.path.join(base, key + '.py')
        with open(path, 'r', encoding='utf-8') as f:
            t = f.read()
        t.encode('ascii')  # raises on non-ASCII (LEARNINGS rule 1)
        compile(t, path, 'exec')
        texts[key] = t
    need = ('baseCOMP', 'websocketDAT', 'textDAT', 'executeDAT', 'parameterexecuteDAT')
    missing = [c for c in need if not hasattr(_jtd_td, c)]
    if missing:
        raise RuntimeError('jazib_mcp install: TD has no class ' + ', '.join(missing) + '; nothing changed')
    _jtd_os.makedirs(build_dir, exist_ok=True)
    with open(probe_path, 'a'):
        pass  # writable?
    root = op('/')
    comp = root.op('jazib_mcp')
    if comp is not None and comp.OPType != 'baseCOMP':
        raise RuntimeError('/jazib_mcp exists but is a ' + comp.OPType + ', not a Base COMP; rename it first. '
                           'Nothing changed.')

    # ---------------------------------------------------------------- 2. build / update in place
    created = comp is None
    if created:
        comp = root.create(baseCOMP, 'jazib_mcp')
        p1 = root.op('project1')
        if p1 is not None:
            comp.nodeX, comp.nodeY = p1.nodeX, p1.nodeY - 250
    comp.comment = 'Jazib MCP for TouchDesigner: dials ws://127.0.0.1:{} (bridge). Protocol v1.'.format(port)
    old_ws = comp.op('ws')
    if old_ws is not None and old_ws.par['active'] is not None:
        old_ws.par.active = False

    def child(cls, name, x, y):
        c = comp.op(name)
        if c is not None and not isinstance(c, cls):
            c.allowCooking = False  # retire, never destroy (LEARNINGS: destroys crashed TD 2)
            c.name = name + '_old' + str(absTime.frame)
            warn.append('retired a ' + c.OPType + ' that was in the way: ' + c.path)
            c = None
        if c is None:
            c = comp.create(cls, name)
        c.nodeX, c.nodeY = x, y
        return c

    handlers = child(textDAT, 'handlers', 0, 0)
    callbacks = child(textDAT, 'callbacks', 0, 200)
    status = child(textDAT, 'status', 400, 200)
    ws = child(websocketDAT, 'ws', 200, 200)
    recon = child(executeDAT, 'reconnect', 200, 0)
    pulse = child(parameterexecuteDAT, 'pulse_exec', 400, 0)

    handlers.text = texts['handlers']
    callbacks.text = texts['callbacks']
    recon.text = ('# Jazib MCP: every 120 frames (~2 s at 60 fps) let handlers decide whether to redial. Cheap.\n'
                  'def onFrameStart(frame):\n'
                  '    if absTime.frame % 120:\n'
                  '        return\n'
                  "    op('handlers').module.tick(parent())\n"
                  '    return\n')
    pulse.text = ('# Jazib MCP: the Reconnect pulse on the "Jazib MCP" page.\n'
                  'def onPulse(par):\n'
                  "    if par.name == 'Reconnect':\n"
                  "        op('handlers').module.reconnect_now(par.owner)\n"
                  '    return\n')

    def set_first(o, names, value, what):
        for n in names:
            p = o.par[n]
            if p is not None:
                try:
                    p.val = value
                    return n
                except Exception as e:
                    warn.append('{}.{} = {!r} failed: {}'.format(o.name, n, value, e))
        warn.append('{}: no parameter for {} (tried {})'.format(o.name, what, list(names)))
        return None

    used = {
        'address': set_first(ws, ('netaddress', 'address', 'host', 'url'), '127.0.0.1', 'address'),
        'port': set_first(ws, ('port', 'netport'), port, 'port'),
        'callbacks': set_first(ws, ('callbacks', 'callbackdat'), callbacks, 'callbacks DAT'),
    }
    if ws.par['maxlines'] is not None and ws.par['clamp'] is not None:  # keep received requests from piling up
        ws.par.clamp = True
        ws.par.maxlines = 20
    set_first(recon, ('framestart',), True, 'Frame Start')
    set_first(recon, ('active',), True, 'active')
    set_first(pulse, ('op',), comp, 'op')
    set_first(pulse, ('pars',), 'Reconnect', 'pars')
    set_first(pulse, ('valuechange',), True, 'valuechange')
    if pulse.par['onpulse'] is not None:
        pulse.par.onpulse = True
    if pulse.par['custom'] is not None:
        pulse.par.custom = True

    # custom page
    page = None
    for pg in comp.customPages:
        if pg.name == 'Jazib MCP':
            page = pg
    if page is None:
        page = comp.appendCustomPage('Jazib MCP')
    hfile = _jtd_os.path.join(base, 'handlers.py')
    if comp.par['Handlersfile'] is None:
        try:
            page.appendFile('Handlersfile', label='Handlers File')
        except Exception as e:
            warn.append('appendFile failed ({}); Handlersfile is a Str par'.format(e))
            page.appendStr('Handlersfile', label='Handlers File')
    comp.par.Handlersfile.val = hfile
    try:
        comp.par.Handlersfile.default = hfile
    except Exception:
        pass
    if comp.par['Reconnect'] is None:
        page.appendPulse('Reconnect', label='Reconnect')
    if comp.par['Bridgeport'] is None:
        page.appendInt('Bridgeport', label='Bridge Port')
    comp.par.Bridgeport.val = port
    try:
        comp.par.Bridgeport.default = 9335
    except Exception:
        pass
    comp.store('handlersFile', hfile)  # fallback for handlers.handlers_file(); written once, not per frame

    status.text = _jtd_time.strftime('%Y-%m-%d %H:%M:%S') + '  installed; dialing 127.0.0.1:{}\n'.format(port)

    # ---------------------------------------------------------------- 3. probe (first live run teaches us)
    def par_list(o):
        out = []
        for p in o.pars():
            d = {'name': p.name, 'label': p.label, 'style': p.style, 'page': p.page.name if p.page is not None else ''}
            try:
                d['val'] = str(p.eval())
            except Exception as e:
                d['val'] = 'ERR ' + str(e)
            try:
                if p.isMenu:
                    d['menuNames'] = list(p.menuNames)
            except Exception:
                pass
            out.append(d)
        return out
    probe = {
        'when': _jtd_time.strftime('%Y-%m-%dT%H:%M:%S'),
        'app_version': str(getattr(app, 'version', '')), 'app_build': str(getattr(app, 'build', '')),
        'osName': str(getattr(app, 'osName', '')),
        'ws_pars': par_list(ws),
        'ws_members': [m for m in dir(ws) if not m.startswith('_')],
        'execute_pars': [p.name for p in recon.pars()],
        'parexec_pars': [p.name for p in pulse.pars()],
        'used': {k: v for k, v in used.items()},
        'Handlersfile_style': comp.par.Handlersfile.style,
        'td_has': {n: hasattr(_jtd_td, n) for n in ('infoDAT', 'ParMode', 'run', 'op', 'project', 'app',
                                                     'absTime', 'root', 'ui', 'OP', 'parent', 'me')},
        'project_attrs': {n: hasattr(project, n) for n in ('cookRate', 'realTime', 'performMode', 'name',
                                                            'folder', 'save')},
        'warnings': warn,
    }
    with open(probe_path, 'w', encoding='utf-8') as f:
        _jtd_json.dump(probe, f, indent=1, ensure_ascii=True)

    # ---------------------------------------------------------------- 4. connect, save, report
    if ws.par['active'] is not None:
        ws.par.active = True
    else:
        warn.append('ws has no "active" parameter; it will not dial')
    if save_tox:
        comp.save(tox_path)

    print('=' * 70)
    print('Jazib MCP for TouchDesigner: ' + ('built' if created else 'updated in place') + ' ' + comp.path)
    print('  ws params used: ' + ', '.join('{}={}'.format(k, v) for k, v in used.items()))
    print('  WebSocket DAT parameters: ' + ', '.join(p.name for p in ws.pars()))
    print('  probe: ' + probe_path)
    print('  saved: ' + (tox_path if save_tox else '(not saved: JTD_INSTALL_SAVE_TOX=0)'))
    print('  bridge port: {}'.format(port))
    print('  token: read from ~/Library/Application Support/JazibTDMCP/token on connect (not stored here)')
    for w in warn:
        print('  WARN ' + w)
    print('  next: watch ' + comp.path + '/status; the bridge /health should show td:true')
    print('=' * 70)
    return comp


_jtd_install()
