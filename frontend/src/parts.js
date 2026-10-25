/* Accessibility geometry, modelled in code: the wing-grip bottle cap (plus two rejected candidates)
   and eight assistive parts for the Examples section. Every part is returned centred on x and z,
   resting on y = 0, at a nominal size of about one unit. */
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

const TAU = Math.PI * 2;
const sstep = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

/* ---------- outlines ---------- */
function circleShape(r) { const s = new THREE.Shape(); s.absarc(0, 0, r, 0, TAU, false); return s; }
function circleHole(r, cx = 0, cy = 0) { const p = new THREE.Path(); p.absarc(cx, cy, r, 0, TAU, true); return p; }
function ellipseHole(cx, cy, rx, ry) { const p = new THREE.Path(); p.absellipse(cx, cy, rx, ry, 0, TAU, true); return p; }
function rectHole(w, h) { const p = new THREE.Path(); p.moveTo(-w / 2, -h / 2); p.lineTo(-w / 2, h / 2); p.lineTo(w / 2, h / 2); p.lineTo(w / 2, -h / 2); p.closePath(); return p; }
function roundedRect(w, h, r) {
  const s = new THREE.Shape(), x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.absarc(x + w - r, y + r, r, -Math.PI / 2, 0, false);
  s.lineTo(x + w, y + h - r); s.absarc(x + w - r, y + h - r, r, 0, Math.PI / 2, false);
  s.lineTo(x + r, y + h); s.absarc(x + r, y + h - r, r, Math.PI / 2, Math.PI, false);
  s.lineTo(x, y + r); s.absarc(x + r, y + r, r, Math.PI, Math.PI * 1.5, false);
  return s;
}
function polarPoints(rFn, n) { const pts = []; for (let i = 0; i < n; i++) { const a = (i / n) * TAU, r = rFn(a); pts.push(new THREE.Vector2(Math.cos(a) * r, Math.sin(a) * r)); } return pts; }
const polarShape = (rFn, n = 256) => new THREE.Shape(polarPoints(rFn, n));
const polarHole = (rFn, n = 256) => new THREE.Path(polarPoints(rFn, n));
const teeth = (r, depth, count) => a => { const f = ((a / TAU) * count) % 1; return r + depth * (1 - Math.abs(2 * f - 1)); };
function starHole(rOut, rIn, count) {
  const pts = []; for (let i = 0; i < count * 2; i++) { const a = (i * Math.PI) / count, r = i % 2 === 0 ? rOut : rIn; pts.push(new THREE.Vector2(Math.cos(a) * r, Math.sin(a) * r)); }
  return new THREE.Path(pts);
}

/* ---------- solids ---------- */
function up(shape, depth, bevel = 0.014) {
  const g = new THREE.ExtrudeGeometry(shape, { depth, steps: 1, curveSegments: 24, bevelEnabled: bevel > 0, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 2 });
  g.rotateX(-Math.PI / 2); g.translate(0, bevel, 0); return g;
}
const lathe = (points, segments = 128) => new THREE.LatheGeometry(points.map(([r, y]) => new THREE.Vector2(r, y)), segments);
function radial(g, fn) {
  const pos = g.getAttribute('position');
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i), r = Math.hypot(x, z);
    if (r < 1e-5) continue;
    const nr = fn(Math.atan2(z, x), y, r); pos.setX(i, (x * nr) / r); pos.setZ(i, (z * nr) / r);
  }
  pos.needsUpdate = true;
}
function flat(g) { const f = g.index ? g.toNonIndexed() : g; f.computeVertexNormals(); return f; }
function merge(parts) {
  const g = mergeGeometries(parts.map(p => (p.index ? p.toNonIndexed() : p)), false);
  if (!g) throw new Error('could not merge geometry'); return g;
}
function dome(r, x, y, z) { const g = new THREE.SphereGeometry(r, 20, 10, 0, TAU, 0, Math.PI / 2); g.translate(x, y, z); return g; }
function box(w, h, d, x, y, z) { const g = new THREE.BoxGeometry(w, h, d); g.translate(x, y, z); return g; }

/** Centre on x and z, sit on y = 0 and scale to a nominal one-unit size. */
function fit(g) {
  g.computeBoundingBox();
  const b = g.boundingBox, size = b.getSize(new THREE.Vector3());
  g.translate(-(b.min.x + b.max.x) / 2, -b.min.y, -(b.min.z + b.max.z) / 2);
  const k = Math.min(1.05 / Math.max(size.x, size.z), 1.1 / size.y, 2.4);
  g.scale(k, k, k);
  return g;
}

