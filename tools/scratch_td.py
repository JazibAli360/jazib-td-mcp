#!/usr/bin/env python3
"""Side TDs: the scratch TD (T-83) and the build TDs b2 / b3 (T-120) beside the main TD (stdlib only; macOS).

Known crash patterns (T-64, T-70, T-74, T-76, T-79) must never run on the main TD, where the user and the builder
lanes work. This starts a SECOND TouchDesigner on a throwaway project whose /jazib_mcp dials its own bridge port
(default 9336), so nothing it does reaches the main session's bridge (9335), exec.log or calls.jsonl, and a crash
there loses only the scratch TD.

  python3 tools/scratch_td.py start [--port 9336]   # fresh projects/scratch/Scratch.toe + bridge + TD
  python3 tools/scratch_td.py status
  python3 tools/scratch_td.py run "<python>" [--frames N] [--timeout S]   # td_exec on the scratch TD, JSON out
  python3 tools/scratch_td.py stop                              # kills ONLY the scratch TD + its bridge
  python3 tools/scratch_td.py watch                             # side watchdog: relaunch any side TD that died

From the MCP: td_exec {code, target: 'scratch'}.

Build TDs (T-120, user 26 Oct: "you can even have 3 td builds live"; b4 / b5 added: "use more tds"): --name b2 / b3 /
b4 / b5 (ports 9337-9340) work the
same way on projects/build2/Build2.toe / projects/build3/Build3.toe, but KEEP their project: it is built once and
the newest Build2[.N].toe is reopened on every start; autosave is on (5 min); the boot sets JTD_INSTANCE=b2 (hello
tdInfo.instance; no heartbeat_mcp.json; the crash guard stays on); logs in logs/b2/, state in scratch_td_b2.json.
Build there, then td_bring_home {comp, from:'b2'} copies the COMP into the main TD and saves the main .toe.
  python3 tools/scratch_td.py start --name b2 ; ... run --name b2 "<python>" ; ... stop --name b2
Start one side TD at a time (a start waits while another is 'launching').

How it stays apart from the main TD:
  - Scratch.toe is rebuilt from TouchDesigner's own empty NewProject.toe on every start (toeexpand -> add one root
    Execute DAT `scratch_boot` -> toecollapse). The boot DAT sets JTD_SCRATCH=1, JTD_BRIDGE_PORT, JTD_TD_DIR,
    JTD_AUTOSAVE_MIN=0 and JTD_INSTALL_SAVE_TOX=0 in the scratch TD's own process, then execs td/install.py, so
    /jazib_mcp is built exactly as install.py builds it, dialing the scratch port, never autosaving and never
    rewriting td/JazibTDMCP.tox. There is no /watchdog_hb, so the main heartbeat file is never written by it.
  - TD is launched as its own binary with the .toe in argv (a new instance; plain `open -a` would hand the file to
    the running main TD), so its command line names projects/scratch/ (or projects/buildN/; the watchdog's
    is_scratch_td, T-82).
  - Its pid goes to scratch_td[_<name>].json in the state dir (state 'launching' with the pids that ran before, then
    'running' with its pid); tools/td_watchdog.py never manages or kills those pids.
  - stop kills only the pid in that state file (never the main heartbeat's pid) and only a bridge on a port that is
    not 9335.
  - Logs: logs/<name>/ (exec.log, boot.log, bridge.out, td.out).
"""
import argparse
import json
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.environ.get('JTD_STATE_DIR') or os.path.expanduser('~/Library/Application Support/JazibTDMCP')
SCRATCH_FILE = os.path.join(STATE_DIR, 'scratch_td.json')
HB_FILE = os.path.join(STATE_DIR, 'heartbeat.json')
TOKEN_FILE = os.path.join(STATE_DIR, 'token')
APP = os.environ.get('JTD_TD_APP') or '/Applications/TouchDesigner 2.app'
MAIN_PORT = 9335
DEFAULT_PORT = int(os.environ.get('JTD_SCRATCH_PORT') or 9336)
SCRATCH_DIR = os.path.join(HERE, 'projects', 'scratch')
TOE = os.path.join(SCRATCH_DIR, 'Scratch.toe')
LOG_DIR = os.path.join(HERE, 'logs', 'scratch')
TEMPLATE = os.path.join(APP, 'Contents', 'Resources', 'tfs', 'Samples', 'Setup', 'Base', 'NewProject.toe')
LAUNCH_GRACE = 120.0  # s: matches the watchdog's SCRATCH_LAUNCH_GRACE

