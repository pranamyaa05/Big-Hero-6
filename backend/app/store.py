"""SQLite job store. One row per request; the files for a job live in data/jobs/<id>/files."""
from __future__ import annotations
import json
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from collections import Counter
import logging
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  mode TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  request_json TEXT NOT NULL,
  plan_json TEXT,
  result_json TEXT,
  error TEXT,
  client TEXT
);
CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created_at);
CREATE TABLE IF NOT EXISTS history (
 job_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, created_at TEXT NOT NULL,
 title TEXT, request TEXT, who_for TEXT, material TEXT, source TEXT,
 models TEXT, attempts INTEGER, reviewed INTEGER, design_seconds REAL,
 filament_g REAL, print_minutes REAL, size_mm TEXT, estimate_source TEXT,
 status TEXT NOT NULL, error TEXT, preview_url TEXT, zip_url TEXT, result TEXT
);
CREATE INDEX IF NOT EXISTS history_client_created ON history(client_id, created_at DESC);
CREATE TABLE IF NOT EXISTS impact_evidence (
 id TEXT NOT NULL, version TEXT NOT NULL, recorded_at TEXT NOT NULL, document TEXT NOT NULL,
 PRIMARY KEY(id, version)
);
CREATE TABLE IF NOT EXISTS impact_research (
 client_id TEXT NOT NULL, job_id TEXT NOT NULL, document TEXT NOT NULL,
 PRIMARY KEY(client_id, job_id)
);
CREATE TABLE IF NOT EXISTS impact_refresh (
 id TEXT PRIMARY KEY, attempted_at TEXT NOT NULL, status TEXT NOT NULL, message TEXT
);
CREATE TABLE IF NOT EXISTS impact_inputs (
 client_id TEXT NOT NULL, job_id TEXT NOT NULL, updated_at TEXT NOT NULL, document TEXT NOT NULL,
 PRIMARY KEY(client_id, job_id)
);
CREATE TABLE IF NOT EXISTS impact_reports (
 report_id TEXT PRIMARY KEY, client_id TEXT NOT NULL, job_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL, created_at TEXT NOT NULL, document TEXT NOT NULL,
 UNIQUE(client_id, job_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS impact_reports_owner ON impact_reports(client_id, job_id, created_at DESC);


"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        (self.data_dir / "jobs").mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.data_dir / "reform3d.db", check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)
        # Additive migration only; no changes to existing job/history rows.
        seed = Path(__file__).parent / "data" / "impact_sources.json"
        if seed.exists():
            for record in json.loads(seed.read_text()):
                self.add_evidence(record)


    def job_dir(self, job_id: str) -> Path:
        return self.data_dir / "jobs" / job_id

    def files_dir(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "files"

    def create(self, job_id: str, mode: str, request: dict, client: str = "") -> None:
        self.files_dir(job_id).mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._db.execute("INSERT INTO jobs (id,status,mode,created_at,updated_at,request_json,client) VALUES (?,?,?,?,?,?,?)",
                             (job_id, "queued", mode, now(), now(), json.dumps(request), client))

    def update(self, job_id: str, **fields) -> None:
        cols, vals = [], []
        for k, v in fields.items():
            if k in ("plan", "result"):
                k, v = k + "_json", json.dumps(v)
            cols.append(f"{k}=?")
            vals.append(v)
        cols.append("updated_at=?")
        vals += [now(), job_id]
        with self._lock:
            self._db.execute(f"UPDATE jobs SET {', '.join(cols)} WHERE id=?", vals)

        if fields.get("status") in ("done", "declined", "failed"):
            # A reporting failure must never turn a successful build into a failed job.
            try:
                self.save_history(job_id)
            except Exception:
                logging.getLogger("reform3d.history").warning("Could not save history for %s", job_id, exc_info=True)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for k in ("request_json", "plan_json", "result_json"):
            d[k[:-5]] = json.loads(d.pop(k)) if d.get(k) else None
        return d

    def delete(self, job_id: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        shutil.rmtree(self.job_dir(job_id), ignore_errors=True)
        return cur.rowcount > 0

    def purge_older_than(self, days: int) -> int:
        if days <= 0:
            return 0
        cutoff = datetime.fromtimestamp(time.time() - days * 86400, timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            ids = [r["id"] for r in self._db.execute("SELECT id FROM jobs WHERE created_at < ?", (cutoff,)).fetchall()]
        for i in ids:
            self.delete(i)
        return len(ids)

    def stats(self) -> dict:
        with self._lock:
            rows = self._db.execute("SELECT status, COUNT(*) c FROM jobs GROUP BY status").fetchall()
        return {r["status"]: r["c"] for r in rows}

    def save_history(self, job_id: str) -> None:
        job = self.get(job_id)
        if not job or job["status"] not in ("done", "declined", "failed"):
            return
        req, res, plan = job["request"] or {}, job["result"] or {}, job["plan"] or {}
        design, est = res.get("design") or {}, res.get("estimate") or {}
        source = plan.get("source")
        source = "cache" if source in ("cache", "tune") else "fallback" if source == "fallback" else "ai" if source == "design" or design else "template"
        url = f"/api/v1/jobs/{job_id}/files/"
        row = dict(job_id=job_id, client_id=job.get("client") or "anonymous", created_at=job["created_at"],
                   title=res.get("part_name") or req.get("description") or "Part request", request=req.get("description", ""),
                   who_for=req.get("who_for"), material=est.get("material") or req.get("material") or None, source=source,
                   models=json.dumps(design.get("models") or []), attempts=design.get("attempts"), reviewed=design.get("reviewed"),
                   design_seconds=max(0, (datetime.fromisoformat(job["updated_at"]) - datetime.fromisoformat(job["created_at"])).total_seconds()),
                   filament_g=est.get("filament_g"), print_minutes=est.get("print_minutes"),
                   size_mm=json.dumps([p.get("size_mm") for p in res.get("pieces", [])]),
                   estimate_source=(est.get("source") or "rough estimate") if est else None,
                   status=job["status"], error=job.get("error"),
                   preview_url=url+"preview.png" if "preview.png" in res.get("files", []) else None,
                   zip_url=url+"download.zip" if "download.zip" in res.get("files", []) else None, result=json.dumps(res))
        with self._lock:
            self._db.execute(f"INSERT OR IGNORE INTO history ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", list(row.values()))

    def history(self, client_id: str, limit: int | None = None, job_id: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM history WHERE client_id=?", [client_id]
        if job_id:
            sql += " AND job_id=?"
            args.append(job_id)
        sql += " ORDER BY created_at DESC, rowid DESC"
        if limit is not None:
            sql += " LIMIT ?"
            args.append(limit)
        with self._lock:
            rows = [dict(r) for r in self._db.execute(sql, args).fetchall()]
        for row in rows:
            for key in ("models", "size_mm", "result"):
                row[key] = json.loads(row[key]) if row[key] else None
            files = (row["result"] or {}).get("files", [])
            row["files_available"] = bool(files) and self.get(row["job_id"]) is not None and all((self.files_dir(row["job_id"]) / name).is_file() for name in files)
        return rows

    def clear_history(self, client_id: str) -> int:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._db.execute("DELETE FROM impact_research WHERE client_id=?", (client_id,))
                self._db.execute("DELETE FROM impact_reports WHERE client_id=?", (client_id,))
                self._db.execute("DELETE FROM impact_inputs WHERE client_id=?", (client_id,))
                count = self._db.execute("DELETE FROM history WHERE client_id=?", (client_id,)).rowcount
                self._db.execute("COMMIT")
                return count
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def history_count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM history").fetchone()[0]

    def history_stats(self, client_id: str) -> dict:
        rows = self.history(client_id)
        def counts(key):
            return dict(Counter(r[key] for r in rows if r.get(key)))
        def measured(key, candidates=None, average=False):
            candidates = rows if candidates is None else candidates
            valid = [r for r in candidates if isinstance(r.get(key), (int, float))]
            sliced = sum(bool(r["estimate_source"] and r["estimate_source"] != "rough estimate") for r in valid) if key != "design_seconds" else 0
            return {"value": (sum(r[key] for r in valid) / (len(valid) if average else 1)) if valid else None,
                    "rows": len(valid), "excluded": len(candidates)-len(valid), "sliced": sliced,
                    "estimated": len(valid)-sliced if key != "design_seconds" else 0,
                    "label": "recorded" if key == "design_seconds" and valid else "unavailable" if not valid else "sliced" if sliced == len(valid) else "estimated" if not sliced else "sliced and estimated"}
        today = datetime.now(timezone.utc).date()
        days = Counter(r["created_at"][:10] for r in rows)
        who = counts("who_for")
        return {"total_requests": len(rows), "statuses": counts("status"), "sources": counts("source"),
                "filament_g": measured("filament_g"), "print_minutes": measured("print_minutes"),
                "average_ai_design_seconds": measured("design_seconds", [r for r in rows if r["source"] == "ai" and r["status"] == "done"], True),
                "materials": counts("material"), "models": dict(Counter(m for r in rows for m in (r["models"] or []))),
                "who_for": who, "most_common_who_for": max(who, key=who.get) if who else None,
                "designs_per_day": [{"date": str(today-timedelta(days=i)), "count": days[str(today-timedelta(days=i))]} for i in range(13, -1, -1)]}

    def add_evidence(self, document: dict) -> str:
        from .impact_sources import validate_evidence
        from .impact import canonical, digest
        record = validate_evidence(document)
        version = digest(record)
        record["version"] = version
        with self._lock:
            self._db.execute("INSERT OR IGNORE INTO impact_evidence VALUES (?,?,?,?)",
                             (record["id"], version, now(), canonical(record)))
        return version

    def evidence_catalog(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT document FROM impact_evidence ORDER BY rowid").fetchall()
        latest = {}
        for row in rows:
            record = json.loads(row[0])
            previous = latest.get(record["id"])
            if previous is None or record["retrieved_at"] >= previous["retrieved_at"]:
                latest[record["id"]] = record
        return list(latest.values())

    def impact_input(self, client_id: str, job_id: str) -> dict:
        with self._lock:
            row = self._db.execute("SELECT document FROM impact_inputs WHERE client_id=? AND job_id=?", (client_id, job_id)).fetchone()
        return json.loads(row[0]) if row else {}

    def save_impact_input(self, client_id: str, job_id: str, document: dict) -> None:
        with self._lock:
            self._db.execute("INSERT INTO impact_inputs VALUES (?,?,?,?) ON CONFLICT(client_id,job_id) DO UPDATE SET updated_at=excluded.updated_at,document=excluded.document",
                             (client_id, job_id, now(), json.dumps(document)))

    def impact_report(self, client_id: str, job_id: str, fingerprint: str | None = None, report_id: str | None = None) -> dict | None:
        field, value = ("report_id", report_id) if report_id else ("fingerprint", fingerprint)
        with self._lock:
            row = self._db.execute(f"SELECT document FROM impact_reports WHERE client_id=? AND job_id=? AND {field}=?",
                                   (client_id, job_id, value)).fetchone()
        return json.loads(row[0]) if row else None

    def save_impact_report(self, client_id: str, job_id: str, fingerprint: str, document: dict) -> dict:
        from .impact import digest, canonical
        report_id = digest([client_id, job_id, fingerprint])
        report = dict(document, report_id=report_id, fingerprint=fingerprint, calculated_at=now())
        with self._lock:
            self._db.execute("INSERT OR IGNORE INTO impact_reports VALUES (?,?,?,?,?,?)",
                             (report_id, client_id, job_id, fingerprint, report["calculated_at"], canonical(report)))
        return self.impact_report(client_id, job_id, fingerprint=fingerprint)

    def list_impact_reports(self, client_id: str, job_id: str) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._db.execute("SELECT report_id,created_at,fingerprint FROM impact_reports WHERE client_id=? AND job_id=? ORDER BY rowid DESC", (client_id, job_id)).fetchall()]

    def record_refresh(self, evidence_id: str, status: str, message: str) -> None:
        with self._lock:
            self._db.execute("INSERT INTO impact_refresh VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET attempted_at=excluded.attempted_at,status=excluded.status,message=excluded.message",
                             (evidence_id, now(), status, message[:500]))

    def refresh_status(self) -> dict:
        with self._lock:
            return {r["id"]: dict(r) for r in self._db.execute("SELECT * FROM impact_refresh").fetchall()}

    def market_observations(self, scope: str) -> list[dict]:
        with self._lock:
            records = self._db.execute("SELECT document FROM impact_evidence ORDER BY rowid").fetchall()
        return [e for row in records if (e := json.loads(row[0])).get("scope") == scope]

    def research_state(self, client_id: str, job_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT document FROM impact_research WHERE client_id=? AND job_id=?", (client_id, job_id)).fetchone()
        return json.loads(row[0]) if row else None

    def save_research_state(self, client_id: str, job_id: str, document: dict) -> None:
        with self._lock:
            # A completed clear-history operation must not be undone by in-flight research.
            if not self._db.execute("SELECT 1 FROM history WHERE client_id=? AND job_id=?", (client_id, job_id)).fetchone():
                return
            self._db.execute("INSERT INTO impact_research VALUES (?,?,?) ON CONFLICT(client_id,job_id) DO UPDATE SET document=excluded.document",
                             (client_id, job_id, json.dumps(document, allow_nan=False)))

    def close(self) -> None:
        with self._lock:
            self._db.close()
