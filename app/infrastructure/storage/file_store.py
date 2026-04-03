import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import (
    DONE_DIR,
    FAILED_DIR,
    PENDING_DIR,
    PROCESSING_DIR,
    RESULTS_DIR,
    STORAGE_DIR,
)


def ensure_storage_dirs() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSING_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_dir(job_id: str) -> Path:
    return RESULTS_DIR / job_id


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def update_status(job_id: str, status: str, extra: dict[str, Any] | None = None) -> None:
    payload = {"job_id": job_id, "status": status, "updated_at": now_iso()}
    if extra:
        payload.update(extra)
    write_json(job_dir(job_id) / "status.json", payload)
