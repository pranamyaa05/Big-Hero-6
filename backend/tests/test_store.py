import os
import time
from app.store import Store


def test_create_update_get_delete(tmp_path):
    s = Store(tmp_path)
    s.create("a" * 32, "auto", {"description": "x"}, "client")
    s.update("a" * 32, status="done", plan={"part_id": None}, result={"ok": True}, error=None)
    job = s.get("a" * 32)
    assert job["status"] == "done" and job["plan"] == {"part_id": None} and job["result"] == {"ok": True} and job["request"]["description"] == "x"
    assert s.stats() == {"done": 1}
    assert s.delete("a" * 32) and s.get("a" * 32) is None and not s.delete("a" * 32)


def test_purge_removes_only_old_jobs(tmp_path):
    s = Store(tmp_path)
    s.create("o" * 32, "auto", {})
    s.create("n" * 32, "auto", {})
    s._db.execute("UPDATE jobs SET created_at='2000-01-01T00:00:00+00:00' WHERE id=?", ("o" * 32,))
    assert s.purge_older_than(14) == 1 and s.get("o" * 32) is None and s.get("n" * 32)
    assert s.purge_older_than(0) == 0