# name -> (default port, folder under projects/, toe name, keeps its project). 'scratch' = exactly T-83.
INSTANCES = {
    'scratch': (DEFAULT_PORT, 'scratch', 'Scratch.toe', False),
    'b2': (int(os.environ.get('JTD_B2_PORT') or 9337), 'build2', 'Build2.toe', True),
    'b3': (int(os.environ.get('JTD_B3_PORT') or 9338), 'build3', 'Build3.toe', True),
    'b4': (int(os.environ.get('JTD_B4_PORT') or 9339), 'build4', 'Build4.toe', True),  # user 26 Oct: "use more tds"
    'b5': (int(os.environ.get('JTD_B5_PORT') or 9340), 'build5', 'Build5.toe', True),
}


def inst(name):
    """Pure: {name, port, dir, toe, keep, state, logs} for a side TD name."""
    if name not in INSTANCES:
        raise SystemExit('unknown side TD {!r} (one of {})'.format(name, ', '.join(INSTANCES)))
    port, folder, toe, keep = INSTANCES[name]
    d = os.path.join(HERE, 'projects', folder)
    return {'name': name, 'port': port, 'dir': d, 'toe': os.path.join(d, toe), 'keep': keep,
            'state': state_file(name), 'logs': os.path.join(HERE, 'logs', name)}


def state_file(name):
    """Pure: scratch keeps scratch_td.json (T-83); builds get scratch_td_<name>.json (the watchdog reads both)."""
    return SCRATCH_FILE if name == 'scratch' else os.path.join(STATE_DIR, 'scratch_td_{}.json'.format(name))


# ------------------------------------------------------------------ pure (unit-tested)

def encode_dat_text(text):
    """Pure: a Text/Execute DAT's .text file as toeexpand writes it: b'2\\n*', 1x1 table header, string cell length,
    then the bytes (ASCII). Byte-identical to TD's own files (test_scratch_td)."""
    b = text.encode('ascii')
    return b'2\n*' + struct.pack('>IIIIII', 1, 1, 1, 1, 2, len(b)) + b


def decode_dat_text(data):
    """Pure: inverse of encode_dat_text (only the 1-cell form)."""
    if not data.startswith(b'2\n*') or len(data) < 27:
        raise ValueError('not a 1-cell DAT text file')
    n = struct.unpack('>I', data[23:27])[0]
    return data[27:27 + n].decode('ascii')


def boot_env(port, td_dir, name='scratch'):
    """Pure: what the boot DAT puts in its TD's environment. scratch: JTD_SCRATCH=1 + autosave off (T-83). A build
    TD: JTD_INSTANCE=<name> + autosave 5 min, no JTD_SCRATCH (crash guard stays on; T-120). Never a .tox write."""
    env = {'JTD_BRIDGE_PORT': str(int(port)), 'JTD_TD_DIR': td_dir, 'JTD_INSTALL_SAVE_TOX': '0', 'JTD_INSTANCE': name}
    if name == 'scratch':
        env.update({'JTD_SCRATCH': '1', 'JTD_AUTOSAVE_MIN': '0'})
    else:
        env['JTD_AUTOSAVE_MIN'] = '5'
    return env


def boot_text(port, td_dir, log_dir, name='scratch'):
    """Pure: the scratch_boot Execute DAT's script (onStart, with onFrameStart as a fallback; runs once)."""
    return '''# Side TD boot (tools/scratch_td.py, LEARNINGS T-83 / T-120): {name}. Scratch is rebuilt on every start; a build
# TD keeps and autosaves its project. Installs /jazib_mcp with td/install.py on its own bridge port, no .tox written.
import os
import traceback
PORT = {port}
TD_DIR = {td_dir!r}
LOG = {log!r}


def _boot():
    if os.environ.get('JTD_SCRATCH_BOOTED') == '1':
        return
    os.environ['JTD_SCRATCH_BOOTED'] = '1'
    os.environ.update({env!r})
    msg = 'ok'
    try:
        g = {{'__name__': '__jtd_scratch_install__'}}
        exec('from td import *', g)
        p = os.path.join(TD_DIR, 'install.py')
        with open(p) as f:
            exec(compile(f.read(), p, 'exec'), g)
    except Exception:
        msg = traceback.format_exc()
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'a') as f:
            f.write('{{}} pid {{}} port {{}}: {{}}\\n'.format(__import__('time').strftime('%Y-%m-%dT%H:%M:%S'),
                                                   os.getpid(), PORT, msg))
    except Exception:
        pass


def onStart():
    _boot()
    return


def onFrameStart(frame):
    _boot()
    return
'''.format(port=int(port), td_dir=td_dir, log=os.path.join(log_dir, 'boot.log'), name=name,
           env=boot_env(port, td_dir, name))


