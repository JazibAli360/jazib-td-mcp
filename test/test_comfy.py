"""Offline tests for td/comfy_client.py and the comfy_* commands in td/handlers.py (stdlib only; no TD, no ComfyUI).

A fake ComfyUI (http.server on an ephemeral loopback port) serves /system_stats, /queue, /object_info/<c>,
/upload/image (multipart, parsed with the email package), /prompt (incl. a 400 with node_errors), /history/<id>
(empty twice, then outputs), /view, /interrupt, /queue, /free.
"""
import email.parser
import email.policy
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_handlers as TH  # noqa: E402  (installs the stub td module and imports handlers)

handlers = TH.handlers
import comfy_client as C  # noqa: E402  (td/ is on sys.path via test_handlers)

PNG = b'\x89PNG\r\n\x1a\n' + b'fakepng' * 10
C.POLL_S = 0.02

API_GRAPH = {
    '3': {'class_type': 'KSampler', 'inputs': {'seed': 5, 'model': ['4', 0], 'positive': ['6', 0]}},
    '4': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'x.safetensors'}},
    '6': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'a', 'clip': ['4', 1]}},
    '10': {'class_type': 'LoadImage', 'inputs': {'image': 'example.png'}},
    '9': {'class_type': 'SaveImage', 'inputs': {'images': ['3', 0], 'filename_prefix': 'td'}},
}


class Fake(BaseHTTPRequestHandler):
    state = None

    def log_message(self, *a):
        pass

    def _send(self, code, obj=None, raw=None, ctype='application/json'):
        body = raw if raw is not None else json.dumps(obj if obj is not None else {}).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return self.rfile.read(n) if n else b''

    def do_GET(self):
        s = self.state
        p = self.path
        s['calls'].append('GET ' + p.split('?')[0])
        if p == '/system_stats':
            return self._send(200, {'system': {'comfyui_version': '0.34.5', 'python_version': '3.13.12'},
                                    'devices': [{'type': 'mps', 'vram_total': 64 * 1073741824, 'vram_free': 1073741824}]})
        if p == '/queue':
            return self._send(200, {'queue_running': [], 'queue_pending': [['x']]})
        if p.startswith('/object_info/'):
            c = p.split('/')[-1]
            return self._send(200, {c: {'api_node': c == 'NewPaidNode'}})
        if p.startswith('/history/'):
            pid = p.split('/')[-1]
            s['polls'] = s.get('polls', 0) + 1
            if s['polls'] <= 2 or pid not in s['prompts']:
                return self._send(200, {})
            if s.get('fail'):
                return self._send(200, {pid: {'outputs': {}, 'status': {'status_str': 'error', 'completed': False,
                                        'messages': [['execution_error', {'node_id': '3', 'node_type': 'KSampler',
                                                                          'exception_message': 'boom'}]]}}})
            return self._send(200, {pid: {'outputs': {'9': {'images': [{'filename': 'td_00001_.png', 'subfolder': '',
                                                                        'type': 'output'}]}},
                                          'status': {'status_str': 'success', 'completed': True}}})
        if p.startswith('/view?'):
            s['view_q'] = p
            return self._send(200, raw=PNG, ctype='image/png')
        return self._send(404, {'error': 'no route'})

    def do_POST(self):
        s = self.state
        p = self.path
        body = self._body()
        s['calls'].append('POST ' + p)
        if p == '/upload/image':
            msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
                b'Content-Type: ' + self.headers['Content-Type'].encode() + b'\r\n\r\n' + body)
            parts = {pt.get_param('name', header='content-disposition'): pt for pt in msg.iter_parts()}
            img = parts['image']
            s['upload'] = {'bytes': img.get_payload(decode=True), 'filename': img.get_filename(),
                           'fields': {k: v.get_content().strip() for k, v in parts.items() if k != 'image'}}
            return self._send(200, {'name': img.get_filename(), 'subfolder': 'jazib_td', 'type': 'input'})
        if p == '/prompt':
            d = json.loads(body)
            if any(n['class_type'] == 'Bad' for n in d['prompt'].values()):
                return self._send(400, {'error': {'type': 'prompt_outputs_failed_validation', 'message': 'Prompt outputs failed validation'},
                                        'node_errors': {'1': {'class_type': 'Bad', 'errors': [{'message': 'Value not in list', 'details': 'ckpt'}]}}})
            s['prompts'][d['prompt_id']] = d
            return self._send(200, {'prompt_id': d['prompt_id'], 'number': 1, 'node_errors': {}})
        if p in ('/interrupt', '/queue', '/free'):
            s.setdefault('posts', []).append((p, json.loads(body or b'{}')))
            return self._send(200, raw=b'')
        return self._send(404, {'error': 'no route'})


