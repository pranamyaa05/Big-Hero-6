"""Round parts built by revolving a profile: wing-grip bottle cap, cane tip, chunky pen grip, walker glide."""
from __future__ import annotations
import math
import numpy as np
from manifold3d import Manifold
from .. import geom as g
from ..spec import PartSpec, ParamSpec, BuildResult
from . import CLEARANCE, register

TAU = math.tau


# ------------------------------------------------------------------------------------ wing-grip bottle cap
def _wing_outline(k: float):
    """Butterfly outline (two upturned ears with a shallow dip), in mm, lying along x, base on y = 0. Authored for a 33.2 mm cap; k rescales it."""
    P = lambda x, y: (x * 1000 * k, y * 1000 * k)
    pts = [P(-0.021, 0), P(0.021, 0), P(0.021, 0.004)]
    right = [
        (P(0.021, 0.004), P(0.027, 0.007), P(0.0385, 0.009), P(0.0405, 0.0172)),
        (P(0.0405, 0.0172), P(0.0415, 0.0215), P(0.0375, 0.0232), P(0.0335, 0.0222)),
        (P(0.0335, 0.0222), P(0.025, 0.0195), P(0.014, 0.0128), P(0, 0.0128)),
        (P(0, 0.0128), P(-0.014, 0.0128), P(-0.025, 0.0195), P(-0.0335, 0.0222)),
        (P(-0.0335, 0.0222), P(-0.0375, 0.0232), P(-0.0415, 0.0215), P(-0.0405, 0.0172)),
        (P(-0.0405, 0.0172), P(-0.0385, 0.009), P(-0.027, 0.007), P(-0.021, 0.004)),
    ]
    for a, b, c, d in right:
        pts += g.bezier(a, b, c, d, 18)
    return pts


def build_wing_cap(p: dict) -> BuildResult:
    clr = p["clearance"]
    rI = (p["neck_diameter"] + clr) / 2
    rO = rI + p["wall_thickness"]
    H = p["cap_height"]
    ceil = min(4.8, 0.3 * H)
    lobes, amp = 24, 1.2 * rO / 33.2
    prof = [(rI, 0), (rO - 0.8, 0), (rO, 1.2), (rO, H - 4.2), (rO - 0.7, H - 2.2), (rO - 4.2, H), (0, H), (0, H - ceil), (rI, H - ceil)]
    drum = g.lathe(prof, 192, 0.7)

    def ribs(th, z, r):
        f = np.power(np.abs(np.cos(lobes * th * 0.5)), 0.55)
        ramp = g.smoothstep(1.6, 6.5, z)                      # the ribs grow in gently from the bottom edge: a sudden step would be a ledge to print in mid-air
        k = 1 + ramp * (amp * (f - 0.5) * 2) / rO
        return np.where((r > rO - 4) & (z > 1.6) & (z < H - 3), r * k, r)
    drum = g.radial(drum, ribs)

    k = rO / 33.2 * p["wing_scale"]
    thick = max(6.0, 10.5 * k)
    wing2d = g.poly(_wing_outline(k))
    wing = Manifold.extrude(wing2d, thick).translate([0, 0, -thick / 2])   # outline in x/y, thickness along z
    wing = wing.rotate([90, 0, 0]).translate([0, 0, H - 0.6])              # outline y becomes height, base sits on the drum top
    cap = drum + wing
    span = 2 * 40.5 * k
    return BuildResult(
        {"cap": cap},
        print_notes=["Print with the open (bore) end down on the bed and the wings pointing up.",
                     "Supports or good bridging are needed over the bore ceiling; tree supports work well.",
                     "PETG or PLA is fine; add a thread or a snap lip yourself if the lid has to stay on a threaded neck."],
        fit_notes=[f"Smooth bore {2 * rI:.1f} mm for a {p['neck_diameter']:.1f} mm neck plus {clr:g} mm clearance. There is no thread."],
        derived={"bore_diameter_mm": 2 * rI, "outer_diameter_mm": 2 * rO, "wing_span_mm": span})


