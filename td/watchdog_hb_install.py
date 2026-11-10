"""Jazib TD watchdog heartbeat -- run inside TouchDesigner (Textport or td_exec):
    exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/td/watchdog_hb_install.py').read(), globals())

Builds /watchdog_hb (a Base COMP with one Execute DAT) that writes a heartbeat file about once a second, and saves it
as td/JazibWatchdogHB.tox (drag that into the show project; save the project so it is always there).
tools/td_watchdog.py reads the file. This beat comes from frame callbacks only, so it also stops when TD's frame loop
stops while TD still answers the network (T-78/T-95: absTime.frame froze). handlers.py writes a second heartbeat
(heartbeat_mcp.json) from the WebSocket callbacks; the watchdog kills only when BOTH are stale, no MCP reply came, and
a hang is evident (crash dialog / uninterruptible process) or both stayed silent past --hard-stale.
Pure ASCII (TD reads it).
"""
import os

_HB_TEXT = r'''# Jazib TD watchdog heartbeat (written by td/watchdog_hb_install.py). Do not rename this COMP.
import json, os, time
HB = os.path.expanduser('~/Library/Application Support/JazibTDMCP/heartbeat.json')
_last = [0.0]


def _beat():
    now = time.time()
    if now - _last[0] < 1.0:
        return
    _last[0] = now
    d = {'time': now, 'pid': os.getpid(), 'frame': int(absTime.frame), 'fps': float(project.cookRate),
         'project': os.path.join(str(project.folder), str(project.name)), 'build': str(app.build), 'src': 'frame'}
    try:
        os.makedirs(os.path.dirname(HB), exist_ok=True)
        tmp = HB + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(d, f)
        os.replace(tmp, HB)
    except Exception:
        pass


def onFrameStart(frame):
    _beat()
    return


def onFrameEnd(frame):
    _beat()
    return
'''

_root = op('/')
_c = _root.op('watchdog_hb')
if _c is None:
    _c = _root.create(baseCOMP, 'watchdog_hb')
_c.nodeX, _c.nodeY = 0, -400
_c.comment = 'Heartbeat for tools/td_watchdog.py: no beat for N s = TD hung -> watchdog relaunches the show .toe.'
_x = _c.op('hb')
if _x is None:
    _x = _c.create(executeDAT, 'hb')
_x.text = _HB_TEXT
_x.par.frameend = True
if getattr(_x.par, 'framestart', None) is not None:  # par['x'] returned None here: framestart never got set (T-97)
    _x.par.framestart = True  # T-95: both frame callbacks beat (1 s rate limit), whichever fires
# T-97: after its text changed, the live Execute DAT stopped firing frame callbacks until active was toggled
_x.par.active = False
_x.par.active = True
_tox = '~/Documents/StageLab_PrismFest/jazib-td-mcp/td/JazibWatchdogHB.tox'
_c.save(_tox)
print('watchdog heartbeat ready: /watchdog_hb, saved', _tox)
