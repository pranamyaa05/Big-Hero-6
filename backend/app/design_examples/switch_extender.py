# request: The rocker light switch is flush with the wall plate and I cannot push it with my arthritic fingers. The rocker is 33 mm wide, 66 mm tall and stands 9 mm proud.
# who: weak grip or arthritis
# idea: a shell slips over the rocker and carries two big raised pads, one for each half of the rocker, so a palm or the back of a wrist can toggle it.
# key sizes: rocker 33 x 66 x 9 mm (user), all fitting the real switch; the fit test is just the open rim, so the fit can be checked in minutes


def _opening(rocker_w, rocker_h, proud, clearance):
    return rocker_w + 2 * clearance, rocker_h + 2 * clearance, proud + clearance


def build(rocker_w=33.0, rocker_h=66.0, proud=9.0, clearance=0.4, wall=2.4):
    top, r = 3.0, 3.0                                    # top plate thickness, edge radius
    cw, ch, cd = _opening(rocker_w, rocker_h, proud, clearance)
    ox, oy, oz = cw / 2 + wall, ch / 2 + wall, cd + top  # outside half-sizes and height
    # round the outside, but extend the rounded box below z = 0 and slice it off so the open rim keeps its full wall thickness
    outer = rounded_box(-ox, ox, -oy, oy, -r, oz, r) ^ box(-ox - 1, ox + 1, -oy - 1, oy + 1, 0, oz + 1)
    shell = outer - box(-cw / 2, cw / 2, -ch / 2, ch / 2, -1, cd)
    # two pads, upper and lower, sunk 1 mm into the top plate so they fuse with it; placed relative to the rocker height
    pad_h = oy - 3.0 - 1.5                                # each pad runs almost to the edge, so no wide strip of the top plate hangs in the air when printed upside down
    pads = [rounded_box(-18, 18, y0, y0 + pad_h, oz - 1, oz + 6, r) for y0 in (3.0, -3.0 - pad_h)]
    # print it upside down: the pads on the bed, the open rim pointing up, so the roof of the cavity never has to bridge
    return {"switch-extender": union([shell] + pads).rotate([180, 0, 0])}


def fit_test(rocker_w=33.0, rocker_h=66.0, proud=9.0, clearance=0.4, wall=2.4):
    # only the rim that slips over the rocker, 4 mm tall: about five minutes to print
    cw, ch, _ = _opening(rocker_w, rocker_h, proud, clearance)
    return box(-cw / 2 - wall, cw / 2 + wall, -ch / 2 - wall, ch / 2 + wall, 0, 4) - box(-cw / 2, cw / 2, -ch / 2, ch / 2, -1, 5)
