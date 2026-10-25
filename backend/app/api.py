"""HTTP API (FastAPI)."""
from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import logging
import re
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request as HttpRequest, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from . import parts as registry
from .config import Settings, get_settings
from .clarify import clarify
from .images import ImageError, clean_image
from .measure import MeasureError, marker_svg, measure
from .jobs import JobManager, job_view
from .llm import pool_status
from .planner import Request, clean_language
from .store import Store
from .impact import ImpactInputs
from .impact_service import get_report
from .impact_research import ResearchService

log = logging.getLogger("reform3d.api")


class StorePrice(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    price_inr: float | None = Field(None, ge=0, le=1e7)
WEB = Path(__file__).resolve().parent.parent / "web"
FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
JOB_RE = re.compile(r"^[0-9a-f]{32}$")
CT = {".stl": "model/stl", ".glb": "model/gltf-binary", ".png": "image/png", ".zip": "application/zip", ".txt": "text/plain; charset=utf-8",
      ".json": "application/json", ".py": "text/plain; charset=utf-8", ".svg": "image/svg+xml"}
SVG_CSP = "default-src 'none'; style-src 'unsafe-inline'"          # our SVGs carry no script; this keeps it that way if one ever did


class MeasurementIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=60, description="What was measured, e.g. 'bottle neck diameter'.")
    value_mm: float = Field(..., gt=0, lt=1000)
    plusminus_mm: float = Field(0.0, ge=0, le=50, description="Measuring error, from POST /measure.")
    source: Literal["measured", "typed"] = Field("typed", description="measured = from a marker photo (confirmed by the user); typed = ruler or calipers.")


class AnswerIn(BaseModel):
    question: str = Field(..., max_length=300)
    answer: str = Field("", max_length=300)


class GenerateIn(BaseModel):
    description: str = Field("", max_length=2000, description="What is hard to use, in the user's words.")
    dims: str = Field("", max_length=300, description="Measurements, e.g. 'neck 50 mm'.")
    material: str = Field("", max_length=60)
    who_for: str = Field("", max_length=80)
    mode: Literal["auto", "design", "template"] = Field("auto", description="auto = the AI designs from scratch when a model is configured; design = require that; template = use a ready-made template only.")
    part_id: str | None = Field(None, max_length=60, description="Skip the AI and build this ready-made template.")
    params: dict[str, Any] | None = Field(None, description="Parameter overrides for part_id (or for the planned part).")
    measurements: list[MeasurementIn] = Field(default_factory=list, max_length=12)
    answers: list[AnswerIn] = Field(default_factory=list, max_length=5, description="Answers to the questions from POST /clarify.")
    fresh: bool = Field(False, description="Design again even if the identical request was designed before (otherwise that design is reused).")
    language: str = Field("", max_length=30, description="The person's language by name, e.g. Hindi or Kannada. The AI then writes its answers in it. Empty = English.")


class ReviseIn(BaseModel):
    feedback: str = Field(..., min_length=3, max_length=800, description="What to change, in plain words, e.g. 'make the handle 10 mm longer'.")


class TuneIn(BaseModel):
    params: dict[str, float] = Field(..., description="New values for the design's adjustable sizes (result.design.parameters).")


class BuildIn(BaseModel):
    params: dict[str, Any] | None = None
    material: str = Field("", max_length=60)
    request: str = Field("", max_length=300)


class RateLimiter:
    """Sliding window per client, in memory. Good enough for one instance; put a proxy or Redis in front for more."""
    def __init__(self, per_minute: int):
        self.per_minute, self.hits, self.lock = per_minute, defaultdict(deque), threading.Lock()

    def check(self, key: str) -> int:
        if self.per_minute <= 0:
            return 0
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return int(60 - (now - q[0])) + 1
            q.append(now)
            if len(self.hits) > 5000:
                for k in [k for k, v in self.hits.items() if not v]:
                    del self.hits[k]
        return 0


