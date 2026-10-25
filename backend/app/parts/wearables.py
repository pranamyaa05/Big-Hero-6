"""Hand-worn and clamp-on parts: two-part ergonomic utensil grip, configurable clip-on palm band."""
from __future__ import annotations
import math
import numpy as np
from manifold3d import Manifold, JoinType
from .. import geom as g
from ..spec import PartSpec, ParamSpec, BuildResult, ParamError
from . import CLEARANCE, register

TAU = math.tau


# ------------------------------------------------------------------------------------ utensil grip (two halves)
def build_utensil_grip(p: dict) -> BuildResult:
    notes = []
    clr = p["clearance"]
    L = p["length"]
    screw = p["screw_diameter"]
    shape = p["channel_shape"]
    if shape == "round":
        cw = ct = p["handle_diameter"] + clr
        chan2d = g.circle(cw / 2, 64)
    else:
        cw, ct = p["handle_width"] + clr, p["handle_thickness"] + clr
        chan2d = g.rrect(ct, cw, min(ct, cw) / 2 - 0.01, 48)         # thickness along x, width along y (in the split plane)
    half_w = cw / 2 if shape == "round" else cw / 2
    hole_r_clear, hole_r_tap = (screw + 0.5) / 2, (screw - 0.4) / 2
    hole_off = half_w + 2.5 + hole_r_clear + 1.0
    R = max(p["grip_diameter"] / 2, hole_off + hole_r_clear + 3.0, ct / 2 + 4.0)
    if R > p["grip_diameter"] / 2 + 1e-9:
        notes.append(f"Grip diameter raised to {2 * R:.1f} mm so the screws and the channel have enough material around them.")
    ch = min(2.5, R * 0.16)
    prof = [(0, -L / 2), (R - ch, -L / 2), (R, -L / 2 + ch), (R, L / 2 - ch), (R - ch, L / 2), (0, L / 2)]
    smooth = Manifold.revolve(g.poly(prof), g.SEG)
    ng = p["grooves"]
    pitch = L * 0.2
    groove = None
    for i in range(ng):
        zc = (i - (ng - 1) / 2) * pitch
        t = Manifold.revolve(g.circle(0.4 * R, 64).translate([1.26 * R, 0]), g.SEG).translate([0, 0, zc])
        groove = t if groove is None else groove + t
    top_space = g.box(-1.0, 3 * R, -3 * R, 3 * R, -L, L)   # starts just past the split plane so the cut crosses the seam cleanly
    ridged = smooth - (groove ^ top_space) if groove is not None else smooth
    chan = Manifold.extrude(chan2d, L + 4).translate([0, 0, -L / 2 - 2])
    zs = [-pitch, pitch]
    side_top = g.box(0, 2 * R, -2 * R, 2 * R, -L, L)
    side_bot = g.box(-2 * R, 0, -2 * R, 2 * R, -L, L)
    top = (ridged ^ side_top) - chan
    bot = (smooth ^ side_bot) - chan
    ycol = math.sqrt(max(R * R - hole_off * hole_off, 1.0))        # half thickness of the grip at the screw line
    tap_depth = min(9.0, ycol - 2.5)
    head_r = screw * 0.95 + 0.25
    for y in (-hole_off, hole_off):
        for z in zs:
            tap = g.cyl(hole_r_tap, tap_depth + 1, -1, 24).rotate([0, 90, 0]).translate([0, y, z])
            top = top - tap
            thru = g.cyl(hole_r_clear, ycol + 2, 0, 24).rotate([0, -90, 0]).translate([1.0, y, z])
            cb = g.cyl(head_r, 4.0, 0, 32).rotate([0, -90, 0]).translate([-(ycol - 3.0), y, z])
            bot = bot - thru - cb
    # lay each half with its flat face on the bed
    top_bed = top.rotate([0, -90, 0])
    bot_bed = bot.rotate([0, 90, 0])
    screw_len = ycol - 3.0 + tap_depth - 1.0
    return BuildResult(
        {"top-half": top_bed, "bottom-half": bot_bed}, notes=notes,
        print_notes=["Print each half with its flat face down. The channel is a small arch: the slicer adds a little support inside it (under a tenth of the plastic), so leave automatic supports on.",
                     "TPU 95A for a soft, grippy grip, or PETG for a firm one. 3 walls, 20% infill.",
                     f"Assembly: four M{screw:g} screws from the smooth half into the grooved half (about {int(round(screw_len / 2) * 2)} mm long). "
                     "Tighten gently; a thin strip of non-slip tape in the channel stops the utensil twisting."],
        fit_notes=[f"Channel {'%.1f mm round' % cw if shape == 'round' else '%.1f x %.1f mm flat' % (cw, ct)} for the utensil handle. "
                   "Measure the thickest part of the handle."],
        derived={"grip_diameter_mm": 2 * R, "length_mm": L, "channel_width_mm": cw, "channel_thickness_mm": ct, "screw_length_mm": screw_len})


