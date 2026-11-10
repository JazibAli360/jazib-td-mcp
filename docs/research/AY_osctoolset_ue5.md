# AY - OSCToolset (Eusebi Jucgla): TD <-> Unreal Engine 5 over OSC (asset 70704; 26 Oct 2026)

Research only. Nothing loaded into TD, nothing run, no ports opened. Source: `research_src/osctoolset_70704/repo/` (shallow clone of
github.com/eusebijucgla/OSCToolset, 464 KB, HEAD 20 Oct 2026, GPL-3.0). **The TD side (OSCToolset-TouchDesigner .tox) is paid and was
NOT obtainable** (account + purchase), so TD-side internals below are from the vendor page only, not from a `toeexpand`.

## What it is
- Community post 70704 "OSCToolset v2.0" (14 Nov 2024) is a pointer page: no file, no features. Newer post 74257 (30 Mar 2026) says
  the UE plugin went open source. Pages fetched: derivative.ca 70704 + 74257, eusebijucgla.com TD page + docs landing. Docs deeper
  pages (formatted address, packs, tick, router) were not fetched; schema below is read from source instead.
- Two halves: **UE5 runtime plugin** (open, GPL-3.0, C++ over Epic's built-in `OSC` plugin; Win64 only per `.uplugin` PlatformAllowList)
  and **OSCToolset-TouchDesigner** (closed .tox, v3.0.3 3 Mar 2026; EUR 30 personal / EUR 180 studio; zip 51 MB with .tox, examples,
  prebuilt plugin for UE 5.6/5.7/5.8; needs TD 2025.*, works on Non-Commercial; Windows 10/11 listed, "could run on a Mac and send OSC to a Windows machine").
- Design idea: the user never touches OSC servers/clients; a UE GameInstance subsystem (`UOSCT_Master`) owns one server + N clients,
  and Blueprint "modules" (actor components) register typed receivers/senders by short name. The address is derived, not typed.

## Address schema (from `OSCT_Functions.cpp::FormatAddress`)
`/OSCT/<R|S>/<TYPE>[/p]/<name>` - role letter is from UE's point of view (R = UE receives, S = UE sends), TYPE upper-case:
EVENT BOOL FLOAT INT VEC2 VEC3 COLOR TRANSFORM STRING ROTATION NOTE; `/p` = **pack**. Leading `/` of the user name is stripped.
- Arg layouts (`OSCT_Parsing.cpp`): float/int/bool/string = 1 arg; VEC2 2f; VEC3 and ROTATION 3f; COLOR RGBA 4f; TRANSFORM 9f
  (loc xyz, rot xyz, scale xyz); EVENT = no arg parsed (trigger); NOTE = 3 ints (pitch, velocity, voices).
- **Pack** = one message carrying many named values: arg0 = int count N, then N times (string key, component floats). Stride
  = componentLength+1. This is their bundle substitute (one datagram, many keys); true OSC bundles are not used.
- Control/meta: `/OSCT/init`, `/OSCT/shutdown`, `/OSCT/level_changed`, `/OSCT/play_state`-style game state; `/OSCT/R/CMD <string>` runs a
  UE **console command** on the first player controller (`PC->ConsoleCommand`). Remote-exec by design: anything that can reach the
  server port can run console commands. This is the one audit-relevant behaviour.
- **Handshake / discovery (not OSCQuery):** when a UE receiver registers or goes away, UE sends `/OSCT/module_connected` /
  `/OSCT/module_disconnected` to its clients: a list of `Key%Value` strings (Name, Class, Address, Formatted Address, Role Type,
  ModuleType, Pack). The TD component uses it so it "only sends OSC when Unreal is receiving that address" and can auto-add senders
  (Export module manages "receiver profiles", fills from a UE DataTable). So discovery = UE announces its receiver list to TD.
- No OSCQuery/mDNS anywhere in the repo (grep: no HTTP, no Bonjour). Discovery is ad hoc, one-way, over the same OSC pipe.

## Latency / smoothing
- Filtering only by exact address key (`AddressToType` map, FName lookup), so routing is O(1). Router interface for Blueprints.
- **Tick interpolation** is on the receiver (UE game thread): per-receiver `Tick.bEnable`, `InterpolationSpeed`, `Tolerance`; UE
  lerps toward the last received target every frame and stops when within tolerance, so TD can send at a low rate (e.g. 30 Hz) and UE
  still renders smooth at 60+. Float, Vec2/3, Rotation, Color, Transform and their packs support it. Events/bools/ints/strings do not.
- Sends are skipped when UE is not listening for that address (TD side), and UE sends only if clients exist. No timestamps / OSC
  time tags, no ack, UDP only.

## Network defaults and audit (UE plugin source, 2,577 lines of C++; the TD .tox could not be audited)
| Item | Finding |
|---|---|
| Server bind | **`0.0.0.0:9999`** default (`OSCT_Settings.cpp`), multicast-loopback option; i.e. LAN-reachable, not loopback |
| Client target | `127.0.0.1:9998` default; list of remote clients in settings |
| `UseLocalIPV4` | optional: rewrites localhost to the machine's LAN IPv4 (a UE 5.5 workaround) |
| Console exec | `/OSCT/R/CMD` -> `ConsoleCommand(cmd)`: unauthenticated remote console on the bind address |
| Outbound network | none beyond configured OSC clients; no HTTP, no analytics, no updater in source (grep `HTTP`, `Process`, `system(`: none) |
| Subprocess / eval / pip | none (C++ only; deps Core, OSC, Networking, Sockets, Slate) |
| Licence | GPL-3.0 (the UE plugin); copyleft only matters if we ship it. User rule: licences irrelevant for research |
| TD .tox | paid, not downloaded; its Python/`eval`/sockets could not be checked. Do not buy-and-load without a `toeexpand` audit |
Verdict on safety: the plugin itself is clean, but its default `0.0.0.0` + remote console command means that on a show LAN it must
be bound to 127.0.0.1 (or firewalled) and the CMD route disabled/avoided.

## TD side (vendor claims only)
- Modules: 10 senders (Event, Bool, Float, Integer, String single-channel; Vector2, Vector3, Rotation, Color, Transform multi-channel),
  10 receivers, utils (GameState CHOP: Init/Shutdown/LevelChanged/PlayState; Debug; Export), 5 examples; 23 modules total.
- Single-channel senders: **the CHOP channel name becomes the address**. Multi-channel senders take the first N channels (Color=4).
  Receivers: you give the address and value name. Likely an OSC Out CHOP/DAT internally (UNVERIFIED, closed).
- Bidirectional: receivers bring UE values and game state back into CHOPs; no parameter mirroring, no custom-par auto-export.

## Mac / Windows / versions
UE plugin: Win64 only in `.uplugin`; macOS/Linux "you can package it yourself" (author). Prebuilt for UE 5.6/5.7/5.8. Our show
host is a Mac running Arena 7.23.2 and TD under Rosetta, so any UE machine would be a separate Windows box over the LAN anyway.
Relevance for PF26: **low today** (no UE in the plan). Value is the patterns, not the product.

## Cross-check with what we have
- `community/slice_09.md` and `top_assets_05.md`: OSC Query Server component 62663 (manuel_mitasch, MIT): Web Server DAT serving
  OSCQuery JSON for custom pars so TouchOSC/Chataigne/Vezer discover them. This is the missing half OSCToolset lacks (it has typed
  addresses + announce, no standard discovery). `AI_td_resolume.md`: Resolume OSC in 7000 / out 7001, one OSC Out target per Arena;
  our `td_publish` / `td_osc_learn` already cover TD -> Resolume.

## Patterns our MCP should adopt (proposal, nothing built)
1. **`td_osc_expose(comp, prefix='/jazib', host='127.0.0.1', port, rate_hz, oscquery=False)`**: walk a COMP's custom pars and publish
   them as an address tree `/<prefix>/<comp path>/<page>/<par>`: Float/Int -> 1 arg, Toggle -> bool, Pulse -> event (no arg), Menu/Str ->
   string, XY/XYZ/RGBA(W) pars -> vec2/vec3/color in one message, using OSCToolset's arg layouts for UE compatibility. A Parameter
   Execute DAT (change-only, rate-limited) sends; an OSC In DAT writes back (bidirectional). Defaults loopback; refuse `0.0.0.0`
   unless the user opts in. Fits "no eval / logged td_exec" rules (a fixed generated script).
2. **Pack mode**: many floats in one datagram (`count, key, v...`) instead of one message each; cheaper than bundles for sliders.
3. **Announce handshake**: on expose/unexpose send `/<prefix>/module_connected` with `Key%Value` strings (Name, Address, Type, Pack), and
   only send addresses the peer has registered (saves bandwidth, avoids spam).
4. **Optional OSCQuery** (HOST_INFO + tree JSON with TYPE, RANGE, VALUE per par, GET/SET) over a loopback Web Server DAT, adapted from
   62663; gives free discovery for Chataigne/TouchOSC without our own schema. Needs TD's WebSocket server only if LISTEN is wanted.
5. **Receiver-side smoothing is the peer's job**: send at 30 Hz with change-detection, let the receiver lerp; document this rather
   than oversampling from TD. Keep a `rate_hz` cap (our FX-pipeline rule: <=30 sends/s).
6. **Never expose a remote-exec route** (OSCToolset `/R/CMD`): if we need commands, a fixed allow-list of address -> action.
7. Names from pars, not typed addresses (same as "CHOP channel name = address"): fewer mismatches between TD and the receiver.

## UE5 notes for a future integration
- Epic's `OSC` plugin must be enabled (OSCToolset depends on it); server/client are created at GameInstance init, restart needed to
  change ports. Default UE listens 9999 (TD -> UE) and sends to 9998 (UE -> TD); set `ServerConfig.Address=127.0.0.1` for single box.
- UE-side usage is Blueprint: add the module component, set name + type (+ pack, + tick interpolation), bind the event. Our MCP could
  emit the same `/OSCT/R/<TYPE>/<name>` addresses so a stock OSCToolset UE project works with our `td_osc_expose` without buying the .tox.
- Windows-only plugin build: a UE box would be a separate Windows machine; check TD<->UE latency on LAN, not loopback.
- UNVERIFIED: TD .tox internals, UE 5.6+ behaviour of plugin on Mac, real round-trip latency (no hardware run).

## Open questions for the user
1. Is UE5 in scope at all for PF26? If not, adopt only patterns 1-4 for Resolume/TouchOSC/Chataigne.
2. Buy the .tox (EUR 30) for audit, or just emit its address schema ourselves (this file's schema)?
3. OSCQuery on by default for exposed COMPs, or opt-in per call?
