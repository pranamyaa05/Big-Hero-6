"""The extended parts library: every new part is registered with a complete spec, builds, responds to every parameter,
and is picked by the offline planner for the kind of request it exists for (so a fallback never hands back a weird template)."""
import warnings
import pytest
from app import parts as registry
from app.config import Settings
from app.engine import build_pieces, make_meshes
from app import geom as g
from app.planner import RulePlanner, Request, parse_measurements

warnings.filterwarnings("ignore", category=RuntimeWarning)
SETTINGS = Settings(bed_x=220, bed_y=220, bed_z=250)

NEW = ["door-handle-adapter", "switch-extender", "zipper-pull", "button-hook", "card-holder", "pill-funnel", "cable-clip", "drawer-pull",
       "can-tab-lifter", "plug-puller", "keyguard", "button-dots", "step-marker", "cane-table-clip", "pump-pusher", "keyhole-guide",
       "key-id-grip", "sound-horn", "label-holder", "bag-handle", "chair-hook", "plate-guard", "pill-popper", "book-stand", "cup-handle"]

CASES = [
 ("My mum can't turn the round door knob, arthritis. Knob is 5 cm across", "door-handle-adapter"),
 ("I want a lever for our bathroom door knob", "door-handle-adapter"),
 ("extend the light switch so my son in a wheelchair can reach it", "switch-extender"),
 ("long paddle for a toggle switch on the wall", "switch-extender"),
 ("broken zipper pull on my jacket, tab is 8mm", "zipper-pull"),
 ("big loop for the zip on dad's coat, he can't pinch it", "zipper-pull"),
 ("help my grandfather do up his shirt buttons with one hand", "button-hook"),
 ("button hook for tiny buttons", "button-hook"),
 ("holder for playing cards, my grandma can't hold a fan of cards", "card-holder"),
 ("stand that keeps a stack of bank cards upright", "card-holder"),
 ("funnel so I can put pills back in the pill bottle without spilling, tremor", "pill-funnel"),
 ("pill guide to pour tablets into my weekly organiser", "pill-funnel"),
 ("clip to keep my charger cable from falling off the desk", "cable-clip"),
 ("tidy the power cord along the wall so nobody trips", "cable-clip"),
 ("new handle for my kitchen drawer, the small knob is hard to grip, holes are 96 mm apart", "drawer-pull"),
 ("cupboard handle that's easy to pull open with arthritis", "drawer-pull"),

 ("can't open drinks cans, I can't get my fingernail under the ring pull", "can-tab-lifter"),
 ("something to lift the tab on a soda can with arthritis", "can-tab-lifter"),
 ("my dad can't pull the plug out of the wall socket, grip is weak", "plug-puller"),
 ("easier way to unplug the kettle, plug is 5 cm wide", "plug-puller"),
 ("tremor means I hit the wrong keys on the numpad", "keyguard"),
 ("guard for my calculator keys so my hand doesn't press the neighbours", "keyguard"),
 ("mark the start button on the microwave so my blind mum can feel it", "button-dots"),
 ("raised dots on the remote control buttons for low vision", "button-dots"),
 ("grandad can't see the edge of the garden steps, he trips", "step-marker"),
 ("mark the edge of the stairs so they can be seen and felt", "step-marker"),
 ("my walking stick keeps falling off the table at the cafe", "cane-table-clip"),
 ("holder to park my cane on the edge of a desk", "cane-table-clip"),
 ("the hand soap pump is too hard to press with arthritis", "pump-pusher"),
 ("wide pad for the lotion pump dispenser so I can push it with my palm", "pump-pusher"),
 ("can't find the keyhole in the dark, front door lock, low vision", "keyhole-guide"),
 ("guide so my key goes in the lock, my hand shakes", "keyhole-guide"),
 ("I can't tell my keys apart, I'm nearly blind", "key-id-grip"),
 ("big grip on my house key and a shape so I know which key it is", "key-id-grip"),
 ("my grandmother is hard of hearing and can't hear her phone", "sound-horn"),
 ("make phone calls louder without a hearing aid", "sound-horn"),
 ("my dad has dementia, label the kitchen cupboards with pictures", "label-holder"),
 ("picture cards for each drawer because of aphasia", "label-holder"),
 ("shopping bags cut into my hands, arthritis", "bag-handle"),
 ("handle to carry heavy plastic carrier bags", "bag-handle"),
 ("I need somewhere to hang my bag on my wheelchair", "chair-hook"),
 ("hook for the frame of my rollator, tube is 25 mm", "chair-hook"),
 ("after my stroke I can only use one hand and food keeps sliding off the plate", "plate-guard"),
 ("a plate guard to push food against", "plate-guard"),
 ("I can't push tablets out of the blister pack", "pill-popper"),
 ("press pills out of foil strips with arthritis", "pill-popper"),
 ("hold my cookbook open while I cook, I can't hold it", "book-stand"),
 ("reading stand for in bed", "book-stand"),
 ("my mug has no handle and it's too hot and heavy to hold", "cup-handle"),
 ("clip on handle for a glass tumbler", "cup-handle"),
 # old parts must still win their own requests
 ("grip for opening jars, arthritis", "jar-grip"),
 ("rubber tip for my cane", "cane-tip"),
 ("make the oven dial easy to feel, low vision", "dial-marker"),
 ("tap lever for my kitchen faucet", "lever-wing"),
 ("make my key easier to turn", "key-turner"),
 ("easier to grip fork and spoon for tremor", "utensil-grip"),
 ("braille label for the spice jars", "braille-tag"),
 ("thicker pen grip for writing with arthritis", "pen-grip"),
 ("bottle cap that is easy to twist open", "wing-cap"),
]

