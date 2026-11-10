// PX_pointfx effector modules (clean-room, 26 Oct 2026). Each section is ONE module's code for ONE stage:
//   //@module <type> <update|colour>
// The codegen (px_logic.codegen) pastes the enabled sections, in the user's stack order, into ONE compute pass per
// stage, each inside its own { } block that first declares
//   float G   = amount x mask input (header row x; mask menu y/z/w), the module's overall gain
//   int   EM  = effector bit mask (bit i = effector i of the px_eff table is linked to this module)
// and replaces every $name with the module instance's uniform slot (uM[row].c, or uM[row].xyz for xyz/rgb params;
// $<name>ph = the engine-integrated phase of a 'rate' param). Param schemas: px_logic.MODULES (names must match).
// Every block also has const int SLOT / NSLOT (index among the enabled instances of its type / their count) and,
// with the header chunk > 0, id / seed / p0 / P of the point's rest CELL (the point takes the cell's displacement).
// Update-stage locals: uint id; float seed; vec3 p0 (rest), vec4 c0 (rest colour), vec3 P (last visible position),
//   vec3 home (kinematic target, starts at p0), vec3 o (dynamic offset), vec3 v (offset velocity), vec3 acc (force sum),
//   float age, life, heat, dis (dissolve 0..1), vec3 mk (mask registers m0..m2, cleared per frame), bool JUSTRESET,
//   float dt, int LAYER (0 scene, 1 actor, 2 pool), bool POOLPT, vec3 pcol (pool spawn colour), vec4 qrot (module
//   rotation this frame, S4: rotate splats / oriented sprites with the field), float qid (pull to identity orientation).
//   Visible position = home + o; spring/damping/drag pull o back to 0 (core, px_update.glsl).
// Colour-stage locals: id, seed, p0, c0, P, o, v, age, life, heat, dis, mk, LAYER, pcol and the outputs vec3 col,
//   float alpha, float size (x base size), float stretch (extra length in radii), float emis (HDR emission multiplier),
//   vec3 sdir (stretch axis, 0 = screen velocity), float sthin (thin across it), float iso / isosize (lattice blob).
// Defines: DT TIME FRAME SIDE COUNT RESET LOW MID HIGH LEVEL BEAT BEATPH BPM BAR LFO1 LFO2 BBC BBR CAMPOS CAMFWD
//   NSCENE NACTOR NPOOL ACTORVEL (px_logic.decl).

//@module prox_push update
vec3 q = pxI($space) == 1 ? home : P;
int bi;
float w = G * pxFlip(pxW(q, EM, $radius, $falloff, pxI($shape), pxI($combine), $noiseedge, $noisefreq, $edge, bi), $flip);
pxPublish(mk, pxI($publish), 1, w);
if (bi >= 0 && w != 0.0) {
	vec3 f = pxDirOf(pxI($dir), bi, q) * ($strength * w);
	if (pxI($mode) == 1) acc += f; else home += f;
}

//@module prox_vortex update
vec3 q = pxI($space) == 1 ? home : P;
int bi;
float w = G * pxFlip(pxW(q, EM, $radius, $falloff, pxI($shape), pxI($combine), $noiseedge, $noisefreq, $edge, bi), $flip);
if (bi >= 0 && w != 0.0) {
	vec3 c = pxXCentre(bi);
	vec3 ax = pxXAxis(bi);
	vec3 r = q - c;
	vec3 rr = r - ax * dot(r, ax);
	if (pxI($mode) == 1) { home = c + pxRot(home - c, ax, $strength * w); qrot = pxQMul(pxQAxis(ax, $strength * w), qrot); }
	else acc += (pxSafeN(cross(ax, rr), vec3(0.0)) * $strength - pxSafeN(rr, vec3(0.0)) * $pull + ax * $lift) * w;
}

//@module prox_dissolve update
vec3 q = pxI($space) == 1 ? home : P;
int bi;
float w = G * pxFlip(pxW(q, EM, $radius, $falloff, pxI($shape), pxI($combine), $noiseedge, $noisefreq, $edge, bi), $flip);
if (bi >= 0) {
	float n = pxFbm(p0 * $noisescale, 3, 11u);
	float d = smoothstep($threshold - $soft, $threshold + 1e-4, w + (n - 0.5) * $noisegain);
	dis = max(dis, d);
	if (d > 0.0) acc += (pxDirOf(0, bi, q) * $release + pxCurl(p0 * $curlscale, TIME, 2) * $curl) * d;
}

