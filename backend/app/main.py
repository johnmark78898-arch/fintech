from pathlib import Path

from app.api.routes.imports import router as imports_router
from app.api.routes.public_library import router as public_library_router
from app.api.routes.recommendations import router as recommendations_router
from app.core.config import get_settings
from app.database.session import get_engine
from fastapi import FastAPI, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

settings = get_settings()
app = FastAPI(title=settings.service_name, version="0.1.0")
app.include_router(imports_router, prefix="/api/v1")
app.include_router(public_library_router, prefix="/api/v1")
app.include_router(recommendations_router, prefix="/api/v1")

DEMO_SAMPLE_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "demo"
    / "uci_online_retail_sample.csv"
)


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
def readiness(response: Response) -> dict[str, str]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except (RuntimeError, SQLAlchemyError):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready"}
    return {"status": "ready"}


@app.get("/api/v1/demo/uci-online-retail-sample.csv", tags=["demo"])
def demo_sample() -> FileResponse:
    return FileResponse(
        DEMO_SAMPLE_PATH,
        media_type="text/csv",
        filename="uci_online_retail_sample.csv",
    )
