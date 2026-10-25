/* The 3D studio: renderer, lights, stone stage, the real water-bottle (Khronos, CC0), the printed wing-grip cap, a print head, and the accessibility example parts */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { makeUniforms, patchMaterial, makeDepthMaterial, stoneTextures } from './fx.js';
import { capGeometry, BUILDERS } from './parts.js';
import { EX } from './ex.js';
import bottleGlb from '../assets/WaterBottle.glb';

export const S = 5;                    // bottle metres -> world units
const CAP_Y0 = 0.0885, CAP_Y1 = 0.1335; // printed cap spans this height (bottle metres)
const CUT_Y = 0.1005;                   // where the original cap meets the bottle
export const BOTTLE_HALF = 0.13022;
export const CAP_PIECE_Y = 0.1175;       // height of the original cap's centre, bottle metres

const rad = d => d * Math.PI / 180;
const parseGlb = (u8) => new Promise((res, rej) => {
  new GLTFLoader().parse(u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.byteLength), '', res, rej);
});

function buildPrinter(accent) {
  const g = new THREE.Group();
  const metal = new THREE.MeshStandardMaterial({ color: 0x252d2a, metalness: 0.85, roughness: 0.38 });
  const alu = new THREE.MeshStandardMaterial({ color: 0xb4beb9, metalness: 0.95, roughness: 0.26 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x0f1513, roughness: 0.55, metalness: 0.2 });
  const glow = new THREE.MeshStandardMaterial({ color: accent, emissive: accent, emissiveIntensity: 1.2, roughness: 0.4 });
  const pla = new THREE.MeshStandardMaterial({ color: accent, roughness: 0.5 });
  const sh = (m) => { m.castShadow = true; m.receiveShadow = true; return m; };

  const plate = sh(new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.53, 0.07, 72), metal)); plate.position.y = 0.035; g.add(plate);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.011, 10, 96), glow); ring.rotation.x = Math.PI / 2; ring.position.y = 0.071; g.add(ring);
  const post = sh(new THREE.Mesh(new THREE.BoxGeometry(0.17, 1.6, 0.17), metal)); post.position.set(0, 0.8, -0.78); g.add(post);
  const strip = new THREE.Mesh(new THREE.BoxGeometry(0.02, 1.5, 0.02), glow); strip.position.set(0, 0.8, -0.69); g.add(strip);
  const foot = sh(new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.1, 0.5), metal)); foot.position.set(0, 0.05, -0.78); g.add(foot);

  // spool on top of the post (horizontal axis)
  const spool = new THREE.Group(); spool.position.set(0, 1.78, -0.78); g.add(spool);
  const fl = new THREE.CylinderGeometry(0.44, 0.44, 0.03, 48);
  const f1 = sh(new THREE.Mesh(fl, dark)), f2 = sh(new THREE.Mesh(fl, dark)); f1.position.y = -0.1; f2.position.y = 0.1; spool.add(f1, f2);
  const core = sh(new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.2, 32), dark)); spool.add(core);
  const wound = sh(new THREE.Mesh(new THREE.CylinderGeometry(0.37, 0.37, 0.19, 64), pla)); spool.add(wound);
  spool.rotation.z = Math.PI / 2;

  // arm (stretched between post and head every frame)
  const arm = sh(new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.09, 1), alu)); g.add(arm);
  const armGlow = new THREE.Mesh(new THREE.BoxGeometry(0.104, 0.012, 1), glow); armGlow.position.y = 0.046; arm.add(armGlow);

  // head
  const head = new THREE.Group(); g.add(head);
  const body = sh(new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.2, 0.24), dark)); body.position.y = 0.12; head.add(body);
  const fan = sh(new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.12, 0.1), glow)); fan.position.set(0.14, 0.1, 0); head.add(fan);
  const block = sh(new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.06, 0.09), alu)); block.position.y = 0.005; head.add(block);
  const nozzle = sh(new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.05, 0.12, 28), alu)); nozzle.position.y = -0.06; head.add(nozzle);
  const tipMat = new THREE.MeshStandardMaterial({ color: accent, emissive: accent, emissiveIntensity: 4, roughness: 0.3 });
  const tip = new THREE.Mesh(new THREE.SphereGeometry(0.02, 16, 12), tipMat); tip.position.y = -0.125; head.add(tip);
  const light = new THREE.PointLight(accent, 0, 2.4, 2); light.position.y = -0.16; head.add(light);

  const filMat = new THREE.MeshStandardMaterial({ color: accent, roughness: 0.45 });
  const filament = new THREE.Mesh(new THREE.BufferGeometry(), filMat); g.add(filament);

  return { group: g, plate, ring, post, spool, arm, head, tip, tipMat, light, filament, filMat, glow, pla, postTop: new THREE.Vector3(0, 1.78 + 0.44, -0.78), postBase: new THREE.Vector3(0, 0, -0.78) };
}

