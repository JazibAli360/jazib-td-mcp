"""dmx_sniff - stdlib UDP sniffer for Art-Net (ArtDmx) and sACN (E1.31) on one port (BK_dmx_out tests L3/L4).
Run with an isolated interpreter (no third-party imports):
  python3 -I tools/dmx_sniff.py --port 16454 --seconds 10 [--bind 127.0.0.1] [--json out.json]
Prints a JSON summary: packets, packets/s per universe, header fields seen (seq values, length, priority, source
name, CID), first-packet data head. Read-only: binds one UDP socket, sends nothing. Stop: Ctrl+C or --seconds.
Parsing is the same as builders/dmx_logic.py (parse_artdmx / parse_sacn), imported by path."""
import argparse
import json
import os
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import dmx_logic as L  # noqa: E402


def sniff(port, seconds, bind='127.0.0.1'):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, 'SO_REUSEPORT'):
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    s.bind((bind, port))
    s.settimeout(0.2)
    per = {}
    other = 0
    t0 = time.time()
    first_t = last_t = None
    while time.time() - t0 < seconds:
        try:
            pkt, src = s.recvfrom(2048)
        except socket.timeout:
            continue
        now = time.time()
        p = L.parse_artdmx(pkt)
        proto = 'artnet'
        if p is None:
            p = L.parse_sacn(pkt)
            proto = 'sacn'
        if p is None or 'univ' not in p:
            other += 1
            continue
        first_t = first_t or now
        last_t = now
        u = per.setdefault((proto, p['univ']), {'n': 0, 'seq': set(), 'len': set(), 'src': src[0], 'size': set(),
                                                'prio': set(), 'name': set(), 'cid': set(), 'head': list(p['data'][:16])})
        u['n'] += 1
        u['seq'].add(p['seq'])
        u['len'].add(p['length'])
        u['size'].add(len(pkt))
        if proto == 'sacn':
            u['prio'].add(p['priority'])
            u['name'].add(p['name'])
            u['cid'].add(p['cid'].hex())
    s.close()
    span = (last_t - first_t) if (first_t and last_t and last_t > first_t) else 0.0
    out = {'port': port, 'seconds': seconds, 'other_packets': other, 'universes': []}
    for (proto, univ), u in sorted(per.items()):
        seqs = sorted(u['seq'])
        out['universes'].append({
            'protocol': proto, 'univ': univ, 'packets': u['n'], 'per_s': round(u['n'] / span, 2) if span else None,
            'seq_values': seqs if len(seqs) <= 8 else [seqs[0], '...', seqs[-1], '({} distinct)'.format(len(seqs))],
            'length': sorted(u['len']), 'packet_size': sorted(u['size']), 'src': u['src'],
            'priority': sorted(u['prio']), 'source_name': sorted(u['name']), 'cid': sorted(u['cid']),
            'data_head': u['head']})
    out['total_packets'] = sum(u['n'] for u in per.values())
    out['total_per_s'] = round(out['total_packets'] / span, 2) if span else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=16454)
    ap.add_argument('--seconds', type=float, default=10.0)
    ap.add_argument('--bind', default='127.0.0.1')
    ap.add_argument('--json', default='')
    a = ap.parse_args()
    out = sniff(a.port, a.seconds, a.bind)
    txt = json.dumps(out, indent=1)
    if a.json:
        with open(a.json, 'w') as f:
            f.write(txt)
    print(txt)


if __name__ == '__main__':
    main()