/* ==========================================================================
   Bottle caps (units: metres, same space as the bottle mesh)
   ========================================================================== */

/** Ribbed drum, open underneath. The ribs come from pushing the wall in and out with the angle. */
function drum({ rOut, y0, yTop, lobes, amp, lift = 0 }) {
  const rTop = rOut - 0.0022;
  const pts = [[rOut - 0.0058, y0], [rOut - 0.0008, y0], [rOut, y0 + 0.0012], [rOut, yTop - 0.0042], [rOut - 0.0007, yTop - 0.0022 + lift * 0.2], [rTop - 0.002, yTop + lift], [rTop - 0.012, yTop + lift * 1.1], [0, yTop + lift * 1.2]];
  const g = lathe(pts, 160);
  radial(g, (a, y, r) => {
    if (r > rOut - 0.004 && y > y0 + 0.0016 && y < yTop - 0.003) {
      const f = Math.pow(Math.abs(Math.cos(lobes * a * 0.5)), 0.55);
      return r * ((rOut + amp * (f - 0.5) * 2) / rOut);
    }
    return r;
  });
  g.computeVertexNormals();
  return g.toNonIndexed();
}

/** Two upturned ears joined by a shallow dip: a butterfly grip that a palm or a wrist can turn. Lies along x. */
function wingGeometry(yTop) {
  const s = new THREE.Shape();
  s.moveTo(-0.021, 0); s.lineTo(0.021, 0); s.lineTo(0.021, 0.004);
  s.bezierCurveTo(0.027, 0.007, 0.0385, 0.009, 0.0405, 0.0172);
  s.bezierCurveTo(0.0415, 0.0215, 0.0375, 0.0232, 0.0335, 0.0222);
  s.bezierCurveTo(0.025, 0.0195, 0.014, 0.0128, 0, 0.0128);
  s.bezierCurveTo(-0.014, 0.0128, -0.025, 0.0195, -0.0335, 0.0222);
  s.bezierCurveTo(-0.0375, 0.0232, -0.0415, 0.0215, -0.0405, 0.0172);
  s.bezierCurveTo(-0.0385, 0.009, -0.027, 0.007, -0.021, 0.004);
  s.closePath();
  const d = 0.0085, b = 0.001;
  const g = new THREE.ExtrudeGeometry(s, { depth: d, steps: 1, curveSegments: 18, bevelEnabled: true, bevelThickness: b, bevelSize: b, bevelSegments: 2 });
  g.translate(0, yTop, -d / 2);
  return g;
}

/**
 * kind 'wing' is the design that gets printed (wide ribbed drum with two grip wings).
 * 'grip' and 'ring' are the two candidates the AI rejects: a tall chunky knurled cap and a ring-pull cap.
 */
export function capGeometry(kind, y0, y1) {
  const yTop = y1 - 0.0232;
  if (kind === 'grip') return drum({ rOut: 0.0347, y0, yTop: y1 - 0.001, lobes: 14, amp: 0.0021, lift: 0.0032 });
  if (kind === 'ring') {
    const base = drum({ rOut: 0.0326, y0, yTop, lobes: 36, amp: 0.0007 });
    const ring = new THREE.TorusGeometry(0.0098, 0.0028, 12, 36); ring.translate(0, yTop + 0.0112, 0);
    return merge([base, ring]);
  }
  return merge([drum({ rOut: 0.0332, y0, yTop, lobes: 24, amp: 0.0012 }), wingGeometry(yTop)]);
}

/* ==========================================================================
   The eight assistive parts (nominal one-unit size)
   ========================================================================== */

// Weak legs: flared foot with grip ribs, a beaded lip and a deep socket for the cane
function caneTip() {
  const pts = [[0.001, 0], [0.43, 0], [0.455, 0.025], [0.455, 0.06]];
  const n = 60;
  for (let i = 1; i <= n; i++) { const k = i / n; pts.push([0.455 - 0.2 * (k * k * (3 - 2 * k)), 0.06 + 0.56 * k]); }
  pts.push([0.3, 0.645], [0.3, 0.71], [0.27, 0.745], [0.2, 0.745], [0.2, 0.24], [0.001, 0.24]);
  const g = lathe(pts, 192);
  radial(g, (a, y, r) => {
    if (r < 0.24 || y < 0.06 || y > 0.62) return r;
    const rib = sstep(0.55, 0.9, 0.5 + 0.5 * Math.cos(a * 22)), fade = sstep(0.07, 0.16, y) * (1 - sstep(0.5, 0.6, y));
    return r * (1 + 0.07 * rib * fade);
  });
  return fit(flat(g));
}

