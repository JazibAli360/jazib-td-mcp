"""Jazib MCP for TouchDesigner -- ComfyUI client (Text DAT <comfy COMP>/client, written by td_comfy_build).

Source of truth: td/comfy_client.py on disk; `td_comfy_build` on an existing COMP refreshes the DAT text.
Design: docs/research/AL_td_comfyui.md (sections 3.1-3.4, 4.2). Written here from ComfyUI's own HTTP API
(local source v0.34.5: server.py); no peer code copied.

Rules (TD threading, offline help "Python threading in TouchDesigner"):
  - all HTTP runs in plain Python threads (stdlib threading + urllib, no new dependency) that get PLAIN DATA only and
    never touch an OP, a par or `op()`;
  - a thread reports through the queue `_Q`; the main thread drains it in pump(comp) (Execute DAT `pump`, Frame Start,
    and every td_comfy_* command), which writes the tables and loads finished images into the Movie File In TOP;
  - every request has a timeout; only loopback URLs (127.0.0.1 / localhost / ::1) are accepted; system proxies are
    bypassed (ProxyHandler({})) so a loopback call can never leave the machine.

Layout: pure helpers (unit-tested without TD), then HTTP + thread workers (tested against a fake ComfyUI), then the
main-thread part (needs TD ops). ASCII only.
"""
import copy
import json
import os
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

DEFAULT_URL = 'http://127.0.0.1:8188'
LOOPBACK_HOSTS = ('127.0.0.1', 'localhost', '::1')
HTTP_TIMEOUT_S = 10.0
PROBE_TIMEOUT_S = 2.0
POLL_S = 0.5
JOB_TIMEOUT_S = 600.0
JOBS_KEEP = 20          # rows kept in the jobs table / module state
MAX_OUTPUT_FILES = 16   # images fetched per job

