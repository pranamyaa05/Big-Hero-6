"""Everyday-object parts: handles, extenders, hooks, holders, brackets. Same pattern as the other part files: one build function and one
registered PartSpec each. Every part builds from its defaults and at the edge of every parameter's range (tests/test_parts.py sweeps them)."""
from __future__ import annotations
import math
import numpy as np
from manifold3d import Manifold

from .. import geom as g
from ..spec import PartSpec, ParamSpec, BuildResult
from . import CLEARANCE, register

TAU = math.tau


def axis_cyl(r: float, length: float, axis: str, at=(0.0, 0.0, 0.0), seg: int = 48) -> Manifold:
    """Cylinder of radius r and the given length lying along x, y or z, centred on `at`."""
    c = Manifold.cylinder(length, r, r, seg).translate([0, 0, -length / 2])
    if axis == "x":
        c = c.rotate([0, 90, 0])
    elif axis == "y":
        c = c.rotate([-90, 0, 0])
    return c.translate(list(at))


def half_space_above(z: float, span: float = 1000.0) -> Manifold:
    return g.box(-span, span, -span, span, z, span)


# ------------------------------------------------------------------------------------ door handle adapter
def build_door_handle_adapter(p: dict) -> BuildResult:
    clr = p["clearance"]
    r_i = (p["knob_diameter"] + clr) / 2
    wall = 5.0
    r_o = r_i + wall
    H = p["collar_height"]
    L = p["lever_length"]
    top = 5.0
    collar = g.cyl(r_o, H)
    w1, w2 = 1.7 * r_o, p["lever_width"]
    outline = g.round_corners(g.poly([(0, -w1 / 2), (L, -w2 / 2), (L, w2 / 2), (0, w1 / 2)]), min(w2 / 2 - 0.5, 8))
    arm = g.extrude(outline, p["lever_thickness"], H - p["lever_thickness"])
    body = collar + arm
    body = body - g.cyl(r_i, H - top + 1, -1)
    body = body.rotate([180, 0, 0])                                     # lever flat on the bed, collar standing up with its open end up
    return BuildResult(
        {"door-handle-adapter": body},
        print_notes=["Print as modelled: the lever flat on the bed and the collar standing up with its open end at the top; no supports are needed.",
                     "PETG, 4 walls, 40% infill: the lever turns the knob, so the collar takes the load."],
        fit_notes=[f"Bore {2 * r_i:.1f} mm for a knob {p['knob_diameter']:g} mm across. Measure the widest part of the knob, not the neck, "
                   "and check the collar is tall enough to reach past the knob's widest point."],
        derived={"bore_diameter_mm": 2 * r_i, "overall_length_mm": L + r_o})


register(PartSpec(
    "door-handle-adapter", "Door knob lever adapter",
    "A collar that slips over a round door knob and carries a long lever, so the door opens with a push of the palm or forearm instead of a grip and twist.",
    "Weak grip, arthritis, wheelchair users, hands that are full",
    [ParamSpec("knob_diameter", "Knob diameter", "float", 55.0, 35, 75, "mm", "Measure across the widest part of the round knob."),
     ParamSpec("collar_height", "Collar height", "float", 32.0, 20, 50, "mm", "How far down the knob the collar reaches."),
     ParamSpec("lever_length", "Lever length", "float", 110.0, 70, 160, "mm", "Longer is easier to turn but sticks out further."),
     ParamSpec("lever_width", "Lever width", "float", 24.0, 16, 40, "mm"),
     ParamSpec("lever_thickness", "Lever thickness", "float", 12.0, 8, 20, "mm"),
     CLEARANCE],
    build_door_handle_adapter,
    ["door knob", "door handle", "doorknob", "round knob", "lever handle", "handle adapter", "knob lever", "turn the knob", "open the door"],
    ["grip", "door"]))