CONTEXT = {"button-dots": {"dot_count": 3}}


def signature(part_id, params):
    result, _, _ = build_pieces(part_id, params)
    return tuple(sorted((n, round(m.volume(), 1), tuple(round(x, 1) for x in (m.bounding_box()[3] - m.bounding_box()[0], m.bounding_box()[4] - m.bounding_box()[1], m.bounding_box()[5] - m.bounding_box()[2])))
                        for n, m in result.pieces.items()))


def test_all_new_parts_are_registered():
    assert set(NEW) <= set(registry.REGISTRY)
    assert len(registry.REGISTRY) >= 11 + len(NEW)


@pytest.mark.parametrize("part_id", NEW)
def test_spec_is_complete_and_sensible(part_id):
    spec = registry.get(part_id)
    assert spec.name and len(spec.summary) > 30 and spec.helps and spec.tags and len(spec.keywords) >= 6
    for p in spec.params:
        assert p.label and p.name
        if p.kind in ("float", "int"):
            assert p.min is not None and p.max is not None and p.min < p.max, p.name
            assert p.min <= p.default <= p.max, f"{part_id}.{p.name} default {p.default} outside {p.min}..{p.max}"
            assert p.unit is not None
        if p.kind == "enum":
            assert p.default in p.choices
    assert len({p.name for p in spec.params}) == len(spec.params)


@pytest.mark.parametrize("part_id", NEW)
def test_builds_with_notes_and_expected_pieces(part_id):
    result, resolved, _ = build_pieces(part_id, {})
    meshes, reports = make_meshes(result, SETTINGS)
    assert set(result.pieces) == {part_id}
    assert result.print_notes and result.fit_notes and result.derived
    for r in reports:
        assert r["ok"] and r["watertight"] and r["bodies"] == 1, (part_id, r)
        assert not any("larger than the configured print bed" in w for w in r["warnings"]), (part_id, r["warnings"])


@pytest.mark.parametrize("part_id", NEW)
def test_every_parameter_changes_the_geometry(part_id):
    """A parameter that does nothing is a bug: it would let a user type a measurement that the part ignores."""
    spec = registry.get(part_id)
    base = signature(part_id, {})
    for p in spec.params:
        if p.kind in ("float", "int"):
            ctx = CONTEXT.get(part_id, {})                    # a few parameters only matter in a particular setup (spacing needs 2+ dots)
            lo, hi = signature(part_id, {**ctx, p.name: p.min}), signature(part_id, {**ctx, p.name: p.max})
            assert lo != hi, f"{part_id}.{p.name} has no effect between its minimum and maximum"
        elif p.kind == "bool":
            assert signature(part_id, {p.name: True}) != signature(part_id, {p.name: False}), f"{part_id}.{p.name} has no effect"
        elif p.kind == "enum":
            assert len({signature(part_id, {p.name: c}) for c in p.choices}) == len(p.choices), f"{part_id}.{p.name}: two choices give the same part"


@pytest.mark.parametrize("part_id", NEW)
def test_out_of_range_values_are_clamped_and_reported(part_id):
    spec = registry.get(part_id)
    p = next(p for p in spec.params if p.kind == "float")
    result, resolved, notes = build_pieces(part_id, {p.name: p.max * 10})
    assert resolved[p.name] == p.max and any("maximum" in n for n in notes)


