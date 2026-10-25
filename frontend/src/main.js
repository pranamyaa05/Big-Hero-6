/* Scroll director + page behaviour. The 3D state is a pure function of the scroll chapter T:
   0 hero, 1 problem, 2..8 the six repair steps, 9 examples, 10-11 hidden, 12 request form. */
import * as THREE from 'three';
import { createWorld, S, BOTTLE_HALF, CAP_PIECE_Y } from './world.js';
import { EX } from './ex.js';
import { initBackend } from './backend.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
const sm = t => t * t * (3 - 2 * t);
const eio = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const eo = t => 1 - Math.pow(1 - t, 3);
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const keyLerp = (x, pts) => {
  if (x <= pts[0][0]) return pts[0][1];
  for (let i = 0; i < pts.length - 1; i++) if (x < pts[i + 1][0]) return lerp(pts[i][1], pts[i + 1][1], sm((x - pts[i][0]) / (pts[i + 1][0] - pts[i][0])));
  return pts[pts.length - 1][1];
};

const STAGES = [
  ['Snap a photo', 'Snap a photo of the object that is hard to use. Add 1–3 photos, optional dimensions, a short description of the problem and who it needs to work for.'],
  ['Scaled 3D digital twin', 'ReForm3D doesn’t just see an object. It reasons about how the object is used, what gets in the way and who struggles with it. The photo becomes a scaled digital twin.'],
  ['AI understands', 'Geometric and functional analysis: object recognition, interaction analysis and the functional requirement, mapped onto eight interaction primitives. Here: a smooth cap that weak hands can’t grip.'],
  ['AI generates the aid', 'Generative intervention: the AI writes the part as CAD code, and the engine turns it into a 3D mesh and a print-ready STL. Candidates are weighed, one is chosen: a wing grip that turns with a palm.'],
  ['Compatibility check', 'Before anything prints, the part is checked: a closed solid, thick enough walls, no unsupported overhangs, and a real slicer run for print time and plastic.'],
  ['Print & fit', 'Printed in durable, recyclable filament at home or in a community makerspace, then fitted on. A bottle that was hard to open becomes one anyone can open, for a few grams of plastic.']
];

/* chapter poses: camera orbit (az, el, dist), look-at height, screen position of the look-at point, exposure */
const POSE = [
  { az: 14, el: 9, dist: 4.6, ty: 0.70, sx: 0.69, sy: 0.55, exp: 1.08 },   // 0 hero
  { az: -16, el: 9, dist: 5.4, ty: 0.70, sx: 0.80, sy: 0.56, exp: 0.82 },    // 1 problem
  { az: 6, el: 8, dist: 4.7, ty: 0.64, sx: 0.68, sy: 0.45, exp: 1.0 },       // 2 snap
  { az: -24, el: 8, dist: 4.6, ty: 0.66, sx: 0.66, sy: 0.45, exp: 0.92 },    // 3 digital twin
  { az: 24, el: 10, dist: 4.1, ty: 0.80, sx: 0.66, sy: 0.45, exp: 0.9 },     // 4 understand
  { az: 0, el: 8, dist: 5.4, ty: 1.02, sx: 0.68, sy: 0.45, exp: 0.95 },      // 5 generate
  { az: -12, el: 6, dist: 5.2, ty: 1.0, sx: 0.68, sy: 0.45, exp: 1.0 },      // 6 check
  { az: 0, el: 9, dist: 7.0, ty: 1.05, sx: 0.68, sy: 0.47, exp: 1.0 },       // 7 print
  { az: 18, el: 6, dist: 4.4, ty: 0.72, sx: 0.68, sy: 0.54, exp: 1.08 },     // 8 done
  { az: 16, el: 6, dist: 4.6, ty: 0.8, sx: 0.70, sy: 0.55, exp: 1.08 },      // 9 examples
  { az: 16, el: 6, dist: 4.6, ty: 0.8, sx: 0.70, sy: 0.55, exp: 1.08 },      // 10
  { az: -18, el: 6, dist: 4.6, ty: 0.72, sx: 0.30, sy: 0.56, exp: 1.08 },    // 11
  { az: -18, el: 6, dist: 4.6, ty: 0.72, sx: 0.30, sy: 0.56, exp: 1.08 }     // 12 repair
];