class FakeComfy(object):
    def __enter__(self):
        self.state = {'calls': [], 'prompts': {}}
        handler = type('H', (Fake,), {'state': self.state})
        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.url = 'http://127.0.0.1:{}'.format(self.srv.server_address[1])
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def reset():
    while not C._Q.empty():
        C._Q.get_nowait()
    C._STATE.update({'status': {}, 'jobs': {}, 'order': [], 'last_action': None, 'dirty': True})
    C._STATE.pop('pump_error', None)
    C._PROBE['busy'] = False


def wait_state(jid, states, secs=5.0):
    end = time.time() + secs
    while time.time() < end:
        C.drain()
        st = (C._STATE['jobs'].get(jid) or {}).get('state')
        if st in states:
            return st
        time.sleep(0.01)
    raise AssertionError('job {} stuck at {}'.format(jid, (C._STATE['jobs'].get(jid) or {}).get('state')))


# ---------------------------------------------------------------- pure helpers

class Url(unittest.TestCase):
    def test_loopback_only(self):
        self.assertEqual(C.check_url('http://127.0.0.1:8188/'), 'http://127.0.0.1:8188')
        self.assertEqual(C.check_url('localhost:8189'), 'http://localhost:8189')
        self.assertEqual(C.check_url(None), 'http://127.0.0.1:8188')
        self.assertEqual(C.check_url('http://[::1]:8188'), 'http://[::1]:8188')
        for bad in ('http://192.168.1.4:8188', 'http://comfy.example.com', 'http://127.0.0.1.evil.com:8188',
                    'http://user:pw@127.0.0.1:8188', 'ftp://127.0.0.1', 'http://127.0.0.1:99999'):
            with self.assertRaises(ValueError, msg=bad):
                C.check_url(bad)