// Tremor and limited dexterity: contoured barrel, three finger dimples, ridges, collar, pen bore
function penGrip() {
  const pts = [[0.07, 0], [0.19, 0], [0.2, 0.02], [0.2, 0.045], [0.17, 0.07]];
  const n = 90;
  for (let i = 0; i <= n; i++) { const k = i / n; pts.push([0.125 + 0.06 * Math.pow(Math.sin(Math.PI * k), 0.9), 0.07 + 0.71 * k]); }
  pts.push([0.15, 0.8], [0.15, 0.84], [0.12, 0.86], [0.07, 0.86], [0.07, 0]);
  const g = lathe(pts, 144);
  radial(g, (a, y, r) => {
    if (r < 0.1) return r;
    let d = 0;
    for (const a0 of [0, TAU / 3, (2 * TAU) / 3]) { const da = Math.atan2(Math.sin(a - a0), Math.cos(a - a0)); d -= 0.03 * Math.exp(-(da * da) / 0.18) * Math.exp(-(((y - 0.42) / 0.12) ** 2)); }
    if (y > 0.1 && y < 0.26) d += 0.012 * Math.max(0, Math.sin((y - 0.1) * 120));
    if (y > 0.6 && y < 0.76) d += 0.012 * Math.max(0, Math.sin((y - 0.6) * 120));
    return r + d;
  });
  return fit(flat(g));
}

// Blind and low vision: stepped tag with a reinforced eyelet and real Braille cells spelling SALT
function brailleTag() {
  const plate = roundedRect(0.98, 0.52, 0.11); plate.holes.push(circleHole(0.045, -0.39, 0));
  const baseTop = 0.064;
  const eye = circleShape(0.095); eye.holes.push(circleHole(0.045));
  const eyeG = up(eye, 0.018, 0.006); eyeG.translate(-0.39, baseTop - 0.006, 0);
  const panelG = up(roundedRect(0.78, 0.4, 0.07), 0.014, 0.006); panelG.translate(0.07, baseTop - 0.006, 0);
  const panelTop = baseTop + 0.02;
  const pieces = [up(plate, 0.04, 0.012), eyeG, panelG];
  const cells = [[-0.2, [[0, 1], [0, 2], [1, 0]]], [-0.03, [[0, 0]]], [0.14, [[0, 0], [0, 1], [0, 2]]], [0.31, [[0, 1], [0, 2], [1, 0], [1, 1]]]];
  for (const [cx, dots] of cells) for (const [c, r] of dots) pieces.push(dome(0.036, cx + (c - 0.5) * 0.09, panelTop - 0.004, (r - 1) * 0.09));
  return fit(merge(pieces));
}

// Weak hands and arthritis: scalloped ring, two tiers, serrated bore and a ring of studs
function jarGrip() {
  const lobes = 14, bore = teeth(0.3, 0.018, 56);
  const outer = polarShape(a => 0.5 + 0.032 * Math.cos(a * lobes), 336); outer.holes.push(polarHole(bore, 448));
  const baseTop = 0.19 + 0.036;
  const tier = polarShape(a => 0.43 + 0.01 * Math.cos(a * lobes), 224); tier.holes.push(polarHole(bore, 448));
  const tierG = up(tier, 0.05, 0.012); tierG.translate(0, baseTop - 0.008, 0);
  const pieces = [up(outer, 0.19, 0.018), tierG];
  for (let i = 0; i < lobes; i++) { const a = (i / lobes) * TAU; pieces.push(dome(0.022, Math.cos(a) * 0.468, baseTop - 0.004, Math.sin(a) * 0.468)); }
  return fit(merge(pieces));
}

// Walkers and frames: scalloped flange, ringed dome and a cross-ribbed tread pad
function walkerGlide() {
  const pts = [[0.001, 0], [0.5, 0], [0.512, 0.03], [0.512, 0.075]];
  const n = 70;
  for (let i = 1; i <= n; i++) { const y = 0.075 + (0.225 * i) / n; pts.push([0.5 * Math.sqrt(Math.max(0, 1 - (y / 0.36) ** 2)), y]); }
  pts.push([0.26, 0.31], [0.2, 0.335], [0.001, 0.335]);
  const g = lathe(pts, 144);
  radial(g, (a, y, r) => {
    if (y < 0.08) return r * (1 + 0.035 * Math.cos(a * 18));
    if (y > 0.09 && y < 0.3) return r - 0.014 * Math.max(0, Math.sin((y - 0.09) * 95));
    return r;
  });
  return fit(merge([flat(g), box(0.32, 0.03, 0.045, 0, 0.345, 0), box(0.045, 0.03, 0.32, 0, 0.345, 0)]));
}

