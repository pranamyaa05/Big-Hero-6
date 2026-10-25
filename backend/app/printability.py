"""Printability knowledge that does not depend on how a part was made: material profiles and a geometric overhang survey.

The overhang survey answers the question the slicer would: how much of the surface hangs in the air steeper than a printer can bridge,
as the part sits on the bed. It also tries the six face-down orientations and reports whether another one would print with less support."""
from __future__ import annotations
from dataclasses import dataclass
import re

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from scipy import ndimage

OVERHANG_LIMIT_DEG = 45.0        # a surface tilted more than this from vertical, facing down, needs support


@dataclass(frozen=True)
class Material:
    key: str
    name: str
    density: float               # g/cm3
    speed: float                 # mm3 of plastic per second at moderate settings
    min_wall: float              # walls thinner than this (mm) are flagged
    max_overhang_share: float    # share of the surface allowed to hang before support is flagged
    flexible: bool
    rules: str                   # what the designer is told when this material is chosen
    notes: tuple                 # print notes added to every result


MATERIALS: dict[str, Material] = {m.key: m for m in (
    Material("pla", "PLA", 1.24, 7.0, 0.8, 0.10, False,
             "Material: PLA. Stiff and easy to print but it softens near 55 degrees C and is brittle under shock: no use in a dishwasher, a hot car or a hot kettle; keep snap fits short and thick.",
             ("PLA softens near 55 degrees C: keep it away from hot water, cars in sun and radiators.",)),
    Material("petg", "PETG", 1.27, 6.5, 0.8, 0.10, False,
             "Material: PETG. Tough, slightly flexible and water-resistant; good for snap fits and things that get wet. Bridges sag a little, so keep unsupported spans under 20 mm.",
             ("PETG is tough and water-resistant; print slowly with a cooler nozzle to avoid stringing.",)),
    Material("abs", "ABS", 1.04, 6.0, 1.0, 0.10, False,
             "Material: ABS or ASA. Strong and heat-tolerant but warps: avoid long thin flat parts, use rounded corners and keep the footprint small.",
             ("ABS needs an enclosure and a heated bed; large flat parts warp. Use a brim.",)),
    Material("tpu", "TPU", 1.21, 3.0, 1.2, 0.05, True,
             "Material: TPU (flexible). Walls under 1.2 mm tear, bridges and overhangs print badly so avoid them, features smaller than 1.5 mm vanish, and the part will bend: do not rely on it for stiffness; add 0.1 mm to fit clearances because it compresses.",
             ("TPU prints slowly (about 20 to 30 mm/s) with no retraction; dry the filament first.",)),
    Material("nylon", "Nylon", 1.14, 5.0, 1.0, 0.10, False,
             "Material: nylon. Very tough and wear-resistant but absorbs water and warps: dry the filament, keep walls even and corners rounded.",
             ("Nylon absorbs moisture: dry the spool before printing.",)),
)}
ALIASES = {"asa": "abs", "flex": "tpu", "flexible": "tpu", "tpe": "tpu", "pet-g": "petg"}
DEFAULT = "pla"


def profile_for(text: str | None) -> Material:
    """The material named in free text ('PETG please', 'flexible rubber-like'); PLA when nothing recognisable is given."""
    low = (text or "").lower()
    for key in list(MATERIALS) + list(ALIASES):
        if re.search(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])", low):
            return MATERIALS[ALIASES.get(key, key)]
    if "rubber" in low or "soft" in low:
        return MATERIALS["tpu"]
    if "durable" in low or "tough" in low:           # the website's "Durable" choice
        return MATERIALS["petg"]
    return MATERIALS[DEFAULT]