register(PartSpec(
    "utensil-grip", "Utensil grip (two halves)",
    "A fat, grooved grip that clamps around a fork, spoon or toothbrush handle with four screws.",
    "Tremor, weak grip, arthritis, limited dexterity",
    [ParamSpec("channel_shape", "Channel shape", "enum", "round", unit="", choices=["round", "flat"], help="'round' for a round handle, 'flat' for a flat fork or spoon handle."),
     ParamSpec("handle_diameter", "Handle diameter (round)", "float", 9.1, 3, 20, "mm"),
     ParamSpec("handle_width", "Handle width (flat)", "float", 16.0, 6, 30, "mm"),
     ParamSpec("handle_thickness", "Handle thickness (flat)", "float", 4.0, 1.5, 12, "mm"),
     ParamSpec("grip_diameter", "Grip diameter", "float", 32.0, 24, 55, "mm"),
     ParamSpec("length", "Grip length", "float", 100.0, 60, 170, "mm"),
     ParamSpec("grooves", "Finger grooves", "int", 4, 0, 6, ""),
     ParamSpec("screw_diameter", "Screw size (M)", "float", 3.0, 2, 5, "mm", "Metric screw diameter used to clamp the halves."),
     CLEARANCE],
    build_utensil_grip, ["fork", "spoon", "cutlery", "utensil", "eating", "toothbrush", "thick handle", "grip for fork", "knife"], ["dexterity", "eating"]))