//@module prox_burn update
if (!POOLPT) {
	vec3 q = pxI($space) == 1 ? home : P;
	int bi;
	float w = G * pxFlip(pxW(q, EM, $radius, $falloff, pxI($shape), pxI($combine), $noiseedge, $noisefreq, $edge, bi), $flip);
	heat += w * $rise * dt;
	float fl = heat * smoothstep(0.4, 1.0, pxFbm(p0 * $flamefreq + vec3(0.0, -TIME * $flamespeed, 0.0), 3, 23u));
	acc += vec3(0.0, $lift * fl, 0.0) + pxCurl(p0 * 2.0, TIME, 2) * ($embers * fl);
	if ($consume > 0.0) dis = max(dis, smoothstep($consume, $consume + 0.5, heat));
} else if (int(id) % NSLOT == SLOT) {
	// pool point owned by this instance (pool split by id among the burn instances): respawn when dead, else fly
	bool alive = life > 0.0 && age < life;
	uint fr = uint(max(FRAME, 0.0));
	if (!alive && G > 0.0 && pxRnd(id, fr * 13u + 5u) < $rate * dt) {
		int sm = pxI($source);
		vec3 sp = home;
		vec3 ax = vec3(0.0, 1.0, 0.0);
		vec3 sc = vec3(1.0, 0.45, 0.1);
		bool ok = false;
		if (sm == 0) {                                   // scan: a random scene point that is burning now
			int nsc = max(pxI(NSCENE), 1);
			int pick = int(pxRnd(id, fr * 17u + 9u) * float(nsc)) % nsc;
			vec4 st2 = pxStateT(pick, 2);
			if (st2.w > 0.2) { sp = pxStateT(pick, 0).xyz; ok = true; }
			ivec2 rp = ivec2((pick % max(pxI(SIDE), 1)) * 4 + 1, pick / max(pxI(SIDE), 1));
			ivec2 rs = textureSize(sTD2DInputs[1], 0);
			if (rp.x < rs.x && rp.y < rs.y) sc = texelFetch(sTD2DInputs[1], rp, 0).rgb;
		} else {
			int e = pxFirst(EM);
			if (e >= 0) { sp = pxXSample(e, id, fr, sm == 2, ax); ok = true; if (sm == 1) ax = pxXAxis(e); }
		}
		if (ok) {
			o = sp - home;
			v = pxCone(ax, radians($cone), id, fr) * ($speed * (0.5 + pxRnd(id, fr * 43u + 11u)));
			age = 0.0;
			life = $lifespan * (0.5 + pxRnd(id, fr * 47u + 13u));
			heat = 1.0;
			pcol = sc;
		}
	}
	if (life > 0.0 && age < life)
		acc += vec3(0.0, $lift, 0.0) * (1.0 - age / life) + pxCurl(P * 2.0, TIME, 2) * $embers;
}

//@module prox_burn colour
if (LAYER != 2) {
	float fl = heat * smoothstep(0.4, 1.0, pxFbm(p0 * $flamefreq + vec3(0.0, -TIME * $flamespeed, 0.0), 3, 23u));
	float x = clamp(fl * $heatscale, 0.0, 1.0) * G;
	vec3 fire = pxI($firesrc) == 1 ? pxPal(x) : pxHue(pxFire(x), $ramphue);
	col = mix(col, fire, clamp(x * 2.0, 0.0, 1.0));
	emis += $emission * x;
} else if (int(id) % NSLOT == SLOT) {
	// ember: fire ramp by remaining life, part of the source point's colour kept (S5: splat embers keep the splat colour)
	float x = life > 0.0 ? clamp(1.0 - age / life, 0.0, 1.0) * $heatscale : 0.0;
	vec3 fe = pxI($firesrc) == 1 ? pxPal(clamp(x, 0.0, 1.0)) : pxHue(pxFire(clamp(x, 0.0, 1.0)), $ramphue);
	col = mix(fe, pcol, clamp($keep, 0.0, 1.0));
	alpha = 1.0;
	emis += $emission * clamp(x, 0.0, 1.0) * G;
}

//@module prox_magnet update
vec3 q = pxI($space) == 1 ? home : P;
int bi;
float w = G * pxFlip(pxW(q, EM, $radius, $falloff, pxI($shape), pxI($combine), $noiseedge, $noisefreq, $edge, bi), $flip);
if (bi >= 0 && w != 0.0) {
	float sd = pxXSd(bi, home);
	vec3 n = pxXGrad(bi, home);
	vec3 s = home - n * (sd - $shell) + (pxRnd3(id, 41u) - 0.5) * $jitter;
	home = mix(home, s, clamp(w * $pull, 0.0, 1.0));
}

