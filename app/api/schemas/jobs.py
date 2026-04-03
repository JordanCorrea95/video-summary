from typing import Any

from pydantic import BaseModel


class CreateJobResponse(BaseModel):
    job_id: str
    status: str


class WorkerRunOnceResponse(BaseModel):
    processed: bool


class EventsResponse(BaseModel):
    job_id: str
    source: str
    events: list[dict[str, Any]]