# ------------------------------------------------------------------------------------ clip-on palm band
def build_palm_band(p: dict) -> BuildResult:
    notes: list[str] = []
    clr = p["clearance"]
    T = p["wall_thickness"]
    IL, IH = p["palm_width"] + 10.0, p["palm_thickness"] + 8.0
    W = p["band_width"]
    want_ring, fork, want_tube = p["cap_opener"], p["fork_holder"], p["pen_tube"]

    # --- feature sizes
    r_tip = (p["cap_diameter"] + clr) / 2
    r_root = r_tip + 1.8
    RO = r_root + 5.4
    pocket_d = p["pocket_depth"]
    slit_w, slit_h = p["handle_thickness"] + clr, p["handle_width"] + clr
    tun_w, tun_t = p["handle_width"] + clr, p["handle_thickness"] + clr
    if want_ring and W < 2 * (RO + 0.8) + 0.4:
        W = 2 * (RO + 0.8) + 0.4
        notes.append(f"Band width raised to {W:.1f} mm so the cap-opener ring fits across the band.")
    if fork == "slit" and slit_h > W - 16:
        slit_h = W - 16
        notes.append(f"Fork slit height limited to {slit_h:.1f} mm by the band width; widen the band for a wider handle.")
    if fork == "tunnel" and tun_w > W - 10:
        tun_w = W - 10
        notes.append(f"Fork tunnel width limited to {tun_w:.1f} mm by the band width; widen the band for a wider handle.")

    # --- band length needed to fit the features side by side on the palm side
    out_half = (slit_w / 2 + 8.5 if fork == "slit" else tun_w / 2 + 5.0)
    out_half = max(out_half, 12.0)
    base_half = out_half + 5.0
    a = RO + 4.5 if want_ring else 0.0
    b = (a + RO + 0.8 + 4.0 + base_half) if want_ring else (base_half + 8.0)
    need_OL = (b + base_half + 8.0) if fork != "none" else (a + RO + 8.0)
    OL = IL + 2 * T
    if OL < need_OL:
        OL = need_OL
        IL = OL - 2 * T
        notes.append(f"Band lengthened to {OL:.1f} mm outside so the cap opener and utensil holder fit side by side (palm opening {IL:.1f} mm).")
    OH = IH + 2 * T
    R_O = min(20.0, OH / 2 - 1.0)
    R_I = max(R_O - 4.0, 3.0)
    y_bot = -OH / 2

    # --- C-shaped (or closed) band
    band2d = g.rrect(OL, OH, R_O) - g.rrect(IL, IH, R_I)
    gap = 0.0
    if p["clip"]:
        gap = min(p["palm_thickness"] + 14.0, IL * 0.62)
        band2d = band2d - g.rect(gap, 20, center=False).translate([-gap / 2, OH / 2 - 14])
        band2d = band2d.offset(-1.4, JoinType.Round, 2.0, 48).offset(1.4, JoinType.Round, 2.0, 48)
    band = Manifold.extrude(band2d, W)

    adds, cuts = [band], []
    ring_x = -OL / 2 + a
    cz = W / 2
    if want_ring:
        th = np.linspace(0, TAU, 28 * 14, endpoint=False)
        rr = RO + 0.8 * np.cos(28 * th)
        knurl = g.poly(np.c_[rr * np.cos(th), rr * np.sin(th)])
        th2 = np.linspace(0, TAU, 24 * 14, endpoint=False)
        rp = r_tip + 0.9 + 0.9 * np.cos(24 * th2)
        pocket2d = g.poly(np.c_[rp * np.cos(th2), rp * np.sin(th2)])
        y_face = y_bot - pocket_d
        adds.append(g.along_y(Manifold.extrude(knurl, abs(y_face) - 10.0).translate([0, 0, 10.0]), ring_x, cz))
        cuts.append(g.along_y(Manifold.extrude(pocket2d, pocket_d + 4).translate([0, 0, -y_bot]), ring_x, cz))   # floor at the band's outer surface
    if fork != "none":
        bx = ring_x + RO + 0.8 + 4.0 + base_half if want_ring else -OL / 2 + base_half + 8.0
        if fork == "slit":
            y_face = y_bot - pocket_d if want_ring else y_bot - 16.0
            depth = abs(y_face) - abs(y_bot) + 2.0
            blk = g.poly([(bx - base_half, y_face), (bx + base_half, y_face), (bx + base_half + 3, -10), (bx - base_half - 3, -10)])
            blk = g.poly([(bx - out_half, y_face), (bx + out_half, y_face), (bx + base_half, -10), (bx - base_half, -10)])
            adds.append(Manifold.extrude(blk, W))
            cuts.append(g.box(bx - slit_w / 2, bx + slit_w / 2, y_face - 1, y_face + depth + 1, cz - slit_h / 2, cz + slit_h / 2))
        else:
            y_face = y_bot - (1.5 + tun_t + 5.0)
            blk = g.poly([(bx - out_half, y_face), (bx + out_half, y_face), (bx + base_half, -10), (bx - base_half, -10)])
            adds.append(Manifold.extrude(blk, W))
            cuts.append(g.box(bx - tun_w / 2, bx + tun_w / 2, y_bot - 1.5 - tun_t, y_bot - 1.5, cz - W / 2 - 1, cz + W / 2 + 1))
    tube_bore = None
    if want_tube:
        TB = (p["pen_diameter"] + clr) / 2
        TR = TB + 3.5
        TX = OL / 2 + TB + 0.2
        adds.append(g.cyl(TR, W).translate([TX, 0, 0]))
        adds.append(g.box(OL / 2 - 4.5, TX, -6.0, 6.0, 0, W))
        cuts.append(g.cyl(TB, W + 2, -1).translate([TX, 0, 0]))
    inner_open = Manifold.extrude(g.rrect(IL, IH, R_I), W + 2).translate([0, 0, -1])
    if p["clip"]:
        inner_open = inner_open + g.box(-gap / 2, gap / 2, 0, OH, -1, W + 1)
    body = g.union(adds) - inner_open
    for c in cuts:
        body = body - c
    feats = []
    if want_ring:
        feats.append(f"Cap opener: ring on the palm side, blind pocket {pocket_d:g} mm deep with 24 inner ridges (tips {2 * r_tip:.1f} mm, roots {2 * r_root:.1f} mm) for a {p['cap_diameter']:g} mm cap.")
    if fork == "slit":
        feats.append(f"Utensil slit beside the cap opener: {slit_w:.1f} x {slit_h:.1f} mm opening, push the flat handle end in; the utensil then points straight out from the palm.")
    elif fork == "tunnel":
        feats.append(f"Utensil tunnel beside the cap opener: {tun_w:.1f} x {tun_t:.1f} mm, slide the handle through along the band axis.")
    if want_tube:
        feats.append(f"Pen tube on the thumb-side end: {2 * TB:.1f} mm bore, {W:.0f} mm long.")
    return BuildResult(
        {"palm-band": body}, notes=notes,
        print_notes=["Print standing on its edge, as supplied (band axis along Z). The tunnel and tube are vertical; expect a little support (about a tenth of the plastic) under the hand pocket.",
                     "Supports are only needed for the cap-opener ring and the arch at the top of its pocket." if want_ring else "No supports needed.",
                     ("Use TPU 95A: the lips must flex to snap over the hand. PETG is too stiff and can crack." if p["clip"] else "TPU 95A is comfortable against the skin; PETG works for a rigid loop."),
                     "3 walls, 15-20% infill."],
        fit_notes=feats + [f"Palm opening {IL:.0f} x {IH:.0f} mm for a hand about {p['palm_width']:g} mm wide and {p['palm_thickness']:g} mm thick."
                           + (f" The back-of-hand gap is {gap:.0f} mm." if p["clip"] else "")],
        derived={"outer_length_mm": OL, "outer_height_mm": OH, "band_width_mm": W, "gap_mm": gap})


