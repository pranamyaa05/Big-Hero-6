"""Checks that a piece is something a slicer can print. Hard failures make a job fail; warnings travel with the result."""
from __future__ import annotations
import numpy as np
import trimesh
from manifold3d import Manifold

from .printability import Material, MATERIALS, DEFAULT, overhang_survey, overhang_warnings

MIN_VOLUME_MM3 = 50.0
THIN_WARN_MM = 0.8


def thin_wall_estimate(man: Manifold, tm: trimesh.Trimesh, samples: int = 400, seed: int = 7, thin_mm: float = THIN_WARN_MM) -> tuple[float, float] | None:
    """Wall thickness survey: from random points on the surface, cast a ray inward along the normal and measure how far it
    travels inside the solid. Returns (5th percentile thickness in mm, share of samples thinner than thin_mm).
    Knurls, teeth and Braille dots are thin on purpose and only touch a few samples, so only a large share raises a warning."""
    if len(tm.faces) == 0:
        return None
    rng = np.random.default_rng(seed)
    areas = tm.area_faces
    idx = rng.choice(len(tm.faces), size=min(samples, len(tm.faces)), replace=False, p=areas / areas.sum())
    reach = float(np.max(tm.extents)) * 1.2
    d_all = []
    for i in idx:
        n = tm.face_normals[i]
        origin = tm.triangles_center[i] - n * 0.03
        hits = man.ray_cast(origin.tolist(), (origin - n * reach).tolist())
        for h in hits:
            d = float(h.distance) * reach
            if d > 0.05:
                d_all.append(d)
                break
    if not d_all:
        return None
    d = np.array(d_all)
    return float(np.percentile(d, 5)), float(np.mean(d < thin_mm))


def validate_piece(name: str, man: Manifold, tm: trimesh.Trimesh, bed: tuple[float, float, float], material: Material | None = None) -> dict:
    material = material or MATERIALS[DEFAULT]
    errors: list[str] = []
    warnings: list[str] = []
    watertight = bool(tm.is_watertight and tm.is_winding_consistent)
    if not watertight:
        errors.append("mesh is not watertight")
    vol = float(tm.volume) if watertight else 0.0
    if vol < MIN_VOLUME_MM3:
        errors.append("volume is zero or negative")
    bodies = len(tm.split(only_watertight=False)) if len(tm.faces) < 200000 else 1
    if bodies > 1:
        warnings.append(f"{bodies} separate bodies: the slicer will print them as loose pieces")
    ex = sorted(tm.extents.tolist(), reverse=True)
    bx = sorted(bed, reverse=True)
    # the part may be rotated on the bed, so compare the two footprints loosely: footprint (x,y) must fit the bed and height the z limit
    fits_bed = (tm.extents[0] <= bed[0] and tm.extents[1] <= bed[1] and tm.extents[2] <= bed[2]) or (tm.extents[1] <= bed[0] and tm.extents[0] <= bed[1] and tm.extents[2] <= bed[2])
    if not fits_bed:
        warnings.append(f"size {tm.extents[0]:.0f} x {tm.extents[1]:.0f} x {tm.extents[2]:.0f} mm is larger than the configured print bed "
                        f"{bed[0]:.0f} x {bed[1]:.0f} x {bed[2]:.0f} mm; rotate it or split it")
    survey = thin_wall_estimate(man, tm, thin_mm=material.min_wall) if watertight else None
    thin = survey[0] if survey else None
    if survey and survey[1] > 0.10:
        warnings.append(f"about {survey[1] * 100:.0f}% of the surface sits on walls thinner than {material.min_wall:g} mm: they may not print well in {material.name} with a 0.4 mm nozzle")
    oh = overhang_survey(tm, material) if watertight else None
    if oh:
        warnings += overhang_warnings(oh, material)
    return {
        "name": name, "ok": not errors, "errors": errors, "warnings": warnings, "watertight": watertight,
        "volume_cm3": round(vol / 1000.0, 3), "triangles": int(len(tm.faces)), "bodies": bodies,
        "size_mm": [round(float(x), 2) for x in tm.extents], "min_wall_mm": None if thin is None else round(thin, 2),
        "overhang_pct": None if oh is None else round(oh["overhang_share"] * 100, 1), "material": material.name,
    }