//@module prox_stretch update
vec3 q = pxI($space) == 1 ? home : P;
int bi;
float w = G * pxFlip(pxW(q, EM, $radius, $falloff, pxI($shape), pxI($combine), $noiseedge, $noisefreq, $edge, bi), $flip);
int smd = pxI($mode);
if (w != 0.0 && smd == 2) {                       // slices: each band flattens toward its centre plane (snap = pull)
	vec3 ax = pxStretchAxis(pxI($axis), bi, home);
	ax = dot(ax, ax) > 0.0 ? ax : vec3(0.0, 1.0, 0.0);
	vec3 c = bi >= 0 ? pxXCentre(bi) : BBC;
	float bw = max($bandwidth, 1e-4);
	float s = dot(p0 - c, ax) / bw;
	home += ax * ((floor(s) + 0.5 - s) * bw * clamp(w * $snap, 0.0, 1.0));
} else if (w != 0.0 && ($snap != 0.0 || smd == 1)) {   // lattice: snap to cells (lattice mode snaps fully by default)
	float cs = max($cell, 1e-4);
	float sn = clamp(w * (smd == 1 && $snap == 0.0 ? 1.0 : $snap), 0.0, 1.0);
	home = mix(home, floor(home / cs + 0.5) * cs, sn);
	qid = max(qid, sn);                           // S4: snapped splats lose their rotation (cube / voxel look)
}

//@module prox_stretch colour
vec3 q = pxI($space) == 1 ? p0 : P;
int bi;
float w = G * pxFlip(pxW(q, EM, $radius, $falloff, pxI($shape), pxI($combine), $noiseedge, $noisefreq, $edge, bi), $flip);
int smd = pxI($mode);
if (smd == 2) {                                   // slices: points in the gap part of each band vanish
	vec3 ax = pxStretchAxis(pxI($axis), bi, P);
	ax = dot(ax, ax) > 0.0 ? ax : vec3(0.0, 1.0, 0.0);
	vec3 c = bi >= 0 ? pxXCentre(bi) : BBC;
	float s = dot(p0 - c, ax) / max($bandwidth, 1e-4);
	if (fract(s) > 1.0 - $gap) alpha *= 1.0 - clamp(w, 0.0, 1.0);
} else {
	stretch += $stretch * w;
	if (w > 1e-4) {
		vec3 ax = pxStretchAxis(pxI($axis), bi, P);
		if (dot(ax, ax) > 0.0) sdir = ax;
	}
	sthin = max(sthin, clamp($thin * w, 0.0, 1.0));
	if (smd == 1) {                               // lattice: splats become isotropic cell blobs (S4)
		float sn = clamp(w * ($snap == 0.0 ? 1.0 : $snap), 0.0, 1.0);
		iso = max(iso, sn);
		isosize = max($cell, 1e-4) * 0.5;
	}
}
col = mix(col, $tint, clamp($tintamt * w, 0.0, 1.0));

//@module strands colour
// wave 4 K22: blades along up + curl-noise wind (sway); length varies per point; thin across (mirror ref_strands)
if (G > 0.0) {
	vec3 sup = pxSafeN($up, vec3(0.0, 1.0, 0.0));
	vec3 sax = $sway > 0.0 ? pxSafeN(sup + pxCurl(p0 * $swayscale, TIME * $swayspeed, 2) * $sway, sup) : sup;
	stretch += G * $length * (1.0 - $lengthvar * pxRnd(id, 71u)) * mix(1.0, pxLum(c0.rgb), $bylum);
	sdir = sax;
	sthin = max(sthin, clamp($thin * G, 0.0, 1.0));
}

//@module prox_scale colour
vec3 q = pxI($space) == 1 ? p0 : P;
int bi;
float w = G * pxFlip(pxW(q, EM, $radius, $falloff, pxI($shape), pxI($combine), $noiseedge, $noisefreq, $edge, bi), $flip);
size *= max(1.0 + $sizegain * w, 0.0);
alpha *= max(1.0 + $alphagain * w, 0.0);
if ($cull > 0.0 && w < $cull) alpha = 0.0;

