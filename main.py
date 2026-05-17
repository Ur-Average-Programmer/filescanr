from __future__ import annotations
import multiprocessing
import os
import sys
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

APP_VERSION = "1.0.0"
START_TIME = time.time()

# When frozen by PyInstaller (--onefile), __file__ lives inside a temp
# extraction dir (_MEIPASS) that is deleted on exit.  Bundled assets
# (frontend/, config.yaml) are in _MEIPASS; runtime data (DB, logs)
# must live next to the .exe so they survive across restarts.
if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)       # bundled read-only assets
    RUNTIME_DIR = Path(sys.executable).parent  # writable, next to .exe
else:
    BUNDLE_DIR = Path(__file__).parent
    RUNTIME_DIR = Path(__file__).parent

LOGS_DIR = RUNTIME_DIR / "logs"
FRONTEND_DIR = BUNDLE_DIR / "frontend"

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
    db_store.init_db(runtime_dir=RUNTIME_DIR)

    from scanner.engine import JobManager
    manager = JobManager(db_store, logs_dir=LOGS_DIR)
    manager.load_from_db()

    from api.routes import router, set_dependencies
    set_dependencies(manager, db_store, logs_dir=LOGS_DIR, bundle_dir=BUNDLE_DIR)
    app.include_router(router)

    # Serve frontend as static files — must be last so API routes take precedence
    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


_bootstrap()

if __name__ == "__main__":
    # Required for PyInstaller --onefile on Windows; harmless elsewhere
    multiprocessing.freeze_support()
    port = int(os.environ.get("PORT", 8443))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
