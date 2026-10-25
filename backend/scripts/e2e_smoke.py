"""End-to-end smoke test over HTTP against a running server:
clarify -> measure from a photo -> generate (AI design) -> tune sizes -> revise with feedback -> download files.

    python scripts/e2e_smoke.py http://localhost:8000 path/to/photo_with_marker.jpg [--design "description"]

Prints one line per step with its time and exits non-zero on the first failure. Needs a configured model for the generate and revise steps."""
import argparse
import json
import sys
import time
import zipfile
import io

import httpx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("photo", help="a photo that shows the printed 50 mm measuring marker")
    ap.add_argument("--design", default="A grip for my kitchen tap, I cannot turn the small lever knob. The lever is 14 mm wide and 40 mm long.")
    ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args()
    c = httpx.Client(base_url=a.base.rstrip("/"), timeout=60)
    t_all = time.time()

    def step(name, t0, detail=""):
        print(f"  {name:<28} {time.time() - t0:6.1f}s  {detail}", flush=True)

    def need(cond, msg):
        if not cond:
            print("FAILED:", msg)
            sys.exit(1)

    def wait(job_id, label):
        t0 = time.time()
        while time.time() - t0 < a.timeout:
            j = c.get(f"/api/v1/jobs/{job_id}").json()
            if j["status"] in ("done", "failed"):
                return j
            time.sleep(3)
        need(False, f"{label} did not finish in {a.timeout:.0f} s")

    t0 = time.time()
    h = c.get("/health").json()
    step("health", t0, f"design={h['design']} pool={h.get('pool')} templates={h['templates']}")

    t0 = time.time()
    q = c.post("/api/v1/clarify", data={"what": a.design, "who": "Weak grip or arthritis"}).json()
    need(q.get("questions"), f"clarify gave no questions: {q}")
    step("clarify", t0, f"{len(q['questions'])} questions, source={q.get('source')}")

    t0 = time.time()
    with open(a.photo, "rb") as f:
        photo = f.read()
    sys.path.insert(0, ".")
    from app.measure import find_marker, _load
    corners = find_marker(_load(photo))
    seg = [[corners[0].tolist(), corners[1].tolist()]]
    m = c.post("/api/v1/measure", files={"photo": ("p.jpg", photo, "image/jpeg")}, data={"segments": json.dumps(seg)}).json()
    mm = m["measurements"][0]["mm"]
    need(45 < mm < 55, f"the 50 mm marker side measured {mm} mm")
    step("measure (marker side)", t0, f"{mm:.1f} mm for a 50 mm side")

    t0 = time.time()
    meas = [{"label": "lever width", "value_mm": 14.0, "source": "measured", "plusminus_mm": 0.5}]
    r = c.post("/api/v1/generate", json={"description": a.design, "who_for": "Weak grip or arthritis", "mode": "design", "material": "PETG",
                                         "measurements": meas, "answers": [{"question": q["questions"][0]["question"], "answer": q["questions"][0].get("suggested", "") or "no preference"}],
                                         "fresh": True})
    need(r.status_code in (200, 202), f"generate: {r.status_code} {r.text[:200]}")
    job = wait(r.json()["id"], "generate")
    need(job["status"] == "done", f"design failed: {job.get('error')}")
    res = job["result"]
    est = res["estimate"]
    step("generate (AI design)", t0, f"{res['part_name']!r}, models={(res.get('design') or {}).get('models')}, {est.get('print_minutes')} min / {est.get('filament_g')} g {est.get('material')}, source={est.get('source', 'heuristic')}")
    need(res["ok"] and any(f.endswith(".stl") for f in res["files"]), "no STL in the result")
    need(est["material"] == "PETG", f"material was not carried through: {est['material']}")

    t0 = time.time()
    for name in ("download.zip", "README.txt", "preview.png"):
        resp = c.get(f"/api/v1/jobs/{job['id']}/files/{name}")
        need(resp.status_code == 200 and len(resp.content) > 100, f"download {name}: {resp.status_code}")
        if name == "download.zip":
            names = zipfile.ZipFile(io.BytesIO(resp.content)).namelist()
            need(any(n.endswith(".stl") for n in names) and "README.txt" in names, f"zip contents: {names}")
    step("download zip/readme/preview", t0)

    params = (res.get("design") or {}).get("parameters") or []
    if params:
        t0 = time.time()
        p0 = params[0]
        new = round(float(p0["default"]) * 1.1, 2)
        r = c.post(f"/api/v1/jobs/{job['id']}/tune", json={"params": {p0["name"]: new}})
        need(r.status_code in (200, 202), f"tune: {r.status_code} {r.text[:200]}")
        tj = wait(r.json()["id"], "tune")
        need(tj["status"] == "done", f"tune failed: {tj.get('error')}")
        step("tune (no AI)", t0, f"{p0['name']} {p0['default']} -> {new}")
    else:
        print("  tune                          skipped (the design has no adjustable sizes)")

    t0 = time.time()
    r = c.post(f"/api/v1/jobs/{job['id']}/revise", json={"feedback": "make it a little bigger overall and round every edge more"})
    need(r.status_code in (200, 202), f"revise: {r.status_code} {r.text[:200]}")
    rj = wait(r.json()["id"], "revise")
    need(rj["status"] == "done", f"revise failed: {rj.get('error')}")
    step("revise (AI)", t0, f"{rj['result']['part_name']!r}")
    print(f"ALL STEPS PASSED in {time.time() - t_all:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