//@module prox_colour colour
vec3 q = pxI($space) == 1 ? p0 : P;
int bi;
float w = G * pxFlip(pxW(q, EM, $radius, $falloff, pxI($shape), pxI($combine), $noiseedge, $noisefreq, $edge, bi), $flip);
int md = pxI($mode);
int csm = pxI($colsrc);
vec3 C1 = $colour;                                  // W1-B colour source (solid = the colour par, the v2 look)
if (csm != 0 || $palkeep > 0.0) C1 = pxColSrc(vec4(float(csm), $palpos, $palspread, $palkeep), $colour, col, clamp(w, 0.0, 1.0));
vec3 tgt = col;
if (md == 0) tgt = vec3(pxLum(col)) * C1 * 2.0;
else if (md == 1) tgt = C1;
else if (md == 2) tgt = csm == 2 ? C1 : mix(C1, $colour2, clamp(w, 0.0, 1.0));
else if (md == 3) tgt = pxHue(col, $hueshift);
else if (md == 4) tgt = max(vec3(1.0) - col, vec3(0.0));
float wc = mix(w, smoothstep(0.0, 0.12, w), clamp($cover, 0.0, 1.0));   // cover: solid colour bands, short fade-in
col = mix(col, tgt, clamp(wc, 0.0, 1.0));
emis += $emission * w * (1.0 + $flicker * (pxRnd(id, uint(max(FRAME, 0.0)) * 7u + 3u) * 2.0 - 1.0));

//@module curl update
int md = pxI($mode);
vec3 cv = pxCurl((md == 1 ? p0 : P) * $scale, $speedph, pxI($octaves));
if (md == 1) home += cv * ($distance * G); else acc += cv * ($strength * G);

//@module wind update
float gu = 1.0 + $gust * (pxNoise(vec3(TIME * $gustfreq, seed * 3.0, 0.0), 5u) * 2.0 - 1.0);
acc += ($gravity + $wind * gu + vec3(0.0, $buoyancy * heat, 0.0)) * G;
if ($floor > 0.5) {
	float y = home.y + o.y;
	if (y < $floory) { o.y += $floory - y; if (v.y < 0.0) v.y = -v.y * $bounce; }
}

//@module attractor update
vec3 c = pxCentreOf(EM);
float sc = max($scale, 1e-5);
vec3 qa = (P - c) / sc + $offset;
vec3 fv = pxAttractor(pxI($type), qa, vec4($a, $b, $c, $d), $custom > 0.5) * (sc * $speed);
float fs = length(fv);
if ($limit > 0.0 && fs > $limit) fv *= $limit / fs;
acc += (fv - v) * ($strength * G);

//@module orbit update
vec3 c = pxCentreOf(EM);
vec3 ax = pxAxisOf(EM, pxI($axis));
vec3 r = home - c;
float rl = max(length(r - ax * dot(r, ax)), max($minr, 1e-4));
float oa = $speedph * G * pow(rl, -$falloff);
home = c + pxRot(r, ax, oa);
qrot = pxQMul(pxQAxis(ax, oa), qrot);

//@module twist update
vec3 c = pxCentreOf(EM);
vec3 ax = pxAxisOf(EM, pxI($axis));
vec3 r = home - c;
float k = ($twist + $wobble * sin($wobblespeedph)) * G;
if (pxI($mode) == 1) {                            // bend: the axis curves (curvature k), arc length kept (KANDA tunnel)
	vec3 bd, nn;
	pxBendFrame(ax, bd, nn);
	vec4 qb;
	home = c + pxBend(r, ax, bd, nn, k, qb);
	qrot = pxQMul(qb, qrot);
} else {
	float ang = k * dot(r, ax);
	home = c + pxRot(r, ax, ang);
	qrot = pxQMul(pxQAxis(ax, ang), qrot);
}

//@module explode update
float pg = $auto < 0.5 ? $progress : $automax * ($auto < 1.5 ? fract($rateph) : smoothstep(0.0, 1.0, 1.0 - abs(2.0 * fract($rateph) - 1.0)));   // auto progress (28 Oct)
vec3 c = pxCentreOf(EM);
vec3 r = home - c;
vec3 ax = pxAxisOf(EM, pxI($axis));
int md = pxI($mode);
vec3 rd = pxSafeN(pxRnd3(id, 51u) - 0.5, vec3(0.0, 1.0, 0.0));
vec3 d = md == 1 ? ax * (dot(r, ax) < 0.0 ? -1.0 : 1.0) : (md == 2 ? rd : pxSafeN(r, rd));
float e = pow(max(pg, 0.0), $power) * G;
home = c + pxRot(r, ax, $swirl * e) + d * ($distance * e * (1.0 - $random + $random * 2.0 * seed));
qrot = pxQMul(pxQAxis(ax, $swirl * e), qrot);

