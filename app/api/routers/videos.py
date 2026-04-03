from fastapi import APIRouter, File, UploadFile

from app.api.schemas.jobs import CreateJobResponse, EventsResponse
from app.application.services.video_jobs import (
    create_video_job,
    get_job_events,
    get_job_status,
    get_job_summary,
)

router = APIRouter(prefix="/videos", tags=["videos"])


@router.post("", response_model=CreateJobResponse, status_code=202)
async def upload_video(file: UploadFile = File(...)) -> CreateJobResponse:
    payload = await create_video_job(file)
    return CreateJobResponse(**payload)


@router.get("/{job_id}/status")
def get_status(job_id: str) -> dict:
    return get_job_status(job_id)


@router.get("/{job_id}/events", response_model=EventsResponse)
def get_events(job_id: str) -> EventsResponse:
    return EventsResponse(**get_job_events(job_id))


@router.get("/{job_id}/summary")
def get_summary(job_id: str) -> dict:
    return get_job_summary(job_id)

