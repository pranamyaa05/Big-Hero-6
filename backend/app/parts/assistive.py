"""Assistive aids for specific daily-life barriers: pulling a plug, opening a can, hitting the right key, finding a keyhole,
feeling a button, seeing a step edge, parking a cane, pressing a soap pump. One build function and one PartSpec each."""
from __future__ import annotations
import math
import numpy as np
from manifold3d import Manifold

from .. import geom as g
from ..spec import PartSpec, ParamSpec, BuildResult
from . import CLEARANCE, register
from .household import axis_cyl


# ------------------------------------------------------------------------------------ can tab lifter
def build_can_tab_lifter(p: dict) -> BuildResult:
    L, hole = p["length"], p["finger_hole"]
    ring_r = hole / 2 + 7.0
    bw, bt = p["blade_width"], p["blade_thickness"]
    bar_t = 5.0
    blade_len = 24.0
    bar_w = 14.0
    ring = g.circle(ring_r) - g.circle(hole / 2)
    bar = g.round_corners(g.poly([(0, -bar_w / 2), (L - blade_len, -bar_w * 0.35), (L - blade_len, bar_w * 0.35), (0, bar_w / 2)]), 2.0)
    body = g.extrude(ring, bar_t) + g.extrude(bar, bar_t)
    body = body - g.cyl(hole / 2, bar_t + 2, -1)
    blade = g.extrude(g.round_corners(g.poly([(L - blade_len - 1.0, -bar_w * 0.35), (L - 3.0, -bw / 2), (L - 3.0, bw / 2), (L - blade_len - 1.0, bar_w * 0.35)]), 1.0), bt)
    lip = g.box(L - 3.0, L, -bw / 2 + 0.5, bw / 2 - 0.5, 0, bt + 3.2)
    body = body + blade + lip
    return BuildResult(
        {"can-tab-lifter": body},
        print_notes=[f"Print flat on the bed; no supports. Use PETG with full infill in the blade: it is only {bt:g} mm thick and takes the force of the lift."],
        fit_notes=[f"Blade {bt:g} mm thick, {bw:g} mm wide. The gap under a drinks-can tab is about 2.5 mm, so keep the blade under 2.2 mm. "
                   f"Finger hole {hole:g} mm: measure your index finger at the knuckle and add 2 mm."],
        derived={"blade_thickness_mm": bt, "length_mm": L})


register(PartSpec(
    "can-tab-lifter", "Can tab lifter",
    "A flat lever with a finger ring and a thin hooked blade that slides under a can's pull tab and lifts it with the whole hand, not a pinched fingernail.",
    "Weak pinch, arthritis, long or fragile nails, tremor",
    [ParamSpec("length", "Length", "float", 90.0, 60, 140, "mm", "Longer gives more leverage."),
     ParamSpec("finger_hole", "Finger hole diameter", "float", 20.0, 14, 30, "mm", "Measure the finger at the knuckle and add 2 mm."),
     ParamSpec("blade_width", "Blade width", "float", 12.0, 8, 18, "mm"),
     ParamSpec("blade_thickness", "Blade thickness", "float", 1.8, 1.2, 2.2, "mm", "Must be thinner than the gap under the tab (about 2.5 mm).")],
    build_can_tab_lifter,
    ["can tab", "pull tab", "ring pull", "soda can", "drinks can", "beer can", "tin can tab", "open a can", "can opener", "pop the tab", "tab lifter"],
    ["kitchen"]))


# ------------------------------------------------------------------------------------ plug puller
def build_plug_puller(p: dict) -> BuildResult:
    clr = p["clearance"]
    pw, ph = p["plug_width"] + clr, p["plug_height"] + clr
    wall, depth, wing = p["wall"], p["grip_depth"], p["wing_length"]
    plate_t = 6.0
    sleeve = g.extrude(g.rrect(pw + 2 * wall, ph + 2 * wall, 4.0), depth + plate_t)
    body = sleeve - g.extrude(g.rrect(pw, ph, 2.0), depth + 1, -0.0)
    pull_plate = g.extrude(g.rrect(pw + 2 * wall + 2 * wing, ph + 2 * wall, 8.0), plate_t, depth)
    body = (body + pull_plate).rotate([180, 0, 0])                         # pull plate on the bed, pocket opening up
    return BuildResult(
        {"plug-puller": body},
        print_notes=["Print as modelled, the pull plate flat on the bed and the pocket opening up, so nothing bridges. The sleeve is joined to the plate across the layers, so pull straight out and gently: it is a light-duty aid.",
                     "Use PETG with 5 walls and 40% infill. A slightly flexible wall also grips the plug better than stiff plastic."],
        fit_notes=[f"Pocket {pw:.1f} x {ph:.1f} mm and {depth:g} mm deep for a plug body {p['plug_width']:g} x {p['plug_height']:g} mm. "
                   "Measure the plug body from the back (not the pins), at its widest. It slips over the back of the plug and stays on, so you pull on the wings instead of the plug."],
        derived={"pocket_width_mm": pw, "pocket_height_mm": ph, "overall_width_mm": pw + 2 * wall + 2 * wing})


register(PartSpec(
    "plug-puller", "Plug puller",
    "A cap that stays on the back of a mains plug, with two wide wings to hook your fingers behind, so you pull the plug out with the hand instead of pinching the cable.",
    "Weak grip, arthritis, tremor, plugs that are stiff or sit behind furniture",
    [ParamSpec("plug_width", "Plug width", "float", 50.0, 30, 75, "mm", "Measure the plug body from the back, at its widest."),
     ParamSpec("plug_height", "Plug height", "float", 38.0, 25, 60, "mm"),
     ParamSpec("grip_depth", "Grip depth", "float", 22.0, 12, 40, "mm", "How much of the plug the cap covers."),
     ParamSpec("wing_length", "Wing length", "float", 35.0, 20, 60, "mm", "How far each wing sticks out for your fingers."),
     ParamSpec("wall", "Wall thickness", "float", 3.0, 2, 5, "mm"),
     CLEARANCE],
    build_plug_puller,
    ["plug", "unplug", "plug puller", "pull the plug", "power plug", "wall plug", "mains plug", "plug socket", "remove a plug", "plug out", "pull out the plug"],
    ["grip"]))