export async function createWorld(canvas, opts = {}) {
  const accent = new THREE.Color(opts.accent || '#ff6b2c');
  const mobile = !!opts.mobile;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !mobile, alpha: true, powerPreference: 'high-performance' });
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.035).texture;
  scene.environmentIntensity = 0.55;
  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 80);

  /* ---- lights ---- */
  const key = new THREE.DirectionalLight(0xffe3c6, 3.0);
  key.position.set(-3.4, 5.4, 3.6); key.castShadow = true;
  key.shadow.mapSize.set(mobile ? 1024 : 2048, mobile ? 1024 : 2048);
  Object.assign(key.shadow.camera, { left: -3.2, right: 3.2, top: 3.2, bottom: -3.2, near: 1, far: 16 });
  key.shadow.radius = 5; key.shadow.bias = -0.0003; key.shadow.normalBias = 0.02;
  key.target.position.set(0, 0.6, 0);
  scene.add(key, key.target);
  const rim = new THREE.DirectionalLight(0xffffff, 1.4); rim.position.set(3.5, 2.6, -3.2); scene.add(rim);
  rim.color.copy(accent).lerp(new THREE.Color(0xffffff), 0.35);
  const fill = new THREE.DirectionalLight(0x9fd4c0, 0.35); fill.position.set(2.5, 1.2, 4); scene.add(fill);

  /* ---- stage: a stone plinth on a soft-fading studio floor ---- */
  const tex = stoneTextures(mobile ? 256 : 512);
  const R = 2.05, T = 0.5;
  const prof = [[0, 0], [R - 0.1, 0]];
  for (let i = 1; i <= 6; i++) { const a = (i / 6) * Math.PI / 2; prof.push([R - 0.1 + Math.sin(a) * 0.1, -0.1 + Math.cos(a) * 0.1]); }
  prof.push([R, -T], [0, -T]);
  const stageGeo = new THREE.LatheGeometry(prof.map(p => new THREE.Vector2(p[0], p[1])), 128);
  [tex.color, tex.rough].forEach(t => t.repeat.set(1.6, 1.6));
  const stageMat = new THREE.MeshStandardMaterial({ map: tex.color, roughnessMap: tex.rough, roughness: 1, bumpMap: tex.rough, bumpScale: 0.9, color: 0x3b4c44, metalness: 0.0, envMapIntensity: 0.28 });
  const stage = new THREE.Mesh(stageGeo, stageMat); stage.receiveShadow = true; stage.castShadow = true; scene.add(stage);
  const fc = document.createElement('canvas'); fc.width = fc.height = 256; const fx = fc.getContext('2d');
  const fg = fx.createRadialGradient(128, 128, 0, 128, 128, 128); fg.addColorStop(0, '#fff'); fg.addColorStop(0.32, '#fff'); fg.addColorStop(1, '#000'); fx.fillStyle = fg; fx.fillRect(0, 0, 256, 256);
  const floor = new THREE.Mesh(new THREE.CircleGeometry(10, 64), new THREE.MeshStandardMaterial({ color: 0x0c1511, roughness: 0.82, metalness: 0.1, transparent: true, alphaMap: new THREE.CanvasTexture(fc), depthWrite: false }));
  floor.rotation.x = -Math.PI / 2; floor.position.y = -T - 0.002; floor.receiveShadow = true; scene.add(floor);

  /* ---- the real bottle ---- */
  const bg = await parseGlb(bottleGlb);
  let bMesh; bg.scene.traverse(o => { if (o.isMesh && !bMesh) bMesh = o; });
  const bGeo = bMesh.geometry, bBase = bMesh.material;
  const bu = makeUniforms(accent); Object.assign(bu.uCut, { value: CUT_Y }); bu.uCutSide.value = -1; bu.uCutAmp.value = 0; bu.uGridY.value = 150; bu.uGridA.value = 6; bu.uGrade.value = 1;
  const bodyMat = patchMaterial(bBase.clone(), bu); bodyMat.side = THREE.DoubleSide;
  const body = new THREE.Mesh(bGeo, bodyMat); body.castShadow = body.receiveShadow = true; body.customDepthMaterial = makeDepthMaterial(bu);
  const bottle = new THREE.Group(); bottle.add(body); bottle.scale.setScalar(S); bottle.position.y = BOTTLE_HALF * S; scene.add(bottle);

  const cu = makeUniforms(accent); cu.uCut.value = CUT_Y; cu.uCutSide.value = 1; cu.uCutAmp.value = 0; cu.uGridY.value = 400; cu.uGridA.value = 8; cu.uGrade.value = 1;
  const capMat = patchMaterial(bBase.clone(), cu); capMat.side = THREE.DoubleSide;
  const capMesh = new THREE.Mesh(bGeo, capMat); capMesh.castShadow = capMesh.receiveShadow = true; capMesh.customDepthMaterial = makeDepthMaterial(cu);
  capMesh.position.y = -CAP_PIECE_Y;
  const capPiece = new THREE.Group(); capPiece.add(capMesh); capPiece.scale.setScalar(S); capPiece.rotation.order = 'YZX';
  capPiece.rotation.set(0, rad(32), Math.PI / 2 - 0.05); capPiece.position.set(-0.95, 0.0288 * S + 0.004, 0.78); scene.add(capPiece);

  /* ---- the printed replacement cap: a wing-grip cap for weak hands (and the wire candidates the AI weighs) ---- */
  const nu = makeUniforms(accent); nu.uGridY.value = 480; nu.uGridA.value = 8; nu.uLayer.value = 1;
  const newMat = patchMaterial(new THREE.MeshPhysicalMaterial({ color: accent, roughness: 0.42, metalness: 0, clearcoat: 0.22, clearcoatRoughness: 0.55, side: THREE.DoubleSide }), nu);
  const newGeo = capGeometry('wing', CAP_Y0, CAP_Y1);
  const newMesh = new THREE.Mesh(newGeo, newMat); newMesh.castShadow = newMesh.receiveShadow = true; newMesh.customDepthMaterial = makeDepthMaterial(nu);
  const newCap = new THREE.Group(); newCap.add(newMesh); newCap.scale.setScalar(S); scene.add(newCap);

  const ghostDefs = ['grip', 'wing', 'ring'];
  const ghosts = ghostDefs.map((d) => {
    const u = makeUniforms(accent); u.uWire.value = 1; u.uGridY.value = 480; u.uGridA.value = 8; u.uAlpha.value = 0;
    const mat = patchMaterial(new THREE.MeshStandardMaterial({ side: THREE.DoubleSide, transparent: true, depthWrite: false }), u);
    const m = new THREE.Mesh(capGeometry(d, CAP_Y0, CAP_Y1), mat); const grp = new THREE.Group(); grp.add(m); grp.scale.setScalar(S); grp.visible = false; scene.add(grp);
    return { group: grp, u };
  });

  /* ---- print head ---- */
  const printer = buildPrinter(accent); printer.group.visible = false; scene.add(printer.group);

  /* ---- accessibility example parts (modelled in code, printed look) ---- */
  const pu = makeUniforms(accent); pu.uLayer.value = 1; pu.uLayerF.value = 720;
  const partMat = patchMaterial(new THREE.MeshPhysicalMaterial({ color: accent, roughness: 0.42, metalness: 0, clearcoat: 0.22, clearcoatRoughness: 0.55 }), pu);
  const models = EX.map((e) => {
    const geo = BUILDERS[e.id]();
    const mesh = new THREE.Mesh(geo, partMat); mesh.castShadow = mesh.receiveShadow = true;
    const nb = new THREE.Box3().setFromObject(mesh), ns = nb.getSize(new THREE.Vector3());
    const k = 1.9 / Math.max(ns.x, ns.y, ns.z); mesh.scale.setScalar(k);
    const wrap = new THREE.Group(); wrap.add(mesh); wrap.visible = false; scene.add(wrap);
    const box = new THREE.Box3().setFromObject(wrap), size = box.getSize(new THREE.Vector3());
    const w = Math.max(size.x, size.z), h = size.y;
    return { id: e.id, group: wrap, size, box, h, w, ty: h * 0.46 + 0.04, dist: Math.max(6.4, 3.6 * h, 3.4 * w), fit: { cy: h * 0.5, dist: Math.max(2.7 * h, 3.0 * w), el: e.el } };
  });

  /* ---- dust in the light ---- */
  const dustN = mobile ? 140 : 320, dpos = new Float32Array(dustN * 3), dvel = new Float32Array(dustN);
  for (let i = 0; i < dustN; i++) { dpos[i * 3] = (Math.random() - 0.5) * 7; dpos[i * 3 + 1] = Math.random() * 4.2; dpos[i * 3 + 2] = (Math.random() - 0.5) * 6; dvel[i] = 0.02 + Math.random() * 0.05; }
  const dg = new THREE.BufferGeometry(); dg.setAttribute('position', new THREE.BufferAttribute(dpos, 3));
  const sc = document.createElement('canvas'); sc.width = sc.height = 32; const sx = sc.getContext('2d');
  const gr = sx.createRadialGradient(16, 16, 0, 16, 16, 16); gr.addColorStop(0, 'rgba(255,236,210,1)'); gr.addColorStop(1, 'rgba(255,236,210,0)'); sx.fillStyle = gr; sx.fillRect(0, 0, 32, 32);
  const dust = new THREE.Points(dg, new THREE.PointsMaterial({ map: new THREE.CanvasTexture(sc), size: 0.028, transparent: true, opacity: 0.4, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true }));
  scene.add(dust);

  /* ---- measurements read from the real mesh (shown in the digital-twin step) ---- */
  const bb = new THREE.Box3().setFromBufferAttribute(bGeo.attributes.position); const bs = bb.getSize(new THREE.Vector3());
  const measures = { heightMm: Math.round(bs.y * 1000), diaMm: Math.round(bs.x * 1000), neckMm: Math.round(0.0249 * 2 * 1000 * 10) / 10, capMm: Math.round(0.0288 * 2 * 1000 * 10) / 10 };

  const size = { w: 1, h: 1 }, dprMax = { v: Math.min(window.devicePixelRatio || 1, mobile ? 1.5 : 1.75) };
  function resize(w, h) {
    size.w = w; size.h = h; renderer.setPixelRatio(dprMax.v); renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }

  const _v = new THREE.Vector3();
  function project(v3, out) {
    _v.copy(v3).project(camera);
    out.x = (_v.x * 0.5 + 0.5) * size.w; out.y = (-_v.y * 0.5 + 0.5) * size.h; out.z = _v.z; return out;
  }

  function setCamera(p) {
    const az = rad(p.az), el = rad(p.el);
    camera.position.set(p.tx + p.dist * Math.sin(az) * Math.cos(el), p.ty + p.dist * Math.sin(el), p.tz + p.dist * Math.cos(az) * Math.cos(el));
    camera.lookAt(p.tx, p.ty, p.tz);
    camera.setViewOffset(size.w, size.h, (0.5 - p.sx) * size.w, (0.5 - p.sy) * size.h, size.w, size.h);
  }

  function setAccent(hex) {
    accent.set(hex);
    [bu, cu, nu, pu, ...ghosts.map(g => g.u)].forEach(u => u.uAccent.value.copy(accent));
    newMat.color.copy(accent); partMat.color.copy(accent);
    printer.glow.color.copy(accent); printer.glow.emissive.copy(accent); printer.pla.color.copy(accent); printer.tipMat.color.copy(accent); printer.tipMat.emissive.copy(accent); printer.light.color.copy(accent); printer.filMat.color.copy(accent);
    rim.color.copy(accent).lerp(new THREE.Color(0xffffff), 0.35);
  }

  /* arm + filament follow the head each frame */
  const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _m = new THREE.Vector3();
  function updatePrinterRig(printProgress) {
    const P = printer; const headPos = P.head.position;
    _a.set(0, headPos.y + 0.06, -0.78); _b.copy(headPos); _b.y += 0.14;
    P.arm.position.copy(_a).add(_b).multiplyScalar(0.5); P.arm.lookAt(_b); P.arm.scale.z = _a.distanceTo(_b);
    // filament: spool rim -> head
    const p0 = new THREE.Vector3(0.02, 1.78 + 0.38, -0.78 + 0.0), p2 = new THREE.Vector3(headPos.x, headPos.y + 0.24, headPos.z);
    const p1 = new THREE.Vector3((p0.x + p2.x) / 2, Math.max(p0.y, p2.y) + 0.12, (p0.z + p2.z) / 2);
    const curve = new THREE.CatmullRomCurve3([p0, p1, p2]);
    const old = P.filament.geometry; P.filament.geometry = new THREE.TubeGeometry(curve, 18, 0.011, 5, false); old.dispose();
    P.spool.rotation.x = printProgress * 18;
  }

  /* snapshots of each hero object for the example picker */
  function snapshot(groups, fit, w = 360, h = 420) {
    groups = [].concat(groups);
    const rt = new THREE.WebGLRenderTarget(w, h, { samples: 4 });
    const cam = new THREE.PerspectiveCamera(26, w / h, 0.1, 50);
    const hidden = []; scene.traverse(o => { if (o.parent === scene && !groups.includes(o) && o.visible && o !== key && o !== rim && o !== fill && o !== key.target) { hidden.push(o); o.visible = false; } });
    const wasVis = groups.map(g => g.visible); groups.forEach(g => { g.visible = true; });
    const cx = fit.cx || 0, cy = fit.cy, d = fit.dist;
    const el = rad(fit.el == null ? 10 : fit.el); cam.position.set(cx + d * Math.sin(rad(26)) * Math.cos(el), cy + d * Math.sin(el), d * Math.cos(rad(26)) * Math.cos(el)); cam.lookAt(cx, cy, 0);
    renderer.setRenderTarget(rt); renderer.setClearColor(0x000000, 0); renderer.clear(); renderer.render(scene, cam); renderer.setRenderTarget(null);
    const buf = new Uint8Array(w * h * 4); renderer.readRenderTargetPixels(rt, 0, 0, w, h, buf);
    hidden.forEach(o => { o.visible = true; }); groups.forEach((g, i) => { g.visible = wasVis[i]; }); rt.dispose();
    const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'); const im = x.createImageData(w, h);
    for (let yy = 0; yy < h; yy++) { const src = (h - 1 - yy) * w * 4; im.data.set(buf.subarray(src, src + w * 4), yy * w * 4); }
    // premultiplied -> straight is not needed for opaque pixels; soften alpha edge by drawing as-is
    x.putImageData(im, 0, 0);
    return c.toDataURL('image/png');
  }

  /* ---- a part designed by the backend: its GLB (millimetres, Y up) on the stage, in the same printed look ---- */
  let result = null;
  async function showResult(buf) {
    const gltf = await new Promise((res, rej) => new GLTFLoader().parse(buf, '', res, rej));
    const inner = new THREE.Group();
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(o => {
      if (!o.isMesh) return;
      if (!o.geometry.attributes.normal) o.geometry.computeVertexNormals();
      const m = new THREE.Mesh(o.geometry, partMat); m.applyMatrix4(o.matrixWorld); m.castShadow = m.receiveShadow = true; inner.add(m);
    });
    if (!inner.children.length) throw new Error('empty model');
    const b0 = new THREE.Box3().setFromObject(inner), s0 = b0.getSize(new THREE.Vector3()), c0 = b0.getCenter(new THREE.Vector3());
    inner.position.set(-c0.x, -b0.min.y, -c0.z);
    const wrap = new THREE.Group(); wrap.add(inner); wrap.scale.setScalar(1.9 / Math.max(s0.x, s0.y, s0.z, 1e-6));
    if (result) scene.remove(result.group);
    scene.add(wrap); wrap.visible = false;
    const box = new THREE.Box3().setFromObject(wrap), size = box.getSize(new THREE.Vector3());
    const w = Math.max(size.x, size.z), h = size.y;
    result = { group: wrap, h, w, ty: h * 0.46 + 0.04, dist: Math.max(6.2, 4.0 * h, 4.2 * w), el: h < 0.7 * w ? 22 : 10, mm: [s0.x, s0.y, s0.z] };
    return result;
  }
  const getResult = () => result;
  const clearResult = () => { if (result) { scene.remove(result.group); result = null; } };

  return {
    showResult, getResult, clearResult,
    THREE, renderer, scene, camera, size, dprMax, key, rim, fill, stage, accent, measures,
    bottle, body, bu, capPiece, cu, newCap, nu, newMat, ghosts, printer, models, dust, dpos, dvel,
    CAP_Y0, CAP_Y1, CUT_Y, resize, project, setCamera, setAccent, updatePrinterRig, snapshot
  };
}
