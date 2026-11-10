#!/usr/bin/env python3
"""Jazib TD watchdog: keeps the show's TouchDesigner running (stdlib only; macOS).

TD can't rescue itself: a crash leaves it frozen on a modal "Fatal Error" dialog (LEARNINGS T-31), and a hang
just stops cooking. So TD writes a heartbeat (/watchdog_hb, td/watchdog_hb_install.py) about once a second and this
process watches it:
  - no TD process                         -> launch the show .toe
  - TD running, heartbeat stale > --stale -> kill ONLY if also no MCP sign of life (exec.log reply or
    heartbeat_mcp.json, written from TD's WebSocket callbacks) within --stale AND hang evidence (crash dialog
    window / process state U) or everything silent past --hard-stale (T-78/T-95); else warn. Kill = TERM, KILL,
    relaunch; after the relaunched TD's first heartbeat, tools/td_recover.py runs once (reload, park, autosave, save)
  - TD just launched                      -> wait --boot-grace seconds for the first heartbeat
  - TD that never sent a heartbeat         -> warn only (no /watchdog_hb in its project); never killed
  - crash loop (> --max-restarts within --window s) -> keep relaunching but wait --loop-backoff s first, and notify
Paused (file `watchdog.pause` in the state dir, or `pause` command) = watch and log only, never kill or launch,
so an intentional quit isn't undone.
Scratch TD (T-83, tools/scratch_td.py): the disposable second TD launched from projects/scratch/ is never managed,
counted or killed: its pid comes from scratch_td.json in the state dir (plus any TD that appears while that file
says "launching"), and a heartbeat whose project is not the --toe project (or lives under projects/scratch/) is
ignored. The build TDs b2 / b3 (T-120, projects/build2|build3/, scratch_td_b2|b3.json) are side TDs the same way. Launches use `open -n`, so a running scratch TD is never handed the show file.

Usage (from jazib-td-mcp/):
  python3 tools/td_watchdog.py run --toe projects/JazibTD_home.toe          # foreground
  python3 tools/td_watchdog.py start --toe <show.toe>                        # background (pid file)
  python3 tools/td_watchdog.py status | stop | pause | resume
Logs: logs/watchdog.log (JSON lines). Reopens the show .toe, never a CrashAutoSave (that's for the user to inspect).
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.expanduser('~/Library/Application Support/JazibTDMCP')
HB_FILE = os.path.join(STATE_DIR, 'heartbeat.json')
MCP_HB_FILE = os.path.join(STATE_DIR, 'heartbeat_mcp.json')  # T-95: written by handlers.py from WebSocket callbacks
PAUSE_FILE = os.path.join(STATE_DIR, 'watchdog.pause')
PID_FILE = os.path.join(STATE_DIR, 'watchdog.pid')
LOG_FILE = os.path.join(HERE, 'logs', 'watchdog.log')
SCRATCH_FILE = os.path.join(STATE_DIR, 'scratch_td.json')  # written by tools/scratch_td.py (T-83)
SIDE_RE = re.compile(r'/projects/(scratch|build\d+)/|Scratch\.toe|Build\d+(\.\d+)?\.toe')  # side TDs (T-83, T-120)
SCRATCH_LAUNCH_GRACE = 120.0  # s: a TD appearing while scratch_td.json says "launching" is the scratch one
DEFAULT_APP = '/Applications/TouchDesigner 2.app'


# ------------------------------------------------------------------ pure decision (unit-tested)

def decide(now, td_pids, hb, st, cfg, paused=False, mcp_alive_at=None, hung=None):
    """One tick. td_pids: running TD pids; hb: frame heartbeat dict or None; st: mutable state
    {'launched_at', 'restarts': [times]}; cfg: stale, boot_grace, max_restarts, window, loop_backoff, hard_stale.
    mcp_alive_at: newest epoch TD showed life outside frame callbacks (exec.log reply / heartbeat_mcp.json).
    hung: hang evidence from hang_evidence() ({'dialog': ...} / {'state': 'U'}); None or {} = none.
    Returns (action, reason) with action in: ok, wait, warn, launch, kill, kill_extra, paused.
    A kill needs ALL of (T-78/T-95): a TD that has beaten before (st['beat_pids']), frame heartbeat stale, no MCP sign
    of life within stale, and hang evidence -- or, without evidence, both signals silent past hard_stale
    (default 3 x stale) so a hang that shows no dialog is still caught."""
    if paused:
        return 'paused', 'paused: watching only'
    if len(td_pids) > 1:
        # T-82: other TDs (the scratch TD, a user's own TD) are not ours: manage only the one our heartbeat names,
        # else the oldest (lowest pid); never kill the others
        mine = hb.get('pid') if hb else None
        td_pids = [mine] if mine in td_pids else [min(td_pids)]
    if not td_pids:
        recent = [t for t in st.get('restarts', []) if now - t < cfg['window']]
        if len(recent) >= cfg['max_restarts'] and now - recent[-1] < cfg['loop_backoff']:
            return 'wait', 'crash loop: {} restarts in {} s, backing off'.format(len(recent), cfg['window'])
        return 'launch', 'no TD process'
    pid = td_pids[0]
    fresh = hb is not None and hb.get('pid') == pid and now - float(hb.get('time', 0)) <= cfg['stale']
    if fresh:
        st.setdefault('beat_pids', set()).add(pid)
        st['last_beat_at'] = float(hb['time'])
        return 'ok', 'heartbeat {:.1f} s old'.format(now - float(hb['time']))
    if pid not in st.get('beat_pids', set()):
        # never heard from this TD: still loading, or its project has no /watchdog_hb. Killing it would loop
        # forever (16 Oct 19:24-19:25, LEARNINGS T-38), so only warn.
        launched = st.get('launched_at')
        if launched is None:
            st['launched_at'] = launched = now
        if now - launched < cfg['boot_grace']:
            return 'wait', 'booting ({:.0f}/{} s)'.format(now - launched, cfg['boot_grace'])
        return 'warn', 'pid {} has never sent a heartbeat: is /watchdog_hb in the project?'.format(pid)
    own = hb is not None and hb.get('pid') == pid
    age = '{:.0f} s'.format(now - float(hb.get('time', 0))) if own else '(none from this pid)'
    if mcp_alive_at is not None and now - mcp_alive_at <= cfg['stale']:
        # 26 Oct 16:02 false kill (T-78): the frame heartbeat went quiet (TD's frame clock froze, T-95) while TD kept
        # answering MCP calls. A TD that replied recently is alive; only warn.
        return 'warn', 'frame heartbeat stale {} but TD answered {:.0f} s ago: frames stopped? not killing'.format(
            age, now - mcp_alive_at)
    if hung:
        return 'kill', 'heartbeat stale {}, no MCP sign of life, hang evidence: {}'.format(
            age, ', '.join('{}={}'.format(k, str(v)[:80]) for k, v in sorted(hung.items())))
    hard = cfg.get('hard_stale') or 3 * cfg['stale']
    signs = [t for t in (float(hb.get('time', 0)) if own else st.get('last_beat_at'), mcp_alive_at) if t is not None]
    silent = now - max(signs) if signs else None
    if silent is None or silent > hard:
        return 'kill', 'no heartbeat and no MCP sign of life for {} (> hard_stale {:.0f} s, no dialog seen)'.format(
            '{:.0f} s'.format(silent) if silent is not None else 'ever', hard)
    return 'warn', 'heartbeat stale {}, no MCP sign of life, no hang evidence yet: waiting ({:.0f}/{:.0f} s)'.format(
        age, silent, hard)


def hang_evidence(windows, pid, ps_state):
    """Pure (T-95): evidence that TD `pid` is stuck. windows: CGWindowList rows {'pid', 'owner', 'name'}; ps_state:
    `ps -o state=` text. Returns {} or e.g. {'dialog': '<window title>'} / {'state': 'U'}.
    Crash dialog = TD's own window titled like its crash alert ('Fatal Error', 'CrashAutoSave', 'crashed', 'not
    responding') or a system alert (UserNotificationCenter, CoreServicesUIAgent, ReportCrash, Problem Reporter)
    naming TouchDesigner. Window titles need Screen Recording permission for the terminal running the watchdog;
    without it titles are empty and only the process state and hard_stale apply."""
    ev = {}
    td_words = ('fatal error', 'crashautosave', 'crashed', 'not responding', 'unexpectedly')
    sys_owners = ('usernotificationcenter', 'coreservicesuiagent', 'reportcrash', 'problem reporter')
    for w in windows or []:
        owner = str(w.get('owner') or '').lower()
        name = str(w.get('name') or '')
        low = name.lower()
        if w.get('pid') == pid and any(t in low for t in td_words):
            ev['dialog'] = name
            break
        if owner in sys_owners and 'touchdesigner' in low:
            ev['dialog'] = '{}: {}'.format(w.get('owner'), name)
            break
    s = (ps_state or '').strip()
    if s[:1] in ('U', 'Z', 'T'):  # uninterruptible wait, zombie, stopped
        ev['state'] = s
    return ev


def list_windows():
    """On-screen windows via CoreGraphics (ctypes, stdlib): [{'pid', 'owner', 'name'}]; [] when unavailable."""
    import ctypes
    import ctypes.util
    try:
        cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library('CoreGraphics') or
                                     '/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
        cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library('CoreFoundation') or
                                     '/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        vp, ci = ctypes.c_void_p, ctypes.c_long
        cg.CGWindowListCopyWindowInfo.restype = vp
        cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        cf.CFArrayGetCount.restype = ci
        cf.CFArrayGetCount.argtypes = [vp]
        cf.CFArrayGetValueAtIndex.restype = vp
        cf.CFArrayGetValueAtIndex.argtypes = [vp, ci]
        cf.CFDictionaryGetValue.restype = vp
        cf.CFDictionaryGetValue.argtypes = [vp, vp]
        cf.CFStringCreateWithCString.restype = vp
        cf.CFStringCreateWithCString.argtypes = [vp, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFStringGetCString.argtypes = [vp, ctypes.c_char_p, ci, ctypes.c_uint32]
        cf.CFNumberGetValue.restype = ctypes.c_bool
        cf.CFNumberGetValue.argtypes = [vp, ctypes.c_int, vp]
        cf.CFRelease.argtypes = [vp]
        utf8 = 0x08000100
        keys = {k: cf.CFStringCreateWithCString(None, k.encode(), utf8)
                for k in ('kCGWindowOwnerPID', 'kCGWindowOwnerName', 'kCGWindowName')}

        def text(ref):
            buf = ctypes.create_string_buffer(1024)
            return buf.value.decode('utf-8', 'replace') if ref and cf.CFStringGetCString(ref, buf, 1024, utf8) else ''

        arr = cg.CGWindowListCopyWindowInfo(1 | 16, 0)  # on-screen only | exclude desktop elements
        out = []
        if arr:
            for i in range(cf.CFArrayGetCount(arr)):
                d = cf.CFArrayGetValueAtIndex(arr, i)
                n = ctypes.c_int64(0)
                pref = cf.CFDictionaryGetValue(d, keys['kCGWindowOwnerPID'])
                if pref:
                    cf.CFNumberGetValue(pref, 4, ctypes.byref(n))  # kCFNumberSInt64Type
                out.append({'pid': int(n.value), 'owner': text(cf.CFDictionaryGetValue(d, keys['kCGWindowOwnerName'])),
                            'name': text(cf.CFDictionaryGetValue(d, keys['kCGWindowName']))})
            cf.CFRelease(arr)
        for k in keys.values():
            cf.CFRelease(k)
        return out
    except Exception:
        return []


def ps_state(pid):
    try:
        return subprocess.run(['ps', '-o', 'state=', '-p', str(pid)], capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except Exception:
        return ''


def read_mcp_hb(path=None):
    try:
        with open(path or MCP_HB_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def mcp_alive(pid, exec_reply_at, mcp_hb):
    """Pure: newest epoch TD `pid` showed life outside frame callbacks (exec.log reply, heartbeat_mcp.json)."""
    ts = [exec_reply_at] if exec_reply_at is not None else []
    if mcp_hb and mcp_hb.get('pid') == pid and mcp_hb.get('time') is not None:
        ts.append(float(mcp_hb['time']))
    return max(ts) if ts else None


def frames_frozen_s(now, mcp_hb):
    """Pure: seconds absTime.frame has not changed according to heartbeat_mcp.json (None = unknown)."""
    if not mcp_hb or mcp_hb.get('frame_changed_at') is None:
        return None
    return round(now - float(mcp_hb['frame_changed_at']), 1)


def recover_due(st, action, pid):
    """Pure: start tools/td_recover.py once per TD the watchdog launched, on that TD's first fresh heartbeat."""
    if action != 'ok' or not st.get('recover_pending') or pid is None:
        return False
    done = st.setdefault('recovered_pids', set())
    if pid in done:
        return False
    done.add(pid)
    st['recover_pending'] = False
    return True