//@module wave update
vec3 dirv = pxSafeN($dir, vec3(1.0, 0.0, 0.0));
vec3 c = pxCentreOf(EM);
int ty = pxI($type);
float s;
if (ty == 1) { float rr = length(p0 - c); s = sin(rr * $freq - $speedph) * exp(-$decay * rr); }
else if (ty == 2) s = sin(dot(dirv, p0) * $freq) * cos($speedph);
else if (ty == 3) s = pxFbm(p0 * $freq + dirv * $speedph, 3, 61u) * 2.0 - 1.0;
else s = sin(dot(dirv, p0) * $freq - $speedph);
int axs = pxI($axis);
vec3 ad = axs == 5 ? pxSafeN(p0 - c, vec3(0.0, 1.0, 0.0)) : pxAxisOf(EM, axs);
home += ad * ($amp * s * G);

//@module jitter update
int md = pxI($mode);
vec3 j;
if (md == 2) j = pxRnd3(id, 71u) - 0.5;
else {
	float tt = max(TIME, 0.0) * $rate;
	float f0 = floor(tt);
	vec3 ja = pxRnd3(id, 71u + uint(f0) * 3u) - 0.5;
	if (md == 1) {
		vec3 jb = pxRnd3(id, 71u + uint(f0 + 1.0) * 3u) - 0.5;
		float u = tt - f0;
		j = mix(ja, jb, u * u * (3.0 - 2.0 * u));
	} else j = ja;
}
home += j * (2.0 * $amp * G);

//@module glitch update
// mode blocks (v1): random cells jump by an offset, re-rolled every `hold` s. mode packet (SA18, Superman holograms):
// each picked cell moves RIGIDLY (offset + rotation about the cell centre, splats rotate with it through qrot) scaled
// by the envelope (beat / trigger decay): the scene breaks into packets on the hit and reassembles as it decays.
float bs = max($block, 1e-4);
ivec3 bk = ivec3(floor(p0 / bs));
uint st = uint(floor(max(TIME, 0.0) / max($hold, 1e-3))) * 97u;
int es = pxI($envsrc);
float genv = es == 1 ? BEAT : (es >= 2 && es <= 5 ? uG[4][es - 2] : 1.0);
if (pxLattice(bk, st + 3u) < $prob) {
	vec3 goff = (vec3(pxLattice(bk, st + 5u), pxLattice(bk, st + 6u), pxLattice(bk, st + 7u)) - 0.5) * (2.0 * $offset * G);
	if (pxI($gmode) == 1) {
		vec3 gc = (vec3(bk) + 0.5) * bs;
		vec3 gax = pxSafeN(vec3(pxLattice(bk, st + 11u), pxLattice(bk, st + 12u), pxLattice(bk, st + 13u)) - 0.5,
		                   vec3(0.0, 1.0, 0.0));
		vec4 gq = pxQAxis(gax, radians($rot) * (pxLattice(bk, st + 14u) * 2.0 - 1.0) * genv * G);
		home = gc + pxQMat(gq) * (home - gc) + goff * genv;
		qrot = pxQMul(gq, qrot);
	} else
		home += goff * genv;
}
if ($quantize != 0.0) {
	float qc = bs / max($qcells, 1.0);
	home = mix(home, floor(home / qc + 0.5) * qc, clamp($quantize * G, 0.0, 1.0));
}

//@module audio_displace update
int bd = pxI($band);
vec3 c = pxCentreOf(EM);
float a;
if (bd == 0) a = LOW;
else if (bd == 1) a = MID;
else if (bd == 2) a = HIGH;
else if (bd == 3) a = LEVEL;
else if (bd == 4) a = pxSpec((p0.y - (BBC.y - BBR)) / max(2.0 * BBR, 1e-5));
else if (bd == 5) a = pxSpec(length(p0 - c) / max(BBR, 1e-5));
else a = pxSpec(seed);
int dm = pxI($dir);
vec3 d;
if (dm == 1) d = vec3(0.0, 1.0, 0.0);
else if (dm == 2) d = vec3(1.0, 0.0, 0.0);
else if (dm == 3) d = vec3(0.0, 0.0, 1.0);
else if (dm == 4) d = pxCurl(p0 * 1.5, TIME, 1);
else d = pxSafeN(p0 - c, vec3(0.0, 1.0, 0.0));
home += d * (($amp * a + $beatkick * BEAT) * G);

//@module shockwave update
int tg = clamp(pxI($trigger), 0, 4);
float ta = tg == 4 ? BEATPH * 60.0 / max(BPM, 1e-3) : uG[5][tg];
vec3 c = pxCentreOf(EM);
float x = (length(p0 - c) - ta * $speed) / max($width, 1e-4);
float w = exp(-x * x) * exp(-$decay * ta) * G;
home += pxSafeN(p0 - c, vec3(0.0, 1.0, 0.0)) * ($amp * w);

