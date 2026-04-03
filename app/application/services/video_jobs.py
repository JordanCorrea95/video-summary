from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from app.core.config import TMP_INPUT_DIR
from app.infrastructure.queue.file_queue import enqueue
from app.infrastructure.storage.file_store import job_dir, now_iso, read_json, update_status
from app.workers.runner import process_once


async def create_video_job(file: UploadFile) -> dict[str, str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    if not (file.content_type or "").startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video.")

    job_id = uuid.uuid4().hex
    jdir = job_dir(job_id)
    jdir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename).suffix or ".mp4"
    # Store the input video only temporarily. Results live in storage/results/{job_id}/.
    TMP_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    input_path = TMP_INPUT_DIR / f"{job_id}{suffix}"
    with input_path.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    update_status(
        job_id,
        "pending",
        {
            "created_at": now_iso(),
            "original_filename": file.filename,
        },
    )
    enqueue({"job_id": job_id, "video_path": str(input_path), "enqueued_at": now_iso()})
    return {"job_id": job_id, "status": "pending"}


def get_job_status(job_id: str) -> dict[str, Any]:
    status_path = job_dir(job_id) / "status.json"
    if not status_path.exists():
        raise HTTPException(status_code=404, detail="Job not found.")
    return read_json(status_path)


def get_job_events(job_id: str) -> dict[str, Any]:
    jdir = job_dir(job_id)
    enriched = jdir / "events_enriched.json"
    raw = jdir / "events_raw.json"
    if enriched.exists():
        return {"job_id": job_id, "events": read_json(enriched), "source": "enriched"}
    if raw.exists():
        return {"job_id": job_id, "events": read_json(raw), "source": "raw"}
    raise HTTPException(status_code=404, detail="Events not available yet.")


def get_job_summary(job_id: str) -> dict[str, Any]:
    summary_path = job_dir(job_id) / "summary.json"
    if not summary_path.exists():
        status_path = job_dir(job_id) / "status.json"
        if status_path.exists():
            raise HTTPException(status_code=202, detail=read_json(status_path))
        raise HTTPException(status_code=404, detail="Job not found.")
    return read_json(summary_path)


def run_worker_once() -> dict[str, bool]:
    return {"processed": process_once()}