# ------------------------------------------------------------------------------------ light switch extender
def build_switch_extender(p: dict) -> BuildResult:
    clr = p["clearance"]
    sw, st = p["toggle_width"] + clr, p["toggle_thickness"] + clr
    wall = 3.0
    depth = p["pocket_depth"]
    H = depth + 4.0
    block = g.rounded_box(-(sw / 2 + wall), sw / 2 + wall, -(st / 2 + wall), st / 2 + wall, 0, H, 1.5)
    L, Wp = p["paddle_length"], p["paddle_width"]
    outline = g.round_corners(g.poly([(0, -(sw / 2 + wall)), (L, -Wp / 2), (L, Wp / 2), (0, sw / 2 + wall)]), 6)
    paddle = g.extrude(outline, 6.0, H - 6.0).rotate([0, 0, 90])        # the lever runs along +y, across the toggle's swing
    body = block + paddle
    body = body - g.box(-sw / 2, sw / 2, -st / 2, st / 2, -1, depth)
    body = body.rotate([180, 0, 0])                                     # paddle flat on the bed, pocket opening upward
    return BuildResult(
        {"switch-extender": body},
        print_notes=["Print as modelled: the paddle flat on the bed and the toggle pocket opening upward; nothing needs supports.",
                     "Fit it by pressing the pocket onto the toggle; it holds by friction, so use PETG or TPU for a snug grip."],
        fit_notes=[f"Pocket {sw:.1f} x {st:.1f} mm, {depth:g} mm deep, for a toggle {p['toggle_width']:g} x {p['toggle_thickness']:g} mm. "
                   "Measure the toggle at its base. This is for toggle switches; a flat rocker plate needs a different part."],
        derived={"pocket_width_mm": sw, "pocket_thickness_mm": st, "paddle_length_mm": L})


register(PartSpec(
    "switch-extender", "Light switch extender",
    "A sleeve that presses onto a toggle switch and a long paddle that gives you something wide to push.",
    "Low reach, weak fingers, children, wheelchair users",
    [ParamSpec("toggle_width", "Toggle width", "float", 12.0, 6, 25, "mm", "The long side of the toggle where it leaves the wall plate."),
     ParamSpec("toggle_thickness", "Toggle thickness", "float", 5.5, 3, 12, "mm", "The short side of the toggle."),
     ParamSpec("pocket_depth", "Pocket depth", "float", 14.0, 8, 24, "mm", "How far down the toggle the sleeve reaches."),
     ParamSpec("paddle_length", "Paddle length", "float", 80.0, 40, 140, "mm"),
     ParamSpec("paddle_width", "Paddle width", "float", 30.0, 18, 55, "mm"),
     CLEARANCE],
    build_switch_extender,
    ["light switch", "switch", "toggle switch", "lamp switch", "switch extender", "reach the switch", "flick", "wall switch", "toggle"],
    ["reach"]))


# ------------------------------------------------------------------------------------ zipper pull
def build_zipper_pull(p: dict) -> BuildResult:
    clr = p["clearance"]
    L, t = p["pull_length"], p["thickness"]
    tab_w, tab_t = p["tab_width"] + clr, p["tab_thickness"] + clr
    border = 3.5
    W = max(p["pull_width"], tab_w + 2 * border)
    outline = g.rrect(L, W, min(W / 2 - 0.5, 9))
    slot_x = -L / 2 + border + tab_t / 2
    slot = g.rrect(tab_t, tab_w, min(tab_t / 2 - 0.05, 0.8)).translate([slot_x, 0])
    finger_x0 = slot_x + tab_t / 2 + border
    finger_x1 = L / 2 - border
    finger = g.rrect(finger_x1 - finger_x0, W - 2 * border, min((W - 2 * border) / 2 - 0.3, 6)).translate([(finger_x0 + finger_x1) / 2, 0])
    shape = outline - slot - finger
    body = g.extrude(shape, t)
    return BuildResult(
        {"zipper-pull": body},
        print_notes=["Print flat; it has no overhangs. Use PETG or TPU, since the slot flexes a little when you thread the tab through."],
        fit_notes=[f"Tab slot {tab_t:.1f} x {tab_w:.1f} mm for a zipper tab {p['tab_width']:g} x {p['tab_thickness']:g} mm. "
                   "Measure the metal tab's width and thickness where the slot will sit."],
        derived={"slot_width_mm": tab_w, "slot_thickness_mm": tab_t, "pull_width_mm": W})


register(PartSpec(
    "zipper-pull", "Zipper pull loop",
    "A big flat loop that threads onto a zipper's tab, so it can be hooked with a finger instead of pinched.",
    "Weak pinch, arthritis, tremor, low dexterity, replacing a broken zipper pull",
    [ParamSpec("tab_width", "Zipper tab width", "float", 8.0, 3, 16, "mm", "Width of the metal tab the loop threads onto."),
     ParamSpec("tab_thickness", "Zipper tab thickness", "float", 2.0, 1, 4, "mm"),
     ParamSpec("pull_length", "Loop length", "float", 50.0, 30, 90, "mm"),
     ParamSpec("pull_width", "Loop width", "float", 20.0, 14, 35, "mm"),
     ParamSpec("thickness", "Thickness", "float", 4.0, 3, 8, "mm"),
     CLEARANCE],
    build_zipper_pull,
    ["zipper", "zip", "zip pull", "zipper pull", "zipper tab", "zip tab", "jacket zip", "pull tab", "broken zipper"],
    ["clothing"]))


