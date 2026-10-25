"""The generation pipeline: parameters -> solids -> checked meshes -> STL / GLB / preview / README / zip on disk."""
from __future__ import annotations
import io
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import trimesh

from . import parts as registry
from .config import Settings
from .geom import to_trimesh, sit
from .preview import layout, render_png
from .spec import BuildResult, ParamError, slugify
from . import slicer as slicing
from .printability import profile_for, MATERIALS
from .validate import validate_piece

DISCLAIMER = ("Sizes are nominal and come from the numbers you gave. The parts are checked by software (watertight, positive volume, size) "
              "but have not been test-printed. Measure the real object, do a test print, and adjust before relying on a part.")


class GenerationError(Exception):
    """A build failed in a way the user can act on (bad parameters, impossible geometry)."""


def _clean(tm: trimesh.Trimesh) -> trimesh.Trimesh:
    """Drop zero-volume sliver shells (a few triangles left by exact boolean contacts)."""
    comps = tm.split(only_watertight=False)
    if len(comps) <= 1:
        return tm
    keep = [c for c in comps if len(c.faces) > 8 and abs(c.volume) > 0.5]
    return trimesh.util.concatenate(keep) if len(keep) > 1 else (keep[0] if keep else tm)


def build_pieces(part_id: str, params: dict | None) -> tuple[BuildResult, dict, list[str]]:
    spec = registry.get(part_id)
    resolved, notes = spec.resolve(params)
    try:
        result = spec.build(resolved)
    except (GenerationError, ParamError):
        raise
    except Exception as e:                               # geometry or value errors from a generator
        raise GenerationError(f"{spec.name}: could not build this geometry with those values ({e})") from e
    result.notes = notes + result.notes
    return result, resolved, notes


def make_meshes(result: BuildResult, settings: Settings, material: str | None = None) -> tuple[dict[str, trimesh.Trimesh], list[dict]]:
    meshes: dict[str, trimesh.Trimesh] = {}
    reports: list[dict] = []
    bed = (settings.bed_x, settings.bed_y, settings.bed_z)
    mat = profile_for(material)
    for name, man in result.pieces.items():
        if man.is_empty():
            raise GenerationError(f"piece '{name}' came out empty; check the parameter values")
        raw = _clean(to_trimesh(man))                       # still in the solid's own coordinates, which the wall survey needs
        reports.append(validate_piece(name, man, raw, bed, mat))
        meshes[name] = sit(raw)
    return meshes, reports


def _glb(meshes: dict[str, trimesh.Trimesh]) -> bytes:
    """GLB for the web viewer: pieces laid out side by side and converted to glTF's Y-up convention."""
    scene = trimesh.Scene()
    to_y_up = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
    for (name, _), tm in zip(meshes.items(), layout(meshes)):
        t = tm.copy()
        t.apply_transform(to_y_up)
        t.visual = trimesh.visual.ColorVisuals(t, face_colors=[232, 112, 28, 255])
        scene.add_geometry(t, node_name=name, geom_name=name)
    return scene.export(file_type="glb")


TIME_FACTOR = 2.6       # measured: PrusaSlicer needs about 2.6 times the print time that plastic volume / flow rate suggests (travel, acceleration, small layers)


def estimate(meshes: dict[str, trimesh.Trimesh], material: str = "") -> dict:
    """Rough filament and print-time estimate at common settings (0.4 mm nozzle, about 1 mm of walls and skins, 20 % infill).
    Real numbers come from your slicer; this is for comparing designs and planning."""
    mat = profile_for(material)
    vol = sum(abs(float(m.volume)) for m in meshes.values())
    area = sum(float(m.area) for m in meshes.values())
    shell = min(vol, area * 1.0)
    printed = shell + 0.2 * (vol - shell)                   # mm3 of plastic actually laid down
    rate = mat.speed                                        # mm3 per second, moderate speeds
    return {"material": mat.name, "filament_g": round(printed / 1000 * mat.density, 1), "solid_g": round(vol / 1000 * mat.density, 1),
            "print_minutes": int(round(printed / rate / 60 * TIME_FACTOR + 2)),
            "assumptions": "0.4 mm nozzle, about 1 mm of walls and top/bottom skins, 20 % infill, moderate speed. Your slicer gives the real figure."}


def slice_estimate(meshes: dict, settings: Settings, material: str = "") -> dict | None:
    """Real numbers from the slicer when one is installed (else None, and the heuristic estimate stands)."""
    binary = slicing.find_slicer(settings.slicer)
    if not binary:
        return None
    mat = profile_for(material)
    bed = (settings.bed_x, settings.bed_y, settings.bed_z)
    results = slicing.slice_meshes(meshes, mat, bed, binary, settings.slicer_timeout_s)
    whole = slicing.combine(results)
    if whole is None:
        failed = next((r.error for r in results.values() if not r.ok), "")
        return {"slicer_error": failed or "the slicer did not run"}
    out = {"source": slicing.slicer_version(binary), "filament_g": round(whole.filament_g, 1), "print_minutes": int(round(whole.minutes)),
           "support_g": round(whole.support_cm3 * mat.density, 1), "support_share": whole.support_share, "layers": whole.layers,
           "assumptions": "Sliced by " + slicing.slicer_version(binary) + f" at 0.2 mm layers, 3 walls, 20 % infill, automatic supports, {mat.name} temperatures and speeds. "
                          "Your own slicer settings will differ a little."}
    warn = slicing.support_warning(whole, mat)
    if warn:
        out["support_warning"] = warn
    return out


