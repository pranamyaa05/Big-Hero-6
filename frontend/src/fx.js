/* Shader patches shared by every "repair" mesh: jagged break, scan hologram, wire ghosts, layer-by-layer print */
import * as THREE from 'three';

const COMMON = /* glsl */ `
uniform float uCut, uCutSide, uCutAmp, uScan, uScanOn, uWire, uPrint, uHot, uPrintGlow, uLayer, uLayerF, uGridY, uGridA, uAlpha, uGrade;
uniform vec3 uAccent;
varying vec3 vObj;
float rfH(vec3 p){ p = fract(p*0.3183099+.1); p *= 17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
float rfN(vec3 x){ vec3 i=floor(x), f=fract(x); f=f*f*(3.-2.*f);
  return mix(mix(mix(rfH(i),rfH(i+vec3(1,0,0)),f.x), mix(rfH(i+vec3(0,1,0)),rfH(i+vec3(1,1,0)),f.x),f.y),
             mix(mix(rfH(i+vec3(0,0,1)),rfH(i+vec3(1,0,1)),f.x), mix(rfH(i+vec3(0,1,1)),rfH(i+vec3(1,1,1)),f.x),f.y), f.z); }
float rfFbm(vec3 p){ float a=.5, s=0.; for(int i=0;i<3;i++){ s+=a*rfN(p); p*=2.07; a*=.5; } return s/.875; }
`;

const DISCARD_COLOR = /* glsl */ `
float rfEdge = 0.; float rfBand = 0.; float rfLine = 0.; float rfRim = 0.; float rfHolo = 0.; float rfScanLine = 0.;
{
  float cutN = rfFbm(vObj * vec3(130., 70., 130.));
  float d = vObj.y - (uCut + (cutN - .5) * uCutAmp * 2.);
  if (uCutSide != 0.) { if (d * uCutSide < 0.) discard; rfEdge = 1. - smoothstep(0., 0.0018, abs(d)); }
  if (vObj.y > uPrint) discard;
  rfBand = 1. - smoothstep(0., 0.0035, uPrint - vObj.y);
  rfHolo = max(step(vObj.y, uScan), uWire);
  rfScanLine = (1. - smoothstep(0., 0.0034, abs(vObj.y - uScan))) * uScanOn;
  if (rfHolo > 0.) {
    float ang = atan(vObj.z, vObj.x);
    vec2 g = vec2(vObj.y * uGridY, ang * uGridA);
    vec2 gw = max(fwidth(g), vec2(1e-4));
    vec2 gl = abs(fract(g - .5) - .5) / gw;
    rfLine = 1. - min(min(gl.x, gl.y), 1.);
    rfRim = pow(1. - abs(dot(normalize(vNormal), normalize(vViewPosition))), 2.5);
    if (rfLine + rfRim * .5 + rfEdge * uHot * 2. < .2 && rfScanLine < .05) discard;
  }
}
`;

const DISCARD_DEPTH = /* glsl */ `
{
  float cutN = rfFbm(vObj * vec3(130., 70., 130.));
  float d = vObj.y - (uCut + (cutN - .5) * uCutAmp * 2.);
  if (uCutSide != 0. && d * uCutSide < 0.) discard;
  if (vObj.y > uPrint) discard;
  if (max(step(vObj.y, uScan), uWire) > 0.) discard;
}
`;

export function makeUniforms(accent) {
  return {
    uCut: { value: -1e3 }, uCutSide: { value: 0 }, uCutAmp: { value: 0.0045 },
    uScan: { value: -1e3 }, uScanOn: { value: 0 }, uWire: { value: 0 },
    uPrint: { value: 1e3 }, uHot: { value: 0 }, uPrintGlow: { value: 0 }, uLayer: { value: 0 }, uLayerF: { value: 4200 },
    uGridY: { value: 150 }, uGridA: { value: 6 }, uAlpha: { value: 1 }, uGrade: { value: 0 },
    uAccent: { value: accent }
  };
}

