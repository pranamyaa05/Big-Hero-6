def test_build_that_runs_too_long_is_stopped_with_a_clear_message(make_client):
    c = make_client(job_timeout_s=0.3)
    j = c.post("/api/v1/parts/palm-band/build?wait=30", json={}).json()
    assert j["status"] == "failed" and "longer than" in j["error"]
    row = c.get("/api/v1/history").json()["rows"][0]
    assert row["job_id"] == j["id"] and row["status"] == "failed"


def test_unexpected_crash_never_leaks_internals(make_client, monkeypatch):
    import app.jobs as jobs
    c = make_client()
    monkeypatch.setattr(jobs.JobManager, "_build", lambda self, jid, d: (_ for _ in ()).throw(RuntimeError("secret internals /srv/x")))
    j = c.post("/api/v1/parts/key-turner/build?wait=30", json={}).json()
    assert j["status"] == "failed" and "secret" not in j["error"] and "RuntimeError" in j["error"]


def test_worker_settings_follow_the_server(tmp_path):
    from conftest import make_settings
    s = make_settings(tmp_path, bed_x=77, render_preview=False)
    assert s.for_worker() == {"bed_x": 77, "bed_y": 220.0, "bed_z": 250.0, "render_preview": False, "slicer": "off", "slicer_in_loop": True, "slicer_timeout_s": 60.0}


def test_cli_lists_builds_and_refuses_design_without_a_model(tmp_path, capsys, monkeypatch):
    from app import cli
    monkeypatch.setenv("REFORM3D_ENABLE_LLM", "false")
    assert cli.main(["templates"]) == 0 and "wing-cap" in capsys.readouterr().out
    assert cli.main(["template", "key-turner", "-p", "key_width=12", "-o", str(tmp_path)]) == 0
    assert (tmp_path / "key-turner" / "key-turner.stl").exists()
    assert cli.main(["design", "x", "-o", str(tmp_path)]) == 2
