"""The design engine: code checks, the sandbox, and the model loop (with a scripted model)."""
import pytest
from app.designer import DesignError, FreeformError, design_part, run_sandboxed, to_manifolds, validate_code
from app.engine import make_meshes
from app.planner import Request
from app.spec import BuildResult
from conftest import make_settings
from fakes import FakeClient, accept, example_code, submit, tool_use

GOOD = "def build():\n    return {'plate': extrude(rrect(40, 20, 4), 6) - cyl(3, 8, -1)}"
FRAGMENTS = "def build():\n    return cyl(5, 10) + cyl(5, 10).translate([50, 0, 0])"


# ------------------------------------------------------------------ the code check
@pytest.mark.parametrize("code,fragment", [
    ("import os\ndef build():\n    return cyl(1,1)", "Import"),
    ("def build():\n    x = ().__class__\n    return cyl(1,1)", "not allowed"),
    ("def build():\n    open('/etc/passwd')\n    return cyl(1,1)", "open"),
    ("def build():\n    getattr(np, 'x')\n    return cyl(1,1)", "getattr"),
    ("def build():\n    s = '{0.__class__}'.format(1)\n    return cyl(1,1)", "format"),
    ("class A:\n    pass\ndef build():\n    return cyl(1,1)", "ClassDef"),
    ("def build():\n    with open('x') as f:\n        pass", "With"),
    ("def build():\n    return next(iter([1]))", "next"),
    ("x = 1", "build()"),
    ("def build(:", "syntax error"),
    ("", "no code"),
])
def test_validate_code_rejects(code, fragment):
    with pytest.raises(FreeformError) as e:
        validate_code(code)
    assert fragment.lower() in str(e.value).lower()


def test_validate_code_accepts_good_code():
    validate_code(GOOD)


# ------------------------------------------------------------------ the sandbox
def test_sandbox_runs_good_code(tmp_path):
    pieces = run_sandboxed(GOOD, make_settings(tmp_path), tmp_path / "o.npz")
    assert list(pieces) == ["plate"] and to_manifolds(pieces)["plate"].volume() > 1000


@pytest.mark.parametrize("code,fragment", [
    ("def build():\n    return foo(1)", "NameError"),
    ("def build():\n    return 5", "Manifold"),
    ("def build():\n    return cyl(1000, 5)", "600 mm"),
    ("def build():\n    return np.os.system('id')", "not allowed"),
    ("def build():\n    return Manifold.cube([1, 1, 1]) ^ Manifold.cube([1, 1, 1]).translate([9, 0, 0])", "empty"),
])
def test_sandbox_reports_runtime_failures_with_a_line(tmp_path, code, fragment):
    with pytest.raises(FreeformError) as e:
        run_sandboxed(code, make_settings(tmp_path), tmp_path / "o.npz")
    assert fragment in str(e.value)


def test_sandbox_error_names_the_line(tmp_path):
    with pytest.raises(FreeformError) as e:
        run_sandboxed("def build():\n    a = 1\n    return nothing_here", make_settings(tmp_path), tmp_path / "o.npz")
    assert "line 3" in str(e.value)


def test_sandbox_stops_endless_loops(tmp_path):
    s = make_settings(tmp_path, design_timeout_s=4.0)
    with pytest.raises(FreeformError) as e:
        run_sandboxed("def build():\n    while True:\n        pass", s, tmp_path / "o.npz")
    assert "seconds" in str(e.value)


def test_sandbox_environment_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "hunter2")
    with pytest.raises(FreeformError):
        run_sandboxed("def build():\n    return environ", make_settings(tmp_path), tmp_path / "o.npz")


# ------------------------------------------------------------------ bundled worked examples are real, printable designs
@pytest.mark.parametrize("name", ["zipper_pull", "switch_extender", "jar_ring_with_arrow"])
def test_examples_are_printable(name, tmp_path):
    s = make_settings(tmp_path)
    pieces = to_manifolds(run_sandboxed(example_code(name), s, tmp_path / "o.npz"))
    _, reports = make_meshes(BuildResult(pieces), s)
    assert all(r["ok"] and r["bodies"] == 1 and not r["warnings"] for r in reports), reports


def test_lib_building_blocks_are_callable(tmp_path):
    code = "def build():\n    return lib('key-turner', key_width=10)"
    assert run_sandboxed(code, make_settings(tmp_path), tmp_path / "o.npz")
    with pytest.raises(FreeformError):
        run_sandboxed("def build():\n    return lib('nope')", make_settings(tmp_path), tmp_path / "o.npz")


# ------------------------------------------------------------------ the model loop
def run_loop(tmp_path, *responses, **over):
    fc = FakeClient(*responses)
    s = make_settings(tmp_path, **over)
    return design_part(Request(description="a request"), s, tmp_path / "work", fc), fc


def test_first_try_then_review_accept(tmp_path):
    d, fc = run_loop(tmp_path, submit(GOOD), accept())
    assert d["attempts"] == 1 and d["reviewed"] and list(d["pieces"]) == ["plate"]
    assert (tmp_path / "work" / "freeform_pieces.npz").exists() and not list((tmp_path / "work").glob("attempt*.npz"))
    review = fc.calls[1]["messages"][-1]["content"][0]["content"]
    assert any(b["type"] == "image" and b["source"]["data"] for b in review), "the model must be shown a render of its own result"
    assert [t["name"] for t in fc.calls[1]["tools"]] == ["submit_design", "accept_design"]