def no_reply(r):
    """True for an exec.log 'end' row that TD never answered: cut off by a crash ('TouchDesigner disconnected') or
    timed out on the MCP side ('TouchDesigner timeout after N ms'). T-82: hung TD + agents still polling wrote a
    timeout 'end' row every few s, which counted as 'TD answered', so the watchdog warned forever and never killed."""
    e = str(r.get('error') or '')
    return 'disconnected' in e or 'TouchDesigner timeout' in e or bool(r.get('timeout'))


def project_base(path):
    """Pure: 'X' for .../X.toe, X.12.toe or CrashAutoSave.X.3.toe."""
    import re
    b = os.path.basename(str(path or ''))
    if b.startswith('CrashAutoSave.'):
        b = b[len('CrashAutoSave.'):]
    return re.sub(r'(\.\d+)?\.toe$', '', b)


def hb_is_main(hb, toe):
    """Pure (T-83): is this heartbeat from the watched project? An old heartbeat without 'project' counts as main;
    one from projects/scratch/ or another project does not."""
    if not hb:
        return False
    proj = hb.get('project')
    if not proj:
        return True
    if SIDE_RE.search(str(proj).replace('\\', '/')):
        return False
    return project_base(proj) == project_base(toe)


def scratch_pids(pids, info, now, main_pid=None):
    """Pure (T-83): the running pids that belong to the scratch TD (never managed or killed). info = scratch_td.json:
    {'state': 'launching'|'running', 'pid', 'time', 'before': [pids running before the launch]}. The main heartbeat's
    pid is never scratch. info may be a list of such dicts (every side TD: scratch, b2, b3; T-120)."""
    if isinstance(info, (list, tuple)):
        out = set()
        for i in info:
            out |= scratch_pids(pids, i, now, main_pid)
        return out
    if not info:
        return set()
    out = set()
    p = info.get('pid')
    if p in pids and p != main_pid:
        out.add(p)
    if info.get('state') == 'launching' and now - float(info.get('time', 0)) < SCRATCH_LAUNCH_GRACE:
        before = set(info.get('before') or [])
        out |= {q for q in pids if q not in before and q != main_pid}
    return out


