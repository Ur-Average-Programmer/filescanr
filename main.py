from __future__ import annotations
import os
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

APP_VERSION = "1.0.0"
START_TIME = time.time()

BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="FileScanr", version=APP_VERSION)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": APP_VERSION,
        "uptime_seconds": round(time.time() - START_TIME, 1),
    }


def _bootstrap():
    LOGS_DIR.mkdir(exist_ok=True)

    from db import store as db_store
    db_store.init_db()

    from scanner.engine import JobManager
    manager = JobManager(db_store)
    manager.load_from_db()

    from api.routes import router, set_dependencies
    set_dependencies(manager, db_store)
    app.include_router(router)

    # Serve frontend as static files — must be last so API routes take precedence
    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


_bootstrap()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8443))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
