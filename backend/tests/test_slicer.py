"""Slicer-in-the-loop: parsing, failure handling, and (when PrusaSlicer is installed) a real slice."""
import os
import stat
import textwrap

import pytest
from manifold3d import Manifold

from app import slicer
from app.config import Settings
from app.engine import build_pieces, finish, make_meshes, slice_estimate
from app.geom import to_trimesh, sit
from app.printability import MATERIALS
from app.spec import BuildResult
from conftest import make_settings

REAL = slicer.find_slicer("auto")
needs_slicer = pytest.mark.skipif(not REAL, reason="PrusaSlicer is not installed")

GCODE = textwrap.dedent("""\
    ;LAYER_CHANGE
    ;Z:0.2
    ;TYPE:Perimeter
    G1 X10 Y10 E100.0 F1800
    G1 E-2 F2100
    G1 E2 F2100
    G1 X20 Y10 E100.0
    ;LAYER_CHANGE
    ;Z:0.4
    ;TYPE:Support material
    G1 X10 Y10 E100.0
    G1 E2
    ;TYPE:Solid infill
    G1 X30 Y10 E100.0
    ; estimated printing time (normal mode) = 1h 2m 3s
    """)


def make_fake(tmp_path, body):
    path = tmp_path / "fake-slicer"
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def cube():
    return sit(to_trimesh(Manifold.cube([20, 20, 10])))


def test_parse_counts_printing_moves_only_and_splits_support():
    r = slicer.parse_gcode(GCODE, 1.24)
    assert r.ok and r.layers == 2
    assert r.minutes == pytest.approx(62.05, abs=0.1)
    # 4 printing moves of 100 mm: bare 'G1 E2' pushes after a retraction must not count
    area = 3.14159265 * (1.75 / 2) ** 2
    assert r.filament_cm3 == pytest.approx(400 * area / 1000, rel=0.01)
    assert r.support_share == pytest.approx(0.25, abs=0.01)
    assert r.filament_g == pytest.approx(r.filament_cm3 * 1.24, abs=0.01)


def test_empty_gcode_is_a_failure_not_a_zero():
    assert not slicer.parse_gcode("; nothing", 1.2).ok


def test_find_slicer_off_and_missing(tmp_path):
    assert slicer.find_slicer("off") is None
    assert slicer.find_slicer(str(tmp_path / "nope")) is None
    fake = make_fake(tmp_path, "exit 0")
    assert slicer.find_slicer(fake) == fake


def test_a_slicer_that_fails_or_hangs_is_reported_not_raised(tmp_path):
    stl = tmp_path / "c.stl"
    stl.write_bytes(cube().export(file_type="stl"))
    bed = (220, 220, 250)
    bad = slicer.slice_stl(stl, "pla", bed, make_fake(tmp_path, "echo 'Objects could not fit on the bed' >&2; exit 1"))
    assert not bad.ok and "rejected" in bad.error and "bed" in bad.error
    slow = slicer.slice_stl(stl, "pla", bed, make_fake(tmp_path, "sleep 5"), timeout=0.5)
    assert not slow.ok and "longer than" in slow.error
    nothing = slicer.slice_stl(stl, "pla", bed, make_fake(tmp_path, "exit 0"))
    assert not nothing.ok


def test_fake_slicer_output_flows_into_the_estimate(tmp_path):
    # the fake reads --output from its arguments and writes the sample G-code there
    fake = make_fake(tmp_path, 'while [ $# -gt 0 ]; do [ "$1" = "--output" ] && out="$2"; shift; done\ncat > "$out" <<\'EOF\'\n' + GCODE + "EOF\n")
    s = make_settings(tmp_path, slicer=fake)
    est = slice_estimate({"c": cube()}, s, "PETG")
    assert est["print_minutes"] == 62 and est["support_share"] == pytest.approx(0.25, abs=0.01)
    assert est["support_g"] > 0 and "Sliced by" in est["assumptions"]
    assert slice_estimate({"c": cube()}, make_settings(tmp_path, slicer="off")) is None