# Partner (paid, credit-spending) API node classes: every node_id declared in ComfyUI v0.34.5 comfy_api_nodes/*.py
# (local install JZB1, read 26 Oct 2026; 267 names). The worker also asks the live server: any class whose
# /object_info entry says api_node=true is refused the same way, so a newer ComfyUI with new partner nodes is covered.
PARTNER_NODES = frozenset((
    'BeebleSwitchXImageEdit BeebleSwitchXVideoEdit BriaEraser BriaExpandImage BriaGenFill BriaImageEditNode '
    'BriaIncreaseResolution BriaRemoveImageBackground BriaRemoveVideoBackground BriaTransparentVideoBackground '
    'BriaVideoGreenScreen BriaVideoReplaceBackground ByteDance2FirstLastFrameNode ByteDance2ReferenceNode '
    'ByteDance2ReferenceNodeV2 ByteDance2TextToVideoNode ByteDanceCreateImageAsset ByteDanceCreateVideoAsset '
    'ByteDanceFirstLastFrameNode ByteDanceImageNode ByteDanceImageReferenceNode ByteDanceImageToVideoNode '
    'ByteDanceSeedAudio ByteDanceSeedNode ByteDanceSeedreamLayerSeparationNode ByteDanceSeedreamNode '
    'ByteDanceSeedreamNodeV2 ByteDanceSeedreamNodeV3 ByteDanceTextToVideoNode ByteDanceVideoEnhanceNode '
    'ClaudeNode ElevenLabsAudioIsolation ElevenLabsInstantVoiceClone ElevenLabsSpeechToSpeech '
    'ElevenLabsSpeechToText ElevenLabsTextToDialogue ElevenLabsTextToSoundEffects ElevenLabsTextToSpeech '
    'ElevenLabsVoiceSelector FishAudioInstantVoiceClone FishAudioSpeechToText FishAudioTextToSpeech '
    'FishAudioVoiceSelector Flux2ImageNode Flux3ImageToVideoNode Flux3TextToVideoNode Flux3VideoContinuationNode '
    'FluxEraseNode FluxProExpandNode FluxProFillNode FluxProUltraImageNode FluxVideoUpscaleNode FluxVTONode '
    'GeminiImage2Node GeminiImageNode GeminiInputFiles GeminiNanoBanana2 GeminiNanoBanana2V2 GeminiNode '
    'GeminiNodeV2 GeminiVideoOmni GeminiVideoOmniV2 GrokImageEditNode GrokImageEditNodeV2 GrokImageNode '
    'GrokVideoEditNode GrokVideoExtendNode GrokVideoNode GrokVideoReferenceNode HappyHorseImageToVideoApi '
    'HappyHorseReferenceVideoApi HappyHorseTextToVideoApi HappyHorseVideoEditApi HeyGenAvatarVideoNode '
    'HeyGenCreateAvatarNode HeyGenTalkingPhotoNode HeyGenTextToSpeechNode HeyGenVideoTranslateNode '
    'HitPawGeneralImageEnhance HitPawVideoEnhance IdeogramPImage IdeogramV3 IdeogramV4 KlingAvatarNode '
    'KlingFirstLastFrameNode KlingImage2VideoNode KlingImageGenerationNode KlingImageToVideoWithAudio '
    'KlingLipSyncAudioToVideoNode KlingLipSyncTextToVideoNode KlingMotionControl KlingOmniProEditVideoNode '
    'KlingOmniProFirstLastFrameNode KlingOmniProImageNode KlingOmniProImageToVideoNode '
    'KlingOmniProTextToVideoNode KlingOmniProVideoToVideoNode KlingStartEndFrameNode KlingTextToVideoNode '
    'KlingTextToVideoWithAudio KlingVideoExtendNode KlingVideoNode Krea2ImageNode Krea2StyleReferenceNode '
    'LtxApi25AudioToVideo LtxApi25ImageToVideo LtxApi25TextToVideo LtxvApiImageToVideo LtxvApiTextToVideo '
    'LumaConceptsNode LumaImageEditNode2 LumaImageModifyNode LumaImageNode LumaImageNode2 LumaImageToVideoNode '
    'LumaRay32ExtendVideoNode LumaRay32ImageToVideoNode LumaRay32KeyframeNode LumaRay32KeyframesToVideoNode '
    'LumaRay32TextToVideoNode LumaRay32VideoEditNode LumaRay32VideoReframeNode LumaReferenceNode LumaVideoNode '
    'MagnificImageRelightNode MagnificImageSkinEnhancerNode MagnificImageStyleTransferNode '
    'MagnificImageUpscalerCreativeNode MagnificImageUpscalerPreciseV2Node MeshyAnimateModelNode '
    'MeshyImageToModelNode MeshyMultiImageToModelNode MeshyRefineNode MeshyRigModelNode MeshyTextToModelNode '
    'MeshyTextureMultiViewNode MeshyTextureNode MetaMuseImageEditApi MetaMuseImageTextToImageApi '
    'MinimaxHailuo03ContextIRNode MinimaxHailuo03FirstLastFrameNode MinimaxHailuo03ReferenceNode '
    'MinimaxHailuo03RegenerateNode MinimaxHailuo03TextToVideoNode MinimaxHailuoVideoNode MinimaxImageToVideoNode '
    'MinimaxSubjectToVideoNode MinimaxTextToVideoNode OpenAIChatConfig OpenAIChatNode OpenAIDalle2 OpenAIDalle3 '
    'OpenAIGPTImage1 OpenAIGPTImageNodeV2 OpenAIInputFiles OpenAIVideoSora2 OpenRouterLLMNode '
    'PixverseImageToVideoNode PixverseTemplateNode PixverseTextToVideoNode PixverseTransitionVideoNode '
    'PixverseV6ExtendVideoNode PixverseV6FirstLastFrameNode PixverseV6FusionVideoNode PixverseV6ImageToVideoNode '
    'PixverseV6TextToVideoNode QuiverImageToSVGNode QuiverTextToSVGNode QwenImageEditApi QwenImageTextToImageApi '
    'RecraftColorRGB RecraftControls RecraftCreateStyleNode RecraftCreativeUpscaleNode RecraftCrispUpscaleNode '
    'RecraftImageInpaintingNode RecraftImageToImageNode RecraftRemoveBackgroundNode RecraftReplaceBackgroundNode '
    'RecraftStyleV3DigitalIllustration RecraftStyleV3InfiniteStyleLibrary RecraftStyleV3LogoRaster '
    'RecraftStyleV3RealisticImage RecraftStyleV3VectorIllustrationNode RecraftTextToImageNode '
    'RecraftTextToVectorNode RecraftV4CreateStyleNode RecraftV4TextToImageNode RecraftV4TextToVectorNode '
    'RecraftVectorizeImageNode ReveImageCreateNode ReveImageEditNode ReveImageRemixNode Rodin3D_Detail '
    'Rodin3D_Gen2 Rodin3D_Gen25_Image Rodin3D_Gen25_Text Rodin3D_Regular Rodin3D_Sketch Rodin3D_Smooth '
    'RunwayAleph2KeyframeNode RunwayAleph2PromptImageNode RunwayAleph2VideoToVideoNode RunwayFirstLastFrameNode '
    'RunwayImageToVideoNodeGen3a RunwayImageToVideoNodeGen4 RunwayTextToImageNode SoniloTextToMusic '
    'SoniloVideoToMusic SyncLipSyncNode SyncTalkingImageNode Tencent3DPartNode Tencent3DTextureEditNode '
    'TencentImageToModelNode TencentModelTo3DUVNode TencentSmartTopologyNode TencentTextToModelNode '
    'TopazImageEnhance TopazImageEnhanceV2 TopazVideoEnhance TopazVideoEnhanceV2 TripoConversionNode '
    'TripoEditMultiviewNode TripoImageToModelNode TripoImageToMultiviewNode TripoImportModelNode '
    'TripoMeshCompleteNode TripoMultiviewToModelNode TripoP1ImageToModelNode TripoP1MultiviewToModelNode '
    'TripoP1TextToModelNode TripoRetargetNode TripoRetopologyNode TripoRigCheckNode TripoRigNode TripoSegmentNode '
    'TripoTextToModelNode TripoTextureNode Veo3FirstLastFrameNode Veo3VideoGenerationNode Vidu2ImageToVideoNode '
    'Vidu2ReferenceVideoNode Vidu2StartEndToVideoNode Vidu2TextToVideoNode Vidu3ImageToVideoNode '
    'Vidu3StartEndToVideoNode Vidu3TextToVideoNode ViduExtendVideoNode ViduImageToVideoNode '
    'ViduMultiFrameVideoNode ViduReferenceVideoNode ViduStartEndToVideoNode ViduTextToVideoNode '
    'Wan2ImageToVideoApi Wan2ReferenceVideoApi Wan2TextToVideoApi Wan2VideoContinuationApi Wan2VideoEditApi '
    'Wan3ImageToVideoApi Wan3ReferenceToVideoApi WanImageToImageApi WanImageToVideoApi WanReferenceVideoApi '
    'WanTextToImageApi WanTextToVideoApi WavespeedFlashVSRNode WavespeedImageUpscaleNode '
).split())


