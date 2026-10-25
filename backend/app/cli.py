"""Command line: make parts without running the server.

  python -m app.cli templates                                   list the ready-made templates and their parameters
  python -m app.cli template wing-cap -p neck_diameter=50 -o out   build one template
  python -m app.cli export-all -o out                           every template at its defaults (a quick health check of the generators)
  python -m app.cli models                                      which models this server will call, and which REFORM3D_LLM_POOL entries were left out and why
  python -m app.cli design "zipper pull I cannot grip" --dims "hole 4 mm" --who "Weak grip or arthritis" --photo pull.jpg -o out
                                                                the AI designs a new part (needs a configured model, see README)"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from . import parts as registry
from .config import get_settings
from .engine import finish, generate
from .images import clean_image
from .planner import Request
from .spec import BuildResult, slugify


def _coerce(raw: str):
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return float(raw)
    except ValueError:
        return raw


def _report(rec: dict, out: Path) -> int:
    for p in rec["pieces"]:
        flag = "ok" if p["ok"] else "FAILED"
        print(f"  {p['file']}: {flag}, {' x '.join(str(x) for x in p['size_mm'])} mm, {p['volume_cm3']} cm3, bodies={p['bodies']}")
    for w in rec["warnings"] + rec["errors"]:
        print(f"  note: {w}")
    print(f"files in {out}")
    return 0 if rec["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("templates")
    sub.add_parser("models")
    t = sub.add_parser("template")
    t.add_argument("part_id")
    t.add_argument("-p", "--param", action="append", default=[], metavar="NAME=VALUE")
    t.add_argument("-o", "--out", default="out")
    e = sub.add_parser("export-all")
    e.add_argument("-o", "--out", default="out")
    d = sub.add_parser("design")
    d.add_argument("description")
    d.add_argument("--dims", default="")
    d.add_argument("--who", default="")
    d.add_argument("--material", default="")
    d.add_argument("--photo", action="append", default=[], help="up to 3 image files")
    d.add_argument("-o", "--out", default="out")
    a = ap.parse_args(argv)
    settings = get_settings()

    if a.cmd == "templates":
        for s in registry.REGISTRY.values():
            print(f"{s.id:14s} {s.name}: {s.summary}")
            for p in s.params:
                rng = f" [{p.min:g}..{p.max:g}]" if p.kind in ("float", "int") else (f" one of {p.choices}" if p.choices else "")
                print(f"    {p.name} = {p.default!r} {p.unit}{rng}")
        return 0
    if a.cmd == "models":
        models = settings.models()
        for i, m in enumerate(models, 1):
            print(f"{i}. {m.label}  ({'sees pictures' if m.vision else 'text only'})")
        for why in settings.pool_skipped:
            print(f"left out: {why}")
        if not models:
            print("no model is configured: only the ready-made templates will work")
        elif settings.uses_pool:
            print(f"design candidates: {settings.design_candidates} ({settings.design_race})")
        return 0
    if a.cmd == "template":
        params = {}
        for kv in a.param:
            k, _, v = kv.partition("=")
            params[k.strip()] = _coerce(v.strip())
        rec = generate(a.part_id, params, Path(a.out) / a.part_id, settings, {"request": "command line"})
        return _report(rec, Path(a.out) / a.part_id)
    if a.cmd == "export-all":
        bad = 0
        for pid in registry.REGISTRY:
            print(pid)
            bad += _report(generate(pid, {}, Path(a.out) / pid, settings, {}), Path(a.out) / pid)
        return 1 if bad else 0
    if a.cmd == "design":
        from .designer import DesignError, design_part
        photos = [clean_image(Path(f).read_bytes()) for f in a.photo[:3]]
        req = Request(description=a.description, dims=a.dims, who_for=a.who, material=a.material, photos=photos)
        out = Path(a.out) / "design"
        try:
            design = design_part(req, settings, out)
        except DesignError as e:
            print(f"could not design this: {e}", file=sys.stderr)
            return 2
        import numpy as np
        from .designer import to_manifolds
        from .designer import FIT_TEST
        data = np.load(out / "freeform_pieces.npz")
        pieces = to_manifolds({n: (data[f"v{i}"], data[f"f{i}"]) for i, n in enumerate(design["pieces"])})
        fit = pieces.pop(FIT_TEST, None)
        notes = [f"Assumed: {x}" for x in design["assumptions"]]
        res = BuildResult(pieces, notes=notes, print_notes=design["print_notes"], fit_notes=design["fit_notes"])
        rec = finish("custom-" + (slugify(design["title"]) or "part"), design["title"], {}, res, out, settings, {"request": a.description, "material": a.material},
                     key_dimensions=design.get("key_dimensions"), fit_test=fit)
        (out / "design.py").write_text(design["code"])
        print(design["understanding"])
        c = design.get("fit_confidence") or {}
        print(f"fit confidence: {c.get('level', 'unknown')}. {c.get('why', '')}")
        for k in design.get("key_dimensions", []):
            print(f"  {k['label']}: {k['value_mm']} mm ({k['source']}{', must fit' if k['fits_object'] else ''})")
        if design.get("parameters"):
            print("adjustable sizes: " + ", ".join(f"{p['name']}={p['default']:g}" for p in design["parameters"]))
        print(f"{design['attempts']} design pass(es), reviewed={design['reviewed']}, model: {', '.join(design.get('models', []))}")
        for c in design.get("candidates") or []:
            print(f"  candidate {c['model']}: {c['outcome']}")
        return _report(rec, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