//@module shockwave colour
int tg = clamp(pxI($trigger), 0, 4);
float ta = tg == 4 ? BEATPH * 60.0 / max(BPM, 1e-3) : uG[5][tg];
vec3 c = pxCentreOf(EM);
float x = (length(p0 - c) - ta * $speed) / max($width, 1e-4);
float w = exp(-x * x) * exp(-$decay * ta) * G;
col = mix(col, $ringcol, clamp(w * $colourmix, 0.0, 1.0));
emis += $emission * w;

//@module mask_region update
vec3 q = pxI($space) == 1 ? home : P;
int bi;
float w = G * pxFlip(pxW(q, EM, $radius, $falloff, pxI($shape), pxI($combine), $noiseedge, $noisefreq, $edge, bi), $flip);
pxPublish(mk, pxI($out) + 1, pxI($op), w);

//@module mask_image update
float t = pxMaskTex(P, pxI($proj), pxCentreOf(EM), $size, pxI($chan), pxI($mirror));
float w = smoothstep($threshold, $threshold + max($soft, 1e-4), t) * G;
pxPublish(mk, pxI($out) + 1, pxI($op), w);

//@module mask_attr update
int by = pxI($by);
float a;
if (by == 0) a = p0.y;
else if (by == 1) a = p0.x;
else if (by == 2) a = p0.z;
else if (by == 3) a = length(p0 - pxCentreOf(EM));
else if (by == 4) a = length(P - CAMPOS);
else if (by == 5) a = pxLum(c0.rgb);
else if (by == 6) a = seed;
else if (by == 7) a = length(v);
else if (by == 8) a = age;
else if (by == 9 || by == 11) a = pxSplatAttr(texelFetch(sTD2DInputs[1], r0p + ivec2(2, 0), 0).xyz, by == 9 ? 0 : 1);
else a = c0.a;                                                  // 10: splat / point opacity (rest alpha)
float s = max($soft, 1e-5);
float w = smoothstep($lo - s, $lo, a) * (1.0 - smoothstep($hi, $hi + s, a)) * G;
pxPublish(mk, pxI($out) + 1, pxI($op), w);

//@module dissolve_noise update
float pg = $auto < 0.5 ? $progress : $automax * ($auto < 1.5 ? fract($rateph) : smoothstep(0.0, 1.0, 1.0 - abs(2.0 * fract($rateph) - 1.0)));   // auto progress (28 Oct)
float n = pxFbm(p0 * $scale, pxI($octaves), 13u) + dot(p0 - BBC, $bias);
float s = max($soft, 1e-4);
float e = pg * (1.0 + s);
float d = (1.0 - smoothstep(e - s, e, n)) * G;
dis = max(dis, d);
if (d > 0.0) acc += (pxCurl(p0 * 1.5, TIME, 2) * $curl + vec3(0.0, $up, 0.0) + pxSafeN(p0 - BBC, vec3(0.0, 1.0, 0.0)) * $release) * d;

//@module dissolve_gradient update
float pg = $auto < 0.5 ? $progress : $automax * ($auto < 1.5 ? fract($rateph) : smoothstep(0.0, 1.0, 1.0 - abs(2.0 * fract($rateph) - 1.0)));   // auto progress (28 Oct)
vec3 c = pxCentreOf(EM);
int am = pxI($axis);
float gr;
if (am == 5) gr = length(p0 - c) / max($range, 1e-5);
else if (am == 7) gr = length(p0 - CAMPOS) / max($range, 1e-5);               // SA19: peels from the camera outward
else if (am == 8) {                                                             // SA20: helix about y through the centre
	float ang = atan(p0.z - c.z, p0.x - c.x) * 0.15915494309189535 + 0.5;
	float pt = max($pitch, 1e-4);
	gr = (ang + (p0.y - c.y + $range) / pt) / (2.0 * $range / pt + 1.0);
}
else {
	vec3 ax = am == 6 ? pxSafeN($dirv, vec3(0.0, 1.0, 0.0)) : pxAxisOf(EM, am);
	gr = dot(p0 - c, ax) / max($range, 1e-5) * 0.5 + 0.5;
}
gr += (pxFbm(p0 * $warpscale, 2, 17u) - 0.5) * $warp;
float s = max($soft, 1e-4);
float e = pg * (1.0 + s);
float d = (1.0 - smoothstep(e - s, e, gr)) * G;
dis = max(dis, d);
// release: starts `linger` (front units) after the dissolve (fragments hang in place, then go), + swirl about y
float rl = $linger > 0.0 ? (1.0 - smoothstep(e - s - $linger, e - $linger, gr)) * G : d;
if (rl > 0.0) acc += (pxCurl(p0 * 1.5, TIME, 2) * $curl + vec3(0.0, $up, 0.0) + pxSafeN(p0 - c, vec3(0.0, 1.0, 0.0)) * $release
                      + cross(vec3(0.0, 1.0, 0.0), p0 - c) * $swirl) * rl;

