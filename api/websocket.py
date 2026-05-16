from __future__ import annotations
import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect


async def scan_ws(websocket: WebSocket, job_id: str, job_manager):
    await websocket.accept()

    job = job_manager.get_job(job_id)
    if not job:
        await websocket.send_json({"type": "error", "message": "Job not found"})
        await websocket.close()
        return

    loop = asyncio.get_event_loop()

    try:
        while True:
            # Non-blocking read from the progress queue
            try:
                msg = await loop.run_in_executor(
                    None, lambda: job.progress_queue.get(timeout=1.0)
                )
            except Exception:
                # Timeout — check if job is still running
                if job.status not in ("running", "pending"):
                    break
                continue

            await websocket.send_text(json.dumps(msg, default=str))

            if msg.get("type") == "complete":
                break

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
