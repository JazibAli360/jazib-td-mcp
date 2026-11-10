# LK_projection_room

> projector_dome: LK_projection_room upgrade (projector planner + fulldome mode), 26 Oct 2026, TD 2025.31550

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:57 from `/project1/lab/LK_projection_room`

COMP: `/project1/lab/LK_projection_room` (upgraded in place; in/out architecture, Room page and stage plan kept).
Builder: `builders/projector_dome.py` (`build(parent_path)`, idempotent, T-70 safe), logic `builders/projector_dome_logic.py`
(copied into `pd_logic`), tests `test/test_projector_dome.py` (23, offline:
`python3 -I -m unittest discover -s test -p 'test_projector_dome.py'`). Backup of the COMP before the upgrade:
`output/backups/LK_projection_room_before_projector_dome_2026-10-26.tox`.
Specs: `docs/research/AT_projector_coverage.md` (sections 3, 6) and `AW_fulldome_simulator.md` (sections 5, 7).
Clean-room: par vocabulary from asterix "Projector Coverage Tool" (paid, never obtained); dome preview idea from
Theinfranet "Fulldome Simulator" (no licence, never loaded). Turbo colormap polynomial: Google / Ruofei Du, Apache-2.0.

```python
ns = dict(globals()); exec(open('<repo>/builders/projector_dome.py').read(), ns); ns['build']('/project1/lab')

Build doc: `docs/builds/projector_dome.md`

## Inputs / outputs

- in `content_in` (inTOP) 128x128
- out `domemaster_out` (outTOP) 2048x2048
- out `room_out` (outTOP) 1920x1080

## Custom parameters

### Room

| name | label | style | default | value |
|---|---|---|---|---|
| Throw | Cone angle (Lens input = angle) | Float | 50.0 | 43.4 |
| Brightness | Projector brightness | Float | 2.2 | 4.21 |
| Ambient | Room ambient | Float | 0.06 | 0.112839 |
| Orbit | Audience camera orbit (deg) | Float | 0.0 | -59.2 |
| Height | Audience camera height | Float | 3.5 | 5.34 |
| Shadows | Projector shadows | Toggle | True | True |
| Projx | Projector X | Float | 0.0 | 0.237197 |
| Projy | Projector height | Float | 2.0 | 2.24 |
| Projz | Projector distance (Z) | Float | 6.0 | 6.58 |
| Projtilt | Projector tilt (deg) | Float | -10.0 | -10.7547 |
| Projpan | Projector pan (deg) | Float | 0.0 | 2.74933 |
| Camfov | Audience camera FOV (deg) | Float | 45.0 | 45.0 |
| Camdist | Audience camera distance | Float | 11.0 | 10.469 |
| Lookheight | Camera looks at height | Float | 0.7 | 0.808625 |
| Opencontrols | Open controls window | Pulse | False | False |

### Projector

| name | label | style | default | value |
|---|---|---|---|---|
| Lensinput | Lens input | Menu | ratio | ratio |
| Throwratio | Throw ratio (distance / width) | Float | 1.2564 | 1.2564 |
| Respreset | Native resolution | Menu | hd | hd |
| Resx | Native width px | Int | 1920 | 1920 |
| Resy | Native height px | Int | 1080 | 1080 |
| Lumens | Lumens (ANSI) | Float | 6000.0 | 6000.0 |
| Fnum | F-number (info) | Float | 2.0 | 2.0 |
| Shifth | Lens shift H % of width | Float | 0.0 | 0.0 |
| Shiftv | Lens shift V % of height | Float | 0.0 | 0.0 |
| Gain | Screen gain | Float | 1.0 | 1.0 |
| Fitcontent | Content fit | Menu | fit | fit |
| Testchart | Test chart | Toggle | False | False |
| Mapres | Light map width px | Int | 1024 | 1024 |
| Showfrustum | Show frustum | Toggle | True | True |
| Unit | Units | Menu | m | m |

### Projb

| name | label | style | default | value |
|---|---|---|---|---|
| Projbon | Projector B on | Toggle | False | False |
| Projbx | B x | Float | 2.7 | 2.7 |
| Projby | B y | Float | 2.24 | 2.24 |
| Projbz | B z | Float | 6.58 | 6.58 |
| Projbtilt | B tilt | Float | -10.75 | -10.75 |
| Projbpan | B pan | Float | -8.0 | -8.0 |
| Projbthrow | B throw ratio | Float | 1.2564 | 1.2564 |
| Projbshifth | B lens shift H % | Float | 0.0 | 0.0 |
| Projbshiftv | B lens shift V % | Float | 0.0 | 0.0 |
| Projblumens | B lumens | Float | 6000.0 | 6000.0 |

### View

| name | label | style | default | value |
|---|---|---|---|---|
| Viewmode | View mode | Menu | lit | lit |
| Maxppi | Legend max ppi | Float | 40.0 | 40.0 |
| Maxnits | Legend max nits | Float | 500.0 | 500.0 |
| Heatshadows | Occlusion in heat views | Toggle | True | True |
| Shadowres | Probe width px | Int | 384 | 384 |
| Shadowbias | Occlusion bias | Float | 0.02 | 0.02 |
| Showhud | Show readouts | Toggle | True | True |

### Camera

| name | label | style | default | value |
|---|---|---|---|---|
| Campreset | Camera preset | Menu | orbit | orbit |
| Camproj | Projection | Menu | persp | persp |
| Orthowidth | Ortho width | Float | 12.0 | 12.0 |
| Lookx | Look at x | Float | 0.0 | 0.0 |
| Lookz | Look at z | Float | 0.0 | 0.0 |
| Eyeheight | Audience eye height | Float | 1.7 | 1.7 |
| Camshiftx | Camera shift x % | Float | 0.0 | 0.0 |
| Camshifty | Camera shift y % | Float | 0.0 | 0.0 |

### Dome

| name | label | style | default | value |
|---|---|---|---|---|
| Domemode | Dome mode | Menu | off | off |
| Inputformat | Input format | Menu | flat | flat |
| Domefov | Dome fov | Float | 180.0 | 180.0 |
| Dometilt | Dome tilt | Float | 0.0 | 0.0 |
| Domeradius | Dome radius m | Float | 6.0 | 6.0 |
| Seatx | Seat x | Float | 0.0 | 0.0 |
| Seatz | Seat z | Float | 0.0 | 0.0 |
| Domeeye | Eye above spring line | Float | 0.0 | 0.0 |
| Domeyaw | Look yaw | Float | 0.0 | 0.0 |
| Domepitch | Look pitch | Float | 45.0 | 45.0 |
| Domecamfov | View fov | Float | 100.0 | 100.0 |
| Domeres | Domemaster px | Int | 2048 | 2048 |
| Winaz | Window azimuth | Float | 0.0 | 0.0 |
| Winel | Window elevation | Float | 25.0 | 25.0 |
| Winhw | Window half width | Float | 60.0 | 60.0 |
| Winhh | Window half height | Float | 34.0 | 34.0 |
| Template | Angle rings | Toggle | True | True |
| Templateopacity | Rings opacity | Float | 0.5 | 0.5 |
| Domemask | Circle mask | Toggle | True | True |
| Scenex | Room fisheye x | Float | 0.0 | 0.0 |
| Sceney | Room fisheye y | Float | 1.6 | 1.6 |
| Scenez | Room fisheye z | Float | 0.0 | 0.0 |

### Readouts

| name | label | style | default | value |
|---|---|---|---|---|
| Throwdist | Throw distance m (image centre) | Float | 0.0 | 5.992032051086426 |
| Imgw | Image width m | Float | 0.0 | 4.76920747756958 |
| Imgh | Image height m | Float | 0.0 | 2.6826791763305664 |
| Imgdiag | Image diagonal m | Float | 0.0 | 5.471938133239746 |
| Hfov | H FOV deg | Float | 0.0 | 43.40139389038086 |
| Vfov | V FOV deg | Float | 0.0 | 25.235727310180664 |
| Pxpm | Px per metre (centre) | Float | 0.0 | 395.0565185546875 |
| Ppi | Ppi (centre) | Float | 0.0 | 10.034435272216797 |
| Mmpx | mm per px (centre) | Float | 0.0 | 2.531283378601074 |
| Lux | Lux (centre) | Float | 0.0 | 460.19354248046875 |
| Nits | Nits (centre) | Float | 0.0 | 146.48416137695312 |
| Fl | Foot-lamberts (centre) | Float | 0.0 | 42.756614685058594 |
| Avgppi | Ppi average on surfaces | Float | 0.0 | 6.3170270919799805 |
| Minppi | Ppi minimum | Float | 0.0 | 0.987446665763855 |
| Coverage | Image on surfaces (0-1) | Float | 0.0 | 0.9908854365348816 |
| Bthrowdist | B throw distance m | Float | 0.0 | 0.0 |
| Bppi | B ppi (centre) | Float | 0.0 | 0.0 |
| Bnits | B nits (centre) | Float | 0.0 | 0.0 |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 52 |
| Zkcols | Columns | Int | 8 | 10 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkm1 | Light | Float | 0.0 | 0.3 |
| Zkm2 | Dome view | Float | 0.0 | 0.5 |
| Zkm3 | View aids | Float | 0.0 | 0.5 |

## Perf

cook 1.425 ms (CPU 1.425 / GPU 0.54) summed over the 4 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "LK_projection_room", "parent": "/project1/lab"}` (lands parked)