# ================================================================== pure helpers (no TD, no network)

def check_url(url):
    """'http://127.0.0.1:8188' from a loopback URL; ValueError for anything else (other hosts, userinfo, bad scheme)."""
    u = str(url or DEFAULT_URL).strip()
    if '://' not in u:
        u = 'http://' + u
    p = urllib.parse.urlsplit(u)
    if p.scheme not in ('http', 'https'):
        raise ValueError('ComfyUI url must be http(s), got {!r}'.format(url))
    if p.username or p.password or '@' in p.netloc:
        raise ValueError('ComfyUI url must not carry a user/password: {!r}'.format(url))
    host = (p.hostname or '').lower()
    if host not in LOOPBACK_HOSTS:
        raise ValueError('ComfyUI url must be loopback (127.0.0.1 / localhost / ::1), got host {!r}'.format(host))
    try:
        port = p.port
    except ValueError:
        raise ValueError('bad port in ComfyUI url {!r}'.format(url))
    h = '[::1]' if host == '::1' else host
    return '{}://{}{}'.format(p.scheme, h, ':' + str(port) if port else '')


def parse_workflow(src):
    """API-format graph (dict) from a dict or JSON text. The UI export (nodes/links) is refused with a hint."""
    g = src
    if isinstance(src, (bytes, bytearray)):
        src = src.decode('utf-8')
    if isinstance(src, str):
        try:
            g = json.loads(src)
        except Exception as e:
            raise ValueError('workflow is not JSON: {}'.format(e))
    if not isinstance(g, dict) or not g:
        raise ValueError('workflow must be a non-empty JSON object (API format: {"<id>": {"class_type", "inputs"}})')
    if 'prompt' in g and isinstance(g['prompt'], dict) and 'class_type' not in g:
        g = g['prompt']  # a saved /prompt body
    if 'nodes' in g and 'links' in g:
        raise ValueError('this is the UI-format workflow (nodes/links); export it with "Save (API Format)" in ComfyUI')
    bad = [k for k, v in g.items() if not (isinstance(v, dict) and isinstance(v.get('class_type'), str)
                                            and isinstance(v.get('inputs', {}), dict))]
    if bad:
        raise ValueError('not API format: node(s) {} lack class_type/inputs'.format(sorted(bad)[:8]))
    return g


