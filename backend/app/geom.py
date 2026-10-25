"""Small geometry toolkit on top of manifold3d. Everything is in millimetres, Z up.
Manifold guarantees that every boolean result is a closed, manifold solid, which is what makes the STL output printable."""
from __future__ import annotations
import math
import numpy as np
import trimesh
from manifold3d import Manifold, CrossSection, JoinType, OpType

SEG = 96          # default circular segments
TAU = math.tau


# ---------------------------------------------------------------- 2D outlines
def _ccw(pts: np.ndarray) -> np.ndarray:
    x, y = pts[:, 0], pts[:, 1]
    area = 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
    return pts if area >= 0 else pts[::-1].copy()


def poly(pts) -> CrossSection:
    """Polygon from (x, y) points in any winding order."""
    return CrossSection([_ccw(np.asarray(pts, dtype=np.float64))])


def circle(r: float, seg: int = SEG) -> CrossSection:
    return CrossSection.circle(r, seg)


def ellipse(rx: float, ry: float, seg: int = SEG) -> CrossSection:
    return CrossSection.circle(1.0, seg).scale([rx, ry])


def rect(w: float, h: float, center: bool = True) -> CrossSection:
    return CrossSection.square([w, h], center=center)


def rrect(w: float, h: float, r: float, seg: int = SEG) -> CrossSection:
    """Rounded rectangle, centred. r is clamped so it always fits."""
    r = max(0.01, min(r, w / 2 - 0.01, h / 2 - 0.01))
    return CrossSection.square([w - 2 * r, h - 2 * r], center=True).offset(r, JoinType.Round, 2.0, seg)


def polar(rfn, n: int = 256) -> CrossSection:
    """Closed outline r = rfn(angle); rfn receives a numpy array of angles."""
    a = np.linspace(0, TAU, n, endpoint=False)
    r = np.asarray(rfn(a), dtype=np.float64)
    return poly(np.c_[r * np.cos(a), r * np.sin(a)])


def star(r_out: float, r_in: float, count: int) -> CrossSection:
    pts = []
    for i in range(count * 2):
        a = i * math.pi / count
        r = r_out if i % 2 == 0 else r_in
        pts.append((r * math.cos(a), r * math.sin(a)))
    return poly(pts)


def spline(r_tip: float, r_root: float, count: int) -> CrossSection:
    """Hole outline for a splined stem: flat-topped teeth so no wall tapers to a sharp edge (those do not print)."""
    pts = []
    per = TAU / count
    for i in range(count):
        a0 = i * per
        for f, r in ((0.00, r_tip), (0.22, r_tip), (0.42, r_root), (0.72, r_root), (0.92, r_tip)):
            pts.append(((r) * math.cos(a0 + f * per), r * math.sin(a0 + f * per)))
    return poly(pts)


def tri_wave(r: float, depth: float, count: int):
    """Sawtooth-ish ridge profile used for serrated bores: r at the tips, r + depth at the roots."""
    def f(a):
        t = ((np.asarray(a) / TAU) * count) % 1.0
        return r + depth * (1 - np.abs(2 * t - 1))
    return f


def bezier(p0, p1, p2, p3, n: int = 14):
    t = np.linspace(0, 1, n)[1:, None]
    p0, p1, p2, p3 = (np.asarray(p, dtype=np.float64) for p in (p0, p1, p2, p3))
    return ((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3).tolist()


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- 3D solids
def extrude(cs: CrossSection, h: float, z0: float = 0.0, twist: float = 0.0, scale: float = 1.0) -> Manifold:
    """Push a 2D shape up along Z. twist (degrees over the height) and scale (top size relative to the bottom) make spiral and tapered grips."""
    divisions = max(1, int(abs(twist) / 5)) if twist else (8 if scale != 1.0 else 0)
    sc = (float(scale), float(scale)) if np.isscalar(scale) else (float(scale[0]), float(scale[1]))
    return Manifold.extrude(cs, h, divisions, float(twist), sc).translate([0, 0, z0])


def cyl(r: float, h: float, z0: float = 0.0, seg: int = SEG) -> Manifold:
    return Manifold.cylinder(h, r, r, seg).translate([0, 0, z0])


def box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> Manifold:
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def dome(r: float, x: float, y: float, z: float, seg: int = 24) -> Manifold:
    """Solid hemisphere sitting on the plane z, centred at (x, y)."""
    s = Manifold.sphere(r, seg) ^ box(-r - 1, r + 1, -r - 1, r + 1, 0, r + 1)
    return s.translate([x, y, z])


def hull(items) -> Manifold:
    """Convex hull of a list of solids: blends shapes into smooth, rounded forms (handles, pebbles, tapers)."""
    return Manifold.batch_hull(list(items))


def tube(r_out: float, r_in: float, h: float, z0: float = 0.0) -> Manifold:
    return cyl(r_out, h, z0) - cyl(r_in, h + 2, z0 - 1)


def torus(R: float, r: float, seg: int = SEG) -> Manifold:
    """Ring lying flat on z = 0 plane's centre: major radius R, tube radius r, axis along Z, centred on z = 0."""
    return Manifold.revolve(circle(r, 32).translate([R, 0]), seg)


def capsule(r: float, length: float, seg: int = 32) -> Manifold:
    """Rounded rod along Z from z = 0 to z = length (length includes both rounded ends)."""
    return hull([Manifold.sphere(r, seg).translate([0, 0, r]), Manifold.sphere(r, seg).translate([0, 0, length - r])])


def rounded_box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float, r: float, seg: int = 20) -> Manifold:
    """Box with all edges rounded by radius r."""
    r = min(r, (x1 - x0) / 2 - 1e-3, (y1 - y0) / 2 - 1e-3, (z1 - z0) / 2 - 1e-3)
    pts = [Manifold.sphere(r, seg).translate([x, y, z]) for x in (x0 + r, x1 - r) for y in (y0 + r, y1 - r) for z in (z0 + r, z1 - r)]
    return hull(pts)