# ------------------------------------------------------------------------------------ button hook
def build_button_hook(p: dict) -> BuildResult:
    Lh, Dh = p["handle_length"], p["handle_diameter"]
    R = Dh / 2
    handle = g.capsule(R, Lh).rotate([0, 90, 0])                        # along +x
    wire, loop_w, loop_l = p["wire_thickness"], p["loop_width"], p["loop_length"]
    bar = 3.0
    ow = loop_w + 2 * bar
    outer = g.rrect(loop_l + bar, ow, min(ow / 2 - 0.2, ow * 0.5))
    inner = g.rrect(loop_l - bar, loop_w, min(loop_w / 2 - 0.1, loop_w * 0.5)).translate([-bar / 2 + 0.01, 0])
    ring = g.extrude((outer - inner).translate([(loop_l + bar) / 2, 0]), wire, -wire / 2)
    body = handle + ring.translate([Lh - 2.0, 0, 0])
    body = body ^ half_space_above(-0.8 * R)                            # a flat on the underside so it lies on the bed
    return BuildResult(
        {"button-hook": body},
        print_notes=["Print with the flat side down. The loop is thin, so use PETG and 3 walls; it must not be brittle.",
                     "The loop passes through the buttonhole, hooks the button and pulls it back through."],
        fit_notes=[f"Loop opening {loop_w:g} mm wide. It must be narrower than the buttonhole (usually 10-14 mm) and wider than the button's shank."],
        derived={"overall_length_mm": Lh + loop_l + bar - 2.0})


register(PartSpec(
    "button-hook", "Button hook",
    "A thick handle with a flat loop on the end: push the loop through a buttonhole, catch the button and pull it through.",
    "Arthritis, tremor, one-handed dressing, stiff fingers",
    [ParamSpec("handle_length", "Handle length", "float", 85.0, 60, 140, "mm"),
     ParamSpec("handle_diameter", "Handle diameter", "float", 24.0, 16, 36, "mm", "Bigger is easier to hold with a weak grip."),
     ParamSpec("loop_width", "Loop opening width", "float", 7.0, 4, 12, "mm", "Must pass through the buttonhole."),
     ParamSpec("loop_length", "Loop length", "float", 24.0, 14, 40, "mm"),
     ParamSpec("wire_thickness", "Loop thickness", "float", 2.4, 1.6, 4, "mm")],
    build_button_hook,
    ["button hook", "buttoning", "do up buttons", "shirt buttons", "dressing aid", "fasten buttons", "cuff"],
    ["clothing"]))


# ------------------------------------------------------------------------------------ card holder
def build_card_holder(p: dict) -> BuildResult:
    clr = p["clearance"]
    cw, st = p["card_width"] + clr, p["stack_thickness"] + clr
    wall, floor = p["wall"], 3.0
    pocket = p["pocket_depth"]
    ox, oy = cw + 2 * wall, st + 2 * wall
    H = floor + pocket
    body = g.extrude(g.rrect(ox, oy, 3.0), H)
    body = body - g.extrude(g.rrect(cw, st, 1.0), pocket + 1, floor)
    if p["finger_notch"]:                                               # a half-round bite out of the front wall to get a thumb on the cards
        notch_r = min(cw / 2 - 4, 16)
        body = body - axis_cyl(notch_r, wall + 4, "y", (0, -(oy / 2 - wall / 2), H + notch_r * 0.2), 64)
    return BuildResult(
        {"card-holder": body},
        print_notes=["Print upright with the opening up; no supports are needed."],
        fit_notes=[f"Pocket {cw:.1f} x {st:.1f} mm for cards {p['card_width']:g} mm wide in a stack {p['stack_thickness']:g} mm thick "
                   "(a standard bank card is 85.6 x 54 mm and 0.8 mm thick, so ten cards are about 8 mm)."],
        derived={"pocket_width_mm": cw, "pocket_thickness_mm": st, "height_mm": H})


