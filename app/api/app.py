from fastapi import FastAPI

from app.api.routers.videos import router as videos_router
from app.api.routers.workers import router as workers_router
from app.infrastructure.storage.file_store import ensure_storage_dirs


def create_app() -> FastAPI:
    app = FastAPI(title="Video Summary API", version="1.1.0")

    @app.on_event("startup")
    def startup() -> None:
        ensure_storage_dirs()

    app.include_router(videos_router)
    app.include_router(workers_router)
    return app


app = create_app()

