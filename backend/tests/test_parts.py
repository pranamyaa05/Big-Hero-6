"""Every template at its defaults and at the edge of every parameter's range must give closed, single-body, printable solids."""
import json
import pytest
from app import parts as registry
from app.config import Settings
from app.engine import build_pieces, make_meshes

SETTINGS = Settings(bed_x=220, bed_y=220, bed_z=250)


def cases(spec):
    out = [("defaults", {}),
           ("all-min", {p.name: p.min for p in spec.params if p.kind in ("float", "int")}),
           ("all-max", {p.name: p.max for p in spec.params if p.kind in ("float", "int")})]
    for p in spec.params:
        if p.kind in ("float", "int"):
            out += [(f"{p.name}=min", {p.name: p.min}), (f"{p.name}=max", {p.name: p.max})]
        elif p.kind == "bool":
            out += [(f"{p.name}=true", {p.name: True}), (f"{p.name}=false", {p.name: False})]
        elif p.kind == "enum":
            out += [(f"{p.name}={c}", {p.name: c}) for c in p.choices]
    return out


def test_registry_has_all_templates():
    assert len(registry.REGISTRY) == 36
    for spec in registry.REGISTRY.values():
        assert spec.keywords and spec.params and spec.summary
        json.dumps(spec.to_dict())                      # the API serialises this


@pytest.mark.parametrize("part_id", sorted(registry.REGISTRY))
def test_part_sweep(part_id):
    spec = registry.get(part_id)
    for label, params in cases(spec):
        result, _, _ = build_pieces(part_id, params)
        _, reports = make_meshes(result, SETTINGS)
        for r in reports:
            assert r["ok"] and r["watertight"], (part_id, label, r)
            assert r["bodies"] == 1, (part_id, label, r["name"], r["bodies"])
            assert r["volume_cm3"] > 0.05


def test_braille_tag_text_changes_the_part():
    a, _, _ = build_pieces("braille-tag", {"text": "A"})
    b, _, _ = build_pieces("braille-tag", {"text": "ABCDEFGH"})
    assert list(b.pieces.values())[0].volume() > list(a.pieces.values())[0].volume()


def test_palm_band_adjusts_and_says_so():
    result, _, _ = build_pieces("palm-band", {"palm_width": 120})
    assert result.notes or result.fit_notes