BOOT_N = 'DAT:execute\ntile -200 -200 130 90\nflags =  viewer 1 parlanguage 0\nend\n'
BOOT_PARM = '?\nstart 0 on\nframestart 0 on\nlanguage 0 python\n?\n'


def new_pids(before, after):
    """Pure: pids in after that were not in before."""
    b = set(before)
    return sorted(p for p in after if p not in b)


def stop_targets(info, alive, main_hb_pid, main_port=MAIN_PORT):
    """Pure: (pid to kill or None, why). Never the main heartbeat's pid; never when the state names the main port."""
    if not info:
        return None, 'no scratch_td.json'
    if int(info.get('port') or 0) == main_port:
        return None, 'scratch_td.json names the main port; refusing'
    p = info.get('pid')
    if p is None:
        return None, 'no pid recorded'
    if p == main_hb_pid:
        return None, 'pid {} is the main TD (heartbeat); refusing'.format(p)
    if p not in alive:
        return None, 'pid {} not running'.format(p)
    return p, 'scratch pid {}'.format(p)


def newest_toe(listing, toe_name):
    """Pure: the newest save of a build project in a folder listing: Build2.toe / Build2.N.toe -> highest N (plain =
    0); CrashAutoSave and other names are ignored. None when there is none."""
    base = toe_name[:-4]
    best = None
    for n in listing:
        m = re.match(r'^{}(?:\.(\d+))?\.toe$'.format(re.escape(base)), n)
        if m:
            k = int(m.group(1) or 0)
            if best is None or k > best[0]:
                best = (k, n)
    return best and best[1]


def launch_blocked(states, now, me):
    """Pure: the name of another side TD that is still 'launching' (its new pid is not known yet, so a second launch
    could take it for its own), else None. states = {name: state dict}."""
    for n, st in states.items():
        if n != me and st and st.get('state') == 'launching' and now - float(st.get('time', 0)) < LAUNCH_GRACE:
            return n
    return None


# ------------------------------------------------------------------ side effects

def td_pids():
    exe = os.path.join(APP, 'Contents', 'MacOS', 'TouchDesigner')
    out = subprocess.run(['pgrep', '-f', exe], capture_output=True, text=True).stdout.split()
    return sorted(int(p) for p in out if p.strip().isdigit())


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_state(d, path=SCRATCH_FILE):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(d, f)
    os.replace(tmp, path)


def token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()