# ------------------------------------------------------------------------------------ keyguard
def build_keyguard(p: dict) -> BuildResult:
    cols, rows = int(p["columns"]), int(p["rows"])
    px, py = p["key_pitch_x"], p["key_pitch_y"]
    hw, hh = p["hole_width"], p["hole_height"]
    hw, hh = min(hw, px - 2.0), min(hh, py - 2.0)
    margin, t, skirt = p["margin"], p["plate_thickness"], p["standoff"]
    W, H = cols * px + 2 * margin, rows * py + 2 * margin
    holes = None
    for c in range(cols):
        for r in range(rows):
            x, y = (c - (cols - 1) / 2) * px, (r - (rows - 1) / 2) * py
            h = g.rrect(hw, hh, min(2.0, hw / 2 - 0.1, hh / 2 - 0.1)).translate([x, y])
            holes = h if holes is None else holes + h
    plate = g.extrude(g.rrect(W, H, 4.0) - holes, t)
    wall = 3.0
    skirt_ring = g.extrude(g.rrect(W, H, 4.0) - g.rrect(W - 2 * wall, H - 2 * wall, 2.5), t + skirt)
    return BuildResult(
        {"keyguard": plate + skirt_ring},
        print_notes=["Print as modelled, plate flat on the bed with the standoff walls pointing up, so nothing bridges. Turn it over to use it: the walls then rest on the keyboard frame.",
                     "Fix it with a few strips of removable tape or small magnets on the keyboard frame. The walls hold the plate above the keys so a resting hand does not press them."],
        fit_notes=[f"{cols} x {rows} holes, each {hw:g} x {hh:g} mm on a {px:g} x {py:g} mm pitch. Measure the distance from the centre of one key to the next, "
                   "sideways and down. A full-size keyboard is 19 mm each way; many numpads and calculators are 16 to 19 mm."],
        derived={"overall_width_mm": W, "overall_height_mm": H, "hole_count": cols * rows})


register(PartSpec(
    "keyguard", "Keyguard for a keypad",
    "A plate with one hole per key that sits just above a keypad, so a shaking or resting hand lands on one key at a time instead of pressing its neighbours.",
    "Tremor, Parkinson's, limited fine motor control, typing and calculator or phone keypad use",
    [ParamSpec("columns", "Keys across", "int", 3, 1, 8, "", "Number of keys in a row."),
     ParamSpec("rows", "Keys down", "int", 4, 1, 6, "", "Number of rows of keys."),
     ParamSpec("key_pitch_x", "Key spacing across", "float", 19.0, 12, 28, "mm", "Centre of one key to the centre of the next, sideways."),
     ParamSpec("key_pitch_y", "Key spacing down", "float", 19.0, 12, 28, "mm"),
     ParamSpec("hole_width", "Hole width", "float", 14.0, 8, 24, "mm", "Slightly smaller than the key, so the edge guides the finger."),
     ParamSpec("hole_height", "Hole height", "float", 14.0, 8, 24, "mm"),
     ParamSpec("plate_thickness", "Plate thickness", "float", 2.4, 1.6, 4, "mm"),
     ParamSpec("standoff", "Standoff height", "float", 5.0, 3, 12, "mm", "Height of the plate above the keys. Key travel plus 2 mm is enough."),
     ParamSpec("margin", "Border", "float", 8.0, 5, 20, "mm")],
    build_keyguard,
    ["keyboard", "keypad", "numpad", "keyguard", "key guard", "typing", "mistype", "wrong key", "calculator", "tremor typing", "hit the wrong keys", "phone keypad", "numeric keypad"],
    ["tremor"]))


# ------------------------------------------------------------------------------------ button dots
def build_button_dots(p: dict) -> BuildResult:
    n = int(p["dot_count"])
    d, h, sp = p["dot_diameter"], p["dot_height"], p["spacing"]
    r = d / 2
    base_t = 1.0
    margin = 2.5
    W = (n - 1) * sp + d + 2 * margin
    Hh = d + 2 * margin
    base = g.extrude(g.rrect(W, Hh, min(Hh / 2 - 0.1, 3.0)), base_t)
    dots = []
    for i in range(n):
        x = (i - (n - 1) / 2) * sp
        dome = g.dome(r, 0, 0, 0, 32).scale([1.0, 1.0, h / r]).translate([x, 0, base_t - 0.05])
        dots.append(dome)
    return BuildResult(
        {"button-dots": base + g.union(dots)},
        print_notes=["Print flat with the dots up; they print as smooth domes. Use PETG or PLA at 0.12 mm layer height so the dots are smooth under a fingertip.",
                     "Stick it on with a thin double-sided tape, or print it in a colour that contrasts with the appliance."],
        fit_notes=[f"{n} dot(s), {d:g} mm across and {h:g} mm high, {sp:g} mm apart. One dot on the start button and two on the stop button is a common convention; "
                   "match the number to your own scheme and keep it consistent across appliances."],
        derived={"strip_length_mm": W, "dot_height_mm": h})


register(PartSpec(
    "button-dots", "Tactile button dots",
    "A small adhesive strip with raised dots, to mark a button, a dial position or a key by touch.",
    "Blind or low vision, microwave and oven buttons, remote controls, keyboards, marking medicine boxes",
    [ParamSpec("dot_count", "Number of dots", "int", 1, 1, 6, "", "Use a different number of dots for different buttons."),
     ParamSpec("dot_diameter", "Dot diameter", "float", 5.0, 3, 10, "mm", "Match to the button; smaller than the button face."),
     ParamSpec("dot_height", "Dot height", "float", 1.6, 1.0, 3.0, "mm", "1.5 mm or more is easy to feel; more than 3 mm catches on things."),
     ParamSpec("spacing", "Dot spacing", "float", 9.0, 6, 18, "mm", "Centre to centre.")],
    build_button_dots,
    ["tactile", "bump", "bumps", "dots", "raised dot", "raised dots", "dots on", "remote control", "button marker", "mark a button", "feel the button", "microwave button", "touch", "start button", "button marker", "low vision button", "blind button"],
    ["low vision"]))


