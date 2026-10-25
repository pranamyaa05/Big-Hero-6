"""Flat or stepped parts built from outlines: Braille tag, jar grip ring, key turner, tactile dial marker, tap lever wing."""
from __future__ import annotations
import math
import numpy as np
from manifold3d import Manifold
from .. import geom as g
from .. import braille
from ..spec import PartSpec, ParamSpec, BuildResult, ParamError
from . import CLEARANCE, register

TAU = math.tau


# ------------------------------------------------------------------------------------ Braille tag
SIZES = {   # dot spacing inside a cell, dot diameter, cell pitch (centre to centre), dot height
    "standard": dict(spacing=2.5, dia=1.6, pitch=6.2, height=0.8),
    "large": dict(spacing=3.6, dia=2.6, pitch=8.6, height=1.3),
}


def build_braille_tag(p: dict) -> BuildResult:
    text = p["text"]
    if not text:
        raise ParamError("text: enter the word or number to write in Braille")
    try:
        cells = braille.encode(text, p["capital_sign"])
    except braille.BrailleError as e:
        raise ParamError(f"text: {e}")
    sz = SIZES[p["dot_size"]]
    n = len(cells)
    if n > 16:
        raise ParamError(f"text: needs {n} Braille cells (numbers and capitals add a sign cell); the limit is 16 so the tag fits a print bed")
    pitch, sp, dia, hdot = sz["pitch"], sz["spacing"], sz["dia"], sz["height"]
    base_t, panel_t = p["plate_thickness"], 0.9
    margin = 4.5
    panel_len = n * pitch + 2 * margin
    panel_w = 2 * sp + dia + 2 * margin
    eye_r = 6.0 if p["eyelet"] else 0.0
    plate_len = panel_len + (2 * eye_r + 6 if p["eyelet"] else 6)
    plate_w = panel_w + 6
    x_left = -plate_len / 2
    plate = g.rrect(plate_len, plate_w, min(6.0, plate_w / 2 - 1))
    eye_x = x_left + 3 + eye_r
    parts = g.extrude(plate, base_t)
    if p["eyelet"]:
        boss = g.extrude(g.circle(eye_r + 1.8), base_t + panel_t, 0)
        parts = parts + boss
        panel_x0 = eye_x + eye_r + 1.8 + 1.0
    else:
        panel_x0 = x_left + 3
    panel_x1 = plate_len / 2 - 3
    pw = panel_x1 - panel_x0
    panel = g.extrude(g.rrect(pw, panel_w, 3.0), panel_t, base_t - 0.2).translate([(panel_x0 + panel_x1) / 2, 0, 0])
    parts = parts + panel
    if p["eyelet"]:
        parts = parts - g.cyl(2.2, base_t + panel_t + 2, -1).translate([eye_x, 0, 0])
    # dots, centred on the panel
    top = base_t + panel_t - 0.2
    cx0 = (panel_x0 + panel_x1) / 2 - (n - 1) * pitch / 2
    dots = []
    for i, cell in enumerate(cells):
        cx = cx0 + i * pitch
        for d in sorted(cell):
            col, row = braille.dot_position(d)
            dots.append(_flat_dome(dia / 2, hdot, cx + (col - 0.5) * sp, (1 - row) * sp, top - 0.2))
    if dots:
        parts = parts + g.union(dots)
    return BuildResult(
        {"braille-tag": parts},
        notes=[f"'{text}' needs {n} Braille cell(s) in Grade 1 (uncontracted) English Braille."],
        print_notes=["Print flat with the dots facing up; no supports are needed.",
                     "Use a 0.2 mm layer height or finer and slow the top layers so the dots stay round.",
                     "Check the dots by touch before attaching the tag to anything that matters."],
        fit_notes=[f"Dot size '{p['dot_size']}': {dia:g} mm dots, {hdot:g} mm high, {sp:g} mm apart inside a cell, {pitch:g} mm cell pitch. "
                   "'standard' follows common Braille sizing but needs a well tuned printer; 'large' prints reliably."],
        derived={"cells": n, "length_mm": plate_len, "width_mm": plate_w})


def _flat_dome(r: float, h: float, x: float, y: float, z: float) -> Manifold:
    """A rounded dot: hemisphere of radius r squashed to height h."""
    s = Manifold.sphere(r, 20) ^ g.box(-r - 1, r + 1, -r - 1, r + 1, 0, r + 1)
    return s.scale([1, 1, h / r]).translate([x, y, z])


