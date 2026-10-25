import io
import time
from PIL import Image
import pytest
from app.images import ImageError, clean_image
from conftest import make_settings
from fakes import FakeClient, accept, example_code, submit

GOOD = example_code("zipper_pull")


def jpeg_with_exif(size=(80, 60)) -> bytes:
    img = Image.new("RGB", size, (200, 120, 40))
    exif = Image.Exif()
    exif[0x010F] = "TestCamera"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def ai_client(make_client, *responses, **over):
    fc = FakeClient(*responses)
    return make_client(fc, enable_llm=True, llm_api_key="x", **over), fc


# ------------------------------------------------------------------ meta
def test_health_and_template_list(client):
    h = client.get("/health").json()
    assert h["ok"] and h["templates"] == 36 and h["design"] is False and h["llm"] is False
    parts = client.get("/api/v1/parts").json()["parts"]
    assert len(parts) == 36 and all(p["params"] for p in parts)
    assert client.get("/api/v1/parts/wing-cap").json()["id"] == "wing-cap"
    assert client.get("/api/v1/parts/nope").status_code == 404


def test_demo_page_and_client_are_served(client):
    assert "Design my part" in client.get("/").text
    assert "class ReForm3D" in client.get("/web/reform3d-client.js").text
    assert client.get("/web/vendor/three.min.js").status_code == 200


# ------------------------------------------------------------------ template path (no model)
def test_template_build_end_to_end(client):
    r = client.post("/api/v1/parts/braille-tag/build?wait=60", json={"params": {"text": "SALT"}})
    j = r.json()
    assert r.status_code == 200 and j["status"] == "done" and j["result"]["params"]["text"] == "SALT"
    stl = j["files"]["stl"][0]
    body = client.get(stl["url"])
    assert body.status_code == 200 and body.content[:5] != b"solid" and len(body.content) > 1000       # binary STL
    assert client.get(j["files"]["glb"]).content[:4] == b"glTF"
    assert client.get(j["files"]["preview"]).content[:4] == b"\x89PNG"
    import zipfile
    names = zipfile.ZipFile(io.BytesIO(client.get(j["files"]["zip"]).content)).namelist()
    assert "README.txt" in names and stl["name"] in names
    assert client.get(f"/api/v1/jobs/{j['id']}").json()["status"] == "done"


def test_parameters_are_clamped_and_reported(client):
    j = client.post("/api/v1/parts/wing-cap/build?wait=60", json={"params": {"neck_diameter": 9999}}).json()
    assert j["status"] == "done" and j["result"]["params"]["neck_diameter"] <= 200 and any("maximum" in n for n in j["result"]["notes"])


def test_bad_parameter_fails_the_job_cleanly(client):
    j = client.post("/api/v1/parts/pen-grip/build?wait=60", json={"params": {"pen_diameter": "abc"}}).json()
    assert j["status"] == "failed" and "pen_diameter" in j["error"]


def test_auto_without_a_model_uses_a_matching_template_and_says_so(client):
    j = client.post("/api/v1/generate?wait=60", json={"description": "grandma cannot twist the cap on her water bottle", "dims": "neck 50 mm"}).json()
    assert j["status"] == "done" and j["plan"]["part_id"] == "wing-cap" and "No AI model is configured" in j["plan"]["warnings"][0]


def test_auto_without_a_model_and_no_match_explains_why(client):
    j = client.post("/api/v1/generate?wait=60", json={"description": "zzzz"}).json()
    assert j["status"] == "failed" and "AI design is not set up" in j["error"]


def test_design_mode_without_a_model_fails_clearly(client):
    j = client.post("/api/v1/generate?wait=60", json={"description": "anything", "mode": "design"}).json()
    assert j["status"] == "failed" and "no model is configured" in j["error"]


def test_template_mode_no_match(client):
    j = client.post("/api/v1/generate?wait=60", json={"description": "zzzz", "mode": "template"}).json()
    assert j["status"] == "failed" and "No template matches" in j["error"]


# ------------------------------------------------------------------ AI design path (scripted model)
def test_ai_designs_a_new_part_from_scratch(make_client):
    c, fc = ai_client(make_client, submit(GOOD, title="Big zipper pull"), accept())
    j = c.post("/api/v1/generate?wait=60", json={"description": "zipper pull is tiny, I cannot grip it", "who_for": "Weak grip or arthritis"}).json()
    assert j["status"] == "done", j.get("error")
    assert j["plan"]["source"] == "design" and j["result"]["design"]["reviewed"] and j["result"]["design"]["assumptions"]
    assert j["files"]["code"] and c.get(j["files"]["code"]).text.startswith("# request")
    assert j["result"]["pieces"][0]["ok"] and j["result"]["part_id"].startswith("custom-")
    assert "Who it is for: Weak grip or arthritis" in fc.calls[0]["messages"][0]["content"][-1]["text"]
    assert c.get("/health").json()["design"] is True


