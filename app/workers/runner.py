from __future__ import annotations

import time
from pathlib import Path

from app.infrastructure.queue.file_queue import claim_next, mark_done, mark_failed
from app.infrastructure.storage.file_store import job_dir, update_status
from app.infrastructure.vision.pipeline import process_video_job


def process_once() -> bool:
    claimed = claim_next()
    if claimed is None:
        return False

    processing_marker, payload = claimed
    job_id = str(payload["job_id"])
    video_path = Path(payload["video_path"])
    jdir = job_dir(job_id)
    update_status(job_id, "processing", {"started_at": payload.get("enqueued_at")})

    try:
        result = process_video_job(job_id, video_path, jdir)
        update_status(job_id, "done", {"result": result})
        mark_done(processing_marker)
    except Exception as exc:
        error_msg = str(exc)
        update_status(job_id, "failed", {"error": error_msg})
        mark_failed(processing_marker)
    finally:
        # Input video is temporary by design; always attempt cleanup.
        try:
            if video_path.exists():
                video_path.unlink()
        except Exception:
            pass
    return True


def run_loop(poll_seconds: int = 2) -> None:
    while True:
        processed = process_once()
        if not processed:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run_loop()