//@module dissolve_time update
int od = pxI($order);
float key = od == 1 ? (p0.y - BBC.y) / max(BBR, 1e-5) * 0.5 + 0.5 : (od == 2 ? length(p0 - BBC) / max(BBR, 1e-5) : seed);
float x = fract($rateph - key * $spread);
float s = max($soft, 1e-4);
float d = smoothstep(0.0, s, x) * (1.0 - smoothstep($width, $width + s, x)) * G;
dis = max(dis, d);
if (d > 0.0) acc += (pxCurl(p0 * 1.5, TIME, 2) * $curl + vec3(0.0, $up, 0.0) + pxSafeN(p0 - BBC, vec3(0.0, 1.0, 0.0)) * $release) * d;

//@module lifetime update
if (!POOLPT) {                                    // the pool keeps its own ember lives (prox_burn)
	float lp = max($life * (1.0 + $lifevar * (pxRnd(id, 81u) * 2.0 - 1.0)), 1e-3);
	life = lp;
	if (JUSTRESET && $stagger > 0.5) age = pxRnd(id, 83u) * lp;
	if (age > lp) { age = mod(age, lp); o = vec3(0.0); v = vec3(0.0); dis = 0.0; heat = 0.0; }
}

//@module lifetime colour
if (LAYER == 2) G = 0.0;
float lp = max(life, 1e-3);
float f = smoothstep(0.0, max($fadein, 1e-4), age) * (1.0 - smoothstep(lp - max($fadeout, 1e-4), lp, age));
alpha *= mix(1.0, f, clamp(G, 0.0, 1.0));

//@module density colour
float lod = $bydist > 0.5 ? clamp(1.0 - (length(P - CAMPOS) - $near) / max($far - $near, 1e-4), $minlod, 1.0) : 1.0;
if (pxRnd(id, 91u) >= mix(1.0, $density * lod, clamp(G, 0.0, 1.0))) { alpha = 0.0; size = 0.0; }

//@module colour_ramp colour
int at = pxI($attr);
float a;
if (at == 0) a = P.y;
else if (at == 1) a = length(P - CAMPOS);
else if (at == 2) a = length(v);
else if (at == 3) a = age;
else if (at == 4) a = heat;
else if (at == 5) a = pxFbm(p0 * $noisescale, 3, 29u);
else if (at == 6) a = mk.x;
else if (at == 7) a = mk.y;
else if (at == 8) a = mk.z;
else if (at == 9) a = dis;
else if (at == 10) a = length(P - BBC);
else if (at == 11) a = seed;
else if (at == 12) a = P.x;
else if (at == 13) a = P.z;
else if (at == 14) a = age / max(life, 1e-3);
else if (at == 15) a = pxLum(col);
else if (at == 16 || at == 18) a = pxSplatAttr(texelFetch(sTD2DInputs[1], r0p + ivec2(2, 0), 0).xyz, at == 16 ? 0 : 1);
else a = c0.a;                                                  // 17: splat / point opacity (rest alpha)
float den = $hi - $lo;
den = abs(den) < 1e-6 ? 1e-6 : den;
float x = clamp((a - $lo) / den, 0.0, 1.0);
vec3 rc = x < 1.0 / 3.0 ? mix($col0, $col1, x * 3.0) : (x < 2.0 / 3.0 ? mix($col1, $col2, x * 3.0 - 1.0) : mix($col2, $col3, x * 3.0 - 2.0));
if (pxI($ramp) == 1) rc = pxPal(x);                // shared palette (Palette page; CO2 / CO3 acid remap by luma)
int bm = pxI($blend);
vec3 tgt = rc;
if (bm == 1) tgt = col * rc;
else if (bm == 2) tgt = col + rc;
else if (bm == 3) tgt = vec3(1.0) - (vec3(1.0) - col) * (vec3(1.0) - rc);
else if (bm == 4) tgt = col;
col = mix(col, tgt, G);
emis += $emission * x * G;