def read_scratch():
    """Every side TD's state (scratch_td.json + scratch_td_<name>.json, T-120) as a list (empty = none)."""
    out = []
    try:
        names = sorted(n for n in os.listdir(STATE_DIR) if n.startswith('scratch_td') and n.endswith('.json'))
    except OSError:
        names = []
    for n in names:
        try:
            with open(os.path.join(STATE_DIR, n)) as f:
                out.append(json.load(f))
        except (OSError, ValueError):
            pass
    return out


def last_mcp_reply(path):
    """Epoch of the newest exec.log 'end' row (a reply TD actually sent), or None."""
    import calendar
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 65536))
            tail = f.read().decode('utf-8', 'replace').splitlines()
    except OSError:
        return None
    for ln in reversed(tail):
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get('phase') == 'end' and r.get('ok') is not None and not no_reply(r):
            t = r.get('time', '')[:19]
            try:
                return calendar.timegm(time.strptime(t, '%Y-%m-%dT%H:%M:%S'))
            except ValueError:
                return None
    return None


# ------------------------------------------------------------------ side effects

def log(event, **kw):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    kw.update(time=time.strftime('%Y-%m-%dT%H:%M:%S'), event=event)
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(kw) + '\n')
    print('[watchdog]', kw['time'], event, {k: v for k, v in kw.items() if k not in ('time', 'event')}, flush=True)