export function patchMaterial(mat, uniforms) {
  mat.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, uniforms);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vObj;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvObj = position;');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\n' + COMMON)
      .replace('#include <clipping_planes_fragment>', '#include <clipping_planes_fragment>\n' + DISCARD_COLOR)
      .replace('#include <map_fragment>', '#include <map_fragment>\n' +
        'if (uGrade > .5) { vec3 gc = diffuseColor.rgb; float lum = dot(gc, vec3(.2126, .7152, .0722)); float red = smoothstep(.12, .45, (gc.r - max(gc.g, gc.b)) / max(gc.r, .02)); vec3 steel = mix(vec3(lum), gc, .16) * vec3(1., 1.02, 1.) * 1.18; diffuseColor.rgb = mix(steel, vec3(.032, .038, .035), red); }\n' +
        'if (!gl_FrontFacing && uCutSide != 0.) diffuseColor.rgb *= .32;\n' +
        'diffuseColor.rgb *= 1. - uLayer * .2 * (.5 + .5 * sin(vObj.y * uLayerF));')
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n' +
        'totalEmissiveRadiance += uAccent * (rfEdge * uHot * 3.2 + rfBand * uPrintGlow * 3.5 + rfScanLine * 2.4);')
      .replace('#include <opaque_fragment>', '#include <opaque_fragment>\n' +
        'if (rfHolo > 0.) { gl_FragColor = vec4(uAccent * (.18 + rfLine * 1.9 + rfRim * 1.4 + rfScanLine * 2. + rfEdge * uHot * 3.) * uAlpha, mix(1., uAlpha, step(.5, uWire))); }');
  };
  mat.customProgramCacheKey = () => 'rfpatch1';
  mat.needsUpdate = true;
  return mat;
}

export function makeDepthMaterial(uniforms) {
  const m = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking });
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, uniforms);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vObj;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvObj = position;');
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\n' + COMMON)
      .replace('#include <clipping_planes_fragment>', '#include <clipping_planes_fragment>\n' + DISCARD_DEPTH);
  };
  m.customProgramCacheKey = () => 'rfdepth1';
  return m;
}

/* ---------- procedural stone for the stage ---------- */
function hash2(x, y) { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); }
function vnoise(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash2(xi, yi), b = hash2(xi + 1, yi), c = hash2(xi, yi + 1), d = hash2(xi + 1, yi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
export function stoneTextures(size = 512) {
  const c1 = document.createElement('canvas'), c2 = document.createElement('canvas');
  c1.width = c1.height = c2.width = c2.height = size;
  const x1 = c1.getContext('2d'), x2 = c2.getContext('2d');
  const i1 = x1.createImageData(size, size), i2 = x2.createImageData(size, size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    let n = 0, a = 0.5, f = 5; // tileable-ish fbm
    for (let o = 0; o < 5; o++) { n += a * vnoise((x / size) * f, (y / size) * f); a *= 0.5; f *= 2; }
    const speck = hash2(x * 0.7, y * 0.9) > 0.985 ? 0.25 : 0;
    const v = Math.min(1, Math.max(0, n * 1.15 + speck - 0.1));
    const k = (y * size + x) * 4;
    const col = 150 + v * 80;
    i1.data[k] = col * 0.78; i1.data[k + 1] = col * 0.9; i1.data[k + 2] = col * 0.82; i1.data[k + 3] = 255; // slightly green stone
    const r = 190 + v * 65;
    i2.data[k] = i2.data[k + 1] = i2.data[k + 2] = r; i2.data[k + 3] = 255;
  }
  x1.putImageData(i1, 0, 0); x2.putImageData(i2, 0, 0);
  const t1 = new THREE.CanvasTexture(c1), t2 = new THREE.CanvasTexture(c2);
  [t1, t2].forEach(t => { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4; });
  t1.colorSpace = THREE.SRGBColorSpace;
  return { color: t1, rough: t2 };
}
