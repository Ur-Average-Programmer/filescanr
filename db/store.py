from __future__ import annotations
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).parent.parent / "filescanr.db"

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn = conn
    return _local.conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scan_jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            config_json TEXT,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            files_scanned INTEGER DEFAULT 0,
            matches_found INTEGER DEFAULT 0,
            errors_count INTEGER DEFAULT 0,
            duration_seconds REAL
        );

        CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            path TEXT,
            filename TEXT,
            modified_ts TEXT,
            size_bytes INTEGER,
            source TEXT,
            match_line TEXT,
            match_line_number INTEGER,
            match_strings_json TEXT,
            FOREIGN KEY (job_id) REFERENCES scan_jobs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_results_job_id ON scan_results(job_id);
        CREATE INDEX IF NOT EXISTS idx_results_filename ON scan_results(filename);
    """)
    conn.commit()


def upsert_job(job) -> None:
    from scanner.models import ScanConfig

    conn = _get_conn()
    config_json = None
    if job.config:
        try:
            config_json = job.config.model_dump_json()
        except Exception:
            pass

    conn.execute("""
        INSERT INTO scan_jobs
            (id, name, status, config_json, created_at, started_at, completed_at,
             files_scanned, matches_found, errors_count, duration_seconds)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            status=excluded.status,
            started_at=excluded.started_at,
            completed_at=excluded.completed_at,
            files_scanned=excluded.files_scanned,
            matches_found=excluded.matches_found,
            errors_count=excluded.errors_count,
            duration_seconds=excluded.duration_seconds
    """, (
        job.id,
        job.name,
        job.status,
        config_json,
        _iso(job.created_at),
        _iso(job.started_at),
        _iso(job.completed_at),
        job.files_scanned,
        job.matches_found,
        job.errors_count,
        job.duration_seconds,
    ))
    conn.commit()


def insert_results(job_id: str, results: list) -> None:
    if not results:
        return
    conn = _get_conn()
    rows = [
        (
            job_id,
            r.path,
            r.filename,
            _iso(r.modified),
            r.size_bytes,
            r.source,
            r.match_line,
            r.match_line_number,
            json.dumps(r.match_strings),
        )
        for r in results
    ]
    conn.executemany("""
        INSERT INTO scan_results
            (job_id, path, filename, modified_ts, size_bytes, source,
             match_line, match_line_number, match_strings_json)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()


def list_jobs() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT id, name, status, created_at, started_at, completed_at,
               files_scanned, matches_found, errors_count, duration_seconds
        FROM scan_jobs ORDER BY created_at DESC
    """).fetchall()
    return [dict(r) for r in rows]


def get_job(job_id: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM scan_jobs WHERE id=?", (job_id,)
    ).fetchone()
    return dict(row) if row else None


def get_results(
    job_id: str,
    page: int = 1,
    page_size: int = 100,
    filter_text: str = "",
) -> dict:
    conn = _get_conn()

    base_where = "WHERE job_id=?"
    params: list[Any] = [job_id]

    if filter_text:
        base_where += " AND (path LIKE ? OR match_line LIKE ?)"
        like = f"%{filter_text}%"
        params.extend([like, like])

    total_row = conn.execute(
        f"SELECT COUNT(*) FROM scan_results {base_where}", params
    ).fetchone()
    total = total_row[0] if total_row else 0

    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT id, job_id, path, filename, modified_ts, size_bytes, source,
                   match_line, match_line_number, match_strings_json
            FROM scan_results {base_where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    ).fetchall()

    items = []
    for r in rows:
        d = dict(r)
        try:
            d["match_strings"] = json.loads(d.pop("match_strings_json") or "[]")
        except Exception:
            d["match_strings"] = []
        items.append(d)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def _iso(dt) -> Optional[str]:
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)
