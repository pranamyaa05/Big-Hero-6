"""Material profiles, the overhang survey, and how both reach validation, estimates and the designer's prompt."""
import pytest
import trimesh
from manifold3d import Manifold

from app import parts
from app.config import Settings
from app.engine import build_pieces, estimate, make_meshes
from app.geom import to_trimesh
from app.planner import Request, request_content
from app.printability import MATERIALS, named, overhang_survey, overhang_warnings, profile_for
from app.spec import BuildResult


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def survey(man, material="pla"):
    return overhang_survey(to_trimesh(man), profile_for(material))


def test_profiles_pick_up_names_and_aliases():
    assert profile_for("PETG please").key == "petg"
    assert profile_for("pet-g").key == "petg"
    assert profile_for("flexible, rubber-like").key == "tpu"
    assert profile_for("ASA for outdoors").key == "abs"
    assert profile_for("nylon").key == "nylon"
    assert profile_for("").key == "pla" and profile_for(None).key == "pla"
    assert profile_for("something soft").key == "tpu"
    assert profile_for("Durable").key == "petg" and named("Durable") and profile_for("Flexible and grippy").key == "tpu" and not named("No preference")
    assert not named("") and not named("whatever you have") and named("PLA")
    assert profile_for("platinum finish").key == "pla" and not named("platinum finish")      # a word that only contains a material name


def test_material_inside_a_description_needs_an_explicit_name():
    from app.printability import stated_material
    assert stated_material("please print it in PETG, thanks") == "petg"
    assert stated_material("TPU if possible") == "tpu"
    assert stated_material("a soft grip for my pet's lead") == ""
    assert stated_material("platinum plated") == "" and stated_material("") == ""
    assert profile_for("pet bottle").key == "pla"


def test_every_material_has_usable_numbers():
    for m in MATERIALS.values():
        assert 0.9 < m.density < 1.4 and m.speed > 0 and 0.5 < m.min_wall < 2 and 0 < m.max_overhang_share < 0.5
        assert m.rules.startswith("Material:") and m.notes


def test_a_plain_block_has_no_overhang():
    s = survey(box(0, 30, 0, 20, 0, 10))
    assert s["overhang_mm2"] == 0 and s["overhang_share"] == 0


def roof(span):
    """A roof `span` mm wide held by two walls, 40 mm long."""
    return box(0, span + 6, 0, 40, 10, 13) + box(0, 3, 0, 40, 0, 10) + box(span + 3, span + 6, 0, 40, 0, 10)


def test_a_wide_flat_roof_is_a_bridge_problem_and_a_short_one_is_not():
    assert survey(roof(40))["flat_ceiling_mm2"] > 1000
    assert survey(roof(8))["flat_ceiling_mm2"] == 0
    assert survey(roof(15), "pla")["flat_ceiling_mm2"] == 0 and survey(roof(30), "pla")["flat_ceiling_mm2"] > 0
    # TPU and PETG tolerate less span than PLA
    assert survey(roof(12), "pla")["flat_ceiling_mm2"] == 0 and survey(roof(12), "tpu")["flat_ceiling_mm2"] > 0
    assert survey(roof(22), "pla")["flat_ceiling_mm2"] == 0 and survey(roof(22), "petg")["flat_ceiling_mm2"] > 0


def test_a_shelf_held_on_one_side_is_judged_more_strictly_than_a_bridge():
    stem = box(-5, 5, -5, 5, 0, 20)
    shelf = stem + box(-5, 20, -5, 5, 20, 24)                  # reaches 15 mm out on one side only
    assert survey(shelf)["flat_ceiling_mm2"] > 0
    lip = stem + box(-5, 8, -5, 5, 20, 24)                     # 3 mm lip: fine
    assert survey(lip)["flat_ceiling_mm2"] == 0


def test_a_steep_overhang_counts_but_a_gentle_slope_does_not():
    stem = box(-5, 5, -5, 5, 0, 20)
    arm = Manifold.cube([40, 10, 4]).translate([-20, -5, 20])                         # sticks out sideways: its underside is a 90 degree overhang
    t_shape = stem + arm
    assert survey(t_shape)["overhang_mm2"] > 200
    cone = Manifold.cylinder(20, 15, 5, 64)                                           # wide at the bottom: nothing overhangs
    assert survey(cone)["overhang_mm2"] == 0