def test_fit_dimension_shows_up_in_the_geometry():
    """The measurement the user types must be the size the part actually has."""
    r, _, _ = build_pieces("door-handle-adapter", {"knob_diameter": 40, "clearance": 0.0})
    assert r.derived["bore_diameter_mm"] == pytest.approx(40.0)
    r, _, _ = build_pieces("zipper-pull", {"tab_width": 10, "tab_thickness": 2.5, "clearance": 0.0})
    assert r.derived["slot_width_mm"] == pytest.approx(10.0) and r.derived["slot_thickness_mm"] == pytest.approx(2.5)
    r, _, _ = build_pieces("cable-clip", {"cable_diameter": 8, "clearance": 0.0})
    assert r.derived["ring_inner_diameter_mm"] == pytest.approx(8.0)
    r, _, _ = build_pieces("drawer-pull", {"hole_spacing": 128})
    assert r.derived["hole_spacing_mm"] == 128
    r, _, _ = build_pieces("pill-funnel", {"opening_diameter": 20, "clearance": 0.0})
    assert r.derived["spout_diameter_mm"] == pytest.approx(20.0)
    r, _, _ = build_pieces("plug-puller", {"plug_width": 52, "plug_height": 40, "clearance": 0.0})
    assert r.derived["pocket_width_mm"] == pytest.approx(52.0) and r.derived["pocket_height_mm"] == pytest.approx(40.0)
    r, _, _ = build_pieces("keyhole-guide", {"lock_diameter": 24, "clearance": 0.0})
    assert r.derived["hole_diameter_mm"] == pytest.approx(24.0)
    r, _, _ = build_pieces("pump-pusher", {"head_diameter": 40, "clearance": 0.0})
    assert r.derived["cap_diameter_mm"] == pytest.approx(40.0)
    r, _, _ = build_pieces("cane-table-clip", {"cane_diameter": 22, "table_thickness": 30, "clearance": 0.0})
    assert r.derived["cane_ring_diameter_mm"] == pytest.approx(22.0) and r.derived["table_gap_mm"] == 30.0














@pytest.mark.parametrize("text,want", CASES)
def test_the_planner_picks_the_right_part(text, want):
    plan = RulePlanner().plan(Request(description=text, who_for=""))
    assert plan.part_id == want


@pytest.mark.parametrize("text", ["a stand for my guitar", "toy dinosaur for my nephew", "coaster for my cup", "a ramp for my wheelchair",
                                  "bookend", "soap dish for the shower",
                                  # words that sound like a part's keywords but ask for something else must not pick that part
                                  "replace the hinge on my cupboard door", "phone stand for video calls, tremor", "handle for my fridge door",
                                  "a lid for my box", "a handle for my saucepan lid", "extend my crutch handle", "cupboard door keeps swinging shut",
                                  # things that name a person's condition or a loose word but no object a part fits
                                  "ramp for my wheelchair, carries 150 kg", "camera mount for my wheelchair", "handle for my razor, arthritis", "bag for my walker",
                                  "knob for the microwave remote", "switch for blowing through a straw", "strap for my glasses", "stair railing for my dad",
                                  "cuff for my garden trowel", "hearing aid battery box", "frame for my picture",
                                  "pen stand for desk", "walker tray for meals", "wheelchair cup holder"])
def test_requests_outside_the_catalog_get_no_part_rather_than_a_random_one(text):
    plan = RulePlanner().plan(Request(description=text, who_for=""))
    assert plan.part_id is None and plan.warnings


@pytest.mark.parametrize("text,part,expect", [
    ("round door knob that is 5 cm across", "door-handle-adapter", {"knob_diameter": 50}),
    ("zipper tab 8 mm wide", "zipper-pull", {"tab_width": 8}),
    ("charger cable 6 mm thick", "cable-clip", {"cable_diameter": 6}),
    ("holes are 96 mm apart", "drawer-pull", {"hole_spacing": 96}),
    ("the plug is 52 mm wide", "plug-puller", {"plug_width": 52}),
    ("lock face is 24 mm across", "keyhole-guide", {"lock_diameter": 24}),
    ("pump head 40 mm wide", "pump-pusher", {"head_diameter": 40}),
    ("table edge is 28 mm thick", "cane-table-clip", {"table_thickness": 28}),
    ("bottle opening 3/4 inch", "pill-funnel", {"opening_diameter": 19.05}),
])
def test_measurements_are_read_from_the_request(text, part, expect):
    got = parse_measurements(text, part)
    for k, v in expect.items():
        assert got.get(k) == pytest.approx(v, abs=0.1), (text, got)