def test_runtime_error_is_fed_back_and_fixed(tmp_path):
    d, fc = run_loop(tmp_path, submit("def build():\n    return nothing_here"), submit(GOOD), accept())
    assert d["attempts"] == 2
    fed = fc.calls[1]["messages"][-1]["content"][0]
    assert fed["is_error"] and "NameError" in fed["content"] and "line 2" in fed["content"]
    assert d["log"][0]["outcome"].startswith("failed")


def test_loose_fragments_are_fed_back(tmp_path):
    d, fc = run_loop(tmp_path, submit(FRAGMENTS), submit(GOOD), accept())
    assert "separate bodies" in fc.calls[1]["messages"][-1]["content"][0]["content"]
    assert list(d["pieces"]) == ["plate"]


def test_review_can_correct_the_design(tmp_path):
    d, _ = run_loop(tmp_path, submit(GOOD, title="first"), submit(GOOD, title="second"), accept())
    assert d["title"] == "second"


def test_a_failed_late_fix_keeps_the_last_good_design(tmp_path):
    bad = "def build():\n    return nothing_here"
    d, _ = run_loop(tmp_path, submit(GOOD, title="good"), submit(bad), submit(bad))
    assert d["title"] == "good" and not d["reviewed"]


def test_gives_up_after_the_attempt_limit(tmp_path):
    bad = "def build():\n    return nothing_here"
    with pytest.raises(DesignError) as e:
        run_loop(tmp_path, submit(bad), submit(bad), submit(bad))
    assert "3 attempt" in str(e.value) and "nothing_here" in str(e.value)


def test_declined_requests_stop_the_job(tmp_path):
    with pytest.raises(DesignError) as e:
        run_loop(tmp_path, tool_use("decline_request", {"reason": "this is a brake part"}))
    assert "declined" in str(e.value) and "brake" in str(e.value)


def test_model_outage_is_a_clean_error(tmp_path):
    with pytest.raises(DesignError) as e:
        run_loop(tmp_path, RuntimeError("connection reset"))
    assert "could not be reached" in str(e.value)


def test_model_that_forgets_the_tool_is_nudged(tmp_path):
    import types
    text_only = [types.SimpleNamespace(type="text", text="Here you go")]
    d, fc = run_loop(tmp_path, text_only, submit(GOOD), accept())
    assert d["attempts"] == 1 and "Call submit_design" in fc.calls[1]["messages"][-1]["content"]


def test_review_rounds_zero_skips_the_picture(tmp_path):
    d, fc = run_loop(tmp_path, submit(GOOD), review_rounds=0)
    assert not d["reviewed"] and len(fc.calls) == 1


def test_prompt_treats_requests_as_untrusted_and_lists_blocks(tmp_path):
    _, fc = run_loop(tmp_path, submit(GOOD), accept())
    sysmsg = fc.calls[0]["system"]
    assert "untrusted" in sysmsg and "lib('wing-cap')" in sysmsg and "example 1" in sysmsg and "def build" in sysmsg


def test_text_only_models_get_no_photos_and_a_measurement_review(tmp_path):
    fc = FakeClient(submit(GOOD), accept())
    s = make_settings(tmp_path, llm_vision=False)
    req = Request(description="a request", photos=[("image/jpeg", b"\xff\xd8not-really")])
    design_part(req, s, tmp_path / "work", fc)
    first = fc.calls[0]["messages"][0]["content"]
    assert all(b["type"] == "text" for b in first) and "cannot see images" in first[-1]["text"]
    review = fc.calls[1]["messages"][-1]["content"][0]["content"]
    assert len(review) == 1 and review[0]["type"] == "text"
    assert "40.0 x 20.0 x 6.0 mm" in review[0]["text"] and "1 through-holes" in review[0]["text"] and "accept_design" in review[0]["text"]


def test_lean_prompt_is_much_shorter_but_keeps_the_rules():
    from app.designer import system_prompt
    full, lean = system_prompt(False), system_prompt(True)
    assert len(lean) < 0.8 * len(full) and len(lean) // 4 < 3800
    for must in ("submit_design", "Overhangs", "Strength", "lib('keyguard')", "def build("):
        assert must in lean, must
    assert lean.count("--- example") == 1 and full.count("--- example") == 3


def test_a_cut_off_answer_is_fed_back_as_cut_off(tmp_path):
    d, fc = run_loop(tmp_path, tool_use("submit_design", {"_truncated": True}), submit(GOOD), accept())
    fed = fc.calls[1]["messages"][-1]["content"][0]["content"]
    assert "cut off" in fed and "shorter" in fed and d["attempts"] == 2


def test_overhang_in_the_design_is_fed_back_with_a_remedy(tmp_path):
    shelf = ("def build():\n    return {'t': union([box(-5, 5, -5, 5, 0, 20), box(-30, 30, -5, 5, 20, 24)])}")
    d, fc = run_loop(tmp_path, submit(shelf), submit(GOOD), accept())
    fed = fc.calls[1]["messages"][-1]["content"][0]["content"]
    assert "support material" in fed and "flipped" in fed          # the problem and the better orientation
    assert list(d["pieces"]) == ["plate"]
