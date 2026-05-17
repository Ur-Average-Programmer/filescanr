from __future__ import annotations
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Query, WebSocket
from fastapi.responses import PlainTextResponse

from scanner.models import ScanConfig
from api.websocket import scan_ws

LOGS_DIR = Path(__file__).parent.parent / "logs"
CONFIG_YAML_PATH = Path(__file__).parent.parent / "config.yaml"

router = APIRouter()

# These are injected by main.py after app creation
_job_manager = None
_db_store = None


def set_dependencies(job_manager, db_store, logs_dir: Path = None, bundle_dir: Path = None):
    global _job_manager, _db_store, LOGS_DIR, CONFIG_YAML_PATH
    _job_manager = job_manager
    _db_store = db_store
    if logs_dir is not None:
        LOGS_DIR = logs_dir
    if bundle_dir is not None:
        CONFIG_YAML_PATH = bundle_dir / "config.yaml"


# ── Scan Jobs ──────────────────────────────────────────────────────────────────

@router.post("/api/v1/scans", status_code=201)
def create_scan(config: ScanConfig):
    job = _job_manager.create_job(config)
    _job_manager.start_job(job)
    return {"id": job.id, "status": job.status, "name": job.name}


@router.get("/api/v1/scans")
def list_scans():
    rows = _db_store.list_jobs()
    # Merge with in-memory jobs for live stats
    live = {j.id: j for j in _job_manager.list_jobs()}
    result = []
    for row in rows:
        jid = row["id"]
        if jid in live:
            j = live[jid]
            row.update({
                "status": j.status,
                "files_scanned": j.files_scanned,
                "matches_found": j.matches_found,
                "errors_count": j.errors_count,
                "duration_seconds": j.duration_seconds,
            })
        result.append(row)
    return result


@router.get("/api/v1/scans/{job_id}")
def get_scan(job_id: str):
    job = _job_manager.get_job(job_id)
    if not job:
        row = _db_store.get_job(job_id)
        if not row:
            raise HTTPException(404, "Job not found")
        return row

    return {
        "id": job.id,
        "name": job.name,
        "status": job.status,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "files_scanned": job.files_scanned,
        "matches_found": job.matches_found,
        "errors_count": job.errors_count,
        "duration_seconds": job.duration_seconds,
        "config": job.config.model_dump() if job.config else None,
    }


@router.get("/api/v1/scans/{job_id}/results")
def get_results(
    job_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    filter: str = Query(""),
):
    job = _job_manager.get_job(job_id)
    if not job:
        row = _db_store.get_job(job_id)
        if not row:
            raise HTTPException(404, "Job not found")
    return _db_store.get_results(job_id, page=page, page_size=page_size, filter_text=filter)


@router.delete("/api/v1/scans/{job_id}", status_code=200)
def cancel_scan(job_id: str):
    cancelled = _job_manager.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(400, "Job not running or not found")
    return {"message": "Cancellation requested"}


# ── Logs ───────────────────────────────────────────────────────────────────────

@router.get("/api/v1/logs")
def list_logs():
    LOGS_DIR.mkdir(exist_ok=True)
    files = []
    for p in sorted(LOGS_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True):
        if p.is_file():
            stat = p.stat()
            files.append({
                "name": p.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
    return files


@router.get("/api/v1/logs/{filename}")
def get_log(filename: str):
    # Prevent path traversal
    safe = Path(filename).name
    path = LOGS_DIR / safe
    if not path.exists():
        raise HTTPException(404, "Log file not found")
    return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace"))


# ── Config Template ────────────────────────────────────────────────────────────

@router.get("/api/v1/config/template")
def get_config_template():
    if CONFIG_YAML_PATH.exists():
        with open(CONFIG_YAML_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


# ── Shutdown ───────────────────────────────────────────────────────────────────

@router.post("/api/v1/shutdown")
def shutdown():
    # Delay exit slightly so this HTTP response can be delivered first
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return {"message": "Shutting down"}


# ── WebSocket ──────────────────────────────────────────────────────────────────

@router.websocket("/ws/scans/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await scan_ws(websocket, job_id, _job_manager)