def test_keyguard_has_one_hole_per_key_at_the_pitch():
    r, _, _ = build_pieces("keyguard", {"columns": 4, "rows": 3, "key_pitch_x": 20, "key_pitch_y": 18, "margin": 8})
    assert r.derived["hole_count"] == 12
    assert r.derived["overall_width_mm"] == pytest.approx(4 * 20 + 16) and r.derived["overall_height_mm"] == pytest.approx(3 * 18 + 16)
    few, _, _ = build_pieces("keyguard", {"columns": 1, "rows": 1})
    many, _, _ = build_pieces("keyguard", {"columns": 8, "rows": 6})
    assert many.pieces["keyguard"].genus() - few.pieces["keyguard"].genus() == 47          # one more through-hole per extra key


def test_keyguard_prints_with_the_plate_on_the_bed():
    r, _, _ = build_pieces("keyguard", {})
    m, _ = make_meshes(r, SETTINGS)
    z = m["keyguard"].vertices[:, 2]
    assert z.min() == pytest.approx(0.0, abs=1e-6)
    footprint_at_bed = (z < 0.01).sum()
    assert footprint_at_bed > 100                       # the plate (not just a thin rim) touches the bed: nothing bridges


def test_tactile_dots_are_tall_enough_to_feel_and_count_matches():
    r, _, _ = build_pieces("button-dots", {"dot_count": 3, "dot_height": 1.6})
    assert r.pieces["button-dots"].bounding_box()[5] == pytest.approx(1.0 + 1.6, abs=0.1)      # 1 mm backing plus the dot
    a, _, _ = build_pieces("button-dots", {"dot_count": 1})
    b, _, _ = build_pieces("button-dots", {"dot_count": 4})
    assert b.pieces["button-dots"].volume() > 3 * a.pieces["button-dots"].volume() * 0.9


def test_can_tab_lifter_blade_is_thinner_than_the_gap_under_a_tab():
    r, _, _ = build_pieces("can-tab-lifter", {})
    assert r.derived["blade_thickness_mm"] < 2.5
    over, _, notes = build_pieces("can-tab-lifter", {"blade_thickness": 5})
    assert over.derived["blade_thickness_mm"] <= 2.2 and any("maximum" in n for n in notes)       # cannot be set thicker than the tab gap


def test_step_marker_ridges_follow_length_and_pitch():
    r, _, _ = build_pieces("step-marker", {"length": 200, "ridge_pitch": 10})
    assert r.derived["ridge_count"] == 20
    assert r.derived["length_mm"] == 200
    assert r.pieces["step-marker"].bounding_box()[5] == pytest.approx(2.4 + 1.6, abs=0.05)


def test_the_cane_clip_ring_has_a_mouth_narrower_than_the_cane():
    """Slice the ring at mid height: its two lips at the far end must leave a gap smaller than the cane, so the cane snaps in and stays."""
    cane = 19.0
    r, _, _ = build_pieces("cane-table-clip", {"cane_diameter": cane, "clearance": 0.4})
    m = r.pieces["cane-table-clip"].rotate([90, 0, 0])               # y (height) becomes z so we can slice horizontally
    bb = m.bounding_box()
    section = m.slice((bb[2] + bb[5]) / 2)
    x0 = section.bounds()[0]
    lips = (section ^ g.rect(3.0, 200.0, center=False).translate([x0, -100.0])).decompose()
    assert len(lips) == 2, "the ring should be open at the far end"
    ys = sorted((c.bounds()[1], c.bounds()[3]) for c in lips)
    mouth = ys[1][0] - ys[0][1]
    assert 0 < mouth < cane


def test_parts_that_print_flat_are_not_bridging_over_a_pocket():
    """Lever, pad and plate parts are modelled upside down on purpose, so the wide face is the first layer and nothing hangs in the air."""
    for pid in ("door-handle-adapter", "switch-extender", "plug-puller", "pump-pusher", "keyguard"):
        r, _, _ = build_pieces(pid, {})
        m, _ = make_meshes(r, SETTINGS)
        mesh = m[pid]
        bed = mesh.vertices[:, 2] < 0.01
        # triangles lying on the bed: their total area is the footprint of the first layer
        tri_on_bed = bed[mesh.faces].all(axis=1)
        assert mesh.area_faces[tri_on_bed].sum() > 0.45 * (mesh.bounds[1][0] - mesh.bounds[0][0]) * 8, f"{pid} has almost nothing on the bed"


def _section(part_id, params, z):
    r, _, _ = build_pieces(part_id, params)
    m = list(r.pieces.values())[0]
    return m.slice(z), r


def _solid_at(section, x, y):
    return not (section ^ g.rect(0.4, 0.4).translate([x, y])).is_empty()