register(PartSpec(
    "card-holder", "Playing card or card holder",
    "An open-topped tray that stands a stack of cards upright, so no one has to hold them in a fan.",
    "Arthritis, tremor, one-handed play, low grip strength",
    [ParamSpec("card_width", "Card width", "float", 64.0, 40, 110, "mm", "The short side of a playing card is about 64 mm; a bank card is 54 mm."),
     ParamSpec("stack_thickness", "Stack thickness", "float", 12.0, 4, 40, "mm", "How many cards you want it to hold."),
     ParamSpec("pocket_depth", "Pocket depth", "float", 40.0, 25, 80, "mm", "How much of the card is hidden. The rest sticks out to be picked up."),
     ParamSpec("wall", "Wall thickness", "float", 2.4, 1.6, 5, "mm"),
     ParamSpec("finger_notch", "Finger notch", "bool", True, unit="", help="A scoop in the front wall to get a thumb on the cards."),
     CLEARANCE],
    build_card_holder,
    ["card holder", "playing cards", "cards", "card stand", "hold cards", "card game", "bank card", "business card", "deck of cards"],
    ["games"]))


# ------------------------------------------------------------------------------------ pill funnel
def build_pill_funnel(p: dict) -> BuildResult:
    clr = p["clearance"]
    spout_od = p["opening_diameter"] - 2 * clr
    r_s = spout_od / 2
    wall = p["wall"]
    sl, H, D = p["spout_length"], p["funnel_height"], p["funnel_diameter"]
    r_top = D / 2
    r_sh = r_s + 3.0                                                    # a shoulder wider than the opening stops the funnel sliding in
    shoulder = 3.0
    outer = g.cyl(r_s, sl + 0.05) + g.cyl(r_sh, shoulder, sl) + g.loft(g.circle(r_sh), g.circle(r_top), H, sl + shoulder - 0.01)
    r_in = max(r_s - wall, 2.0)
    bore = g.cyl(r_in, sl + shoulder + 0.5, -0.5) + g.loft(g.circle(r_in), g.circle(max(r_top - wall, r_in + 1)), H + 0.02, sl + shoulder - 0.01)
    body = (outer - bore).rotate([180, 0, 0])                           # wide mouth on the bed, spout pointing up: the cone then never overhangs
    return BuildResult(
        {"pill-funnel": body},
        print_notes=["Print as modelled, standing on the wide mouth with the spout pointing up (the way a funnel stands); no supports are needed.",
                     "Use a food-safe filament (PETG) and wash it before use; do not leave medicine in it."],
        fit_notes=[f"Spout {spout_od:.1f} mm across for a bottle opening {p['opening_diameter']:g} mm wide. Measure the inside of the opening, not the outside of the neck."],
        derived={"spout_diameter_mm": spout_od, "overall_height_mm": sl + shoulder + H})


register(PartSpec(
    "pill-funnel", "Pill funnel",
    "A wide funnel with a short spout that sits in a pill bottle's opening, so tablets can be tipped from a hand, a tray or a cutter without spilling.",
    "Tremor, low vision, arthritis, refilling a weekly pill organiser",
    [ParamSpec("opening_diameter", "Bottle opening diameter", "float", 22.0, 8, 60, "mm", "Measure the inside of the opening the pills go into."),
     ParamSpec("funnel_diameter", "Funnel mouth diameter", "float", 70.0, 30, 130, "mm"),
     ParamSpec("funnel_height", "Funnel height", "float", 35.0, 15, 70, "mm"),
     ParamSpec("spout_length", "Spout length", "float", 14.0, 8, 30, "mm"),
     ParamSpec("wall", "Wall thickness", "float", 1.6, 1.2, 3, "mm"),
     CLEARANCE],
    build_pill_funnel,
    ["pill", "pills", "tablets", "pill guide", "pill funnel", "pill bottle", "medicine bottle", "medication", "capsule", "pill organiser", "pill organizer"],
    ["medicine"]))


# ------------------------------------------------------------------------------------ cable clip
def build_cable_clip(p: dict) -> BuildResult:
    clr = p["clearance"]
    r_i = (p["cable_diameter"] + clr) / 2
    wall, bt, w = p["wall"], 3.0, p["clip_width"]
    r_o = r_i + wall
    pw = 2 * r_o + 2 * p["flange"]
    yc = bt + r_o - 0.5
    ring = g.circle(r_o) - g.circle(r_i)
    open_w = r_i * 1.3                                                  # the mouth is narrower than the cable, so it snaps in
    ring = ring - g.rect(open_w, r_o + 2, center=False).translate([-open_w / 2, 0])
    ring = ring.translate([0, yc])
    base = g.rect(pw, bt, center=False).translate([-pw / 2, 0])
    profile = base + ring
    body = g.extrude(profile, w).rotate([90, 0, 0]).translate([0, w / 2, 0])
    if p["screw_hole"]:
        xh = (r_o + pw / 2) / 2
        for sgn in (-1, 1):
            body = body - g.cyl(p["screw_diameter"] / 2, bt + 2, -1).translate([sgn * xh, 0, 0])
    return BuildResult(
        {"cable-clip": body},
        print_notes=["Print flat on its back; the open mouth faces up and expect a thin layer of support inside the ring.",
                     "PETG or TPU keeps the mouth springy so the cable snaps in without cracking the clip."],
        fit_notes=[f"Ring {2 * r_i:.1f} mm inside for a cable {p['cable_diameter']:g} mm thick. Fix it with screws or double-sided tape on the flat base."],
        derived={"ring_inner_diameter_mm": 2 * r_i, "base_width_mm": pw})