def classes(graph):
    return sorted(set(v['class_type'] for v in graph.values()))


def partner_nodes(graph, extra=()):
    """[(node_id, class_type)] of nodes that spend partner credits (static list + classes the server flagged)."""
    flagged = PARTNER_NODES | frozenset(extra)
    return sorted((k, v['class_type']) for k, v in graph.items() if v['class_type'] in flagged)


IMAGE_TOKEN = '$image'


def apply_inputs(graph, inputs=None, image_name=None):
    """A copy of graph with {"<node>.<field>": value} set. Node and field must exist (else ValueError naming it); a
    link ([id, i]) is never overwritten by a literal. The value "$image" becomes image_name; with image_name and no
    "$image" anywhere, the first LoadImage node (by id) gets it. Returns (graph, notes)."""
    g = copy.deepcopy(graph)
    notes = []
    errs = []
    used_image = False
    for key, val in (inputs or {}).items():
        node, sep, field = str(key).partition('.')
        if not sep or not node or not field:
            errs.append('{!r}: use "<node_id>.<input>", e.g. "6.text"'.format(key))
            continue
        if node not in g:
            errs.append('{!r}: no node {!r} (nodes: {})'.format(key, node, sorted(g)[:20]))
            continue
        ins = g[node].setdefault('inputs', {})
        if field not in ins:
            errs.append('{!r}: node {} ({}) has no input {!r} (has {})'.format(key, node, g[node]['class_type'], field,
                                                                           sorted(ins)[:20]))
            continue
        if is_link(ins[field]) and not is_link(val):
            errs.append('{!r}: is wired to node {}; refusing to replace a link with a value'.format(key, ins[field][0]))
            continue
        if val == IMAGE_TOKEN:
            if image_name is None:
                errs.append('{!r}: "$image" needs image_from'.format(key))
                continue
            val, used_image = image_name, True
        ins[field] = val
    if errs:
        raise ValueError('inputs: ' + '; '.join(errs))
    if image_name is not None and not used_image:
        loads = sorted((k for k, v in g.items() if v['class_type'] == 'LoadImage'), key=_node_key)
        if not loads:
            raise ValueError('image_from given but the workflow has no LoadImage node (or pass "<node>.image": "$image")')
        g[loads[0]].setdefault('inputs', {})['image'] = image_name
        notes.append('image -> node {} LoadImage.image'.format(loads[0]))
        if len(loads) > 1:
            notes.append('{} LoadImage nodes; only {} got the image'.format(len(loads), loads[0]))
    return g, notes


def is_link(v):
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int)


def _node_key(k):
    return (0, int(k), '') if str(k).isdigit() else (1, 0, str(k))