def array_polar(m: Manifold, n: int, sweep: float = 360.0) -> Manifold:
    """n copies of m rotated about the Z axis (sweep 360 spreads them evenly round a full circle)."""
    step = sweep / n if abs(sweep - 360.0) < 1e-6 else sweep / max(n - 1, 1)
    return union([m.rotate([0, 0, step * i]) for i in range(int(n))])


def array_linear(m: Manifold, n: int, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> Manifold:
    return union([m.translate([dx * i, dy * i, dz * i]) for i in range(int(n))])


def round_corners(cs: CrossSection, r: float) -> CrossSection:
    """Round the convex corners of a 2D shape by radius r."""
    return cs.offset(-r, JoinType.Round, 2.0, 48).offset(r, JoinType.Round, 2.0, 48)


def loft(a: CrossSection, b: CrossSection, h: float, z0: float = 0.0) -> Manifold:
    """Blend from shape a at z0 to shape b at z0+h. Works for convex shapes (it is a hull of two thin slabs)."""
    return hull([extrude(a, 0.01, z0), extrude(b, 0.01, z0 + h - 0.01)])


def union(items) -> Manifold:
    items = list(items)
    return items[0] if len(items) == 1 else Manifold.batch_boolean(items, OpType.Add)


def densify(pts, step: float) -> list:
    """Split long polyline edges so a later radial() warp has vertices to move."""
    out = []
    pts = [tuple(p) for p in pts]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        out.append(p)
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        k = int(d // step)
        for j in range(1, k + 1):
            t = j / (k + 1)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def lathe(profile, seg: int = 160, step: float = 0.8) -> Manifold:
    """Revolve a closed (radius, z) profile around the Z axis."""
    pts = densify([(max(0.0, r), z) for r, z in profile], step)
    return Manifold.revolve(poly(pts), seg)


def radial(m: Manifold, fn) -> Manifold:
    """Push the wall in or out with angle and height: fn(theta, z, r) -> new radius (arrays in, array out)."""
    def warp(v):
        v = np.asarray(v, dtype=np.float64)
        x, y, z = v[:, 0], v[:, 1], v[:, 2]
        r = np.hypot(x, y)
        th = np.arctan2(y, x)
        nr = np.asarray(fn(th, z, r), dtype=np.float64)
        k = np.where(r > 1e-9, nr / np.maximum(r, 1e-9), 1.0)
        return np.c_[x * k, y * k, z]
    return m.warp_batch(warp)


def along_y(m: Manifold, x: float = 0.0, z: float = 0.0) -> Manifold:
    """Take something built along +Z and point it along -Y (out of the bottom wall of a band), then place it."""
    return m.rotate([90, 0, 0]).translate([x, 0, z])


# ---------------------------------------------------------------- meshes
def to_trimesh(m: Manifold) -> trimesh.Trimesh:
    mesh = m.to_mesh()
    tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3].astype(np.float64).copy(),
                         np.asarray(mesh.tri_verts).astype(np.int64).copy(), process=True)
    tm.merge_vertices()
    return tm


def sit(tm: trimesh.Trimesh) -> trimesh.Trimesh:
    """Centre on X and Y and rest on z = 0."""
    tm = tm.copy()
    b = tm.bounds
    tm.apply_translation([-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]])
    return tm


def rot_to_bed(m: Manifold, axis: str, deg: float) -> Manifold:
    v = {"x": [deg, 0, 0], "y": [0, deg, 0], "z": [0, 0, deg]}[axis]
    return m.rotate(v)