register(PartSpec(
    "cable-clip", "Cable clip",
    "A flat base with a C-shaped ring that snaps round a cable and holds it to a desk, wall or bed frame.",
    "Trip hazards, wheelchair users, tidy cables out of reach of pets and walkers",
    [ParamSpec("cable_diameter", "Cable diameter", "float", 6.0, 2, 30, "mm", "Measure the thickest cable that has to fit."),
     ParamSpec("clip_width", "Clip width", "float", 12.0, 6, 30, "mm", "Length of the clip along the cable."),
     ParamSpec("wall", "Ring wall thickness", "float", 2.2, 1.6, 5, "mm"),
     ParamSpec("flange", "Base flange", "float", 8.0, 6, 16, "mm", "Flat base sticking out either side of the ring, for screws or tape."),
     ParamSpec("screw_hole", "Screw holes", "bool", True, unit=""),
     ParamSpec("screw_diameter", "Screw hole diameter", "float", 3.5, 2.5, 5, "mm"),
     CLEARANCE],
    build_cable_clip,
    ["cable", "cable clip", "wire", "cord", "charger cable", "cable management", "tidy cables", "power cord", "usb cable", "trip hazard"],
    ["tidy"]))


# ------------------------------------------------------------------------------------ drawer pull
def build_drawer_pull(p: dict) -> BuildResult:
    sp, proj = p["hole_spacing"], p["projection"]
    r_b = p["grip_diameter"] / 2
    sd = p["screw_diameter"]
    r_p = max(7.0, sd / 2 + 3.0)
    bar_len = sp + 2 * r_p + 4.0
    bar = g.capsule(r_b, bar_len).rotate([0, 90, 0]).translate([-bar_len / 2, 0, proj - r_b])
    posts = [g.cyl(r_p, proj - r_b + 1.0).translate([sgn * sp / 2, 0, 0]) for sgn in (-1, 1)]
    body = g.union([bar] + posts)
    depth = min(proj - 2 * r_b + 6.0, proj - 4.0)
    for sgn in (-1, 1):
        body = body - g.cyl(sd / 2, depth + 1, -1).translate([sgn * sp / 2, 0, 0])
    body = body.rotate([90, 0, 0]) ^ half_space_above(-0.8 * max(r_p, r_b))     # lie on its side with a flat underneath
    return BuildResult(
        {"drawer-pull": body},
        print_notes=["Print on its side with the flat underneath, so the layers run through the posts and the pull does not snap at the screws.",
                     "PETG, 5 walls. Screw from inside the drawer into the blind holes; self-tapping or M4 machine screws both work."],
        fit_notes=[f"Holes {sp:g} mm apart, centre to centre. Measure between the two screw holes already in the drawer front; "
                   "common spacings are 64, 96 and 128 mm."],
        derived={"hole_spacing_mm": sp, "length_mm": bar_len})


register(PartSpec(
    "drawer-pull", "Drawer pull handle",
    "A chunky bar handle on two posts that replaces a small knob or a lost handle on a drawer or cupboard.",
    "Weak grip, arthritis, cupboards that need a pinch to open",
    [ParamSpec("hole_spacing", "Screw hole spacing", "float", 96.0, 32, 192, "mm", "Centre to centre between the two screw holes in the drawer."),
     ParamSpec("grip_diameter", "Bar thickness", "float", 16.0, 10, 26, "mm", "Thicker is easier to hold with a weak grip."),
     ParamSpec("projection", "Projection", "float", 36.0, 26, 60, "mm", "How far the handle stands off the drawer; leave room for fingers behind the bar."),
     ParamSpec("screw_diameter", "Screw hole diameter", "float", 3.6, 3, 6, "mm", "For self-tapping M4 screws use 3.5; for M5, 4.5.")],
    build_drawer_pull,
    ["drawer pull", "drawer handle", "cupboard handle", "cabinet handle", "cabinet knob", "drawer knob", "pull handle", "cupboard", "wardrobe", "open the drawer", "drawer", "cabinet", "kitchen drawer", "new handle", "screw holes", "holes are", "hole spacing", "apart"],
    ["grip", "kitchen"]))
