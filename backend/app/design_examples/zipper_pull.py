# request: The zipper pull on my jacket is tiny and my fingers cannot grip it. The slider has a 4 mm hole I can thread a cord or split ring through.
# who: weak grip or arthritis
# idea: a big pebble-shaped paddle fills the whole hand, finger grooves stop it slipping, and a hole at the narrow end takes the cord.
# key sizes: hole 4 mm (user) + clearance; paddle 30 mm wide at the big end (assumed, fills a weak hand)


def build(hole=4.0, clearance=0.4, big=15.0, small=7.0, span=40.0, thickness=7.0):
    # big/small: radius of each end, span: distance between them; every size the user may want to change is an argument
    t = thickness
    r = t / 2                                           # fully rounded rim: no sharp edge ever touches skin
    # torus() lies round the z = 0 plane, so lift it to mid-thickness; the hull of two tori is a smooth tapered pebble
    paddle = hull([torus(big - r, r).translate([0, 0, r]), torus(small - r, r).translate([span, 0, r])])
    # five finger grooves, 1 mm deep, cut into both flat faces (kept inside the flat area so the rim stays smooth)
    xs = [-6 + 4.5 * i for i in range(5)]
    grooves = union([box(x, x + 1.6, -6, 6, -0.01, 1.0) for x in xs] + [box(x, x + 1.6, -6, 6, t - 1.0, t + 0.01) for x in xs])
    paddle = paddle - grooves
    bore = hole + 2 * clearance                         # cord or split-ring hole with clearance
    paddle = paddle - cyl(bore / 2, t + 2, -1).translate([span, 0, 0])
    return {"zipper-pull": paddle}