def notify(msg):
    subprocess.run(['osascript', '-e', 'display notification "{}" with title "TD watchdog"'.format(
        msg.replace('"', "'"))], capture_output=True)


def td_pids(app):
    exe = os.path.join(app, 'Contents', 'MacOS', 'TouchDesigner')
    out = subprocess.run(['pgrep', '-f', exe], capture_output=True, text=True).stdout.split()
    pids = []
    for p in out:
        if not p.strip().isdigit():
            continue
        args = subprocess.run(['ps', '-o', 'command=', '-p', p], capture_output=True, text=True).stdout
        if is_scratch_td(args):
            continue  # T-82: the scratch TD (projects/scratch/) is not ours to manage or kill
        pids.append(int(p))
    return sorted(pids)


def is_scratch_td(cmdline):
    """Pure: a TD started on a project under projects/scratch/ or projects/buildN/ (Scratch.toe, BuildN[.k].toe) is a
    side TD (scratch T-83, build b2/b3 T-120), never the main one."""
    return bool(SIDE_RE.search(cmdline))


def read_hb():
    try:
        with open(HB_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def kill(pid, wait_s=6.0):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return True
        t0 = time.time()
        while time.time() - t0 < wait_s:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.3)
    return False


def newest_save(toe, listing, mtimes):
    """Pure: the newest numbered save X.N.toe (or X.toe) beside `toe` by mtime, never a CrashAutoSave."""
    import re
    base = re.sub(r'(\.\d+)?\.toe$', '', os.path.basename(toe))
    cands = [n for n in listing if not n.startswith('CrashAutoSave') and re.match(re.escape(base) + r'(\.\d+)?\.toe$', n)]
    return max(cands, key=lambda n: mtimes.get(n, 0)) if cands else os.path.basename(toe)