//@module colour_adjust colour
vec3 cc = col * exp2($exposure);
cc = pxHue(cc, $hue);
cc = mix(vec3(pxLum(cc)), cc, $saturation);
cc = (cc - 0.18) * $contrast + 0.18;
cc = pow(max(cc, vec3(0.0)), vec3(1.0 / max($gamma, 1e-3)));
cc = mix(cc, cc * $tint, $tintamt);
col = mix(col, cc, G);
alpha *= mix(1.0, $alphamul, G);
emis += $emission * G;

//@module heat_spread update
// SA21: points near hot points heat up (the shared grid's distance field of PX's hot_pts cloud: every point whose heat
// is over Hotthr), so fire creeps along the scan instead of staying where an effector put it. Needs the grid
// (PXE_GRID: input 2, /project1/effectors Gridon + the px hot cloud row; PX does both when this module is on).
#ifdef PXE_GRID
if (!POOLPT) {
	float hd = pxgFieldSd(P);
	heat += $rate * dt * pxFall(hd, $radius, $falloff, 0) * G;
}
#endif

//@module light colour
// Relight by the light effectors (/project1/effectors kind light, W1-A packed light region; selection = this module's
// shared selection, default all). rgb = mix(col, col x (ambient + gain x sum lights), relight) + add x sum; each
// light's colour = pxColSrc(cs, tint, its own colour (palette-resolved by the list), k) x its intensity. Normal: the
// splat's smallest-scale axis from the state rotation + rest scale (pxeSplatNormal), plain points glow by distance
// (auto), or view / radial / up. Numpy twin: px_logic.ref_light_module.
int lb = pxeLightBase();
int LK = pxeLightCountB(lb);
if ((LK > 0 || $bounce > 0.0) && G > 0.0) {
	vec3 vv = pxSafeN(CAMPOS - P, vec3(0.0, 0.0, 1.0));
	vec3 lsc = texelFetch(sTD2DInputs[1], r0p + ivec2(2, 0), 0).xyz;
	vec4 lq = texelFetch(sTD2DInputs[0], t0 + ivec2(4, 0), 0);
	bool hasS = max(lsc.x, max(lsc.y, lsc.z)) > 0.0;
	int nmode = pxI($normal);
	int model = pxI($model);
	vec3 nn = vv;
	if (nmode == 1 || (nmode == 0 && hasS)) nn = hasS ? pxeSplatNormal(lq, lsc, vv) : vv;
	else if (nmode == 0) model = 3;                     // plain points: no normal, glow by distance
	else if (nmode == 3) nn = pxSafeN(P - BBC, vv);
	else if (nmode == 4) nn = vec3(0.0, 1.0, 0.0);
	vec4 lmode = vec4(float(model), $wrap, $spec, $rough);
	vec4 lcs = vec4(float(pxI($colsrc)), $palpos, $palspread, $palkeep);
	vec3 Ls = vec3(0.0);
	for (int k = 0; k < PXE_LIGHT_MAX; k++) {
		if (k >= LK) break;
		if (!pxeLightSelB(lb, k, pxShSel, pxShIds)) continue;
		float sh = pxeLightShadeB(lb, k, P, nn, vv, lmode);
		if (sh <= 0.0) continue;
		vec4 l0 = pxeLTb(lb, k, 0);
		vec3 lc = pxI($colsrc) == 3 && $palkeep <= 0.0 ? l0.rgb : pxColSrc(lcs, $tint, l0.rgb, float(k));
		Ls += lc * (l0.w * sh);
	}
#ifdef PXE_GRID
	if ($bounce > 0.0) Ls += $bouncecol * ($bounce * pxFall(pxgFieldSd(P), $bounceradius, 2.0, 2));   // SA5 bounce
#endif
	float rl = clamp($relight * G, 0.0, 1.0);
	col = mix(col, col * ($ambient + Ls * $gain), rl) + Ls * ($add * G);
	emis += $emit * pxLum(Ls) * G;
}

//@module velocity_streak colour
// source force (v1): the integrated offset velocity (screen streak in the sprite shader). camera / both (K25 + SA16):
// + the apparent world velocity of the point under the camera move, -(CAMVEL + CAMOMEGA x (P - CAMPOS)): streak
// along that world axis (sdir; splats: covariance stretch), so a fast crane / director move smears the scan.
int vsrc = pxI($source);
vec3 vrel = vsrc == 0 ? v : (-(CAMVEL + cross(CAMOMEGA, P - CAMPOS)) + (vsrc == 2 ? v : vec3(0.0)));
float sp = length(vrel);
stretch += min(sp * $gain, $maxlen) * G;
emis += $colourspeed * sp * G;
if (vsrc != 0 && sp > 1e-6) sdir = vrel / sp;