def named(text: str | None) -> bool:
    """True when the text actually names a material (so the profile is a choice, not the default)."""
    low = (text or "").lower()
    return any(re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", low) for k in list(MATERIALS) + list(ALIASES)) or "rubber" in low or "durable" in low or "tough" in low


# ------------------------------------------------------------------------------------ overhang survey
FLAT = 0.985          # |normal z| above this is a flat ceiling (bridging); between the limit and this it is a sloped overhang
BRIDGE_SPAN_MM = {"pla": 25.0, "petg": 18.0, "abs": 22.0, "tpu": 8.0, "nylon": 18.0}      # widest flat ceiling that normally bridges without support; a heuristic, not a guarantee


def _ceiling_clusters(tm: trimesh.Trimesh, flat_idx: np.ndarray, up: np.ndarray) -> list[tuple[float, float, float]]:
    """(area, width, supported share) of each connected patch of flat ceiling faces. Width is the diameter of the biggest circle that fits in the patch,
    which is the distance a bridge has to span. Supported share is the part of the patch's outline that meets a wall running down from it: a bridge is held at two
    opposite edges, a shelf is held at one, so a shelf droops over a much shorter reach than a bridge does."""
    if len(flat_idx) == 0:
        return []
    areas = tm.area_faces
    if len(tm.faces) > 60000 or len(flat_idx) > 20000:
        return [(float(areas[flat_idx].sum()), 1e9, 0.0)]                  # too big to analyse quickly: treat it as one unsupported patch
    inside = np.zeros(len(tm.faces), dtype=bool)
    inside[flat_idx] = True
    adj, edges = tm.face_adjacency, tm.face_adjacency_edges
    both = inside[adj[:, 0]] & inside[adj[:, 1]]
    comps = trimesh.graph.connected_components(adj[both], nodes=flat_idx, min_len=1)
    label = np.full(len(tm.faces), -1)
    for k, comp in enumerate(comps):
        label[np.asarray(comp)] = k
    height = tm.triangles_center @ up
    length = np.linalg.norm(tm.vertices[edges[:, 0]] - tm.vertices[edges[:, 1]], axis=1)
    per = np.zeros(len(comps))
    held = np.zeros(len(comps))
    for side in (0, 1):
        mine, other = adj[:, side], adj[:, 1 - side]
        edge = inside[mine] & ~inside[other]
        for i in np.nonzero(edge)[0]:
            k = label[mine[i]]
            per[k] += length[i]
            if height[other[i]] < height[mine[i]] - 0.2:                   # the neighbour lies below the ceiling: a wall holds this edge up
                held[k] += length[i]
    out = []
    for k, comp in enumerate(comps):
        area = float(areas[np.asarray(comp)].sum())
        p = max(float(per[k]), 1e-6)
        out.append((area, _widest_span(tm, np.asarray(comp), up), float(held[k] / p)))
    return out


def _widest_span(tm: trimesh.Trimesh, faces: np.ndarray, up: np.ndarray) -> float:
    """Diameter (mm) of the largest circle that fits inside a flat patch: rasterise the patch and take its distance transform."""
    helper = np.array([1.0, 0, 0]) if abs(up[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(up, helper)
    u /= np.linalg.norm(u)
    v = np.cross(up, u)
    tri = tm.vertices[tm.faces[faces]]                                   # (n, 3, 3)
    uv = np.stack([tri @ u, tri @ v], axis=-1)                           # (n, 3, 2)
    lo, hi = uv.reshape(-1, 2).min(axis=0), uv.reshape(-1, 2).max(axis=0)
    cell = max(0.25, float(np.max(hi - lo)) / 700.0)
    size = (np.ceil((hi - lo) / cell).astype(int) + 3)
    img = Image.new("L", (int(size[0]), int(size[1])), 0)
    draw = ImageDraw.Draw(img)
    for t in uv:
        draw.polygon([tuple(((pt - lo) / cell + 1).tolist()) for pt in t], fill=1)
    dist = ndimage.distance_transform_edt(np.asarray(img) > 0)
    return float(2.0 * dist.max() * cell)


SHELF_REACH = 0.3          # an unsupported shelf may reach this share of the distance a two-sided bridge may span


def _survey_one(tm: trimesh.Trimesh, up: np.ndarray, span_limit: float) -> tuple[float, float]:
    """(overhang area, area of flat ceilings that are too far from their supports) with `up` pointing away from the bed."""
    normals, areas, centres = tm.face_normals, tm.area_faces, tm.triangles_center
    nz = normals @ up
    floor = float((tm.vertices @ up).min())
    airborne = (centres @ up) > floor + 0.15
    sloped = airborne & (nz < -np.sin(np.radians(OVERHANG_LIMIT_DEG))) & (nz >= -FLAT)
    flat_idx = np.nonzero(airborne & (nz < -FLAT))[0]
    bad_flat = 0.0
    for area, width, held in _ceiling_clusters(tm, flat_idx, up):
        limit = span_limit if held >= 0.5 else span_limit * SHELF_REACH
        if width > limit:
            bad_flat += area
    return float(areas[sloped].sum()) + bad_flat, bad_flat


def overhang_survey(tm: trimesh.Trimesh, material: "Material | None" = None) -> dict:
    """Overhang as modelled (the orientation the STL is delivered in) and for each of the six face-down orientations."""
    if len(tm.faces) == 0:
        return {"overhang_mm2": 0.0, "overhang_share": 0.0, "flat_ceiling_mm2": 0.0, "best": None}
    material = material or MATERIALS[DEFAULT]
    span = BRIDGE_SPAN_MM.get(material.key, 12.0)
    total = float(tm.area_faces.sum()) or 1.0
    options = {}
    for label, up in (("as modelled (+z up)", (0, 0, 1)), ("flipped (-z up)", (0, 0, -1)), ("on its +x side", (1, 0, 0)), ("on its -x side", (-1, 0, 0)),
                      ("on its +y side", (0, 1, 0)), ("on its -y side", (0, -1, 0))):
        options[label] = _survey_one(tm, np.array(up, dtype=float), span)
    cur_over, cur_flat = options["as modelled (+z up)"]
    best_label = min(options, key=lambda k: (options[k][0], k != "as modelled (+z up)"))
    best_over = options[best_label][0]
    return {"overhang_mm2": round(cur_over, 1), "overhang_share": round(cur_over / total, 4), "flat_ceiling_mm2": round(cur_flat, 1),
            "best": {"orientation": best_label, "overhang_mm2": round(best_over, 1), "overhang_share": round(best_over / total, 4)}}


def overhang_warnings(survey: dict, material: Material) -> list[str]:
    """Advisory text. Support is a nuisance, not an error, so these are warnings; the designer is asked to remove them."""
    out = []
    share = survey["overhang_share"]
    if share > material.max_overhang_share and survey["overhang_mm2"] > 150:
        kind = "flat ceilings that span too far to bridge" if survey["flat_ceiling_mm2"] > 0.5 * survey["overhang_mm2"] else "steep overhangs"
        msg = (f"about {share * 100:.0f}% of the surface ({survey['overhang_mm2']:.0f} mm2) is {kind} as modelled, so it will need support material"
               + (" (TPU prints support badly)" if material.flexible else ""))
        best = survey["best"]
        if best and best["orientation"] != "as modelled (+z up)" and best["overhang_mm2"] < 0.6 * survey["overhang_mm2"]:
            msg += f"; printing it {best['orientation']} would cut that to {best['overhang_mm2']:.0f} mm2"
        else:
            msg += "; chamfer or round the underside of the hanging features, or add a flat base, to avoid it"
        out.append(msg)
    return out


STATED = ("pla", "petg", "pet-g", "abs", "asa", "tpu", "tpe", "nylon")


def stated_material(text: str | None) -> str:
    """A material the person wrote inside a free-text description ("print it in PETG"), or "". Only explicit names count, so "soft grip" or
    "my pet" never change the material."""
    low = (text or "").lower()
    for key in STATED:
        if re.search(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])", low):
            return key
    return ""
