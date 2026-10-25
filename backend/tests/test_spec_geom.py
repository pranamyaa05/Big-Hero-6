import pytest
from app import geom as g
from app.spec import ParamError, ParamSpec
from app import parts as registry


def test_float_is_clamped_and_noted():
    p = ParamSpec("d", "Diameter", "float", 10, 5, 20, "mm")
    notes = []
    assert p.coerce(100, notes) == 20 and "above the supported maximum" in notes[0]
    assert p.coerce(1, notes) == 5 and "below the supported minimum" in notes[1]
    assert p.coerce(None, notes) == 10 and p.coerce("12.5", notes) == 12.5


def test_int_rounds_and_bad_values_raise():
    p = ParamSpec("n", "Count", "int", 3, 1, 9, "")
    assert p.coerce(4.6, []) == 5
    for bad in ("abc", float("nan"), float("inf")):
        with pytest.raises(ParamError):
            p.coerce(bad, [])


def test_enum_bool_text():
    e = ParamSpec("s", "Shape", "enum", "round", choices=["round", "flat"], unit="")
    assert e.coerce("FLAT", []) == "flat"
    with pytest.raises(ParamError):
        e.coerce("hex", [])
    b = ParamSpec("b", "Flag", "bool", False, unit="")
    assert b.coerce("yes", []) is True and b.coerce("0", []) is False
    t = ParamSpec("t", "Text", "text", "", unit="", max_length=5)
    assert t.coerce("  hi ", []) == "hi"
    with pytest.raises(ParamError):
        t.coerce("too long text", [])


def test_resolve_reports_unknown_parameters():
    spec = registry.get("wing-cap")
    resolved, notes = spec.resolve({"neck_diameter": 40, "bogus": 1})
    assert resolved["neck_diameter"] == 40 and any("bogus" in n for n in notes)


@pytest.mark.parametrize("name,solid", [
    ("twist", lambda: g.extrude(g.star(10, 7, 6), 30, twist=90)),
    ("taper", lambda: g.extrude(g.circle(10), 30, scale=0.6)),
    ("capsule", lambda: g.capsule(6, 40)),
    ("rounded_box", lambda: g.rounded_box(0, 40, 0, 20, 0, 10, 3)),
    ("torus", lambda: g.torus(15, 3)),
    ("tube", lambda: g.tube(10, 8, 20)),
    ("loft", lambda: g.loft(g.circle(10), g.rect(30, 12), 25)),
    ("round_corners", lambda: g.extrude(g.round_corners(g.rect(30, 20), 4), 5)),
    ("lathe", lambda: g.lathe([(0, 0), (10, 0), (8, 20), (0, 20)])),
])
def test_helpers_make_closed_single_solids(name, solid):
    tm = g.to_trimesh(solid())
    assert tm.is_watertight and tm.volume > 0 and len(tm.split(only_watertight=False)) == 1


def test_clockwise_polygons_are_fixed():
    cw = [(0, 0), (0, 10), (10, 10), (10, 0)]
    assert g.to_trimesh(g.extrude(g.poly(cw), 5)).volume == pytest.approx(500, rel=1e-3)


def test_sit_rests_on_the_bed():
    tm = g.sit(g.to_trimesh(g.cyl(5, 10, z0=7).translate([20, 30, 0])))
    assert tm.bounds[0][2] == pytest.approx(0) and abs(tm.bounds[0][0] + tm.bounds[1][0]) < 1e-6