def _readme(part_name: str, params: dict, result: BuildResult, reports: list[dict], files: list[str], context: dict) -> str:
    L = [f"{part_name}", "=" * len(part_name), "", "Made by the ReForm3D backend. Millimetres, binary STL, Z up, each piece rests flat on z = 0.", ""]
    if context.get("request"):
        L += ["Request", "-------", context["request"], ""]
    L += ["Files", "-----"] + [f"  {f}" for f in files] + [""]
    L += ["Parameters used", "---------------"] + [f"  {k}: {v}" for k, v in params.items()] + [""]
    L += ["Checks", "------"]
    for r in reports:
        status = "OK" if r["ok"] else "FAILED"
        L.append(f"  {r['name']}: {status}, {r['size_mm'][0]} x {r['size_mm'][1]} x {r['size_mm'][2]} mm, {r['volume_cm3']} cm3, {r['triangles']} triangles")
        for w in r["warnings"]:
            L.append(f"    warning: {w}")
    L.append("")
    if result.notes:
        L += ["Adjustments and notes", "---------------------"] + [f"  - {n}" for n in result.notes] + [""]
    if result.print_notes:
        L += ["How to print", "------------"] + [f"  - {n}" for n in result.print_notes] + [""]
    if context.get("material"):
        L += [f"  Material preference given: {context['material']}", ""]
    if result.fit_notes:
        L += ["Fit: match these to the real object", "-----------------------------------"] + [f"  - {n}" for n in result.fit_notes] + [""]
    L += [DISCLAIMER, ""]
    return "\n".join(L)


def generate(part_id: str, params: dict | None, out_dir: Path, settings: Settings, context: dict | None = None) -> dict:
    """Run one build and write all outputs into out_dir. Returns the JSON-able result record."""
    t0 = time.time()
    context = context or {}
    spec = registry.get(part_id)
    result, resolved, _ = build_pieces(part_id, params)
    return finish(spec.id, spec.name, resolved, result, out_dir, settings, context, t0)


def finish(part_id: str, part_name: str, resolved: dict, result: BuildResult, out_dir: Path, settings: Settings, context: dict, t0: float | None = None,
           key_dimensions: list[dict] | None = None, fit_test=None) -> dict:
    """Write every output. fit_test (optional Manifold) becomes fit-test.stl; key_dimensions feed the drawing's table."""
    t0 = t0 or time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    meshes, reports = make_meshes(result, settings, context.get("material"))
    files: list[str] = []
    piece_records = []
    for (name, tm), rep in zip(meshes.items(), reports):
        fname = f"{slugify(part_id)}.stl" if len(meshes) == 1 else f"{slugify(part_id)}-{slugify(name)}.stl"
        (out_dir / fname).write_bytes(tm.export(file_type="stl"))
        files.append(fname)
        piece_records.append({**rep, "file": fname})
    ok = all(r["ok"] for r in reports)
    (out_dir / "model.glb").write_bytes(_glb(meshes))
    files.append("model.glb")
    if settings.render_preview:
        (out_dir / "preview.png").write_bytes(render_png(meshes))
        files.append("preview.png")
    extra_zip: list[str] = []
    fit_record = None
    if fit_test is not None:
        try:
            fmeshes, freps = make_meshes(BuildResult({"fit-test": fit_test}), settings, context.get("material"))
            if freps[0]["ok"]:
                (out_dir / "fit-test.stl").write_bytes(fmeshes["fit-test"].export(file_type="stl"))
                files.append("fit-test.stl")
                extra_zip.append("fit-test.stl")
                fit_record = {"file": "fit-test.stl", "size_mm": freps[0]["size_mm"], **estimate(fmeshes, context.get("material", ""))}
        except GenerationError:
            fit_record = None
    try:
        from .drawing import drawing_svg
        (out_dir / "drawing.svg").write_text(drawing_svg(meshes, part_name, key_dimensions), encoding="utf-8")
        files.append("drawing.svg")
        extra_zip.append("drawing.svg")
    except Exception:                                       # a drawing problem must never block the printable files
        pass
    est = estimate(meshes, context.get("material", ""))
    sliced = slice_estimate(meshes, settings, context.get("material", ""))
    if sliced:
        est = {**est, **sliced}
        warn = est.pop("support_warning", None)
        if warn:
            reports[0]["warnings"].append(warn)
    readme = _readme(part_name, resolved, result, reports, [f for f in files if f.endswith(".stl")], context)
    if est.get("source"):
        readme += (f"\nSlicer estimate ({est['source']}): about {est['filament_g']} g of {est['material']}, about {est['print_minutes']} minutes, "
                   f"{est['support_g']} g of that is support. {est['assumptions']}\n")
    else:
        readme += (f"\nEstimate (rough): about {est['filament_g']} g of {est['material']}, about {est['print_minutes']} minutes. {est['assumptions']}\n")
    if fit_record:
        readme += (f"\nfit-test.stl: print this first (about {fit_record['print_minutes']} minutes). It is only the part that must fit the real object. "
                   "If it is tight or loose, change the clearance and rebuild before printing the whole part.\n")
    (out_dir / "README.txt").write_bytes(readme.encode("utf-8"))
    stls = [f for f in files if f.endswith(".stl")]
    with zipfile.ZipFile(out_dir / "download.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in stls + [f for f in extra_zip if f not in stls] + ["README.txt"]:
            z.write(out_dir / f, f)
    record = {
        "part_id": part_id, "part_name": part_name, "ok": ok, "params": resolved,
        "notes": result.notes, "print_notes": result.print_notes, "fit_notes": result.fit_notes, "derived": result.derived,
        "pieces": piece_records, "warnings": [w for r in reports for w in r["warnings"]], "errors": [e for r in reports for e in r["errors"]],
        "files": files + ["README.txt", "download.zip"], "estimate": est, "fit_test": fit_record, "disclaimer": DISCLAIMER, "seconds": round(time.time() - t0, 2),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / "result.json").write_text(json.dumps(record, indent=2))
    return record