register(PartSpec(
    "palm-band", "Clip-on palm band",
    "A flexible band that clips onto the hand and carries a bottle-cap opener, a fork/spoon holder and a pen tube.",
    "Weak grip, arthritis, tremor: opening bottles, eating and writing without a tight grip",
    [ParamSpec("palm_width", "Palm width", "float", 85.0, 70, 115, "mm", "Measure across the knuckles with the hand flat."),
     ParamSpec("palm_thickness", "Palm thickness", "float", 30.0, 22, 48, "mm", "Measure the thickness of the hand at the knuckles."),
     ParamSpec("band_width", "Band width", "float", 48.0, 36, 70, "mm", "Raised automatically if the cap-opener ring needs more."),
     ParamSpec("wall_thickness", "Band wall thickness", "float", 6.0, 4, 9, "mm"),
     ParamSpec("clip", "Open clip (snaps on)", "bool", True, unit="", help="Off makes a closed loop you slide the hand into."),
     ParamSpec("cap_opener", "Cap opener ring", "bool", True, unit=""),
     ParamSpec("cap_diameter", "Cap diameter", "float", 31.0, 24, 50, "mm", "Outside diameter of the bottle cap (about 30-31 mm for PET bottles)."),
     ParamSpec("pocket_depth", "Cap pocket depth", "float", 16.0, 10, 24, "mm"),
     ParamSpec("fork_holder", "Utensil holder", "enum", "slit", unit="", choices=["slit", "tunnel", "none"], help="'slit' is a push-in slot, 'tunnel' lets the handle slide through the band."),
     ParamSpec("handle_width", "Utensil handle width", "float", 20.0, 8, 32, "mm"),
     ParamSpec("handle_thickness", "Utensil handle thickness", "float", 5.0, 2, 10, "mm"),
     ParamSpec("pen_tube", "Pen tube", "bool", True, unit=""),
     ParamSpec("pen_diameter", "Pen barrel diameter", "float", 10.2, 6, 16, "mm"),
     CLEARANCE],
    build_palm_band, ["band", "palm", "clip on", "clip-on", "hand band", "strap", "multi", "opener and fork", "bottle opener", "grip band",
                      "bottle cap opener", "hold fork", "hold pen", "palm", "wrist band", "multi-tool", "all three"], ["grip", "multi"]))
