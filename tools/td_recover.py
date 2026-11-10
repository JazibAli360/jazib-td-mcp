#!/usr/bin/env python3
"""Zero-hands recovery after the watchdog relaunched TouchDesigner (stdlib only; T-95).

tools/td_watchdog.py starts this once per relaunched TD, on that TD's first heartbeat. One pass, never loops:
  1. wait (bounded, --timeout) for TD's /jazib_mcp to dial the bridge on 127.0.0.1:9335 (bridge /health td:true;
     starts the bridge through the MCP server if nobody has)
  2. td_reload                      the .toe carries an old copy of handlers.py; load the one on disk
  3. park lab COMPs                 allowCooking off for every COMP in --lab EXCEPT the ones named in
                                    logs/active_lanes.json (builders keep it current: tools/lane.py) and the ones
                                    td_exec touched in the last --recent-min minutes (exec.log); never un-parks
  4. td_autosave minutes=5          (T-71/T-77)
  5. td_save_project                a fresh numbered save of the recovered state
Every MCP call goes through `node test/mcp_client.mjs` (the same path Claude Code uses, logged in calls.jsonl).
Writes logs/recovery.log and ends with one line starting "TD recovered" (or "TD recovery incomplete") for monitors;
the same line goes to logs/watchdog.log as event "recovered". Idempotent: logs/recovery.state.json remembers the
TD pid it finished for (a second run for that pid exits at once) and logs/recovery.lock stops two runs at once.

Usage (from jazib-td-mcp/):  python3 tools/td_recover.py [--pid <td pid>] [--dry] [--timeout 300]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.environ.get('JTD_STATE_DIR') or os.path.expanduser('~/Library/Application Support/JazibTDMCP')
LOGS = os.path.join(HERE, 'logs')
LANES_FILE = os.path.join(LOGS, 'active_lanes.json')
STATE_FILE = os.path.join(LOGS, 'recovery.state.json')
LOCK_FILE = os.path.join(LOGS, 'recovery.lock')
REC_LOG = os.path.join(LOGS, 'recovery.log')
WD_LOG = os.path.join(LOGS, 'watchdog.log')
PORT = int(os.environ.get('JTD_BRIDGE_PORT') or 9335)
LAB = '/project1/lab'
LOCK_STALE_S = 900
LANE_MAX_AGE_S = 6 * 3600


# ------------------------------------------------------------------ pure (unit-tested)

def iso(t=None):
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time() if t is None else t))


def parse_iso(s):
    try:
        return time.mktime(time.strptime(str(s)[:19], '%Y-%m-%dT%H:%M:%S'))
    except (ValueError, TypeError):
        return None


def lanes_keep(lanes, now, max_age=LANE_MAX_AGE_S):
    """Names of COMPs live lanes are working on (basename of a path or a bare name). Entries older than max_age are
    ignored (a lane that crashed without `lane.py remove`); an entry with no readable time is kept (safe side)."""
    keep, stale = set(), []
    for comp, v in (lanes or {}).items():
        t = parse_iso(v.get('time')) if isinstance(v, dict) else None
        if t is not None and now - t > max_age:
            stale.append(comp)
            continue
        keep.add(str(comp).rstrip('/').rsplit('/', 1)[-1])
    return keep, stale


def recent_lab_comps(lines, since_iso_utc, lab=LAB):
    """CLAUDE.md "never park a COMP someone is working on": lab COMP names that td_exec calls (logs/exec.log JSON
    lines, UTC times) touched since since_iso_utc. Kept cooking as a backstop to the lanes file."""
    import re
    rx = re.compile(re.escape(lab.rstrip('/')) + r'/([A-Za-z_][A-Za-z0-9_]*)')
    out = set()
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if str(r.get('time', ''))[:19] < since_iso_utc[:19]:
            continue
        out.update(rx.findall(str(r.get('code') or '')[:2000]))
    return out


def park_code(lab, keep):
    """td_exec code: allowCooking off for the lab's child COMPs not in keep; never turns anything on."""
    return ('# td_recover (T-95): park idle lab COMPs; lanes in logs/active_lanes.json stay as they are\n'
            'L = op({lab!r}); keep = set({keep!r}); parked = []; kept = []\n'
            'for c in (list(L.children) if L is not None else []):\n'
            "    if not c.isCOMP or c.OPType in ('annotateCOMP', 'windowCOMP'):\n"
            '        continue\n'
            '    if c.name in keep:\n'
            '        kept.append(c.name)\n'
            '    elif c.allowCooking:\n'
            '        c.allowCooking = False\n'
            '        parked.append(c.name)\n'
            "{{'lab': L is not None, 'parked': parked, 'kept': kept}}").format(lab=lab, keep=sorted(keep))


def plan(lab, keep):
    """The fixed steps: (label, tool, args)."""
    return [('reload', 'td_reload', {}),
            ('park', 'td_exec', {'code': park_code(lab, keep)}),
            ('autosave', 'td_autosave', {'minutes': 5}),
            ('save', 'td_save_project', {})]


def already_done(state, pid):
    return bool(state) and pid is not None and state.get('pid') == pid and state.get('status') == 'done'


