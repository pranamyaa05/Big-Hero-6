"""Build step, run as a separate process per job so a crash, a runaway boolean or a memory spike cannot take the API down.
usage: python -m app.worker JOB_DIR   (reads JOB_DIR/job.json, writes JOB_DIR/files/* and JOB_DIR/outcome.json)"""
from __future__ import annotations
import json
import logging
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path


def _limit_memory(mb: int) -> None:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (mb * 1024 * 1024, mb * 1024 * 1024))
    except Exception:
        pass


def run(job_dir: Path) -> dict:
    import numpy as np
    from .config import get_settings
    from .engine import generate, finish, GenerationError
    from .spec import BuildResult, ParamError
    job = json.loads((job_dir / "job.json").read_text())
    settings = replace(get_settings(), **job.get("settings", {}))
    _limit_memory(3072)
    out = job_dir / "files"
    ctx = job.get("context", {})
    try:
        if job["kind"] == "template":
            record = generate(job["part_id"], job.get("params"), out, settings, ctx)
        else:
            from .designer import FIT_TEST, to_manifolds
            data = np.load(job_dir / "freeform_pieces.npz")
            names = job["names"]
            solids = to_manifolds({n: (data[f"v{i}"], data[f"f{i}"]) for i, n in enumerate(names)})
            fit = solids.pop(FIT_TEST, None)
            notes = ["Designed from scratch by the AI for this request. Review the preview and check every assumed size against the real object "
                     "before printing."] + [f"Assumed: {a}" for a in job.get("assumptions", [])]
            res = BuildResult(solids, notes=notes, print_notes=job.get("print_notes", []), fit_notes=job.get("fit_notes", []))
            record = finish("custom-" + job.get("slug", "part"), job.get("title", "Custom part"), job.get("params_used") or {}, res, out, settings, ctx,
                            key_dimensions=job.get("key_dimensions"), fit_test=fit)
            (out / "design.py").write_text(job["code"])
            record["files"].append("design.py")
            record["design"] = {k: job.get(k, d) for k, d in (
                ("understanding", ""), ("assumptions", []), ("attempts", 1), ("reviewed", False), ("log", []), ("models", []), ("candidates", None),
                ("race", None), ("key_dimensions", []), ("fit_confidence", None), ("parameters", []), ("params_used", {}), ("revised_from", None),
                ("tuned_from", None), ("feedback", None), ("cached_from", None))}
            (out / "result.json").write_text(json.dumps(record, indent=2))
        return {"ok": record["ok"], "result": record}
    except (ParamError, GenerationError) as e:
        return {"ok": False, "error": str(e), "user_error": True}
    except Exception as e:                                  # unexpected: log the trace privately, show a plain message
        (job_dir / "worker.log").write_text(traceback.format_exc())
        return {"ok": False, "error": f"The part could not be built ({e.__class__.__name__}). The error was logged.", "user_error": False}


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    job_dir = Path(sys.argv[1])
    t0 = time.time()
    outcome = run(job_dir)
    outcome["seconds"] = round(time.time() - t0, 2)
    (job_dir / "outcome.json").write_text(json.dumps(outcome))


if __name__ == "__main__":
    main()