register(PartSpec(
    "wing-cap", "Wing-grip bottle cap",
    "A wide ribbed cap with two upturned grip wings that turn with a palm instead of a pinch.",
    "Weak grip, arthritis, limited hand strength",
    [ParamSpec("neck_diameter", "Neck outer diameter", "float", 49.8, 20, 90, "mm", "Outside diameter of the bottle neck the cap sits on."),
     ParamSpec("cap_height", "Cap height", "float", 21.8, 14, 40, "mm"),
     ParamSpec("wall_thickness", "Wall thickness", "float", 8.0, 5, 14, "mm", "Radial thickness of the cap wall."),
     ParamSpec("wing_scale", "Wing size", "float", 1.0, 0.6, 1.4, "x", "Scales the grip wings relative to the cap."),
     CLEARANCE],
    build_wing_cap, ["cap", "bottle cap", "lid", "twist", "unscrew", "water bottle", "smooth cap"], ["grip", "bottle"]))


# ------------------------------------------------------------------------------------ cane tip
def build_cane_tip(p: dict) -> BuildResult:
    notes = []
    clr = p["clearance"]
    rb = (p["cane_diameter"] + clr) / 2
    foot_d = max(p["foot_diameter"], 2 * rb + 18)
    if foot_d > p["foot_diameter"] + 1e-9:
        notes.append(f"Foot diameter raised to {foot_d:.1f} mm so the wall around the cane stays strong.")
    H = p["height"]
    s = (foot_d / 2) / 1.07 / 0.455           # radial scale: the ribs add up to 7 % on top of the 0.455 body radius
    R = 0.455 * s
    bead = max(0.3 * s, rb + 4.5)
    rf = 0.85 * bead                           # flare ends under the bead
    top = H
    n = 60
    pts = [(0, 0), (0.43 * s, 0), (R, 0.034 * H), (R, 0.08 * H)]
    for i in range(1, n + 1):
        k = i / n
        sm = k * k * (3 - 2 * k)
        pts.append((R - (R - rf) * sm, (0.08 + (0.835 - 0.08) * k) * H))
    pts += [(bead, 0.905 * H), (bead, 0.953 * H), (bead - 0.03 * s, top), (rb, top), (rb, 0.322 * H), (0, 0.322 * H)]      # the bead flares out at about 40 degrees, so it prints without support
    body = g.lathe(pts, 192, 0.8)

    def ribs(th, z, r):
        yn = z / H * 0.745
        rib = g.smoothstep(0.55, 0.9, 0.5 + 0.5 * np.cos(th * 22))
        fade = g.smoothstep(0.07, 0.16, yn) * (1 - g.smoothstep(0.5, 0.6, yn))
        on = (r > rb + 3) & (yn > 0.06) & (yn < 0.62)
        return np.where(on, r * (1 + 0.07 * rib * fade), r)
    body = g.radial(body, ribs)
    return BuildResult(
        {"cane-tip": body}, notes=notes,
        print_notes=["Print flared foot down; the bore opens upward, so no supports are needed.",
                     "Use TPU 95A (or any flexible filament) so the ribbed foot grips the floor; PETG is stiffer but works."],
        fit_notes=[f"Socket {2 * rb:.1f} mm wide for a {p['cane_diameter']:.1f} mm cane tube, {H * (1 - 0.322):.0f} mm deep."],
        derived={"bore_diameter_mm": 2 * rb, "foot_diameter_mm": foot_d, "socket_depth_mm": H * (1 - 0.322)})


register(PartSpec(
    "cane-tip", "Cane tip",
    "A flared, ribbed rubber-style foot that grips the floor and fits over the end of a walking cane.",
    "Weak legs, walking support, worn or slippery cane tips",
    [ParamSpec("cane_diameter", "Cane tube outer diameter", "float", 19.4, 8, 40, "mm", "Measure the end of the cane (19 mm is common)."),
     ParamSpec("foot_diameter", "Foot diameter", "float", 45.0, 30, 90, "mm"),
     ParamSpec("height", "Overall height", "float", 35.6, 24, 70, "mm"),
     CLEARANCE],
    build_cane_tip, ["cane", "walking stick", "stick tip", "slip", "slips", "ferrule"], ["mobility"]))