# ------------------------------------------------------------------------------------ step edge marker
def build_step_marker(p: dict) -> BuildResult:
    L, W, t = p["length"], p["depth"], p["thickness"]
    rh, rw, pitch = p["ridge_height"], p["ridge_width"], p["ridge_pitch"]
    plate = g.extrude(g.rrect(L, W, 2.0), t)
    n = max(1, int((L - 8.0) // pitch) + 1)
    ridges = [g.box(-rw / 2, rw / 2, -W / 2 + 4.0, W / 2 - 4.0, t - 0.2, t + rh).translate([(i - (n - 1) / 2) * pitch, 0, 0]) for i in range(n)]
    return BuildResult(
        {"step-marker": plate + g.union(ridges)},
        print_notes=["Print flat, ridges up. For high contrast print it in a bright colour against the step (yellow on grey stone, white on dark wood).",
                     "Stick it along the front edge of the step with strong outdoor double-sided tape or construction adhesive. Check it is not itself a trip hazard: the plate is flat and only the ridges stand proud."],
        fit_notes=[f"A {L:g} x {W:g} mm strip with {n} ridges, {rh:g} mm high every {pitch:g} mm. Measure the width of the step nosing and choose a length to match; "
                   "for a long stair, print several strips and butt them end to end."],
        derived={"ridge_count": n, "length_mm": L})


register(PartSpec(
    "step-marker", "Step edge marker strip",
    "A bright, ridged strip that sticks to the front edge of a step, so the edge can be seen and felt before the foot reaches it.",
    "Low vision, unsteady walking, dim stairs and garden steps",
    [ParamSpec("length", "Strip length", "float", 200.0, 60, 210, "mm", "Along the step edge."),
     ParamSpec("depth", "Strip depth", "float", 45.0, 25, 80, "mm", "From the front edge back across the tread."),
     ParamSpec("thickness", "Plate thickness", "float", 2.4, 1.6, 4, "mm"),
     ParamSpec("ridge_height", "Ridge height", "float", 1.6, 1.0, 3.0, "mm", "Tall enough to feel, low enough not to catch a toe."),
     ParamSpec("ridge_width", "Ridge width", "float", 3.0, 2, 6, "mm"),
     ParamSpec("ridge_pitch", "Ridge spacing", "float", 9.0, 6, 20, "mm")],
    build_step_marker,
    ["stairs", "step", "steps", "edge of the steps", "see the edge", "stair edge", "step edge", "stair", "stair nosing", "nosing", "trip on stairs", "see the steps", "garden step", "curb", "kerb"],
    ["low vision", "mobility"]))


# ------------------------------------------------------------------------------------ cane table clip
def build_cane_clip(p: dict) -> BuildResult:
    clr = p["clearance"]
    th, dp, W, wall = p["table_thickness"], p["clip_depth"], p["width"], p["wall"]
    r_i = (p["cane_diameter"] + clr) / 2
    r_o = r_i + wall
    H = th + 2 * wall
    profile = (g.rect(wall, H, center=False)
               + g.rect(dp, wall, center=False).translate([0, 0])
               + g.rect(dp, wall, center=False).translate([0, H - wall]))
    clip = g.extrude(g.round_corners(profile, 1.2), W).translate([0, 0, -W / 2])
    ring_h = min(max(H, 30.0), 40.0)
    ring = (g.cyl(r_o, ring_h) - g.cyl(r_i, ring_h + 2, -1)).rotate([-90, 0, 0])      # axis becomes vertical (y here)
    ring = ring.translate([-r_o + 1.2, H - ring_h if H >= ring_h else 0, 0])
    mouth = r_i * 1.35
    gap_box = g.box(-2 * r_o - 3, -r_o + 0.5, -5, H + 40, -mouth / 2, mouth / 2)
    ring = ring - gap_box
    body = clip + ring
    return BuildResult(
        {"cane-table-clip": body},
        print_notes=["Print as modelled, the C-shaped clip flat on the bed so the layers run along the arms that clamp the table, which is where it takes load. The cane ring then lies on its side, so the slicer adds support under it (about a fifth more plastic): use tree supports and a brim, and expect a slightly rough underside on the ring.",
                     "PETG, 5 walls, 50% infill. Pad the inside of the arms with a strip of rubber or felt so it does not mark the table or slide."],
        fit_notes=[f"Opening {th + 0:g} mm between the arms for a table top {p['table_thickness']:g} mm thick; cane ring {2 * r_i:.1f} mm for a cane {p['cane_diameter']:g} mm across. "
                   "Measure the table edge and the cane shaft just below the handle. It holds the cane so it does not fall on the floor; do not lean your weight on it."],
        derived={"cane_ring_diameter_mm": 2 * r_i, "table_gap_mm": float(th)})


register(PartSpec(
    "cane-table-clip", "Cane table clip",
    "A clip that hooks over the edge of a table or counter with a snap-in ring that parks a walking stick, so it is within reach and does not clatter to the floor.",
    "Walking stick users, people who cannot bend to pick a cane up, restaurants and desks",
    [ParamSpec("table_thickness", "Table thickness", "float", 28.0, 12, 60, "mm", "Measure the edge of the table top where the clip will sit."),
     ParamSpec("cane_diameter", "Cane diameter", "float", 19.0, 12, 30, "mm", "Measure the shaft just under the handle."),
     ParamSpec("clip_depth", "Clip depth", "float", 45.0, 25, 80, "mm", "How far the arms reach in over the table."),
     ParamSpec("width", "Clip width", "float", 34.0, 24, 60, "mm"),
     ParamSpec("wall", "Wall thickness", "float", 5.0, 3, 8, "mm"),
     CLEARANCE],
    build_cane_clip,
    ["cane holder", "walking stick holder", "cane clip", "park my cane", "hold my cane", "cane falls", "stick holder", "cane hook", "cane on the table", "falling off the table", "falls off the table", "park my walking stick", "walking stick keeps falling", "crutch holder", "cane table", "hang my cane"],
    ["mobility"]))


# ------------------------------------------------------------------------------------ pump pusher
def build_pump_pusher(p: dict) -> BuildResult:
    clr = p["clearance"]
    r_i = (p["head_diameter"] + clr) / 2
    wall, hh = 3.0, p["head_height"]
    pad_r = max(p["pad_diameter"] / 2, r_i + wall + 4.0)
    top_t = 4.0
    skirt = g.cyl(r_i + wall, hh + top_t)
    pad = g.extrude(g.polar(lambda a: pad_r * (1 + 0.02 * np.cos(a * 12)), 240), top_t, hh)
    body = skirt + pad
    body = body - g.cyl(r_i, hh + 1, -1)
    sw, sh = p["spout_width"], p["spout_height"]
    body = body - g.box(-sw / 2, sw / 2, -(r_i + wall + 2), 0, -1, min(sh, hh - 2))       # the spout comes out through this slot
    body = body.rotate([180, 0, 0])                                                      # pad on the bed, cap standing up
    return BuildResult(
        {"pump-pusher": body},
        print_notes=["Print as modelled, the wide pad flat on the bed and the cap standing up; no supports are needed. The spout slot is a vertical cut, so it prints cleanly.",
                     "TPU or flexible PETG makes the cap grip the pump head. Slip it over the head with the slot facing the spout, then press anywhere on the pad."],
        fit_notes=[f"Cap {2 * r_i:.1f} mm inside for a pump head {p['head_diameter']:g} mm across, {hh:g} mm tall; spout slot {sw:g} mm wide. "
                   "Measure the widest part of the pump head with the spout pointing away, and how far the spout is above the bottle."],
        derived={"cap_diameter_mm": 2 * r_i, "pad_diameter_mm": 2 * pad_r})


register(PartSpec(
    "pump-pusher", "Soap pump pusher",
    "A wide cap that fits over a soap or lotion pump head, so the pump is pressed with the heel of the hand or a closed fist instead of a precise finger push.",
    "Weak grip, arthritis, tremor, one-handed use, pumps that need firm pressure",
    [ParamSpec("head_diameter", "Pump head diameter", "float", 38.0, 22, 60, "mm", "Widest part of the head, not counting the spout."),
     ParamSpec("head_height", "Pump head height", "float", 28.0, 15, 50, "mm"),
     ParamSpec("pad_diameter", "Pad diameter", "float", 75.0, 50, 110, "mm", "Bigger is easier to hit."),
     ParamSpec("spout_width", "Spout slot width", "float", 16.0, 8, 30, "mm"),
     ParamSpec("spout_height", "Spout slot height", "float", 14.0, 6, 40, "mm", "Height of the slot measured from the bottom edge of the cap."),
     CLEARANCE],
    build_pump_pusher,
    ["soap pump", "pump dispenser", "lotion pump", "hand soap", "pump bottle", "press the pump", "dispenser", "pump head", "soap dispenser", "hand wash pump", "hand sanitiser", "hand sanitizer"],
    ["bathroom"]))


# ------------------------------------------------------------------------------------ keyhole guide
def build_keyhole_guide(p: dict) -> BuildResult:
    clr = p["clearance"]
    hole_r = (p["lock_diameter"] + clr) / 2
    fun_r = p["funnel_diameter"] / 2
    depth = p["depth"]
    plate_r = max(p["plate_diameter"] / 2, fun_r + 5.0)
    body = g.cyl(plate_r, depth)
    cone = g.loft(g.circle(hole_r), g.circle(fun_r), depth - 3.0 + 0.02, 3.0 - 0.01)
    body = body - g.cyl(hole_r, depth + 2, -1) - cone - g.cyl(fun_r, 1.0, depth - 0.5)
    return BuildResult(
        {"keyhole-guide": body},
        print_notes=["Print with the wide face down (as modelled, the funnel opens upward), no supports are needed.",
                     "Fix it round the lock with strong double-sided tape on the flat back. Use a bright colour so the lock is easy to spot."],
        fit_notes=[f"The funnel narrows to {2 * hole_r:.1f} mm, which must sit over a lock face {p['lock_diameter']:g} mm across with the keyhole in the middle. "
                   "Measure the metal lock face on the door. A key dropped into the funnel slides to the centre of the lock."],
        derived={"hole_diameter_mm": 2 * hole_r, "funnel_diameter_mm": 2 * fun_r})


register(PartSpec(
    "keyhole-guide", "Keyhole guide",
    "A bright funnel that sticks round a door lock and steers the key tip to the keyhole, so it can be found by touch or with a shaky hand.",
    "Low vision, tremor, arthritis, finding the lock in the dark",
    [ParamSpec("lock_diameter", "Lock face diameter", "float", 22.0, 12, 40, "mm", "Measure the round metal face of the lock."),
     ParamSpec("funnel_diameter", "Funnel mouth diameter", "float", 46.0, 30, 70, "mm"),
     ParamSpec("plate_diameter", "Outer diameter", "float", 56.0, 40, 90, "mm"),
     ParamSpec("depth", "Depth", "float", 12.0, 8, 20, "mm", "Deeper makes a steeper funnel."),
     CLEARANCE],
    build_keyhole_guide,
    ["keyhole", "lock", "find the lock", "key guide", "guide the key", "front door lock", "key funnel", "keyhole guide", "find the keyhole", "put the key in", "key goes in the lock", "key in the lock", "goes in the lock", "door lock", "padlock"],
    ["low vision"]))


# ====================================================================================== second set: vision, hearing, memory, wheelchair, eating, dexterity
# ------------------------------------------------------------------------------------ key ID grip
def build_key_id_grip(p: dict) -> BuildResult:
    clr = p["clearance"]
    kw, kt = p["key_width"] + clr, p["key_thickness"] + clr
    L, W, T = p["length"], p["width"], 8.0
    paddle = g.extrude(g.rrect(L, W, min(W / 2 - 0.5, 9.0)), T)
    z0 = (T - kt) / 2
    depth = p["key_depth"]
    paddle = paddle - g.box(L / 2 - depth, L / 2 + 1, -kw / 2, kw / 2, z0, z0 + kt)           # key bow slides in from the +x end
    paddle = paddle - g.cyl(3.2, T + 2, -1).translate([-L / 2 + 8.0, 0, 0])                    # hole for the key ring
    shape = p["marker"]
    r = min(W / 2 - 4.0, 9.0)
    cs = {"circle": g.circle(r), "square": g.rect(1.7 * r, 1.7 * r), "triangle": g.poly([(-r, -0.8 * r), (r, -0.8 * r), (0, 0.95 * r)]),
          "star": g.star(r * 1.1, r * 0.5, 5)}[shape]
    marker = g.extrude(cs.translate([-L / 2 + 20.0, 0]), 1.4, T - 0.05)
    return BuildResult(
        {"key-id-grip": paddle + marker},
        print_notes=["Print flat as modelled with the marker shape on top; the key slot is a thin horizontal cavity, 2.5 mm tall, which bridges fine.",
                     "Print each key's cover in a different colour AND shape, so it can be told apart by sight or by touch."],
        fit_notes=[f"Slot {kw:.1f} x {kt:.1f} mm, {depth:g} mm deep, for a key bow {p['key_width']:g} x {p['key_thickness']:g} mm. Measure the bow (the head) where the cover grips it. "
                   f"Raised {shape} marks this key; use a different shape for each key."],
        derived={"slot_width_mm": kw, "slot_thickness_mm": kt, "marker": shape})


register(PartSpec(
    "key-id-grip", "Key identification grip",
    "A big paddle that slides over a key's head, so it can be turned with the whole hand, and a raised shape on top that tells keys apart by touch.",
    "Low vision or blindness, weak pinch, arthritis, memory (which key is which)",
    [ParamSpec("key_width", "Key head width", "float", 24.0, 14, 34, "mm", "Measure across the head of the key (the part you hold)."),
     ParamSpec("key_thickness", "Key head thickness", "float", 2.4, 1.5, 4.5, "mm"),
     ParamSpec("key_depth", "Key insertion depth", "float", 28.0, 15, 40, "mm", "How much of the key head the slot covers."),
     ParamSpec("length", "Paddle length", "float", 70.0, 50, 100, "mm"),
     ParamSpec("width", "Paddle width", "float", 36.0, 28, 55, "mm"),
     ParamSpec("marker", "Tactile marker", "enum", "star", unit="", choices=["circle", "square", "triangle", "star"], help="A different shape for each key."),
     CLEARANCE],
    build_key_id_grip,
    ["key", "keys", "key cover", "tell my keys apart", "which key", "key identification", "key marker", "key grip", "tactile key", "colour code keys", "big key head", "identify keys"],
    ["low vision", "grip"]))


# ------------------------------------------------------------------------------------ phone sound horn
def build_sound_horn(p: dict) -> BuildResult:
    sl, sw, wall = p["speaker_length"], p["speaker_width"], 1.8
    seal = 3.0
    inlet_o = g.rrect(sl + 2 * seal, sw + 2 * seal, min((sw + 2 * seal) / 2 - 0.2, 4.0))
    inlet_i = g.rrect(sl + 1.0, sw + 1.0, min((sw + 1.0) / 2 - 0.1, 2.0))
    bell_d, H = p["bell_diameter"], p["horn_length"]
    flange_t = 2.0
    outer = g.extrude(g.rrect(sl + 2 * seal + 10, sw + 2 * seal + 10, 6.0), flange_t) + g.loft(inlet_o, g.circle(bell_d / 2), H, flange_t - 0.01)
    bore = g.extrude(inlet_i, flange_t + 0.5, -0.25) + g.loft(inlet_i, g.circle(max(bell_d / 2 - wall, 6.0)), H + 0.02, flange_t - 0.01)
    return BuildResult(
        {"sound-horn": outer - bore},
        print_notes=["Print with the flange on the bed and the bell opening up; no supports are needed. A smooth, sealed print sounds better: use 4 walls and 100% infill near the flange.",
                     "Hold the flat flange over the phone's speaker grille with a ring of soft putty, blu-tack or foam tape, and put the bell to your ear."],
        fit_notes=[f"Throat {sl + 1:g} x {sw + 1:g} mm for a speaker grille about {sl:g} x {sw:g} mm; bell {bell_d:g} mm across. "
                   "Find the speaker slot (usually at the top edge of the front) and measure it. "
                   "This is a passive horn: it directs sound and gains a few decibels, it is not a hearing aid."],
        derived={"bell_diameter_mm": bell_d, "length_mm": H + flange_t})


register(PartSpec(
    "sound-horn", "Phone sound horn",
    "A small horn that sits over a phone's speaker and funnels the sound into the ear, for calls and voice messages without turning the volume up.",
    "Hard of hearing, mild hearing loss, noisy rooms (a simple passive aid, not a hearing aid)",
    [ParamSpec("speaker_length", "Speaker slot length", "float", 14.0, 6, 40, "mm", "Length of the speaker grille or slot on the phone."),
     ParamSpec("speaker_width", "Speaker slot width", "float", 3.0, 2, 14, "mm"),
     ParamSpec("bell_diameter", "Bell diameter", "float", 45.0, 28, 70, "mm", "Opening that goes next to the ear."),
     ParamSpec("horn_length", "Horn length", "float", 55.0, 30, 90, "mm", "Longer horns amplify the low sounds of speech better.")],
    build_sound_horn,
    ["hearing", "hard of hearing", "can't hear", "cannot hear", "deaf", "hearing loss", "phone speaker", "amplify", "loud enough", "sound horn", "phone volume", "hear the phone", "voice calls"],
    ["hearing"]))


# ------------------------------------------------------------------------------------ picture label holder
def build_label_holder(p: dict) -> BuildResult:
    clr = p["clearance"]
    cw, ch, ct = p["card_width"] + clr, p["card_height"] + clr, p["card_thickness"] + clr
    border = 5.0
    ow, oh = cw + 2 * border, ch + 2 * border
    back_t, front_t = 1.6, 1.2
    outer = g.rrect(ow, oh, 4.0)
    back = g.extrude(outer, back_t)
    mid = g.extrude(outer - g.rrect(cw, ch, 1.0), ct + 0.05, back_t - 0.05)
    front = g.extrude(outer - g.rrect(cw - 2 * 4.0, ch - 2 * 4.0, 1.0), front_t, back_t + ct - 0.05)
    body = back + mid + front
    body = body - g.box(-cw / 2 + 2.0, cw / 2 - 2.0, ch / 2 - 0.5, oh / 2 + 1.0, back_t, back_t + ct)        # slot at the top to slide the card in
    return BuildResult(
        {"label-holder": body},
        print_notes=["Print flat, back plate on the bed; the front frame bridges only 4 mm, so only a little support is needed. Print in a high-contrast colour (white on a dark cupboard, black on a light one).",
                     "Stick it to the cupboard door with strong double-sided tape. The picture card slides in from the top, so it can be changed when the contents change."],
        fit_notes=[f"Pocket {cw:.1f} x {ch:.1f} x {ct:.1f} mm for a card {p['card_width']:g} x {p['card_height']:g} mm and {p['card_thickness']:g} mm thick (card or laminated paper). "
                   "Measure your picture cards and add nothing: the clearance is built in."],
        derived={"overall_width_mm": ow, "overall_height_mm": oh})


register(PartSpec(
    "label-holder", "Picture label holder",
    "A small frame stuck to a cupboard or drawer with a slot at the top for a picture or word card, so what is inside is shown, not remembered.",
    "Dementia, memory loss, aphasia, learning disability, autism, anyone who benefits from picture labels",
    [ParamSpec("card_width", "Card width", "float", 70.0, 30, 130, "mm", "Width of the picture or word card."),
     ParamSpec("card_height", "Card height", "float", 50.0, 25, 100, "mm"),
     ParamSpec("card_thickness", "Card thickness", "float", 1.0, 0.4, 3.0, "mm", "A laminated card is about 0.5 mm; card stock 0.3 mm; add the laminate."),
     CLEARANCE],
    build_label_holder,
    ["label", "picture label", "picture cards", "word cards", "label holder", "cupboard label", "dementia", "memory loss", "aphasia", "picture card", "label the cupboards", "what is in the drawer", "picture frame for cupboard",
     "remember what's inside", "memory aid", "learning disability", "autism labels"],
    ["memory", "cognitive"]))


# ------------------------------------------------------------------------------------ bag carrier handle
def build_bag_handle(p: dict) -> BuildResult:
    L, H, T = p["length"], p["grip_height"], p["grip_thickness"]
    slots = int(p["loop_slots"])
    sw, sh = p["slot_width"], 5.0
    body = g.extrude(g.round_corners(g.rrect(L, H + 14.0, 8.0), 6.0), T)
    for i in range(slots):
        x = (i - (slots - 1) / 2) * (sw + 14.0)
        body = body - g.extrude(g.rrect(sw, sh, sh / 2 - 0.05).translate([x, -(H + 14.0) / 2 + 6.5]), T + 2, -1)
    finger = g.rrect(L - 40.0, H - 8.0, min((H - 8.0) / 2 - 0.2, 8.0)).translate([0, 7.0])
    body = body - g.extrude(finger, T + 2, -1)
    return BuildResult(
        {"bag-handle": body},
        print_notes=["Print flat; no supports. PETG with 5 walls and 40% infill: it carries the whole weight of the shopping.",
                     "Thread the plastic bag handle loops through the lower slots and up over the bar, then carry the grip in your whole hand."],
        fit_notes=[f"{slots} slot(s), {sw:g} mm wide, for bag handles; the grip bar is {T:g} mm thick and about {H:g} mm tall. A wide bar spreads the load across the palm. "
                   "Not for loads over about 5 kg."],
        derived={"length_mm": L, "slot_count": slots})


register(PartSpec(
    "bag-handle", "Shopping bag carrier handle",
    "A wide, comfortable handle with slots for plastic bag loops, so a heavy shopping bag is carried in the palm and not on thin cutting loops.",
    "Weak grip, arthritis, one-handed carrying, walking-stick users carrying shopping",
    [ParamSpec("length", "Length", "float", 110.0, 80, 160, "mm", "Along the grip."),
     ParamSpec("grip_height", "Grip bar height", "float", 38.0, 28, 55, "mm"),
     ParamSpec("grip_thickness", "Grip thickness", "float", 18.0, 12, 28, "mm", "Thicker is easier on a weak grip."),
     ParamSpec("loop_slots", "Bag loop slots", "int", 2, 1, 3, "", "How many bags or loops it can carry."),
     ParamSpec("slot_width", "Slot width", "float", 20.0, 12, 30, "mm", "Wide enough for a bunched bag handle.")],
    build_bag_handle,
    ["shopping bag", "carrier bag", "plastic bag", "bag handle", "carry shopping", "carry the shopping", "grocery bag", "bags cut my hands", "carry bags", "heavy bags", "bag carrier", "shopping bags", "carrier bags", "plastic carrier", "carry heavy", "bags cut"],
    ["grip", "mobility"]))


# ------------------------------------------------------------------------------------ wheelchair / walker hook
def build_chair_hook(p: dict) -> BuildResult:
    clr = p["clearance"]
    r_i = (p["tube_diameter"] + clr) / 2
    wall, W = p["wall"], p["width"]
    r_o = r_i + wall
    ring = g.circle(r_o) - g.circle(r_i)
    mouth = 2 * r_i * 0.78
    ring = ring - g.rect(r_o + 2, mouth, center=False).translate([0, -mouth / 2])           # mouth faces +x; the hook leaves on the opposite side
    arm_len, tip = p["hook_depth"], p["tip_height"]
    t = max(wall, 5.0)
    arm = g.rect(arm_len + r_o, t, center=False).translate([-r_o - arm_len, -t / 2])
    up = g.rect(t, tip + t / 2, center=False).translate([-r_o - arm_len, -t / 2])
    profile = g.round_corners(ring + arm + up, 1.2)
    body = g.extrude(profile, W).translate([0, 0, -W / 2])
    return BuildResult(
        {"chair-hook": body},
        print_notes=["Print as modelled, flat on the bed with the C-ring and hook in the plane of the bed, so the layers run round the ring. PETG, 5 walls: it grips by springing open.",
                     "Snap the C-ring onto the tube from the side. It holds a bag or a cane hooked on the arm; keep loads under about 3 kg and never hang a child's weight."],
        fit_notes=[f"Ring {2 * r_i:.1f} mm inside for a tube {p['tube_diameter']:g} mm across. Wheelchair and walker frames are usually 22 to 25 mm; measure yours with a ruler across the tube. "
                   "Wrap a turn of tape round the tube first if it feels loose."],
        derived={"ring_inner_diameter_mm": 2 * r_i, "mouth_mm": mouth})


register(PartSpec(
    "chair-hook", "Wheelchair or walker hook",
    "A C-ring that snaps onto a frame tube with a deep hook on the other side, to hang a bag, a coat or a cane where it can be reached.",
    "Wheelchair and walker users, one-handed users, anyone who cannot carry a bag and a frame at once",
    [ParamSpec("tube_diameter", "Frame tube diameter", "float", 22.0, 14, 40, "mm", "Measure across the tube the hook will clip to."),
     ParamSpec("hook_depth", "Hook depth", "float", 40.0, 25, 70, "mm", "How far the hook reaches from the tube."),
     ParamSpec("tip_height", "Tip height", "float", 22.0, 12, 40, "mm", "How far the end curls up to keep the bag on."),
     ParamSpec("width", "Hook width", "float", 20.0, 14, 36, "mm"),
     ParamSpec("wall", "Ring wall thickness", "float", 4.0, 3, 7, "mm"),
     CLEARANCE],
    build_chair_hook,
    ["frame hook", "wheelchair hook", "bag on my wheelchair", "on my wheelchair", "walker hook", "rollator hook", "hang a bag", "bag hook", "chair hook", "hook for my wheelchair", "hang my bag", "hang my cane", "walker bag", "carry my bag", "hook for the frame", "hook for my rollator", "hook for my walker"],
    ["mobility"]))


# ------------------------------------------------------------------------------------ plate guard
def build_plate_guard(p: dict) -> BuildResult:
    clr = p["clearance"]
    R = p["plate_diameter"] / 2
    ang = math.radians(p["arc_angle"])
    wall, H = 9.0, p["guard_height"]
    t_rim = p["rim_thickness"] + clr
    big = (R + wall + 20.0) / math.cos(ang / 2)
    wedge = g.poly([(0, 0), (big * math.cos(-ang / 2), big * math.sin(-ang / 2)), (big * math.cos(ang / 2), big * math.sin(ang / 2))])
    ring = (g.circle(R + wall, 256) - g.circle(R, 256)) ^ wedge
    wall_body = g.extrude(ring, H)
    slot_ring = (g.circle(R + 6.0, 256) - g.circle(R - 1.0, 256)) ^ wedge
    z_slot = 8.0
    body = wall_body - g.extrude(slot_ring, t_rim, z_slot)
    return BuildResult(
        {"plate-guard": body},
        print_notes=["Print standing as modelled, the curved wall upright. The rim slot is a 6 mm deep horizontal groove, which the slicer supports lightly (about a tenth of the plastic).",
                     "Use PETG (dishwasher-safe on the top rack at 60 degrees is a risk for PLA). Food contact: wash well, and it is not for hot oven plates."],
        fit_notes=[f"Slot {t_rim:.1f} mm for a plate rim {p['rim_thickness']:g} mm thick, curved for a plate {p['plate_diameter']:g} mm across. "
                   "Measure the plate across the rim and the rim's edge thickness, then slide the guard onto the rim on the side the food gets pushed against."],
        derived={"arc_length_mm": ang * (R + wall / 2), "guard_height_mm": H})


register(PartSpec(
    "plate-guard", "Plate guard",
    "A curved wall that slides onto a plate's rim, so food can be pushed against it and scooped up with one hand instead of chasing it round the plate.",
    "One-handed eating, tremor, limited grip, low vision, stroke recovery",
    [ParamSpec("plate_diameter", "Plate diameter", "float", 240.0, 160, 300, "mm", "Measure across the rim, edge to edge."),
     ParamSpec("rim_thickness", "Rim thickness", "float", 5.0, 2.5, 9.0, "mm", "How thick the edge of the plate is."),
     ParamSpec("guard_height", "Guard height", "float", 42.0, 28, 65, "mm"),
     ParamSpec("arc_angle", "Guard arc", "float", 70.0, 45, 100, "deg", "How much of the plate's edge it covers."),
     CLEARANCE],
    build_plate_guard,
    ["plate guard", "food guard", "push food", "food falls off", "one-handed eating", "eat with one hand", "scoop food", "plate", "stroke eating", "food slides off", "scoop plate", "eating aid"],
    ["eating"]))


# ------------------------------------------------------------------------------------ pill popper
def build_pill_popper(p: dict) -> BuildResult:
    n = int(p["plunger_count"])
    d, Lp, pad = p["plunger_diameter"], p["plunger_length"], p["pad_diameter"]
    pitch = max(d + 8.0, 14.0)
    pad_w = max(pad, (n - 1) * pitch + d + 24.0)
    base = g.extrude(g.rrect(pad_w, pad, min(pad / 2 - 0.5, 12.0)), 7.0)
    posts = []
    for i in range(n):
        x = (i - (n - 1) / 2) * pitch
        posts.append(g.cyl(d / 2, Lp + 1.0, 6.0).translate([x, 0, 0]))
        posts.append(g.dome(d / 2 * 0.9, x, 0, 6.0 + Lp + 0.5, 24))
    body = base + g.union(posts)
    return BuildResult(
        {"pill-popper": body},
        print_notes=["Print as modelled, the pad flat on the bed and the plunger posts standing up; 5 walls so the posts do not snap.",
                     "Hold the blister pack bubble-side up over a tray or cup and push the post down onto the bubble with the heel of the hand."],
        fit_notes=[f"{n} plunger(s) {d:g} mm across and {Lp:g} mm long. Choose a diameter a little smaller than the blister bubble so it presses without piercing the foil. "
                   "Match it to your pill size, usually 6 to 10 mm."],
        derived={"plunger_diameter_mm": d, "pad_width_mm": pad_w})


register(PartSpec(
    "pill-popper", "Blister pack pill popper",
    "A wide pad with a rounded plunger that presses a tablet out of a blister pack with the palm instead of a pinching thumbnail.",
    "Weak grip, arthritis, tremor, difficulty with childproof blister packs",
    [ParamSpec("plunger_diameter", "Plunger diameter", "float", 8.0, 4, 16, "mm", "A little smaller than the pill bubble."),
     ParamSpec("plunger_length", "Plunger length", "float", 12.0, 8, 22, "mm"),
     ParamSpec("plunger_count", "Number of plungers", "int", 1, 1, 3, ""),
     ParamSpec("pad_diameter", "Pad size", "float", 45.0, 30, 75, "mm", "Bigger is easier to press.")],
    build_pill_popper,
    ["blister", "blister pack", "pop pills", "push pills out", "press out", "tablet blister", "medicine strip", "foil pack", "popping pills", "pill press", "pill popper", "press pills out", "pills out of", "foil strips", "foil", "tablets out"],
    ["medicine"]))


# ------------------------------------------------------------------------------------ book stand
def build_book_stand(p: dict) -> BuildResult:
    clr = p["clearance"]
    T = p["book_thickness"] + clr
    th = math.radians(p["angle"])
    bt, tl, tb = 5.0, 5.0, 6.0
    u, nf = (math.cos(th), math.sin(th)), (-math.sin(th), math.cos(th))
    Lb = p["backrest_height"] / math.sin(th)
    P0 = (0.0, bt)
    top = (P0[0] + Lb * u[0], P0[1] + Lb * u[1])
    back = g.poly([P0, top, (top[0] - tb * nf[0], top[1] - tb * nf[1]), (P0[0] - tb * nf[0], P0[1] - tb * nf[1])])
    y_f = -T / math.sin(th)
    back_end = top[0] - tb * nf[0] + 2.0
    base = g.rect(back_end - (y_f - tl), bt, center=False).translate([y_f - tl, 0])
    lip = g.rect(tl, bt + p["lip_height"], center=False).translate([y_f - tl, 0])
    W = p["width"]
    body = g.extrude(base + lip + back, W).rotate([90, 0, 90]).translate([-W / 2, 0, 0])
    return BuildResult(
        {"book-stand": body},
        print_notes=["Print on its side with the profile flat on the bed if it fits; otherwise upright with a brim. No supports are needed either way.",
                     "Open the book against the backrest with its bottom edge in the lip. A rubber band or two elastic bands across the pages keep it open."],
        fit_notes=[f"Slot {T:.1f} mm for a book {p['book_thickness']:g} mm thick at a {p['angle']:g} degree lean. Measure the book closed. "
                   "Tablets and recipe books work too."],
        derived={"slot_width_mm": T, "angle_deg": p["angle"], "depth_mm": back_end - (y_f - tl)})


register(PartSpec(
    "book-stand", "Reading stand",
    "A leaning stand with a front lip that holds a book, tablet or recipe open at a comfortable angle, hands free.",
    "Arthritis, tremor, weak grip, one-handed reading, low-vision users who read close to the page",
    [ParamSpec("book_thickness", "Book thickness", "float", 25.0, 6, 50, "mm", "The closed book, or the tablet with its case."),
     ParamSpec("angle", "Lean angle", "float", 70.0, 55, 80, "deg"),
     ParamSpec("backrest_height", "Backrest height", "float", 140.0, 90, 200, "mm"),
     ParamSpec("lip_height", "Front lip height", "float", 20.0, 10, 35, "mm"),
     ParamSpec("width", "Width", "float", 180.0, 100, 210, "mm"),
     CLEARANCE],
    build_book_stand,
    ["book stand", "reading stand", "hold a book", "read a book", "hold the book open", "recipe book", "cookbook stand", "tablet stand", "can't hold a book", "reading in bed", "book holder", "cookbook", "hold my cookbook", "book open", "hold it open", "page"],
    ["reading"]))


# ------------------------------------------------------------------------------------ cup handle clip
def build_cup_handle(p: dict) -> BuildResult:
    clr = p["clearance"]
    r_i = (p["cup_diameter"] + clr) / 2
    wall, H = p["wall"], p["grip_height"]
    r_o = r_i + wall
    ring = g.circle(r_o, 192) - g.circle(r_i, 192)
    half = math.radians(55)
    big = (r_o + 20.0) / math.cos(half)
    ring = ring - g.poly([(0, 0), (big * math.cos(-half), big * math.sin(-half)), (big * math.cos(half), big * math.sin(half))])    # mouth faces +x
    hl, hw = p["handle_length"], p["handle_opening"]
    outer = g.rrect(hl, hw + 2 * 9.0, min((hw + 18.0) / 2 - 0.5, 14.0)).translate([-(r_o + hl / 2 - 3.0), 0])
    hole = g.rrect(hl - 18.0, hw, min(hw / 2 - 0.2, 10.0)).translate([-(r_o + hl / 2 - 3.0), 0])
    handle = outer - hole
    body = g.extrude(ring + handle, H)
    return BuildResult(
        {"cup-handle": body},
        print_notes=["Print standing as modelled, flat on its base; the clip and the handle are one extrusion, so there is nothing to bridge. Use PETG: it must flex to snap on.",
                     "Spring it onto the cup from the side. Hand-wash only, and not for very hot drinks: PETG softens near 70 degrees."],
        fit_notes=[f"Clip {2 * r_i:.1f} mm inside for a cup or glass {p['cup_diameter']:g} mm across at the point it grips (measure below the rim, not across the lip). "
                   "Straight-sided cups and mugs hold best; tapered ones need the clip near the widest part."],
        derived={"clip_inner_diameter_mm": 2 * r_i, "handle_opening_mm": hw})


register(PartSpec(
    "cup-handle", "Clip-on cup handle",
    "A snap-on ring with a large finger loop that gives a handleless cup or glass a handle.",
    "Weak grip, arthritis, tremor, mugs and tumblers with no handle",
    [ParamSpec("cup_diameter", "Cup diameter", "float", 78.0, 50, 100, "mm", "Measure across the cup where the clip will grip."),
     ParamSpec("grip_height", "Clip height", "float", 28.0, 18, 45, "mm"),
     ParamSpec("handle_length", "Handle length", "float", 70.0, 50, 100, "mm"),
     ParamSpec("handle_opening", "Finger opening", "float", 26.0, 18, 40, "mm", "Big enough for two or three fingers."),
     ParamSpec("wall", "Clip wall thickness", "float", 3.5, 2.4, 6, "mm"),
     CLEARANCE],
    build_cup_handle,
    ["cup handle", "mug handle", "glass handle", "no handle", "handleless", "tumbler", "can't hold a cup", "cup is hard to hold", "hold a cup", "clip on handle", "mug", "drinking aid"],
    ["drinking"]))
