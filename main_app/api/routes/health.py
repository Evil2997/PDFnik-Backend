# /home/dmitriy/PycharmProjects/FastAPI-Learning/main_app/api/routes/health.py
# repo: PDFnik-Backend

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from main_app.core.constants import FILES_ROOT, RUNS_DB_PATH
from main_app.core.logger import logger
from main_app.infrastructure.rabbit_connector import router as rabbit_router

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health_check() -> JSONResponse:
    """
    Returns service health status.

    Checks:
    - RabbitMQ broker connection
    - files_storage directory existence
    - SQLite runs DB accessibility

    Returns 200 if all checks pass, 503 if any check fails.
    """
    checks: dict[str, str] = {}
    healthy = True

    # RabbitMQ
    try:
        broker = rabbit_router.broker
        if broker and broker._connection:
            checks["rabbitmq"] = "ok"
        else:
            checks["rabbitmq"] = "not connected"
            healthy = False
    except Exception as e:
        checks["rabbitmq"] = f"error: {e}"
        healthy = False

    # files_storage
    try:
        if FILES_ROOT.exists() and FILES_ROOT.is_dir():
            checks["files_storage"] = "ok"
        else:
            checks["files_storage"] = "missing"
            healthy = False
    except Exception as e:
        checks["files_storage"] = f"error: {e}"
        healthy = False

    # SQLite runs DB
    try:
        if RUNS_DB_PATH.exists():
            checks["runs_db"] = "ok"
        else:
            checks["runs_db"] = "not initialized"
            # Not fatal — DB is created on first transcription
    except Exception as e:
        checks["runs_db"] = f"error: {e}"

    status_code = 200 if healthy else 503
    if not healthy:
        logger.warning("Health check failed: %s", checks)

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if healthy else "degraded",
            "checks": checks,
        },
    )