def multipart(fields, files, boundary=None):
    """(body bytes, content-type) for multipart/form-data. fields {name: str}; files [(field, filename, bytes, mime)]."""
    b = boundary or ('----jazibtd' + uuid.uuid4().hex)
    out = []
    for name, val in (fields or {}).items():
        out.append(('--' + b + '\r\nContent-Disposition: form-data; name="{}"\r\n\r\n{}\r\n'.format(
            _q(name), val)).encode('utf-8'))
    for field, filename, data, mime in (files or ()):
        out.append(('--' + b + '\r\nContent-Disposition: form-data; name="{}"; filename="{}"\r\n'
                    'Content-Type: {}\r\n\r\n'.format(_q(field), _q(filename), mime or 'application/octet-stream')
                    ).encode('utf-8'))
        out.append(bytes(data))
        out.append(b'\r\n')
    out.append(('--' + b + '--\r\n').encode('utf-8'))
    return b''.join(out), 'multipart/form-data; boundary=' + b


def _q(s):
    return str(s).replace('\\', '_').replace('"', '_').replace('\r', '_').replace('\n', '_')


def parse_history(hist, prompt_id):
    """{state: pending|done|error, outputs: [{node, filename, subfolder, type}], error?} from GET /history/<id>."""
    h = (hist or {}).get(prompt_id) if isinstance(hist, dict) else None
    if not h:
        return {'state': 'pending', 'outputs': []}
    st = h.get('status') or {}
    outs = []
    for node, o in sorted((h.get('outputs') or {}).items(), key=lambda kv: _node_key(kv[0])):
        for kind in ('images', 'gifs', 'videos'):
            for it in (o or {}).get(kind) or []:
                if isinstance(it, dict) and it.get('filename'):
                    outs.append({'node': node, 'filename': it['filename'], 'subfolder': it.get('subfolder', ''),
                                 'type': it.get('type', 'output')})
    r = {'state': 'done', 'outputs': outs}
    if st.get('status_str') == 'error' or st.get('completed') is False:
        r['state'] = 'error'
        r['error'] = _history_error(st)
    return r


def _history_error(st):
    for m in st.get('messages') or []:
        if isinstance(m, list) and len(m) == 2 and m[0] in ('execution_error', 'execution_interrupted'):
            d = m[1] or {}
            if m[0] == 'execution_interrupted':
                return 'interrupted'
            return '{} ({}): {}'.format(d.get('node_type', '?'), d.get('node_id', '?'),
                                        str(d.get('exception_message', '')).strip()[:300])
    return 'ComfyUI reported an error'


def node_errors_text(body):
    """Short text from a /prompt 400 reply {error, node_errors}."""
    try:
        d = json.loads(body) if isinstance(body, (bytes, str)) else body
    except Exception:
        return str(body)[:300]
    parts = []
    e = d.get('error') if isinstance(d, dict) else None
    if isinstance(e, dict):
        parts.append(str(e.get('message') or e.get('type') or e))
    elif e:
        parts.append(str(e))
    for nid, ne in sorted(((d or {}).get('node_errors') or {}).items())[:6]:
        msgs = [str(x.get('message', '')) + (': ' + str(x.get('details')) if x.get('details') else '')
                for x in (ne or {}).get('errors', [])][:3]
        parts.append('node {} ({}): {}'.format(nid, (ne or {}).get('class_type', '?'), '; '.join(msgs)))
    return ' | '.join(parts)[:600] or 'rejected'


def view_query(item):
    return urllib.parse.urlencode({'filename': item['filename'], 'subfolder': item.get('subfolder', ''),
                                   'type': item.get('type', 'output')})


def safe_name(s):
    keep = ''.join(c if (c.isalnum() or c in '._-') else '_' for c in str(s))
    return keep.strip('._')[:120] or 'out'


def new_prompt_id():
    return str(uuid.uuid4())  # lowercase hyphenated: ComfyUI accepts a client-chosen prompt_id in this form


# ================================================================== HTTP + workers (threads; plain data only)

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never route loopback through a proxy
_Q = queue.Queue()
_CANCEL = {}            # job -> threading.Event
_PROBE = {'busy': False}