// Weak wrists and arthritis: butterfly wing with finger holes and a fluted boss with a key slot
function keyTurner() {
  const wing = roundedRect(1.0, 0.36, 0.17); wing.holes.push(ellipseHole(-0.3, 0, 0.1, 0.07), ellipseHole(0.3, 0, 0.1, 0.07));
  const boss = polarShape(a => 0.2 + 0.012 * Math.cos(a * 16), 160); boss.holes.push(rectHole(0.14, 0.04));
  const cap = polarShape(a => 0.17 + 0.008 * Math.cos(a * 16), 160); cap.holes.push(rectHole(0.14, 0.04));
  const capG = up(cap, 0.012, 0.008); capG.translate(0, 0.26 + 0.028 - 0.006, 0);
  return fit(merge([up(wing, 0.09, 0.014), up(boss, 0.26, 0.014), capG]));
}

// Blind and low vision: knurled ring, D-shaft bore, pointer, rim bead and raised bumps
function dialMarker() {
  const ring = polarShape(a => 0.5 + 0.012 * Math.cos(a * 36), 288);
  const d = [];
  for (let i = 0; i <= 48; i++) { const a = 0.85 + ((TAU - 1.7) * i) / 48; d.push(new THREE.Vector2(Math.cos(a) * 0.22, Math.sin(a) * 0.22)); }
  ring.holes.push(new THREE.Path(d));
  const top = 0.09 + 0.028;
  const bead = circleShape(0.465); bead.holes.push(circleHole(0.435));
  const beadG = up(bead, 0.012, 0.006); beadG.translate(0, top - 0.004, 0);
  const tri = new THREE.Shape(); tri.moveTo(0.43, 0); tri.lineTo(0.27, 0.06); tri.lineTo(0.27, -0.06); tri.closePath();
  const pointer = up(tri, 0.05, 0.008); pointer.translate(0, top - 0.004, 0);
  const pieces = [up(ring, 0.09, 0.014), beadG, pointer];
  for (let i = 1; i < 12; i++) { const a = (i / 12) * TAU, big = i % 3 === 0; pieces.push(dome(big ? 0.042 : 0.027, Math.cos(a) * 0.35, top - 0.004, Math.sin(a) * 0.35)); }
  return fit(merge(pieces));
}

// Weak arms and grip: splined hub, set-screw boss and a tall ridged paddle with a finger hole
function leverWing() {
  const hub = circleShape(0.23); hub.holes.push(starHole(0.115, 0.085, 8));
  const hubG = up(hub, 0.3, 0.02);
  const s = new THREE.Shape();
  s.moveTo(-0.085, 0.2); s.lineTo(0.085, 0.2); s.lineTo(0.085, 0.42);
  s.bezierCurveTo(0.085, 0.52, 0.29, 0.52, 0.29, 0.7); s.absarc(0, 0.7, 0.29, 0, Math.PI, false);
  s.bezierCurveTo(-0.29, 0.52, -0.085, 0.52, -0.085, 0.42); s.closePath();
  s.holes.push(ellipseHole(0, 0.74, 0.06, 0.1));
  const paddle = new THREE.ExtrudeGeometry(s, { depth: 0.12, steps: 1, curveSegments: 28, bevelEnabled: true, bevelThickness: 0.014, bevelSize: 0.014, bevelSegments: 2 });
  paddle.translate(0, 0, -0.06);
  const screwBoss = new THREE.CylinderGeometry(0.05, 0.05, 0.12, 20); screwBoss.rotateZ(Math.PI / 2); screwBoss.translate(0.25, 0.17, 0);
  const pieces = [hubG, paddle, screwBoss];
  for (const y of [0.52, 0.56, 0.6]) for (const z of [0.08, -0.08]) pieces.push(box(0.3, 0.022, 0.02, 0, y, z));
  return fit(merge(pieces));
}

export const BUILDERS = {
  'cane-tip': caneTip, 'pen-grip': penGrip, 'braille-tag': brailleTag, 'jar-grip': jarGrip,
  'walker-glide': walkerGlide, 'key-turner': keyTurner, 'dial-marker': dialMarker, 'lever-wing': leverWing
};