# ------------------------------------------------------------------------------------ chunky pen grip
def _ridge(phase):
    """One ridge per unit of phase (0..1): a long gentle climb and a short drop, so the underside of every ridge leans well under 45 degrees
    from vertical and prints without support (a sine ridge of the same height leans about 50 degrees)."""
    u = np.mod(phase, 1.0)
    rise = 0.75
    return np.where(u < rise, g.smoothstep(0.0, 1.0, u / rise), 1.0 - (u - rise) / (1.0 - rise))


def build_pen_grip(p: dict) -> BuildResult:
    notes = []
    clr = p["clearance"]
    rb = (p["pen_diameter"] + clr) / 2
    grip_d = max(p["grip_diameter"], p["pen_diameter"] + clr + 18)
    if grip_d > p["grip_diameter"] + 1e-9:
        notes.append(f"Grip diameter raised to {grip_d:.1f} mm so the barrel wall stays thick enough.")
    A = (grip_d / 2) / 0.2            # radial units -> mm
    B = p["length"] / 0.86            # axial units -> mm
    n = 90
    pts = [(rb, 0), (0.19 * A, 0), (0.2 * A, 0.02 * B), (0.2 * A, 0.045 * B), (0.17 * A, 0.07 * B)]
    for i in range(n + 1):
        k = i / n
        pts.append(((0.125 + 0.06 * math.sin(math.pi * k) ** 0.9) * A, (0.07 + 0.71 * k) * B))
    pts += [(0.15 * A, 0.83 * B), (0.15 * A, 0.84 * B), (0.12 * A, 0.86 * B), (rb, 0.86 * B)]       # the collar flares out gently: no flat ledge to print in mid-air
    body = g.lathe(pts, 144, 0.8)
    nd = p["dimples"]

    def detail(th, z, r):
        yn = z / B
        d = np.zeros_like(r)
        for i in range(nd):
            a0 = i * TAU / max(nd, 1)
            da = np.arctan2(np.sin(th - a0), np.cos(th - a0))
            d -= 0.03 * A * np.exp(-(da * da) / 0.18) * np.exp(-(((yn - 0.42) / 0.12) ** 2))
        d += np.where((yn > 0.1) & (yn < 0.26), 0.012 * A * _ridge((yn - 0.1) * 120 / TAU), 0)
        d += np.where((yn > 0.6) & (yn < 0.76), 0.012 * A * _ridge((yn - 0.6) * 120 / TAU), 0)
        return np.where(r > rb + 2.5, r + d, r)
    body = g.radial(body, detail)
    return BuildResult(
        {"pen-grip": body}, notes=notes,
        print_notes=["Print standing upright; the pen bore goes straight through, so no supports are needed.",
                     "TPU or PETG both work. Rotate the part 90 degrees if you want the finger dimples facing the bed side you prefer."],
        fit_notes=[f"Bore {2 * rb:.1f} mm for a {p['pen_diameter']:.1f} mm pen barrel. Add a small amount of tape inside for thinner pens."],
        derived={"bore_diameter_mm": 2 * rb, "grip_diameter_mm": grip_d})


register(PartSpec(
    "pen-grip", "Chunky pen grip",
    "A fat, contoured barrel with finger dimples and ridges that slides onto a pen or pencil.",
    "Tremor, limited dexterity, weak pinch",
    [ParamSpec("pen_diameter", "Pen barrel diameter", "float", 9.4, 4, 16, "mm", "Measure the pen or pencil where the grip will sit."),
     ParamSpec("grip_diameter", "Grip diameter", "float", 28.0, 20, 50, "mm"),
     ParamSpec("length", "Grip length", "float", 60.2, 35, 110, "mm"),
     ParamSpec("dimples", "Finger dimples", "int", 3, 0, 5, "", "How many finger dimples around the barrel (0 for a plain barrel)."),
     CLEARANCE],
    build_pen_grip, ["pen", "pencil", "writing", "write", "tremor", "shaky", "handwriting", "stylus", "grip for pen"], ["dexterity", "tremor"]))