def http(method, url, body=None, headers=None, timeout=HTTP_TIMEOUT_S):
    """(status, bytes). HTTP errors return their status + body; connection problems raise OSError."""
    req = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b''


def http_json(method, url, obj=None, timeout=HTTP_TIMEOUT_S):
    body = None if obj is None else json.dumps(obj).encode('utf-8')
    st, data = http(method, url, body, {'Content-Type': 'application/json'} if body is not None else None, timeout)
    try:
        val = json.loads(data.decode('utf-8')) if data else None
    except Exception:
        val = None
    return st, val, data


def unreachable(e):
    return 'ComfyUI not reachable ({}): open Comfy Desktop (it listens on 127.0.0.1:8188)'.format(
        type(e).__name__ + (': ' + str(getattr(e, 'reason', '') or e))[:160])


def _post(kind, **data):
    _Q.put(dict(data, kind=kind, t=time.time()))


def probe(base, timeout=PROBE_TIMEOUT_S):
    """Thread body: GET /system_stats and /queue -> a 'status' message."""
    s = {'url': base, 'checked': time.strftime('%H:%M:%S')}
    try:
        st, d, _ = http_json('GET', base + '/system_stats', timeout=timeout)
        if st != 200 or not isinstance(d, dict):
            s.update(reachable=False, error='GET /system_stats -> HTTP {}: not a ComfyUI?'.format(st))
        else:
            sysd = d.get('system') or {}
            dev = (d.get('devices') or [{}])[0] or {}
            s.update(reachable=True, version=sysd.get('comfyui_version', '?'), python=str(sysd.get('python_version', ''))[:12],
                     device=dev.get('type', '?'), vram_total_mb=int((dev.get('vram_total') or 0) / 1048576),
                     vram_free_mb=int((dev.get('vram_free') or 0) / 1048576), error='')
            st2, q, _ = http_json('GET', base + '/queue', timeout=timeout)
            if st2 == 200 and isinstance(q, dict):
                s.update(queue_running=len(q.get('queue_running') or []), queue_pending=len(q.get('queue_pending') or []))
    except Exception as e:
        s.update(reachable=False, error=unreachable(e))
    _post('status', status=s)
    return s


def _api_flagged(base, cls_list, timeout):
    """Classes the live server marks api_node=true (GET /object_info/<class>). Unknown classes are ignored here
    (POST /prompt names them)."""
    out = []
    for c in cls_list:
        st, d, _ = http_json('GET', base + '/object_info/' + urllib.parse.quote(c, safe=''), timeout=timeout)
        if st == 200 and isinstance(d, dict) and isinstance(d.get(c), dict) and d[c].get('api_node'):
            out.append(c)
    return out


def run_job(job):
    """Thread body for one job. job = plain dict: id, base, graph, inputs, image (bytes|None), image_file (str|None),
    confirm_spend, out_dir, timeout_s. Reports 'job' messages; never raises."""
    jid, base = job['id'], job['base']
    cancel = _CANCEL.setdefault(jid, threading.Event())
    t0 = time.time()

    def up(**kw):
        _post('job', job=jid, **kw)

    try:
        graph = job['graph']
        if not job.get('confirm_spend'):
            up(state='checking')
            flagged = _api_flagged(base, classes(graph), HTTP_TIMEOUT_S)
            hits = partner_nodes(graph, flagged)
            if hits:
                up(state='refused', error='partner/API nodes spend credits: {}; pass confirm_spend=true only with the '
                                          "user's go-ahead".format(', '.join('{} {}'.format(*h) for h in hits[:8])))
                return
        image_name = None
        data = job.get('image')
        if data is None and job.get('image_file'):
            with open(job['image_file'], 'rb') as f:
                data = f.read()
        if data is not None:
            up(state='uploading')
            body, ctype = multipart({'type': 'input', 'subfolder': 'jazib_td', 'overwrite': 'true'},
                                    [('image', 'td_{}.png'.format(jid[:8]), data, 'image/png')])
            st, d, raw = http_json_raw('POST', base + '/upload/image', body, ctype)
            if st != 200 or not isinstance(d, dict) or not d.get('name'):
                up(state='error', error='upload -> HTTP {}: {}'.format(st, raw[:200]))
                return
            image_name = (d.get('subfolder') + '/' if d.get('subfolder') else '') + d['name']
        graph, notes = apply_inputs(graph, job.get('inputs'), image_name)
        if cancel.is_set():
            up(state='cancelled')
            return
        up(state='queueing', notes=notes)
        st, d, raw = http_json('POST', base + '/prompt', {'prompt': graph, 'client_id': job.get('client_id', jid),
                                                         'prompt_id': jid})
        if st != 200:
            up(state='error', error='POST /prompt -> HTTP {}: {}'.format(st, node_errors_text(raw)))
            return
        up(state='queued', number=(d or {}).get('number'))
        deadline = t0 + float(job.get('timeout_s') or JOB_TIMEOUT_S)
        wait_and_fetch(base, jid, job['out_dir'], deadline, cancel)
    except Exception as e:
        up(state='error', error=unreachable(e) if isinstance(e, OSError) else '{}: {}'.format(type(e).__name__, e)[:400])
    finally:
        _CANCEL.pop(jid, None)


