from __future__ import annotations
import json
import os
import queue
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import ScanConfig, ScanResult

LOGS_DIR = Path(__file__).parent.parent / "logs"


@dataclass
class ScanJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    status: str = "pending"   # pending/running/completed/cancelled/error
    config: Optional[ScanConfig] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    files_scanned: int = 0
    matches_found: int = 0
    errors_count: int = 0
    duration_seconds: Optional[float] = None

    # Internal
    stop_event: threading.Event = field(default_factory=threading.Event)
    progress_queue: queue.Queue = field(default_factory=queue.Queue)


def _structured_log(log_queue: queue.Queue, level: str, event: str, **extra):
    record = {"ts": datetime.now(tz=timezone.utc).isoformat(), "level": level, "event": event}
    record.update(extra)
    log_queue.put(record)


def _log_writer(log_queue: queue.Queue, log_path: Path):
    """Dedicated thread that drains the log queue and writes to file."""
    with open(log_path, "w", encoding="utf-8") as f:
        while True:
            try:
                record = log_queue.get(timeout=1.0)
                if record is None:
                    break
                f.write(json.dumps(record) + "\n")
                f.flush()
            except queue.Empty:
                continue


def _run_job(job: ScanJob, db_store):
    from .file_scanner import scan_path
    from .log_scanner import scan_system_logs, scan_windows_event_logs, scan_journald
    from .db_scanner import scan_database_logs

    job.status = "running"
    job.started_at = datetime.now(tz=timezone.utc)
    db_store.upsert_job(job)

    ts_str = job.started_at.strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"scan_{ts_str}_{job.id[:8]}.log"
    LOGS_DIR.mkdir(exist_ok=True)

    log_queue: queue.Queue = queue.Queue()
    log_thread = threading.Thread(
        target=_log_writer, args=(log_queue, log_path), daemon=True
    )
    log_thread.start()

    def slog(level, event, **kw):
        _structured_log(log_queue, level, event, **kw)

    rg_available = shutil.which("rg") is not None
    engine_name = "ripgrep" if rg_available else "python_fallback"
    slog("INFO", "scan_start", job_id=job.id, job_name=job.name, engine=engine_name)

    batch: list[ScanResult] = []

    def flush_batch():
        if batch:
            db_store.insert_results(job.id, batch)
            batch.clear()

    try:
        for source_cfg in job.config.sources:
            if not source_cfg.enabled:
                continue
            if job.stop_event.is_set():
                break

            if source_cfg.type in ("file_share", "system_log") and source_cfg.path:
                gen = (
                    scan_system_logs(source_cfg.path, job.config, stop_event=job.stop_event)
                    if source_cfg.type == "system_log"
                    else scan_path(source_cfg.path, job.config, stop_event=job.stop_event)
                )
                for result in gen:
                    if job.stop_event.is_set():
                        break

                    result.source = source_cfg.type
                    batch.append(result)
                    job.matches_found += 1
                    job.files_scanned += 1

                    slog("INFO", "file_match",
                         path=result.path,
                         matched_strings=result.match_strings,
                         line_number=result.match_line_number)

                    job.progress_queue.put({
                        "type": "match",
                        "path": result.path,
                        "filename": result.filename,
                        "match_line": result.match_line,
                        "match_line_number": result.match_line_number,
                        "match_strings": result.match_strings,
                    })

                    if len(batch) >= 500:
                        flush_batch()

                    if job.files_scanned % 1000 == 0:
                        slog("INFO", "progress",
                             files_scanned=job.files_scanned,
                             matches_found=job.matches_found)
                        job.progress_queue.put({
                            "type": "progress",
                            "files_scanned": job.files_scanned,
                            "matches_found": job.matches_found,
                            "errors_count": job.errors_count,
                            "current_path": result.path,
                        })
                        db_store.upsert_job(job)

            elif source_cfg.type == "windows_event" and source_cfg.event_channels:
                for result in scan_windows_event_logs(
                    source_cfg.event_channels, job.config, stop_event=job.stop_event
                ):
                    if job.stop_event.is_set():
                        break
                    batch.append(result)
                    job.matches_found += 1
                    job.files_scanned += 1
                    if len(batch) >= 500:
                        flush_batch()

            elif source_cfg.type == "database" and source_cfg.connection_string:
                for result in scan_database_logs(
                    source_cfg.connection_string,
                    source_cfg.log_table or "logs",
                    source_cfg.timestamp_column or "timestamp",
                    source_cfg.message_column or "message",
                    job.config,
                    stop_event=job.stop_event,
                ):
                    if job.stop_event.is_set():
                        break
                    batch.append(result)
                    job.matches_found += 1
                    job.files_scanned += 1
                    if len(batch) >= 500:
                        flush_batch()

        flush_batch()

        if job.stop_event.is_set():
            job.status = "cancelled"
            slog("INFO", "scan_cancelled",
                 files_scanned=job.files_scanned,
                 matches_found=job.matches_found)
        else:
            job.status = "completed"
            slog("INFO", "scan_complete",
                 files_scanned=job.files_scanned,
                 matches_found=job.matches_found,
                 errors_count=job.errors_count)

    except Exception as exc:
        job.status = "error"
        job.errors_count += 1
        slog("ERROR", "scan_error", error=str(exc))

    finally:
        job.completed_at = datetime.now(tz=timezone.utc)
        if job.started_at:
            job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
        db_store.upsert_job(job)

        job.progress_queue.put({
            "type": "complete",
            "status": job.status,
            "files_scanned": job.files_scanned,
            "matches_found": job.matches_found,
            "errors_count": job.errors_count,
            "duration_seconds": job.duration_seconds,
        })

        log_queue.put(None)
        log_thread.join(timeout=5)


class JobManager:
    def __init__(self, db_store):
        self._jobs: dict[str, ScanJob] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="scan-job")
        self._db = db_store

    def create_job(self, config: ScanConfig) -> ScanJob:
        job = ScanJob(name=config.name, config=config)
        with self._lock:
            self._jobs[job.id] = job
        self._db.upsert_job(job)
        return job

    def start_job(self, job: ScanJob):
        self._executor.submit(_run_job, job, self._db)

    def get_job(self, job_id: str) -> Optional[ScanJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if job and job.status == "running":
            job.stop_event.set()
            return True
        return False

    def list_jobs(self) -> list[ScanJob]:
        with self._lock:
            return list(self._jobs.values())

    def load_from_db(self):
        """Restore job metadata from DB on startup (without re-running)."""
        for row in self._db.list_jobs():
            job = ScanJob(
                id=row["id"],
                name=row["name"],
                status=row["status"],
                created_at=_parse_dt(row["created_at"]),
                started_at=_parse_dt(row.get("started_at")),
                completed_at=_parse_dt(row.get("completed_at")),
                files_scanned=row.get("files_scanned", 0),
                matches_found=row.get("matches_found", 0),
                errors_count=row.get("errors_count", 0),
                duration_seconds=row.get("duration_seconds"),
            )
            if job.status == "running":
                job.status = "error"
            with self._lock:
                self._jobs[job.id] = job


def _parse_dt(val) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val))
    except Exception:
        return None