(async function main() {
  const root = document.documentElement;
  root.classList.add('js');
  setTimeout(() => document.body.classList.add('ready'), 5000);
  let backend = null;
  const ldBar = $('#ldBar'), ldTxt = $('#ldTxt'), loader = $('#loader');
  const setLd = (p, t) => { ldBar.style.width = p + '%'; if (t) ldTxt.textContent = t; };
  const isMobile = () => innerWidth < 900;
  const finishLoader = () => { loader.classList.add('done'); document.body.classList.add('ready'); };

  setLd(12, 'Loading 3D models');
  let W;
  try { W = await createWorld($('#gl'), { accent: '#ff6b2c', mobile: isMobile() }); }
  catch (err) { console.error(err); root.classList.add('no-gl'); $('#gl').style.display = 'none'; finishLoader(); wireBasics(); return; }
  setLd(62, 'Lighting the stage');

  const { bottle, bu, capPiece, cu, newCap, nu, ghosts, printer, models, CAP_Y0, CAP_Y1, camera } = W;
  const NX = EX.length;
  const glCanvas = $('#gl');
  const state = { resKey: 0, resA: 0, T: 0, Ts: 0, rotY: 0.5, mRot: EX.map((_, i) => 0.4 + i * 0.37), userRot: 0, userVel: 0, sel: 0, time: 0, px: 0, py: 0, pxs: 0, pys: 0, photo: false, snapReq: false, flashed1: false, flashed2: false, frameDist: 4.6, frameTy: 0.78, frameEl: 6 };
  let canvasA = 1;
  const pres = [1, ...EX.map(() => 0)];
  const objs = [bottle, ...models.map(m => m.group)];

  /* ---------- layout metrics -> chapter T ---------- */
  let K = [0, 1, 2, 3, 4, 5, 6], V = [0, 1, 2, 8, 9, 9.4, 12], vw = innerWidth, vh = innerHeight, secs = {};
  function measure() {
    vw = innerWidth; vh = innerHeight;
    const top = el => el.getBoundingClientRect().top + scrollY;
    const sec = id => { const el = $('#' + id); return { el, top: top(el), h: el.offsetHeight }; };
    secs = { hero: sec('hero'), problem: sec('problem'), how: sec('how'), ex: sec('examples'), repair: sec('repair') };
    // examples: on desktop park the text column just under the nav; on a phone the part sits above the text, so centre the section
    const exPad = parseFloat(getComputedStyle(secs.ex.el).paddingTop), exK = secs.ex.top + exPad - (isMobile() ? vh * 0.47 : 92);
    K = [0, secs.problem.top + secs.problem.h * 0.45 - vh * 0.5, secs.how.top, secs.how.top + secs.how.h - vh, exK,
      Math.max(exK + 60, secs.ex.top + secs.ex.h - vh * 0.5), secs.repair.top + secs.repair.h * 0.5 - vh * 0.5];
    for (let i = 1; i < K.length; i++) K[i] = Math.max(K[i], K[i - 1] + 2);
    W.resize(vw, vh);
    fitWords();
  }
  const toT = y => { for (let i = 0; i < K.length - 1; i++) if (y < K[i + 1]) return lerp(V[i], V[i + 1], clamp((y - K[i]) / (K[i + 1] - K[i]))); return 12; };

  function fitWords() {
    const w = $('#wordmark'); w.style.fontSize = '100px';
    const bw = w.getBoundingClientRect().width || 1; w.style.fontSize = (100 * (vw * 0.94) / bw) + 'px';
    const f = $('.foot-big'); f.style.fontSize = '100px';
    const fp = getComputedStyle(f.parentElement), avail = f.parentElement.clientWidth - parseFloat(fp.paddingLeft) - parseFloat(fp.paddingRight);
    const fw = f.scrollWidth || 1; f.style.fontSize = Math.min(100 * (avail / fw), 420) + 'px';
  }

  /* ---------- camera pose ---------- */
  const mobileSy = [[0, 0.72], [1, 0.5], [2, 0.27], [8.6, 0.27], [9.2, 0.23], [11.4, 0.23], [12, 0.2]];
  function poseAt(T) {
    const i = Math.min(POSE.length - 2, Math.floor(T)), f = sm(T - i), a = POSE[i], b = POSE[i + 1], p = {};
    for (const k in a) p[k] = lerp(a[k], b[k], f);
    const g = sm(clamp((T - 8.5) / 0.6)) * (1 - sm(clamp((T - 9.8) / 0.4)));
    p.dist = lerp(p.dist, state.frameDist, g); p.ty = lerp(p.ty, state.frameTy, g); p.el = lerp(p.el, state.frameEl, g);
    const res = W.getResult();
    if (res && state.resA > 0.001) { const r = state.resA; p.dist = lerp(p.dist, res.dist, r); p.ty = lerp(p.ty, res.ty, r); p.el = lerp(p.el, res.el, r); }
    p.tx = keyLerp(T, [[0, 0], [6.65, 0], [7, 0.22], [7.8, 0.22], [8.0, -0.55], [8.6, -0.55], [9.2, 0]]);
    if (isMobile()) { p.sx = 0.5; p.dist *= T > 6.6 && T < 8.1 ? 2.05 : T > 8.1 ? 1.65 : 1.4; p.sy = keyLerp(T, mobileSy); p.dist *= 1 + 0.35 * g; }
    return p;
  }
  const bxAt = T => keyLerp(T, [[0, 0], [6.65, 0], [7, -0.55], [8.6, -0.55], [9.2, 0]]);

  /* ---------- pins ---------- */
  const pinEls = { wing: $('#pinWing'), snap: $('#pinSnap'), h: $('#pinH'), d: $('#pinD'), n: $('#pinN'), brk: $('#pinBreak'), piece: $('#pinPiece'), fit: $('#pinFit'), ex: $('#pinEx') };
  const tmp = { x: 0, y: 0, z: 0 }, V3 = new THREE.Vector3(), V4 = new THREE.Vector3(), RIGHT = new THREE.Vector3();
  function placePin(el, v3, on) {
    if (!on) { el.classList.remove('on'); return; }
    W.project(v3, tmp);
    if (tmp.z > 1 || tmp.x < -40 || tmp.x > vw + 40) { el.classList.remove('on'); return; }
    el.style.transform = 'translate3d(' + tmp.x.toFixed(1) + 'px,' + tmp.y.toFixed(1) + 'px,0)'; el.classList.add('on');
  }

  /* ---------- DOM refs ---------- */
  const how = $('#how'), stepNo = $('#stepNo'), stepTitle = $('#stepTitle'), stepText = $('#stepText'), vf = $('#vf'), polaroid = $('#polaroid'), polImg = $('#polImg');
  const railBtns = $$('#howRail button'), railFill = railBtns.map(b => $('i', b));
  const in0 = $$('#in0 li'), kvTwin = $$('#kvTwin div'), kvAI = $$('#kvAI div'), prims = $$('#prims span'), pipe = $$('#pipe li'), cands = $$('#cands span'), checks = $$('#checks li');
  const prBar = $('#prBar'), prLayer = $('#prLayer'), rescued = $('#rescued'), flashEl = $('#flash');
  $('#mH').textContent = W.measures.heightMm; $('#mD').textContent = W.measures.diaMm; $('#mN').textContent = W.measures.neckMm;
  $('#tH').textContent = W.measures.heightMm + ' mm'; $('#tD').textContent = W.measures.diaMm + ' mm'; $('#tN').textContent = W.measures.neckMm + ' mm';
  let curStage = -1;
  const flash = () => { flashEl.classList.remove('on'); void flashEl.offsetWidth; flashEl.classList.add('on'); };
  const setOn = (list, fn) => list.forEach((el, i) => el.classList.toggle('on', !!fn(i)));

  function updateHowUI(T) {
    const stT = clamp(T - 2, 0, 6), i = Math.min(5, Math.floor(stT)), u = stT - i;
    const inside = T >= 1.7 && T <= 8.4;
    how.dataset.stage = i;
    if (i !== curStage) {
      curStage = i; stepNo.textContent = 'Step ' + (i + 1) + ' of 6'; stepTitle.textContent = STAGES[i][0]; stepText.textContent = STAGES[i][1];
      railBtns.forEach((b, k) => b.classList.toggle('on', k === i));
    }
    railFill.forEach((el, k) => { el.style.width = (k < i ? 100 : k === i ? u * 100 : 0) + '%'; });
    setOn(in0, k => i > 0 || u > 0.12 + k * 0.2);
    setOn(kvTwin, k => i > 1 || (i === 1 && u > [0.05, 0.28, 0.5, 0.72][k]));
    setOn(kvAI, k => i > 2 || (i === 2 && u > [0.1, 0.3, 0.5, 0.7][k]));
    setOn(prims, k => ['Rotate', 'Grip'].includes(prims[k].textContent) && (i > 2 || (i === 2 && u > 0.78)));
    setOn(pipe, k => i > 3 || (i === 3 && u > [0.12, 0.42, 0.72][k]));
    setOn(cands, k => i > 3 || (i === 3 && (u > 0.64 ? k === 1 : u > 0.18 && k === Math.floor((u - 0.18) / 0.15) % 3)));
    setOn(checks, k => i > 4 || (i === 4 && u > [0.2, 0.45, 0.7][k]));
    const pu = i === 5 ? u : 0, p = clamp((pu - 0.14) / 0.56);
    prBar.style.width = (i === 5 ? eio(p) * 100 : 0) + '%';
    const layers = Math.round(eio(p) * 225); prLayer.textContent = 'Layer ' + layers + ' of 225';
    rescued.classList.toggle('on', i === 5 && u > 0.95);
    // flashes
    if (T >= 2.55 && T < 3.2 && !state.photo) state.snapReq = true;
    if (T >= 2.5 && T < 3.1 && !state.flashed1) { state.flashed1 = true; flash(); }
    if (T < 2.3) { state.flashed1 = false; }
    if (T >= 7.96 && T < 8.5 && !state.flashed2) { state.flashed2 = true; flash(); }
    if (T < 7.8) state.flashed2 = false;
    polaroid.classList.toggle('on', state.photo && T >= 2.6 && T < 3.5);
    vf.classList.toggle('on', T >= 2.0 && T < 2.8);
    return { stT, i, u, inside };
  }

  /* ---------- per-frame: choreography ---------- */
  const SH = { PX: 1.0, PZ: 0.1, plateTop: 0.07 };
  function choreograph(T, dt) {
    const time = state.time, stT = clamp(T - 2, 0, 6);
    const bx = bxAt(T);
    // presence and sliding
    const inGal = T > 8.75 && T < 9.95;
    const target = pres.map((_, k) => (k === 0 ? 1 : 0));
    if (inGal) { target.fill(0); target[state.sel + 1] = 1; }
    // a part from the design server replaces the bottle in the request chapter
    const res = W.getResult(), resOn = !!res && T > 10.6;
    if (resOn || (T > 10.6 && document.documentElement.classList.contains('has-printer'))) target[0] = 0;   // the request panel shows the printer instead of the bottle
    state.resA += ((resOn ? 1 : 0) - state.resA) * (1 - Math.exp(-dt * 5.5));
    if (res) { res.group.visible = state.resA > 0.01; res.group.position.set((1 - state.resA) * -5.5, 0, 0); res.group.rotation.y = state.rotY + state.userRot; }
    for (let k = 0; k <= NX; k++) pres[k] += (target[k] - pres[k]) * (1 - Math.exp(-dt * 5.5));
    // spin
    const gate = 1 - sm(clamp((stT - 0.9) / 0.2)) * (1 - sm(clamp((stT - 4.8) / 0.2)));
    if (!reduce) { state.rotY += dt * 0.26 * gate; for (let k = 0; k < NX; k++) state.mRot[k] += dt * 0.3; }
    state.userRot += state.userVel; state.userVel *= 0.94;
    bottle.position.set(bx + (1 - pres[0]) * -5.5, BOTTLE_HALF * S, 0);
    bottle.rotation.y = state.rotY + state.userRot;
    bottle.visible = pres[0] > 0.01;
    for (let k = 1; k <= NX; k++) { objs[k].position.set((1 - pres[k]) * 5.5, 0, 0); objs[k].rotation.y = state.mRot[k - 1] + state.userRot; objs[k].visible = pres[k] > 0.01; }
    // the original cap is not broken: it sits on the bottle until the AI decides to swap it, then lifts off and is laid aside
    const lift = sm(clamp((stT - 2.6) / 0.3)), lay = sm(clamp((stT - 2.85) / 0.5));
    capPiece.position.set(
      lerp(bottle.position.x, bottle.position.x - 0.66, lay),
      lerp(bottle.position.y + CAP_PIECE_Y * S + lift * 0.45, 0.0288 * S + 0.004, lay),
      lerp(bottle.position.z, 0.62, lay));
    capPiece.rotation.set(0, lerp(bottle.rotation.y, 32 * Math.PI / 180, lay), lay * (Math.PI / 2 - 0.05));
    const capGone = sm(clamp((T - 7.85) / 0.25));
    capPiece.scale.setScalar(S * Math.max(0.001, 1 - capGone));
    capPiece.visible = bottle.visible && capGone < 0.999;

    // scan / hologram
    let scan = -1e3, scanOn = 0;
    if (stT >= 1 && stT < 4.55) { if (stT < 1.85) { scan = lerp(-0.14, 0.15, eio(clamp((stT - 1) / 0.85))); scanOn = 1; } else scan = 1e3; }
    else if (stT >= 4.55 && stT < 5.0) { scan = lerp(0.15, -0.14, eio(clamp((stT - 4.55) / 0.45))); scanOn = 1; }
    const hot = stT < 2.05 ? 0 : stT < 2.35 ? eo((stT - 2.05) / 0.3) : stT < 4.4 ? 1 : stT < 4.8 ? 1 - sm((stT - 4.4) / 0.4) : 0;
    for (const u of [bu, cu]) { u.uScan.value = scan; u.uScanOn.value = scanOn; u.uHot.value = hot; }

    // ghost candidates (generate) and fit test (check)
    ghosts.forEach(g => { g.group.visible = false; g.u.uAlpha.value = 0; });
    if (stT >= 3 && stT < 5) {
      const gu = stT - 3;
      ghosts.forEach((g, i) => {
        let a = 0, dx = [-0.9, 0, 0.9][i], dy = 0.5;
        if (gu < 1) {
          a = eo(clamp((gu - 0.05 - i * 0.1) / 0.22));
          if (gu > 0.62) { const k = eio(clamp((gu - 0.62) / 0.26)); if (i !== 1) { a *= 1 - k; dx += (i === 0 ? -1 : 1) * 1.4 * k; } else dx = lerp(dx, 0, k); }
        } else {
          const c = gu - 1;
          if (i === 1) { dx = 0; dy = lerp(0.5, 0, eio(clamp((c - 0.1) / 0.62))); a = c < 0.8 ? 1 : 1 - sm((c - 0.8) / 0.18); }
        }
        if (a > 0.01) { g.group.visible = true; g.u.uAlpha.value = a; g.group.position.set(bottle.position.x + dx, bottle.position.y + dy, 0); g.group.rotation.y = time * 0.7 + i * 1.7; }
      });
    }

    // printed cap + print head
    newCap.visible = false; nu.uPrint.value = 1e3; nu.uPrintGlow.value = 0; printer.group.visible = false; printer.light.intensity = 0; printer.tipMat.emissiveIntensity = 0.6;
    if (stT >= 5) {
      const u = stT - 5, plateTop = SH.plateTop;
      const slideIn = 1 - eo(clamp(u / 0.14)), slideOut = eio(clamp((u - 0.7) / 0.08)), slide = (u < 0.7 ? slideIn : slideOut) * 4.6;
      const p = clamp((u - 0.14) / 0.56), pe = eio(p);
      printer.group.visible = u < 0.79; printer.group.position.set(SH.PX + slide, 0, SH.PZ);
      nu.uPrint.value = u < 0.14 ? CAP_Y0 - 0.001 : CAP_Y0 + pe * (CAP_Y1 - CAP_Y0) + (p >= 1 ? 0.01 : 0);
      newCap.visible = pres[0] > 0.01;
      if (u < 0.78) {
        newCap.position.set(SH.PX + slide, plateTop - CAP_Y0 * S, SH.PZ); newCap.rotation.y = 0;
        const printing = u >= 0.14 && u < 0.72; nu.uPrintGlow.value = printing ? 1 : 0;
        const wy = plateTop + (nu.uPrint.value - CAP_Y0) * S, ang = pe * 70;
        let hy = wy + 0.135; if (u >= 0.7) hy += eio(clamp((u - 0.7) / 0.08)) * 0.6;
        const sw = sm(clamp((pe - 0.46) / 0.08));
        printer.head.position.set(lerp(Math.cos(ang) * 0.164, Math.sin(ang * 0.4) * 0.17, sw), hy, lerp(Math.sin(ang) * 0.164, 0, sw));
        printer.tipMat.emissiveIntensity = printing ? 5 : 0.6; printer.light.intensity = printing ? 2.4 : 0;
        W.updatePrinterRig(pe);
      } else {
        const t = clamp((u - 0.78) / 0.17), t1 = clamp(t / 0.62), t2 = clamp((t - 0.62) / 0.38);
        const sx0 = SH.PX, sy0 = plateTop - CAP_Y0 * S, sz0 = SH.PZ, ex = bottle.position.x, ey = bottle.position.y, ez = bottle.position.z;
        if (t < 0.62) { const e = eio(t1); newCap.position.set(lerp(sx0, ex, e), lerp(sy0, ey + 0.7, e) + Math.sin(Math.PI * t1) * 0.45, lerp(sz0, ez, e)); newCap.rotation.y = bottle.rotation.y + e * 1.0; }
        else { const e = eio(t2); newCap.position.set(ex, ey + 0.7 * (1 - e), ez); newCap.rotation.y = bottle.rotation.y + 1.0 + e * (Math.PI * 4 - 1.0); }
        if (t >= 1) newCap.rotation.y = bottle.rotation.y;
      }
    }
  }

  /* ---------- pins & overlays that depend on the projected scene ---------- */
  function overlays(T) {
    camera.updateMatrixWorld();
    RIGHT.setFromMatrixColumn(camera.matrixWorld, 0);
    const stT = clamp(T - 2, 0, 6);
    const bpos = bottle.position;
    const stub = V3.set(0, CAP_PIECE_Y, 0); bottle.localToWorld(stub); const stubW = stub.clone();
    placePin(pinEls.snap, stubW, T < 0.85 && bottle.visible);
    const sil = (yLocal, rLocal, dir) => V4.set(bpos.x, bpos.y + yLocal * S, bpos.z).addScaledVector(RIGHT, dir * rLocal * S);
    placePin(pinEls.h, sil(0.04, 0.052, 1).clone(), stT > 1.55 && stT < 3.0);
    placePin(pinEls.d, sil(-0.05, 0.0545, 1).clone(), stT > 1.7 && stT < 3.0);
    placePin(pinEls.n, sil(0.0875, 0.025, 1).clone(), stT > 1.85 && stT < 3.0);
    placePin(pinEls.brk, stubW.clone().addScaledVector(RIGHT, -0.17), stT > 2.2 && stT < 2.7);
    placePin(pinEls.piece, V4.copy(capPiece.position).add(new THREE.Vector3(0, 0.34, 0)).clone(), stT > 2.8 && stT < 3.4);
    placePin(pinEls.fit, V4.set(bpos.x, bpos.y + 0.1275 * S, bpos.z).addScaledVector(RIGHT, 0.34).clone(), stT > 4.62 && stT < 5.0);
    // the wing-grip cap once it is back on the bottle
    placePin(pinEls.wing, V4.set(bpos.x, bpos.y + CAP_Y1 * S, bpos.z).addScaledVector(RIGHT, 0.17).clone(), T > 7.97 && T < 8.95 && pres[0] > 0.9);
    // example pin: sticks to a feature of the part, and hides when that feature turns away from the camera
    {
      const k = state.sel, ex = EX[k], m = models[k], b = m.box, show = T > 8.9 && T < 9.85 && pres[k + 1] > 0.9;
      V3.set(b.min.x + ex.anchor[0] * (b.max.x - b.min.x), b.min.y + ex.anchor[1] * (b.max.y - b.min.y), b.min.z + ex.anchor[2] * (b.max.z - b.min.z)); m.group.localToWorld(V3);
      const rx = V3.x - m.group.position.x, rz = V3.z - m.group.position.z, cxz = camera.position.x - m.group.position.x, czz = camera.position.z - m.group.position.z;
      const rl = Math.hypot(rx, rz), facing = rl < 0.15 ? 1 : (rx * cxz + rz * czz) / (rl * Math.hypot(cxz, czz) + 1e-6);
      placePin(pinEls.ex, V3.clone(), show && (ex.anchor[1] > 0.95 || facing > -0.35));
    }

    // viewfinder box follows the bottle
    {
      const a = V3.set(bpos.x, bpos.y + 0.13 * S + 0.05, bpos.z).clone(), b2 = V4.set(bpos.x, bpos.y - 0.13 * S - 0.05, bpos.z).clone();
      const c = { x: 0, y: 0, z: 0 }, d = { x: 0, y: 0, z: 0 };
      W.project(a, c); W.project(b2, d);
      const h = d.y - c.y, w = h * 0.62, cx = (c.x + d.x) / 2;
      vf.style.width = w + 'px'; vf.style.height = h + 'px'; vf.style.transform = 'translate(' + (cx - w / 2) + 'px,' + c.y + 'px)';
      state.vfRect = { cx, top: c.y, w, h };
    }
  }

  function takePhoto() {
    const r = state.vfRect; if (!r) return; const k = glCanvas.width / vw;
    const cv = document.createElement('canvas'); cv.width = 320; cv.height = 352; const x = cv.getContext('2d');
    const g = x.createRadialGradient(160, 120, 10, 160, 176, 260); g.addColorStop(0, '#26503f'); g.addColorStop(1, '#0a1913'); x.fillStyle = g; x.fillRect(0, 0, 320, 352);
    const pad = r.h * 0.18, sw = r.w + pad * 2, sh = sw * 1.1;
    x.drawImage(glCanvas, (r.cx - sw / 2) * k, (r.top + r.h / 2 - sh / 2) * k, sw * k, sh * k, 0, 0, 320, 352);
    try { polImg.src = cv.toDataURL('image/jpeg', 0.88); state.photo = true; } catch (e) { state.photo = false; }
  }

  /* ---------- examples picker ---------- */
  const exList = $('#exList'), exName = $('#exName'), exHelps = $('#exHelps'), exFail = $('#exFail'), exPrint = $('#exPrint'), exPrims = $('#exPrims'), pinExTxt = $('#pinExTxt');
  function setSel(k) {
    state.sel = k; const e = EX[k], m = models[k];
    exName.textContent = e.name; exHelps.textContent = e.helps; exFail.textContent = e.fails; exPrint.textContent = e.prints; pinExTxt.textContent = e.pin;
    exPrims.textContent = ''; e.prims.forEach(p => { const s = document.createElement('span'); s.className = 'on'; s.textContent = p; exPrims.appendChild(s); });
    state.frameDist = m.dist; state.frameTy = m.ty; state.frameEl = e.el;
    $$('button', exList).forEach((b, i) => b.setAttribute('aria-pressed', i === k));
  }
  function buildExamples(thumbs) {
    EX.forEach((e, k) => {
      const b = document.createElement('button'); b.type = 'button'; b.setAttribute('aria-pressed', 'false');
      const img = document.createElement('img'); img.alt = ''; img.src = thumbs[k] || ''; img.width = 120; img.height = 138;
      const s = document.createElement('span'); s.textContent = e.name;
      b.append(img, s); b.addEventListener('click', () => setSel(k)); exList.appendChild(b);
    });
    setSel(0);
  }
  function makeThumbs() {
    return models.map((m, k) => { m.group.rotation.y = 0.55; const url = W.snapshot([m.group], m.fit); m.group.rotation.y = 0; return url; });
  }

  /* ---------- basic page behaviour ---------- */
  function wireBasics() {
    // anchors
    $$('a[href^="#"]').forEach(a => a.addEventListener('click', e => {
      const id = a.getAttribute('href').slice(1); const el = id === 'top' ? document.body : document.getElementById(id); if (!el) return;
      e.preventDefault(); const y = id === 'top' ? 0 : el.getBoundingClientRect().top + scrollY - (id === 'how' ? 0 : 0);
      scrollTo({ top: y, behavior: reduce ? 'auto' : 'smooth' });
    }));
    // reveal
    if ('IntersectionObserver' in window) { const io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } }), { threshold: 0.15 }); $$('.reveal').forEach(el => io.observe(el)); }
    else $$('.reveal').forEach(el => el.classList.add('in'));
    // swatches
    const lum = h => { const n = parseInt(h.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255; return (0.299 * r + 0.587 * g + 0.114 * b) / 255; };
    const setAccent = (hex, save) => {
      const n = parseInt(hex.slice(1), 16);
      root.style.setProperty('--fil', hex); root.style.setProperty('--fil-rgb', (n >> 16) + ', ' + ((n >> 8) & 255) + ', ' + (n & 255)); root.style.setProperty('--fil-ink', lum(hex) > 0.55 ? '#10190f' : '#08140f');
      $$('.sw button').forEach(b => b.setAttribute('aria-pressed', b.dataset.c === hex)); if (W) W.setAccent(hex);
      document.dispatchEvent(new CustomEvent('rf-accent', { detail: hex }));
      if (save) { try { localStorage.setItem('rf-fil', hex); } catch (e) { /* ignore */ } }
    };
    $$('.sw button').forEach(b => b.addEventListener('click', () => setAccent(b.dataset.c, true)));
    try { const s = localStorage.getItem('rf-fil'); if (s && /^#[0-9a-f]{6}$/i.test(s)) setAccent(s, false); } catch (e) { /* ignore */ }
    // form
    const drop = $('#drop'), input = $('#photos'), thumbs = $('#thumbs'), note = $('#formNote');
    const showFiles = files => { thumbs.textContent = ''; Array.from(files || []).slice(0, 3).forEach(f => { if (!/^image\//.test(f.type)) return; const im = document.createElement('img'); im.alt = 'Selected photo'; im.src = URL.createObjectURL(f); thumbs.appendChild(im); }); };
    input.addEventListener('change', () => showFiles(input.files));
    ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
    ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
    drop.addEventListener('drop', e => {
      const f = e.dataTransfer && e.dataTransfer.files; if (!f) return;
      try { input.files = f; } catch (err) { /* older browsers: preview only */ }
      showFiles(f);
    });
    // the design server: clarifying questions, AI design, sizes, downloads; the finished part goes onto the 3D stage
    backend = initBackend({ onModel: (W && state) ? async (buf) => { if (buf) await W.showResult(buf); else W.clearResult(); state.resKey++; } : null });
    const make = $('#exMake'), makeNote = $('#exMakeNote');
    if (make) {
      if (!backend.makeTemplate) { make.hidden = true; }
      else make.addEventListener('click', () => {
        const e = EX[state.sel];
        makeNote.textContent = 'Building your ' + e.name.toLowerCase() + '. It will appear in the request form below.';
        backend.makeTemplate(e.id).then(() => { makeNote.textContent = ''; });
        const rep = document.getElementById('repair'); scrollTo({ top: rep.getBoundingClientRect().top + scrollY, behavior: reduce ? 'auto' : 'smooth' });
      });
    }
    // magnetic buttons
    if (matchMedia('(hover: hover)').matches && !reduce) $$('.btn').forEach(b => {
      b.addEventListener('pointermove', e => { const r = b.getBoundingClientRect(); b.style.translate = ((e.clientX - r.left - r.width / 2) * 0.12) + 'px ' + ((e.clientY - r.top - r.height / 2) * 0.2) + 'px'; });
      b.addEventListener('pointerleave', () => { b.style.translate = ''; });
    });
  }
  wireBasics();

  // problem statement words
  const stEl = $('#statement'), words = (stEl.textContent || '').trim().split(/\s+/);
  stEl.textContent = ''; const wEls = words.map(w => { const s = document.createElement('span'); s.className = 'w'; s.textContent = w + ' '; stEl.appendChild(s); return s; });
  function wordsUpdate() {
    const r = stEl.getBoundingClientRect(); if (r.bottom < -50 || r.top > vh) return;
    const p = clamp((vh * 0.82 - r.top) / (r.height + vh * 0.28));
    wEls.forEach((s, i) => { const k = clamp((p * 1.25 - i / wEls.length) * 6); s.style.opacity = (0.2 + 0.8 * k).toFixed(2); });
  }
  // nav active
  const navA = $$('.nav-links a');
  function navUpdate() {
    const y = scrollY + vh * 0.4; const order = ['problem', 'how', 'ex']; let cur = -1;
    order.forEach((k, i) => { if (y >= secs[k].top) cur = i; }); if (y >= secs.repair.top) cur = -1;
    navA.forEach((a, i) => a.classList.toggle('on', i === cur));
  }
  // rail clicks
  railBtns.forEach((b, i) => b.addEventListener('click', () => { const run = secs.how.h - vh; scrollTo({ top: secs.how.top + run * (i / 6) + 4, behavior: reduce ? 'auto' : 'smooth' }); }));

  /* ---------- input: pointer parallax, drag-to-turn, cursor ---------- */
  const cur = $('#cur'); let cx = -100, cy = -100, cxs = -100, cys = -100, dragging = false, lastX = 0;
  const interactive = t => t && t.closest && t.closest('a,button,input,textarea,select,label,.glass,.how-rail,.nav,.ex-list');
  addEventListener('pointermove', e => {
    state.px = (e.clientX / vw - 0.5) * 2; state.py = (e.clientY / vh - 0.5) * 2; cx = e.clientX; cy = e.clientY; cur.classList.add('show');
    const zone = canvasA > 0.5 && !interactive(e.target) && e.target !== document.documentElement;
    cur.classList.toggle('big', zone || dragging);
    if (dragging) { const dx = e.clientX - lastX; lastX = e.clientX; state.userVel = dx * 0.0035; state.userRot += dx * 0.0085; }
  }, { passive: true });
  addEventListener('pointerdown', e => { if (e.pointerType === 'touch' || e.button !== 0 || interactive(e.target) || canvasA < 0.5) return; dragging = true; lastX = e.clientX; });
  addEventListener('pointerup', () => { dragging = false; });
  addEventListener('pointerleave', () => { cur.classList.remove('show'); });

  /* ---------- thumbnails, then go ---------- */
  setLd(78, 'Developing example photos');
  measure();
  let thumbs = [];
  try { thumbs = makeThumbs(); } catch (err) { console.error('thumbs', err); }
  buildExamples(thumbs);
  setLd(94, 'Warming up the printer');
  try { // compile every shader variant up front so the first scroll into a stage never hitches
    const vis = [], fc = [];
    W.scene.traverse(o => { vis.push(o.visible); fc.push(o.frustumCulled); o.visible = true; o.frustumCulled = false; });
    W.renderer.render(W.scene, W.camera);
    let i = 0; W.scene.traverse(o => { o.visible = vis[i]; o.frustumCulled = fc[i]; i++; });
  } catch (err) { console.warn('warm', err); }
  if (document.fonts && document.fonts.ready) { try { await document.fonts.ready; } catch (e) { /* ignore */ } }
  measure();
  addEventListener('resize', () => { measure(); });
  addEventListener('load', measure);

  /* ---------- loop ---------- */
  let last = performance.now(), frames = 0, slow = 0, firstFrame = true;
  function frame(now) {
    requestAnimationFrame(frame);
    const dt = Math.min(0.05, Math.max(0.001, (now - last) / 1000)); last = now; state.time += dt;
    state.T = toT(scrollY); state.Ts += (state.T - state.Ts) * (1 - Math.exp(-dt * (reduce ? 30 : 6.5)));
    const T = state.Ts;
    state.pxs += (state.px - state.pxs) * (1 - Math.exp(-dt * 4)); state.pys += (state.py - state.pys) * (1 - Math.exp(-dt * 4));
    cxs += (cx - cxs) * (1 - Math.exp(-dt * 16)); cys += (cy - cys) * (1 - Math.exp(-dt * 16)); cur.style.transform = 'translate3d(' + cxs + 'px,' + cys + 'px,0)';
    let target = T < 9.4 ? 1 : T < 9.9 ? 1 - sm((T - 9.4) / 0.5) : T < 11.3 ? 0 : T < 11.8 ? sm((T - 11.3) / 0.5) : 1;
    if (isMobile()) target *= 1 - 0.8 * sm(clamp((T - 0.35) / 0.4)) * (1 - sm(clamp((T - 1.4) / 0.5)));
    canvasA = target; glCanvas.style.opacity = target.toFixed(3); glCanvas.style.visibility = target < 0.01 ? 'hidden' : 'visible';

    const ui = updateHowUI(T);
    wordsUpdate(); navUpdate();
    if (target >= 0.01) {
      choreograph(T, dt);
      const p = poseAt(T);
      W.setCamera({ az: p.az + state.pxs * 4, el: p.el - state.pys * 2, dist: p.dist, tx: p.tx, ty: p.ty, tz: 0, sx: p.sx, sy: p.sy });
      W.renderer.toneMappingExposure += (p.exp - W.renderer.toneMappingExposure) * (1 - Math.exp(-dt * 4));
      // dust
      const dp = W.dpos, dv = W.dvel; for (let i = 0; i < dv.length; i++) { dp[i * 3 + 1] += dv[i] * dt; if (dp[i * 3 + 1] > 4.4) dp[i * 3 + 1] = 0; dp[i * 3] += Math.sin(state.time * 0.3 + i) * 0.0008; }
      W.dust.geometry.attributes.position.needsUpdate = true;
      overlays(T);
      W.renderer.render(W.scene, W.camera);
      if (state.snapReq) { state.snapReq = false; takePhoto(); }
    } else {
      Object.values(pinEls).forEach(el => el.classList.remove('on'));
    }
    // adaptive resolution
    frames++; if (dt > 0.034) slow++; else slow = Math.max(0, slow - 0.5);
    if (frames > 60 && slow > 40 && W.dprMax.v > 1) { W.dprMax.v = Math.max(1, W.dprMax.v - 0.25); slow = 0; W.resize(vw, vh); }
    if (firstFrame) { firstFrame = false; setLd(100, 'Ready'); setTimeout(finishLoader, 350); }
  }
  requestAnimationFrame(frame);
  window.__rf = { state, W, pres, measure, toT, K: () => K, secs: () => secs };
})();