def http_json_raw(method, url, body, ctype):
    st, data = http(method, url, body, {'Content-Type': ctype})
    try:
        return st, json.loads(data.decode('utf-8')), data.decode('utf-8', 'replace')
    except Exception:
        return st, None, data.decode('utf-8', 'replace')


def wait_and_fetch(base, jid, out_dir, deadline, cancel=None):
    """Poll /history/<id> until done, then GET /view each output into out_dir. Reports 'job' messages."""
    cancel = cancel or threading.Event()
    running_said = False
    while True:
        if cancel.is_set():
            _post('job', job=jid, state='cancelled')
            return
        st, hist, _ = http_json('GET', base + '/history/' + urllib.parse.quote(jid, safe=''))
        h = parse_history(hist if st == 200 else {}, jid)
        if h['state'] != 'pending':
            break
        if time.time() > deadline:
            _post('job', job=jid, state='timeout', error='no result before the timeout; td_comfy_result later, or cancel')
            return
        if not running_said:
            _post('job', job=jid, state='running')
            running_said = True
        cancel.wait(POLL_S)
    if h['state'] == 'error':
        _post('job', job=jid, state='error', error=h.get('error'))
        return
    os.makedirs(out_dir, exist_ok=True)
    files = []
    for it in h['outputs'][:MAX_OUTPUT_FILES]:
        st, data = http('GET', base + '/view?' + view_query(it))
        if st != 200:
            continue
        p = os.path.join(out_dir, '{}_{}'.format(jid[:8], safe_name(it['filename'])))
        with open(p, 'wb') as f:
            f.write(data)
        files.append(p)
    _post('job', job=jid, state='done', files=files, outputs=len(h['outputs']),
          error='' if files or not h['outputs'] else 'outputs listed but /view failed')


def fetch_job(base, jid, out_dir, timeout_s):
    """Thread body for td_comfy_result on a job this COMP did not send (e.g. the comfyui MCP's run_workflow)."""
    cancel = _CANCEL.setdefault(jid, threading.Event())
    try:
        wait_and_fetch(base, jid, out_dir, time.time() + float(timeout_s), cancel)
    except Exception as e:
        _post('job', job=jid, state='error', error=unreachable(e) if isinstance(e, OSError) else str(e)[:300])
    finally:
        _CANCEL.pop(jid, None)


def simple_post(base, what, path, obj, jid=None):
    """Thread body for cancel / free: POST json, report an 'action' message."""
    try:
        st, _d, raw = http_json('POST', base + path, obj)
        _post('action', what=what, job=jid, ok=st == 200, detail='HTTP {}'.format(st) + ('' if st == 200 else ': ' + raw[:120].decode('utf-8', 'replace')))
    except Exception as e:
        _post('action', what=what, job=jid, ok=False, detail=unreachable(e))


