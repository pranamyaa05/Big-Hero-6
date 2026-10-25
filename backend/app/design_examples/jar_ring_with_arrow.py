# request: Make the big jar-opening ring for a 70 mm lid, and add a raised arrow on top that shows which way to turn it.
# who: weak grip or arthritis, low vision
# idea: reuse the tested jar-grip generator through lib(), then add one custom feature to its top face.
# key sizes: lid 70 mm (user); the generator adds its own clearance


def build(lid_diameter=70.0, arrow_height=1.8):
    parts = lib("jar-grip", lid_diameter=lid_diameter)
    ring = list(parts.values())[0]
    x0, y0, z0, x1, y1, z1 = ring.bounding_box()           # find the top face rather than guessing it
    # arrow pointing anticlockwise, laid on the rim between the lid and the outer edge, sunk 0.4 mm into the top face so it fuses
    rim_r = (lid_diameter / 2 + max(x1, y1)) / 2
    arrow2d = poly([(-14, -4), (4, -4), (4, -9), (16, 0), (4, 9), (4, 4), (-14, 4)])
    arrow = extrude(arrow2d, arrow_height + 0.4, z1 - 0.4).translate([0, rim_r, 0])
    return {"jar-ring": ring + arrow}
