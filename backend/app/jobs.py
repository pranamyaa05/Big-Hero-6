"""Job manager: plan (LLM or rules) in a worker thread, then build in a separate process with a hard timeout."""
from __future__ import annotations
import hashlib
import json
import logging
import shutil
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from . import parts as registry
from .config import Settings
from .designer import reset_step_listener, set_step_listener, FIT_TEST, DesignDeclined, DesignError, ModelUnavailable, FreeformError, _evaluate, check_params, design_part, extract_params, fit_confidence
from .planner import LLMPlanner, Plan, Request, RulePlanner, make_plan
from .printability import stated_material
from .spec import ParamError, slugify
from .store import Store

log = logging.getLogger("reform3d.jobs")
ROOT = Path(__file__).resolve().parent.parent


class JobManager:
    def __init__(self, settings: Settings, store: Store, llm_client: Any = None):
        self.settings, self.store, self.llm_client = settings, store, llm_client
        self.pool = ThreadPoolExecutor(max_workers=max(1, settings.workers), thread_name_prefix="rf-job")

    # ------------------------------------------------------------------ public
    def llm_available(self) -> bool:
        return bool(self.settings.enable_llm and (self.settings.llm_configured or self.llm_client))

    def design_available(self) -> bool:
        return bool(self.settings.enable_design and self.llm_available())

    def plan_only(self, req: Request) -> Plan:
        return make_plan(req, self.settings, self._llm())

    def submit(self, req: Request, mode: str = "auto", part_id: str | None = None, params: dict | None = None, client: str = "",
               base: str | None = None, feedback: str = "", fresh: bool = False) -> str:
        """mode: auto | design | template, or revise (the AI changes job `base` as `feedback` asks) or tune (rebuild job `base` with new `params`, no AI)."""
        job_id = uuid.uuid4().hex
        record = {"description": req.description, "dims": req.dims, "material": req.material, "who_for": req.who_for,
                  "photos": len(req.photos), "language": req.language, "part_id": part_id, "params": params, "measurements": req.measurements, "answers": req.answers,
                  "base": base, "feedback": feedback or None}
        self.store.create(job_id, mode, record, client)
        if mode == "tune":
            self.pool.submit(self._tune, job_id, base, params or {})
        elif mode == "revise":
            self.pool.submit(self._revise, job_id, req, base, feedback)
        else:
            self.pool.submit(self._run, job_id, req, mode, part_id, params, fresh)
        return job_id

    # ------------------------------------------------------------------ repeat cache
    @staticmethod
    def cache_key(req: Request) -> str:
        """Same words (ignoring case and spacing), same measurements, answers and photos -> same key."""
        norm = lambda t: " ".join(str(t).lower().split())
        h = hashlib.sha256()
        h.update(json.dumps([norm(req.description), norm(req.dims), norm(req.material), norm(req.who_for), req.measurements, req.answers, norm(req.language)],
                            sort_keys=True, default=str).encode())
        for _, data in req.photos:
            h.update(hashlib.sha256(data).digest())
        return h.hexdigest()[:32]

    def _cache_file(self, key: str) -> Path:
        return self.settings.data_dir / "design_cache" / key

    def _cached(self, key: str) -> str | None:
        f = self._cache_file(key)
        if not f.exists():
            return None
        base = f.read_text().strip()
        job = self.store.get(base) if len(base) == 32 else None
        d = self.store.job_dir(base) if job else None
        if job and job["status"] == "done" and (d / "job.json").exists() and (d / "freeform_pieces.npz").exists():
            return base
        f.unlink(missing_ok=True)
        return None

    def _remember(self, key: str, job_id: str) -> None:
        job = self.store.get(job_id)
        if job and job["status"] == "done":
            f = self._cache_file(key)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(job_id)

    def base_design(self, job_id: str) -> tuple[dict, dict]:
        """(store record, job.json) of a finished AI design that can be revised or tuned. Raises LookupError with a user-safe message."""
        job = self.store.get(job_id)
        if not job:
            raise LookupError("No such job (it may have expired).")
        path = self.store.job_dir(job_id) / "job.json"
        spec = json.loads(path.read_text()) if path.exists() else {}
        if job["status"] != "done" or spec.get("kind") != "design":
            raise LookupError("Only a finished AI design can be revised or tuned.")
        return job, spec

    @staticmethod
    def request_of(job: dict) -> Request:
        r = job["request"]
        return Request(description=r.get("description", ""), dims=r.get("dims", ""), material=r.get("material", ""), who_for=r.get("who_for", ""),
                       measurements=r.get("measurements") or [], answers=r.get("answers") or [], language=r.get("language", ""))

    def shutdown(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ internals
    def _llm(self) -> LLMPlanner | None:
        return LLMPlanner(self.settings, self.llm_client) if self.llm_client else None

    def _design_with_steps(self, job_id: str, plan: Plan, fn):
        """Run `fn` (a design call) while keeping a one-line 'what is happening now' in the job's plan, which the page shows under the printer."""
        base = plan.to_dict()
        def listener(text: str) -> None:
            self.store.update(job_id, plan=dict(base, step=text))
        tok = set_step_listener(listener)
        try:
            return fn()
        finally:
            reset_step_listener(tok)

    def _fail(self, job_id: str, message: str) -> None:
        self.store.update(job_id, status="failed", error=message)

    def _run(self, job_id: str, req: Request, mode: str, part_id: str | None, params: dict | None, fresh: bool = False) -> None:
        try:
            self.store.update(job_id, status="planning")
            ctx = {"request": req.description.strip(), "material": req.material or stated_material(req.description)}
            job_dir = self.store.job_dir(job_id)
            plan: Plan | None = None
            if part_id:                                                      # explicit template, no model involved
                registry.get(part_id)                                        # KeyError -> handled below
                plan = Plan(part_id, params or {}, rationale="Template and values chosen directly.", confidence=1.0, source="explicit")
            elif mode == "design" and not self.design_available():
                return self._fail(job_id, "AI design is not available on this server because no model is configured. "
                                          "Ask the operator to set a model (see the README), or use a template.")
            elif mode != "template" and self.design_available():
                plan = None                                                  # the AI designs from scratch
            else:                                                            # template mode, or auto with no model: offline matching
                plan = self.plan_only(req)
                if plan.part_id and mode == "auto":
                    plan.warnings.insert(0, "No AI model is configured on this server, so a ready-made template was used instead of a new design.")
                if not plan.part_id:
                    names = ", ".join(s.name for s in registry.REGISTRY.values())
                    why = "AI design is not set up on this server, and no ready-made template matches your description." if mode == "auto" else "No template matches your description."
                    return self._fail(job_id, f"{why} Templates available: {names}.")

            if plan is not None:
                self.store.update(job_id, plan=plan.to_dict())
                (job_dir / "job.json").write_text(json.dumps({"kind": "template", "part_id": plan.part_id, "params": plan.params, "context": ctx,
                                                              "settings": self.settings.for_worker()}))
            else:
                key = self.cache_key(req) if self.settings.design_cache else None
                base = self._cached(key) if key and not fresh else None
                if base:                                                     # identical request: reuse the design, no model call
                    job_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(self.store.job_dir(base) / "freeform_pieces.npz", job_dir / "freeform_pieces.npz")
                    spec = json.loads((self.store.job_dir(base) / "job.json").read_text())
                    spec.update({"cached_from": base, "context": ctx, "settings": self.settings.for_worker()})
                    (job_dir / "job.json").write_text(json.dumps(spec))
                    self.store.update(job_id, plan=Plan(None, rationale=spec.get("understanding", ""), confidence=1.0, source="cache",
                                                        warnings=["The same request was designed before, so that design was reused. Ask for a fresh design to get a new one."]).to_dict())
                    self.store.update(job_id, status="building")
                    self._build(job_id, job_dir)
                    return
                dplan = Plan(None, rationale="The AI is designing a new part from your description.", source="design")
                self.store.update(job_id, status="designing", plan=dplan.to_dict())
                try:
                    design = self._design_with_steps(job_id, dplan, lambda: design_part(req, self.settings, job_dir, self.llm_client))
                except ModelUnavailable as e:
                    fallback = RulePlanner().plan(req) if (mode == "auto" and self.settings.template_fallback) else None
                    if not fallback or not fallback.part_id:
                        raise
                    log.warning("job %s: no model reachable, using template %s", job_id, fallback.part_id)
                    fallback.warnings.insert(0, "The AI designers are unavailable right now (quota used up or an outage), so the closest ready-made "
                                                "template was used instead. Try again later for a design made from scratch.")
                    fallback.source = "fallback"
                    self.store.update(job_id, plan=fallback.to_dict())
                    (job_dir / "job.json").write_text(json.dumps({"kind": "template", "part_id": fallback.part_id, "params": fallback.params, "context": ctx,
                                                                  "settings": self.settings.for_worker()}))
                    self.store.update(job_id, status="building")
                    self._build(job_id, job_dir)
                    return
                self._write_design(job_id, job_dir, design, ctx)
                self.store.update(job_id, status="building")
                self._build(job_id, job_dir)
                if key:
                    self._remember(key, job_id)
                return

            self.store.update(job_id, status="building")
            self._build(job_id, job_dir)
        except KeyError as e:
            self._fail(job_id, str(e).strip("'\""))
        except DesignDeclined as e:
            self.store.update(job_id, status="declined", error=str(e))
        except (ParamError, FreeformError, DesignError) as e:
            self._fail(job_id, str(e))
        except Exception as e:
            log.exception("job %s crashed", job_id)
            self._fail(job_id, f"Something went wrong while making this part ({e.__class__.__name__}).")

    def _write_design(self, job_id: str, job_dir: Path, design: dict, ctx: dict, **extra) -> None:
        self.store.update(job_id, plan=Plan(None, rationale=design["understanding"], confidence=1.0, source="design").to_dict())
        used = design.get("params_used") or {}
        params = [{**p, "value": used.get(p["name"], p["default"])} for p in design.get("parameters") or extract_params(design["code"])]
        (job_dir / "job.json").write_text(json.dumps({
            "kind": "design", "names": list(design["pieces"]), "title": design["title"], "slug": slugify(design["title"]) or "part", "code": design["code"],
            "understanding": design["understanding"], "assumptions": design["assumptions"], "print_notes": design["print_notes"], "fit_notes": design["fit_notes"],
            "attempts": design["attempts"], "reviewed": design["reviewed"], "log": design["log"], "models": design.get("models", []),
            "candidates": design.get("candidates"), "race": design.get("race"), "key_dimensions": design.get("key_dimensions", []),
            "fit_confidence": design.get("fit_confidence"), "parameters": params, "params_used": used, "context": ctx,
            "settings": self.settings.for_worker(), **extra}))

    def _guarded(self, job_id: str, fn) -> None:
        try:
            fn()
        except DesignDeclined as e:
            self.store.update(job_id, status="declined", error=str(e))
        except (LookupError, ParamError, FreeformError, DesignError) as e:
            self._fail(job_id, str(e).strip("'\""))
        except Exception as e:
            log.exception("job %s crashed", job_id)
            self._fail(job_id, f"Something went wrong while making this part ({e.__class__.__name__}).")

    def _revise(self, job_id: str, req: Request, base: str, feedback: str) -> None:
        def work():
            job, spec = self.base_design(base)
            if not self.design_available():
                raise DesignError("AI design is not available on this server because no model is configured.")
            rplan = Plan(None, rationale="The AI is changing the design as you asked.", source="design")
            self.store.update(job_id, status="designing", plan=rplan.to_dict())
            job_dir = self.store.job_dir(job_id)
            revision = {"title": spec.get("title"), "understanding": spec.get("understanding"), "code": spec.get("code"), "feedback": feedback}
            design = self._design_with_steps(job_id, rplan, lambda: design_part(req, self.settings, job_dir, self.llm_client, revision=revision))
            self._write_design(job_id, job_dir, design, spec.get("context", {}), revised_from=base, feedback=feedback[:800])
            self.store.update(job_id, status="building")
            self._build(job_id, job_dir)
        self._guarded(job_id, work)

    def _tune(self, job_id: str, base: str, values: dict) -> None:
        """Rebuild a finished design with new values for its adjustable sizes. Runs the same sandbox and checks as the AI loop, no model call."""
        def work():
            job, spec = self.base_design(base)
            self.store.update(job_id, status="building", plan=Plan(None, rationale="Rebuilding with your new sizes (no AI involved).", source="tune").to_dict())
            code = spec["code"]
            used = {**(spec.get("params_used") or {}), **check_params(code, values)}
            job_dir = self.store.job_dir(job_id)
            job_dir.mkdir(parents=True, exist_ok=True)
            npz = job_dir / "freeform_pieces.npz"
            raw, hard, soft = _evaluate(code, self.settings, npz, used, (spec.get("context") or {}).get("material"))
            if raw is None or hard:
                raise FreeformError("With those sizes the part no longer builds or passes the print checks: " + "; ".join(hard)[:500])
            defaults = {p["name"]: p["default"] for p in extract_params(code)}
            dims = []
            for d in spec.get("key_dimensions") or []:
                d = dict(d)
                pname = d.get("parameter")
                if pname in used and pname in defaults and abs(float(d["value_mm"]) - defaults[pname]) < 1e-6:
                    d["value_mm"], d["source"], d["note"] = used[pname], "user", "set by you"
                dims.append(d)
            req = self.request_of(job)
            design = {**{k: spec.get(k) for k in ("title", "understanding", "assumptions", "print_notes", "fit_notes", "attempts", "reviewed", "log", "models")},
                      "code": code, "pieces": raw, "key_dimensions": dims, "fit_confidence": fit_confidence(dims, req), "params_used": used}
            design["log"] = (design.get("log") or []) + [{"attempt": "tune", "outcome": "rebuilt with " + ", ".join(f"{k}={v:g}" for k, v in used.items())
                                                          + ("" if not soft else "; warnings: " + "; ".join(soft)[:200])}]
            self._write_design(job_id, job_dir, design, spec.get("context", {}), tuned_from=base)
            self._build(job_id, job_dir)
        self._guarded(job_id, work)

    def _build(self, job_id: str, job_dir: Path) -> None:
        try:
            p = subprocess.run([sys.executable, "-m", "app.worker", str(job_dir)], cwd=str(ROOT), capture_output=True, text=True,
                               timeout=self.settings.job_timeout_s, env={**os.environ, "PYTHONPATH": str(ROOT)})
        except subprocess.TimeoutExpired:
            return self._fail(job_id, f"Building took longer than {self.settings.job_timeout_s:.0f} seconds and was stopped. Try simpler values.")
        outcome_path = job_dir / "outcome.json"
        if p.returncode != 0 or not outcome_path.exists():
            log.error("worker for %s failed: %s", job_id, (p.stderr or "")[-600:])
            return self._fail(job_id, "The part could not be built. The error was logged.")
        outcome = json.loads(outcome_path.read_text())
        if outcome.get("result"):
            self.store.update(job_id, result=outcome["result"])
        if outcome.get("ok"):
            self.store.update(job_id, status="done")
        else:
            errs = outcome.get("error") or "; ".join(outcome.get("result", {}).get("errors", [])) or "The part failed its print checks."
            self._fail(job_id, errs)


def job_view(job: dict, base: str = "/api/v1") -> dict:
    """The JSON the API returns for a job, with file URLs filled in."""
    jid = job["id"]
    files: dict[str, Any] = {}
    res = job.get("result")
    if res:
        u = lambda name: f"{base}/jobs/{jid}/files/{name}"
        files = {
            "stl": [{"piece": p["name"], "name": p["file"], "url": u(p["file"]), "size_mm": p["size_mm"], "volume_cm3": p["volume_cm3"], "ok": p["ok"]} for p in res["pieces"]],
            "glb": u("model.glb") if "model.glb" in res["files"] else None,
            "preview": u("preview.png") if "preview.png" in res["files"] else None,
            "zip": u("download.zip"), "readme": u("README.txt"),
            "code": u("design.py") if "design.py" in res["files"] else None,
            "drawing": u("drawing.svg") if "drawing.svg" in res["files"] else None,
            "fit_test": u("fit-test.stl") if "fit-test.stl" in res["files"] else None,
        }
    return {"id": jid, "status": job["status"], "mode": job["mode"], "created_at": job["created_at"], "updated_at": job["updated_at"],
            "request": job["request"], "plan": job.get("plan"), "result": res, "error": job.get("error"), "files": files}
