import json
import uuid
from pathlib import Path
from typing import Any

from app.core.config import DONE_DIR, FAILED_DIR, PENDING_DIR, PROCESSING_DIR


def enqueue(payload: dict[str, Any]) -> Path:
    job_id = payload["job_id"]
    marker_id = uuid.uuid4().hex
    marker_path = PENDING_DIR / f"{job_id}.{marker_id}.json"
    with marker_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return marker_path


def _read_marker(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def claim_next() -> tuple[Path, dict[str, Any]] | None:
    pending_markers = sorted(PENDING_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for marker in pending_markers:
        target = PROCESSING_DIR / marker.name
        try:
            marker.replace(target)
            return target, _read_marker(target)
        except FileNotFoundError:
            continue
    return None


def mark_done(processing_marker: Path) -> None:
    done_marker = DONE_DIR / processing_marker.name
    processing_marker.replace(done_marker)


def mark_failed(processing_marker: Path) -> None:
    failed_marker = FAILED_DIR / processing_marker.name
    processing_marker.replace(failed_marker)
