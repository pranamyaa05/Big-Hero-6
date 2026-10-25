import pytest
from app.planner import LLMPlanner, Plan, Request, RulePlanner, make_plan, parse_braille_text, parse_measurements, request_content
from conftest import make_settings
from fakes import FakeClient, tool_use


@pytest.mark.parametrize("desc,dims,who,part", [
    ("My grandmother can't grip the smooth cap on her water bottle.", "neck 50 mm", "Weak grip or arthritis", "wing-cap"),
    ("Braille label that says RICE", "", "Low vision or blind", "braille-tag"),
    ("hard to turn the dial on the stove", "", "Weak grip or arthritis", "dial-marker"),
    ("old cane tip worn out", "19 mm tube", "Limited mobility", "cane-tip"),
    ("jar lid is too tight", "lid 70 mm", "Weak grip or arthritis", "jar-grip"),
    ("can't hold a pen steadily", "", "Tremor or limited dexterity", "pen-grip"),
    ("rollator feet scratch the floor", "tube 1 inch", "Limited mobility", "walker-glide"),
    ("hard to turn my door key", "", "Weak grip or arthritis", "key-turner"),
    ("the round tap is hard to turn", "", "Weak grip or arthritis", "lever-wing"),
    ("I want to open bottles, eat with a fork and write with a pen", "", "Tremor or limited dexterity", "palm-band"),
])
def test_rule_planner_picks_the_right_template(desc, dims, who, part):
    assert RulePlanner().plan(Request(description=desc, dims=dims, who_for=who)).part_id == part


def test_who_for_alone_never_picks_a_part():
    assert RulePlanner().plan(Request(description="zzzz", who_for="Weak grip or arthritis")).part_id is None


def test_measurements_units_and_roles():
    assert parse_measurements("neck 50 mm", "wing-cap") == {"neck_diameter": 50.0}
    assert parse_measurements("bottle neck is 2 inches", "wing-cap")["neck_diameter"] == pytest.approx(50.8)
    assert parse_measurements("tube 3/4 inch", "walker-glide")["tube_diameter"] == pytest.approx(19.05)
    assert parse_measurements("lid 7 cm", "jar-grip")["lid_diameter"] == 70.0
    assert parse_measurements("pen is 11 mm", "pen-grip") == {"pen_diameter": 11.0}


def test_braille_text_extraction():
    assert parse_braille_text('a label that says "SALT"') == "SALT"
    assert parse_braille_text("label that says RICE") == "RICE"


def test_llm_planner_reads_tool_call_and_params_json():
    fc = FakeClient(tool_use("choose_part", {"part_id": "wing-cap", "params_json": '{"neck_diameter": 44}', "rationale": "smooth cap", "confidence": 0.9}))
    plan = LLMPlanner(make_settings(__import__("pathlib").Path("/tmp")), fc).plan(Request(description="cap"))
    assert plan.part_id == "wing-cap" and plan.params == {"neck_diameter": 44} and plan.source == "llm"
    assert fc.calls[0]["tool_choice"] == {"type": "tool", "name": "choose_part"}


def test_llm_planner_none_and_unknown_ids(tmp_path):
    s = make_settings(tmp_path)
    for pid in ("none", "made-up"):
        p = LLMPlanner(s, FakeClient(tool_use("choose_part", {"part_id": pid, "rationale": "nothing fits", "confidence": 0.1}))).plan(Request(description="x"))
        assert p.part_id is None


def test_make_plan_falls_back_to_rules_when_the_model_fails(tmp_path):
    s = make_settings(tmp_path, enable_llm=True)
    plan = make_plan(Request(description="jar lid too tight"), s, LLMPlanner(s, FakeClient(RuntimeError("boom"))))
    assert plan.part_id == "jar-grip" and plan.source == "rules" and "unavailable" in plan.warnings[0]


def test_request_content_orders_photos_before_text():
    blocks = request_content(Request(description="d", dims="5 mm", who_for="w", photos=[("image/jpeg", b"abc")]))
    assert blocks[0]["type"] == "image" and blocks[-1]["type"] == "text" and "5 mm" in blocks[-1]["text"]