def suspects_from_exec_log(lines, since_iso):
    """Pure (T-77): /project1/... COMPs named by td_exec calls that STARTED after since_iso and never ENDED - the
    work in flight when TD died. lines: exec.log JSON lines."""
    import re
    started, ended = {}, set()
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get('time', '') < since_iso:
            continue
        key = (r.get('code') or '')[:400]
        if r.get('phase') == 'start':
            started[key] = r
        elif r.get('phase') == 'end' and not no_reply(r):
            ended.add(key)  # a reply cut off by the crash or timed out is NOT an end (T-79, T-82)
    out = set()
    for key in started:
        if key not in ended:
            for m in re.findall(r"/project1/(?:lab/)?[A-Za-z_][A-Za-z0-9_]*", key):
                out.add(m)
            for m in re.findall(r"build'\]\('(/project1/[A-Za-z0-9_/]+)'", key):
                out.add(m)
    return sorted(out)


def expanded_has(expand_dir, op_path):
    """Pure-ish: does a toeexpand output dir contain op_path (e.g. /project1/lab/BJ_urdu_type)?"""
    rel = op_path.strip('/')
    for root, dirs, files in os.walk(expand_dir):
        for n in dirs + files:
            p = os.path.relpath(os.path.join(root, n), expand_dir)
            p = p.split('.toe.dir' + os.sep, 1)[-1]
            stem = p.rsplit('.', 1)[0] if '.' in os.path.basename(p) else p
            if stem == rel or stem.startswith(rel + os.sep) or stem.startswith(rel + '.'):
                return True
    return False


def crash_save_sane(crash_bytes, newest_bytes):
    """Pure (T-81): a crash autosave written by a hung/killed TD can be empty (0 bytes) or a near-empty project."""
    return crash_bytes > 0 and crash_bytes >= 0.5 * max(1, newest_bytes)