register(PartSpec(
    "braille-tag", "Braille tag",
    "A raised Braille label on a tag with an eyelet, to tie onto jars, boxes, keys or bags.",
    "Blind and low vision",
    [ParamSpec("text", "Text to write in Braille", "text", "SALT", unit="", help="Letters, digits, spaces and . , ; : ! ? - ' ( ) /. Up to 16 Braille cells.", max_length=24),
     ParamSpec("dot_size", "Dot size", "enum", "large", unit="", choices=["standard", "large"], help="'standard' is regulation Braille sizing, 'large' prints more reliably on a normal 0.4 mm nozzle."),
     ParamSpec("capital_sign", "Add capital signs", "bool", False, unit="", help="Put the capital indicator before each capital letter."),
     ParamSpec("eyelet", "Tie-on eyelet", "bool", True, unit=""),
     ParamSpec("plate_thickness", "Plate thickness", "float", 2.4, 1.6, 5, "mm")],
    build_braille_tag, ["braille", "label", "tag", "blind", "low vision", "visually impaired", "tactile label", "spells", "name tag"], ["vision"]))


# ------------------------------------------------------------------------------------ jar grip ring
def build_jar_grip(p: dict) -> BuildResult:
    clr = p["clearance"]
    r_tip = (p["lid_diameter"] + clr) / 2
    depth_t = 2.0
    ring_w = p["ring_width"]
    Ro = r_tip + depth_t + ring_w
    H = p["height"]
    hb, ht = 0.78 * H, 0.22 * H
    lobes = 14
    amp = 0.064 * Ro
    outline = g.polar(lambda a: Ro + amp * np.cos(a * lobes), 360)
    bore = g.polar(g.tri_wave(r_tip, depth_t, 56), 448)
    base = g.extrude(outline - bore, hb)
    tier_r = 0.86 * Ro
    tier = g.extrude(g.polar(lambda a: tier_r + 0.0184 * Ro * np.cos(a * lobes), 240) - bore, ht, hb - 0.4)
    ring = base + tier
    studs = [g.dome(2.2, math.cos(i * TAU / lobes) * 0.936 * Ro, math.sin(i * TAU / lobes) * 0.936 * Ro, hb - 0.4, 16) for i in range(lobes)]
    ring = ring + g.union(studs)
    return BuildResult(
        {"jar-grip-ring": ring},
        print_notes=["Print flat; the bore goes straight through, so no supports are needed.",
                     "TPU 95A gives a ring that bites into the lid; PETG works for a rigid version."],
        fit_notes=[f"Serrated bore: ridge tips {2 * r_tip:.1f} mm across, roots {2 * (r_tip + depth_t):.1f} mm, for a lid about {p['lid_diameter']:.1f} mm. "
                   "Measure the lid at its widest edge, including any lip."],
        derived={"outer_diameter_mm": 2 * (Ro + amp), "bore_tip_diameter_mm": 2 * r_tip})


register(PartSpec(
    "jar-grip", "Jar grip ring",
    "A wide scalloped ring that fits over a jar lid so the whole palm can turn it.",
    "Weak hands, arthritis, jars that are hard to open",
    [ParamSpec("lid_diameter", "Lid diameter", "float", 65.0, 28, 110, "mm", "Measure across the lid's widest edge."),
     ParamSpec("ring_width", "Ring width", "float", 19.8, 10, 40, "mm", "Radial width of the ring around the lid."),
     ParamSpec("height", "Height", "float", 26.0, 14, 45, "mm"),
     CLEARANCE],
    build_jar_grip, ["jar", "jars", "lid", "jam", "pickle", "twist off", "opener", "arthritis", "jar opener"], ["grip", "kitchen"]))


# ------------------------------------------------------------------------------------ key turner
def build_key_turner(p: dict) -> BuildResult:
    clr = p["clearance"]
    L = p["wing_length"]
    sw, st = p["key_width"] + clr, p["key_thickness"] + clr
    wing_w = 0.36 * L
    wing_t = 0.09 * L
    boss_r = max(0.2 * L, sw / 2 + 6.5)
    bh = p["boss_height"]
    cap_t = 0.012 * L
    wing = g.extrude(g.rrect(L, wing_w, 0.17 * L) - g.ellipse(0.1 * L, 0.07 * L).translate([-0.3 * L, 0]) - g.ellipse(0.1 * L, 0.07 * L).translate([0.3 * L, 0]), wing_t)
    boss = g.extrude(g.polar(lambda a: boss_r + 0.06 * boss_r * np.cos(a * 16), 192), bh)
    body = wing + boss
    floor = min(wing_t * 0.5, bh * 0.4)
    slot = g.box(-sw / 2, sw / 2, -st / 2, st / 2, floor, bh + 1)
    body = body - slot
    return BuildResult(
        {"key-turner": body},
        print_notes=["Print flat with the wing down; the key slot opens upward, so no supports are needed.",
                     "Print with at least 4 walls: the key twists inside the slot and puts stress on the boss."],
        fit_notes=[f"Key slot {sw:.1f} x {st:.1f} mm, {bh - floor:.1f} mm deep, for a key bow {p['key_width']:g} x {p['key_thickness']:g} mm. "
                   "Measure the thickest part of the key you want to hold."],
        derived={"slot_width_mm": sw, "slot_thickness_mm": st, "slot_depth_mm": bh - floor, "length_mm": L})