def create_app(settings: Settings | None = None, llm_client: Any = None) -> FastAPI:
    settings = settings or get_settings()
    settings.ensure_dirs()
    for why in settings.pool_skipped:
        log.warning("REFORM3D_LLM_POOL entry left out: %s", why)
    store = Store(settings.data_dir)
    jobs = JobManager(settings, store, llm_client)
    limiter = RateLimiter(settings.rate_limit_per_min)
    research = ResearchService(store, settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        removed = store.purge_older_than(settings.retention_days)
        if removed:
            log.info("purged %d old jobs", removed)
        yield
        jobs.shutdown()
        store.close()

    app = FastAPI(title="ReForm3D backend", version=__version__, lifespan=lifespan,
                  description="Turns a description, measurements or explicit parameters into print-ready STL files for accessibility parts.")
    app.state.settings, app.state.store, app.state.jobs = settings, store, jobs
    app.state.research = research
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["Content-Type", "X-API-Key", "X-Client-Id"], allow_credentials=False, max_age=600)

    def client_id(request: HttpRequest) -> str:
        fwd = request.headers.get("x-forwarded-for", "")
        ip = fwd.split(",")[0].strip() if fwd and settings.trust_proxy else (request.client.host if request.client else "?")
        return hashlib.sha256(("rf1|" + ip).encode()).hexdigest()[:16]

    def guard(request: HttpRequest) -> str:
        if settings.api_key:
            given = request.headers.get("x-api-key", "")
            if not hmac.compare_digest(given.encode(), settings.api_key.encode()):
                raise HTTPException(401, "Missing or wrong X-API-Key.")
        cid = client_id(request)
        wait = limiter.check(cid)
        if wait:
            raise HTTPException(429, f"Too many requests. Try again in {wait} seconds.", headers={"Retry-After": str(wait)})
        return request.headers.get("x-client-id", "").strip()[:128] or "anonymous"

    async def finish_or_wait(job_id: str, wait: float) -> JSONResponse:
        deadline = time.monotonic() + max(0.0, min(wait, 60.0))
        while True:
            job = store.get(job_id)
            if job["status"] in ("done", "declined", "failed") or time.monotonic() >= deadline:
                break
            await asyncio.sleep(0.2)
        code = 200 if job["status"] in ("done", "declined", "failed") else 202
        return JSONResponse(job_view(job), status_code=code, headers={"Location": f"/api/v1/jobs/{job_id}"})

    # ------------------------------------------------------------------ meta
    @app.get("/health")
    def health():
        return {"ok": True, "version": __version__, "llm": jobs.llm_available(), "design": jobs.design_available(), "provider": ("pool" if settings.uses_pool else settings.llm_provider_name) if jobs.llm_available() else None,
                "pool": pool_status(settings) if settings.uses_pool else None, "candidates": settings.design_candidates if settings.uses_pool else 1,
                "templates": len(registry.REGISTRY), "parts": len(registry.REGISTRY), "jobs": store.stats(), "history": {"store": "sqlite", "rows": store.history_count()}}

    @app.get("/api/v1/history")
    def history(limit: int = Query(50, ge=1, le=10000), cid: str = Depends(guard)):
        return {"rows": store.history(cid, limit), "total": len(store.history(cid))}

    @app.get("/api/v1/history-summaries")
    def history_summaries(limit: int = Query(50, ge=1, le=200), cid: str = Depends(guard)):
        """The few numbers each history card shows: print cost, store price (when known), carbon and time. Reports are cached, so this is cheap."""
        out = {}
        for row in store.history(cid, limit):
            if row["status"] != "done":
                continue
            try:
                simple = get_report(store, cid, row["job_id"])["report"].get("simple") or {}
            except (LookupError, ValueError):
                continue
            out[row["job_id"]] = {k: simple.get(k) for k in ("cost", "carbon", "time")}
        return out

    @app.get("/api/v1/history/{job_id}")
    def history_entry(job_id: str, cid: str = Depends(guard)):
        rows = store.history(cid, job_id=job_id)
        if not rows:
            raise HTTPException(404, "No such history entry.")
        row = rows[0]
        row["job"] = job_view(dict(id=job_id, mode="template" if row["source"] in ("template", "fallback") else "design",
                                  status=row["status"], created_at=row["created_at"], updated_at=row["created_at"],
                                  request={"description": row["request"]}, result=row["result"]))
        if not row["files_available"]:
            row["job"]["files"] = {}
        return row

    def impact_or_error(job_id: str, cid: str, report_id: str | None = None):
        try:
            return get_report(store, cid, job_id, report_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc))
        except ValueError as exc:
            raise HTTPException(409, str(exc))

    @app.post("/api/v1/history/{job_id}/research")
    async def research_impact(job_id: str, force: bool = Query(False), cid: str = Depends(guard)):
        try:
            state = await asyncio.to_thread(research.run, cid, job_id, force)
            payload = impact_or_error(job_id, cid)
            payload["research"] = state
            return payload
        except LookupError as exc:
            raise HTTPException(404, str(exc))
        except ValueError as exc:
            raise HTTPException(409, str(exc))

    @app.get("/api/v1/history/{job_id}/impact")
    def impact(job_id: str, report_id: str | None = Query(None, max_length=64), cid: str = Depends(guard)):
        payload = impact_or_error(job_id, cid, report_id)
        payload["research"] = research.state(cid, job_id)
        return payload

    @app.post("/api/v1/history/{job_id}/impact")
    def update_impact(job_id: str, body: ImpactInputs, cid: str = Depends(guard)):
        rows = store.history(cid, job_id=job_id)
        if not rows:
            raise HTTPException(404, "No such history entry.")
        if rows[0]["status"] != "done":
            raise HTTPException(409, "Impact analysis is available for completed designs only.")
        store.save_impact_input(cid, job_id, body.model_dump(exclude_unset=True))
        payload = impact_or_error(job_id, cid)
        payload["research"] = research.state(cid, job_id)
        return payload

    @app.post("/api/v1/history/{job_id}/store-price")
    def store_price(job_id: str, body: StorePrice, cid: str = Depends(guard)):
        rows = store.history(cid, job_id=job_id)
        if not rows:
            raise HTTPException(404, "No such history entry.")
        if rows[0]["status"] != "done":
            raise HTTPException(409, "Impact analysis is available for completed designs only.")
        saved = store.impact_input(cid, job_id)
        if body.price_inr is None:
            saved.pop("store_price_inr", None)
        else:
            saved["store_price_inr"] = body.price_inr
        store.save_impact_input(cid, job_id, saved)
        return impact_or_error(job_id, cid)

    @app.delete("/api/v1/history")
    def clear_history(cid: str = Depends(guard)):
        return {"deleted": store.clear_history(cid)}

    @app.get("/api/v1/stats")
    def history_stats(cid: str = Depends(guard)):
        return store.history_stats(cid)

    @app.get("/api/v1/parts")
    def list_parts():
        return {"parts": [s.to_dict() for s in registry.REGISTRY.values()]}

    @app.get("/api/v1/parts/{part_id}")
    def get_part(part_id: str):
        try:
            return registry.get(part_id).to_dict()
        except KeyError as e:
            raise HTTPException(404, str(e).strip("'\""))

    # ------------------------------------------------------------------ planning and generating
    def to_request(body: GenerateIn) -> Request:
        return Request(description=body.description.strip(), dims=body.dims.strip(), material=body.material.strip(), who_for=body.who_for.strip(),
                       measurements=[m.model_dump() for m in body.measurements], answers=[a.model_dump() for a in body.answers], language=clean_language(body.language))

    def parse_json_list(raw: str, model, limit: int, what: str) -> list[dict]:
        if not raw.strip():
            return []
        try:
            items = json.loads(raw)
            if not isinstance(items, list) or len(items) > limit:
                raise ValueError
            return [model(**i).model_dump() for i in items]
        except Exception:
            raise HTTPException(422, f"'{what}' must be a JSON list of at most {limit} items in the documented shape.")

    async def read_photos(photos: list[UploadFile]) -> list:
        files = [f for f in photos if f.filename]
        if len(files) > settings.max_photos:
            raise HTTPException(422, f"At most {settings.max_photos} photos.")
        cleaned = []
        for f in files:
            data = await f.read(int(settings.max_upload_mb * 1024 * 1024) + 1)
            if len(data) > settings.max_upload_mb * 1024 * 1024:
                raise HTTPException(413, f"Each photo must be under {settings.max_upload_mb:g} MB.")
            try:
                cleaned.append(await asyncio.to_thread(clean_image, data))
            except ImageError as e:
                raise HTTPException(422, f"{f.filename}: {e}")
        return cleaned

    async def form_request(what: str, dims: str, mat: str, who: str, measurements: str, answers: str, photos: list[UploadFile], lang: str = "") -> Request:
        if not (what.strip() or dims.strip()):
            raise HTTPException(422, "Tell us what is hard to use.")
        meas = parse_json_list(measurements, MeasurementIn, 12, "measurements")
        ans = parse_json_list(answers, AnswerIn, 5, "answers")
        return Request(description=what.strip(), dims=dims.strip(), material=mat.strip(), who_for=who.strip(), photos=await read_photos(photos),
                       measurements=meas, answers=ans, language=clean_language(lang))

    @app.post("/api/v1/plan")
    async def plan(body: GenerateIn, cid: str = Depends(guard)):
        """Template matching only (which ready-made template and values would be used). The AI design path has no separate preview step."""
        if not (body.description.strip() or body.dims.strip()):
            raise HTTPException(422, "Describe the problem or give measurements.")
        plan = await asyncio.to_thread(jobs.plan_only, to_request(body))
        out = plan.to_dict()
        if plan.part_id:
            spec = registry.get(plan.part_id)
            resolved, notes = spec.resolve(plan.params)
            out.update({"part_name": spec.name, "resolved_params": resolved, "param_notes": notes})
        return out

    @app.post("/api/v1/generate")
    async def generate(body: GenerateIn, wait: float = Query(0, ge=0, le=60), cid: str = Depends(guard)):
        if not body.part_id and not (body.description.strip() or body.dims.strip()):
            raise HTTPException(422, "Describe the problem, give measurements, or choose a part_id.")
        if body.part_id and body.part_id not in registry.REGISTRY:
            raise HTTPException(404, f"unknown part '{body.part_id}'")
        job_id = jobs.submit(to_request(body), body.mode, body.part_id, body.params, cid, fresh=body.fresh)
        return await finish_or_wait(job_id, wait)

    @app.post("/api/v1/generate/form")
    async def generate_form(wait: float = Query(0, ge=0, le=60), what: str = Form("", max_length=2000), dims: str = Form("", max_length=300),
                            mat: str = Form("", max_length=60), who: str = Form("", max_length=80), mode: Literal["auto", "design", "template"] = Form("auto"),
                            measurements: str = Form("", max_length=6000), answers: str = Form("", max_length=4000), fresh: bool = Form(False),
                            lang: str = Form("", max_length=30), photos: list[UploadFile] = File(default=[]), cid: str = Depends(guard)):
        """Same fields as the website's request form: what, dims, mat, who, up to three photos, and optionally measurements and answers as JSON lists."""
        req = await form_request(what, dims, mat, who, measurements, answers, photos, lang)
        job_id = jobs.submit(req, mode, None, None, cid, fresh=fresh)
        return await finish_or_wait(job_id, wait)

    @app.post("/api/v1/clarify")
    async def clarify_form(what: str = Form("", max_length=2000), dims: str = Form("", max_length=300), mat: str = Form("", max_length=60),
                           who: str = Form("", max_length=80), measurements: str = Form("", max_length=6000),
                           lang: str = Form("", max_length=30), photos: list[UploadFile] = File(default=[]), cid: str = Depends(guard)):
        """Before designing: up to three questions (with suggested answers) whose answers would change the design most.
        Send the answers back as `answers` with /generate. Falls back to standard questions when no model is available."""
        req = await form_request(what, dims, mat, who, measurements, "", photos, lang)
        return await asyncio.to_thread(clarify, req, settings, jobs.llm_client)

    # ------------------------------------------------------------------ measuring from a photo
    @app.get("/api/v1/marker.svg")
    def get_marker():
        """The printable measuring sheet: a 50 mm reference marker and a 100 mm check line. Print at 100 %."""
        return Response(marker_svg(), media_type="image/svg+xml", headers={"Content-Security-Policy": SVG_CSP, "Cache-Control": "public, max-age=86400",
                                                                           "Content-Disposition": 'inline; filename="reform3d-measuring-sheet.svg"'})

    @app.post("/api/v1/measure")
    async def measure_photo(photo: UploadFile = File(...), segments: str = Form(..., max_length=4000), cid: str = Depends(guard)):
        """Distances in mm between pairs of points on a photo that shows the printed marker. segments: JSON [[[x1,y1],[x2,y2]], ...] in the
        photo's pixels (as displayed, EXIF rotation applied). The photo is not stored and is not sent to any model."""
        data = await photo.read(int(settings.max_upload_mb * 1024 * 1024) + 1)
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"The photo must be under {settings.max_upload_mb:g} MB.")
        try:
            segs = json.loads(segments)
        except ValueError:
            raise HTTPException(422, "segments must be JSON: [[[x1, y1], [x2, y2]], ...]")
        try:
            return await asyncio.to_thread(measure, data, segs)
        except MeasureError as e:
            raise HTTPException(422, str(e))

    # ------------------------------------------------------------------ changing a finished design
    def base_or_error(job_id: str) -> None:
        must_job(job_id)
        try:
            jobs.base_design(job_id)
        except LookupError as e:
            raise HTTPException(409, str(e))

    @app.post("/api/v1/jobs/{job_id}/revise")
    async def revise(job_id: str, body: ReviseIn, wait: float = Query(0, ge=0, le=60), cid: str = Depends(guard)):
        """The AI changes a finished design as asked ('make it 10 mm longer', 'add a hole for a lanyard'). Creates a new job."""
        base_or_error(job_id)
        if not jobs.design_available():
            raise HTTPException(409, "AI design is not available on this server because no model is configured.")
        new_id = jobs.submit(jobs.request_of(store.get(job_id)), "revise", base=job_id, feedback=body.feedback.strip(), client=cid)
        return await finish_or_wait(new_id, wait)

    @app.post("/api/v1/jobs/{job_id}/tune")
    async def tune(job_id: str, body: TuneIn, wait: float = Query(0, ge=0, le=60), cid: str = Depends(guard)):
        """No AI: rebuild a finished design with new values for its adjustable sizes, e.g. a bigger clearance after a fit test. Creates a new job."""
        base_or_error(job_id)
        new_id = jobs.submit(jobs.request_of(store.get(job_id)), "tune", params=body.params, base=job_id, client=cid)
        return await finish_or_wait(new_id, wait)

    @app.post("/api/v1/parts/{part_id}/build")
    async def build_part(part_id: str, body: BuildIn, wait: float = Query(0, ge=0, le=60), cid: str = Depends(guard)):
        """No AI: build one ready-made template from explicit parameters (what a parameter form or slider UI calls)."""
        if part_id not in registry.REGISTRY:
            raise HTTPException(404, f"unknown part '{part_id}'")
        req = Request(description=body.request, material=body.material)
        job_id = jobs.submit(req, "template", part_id, body.params or {}, cid)
        return await finish_or_wait(job_id, wait)

    # ------------------------------------------------------------------ jobs and files
    def must_job(job_id: str) -> dict:
        if not JOB_RE.match(job_id):
            raise HTTPException(404, "No such job.")
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "No such job (it may have expired).")
        return job

    @app.get("/api/v1/jobs/{job_id}")
    def get_job(job_id: str):
        return job_view(must_job(job_id))

    @app.get("/api/v1/jobs/{job_id}/files/{name}")
    def get_file(job_id: str, name: str):
        must_job(job_id)
        if not FILE_RE.match(name):
            raise HTTPException(404, "No such file.")
        path = store.files_dir(job_id) / name
        if not path.is_file() or path.suffix.lower() not in CT:
            raise HTTPException(404, "No such file.")
        attach = path.suffix.lower() in (".stl", ".zip", ".py")
        headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"}
        if path.suffix.lower() == ".svg":
            headers["Content-Security-Policy"] = SVG_CSP
        return FileResponse(path, media_type=CT[path.suffix.lower()], filename=name if attach else None, headers=headers)

    @app.delete("/api/v1/jobs/{job_id}", status_code=204)
    def delete_job(job_id: str, request: HttpRequest):
        if settings.api_key and not hmac.compare_digest(request.headers.get("x-api-key", "").encode(), settings.api_key.encode()):
            raise HTTPException(401, "Missing or wrong X-API-Key.")
        must_job(job_id)
        store.delete(job_id)

    # ------------------------------------------------------------------ demo page
    if WEB.exists():
        app.mount("/web", StaticFiles(directory=WEB), name="web")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})
    return app