class Workflow(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(C.parse_workflow(json.dumps(API_GRAPH)), API_GRAPH)
        self.assertEqual(C.parse_workflow({'prompt': API_GRAPH}), API_GRAPH)
        with self.assertRaisesRegex(ValueError, 'API Format'):
            C.parse_workflow({'nodes': [], 'links': [], 'version': 0.4})
        with self.assertRaisesRegex(ValueError, 'not JSON'):
            C.parse_workflow('{nope')
        with self.assertRaisesRegex(ValueError, 'class_type'):
            C.parse_workflow({'1': {'inputs': {}}})

    def test_apply_inputs(self):
        g, notes = C.apply_inputs(API_GRAPH, {'6.text': 'neon', '3.seed': 42})
        self.assertEqual((g['6']['inputs']['text'], g['3']['inputs']['seed']), ('neon', 42))
        self.assertEqual(API_GRAPH['6']['inputs']['text'], 'a', 'original untouched')
        self.assertEqual(g['3']['inputs']['model'], ['4', 0])
        with self.assertRaises(ValueError) as cm:
            C.apply_inputs(API_GRAPH, {'99.text': 1, '6.nope': 1, '3.model': 'x', 'bad': 1})
        msg = str(cm.exception)
        for part in ("'99.text'", "'6.nope'", 'link', "'bad'"):
            self.assertIn(part, msg)

    def test_image_slot(self):
        g, notes = C.apply_inputs(API_GRAPH, None, 'jazib_td/td_1.png')
        self.assertEqual(g['10']['inputs']['image'], 'jazib_td/td_1.png')
        self.assertTrue(notes)
        g, _ = C.apply_inputs(API_GRAPH, {'4.ckpt_name': '$image'}, 'n.png')
        self.assertEqual((g['4']['inputs']['ckpt_name'], g['10']['inputs']['image']), ('n.png', 'example.png'))
        with self.assertRaisesRegex(ValueError, 'LoadImage'):
            C.apply_inputs({'1': {'class_type': 'SaveImage', 'inputs': {}}}, None, 'n.png')

    def test_partner_detection(self):
        self.assertEqual(C.partner_nodes(API_GRAPH), [])
        g = dict(API_GRAPH, **{'20': {'class_type': 'OpenAIDalle3', 'inputs': {}}})
        self.assertEqual(C.partner_nodes(g), [('20', 'OpenAIDalle3')])
        g2 = dict(API_GRAPH, **{'21': {'class_type': 'NewPaidNode', 'inputs': {}}})
        self.assertEqual(C.partner_nodes(g2, ['NewPaidNode']), [('21', 'NewPaidNode')])
        self.assertGreater(len(C.PARTNER_NODES), 200)
        self.assertNotIn('KSampler', C.PARTNER_NODES)

    def test_multipart_parses(self):
        body, ctype = C.multipart({'overwrite': 'true', 'type': 'input'}, [('image', 'a"b.png', PNG, 'image/png')])
        msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            b'Content-Type: ' + ctype.encode() + b'\r\n\r\n' + body)
        parts = {p.get_param('name', header='content-disposition'): p for p in msg.iter_parts()}
        self.assertEqual(parts['image'].get_payload(decode=True), PNG)
        self.assertEqual(parts['image'].get_filename(), 'a_b.png')
        self.assertEqual(parts['overwrite'].get_content().strip(), 'true')

    def test_history(self):
        self.assertEqual(C.parse_history({}, 'x')['state'], 'pending')
        h = {'x': {'outputs': {'9': {'images': [{'filename': 'a.png', 'subfolder': 's', 'type': 'output'}]},
                               '12': {'gifs': [{'filename': 'b.mp4'}]}}, 'status': {'status_str': 'success'}}}
        r = C.parse_history(h, 'x')
        self.assertEqual(r['state'], 'done')
        self.assertEqual([o['filename'] for o in r['outputs']], ['a.png', 'b.mp4'])
        e = C.parse_history({'x': {'outputs': {}, 'status': {'status_str': 'error', 'messages': [
            ['execution_error', {'node_id': '3', 'node_type': 'KSampler', 'exception_message': 'oom'}]]}}}, 'x')
        self.assertEqual(e['state'], 'error')
        self.assertIn('KSampler (3): oom', e['error'])
        self.assertIn('node 1 (Bad): Value not in list: ckpt', C.node_errors_text(json.dumps(
            {'error': {'message': 'failed'}, 'node_errors': {'1': {'class_type': 'Bad', 'errors': [
                {'message': 'Value not in list', 'details': 'ckpt'}]}}})))

    def test_misc(self):
        pid = C.new_prompt_id()
        self.assertRegex(pid, r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$')
        self.assertEqual(C.safe_name('../x y.png'), 'x_y.png')
        self.assertIn('subfolder=s', C.view_query({'filename': 'a b.png', 'subfolder': 's'}))


# ---------------------------------------------------------------- workers against a fake ComfyUI

class Worker(unittest.TestCase):
    def setUp(self):
        reset()
        self.out = tempfile.mkdtemp(prefix='jtd-comfy-')

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def job(self, base, **kw):
        j = {'id': C.new_prompt_id(), 'base': base, 'graph': API_GRAPH, 'inputs': {'6.text': 'hi'}, 'image': None,
             'image_file': None, 'confirm_spend': False, 'out_dir': self.out, 'timeout_s': 10}
        j.update(kw)
        return j

    def test_probe_up_and_down(self):
        with FakeComfy() as f:
            s = C.probe(f.url)
        self.assertEqual((s['reachable'], s['version'], s['device'], s['queue_pending']), (True, '0.34.5', 'mps', 1))
        t0 = time.time()
        s = C.probe('http://127.0.0.1:{}'.format(free_port()))
        self.assertFalse(s['reachable'])
        self.assertIn('open Comfy Desktop', s['error'])
        self.assertLess(time.time() - t0, 3.0)
        C.drain()
        self.assertFalse(C._STATE['status']['reachable'])

    def test_full_cycle_with_upload(self):
        with FakeComfy() as f:
            j = self.job(f.url, image=PNG)
            C.run_job(j)
            C.drain()
            r = C._STATE['jobs'][j['id']]
            self.assertEqual(r['state'], 'done', r)
            self.assertEqual(f.state['upload']['bytes'], PNG)
            self.assertEqual(f.state['upload']['fields']['overwrite'], 'true')
            sent = f.state['prompts'][j['id']]['prompt']
            self.assertEqual(sent['6']['inputs']['text'], 'hi')
            self.assertEqual(sent['10']['inputs']['image'], 'jazib_td/' + f.state['upload']['filename'])
            self.assertEqual(len(r['files']), 1)
            with open(r['files'][0], 'rb') as fh:
                self.assertEqual(fh.read(), PNG)
            self.assertTrue(r['files'][0].startswith(self.out))
            self.assertIn('GET /object_info/KSampler', f.state['calls'])

    def test_server_flags_api_node(self):
        g = dict(API_GRAPH, **{'30': {'class_type': 'NewPaidNode', 'inputs': {}}})
        with FakeComfy() as f:
            j = self.job(f.url, graph=g)
            C.run_job(j)
            C.drain()
            self.assertEqual(C._STATE['jobs'][j['id']]['state'], 'refused')
            self.assertNotIn('POST /prompt', f.state['calls'])
            j2 = self.job(f.url, graph=g, confirm_spend=True)
            C.run_job(j2)
            C.drain()
            self.assertEqual(C._STATE['jobs'][j2['id']]['state'], 'done')

    def test_400_and_exec_error_and_unreachable(self):
        with FakeComfy() as f:
            j = self.job(f.url, graph={'1': {'class_type': 'Bad', 'inputs': {}}}, inputs={})
            C.run_job(j)
            C.drain()
            r = C._STATE['jobs'][j['id']]
            self.assertEqual(r['state'], 'error')
            self.assertIn('HTTP 400', r['error'])
            self.assertIn('Value not in list', r['error'])
            f.state['fail'] = True
            j = self.job(f.url)
            C.run_job(j)
            C.drain()
            self.assertIn('boom', C._STATE['jobs'][j['id']]['error'])
        j = self.job('http://127.0.0.1:{}'.format(free_port()))
        C.run_job(j)
        C.drain()
        r = C._STATE['jobs'][j['id']]
        self.assertEqual(r['state'], 'error')
        self.assertIn('not reachable', r['error'])

    def test_timeout_and_cancel(self):
        with FakeComfy() as f:
            ev = threading.Event()
            C.wait_and_fetch(f.url, 'unknown-id', self.out, time.time() + 0.15, ev)
            C.drain()
            self.assertEqual(C._STATE['jobs']['unknown-id']['state'], 'timeout')
            C.cancel_job(f.url, 'abc')
            self.assertEqual([p for p, _ in f.state['posts']], ['/queue', '/interrupt'])
            self.assertEqual(f.state['posts'][1][1], {'prompt_id': 'abc'})
            C.simple_post(f.url, 'free', '/free', {'unload_models': True, 'free_memory': True})
            C.drain()
            self.assertTrue(C._STATE['last_action']['ok'])


# ---------------------------------------------------------------- handlers glue (fake comp, no TD)

class Table(object):
    def __init__(self):
        self.rows = []

    def clear(self):
        self.rows = []

    def appendRow(self, r):
        self.rows.append([str(x) for x in r])


class Glue(unittest.TestCase):
    def setUp(self):
        reset()
        self.out = tempfile.mkdtemp(prefix='jtd-comfy-')
        TH.OPS.clear()
        self.orig_file = handlers.handlers_file
        handlers.handlers_file = lambda: os.path.join(TH.TD_DIR, 'handlers.py')

    def tearDown(self):
        handlers.handlers_file = self.orig_file
        shutil.rmtree(self.out, ignore_errors=True)

    def make_comp(self, url):
        comp = TH.OP('/project1/comfy', optype='baseCOMP', family='COMP')
        comp.isCOMP = True
        comp.par = types.SimpleNamespace(Url=types.SimpleNamespace(eval=lambda: url))
        pulses = []
        result = types.SimpleNamespace(par=types.SimpleNamespace(file='', reloadpulse=types.SimpleNamespace(
            pulse=lambda: pulses.append(1))))
        kids = {'client': types.SimpleNamespace(module=C), 'status': Table(), 'jobs': Table(), 'result': result,
                'workflow': types.SimpleNamespace(text=json.dumps(API_GRAPH))}
        comp.op = kids.get
        TH.OPS[comp.path] = comp
        src = TH.OP('/project1/src', optype='nullTOP', family='TOP')
        src.saveByteArray = lambda ext: bytearray(PNG)
        TH.OPS[src.path] = src
        TH.OPS['/project1/chop'] = TH.OP('/project1/chop', optype='noiseCHOP', family='CHOP')
        return comp, kids, pulses

    def test_registered_and_mutating(self):
        for c in ('comfy_build', 'comfy_status', 'comfy_send', 'comfy_result', 'comfy_cancel', 'comfy_free'):
            self.assertIn(c, handlers.COMMANDS)
        self.assertIn('comfy_build', handlers.MUTATING)
        for c in ('comfy_status', 'comfy_result', 'comfy_send', 'comfy_cancel', 'comfy_free'):
            self.assertNotIn(c, handlers.MUTATING)

    def test_build_refuses_remote_url_first(self):
        with self.assertRaisesRegex(ValueError, 'loopback'):
            handlers.cmd_comfy_build('/project1', 'comfy', 'http://10.0.0.5:8188')
        with self.assertRaisesRegex(ValueError, 'no operator'):
            handlers.cmd_comfy_build('/nowhere', 'comfy', 'http://127.0.0.1:8188')

    def test_send_refuses_partner_without_confirm(self):
        self.make_comp('http://127.0.0.1:1')
        g = dict(API_GRAPH, **{'20': {'class_type': 'KlingTextToVideoNode', 'inputs': {}}})
        with self.assertRaisesRegex(ValueError, 'confirm_spend'):
            handlers.cmd_comfy_send('/project1/comfy', workflow=g)
        self.assertEqual(C._STATE['order'], [], 'nothing started')
        with self.assertRaisesRegex(ValueError, 'TOP'):
            handlers.cmd_comfy_send('/project1/comfy', image_from='/project1/chop', out_dir=self.out)
        with self.assertRaisesRegex(ValueError, "'6.nope'"):
            handlers.cmd_comfy_send('/project1/comfy', inputs={'6.nope': 1})
        with self.assertRaisesRegex(ValueError, 'not a comfy COMP'):
            TH.OPS['/project1/x'] = TH.OP('/project1/x', optype='baseCOMP', family='COMP')
            TH.OPS['/project1/x'].op = lambda n: None
            handlers.cmd_comfy_status('/project1/x')

    def test_send_result_status_cycle(self):
        with FakeComfy() as f:
            comp, kids, pulses = self.make_comp(f.url)
            r = handlers.cmd_comfy_send('/project1/comfy', inputs={'3.seed': 7}, image_from='/project1/src',
                                        out_dir=self.out)
            self.assertEqual(r['state'], 'starting')
            self.assertEqual(r['image_bytes'], len(PNG))
            jid = r['job']
            self.assertEqual(wait_state(jid, ('done', 'error')), 'done', C._STATE['jobs'][jid])
            C._STATE['dirty'] = True
            C.pump(comp)
            self.assertTrue(kids['result'].par.file.endswith('td_00001_.png'))
            self.assertEqual(len(pulses), 1)
            self.assertEqual(kids['jobs'].rows[1][:2], [jid, 'done'])
            res = handlers.cmd_comfy_result('/project1/comfy')
            self.assertEqual((res['job'], res['state'], res['loaded']), (jid, 'done', True))
            self.assertEqual(f.state['prompts'][jid]['prompt']['3']['inputs']['seed'], 7)
            p = handlers.cmd_comfy_status('/project1/comfy')
            self.assertIsInstance(p, handlers.Pending)
            end = time.time() + 3
            while C._PROBE['busy'] and time.time() < end:
                C.drain()
                time.sleep(0.01)
            st = p.finish()
            self.assertTrue(st['status']['reachable'])
            self.assertEqual(st['jobs'][0]['job'], jid)
            json.loads(handlers.dumps(st))
            self.assertEqual(kids['status'].rows[0], ['key', 'value'])
            c = handlers.cmd_comfy_cancel('/project1/comfy', job=jid)
            self.assertEqual(c['state'], 'cancelling')
            handlers.cmd_comfy_free('/project1/comfy')
            end = time.time() + 3
            while len(f.state.get('posts', [])) < 3 and time.time() < end:
                time.sleep(0.01)
            self.assertIn(('/free', {'unload_models': True, 'free_memory': True}), f.state['posts'])
            fr = handlers.cmd_comfy_result('/project1/comfy', job='foreign-1', out_dir=self.out)
            self.assertEqual(fr['state'], 'fetching')
            with self.assertRaisesRegex(ValueError, 'prompt_id'):
                handlers.cmd_comfy_result('/project1/comfy', job='../etc')

    def test_status_unreachable_clean(self):
        self.make_comp('http://127.0.0.1:{}'.format(free_port()))
        p = handlers.cmd_comfy_status('/project1/comfy')
        end = time.time() + 3
        while C._PROBE['busy'] and time.time() < end:
            C.drain()
            time.sleep(0.01)
        st = p.finish()
        self.assertFalse(st['status']['reachable'])
        self.assertIn('Comfy Desktop', st['hint'])


if __name__ == '__main__':
    unittest.main()