register(PartSpec(
    "key-turner", "Key turner",
    "A butterfly wing with a key slot: two big finger holes give leverage for turning small keys.",
    "Weak wrists and fingers, arthritis, keys that need a pinch and twist",
    [ParamSpec("key_width", "Key width", "float", 8.0, 4, 18, "mm", "Width of the key bow or head."),
     ParamSpec("key_thickness", "Key thickness", "float", 2.0, 1, 6, "mm"),
     ParamSpec("wing_length", "Wing length", "float", 60.0, 45, 110, "mm"),
     ParamSpec("boss_height", "Boss height", "float", 16.0, 9, 32, "mm", "Taller bosses hold more of the key."),
     CLEARANCE],
    build_key_turner, ["key", "keys", "door key", "lock", "turn key", "deadbolt"], ["grip"]))


# ------------------------------------------------------------------------------------ dial marker
def build_dial_marker(p: dict) -> BuildResult:
    notes = []
    clr = p["clearance"]
    rb = (p["knob_diameter"] + clr) / 2
    outer = max(p["outer_diameter"], 2 * rb + 20)
    if outer > p["outer_diameter"] + 1e-9:
        notes.append(f"Outer diameter raised to {outer:.1f} mm so the ring stays strong around the knob.")
    s = (outer / 2) / 0.506
    rh = p["ring_height"]
    kn = lambda a: 0.5 * s + 0.012 * s * np.cos(a * 36)
    ring = g.extrude(g.polar(kn, 288), rh)
    if p["d_flat"]:
        flat_x = 0.66 * rb
        # D-shaped bore: circle with the +x side cut flat
        bore = g.circle(rb) ^ g.poly([(-rb - 1, -rb - 1), (flat_x, -rb - 1), (flat_x, rb + 1), (-rb - 1, rb + 1)])
    else:
        bore = g.circle(rb)
    ring = ring - Manifold.extrude(bore, rh + 2).translate([0, 0, -1])
    top = rh
    bead_h = 0.012 * s * 1.6
    bead = g.extrude(g.circle(0.465 * s) - g.circle(0.435 * s), bead_h, top - 0.3)
    pointer = g.extrude(g.poly([(0.43 * s, 0), (0.27 * s, 0.06 * s), (0.27 * s, -0.06 * s)]), 0.05 * s * 0.9, top - 0.3)
    pieces = [ring, bead, pointer]
    bumps = []
    for i in range(1, 12):
        a = i / 12 * TAU
        big = i % 3 == 0
        bumps.append(g.dome((0.042 if big else 0.027) * s, math.cos(a) * 0.35 * s, math.sin(a) * 0.35 * s, top - 0.3, 20))
    body = g.union(pieces + bumps)
    return BuildResult(
        {"dial-marker": body}, notes=notes,
        print_notes=["Print flat; the bore goes straight through, so no supports are needed.",
                     "The pointer sits on the flat side of the D-shaped bore, so you can feel which way the dial is set."],
        fit_notes=[f"{'D-shaped' if p['d_flat'] else 'Round'} bore {2 * rb:.1f} mm across for a {p['knob_diameter']:.1f} mm knob or shaft. "
                   "Measure the knob you want to mark; add a small shim or a drop of glue to fix it in place."],
        derived={"bore_diameter_mm": 2 * rb, "outer_diameter_mm": outer})


register(PartSpec(
    "dial-marker", "Tactile dial marker",
    "A knurled ring with a raised pointer and bumps, to find a setting on an oven, radio or knob by touch.",
    "Blind and low vision",
    [ParamSpec("knob_diameter", "Knob or shaft diameter", "float", 23.6, 10, 50, "mm", "Measure the knob the ring will sit on."),
     ParamSpec("outer_diameter", "Ring outer diameter", "float", 55.0, 30, 90, "mm"),
     ParamSpec("ring_height", "Ring height", "float", 5.0, 3, 16, "mm"),
     ParamSpec("d_flat", "D-shaped bore", "bool", True, unit="", help="Adds a flat so the ring cannot slip round a D-shaft knob."),
     CLEARANCE],
    build_dial_marker, ["dial", "knob", "oven", "radio", "cooker", "stove", "marker", "tactile", "setting", "thermostat"], ["vision"]))