def pick_crash_save(d, base, newest, since_iso, log_path, app):
    """T-77: a CrashAutoSave newer than the newest save is opened unless it contains the COMP that was in flight when
    TD died (scanned offline with toeexpand). Returns the path to open or None."""
    import shutil
    import tempfile
    cands = [n for n in os.listdir(d) if n.startswith('CrashAutoSave.' + base) and n.endswith('.toe')]
    if not cands:
        return None
    crash = max(cands, key=lambda n: os.path.getmtime(os.path.join(d, n)))
    if os.path.getmtime(os.path.join(d, crash)) <= os.path.getmtime(os.path.join(d, newest)):
        return None
    if not crash_save_sane(os.path.getsize(os.path.join(d, crash)), os.path.getsize(os.path.join(d, newest))):
        log('crash_scan', crash=crash, rejected='too small vs newest save (T-81)')
        return None
    try:
        lines = open(log_path).read().splitlines()[-400:]
    except OSError:
        lines = []
    sus = suspects_from_exec_log(lines, since_iso)
    tmp = tempfile.mkdtemp(prefix='wd_expand_')
    try:
        src = os.path.join(tmp, crash)
        shutil.copy2(os.path.join(d, crash), src)
        subprocess.run([os.path.join(app, 'Contents', 'MacOS', 'toeexpand'), src], cwd=tmp, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        bad = [s_ for s_ in sus if expanded_has(tmp, s_)]
        if not expanded_has(tmp, '/jazib_mcp'):  # T-81: a crash autosave without the MCP COMP is broken/empty
            log('crash_scan', crash=crash, rejected='no /jazib_mcp inside (T-81)')
            return None
    except Exception as e:
        log('crash_scan_error', error=str(e)[:200])
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log('crash_scan', crash=crash, suspects=sus, found=bad)
    if bad:
        return None
    import re
    nums = [int(m.group(1)) for n in os.listdir(d) for m in [re.match(re.escape(base) + r'\.(\d+)\.toe$', n)] if m]
    dst = os.path.join(d, '{}.{}.toe'.format(base, (max(nums) if nums else 0) + 1))
    shutil.copy2(os.path.join(d, crash), dst)  # a normal name, so saves continue from it
    return dst


DISMISS_JXA = None  # (kept simple: AppleScript below)


def dismiss_td_alerts():
    """T-79 (user: "can u click on the ok error by urself too?"): click OK on TouchDesigner alerts (crash 'Fatal
    Error', 'Plugin Load Error', ...) shown by UserNotificationCenter or TD itself, so no dialog blocks a relaunch.
    Returns the number clicked. Needs Accessibility for osascript (granted)."""
    script = (
        'set n to 0\n'
        'tell application "System Events"\n'
        '  repeat with pn in {"UserNotificationCenter", "TouchDesigner"}\n'
        '    if exists process pn then\n'
        '      tell process pn\n'
        '        repeat with w in windows\n'
        '          try\n'
        '            set txt to (value of static texts of w) as text\n'
        '            if (txt contains "TouchDesigner") and (exists button "OK" of w) then\n'
        '              click button "OK" of w\n'
        '              set n to n + 1\n'
        '            end if\n'
        '          end try\n'
        '        end repeat\n'
        '      end tell\n'
        '    end if\n'
        '  end repeat\n'
        'end tell\n'
        'return n')
    try:
        r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=10)
        return int((r.stdout or '0').strip() or 0)
    except Exception:
        return 0


def launch(app, toe, latest=False, since_iso=''):
    if latest:  # dev mode: reopen the newest save (autosaves every 5 min, T-71/T-77), not a fixed show file
        import re
        d = os.path.dirname(toe)
        ls = os.listdir(d)
        newest = newest_save(toe, ls, {n: os.path.getmtime(os.path.join(d, n)) for n in ls})
        base = re.sub(r'(\.\d+)?\.toe$', '', os.path.basename(toe))
        crash = pick_crash_save(d, base, newest, since_iso, os.path.join(HERE, 'logs', 'exec.log'), app)
        toe = crash or os.path.join(d, newest)
    subprocess.run(['open', '-n', '-a', app, toe], check=False)  # -n: never hand the show to a scratch TD (T-83)
    return toe


WAKE_GRACE_S = 180.0  # T-219: after the Mac sleeps, frozen-but-healthy TDs get this long to beat again


def slept_s(prev_wall, prev_mono, wall, mono):
    """Pure (T-219): seconds the machine slept between two ticks. On macOS time.monotonic() stops during sleep while
    wall time runs on, so the difference of the two deltas is the sleep (0 on the first tick)."""
    if prev_wall is None or prev_mono is None:
        return 0.0
    return max(0.0, (wall - prev_wall) - (mono - prev_mono))