# ------------------------------------------------------------------------------------ walker glide
def build_walker_glide(p: dict) -> BuildResult:
    notes = []
    clr = p["clearance"]
    rs = (p["tube_diameter"] + clr) / 2
    depth = p["socket_depth"]
    h_total = max(p["height"], depth + 5)
    if h_total > p["height"] + 1e-9:
        notes.append(f"Height raised to {h_total:.1f} mm to leave a solid ceiling above the socket.")
    flange_d = max(p["flange_diameter"], p["tube_diameter"] + clr + 24)
    if flange_d > p["flange_diameter"] + 1e-9:
        notes.append(f"Flange diameter raised to {flange_d:.1f} mm so the wall around the tube stays strong.")
    s = (flange_d / 2) / (0.512 * 1.035)
    sv = h_total / 0.365
    n = 70
    pts = [(0, 0), (0.5 * s, 0), (0.512 * s, 0.03 * sv), (0.512 * s, 0.075 * sv)]
    for i in range(1, n + 1):
        y = 0.075 + 0.225 * i / n
        pts.append((0.5 * s * math.sqrt(max(0.0, 1 - (y / 0.36) ** 2)), y * sv))
    pts += [(0.26 * s, 0.31 * sv), (0.2 * s, 0.335 * sv), (0, 0.335 * sv)]
    body = g.lathe(pts, 144, 0.8)

    def detail(th, z, r):
        yn = z / sv
        scallop = r * (1 + 0.035 * np.cos(th * 18))
        rings = r - 0.014 * s * np.maximum(0, np.sin((yn - 0.09) * 95))
        out = np.where(yn < 0.08, scallop, np.where((yn > 0.09) & (yn < 0.3), rings, r))
        return out
    body = g.radial(body, detail)
    ribs = g.box(-0.16 * s, 0.16 * s, -0.0225 * s, 0.0225 * s, 0.33 * sv, 0.36 * sv) + g.box(-0.0225 * s, 0.0225 * s, -0.16 * s, 0.16 * s, 0.33 * sv, 0.36 * sv)
    glide = (body + ribs) - g.cyl(rs, depth + 1, -1)
    return BuildResult(
        {"walker-glide": glide}, notes=notes,
        print_notes=["Print as modelled: socket opening down on the bed, ribbed pad up. The socket ceiling is a short bridge (a support under it is optional).",
                     "TPU gives the smooth, quiet glide; PETG also works but is harder."],
        fit_notes=[f"Socket {2 * rs:.1f} mm wide, {depth:.0f} mm deep for a {p['tube_diameter']:.1f} mm tube (22.2 mm is 7/8 inch)."],
        derived={"socket_diameter_mm": 2 * rs, "flange_diameter_mm": flange_d, "height_mm": h_total + 0.03 * sv})


register(PartSpec(
    "walker-glide", "Walker glide",
    "A smooth ringed glide cap with a ribbed pad that fits over the leg of a walker or frame.",
    "Walkers and frames: worn tips that catch on the floor",
    [ParamSpec("tube_diameter", "Walker leg outer diameter", "float", 22.2, 12, 40, "mm", "22.2 mm is 7/8 inch, a common walker tube."),
     ParamSpec("flange_diameter", "Flange diameter", "float", 50.0, 34, 80, "mm"),
     ParamSpec("socket_depth", "Socket depth", "float", 12.0, 6, 30, "mm"),
     ParamSpec("height", "Overall height", "float", 17.0, 12, 40, "mm"),
     CLEARANCE],
    build_walker_glide, ["walker", "frame", "zimmer", "rollator", "glide", "tennis ball", "furniture foot"], ["mobility"]))
