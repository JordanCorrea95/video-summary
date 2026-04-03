from fastapi import APIRouter

from app.api.schemas.jobs import WorkerRunOnceResponse
from app.application.services.video_jobs import run_worker_once

router = APIRouter(prefix="/workers", tags=["workers"])


@router.post("/run-once", response_model=WorkerRunOnceResponse)
def run_once() -> WorkerRunOnceResponse:
    return WorkerRunOnceResponse(**run_worker_once())