def summary_line(pid, results, keep):
    bad = [k for k, r in results if not r['ok']]
    head = 'TD recovered' if not bad else 'TD recovery incomplete'
    parts = ['{}: pid {}'.format(head, pid if pid is not None else '?')]
    for k, r in results:
        parts.append('{}={}'.format(k, 'ok' if r['ok'] else 'FAILED'))
    if keep:
        parts.append('lanes kept: ' + ', '.join(sorted(keep)))
    return '; '.join(parts)


# ------------------------------------------------------------------ side effects

def note(msg, **kw):
    os.makedirs(LOGS, exist_ok=True)
    line = '{} {}{}'.format(iso(), msg, (' ' + json.dumps(kw)) if kw else '')
    with open(REC_LOG, 'a') as f:
        f.write(line + '\n')
    print('[td_recover]', line, flush=True)


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def take_lock():
    os.makedirs(LOGS, exist_ok=True)
    try:
        if time.time() - os.path.getmtime(LOCK_FILE) > LOCK_STALE_S:
            os.remove(LOCK_FILE)
    except OSError:
        pass
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return True


def health():
    try:
        tok = open(os.path.join(STATE_DIR, 'token')).read().strip()
        req = urllib.request.Request('http://127.0.0.1:{}/health'.format(PORT), headers={'x-jtd-token': tok})
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def node_bin():
    for c in (shutil.which('node'), '/opt/homebrew/bin/node', '/usr/local/bin/node'):
        if c and os.path.exists(c):
            return c
    return 'node'


def mcp(tool, args, timeout=240):
    """One MCP tool call via test/mcp_client.mjs. Returns {'ok', 'out'}."""
    cmd = [node_bin(), os.path.join(HERE, 'test', 'mcp_client.mjs'), tool, json.dumps(args)]
    try:
        p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout + p.stderr).strip()
        ok = p.returncode == 0 and 'not connected' not in out[:200]
        return {'ok': ok, 'out': out[-600:]}
    except Exception as e:
        return {'ok': False, 'out': str(e)[:300]}


def wait_td(pid, timeout):
    """Bounded wait for TD (pid, if given) on the bridge. Starts the bridge once through the MCP server if absent."""
    t0 = time.time()
    started = False
    while time.time() - t0 < timeout:
        h = health()
        if h is None and not started:
            started = True
            mcp('--list', {}, timeout=60)  # server.js ensureBridge() starts the detached bridge
            continue
        if h and h.get('td'):
            hp = (h.get('tdInfo') or {}).get('pid')
            if pid is None or hp in (None, pid):
                return h
        time.sleep(3)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pid', type=int, default=None, help='the relaunched TD pid (from the watchdog)')
    ap.add_argument('--timeout', type=float, default=300.0, help='max wait for TD on the bridge (s)')
    ap.add_argument('--lab', default=LAB)
    ap.add_argument('--recent-min', type=float, default=10.0,
                    help='also keep lab COMPs td_exec touched in the last N minutes (exec.log)')
    ap.add_argument('--dry', action='store_true', help='print the plan, call nothing')
    a = ap.parse_args()
    keep, stale = lanes_keep(read_json(LANES_FILE, {}), time.time())
    try:
        with open(os.path.join(LOGS, 'exec.log'), 'rb') as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 2 * 1024 * 1024))
            tail = f.read().decode('utf-8', 'replace').splitlines()[1:]
    except OSError:
        tail = []
    since = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time() - a.recent_min * 60))
    recent = recent_lab_comps(tail, since, a.lab)
    keep = keep | recent
    steps = plan(a.lab, keep)
    if a.dry:
        print(json.dumps({'pid': a.pid, 'keep': sorted(keep), 'stale_lanes': stale,
                          'steps': [[k, t, x] for k, t, x in steps]}, indent=1))
        return 0
    state = read_json(STATE_FILE, {})
    if already_done(state, a.pid):
        note('already recovered for this TD; nothing to do', pid=a.pid)
        return 0
    if not take_lock():
        note('another td_recover is running (logs/recovery.lock); exiting')
        return 0
    try:
        write_json(STATE_FILE, {'pid': a.pid, 'status': 'running', 'time': iso()})
        note('start', pid=a.pid, keep=sorted(keep), stale_lanes=stale)
        h = wait_td(a.pid, a.timeout)
        if not h:
            line = 'TD recovery incomplete: pid {}; TD did not reach the bridge within {:.0f} s'.format(a.pid, a.timeout)
            write_json(STATE_FILE, {'pid': a.pid, 'status': 'failed', 'time': iso(), 'line': line})
            note(line)
            _wd_event(line, a.pid)
            return 1
        results = []
        for k, tool, args in steps:
            r = mcp(tool, args)
            results.append((k, r))
            note('step ' + k, ok=r['ok'], out=r['out'][-300:])
        line = summary_line(a.pid, results, keep)
        write_json(STATE_FILE, {'pid': a.pid, 'status': 'done' if all(r['ok'] for _k, r in results) else 'partial',
                                'time': iso(), 'line': line})
        note(line)
        _wd_event(line, a.pid)
        return 0
    finally:
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass


def _wd_event(line, pid):
    try:
        with open(WD_LOG, 'a') as f:
            f.write(json.dumps({'time': iso(), 'event': 'recovered', 'td_pid': pid, 'line': line}) + '\n')
    except OSError:
        pass


if __name__ == '__main__':
    sys.exit(main())