def cancel_job(base, jid):
    ev = _CANCEL.get(jid)
    if ev is not None:
        ev.set()
    simple_post(base, 'cancel', '/queue', {'delete': [jid]}, jid)
    simple_post(base, 'interrupt', '/interrupt', {'prompt_id': jid}, jid)


def start(fn, *args):
    t = threading.Thread(target=fn, args=args, daemon=True, name='jazib-comfy-' + fn.__name__)
    t.start()
    return t


# ================================================================== main thread (TD)

_STATE = {'status': {}, 'jobs': {}, 'order': [], 'last_action': None}


def drain():
    """Apply queued thread messages to _STATE (main thread). Returns the jobs that just finished."""
    done = []
    while True:
        try:
            m = _Q.get_nowait()
        except queue.Empty:
            break
        _STATE['dirty'] = True
        k = m.pop('kind', None)
        m.pop('t', None)
        if k == 'status':
            _STATE['status'] = m['status']
            _PROBE['busy'] = False
        elif k == 'job':
            j = _STATE['jobs'].get(m['job']) or track(m['job'])
            j.update({a: b for a, b in m.items() if a != 'job'})
            if m.get('state') == 'done':
                done.append(m['job'])
                j['pending_load'] = bool(j.get('autoload', True) and j.get('files'))
        elif k == 'action':
            _STATE['last_action'] = m
    return done


def track(jid, **info):
    j = _STATE['jobs'].setdefault(jid, {'job': jid, 'started': time.strftime('%H:%M:%S')})
    j.update(info)
    if jid in _STATE['order']:
        _STATE['order'].remove(jid)
    _STATE['order'].append(jid)
    for old in _STATE['order'][:-JOBS_KEEP]:
        _STATE['jobs'].pop(old, None)
    del _STATE['order'][:-JOBS_KEEP]
    _STATE['dirty'] = True
    return j


def kick_probe(base):
    if not _PROBE['busy']:
        _PROBE['busy'] = True
        start(probe, base)
        return True
    return False


def pump(comp):
    """Main thread: drain, write the tables, load a just-finished image. Called by the Execute DAT every frame and
    by every td_comfy_* command. Cheap when nothing happened."""
    try:
        done = drain()
        if not _STATE.get('dirty', True):
            return done
        _STATE['dirty'] = False
        _write_tables(comp)
        for jid in list(_STATE['order']):
            j = _STATE['jobs'].get(jid) or {}
            if j.pop('pending_load', False):
                load_result(comp, j['files'][0])
        return done
    except Exception as e:  # never raise every frame from the Execute DAT
        _STATE['pump_error'] = '{}: {}'.format(type(e).__name__, e)[:300]
        return []


def mark_dirty():
    _STATE['dirty'] = True


def load_result(comp, file):
    top = comp.op('result')
    if top is None or not file:
        return False
    top.par.file = file
    try:
        top.par.reloadpulse.pulse()
    except Exception:
        pass
    return True


def _write_tables(comp):
    t = comp.op('status')
    if t is not None:
        s = dict(_STATE['status'])
        a = _STATE.get('last_action')
        if a:
            s['last_action'] = '{} {} {}'.format(a.get('what'), 'ok' if a.get('ok') else 'failed', a.get('detail', ''))
        t.clear()
        t.appendRow(['key', 'value'])
        for k in sorted(s):
            t.appendRow([k, str(s[k])[:200]])
    t = comp.op('jobs')
    if t is not None:
        t.clear()
        t.appendRow(['job', 'state', 'started', 'files', 'error'])
        for jid in reversed(_STATE['order']):
            j = _STATE['jobs'].get(jid) or {}
            t.appendRow([jid, j.get('state', ''), j.get('started', ''), len(j.get('files') or []),
                         str(j.get('error') or '')[:160]])


def job_view(j):
    """Compact JSON-safe view of a job for replies."""
    keep = ('job', 'state', 'started', 'files', 'outputs', 'error', 'notes', 'number', 'spend_confirmed')
    return {k: j[k] for k in keep if k in j and j[k] not in (None, '', [])}