# ------------------------------------------------------------------------------------ tap lever wing
def build_lever_wing(p: dict) -> BuildResult:
    clr = p["clearance"]
    Htot = p["lever_height"]
    s = Htot / 1.0
    tip_r = (p["stem_diameter"] + clr) / 2
    root_r = 0.74 * tip_r
    hub_r = max(0.23 * s, tip_r + 6.0)
    hub_h = 0.3 * s
    depth = min(p["engage_depth"], hub_h - 2)
    hub = g.extrude(g.circle(hub_r), hub_h)
    # paddle: authored in x/y (y up) then stood up so y becomes Z
    pts = [(-0.085 * s, 0.2 * s), (0.085 * s, 0.2 * s), (0.085 * s, 0.42 * s)]
    c = lambda *a: [(x * s, y * s) for x, y in a]
    pts += g.bezier(*c((0.085, 0.42), (0.085, 0.52), (0.29, 0.52), (0.29, 0.7)), n=16)
    for i in range(1, 49):
        a = i * math.pi / 48
        pts.append((0.29 * s * math.cos(a), (0.7 + 0.29 * math.sin(a)) * s))
    pts += g.bezier(*c((-0.29, 0.7), (-0.29, 0.52), (-0.085, 0.52), (-0.085, 0.42)), n=16)
    paddle2d = g.poly(pts) - g.ellipse(0.06 * s, 0.1 * s).translate([0, 0.74 * s])
    th = 0.12 * s
    paddle = Manifold.extrude(paddle2d, th).translate([0, 0, -th / 2]).rotate([90, 0, 0])
    body = hub + paddle
    for z in (0.52, 0.56, 0.6):
        for sgn in (1, -1):   # ridges stand 0.02 s proud of each paddle face and sink 0.01 s into it
            # a triangular rib (base 0.06 s tall, 0.03 s proud) so its underside leans about 35 degrees and needs no support
            tri = g.poly([(sgn * 0.05 * s, z * s - 0.03 * s), (sgn * 0.08 * s, z * s), (sgn * 0.05 * s, z * s + 0.03 * s)][::sgn])      # counter-clockwise on both sides
            body = body + Manifold.extrude(tri, 0.3 * s).translate([0, 0, -0.15 * s]).rotate([90, 0, 90])
    spline = g.extrude(g.spline(tip_r, root_r, 8), depth + 1, -1)
    notes = []
    if p["set_screw"]:
        z_screw = 0.17 * s
        boss = g.cyl(0.05 * s, 0.12 * s, 0).rotate([0, 90, 0]).translate([0.19 * s, 0, z_screw])
        body = body + boss
        hole = g.cyl(1.65, hub_r + 0.12 * s, 0, 24).rotate([0, 90, 0]).translate([0, 0, z_screw])
        body = body - hole
        notes.append("Set-screw hole is 3.3 mm: tap it with an M4 tap (or use a self-tapping screw) to lock the lever onto the stem.")
    body = body - spline
    return BuildResult(
        {"lever-wing": body}, notes=notes,
        print_notes=["Print upright on the hub with the paddle pointing up; the spline hole opens downward onto the bed (a small bridge). The slicer adds light support under the wing of the paddle, so keep automatic supports on.",
                     "Orient with the paddle's flat face along the X axis for best layer strength across the paddle."],
        fit_notes=[f"Spline hole {2 * tip_r:.1f} mm across the tips, 8 teeth, {depth:.0f} mm deep, for a {p['stem_diameter']:.1f} mm stem. "
                   "Match the tooth count and diameter to your tap or valve stem."],
        derived={"spline_tip_diameter_mm": 2 * tip_r, "hub_diameter_mm": 2 * hub_r, "height_mm": Htot})


register(PartSpec(
    "lever-wing", "Tap lever wing",
    "A tall ridged paddle on a splined hub that turns a round tap or valve with a push of the forearm.",
    "Weak arms and grip, round taps that need a tight twist",
    [ParamSpec("stem_diameter", "Tap stem diameter (spline tips)", "float", 15.0, 8, 28, "mm", "Measure across the stem or spline tips."),
     ParamSpec("lever_height", "Overall height", "float", 70.0, 50, 120, "mm"),
     ParamSpec("engage_depth", "Stem engagement depth", "float", 13.0, 8, 24, "mm"),
     ParamSpec("set_screw", "Add set-screw boss", "bool", True, unit=""),
     CLEARANCE],
    build_lever_wing, ["tap", "faucet", "valve", "lever", "paddle", "round tap", "turn tap", "water tap", "spigot"], ["grip", "kitchen"]))
