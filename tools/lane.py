#!/usr/bin/env python3
"""Builder lanes register the COMP they work on, so automatic recovery (tools/td_recover.py) never parks it (T-95).

  python3 tools/lane.py add <comp> <label>     at job start   (comp = name like BK_dmx_out, or its /project1/lab path)
  python3 tools/lane.py remove <comp>          at job end (after saving and parking your COMP)
  python3 tools/lane.py list
File: logs/active_lanes.json = {comp: {"agent": label, "time": local ISO}}. Locked (fcntl), written atomically.
"""
import fcntl
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANES_FILE = os.path.join(HERE, 'logs', 'active_lanes.json')


def apply(lanes, cmd, comp=None, label=None, now_iso=None):
    """Pure: the lanes dict after add/remove."""
    out = dict(lanes or {})
    if cmd == 'add':
        out[comp] = {'agent': label or '?', 'time': now_iso or time.strftime('%Y-%m-%dT%H:%M:%S')}
    elif cmd == 'remove':
        out.pop(comp, None)
        name = comp.rstrip('/').rsplit('/', 1)[-1]
        for k in [k for k in out if k.rstrip('/').rsplit('/', 1)[-1] == name]:
            out.pop(k)
    return out


def update(cmd, comp=None, label=None, path=LANES_FILE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + '.lock', 'w') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            with open(path) as f:
                lanes = json.load(f)
        except (OSError, ValueError):
            lanes = {}
        if cmd == 'list':
            return lanes
        lanes = apply(lanes, cmd, comp, label)
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(lanes, f, indent=1)
        os.replace(tmp, path)
        return lanes


def main(argv):
    if not argv or argv[0] not in ('add', 'remove', 'list') or (argv[0] == 'add' and len(argv) < 3) or \
            (argv[0] == 'remove' and len(argv) < 2):
        print(__doc__)
        return 2
    print(json.dumps(update(argv[0], *argv[1:3]), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