def test_photos_reach_the_model_stripped_of_metadata(make_client):
    c, fc = ai_client(make_client, submit(GOOD), accept())
    files = [("photos", ("p.jpg", jpeg_with_exif(), "image/jpeg"))]
    j = c.post("/api/v1/generate/form?wait=60", data={"what": "zipper pull", "dims": "hole 4 mm", "mat": "Durable", "who": "Weak grip or arthritis"}, files=files).json()
    assert j["status"] == "done" and j["request"]["photos"] == 1
    blocks = fc.calls[0]["messages"][0]["content"]
    assert blocks[0]["type"] == "image" and blocks[0]["source"]["media_type"] == "image/jpeg"
    import base64
    sent = Image.open(io.BytesIO(base64.b64decode(blocks[0]["source"]["data"])))
    assert len(sent.getexif()) == 0
    assert "Material preference: Durable" in blocks[-1]["text"]


def test_declined_designs_keep_the_reason(make_client):
    from fakes import tool_use
    c, _ = ai_client(make_client, tool_use("decline_request", {"reason": "that is a climbing part"}))
    j = c.post("/api/v1/generate?wait=60", json={"description": "carabiner"}).json()
    assert j["status"] == "declined" and "climbing" in j["error"]
    row = c.get("/api/v1/history").json()["rows"][0]
    assert row["status"] == "declined" and "climbing" in row["error"]


def test_design_that_never_works_fails_the_job(make_client):
    bad = submit("def build():\n    return nothing_here")
    c, _ = ai_client(make_client, bad, bad, bad)
    j = c.post("/api/v1/generate?wait=60", json={"description": "x"}).json()
    assert j["status"] == "failed" and "attempt" in j["error"]


# ------------------------------------------------------------------ validation, security, limits
def test_input_validation(client):
    assert client.post("/api/v1/generate", json={}).status_code == 422
    assert client.post("/api/v1/generate", json={"description": "x" * 2001}).status_code == 422
    assert client.post("/api/v1/generate", json={"description": "x", "mode": "bogus"}).status_code == 422
    assert client.post("/api/v1/generate", json={"part_id": "nope"}).status_code == 404
    assert client.post("/api/v1/generate/form", data={"what": ""}).status_code == 422
    assert client.post("/api/v1/parts/nope/build", json={}).status_code == 404


def test_photo_rules(client):
    bad = client.post("/api/v1/generate/form", data={"what": "x"}, files=[("photos", ("a.jpg", b"not an image", "image/jpeg"))])
    assert bad.status_code == 422
    four = [("photos", (f"{i}.jpg", jpeg_with_exif(), "image/jpeg")) for i in range(4)]
    assert client.post("/api/v1/generate/form", data={"what": "x"}, files=four).status_code == 422
    with pytest.raises(ImageError):
        clean_image(b"GIF-less nonsense")


def test_oversized_photo_is_refused(make_client):
    c = make_client(max_upload_mb=0.001)
    r = c.post("/api/v1/generate/form", data={"what": "x"}, files=[("photos", ("a.jpg", jpeg_with_exif((600, 600)), "image/jpeg"))])
    assert r.status_code == 413


def test_job_ids_and_file_names_are_locked_down(client):
    j = client.post("/api/v1/parts/key-turner/build?wait=60", json={}).json()
    jid = j["id"]
    assert client.get("/api/v1/jobs/not-a-job-id").status_code == 404
    assert client.get("/api/v1/jobs/" + "0" * 32).status_code == 404
    for name in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd", "job.json", "outcome.json", ".hidden", "nope.stl"):
        assert client.get(f"/api/v1/jobs/{jid}/files/{name}").status_code == 404, name


def test_wait_returns_202_while_running(make_client):
    c = make_client(workers=1)
    j = c.post("/api/v1/parts/palm-band/build?wait=0", json={})
    assert j.status_code == 202 and j.headers["location"].endswith(j.json()["id"])
    for _ in range(120):
        s = c.get(f"/api/v1/jobs/{j.json()['id']}").json()
        if s["status"] in ("done", "failed"):
            break
        time.sleep(0.5)
    assert s["status"] == "done"


def test_api_key_is_required_when_set(make_client):
    c = make_client(api_key="s3cret")
    assert c.post("/api/v1/generate", json={"description": "x"}).status_code == 401
    assert c.post("/api/v1/generate", json={"description": "x"}, headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.post("/api/v1/parts/key-turner/build?wait=60", json={}, headers={"X-API-Key": "s3cret"}).status_code == 200
    assert c.get("/health").status_code == 200


def test_rate_limit(make_client):
    c = make_client(rate_limit_per_min=3)
    codes = [c.post("/api/v1/generate", json={"description": "zzzz"}).status_code for _ in range(5)]
    assert all(code in (200, 202) for code in codes[:3]) and codes[3:] == [429, 429]
    r = c.post("/api/v1/generate", json={"description": "zzzz"})
    assert int(r.headers["retry-after"]) >= 1


def test_delete_removes_job_and_files(client, settings):
    j = client.post("/api/v1/parts/key-turner/build?wait=60", json={}).json()
    assert (settings.data_dir / "jobs" / j["id"]).exists()
    assert client.delete(f"/api/v1/jobs/{j['id']}").status_code == 204
    assert client.get(f"/api/v1/jobs/{j['id']}").status_code == 404 and not (settings.data_dir / "jobs" / j["id"]).exists()


def test_bed_size_comes_from_settings(make_client):
    c = make_client(bed_x=50, bed_y=50, bed_z=50)
    j = c.post("/api/v1/parts/jar-grip/build?wait=60", json={}).json()
    assert j["status"] == "done" and any("larger than the configured print bed" in w for w in j["result"]["warnings"])