def test_support_warning_only_for_a_real_amount():
    mat = MATERIALS["pla"]
    assert slicer.support_warning(slicer.SliceResult(True, filament_cm3=10, support_cm3=3, support_share=0.3), mat)
    assert slicer.support_warning(slicer.SliceResult(True, filament_cm3=10, support_cm3=0.1, support_share=0.01), mat) is None
    assert slicer.support_warning(slicer.SliceResult(True, filament_cm3=2, support_cm3=0.4, support_share=0.2), mat) is None      # tiny absolute amount
    assert slicer.support_warning(slicer.SliceResult(False, error="x"), mat) is None


def test_combine_needs_every_piece():
    a = slicer.SliceResult(True, minutes=10, filament_cm3=2, filament_g=2.4, support_cm3=0.0, layers=5)
    b = slicer.SliceResult(True, minutes=20, filament_cm3=3, filament_g=3.6, support_cm3=1.0, layers=7)
    c = slicer.combine({"a": a, "b": b})
    assert c.minutes == 30 and c.filament_cm3 == 5 and c.support_cm3 == 1.0 and c.layers == 12
    assert slicer.combine({"a": a, "b": slicer.SliceResult(False, error="x")}) is None
    assert slicer.combine({}) is None


@needs_slicer
def test_real_slicer_on_a_block_and_a_t_shape():
    bed = (220, 220, 250)
    block = slicer.slice_meshes({"b": cube()}, "pla", bed, REAL)["b"]
    assert block.ok and block.support_cm3 == 0 and 3 < block.minutes < 60 and 0.5 < block.filament_g < 6
    t = Manifold.cube([10, 10, 20]).translate([-5, -5, 0]) + Manifold.cube([60, 10, 4]).translate([-30, -5, 20])
    tee = slicer.slice_meshes({"t": sit(to_trimesh(t))}, "pla", bed, REAL)["t"]
    assert tee.ok and tee.support_share > 0.15, tee
    tpu = slicer.slice_meshes({"b": cube()}, "tpu", bed, REAL)["b"]
    assert tpu.minutes > block.minutes                                   # flexible filament prints slower


@needs_slicer
def test_finish_uses_the_slicer_numbers_and_says_so(tmp_path):
    s = make_settings(tmp_path, slicer="auto")
    result, resolved, _ = build_pieces("cane-tip", {})
    rec = finish("cane-tip", "Cane tip", resolved, result, tmp_path / "out", s, {"request": "x", "material": "PETG"})
    assert rec["estimate"]["source"].startswith("PrusaSlicer") and rec["estimate"]["material"] == "PETG"
    assert "Slicer estimate" in (tmp_path / "out" / "README.txt").read_text()


@needs_slicer
def test_a_huge_part_is_reported_not_crashed(tmp_path):
    big = sit(to_trimesh(Manifold.cube([400, 400, 20])))
    res = slicer.slice_meshes({"x": big}, "pla", (220, 220, 250), REAL)["x"]
    assert isinstance(res, slicer.SliceResult)


@needs_slicer
def test_every_template_prints_with_modest_support_and_its_notes_tell_the_truth():
    """Slice all 36 templates at their defaults. None may need more than a quarter of its plastic as support, and a part whose print notes
    say 'no supports' must really come out with (almost) none."""
    from concurrent.futures import ThreadPoolExecutor
    from app import parts
    s = Settings(slicer="off")

    def one(pid):
        result, _, _ = build_pieces(pid, {})
        meshes, _ = make_meshes(result, s)
        res = slicer.combine(slicer.slice_meshes(meshes, "pla", (220, 220, 250), REAL))
        notes = " ".join(result.print_notes).lower()
        return pid, res, ("no supports" in notes or "without supports" in notes)

    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(one, list(parts.REGISTRY)))
    for pid, res, claims_none in rows:
        assert res is not None, f"{pid}: the slicer could not slice it"
        assert res.support_share < 0.25, f"{pid}: {res.support_share:.0%} of the plastic is support"
        if claims_none:
            assert res.support_share < 0.03, f"{pid}: its print notes say no supports but the slicer adds {res.support_share:.0%}"