def http(port, path, body=None, timeout=5.0):
    req = urllib.request.Request('http://127.0.0.1:{}{}'.format(port, path), method='POST' if body is not None else 'GET',
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={'x-jtd-token': token(), 'content-type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except ValueError:
            return {'ok': False, 'error': 'HTTP {}'.format(e.code)}
    except (OSError, ValueError) as e:
        return None if body is None else {'ok': False, 'error': str(e)}


def build_toe(port, out=TOE, name='scratch'):
    """Fresh side-TD .toe: TD's empty NewProject.toe + the root scratch_boot Execute DAT. Scratch: old saves go."""
    tools = os.path.join(APP, 'Contents', 'MacOS')
    folder = os.path.dirname(out)
    logs = os.path.join(HERE, 'logs', name)
    tmp = tempfile.mkdtemp(prefix='jtd_scratch_')
    try:
        shutil.copy2(TEMPLATE, os.path.join(tmp, 'Scratch.toe'))
        # toeexpand / toecollapse exit 1 even when they worked (seen 26 Oct, 31550): check the files instead
        subprocess.run([os.path.join(tools, 'toeexpand'), 'Scratch.toe'], cwd=tmp, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        d = os.path.join(tmp, 'Scratch.toe.dir')
        toc = os.path.join(tmp, 'Scratch.toe.toc')
        if not (os.path.isdir(d) and os.path.isfile(toc)):
            raise RuntimeError('toeexpand did not expand ' + TEMPLATE)
        with open(os.path.join(d, 'scratch_boot.n'), 'w') as f:
            f.write(BOOT_N)
        with open(os.path.join(d, 'scratch_boot.parm'), 'w') as f:
            f.write(BOOT_PARM)
        with open(os.path.join(d, 'scratch_boot.text'), 'wb') as f:
            f.write(encode_dat_text(boot_text(port, os.path.join(HERE, 'td'), logs, name)))
        with open(toc) as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
        lines += ['scratch_boot.n', 'scratch_boot.parm', 'scratch_boot.text']
        with open(toc, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        os.remove(os.path.join(tmp, 'Scratch.toe'))
        subprocess.run([os.path.join(tools, 'toecollapse'), 'Scratch.toe'], cwd=tmp, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        built = os.path.join(tmp, 'Scratch.toe')
        if not os.path.isfile(built):
            raise RuntimeError('toecollapse made no Scratch.toe')
        if name == 'scratch' and os.path.isdir(folder):  # disposable: old saves / crash autosaves go
            for n in os.listdir(folder):
                p = os.path.join(folder, n)
                if n.endswith('.toe') or n in ('Backup', 'Log', 'TDImportCache'):
                    shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
        os.makedirs(folder, exist_ok=True)
        shutil.move(built, out)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def detach(argv, out, cwd, env=None):
    """Start argv fully detached (T-211): a shell backgrounds it and exits at once, so the process is re-parented to
    launchd and outlives whoever started it (stopping the side watchdog's task used to kill the TDs it relaunched)."""
    subprocess.run(['/bin/sh', '-c', '"$@" </dev/null >>"$JTD_OUT" 2>&1 &', 'sh'] + list(argv), cwd=cwd,
                   env=dict(env or os.environ, JTD_OUT=out), start_new_session=True, check=True, timeout=10)


def ensure_bridge(port, log_dir=LOG_DIR):
    if port == MAIN_PORT:
        raise SystemExit('refusing: port {} is the main bridge'.format(port))
    h = http(port, '/health')
    if h:
        return h
    os.makedirs(log_dir, exist_ok=True)
    env = dict(os.environ, JTD_BRIDGE_PORT=str(port))
    detach(['node', os.path.join(HERE, 'src', 'bridge.js'), 'serve'], os.path.join(log_dir, 'bridge.out'), HERE, env)
    for _ in range(40):
        time.sleep(0.25)
        h = http(port, '/health')
        if h:
            return h
    raise SystemExit('side bridge did not start on {} ({}/bridge.out)'.format(port, log_dir))


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def kill(pid, wait_s=6.0):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return True
        t0 = time.time()
        while time.time() - t0 < wait_s:
            if not alive(pid):
                return True
            time.sleep(0.3)
    return False


def main_hb_pid():
    hb = read_json(HB_FILE) or {}
    return hb.get('pid')


def cmd_status(port, name='scratch'):
    i = inst(name)
    info = read_json(i['state'])
    h = http(int((info or {}).get('port') or port), '/health')
    up = bool(info and alive(info.get('pid')))
    out = {'name': name, 'state': info, 'alive': up, 'bridge': h, 'td_pids': td_pids(), 'main_heartbeat_pid': main_hb_pid()}
    if name == 'scratch':  # T-83 keys kept
        out.update(scratch=info, scratch_alive=up)
    return out


def other_side_pids(name):
    out = set()
    for n in INSTANCES:
        if n != name:
            p = (read_json(state_file(n)) or {}).get('pid')
            if p:
                out.add(p)
    return out


def cmd_start(port, wait=150, name='scratch'):
    """One start at a time across lanes and the side watchdog (a lock, so two callers never launch twice)."""
    import fcntl
    os.makedirs(os.path.join(HERE, 'logs'), exist_ok=True)
    with open(os.path.join(HERE, 'logs', 'side_start.lock'), 'w') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        return _start(port, wait, name)


def _start(port, wait=150, name='scratch'):
    i = inst(name)
    info = read_json(i['state'])
    if info and info.get('pid') and alive(info['pid']) and info['pid'] != main_hb_pid():
        return dict(cmd_status(port, name), note='already running')
    busy = launch_blocked({n: read_json(state_file(n)) for n in INSTANCES}, time.time(), name)
    if busy:
        raise SystemExit('side TD {} is still launching: start {} when it is up'.format(busy, name))
    os.makedirs(i['logs'], exist_ok=True)
    if i['keep']:  # build TD: reopen its newest save; build it only the first time
        os.makedirs(i['dir'], exist_ok=True)
        last = newest_toe(os.listdir(i['dir']), os.path.basename(i['toe']))
        toe = os.path.join(i['dir'], last) if last else build_toe(port, i['toe'], name)
    else:
        toe = build_toe(port, i['toe'], name)
    ensure_bridge(port, i['logs'])
    before = td_pids()
    write_state({'state': 'launching', 'time': time.time(), 'before': before, 'port': port, 'project': toe,
                 'name': name}, i['state'])
    # The binary itself with the .toe in argv (not `open`, which passes the file by Apple Event): the watchdog's
    # is_scratch_td() spots '/projects/scratch/' or '/projects/buildN/' in the command line (T-82), and the state
    # file covers the rest.
    exe = os.path.join(APP, 'Contents', 'MacOS', 'TouchDesigner')
    detach([exe, toe], os.path.join(i['logs'], 'td.out'), i['dir'])
    pid = None
    others = other_side_pids(name)
    for _ in range(120):
        time.sleep(0.5)
        new = [p for p in new_pids(before, td_pids()) if p not in others]
        if new:
            pid = new[-1]
            break
    if pid is None:
        write_state({'state': 'failed', 'time': time.time(), 'port': port, 'project': toe, 'name': name}, i['state'])
        raise SystemExit('no new TouchDesigner process appeared')
    write_state({'state': 'running', 'time': time.time(), 'pid': pid, 'port': port, 'project': toe, 'before': before,
                 'name': name}, i['state'])
    t0 = time.time()
    h = None
    while time.time() - t0 < wait:
        h = http(port, '/health')
        if h and h.get('td'):
            break
        if not alive(pid):
            raise SystemExit('side TD {} ({}) exited during boot ({}/boot.log)'.format(name, pid, i['logs']))
        time.sleep(1.0)
    return {'name': name, 'pid': pid, 'port': port, 'project': toe, 'connected': bool(h and h.get('td')),
            'tdInfo': (h or {}).get('tdInfo'), 'boot_s': round(time.time() - t0, 1)}


def cmd_stop(port, name='scratch'):
    i = inst(name)
    info = read_json(i['state'])
    pid, why = stop_targets(info, td_pids(), main_hb_pid())
    out = {'name': name, 'why': why}
    if pid is not None:
        if i['keep']:  # a build TD keeps its work: save in place first (T-120)
            r = http(int(info.get('port') or port), '/ctl', {'cmd': 'save_project', 'args': {}, 'timeoutMs': 30000},
                     timeout=35)
            out['saved'] = (r or {}).get('result') if r and r.get('ok') else {'error': (r or {}).get('error')}
        out['killed'] = pid
        out['ok'] = kill(pid)
    bport = int((info or {}).get('port') or port)
    h = http(bport, '/health') if bport != MAIN_PORT else None
    if h and h.get('pid') and bport != MAIN_PORT:
        out['bridge_killed'] = h['pid']
        out['bridge_ok'] = kill(int(h['pid']), 3.0)
    if pid is not None or not (info and alive(info.get('pid'))):
        try:
            os.remove(i['state'])
        except OSError:
            pass
    return out


def exec_log(row, name='scratch'):
    d = inst(name)['logs']
    os.makedirs(d, exist_ok=True)
    row = dict(row, time=time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()), pid=os.getpid(), target=name,
               client='scratch_td.py')
    with open(os.path.join(d, 'exec.log'), 'a') as f:
        f.write(json.dumps(row) + '\n')


def identity_ok(name, td_info):
    """Pure: does the TD on a side port say it is `name`? scratch: not tdInfo.scratch false (T-83; an older install
    has no instance); b2/b3: tdInfo.instance must be the name."""
    ti = td_info or {}
    if name == 'scratch':
        return ti.get('scratch') is not False and ti.get('instance') in (None, 'scratch')
    return ti.get('instance') == name


def cmd_run(port, code, frames=0, timeout=60.0, name='scratch'):
    info = read_json(inst(name)['state']) or {}
    port = int(info.get('port') or port)
    if port == MAIN_PORT:
        raise SystemExit('refusing: port {} is the main bridge'.format(port))
    h = http(port, '/health')
    if not (h and h.get('td')):
        raise SystemExit('{} TD not connected on {}: python3 tools/scratch_td.py start --name {}'.format(name, port, name))
    if not identity_ok(name, h.get('tdInfo')):
        raise SystemExit('the TD on {} is not the {} TD (tdInfo {}); refusing'.format(port, name, h.get('tdInfo')))
    exec_log({'phase': 'start', 'code': code}, name)
    r = http(port, '/ctl', {'cmd': 'exec', 'args': {'code': code, 'frames': int(frames)}, 'timeoutMs': int(timeout * 1000)},
             timeout=timeout + 5)
    exec_log({'phase': 'end', 'code': code, 'ok': bool(r and r.get('ok')),
              ('result' if r and r.get('ok') else 'error'): str((r or {}).get('result' if r and r.get('ok') else 'error'))[:500]},
             name)
    return r


WATCH_LOG = os.path.join(HERE, 'logs', 'side_watchdog.log')
WATCH_MAX = 4          # relaunches per name within WATCH_WINDOW s, then give up on it (crash loop)
WATCH_WINDOW = 900.0


HANG_S = 300.0         # a side TD that answers no ping for this long with ~0% CPU is hung (T-147/T-148)
HANG_CPU = 2.0
HANG_S2 = 600.0        # second tier (T-203): a hang that idles at 10-15 % CPU (b3 27 Oct) is caught after this long
HANG_CPU2 = 25.0
ACT_GAP = 60.0         # at most one kill/relaunch per this many seconds (a kill can freeze other TDs: T-148)


def hang_due(first_fail, now, cpu):
    """Pure: is a side TD hung? first_fail = time its pings started failing (None = answering)."""
    if first_fail is None or cpu is None:
        return False
    waited = now - first_fail
    return (waited >= HANG_S and cpu < HANG_CPU) or (waited >= HANG_S2 and cpu < HANG_CPU2)


def cpu_of(pid):
    try:
        return float(subprocess.run(['ps', '-o', '%cpu=', '-p', str(int(pid))], capture_output=True, text=True,
                                    timeout=5).stdout.strip())
    except (ValueError, OSError, subprocess.SubprocessError):
        return None


def watch_due(state, is_alive, recent, now):
    """Pure: should the side watchdog relaunch this side TD? Only one that was 'running' (a stop removes the state, so
    stopped TDs stay down) whose pid is gone, and not after WATCH_MAX relaunches in WATCH_WINDOW s."""
    if not state or state.get('state') != 'running' or not state.get('pid') or is_alive:
        return False
    return len([t for t in recent if now - t < WATCH_WINDOW]) < WATCH_MAX


def _wlog(row):
    row['time'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    line = json.dumps(row)
    print(line, flush=True)
    with open(WATCH_LOG, 'a') as f:
        f.write(line + '\n')


def cmd_watch(every=10.0):
    """Side watchdog (user 26 Oct: "make sure ur watchdogs are updated correctly"): the main watchdog
    (td_watchdog.py) manages only the main TD (T-82); this relaunches any side TD that died (its newest save for a
    build TD, a fresh Scratch.toe for scratch) after clicking away TD alerts (T-124: Vulkan 'Exiting' dialogs), and
    kills + relaunches a HUNG one (no `status` reply for HANG_S with < HANG_CPU % CPU: T-148), one action per ACT_GAP."""
    sys.path.insert(0, os.path.join(HERE, 'tools'))
    from td_watchdog import WAKE_GRACE_S, dismiss_td_alerts, slept_s
    hist = {n: [] for n in INSTANCES}
    gave_up = set()
    fails = {}             # name -> (pid, time its pings started failing)
    last_act = [0.0]
    _wlog({'event': 'start', 'names': sorted(INSTANCES), 'max': WATCH_MAX, 'window': WATCH_WINDOW})
    prev = (None, None)
    wake_until = 0.0
    while True:
        slept = slept_s(prev[0], prev[1], time.time(), time.monotonic())
        prev = (time.time(), time.monotonic())
        if slept > 30:  # T-219: the Mac slept; frozen side TDs are not hung, restart their hang timers
            fails.clear()
            wake_until = time.time() + WAKE_GRACE_S
            _wlog({'event': 'slept', 'seconds': round(slept), 'grace_s': WAKE_GRACE_S})
        for n in INSTANCES:
            st = read_json(state_file(n))
            pid = (st or {}).get('pid')
            dead = bool(st and st.get('state') == 'running' and pid and not alive(pid))
            if fails.get(n, (pid,))[0] != pid or not (st and st.get('state') == 'running'):
                fails.pop(n, None)  # T-210: a new pid (restart) or a stop starts the hang timer afresh
            if not dead and st and st.get('state') == 'running' and pid:
                r = http(int(st.get('port') or INSTANCES[n][0]), '/ctl', {'cmd': 'status', 'args': {}, 'timeoutMs': 15000},
                         timeout=20)
                if r and r.get('ok'):
                    fails.pop(n, None)
                    continue
                fails.setdefault(n, (pid, time.time()))
                cpu = cpu_of(pid)
                if (not hang_due(fails[n][1], time.time(), cpu) or time.time() - last_act[0] < ACT_GAP
                        or time.time() < wake_until):
                    continue
                if not watch_due(st, False, hist[n], time.time()):
                    if n not in gave_up:
                        gave_up.add(n)
                        _wlog({'event': 'gave_up', 'name': n, 'pid': pid, 'relaunches': len(hist[n]), 'why': 'hung'})
                    continue
                late = slept_s(prev[0], prev[1], time.time(), time.monotonic())
                if late > 30:  # T-224: the Mac slept inside this pass (after the top-of-loop check): not a hang
                    fails.clear()
                    wake_until = time.time() + WAKE_GRACE_S
                    _wlog({'event': 'slept', 'seconds': round(late), 'grace_s': WAKE_GRACE_S, 'where': 'before hung'})
                    continue
                _wlog({'event': 'hung', 'name': n, 'pid': pid, 'cpu': cpu,
                       'no_reply_s': round(time.time() - fails[n][1]), 'dismissed': dismiss_td_alerts()})
                kill(pid)
                fails.pop(n, None)
                dead = True
            if not dead:
                continue
            if time.time() - last_act[0] < ACT_GAP:
                continue
            if not watch_due(st, False, hist[n], time.time()):
                if n not in gave_up:
                    gave_up.add(n)
                    _wlog({'event': 'gave_up', 'name': n, 'pid': pid, 'relaunches': len(hist[n])})
                continue
            clicked = dismiss_td_alerts()
            _wlog({'event': 'died', 'name': n, 'pid': pid, 'dismissed': clicked})
            hist[n].append(time.time())
            last_act[0] = time.time()
            try:
                r = cmd_start(int(st.get('port') or INSTANCES[n][0]), name=n)
                _wlog({'event': 'relaunched', 'name': n, 'pid': r.get('pid'), 'note': r.get('note'),
                       'connected': r.get('connected'), 'project': os.path.basename(str(r.get('project')))})
                gave_up.discard(n)
            except (SystemExit, Exception) as e:  # noqa: BLE001
                _wlog({'event': 'relaunch_failed', 'name': n, 'error': str(e)[:200]})
        time.sleep(every)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['start', 'stop', 'status', 'run', 'build', 'watch'])
    ap.add_argument('code', nargs='?', help='python for run')
    ap.add_argument('--name', choices=sorted(INSTANCES), default='scratch', help='side TD (default scratch)')
    ap.add_argument('--port', type=int, default=None, help='default per name: scratch 9336, b2 9337, b3 9338, b4 9339, b5 9340')
    ap.add_argument('--frames', type=int, default=0)
    ap.add_argument('--timeout', type=float, default=60.0)
    a = ap.parse_args()
    port = a.port or INSTANCES[a.name][0]
    if port == MAIN_PORT:
        ap.error('--port {} is the main bridge'.format(MAIN_PORT))
    if a.cmd == 'watch':
        return cmd_watch()
    if a.cmd == 'start':
        r = cmd_start(port, name=a.name)
    elif a.cmd == 'stop':
        r = cmd_stop(port, a.name)
    elif a.cmd == 'status':
        r = cmd_status(port, a.name)
    elif a.cmd == 'build':
        r = {'built': build_toe(port, inst(a.name)['toe'], a.name)}
    else:
        if not a.code:
            ap.error('run needs code')
        r = cmd_run(port, a.code, a.frames, a.timeout, a.name)
    print(json.dumps(r, indent=1, default=str))
    if isinstance(r, dict) and r.get('ok') is False:
        sys.exit(2)


if __name__ == '__main__':
    main()