def run(args):
    toe = os.path.abspath(args.toe)
    if not os.path.isfile(toe):
        sys.exit('no such .toe: ' + toe)
    if os.path.basename(toe).startswith('CrashAutoSave'):
        sys.exit('refusing to run a CrashAutoSave as the show file: ' + toe)
    cfg = {'stale': args.stale, 'boot_grace': args.boot_grace, 'max_restarts': args.max_restarts,
           'window': args.window, 'loop_backoff': args.loop_backoff,
           'hard_stale': getattr(args, 'hard_stale', None) or 3 * args.stale}
    st = {'launched_at': None, 'restarts': []}
    hb0 = read_hb()  # T-80: a watchdog restart must remember the TD that was already beating, or it never kills it
    if hb0 and hb0.get('pid') in td_pids(args.app):
        st['beat_pids'] = {hb0.get('pid')}
    log('start', toe=toe, app=args.app, pid=os.getpid(), recover=not getattr(args, 'no_recover', False), **cfg)
    last = None
    prev_wall = prev_mono = None
    wake_until = 0.0
    while True:
        now = time.time()
        mono = time.monotonic()
        slept = slept_s(prev_wall, prev_mono, now, mono)
        prev_wall, prev_mono = now, mono
        if slept > 30:
            wake_until = now + WAKE_GRACE_S
            log('slept', seconds=round(slept), grace_s=WAKE_GRACE_S)
        all_pids = td_pids(args.app)
        hb = read_hb()
        if hb is not None and not hb_is_main(hb, toe):
            hb = None  # another project's (scratch) heartbeat: not ours (T-83)
        sc = scratch_pids(all_pids, read_scratch(), now, hb.get('pid') if hb else None)
        pids = [p for p in all_pids if p not in sc]
        if not os.path.exists(PAUSE_FILE):
            clicked = dismiss_td_alerts()
            if clicked:
                log('dismissed', count=clicked)
        mhb = read_mcp_hb()
        if len(pids) > 1:  # the same TD decide() manages (T-82): the heartbeat's pid, else the oldest
            pid = hb.get('pid') if hb and hb.get('pid') in pids else min(pids)
        else:
            pid = pids[0] if pids else None
        alive = mcp_alive(pid, last_mcp_reply(os.path.join(HERE, 'logs', 'exec.log')), mhb)
        hb_stale = pid is not None and not (hb and hb.get('pid') == pid and now - float(hb.get('time', 0)) <= cfg['stale'])
        # hang evidence costs a ps + a window list: only looked up when the frame heartbeat is already stale
        hung = hang_evidence(list_windows(), pid, ps_state(pid)) if hb_stale and pid in st.get('beat_pids', set()) else None
        action, why = decide(now, pids, hb, st, cfg, paused=os.path.exists(PAUSE_FILE), mcp_alive_at=alive, hung=hung)
        late = slept_s(now, mono, time.time(), time.monotonic())
        if late > 30:  # T-224: the Mac slept inside this pass, after the top-of-loop check
            wake_until = time.time() + WAKE_GRACE_S
            log('slept', seconds=round(late), grace_s=WAKE_GRACE_S, where='mid-pass')
            now = time.time()
        if action == 'kill' and now < wake_until:  # T-219: stale only because the Mac slept, not hung
            action, why = 'wait', 'woke from sleep {:.0f} s ago: kill deferred ({})'.format(
                now - (wake_until - WAKE_GRACE_S), why)
        if action == 'warn' and last != 'warn':
            notify(why)
        if action != last or action in ('kill', 'kill_extra', 'launch'):
            log(action, reason=why, pids=pids, hb_age=None if hb is None else round(now - hb.get('time', 0), 1),
                mcp_age=None if alive is None else round(now - alive, 1), frames_frozen_s=frames_frozen_s(now, mhb),
                hung=hung or None, **({'scratch_pids': sorted(sc)} if sc else {}))
        last = action
        if recover_due(st, action, pid) and not getattr(args, 'no_recover', False):
            # zero-hands recovery after OUR relaunch: one background td_recover.py per new TD pid (it is idempotent too)
            rec = [sys.executable, os.path.join(HERE, 'tools', 'td_recover.py'), '--pid', str(pid)]
            try:
                p = subprocess.Popen(rec, cwd=HERE, stdout=open(LOG_FILE + '.out', 'a'), stderr=subprocess.STDOUT,
                                     start_new_session=True)
                log('recover_started', td_pid=pid, recover_pid=p.pid)
            except OSError as e:
                log('recover_error', td_pid=pid, error=str(e)[:200])
        if action == 'kill_extra':
            keep = hb.get('pid') if hb and hb.get('pid') in pids else pids[0]
            for p in pids:
                if p != keep:
                    log('killed_extra', pid=p, ok=kill(p))
        elif action == 'kill':
            for p in pids:
                log('killed', pid=p, ok=kill(p), reason=why)
            notify('TouchDesigner was stuck ({}); restarting the show file.'.format(why))
            # no launch here: the next tick sees no TD and decides, so crash-loop backoff applies to kills too
        if action == 'launch':
            st['restarts'] = [t for t in st['restarts'] if now - t < cfg['window']] + [now]
            if len(st['restarts']) > cfg['max_restarts']:
                notify('TouchDesigner crash loop: {} restarts in {} s'.format(len(st['restarts']), cfg['window']))
            since = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time() - 180))
            opened = launch(args.app, toe, getattr(args, 'latest', False), since)
            log('launch', toe=opened, restarts_in_window=len(st['restarts']))
            notify('TD relaunched: ' + os.path.basename(opened))
            st['launched_at'] = time.time()
            st['recover_pending'] = True  # run tools/td_recover.py on the new TD's first heartbeat
        if args.once:
            return action
        time.sleep(args.interval)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['run', 'start', 'stop', 'status', 'pause', 'resume'])
    ap.add_argument('--toe', help='the show .toe to keep running (required for run/start)')
    ap.add_argument('--latest', action='store_true', help='dev mode: relaunch the newest numbered save beside --toe')
    ap.add_argument('--app', default=DEFAULT_APP)
    ap.add_argument('--stale', type=float, default=8.0, help='heartbeat older than this = hung (s)')
    ap.add_argument('--hard-stale', type=float, default=None,
                    help='kill without hang evidence only after both heartbeats + MCP silent this long (default 3 x stale)')
    ap.add_argument('--no-recover', action='store_true', help='do not run tools/td_recover.py after a relaunch')
    ap.add_argument('--boot-grace', type=float, default=90.0, help='wait this long after a launch (s)')
    ap.add_argument('--max-restarts', type=int, default=3)
    ap.add_argument('--window', type=float, default=300.0)
    ap.add_argument('--loop-backoff', type=float, default=30.0)
    ap.add_argument('--interval', type=float, default=1.0)
    ap.add_argument('--once', action='store_true', help='one tick then exit (tests)')
    a = ap.parse_args()
    os.makedirs(STATE_DIR, exist_ok=True)
    if a.cmd in ('run', 'start') and not a.toe:
        ap.error('--toe is required')
    if a.cmd == 'run':
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        try:
            run(a)
        finally:
            try:
                os.remove(PID_FILE)
            except OSError:
                pass
    elif a.cmd == 'start':
        argv = [sys.executable, os.path.abspath(__file__), 'run'] + sys.argv[2:]
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        p = subprocess.Popen(argv, stdout=open(LOG_FILE + '.out', 'a'), stderr=subprocess.STDOUT,
                             start_new_session=True)
        print('watchdog started, pid', p.pid)
    elif a.cmd == 'stop':
        try:
            pid = int(open(PID_FILE).read())
            os.kill(pid, signal.SIGTERM)
            print('stopped', pid)
        except (OSError, ValueError):
            print('not running')
    elif a.cmd == 'status':
        pid = None
        try:
            pid = int(open(PID_FILE).read())
            os.kill(pid, 0)
        except (OSError, ValueError):
            pid = None
        hb = read_hb()
        print(json.dumps({'watchdog_pid': pid, 'paused': os.path.exists(PAUSE_FILE), 'td_pids': td_pids(a.app),
                          'scratch': read_scratch(),
                          'heartbeat': hb, 'heartbeat_age_s': None if hb is None else round(time.time() - hb['time'], 1),
                          'heartbeat_mcp': read_mcp_hb(), 'frames_frozen_s': frames_frozen_s(time.time(), read_mcp_hb())},
                         indent=1))
    elif a.cmd == 'pause':
        open(PAUSE_FILE, 'w').write(time.strftime('%Y-%m-%dT%H:%M:%S'))
        print('paused (watch only)')
    elif a.cmd == 'resume':
        try:
            os.remove(PAUSE_FILE)
        except OSError:
            pass
        print('resumed')


if __name__ == '__main__':
    main()