def test_the_survey_suggests_a_better_orientation():
    stem = box(-5, 5, -5, 5, 0, 20)
    arm = box(-20, 20, -5, 5, 20, 24)
    s = survey(stem + arm)
    assert s["best"]["overhang_mm2"] <= s["overhang_mm2"]
    flipped = survey((stem + arm).rotate([180, 0, 0]))
    assert flipped["overhang_mm2"] == s["best"]["overhang_mm2"] or flipped["overhang_mm2"] < 200


def test_warnings_are_quiet_for_small_overhang_and_name_the_remedy_for_large():
    block = survey(box(0, 30, 0, 20, 0, 10))
    assert overhang_warnings(block, MATERIALS["pla"]) == []
    t = survey(box(-5, 5, -5, 5, 0, 20) + box(-30, 30, -5, 5, 20, 24))
    msgs = overhang_warnings(t, MATERIALS["pla"])
    assert msgs and "support" in msgs[0]
    assert "TPU" in overhang_warnings(t, MATERIALS["tpu"])[0]


def test_tpu_is_stricter_than_pla():
    assert MATERIALS["tpu"].max_overhang_share < MATERIALS["pla"].max_overhang_share
    assert MATERIALS["tpu"].min_wall > MATERIALS["pla"].min_wall


def test_validation_report_carries_overhang_and_material(tmp_path):
    s = Settings(data_dir=tmp_path) if "data_dir" in Settings.__dataclass_fields__ else Settings()
    t = box(-5, 5, -5, 5, 0, 20) + box(-30, 30, -5, 5, 20, 24)
    meshes, reps = make_meshes(BuildResult({"t": t}), s, "PETG")
    assert reps[0]["material"] == "PETG" and reps[0]["overhang_pct"] > 10
    assert any("support" in w for w in reps[0]["warnings"])
    _, plain = make_meshes(BuildResult({"b": box(0, 30, 0, 20, 0, 10)}), s)
    assert plain[0]["material"] == "PLA" and plain[0]["overhang_pct"] == 0 and plain[0]["warnings"] == []


def test_estimate_follows_the_material():
    tm = to_trimesh(box(0, 40, 0, 40, 0, 20))
    pla, petg, tpu, abs_ = (estimate({"p": tm}, m) for m in ("", "PETG", "TPU", "ABS"))
    assert pla["material"] == "PLA" and petg["material"] == "PETG" and tpu["material"] == "TPU" and abs_["material"] == "ABS"
    assert petg["filament_g"] > pla["filament_g"] > abs_["filament_g"]
    assert tpu["print_minutes"] > 2 * pla["print_minutes"] * 0.8 and tpu["print_minutes"] > pla["print_minutes"]
    assert pla["filament_g"] > 0 and pla["solid_g"] >= pla["filament_g"]


def test_the_designer_is_told_the_material_rules_only_when_one_is_named():
    plain = request_content(Request(description="a handle for my cup"), 0)
    petg = request_content(Request(description="a handle for my cup", material="PETG"), 0)
    text = lambda blocks: " ".join(b.get("text", "") for b in blocks)
    assert "Material:" not in text(plain)
    assert "Material: PETG" in text(petg)
    unknown = request_content(Request(description="a handle", material="whatever you have"), 0)
    assert "Material:" not in text(unknown)


def test_every_template_prints_without_a_flood_of_support_warnings():
    """Support warnings on a catalogue part would look like a defect in the demo, so only known cases may warn, and only about overhang."""
    allowed = {"wing-cap"}                      # printed bore end down: the bore roof is a real bridge, and its print notes say so
    for pid in parts.REGISTRY:
        result, _, _ = build_pieces(pid, {})
        _, reps = make_meshes(result, Settings())
        for r in reps:
            for w in r["warnings"]:
                assert pid in allowed and "support" in w, (pid, w)