@pytest.mark.parametrize("part_id,params,r_fn", [("cup-handle", {"cup_diameter": 78, "clearance": 0.4, "wall": 3.5}, lambda p: p["cup_diameter"] / 2 + 0.2),
                                                  ("chair-hook", {"tube_diameter": 22, "clearance": 0.4, "wall": 4}, lambda p: p["tube_diameter"] / 2 + 0.2)])
def test_snap_on_rings_are_open_on_one_side_and_closed_on_the_other(part_id, params, r_fn):
    """A clip that is closed all round cannot be fitted; one open too wide falls off. The mouth faces +x, the handle or hook is on the -x side."""
    sec, r = _section(part_id, params, list(build_pieces(part_id, params)[0].pieces.values())[0].bounding_box()[5] / 2)
    ri = r_fn(params)
    wall = params["wall"]
    assert not _solid_at(sec, ri + wall / 2, 0), "the ring is closed on the open side"
    assert _solid_at(sec, -(ri + wall / 2), 0), "the ring has no wall on the back side"
    mouth = r.derived.get("mouth_mm")
    if mouth is not None:
        assert mouth < params["tube_diameter"]                 # narrower than the tube, so it snaps on and stays


def test_plate_guard_has_a_rim_slot_and_a_solid_wall_above_it():
    z_slot, wall_h = 8.0 + 1.0, 30.0
    slot_sec, _ = _section("plate-guard", {}, z_slot)
    wall_sec, _ = _section("plate-guard", {}, wall_h)
    assert slot_sec.area() < wall_sec.area() * 0.8             # the groove removes a big share of the wall at slot height
    assert not wall_sec.is_empty()


def test_label_holder_card_slides_in_from_the_top():
    r, _, _ = build_pieces("label-holder", {"card_width": 70, "card_height": 50, "card_thickness": 1.0, "clearance": 0.4})
    m = r.pieces["label-holder"]
    sec = m.slice(1.6 + 0.7)                                   # through the pocket layer
    oh = 50 + 0.4 + 10
    assert not _solid_at(sec, 0, 0) and not _solid_at(sec, 0, oh / 2 - 2.0)          # pocket and slot are open
    assert _solid_at(sec, -(70 + 0.4) / 2 - 2.5, 0)                                   # side wall holds the card


def test_sound_horn_widens_from_the_speaker_to_the_ear():
    r, _, _ = build_pieces("sound-horn", {"speaker_length": 14, "speaker_width": 3, "bell_diameter": 45, "horn_length": 55})
    m = r.pieces["sound-horn"]
    low, high = m.slice(3.0), m.slice(55.0)
    lo_b, hi_b = low.bounds(), high.bounds()
    assert (hi_b[2] - hi_b[0]) > 2.0 * (lo_b[2] - lo_b[0]) * 0.9 and high.num_contour() == 2     # a ring (open bore) at the bell
    assert low.num_contour() == 2                                                       # and the throat is open too


def test_bag_handle_slot_count_and_pill_popper_plunger_count():
    one, _, _ = build_pieces("bag-handle", {"loop_slots": 1})
    three, _, _ = build_pieces("bag-handle", {"loop_slots": 3})
    assert three.pieces["bag-handle"].genus() - one.pieces["bag-handle"].genus() == 2
    a, _, _ = build_pieces("pill-popper", {"plunger_count": 1})
    b, _, _ = build_pieces("pill-popper", {"plunger_count": 3})
    assert b.pieces["pill-popper"].volume() > a.pieces["pill-popper"].volume() + 2 * 3.14 * 4 ** 2 * 12 * 0.8


def test_key_id_grip_has_a_key_slot_and_a_tactile_marker():
    r, _, _ = build_pieces("key-id-grip", {"key_width": 24, "key_thickness": 2.4, "clearance": 0.0})
    m = r.pieces["key-id-grip"]
    assert r.derived["slot_width_mm"] == pytest.approx(24.0) and r.derived["slot_thickness_mm"] == pytest.approx(2.4)
    assert m.bounding_box()[5] == pytest.approx(8.0 - 0.05 + 1.4, abs=0.05)             # the marker stands about 1.4 mm proud of the paddle
    mid = m.slice(4.0)
    assert not _solid_at(mid, 70 / 2 - 5.0, 0)                                           # the slot is open where the key goes in


def test_book_stand_holds_the_book_at_the_lean_angle():
    r, _, _ = build_pieces("book-stand", {"book_thickness": 30, "angle": 70, "clearance": 0.0})
    assert r.derived["slot_width_mm"] == pytest.approx(30.0) and r.derived["angle_deg"] == 70
